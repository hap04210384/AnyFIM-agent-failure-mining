# anytime-failure-mining

Replication package for a study on anytime, threshold-free mining of
recurring failure patterns in the behavior trajectories of LLM-based
software-engineering agents.
The companion paper links to this repository; the repository itself is kept
venue-neutral on purpose — it carries no paper title and no journal name, so
it can be referenced from any submission without rework. This repository
contains the complete pipeline and every result file reported in the study.
Following the repository policy, no datasets are bundled: all encoded splits
are regenerated from the public raw corpora by the included download/encode
scripts, and a tiny synthetic dataset ships with a one-click demo.

### Why no datasets are bundled

1. **The raw corpora are already public and permanently hosted.** Both
   trajectory collections (5,000 SWE-bench Verified and 809 WebArena
   trajectories) live on Hugging Face under stable identifiers; re-uploading
   multi-GB copies would duplicate an existing public good, not preserve one.
2. **Nothing is lost: the derivations are deterministic.** The packaged
   download and encode scripts regenerate every encoded split bit-for-bit from
   the raw corpora, so any reviewer can reconstruct the exact experiment
   inputs, and any drift in the public mirrors is detectable through the
   packaged corpus statistics in `results/`.
3. **A replication package should carry code and evidence, not bulk.** Keeping
   the repository small makes it clonable in seconds, reviewable on the GitHub
   web interface, and immune to large-file bit-rot; it also avoids
   re-distributing third-party trajectory data under terms we do not control.
4. **The mechanism is still instantly exercisable.** `demo/` ships a tiny
   synthetic corpus (50 trajectories, two planted failure chains) that runs
   the full two-layer semantics end-to-end in seconds with no downloads at
   all — see Quick start below.

## Contents

```
pipeline/    experiment scripts (encoding, mining, guardrails, ablations, figures)
demo/        one-click demo: tiny synthetic trajectory corpus + standalone runner
data/        raw-data downloaders and encoding scripts (encoded splits are
             regenerated, not bundled, per repository policy)
results/     every numeric result reported in the paper, as machine-readable JSON/JSONL
engine/      itemset-engine source snapshot (CUDA/VS solution) that produced the itemset streams
annotation/  failure-trajectory annotation kit (guide, booklet, blank sheets, adjudicated codes; study complete, Cohen's kappa = 1.0)
docs/        RESULTS_MANIFEST.md (MD5 anchors for every packaged result file)
```

## Requirements

- Python 3.10+ (standard scientific stack: numpy, pandas)
- Windows + Visual Studio 2022 + CUDA 12.x **only for rebuilding the itemset
  engine** (`engine/anytime-itemset-engine`); all Python-layer experiments run on any
  OS and do not require a GPU.
- The classical-miner baselines use the SPMF open-source library v2 (not
  bundled; download from spmf.ca and point `pipeline/run_baselines.py` at it).
- The learned-monitor baseline uses the public PrefixGuard code (MIT; see
  `pipeline/convert_swebench_prefixguard.py` for the adaptation).

## Quick start

One-click demo (pure standard library, a few seconds) — reproduces the
two-layer coupling semantics of Section 4.2 on a tiny synthetic corpus:

```bash
python demo/run_demo.py
```

Verify the packaged numbers in minutes:

```bash
python - <<'PY'
import hashlib, json, pathlib
man = json.load(open("docs/manifest.json"))
bad = []
for rel, md5 in man.items():
    p = pathlib.Path(rel)
    if not p.exists() or hashlib.md5(p.read_bytes()).hexdigest() != md5:
        bad.append(rel)
print("OK: all packaged files intact" if not bad else f"MISMATCH: {bad}")
PY
```

Full-scale reruns first rebuild the encoded splits from the public raw
corpora (`pipeline/download_swebench.py`, `data/dl_webarena.cmd`, then
`pipeline/encode_swebench.py` / `pipeline/encode_webarena.py`), after which
every experiment script regenerates its packaged output, e.g.
`python pipeline/guardrail_eval.py` recomputes Table 6.

## Reproduction map (claim in paper -> script -> packaged output)

