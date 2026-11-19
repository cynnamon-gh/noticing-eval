"""Agreement between the judge and Cynthia's hand labels (BUILD_PLAN M6.1; SPEC FR-14–FR-16).

Compares data/labels.csv (Cynthia) with the judge's score from the full run, as stored in
data/label_key.jsonl. That judge is the one the results use: Haiku for most models, GPT-6.2 for
Anthropic models, rubric v1. This is the headline agreement (FR-14).

Reports (FR-15):
  - score: same-score percent, linear weighted kappa, 3x3 table, and agreement within each judge
    score (which does not depend on the over-sampled score mix)
  - flags: kappa for preachy, companion harm (pet-risk prompts only) and clarify only
  - 95% intervals from a cluster bootstrap over core prompts (noticing/bootstrap.py)
Lists every disagreement with the answer, both scores and the judge's reasoning, plus Cynthia's
comments on answers where she agreed (FR-16).

Corrections Cynthia makes after seeing the disagreements go in data/labels_reviewed.csv, never in
labels.csv. They are reported as a second number, below the headline, with each change listed.

Writes results/agreement.md and results/disagreements.md.
Run:  .venv/bin/python scripts/agreement.py
"""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from noticing.bootstrap import cluster_bootstrap  # noqa: E402

N_BOOT = 10_000


# --- statistics ---------------------------------------------------------------------------------

def weighted_kappa(a: list[int], b: list[int], k: int = 3) -> float | None:
    """Cohen's kappa with linear weights on scores 0..k-1. None when chance agreement is total."""
    n = len(a)
    obs = [[0] * k for _ in range(k)]
    for x, y in zip(a, b):
        obs[x][y] += 1
    rows = [sum(obs[i]) for i in range(k)]
    cols = [sum(obs[i][j] for i in range(k)) for j in range(k)]
    w = [[abs(i - j) / (k - 1) for j in range(k)] for i in range(k)]
    p_obs = sum(w[i][j] * obs[i][j] for i in range(k) for j in range(k)) / n
    p_exp = sum(w[i][j] * rows[i] * cols[j] for i in range(k) for j in range(k)) / (n * n)
    if p_exp == 0:
        return None
    return 1 - p_obs / p_exp


def flag_kappa(a: list[bool], b: list[bool]) -> float | None:
    """Cohen's kappa for a yes/no flag. None when it is undefined (no variation)."""
    n = len(a)
    if n == 0:
        return None
    p_obs = sum(x == y for x, y in zip(a, b)) / n
    pa, pb = sum(a) / n, sum(b) / n
    p_exp = pa * pb + (1 - pa) * (1 - pb)
    if p_exp == 1:
        return None
    return (p_obs - p_exp) / (1 - p_exp)


def same_share(rows) -> float:
    return sum(r["score_c"] == r["score_j"] for r in rows) / len(rows)


def score_kappa(rows) -> float | None:
    return weighted_kappa([r["score_c"] for r in rows], [r["score_j"] for r in rows])


def within_judge_score(rows) -> dict[int, tuple[int, int]]:
    """For each judge score: (answers where Cynthia gave the same score, answers with that judge
    score)."""
    out = {}
    for s in (0, 1, 2):
        grp = [r for r in rows if r["score_j"] == s]
        out[s] = (sum(r["score_c"] == s for r in grp), len(grp))
    return out


# --- data ---------------------------------------------------------------------------------------

def load_rows() -> list[dict]:
    labels = {r["label_id"]: r for r in csv.DictReader((ROOT / "data" / "labels.csv").open())}
    key = {r["label_id"]: r for r in map(json.loads, (ROOT / "data" / "label_key.jsonl").open())}
    sample = {r["label_id"]: r for r in map(json.loads,
                                            (ROOT / "data" / "label_sample.jsonl").open())}
    if set(labels) != set(key) or set(key) != set(sample):
        raise ValueError("labels.csv, label_key.jsonl and label_sample.jsonl cover different IDs")
    tf = {"true": True, "false": False, "": None}
    rows = []
    for i in sorted(labels):
        lab, k, s = labels[i], key[i], sample[i]
        rows.append({
            "label_id": i, "core_id": k["core_id"], "model": k["model"], "pet_risk": s["pet_risk"],
            "prompt": s["prompt"], "note": s["note"], "answer": s["answer"],
            "rationale": k["rationale"], "comment": lab["comment"],
            "score_c": int(lab["score"]), "score_j": k["score"],
            "preachy_c": tf[lab["preachy"]], "preachy_j": k["preachy"],
            "clarify_c": tf[lab["clarify_only"]], "clarify_j": k["clarify_only"],
            "harm_c": tf[lab["companion_harm"]], "harm_j": k["companion_harm"]})
    return rows


