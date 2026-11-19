"""Re-judge the 100 hand-labelled answers with one chosen judge (BUILD_PLAN M5.4; SPEC FR-17).

In the full run each answer was judged by one judge: J1 (Haiku) for most models, J2 (GPT-6.2) for
Anthropic models. Here a single judge scores all 100 answers, so J1 and J2 can be compared on
the same answers, and J1 can be checked for favouring its own family.

No answer is generated. The solver puts the saved answer from data/label_sample.jsonl in place of
a model reply, then the normal judge scorer (rubric v1) runs. The sample file holds no model
names, so the judge stays blind.

Run (the --model is a placeholder and is never called):
  inspect eval noticing/crossjudge.py --model mockllm/model -T judge=openrouter/<judge id> \
      --log-dir logs/crossjudge
"""

from __future__ import annotations

import json
from pathlib import Path

from inspect_ai import Task, task
from inspect_ai.dataset import MemoryDataset, Sample
from inspect_ai.model import Model, ModelOutput
from inspect_ai.solver import Generate, TaskState, solver

from noticing.judge_prompt import judge_prompt_hash
from noticing.scorer import noticing_judge

ROOT = Path(__file__).resolve().parent.parent
SAMPLE = ROOT / "data" / "label_sample.jsonl"


def load_label_samples(path: Path = SAMPLE) -> list[Sample]:
    samples = []
    for line in path.read_text().splitlines():
        r = json.loads(line)
        samples.append(Sample(id=r["label_id"], input=r["prompt"], metadata={
            "prompt": r["prompt"], "noticing_note": r["note"], "pet_risk": r["pet_risk"],
            "answer": r["answer"]}))
    return samples


@solver
def replay_answer():
    """Use the saved answer as the model's output. Calls no model."""

    async def solve(state: TaskState, generate: Generate) -> TaskState:
        state.output = ModelOutput.from_content(model="replay", content=state.metadata["answer"])
        return state

    return solve


@task
def crossjudge(judge: str | Model) -> Task:
    # One judge for every answer: J1 and J2 are both set to it, and the placeholder answering
    # model is given a family that is not J1's, so pick_judge always returns it.
    return Task(
        dataset=MemoryDataset(load_label_samples()),
        solver=replay_answer(),
        scorer=noticing_judge(j1=judge, j2=judge, families={"mockllm/model": "replay"},
                              j1_family="none"),
        metadata={"judge_prompt_hash": judge_prompt_hash(), "judge": str(judge)},
    )
