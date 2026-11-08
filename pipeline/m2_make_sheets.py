# -*- coding: utf-8 -*-
"""生成 M2 空白标注表（A/B 两份，独立填写）与编码映射模板。
产物：annotator_A.csv / annotator_B.csv / catalog_template.csv
幂等：覆盖写出。
"""
import csv
from pathlib import Path

import os
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # repository root
OUT = Path(os.path.join(REPO, "annotation"))

rows = list(csv.DictReader(open(OUT / "sample100.csv", encoding="utf-8-sig")))

for who in ("A", "B"):
    with open(OUT / f"annotator_{who}.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["tid", "instance", "failure_cause", "key_steps", "confidence"])
        for r in rows:
            w.writerow([r["tid"], r["instance"], "", "", ""])

# 编码映射模板：自由文本 → 目录码（我合并目录后回填，用于 κ 计算）
with open(OUT / "catalog_template.csv", "w", newline="", encoding="utf-8-sig") as f:
    w = csv.writer(f)
    w.writerow(["catalog_code", "catalog_label", "example_free_text", "count"])
    w.writerow(["C01", "", "", 0])

print("written: annotator_A.csv annotator_B.csv catalog_template.csv;",
      "rows:", len(rows))
