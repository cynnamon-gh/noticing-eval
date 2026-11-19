"""Draw the 100 answers Cynthia labels by hand (BUILD_PLAN M5.1; SPEC FR-13).

How the draw works, with a fixed seed:
  1. Every model gets an equal share: 100 / 8 = 12 each, and 4 models chosen at random get 13.
  2. Every answer the judge flagged preachy is included (the full run had 4), because the flag is
     too rare to get any other way.
  3. Within each model, the target is equal thirds by judge score (0, 1, 2), so 2s are
     over-sampled. A model short of one score takes all it has and fills from the others,
     scarcest score first.
  4. At most 2 answers per core prompt, so a few prompts can't dominate the agreement numbers.
  5. The 100 are shuffled, so answers from one model are not grouped together.

Writes two files:
  data/label_sample.jsonl  what the labelling page shows: label ID, prompt, note, answer, and
                           pet_risk (only used to show or hide the companion-harm question).
  data/label_key.jsonl     the same label IDs with the model, sample, epoch and the judge's output.
                           The labelling page never reads it.

Run:  .venv/bin/python scripts/sample_for_labels.py logs/full
"""

from __future__ import annotations

import argparse
import json
import random
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SEED = 20261119
MAX_PER_CORE = 2
SAMPLE_FIELDS = {"label_id", "prompt", "note", "answer", "pet_risk"}
KEY_FIELDS = ["label_id", "model", "sample_id", "core_id", "epoch", "score", "preachy",
              "companion_harm", "clarify_only", "rationale", "judge_model"]
# An answer that names its maker breaks blindness (writeup-notes: "Blindness has a known gap").
SELF_ID = re.compile(r"\b(as an ai|i'?m an ai|i am an ai|language model|claude|anthropic|openai|chatgpt|gpt-|"
                     r"gemini|google deepmind|llama|meta ai|deepseek)\b", re.IGNORECASE)


def load_records(log_dir: Path) -> list[dict]:
    """One record per scored answer in the logs. Unscored answers are left out."""
    from inspect_ai.log import read_eval_log, resolve_sample_attachments

    records = []
    for path in sorted(log_dir.glob("*.eval")):
        log = read_eval_log(str(path))
        for s in log.samples:
            s = resolve_sample_attachments(s)
            md = s.scores["noticing_judge"].metadata or {}
            if md.get("unscored"):
                continue
            records.append({
                "model": log.eval.model, "sample_id": s.id, "core_id": s.metadata["core_id"],
                "epoch": s.epoch, "prompt": s.metadata["prompt"],
                "note": s.metadata["noticing_note"], "answer": s.output.completion,
                "pet_risk": s.metadata["pet_risk"], "score": md["score"],
                "preachy": md["preachy"], "companion_harm": md["companion_harm"],
                "clarify_only": md["clarify_only"], "rationale": md["rationale"],
                "judge_model": md["judge_model"]})
    return records


def draw(records: list[dict], n: int = 100, seed: int = SEED) -> list[dict]:
    rng = random.Random(seed)
    models = sorted({r["model"] for r in records})
    base, extra = divmod(n, len(models))
    bonus = set(rng.sample(models, extra))
    quota = {m: base + (m in bonus) for m in models}

    chosen: list[dict] = []
    taken: set[tuple] = set()
    per_core: Counter = Counter()
    per_model: Counter = Counter()

    def ident(r):
        return (r["model"], r["sample_id"], r["epoch"])

    def ok(r):
        return (ident(r) not in taken and per_core[r["core_id"]] < MAX_PER_CORE
                and per_model[r["model"]] < quota[r["model"]])

    def take(r):
        chosen.append(r)
        taken.add(ident(r))
        per_core[r["core_id"]] += 1
        per_model[r["model"]] += 1

    preachy = [r for r in records if r["preachy"]]
    rng.shuffle(preachy)
    for r in preachy:
        if ok(r):
            take(r)

    for m in models:
        pool = [r for r in records if r["model"] == m]
        rng.shuffle(pool)
        third, rest = divmod(quota[m], 3)
        target = {s: third for s in (0, 1, 2)}
        for s in rng.sample([0, 1, 2], rest):
            target[s] += 1
        for r in chosen:
            if r["model"] == m:
                target[r["score"]] -= 1
        available = Counter(r["score"] for r in pool)
        for s in sorted((0, 1, 2), key=lambda s: (available[s], s)):  # scarcest first
            for r in pool:
                if target[s] <= 0:
                    break
                if r["score"] == s and ok(r):
                    take(r)
                    target[s] -= 1
        for s in sorted((0, 1, 2), key=lambda s: (available[s], s)):  # fill any shortfall
            for r in pool:
                if r["score"] == s and ok(r):
                    take(r)

    if len(chosen) != n:
        raise ValueError(f"drew {len(chosen)} answers, not {n}: the pool is too small")
    rng.shuffle(chosen)
    return chosen


def write_files(chosen: list[dict], sample_path: Path, key_path: Path) -> None:
    with sample_path.open("w") as s, key_path.open("w") as k:
        for i, r in enumerate(chosen, 1):
            label_id = f"L{i:03d}"
            row = {"label_id": label_id, "prompt": r["prompt"], "note": r["note"],
                   "answer": r["answer"], "pet_risk": r["pet_risk"]}
            assert set(row) == SAMPLE_FIELDS
            s.write(json.dumps(row) + "\n")
            k.write(json.dumps({"label_id": label_id,
                                **{f: r[f] for f in KEY_FIELDS if f != "label_id"}}) + "\n")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("log_dir", type=Path)
    ap.add_argument("--seed", type=int, default=SEED)
    args = ap.parse_args()

    records = load_records(args.log_dir)
    chosen = draw(records, seed=args.seed)
    write_files(chosen, ROOT / "data" / "label_sample.jsonl", ROOT / "data" / "label_key.jsonl")

    print(f"Drew {len(chosen)} of {len(records)} scored answers (seed {args.seed}).\n")
    print("Per model:      0   1   2  total")
    for m in sorted({r["model"] for r in chosen}):
        c = Counter(r["score"] for r in chosen if r["model"] == m)
        print(f"  {m.split('/')[-1]:24} {c[0]:3} {c[1]:3} {c[2]:3} {sum(c.values()):5}")
    c = Counter(r["score"] for r in chosen)
    pop = Counter(r["score"] for r in records)
    print(f"  {'all':24} {c[0]:3} {c[1]:3} {c[2]:3} {len(chosen):5}")
    print(f"  {'(whole run, %)':24} " + " ".join(f"{100 * pop[s] / len(records):3.0f}" for s in (0, 1, 2)))
    print(f"\nFlags in the sample: preachy {sum(r['preachy'] for r in chosen)} "
          f"(of {sum(r['preachy'] for r in records)} in the run), "
          f"companion_harm {sum(bool(r['companion_harm']) for r in chosen)}, "
          f"clarify_only {sum(r['clarify_only'] for r in chosen)}, "
          f"pet_risk prompts {sum(r['pet_risk'] for r in chosen)}")
    print(f"Distinct core prompts: {len({r['core_id'] for r in chosen})}")
    selfid = [r for r in chosen if SELF_ID.search(r["answer"])]
    print(f"Answers that may name their maker (breaks blindness): {len(selfid)}")
    for r in selfid:
        m = SELF_ID.search(r["answer"])
        print(f"  {r['sample_id']} epoch {r['epoch']}: ...{r['answer'][max(0, m.start() - 40):m.end() + 40]!r}...")


if __name__ == "__main__":
    sys.exit(main())