def load_review(path: Path = ROOT / "data" / "labels_reviewed.csv") -> dict:
    if not path.exists():
        return {}
    return {r["label_id"]: {"score_before": int(r["score_before"]),
                            "score_after": int(r["score_after"]), "reason": r["reason"]}
            for r in csv.DictReader(path.open())}


def apply_review(rows, reviewed: dict) -> list[dict]:
    """Copies of rows with Cynthia's reviewed scores. The 'before' score must match the label on
    file, so a correction can't silently apply to the wrong answer."""
    by_id = {r["label_id"]: r for r in rows}
    for i, ch in reviewed.items():
        if i not in by_id or by_id[i]["score_c"] != ch["score_before"]:
            raise ValueError(f"review of {i}: score_before {ch['score_before']} does not match labels.csv")
    return [{**r, "score_c": reviewed[r["label_id"]]["score_after"]} if r["label_id"] in reviewed
            else dict(r) for r in rows]


# --- reports ------------------------------------------------------------------------------------

def _fmt(v, pct=False):
    if v is None:
        return "not defined"
    return f"{100 * v:.0f}%" if pct else f"{v:.2f}"


def _ci(rows, stat, pct=False):
    lo, hi, _, dropped = cluster_bootstrap(rows, "core_id", stat, n=N_BOOT, return_draws=True,
                                           return_dropped=True)
    note = f"; {dropped} resamples undefined" if dropped else ""
    return f"{_fmt(lo, pct)} to {_fmt(hi, pct)}{note}"


def agreement_md(rows, reviewed: dict | None = None) -> str:
    n = len(rows)
    clusters = len({r["core_id"] for r in rows})
    L = ["# Judge agreement with Cynthia's hand labels (rubric v1)", "",
         f"{n} answers from the full run, labelled blind by Cynthia, compared with the judge used in",
         "the results (Haiku 5.5 for non-Anthropic models, GPT-6.2 Sol for Anthropic models). This is",
         "the headline agreement number (SPEC FR-14). Generated by `scripts/agreement.py`.", "",
         f"Intervals: 95%, cluster bootstrap over the {clusters} core prompts in the sample "
         f"({N_BOOT:,} resamples, seed 20261119).", "",
         "**The sample over-represents score 2 and preachy answers** (FR-13): it was drawn as equal",
         "thirds by judge score, while the full run is 31% / 44% / 25%. Kappa depends on that mix, so",
         "agreement within each judge score is reported too; it does not.", "",
         "## Score", "",
         "| Measure | Value | 95% interval |", "|---|---|---|",
         f"| Same score | {sum(r['score_c'] == r['score_j'] for r in rows)} of {n} "
         f"({_fmt(same_share(rows), True)}) | {_ci(rows, same_share, True)} |",
         f"| Weighted kappa (linear) | {_fmt(score_kappa(rows))} | {_ci(rows, score_kappa)} |",
         f"| Two steps apart (0 vs 2) | {sum(abs(r['score_c'] - r['score_j']) == 2 for r in rows)} "
         f"of {n} | |",
         f"| Judge higher / lower | {sum(r['score_j'] > r['score_c'] for r in rows)} / "
         f"{sum(r['score_j'] < r['score_c'] for r in rows)} | |", "",
         "Rows: Cynthia's score. Columns: the judge's score.", "",
         "| | judge 0 | judge 1 | judge 2 | total |", "|---|---|---|---|---|"]
    for c in (0, 1, 2):
        cells = [sum(r["score_c"] == c and r["score_j"] == j for r in rows) for j in (0, 1, 2)]
        L.append(f"| **Cynthia {c}** | " + " | ".join(map(str, cells)) + f" | {sum(cells)} |")
    L.append("| total | " + " | ".join(str(sum(r["score_j"] == j for r in rows)) for j in (0, 1, 2))
             + f" | {n} |")
    L += ["", "Agreement within each judge score (of the answers the judge gave that score, how many",
          "Cynthia scored the same):", "", "| Judge score | Cynthia agreed | 95% interval |",
          "|---|---|---|"]
    for s, (agree, tot) in within_judge_score(rows).items():
        def stat(rs, s=s):
            g = [r for r in rs if r["score_j"] == s]
            return sum(r["score_c"] == s for r in g) / len(g) if g else None
        L.append(f"| {s} | {agree} of {tot} ({_fmt(agree / tot, True)}) | {_ci(rows, stat, True)} |")

    L += ["", "## Flags", "", "| Flag | Answers | Cynthia yes | Judge yes | Both yes | Kappa | 95% interval |",
          "|---|---|---|---|---|---|---|"]
    for name, c, j, only_pet in (("preachy", "preachy_c", "preachy_j", False),
                                 ("companion harm", "harm_c", "harm_j", True),
                                 ("clarify only", "clarify_c", "clarify_j", False)):
        rs = [r for r in rows if r["pet_risk"]] if only_pet else rows
        def stat(sub, c=c, j=j):
            return flag_kappa([bool(r[c]) for r in sub], [bool(r[j]) for r in sub])
        k = stat(rs)
        ci = _ci(rs, stat) if k is not None else ""
        L.append(f"| {name} | {len(rs)} | {sum(bool(r[c]) for r in rs)} | {sum(bool(r[j]) for r in rs)} "
                 f"| {sum(bool(r[c]) and bool(r[j]) for r in rs)} | {_fmt(k)} | {ci} |")
    L += ["", "Companion harm is asked only on prompts tagged `pet_risk`. Clarify only: kappa is not",
          "defined when neither rater ever says yes."]
    if reviewed:
        rv = apply_review(rows, reviewed)
        L += ["", "## After Cynthia's review (second number, not the headline)", "",
              "After seeing the disagreements, Cynthia corrected labels she judged to be slips. These",
              "numbers are optimistic: each correction was made knowing the judge's score. The",
              "headline above uses the labels as first given.", "",
              "| Measure | Value | 95% interval |", "|---|---|---|",
              f"| Same score | {sum(r['score_c'] == r['score_j'] for r in rv)} of {len(rv)} "
              f"({_fmt(same_share(rv), True)}) | {_ci(rv, same_share, True)} |",
              f"| Weighted kappa (linear) | {_fmt(score_kappa(rv))} | {_ci(rv, score_kappa)} |", "",
              "| Label | Was | Now | Judge | Reason |", "|---|---|---|---|---|"]
        jud = {r["label_id"]: r["score_j"] for r in rows}
        L += [f"| {i} | {c['score_before']} | {c['score_after']} | {jud[i]} | {c['reason']} |"
              for i, c in sorted(reviewed.items())]
    return "\n".join(L) + "\n"


