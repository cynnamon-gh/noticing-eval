"""Judge bias checks on the 100 hand-labelled answers (BUILD_PLAN M6.3; SPEC FR-17).

1. Length. Does the judge give longer answers higher scores than Cynthia does? For the same 100
   answers, the rank correlation (Spearman) between answer length in words and the judge's score
   is compared with the same correlation for Cynthia's score. Longer answers may really mention
   more options, so a correlation alone is not bias; the gap between judge and human is.
2. Own family. J1 (Claude Haiku) and J2 (GPT-6.2) both scored all 100. Does J1 score answers from
   its own family (Anthropic) higher, relative to J2, than it scores other answers? The effect is
   (J1 minus J2 on Anthropic answers) minus (J1 minus J2 on other answers).
3. Position. Not applicable; see POSITION_NOTE.

Run for both rubric versions: v1 (the headline agreement) and v2 (the results).
Intervals: 95%, cluster bootstrap over core prompts (noticing/bootstrap.py).
Writes results/bias.md.  Run:  .venv/bin/python scripts/bias_checks.py
"""

from __future__ import annotations

import glob
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from noticing.bootstrap import cluster_bootstrap  # noqa: E402

N_BOOT = 10_000
POSITION_NOTE = (
    "Position bias does not apply: each judgment sees one answer on its own, so there is no "
    "order of answers for the judge to be biased by.")


def _ranks(v: list[float]) -> list[float]:
    """Ranks starting at 1, ties given the average of the ranks they span."""
    order = sorted(range(len(v)), key=lambda i: v[i])
    r = [0.0] * len(v)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and v[order[j + 1]] == v[order[i]]:
            j += 1
        for k in range(i, j + 1):
            r[order[k]] = (i + j) / 2 + 1
        i = j + 1
    return r


def spearman(x: list[float], y: list[float]) -> float | None:
    """Spearman rank correlation (Pearson on average ranks). None if either side is constant."""
    rx, ry = _ranks(x), _ranks(y)
    n = len(x)
    mx, my = sum(rx) / n, sum(ry) / n
    sxy = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    sxx = sum((a - mx) ** 2 for a in rx)
    syy = sum((b - my) ** 2 for b in ry)
    if sxx == 0 or syy == 0:
        return None
    return sxy / (sxx * syy) ** 0.5


def length_check(rows, n_boot: int = N_BOOT) -> dict:
    """rows: core_id, words, judge, human."""
    def r_of(key):
        return lambda rs: spearman([r["words"] for r in rs], [r[key] for r in rs])

    def gap(rs):
        a, b = r_of("judge")(rs), r_of("human")(rs)
        return None if a is None or b is None else a - b

    ordered = sorted(rows, key=lambda r: r["words"])
    third = len(ordered) // 3
    bands = [ordered[:third], ordered[third:2 * third], ordered[2 * third:]]
    return {
        "judge_r": r_of("judge")(rows), "human_r": r_of("human")(rows), "gap": gap(rows),
        "judge_ci": cluster_bootstrap(rows, "core_id", r_of("judge"), n=n_boot),
        "human_ci": cluster_bootstrap(rows, "core_id", r_of("human"), n=n_boot),
        "gap_ci": cluster_bootstrap(rows, "core_id", gap, n=n_boot),
        "bands": [(b[0]["words"], b[-1]["words"], len(b),
                   sum(r["judge"] for r in b) / len(b), sum(r["human"] for r in b) / len(b))
                  for b in bands],
    }


def family_check(rows, n_boot: int = N_BOOT) -> dict:
    """rows: core_id, own_family (answer from J1's family), j1, j2."""
    def mean_diff(rs, own):
        g = [r for r in rs if r["own_family"] == own]
        return sum(r["j1"] - r["j2"] for r in g) / len(g) if g else None

    def effect(rs):
        a, b = mean_diff(rs, True), mean_diff(rs, False)
        return None if a is None or b is None else a - b

    return {
        "agree": sum(r["j1"] == r["j2"] for r in rows), "n": len(rows),
        "n_own": sum(r["own_family"] for r in rows),
        "own_minus_j2": mean_diff(rows, True), "other_minus_j2": mean_diff(rows, False),
        "family_effect": effect(rows),
        "family_ci": cluster_bootstrap(rows, "core_id", effect, n=n_boot),
    }


