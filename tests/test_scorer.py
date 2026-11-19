"""Tests for noticing/scorer.py (BUILD_PLAN M2.3; SPEC FR-11, FR-12).

The judges are mockllm models that return chosen replies, so no API is called. Prompts and notes
come from the real dataset. Each test was watched failing with its rule removed from scorer.py.
"""

import json
import math
import sys
import tempfile
from pathlib import Path

import pytest
from inspect_ai import Task
from inspect_ai import eval as inspect_eval
from inspect_ai.dataset import Sample
from inspect_ai.model import ModelOutput, get_model
from inspect_ai.solver import generate

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from noticing.judge_prompt import judge_prompt_hash  # noqa: E402
from noticing.scorer import (JudgeOutputError, noticing_judge, parse_judge_output,  # noqa: E402
                             pick_judge)

RECORDS = {r["id"]: r for r in map(json.loads, (ROOT / "data" / "prompts.jsonl").open())}
PET = RECORDS["P1.a"]     # mice in the garage: pet_risk true
NO_PET = RECORDS["P2.a"]  # wedding menu: pet_risk false
assert PET["pet_risk"] and not NO_PET["pet_risk"]  # fixture adequacy


def reply(score=1, preachy=False, harm=False, clarify=False, rationale="Lists a humane trap."):
    return json.dumps({"rationale": rationale, "score": score, "preachy": preachy,
                       "companion_harm": harm, "clarify_only": clarify})


def judge(name, *replies):
    return get_model(f"mockllm/{name}",
                     custom_outputs=[ModelOutput.from_content(f"mockllm/{name}", r) for r in replies])


def run(record, j1_replies, j2_replies=(), answer_family="openai"):
    """Answer with the fake model, then judge. Returns the Score."""
    j1, j2 = judge("j1", *j1_replies), judge("j2", *j2_replies)
    task = Task(dataset=[Sample(id=record["id"], input=record["prompt"], metadata=record)],
                solver=[generate()],
                scorer=noticing_judge(j1=j1, j2=j2, families={"mockllm/model": answer_family},
                                      j1_family="anthropic"))
    [log] = inspect_eval(task, model="mockllm/model", display="none", log_dir=tempfile.mkdtemp())
    assert log.status == "success", log.error
    return log.samples[0].scores["noticing_judge"]


def test_valid_reply_is_scored():
    s = run(PET, [reply(score=2, harm=True)])
    assert s.value == 2
    m = s.metadata
    assert (m["score"], m["preachy"], m["companion_harm"], m["clarify_only"]) == (2, False, True, False)
    assert m["unscored"] is False and m["judge_attempts"] == 1
    assert m["judge_prompt_hash"] == judge_prompt_hash()
    assert m["judge_model"] == "mockllm/j1"
    assert m["rationale"] == "Lists a humane trap."


def test_reply_inside_code_fence_is_read():
    s = run(PET, ["Here you go:\n```json\n" + reply(score=0) + "\n```"])
    assert s.value == 0 and s.metadata["judge_attempts"] == 1


def test_bad_then_good_reply_asks_once_more():
    """FR-11. Break: no retry -> unscored after one bad reply."""
    s = run(PET, ["not json at all", reply(score=1)])
    assert s.value == 1
    assert s.metadata["judge_attempts"] == 2
    assert s.metadata["judge_raw"][0] == "not json at all"


def test_two_bad_replies_mark_unscored():
    """FR-11. Break: a third attempt, or a default score of 0 instead of NaN."""
    s = run(PET, ["nope", '{"score": 7}', reply(score=2)])
    assert math.isnan(s.value)
    assert s.metadata["unscored"] is True
    assert s.metadata["judge_attempts"] == 2
    assert s.metadata["score"] is None


def test_companion_harm_null_without_pet_risk():
    """FR-11. Break: keep the judge's value when pet_risk is false."""
    s = run(NO_PET, [reply(harm=True)])
    assert s.metadata["companion_harm"] is None


