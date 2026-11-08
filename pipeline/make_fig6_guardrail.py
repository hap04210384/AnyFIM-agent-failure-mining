# -*- coding: utf-8 -*-
"""Figure 6 (new): guardrail operating curves (lift vs. coverage).
Three rule sources scored on the same held-out evaluation pool
(1,000 trajectories, 26.9% base failure rate):
  - chain rules mined by our pipeline (top-k by smoothed contrast c')
  - single-symbol rules (length-1 signatures only, ablation)
  - PrefixGuard [7], coverage-matched to the same top-k operating points,
    plus PrefixGuard's own published operating point (m = 511 warnings).
Data: guardrail_eval.json, prefixguard_eval.json.
Pure-vector matplotlib -> SVG (text as paths) -> EMF for Word embedding.
"""
import json
import os

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
g = json.load(open(os.path.join(EXP, "results", "guardrail_eval.json")))
pg = json.load(open(os.path.join(EXP, "results", "prefixguard_eval.json")))

def xy(series):
    xs = [r["coverage"] * 100 for r in series]
    ys = [r["lift"] for r in series]
    return xs, ys

FIG_W, FIG_H = 6.5, 2.9
fig, ax = plt.subplots(figsize=(FIG_W, FIG_H))
fig.subplots_adjust(left=0.095, right=0.985, top=0.93, bottom=0.15)

xs, ys = xy(g["chain_rules"])
ax.plot(xs, ys, "-o", color="#C0392B", lw=1.8, ms=4.5, zorder=6,
        label="chain rules (ours)")
for x, y, r in zip(xs, ys, g["chain_rules"]):
    ax.annotate(f"k={r['k']}", xy=(x, y), xytext=(4, 4),
                textcoords="offset points", fontsize=6.6*FS, color="#C0392B")

xs, ys = xy(g["single_symbol_rules"])
ax.plot(xs, ys, "-s", color="#B7950B", lw=1.4, ms=4, zorder=5,
        label="single-symbol rules (ablation)")
for x, y in zip(xs, ys):
    ax.annotate(f"{y:.2f}", xy=(x, y), xytext=(4, -10),
                textcoords="offset points", fontsize=6.6*FS, color="#B7950B")

xs, ys = xy(pg["coverage_matched_to_table3"].values())
ax.plot(xs, ys, "-^", color="#2471A3", lw=1.4, ms=4, zorder=5,
        label="PrefixGuard (coverage-matched)")

op = pg["prefixguard_own_operating_point"]
ax.plot([op["coverage"] * 100], [op["lift"]], "*", color="#2471A3",
        ms=11, zorder=7)
ax.annotate(f"PrefixGuard own point\n(m = {op['m']} warnings): "
            f"lift {op['lift']:.2f}",
            xy=(op["coverage"] * 100, op["lift"]),
            xytext=(13, 2.55), fontsize=7.0*FS, color="#2471A3",
            arrowprops=dict(arrowstyle="-|>", color="#2471A3", lw=0.9))

ax.axhline(1.0, color="#95A5A6", lw=0.9, ls=":", zorder=2)
ax.text(0.17, 1.06, "no better than base rate", fontsize=6.8*FS,
        color="#5D6D7E", ha="left")

ax.set_xscale("log")
ax.set_xlim(0.15, 80)
ax.set_ylim(0, 3.2)
ax.set_xlabel("coverage (% of evaluation pool intercepted, log scale)",
              fontsize=8.5*FS)
ax.set_ylabel("lift (failure rate ratio)", fontsize=8.5*FS)
ax.grid(True, which="major", lw=0.4, color="#D5DBDB", zorder=0)
ax.legend(loc="lower center", fontsize=7.2*FS, framealpha=0.95)

# bbox_inches tight + 对称 pad：让图框紧贴墨迹，Word 中居中即视觉居中（2026-09-30 图6居中修复）
fig.savefig("fig6_guardrail.svg", format="svg", bbox_inches="tight", pad_inches=0.03)
print("chain k=5 lift:", [r["lift"] for r in g["chain_rules"] if r["k"] == 5])
print("fig6_guardrail.svg written")
