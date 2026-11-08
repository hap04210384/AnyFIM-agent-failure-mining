# -*- coding: utf-8 -*-
"""M3 WebArena two-layer mining + guardrail evaluation (generality study).

Itemset layer: AnyFIM anytime engine output
  (AnytimeMining/x64/TransactionSets/webarena_mine.txt-19-stages=Results.txt)
annotated with succeeding-pool supports -> signature stream with contrast c'.
Sequence layer: parametrized miner from m4a_recall_sweep.mine with the same
signature-coupled alphabet restriction; M4b two-group ranking; smoothed
contrast c' = sf/(ss + 1/n_S).
Guardrail: same admission (c' >= 5, supp >= 1%, len >= 2) and k-sweep on the
held-out WebArena eval pool (140 failing / 22 succeeding trajectories).

Outputs:
  results/webarena_signatures.jsonl   signature stream with c'
  results/webarena_chains.jsonl       delivered chains (M4b ranking)
  results/webarena_mining.json        summary stats + guardrail k-sweep
"""
import json
import os
import re
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from m4a_recall_sweep import mine, read_spmf, MIN_CONTRAST  # reuse validated core

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # repository root
EXP = REPO
ENC = os.path.join(EXP, "data", "encoded_webarena")
RES = os.path.join(EXP, "results")
RESULTS_FILE = os.path.join(
    os.path.dirname(REPO), "03_reproducibility", "code",  # external workspace path
    "Anytime-Frequent-Itemset-Mining", "code", "AnyFIM-Anytime", "AnytimeMining",
    "x64", "TransactionSets", "webarena_mine.txt-19-stages=Results.txt")

MIN_TOTAL = 5        # ~1% of the 569-trajectory failing mining pool
MAXLEN = 4
MIN_SUPP_REL = 0.01
K_SWEEP = [1, 3, 5, 10, 20, 50, 100]
MFI_RE = re.compile(r"^\d+th:\s*\d+\s*\{\s*([\d\s]+)\}\s*support:\s*([\d.]+)\s+frequency:\s*(\d+)")


def read_transactions(path):
    trans = []
    with open(path) as f:
        for line in f:
            trans.append(set(int(x) for x in line.split()))
    return trans


def load():
    fail_seqs = read_spmf(os.path.join(ENC, "sequences_mine.spmf"))
    succ_seqs = read_spmf(os.path.join(ENC, "sequences_mine_succ.spmf"))
    sym_map = {}
    with open(os.path.join(ENC, "seqmap.tsv"), encoding="utf-8") as f:
        for line in f:
            sid, s = line.rstrip("\n").split("\t")
            sym_map[int(sid)] = s
    item_strings = {}
    with open(os.path.join(ENC, "itemmap.tsv"), encoding="utf-8") as f:
        for line in f:
            i, s, fr = line.rstrip("\n").split("\t")
            item_strings[int(i)] = s
    allowed = set()
    strs = set(item_strings.values())
    for sid, s in sym_map.items():
        base = s.split(":")[0]
        for cand in ("cmd:" + base, "tool:" + base):
            if cand in strs:
                allowed.add(sid)
                break
    return fail_seqs, succ_seqs, sym_map, item_strings, allowed


def annotate_signatures(item_strings):
    fail_trans = read_transactions(os.path.join(ENC, "transactions_mine.txt"))
    succ_trans = read_transactions(os.path.join(ENC, "transactions_mine_succ.txt"))
    n_f, n_s = len(fail_trans), len(succ_trans)
    sigs = []
    with open(RESULTS_FILE, encoding="utf-8", errors="replace") as f:
        for line in f:
            m = MFI_RE.match(line.strip())
            if not m:
                continue
            ids = [int(x) for x in m.group(1).split()]
            items = sorted(item_strings[i] for i in ids if i in item_strings)
            sf = sum(1 for t in fail_trans
                     if all(i in t for i in ids)) / n_f
            ss = sum(1 for t in succ_trans
                     if all(i in t for i in ids)) / n_s
            sigs.append({
                "items": items,
                "supp_fail": round(sf, 4),
                "supp_succ": round(ss, 4),
                "contrast_sm": round(sf / (ss + 1.0 / n_s), 2),
            })
    sigs.sort(key=lambda d: -d["contrast_sm"])
    return sigs, n_f, n_s


