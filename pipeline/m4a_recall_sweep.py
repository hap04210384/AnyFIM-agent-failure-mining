# -*- coding: utf-8 -*-
"""M4a recall ablation (reviewer M4): is the modest guardrail recall a
small-corpus artifact or a property of the method?

Sweep three knobs on the mining side, with the evaluation pool FIXED:
  1. mining-pool subsampling by task instance: 200 / 300 / 400 of 400
     (instance-disjoint: whole instances enter or leave together)
  2. maximum chain length: 3 vs 4
  3. absolute failing-support floor: 5 / 10 / 20

Everything else identical to the manuscript pipeline (Section 4.2 / 6.3):
  - same signature-coupled symbol alphabet (allowed set from the full-pool
    itemmap; the alphabet is part of the two-layer coupling, not the knob)
  - same maximality filter (VMSP-style, same-support supersequence)
  - same M4b two-group ranking (perfect signatures by failing support, then
    finite chains by add-one-smoothed contrast c' = sf/(ss + 1/n_S))
  - same rule admission (c' >= 5, supp_fail >= 1%, len >= 2) and the same
    held-out evaluation pool (991 trajectories, 269 failures)
  - metrics: recall@k for k in {5,10,20,50,100} (prefix-union interception)

Output: results/m4a_recall_sweep.json
Deterministic: instance subsample seeded (numpy RandomState(42)); for 400
all instances are used (no sampling).
"""
import json
import os
import time
from collections import Counter, defaultdict

import numpy as np

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # repository root
EXP = REPO
DATA = os.path.join(EXP, "data", "encoded")
RES = os.path.join(EXP, "results")

INSTANCE_COUNTS = [200, 300, 400]
MAXLENS = [3, 4]
FLOORS = [5, 10, 20]
K_SWEEP = [5, 10, 20, 50, 100]
MIN_CONTRAST = 5.0
MIN_SUPP_REL = 0.01
SEED = 42

EPS = 1e-9


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


def load_pool():
    fail_seqs = read_spmf(os.path.join(DATA, "sequences_mine.spmf"))
    succ_seqs = read_spmf(os.path.join(DATA, "sequences_mine_succ.spmf"))
    instances = []
    with open(os.path.join(DATA, "labels_mine.csv"), encoding="utf-8") as f:
        f.readline()
        for line in f:
            instances.append(line.split(",")[1])
    assert len(instances) == len(fail_seqs), (len(instances), len(fail_seqs))
    # labels_mine.csv aggregates failing trajectories only; succeeding pool
    # rows follow the same instance order aggregated separately (verified in
    # encode_swebench.py: both written per trajectory of the same instances).
    with open(os.path.join(DATA, "labels_mine_succ.csv"), encoding="utf-8") as f:
        f.readline()
        succ_inst = [line.split(",")[1] for line in f]
    sym_map = {}
    with open(os.path.join(DATA, "seqmap.tsv"), encoding="utf-8") as f:
        for line in f:
            sid, s = line.rstrip("\n").split("\t")
            sym_map[int(sid)] = s
    item_strings = set()
    with open(os.path.join(DATA, "itemmap.tsv"), encoding="utf-8") as f:
        for line in f:
            i, s, fr = line.rstrip("\n").split("\t")
            item_strings.add(s)
    allowed = set()
    for sid, s in sym_map.items():
        base = s.split(":")[0]
        for cand in ("cmd:" + base, "tool:" + base):
            if cand in item_strings:
                allowed.add(sid)
                break
    return fail_seqs, succ_seqs, instances, succ_inst, sym_map, allowed


def subsample(all_instances, n_inst, rng):
    uniq = sorted(set(all_instances))
    assert len(uniq) == 400, len(uniq)
    if n_inst >= len(uniq):
        return set(uniq)
    return set(rng.choice(np.array(uniq), size=n_inst, replace=False).tolist())


