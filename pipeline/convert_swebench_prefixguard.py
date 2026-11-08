# -*- coding: utf-8 -*-
"""Convert SWE-bench Verified raw trajectories (mini-swe-agent .traj.json)
into the PrefixGuard canonical JSONL format (M1 baseline reproduction).

Output: 05_experiments/data/prefixguard/swebench_trajectories.jsonl
One JSON object per trajectory, schema per PrefixGuard README:
  {trajectory_id, task_id, final_success, failure_bucket, split, metadata,
   steps:[{context, action_text, tool_name, tool_args, result_text, status,
           source_raw_text}]}

Split protocol EXACTLY mirrors the paper's guardrail experiment
(encode_swebench.py): instances sorted lexicographically, first 80% (400)
-> mining pool, last 20% (100) -> evaluation pool. Within the mining pool,
the first 320 instances are "train" (fit) and the remaining 80 are "val"
(model selection + calibration); all splits are task-instance disjoint,
matching PrefixGuard's own OOD protocol (same task never in train and test).

Step failure semantics are identical to the paper's encoding
(error flag or non-zero bash exit code), so labels agree with
labels_mine.csv / labels_eval.csv.
"""
import json
import os
import re

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # repository root
DATA = os.path.join(REPO, "data")
RAW = os.path.join(DATA, "swebench_raw")
OUTDIR = os.path.join(DATA, "prefixguard")
OUT = os.path.join(OUTDIR, "swebench_trajectories.jsonl")

CTX_CHARS = 500
RESULT_CHARS = 1000
RAW_CHARS = 2000


def exit_code_of(content):
    m = re.match(r"\s*Exit code:\s*(-?\d+)", content or "")
    return int(m.group(1)) if m else None


def as_args(x):
    if isinstance(x, dict):
        return x
    if isinstance(x, str):
        try:
            return json.loads(x)
        except Exception:
            return {"raw": x[:300]}
    return {}


def convert(path, model, instance):
    with open(path, encoding="utf-8", errors="replace") as f:
        d = json.load(f)
    msgs = d.get("messages", [])
    calls = []                       # (fn, tool_call_id, args_dict, cmd) in order
    results = {}                     # tool_call_id -> (error_flag, content)
    for m in msgs:
        role = m.get("role")
        if role == "assistant":
            for tc in (m.get("tool_calls") or []):
                fn = tc.get("function") or "?"
                args = as_args(tc.get("arguments"))
                cmd = args.get("command", "") if fn == "bash" else ""
                calls.append((fn, tc.get("id"), args, cmd))
        elif role == "tool":
            content = m.get("content")
            if not isinstance(content, str):
                content = json.dumps(content, ensure_ascii=False)
            results[m.get("tool_call_id")] = (bool(m.get("error")), content or "")

    steps = []
    prev_content = ""
    for fn, cid, args, cmd in calls:
        err_flag, content = results.get(cid, (False, ""))
        ec = exit_code_of(content)
        failed = err_flag or (ec not in (None, 0))
        if fn == "bash" and cmd:
            action_text = cmd
        else:
            action_text = fn + " " + json.dumps(args, ensure_ascii=False)
        args_short = {k: (str(v)[:120]) for k, v in args.items()}
        raw = (f"[{fn}] {json.dumps(args_short, ensure_ascii=False)}\n"
               f"{content[:RAW_CHARS]}")
        steps.append({
            "context": prev_content[:CTX_CHARS],
            "action_text": action_text[:500],
            "tool_name": fn,
            "tool_args": args,
            "result_text": content[:RESULT_CHARS],
            "status": "error" if failed else "ok",
            "source_raw_text": raw,
        })
        prev_content = content
    info = d.get("info", {})
    resolved = bool(info.get("resolved"))
    return {
        "trajectory_id": f"{model}__{instance}",
        "task_id": instance,
        "final_success": resolved,
        "failure_bucket": "NONE" if resolved else "UNRESOLVED",
        "metadata": {"dataset": "swe-bench-verified", "agent": model},
        "steps": steps,
    }


def main():
    os.makedirs(OUTDIR, exist_ok=True)
    rows = []
    instances = set()
    for root, _, names in os.walk(RAW):
        for n in sorted(names):
            if not n.endswith(".traj.json"):
                continue
            p = os.path.join(root, n)
            rel = os.path.relpath(p, RAW)
            parts = rel.split(os.sep)
            model, inst = parts[1], parts[2]
            try:
                rec = convert(p, model, inst)
            except Exception as e:
                print("SKIP (parse)", rel, e)
                continue
            if not rec["steps"]:
                print("SKIP (no tool calls)", rel)
                continue
            rec["_instance"] = inst
            rows.append(rec)
            instances.add(inst)

    # same split rule as encode_swebench.py (sorted instances, 80/20),
    # then train/val = 320/80 inside the mining pool
    inst_sorted = sorted(instances)
    cut = int(0.8 * len(inst_sorted))
    mine = set(inst_sorted[:cut])
    mine_sorted = inst_sorted[:cut]
    train_set = set(mine_sorted[: int(0.8 * len(mine_sorted))])
    n_train = n_val = n_test = 0
    with open(OUT, "w", encoding="utf-8") as f:
        for rec in rows:
            inst = rec.pop("_instance")
            if inst not in mine:
                rec["split"] = "test"
                n_test += 1
            elif inst in train_set:
                rec["split"] = "train"
                n_train += 1
            else:
                rec["split"] = "val"
                n_val += 1
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    print(f"trajectories: {len(rows)}  instances: {len(inst_sorted)}")
    print(f"split: train={n_train} val={n_val} test={n_test}")
    for split in ("train", "val", "test"):
        sub = [r for r in rows if r.get("split") == split]
        nf = sum(1 for r in sub if not r["final_success"])
        print(f"  {split}: {len(sub)} trajectories, {nf} failed "
              f"({nf / max(1, len(sub)):.3f})")
    print("wrote", OUT)


if __name__ == "__main__":
    main()
