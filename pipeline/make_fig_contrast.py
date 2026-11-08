# -*- coding: utf-8 -*-
"""Figure 3: contrast profile of the 72,972 delivered failure chains.

Statistic (M4b reviewer fix, Section 4.2): add-one-smoothed contrast
c' = supp(s, T_F) / (supp(s, T_S) + 1/|T_S|), which bounds c' by |T_S| and
turns the degenerate zero-success contrast into the finite value
sf * |T_S| (the two perfect signatures, c' = 30.2, form their own ranking
group ordered by failing support).

Panel (a): histogram of log10(c'); most chains are failure-agnostic
(c' ~ 1; median 1.40), only 731 chains clear the c' >= 5 guardrail
admission bar, and the two perfect signatures are marked separately.
Panel (b): c' vs failing-corpus support (log-log, 5,000 sampled);
high-contrast chains live one to two orders of magnitude below the support
of failure-agnostic chains (the support-contrast trade-off of Section 6.1).

Output: fig3_contrast.svg (text as paths; converted to EMF by Inkscape).
Data: 05_experiments/results/chains.jsonl (verified numbers).
"""
import json
import random

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import os
FS = float(os.environ.get("FIG_FS", "1"))  # 全局字号系数(2026-11-06统一图字号)

plt.rcParams.update({
    "svg.fonttype": "path",   # keep text vector in Word/PDF
    "font.size": 10*FS,
    "axes.titlesize": 11,
    "axes.labelsize": 11,
    "legend.fontsize": 9.5*FS,
    "xtick.labelsize": 9.5,
    "ytick.labelsize": 9.5,
    "axes.linewidth": 0.8,
})

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # repository root
RES = os.path.join(REPO, "results")
OUT = os.path.join(REPO, "figures", "fig3_contrast.svg")

contrast_sm, supp, perfect = [], [], []
with open(RES + r"\chains.jsonl") as f:
    for line in f:
        c = json.loads(line)
        contrast_sm.append(c["contrast_sm"])
        supp.append(c["supp_fail"])
        perfect.append(c["perfect"])
contrast_sm = np.array(contrast_sm)
supp = np.array(supp)
perfect = np.array(perfect)
n = len(contrast_sm)
n5 = int((contrast_sm >= 5).sum())
n_perfect = int(perfect.sum())
assert n == 72972 and n5 == 731 and n_perfect == 2, (n, n5, n_perfect)

rng = random.Random(42)
idx = rng.sample(range(n), 5000)

fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(6.5, 2.9))

# ---- panel (a): distribution of log10 smoothed contrast ----
lc = np.log10(contrast_sm.clip(min=1e-9))
bins = np.linspace(-1.2, 1.6, 60)
n_bulk = int((contrast_sm < 5).sum())   # 72,241 failure-agnostic chains
ax1.hist(lc, bins=bins, color="#9ecae1", edgecolor="#3182bd", linewidth=0.3)
ax1.axvline(0.0, color="k", linestyle="--", linewidth=0.9)
ax1.axvline(np.log10(5), color="#cb181d", linestyle="--", linewidth=0.9)
lp = np.log10(30.18)   # the two perfect signatures
ax1.plot([lp], [3], marker="v", color="#cb181d", markersize=4, linewidth=0)
ymax = ax1.get_ylim()[1]

# shade and label the diagnostic tail (fills the otherwise empty right side)
ax1.text(1.55, ymax * 0.97, "diagnostic tail", fontsize=9*FS,
         color="#cb181d", va="top", ha="right", style="italic",
         bbox=dict(fc="white", ec="none", alpha=0.85, pad=1.4))

# narrative of the bulk: 99% of chains carry no failure signal
# (placed in the empty upper-left zone; arrow points at the tall bulk bars)
ax1.annotate("", xy=(0.10, ymax * 0.60), xytext=(0.42, ymax * 0.40),
             arrowprops=dict(arrowstyle="->", linewidth=0.7, color="#08519c"))
ax1.text(-1.13, ymax * 0.50,
         f"99.0% of chains ({n_bulk:,})\n"
         "behave like success:\nno contrast, no signal",
         fontsize=9*FS, color="#08519c", va="top", ha="left",
         bbox=dict(fc="white", ec="none", alpha=0.78, pad=1.6))

ax1.text(-1.13, ymax * 0.97, "c' = 1\n(failure-agnostic)", fontsize=9*FS,
         va="top", ha="left")
ax1.annotate("", xy=(0.0, ymax * 0.62), xytext=(-0.35, ymax * 0.80),
             arrowprops=dict(arrowstyle="->", linewidth=0.6, color="k"))
ax1.text(1.55, ymax * 0.72,
         f"c' = 5 guardrail bar:\n{n5:,} chains (1.0%)", fontsize=9*FS,
         color="#cb181d", va="top", ha="right",
         bbox=dict(fc="white", ec="none", alpha=0.85, pad=1.6))
ax1.text(1.55, ymax * 0.24,
         "2 perfect signatures\n(zero succeeding support),\nc' = 30.2, own group",
         fontsize=8.5*FS, va="top", ha="right")
ax1.set_xlabel(r"$\log_{10}$ smoothed contrast $c'$")
ax1.set_ylabel("number of chains")
ax1.set_title("(a) contrast distribution", loc="left")
ax1.set_xlim(-1.2, 1.6)
ax1.spines[["top", "right"]].set_visible(False)

# ---- panel (b): smoothed contrast vs failing support (log-log) ----
ax2.scatter(supp[idx] * 100, contrast_sm[idx], s=2.5, c="#c6dbef",
            alpha=0.55, linewidths=0, rasterized=False)
hi = np.where(contrast_sm[np.array(idx)] >= 5)[0]
ax2.scatter(supp[np.array(idx)[hi]] * 100,
            contrast_sm[np.array(idx)[hi]],
            s=4, c="#cb181d", linewidths=0,
            label=f"admissible c' \u2265 5: {n5:,} chains")
ax2.plot(supp[perfect] * 100, contrast_sm[perfect], marker="v",
         color="#cb181d", markersize=4, linewidth=0)
ax2.set_yscale("log")
ax2.axhline(1.0, color="k", linestyle="--", linewidth=0.9)
ax2.axhline(5.0, color="#cb181d", linestyle="--", linewidth=0.9)
ax2.set_xscale("log")
ax2.set_xlabel("failing-corpus support (%)")
ax2.set_ylabel(r"smoothed contrast $c'$")
ax2.set_title("(b) contrast vs. support", loc="left")
ax2.legend(loc="lower left", frameon=False, fontsize=8.5*FS)
ax2.spines[["top", "right"]].set_visible(False)

fig.tight_layout(w_pad=2.0)
fig.savefig(OUT, format="svg", bbox_inches="tight", pad_inches=0.03)
print(OUT, "written")
