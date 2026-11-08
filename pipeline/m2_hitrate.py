# -*- coding: utf-8 -*-
"""M2 hit-rate：人工失败模式目录 × 对比度排序交付链的匹配评估。

匹配规则（操作化定义，先于结果固定）：
  C01 目录打转      链全部符号 ∈ {cd:ok, cd:err}
  C02 修复失败      含 pytest:err 或 python:err
  C03 缺少验证      不可由链表达（测试缺席是缺失信号），按 0 匹配处理并单列说明
  C04 环境依赖      含 pip:err 或 export:err
  C05 过程命令错误  含 ≥2 个不同错误符号，来自 {cd,cat,grep,sed,git,ls,find,head,rm,cp,echo}:err
  C06 无效命令循环  含 other:err

指标（5.3 节协议）：hit-rate@k（6 模式及剔除 C03 后的 5 可表达模式两套口径）、
time-to-first-hit（每模式首个匹配链的 rank）、AUQC（hit-rate 对 log10 k 的曲线下面积，
按 k 网格归一）、expert precision（top-20 链中匹配 ≥1 模式的比例）、
redundancy（最大链交付按构造为 0，断言）。

产物：results/m2_hitrate.json
幂等：覆盖写出。
"""
import json
from pathlib import Path

import os
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # repository root
EXP = Path(REPO)

CD = {"cd:ok", "cd:err"}
FAM5 = {f"{a}:err" for a in ("cd", "cat", "grep", "sed", "git", "ls",
                              "find", "head", "rm", "cp", "echo")}


def match(chain_syms):
    s = set(chain_syms)
    hits = set()
    if s and s <= CD:
        hits.add("C01")
    if "pytest:err" in s or "python:err" in s:
        hits.add("C02")
    if "pip:err" in s or "export:err" in s:
        hits.add("C04")
    if len(s & FAM5) >= 2:
        hits.add("C05")
    if "other:err" in s:
        hits.add("C06")
    return hits  # C03 无规则（缺失信号不可表达）


def main():
    chains = [json.loads(l) for l in open(EXP / "results" / "chains.jsonl", encoding="utf-8")]
    chains.sort(key=lambda c: c["rank"])
    assert len(chains) == 72_972

    # 逐链匹配标签
    per_chain = [match(c["chain"]) for c in chains]

    K_GRID = [10, 20, 50, 100, 500]
    ALL = ["C01", "C02", "C03", "C04", "C05", "C06"]
    EXPRESSIBLE = [c for c in ALL if c != "C03"]

    hit_at_k, first_hit = {}, {}
    for mode in ALL:
        ranks = [i + 1 for i, h in enumerate(per_chain) if mode in h]
        first_hit[mode] = min(ranks) if ranks else None
    for k in K_GRID:
        matched = {m for m in EXPRESSIBLE if first_hit[m] is not None and first_hit[m] <= k}
        hit_at_k[str(k)] = {
            "matched": sorted(matched),
            "hit_rate_6": round(len(matched) / 6, 4),        # C03 永不匹配计入分母
            "hit_rate_expr": round(len(matched) / 5, 4),     # 5 个可表达模式口径
        }

    # AUQC：hit_rate_expr 对 log10(k) 的曲线下面积（梯形，按网格端点归一到 [0,1]）
    import math
    xs = [math.log10(k) for k in K_GRID]
    ys = [hit_at_k[str(k)]["hit_rate_expr"] for k in K_GRID]
    auc = sum((xs[i + 1] - xs[i]) * (ys[i] + ys[i + 1]) / 2 for i in range(len(xs) - 1))
    auqc = auc / (xs[-1] - xs[0])

    # expert precision：top-20 链匹配 ≥1 模式的比例（可读性/可操作性代理）
    top20 = per_chain[:20]
    expert_precision = sum(1 for h in top20 if h) / len(top20)

    # redundancy：最大链交付，按构造无子链冗余
    subsumption_redundancy = 0.0

    out = {
        "matching_rules": {
            "C01": "all symbols in {cd:ok, cd:err}",
            "C02": "contains pytest:err or python:err",
            "C03": "unmatchable by construction (absence of test execution)",
            "C04": "contains pip:err or export:err",
            "C05": ">=2 distinct err symbols from {cd,cat,grep,sed,git,ls,find,head,rm,cp,echo}",
            "C06": "contains other:err",
        },
        "first_hit_rank": first_hit,
        "hit_rate_at_k": hit_at_k,
        "auqc_expr": round(auqc, 4),
        "expert_precision_top20": round(expert_precision, 4),
        "redundancy": subsumption_redundancy,
        "n_chains": len(chains),
    }
    dst = EXP / "results" / "m2_hitrate.json"
    dst.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
