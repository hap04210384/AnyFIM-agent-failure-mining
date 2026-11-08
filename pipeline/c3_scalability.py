# -*- coding: utf-8 -*-
"""C3 scalability: rerun the AnyFIM engine on stratified subsamples of the
SWE-bench failing pool (997 trajectories) and record engine wall time.

Usage: python c3_scalability.py <pct>     (pct in {20,40,60,80,100}; 100 = full file)

Driver per size:
  1. seeded subsample of transactions_mine.txt -> TransactionSets\\swebench_sub<pct>.txt
  2. patch kernel.cu dataset line (from pristine .c3bak), MSBuild rebuild, run exe
  3. parse cumulative stage runtimes from the engine's Results file
  4. restore kernel.cu, append results/scalability_c3.jsonl
Idempotent per size (subsample deterministic, engine output overwritten).
"""
import json
import os
import random
import re
import shutil
import subprocess
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # repository root
BASE = os.path.dirname(REPO)  # workspace root (external: engine build / logs)
ENC = os.path.join(BASE, "05_experiments", "data", "encoded")
TS_DIR = os.path.join(BASE, "03_reproducibility", "code",
                       "Anytime-Frequent-Itemset-Mining", "code",
                       "AnyFIM-Anytime", "AnytimeMining", "x64", "TransactionSets")
MINING_DIR = os.path.join(BASE, "03_reproducibility", "code",
                          "Anytime-Frequent-Itemset-Mining", "code",
                          "AnyFIM-Anytime", "AnytimeMining")
KERNEL = os.path.join(MINING_DIR, "kernel.cu")
KERNEL_BAK = KERNEL + ".c3bak"
VCPROJ = os.path.join(MINING_DIR, "AnytimeMining.vcxproj")
MSBUILD = r"C:\Program Files\Microsoft Visual Studio\2022\Community\MSBuild\Current\Bin\MSBuild.exe"
RES = os.path.join(BASE, "05_experiments", "results")
LOGS = os.path.join(BASE, "05_experiments", "logs")
SEED = 42


def make_subsample(pct):
    src = os.path.join(ENC, "transactions_mine.txt")
    lines = open(src, encoding="utf-8").read().splitlines()
    n = len(lines)
    k = round(n * pct / 100)
    rng = random.Random(SEED)
    idx = sorted(rng.sample(range(n), k))
    sub = [lines[i] for i in idx]
    items = set()
    for ln in sub:
        items.update(int(x) for x in ln.split())
    dst = os.path.join(TS_DIR, "swebench_sub%d.txt" % pct)
    with open(dst, "w", encoding="utf-8") as f:
        f.write("\n".join(sub) + "\n")
    return k, len(items), dst


def patch_kernel(pct, stages):
    shutil.copy2(KERNEL_BAK, KERNEL)
    src = open(KERNEL, encoding="utf-8").read()
    m = re.search(r'^(CString transSetFile = _T\("\.\.\\\\TransactionSets\\\\webarena_mine\.txt"\); int UptoStage = 19;.*)$',
                  src, re.M)
    assert m, "active webarena line not found in kernel.cu"
    new_line = ('CString transSetFile = _T("..\\\\TransactionSets\\\\swebench_sub%d.txt"); '
                'int UptoStage = %d;//C3 scalability run\n' % (pct, stages))
    src = src[:m.start(1)] + "//" + m.group(1) + "\n" + new_line + src[m.end(1):]
    open(KERNEL, "w", encoding="utf-8").write(src)


def run_engine(pct):
    env = dict(os.environ)
    cuda = r"C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v12.5"
    env["CUDA_PATH"] = cuda
    env["CUDA_PATH_V12_5"] = cuda
    env["PATH"] = cuda + r"\bin;" + env.get("PATH", "")
    build = subprocess.run(
        [MSBUILD, VCPROJ, "/p:Configuration=Release", "/p:Platform=x64", "/v:minimal", "/nologo",
         "/p:CudaToolkitDir=" + cuda + "\\"],
        cwd=MINING_DIR, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=280, env=env)
    build_out = build.stdout.decode("gbk", errors="replace") if build.stdout else ""
    if build.returncode != 0:
        print(build_out[-2000:])
        raise RuntimeError("MSBuild failed rc=%d" % build.returncode)
    exe_dir = os.path.join(MINING_DIR, "x64", "Release")
    run = subprocess.run([os.path.join(exe_dir, "AnytimeMining.exe")],
                         cwd=exe_dir, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=120)
    run_out = run.stdout.decode("gbk", errors="replace") if run.stdout else ""
    log = os.path.join(LOGS, "c3_sub%d_engine.log" % pct)
    open(log, "w", encoding="utf-8").write(run_out)
    return run.returncode


def parse_results(pct, stages):
    path = os.path.join(TS_DIR, "swebench_sub%d.txt-%d-stages=Results.txt" % (pct, stages))
    if not os.path.exists(path):
        cands = [f for f in os.listdir(TS_DIR) if f.startswith("swebench_sub%d.txt-" % pct)]
        raise RuntimeError("results file missing; candidates=%s" % cands)
    text = open(path, encoding="utf-8", errors="replace").read().replace("\r", "")
    m = re.search(r"runtimePerStage\(s\):\s*([\d.eE+,\s-]+)", text)
    times = [float(x) for x in m.group(1).split(",") if x.strip()] if m else []
    m2 = re.search(r"MFIsNumPerStage:\s*([\d,\s]+)", text)
    mfis = [int(x) for x in m2.group(1).split(",") if x.strip()] if m2 else []
    return {
        "pct": pct, "n_traj": None, "n_items": None,
        "stages_completed": len(times),
        "engine_wall_s": round(times[-1], 4) if times else None,
        "per_stage_s": [round(t, 5) for t in times],
        "total_mfis": sum(mfis) if mfis else None,
        "seed": SEED,
    }


def main():
    pct = int(sys.argv[1])
    assert pct in (20, 40, 60, 80, 100), pct
    if not os.path.exists(KERNEL_BAK):
        shutil.copy2(KERNEL, KERNEL_BAK)
        print("kernel.cu pristine backup created")

    if pct == 100:
        # 全量：直接用原始文件，生成副本名以保持流程一致
        src = os.path.join(ENC, "transactions_mine.txt")
        dst = os.path.join(TS_DIR, "swebench_sub100.txt")
        shutil.copy2(src, dst)
        n, n_items = 997, 29
        stages = 29
    else:
        n, n_items, _ = make_subsample(pct)
        stages = n_items  # 激活轮数按实际物品数（全量29）
        print("subsample: %d trajectories, %d items -> %d stages" % (n, n_items, stages))

    patch_kernel(pct, stages)
    try:
        rc = run_engine(pct)
        print("engine rc=%d" % rc)
        rec = parse_results(pct, stages)
        rec["n_traj"] = n
        rec["n_items"] = n_items
        out = os.path.join(RES, "scalability_c3.jsonl")
        rows = []
        if os.path.exists(out):
            rows = [json.loads(l) for l in open(out, encoding="utf-8")]
        rows = [r for r in rows if r["pct"] != pct]
        rows.append(rec)
        rows.sort(key=lambda r: r["pct"])
        with open(out, "w", encoding="utf-8") as f:
            for r in rows:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
        print(json.dumps(rec, ensure_ascii=False))
    finally:
        shutil.copy2(KERNEL_BAK, KERNEL)
        print("kernel.cu restored")


if __name__ == "__main__":
    main()
