"""Tests for scripts/bias_checks.py (BUILD_PLAN M6.3; SPEC FR-17).

Correlations are checked against scipy, which the code does not use. The constructed cases have a
known answer. Each test was watched failing with its bug put back.
"""

import random
import sys
from pathlib import Path

import pytest
from scipy.stats import spearmanr

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import bias_checks as bc  # noqa: E402


@pytest.mark.parametrize("seed", range(4))
def test_spearman_matches_scipy_with_ties(seed):
    """Scores 0-2 are full of ties. Break: rank ties by position instead of averaging them."""
    rng = random.Random(seed)
    x = [rng.randint(50, 900) for _ in range(80)]
    y = [rng.choice([0, 1, 2]) for _ in range(80)]
    assert bc.spearman(x, y) == pytest.approx(spearmanr(x, y).statistic)


def length_rows(n=200, seed=0):
    """The judge's score rises with length; the human's does not."""
    rng = random.Random(seed)
    rows = []
    for i in range(n):
        words = rng.randint(100, 1000)
        rows.append({"core_id": f"C{i // 2}", "words": words,
                     "judge": 0 if words < 400 else (1 if words < 700 else 2),
                     "human": rng.choice([0, 1, 2])})
    return rows


def test_length_gap_finds_a_judge_that_favours_length():
    """Break: compute the human's correlation from the judge's scores (gap becomes 0)."""
    res = bc.length_check(length_rows(), n_boot=500)
    assert res["judge_r"] > 0.8 and abs(res["human_r"]) < 0.2
    assert res["gap_ci"][0] > 0.5  # the whole interval is well above zero


def test_length_gap_is_near_zero_when_both_follow_length_equally():
    rows = [{**r, "human": r["judge"]} for r in length_rows()]
    res = bc.length_check(rows, n_boot=500)
    assert res["gap"] == pytest.approx(0)


def family_rows():
    """J1 is one point harsher than J2 on other families' answers, and agrees with J2 on its own
    family's. Relative to its usual harshness, J1 favours its own family by one point. The
    baseline is not zero, so a check that skips it gives the wrong answer."""
    rows = []
    for i in range(60):
        own = i < 20
        j2 = 1 + i % 2
        rows.append({"core_id": f"C{i}", "own_family": own, "j2": j2, "j1": j2 if own else j2 - 1})
    return rows


assert {r["j1"] - r["j2"] for r in family_rows() if not r["own_family"]} == {-1}  # fixture adequacy


def test_own_family_difference():
    """J1 minus J2 on J1's own family, minus the same on other answers.
    Break: subtract in the other order (J2 minus J1), or skip the 'other answers' baseline."""
    res = bc.family_check(family_rows(), n_boot=500)
    assert res["own_minus_j2"] == pytest.approx(0)
    assert res["other_minus_j2"] == pytest.approx(-1)
    assert res["family_effect"] == pytest.approx(1)
    assert res["family_ci"][0] > 0


def test_position_sentence_is_in_the_report():
    """M6.3 acceptance: the report says why position bias does not apply."""
    assert "one answer" in bc.POSITION_NOTE and "order" in bc.POSITION_NOTE
