# -*- coding: utf-8 -*-
"""M2 人工标注抽样：从评估池 269 条失败轨迹分层抽样 100 条。

分层维度：轨迹长度（短 <=40 / 中 41-90 / 长 >90）× 是否含错误动作（存在 :err token）。
层内按实例名字典序 + seed 42 用 numpy 无放回抽取，比例分配、每层至少 5 条。

产物（data/annotation/）：
- sample100.csv        机读：tid, model, instance, len, has_err, symbols（空格分隔 token）
- booklet.md           人读标注册：符号表 + 每条轨迹一节 + 空白标注栏
- strata_summary.json  分层概况（校验用）
幂等：固定 seed，重跑结果一致。
"""
import csv, json
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

import os
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # repository root
ROOT = Path(REPO)
ENC = ROOT / "data" / "encoded"
OUT = ROOT / "data" / "annotation"
N_TARGET = 100
MIN_PER_STRATUM = 5
SEED = 42


def len_band(n):
    return "short" if n <= 40 else ("mid" if n <= 90 else "long")


def main():
    OUT.mkdir(parents=True, exist_ok=True)

    # 符号表
    id2sym = {}
    with open(ENC / "seqmap.tsv", encoding="utf-8") as f:
        for line in f:
            i, s = line.rstrip("\n").split("\t")
            id2sym[int(i)] = s

    # 评估池失败轨迹
    rows = []
    with open(ENC / "labels_eval.csv", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if r["resolved"] == "False":
                rows.append(r)
    assert len(rows) == 269, len(rows)

    # 序列：SPMF 每行一条序列（token 与 -1 间隔、行尾 -2），无显式事务号；
    # 与 labels_eval.csv 由 encode_swebench.py 同一循环按相同顺序写出 → 行序对齐
    seqs = []
    with open(ENC / "sequences_eval.spmf", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            toks = [id2sym[int(x)] for x in line.split() if x not in ("-1", "-2")]
            seqs.append(toks)
    assert len(seqs) == len(rows), (len(seqs), len(rows))

    for r, toks in zip(rows, seqs):
        r["symbols"] = toks
        r["len"] = len(toks)
        r["has_err"] = any(t.endswith(":err") for t in toks)
        r["band"] = len_band(r["len"])

    # 分层抽样：比例分配 + 每层地板
    strata = defaultdict(list)
    for r in rows:
        strata[(r["band"], r["has_err"])].append(r)
    rng = np.random.default_rng(SEED)
    picked = []
    summary = {}
    total = len(rows)
    alloc = {k: max(MIN_PER_STRATUM, round(N_TARGET * len(v) / total)) for k, v in strata.items()}

    def alloc_total():
        return sum(min(a, len(strata[k])) for k, a in alloc.items())

    # 向目标数收敛：先调最大层，且不超过该层池大小
    guard = 0
    while alloc_total() != N_TARGET and guard < 1000:
        guard += 1
        cur = alloc_total()
        if cur < N_TARGET:
            k = max(alloc, key=lambda kk: len(strata[kk]) - min(alloc[kk], len(strata[kk])))
            if alloc[k] < len(strata[k]):
                alloc[k] += 1
            else:  # 所有层都满 → 目标不可达，降低期望
                break
        else:
            k = max((kk for kk in alloc if alloc[kk] > MIN_PER_STRATUM),
                    key=lambda kk: alloc[kk], default=None)
            if k is None:
                break
            alloc[k] -= 1
    for k, v in strata.items():
        n = min(alloc[k], len(v))
        idx = rng.choice(len(v), size=n, replace=False)
        got = [v[i] for i in sorted(idx, key=lambda i: v[i]["instance"])]
        picked.extend(got)
        summary[f"{k[0]}|err={k[1]}"] = {"pool": len(v), "picked": len(got)}
    picked.sort(key=lambda r: r["instance"])

    # 机读 CSV
    with open(OUT / "sample100.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["tid", "model", "instance", "len", "has_err", "symbols"])
        for i, r in enumerate(picked, 1):
            w.writerow([f"A{i:03d}", r["model"], r["instance"], r["len"],
                        int(r["has_err"]), " ".join(r["symbols"])])

    # 符号表（只列样本中出现过的）
    used = Counter(t for r in picked for t in r["symbols"])
    glossary = "\n".join(f"| `{s}` | {c} |" for s, c in used.most_common())

    # 人读标注册
    lines = ["# M2 失败轨迹标注册（样本 100 条）", "",
             "每条轨迹：`动作:结果` token 序列，按步顺序排列，10 个一行。",
             "请在每节的标注栏填写：①失败原因（自由文本一句话）②关键步骤号区间（可选）③置信度（高/中/低）。",
             "",
             "## 符号表（按出现频次排序）", "",
             "| 符号 | 出现次数 |", "| --- | --- |", glossary, "",
             "---", ""]
    for i, r in enumerate(picked, 1):
        toks = r["symbols"]
        body = "\n".join(" ".join(toks[j:j + 10]) for j in range(0, len(toks), 10))
        lines += [f"## A{i:03d} · {r['instance']} · {r['model']} · {r['len']} 步"
                  + (" · 含错误动作" if r["has_err"] else ""), "",
                  "```", body, "```", "",
                  "**① 失败原因**：", "", "**② 关键步骤区间**（如 12–18，可空）：", "",
                  "**③ 置信度**（高/中/低）：", "", "---", ""]
    (OUT / "booklet.md").write_text("\n".join(lines), encoding="utf-8")

    with open(OUT / "strata_summary.json", "w", encoding="utf-8") as f:
        json.dump({"seed": SEED, "n_target": N_TARGET, "strata": summary}, f, ensure_ascii=False, indent=2)

    print("picked:", len(picked))
    print(json.dumps(summary, ensure_ascii=False, indent=1))
    print("err present:", sum(1 for r in picked if r["has_err"]))
    print("len range:", min(r["len"] for r in picked), "-", max(r["len"] for r in picked))


if __name__ == "__main__":
    main()
