# -*- coding: utf-8 -*-
"""Support-floor sensitivity (Section 6.4, "Support floor and depth").

Reproduces the sequence-layer candidate growth when the absolute support
floor is halved from 10 to 5 trajectories, and the contrast profile of the
extra low-support chains. Output: results/sensitivity_floor.json.

Method mirrors sequence_layer.py (same dedup, same bitmap+subsequence
counting), only the reporting floor changes.
"""
import json
import time
from collections import Counter, defaultdict

import os
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # repository root
DATA = os.path.join(REPO, "data", "encoded")
RES = os.path.join(REPO, "results")


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
                        seq.append(cur[0])
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
            toks = line.split()
            if toks:
                trans.append(set(int(t) for t in toks))
    return trans


def load():
    fail_seqs = read_spmf_sequences(f"{DATA}/sequences_mine.spmf")
    succ_seqs = read_spmf_sequences(f"{DATA}/sequences_mine_succ.spmf")
    fail_trans = read_transactions(f"{DATA}/transactions_mine.txt")
    succ_trans = read_transactions(f"{DATA}/transactions_mine_succ.txt")
    item_strings = set()
    with open(f"{DATA}/itemmap.tsv", encoding="utf-8") as f:
        for line in f:
            parts = line.rstrip("\n").split("\t")
            if len(parts) >= 2:
                item_strings.add(parts[1])
    # mirror sequence_layer.py: a sequence symbol is allowed iff its base
    # (cmd:<base> or tool:<base>) appears in the mined item alphabet
    sym_map = {}
    with open(f"{DATA}/seqmap.tsv", encoding="utf-8") as f:
        for line in f:
            sid, s = line.rstrip("\n").split("\t")
            sym_map[int(sid)] = s
    sig_symbols = set()
    for sid, s in sym_map.items():
        base = s.split(":")[0]
        for cand in ("cmd:" + base, "tool:" + base):
            if cand in item_strings:
                sig_symbols.add(sid)
                break
    return fail_seqs, succ_seqs, fail_trans, succ_trans, item_strings, sig_symbols


def build_counter(fail_seqs, succ_seqs, allowed):
    restricted = [[s for s in seq if s in allowed] for seq in fail_seqs]
    restricted = [s for s in restricted if s]
    fail_cnt = Counter(tuple(s) for s in restricted)
    uniq_fail = [list(t) for t in fail_cnt]
    fail_w = [fail_cnt[tuple(s)] for s in uniq_fail]
    succ_cnt = Counter(tuple(s) for s in succ_seqs)
    uniq_succ = [list(t) for t in succ_cnt]
    succ_w = [succ_cnt[tuple(s)] for s in uniq_succ]

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

    def count_support(cand, uniq, weights, bits_map, byte_seqs):
        bits = None
        for s in cand:
            b = bits_map.get(s)
            if b is None:
                return 0
            bits = b if bits is None else (bits & b)
            if bits == 0:
                return 0
        c = 0
        while bits:
            low = bits & (-bits)
            i = low.bit_length() - 1
            if contains_b(byte_seqs[i], cand):
                c += weights[i]
            bits ^= low
        return c

    def supp_fail(cand):
        return count_support(cand, uniq_fail, fail_w, sym_bits, fail_b)

    def supp_succ(cand):
        return count_support(cand, uniq_succ, succ_w,
                             {s: 0 for s in sym_bits}, succ_b) if False else \
            count_support(cand, uniq_succ, succ_w,
                          build_succ_bits(cand, uniq_succ, succ_b), succ_b)

    def build_succ_bits(cand, uniq, byte_seqs):
        # succeeding pool is large; build per-symbol bitmaps once
        if not hasattr(build_succ_bits, "cache"):
            fi = defaultdict(list)
            for idx, seq in enumerate(uniq):
                for s in set(seq):
                    fi[s].append(idx)
            cache = {}
            for s, idxs in fi.items():
                bits = 0
                for i in idxs:
                    bits |= (1 << i)
                cache[s] = bits
            build_succ_bits.cache = cache
        return {s: build_succ_bits.cache.get(s, 0) for s in cand}

    freq1 = {s: 0 for s in sorted(allowed)}
    for seq, w in zip(uniq_fail, fail_w):
        for s in set(seq):
            freq1[s] += w
    return uniq_fail, fail_w, uniq_succ, succ_w, fail_b, succ_b, sym_bits, \
        build_succ_bits.cache if hasattr(build_succ_bits, "cache") else {}, freq1


def mine_levels(freq1, sym_bits, fail_b, fail_w, floor, maxlen=4):
    levels = {1: [((s,), c) for s, c in freq1.items() if c >= floor]}
    ext_symbols = [cand[0] for cand, _ in levels[1]]

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
            bseq = fail_b[i]
            it = 0
            ok = True
            for x in cand:
                p = bseq.find(x, it)
                if p < 0:
                    ok = False
                    break
                it = p + 1
            if ok:
                c += fail_w[i]
            bits ^= low
        return c

    L = 1
    while L < maxlen and levels.get(L):
        nxt = {}
        for cand, _ in levels[L]:
            for s in ext_symbols:
                ext = cand + (s,)
                c = count_support(ext)
                if c >= floor:
                    nxt[ext] = c
        L += 1
        if nxt:
            levels[L] = list(nxt.items())
    return levels