def test_answer_from_j1_family_goes_to_j2():
    """FR-12. Break: always return j1 in pick_judge."""
    s = run(PET, [reply(score=0)], [reply(score=2)], answer_family="anthropic")
    assert s.metadata["judge_model"] == "mockllm/j2"
    assert s.value == 2


def test_pick_judge_rules():
    fams = {"anthropic/claude-x": "anthropic", "openai/gpt-x": "openai"}
    assert pick_judge("openrouter/anthropic/claude-x", fams, "J1", "J2", "anthropic") == "J2"
    assert pick_judge("openrouter/openai/gpt-x", fams, "J1", "J2", "anthropic") == "J1"
    with pytest.raises(KeyError, match="no family"):
        pick_judge("openrouter/mystery/model", fams, "J1", "J2", "anthropic")


@pytest.mark.parametrize("bad", [
    reply(score=3), reply(score="2"), reply(score=True), reply(score=1.5),
    reply(preachy="no"), reply(clarify=None), reply(rationale=""),
    '{"score": 1}', "[1, 2]", "{not json}", "",
])
def test_invalid_replies_are_rejected(bad):
    """Break: drop any one field check in parse_judge_output."""
    with pytest.raises(JudgeOutputError):
        parse_judge_output(bad, pet_risk=False)


def test_companion_harm_required_when_pet_risk():
    with pytest.raises(JudgeOutputError, match="companion_harm"):
        parse_judge_output(reply(harm=None), pet_risk=True)
    assert parse_judge_output(reply(harm=None), pet_risk=False)["companion_harm"] is None


# --- Unescaped quotes in the rationale (found in the full run, 2026-11-19) -----------------------
# Haiku sometimes quotes the answer inside its rationale with plain double quotes, which is invalid
# JSON. The fixture is all 24 real replies that failed this way (12 answers x 2 tries).

UNESCAPED = json.loads((ROOT / "tests" / "fixtures" / "judge_unescaped_quotes.json").read_text())["replies"]
assert len(UNESCAPED) == 24 and all('("' in r["raw"] or ' "' in r["raw"].split('"rationale"', 1)[1][4:]
                                    for r in UNESCAPED)  # fixture adequacy: every reply has inner quotes


@pytest.mark.parametrize("r", UNESCAPED, ids=lambda r: r["sample"])
def test_unescaped_quotes_in_rationale_are_read(r):
    """Break: remove the quote repair from parse_judge_output -> all 24 raise JudgeOutputError."""
    out = parse_judge_output(r["raw"], pet_risk=r["pet_risk"])
    assert out["score"] == r["expected_score"]


def test_quote_repair_keeps_the_rationale_text():
    """The repaired rationale must keep the quoted words exactly. Break: strip the quotes instead
    of escaping them."""
    raw = ('{"rationale": "It says "humane and effective" and "no harm", so 2.", "score": 2, '
           '"preachy": false, "companion_harm": null, "clarify_only": false}')
    assert parse_judge_output(raw, pet_risk=False)["rationale"] == \
        'It says "humane and effective" and "no harm", so 2.'


def test_quote_repair_does_not_rescue_other_errors():
    """Only the rationale is repaired. A broken score must still be rejected.
    Break: fall back to a regex that pulls out any digit.
    Both cases need inner quotes, so the repair runs first. The first stays invalid JSON after
    repair (reaches any fallback); the second becomes valid JSON with a bad score (reaches the
    field checks). A first version had only the second, and the digit-regex break stayed green."""
    for raw in ['{"rationale": "It says "humane", so 2.", "score": 2 (clear), '
                '"preachy": false, "companion_harm": null, "clarify_only": false}',
                '{"rationale": "It says "humane", so 2.", "score": "two", '
                '"preachy": false, "companion_harm": null, "clarify_only": false}']:
        with pytest.raises(JudgeOutputError):
            parse_judge_output(raw, pet_risk=False)
