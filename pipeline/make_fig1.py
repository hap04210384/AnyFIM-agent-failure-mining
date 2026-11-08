# -*- coding: utf-8 -*-
"""Figure 1: pipeline overview (two-layer threshold-free anytime mining).
Pure-vector matplotlib -> SVG (text as paths) -> EMF for Word embedding.
"""
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch, Rectangle

plt.rcParams.update({
    "svg.fonttype": "path",        # keep figures font-independent vectors
    "font.family": "DejaVu Sans",
    "font.size": 8,
})

FIG_W, FIG_H = 6.5, 3.4
fig = plt.figure(figsize=(FIG_W, FIG_H))
ax = fig.add_axes([0, 0, 1, 1])
ax.set_xlim(0, 100)
ax.set_ylim(-3.5, 52)
ax.axis("off")

C_ENC = "#EAF2FB"   # encoder
C_GPU = "#FDEBD7"   # itemset layer
C_CPU = "#E8F8F0"   # sequence layer
C_OUT = "#F4ECF7"   # outputs
C_EDGE = "#5D6D7E"
C_SIG_HI = "#C0392B"
C_SIG_LO = "#F5B7B1"


def box(x, y, w, h, face, title, lines, ec=C_EDGE, title_fs=8.2, fs=7.2):
    ax.add_patch(FancyBboxPatch(
        (x, y), w, h, boxstyle="round,pad=0.4,rounding_size=1.2",
        fc=face, ec=ec, lw=1.0))
    ax.text(x + w / 2, y + h - 2.4, title, ha="center", va="center",
            fontsize=title_fs, fontweight="bold", color="#1B2631")
    ax.text(x + w / 2, y + (h - 3.4) / 2, lines, ha="center", va="center",
            fontsize=fs, color="#1B2631", linespacing=1.45)


def arrow(x1, y1, x2, y2, label=None, lx=0, ly=0, style="-|>", color=C_EDGE,
          lw=1.4, ls="-"):
    ax.add_patch(FancyArrowPatch(
        (x1, y1), (x2, y2), arrowstyle=style, mutation_scale=11,
        color=color, lw=lw, linestyle=ls, shrinkA=1, shrinkB=1))
    if label:
        ax.text((x1 + x2) / 2 + lx, (y1 + y2) / 2 + ly, label,
                ha="center", va="center", fontsize=6.6, color="#34495E",
                bbox=dict(fc="white", ec="none", pad=0.6))


# ---- top band: input -> encoder -> itemset layer -> contrast annotation
box(2, 34, 15, 15, C_ENC, "Agent trajectories",
    "5,000 traces\n(bash tool calls,\nresolved labels)")
box(21, 34, 17, 15, C_ENC, "Trajectory encoder",
    "itemset transactions\n(29 items)\n+\ncommand-family\nprojections (58 syms)")
box(42, 34, 20, 15, C_GPU, "Itemset layer (GPU)",
    "two released open-source\nengines\nsupport-ordered MFI\nstream, 29 stages\n(no threshold σ)")
box(66, 34, 15, 15, C_OUT, "Contrast annotation",
    "failing vs\nsucceeding pool\ncontrast c(X)\n1,581 signatures")
box(85, 34, 13, 15, C_OUT, "Evidence packs",
    "signature +\nsupport +\ncontrast +\ninstance ids")

arrow(17, 41.5, 21, 41.5)
arrow(38, 41.5, 42, 41.5)
arrow(62, 41.5, 66, 41.5)
arrow(81, 41.5, 85, 41.5)

# ---- signature stream strip under itemset layer
ax.text(52, 31.2, "delivery order: stage 1 \u2192 stage 29 (support descending)",
        ha="center", fontsize=6.4, color="#5D6D7E", style="italic")
for i in range(18):
    w = 1.35 - i * 0.045
    x = 42.6 + i * 1.12
    shade = plt.matplotlib.colors.to_hex(
        plt.matplotlib.colors.hsv_to_rgb((0.02, 0.75 - i * 0.02, 0.95 - i * 0.01)))
    ax.add_patch(Rectangle((x, 28.6), w, 1.7, fc=shade, ec="none"))
ax.text(42.6 + 18 * 1.12 + 0.6, 29.5, "...", fontsize=8, color="#5D6D7E",
        va="center")

# ---- coupling arrow down to sequence layer
arrow(52, 28.2, 52, 22.8,
      label="allowed-symbol coupling (one-way \u2014 safe: cannot add failing-pool bias)",
      lx=0, ly=1.9, color="#7D3C98", lw=1.8)

# ---- sequence layer
box(30, 8, 44, 14, C_CPU, "Sequence layer (CPU)",
    "signature-constrained prefix-projected chain enumeration\n"
    "maximality filter \u00b7 contrast \u2265 1% support floor\n"
    "72,972 maximal failure chains, contrast-ordered")
box(78, 8, 20, 14, C_OUT, "Guardrail rules",
    "top-k chains \u2192\nlive interception\nrules (Sec. 6.3)")
arrow(74, 15, 78, 15)

# ---- anytime axis
ax.annotate("", xy=(99, 3.2), xytext=(2, 3.2),
            arrowprops=dict(arrowstyle="-|>", color="#1B2631", lw=1.2))
for xpos, lab in [(8, "t=0: stream starts"),
                  (36, "2.2 s: itemset\nstream complete"),
                  (66, "17.8 s: chains\ndelivered"),
                  (90, "any B: take current\ndelivery and stop")]:
    ax.plot([xpos, xpos], [2.6, 3.8], color="#1B2631", lw=1.0)
    ax.text(xpos, 1.0, lab, ha="center", va="top", fontsize=6.4,
            color="#1B2631", linespacing=1.3)
# budget marker
ax.plot([80, 80], [2.6, 3.8], color=C_SIG_HI, lw=1.4, linestyle="--")
ax.text(80, 4.6, "budget B", ha="center", fontsize=6.8, color=C_SIG_HI,
        fontweight="bold")
ax.text(1.2, 4.9, "anytime:", fontsize=6.8, color="#1B2631", fontweight="bold")

fig.savefig("fig1_pipeline.svg", format="svg")
print("fig1_pipeline.svg written")
