# -*- coding: utf-8 -*-
"""Download SWE-bench Verified trajectories from hf-mirror (resumable).
Source: dataset tarsur385/swebench-verified-trajectories (mirror of SWE-bench
Verified trajectory archive, mini-swe-agent .traj.json format, 500 instances x
10 models = 5000 files). Run repeatedly until 'remaining: 0'.
"""
import os
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # repository root
DATA = os.path.join(REPO, "data")
BASE = "https://hf-mirror.com/datasets/tarsur385/swebench-verified-trajectories/resolve/main/"
WORKERS = 8
BUDGET_S = 250  # stop launching new work after this many seconds


def dest(rel):
    return os.path.join(DATA, "swebench_raw", *rel.split("/"))


def fetch(rel):
    out = dest(rel)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    if os.path.exists(out) and os.path.getsize(out) > 0:
        return "skip"
    url = BASE + rel.replace("\\", "/")
    for attempt in range(4):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=60) as r, open(out, "wb") as f:
                f.write(r.read())
            return "ok"
        except Exception:
            time.sleep(2 * (attempt + 1))
    return "fail"


def main():
    files = [l.strip() for l in open(os.path.join(DATA, "filelist.txt"))
             if l.strip()]
    todo = [f for f in files
            if not (os.path.exists(dest(f)) and os.path.getsize(dest(f)) > 0)]
    print(f"total {len(files)}, remaining {len(todo)}")
    t0 = time.time()
    stats = {"ok": 0, "skip": 0, "fail": 0}
    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        for res in ex.map(fetch, todo):
            stats[res] += 1
            if time.time() - t0 > BUDGET_S:
                break
    left = sum(1 for f in files
               if not (os.path.exists(dest(f)) and os.path.getsize(dest(f)) > 0))
    print("stats:", stats, "| remaining after run:", left)


if __name__ == "__main__":
    main()
