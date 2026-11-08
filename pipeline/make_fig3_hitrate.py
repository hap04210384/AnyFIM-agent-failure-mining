# -*- coding: utf-8 -*-
"""Figure 4 (new): human-catalog agreement.
Panel (a): hit-rate_expr@k of the delivered chain stream against the
           independent six-mode failure catalog (m2_hitrate.json).
Panel (b): distribution of the 100 human-labeled failure modes
           (catalog.csv, adjudicated counts; kappa = 1.0 per m2_kappa.json).
Pure-vector matplotlib -> SVG (text as paths) -> EMF for Word embedding.
"""
import csv
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
hit = json.load(open(os.path.join(EXP, "results", "m2_hitrate.json")))

# ---------- panel (a): hit-rate@k ----------
ks = sorted(int(k) for k in hit["hit_rate_at_k"])
hr = [hit["hit_rate_at_k"][str(k)]["hit_rate_expr"] for k in ks]

FIG_W, FIG_H = 6.5, 2.9
fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(FIG_W, FIG_H),
                               gridspec_kw={"width_ratios": [1.25, 1]})
fig.subplots_adjust(left=0.085, right=0.985, top=0.90, bottom=0.15,
                    wspace=0.34)

ax1.plot(ks, [h * 100 for h in hr], "-o", color="#C0392B", lw=1.6, ms=4.5,
         zorder=5, label="hit-rate$_{expr}$@$k$")
lbl_off = {10: (0, 6), 20: (0, -15), 50: (0, 7), 100: (0, -14), 500: (0, -15)}
for k, h in zip(ks, hr):
    ax1.annotate(f"{h*100:.0f}%", xy=(k, h * 100),
                 xytext=lbl_off[k], textcoords="offset points",
                 ha="center", fontsize=7.0*FS, color="#C0392B")

# first-hit ranks of the four matchable modes: thin dotted vlines, with
# short labels in two staggered rows at the top (no leader lines)
ranks = {c: r for c, r in hit["first_hit_rank"].items() if r}
row_a, row_b = {"C05", "C06", "C01"}, {"C02", "C04"}
ha_map = {"C05": "left", "C02": "left", "C06": "center",
          "C04": "center", "C01": "right"}
for c, r in ranks.items():
    ax1.axvline(r, color="#95A5A6", lw=0.8, ls=":", zorder=1)
    y = 74 if c in row_a else 64
    ax1.text(r, y, f"{c} #{r:,}", fontsize=6.6*FS, color="#5D6D7E",
             ha=ha_map[c], va="center")

ax1.set_xscale("log")
ax1.set_xlim(4, 60000)
ax1.set_ylim(0, 80)
ax1.set_xlabel("top-$k$ chains considered (log scale)", fontsize=8.5*FS)
ax1.set_ylabel("catalog modes matched (%)", fontsize=8.5*FS)
ax1.grid(True, which="major", lw=0.4, color="#D5DBDB", zorder=0)
ax1.legend(loc="lower right", fontsize=7.2*FS, framealpha=0.95)
ax1.set_title("(a) catalog agreement vs. stream depth",
              fontsize=8.5*FS)

# ---------- panel (b): mode distribution ----------
codes, labels, counts = [], [], []
with open(os.path.join(EXP, "data", "annotation", "catalog.csv"),
          encoding="utf-8-sig") as f:
    for row in csv.DictReader(f):
        codes.append(row["code"])
        labels.append(row["label_en"])
        counts.append(int(row["count_A"]))

ypos = list(range(len(codes)))[::-1]
colors = ["#2471A3" if c in ("C01", "C02") else "#7F8C8D" for c in codes]
ax2.barh(ypos, counts, color=colors, height=0.62, zorder=5)
for y, n in zip(ypos, counts):
    ax2.text(n + 0.8, y, f"{n}", va="center", fontsize=7.4*FS, color="#212F3C")
ax2.set_yticks(ypos)
ax2.set_yticklabels([f"{c}" for c in codes], fontsize=7.6*FS)
ax2.set_xlim(0, 52)
ax2.set_xlabel("trajectories (of 100 labeled)", fontsize=8.5*FS)
ax2.grid(True, axis="x", lw=0.4, color="#D5DBDB", zorder=0)
ax2.set_title("(b) Human-labeled mode distribution", fontsize=8.5*FS)

fig.savefig("fig3_hitrate.svg", format="svg", bbox_inches="tight", pad_inches=0.03)
print("AUQC_expr =", hit["auqc_expr"], " counts =", dict(zip(codes, counts)))
print("fig3_hitrate.svg written")
