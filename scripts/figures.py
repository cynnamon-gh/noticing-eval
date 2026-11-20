"""Figures for the write-up (BUILD_PLAN M6.5), drawn from results/tables/ and the v2 logs.

  results/figures/noticing_by_model.png    share of answers scored 2, per model, 95% interval;
                                           marker shows which judge scored the model
  results/figures/hidden_vs_visible.png    share of 2s per model, prompts that name an animal
                                           vs prompts that don't

Colours: the dataviz reference palette, slots 1 (blue) and 2 (orange), validated for light mode.
Run:  .venv/bin/python scripts/figures.py
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import analyze as an  # noqa: E402

BLUE, ORANGE = "#2a78d6", "#eb6834"
SURFACE, INK, INK2, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#e4e3df"
GPT_JUDGED = {"Claude Sonnet 5.5", "Claude Haiku 5.5"}
OUT = ROOT / "results" / "figures"


def _style(ax):
    ax.set_facecolor(SURFACE)
    for s in ("top", "right", "left"):
        ax.spines[s].set_visible(False)
    ax.spines["bottom"].set_color(GRID)
    ax.tick_params(colors=INK2, length=0)
    ax.xaxis.grid(True, color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)


def noticing_by_model():
    rows = list(csv.DictReader((ROOT / "results" / "tables" / "by_model.csv").open()))
    rows.sort(key=lambda r: float(r["noticing_rate_pct"]))
    fig, ax = plt.subplots(figsize=(7.5, 4.2), dpi=200, facecolor=SURFACE)
    _style(ax)
    for y, r in enumerate(rows):
        v, lo, hi = (float(r[k]) for k in ("noticing_rate_pct", "ci_low", "ci_high"))
        gpt = r["group"] in GPT_JUDGED
        ax.plot([lo, hi], [y, y], color=BLUE, linewidth=2, solid_capstyle="round")
        ax.plot(v, y, "o", markersize=8, markeredgewidth=2, markeredgecolor=BLUE if gpt else SURFACE,
                markerfacecolor=SURFACE if gpt else BLUE, zorder=3)
        ax.text(hi + 1.2, y, f"{v:.0f}%", va="center", fontsize=9, color=INK)
    ax.set_yticks(range(len(rows)), [r["group"] for r in rows], fontsize=9.5, color=INK)
    ax.set_xlim(0, 55)
    ax.set_xlabel("Answers scored 2 (option offered and said to be better for animals), %",
                  fontsize=9, color=INK2)
    ax.set_title("Noticing rate by model, with 95% intervals", loc="left", fontsize=11.5,
                 color=INK, pad=12)
    h1 = ax.plot([], [], "o", markersize=8, markerfacecolor=BLUE, markeredgecolor=SURFACE,
                 label="judged by Claude Haiku 5.5")[0]
    h2 = ax.plot([], [], "o", markersize=8, markerfacecolor=SURFACE, markeredgecolor=BLUE,
                 markeredgewidth=2, label="judged by GPT-6.2 Sol")[0]
    ax.legend(handles=[h1, h2], loc="lower right", frameon=False, fontsize=8.5, labelcolor=INK2)
    fig.text(0.01, 0.01, "3,264 answers, rubric v2. Intervals: cluster bootstrap over 68 core prompts.",
             fontsize=7.5, color=INK2)
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    fig.savefig(OUT / "noticing_by_model.png", facecolor=SURFACE)


def hidden_vs_visible():
    rows = an.load_rows(ROOT / "logs" / "full_v2")
    cl = an.cluster_sums(rows, lambda r: (r["model"], r["visibility"]))
    models = sorted({r["model"] for r in rows}, key=lambda m: an.rate(cl, (m, "visible"), "two"))
    fig, ax = plt.subplots(figsize=(7.5, 4.2), dpi=200, facecolor=SURFACE)
    _style(ax)
    for y, m in enumerate(models):
        h, v = (100 * an.rate(cl, (m, k), "two") for k in ("hidden", "visible"))
        ax.plot([h, v], [y, y], color=GRID, linewidth=2, zorder=1)
        ax.plot(h, y, "o", markersize=8, color=ORANGE, markeredgecolor=SURFACE, markeredgewidth=2, zorder=3)
        ax.plot(v, y, "o", markersize=8, color=BLUE, markeredgecolor=SURFACE, markeredgewidth=2, zorder=3)
    ax.set_yticks(range(len(models)), models, fontsize=9.5, color=INK)
    ax.set_xlim(0, 50)
    ax.set_xlabel("Answers scored 2, %", fontsize=9, color=INK2)
    ax.set_title("When the prompt never mentions an animal, noticing drops", loc="left",
                 fontsize=11.5, color=INK, pad=12)
    top = len(models) - 1
    hv = [100 * an.rate(cl, (models[top], k), "two") for k in ("hidden", "visible")]
    ax.annotate("animal not mentioned (28 prompts)", (hv[0], top), xytext=(0, 9),
                textcoords="offset points", ha="center", fontsize=8, color=INK2)
    ax.annotate("animal mentioned (40 prompts)", (hv[1], top), xytext=(0, 9),
                textcoords="offset points", ha="center", fontsize=8, color=INK2)
    ax.set_ylim(-0.6, top + 0.9)
    h1 = ax.plot([], [], "o", markersize=8, color=ORANGE, label="animal not mentioned")[0]
    h2 = ax.plot([], [], "o", markersize=8, color=BLUE, label="animal mentioned")[0]
    ax.legend(handles=[h2, h1], loc="lower right", frameon=False, fontsize=8.5, labelcolor=INK2)
    fig.text(0.01, 0.01, "Point estimates, rubric v2. Pooled gap 19.5 points (95% interval 8.1 to 30.9).",
             fontsize=7.5, color=INK2)
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    fig.savefig(OUT / "hidden_vs_visible.png", facecolor=SURFACE)


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    noticing_by_model()
    hidden_vs_visible()
    print("wrote", *sorted(p.name for p in OUT.glob("*.png")))
