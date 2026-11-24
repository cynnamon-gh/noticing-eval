"""Main results from the full run (BUILD_PLAN M6.4; SPEC FR-18–FR-22, FR-24).

Reads the judged logs (default logs/full_v2, rubric v2) and writes one CSV per breakdown to
results/tables/:
  by_model.csv           FR-18 metrics per model, with 95% intervals
  by_model_without_conditional.csv   the same without the 4 conditional-note prompts
  by_voice.csv           noticing rate per voice (all models pooled), with intervals (FR-21)
  by_domain.csv          noticing rate per domain (all models pooled)
  by_tag.csv             with vs without insect / conditional-note / conservation prompts, and by
                         visibility and src
  size_pairs.csv         small model minus its same-family frontier model (FR-22)
  gaps.csv               highest-minus-lowest model and voice gaps (FR-21)

Noticing rate = share of answers scored 2 (the headline, FR-18). Inclusion rate = share scored 1
or 2. Intervals: cluster bootstrap over the 68 core prompts, 10,000 resamples, seed fixed (FR-20).
Model differences are computed inside each resample.

For speed, answers are first summed per (core prompt, group); resampling those sums gives exactly
the same draws as resampling the answers by cluster (tests/test_analyze.py checks this).

Run:  .venv/bin/python scripts/analyze.py [log_dir] [output folder under results/]
"""

from __future__ import annotations

import csv
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from noticing.bootstrap import cluster_bootstrap  # noqa: E402

N_BOOT = 10_000
SHORT = {
    "anthropic/claude-sonnet-5.5": "Claude Sonnet 5.5", "anthropic/claude-haiku-5.5": "Claude Haiku 5.5",
    "openai/gpt-6.2-sol": "GPT-6.2 Sol", "google/gemini-4-carbon": "Gemini 4 Carbon",
    "meta-llama/llama-4-maverick": "Llama 4 Maverick", "meta-llama/llama-3.1-8b-instruct": "Llama 3.1 8B",
    "deepseek/deepseek-v4-pro": "DeepSeek V4 Pro", "deepseek/deepseek-v4.1-flash": "DeepSeek V4.1 Flash",
}
SIZE_PAIRS = [("Claude Haiku 5.5", "Claude Sonnet 5.5"), ("Llama 3.1 8B", "Llama 4 Maverick"),
              ("DeepSeek V4.1 Flash", "DeepSeek V4 Pro")]


def load_rows(log_dir: Path) -> list[dict]:
    """One row per scored answer."""
    from inspect_ai.log import read_eval_log
    rows = []
    for path in sorted(log_dir.glob("*.eval")):
        log = read_eval_log(str(path))
        model = SHORT[log.eval.model.removeprefix("openrouter/")]
        for s in log.samples:
            sc = s.scores["noticing_judge"]
            md = sc.metadata or {}
            if md.get("unscored"):
                continue
            m = s.metadata
            rows.append({"model": model, "core_id": m["core_id"], "voice": m["voice"],
                         "domain": m["domain"], "visibility": m["visibility"], "src": m["src"],
                         "insect": m["insect"], "conditional_note": m["conditional_note"],
                         "conservation": m["conservation"], "pet_risk": m["pet_risk"],
                         "score": int(sc.value), "preachy": bool(md["preachy"]),
                         "companion_harm": bool(md["companion_harm"]),
                         "clarify_only": bool(md["clarify_only"])})
    return rows


# --- per-cluster sums ---------------------------------------------------------------------------

FIELDS = ("n", "two", "incl", "score", "preachy", "clarify", "pet_n", "harm")


def cluster_sums(rows, group_key) -> list[dict]:
    """One row per core prompt: for each group, the counts needed by every metric."""
    by_core: dict = defaultdict(lambda: defaultdict(lambda: dict.fromkeys(FIELDS, 0)))
    for r in rows:
        g = by_core[r["core_id"]][group_key(r)]
        g["n"] += 1
        g["two"] += r["score"] == 2
        g["incl"] += r["score"] >= 1
        g["score"] += r["score"]
        g["preachy"] += r["preachy"]
        g["clarify"] += r["clarify_only"]
        g["pet_n"] += r["pet_risk"]
        g["harm"] += r["pet_risk"] and r["companion_harm"]
    return [{"core_id": c, "groups": dict(gs)} for c, gs in by_core.items()]


def total(clusters, group, field) -> int:
    return sum(c["groups"].get(group, {}).get(field, 0) for c in clusters)


def rate(clusters, group, num, den="n"):
    d = total(clusters, group, den)
    return total(clusters, group, num) / d if d else None