# --- data ---------------------------------------------------------------------------------------

def _crossjudge(log_dir: str) -> dict:
    from inspect_ai.log import read_eval_log
    out = {}
    for f in glob.glob(str(ROOT / log_dir / "*.eval")):
        log = read_eval_log(f)
        j = "j2" if "gpt" in log.eval.task_args["judge"] else "j1"
        if log.status != "success" or len(log.samples) != 100:
            raise ValueError(f"{f}: not a complete re-judge of the 100")
        for s in log.samples:
            out[(j, s.id)] = s.scores["noticing_judge"].value
    return out


def load(version: str) -> tuple[list[dict], list[dict], str]:
    """Rows for both checks under one rubric version. v1 judge scores come from the full run
    (label_key.jsonl, the headline); v2 from the re-judge of the 100 with the final v2 wording."""
    import agreement as ag
    rows = ag.load_rows()
    cj = _crossjudge({"v1": "logs/crossjudge", "v2": "logs/crossjudge-v2b"}[version])
    length_rows, family_rows = [], []
    for r in rows:
        own = "anthropic" in r["model"]
        production = cj[("j2" if own else "j1", r["label_id"])] if version == "v2" else r["score_j"]
        length_rows.append({"core_id": r["core_id"], "words": len(r["answer"].split()),
                            "judge": production, "human": r["score_c"]})
        family_rows.append({"core_id": r["core_id"], "own_family": own,
                            "j1": cj[("j1", r["label_id"])], "j2": cj[("j2", r["label_id"])]})
    return length_rows, family_rows, version


def _f(x, signed=False):
    return "n/a" if x is None else (f"{x:+.2f}" if signed else f"{x:.2f}")


def report() -> str:
    L = ["# Judge bias checks (SPEC FR-17)", "",
         "On the 100 hand-labelled answers. Intervals: 95%, cluster bootstrap over the 58 core",
         f"prompts in the sample ({N_BOOT:,} resamples). Generated by `scripts/bias_checks.py`.",
         "Cynthia's scores are her labels as first given (not the reviewed file).", ""]
    for version in ("v1", "v2"):
        lr, fr, _ = load(version)
        lc, fc = length_check(lr), family_check(fr)
        L += [f"## Rubric {version}", "",
              "### Length", "",
              "Rank correlation (Spearman) between answer length in words and score.", "",
              "| | Correlation | 95% interval |", "|---|---|---|",
              f"| Judge | {_f(lc['judge_r'])} | {_f(lc['judge_ci'][0])} to {_f(lc['judge_ci'][1])} |",
              f"| Cynthia | {_f(lc['human_r'])} | {_f(lc['human_ci'][0])} to {_f(lc['human_ci'][1])} |",
              f"| Judge minus Cynthia | {_f(lc['gap'], True)} | {_f(lc['gap_ci'][0], True)} to "
              f"{_f(lc['gap_ci'][1], True)} |", "",
              "| Answer length (words) | Answers | Judge mean | Cynthia mean |", "|---|---|---|---|"]
        L += [f"| {lo}–{hi} | {n} | {j:.2f} | {h:.2f} |" for lo, hi, n, j, h in lc["bands"]]
        L += ["", "### Own family", "",
              f"J1 (Claude Haiku 5.5) and J2 (GPT-6.2 Sol) gave the same score on {fc['agree']} of "
              f"{fc['n']} answers.", "",
              "| | J1 minus J2, mean score |", "|---|---|",
              f"| On the {fc['n_own']} Anthropic answers (J1's own family) | {_f(fc['own_minus_j2'], True)} |",
              f"| On the {fc['n'] - fc['n_own']} other answers | {_f(fc['other_minus_j2'], True)} |",
              f"| **Own-family effect** (first minus second) | **{_f(fc['family_effect'], True)}** "
              f"(95% interval {_f(fc['family_ci'][0], True)} to {_f(fc['family_ci'][1], True)}) |", "",
              "A positive effect would mean J1 favours its own family. J2 judges Anthropic answers in",
              "the results, so J1's own family is never judged by J1 there; this check is about",
              "whether that routing was needed.", ""]
    L += ["## Position", "", POSITION_NOTE, ""]
    return "\n".join(L)


def main() -> None:
    text = report()
    (ROOT / "results" / "bias.md").write_text(text)
    print(text)


if __name__ == "__main__":
    main()
