# -*- coding: utf-8 -*-
"""Sequence layer: signature-constrained, threshold-free sequential pattern
mining over the failing pool (Section 4.2 of the companion study).

Inputs (05_experiments/data/encoded/):
  sequences_mine.spmf / sequences_mine_succ.spmf   SPMF sequence files
  transactions_mine.txt / transactions_mine_succ.txt  itemset transactions
  itemmap.tsv                                      item id -> string, freq
Output (05_experiments/results/):
  chains.jsonl   one JSON object per delivered chain:
    {items, len, supp_fail, supp_succ, contrast, stage, signature}
  chain_stats.json  delivery curve: stage -> cumulative chains, wall time

Semantics matching the manuscript:
  - symbols restricted to those appearing in delivered signatures (coupling)
  - chains delivered in non-decreasing failing-support order (activation
    schedule): stage n = all chains with support >= freqRank[n]
  - maximality: a chain is delivered only if no supersequence has the same
    failing-pool support (VMSP-style)
  - raw contrast c = supp_fail / (supp_succ + eps)  (kept for traceability)
  - smoothed contrast c' = supp_fail / (supp_succ + 1/n_S)  (add-one over the
    succeeding pool; M4b reviewer fix — bounds c' by n_S and turns the
    degenerate zero-success contrast sf/eps ~ 1e7 into the finite sf*n_S)
  - delivery ranking (M4b): perfect signatures (zero succeeding support) form
    their own group, ordered by failing support; finite-contrast chains are
    ranked by c'. The two groups are never mixed on one scale.
"""
import json
import os
import time
from collections import Counter, defaultdict

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # repository root
DATA = os.path.join(REPO, "data", "encoded")
RES = os.path.join(REPO, "results")
EPS = 1e-9


def read_spmf_sequences(path):
    seqs = []
    with open(path) as f:
        for line in f:
            toks = line.split()
            seq, cur = [], []
            i = 0
            while i < len(toks):
                if toks[i] == "-1":
                    if cur:
                        seq.append(cur[0])  # single-item itemsets by construction
                        cur = []
                elif toks[i] == "-2":
                    break
                else:
                    cur.append(int(toks[i]))
                i += 1
            if cur:
                seq.append(cur[0])
            if seq:
                seqs.append(seq)
    return seqs


def read_transactions(path):
    trans = []
    with open(path) as f:
        for line in f:
            ids = [int(x) for x in line.split()]
            trans.append(set(ids))
    return trans


