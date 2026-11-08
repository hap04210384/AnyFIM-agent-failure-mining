# -*- coding: utf-8 -*-
"""Annotate AnyFIM per-stage MFIs with succeeding-pool supports and emit the
ranked signature stream (Section 4.1 contrast profile c(X)).

Input:  AnyFIM results file (..-stages=Results.txt) written by the anytime
        engine into the TransactionSets directory.
Output: results/signatures.jsonl, one object per signature occurrence:
        {stage, mfi:[str], supp_fail, supp_succ, contrast, n_delivered}
        Ordered exactly as delivered (support-ordered stream = anytime order).
"""
import json
import os
import re
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # repository root
ENC = os.path.join(REPO, "data", "encoded")
RES = os.path.join(REPO, "results")
RESULTS_FILE = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
    os.path.dirname(REPO), "03_reproducibility", "code",  # external workspace path
    "Anytime-Frequent-Itemset-Mining", "code", "AnyFIM-Anytime", "AnytimeMining",
    "x64", "TransactionSets", "swebench_mine.txt-29-stages=Results.txt")
EPS = 1e-9

MFI_RE = re.compile(r"^\d+th:\s*\d+\s*\{\s*([\d\s]+)\}\s*support:\s*([\d.]+)\s+frequency:\s*(\d+)")


def read_transactions(path):
    trans = []
    with open(path) as f:
        for line in f:
            trans.append(set(int(x) for x in line.split()))
    return trans


def main():
    item_str = {}
    with open(os.path.join(ENC, "itemmap.tsv"), encoding="utf-8") as f:
        for line in f:
            i, s, fr = line.rstrip("\n").split("\t")
            item_str[int(i)] = s

    fail = read_transactions(os.path.join(ENC, "transactions_mine.txt"))
    succ = read_transactions(os.path.join(ENC, "transactions_mine_succ.txt"))

    stage = 0
    out = []
    delivered = set()
    with open(RESULTS_FILE, encoding="utf-8", errors="replace") as f:
        for line in f:
            m = re.match(r"=+\s*(\d+)th stage MFIs Number", line)
            if m:
                stage = int(m.group(1))
                continue
            m = MFI_RE.match(line.strip())
            if not m:
                continue
            ids = tuple(sorted(int(x) for x in m.group(1).split()))
            if ids in delivered:      # stream semantics: first delivery counts
                continue
            delivered.add(ids)
            sc = sum(1 for t in succ if set(ids) <= t)
            fc = int(m.group(3))
            supp_fail = fc / max(1, len(fail))
            supp_succ = sc / max(1, len(succ))
            contrast = supp_fail / (supp_succ + EPS)          # raw, traceability
            contrast_sm = supp_fail / (supp_succ + 1.0 / max(1, len(succ)))
            out.append({
                "stage": stage,
                "mfi": [item_str[i] for i in ids],
                "supp_fail": round(supp_fail, 4),
                "supp_succ": round(supp_succ, 4),
                "contrast": round(contrast, 3),
                "contrast_sm": round(contrast_sm, 3),
                "perfect": supp_succ == 0.0,
            })

    with open(os.path.join(RES, "signatures.jsonl"), "w", encoding="utf-8") as f:
        for o in out:
            f.write(json.dumps(o, ensure_ascii=False) + "\n")
    hi = [o for o in out if o["contrast_sm"] >= 2.0]
    n_perfect = sum(1 for o in out if o["perfect"])
    print(f"signatures: {len(out)} total, {len(hi)} with c_sm>=2, {n_perfect} perfect")
    print("top-10 by c_sm:")
    for o in sorted(out, key=lambda d: -d["contrast_sm"])[:10]:
        print("  c'=%6.2f fail=%.3f succ=%.3f" % (o["contrast_sm"], o["supp_fail"], o["supp_succ"]),
              "{" + ", ".join(o["mfi"]) + "}")


if __name__ == "__main__":
    main()
