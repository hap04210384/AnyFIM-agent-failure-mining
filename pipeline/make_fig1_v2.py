# -*- coding: utf-8 -*-
"""Figure 1: pipeline overview (two-layer threshold-free anytime mining). v2 beautified.
Pure-vector matplotlib -> SVG (text as paths) -> EMF for Word embedding.
Same semantic content as v1; professional flat redesign.
"""
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch, Rectangle
import os
FS = float(os.environ.get("FIG_FS", "1"))  # 全局字号系数(2026-11-06统一图字号)

plt.rcParams.update({
    "svg.fonttype": "path",        # keep figures font-independent vectors
    "font.family": "DejaVu Sans",
    "font.size": 7.2*FS,
})

FIG_W, FIG_H = 6.5, 3.4
fig = plt.figure(figsize=(FIG_W, FIG_H))
ax = fig.add_axes([0, 0, 1, 1])
ax.set_xlim(0, 100)
ax.set_ylim(-4, 50.2)
ax.axis("off")

# ---- palette: restrained flat design, one warm accent on the core GPU layer
C_ENC  = "#EDF2F8"; E_ENC  = "#7C8DA6"   # encoder (input + trajectory encoder)
C_GPU  = "#FCEFD9"; E_GPU  = "#C98A2D"   # itemset layer — the contribution
C_CPU  = "#EBF4EE"; E_CPU  = "#6F9B80"   # sequence layer
C_OUT  = "#F3F5F7"; E_OUT  = "#8A97A5"   # outputs
C_ARR  = "#46586B"                        # arrows
C_PLUM = "#7C5C9E"                        # coupling (kept, slimmed)
TXT    = "#22303E"
SUB    = "#5A6B7C"
AMBER  = "#C98A2D"


def box(x, y, w, h, face, edge, title, lines,
        title_fs=7.4*FS, fs=7.0*FS, title_color=TXT):
    ax.add_patch(FancyBboxPatch(
        (x + 0.55, y - 0.65), w, h,
        boxstyle="round,pad=0.35,rounding_size=0.9",
        fc="#7C8DA6", ec="none", alpha=0.28, zorder=0.5))
    ax.add_patch(FancyBboxPatch(
        (x, y), w, h, boxstyle="round,pad=0.35,rounding_size=0.9",
        fc=face, ec=edge, lw=1.0, zorder=1.5))
    # title pinned just below the top edge
    ax.text(x + w / 2, y + h - 2.5, title, ha="center", va="center",
            fontsize=title_fs, fontweight="bold", color=title_color,
            linespacing=1.15)
    # body vertically centred in the space below the title
    ax.text(x + w / 2, y + (h - 3.6) / 2, lines, ha="center", va="center",
            fontsize=fs, color=TXT, linespacing=1.35)


def arrow(x1, y1, x2, y2, color=C_ARR, lw=1.3):
    ax.add_patch(FancyArrowPatch(
        (x1, y1), (x2, y2), arrowstyle="-|>", mutation_scale=10,
        color=color, lw=lw, shrinkA=1, shrinkB=1))


# ================= top band: input -> encoder -> itemset layer -> annotation -> packs
YB, HB = 33.5, 15.8
box(1.5,  YB, 15.5, HB, C_ENC, E_ENC,
    "Agent\ntrajectories", "5,000 traces\n(bash tool calls,\nresolved labels)")
box(19.625, YB, 21.0, HB, C_ENC, E_ENC,
    "Trajectory\nencoder", "itemset transactions\n(29 items)\ncommand-family\nprojections (58 syms)")
box(43.25, YB, 21.0, HB, C_GPU, E_GPU,
    "Itemset layer (GPU)",
    "AnyFIM / TensorFIM\nsupport-ordered MFI\nstream, 29 stages\n(no threshold \u03c3)",
    title_color="#8F5C10")
box(66.875, YB, 15.5, HB, C_OUT, E_OUT,
    "Contrast\nannotation", "failing vs\nsucceeding pool\ncontrast c(X)\n1,581 signatures")
box(85.0, YB, 13.5, HB, C_OUT, E_OUT,
    "Evidence\npacks", "signature +\nsupport +\ncontrast +\ninstance ids")

