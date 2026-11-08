# -*- coding: utf-8 -*-
"""Guardrail downstream evaluation (Section 6.3): turn the mined chains into
prefix-interception rules and measure how well they flag failing trajectories
in the held-out evaluation pool (the 20% split never touched by mining).

Rule form: a trajectory is INTERCEPTED if its command-family projection
contains the chain as a subsequence (anywhere in the trajectory; the chain
encodes failure order, not absolute position).

Protocol:
  - rules come from chains.jsonl mined on the mining pool only
  - rule set = top-K chains by the M4b two-group ranking (perfect signatures
    first by failing support, then finite chains by add-one-smoothed contrast
    c' = sf/(ss + 1/n_S)), K swept; admission bar c' >= 5 (same as manuscript)
  - metrics: coverage, interception precision (fail|hit), fail-rate lift
    vs unintercepted trajectories, false-interception rate on succeeding
    trajectories, per-rule precision/recall
  - ablation: chain rules vs single-symbol signature rules (same statistic)

Outputs results/guardrail_eval.json.
"""
import json
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # repository root
EXP = REPO
DATA = os.path.join(EXP, "data", "encoded")
RES = os.path.join(EXP, "results")

MIN_CONTRAST = 5.0     # contrast floor for a chain to become a rule
MIN_SUPP = 0.01        # >=1% support in the failing mining pool
K_SWEEP = [1, 3, 5, 10, 20, 50, 100]


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
    # symbol name -> id (chains.jsonl stores names)
    name2id = {}
    with open(os.path.join(DATA, "seqmap.tsv"), encoding="utf-8") as f:
        for line in f:
            sid, s = line.rstrip("\n").split("\t")
            name2id[s] = int(sid)

    chains = [json.loads(l) for l in
              open(os.path.join(RES, "chains.jsonl"), encoding="utf-8")]
    rules = [c for c in chains
             if c["contrast_sm"] >= MIN_CONTRAST and c["supp_fail"] >= MIN_SUPP
             and c["len"] >= 2 and all(sym in name2id for sym in c["chain"])]
    # chains.jsonl already carries the M4b two-group ranking (perfect
    # signatures first by failing support, then finite chains by c'); keep it.
    rules.sort(key=lambda d: d["rank"])

    # single-symbol ablation: same smoothed statistic as the chain rules.
    # Single symbols top out at c' ~ 2.5 on this corpus (sequence coupling is
    # what produces c' >= 5), so the ablation uses c' >= 2 and ranks the same
    # way.
    single = [c for c in chains
              if c["contrast_sm"] >= 2.0 and c["supp_fail"] >= MIN_SUPP
              and c["len"] == 1 and c["chain"][0] in name2id]
    single.sort(key=lambda d: d["rank"])

    eval_seqs = [bytes(s) for s in
                 read_spmf(os.path.join(DATA, "sequences_eval.spmf"))]
    eval_seqs += [bytes(s) for s in
                  read_spmf(os.path.join(DATA, "sequences_eval_succ.spmf"))]
    labels = []
    for name in ("labels_eval.csv", "labels_eval_succ.csv"):
        with open(os.path.join(DATA, name), encoding="utf-8") as f:
            f.readline()
            for line in f:
                parts = line.rstrip("\n").split(",")
                labels.append(parts[2] != "True")   # resolved==True -> success
    assert len(labels) == len(eval_seqs), (len(labels), len(eval_seqs))

    n_eval = len(labels)
    n_fail = sum(labels)
    base_fail_rate = n_fail / n_eval
    print(f"eval pool: {n_eval} trajectories, {n_fail} failed "
          f"({base_fail_rate:.3f} base fail rate)")

    def rule_ids(c):
        return tuple(name2id[s] for s in c["chain"])

    def eval_rule_set(rule_list, k):
        """Intercept = hit by ANY of the first k rules."""
        sel = [rule_ids(c) for c in rule_list[:k]]
        n_hit = n_hit_fail = n_hit_succ = 0
        per_rule = []
        hit_by_rule = []          # per-rule hit masks for per-rule stats
        for rid, c in zip(sel, rule_list[:k]):
            hf = hs = 0
            for b, is_fail in zip(eval_seqs, labels):
                if contains_b(b, rid):
                    if is_fail:
                        hf += 1
                    else:
                        hs += 1
            hit_by_rule.append((hf, hs))
            per_rule.append({
                "rule": " -> ".join(c["chain"]),
                "perfect": c["perfect"],
                "contrast_sm": c["contrast_sm"],
                "contrast_raw": c["contrast"],
                "supp_fail": c["supp_fail"],
                "hits_fail": hf, "hits_succ": hs,
                "precision": round(hf / max(1, hf + hs), 4),
                "recall": round(hf / max(1, n_fail), 4),
            })
        # union interception
        for b, is_fail in zip(eval_seqs, labels):
            if any(contains_b(b, rid) for rid in sel):
                n_hit += 1
                if is_fail:
                    n_hit_fail += 1
                else:
                    n_hit_succ += 1
        unhit_fail = n_fail - n_hit_fail
        unhit = n_eval - n_hit
        return {
            "k": k,
            "n_rules": len(sel),
            "coverage": round(n_hit / n_eval, 4),
            "intercepted_fail_rate": round(n_hit_fail / max(1, n_hit), 4),
            "unintercepted_fail_rate": round(unhit_fail / max(1, unhit), 4),
            "lift": round((n_hit_fail / max(1, n_hit))
                          / max(1e-12, unhit_fail / max(1, unhit)), 2),
            "false_interception_rate": round(n_hit_succ / max(1, n_hit), 4),
            "recall": round(n_hit_fail / max(1, n_fail), 4),
            "per_rule": per_rule,
        }

    out = {
        "config": {"min_contrast": MIN_CONTRAST, "min_support": MIN_SUPP,
                   "k_sweep": K_SWEEP},
        "pool": {"n_eval": n_eval, "n_fail": n_fail,
                 "base_fail_rate": round(base_fail_rate, 4)},
        "n_chain_rules_available": len(rules),
        "n_single_rules_available": len(single),
        "chain_rules": [eval_rule_set(rules, k) for k in K_SWEEP
                        if k <= len(rules)],
        "single_symbol_rules": [eval_rule_set(single, k) for k in K_SWEEP
                                if k <= len(single)],
    }
    with open(os.path.join(RES, "guardrail_eval.json"), "w") as f:
        json.dump(out, f, indent=2)

    print(f"chain rules available: {len(rules)}, "
          f"single-symbol rules: {len(single)}")
    for blk, key in (("CHAIN", "chain_rules"), ("SINGLE", "single_symbol_rules")):
        print(f"--- {blk} rule set ---")
        for r in out[key]:
            print(f"k={r['k']:>3} cov={r['coverage']:.3f} "
                  f"fail|hit={r['intercepted_fail_rate']:.3f} "
                  f"fail|noHit={r['unintercepted_fail_rate']:.3f} "
                  f"lift={r['lift']:.2f} FIR={r['false_interception_rate']:.3f} "
                  f"recall={r['recall']:.3f}")


if __name__ == "__main__":
    sys.exit(main())