def main():
    t0 = time.time()
    fail_seqs, succ_seqs, fail_trans, succ_trans, itemmap, sig_symbols = load()
    n_fail, n_succ = len(fail_seqs), len(succ_seqs)
    fail_cnt = Counter(tuple([s for s in seq if s in sig_symbols])
                       for seq in fail_seqs)
    fail_cnt = Counter({k: v for k, v in fail_cnt.items() if k})
    uniq_fail = [list(t) for t in fail_cnt]
    fail_w = [fail_cnt[tuple(s)] for s in uniq_fail]
    succ_cnt = Counter(tuple([s for s in seq if s in sig_symbols])
                       for seq in succ_seqs)
    succ_cnt = Counter({k: v for k, v in succ_cnt.items() if k})
    uniq_succ = [list(t) for t in succ_cnt]
    succ_w = [succ_cnt[tuple(s)] for s in uniq_succ]
    fail_b = [bytes(s) for s in uniq_fail]
    succ_b = [bytes(s) for s in uniq_succ]

    fi = defaultdict(list)
    for idx, seq in enumerate(uniq_fail):
        for s in set(seq):
            fi[s].append(idx)
    sym_bits = {}
    for s, idxs in fi.items():
        bits = 0
        for i in idxs:
            bits |= (1 << i)
        sym_bits[s] = bits

    freq1 = {s: 0 for s in sorted(sig_symbols)}
    for seq, w in zip(uniq_fail, fail_w):
        for s in set(seq):
            freq1[s] += w

    def contains_b(b, cand):
        it = 0
        for x in cand:
            p = b.find(x, it)
            if p < 0:
                return False
            it = p + 1
        return True

    fi_s = defaultdict(list)
    for idx, seq in enumerate(uniq_succ):
        for s in set(seq):
            fi_s[s].append(idx)
    succ_bits = {}
    for s, idxs in fi_s.items():
        bits = 0
        for i in idxs:
            bits |= (1 << i)
        succ_bits[s] = bits

    def count_generic(cand, bits_map, byte_seqs, weights):
        bits = None
        for s in cand:
            b = bits_map.get(s)
            if b is None:
                return 0
            bits = b if bits is None else (bits & b)
            if bits == 0:
                return 0
        c = 0
        while bits:
            low = bits & (-bits)
            i = low.bit_length() - 1
            if contains_b(byte_seqs[i], cand):
                c += weights[i]
            bits ^= low
        return c

    out = {"n_fail": n_fail, "n_succ": n_succ, "floors": {}}
    for floor in (10, 5):
        levels = mine_levels(freq1, sym_bits, fail_b, fail_w, floor)
        delivered = {seq: c for lst in levels.values() for seq, c in lst}
        n_low = sum(1 for seq, c in delivered.items() if c < 10)
        # contrast profile of the extra low-support chains (5 <= supp < 10)
        low_chains = []
        for seq, c in delivered.items():
            if 5 <= c < 10:
                sf = count_generic(seq, sym_bits, fail_b, fail_w)
                ss = count_generic(seq, succ_bits, succ_b, succ_w)
                low_chains.append({"len": len(seq), "supp_fail": round(sf / n_fail, 4),
                                   "supp_succ": round(ss / n_succ, 4),
                                   "contrast": round(sf / (ss + 1e-9), 2),
                                   "contrast_sm": round((sf / n_fail) / (ss / n_succ + 1.0 / n_succ), 2)})
        out["floors"][str(floor)] = {
            "level_counts": {str(l): len(lst) for l, lst in levels.items()},
            "n_delivered": len(delivered),
            "n_low_support_5_9": n_low,
            "low_support_max_contrast_sm": max((c["contrast_sm"] for c in low_chains),
                                               default=None),
            "low_support_median_contrast_sm": sorted(
                [c["contrast_sm"] for c in low_chains])[
                len(low_chains) // 2] if low_chains else None,
            "low_support_p25_contrast_sm": sorted(
                [c["contrast_sm"] for c in low_chains])[
                len(low_chains) // 4] if low_chains else None,
            "low_support_p75_contrast_sm": sorted(
                [c["contrast_sm"] for c in low_chains])[
                (3 * len(low_chains)) // 4] if low_chains else None,
            "low_support_share_csm_ge5": round(sum(
                1 for c in low_chains if c["contrast_sm"] >= 5)
                / len(low_chains), 4) if low_chains else None,
        }
    out["wall_time_s"] = round(time.time() - t0, 2)
    with open(f"{RES}/sensitivity_floor.json", "w") as f:
        json.dump(out, f, indent=1)
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