arrow(17.0, 40.75, 19.625, 40.75)
arrow(40.625, 40.75, 43.25, 40.75)
arrow(64.25, 40.75, 66.875, 40.75)
arrow(82.375, 40.75, 85.0, 40.75)

# ================= stage-delivery strip (support-descending mini bars)
ax.text(52, 30.4, "delivery order: stage 1 \u2192 stage 29 (support descending)",
        ha="center", fontsize=7.4*FS, color=SUB, style="italic")
BASE_Y = 26.8
n_bars = 29
x0 = 29.9  # 整体宽度 x1.5（以带中心 53 为基准对称展开），高度不变
BAR_H = 2.5  # 等高；首段很宽，细段宽度递收（编码 support, 2026-11-07 按参考版式）
RED = lambda v: plt.matplotlib.colors.to_hex(
    plt.matplotlib.colors.hsv_to_rgb((0.02, 0.72, v)))
for i in range(n_bars):
    t = i / (n_bars - 1)
    bw = 1.5 * (5.6 if i == 0 else 0.55 * (1.0 - 0.35 * t) + 0.14)
    ax.add_patch(Rectangle((x0, BASE_Y), bw, BAR_H,
                           fc=RED(0.95 - 0.38 * t), ec="none", zorder=2))
    x0 += bw + 1.5 * (0.10 + 0.45 * t)  # 间距随 t 增大：前密后疏
ax.text(x0 + 0.3, BASE_Y + BAR_H / 2 + 0.08, "\u2026",
        fontsize=8.5*FS, color=SUB, va="center")

# ================= coupling note (single line under the strip) + short arrow
ax.text(52, 24.7,
        "allowed-symbol coupling (one-way \u2014 safe: cannot add failing-pool bias)",
        ha="center", va="center", fontsize=7.4*FS, color=C_ARR)
arrow(52, 23.5, 52, 21.9, color=C_PLUM, lw=1.4)

# ================= sequence layer
box(24, 7.0, 52.0, 14.0, C_CPU, E_CPU,
    "Sequence layer (CPU)",
    "signature-constrained prefix-projected chain enumeration\n"
    "maximality filter \u00b7 contrast \u2265 1% support floor\n"
    "72,972 maximal failure chains, contrast-ordered")
box(78.5, 7.0, 19.5, 14.0, C_OUT, E_OUT,
    "Guardrail\nrules", "top-k chains \u2192\nlive interception\nrules (Sec. 6.3)")
arrow(76.0, 14.0, 78.5, 14.0)

# ================= anytime axis
AXY = 1.2
ax.annotate("", xy=(99, AXY), xytext=(1.5, AXY),
            arrowprops=dict(arrowstyle="-|>", color=TXT, lw=1.1))
for xpos, lab in [(8,  "t=0: stream starts"),
                  (36, "2.2 s: itemset\nstream complete"),
                  (66, "17.8 s: chains\ndelivered"),
                  (90, "any B: take current\ndelivery and stop")]:
    ax.plot([xpos, xpos], [AXY - 0.5, AXY + 0.5], color=TXT, lw=0.9)
    ax.text(xpos, AXY - 1.3, lab, ha="center", va="top", fontsize=6.3*FS,
            color=TXT, linespacing=1.3)
ax.plot([80, 80], [AXY - 0.5, AXY + 0.5], color="#C0392B", lw=1.2,
        linestyle=(0, (3, 2)))
ax.text(80, AXY + 1.4, "budget B", ha="center", fontsize=6.6*FS, color="#C0392B",
        fontweight="bold")
ax.text(1.5, AXY + 1.4, "anytime:", fontsize=6.6*FS, color=TXT,
        fontweight="bold", ha="left")

if len(sys.argv) > 1 and sys.argv[1] == "png":
    fig.savefig("fig1_v2_preview.png", dpi=200)
    print("fig1_v2_preview.png written")
else:
    fig.savefig("fig1_pipeline.svg", format="svg", bbox_inches="tight", pad_inches=0.03)
    print("fig1_pipeline.svg written")
