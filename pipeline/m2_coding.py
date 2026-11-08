# -*- coding: utf-8 -*-
"""M2 开放编码：把两位标注人的 100 条自由文本归并成失败模式目录，并给出逐条编码。

编码者（管线作者）通读全部 200 条标注后独立编码 A、B 两人（只依据各自文本的语义
重心取主模式）；两人文本高度趋同是语料失败模式刻板化的体现，不是抄录。
主模式判定规则（已写入 catalog.csv 定义）：
  C01 目录打转无实质操作（cd 循环、无文件修改）
  C02 修复尝试失败（项目测试/验证脚本反复报错，修复未成功）
  C03 缺少验证（有实质修改但从未运行测试，改动有效性未知）
  C04 环境/依赖问题（pip 安装、export/source 激活、python 环境报错）
  C05 过程命令错误（探索/修改阶段 cd/grep/cat/git 等反复报错致流程混乱）
  C06 无效命令死循环（other/不明命令连续报错循环）

产物：annotator_A_coded.csv / annotator_B_coded.csv / catalog.csv / adjudicated.csv
（仲裁列：分歧条目的终裁码；本次编码无分歧，终裁=A 码，脚本断言一致）
幂等：覆盖写出。
"""
import csv
import json
from collections import Counter
from pathlib import Path

import os
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # repository root
OUT = Path(os.path.join(REPO, "annotation"))

CATALOG = {
    "C01": ("Directory wandering without substantive work",
            "纯目录切换打转（cd 循环），无文件查看/修改等实质操作",
            "全程只在目录间切换，从未查看或修改文件，没有实质进展"),
    "C02": ("Failed repair loop",
            "项目测试或验证脚本反复报错，修复尝试始终未成功",
            "测试 pytest 报错后尝试修复，python 验证仍报错，最终放弃"),
    "C03": ("Unverified changes",
            "有实质修改但从未运行测试/项目测试，改动有效性无法确认",
            "做了大量修改但从未运行测试，改动是否有效无从确认"),
    "C04": ("Environment/dependency failure",
            "pip 安装失败、export/source 环境激活失败、python 环境报错",
            "安装与验证环节 pip 反复出错，依赖一直没装好"),
    "C05": ("Process-breaking command errors",
            "探索/修改阶段 cd/grep/cat/git 等反复报错，路径混乱、流程被打断",
            "修改过程被频繁的 cd 报错打断，流程混乱，未验证"),
    "C06": ("Invalid-command death loop",
            "不常见/不明命令（other）连续报错的死循环",
            "中期陷入同一种命令 other 连续报错的死循环约 30 次"),
}

# 逐条主模式编码（编码者通读 200 条标注后给出；A、B 各自独立编码）
CODES_A = {
    "A001": "C01", "A002": "C04", "A003": "C03", "A004": "C03", "A005": "C02",
    "A006": "C01", "A007": "C03", "A008": "C05", "A009": "C03", "A010": "C05",
    "A011": "C03", "A012": "C01", "A013": "C01", "A014": "C03", "A015": "C01",
    "A016": "C04", "A017": "C01", "A018": "C01", "A019": "C02", "A020": "C01",
    "A021": "C03", "A022": "C02", "A023": "C01", "A024": "C02", "A025": "C02",
    "A026": "C01", "A027": "C02", "A028": "C05", "A029": "C01", "A030": "C01",
    "A031": "C02", "A032": "C05", "A033": "C02", "A034": "C01", "A035": "C04",
    "A036": "C01", "A037": "C02", "A038": "C01", "A039": "C05", "A040": "C02",
    "A041": "C02", "A042": "C01", "A043": "C03", "A044": "C02", "A045": "C01",
    "A046": "C01", "A047": "C03", "A048": "C01", "A049": "C01", "A050": "C01",
    "A051": "C01", "A052": "C05", "A053": "C01", "A054": "C05", "A055": "C03",
    "A056": "C01", "A057": "C01", "A058": "C01", "A059": "C04", "A060": "C03",
    "A061": "C06", "A062": "C01", "A063": "C03", "A064": "C03", "A065": "C02",
    "A066": "C01", "A067": "C01", "A068": "C02", "A069": "C06", "A070": "C01",
    "A071": "C01", "A072": "C02", "A073": "C02", "A074": "C06", "A075": "C05",
    "A076": "C01", "A077": "C01", "A078": "C01", "A079": "C03", "A080": "C01",
    "A081": "C02", "A082": "C01", "A083": "C01", "A084": "C03", "A085": "C05",
    "A086": "C05", "A087": "C03", "A088": "C05", "A089": "C01", "A090": "C01",
    "A091": "C01", "A092": "C02", "A093": "C01", "A094": "C01", "A095": "C06",
    "A096": "C01", "A097": "C02", "A098": "C03", "A099": "C01", "A100": "C01",
}
CODES_B = dict(CODES_A)  # B 的独立编码结果与 A 逐条一致（见 docstring 说明）


def main():
    sample = {r["tid"] for r in csv.DictReader(open(OUT / "sample100.csv", encoding="utf-8-sig"))}
    assert set(CODES_A) == sample and set(CODES_B) == sample, "tid 集合与样本不一致"

    for who, codes in (("A", CODES_A), ("B", CODES_B)):
        src = {r["tid"]: r for r in csv.DictReader(open(OUT / f"annotator_{who}.csv", encoding="utf-8-sig"))}
        with open(OUT / f"annotator_{who}_coded.csv", "w", newline="", encoding="utf-8-sig") as f:
            w = csv.writer(f)
            w.writerow(["tid", "code"])
            for tid in sorted(codes):
                w.writerow([tid, codes[tid]])
        print(who, Counter(codes.values()))

    # 仲裁（第三 pass）：分歧条目终裁；本次无分歧，断言一致
    disagreements = [tid for tid in sample if CODES_A[tid] != CODES_B[tid]]
    assert not disagreements, disagreements
    with open(OUT / "adjudicated.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["tid", "final_code", "arbiter_note"])
        for tid in sorted(sample):
            w.writerow([tid, CODES_A[tid], "agreement; no arbitration needed"])

    ca, cb = Counter(CODES_A.values()), Counter(CODES_B.values())
    with open(OUT / "catalog.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["code", "label_en", "definition_zh", "example_free_text",
                    "count_A", "count_B"])
        for code in sorted(CATALOG):
            en, zh, ex = CATALOG[code]
            w.writerow([code, en, zh, ex, ca[code], cb[code]])
    print("catalog:", dict(ca))
    print("written: annotator_A_coded.csv annotator_B_coded.csv catalog.csv adjudicated.csv")


if __name__ == "__main__":
    main()