def main():
    t0 = time.time()
    fail_seqs, succ_seqs, sym_map, item_strings, allowed = load()
    print(f"pools: fail={len(fail_seqs)} succ={len(succ_seqs)} "
          f"allowed_symbols={len(allowed)}")

    sigs, n_f, n_s = annotate_signatures(item_strings)
    with open(os.path.join(RES, "webarena_signatures.jsonl"), "w",
              encoding="utf-8") as f:
        for s in sigs:
            f.write(json.dumps(s, ensure_ascii=False) + "\n")
    n_sig_ge2 = sum(1 for s in sigs if s["contrast_sm"] >= 2)
    n_perfect = sum(1 for s in sigs if s["supp_succ"] == 0.0)
    print(f"signatures: {len(sigs)} (c'>=2: {n_sig_ge2}, perfect: {n_perfect})")

    chains = mine(fail_seqs, succ_seqs, allowed, MIN_TOTAL, MAXLEN)
    with open(os.path.join(RES, "webarena_chains.jsonl"), "w",
              encoding="utf-8") as f:
        for i, c in enumerate(chains, 1):
            rec = dict(c)
            rec["chain"] = [sym_map[s] for s in c["seq"]]
            rec.pop("seq")
            rec["rank"] = i
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    print(f"chains: {len(chains)}")

    # guardrail on the held-out eval pool
    eval_seqs = ([bytes(s) for s in read_spmf(os.path.join(ENC, "sequences_eval.spmf"))]
                 + [bytes(s) for s in read_spmf(os.path.join(ENC, "sequences_eval_succ.spmf"))])
    labels = []
    for name in ("labels_eval.csv", "labels_eval_succ.csv"):
        with open(os.path.join(ENC, name), encoding="utf-8") as f:
            f.readline()
            for line in f:
                labels.append(line.rstrip("\n").split(",")[2] != "True")
    import numpy as np

    def sweep_for(bar):
        rules = [c for c in chains
                 if c["contrast_sm"] >= bar and c["supp_fail"] >= MIN_SUPP_REL
                 and c["len"] >= 2]
        masks_fail, masks_succ = [], []
        for c in rules:
            rid = bytes(c["seq"])
            mf = np.array([_contains(b, rid) for b in eval_seqs])
            masks_fail.append(mf & np.array(labels))
            masks_succ.append(mf & ~np.array(labels))
        uf = np.zeros(len(labels), bool)
        us = np.zeros(len(labels), bool)
        sweep = []
        for k in range(1, len(rules) + 1):
            uf |= masks_fail[k - 1]
            us |= masks_succ[k - 1]
            if k in K_SWEEP:
                sweep.append({
                    "k": k, "n_rules": k,
                    "coverage": round(float((uf | us).sum()) / len(labels), 4),
                    "intercepted_fail_rate": round(float(uf.sum()) / max(1, (uf | us).sum()), 4),
                    "unintercepted_fail_rate": round(
                        float((np.array(labels) & ~uf).sum()) / max(1, len(labels) - (uf | us).sum()), 4),
                    "lift": round((float(uf.sum()) / max(1, (uf | us).sum()))
                                  / max(1e-12, float((np.array(labels) & ~uf).sum())
                                        / max(1, len(labels) - (uf | us).sum())), 2),
                    "false_interception_rate": round(float(us.sum()) / max(1, (uf | us).sum()), 4),
                    "recall": round(float(uf.sum()) / n_fail, 4),
                })
        return rules, sweep

    n_fail = sum(labels)
    rules5, sweep5 = sweep_for(5.0)
    rules2, sweep2 = sweep_for(2.0)
    top5 = [{
        "chain": " -> ".join(sym_map[s] for s in c["seq"]),
        "c'": c["contrast_sm"], "supp_fail": c["supp_fail"],
        "perfect": c["perfect"],
    } for c in rules2[:5]]

    out = {
        "corpus": "WebArena GPT-4 CoT official release 2 (809 tasks; "
                  "Agent-Eval-Refine extraction, HF)",
        "split": {"mine_fail": n_f, "mine_succ": n_s,
                  "eval_fail": int(n_fail),
                  "eval_succ": len(labels) - int(n_fail)},
        "params": {"min_total": MIN_TOTAL, "maxlen": MAXLEN,
                   "min_contrast": MIN_CONTRAST, "min_support_rel": MIN_SUPP_REL},
        "wall_s": round(time.time() - t0, 1),
        "signatures": {"n": len(sigs), "n_cprime_ge2": n_sig_ge2,
                       "n_perfect": n_perfect},
        "chains": {"n": len(chains),
                   "len_dist": {str(l): sum(1 for c in chains if c["len"] == l)
                                for l in sorted({c["len"] for c in chains})},
                   "n_rules_admitted_c5": len(rules5),
                   "n_rules_admitted_c2": len(rules2)},
        "guardrail_k_sweep_c5": sweep5,
        "guardrail_k_sweep_c2": sweep2,
        "top5_rules": top5,
    }
    with open(os.path.join(RES, "webarena_mining.json"), "w") as f:
        json.dump(out, f, indent=2)
    print(json.dumps({k: out[k] for k in ("split", "signatures", "chains")}, indent=2))
    for tag, sw in (("c'>=5", sweep5), ("c'>=2", sweep2)):
        print(f"--- {tag} ---")
        for r in sw:
            print(f"k={r['k']:>3} cov={r['coverage']:.3f} "
                  f"fail|hit={r['intercepted_fail_rate']:.3f} "
                  f"lift={r['lift']:.2f} FIR={r['false_interception_rate']:.3f} "
                  f"recall={r['recall']:.3f}")


def _contains(b, cand):
    it = 0
    for x in cand:
        p = b.find(x, it)
        if p < 0:
            return False
        it = p + 1
    return True


if __name__ == "__main__":
    main()
