# -*- coding: utf-8 -*-
"""Figure 8 (update of old Figure 6, 6.5): guardrail operating curves over the
FULL coverage interval (R3 response).
  - chain rules, admission c' >= 5, k swept to all 731 rules (k-curve)
  - same rules traced by relaxing the contrast admission floor (floor-curve,
    coverage up to 54%)
  - single-symbol ablation (length-1 rules) at its available points
  - PrefixGuard [7] coverage-matched points (from old guardrail_eval)
Data: guardrail_curve.json (C4), guardrail_eval.json, prefixguard_eval.json.
matplotlib -> SVG (text as paths) -> EMF for Word embedding.
"""
import json
import os

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

plt.rcParams.update({
    "svg.fonttype": "path",
    "font.family": "DejaVu Sans",
    "font.size": 8,
})

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # repository root
EXP = REPO
cur = json.load(open(os.path.join(EXP, "results", "guardrail_curve.json")))
old = json.load(open(os.path.join(EXP, "results", "guardrail_eval.json")))
pg = json.load(open(os.path.join(EXP, "results", "prefixguard_eval.json")))

FIG_W, FIG_H = 6.5, 3.0
fig, ax = plt.subplots(figsize=(FIG_W, FIG_H))
fig.subplots_adjust(left=0.075, right=0.985, top=0.90, bottom=0.15)

# 主曲线1：k-curve（c' >= 5 准入，k 到 731）
xs = [r["coverage"] * 100 for r in cur["k_curve"]]
ys = [r["lift"] for r in cur["k_curve"]]
ax.plot(xs, ys, "-o", color="#C0392B", lw=1.8, ms=4, zorder=7,
        label="chain rules, admission $c' \\geq 5$ (k swept to all 731)")

# 主曲线2：floor-curve（放宽准入，覆盖到54%）
xs = [r["coverage"] * 100 for r in cur["floor_curve"] if r["n_rules"] > 0]
ys = [r["lift"] for r in cur["floor_curve"] if r["n_rules"] > 0]
ax.plot(xs, ys, "-^", color="#7D3C98", lw=1.6, ms=4, zorder=6,
        label="same rules, contrast admission relaxed")

# 消融：单符号规则（旧数据 k<=100）
xs = [r["coverage"] * 100 for r in old["single_symbol_rules"]]
ys = [r["lift"] for r in old["single_symbol_rules"]]
ax.plot(xs, ys, "-s", color="#909497", lw=1.4, ms=3.5, zorder=4,
        label="single-symbol rules (ablation)")

# PrefixGuard 覆盖匹配点
cm_raw = pg.get("coverage_matched_to_table3") or {}
cm = [v for _, v in sorted(cm_raw.items())] if isinstance(cm_raw, dict) else cm_raw
if cm:
    xs = [p["coverage"] * 100 for p in cm]
    ys = [p["lift"] for p in cm]
    ax.plot(xs, ys, "D", color="#1B4F72", ms=4.5, ls="none", zorder=5,
            label="PrefixGuard [7] (coverage-matched)")

ax.axhline(1.0, color="#555555", lw=0.8, ls="--", zorder=1)
ax.set_xlabel("coverage (% of the 1,000-trajectory held-out evaluation pool)")
ax.set_ylabel("fail-rate lift (intercepted / unintercepted)")
ax.set_xlim(-1, 57)
ax.set_ylim(0.8, 3.2)
ax.grid(True, ls=":", lw=0.5, color="#BBBBBB", zorder=0)
ax.legend(loc="upper right", frameon=False, fontsize=8)
for spine in ("top", "right"):
    ax.spines[spine].set_visible(False)

out = os.path.dirname(os.path.abspath(__file__))
fig.savefig(os.path.join(out, "fig8_guardrail.svg"),
            bbox_inches="tight", pad_inches=0.03)
print("wrote fig8_guardrail.svg")