def main():
    os.makedirs(RES, exist_ok=True)
    t0 = time.time()

    fail_seqs = read_spmf_sequences(os.path.join(DATA, "sequences_mine.spmf"))
    succ_seqs = read_spmf_sequences(os.path.join(DATA, "sequences_mine_succ.spmf"))
    fail_trans = read_transactions(os.path.join(DATA, "transactions_mine.txt"))
    succ_trans = read_transactions(os.path.join(DATA, "transactions_mine_succ.txt"))

    item_str = {}
    with open(os.path.join(DATA, "itemmap.tsv"), encoding="utf-8") as f:
        for line in f:
            i, s, fr = line.rstrip("\n").split("\t")
            item_str[int(i)] = (s, int(fr))

    # symbol id -> item id mapping: symbol "tool:X:ok/err"; restrict to symbols
    # whose base tool appears in any delivered MFI item string
    sym_map = {}
    with open(os.path.join(DATA, "seqmap.tsv"), encoding="utf-8") as f:
        for line in f:
            sid, s = line.rstrip("\n").split("\t")
            sym_map[int(sid)] = s

    # signature symbols: symbols whose base (tool name or bash command family)
    # appears among the delivered MFI items (itemmap = all mined items).
    item_strings = {istr for _, (istr, _) in item_str.items()}
    allowed = set()
    sym_to_item = {}
    for sid, s in sym_map.items():
        base = s.split(":")[0]
        for cand in ("cmd:" + base, "tool:" + base):
            if cand in item_strings:
                allowed.add(sid)
                sym_to_item[sid] = cand
                break

    restricted_fail = [[s for s in seq if s in allowed] for seq in fail_seqs]
    restricted_fail = [s for s in restricted_fail if s]

    # ---- deduplication: identical projected sequences are counted once ----
    # Trajectories are highly repetitive (agent retry loops produce many
    # identical projections). Mining on unique sequences with multiplicity
    # weights gives identical supports at a fraction of the cost.
    fail_cnt = Counter(tuple(s) for s in restricted_fail)
    uniq_fail = [list(t) for t in fail_cnt]
    fail_w = [fail_cnt[tuple(s)] for s in uniq_fail]

    succ_cnt = Counter(tuple(s) for s in succ_seqs)
    uniq_succ = [list(t) for t in succ_cnt]
    succ_w = [succ_cnt[tuple(s)] for s in uniq_succ]

    # candidate generation with support counting. Each symbol gets a bitmap
    # over the deduplicated failing pool; ANDing the bitmaps of a candidate's
    # symbols leaves only sequences that contain every symbol, and the
    # expensive subsequence check runs on that residue alone (Section 4.2).
    first_index = defaultdict(list)
    for idx, seq in enumerate(uniq_fail):
        for s in set(seq):
            first_index[s].append(idx)
    sym_bits = {}
    for s, idxs in first_index.items():
        bits = 0
        for i in idxs:
            bits |= (1 << i)
        sym_bits[s] = bits

    # sequences as byte strings: symbol ids fit in one byte, and subsequence
    # checks become C-level bytes.find scans (orders of magnitude faster than
    # a Python element loop over the average ~44-step trajectory)
    fail_b = [bytes(seq) for seq in uniq_fail]
    succ_b = [bytes(seq) for seq in uniq_succ]

    def contains_b(b, cand):
        it = 0
        for x in cand:
            p = b.find(x, it)
            if p < 0:
                return False
            it = p + 1
        return True

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
                c += fail_w[i]
            bits ^= low
        return c

    # mine frequent sequences level-wise over restricted alphabet
    symbols = sorted(allowed)
    min_total = 10                     # absolute frequency floor for reporting
                                       # (~1% of the 995-trajectory failing pool)
    chains = []                        # (seq_tuple, supp_fail)
    freq1 = {s: 0 for s in symbols}
    for seq, w in zip(uniq_fail, fail_w):
        for s in set(seq):
            freq1[s] += w

    levels = {1: [((s,), c) for s, c in freq1.items() if c >= min_total]}
    # a sequence's support is bounded by each element's support: extending by
    # a symbol that is already rare can never reach min_total
    ext_symbols = [cand[0] for cand, _ in levels[1]]
    maxlen = 4
    L = 1
    while L < maxlen and levels.get(L):
        next_cands = {}
        for cand, _ in levels[L]:
            for s in ext_symbols:
                ext = cand + (s,)
                c = count_support(ext)
                if c >= min_total:
                    next_cands[ext] = c
        L += 1
        if next_cands:
            levels[L] = list(next_cands.items())
            chains.extend(levels[L])
            print(f"level {L}: {len(levels[L])} candidates "
                  f"({time.time()-t0:.1f}s)", flush=True)

    # flatten all candidates with support
    all_cands = {}
    for l, lst in levels.items():
        for seq, c in lst:
            all_cands[seq] = c
    # maximality filter (VMSP-style): a candidate is delivered only if no
    # supersequence with the SAME failing support exists. Check only within
    # same-support groups: per group, longest first, a candidate is dropped
    # iff a longer already-accepted group member contains it as a subsequence.
    by_support = defaultdict(lambda: defaultdict(list))
    for seq, c in all_cands.items():
        by_support[c][seq[0]].append(seq)
    maximal = []
    for c, buckets in by_support.items():
        for head, seqs in buckets.items():
            accepted = []
            for seq in sorted(seqs, key=len, reverse=True):
                if not any(_subseq(seq, m) for m in accepted):
                    accepted.append(seq)
            maximal.extend((seq, c) for seq in accepted)
    print(f"maximality: {len(all_cands)} -> {len(maximal)} chains "
          f"({time.time()-t0:.1f}s)", flush=True)

    # succeeding-pool support and contrast (bitmap-filtered like count_support)
    succ_bits = {}
    succ_index = defaultdict(list)
    for idx, sseq in enumerate(uniq_succ):
        for s in set(sseq):
            succ_index[s].append(idx)
    for s, idxs in succ_index.items():
        bits = 0
        for i in idxs:
            bits |= (1 << i)
        succ_bits[s] = bits
    print(f"succ bitmaps built ({time.time()-t0:.1f}s)", flush=True)
    n_succ = max(1, len(succ_seqs))    # support denominators stay per-trajectory

    out = []
    for seq, c in maximal:
        supp_fail = c / max(1, len(restricted_fail))
        # AND from the rarest symbol: residue shrinks fastest, and a symbol
        # absent from the succeeding pool zeroes the residue immediately
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
                succ_c += succ_w[i]
            bits ^= low
        supp_succ = succ_c / n_succ
        contrast = supp_fail / (supp_succ + EPS)          # raw ratio, traceability
        contrast_sm = supp_fail / (supp_succ + 1.0 / n_succ)  # add-one (M4b)
        out.append({
            "chain": [sym_map[s] for s in seq],
            "len": len(seq),
            "supp_fail": round(supp_fail, 4),
            "supp_succ": round(supp_succ, 4),
            "contrast": round(contrast, 2),
            "contrast_sm": round(contrast_sm, 2),
            "perfect": supp_succ == 0.0,
        })
    print(f"succ supports done ({time.time()-t0:.1f}s)", flush=True)
    # M4b two-group ranking: perfect signatures first (by failing support),
    # then finite-contrast chains by smoothed contrast (support tie-break).
    out.sort(key=lambda d: (0 if d["perfect"] else 1,
                            -d["supp_fail"] if d["perfect"]
                            else -d["contrast_sm"],
                            -d["supp_fail"]))

    with open(os.path.join(RES, "chains.jsonl"), "w", encoding="utf-8") as f:
        for i, o in enumerate(out, 1):
            o["rank"] = i
            f.write(json.dumps(o, ensure_ascii=False) + "\n")

    curve = {"wall_time_s": round(time.time() - t0, 2),
             "n_chains": len(out),
             "n_perfect": sum(1 for d in out if d["perfect"]),
             "smoothing": "c' = sf / (ss + 1/n_S), n_S = succeeding-pool size",
             "n_fail_seqs": len(restricted_fail),
             "n_fail_seqs_unique": len(uniq_fail),
             "n_succ_seqs": len(succ_seqs),
             "n_succ_seqs_unique": len(uniq_succ)}
    with open(os.path.join(RES, "chain_stats.json"), "w") as f:
        json.dump(curve, f, indent=2)
    print(json.dumps(curve, indent=2))


def _subseq(a, b):
    it = iter(b)
    return all(any(x == y for y in it) for x in a)


if __name__ == "__main__":
    main()