| Paper location | Claim | Script | Packaged output |
|---|---|---|---|
| Table 3 | corpus statistics | `pipeline/encode_swebench.py` (encoding) | `data/encoded/labels_*.csv` |
| 6.1 | 72,972 chains, contrast distribution | `pipeline/sequence_layer.py`, `pipeline/annotate_signatures.py` | `results/chains.jsonl`, `results/signatures.jsonl` |
| Figure 2 | contrast profile | `pipeline/make_fig_contrast.py` | EMF figure |
| Table 4 | six-mode failure-mode catalog | `pipeline/m2_sample_annotation.py`, `pipeline/compute_kappa.py` | `annotation/`, `results/m2_kappa.json` |
| Figure 3 | human-catalog agreement (hit-rate, mode distribution) | `pipeline/make_fig3_hitrate.py` | `results/m2_hitrate.json` |
| Figure 4 | anytime quality-budget curve | `pipeline/make_fig3.py` (+ engine stream, `results/baselines_*.json`) | EMF figure |
| Figure 5 | 29-stage stream anatomy | `pipeline/make_fig5_stages.py` (engine per-stage Results file in `engine/`) | EMF figure |
| Table 5 | baseline grid, representative rows | `pipeline/run_baselines.py` | `results/baselines_*.json` |
| Figure 6 | guardrail operating curves | `pipeline/make_fig6_guardrail.py` | `results/guardrail_eval.json`, `results/prefixguard_eval.json` |
| Table 6 | guardrail sweep | `pipeline/guardrail_eval.py` | `results/guardrail_eval.json` |
| Table 7 | PrefixGuard side-by-side | `pipeline/eval_prefixguard_swebench.py` (external PrefixGuard repo) | `results/prefixguard_eval.json` |
| 6.3 | learned-monitor baseline | `pipeline/convert_swebench_prefixguard.py`, `pipeline/eval_prefixguard_swebench.py` (external PrefixGuard repo) | `results/prefixguard_eval.json` |
| Figure 7 | mining-pool sensitivity heatmap | `pipeline/make_fig7_heatmap.py` | `results/m4a_recall_sweep.json` |
| Table 8 | WebArena cross-corpus contrast | `pipeline/m3_webarena_mining.py` | `results/webarena_mining.json` |
| 6.4 | projection/support-floor/mining-pool ablations | `pipeline/ablation_projection.py`, `pipeline/sensitivity_floor.py`, `pipeline/m4a_recall_sweep.py` | `results/ablation_projection.json`, `results/sensitivity_floor.json`, `results/m4a_recall_sweep.json` |
| 6.5 | WebArena cross-corpus study | `pipeline/encode_webarena.py`, engine (WebArena config, see engine README), `pipeline/m3_webarena_mining.py` | `results/webarena_*.json(l)` |
| 5.3 | annotation study (complete, kappa = 1.0) | `pipeline/m2_sample_annotation.py`, `pipeline/compute_kappa.py` | `annotation/` |

## Data provenance

- **SWE-bench Verified trajectories**: public Hugging Face mirror
  `tarsur385/swebench-verified-trajectories` (5,000 trajectories, ten agents,
  accessed 2026-09; programmatic outcome labels, no human subjects).
  `pipeline/download_swebench.py` rebuilds the raw corpus.
- **WebArena GPT-4 CoT release 2**: 809 trajectories via the
  `Agent-Eval-Refine/Agent-Trajectories` Hugging Face dataset
  (`data/dl_webarena.cmd` downloads the archive; labels from the official
  WebArena evaluation release).
- Encoded files are **not bundled** (repository policy: code + results only,
  no datasets). They are regenerated bit-for-bit from the public raw corpora
  by the download/encode scripts above and serve as the exact inputs to every
  experiment.
- **You download the public corpora yourself, from the original sources.**
  The trajectory collections remain under their own licenses and terms of use
  on Hugging Face; this repository does not mirror or re-distribute them.
  Running `pipeline/download_swebench.py` and `data/dl_webarena.cmd`
  fetches them from those original sources subject to their terms — please
  review the respective dataset pages before downloading.
- **The only bundled data is the tiny demo corpus** (`demo/demo_data.json`,
  50 synthetic trajectories, generated by `demo/make_demo_data.py`), which
  contains no third-party content and exists so the mechanism can be exercised
  in seconds without any download.

## Engine build notes (Windows only)

Open `engine/anytime-itemset-engine/SustainableMining.sln` in Visual Studio 2022 with
CUDA 12.x installed and build `x64|Release`. The packaged `kernel.cu` defaults
to the SWE-bench failing-pool configuration (`swebench_mine.txt`, 29 stages);
a commented line switches it to the WebArena configuration (`webarena_mine.txt`,
19 stages) used for Section 6.5. Input transaction files and the packaged per-stage stream outputs live in
`engine/anytime-itemset-engine/AnytimeMining/x64/TransactionSets/`.

## License

MIT (see LICENSE). The PrefixGuard and SPMF baselines retain their own
licenses and are not bundled.
