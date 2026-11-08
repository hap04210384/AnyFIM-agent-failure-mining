# -*- coding: utf-8 -*-
"""Figure 10 (new, 6.9): robustness of the delivered stream under telemetry
noise, one mini-panel per perturbation type (means over 3 seeds).
y-axis: chain survival @ top-1000 (left scale) and, on the same panel, the
head-stability of the strongest chains (top-20 by support) as a dashed line.
Data: robustness_c6.json (C6).
matplotlib -> SVG (text as paths) -> EMF for Word embedding.
"""
import json
import os
import statistics

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import os
FS = float(os.environ.get("FIG_FS", "1"))  # 全局字号系数(2026-11-06统一图字号)

plt.rcParams.update({
    "svg.fonttype": "path",
    "font.family": "DejaVu Sans",
    "font.size": 8*FS,
})

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # repository root
EXP = REPO
d = json.load(open(os.path.join(EXP, "results", "robustness_c6.json")))

KINDS = [("delete", "event deletion"),
         ("insert", "noise insertion"),
         ("substitute", "symbol substitution"),
         ("truncate", "trajectory truncation")]


def series(kind, metric):
    levels = sorted({c["level"] for c in d["configs"] if c["kind"] == kind})
    means = []
    for lv in levels:
        vals = [c[metric] for c in d["configs"]
                if c["kind"] == kind and c["level"] == lv]
        means.append(statistics.mean(vals))
    if kind == "truncate":
        levels = [round(1 - x, 2) for x in levels]  # 显示为截掉比例
    return levels, means


FIG_W, FIG_H = 6.5, 2.6
fig, axes = plt.subplots(1, 4, figsize=(FIG_W, FIG_H))
fig.subplots_adjust(left=0.065, right=0.99, top=0.86, bottom=0.19, wspace=0.62)

for ax, (kind, title) in zip(axes, KINDS):
    xs, ys = series(kind, "survival@1000")
    ax.plot(xs, ys, "-o", color="#2471A3", lw=1.7, ms=4, zorder=5,
            label="rule survival")
    xs, ys = series(kind, "head_stability")
    ax.plot(xs, ys, "--s", color="#C0392B", lw=1.5, ms=3.5, zorder=5,
            label="head stability")
    ax.set_xlabel("% events" if kind != "truncate" else "% truncated", fontsize=7.5*FS)
    ax.set_title(title, fontsize=7.6*FS)
    ax.set_ylim(-0.03, 1.08)
    ax.set_xlim(-3, 45 if kind != "truncate" else 75)
    ax.grid(True, ls=":", lw=0.5, color="#BBBBBB", zorder=0)
    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)
    if kind == "delete":
        ax.set_ylabel("fraction")
    ax.tick_params(labelsize=7.5)

axes[0].legend(loc="lower left", frameon=False, fontsize=6.4*FS)

out = os.path.dirname(os.path.abspath(__file__))
fig.savefig(os.path.join(out, "fig10_robustness.svg"),
            bbox_inches="tight", pad_inches=0.03)
print("wrote fig10_robustness.svg")
