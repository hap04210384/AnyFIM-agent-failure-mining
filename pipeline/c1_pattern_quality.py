# -*- coding: utf-8 -*-
"""C1: mined-pattern quality against the human-annotated 100-trajectory reference set.

Metrics:
  1. stream precision@k: fraction of top-k chains matching >=1 expressible catalog mode
  2. per-mode trajectory coverage (recall): annotated failing trajectories of mode C0x
     hit by >=1 top-k chain matching C0x (subsequence semantics)
  3. detector precision/recall on the annotated set (any-chain flags; correct = flagging
     chain matches the trajectory's adjudicated mode)

Idempotent: overwrites results/pattern_quality_vs_annotation.json.
"""
import csv
import json
import os

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # repository root
EXP = REPO
ANN = os.path.join(EXP, "data", "annotation")
RES = os.path.join(EXP, "results")

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
    return hits  # C03 not expressible


def is_subsequence(chain, seq):
    it = iter(seq)
    return all(x in it for x in chain)


def main():
    # 标注集
    anno = {}
    with open(os.path.join(ANN, "adjudicated.csv"), encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            anno[row["tid"]] = row["final_code"]

    traj = {}
    with open(os.path.join(ANN, "sample100.csv"), encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            if row["tid"] in anno:
                traj[row["tid"]] = row["symbols"].split()

    # 只评失败轨迹（成功轨迹无模式标注）
    failing = {t: m for t, m in anno.items() if t in traj}
    print("annotated failing trajectories:", len(failing))

    # 链流
    chains = [json.loads(l) for l in open(os.path.join(RES, "chains.jsonl"), encoding="utf-8")]
    chains.sort(key=lambda c: c["rank"])
    n_chains = len(chains)
    chain_modes = [match(c["chain"]) for c in chains]

    K_GRID = [1, 5, 10, 20, 50, 100, 200, 500, 1000, 5000, 10000, 20000, n_chains]
    ALL = ["C01", "C02", "C03", "C04", "C05", "C06"]
    EXPRESSIBLE = [c for c in ALL if c != "C03"]

    out = {"n_chains": n_chains, "n_annotated_failing": len(failing),
           "mode_counts": {m: sum(1 for x in failing.values() if x == m) for m in ALL},
           "k_grid": K_GRID, "at_k": {}}

    for k in K_GRID:
        top = chains[:k]
        top_modes = chain_modes[:k]
        # 1) 流精度
        stream_prec = sum(1 for h in top_modes if h) / k
        # 2)+3) 轨迹覆盖与检测器指标
        per_mode_hits = {m: 0 for m in ALL}
        n_flagged = n_correct = 0
        for tid, mode in failing.items():
            seq = traj[tid]
            flagged = False
            correct = False
            for c, h in zip(top, top_modes):
                if not is_subsequence(c["chain"], seq):
                    continue
                flagged = True
                if mode in h:
                    correct = True
                    per_mode_hits[mode] += 1
            n_flagged += flagged
            n_correct += correct
        recall_overall = n_correct / len(failing)
        det_precision = n_correct / n_flagged if n_flagged else 0.0
        per_mode_recall = {}
        for m in ALL:
            cnt = out["mode_counts"][m]
            per_mode_recall[m] = round(per_mode_hits[m] / cnt, 4) if cnt else None
        out["at_k"][str(k)] = {
            "stream_precision": round(stream_prec, 4),
            "detector_recall_annotated": round(recall_overall, 4),
            "detector_precision_annotated": round(det_precision, 4),
            "n_flagged": n_flagged,
            "per_mode_recall": per_mode_recall,
        }
        print("k=%-6d stream_prec=%.3f recall=%.3f prec=%.3f" %
              (k, stream_prec, recall_overall, det_precision))

    with open(os.path.join(RES, "pattern_quality_vs_annotation.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print("DONE -> results/pattern_quality_vs_annotation.json")


if __name__ == "__main__":
    main()
