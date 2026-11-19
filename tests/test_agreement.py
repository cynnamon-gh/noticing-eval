"""Tests for noticing/bootstrap.py and scripts/agreement.py (BUILD_PLAN M6.1; SPEC FR-14–FR-16).

Kappa values are checked against scikit-learn, which the code does not use, so the tests do not
repeat the code's own arithmetic. Each test was watched failing with its bug put back.
"""

import random
import sys
from pathlib import Path

import pytest
from sklearn.metrics import cohen_kappa_score

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import agreement as ag  # noqa: E402
from noticing.bootstrap import cluster_bootstrap  # noqa: E402


@pytest.mark.parametrize("seed", range(5))
def test_weighted_kappa_matches_sklearn(seed):
    """Break: quadratic weights, or swap the two raters' marginals."""
    rng = random.Random(seed)
    a = [rng.choice([0, 1, 2]) for _ in range(60)]
    b = [x if rng.random() < 0.6 else rng.choice([0, 1, 2]) for x in a]
    assert ag.weighted_kappa(a, b) == pytest.approx(cohen_kappa_score(a, b, weights="linear"))


def test_weighted_kappa_known_case():
    """A small case worked by hand: one step apart on 1 of 4 items."""
    a, b = [0, 1, 2, 2], [0, 1, 2, 1]
    assert ag.weighted_kappa(a, b) == pytest.approx(cohen_kappa_score(a, b, weights="linear"))
    assert ag.weighted_kappa([0, 1, 2], [0, 1, 2]) == 1


@pytest.mark.parametrize("seed", range(3))
def test_flag_kappa_matches_sklearn(seed):
    rng = random.Random(seed)
    a = [rng.random() < 0.2 for _ in range(50)]
    b = [x if rng.random() < 0.8 else not x for x in a]
    assert ag.flag_kappa(a, b) == pytest.approx(cohen_kappa_score(a, b))


def test_kappa_with_no_variation_is_undefined_not_an_error():
    """clarify_only: both raters said no on all 100. Break: let the division raise."""
    assert ag.flag_kappa([False] * 10, [False] * 10) is None
    assert ag.weighted_kappa([1] * 5, [1] * 5) is None


def test_bootstrap_resamples_whole_core_prompts():
    """FR-20: resample core prompts, not single answers. Two prompts of 50 answers: one where
    rater and judge always agree, one where they never do. Resampling prompts can only give 0, 0.5
    or 1. Break: resample answers instead (then values like 0.47 appear)."""
    rows = [{"core": "A", "ok": True}] * 50 + [{"core": "B", "ok": False}] * 50
    stat = lambda rs: sum(r["ok"] for r in rs) / len(rs)  # noqa: E731
    draws = cluster_bootstrap(rows, "core", stat, n=500, seed=1, return_draws=True)[2]
    assert set(draws) <= {0.0, 0.5, 1.0} and len(set(draws)) == 3


def test_bootstrap_is_reproducible_and_brackets_the_estimate():
    rows = [{"core": f"C{i // 2}", "ok": i % 3 != 0} for i in range(100)]
    stat = lambda rs: sum(r["ok"] for r in rs) / len(rs)  # noqa: E731
    first = cluster_bootstrap(rows, "core", stat, n=1000, seed=7)
    assert first == cluster_bootstrap(rows, "core", stat, n=1000, seed=7)
    lo, hi = first
    assert lo < stat(rows) < hi


def test_bootstrap_skips_undefined_draws_and_says_how_many():
    """A resample with no variation gives kappa None; it is dropped and counted, not crashed on."""
    rows = [{"core": "A", "x": 1}] * 10 + [{"core": "B", "x": 2}] * 10
    stat = lambda rs: None if len({r["x"] for r in rs}) == 1 else 1.0  # noqa: E731
    lo, hi, draws, dropped = cluster_bootstrap(rows, "core", stat, n=200, seed=3,
                                               return_draws=True, return_dropped=True)
    assert dropped > 0 and len(draws) == 200 - dropped


def make_rows():
    """Six labelled answers: agreements, one-step and two-step disagreements, one comment."""
    base = {"prompt": "p", "note": "n", "answer": "THE ANSWER TEXT", "rationale": "WHY",
            "model": "m", "preachy_c": False, "preachy_j": False, "harm_c": None, "harm_j": None,
            "clarify_c": False, "clarify_j": False, "pet_risk": False}
    pairs = [(0, 0), (1, 1), (2, 2), (0, 1), (2, 0), (1, 1)]
    rows = [{**base, "label_id": f"L{i}", "core_id": f"C{i}", "score_c": c, "score_j": j,
             "comment": "odd one" if i == 5 else ""} for i, (c, j) in enumerate(pairs)]
    return rows


def test_every_disagreement_is_listed_with_answer_scores_and_rationale():
    """FR-16. Break: list only two-step disagreements, or drop the answer text."""
    text = ag.disagreements_md(make_rows())
    assert text.count("### L") == 2  # L3 (0 vs 1) and L4 (2 vs 0)
    for must in ("THE ANSWER TEXT", "WHY", "L3", "L4"):
        assert must in text
    assert "### L0" not in text


def test_comments_on_agreed_labels_are_listed_too():
    """Cynthia's comments are read even where she agreed. Break: list comments only on
    disagreements."""
    assert "odd one" in ag.disagreements_md(make_rows())


def test_agreement_within_each_judge_score():
    """FR-15: agreement within each judge-score group. Break: group by Cynthia's score."""
    groups = ag.within_judge_score(make_rows())
    assert groups == {0: (1, 2), 1: (2, 3), 2: (1, 1)}


# --- Reviewed labels: corrections made after seeing the disagreements --------------------------

def test_reviewed_labels_give_a_second_number_and_leave_the_headline_alone():
    """FR-14: the headline uses the labels as first given. A correction made after seeing the judge
    goes in a separate file and is reported as a second, marked number.
    Break: apply the corrections to the headline rows."""
    rows = make_rows()
    reviewed = {"L4": {"score_before": 2, "score_after": 0, "reason": "slip"}}
    before = ag.agreement_md(rows)
    text = ag.agreement_md(rows, reviewed=reviewed)
    assert ag.same_share(rows) == 4 / 6  # unchanged input
    assert text.split("## After Cynthia's review")[0].rstrip() == before.rstrip()
    after = text.split("## After Cynthia's review")[1]
    assert "5 of 6" in after and "L4" in after and "slip" in after


def test_reviewed_label_must_match_the_original():
    """A correction whose 'before' score is not the label on file is refused.
    Break: skip the check."""
    with pytest.raises(ValueError, match="L4"):
        ag.apply_review(make_rows(), {"L4": {"score_before": 1, "score_after": 0, "reason": "x"}})
