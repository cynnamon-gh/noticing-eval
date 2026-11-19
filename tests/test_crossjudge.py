"""Tests for noticing/crossjudge.py (BUILD_PLAN M5.4; SPEC FR-17).

The judge is a mockllm model that records what it was sent, so no API is called.
Each test was watched failing with its rule removed.
"""

import json
import sys
import tempfile
from pathlib import Path

from inspect_ai import eval as inspect_eval
from inspect_ai.log import resolve_sample_attachments
from inspect_ai.model import ModelOutput, get_model

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from noticing.crossjudge import crossjudge  # noqa: E402
from noticing.judge_prompt import judge_prompt_hash  # noqa: E402

SAMPLE = [json.loads(x) for x in (ROOT / "data" / "label_sample.jsonl").read_text().splitlines()]
REPLY = json.dumps({"rationale": "r", "score": 1, "preachy": False, "companion_harm": False,
                    "clarify_only": False})


def run(limit=None):
    judge = get_model("mockllm/judge",
                      custom_outputs=[ModelOutput.from_content("mockllm/judge", REPLY)] * 100)
    [log] = inspect_eval(crossjudge(judge=judge), model="mockllm/model", limit=limit,
                         display="none", log_dir=tempfile.mkdtemp())
    assert log.status == "success", log.error
    return log


def test_all_100_answers_are_judged_once_with_rubric_v1():
    """M5.4 acceptance: a score for all 100. Break: load only part of the sample."""
    log = run()
    assert sorted(s.id for s in log.samples) == sorted(r["label_id"] for r in SAMPLE)
    for s in log.samples:
        md = s.scores["noticing_judge"].metadata
        assert md["judge_prompt_hash"] == judge_prompt_hash() and md["score"] == 1


def test_the_stored_answer_reaches_the_judge_and_no_answer_model_is_called():
    """Re-score only: the judge must see the saved answer, word for word, and the answering
    model must never be asked. Break: call generate() in the solver."""
    log = run(limit=3)
    for s in map(resolve_sample_attachments, log.samples):
        stored = next(r for r in SAMPLE if r["label_id"] == s.id)
        assert s.output.completion == stored["answer"]
        judge_inputs = [e for e in s.events if e.event == "model"]
        assert len(judge_inputs) == 1 and judge_inputs[0].model == "mockllm/judge"
        assert stored["answer"] in judge_inputs[0].input[0].text
    assert "mockllm/model" not in log.stats.model_usage


def test_the_judge_never_sees_the_answering_model():
    """The re-judge reads only the blind sample file. Break: read data/label_key.jsonl."""
    log = run(limit=5)
    for s in log.samples:
        assert not ({"model", "sample_id", "rationale"} & set(s.metadata))
