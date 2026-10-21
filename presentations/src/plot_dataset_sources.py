"""Plot the designs and questions of dataset_v1 per source dataset.

Run: python3.11 presentations/src/plot_dataset_sources.py
Out: presentations/dataset_v1_sources.{png,pdf}, presentations/data/dataset_v1_sources.csv
"""
from __future__ import annotations

import csv
import json
from collections import Counter
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[2]
QUESTIONS = ROOT / "data/questions/dataset_v1.jsonl"
OUT = ROOT / "presentations"

# Source dataset of a design = the dataset of its base design (edits count to their base).
DATASETS = [  # (prefix of base_design_id, name, short description)
    ("revold_", "REvolution ASP-DAC 2026", "LLM answers to RTLLM, VerilogEval"),
    ("metrex_", "MetRex", "public"),
    ("rtllm_", "RTLLM v2.0", "public, verified + ChatGPT files"),
    ("rev_", "ARES", "own medium designs, v0"),
    ("ve_", "VerilogEval", "public, reference designs"),
]
KINDS = [  # request kind, legend text, categorical slot (reference palette, light mode)
    ("basic", "basic: compiles, synthesizes", "#2a78d6"),
    ("performance", "performance: slack, reach, area, power", "#eb6834"),
    ("reason", "reason: why DC rejects it", "#1baf7a"),
    ("pair", "pair: A or B (both orders)", "#eda100"),
]
EDIT_GROUPS = ("mutant", "trap", "noncompile")
SURFACE, INK, INK2, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#e4e3df"
ORIGINAL, EDIT = "#52514e", "#b5b3ad"


def dataset_of(base: str) -> str:
    for prefix, name, _ in DATASETS:
        if base.startswith(prefix):
            return name
    raise ValueError(f"no dataset for base design {base}")


def count():
    designs, questions = {}, Counter()
    for line in QUESTIONS.open():
        req = json.loads(line)
        ds = dataset_of(req["base_design_id"])
        questions[ds, req["request"]] += len(req["correct_answer"])
        if req["request"] != "pair":
            designs[req["design_id"]] = (ds, req["group"] in EDIT_GROUPS)
    d = Counter(designs.values())
    rows = []
    for _, name, desc in DATASETS:
        row = {"dataset": name, "description": desc,
               "designs_original": d[name, False], "designs_edit": d[name, True]}
        row.update({f"questions_{k}": questions[name, k] for k, _, _ in KINDS})
        rows.append(row)
    return rows


def label_in(ax, x, w, y, text, fill):
    # A value goes inside a segment only if it fits; ink or white by the fill luminance.
    r, g, b = (int(fill[i:i + 2], 16) / 255 for i in (1, 3, 5))
    color = INK if 0.2126 * r + 0.7152 * g + 0.0722 * b > 0.5 else "white"
    ax.text(x + w / 2, y, text, ha="center", va="center", fontsize=8.5, color=color)


def main():
    rows = count()
    with (OUT / "data/dataset_v1_sources.csv").open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)

    plt.rcParams.update({"font.family": "Liberation Sans",
                         "font.size": 10, "axes.edgecolor": GRID, "text.color": INK})
    fig, (ax_d, ax_q) = plt.subplots(1, 2, figsize=(12, 4.6), sharey=True,
                                     gridspec_kw={"width_ratios": [1, 1.9], "wspace": 0.06})
    fig.patch.set_facecolor(SURFACE)
    ys = list(range(len(rows)))[::-1]
    h = 0.55

    for ax in (ax_d, ax_q):
        ax.set_facecolor(SURFACE)
        ax.grid(axis="x", color=GRID, linewidth=1)
        ax.set_axisbelow(True)
        for s in ("top", "right", "left"):
            ax.spines[s].set_visible(False)
        ax.tick_params(axis="both", colors=INK2, length=0)

    # Left panel: designs, original RTL or script edit of a base design.
    for y, row in zip(ys, rows):
        x = 0
        for key, color in (("designs_original", ORIGINAL), ("designs_edit", EDIT)):
            n = row[key]
            if n:
                ax_d.barh(y, n, left=x, height=h, color=color, edgecolor=SURFACE, linewidth=2)
                if n >= 5:
                    label_in(ax_d, x, n, y, str(n), color)
                x += n
        ax_d.text(x + 1, y, str(x), va="center", fontsize=10, color=INK, fontweight="bold")
    ax_d.set_xlim(0, 62)
    ax_d.set_title("Designs (151)", loc="left", fontsize=11, color=INK, pad=24)
    ax_d.legend(handles=[plt.Rectangle((0, 0), 1, 1, color=ORIGINAL),
                         plt.Rectangle((0, 0), 1, 1, color=EDIT)],
                labels=["original RTL", "script edit of it"], loc="lower left",
                bbox_to_anchor=(0, 1.0), ncol=2, frameon=False, fontsize=9,
                handlelength=1, borderaxespad=0.2, labelcolor=INK2)

    # Right panel: questions per request kind.
    for y, row in zip(ys, rows):
        x = 0
        for key, _, color in KINDS:
            n = row[f"questions_{key}"]
            if n:
                ax_q.barh(y, n, left=x, height=h, color=color, edgecolor=SURFACE, linewidth=2)
                if n >= 18:
                    label_in(ax_q, x, n, y, str(n), color)
                x += n
        ax_q.text(x + 4, y, str(x), va="center", fontsize=10, color=INK, fontweight="bold")
    ax_q.set_xlim(0, 400)
    ax_q.set_title("Questions (875)", loc="left", fontsize=11, color=INK, pad=24)
    ax_q.legend(handles=[plt.Rectangle((0, 0), 1, 1, color=c) for _, _, c in KINDS],
                labels=[t for _, t, _ in KINDS], loc="lower left", bbox_to_anchor=(0, 1.0),
                ncol=4, frameon=False, fontsize=9, handlelength=1, borderaxespad=0.2,
                columnspacing=1.2, labelcolor=INK2)

    ax_d.set_yticks(ys)
    ax_d.set_yticklabels([f"{r['dataset']}\n{r['description']}" for r in rows], fontsize=9.5,
                         color=INK)
    fig.subplots_adjust(top=0.74)
    fig.suptitle("dataset_v1: designs and questions per source dataset", x=0.01, ha="left",
                 fontsize=13, fontweight="bold", color=INK, y=0.99)
    fig.text(0.01, 0.915, "An edit (mutant, trap, noncompile) counts to the dataset of its base "
             "design. All correct answers: vlog -sv and DC, NanGate 15nm, 500 MHz.",
             fontsize=9, color=INK2)
    for ext in ("png", "pdf"):
        fig.savefig(OUT / f"dataset_v1_sources.{ext}", dpi=200, bbox_inches="tight",
                    facecolor=SURFACE)


if __name__ == "__main__":
    main()
