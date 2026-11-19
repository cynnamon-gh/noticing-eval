"""Re-read the saved judge replies of unscored answers with the current parser (no model calls).

Added 2026-11-19 after the full run: 12 answers were unscored because Haiku put unescaped double
quotes in its rationale. parse_judge_output now repairs that. This script applies the repaired
reading to the logs in place, recording the edit in each score's history (Inspect edit_score).
The first reply that parses is used, as the scorer would have done.

Usage: python scripts/recover_unscored.py logs/full
"""

import sys
from pathlib import Path

from inspect_ai.log import ProvenanceData, edit_score, read_eval_log, write_eval_log
from inspect_ai.scorer import ScoreEdit

from noticing.scorer import JudgeOutputError, parse_judge_output

NAME = "noticing_judge"


def main(log_dir: str) -> None:
    recovered = still = 0
    for path in sorted(Path(log_dir).glob("*.eval")):
        log = read_eval_log(str(path))
        changed = False
        for s in log.samples:
            md = s.scores[NAME].metadata or {}
            if not md.get("unscored"):
                continue
            parsed = []
            for raw in md["judge_raw"]:
                try:
                    parsed.append(parse_judge_output(raw, s.metadata["pet_risk"]))
                except JudgeOutputError:
                    pass
            if not parsed:
                still += 1
                print(f"  still unscored: {log.eval.model} {s.id} epoch {s.epoch}")
                continue
            if len({p["score"] for p in parsed}) > 1:
                print(f"  note: tries disagree on {s.id} epoch {s.epoch}; using the first")
            p = parsed[0]
            edit_score(log, s.id, NAME, ScoreEdit(
                value=p["score"], explanation=p["rationale"],
                metadata={**md, **p, "unscored": False, "recovered_from_raw": True},
                provenance=ProvenanceData(author="recover_unscored.py",
                                          reason="re-read saved judge reply with quote repair")),
                epoch=s.epoch, recompute_metrics=False)
            recovered += 1
            changed = True
            print(f"  recovered: {log.eval.model.split('/')[-1]} {s.id} epoch {s.epoch} -> {p['score']}")
        if changed:
            write_eval_log(log, str(path))
    print(f"recovered {recovered}, still unscored {still}")


if __name__ == "__main__":
    main(sys.argv[1])
