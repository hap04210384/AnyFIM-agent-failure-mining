# -*- coding: utf-8 -*-
"""Figure 7 (new): mining-pool sensitivity heatmap.
18-configuration sweep (m4a_recall_sweep.json): mining pools of 200/300/400
task instances x absolute support floor {5, 10, 20}, chain length cap 4.
Cell value: recall@20 of the top-20 mined guardrail rules on the SAME
held-out evaluation pool (1,000 trajectories, 269 failing); annotated with
the number of rules admitted per configuration.
Pure-vector matplotlib -> SVG (text as paths) -> EMF for Word embedding.
"""
import json
import os

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import os
FS = float(os.environ.get("FIG_FS", "1"))  # 全局字号系数(2026-11-06统一图字号)

plt.rcParams.update({
    "svg.fonttype": "path",
    "font.family": "DejaVu Sans",
    "font.size": 8*FS,
})

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # repository root
EXP = REPO
d = json.load(open(os.path.join(EXP, "results", "m4a_recall_sweep.json")))

insts = [200, 300, 400]
floors = [5, 10, 20]
M = np.full((len(insts), len(floors)), np.nan)
N = np.full((len(insts), len(floors)), np.nan)
for r in d["results"]:
    if r["maxlen"] != 4:
        continue
    i, j = insts.index(r["n_instances"]), floors.index(r["floor"])
    M[i, j] = r["recall_at"]["20"] * 100
    N[i, j] = r["n_rules"]

FIG_W, FIG_H = 6.5, 2.7
fig, ax = plt.subplots(figsize=(FIG_W, FIG_H))
fig.subplots_adjust(left=0.14, right=0.90, top=0.93, bottom=0.13)

im = ax.imshow(M, cmap="Blues", vmin=0, vmax=12, aspect="auto")
ax.set_xticks(range(len(floors)))
ax.set_xticklabels([str(f) for f in floors], fontsize=8*FS)
ax.set_yticks(range(len(insts)))
ax.set_yticklabels([f"{n} tasks" for n in insts], fontsize=8*FS)
ax.set_xlabel("absolute support floor (trajectories)", fontsize=8.5*FS)
ax.set_ylabel("mining-pool size", fontsize=8.5*FS)
ax.set_title("recall@20 of top-20 rules on the held-out pool (%)",
             fontsize=8.5*FS)

for i in range(len(insts)):
    for j in range(len(floors)):
        v = M[i, j]
        n = int(N[i, j])
        ax.text(j, i - 0.14, f"{v:.1f}", ha="center", va="center",
                fontsize=9.5*FS, fontweight="bold", color="#1B2A3A")
        ax.text(j, i + 0.24, f"{n} rules", ha="center", va="center",
                fontsize=6.6*FS, color="#5D6D7E")

cb = fig.colorbar(im, ax=ax, fraction=0.045, pad=0.03)
cb.ax.tick_params(labelsize=7)
cb.set_label("recall@20 (%)", fontsize=8*FS)

fig.savefig("fig7_heatmap.svg", format="svg", bbox_inches="tight", pad_inches=0.03)
print("matrix (%):\n", np.round(M, 2))
print("rules:\n", N)
print("fig7_heatmap.svg written")
