# -*- coding: utf-8 -*-
"""Transactionize SWE-bench Verified agent trajectories (.traj.json, mini-swe-agent
format) into the two-layer layouts of Sections 3-4.

Outputs (under 05_experiments/data/encoded/):
  itemmap.tsv              integer item id <-> (dimension,value) string
  transactions_mine.txt    integer item ids per line, one line per FAILING
                           trajectory of the mining pool (AnyFIM/FP-Growth input)
  transactions_mine_succ.txt   same layout, succeeding trajectories (contrast)
  sequences_mine.spmf      SPMF sequence format over symbols, failing pool
  sequences_mine_succ.spmf succeeding pool
  labels_mine.csv / labels_eval.csv  per-trajectory metadata incl. split
  stats.json               corpus statistics for Table 2

Item facets (Section 3):
  tool:<function>          every tool invoked in the trajectory (set semantics)
  cmd:<family>             bash command family of first meaningful token
  err:<function>           tool call whose response errored or exited non-zero
Sequence vocabulary: <function>:ok / <function>:err per call, in call order.

Split: instances sorted lexicographically; first 80% -> mining pool,
last 20% -> evaluation pool (guardrail experiment, Section 6.3).
"""
import json
import os
import re
import sys
from collections import Counter

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # repository root
DATA = os.path.join(REPO, "data")
RAW = os.path.join(DATA, "swebench_raw")
OUT = os.path.join(DATA, "encoded")

CMD_FAMILY = [
    "pytest", "python", "pip", "git", "grep", "find", "ls", "cd", "cat",
    "sed", "awk", "echo", "mkdir", "rm", "cp", "mv", "tar", "curl", "wget",
    "make", "touch", "chmod", "sort", "uniq", "head", "tail", "wc", "vim",
    "nano", "exit", "source", "export", "set", "env", "which", "printenv",
]
FAMILY_SET = set(CMD_FAMILY)


def command_family(cmd):
    # strip leading env assignments / sudo / cd chains
    tokens = cmd.strip().split()
    i = 0
    while i < len(tokens) and ("=" in tokens[i] or tokens[i] in
                               ("sudo", "env", "time")):
        i += 1
    if i >= len(tokens):
        return "other"
    t = os.path.basename(tokens[i].rstrip(";|&"))
    if t in FAMILY_SET:
        return t
    if t.startswith("py") or t in ("python3",):
        return "python"
    return "other"


def exit_code_of(content):
    m = re.match(r"\s*Exit code:\s*(-?\d+)", content or "")
    return int(m.group(1)) if m else None


def extract(path):
    """Return (items:set, seq:list, meta:dict) for one trajectory file."""
    with open(path, encoding="utf-8", errors="replace") as f:
        d = json.load(f)
    msgs = d.get("messages", [])
    calls = []  # (fn, tool_call_id, cmd) in order; cmd set for bash calls
    results = {}  # tool_call_id -> (error_flag, content)
    for m in msgs:
        role = m.get("role")
        if role == "assistant":
            for tc in (m.get("tool_calls") or []):
                fn = (tc.get("function") or "?")
                args = tc.get("arguments") or {}
                cmd = args.get("command", "") if fn == "bash" else ""
                calls.append((fn, tc.get("id"), cmd))
        elif role == "tool":
            results[m.get("tool_call_id")] = (
                bool(m.get("error")), m.get("content") or "")
    items = set()
    seq = []
    for fn, cid, cmd in calls:
        err_flag, content = results.get(cid, (False, ""))
        ec = exit_code_of(content)
        failed = err_flag or (ec not in (None, 0))
        items.add("tool:" + fn)
        if fn == "bash":
            fam = command_family(cmd)
            items.add("cmd:" + fam)
            sym = fam + (":err" if failed else ":ok")
        else:
            sym = fn + (":err" if failed else ":ok")
        if failed:
            items.add("err:" + fn)
        seq.append(sym)
    info = d.get("info", {})
    meta = {
        "resolved": bool(info.get("resolved")),
        "exit_status": info.get("exit_status", ""),
        "n_calls": len(calls),
        "len_seq": len(seq),
        "instance_cost": info.get("model_stats", {}).get("instance_cost"),
    }
    return items, seq, meta


