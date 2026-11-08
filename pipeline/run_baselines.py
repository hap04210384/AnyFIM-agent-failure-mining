# -*- coding: utf-8 -*-
"""Threshold-grid baseline protocol (Section 5.2): run SPMF algorithms over a
geometric grid of 20 support thresholds on the encoded corpus, timing each run.

Usage: python run_baselines.py <itemset|sequence>
Outputs results/baselines_<kind>.json with per-threshold wall time + pattern
counts, plus grid-aggregated totals.
"""
import json
import os
import subprocess
import time

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # repository root
EXP = REPO
JAVA = os.path.join(EXP, "jdk-25.0.4.1+1-jre", "bin", "java.exe")
SPMF = os.path.join(EXP, "spmf.jar")
ENC = os.path.join(EXP, "data", "encoded")
RES = os.path.join(EXP, "results")
GRID = [round(0.5 * (0.85 ** i), 4) for i in range(20)]  # 0.5 -> ~0.026

ITEMSET_ALGO = "FPGrowth_itemsets"
SEQUENCE_ALGOS = ["PrefixSpan", "VMSP"]


def run_one(algo, infile, minsup):
    out = os.path.join(RES, f"base_{algo}_{minsup}.txt")
    t0 = time.time()
    try:
        r = subprocess.run(
            [JAVA, "-jar", SPMF, "run", algo, infile, out, str(minsup)],
            capture_output=True, text=True, timeout=120)
        wall = time.time() - t0
    except subprocess.TimeoutExpired:
        return {"minsup": minsup, "wall_s": None, "timeout": True,
                "n_patterns": None}
    wall = time.time() - t0
    n = None
    if os.path.exists(out):
        with open(out, encoding="utf-8", errors="replace") as f:
            n = sum(1 for line in f if line.strip() and "#" in line)
        os.remove(out)
    return {"minsup": minsup, "wall_s": round(wall, 3), "n_patterns": n,
            "timeout": False}


def main():
    kind = os.sys.argv[1] if len(os.sys.argv) > 1 else "itemset"
    budget_s = float(os.sys.argv[2]) if len(os.sys.argv) > 2 else 240.0
    os.makedirs(RES, exist_ok=True)
    prog_path = os.path.join(RES, f"baselines_{kind}_progress.jsonl")
    done = set()
    if os.path.exists(prog_path):
        with open(prog_path) as f:
            for line in f:
                try:
                    r = json.loads(line)
                    done.add((r.get("algo", ITEMSET_ALGO), r["minsup"]))
                except Exception:
                    pass

    jobs = []
    if kind == "itemset":
        infile = os.path.join(ENC, "transactions_mine.txt")
        jobs = [(ITEMSET_ALGO, infile, ms) for ms in GRID]
    else:
        infile = os.path.join(ENC, "sequences_mine.spmf")
        for algo in SEQUENCE_ALGOS:
            jobs += [(algo, infile, ms) for ms in GRID]

    t_start = time.time()
    pf = open(prog_path, "a")
    for algo, infile, ms in jobs:
        if (algo, ms) in done:
            continue
        if time.time() - t_start > budget_s:
            break
        row = run_one(algo, infile, ms)
        row["algo"] = algo
        pf.write(json.dumps(row) + "\n")
        pf.flush()
        print(row, flush=True)
    pf.close()

    # summarize whatever is done
    rows = [json.loads(l) for l in open(prog_path)]
    tot = sum(r["wall_s"] or 600 for r in rows)
    summary = {"kind": kind, "grid": GRID, "runs": rows,
               "n_done": len(rows), "n_total": len(jobs),
               "grid_total_wall_s": round(tot, 2)}
    with open(os.path.join(RES, f"baselines_{kind}.json"), "w") as f:
        json.dump(summary, f, indent=2)
    print(f"done {len(rows)}/{len(jobs)} | grid wall so far (s): {tot:.2f}")


if __name__ == "__main__":
    main()
