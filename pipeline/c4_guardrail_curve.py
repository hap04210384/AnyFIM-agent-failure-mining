# -*- coding: utf-8 -*-
"""C4: full-interval interception operating curve (R3 response).

Extends guardrail_eval.py (k only reached 100, coverage <= 8%):
  - K sweep extended to ALL admitted chain rules (731): coverage, intercepted
    fail rate, lift, false interception rate, recall at each k.
  - Contrast-floor sweep (min_contrast in {2,...,60}): the full operating curve
    traced by relaxing the admission bar rather than the count cap.

Bitmask-based incremental union makes the full sweep cheap.
Output: results/guardrail_curve.json (no per-rule detail; aggregate curve only).
"""
import json
import os

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # repository root
EXP = REPO
DATA = os.path.join(EXP, "data", "encoded")
RES = os.path.join(EXP, "results")

MIN_SUPP = 0.01
K_SWEEP = [1, 2, 3, 5, 10, 20, 50, 100, 150, 200, 300, 400, 500, 600, 700]
FLOOR_SWEEP = [60.0, 30.0, 20.0, 15.0, 10.0, 7.0, 5.0, 4.0, 3.0, 2.5, 2.0]


def read_spmf(path):
    seqs = []
    with open(path) as f:
        for line in f:
            toks = line.split()
            seq, cur = [], []
            for t in toks:
                if t == "-1":
                    if cur:
                        seq.append(cur[0])
                        cur = []
                elif t == "-2":
                    break
                else:
                    cur.append(int(t))
            if cur:
                seq.append(cur[0])
            seqs.append(seq)
    return seqs


def contains_b(b, cand):
    it = 0
    for x in cand:
        p = b.find(x, it)
        if p < 0:
            return False
        it = p + 1
    return True


def main():
    name2id = {}
    with open(os.path.join(DATA, "seqmap.tsv"), encoding="utf-8") as f:
        for line in f:
            sid, s = line.rstrip("\n").split("\t")
            name2id[s] = int(sid)

    chains = [json.loads(l) for l in
              open(os.path.join(RES, "chains.jsonl"), encoding="utf-8")]
    admissible = [c for c in chains
                  if c["supp_fail"] >= MIN_SUPP and c["len"] >= 2
                  and all(sym in name2id for sym in c["chain"])]
    admissible.sort(key=lambda d: d["rank"])
    print("admissible chains (supp>=1%%, len>=2):", len(admissible))

    eval_seqs = [bytes(s) for s in read_spmf(os.path.join(DATA, "sequences_eval.spmf"))]
    eval_seqs += [bytes(s) for s in read_spmf(os.path.join(DATA, "sequences_eval_succ.spmf"))]
    labels = []
    for name in ("labels_eval.csv", "labels_eval_succ.csv"):
        with open(os.path.join(DATA, name), encoding="utf-8") as f:
            f.readline()
            for line in f:
                labels.append(line.rstrip("\n").split(",")[2] != "True")
    n_eval = len(labels)
    n_fail = sum(labels)
    print("eval pool:", n_eval, "fails:", n_fail)

    # 预计算每条 admissible 规则的 fail/succ 命中位掩码（按 rank 序）
    masks = []
    for c in admissible:
        rid = tuple(name2id[s] for s in c["chain"])
        fm = sm = 0
        for i, b in enumerate(eval_seqs):
            if contains_b(b, rid):
                if labels[i]:
                    fm |= 1 << i
                else:
                    sm |= 1 << i
        masks.append((c["contrast_sm"], fm, sm))

    def popcount(x):
        return bin(x).count("1")

    def metrics(ufm, usm):
        n_hit_fail = popcount(ufm)
        n_hit_succ = popcount(usm)
        n_hit = n_hit_fail + n_hit_succ
        unhit = n_eval - n_hit
        unhit_fail = n_fail - n_hit_fail
        return {
            "k": None, "coverage": round(n_hit / n_eval, 4),
            "intercepted_fail_rate": round(n_hit_fail / max(1, n_hit), 4),
            "unintercepted_fail_rate": round(unhit_fail / max(1, unhit), 4),
            "lift": round((n_hit_fail / max(1, n_hit))
                          / max(1e-12, unhit_fail / max(1, unhit)), 3),
            "false_interception_rate": round(n_hit_succ / max(1, n_hit), 4),
            "recall": round(n_hit_fail / max(1, n_fail), 4),
        }

    out = {"pool": {"n_eval": n_eval, "n_fail": n_fail,
                    "base_fail_rate": round(n_fail / n_eval, 4)},
           "min_supp": MIN_SUPP, "n_admissible": len(admissible),
           "k_curve": [], "floor_curve": []}

    # K 曲线（contrast_sm >= 5 准入，与原手稿口径一致）
    ufm = usm = 0
    curve = []
    kmax = len(masks)
    ks = [k for k in K_SWEEP if k <= kmax] + ([kmax] if kmax not in K_SWEEP else [])
    ki = 0
    for idx, (c_sm, fm, sm) in enumerate(masks, start=1):
        if c_sm < 5.0:
            break
        ufm |= fm
        usm |= sm
        if ki < len(ks) and idx == ks[ki]:
            m = metrics(ufm, usm)
            m["k"] = idx
            curve.append(m)
            ki += 1
    out["k_curve"] = curve
    print("--- k curve (admission c' >= 5) ---")
    for m in curve:
        print("k=%-4d cov=%.3f recall=%.3f lift=%.2f FIR=%.3f" %
              (m["k"], m["coverage"], m["recall"], m["lift"],
               m["false_interception_rate"]))

    # 地板曲线：放宽 contrast 准入，全区间覆盖
    for floor in FLOOR_SWEEP:
        ufm = usm = 0
        n_used = 0
        for c_sm, fm, sm in masks:
            if c_sm < floor:
                continue
            ufm |= fm
            usm |= sm
            n_used += 1
        m = metrics(ufm, usm)
        m["min_contrast"] = floor
        m["n_rules"] = n_used
        out["floor_curve"].append(m)
    print("--- floor curve ---")
    for m in out["floor_curve"]:
        print("floor=%-5.1f n=%-4d cov=%.3f recall=%.3f lift=%.2f FIR=%.3f" %
              (m["min_contrast"], m["n_rules"], m["coverage"], m["recall"],
               m["lift"], m["false_interception_rate"]))

    with open(os.path.join(RES, "guardrail_curve.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print("DONE -> results/guardrail_curve.json")


if __name__ == "__main__":
    main()