def ci(clusters, stat, n=N_BOOT):
    return cluster_bootstrap(clusters, "core_id", stat, n=n)


# --- tables -------------------------------------------------------------------------------------

def _pct(x):
    return "" if x is None else round(100 * x, 1)


def by_group(rows, key, n=N_BOOT, full=False) -> list[dict]:
    cl = cluster_sums(rows, key)
    groups = sorted({key(r) for r in rows}, key=str)
    out = []
    for g in groups:
        lo, hi = ci(cl, lambda c, g=g: rate(c, g, "two"), n)
        row = {"group": g, "answers": total(cl, g, "n"),
               "core_prompts": sum(1 for c in cl if g in c["groups"]),
               "noticing_rate_pct": _pct(rate(cl, g, "two")), "ci_low": _pct(lo), "ci_high": _pct(hi)}
        if full:
            ilo, ihi = ci(cl, lambda c, g=g: rate(c, g, "incl"), n)
            row.update({"inclusion_rate_pct": _pct(rate(cl, g, "incl")), "incl_ci_low": _pct(ilo),
                        "incl_ci_high": _pct(ihi),
                        "mean_score": round(rate(cl, g, "score"), 3),
                        "preachy_rate_pct": _pct(rate(cl, g, "preachy")),
                        "companion_harm_rate_pct": _pct(rate(cl, g, "harm", "pet_n")),
                        "clarify_only_rate_pct": _pct(rate(cl, g, "clarify"))})
        out.append(row)
    return out


def gap(rows, key, n=N_BOOT) -> dict:
    """Highest minus lowest group's noticing rate, with the groups fixed by the full data and the
    difference recomputed inside each resample."""
    cl = cluster_sums(rows, key)
    groups = sorted({key(r) for r in rows}, key=str)
    rates = {g: rate(cl, g, "two") for g in groups}
    hi_g, lo_g = max(rates, key=rates.get), min(rates, key=rates.get)
    lo, hi = ci(cl, lambda c: rate(c, hi_g, "two") - rate(c, lo_g, "two"), n)
    return {"highest": hi_g, "lowest": lo_g, "gap_pct": _pct(rates[hi_g] - rates[lo_g]),
            "ci_low": _pct(lo), "ci_high": _pct(hi)}


def size_pairs(rows, n=N_BOOT) -> list[dict]:
    cl = cluster_sums(rows, lambda r: r["model"])
    out = []
    for small, big in SIZE_PAIRS:
        d = rate(cl, small, "two") - rate(cl, big, "two")
        lo, hi = ci(cl, lambda c, s=small, b=big: rate(c, s, "two") - rate(c, b, "two"), n)
        out.append({"small": small, "frontier": big, "small_minus_frontier_pct": _pct(d),
                    "ci_low": _pct(lo), "ci_high": _pct(hi)})
    return out


def write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as f:
        w = csv.DictWriter(f, list(rows[0]))
        w.writeheader()
        w.writerows(rows)


def main() -> None:
    log_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "logs" / "full_v2"
    rows = load_rows(log_dir)
    out = ROOT / "results" / (sys.argv[2] if len(sys.argv) > 2 else "tables")
    write_csv(out / "by_model.csv", by_group(rows, lambda r: r["model"], full=True))
    # Sensitivity: the same, leaving out the 4 prompts with a conditional note (SPEC FR-19).
    write_csv(out / "by_model_without_conditional.csv",
              by_group([r for r in rows if not r["conditional_note"]], lambda r: r["model"], full=True))
    write_csv(out / "by_voice.csv", by_group(rows, lambda r: r["voice"]))
    write_csv(out / "by_domain.csv", by_group(rows, lambda r: r["domain"]))
    tag_rows = []
    for tag in ("insect", "conditional_note", "conservation", "visibility", "src"):
        for row in by_group(rows, lambda r, t=tag: r[t]):
            tag_rows.append({"tag": tag, **row})
    write_csv(out / "by_tag.csv", tag_rows)
    write_csv(out / "size_pairs.csv", size_pairs(rows))
    write_csv(out / "gaps.csv", [{"between": "models", **gap(rows, lambda r: r["model"])},
                                 {"between": "voices", **gap(rows, lambda r: r["voice"])}])
    print(f"{len(rows)} scored answers from {log_dir}; tables in {out}")
    for name in ("by_model", "by_voice", "size_pairs", "gaps"):
        print(f"\n== {name}\n" + (out / f"{name}.csv").read_text())


if __name__ == "__main__":
    main()
