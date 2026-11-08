# -*- coding: utf-8 -*-
"""Figure 3 (new, 6.2): detector precision and recall on the human-annotated
100-trajectory reference set as a function of the delivered-stream prefix k,
with Wilson 95% confidence intervals.
Data: pattern_quality_vs_annotation.json (C1).
matplotlib -> SVG (text as paths) -> EMF for Word embedding.
"""
import json
import math
import os

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import os
FS = float(os.environ.get("FIG_FS", "1.35"))  # 全局字号系数(2026-11-06统一图字号, 图3降到1.2与其他图一致)

plt.rcParams.update({
    "svg.fonttype": "path",
    "font.family": "DejaVu Sans",
    "font.size": 8*FS,
})

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # repository root
EXP = REPO
d = json.load(open(os.path.join(EXP, "results", "pattern_quality_vs_annotation.json")))
N = d["n_annotated_failing"]


def wilson(p_hat, n, z=1.959964):
    p_hat = min(1.0, max(0.0, p_hat))
    if n <= 0:
        return (p_hat, p_hat)
    denom = 1 + z * z / n
    c = (p_hat + z * z / (2 * n)) / denom
    h = z * math.sqrt(p_hat * (1 - p_hat) / n + z * z / (4 * n * n)) / denom
    return (c - h, c + h)


ks = [int(k) for k in d["at_k"].keys()]
ks.sort()
rec = [d["at_k"][str(k)]["detector_recall_annotated"] for k in ks]
n_flag = [d["at_k"][str(k)]["n_flagged"] for k in ks]
prec = [d["at_k"][str(k)]["detector_precision_annotated"] for k in ks]
n_correct = [round(r * N) for r in rec]

rec = [min(1.0, max(0.0, r)) for r in rec]
prec = [min(1.0, max(0.0, p)) for p in prec]
rec_ci = [wilson(r, N) for r in rec]
prec_ci = [wilson(c / f, f) if f > 0 else (0.0, 0.0)
           for c, f in zip(n_correct, n_flag)]

FIG_W, FIG_H = 6.5, 2.9
fig, axes = plt.subplots(1, 2, figsize=(FIG_W, FIG_H))
fig.subplots_adjust(left=0.065, right=0.99, top=0.90, bottom=0.16, wspace=0.24)

for ax, ys, ci, title, color in (
        (axes[0], rec, rec_ci, "recall on annotated failures (n=100)", "#C0392B"),
        (axes[1], prec, prec_ci, "precision of flagged trajectories", "#2471A3")):
    lo = [y - c[0] for y, c in zip(ys, ci)]
    hi = [c[1] - y for y, c in zip(ys, ci)]
    ax.errorbar(ks, ys, yerr=[lo, hi], fmt="-o", color=color, lw=1.7, ms=4,
                capsize=2.5, elinewidth=1, zorder=6)
    ax.set_xscale("log")
    from matplotlib.ticker import LogLocator
    ax.xaxis.set_major_locator(LogLocator(base=10.0, numticks=6))
    ax.set_xlabel("delivered-stream prefix  k")
    ax.set_ylim(-0.03, 1.03)
    ax.grid(True, which="both", ls=":", lw=0.5, color="#BBBBBB", zorder=0)
    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)
    ax.set_title(title, fontsize=8.5*FS)

axes[0].set_ylabel("recall")
axes[1].set_ylabel("precision")

# ---------- 叙事标注(2026-11-06): 数据点取自 pattern_quality_vs_annotation.json ----------
AFS = 7.5 * FS  # 标注字号

ax = axes[0]
# 尾部阴影区：cataloged failure modes 集中在诊断尾部
ax.text(1.2e5, 0.52, "tail: cataloged failure modes", ha="right",
        fontsize=AFS, color="#922B21", zorder=7)
# 头部近零区说明
ax.text(2.5, 0.35, "head: annotated recall $\\approx$ 0",
        fontsize=AFS, color="#555555", zorder=7)
# k=10^3 处标注（手稿：首个10%在此恢复）
ax.annotate("$k{=}10^3$: first 10%\nof annotated failures",
            xy=(1000, 0.11), xytext=(5, 0.66),
            fontsize=AFS, color="#555555",
            arrowprops=dict(arrowstyle="->", color="#777777", lw=0.8), zorder=8)
# 全流终点标注
ax.annotate("full stream: recall 0.76\n(72,972 patterns)",
            xy=(72972, 0.76), xytext=(8e2, 0.85),
            fontsize=AFS, color="#922B21",
            arrowprops=dict(arrowstyle="->", color="#777777", lw=0.8), zorder=8)

ax = axes[1]
# 精度稳定带
ax.text(1.6, 0.575, "precision stays in the\n0.42–0.76 band", fontsize=AFS,
        color="#1A5276", zorder=7)
# 极小预算单旗标说明
ax.annotate("$k{=}10$: 1 flag, all genuine\nbut covers 1 failure",
            xy=(10, 1.0), xytext=(12, 0.90),
            fontsize=AFS, color="#555555",
            arrowprops=dict(arrowstyle="->", color="#777777", lw=0.8), zorder=8)
# 全流终点
ax.annotate("0.76 at full stream", xy=(72972, 0.76), xytext=(3e3, 0.86),
            fontsize=AFS, color="#1A5276",
            arrowprops=dict(arrowstyle="->", color="#777777", lw=0.8), zorder=8)

out = os.path.dirname(os.path.abspath(__file__))
fig.savefig(os.path.join(out, "fig3_quality.svg"),
            bbox_inches="tight", pad_inches=0.03)
print("wrote fig3_quality.svg")
