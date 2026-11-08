# -*- coding: utf-8 -*-
"""Cohen's κ 计算（M2 标注一致性）。

输入：两份编码后的标注表（自由文本已由 catalog 映射为目录码），列：tid, code。
用法：
    python compute_kappa.py annotator_A_coded.csv annotator_B_coded.csv
输出：总体 Cohen's κ（单标签）、逐类目 κ 与混淆摘要；同时把结果写入
results/m2_kappa.json（含 n、per-category、overall）。
"""
import csv
import json
import sys
from collections import Counter
from pathlib import Path

import os
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # repository root
ROOT = Path(REPO)


def load(path):
    with open(path, encoding="utf-8-sig") as f:
        return {r["tid"].strip(): r["code"].strip()
                for r in csv.DictReader(f) if r.get("code", "").strip()}


def kappa(a, b, cats):
    n = sum(1 for t in a if t in b)
    po = sum(1 for t in a if t in b and a[t] == b[t]) / max(n, 1)
    ca, cb = Counter(a[t] for t in a if t in b), Counter(b[t] for t in a if t in b)
    pe = sum((ca[c] / n) * (cb[c] / n) for c in cats) if n else 0.0
    return po, (po - pe) / (1 - pe) if pe < 1 else 1.0, n


def main():
    pa, pb = sys.argv[1], sys.argv[2]
    a, b = load(pa), load(pb)
    common = [t for t in a if t in b]
    cats = sorted({a[t] for t in common} | {b[t] for t in common})
    po, k, n = kappa(a, b, cats)

    per = {}
    for c in cats:
        aa = {t: (a[t] == c) for t in common}
        bb = {t: (b[t] == c) for t in common}
        _, kc, _ = kappa(aa, bb, [True, False])
        per[c] = round(kc, 4)

    disagree = [(t, a[t], b[t]) for t in common if a[t] != b[t]]
    out = {
        "n_common": n,
        "observed_agreement": round(po, 4),
        "cohens_kappa": round(k, 4),
        "per_category": per,
        "n_disagree": len(disagree),
        "disagreements": disagree,
        "sources": [pa, pb],
    }
    dst = ROOT / "results" / "m2_kappa.json"
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k2: v for k2, v in out.items() if k2 != "disagreements"},
                     ensure_ascii=False, indent=1))
    print("disagreements (tid, A, B):", len(disagree))


if __name__ == "__main__":
    main()