def mine(fail_seqs, succ_seqs, allowed, min_total, maxlen):
    """Parametrized copy of sequence_layer.py core (kept inline so the main
    artifact chain stays untouched). Returns list of chain dicts ranked."""
    restricted = [[s for s in seq if s in allowed] for seq in fail_seqs]
    restricted = [s for s in restricted if s]
    cnt = Counter(tuple(s) for s in restricted)
    uniq = [list(t) for t in cnt]
    w = [cnt[tuple(s)] for s in uniq]

    first_index = defaultdict(list)
    for idx, seq in enumerate(uniq):
        for s in set(seq):
            first_index[s].append(idx)
    sym_bits = {}
    for s, idxs in first_index.items():
        bits = 0
        for i in idxs:
            bits |= (1 << i)
        sym_bits[s] = bits
    fail_b = [bytes(seq) for seq in uniq]

    def count_support(cand):
        bits = None
        for s in cand:
            b = sym_bits.get(s)
            if b is None:
                return 0
            bits = b if bits is None else (bits & b)
            if bits == 0:
                return 0
        c = 0
        while bits:
            low = bits & (-bits)
            i = low.bit_length() - 1
            if contains_b(fail_b[i], cand):
                c += w[i]
            bits ^= low
        return c

    symbols = sorted(allowed)
    freq1 = {s: 0 for s in symbols}
    for seq, wt in zip(uniq, w):
        for s in set(seq):
            freq1[s] += wt
    levels = {1: [((s,), c) for s, c in freq1.items() if c >= min_total]}
    ext_symbols = [c[0][0] for c in levels[1]]
    L = 1
    while L < maxlen and levels.get(L):
        nxt = {}
        for cand, _ in levels[L]:
            for s in ext_symbols:
                ext = cand + (s,)
                c = count_support(ext)
                if c >= min_total:
                    nxt[ext] = c
        L += 1
        if nxt:
            levels[L] = list(nxt.items())

    all_cands = {}
    for l, lst in levels.items():
        for seq, c in lst:
            all_cands[seq] = c

    def subseq(a, b):
        it = iter(b)
        return all(any(x == y for y in it) for x in a)

    by_support = defaultdict(lambda: defaultdict(list))
    for seq, c in all_cands.items():
        by_support[c][seq[0]].append(seq)
    maximal = []
    for c, buckets in by_support.items():
        for head, seqs in buckets.items():
            accepted = []
            for seq in sorted(seqs, key=len, reverse=True):
                if not any(subseq(seq, m) for m in accepted):
                    accepted.append(seq)
            maximal.extend((seq, c) for seq in accepted)

    # succeeding support
    scnt = Counter(tuple(s) for s in succ_seqs)
    uniq_s = [list(t) for t in scnt]
    w_s = [scnt[tuple(s)] for s in uniq_s]
    succ_index = defaultdict(list)
    for idx, sseq in enumerate(uniq_s):
        for s in set(sseq):
            succ_index[s].append(idx)
    succ_bits = {}
    for s, idxs in succ_index.items():
        bits = 0
        for i in idxs:
            bits |= (1 << i)
        succ_bits[s] = bits
    succ_b = [bytes(seq) for seq in uniq_s]
    n_succ = max(1, len(succ_seqs))
    n_fail = max(1, len(restricted))

    out = []
    for seq, c in maximal:
        supp_fail = c / n_fail
        ordered = sorted((succ_bits.get(s, 0) for s in seq), key=int.bit_count)
        bits = None
        for b in ordered:
            bits = b if bits is None else (bits & b)
            if bits == 0:
                break
        succ_c = 0
        while bits:
            low = bits & (-bits)
            i = low.bit_length() - 1
            if contains_b(succ_b[i], seq):
                succ_c += w_s[i]
            bits ^= low
        supp_succ = succ_c / n_succ
        out.append({
            "seq": seq,
            "len": len(seq),
            "supp_fail": round(supp_fail, 4),
            "supp_succ": round(supp_succ, 4),
            "contrast_sm": round(supp_fail / (supp_succ + 1.0 / n_succ), 2),
            "perfect": supp_succ == 0.0,
        })
    out.sort(key=lambda d: (0 if d["perfect"] else 1,
                            -d["supp_fail"] if d["perfect"]
                            else -d["contrast_sm"],
                            -d["supp_fail"]))
    return out


