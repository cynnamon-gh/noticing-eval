"""Tests for scripts/cost_report.py (BUILD_PLAN M2.4; SPEC NFR-1).

Token totals are cross-checked against Inspect's own per-model usage summary (log.stats), which
the report does not read, so the test does not just repeat the code's arithmetic.
Each test was watched failing with its bug put back.
"""

import json
import sys
from pathlib import Path

import pytest
from inspect_ai import Epochs, Task
from inspect_ai import eval as inspect_eval
from inspect_ai.log import read_eval_log
from inspect_ai.model import ModelOutput, get_model
from inspect_ai.solver import generate

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import cost_report as cr  # noqa: E402
from noticing.scorer import noticing_judge  # noqa: E402
from noticing.task import load_samples  # noqa: E402

PRICES = {"mockllm/model": {"input": 1.0, "output": 2.0},
          "mockllm/j": {"input": 3.0, "output": 4.0}}
GOOD = json.dumps({"rationale": "r", "score": 1, "preachy": False, "companion_harm": False,
                   "clarify_only": False})


@pytest.fixture(scope="module")
def judged_log(tmp_path_factory):
    """4 real prompts, answered and judged by fake models. One judgment needs a retry."""
    d = tmp_path_factory.mktemp("logs")
    replies = ["garbage", GOOD, GOOD, GOOD, GOOD]  # 4 answers -> 5 judge calls
    judge = get_model("mockllm/j", custom_outputs=[ModelOutput.from_content("mockllm/j", r)
                                                    for r in replies])
    task = Task(dataset=load_samples(versions="a", core_ids="P1,P2,V34,W638d9a85"),
                solver=[generate()], epochs=Epochs(1),
                scorer=noticing_judge(j1=judge, j2=judge, families={"mockllm/model": "openai"},
                                      j1_family="anthropic"))
    [log] = inspect_eval(task, model="mockllm/model", log_dir=str(d), display="none",
                         max_samples=1)  # one at a time, so the retry lands on one sample
    assert log.status == "success"
    return d, read_eval_log(log.location)


def test_call_cost_hand_computed():
    """1M input at $2 + 0.5M output at $10 = $7. Break: swap input and output prices."""
    prices = {"m": {"input": 2.0, "output": 10.0}}
    assert cr.call_cost("m", 1_000_000, 500_000, prices) == pytest.approx(7.0)


def test_unpriced_model_is_an_error():
    """Break: return 0.0 for unknown models -> a missing price silently makes a model free."""
    with pytest.raises(cr.PriceError):
        cr.call_cost("unknown/model", 10, 10, PRICES)


def test_tally_matches_inspect_usage_summary(judged_log):
    """Break: count judge calls as answers (compare against the eval model wrongly)."""
    d, log = judged_log
    model, a, j = cr.tally_log(log.location, PRICES)
    usage = log.stats.model_usage
    assert model == "mockllm/model"
    assert (a.input_tokens, a.output_tokens) == (usage["mockllm/model"].input_tokens,
                                                 usage["mockllm/model"].output_tokens)
    assert (j.input_tokens, j.output_tokens) == (usage["mockllm/j"].input_tokens,
                                                 usage["mockllm/j"].output_tokens)
    expected_judge_cost = (usage["mockllm/j"].input_tokens * 3 + usage["mockllm/j"].output_tokens * 4) / 1e6
    assert j.cost == pytest.approx(expected_judge_cost)


def test_judged_answers_counted_once_despite_retry(judged_log):
    """Per-judged-answer cost must include retries but divide by answers, not calls.
    Break: increment items once per judge call."""
    _, log = judged_log
    _, a, j = cr.tally_log(log.location, PRICES)
    assert a.items == 4 and j.items == 4
    assert j.calls == 5


def test_projection_formula(judged_log):
    """Break: drop the judging cost, or forget epochs, in the projection."""
    d, log = judged_log
    _, a, j = cr.tally_log(log.location, PRICES)
    text, projected = cr.report(d, epochs=3, prices=PRICES)
    assert projected == pytest.approx(204 * 3 * (a.cost / 4 + j.cost / 4))
    assert "Projected full run" in text


def test_over_limit_is_flagged(judged_log, monkeypatch):
    d, _ = judged_log
    monkeypatch.setattr(cr, "BUDGET_FULL_RUN", 0.0)
    text, _ = cr.report(d, epochs=3, prices=PRICES)
    assert "OVER LIMIT" in text


def test_cli_fails_on_unpriced_log(judged_log, capsys):
    """The real price table has no mockllm prices, so the CLI must refuse, not report $0."""
    d, _ = judged_log
    assert cr.main([str(d)]) == 1
    assert "no price" in capsys.readouterr().err


def test_cache_write_tokens_are_billed():
    """Found in the pilot: GPT-6.2 logged 48 input tokens and 35,660 cache-write tokens.
    Break: return usage.input_tokens only in billed_input_tokens."""
    from inspect_ai.model import ModelUsage
    u = ModelUsage(input_tokens=48, output_tokens=10, total_tokens=35_718,
                   input_tokens_cache_write=35_660)
    assert cr.billed_input_tokens(u) == 35_708
    u2 = ModelUsage(input_tokens=100, output_tokens=10, total_tokens=160, input_tokens_cache_read=50)
    assert cr.billed_input_tokens(u2) == 150
