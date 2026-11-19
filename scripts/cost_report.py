"""Cost report and full-run projection from Inspect logs (BUILD_PLAN M2.4; SPEC NFR-1).

Reads every .eval log in a folder. For each log it splits model calls into:
  - answers: calls made by the model being evaluated (log.eval.model)
  - judgments: every other model call in a sample (the judge, including retries)
and prices their tokens with config/prices.yaml.

Then it projects the full run: for each answering model,
  234 versions x epochs x (mean cost per answer + mean cost per judged answer)
plus the planned extras (validity check, cross-judging the 100 hand labels).

Run:  .venv/bin/python scripts/cost_report.py logs/pilot [--epochs 3]

Assumptions, stated in the report:
  - the pilot runs .a versions only; .b/.c answers are assumed to cost the same on average
  - output tokens include any reasoning tokens (OpenRouter bills them as output)
  - cached input is priced as normal input (an upper bound)
"""

from __future__ import annotations

import argparse
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

import yaml
from inspect_ai.log import list_eval_logs, read_eval_log

ROOT = Path(__file__).resolve().parent.parent
PRICES_YAML = ROOT / "config" / "prices.yaml"

FULL_RUN_VERSIONS = 234
BUDGET_FULL_RUN = 40.0  # NFR-1: full run goes ahead only if projected cost <= $40
# Planned extras (BUILD_PLAN M3.4, M5.4), counted in calls.
VALIDITY_ANSWERS_PER_MODEL = 78 * 2  # 78 .a versions, with and without the welfare system prompt
VALIDITY_MODELS = 2
CROSSJUDGE_JUDGMENTS = 100 * 2       # both judges score the 100 hand-labelled answers


class PriceError(KeyError):
    pass


def load_prices(path: Path = PRICES_YAML) -> dict[str, dict[str, float]]:
    return yaml.safe_load(path.read_text())["prices"]


def call_cost(model: str, input_tokens: int, output_tokens: int, prices: dict) -> float:
    """Dollar cost of one call. An unpriced model is an error, never $0."""
    if model not in prices:
        raise PriceError(f"no price for {model!r} in config/prices.yaml")
    p = prices[model]
    return (input_tokens * p["input"] + output_tokens * p["output"]) / 1_000_000


@dataclass
class Tally:
    calls: int = 0
    items: int = 0  # answers, or judged answers (one judged answer may take 2 judge calls)
    input_tokens: int = 0
    output_tokens: int = 0
    cost: float = 0.0
    by_judge: dict = field(default_factory=lambda: defaultdict(float))

    def per_item(self) -> float:
        return self.cost / self.items if self.items else 0.0


def tally_log(log_path, prices: dict) -> tuple[str, Tally, Tally]:
    """Return (answering model, answer tally, judgment tally) for one log."""
    log = read_eval_log(log_path)
    answer_model = log.eval.model
    answers, judgments = Tally(), Tally()
    for sample in log.samples or []:
        judged = False
        for e in sample.events:
            if e.event != "model" or e.output is None or e.output.usage is None:
                continue
            u = e.output.usage
            cost = call_cost(e.model, u.input_tokens, u.output_tokens, prices)
            t = answers if e.model == answer_model else judgments
            t.calls += 1
            t.input_tokens += u.input_tokens
            t.output_tokens += u.output_tokens
            t.cost += cost
            if t is judgments:
                judged = True
                t.by_judge[e.model] += cost
        answers.items += 1
        judgments.items += 1 if judged else 0
    return answer_model, answers, judgments


def report(log_dir: Path, epochs: int, prices: dict) -> tuple[str, float]:
    """Return (markdown report, projected full-run cost)."""
    rows, projected = [], 0.0
    spent_answers = spent_judging = 0.0
    judge_cost_per_item: list[float] = []
    for info in list_eval_logs(str(log_dir)):
        model, a, j = tally_log(info.name, prices)
        spent_answers += a.cost
        spent_judging += j.cost
        if j.items:
            judge_cost_per_item.append(j.per_item())
        proj = FULL_RUN_VERSIONS * epochs * (a.per_item() + j.per_item())
        projected += proj
        rows.append(f"| {model} | {a.items} | ${a.per_item():.5f} | {j.calls} | "
                    f"${j.per_item():.5f} | ${proj:.2f} |")
    if not rows:
        raise FileNotFoundError(f"no .eval logs in {log_dir}")

    mean_judge = sum(judge_cost_per_item) / len(judge_cost_per_item) if judge_cost_per_item else 0.0
    # Validity check: answers priced at the mean pilot answer cost of all models (rough).
    extras_crossjudge = CROSSJUDGE_JUDGMENTS * mean_judge
    lines = [
        f"# Cost report: {log_dir}",
        "",
        f"Prices from config/prices.yaml (fetched {yaml.safe_load(PRICES_YAML.read_text())['fetched']}).",
        f"Spent in these logs: answers ${spent_answers:.2f}, judging ${spent_judging:.2f}, "
        f"total ${spent_answers + spent_judging:.2f}.",
        "",
        f"| Answering model | Answers | $ per answer | Judge calls | $ per judged answer | "
        f"Full run ({FULL_RUN_VERSIONS} versions x {epochs} epochs) |",
        "|---|---|---|---|---|---|",
        *rows,
        "",
        f"**Projected full run: ${projected:.2f}** (limit ${BUDGET_FULL_RUN:.0f}, NFR-1): "
        + ("within limit." if projected <= BUDGET_FULL_RUN else "OVER LIMIT: apply the cut order."),
        f"Plus cross-judging the 100 hand labels (~{CROSSJUDGE_JUDGMENTS} judgments): "
        f"~${extras_crossjudge:.2f}. The validity check ({VALIDITY_MODELS} models x "
        f"{VALIDITY_ANSWERS_PER_MODEL} answers) depends on which models; price it from this table.",
        "",
        "Assumptions: .b/.c versions cost the same as .a on average; output tokens include "
        "reasoning tokens; cached input priced as normal input.",
    ]
    return "\n".join(lines), projected


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("log_dir", type=Path)
    ap.add_argument("--epochs", type=int, default=3)
    args = ap.parse_args(argv)
    try:
        text, _ = report(args.log_dir, args.epochs, load_prices())
    except (PriceError, FileNotFoundError) as e:
        print(f"cost_report: {e}", file=sys.stderr)
        return 1
    print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