def main():
    t_start = time.time()
    fail_seqs, succ_seqs, instances, succ_inst, sym_map, allowed = load_pool()
    # eval pool (fixed across all configs)
    eval_seqs = ([bytes(s) for s in read_spmf(os.path.join(DATA, "sequences_eval.spmf"))]
                 + [bytes(s) for s in read_spmf(os.path.join(DATA, "sequences_eval_succ.spmf"))])
    labels = []
    for name in ("labels_eval.csv", "labels_eval_succ.csv"):
        with open(os.path.join(DATA, name), encoding="utf-8") as f:
            f.readline()
            for line in f:
                labels.append(line.rstrip("\n").split(",")[2] != "True")
    assert len(labels) == len(eval_seqs)
    n_fail = sum(labels)

    results = []
    all_inst = instances + succ_inst          # union covers all 400 instances
    for n_inst in INSTANCE_COUNTS:
        rng = np.random.RandomState(SEED)
        keep = subsample(all_inst, n_inst, rng)
        fail_idx = [i for i, inst in enumerate(instances) if inst in keep]
        fail_sub = [fail_seqs[i] for i in fail_idx]
        succ_sub = [succ_seqs[i] for i, inst in enumerate(succ_inst)
                    if inst in keep]
        for maxlen in MAXLENS:
            for floor in FLOORS:
                t0 = time.time()
                chains = mine(fail_sub, succ_sub, allowed, floor, maxlen)
                rules = [c for c in chains
                         if c["contrast_sm"] >= MIN_CONTRAST
                         and c["supp_fail"] >= MIN_SUPP_REL and c["len"] >= 2]
                # per-rule hit masks (fail / succ counts)
                masks_fail, masks_succ = [], []
                for c in rules:
                    rid = bytes(c["seq"])
                    mf = np.array([contains_b(b, rid) for b in eval_seqs])
                    masks_fail.append(mf & np.array(labels))
                    masks_succ.append(mf & ~np.array(labels))
                uf = np.zeros(len(labels), bool)
                us = np.zeros(len(labels), bool)
                rows = {"recall_at": {}, "n_rules": len(rules),
                        "n_chains": len(chains),
                        "n_perfect_rules": sum(1 for c in rules if c["perfect"])}
                for k in range(1, len(rules) + 1):
                    uf |= masks_fail[k - 1]
                    us |= masks_succ[k - 1]
                    if k in K_SWEEP:
                        rows["recall_at"][str(k)] = round(
                            float(uf.sum()) / n_fail, 4)
                        rows[f"coverage_at_{k}"] = round(
                            float((uf | us).sum()) / len(labels), 4)
                rows["recall_at"]["all"] = (round(float(uf.sum()) / n_fail, 4)
                                            if rules else 0.0)
                dt = time.time() - t0
                rec = {"n_instances": n_inst, "maxlen": maxlen, "floor": floor,
                       "wall_s": round(dt, 1), **rows}
                results.append(rec)
                print(f"[{time.time()-t_start:.0f}s] inst={n_inst} maxlen={maxlen} "
                      f"floor={floor}: chains={rows['n_chains']} "
                      f"rules={len(rules)} recall@100="
                      f"{rows['recall_at'].get('100')} ({dt:.0f}s)", flush=True)

    out = {"seed": SEED, "k_sweep": K_SWEEP,
           "min_contrast": MIN_CONTRAST, "min_support_rel": MIN_SUPP_REL,
           "eval_pool": {"n": len(labels), "n_fail": int(n_fail)},
           "alphabet": "full-pool signature coupling (not varied)",
           "results": results}
    with open(os.path.join(RES, "m4a_recall_sweep.json"), "w") as f:
        json.dump(out, f, indent=2)
    print("saved", os.path.join(RES, "m4a_recall_sweep.json"))


if __name__ == "__main__":
    main()
