# -*- coding: utf-8 -*-
"""Figure 3: anytime quality-budget curves on the SWE-bench mining pool.
Data sources (all real, 2026-09-28 full-corpus runs):
  - AnyFIM cumulative per-stage runtime: 05_experiments/logs/anyfim_swebench_full.log
  - cumulative delivered signatures:      05_experiments/results/signatures.jsonl
  - chain delivery endpoint:              chain_stats.json (15.6 s, 72,972 chains)
  - FP-Growth / PrefixSpan / VMSP grids:  results/baselines_itemset.json,
                                          results/baselines_sequence.json
Pure-vector matplotlib -> SVG (text as paths) -> EMF for Word embedding.
"""
import json
import os
import re

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import os
FS = float(os.environ.get("FIG_FS", "1.45"))  # 全局字号系数(2026-11-06统一图字号)

plt.rcParams.update({
    "svg.fonttype": "path",
    "font.family": "DejaVu Sans",
    "font.size": 8*FS,
})

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # repository root
EXP = REPO

# ---- AnyFIM per-stage runtime (log: "kth stage MFIsNum: n, runtime: t")
# NOTE: the engine logs PER-STAGE runtime; cumulative wall-clock = cumsum.
stages, times, counts = [], [], []
pat = re.compile(r"(\d+)th stage MFIsNum: (\d+), runtime: ([\d.eE+-]+)")
for line in open(os.path.join(EXP, "logs", "anyfim_swebench_full.log"),
                 encoding="utf-8", errors="replace"):
    m = pat.search(line)
    if m:
        stages.append(int(m.group(1)))
        counts.append(int(m.group(2)))
        times.append(float(m.group(3)))
times = list(np.cumsum(times))          # cumulative delivery wall-clock
ITEMSET_WALL = times[-1]                # ~2.2 s for all 29 stages

# ---- cumulative delivered signatures per stage (annotated stream)
stage_cum = {}
for l in open(os.path.join(EXP, "results", "signatures.jsonl"), encoding="utf-8"):
    s = json.loads(l)
    stage_cum[s["stage"]] = stage_cum.get(s["stage"], 0) + 1
sig_t, sig_cum = [], []
c = 0
for k in sorted(stage_cum):
    c += stage_cum[k]
    sig_t.append(times[k - 1])
    sig_cum.append(c)
N_SIG = c

# ---- chain delivery endpoint (enumeration clock, from the sequence-layer run:
# "level 4: 67344 candidates (15.6s)"; end-to-end incl. annotation/maximality
# is 95.45 s per chain_stats.json and is stated in the figure caption)
chain_stats = json.load(open(os.path.join(EXP, "results", "chain_stats.json")))
CHAIN_ENUM_S = 15.6
chain_wall = ITEMSET_WALL + CHAIN_ENUM_S
N_CHAIN = chain_stats["n_chains"]

# ---- baselines
item = json.load(open(os.path.join(EXP, "results", "baselines_itemset.json")))
seq = json.load(open(os.path.join(EXP, "results", "baselines_sequence.json")))
fp_x = [r["wall_s"] for r in item["runs"] if r["wall_s"]]
fp_y = [r["n_patterns"] for r in item["runs"] if r["wall_s"]]
ps = {r["minsup"]: r for r in seq["runs"] if r["algo"] == "PrefixSpan"}
ps_x = [r["wall_s"] for r in ps.values() if r["wall_s"]]
ps_y = [r["n_patterns"] for r in ps.values() if r["wall_s"]]
vm = {r["minsup"]: r for r in seq["runs"] if r["algo"] == "VMSP"}
vm_x = [r["wall_s"] for r in vm.values() if r["wall_s"]]
vm_y = [r["n_patterns"] for r in vm.values() if r["wall_s"]]

FIG_W, FIG_H = 6.5, 3.6
fig, ax = plt.subplots(figsize=(FIG_W, FIG_H))
fig.subplots_adjust(left=0.125, right=0.985, top=0.96, bottom=0.30)

