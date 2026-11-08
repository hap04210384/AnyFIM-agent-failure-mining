# Data layout

- `encoded/` — SWE-bench Verified transactionized corpus (itemmap, seqmap,
  per-pool labels and SPMF files). Direct input to `pipeline/sequence_layer.py`
  and the engine. Rebuild from raw with `pipeline/encode_swebench.py`.
- `encoded_webarena/` — WebArena transactionized corpus (Section 6.5).
  Rebuild with `pipeline/encode_webarena.py`.
- Raw corpora are NOT bundled (multi-GB). Download:
  - SWE-bench: `python pipeline/download_swebench.py`
  - WebArena: `data/dl_webarena.cmd` (Hugging Face `Agent-Eval-Refine/Agent-Trajectories`)
