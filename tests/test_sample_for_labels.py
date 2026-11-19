"""Tests for scripts/sample_for_labels.py (BUILD_PLAN M5.1; SPEC FR-13).

The pool has the shape of the full run (8 models x 68 core prompts x 3 versions x 2 epochs) and
the conditions that make sampling hard, taken from the real run: one model with very few 2s
(GPT-6.2 had 30 of 408; here 3), and preachy answers that occur in only one model (Llama 8B had
all 4). Each test was watched failing with its rule removed from the sampler.
"""

import json
import random
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import sample_for_labels as sl  # noqa: E402

MODELS = [f"m{i}" for i in range(8)]
FEW_TWOS, PREACHY_MODEL = "m0", "m7"


def make_pool():
    rng = random.Random(1)
    pool = []
    for m in MODELS:
        for c in range(68):
            for v in "abc":
                for epoch in (1, 2):
                    score = rng.choice([0, 0, 1, 1] if m == FEW_TWOS else [0, 1, 1, 2])
                    pool.append({"model": m, "sample_id": f"C{c}.{v}", "core_id": f"C{c}",
                                 "epoch": epoch, "prompt": f"prompt {c}{v}", "note": f"note {c}",
                                 "answer": f"answer {m} {c}{v} {epoch}\n  with  spacing ",
                                 "pet_risk": c % 3 == 0, "score": score, "preachy": False,
                                 "companion_harm": None, "clarify_only": False,
                                 "rationale": "r", "judge_model": "j"})
    fews = [r for r in pool if r["model"] == FEW_TWOS]
    for r in fews[7::60][:3]:  # 3 different core prompts, none shared with a preachy answer
        r["score"] = 2
    for r in [r for r in pool if r["model"] == PREACHY_MODEL][::100][:4]:
        r["preachy"] = True
    return pool


POOL = make_pool()
# fixture adequacy: the hard conditions are really in the pool
assert sum(r["score"] == 2 for r in POOL if r["model"] == FEW_TWOS) == 3
assert sum(r["preachy"] for r in POOL) == 4
assert {r["model"] for r in POOL if r["preachy"]} == {PREACHY_MODEL}
assert len({r["core_id"] for r in POOL if r["model"] == FEW_TWOS and r["score"] == 2}
           - {r["core_id"] for r in POOL if r["preachy"]}) == 3  # the cap can't block the scarce 2s


def draw(seed=20261119):
    return sl.draw(POOL, n=100, seed=seed)


def test_draws_100_spread_evenly_across_models():
    """Break: take the first 100 candidates, or quota every model at 12 (= 96)."""
    got = draw()
    assert len(got) == 100
    counts = Counter(r["model"] for r in got)
    assert set(counts) == set(MODELS) and set(counts.values()) == {12, 13}


def test_every_preachy_answer_is_included():
    """FR-13 over-samples preachy; with 4 in the whole run, take all of them.
    Break: drop the must-include step."""
    assert sum(r["preachy"] for r in draw()) == 4


def test_scores_are_balanced_not_proportional():
    """FR-13 over-samples score 2. Target is equal thirds per model; a model short of 2s takes all
    it has and fills from the other scores. Break: sample each model at random (proportional)."""
    got = draw()
    by = Counter(r["score"] for r in got)
    assert all(30 <= by[s] <= 37 for s in (0, 1, 2)), by
    assert sum(r["score"] == 2 for r in got if r["model"] == FEW_TWOS) == 3


def test_at_most_two_answers_per_core_prompt():
    """Spread over prompts, so a few prompts can't dominate agreement.
    Break: drop the per-prompt cap."""
    assert max(Counter(r["core_id"] for r in draw()).values()) <= sl.MAX_PER_CORE


def test_same_seed_same_sample_and_different_seed_differs():
    key = lambda rs: [(r["model"], r["sample_id"], r["epoch"]) for r in rs]  # noqa: E731
    assert key(draw()) == key(draw())
    assert key(draw(1)) != key(draw(2))


def test_order_is_shuffled_not_grouped_by_model():
    """Cynthia must not see answers grouped by model. Break: return the draw unshuffled."""
    models = [r["model"] for r in draw()]
    runs = sum(1 for a, b in zip(models, models[1:]) if a != b)
    assert runs > 50, "answers look grouped by model"


def test_sample_file_hides_model_and_judge(tmp_path):
    """FR-13: the labelling page sees only what Cynthia may see. Break: write the whole record."""
    sample, key = tmp_path / "s.jsonl", tmp_path / "k.jsonl"
    sl.write_files(draw(), sample, key)
    rows = [json.loads(x) for x in sample.read_text().splitlines()]
    assert all(set(r) == sl.SAMPLE_FIELDS for r in rows)
    text = sample.read_text()
    assert '"m0"' not in text and "rationale" not in text and "judge" not in text


def test_key_matches_sample_one_to_one_and_answers_are_unchanged(tmp_path):
    """Break: strip() the answer when writing, or number label IDs separately in the two files."""
    got = draw()
    sample, key = tmp_path / "s.jsonl", tmp_path / "k.jsonl"
    sl.write_files(got, sample, key)
    s = [json.loads(x) for x in sample.read_text().splitlines()]
    k = {r["label_id"]: r for r in map(json.loads, key.read_text().splitlines())}
    assert len(s) == len(k) == 100 and len({r["label_id"] for r in s}) == 100
    src = {(r["model"], r["sample_id"], r["epoch"]): r for r in POOL}
    for row in s:
        kr = k[row["label_id"]]
        orig = src[(kr["model"], kr["sample_id"], kr["epoch"])]
        assert row["answer"] == orig["answer"] and row["prompt"] == orig["prompt"]
        assert kr["score"] == orig["score"]