# our framework: signatures then chains
ax.plot(sig_t, sig_cum, "-", color="#C0392B", lw=2.0,
        label="ours: signatures (itemset layer)", zorder=5)
ax.plot([sig_t[-1], chain_wall], [N_SIG, N_SIG + N_CHAIN], "--",
        color="#C0392B", lw=1.6, zorder=5)
ax.plot([chain_wall], [N_SIG + N_CHAIN], "o", color="#C0392B", ms=5, zorder=6)
ax.annotate(f"chains delivered\n({CHAIN_ENUM_S:.1f} s enumeration)",
            xy=(chain_wall, N_SIG + N_CHAIN), xytext=(2.2, 5.0e6),
            fontsize=7.2*FS, color="#C0392B",
            arrowprops=dict(arrowstyle="-|>", color="#C0392B", lw=1.0))
ax.annotate(f"{N_SIG:,} signatures @ {ITEMSET_WALL:.1f} s",
            xy=(sig_t[-1], N_SIG), xytext=(2.6e-3, 3.0),
            fontsize=7.2*FS, color="#C0392B",
            arrowprops=dict(arrowstyle="-|>", color="#C0392B", lw=1.0))

# baselines
ax.plot(fp_x, fp_y, "s", ms=3.5, color="#7F8C8D", ls="none",
        label="FP-Growth grid (20 runs)", zorder=4)
order = np.argsort(ps_x)
ax.plot(np.array(ps_x)[order], np.array(ps_y)[order], "-", color="#2471A3",
        lw=1.3, marker="^", ms=4, label="PrefixSpan", zorder=4)
order = np.argsort(vm_x)
ax.plot(np.array(vm_x)[order], np.array(vm_y)[order], "-", color="#7D3C98",
        lw=1.3, marker="d", ms=4, label="VMSP (maximal)", zorder=4)

# timeouts at the 120 s budget
ax.plot([120], [max(ps_y) * 2.2], "x", color="#2471A3", ms=8, mew=2, zorder=6)
ax.plot([120], [max(vm_y) * 3.0], "x", color="#7D3C98", ms=8, mew=2, zorder=6)
ax.annotate("PrefixSpan: killed at budget;\n15.6M patterns (1.5 GB) already written",
            xy=(120, max(ps_y) * 2.2), xytext=(2.2e-4, 3.0e6),
            fontsize=7.0*FS, color="#2471A3",
            arrowprops=dict(arrowstyle="-|>", color="#2471A3", lw=0.9))
ax.annotate("VMSP: killed at budget\n(maximal sequences)",
            xy=(120, max(vm_y) * 3.0), xytext=(4.0e-3, 2.5e4),
            fontsize=7.0*FS, color="#7D3C98",
            arrowprops=dict(arrowstyle="-|>", color="#7D3C98", lw=0.9))

ax.axvline(120, color="#95A5A6", lw=0.9, ls=":")
ax.text(105, 6.5e5, "per-run budget 120 s", fontsize=6.8*FS, color="#5D6D7E",
        ha="right")

ax.set_xscale("log")
ax.set_yscale("log")
ax.set_xlim(7e-5, 500)
ax.set_ylim(0.7, 6e7)
ax.set_xlabel("wall-clock time (s, log scale)", fontsize=8.5*FS)
ax.set_ylabel("patterns delivered (log scale)", fontsize=8.5*FS)
ax.grid(True, which="major", lw=0.4, color="#D5DBDB", zorder=0)
fig.legend(loc="lower center", bbox_to_anchor=(0.52, 0.0), ncol=2,
           frameon=True, framealpha=0.95, fontsize=7.2*FS)

# bbox_inches tight + 对称 pad：让图框紧贴墨迹，Word 中居中即视觉居中（2026-09-30 图4居中修复）
fig.savefig("fig3_anytime.svg", format="svg", bbox_inches="tight", pad_inches=0.12)
print(f"sig={N_SIG} chains={N_CHAIN} chain_wall={chain_wall:.2f}s")
print("fig3_anytime.svg written")
