# -*- coding: utf-8 -*-
"""Figure 5 (new, 6.3): engine scalability on stratified subsamples of the
SWE-bench failing pool (997 trajectories full; seeds fixed).
Left axis: engine wall time to emit the full MFI stream; bars per size.
Right axis: throughput (trajectories/s) as a line.
Data: scalability_c3.jsonl (C3).
matplotlib -> SVG (text as paths) -> EMF for Word embedding.
"""
import json
import os

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import os
FS = float(os.environ.get("FIG_FS", "1.6"))  # 全局字号系数(2026-11-06统一图字号)

plt.rcParams.update({
    "svg.fonttype": "path",
    "font.family": "DejaVu Sans",
    "font.size": 8*FS,
})

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # repository root
EXP = REPO
rows = [json.loads(l) for l in open(os.path.join(EXP, "results", "scalability_c3.jsonl"))]
rows.sort(key=lambda r: r["n_traj"])

n = [r["n_traj"] for r in rows]
t = [r["engine_wall_s"] for r in rows]
thr = [r["n_traj"] / r["engine_wall_s"] for r in rows]
labels = ["%d\n(%d%%)" % (r["n_traj"], r["pct"]) for r in rows]

FIG_W, FIG_H = 6.5, 2.9
fig, ax = plt.subplots(figsize=(FIG_W, FIG_H))
fig.subplots_adjust(left=0.075, right=0.90, top=0.90, bottom=0.17)

bars = ax.bar(range(len(n)), t, width=0.55, color="#2E86C1", zorder=3,
              label="engine wall time (s)")
for i, v in enumerate(t):
    ax.text(i, v + 0.03, "%.2f" % v, ha="center", va="bottom", fontsize=7.5*FS)
ax.set_xticks(range(len(n)))
ax.set_xticklabels(labels, fontsize=7.5*FS)
ax.set_xlabel("failing trajectories mined (percentage of the 997-trajectory pool)")
ax.set_ylabel("engine wall time (s)")
ax.set_ylim(0, max(t) * 1.25)
ax.grid(True, axis="y", ls=":", lw=0.5, color="#BBBBBB", zorder=0)
for spine in ("top",):
    ax.spines[spine].set_visible(False)

ax2 = ax.twinx()
ax2.plot(range(len(n)), thr, "-o", color="#C0392B", lw=1.8, ms=4.5, zorder=6,
         label="throughput (trajectories/s)")
ax2.set_ylabel("throughput (trajectories/s)", color="#C0392B")
ax2.tick_params(axis="y", labelcolor="#C0392B")
ax2.set_ylim(0, max(thr) * 1.3)
ax2.spines["top"].set_visible(False)

h1, l1 = ax.get_legend_handles_labels()
h2, l2 = ax2.get_legend_handles_labels()
ax.legend(h1 + h2, l1 + l2, loc="upper left", frameon=False, fontsize=8*FS)

out = os.path.dirname(os.path.abspath(__file__))
fig.savefig(os.path.join(out, "fig5_scalability.svg"),
            bbox_inches="tight", pad_inches=0.12)
print("wrote fig5_scalability.svg")
