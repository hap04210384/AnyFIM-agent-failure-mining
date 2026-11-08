# -*- coding: utf-8 -*-
"""C6 robustness: survival of the delivered chain stream under telemetry noise.

Perturbations on the mining-pool encoded sequences (997 failing trajectories):
  delete    : drop each symbol with prob p          p in {0.05,0.10,0.20,0.30,0.40}
  insert    : insert floor(p*len) random symbols    p in {0.05,0.10,0.20,0.30,0.40}
  substitute: replace each symbol with prob p       p in {0.05,0.10,0.20,0.30,0.40}
  truncate  : keep first round(q*len) symbols       q in {0.90,0.70,0.50,0.30}
3 seeds per (type, level). 30 configs total.

Metrics per config:
  survival@100 / @1000  : fraction of top-K chains still present (support > 0)
  head_stability        : original top-20 still in top-20 under perturbed support
  spurious_support      : mean support gain of top-1000 chains (noise-induced)
Output: results/robustness_c6.json
"""
import json
import os
import random
import statistics

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # repository root
EXP = REPO
DATA = os.path.join(EXP, "data", "encoded")
RES = os.path.join(EXP, "results")
SEEDS = (7, 42, 123)
LEVELS = {
    "delete": [0.05, 0.10, 0.20, 0.30, 0.40],
    "insert": [0.05, 0.10, 0.20, 0.30, 0.40],
    "substitute": [0.05, 0.10, 0.20, 0.30, 0.40],
    "truncate": [0.90, 0.70, 0.50, 0.30],
}
K_SETS = (100, 1000)
HEAD = 20


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


def is_subsequence(chain, seq):
    it = iter(seq)
    return all(x in it for x in chain)


def perturb(seqs, vocab, kind, level, rng):
    out = []
    if kind == "delete":
        for s in seqs:
            out.append([x for x in s if rng.random() >= level])
    elif kind == "insert":
        for s in seqs:
            n_ins = int(round(len(s) * level))
            s2 = list(s)
            for _ in range(n_ins):
                s2.insert(rng.randrange(len(s2) + 1), rng.choice(vocab))
            out.append(s2)
    elif kind == "substitute":
        for s in seqs:
            out.append([rng.choice(vocab) if rng.random() < level else x for x in s])
    elif kind == "truncate":
        for s in seqs:
            out.append(s[:max(1, int(round(len(s) * level)))])
    return out


def main():
    seqs = read_spmf(os.path.join(DATA, "sequences_mine.spmf"))
    vocab = sorted({x for s in seqs for x in s})
    print("pool:", len(seqs), "sequences, vocab", len(vocab))

    name2id = {}
    with open(os.path.join(DATA, "seqmap.tsv"), encoding="utf-8") as f:
        for line in f:
            sid, s = line.rstrip("\n").split("\t")
            name2id[s] = int(sid)
    chains = [json.loads(l) for l in
              open(os.path.join(RES, "chains.jsonl"), encoding="utf-8")]
    chains.sort(key=lambda c: c["rank"])
    top = [c for c in chains[:max(K_SETS)] if all(sym in name2id for sym in c["chain"])]
    top_ids = [tuple(name2id[s] for s in c["chain"]) for c in top]
    top_sets = [set(t) for t in top_ids]
    print("top chains usable:", len(top))

    # 原始支持（挖掘池）
    def supports(perturbed):
        """support count of each top chain in the (perturbed) corpus"""
        seq_sets = [set(s) for s in perturbed]
        supp = []
        for t, ts in zip(top_ids, top_sets):
            n = 0
            for s, ss in zip(perturbed, seq_sets):
                if len(t) <= len(s) and ts <= ss and is_subsequence(t, s):
                    n += 1
            supp.append(n)
        return supp

    base_supp = supports(seqs)

    def one_config(kind, level, seed):
        rng = random.Random("%d|%s|%.2f" % (seed, kind, level))
        pert = perturb(seqs, vocab, kind, level, rng)
        supp = supports(pert)
        rec = {"kind": kind, "level": level, "seed": seed}
        for k in K_SETS:
            rec["survival@%d" % k] = round(sum(1 for x in supp[:k] if x > 0) / k, 4)
        # 头部稳定性：按扰动后支持重排 top-1000，与原始支持排序的 top-20 对比
        order = sorted(range(len(top)), key=lambda i: -supp[i])[:HEAD]
        base_order = sorted(range(len(top)), key=lambda i: -base_supp[i])[:HEAD]
        rec["head_stability"] = round(len(set(base_order) & set(order)) / HEAD, 4)
        # 伪支持：top-1000 平均支持增益（噪声带来的假阳性）
        gains = [supp[i] - base_supp[i] for i in range(min(1000, len(top)))]
        rec["mean_support_gain_top1000"] = round(statistics.mean(gains), 3)
        rec["max_support_gain"] = max(gains)
        n_t = min(1000, len(top))
        mean_base = statistics.mean(base_supp[:n_t]) or 1.0
        rec["support_retention"] = round(
            statistics.mean(supp[:n_t]) / mean_base, 4)
        rec["mean_base_support_top1000"] = round(mean_base, 3)
        return rec

    results = []
    for kind, levels in LEVELS.items():
        for level in levels:
            for seed in SEEDS:
                results.append(one_config(kind, level, seed))
            done = results[-len(SEEDS):]
            print("%-10s level=%.2f  surv@100=%.2f@1000=%.2f  head=%.2f  gain=%.1f" % (
                kind, level,
                statistics.mean(r["survival@100"] for r in done),
                statistics.mean(r["survival@1000"] for r in done),
                statistics.mean(r["head_stability"] for r in done),
                statistics.mean(r["mean_support_gain_top1000"] for r in done)))

    out = {"pool_n": len(seqs), "vocab_n": len(vocab), "seeds": list(SEEDS),
           "levels": LEVELS, "k_sets": list(K_SETS), "head": HEAD,
           "configs": results}
    with open(os.path.join(RES, "robustness_c6.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print("DONE -> results/robustness_c6.json")


if __name__ == "__main__":
    main()