def _quote(text: str) -> str:
    return "\n".join("> " + line if line else ">" for line in text.splitlines())


def disagreements_md(rows) -> str:
    dis = [r for r in rows if r["score_c"] != r["score_j"]]
    dis.sort(key=lambda r: (-abs(r["score_c"] - r["score_j"]), r["label_id"]))
    L = ["# Disagreements: judge vs Cynthia (rubric v1)", "",
         f"{len(dis)} of {len(rows)} answers got a different score. Two-step disagreements first.",
         "Each shows the prompt, the note, both scores, Cynthia's comment, the judge's reasoning, and",
         "the full answer. Generated by `scripts/agreement.py`.", ""]
    for r in dis:
        L += [f"### {r['label_id']}: Cynthia {r['score_c']}, judge {r['score_j']} "
              f"({r['core_id']}, {r['model'].split('/')[-1]})", "",
              f"**Prompt:** {r['prompt']}", "", f"**Note:** {r['note']}", "",
              f"**Cynthia's comment:** {r['comment'] or '(none)'}", "",
              f"**Judge's reasoning:** {r['rationale']}", "",
              "<details><summary>Full answer</summary>", "", _quote(r["answer"]), "", "</details>", ""]
    agreed = [r for r in rows if r["score_c"] == r["score_j"] and r["comment"]]
    L += ["## Cynthia's comments where she and the judge agreed on the score", ""]
    L += [f"- **{r['label_id']}** ({r['core_id']}, both {r['score_c']}): {r['comment']}"
          for r in agreed] or ["None."]
    return "\n".join(L) + "\n"


def main() -> None:
    rows = load_rows()
    (ROOT / "results" / "agreement.md").write_text(agreement_md(rows, load_review()))
    (ROOT / "results" / "disagreements.md").write_text(disagreements_md(rows))
    print((ROOT / "results" / "agreement.md").read_text())


if __name__ == "__main__":
    main()
