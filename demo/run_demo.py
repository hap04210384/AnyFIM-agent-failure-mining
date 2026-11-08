# -*- coding: utf-8 -*-
"""One-click demo of the two-layer failure-mining framework (Section 4.2).

Runs the sequence layer on the tiny bundled dataset demo/demo_data.json and
prints the delivered failure chains. Pure standard library, a few seconds.

Semantics mirrored from the full pipeline (pipeline/sequence_layer.py):
  1. coupling:      the chain alphabet is restricted to symbols that appear in
                    the delivered itemset signatures (one-way restriction)
  2. activation:    chains are ranked by failing-pool support (anytime order)
  3. maximality:    a chain is dropped if a supersequence has the same
                    failing-pool support (VMSP-style)
  4. contrast:      raw c = sf / (ss + eps); smoothed c' = sf / (ss + 1/n_S)
  5. two groups:    perfect signatures (ss = 0) first, ordered by sf; then
                    finite-contrast chains ordered by c'  (M4b ranking)

Usage:  python demo/run_demo.py
"""
import itertools
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "demo_data.json")
EPS = 1e-9
MAX_LEN = 4


def is_subsequence(chain, seq):
    it = iter(seq)
    return all(x in it for x in chain)


def main():
    with open(DATA, encoding="utf-8") as f:
        data = json.load(f)
    syms = {int(k): v for k, v in data["symbols"].items()}
    fail, succ = data["failing"], data["succeeding"]
    n_s = len(succ)

    # ---- layer coupling: alphabet restricted to delivered signature symbols
    alpha = sorted({x for sig in data["signatures"] for x in sig})
    print("delivered signatures:",
          ["+".join(syms[i] for i in sig) for sig in data["signatures"]])
    print("coupled alphabet    :", [syms[i] for i in alpha])
    print("pools: %d failing / %d succeeding trajectories" % (len(fail), n_s))
    print("-" * 72)

    # ---- enumerate candidate chains over the coupled alphabet
    cand = {}
    for L in range(1, MAX_LEN + 1):
        for chain in itertools.product(alpha, repeat=L):
            sf = sum(1 for s in fail if is_subsequence(chain, s))
            if sf == 0:
                continue
            ss = sum(1 for s in succ if is_subsequence(chain, s))
            cand[chain] = (sf, ss)

    # ---- maximality: drop chain if a supersequence has the same failing support
    maximal = {}
    for chain, (sf, ss) in cand.items():
        dominated = False
        for other, (sf2, _) in cand.items():
            if len(other) > len(chain) and sf2 == sf and is_subsequence(chain, other):
                dominated = True
                break
        if not dominated:
            maximal[chain] = (sf, ss)

    # ---- two-group M4b ranking
    def c_prime(sf, ss):
        return sf / (ss + 1.0 / n_s)

    perfect = sorted(((c, v) for c, v in maximal.items() if v[1] == 0),
                     key=lambda kv: -kv[1][0])
    finite = sorted(((c, v) for c, v in maximal.items() if v[1] > 0),
                    key=lambda kv: -c_prime(*kv[1]))

    print("GROUP 1 - perfect signatures (zero succeeding-pool support),")
    print("          ordered by failing support (top 10 of %d):" % len(perfect))
    for chain, (sf, ss) in perfect[:10]:
        print("  %-34s sf=%2d ss=%2d" %
              (" -> ".join(syms[i] for i in chain), sf, ss))
    print()
    print("GROUP 2 - finite-contrast chains, ordered by smoothed contrast c'")
    print("          (top 10 of %d):" % len(finite))
    for chain, (sf, ss) in finite[:10]:
        print("  %-34s sf=%2d ss=%2d  c=%8.1f  c'=%6.2f" %
              (" -> ".join(syms[i] for i in chain), sf, ss, sf / (ss + EPS),
               c_prime(sf, ss)))
    print("-" * 72)
    top1 = perfect[0][0] if perfect else None
    ok = top1 == (2, 5)
    print("demo complete: planted chain 'edit -> git_push' heads GROUP 1:",
          "YES" if ok else "NO (check generator)")
    print("The full-scale study regenerates this from public corpora via")
    print("pipeline/download_swebench.py + pipeline/encode_swebench.py.")


if __name__ == "__main__":
    sys.exit(main())
