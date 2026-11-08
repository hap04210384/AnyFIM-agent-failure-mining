# -*- coding: utf-8 -*-
"""Figure 5 (new): anatomy of the 29-stage anytime stream (AnyFIM engine).
Left y-axis : cumulative number of maximal frequent itemsets (MFIs) delivered
              as each stage arrives (MFIsNumPerStage, cumsum) - step curve.
Right y-axis: per-stage absolute support floor (frequencyThrePerStage).
Data: AnyFIM-Anytime engine Results file (29 stages, full mining pool,
      997 failing transactions, dimension 29).
Pure-vector matplotlib -> SVG (text as paths) -> EMF for Word embedding.
"""
import os
import re

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import os
FS = float(os.environ.get("FIG_FS", "1.55"))  # 全局字号系数(2026-11-06统一图字号)

plt.rcParams.update({
    "svg.fonttype": "path",
    "font.family": "DejaVu Sans",
    "font.size": 8*FS,
})

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # repository root
_WS_ENGINE = os.path.join(
    os.path.dirname(REPO), "03_reproducibility", "code",  # workspace root (external)
    "Anytime-Frequent-Itemset-Mining", "code", "AnyFIM-Anytime", "AnytimeMining",
    "x64", "TransactionSets", "swebench_mine.txt-29-stages=Results.txt")
_PKG_ENGINE = (r"..\engine\AnyFIM-Anytime\AnytimeMining\x64\TransactionSets"
               r"\swebench_mine.txt-29-stages=Results.txt")
ENGINE = _PKG_ENGINE if os.path.exists(_PKG_ENGINE) else _WS_ENGINE

txt = open(ENGINE, encoding="utf-8", errors="replace").read()
mfi = [int(x) for x in re.search(r"MFIsNumPerStage:\s*([0-9,\s]+)",
                                 txt).group(1).replace(",", " ").split()]
thr = [int(x) for x in re.search(r"frequencyThrePerStage:\s*([0-9,\s]+)",
                                 txt).group(1).replace(",", " ").split()]
stages = np.arange(1, len(mfi) + 1)
cum_mfi = np.cumsum(mfi)

FIG_W, FIG_H = 6.5, 2.9
fig, ax1 = plt.subplots(figsize=(FIG_W, FIG_H))
fig.subplots_adjust(left=0.085, right=0.90, top=0.93, bottom=0.14)

# step curve: cumulative MFIs delivered up to stage k
ax1.step(np.append(stages, len(stages) + 1) - 0.5,
         np.append(cum_mfi, cum_mfi[-1]), where="post",
         color="#C0392B", lw=1.8, zorder=5)
ax1.fill_between(np.append(stages, len(stages) + 1) - 0.5,
                 np.append(cum_mfi, cum_mfi[-1]), step="post",
                 color="#C0392B", alpha=0.08, zorder=1)
ax1.set_xlabel("engine stage $k$ (support floor relaxed stage by stage)",
               fontsize=8.5*FS)
ax1.set_ylabel("cumulative MFIs delivered", fontsize=8.5*FS, color="#C0392B")
ax1.tick_params(axis="y", labelcolor="#C0392B")
ax1.set_xlim(0.5, len(stages) + 0.5)
ax1.set_xticks([1, 5, 10, 15, 20, 25, 29])
ax1.set_ylim(0, 1900)
ax1.grid(True, axis="y", lw=0.4, color="#D5DBDB", zorder=0)

# annotations
ax1.annotate(f"stage 29: floor = {thr[-1]} trajectory,\n{cum_mfi[-1]:,} MFIs total",
             xy=(29, cum_mfi[-1]), xytext=(16.2, 1500),
             fontsize=7.2*FS, color="#C0392B",
             arrowprops=dict(arrowstyle="-|>", color="#C0392B", lw=1.0))
ax1.annotate("knee: stages 12-14\n(dense mid-support region)",
             xy=(13, cum_mfi[12]), xytext=(4.0, 1150),
             fontsize=7.2*FS, color="#5D6D7E",
             arrowprops=dict(arrowstyle="-|>", color="#95A5A6", lw=0.9))

# right axis: per-stage absolute support floor
ax2 = ax1.twinx()
ax2.plot(stages, thr, "-", color="#2471A3", lw=1.3, marker="s", ms=3,
         zorder=4)
ax2.set_ylabel("absolute support floor\n(# failing trajectories)",
               fontsize=8.5*FS, color="#2471A3")
ax2.tick_params(axis="y", labelcolor="#2471A3")
ax2.set_ylim(0, 1100)
ax2.set_yscale("linear")

fig.savefig("fig5_stages.svg", format="svg", bbox_inches="tight", pad_inches=0.12)
print(f"stages={len(stages)} total_MFIs={cum_mfi[-1]} "
      f"floor: {thr[0]}->{thr[-1]}")
print("fig5_stages.svg written")
