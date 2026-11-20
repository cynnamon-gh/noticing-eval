"""Tests for scripts/analyze.py (BUILD_PLAN M6.4; SPEC FR-18, FR-20).

Each test was watched failing with its bug put back.
"""

import random
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import analyze as an  # noqa: E402
from noticing.bootstrap import cluster_bootstrap  # noqa: E402


def make_rows(seed=0):
    """68 core prompts x 3 versions x 2 epochs x 2 models. Versions of one prompt score alike."""
    rng = random.Random(seed)
    rows = []
    for c in range(68):
        base = rng.choice([0, 1, 2])
        for model in ("A", "B"):
            for v in "abc":
                for _ in range(2):
                    s = base if rng.random() < 0.8 else rng.choice([0, 1, 2])
                    if model == "B" and s == 2 and rng.random() < 0.4:
                        s = 1
                    rows.append({"model": model, "core_id": f"C{c}", "voice": v, "score": s,
                                 "preachy": False, "clarify_only": False, "pet_risk": c % 4 == 0,
                                 "companion_harm": c % 8 == 0})
    return rows


def test_rates_match_a_direct_count():
    """FR-18. Break: count score >= 1 as noticing, or divide by all models' answers."""
    rows = make_rows()
    [a] = [r for r in an.by_group(rows, lambda r: r["model"], n=50, full=True) if r["group"] == "A"]
    mine = [r for r in rows if r["model"] == "A"]
    assert a["noticing_rate_pct"] == round(100 * sum(r["score"] == 2 for r in mine) / len(mine), 1)
    assert a["inclusion_rate_pct"] == round(100 * sum(r["score"] >= 1 for r in mine) / len(mine), 1)
    pet = [r for r in mine if r["pet_risk"]]
    assert a["companion_harm_rate_pct"] == round(100 * sum(r["companion_harm"] for r in pet) / len(pet), 1)


def test_summed_bootstrap_equals_resampling_the_answers():
    """Summing per core prompt first must give the same interval as resampling the answers
    themselves by core prompt. Break: sum per answer version instead of per core prompt."""
    rows = make_rows()
    cl = an.cluster_sums(rows, lambda r: r["model"])
    fast = an.ci(cl, lambda c: an.rate(c, "A", "two"), n=300)
    slow = cluster_bootstrap(rows, "core_id",
                             lambda rs: sum(r["score"] == 2 for r in rs if r["model"] == "A")
                             / sum(r["model"] == "A" for r in rs), n=300)
    assert fast == pytest.approx(slow)


def test_model_gap_is_computed_inside_each_resample():
    """FR-20: a difference's interval comes from differences on the same draw, so it is narrower
    than combining the two separate intervals when versions of a prompt agree across models.
    Break: compute the gap interval from the two models' own intervals."""
    rows = make_rows()
    g = an.gap(rows, lambda r: r["model"], n=1000)
    by = {r["group"]: r for r in an.by_group(rows, lambda r: r["model"], n=1000)}
    naive_width = (by[g["highest"]]["ci_high"] - by[g["lowest"]]["ci_low"]) - \
                  (by[g["highest"]]["ci_low"] - by[g["lowest"]]["ci_high"])
    assert (g["ci_high"] - g["ci_low"]) < naive_width / 2
    assert g["ci_low"] <= g["gap_pct"] <= g["ci_high"]