def main():
    os.makedirs(OUT, exist_ok=True)
    files = []
    for root, _, names in os.walk(RAW):
        for n in names:
            if n.endswith(".traj.json"):
                files.append(os.path.join(root, n))
    print("trajectory files on disk:", len(files))

    rows = []
    for p in sorted(files):
        rel = os.path.relpath(p, RAW)
        parts = rel.split(os.sep)
        # on-disk layout: swebench_verified_raw/<model>/<instance>/<file>.traj.json
        model, inst = parts[1], parts[2]
        try:
            items, seq, meta = extract(p)
        except Exception as e:
            print("SKIP (parse)", rel, e)
            continue
        rows.append({"model": model, "instance": inst, "items": items,
                     "seq": seq, **meta})

    # split by instance (80/20)
    instances = sorted({r["instance"] for r in rows})
    cut = int(0.8 * len(instances))
    mine_set = set(instances[:cut])
    for r in rows:
        r["split"] = "mine" if r["instance"] in mine_set else "eval"

    # alphabet by failing-pool item frequency (desc) -> integer ids from 1
    freq = Counter()
    for r in rows:
        if r["split"] == "mine" and not r["resolved"]:
            for it in r["items"]:
                freq[it] += 1
    ordered = [it for it, _ in sorted(freq.items(), key=lambda kv: (-kv[1], kv[0]))]
    item_id = {it: i + 1 for i, it in enumerate(ordered)}

    sym_ids = {}
    def sid(s):
        if s not in sym_ids:
            sym_ids[s] = len(sym_ids) + 1
        return sym_ids[s]

    def write_pool(split, resolved, tname, sname, lname):
        n = 0
        with open(os.path.join(OUT, tname), "w") as ft, \
             open(os.path.join(OUT, sname), "w") as fs, \
             open(os.path.join(OUT, lname), "w", encoding="utf-8") as fl:
            fl.write("model,instance,resolved,exit_status,n_calls,len_seq\n")
            for r in rows:
                if r["split"] != split or r["resolved"] != resolved:
                    continue
                ids = sorted(item_id[i] for i in r["items"] if i in item_id)
                ft.write(" ".join(map(str, ids)) + " \n")
                fs.write(" ".join(f"{sid(s)} -1" for s in r["seq"]) + " -2\n")
                fl.write(f"{r['model']},{r['instance']},{r['resolved']},"
                         f"{r['exit_status']},{r['n_calls']},{r['len_seq']}\n")
                n += 1
        return n

    n_fm = write_pool("mine", False, "transactions_mine.txt",
                      "sequences_mine.spmf", "labels_mine.csv")
    n_sm = write_pool("mine", True, "transactions_mine_succ.txt",
                      "sequences_mine_succ.spmf", "labels_mine_succ.csv")
    n_fe = write_pool("eval", False, "transactions_eval.txt",
                      "sequences_eval.spmf", "labels_eval.csv")
    n_se = write_pool("eval", True, "transactions_eval_succ.txt",
                      "sequences_eval_succ.spmf", "labels_eval_succ.csv")

    with open(os.path.join(OUT, "itemmap.tsv"), "w", encoding="utf-8") as f:
        for it in ordered:
            f.write(f"{item_id[it]}\t{it}\t{freq[it]}\n")
    with open(os.path.join(OUT, "seqmap.tsv"), "w", encoding="utf-8") as f:
        for s, i in sorted(sym_ids.items(), key=lambda kv: kv[1]):
            f.write(f"{i}\t{s}\n")

    stats = {
        "files_on_disk": len(files), "parsed": len(rows),
        "instances_total": len(instances), "instances_mine": cut,
        "instances_eval": len(instances) - cut,
        "alphabet_size": len(item_id),
        "vocab_size": len(sym_ids),
        "mine_failing": n_fm, "mine_success": n_sm,
        "eval_failing": n_fe, "eval_success": n_se,
    }
    with open(os.path.join(OUT, "stats.json"), "w") as f:
        json.dump(stats, f, indent=2)
    print(json.dumps(stats, indent=2))


if __name__ == "__main__":
    main()
