# -*- coding: utf-8 -*-
"""Projection-granularity ablation (Section 6.4): collapse the command-family
sequence projection (58 symbols) to the function-level projection (tool call
outcome only: ok / err, two symbols), re-run the sequence layer, and compare
what the analyst would receive.

The mini-swe-agent trajectories issue only bash tool calls, so a
function-level projection degenerates to a two-symbol vocabulary; this
ablation quantifies how much diagnostic contrast is lost by not resolving
command families.

Outputs results/ablation_projection.json.
"""
import json
import os
from collections import Counter, defaultdict

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # repository root
EXP = REPO
DATA = os.path.join(EXP, "data", "encoded")
RES = os.path.join(EXP, "results")
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


def main():
    # symbol id -> outcome (1=ok, 2=err)
    id2out = {}
    with open(os.path.join(DATA, "seqmap.tsv"), encoding="utf-8") as f:
        for line in f:
            sid, name = line.rstrip("\n").split("\t")
            id2out[int(sid)] = 1 if name.endswith(":ok") else 2

    def collapse(seqs):
        out = []
        for s in seqs:
            c = [id2out[x] for x in s]
            out.append(bytes(c))
        return out

    fail_b = collapse(read_spmf(os.path.join(DATA, "sequences_mine.spmf")))
    succ_b = collapse(read_spmf(os.path.join(DATA, "sequences_mine_succ.spmf")))
    n_fail = len(fail_b)
    n_succ = len(succ_b)

    # multiplicity-weighted unique sequences (same contract as sequence_layer)
    fcnt = Counter(fail_b)
    scnt = Counter(succ_b)

    def contains_b(b, cand):
        it = 0
        for x in cand:
            p = b.find(x, it)
            if p < 0:
                return False
            it = p + 1
        return True

    min_total = 10
    symbols = (1, 2)
    # level-wise enumeration over a 2-symbol alphabet is tiny
    chains = {}                # cand tuple -> (supp_fail_count, supp_succ_count)
    cands = [(s,) for s in symbols]
    maxlen = 4
    L = 1
    while L <= maxlen and cands:
        nxt = []
        for cand in cands:
            sf = sum(w for b, w in fcnt.items() if contains_b(b, cand))
            if sf < min_total:
                continue
            ss = sum(w for b, w in scnt.items() if contains_b(b, cand))
            chains[cand] = (sf, ss)
            for s in symbols:
                nxt.append(cand + (s,))
        cands = nxt
        L += 1

    # VMSP-style maximality within equal failing support
    by_support = defaultdict(list)
    for cand, (sf, _) in chains.items():
        by_support[sf].append(cand)
    maximal = {}
    for sf, cands_s in by_support.items():
        acc = []
        for cand in sorted(cands_s, key=len, reverse=True):
            if not any(_subseq(cand, m) for m in acc):
                acc.append(cand)
        for cand in acc:
            maximal[cand] = chains[cand]

    out = []
    for cand, (sf, ss) in maximal.items():
        p_f = sf / n_fail
        p_s = ss / n_succ
        out.append({
            "chain": ["ok" if x == 1 else "err" for x in cand],
            "len": len(cand),
            "supp_fail": round(p_f, 4),
            "supp_succ": round(p_s, 4),
            "contrast": round(p_f / (p_s + EPS), 2),
            "contrast_sm": round(p_f / (p_s + 1.0 / n_succ), 2),
        })
    out.sort(key=lambda d: (-d["contrast_sm"], -d["supp_fail"]))

    result = {
        "vocab_symbols": 2,
        "n_fail": n_fail,
        "n_succ": n_succ,
        "min_total": min_total,
        "n_chains": len(out),
        "chains": out,
        "top_chains": out[:10],
        "contrast_sm_max": out[0]["contrast_sm"] if out else None,
    }
    with open(os.path.join(RES, "ablation_projection.json"), "w") as f:
        json.dump(result, f, indent=2)
    print(json.dumps(result, indent=2))


def _subseq(a, b):
    it = iter(b)
    return all(any(x == y for y in it) for x in a)


if __name__ == "__main__":
    main()
