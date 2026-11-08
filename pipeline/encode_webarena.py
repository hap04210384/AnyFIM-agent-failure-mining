# -*- coding: utf-8 -*-
"""Transactionize WebArena GPT-4 CoT trajectories (official release 2, extracted in
Agent-Eval-Refine/Agent-Trajectories, HF) into the two-layer layouts of Sections 3-4.

Source (downloaded via hf-mirror, resumable, see ../data/webarena_raw/dl_webarena.cmd):
  webarena_raw/AgentTrajectories/webarena/webarena-gpt4cot-release2/
    trajectory_log.json   809 trajectories, one per task (uid = task id)
    evals/v0.jsonl        per-task annotation: Success / Failure

Item facets (Section 3, web-navigation adaptation of the 3.1 facet design):
  tool:<action>   action family of each step (click, type, goto, scroll_up, ...)
  page:<site>     site of the task config (gitlab, shopping, shopping_admin,
                  reddit, map, wikipedia)
  err:<action>    steps whose raw action is 'none' (invalid/no-op action)
Sequence vocabulary: <action>:ok / <action>:err per step, in execution order.
  'none' actions are kept in the sequence as none:err (they are steps the agent
  actually took; they carry failure signal).

Split: task ids sorted lexicographically; first 80% -> mining pool, last 20% ->
evaluation pool (same protocol as encode_swebench.py).

Outputs (under 05_experiments/data/encoded_webarena/): itemmap.tsv, seqmap.tsv,
transactions/sequences for mine/eval x fail/succ, labels CSVs, stats.json.
"""
import json
import os
import re
from collections import Counter

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # repository root
DATA = os.path.join(REPO, "data")
SRC = os.path.join(DATA, "webarena_raw", "AgentTrajectories", "webarena",
                   "webarena-gpt4cot-release2")
OUT = os.path.join(DATA, "encoded_webarena")


def action_family(raw):
    """First token of the raw action string, normalized."""
    if not raw:
        return "none"
    fam = raw.split(" ")[0].strip().lower()
    return fam or "none"


def extract(traj, annotation):
    config = (traj.get("other") or {}).get("config", "")
    m = re.search(r"sites: \['([^']+)'", config)
    site = m.group(1) if m else "unknown"
    items = set()
    seq = []
    for s in traj.get("steps") or []:
        raw = ((s.get("other") or {}).get("raw_action")) or ""
        fam = action_family(raw)
        invalid = fam == "none"
        items.add("tool:" + fam)
        items.add("page:" + site)
        if invalid:
            items.add("err:none")
        seq.append(fam + (":err" if invalid else ":ok"))
    return {
        "task": str(traj["uid"]),
        "site": site,
        "resolved": annotation == "Success",
        "items": items,
        "seq": seq,
        "n_steps": len(seq),
        "intent": (traj.get("intent") or "")[:80],
    }


def main():
    os.makedirs(OUT, exist_ok=True)
    labels = {str(r["task_uid"]): r["annotation"]
              for r in (json.loads(l) for l in
                        open(os.path.join(SRC, "evals", "v0.jsonl"), encoding="utf-8"))}
    trajs = json.load(open(os.path.join(SRC, "trajectory_log.json"), encoding="utf-8"))
    rows = []
    for t in trajs:
        ann = labels.get(str(t["uid"]))
        if ann is None:
            print("SKIP (no label)", t["uid"])
            continue
        rows.append(extract(t, ann))
    print("parsed:", len(rows))

    tasks = sorted({r["task"] for r in rows})
    cut = int(0.8 * len(tasks))
    mine_set = set(tasks[:cut])
    for r in rows:
        r["split"] = "mine" if r["task"] in mine_set else "eval"

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
            fl.write("task,site,resolved,n_steps,intent\n")
            for r in rows:
                if r["split"] != split or r["resolved"] != resolved:
                    continue
                ids = sorted(item_id[i] for i in r["items"] if i in item_id)
                ft.write(" ".join(map(str, ids)) + " \n")
                fs.write(" ".join(f"{sid(s)} -1" for s in r["seq"]) + " -2\n")
                fl.write(f"{r['task']},{r['site']},{r['resolved']},"
                         f"{r['n_steps']},{r['intent']}\n")
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
        "source": "Agent-Eval-Refine/Agent-Trajectories trajectories.zip "
                  "(WebArena GPT-4 CoT official release 2), via hf-mirror",
        "parsed": len(rows),
        "tasks_total": len(tasks), "tasks_mine": cut,
        "tasks_eval": len(tasks) - cut,
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
