# -*- coding: utf-8 -*-
"""Evaluate a trained PrefixGuard checkpoint on our evaluation pool with
Table-3-comparable trajectory-level interception statistics (M1).

Protocol (identical to the paper's guardrail experiment, Section 6.3):
  - test split = the 100-instance evaluation pool (991 trajectories after
    dropping zero-step runs; 269 failed -- same labels as labels_eval.csv)
  - trajectory intercepted  <=>  max prefix-time risk >= threshold
  - trajectory score for ranking/AUPRC = max prefix risk (online alert
    statistic: the monitor fires as soon as one prefix crosses)
  - coverage-matched comparison: for each Table 3 coverage point, intercept
    the top-m trajectories by score (m = round(coverage * 991)) and report
    precision / recall / lift / false-interception rate with the same
    formulas as guardrail_eval.py

Also reports PrefixGuard's own operating point (threshold selected on the
train split by their procedure) and inference wall-clock.

Run with the PrefixGuard venv python:
  .venv/Scripts/python.exe ..\\..\\..\\..\\..\\05_experiments\\scripts\\eval_prefixguard_swebench.py

Output: 05_experiments/results/prefixguard_eval.json
"""
import importlib.util
import json
import os
import sys
import time
from types import SimpleNamespace

import numpy as np
import torch
from sklearn.metrics import average_precision_score, roc_auc_score

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # repository root
PG_DIR = os.path.join(os.path.dirname(REPO), "03_reproducibility", "code", "PrefixGuard")  # external dependency: clone PrefixGuard (MIT) separately
sys.path.insert(0, os.path.join(PG_DIR, "src"))

DATA = os.path.join(REPO, "data", "prefixguard", "swebench_trajectories.jsonl")
CKPT = os.path.join(PG_DIR, "outputs", "swebench", "differentiable_automaton", "best_checkpoint.pt")
OUT = os.path.join(REPO, "results", "prefixguard_eval.json")

spec = importlib.util.spec_from_file_location(
    "eda", os.path.join(PG_DIR, "scripts", "evaluate_differentiable_automaton.py"))
eda = importlib.util.module_from_spec(spec)
spec.loader.exec_module(eda)

from monitor_symbolization.data import load_trajectories  # noqa: E402
from monitor_symbolization.data.io import trajectories_for_split  # noqa: E402
from monitor_symbolization.models.symbolizer import GumbelEventSymbolizer  # noqa: E402
from monitor_symbolization.monitor.evaluation import _score_soft_prefixes, _select_threshold  # noqa: E402


def traj_level(per_traj, trajectories):
    ids, scores, labels = [], [], []
    for t in trajectories:
        s = per_traj.get(t.trajectory_id)
        if not s:
            continue
        ids.append(t.trajectory_id)
        scores.append(float(max(s)))
        labels.append(0 if t.final_success else 1)
    return ids, np.array(scores), np.array(labels)


def intercept_stats(labels, scores, m):
    n = len(labels)
    order = np.argsort(-scores)
    hit = order[:m]
    n_hit_fail = int(labels[hit].sum())
    n_hit_succ = m - n_hit_fail
    unhit_fail = int(labels.sum()) - n_hit_fail
    unhit = n - m
    return {
        "m": int(m),
        "coverage": round(m / n, 4),
        "intercepted_fail_rate": round(n_hit_fail / m, 4),
        "unintercepted_fail_rate": round(unhit_fail / max(1, unhit), 4),
        "lift": round((n_hit_fail / m) / max(1e-12, unhit_fail / max(1, unhit)), 2),
        "false_interception_rate": round(n_hit_succ / m, 4),
        "recall": round(n_hit_fail / max(1, int(labels.sum())), 4),
    }


def main():
    device = torch.device("cpu")
    trajectories = load_trajectories(DATA)
    train_trajs = trajectories_for_split(trajectories, "train", role="fit")
    test_trajs = trajectories_for_split(trajectories, "test", role="eval")
    print(f"train={len(train_trajs)} test={len(test_trajs)}")

    ckpt = torch.load(CKPT, map_location="cpu", weights_only=False)
    cfg = ckpt["config"]
    print("config:", json.dumps({k: cfg[k] for k in (
        "encoder_type", "representation_mode", "step_view_frontend",
        "step_view_text_mode", "num_symbols", "q_max", "horizon",
        "warning_model_type", "selection_metric") if k in cfg}, indent=1))

    args = SimpleNamespace(
        encoder_type=None, representation_mode=None, step_view_frontend=None,
        tau2_refinement_profile=None, skillsbench_process_profile=None,
        step_view_text_mode=None, transformer_stepview_view=None,
        encoder_name=None, encoder_max_length=None, encoder_batch_size=None,
        encoder_max_features=None, tfidf_metadata_sidechannel=None,
        tfidf_metadata_sidechannel_scale=None, max_observation_lines=None)
    (encoder, encoder_type, representation_mode, max_obs_lines, frontend,
     tau2_prof, sb_prof, _, _, _, _) = eda._build_encoder(ckpt, args, train_trajs)

    symbolizer = GumbelEventSymbolizer(
        input_dim=encoder.output_dim,
        hidden_dim=cfg["hidden_dim"],
        num_symbols=cfg["num_symbols"],
        symbol_embedding_dim=cfg["symbol_embedding_dim"],
    )
    symbolizer.load_state_dict(ckpt["symbolizer_state_dict"])
    automaton = eda._build_warning_model(cfg)
    automaton.load_state_dict(
        ckpt.get("warning_model_state_dict", ckpt["automaton_state_dict"]))
    symbolizer.eval(); automaton.eval()

    horizon = cfg.get("horizon", 3)
    tau_sym = float(ckpt.get("tau_sym", cfg.get("tau_sym_end", 1.0)))
    tau_trans = float(ckpt.get("tau_trans", cfg.get("tau_trans_end", 1.0)))

    t0 = time.perf_counter()
    tr_scores, tr_labels, train_per_traj = _score_soft_prefixes(
        trajectories=train_trajs, encoder=encoder, symbolizer=symbolizer,
        automaton=automaton, horizon=horizon, device=device,
        symbol_temperature=tau_sym, transition_temperature=tau_trans,
        progress_label="pg/train",
        representation_mode=representation_mode,
        max_observation_lines=max_obs_lines, step_view_frontend=frontend,
        tau2_refinement_profile=tau2_prof,
        skillsbench_process_profile=sb_prof)
    te_scores, te_labels, test_per_traj = _score_soft_prefixes(
        trajectories=test_trajs, encoder=encoder, symbolizer=symbolizer,
        automaton=automaton, horizon=horizon, device=device,
        symbol_temperature=tau_sym, transition_temperature=tau_trans,
        progress_label="pg/test",
        representation_mode=representation_mode,
        max_observation_lines=max_obs_lines, step_view_frontend=frontend,
        tau2_refinement_profile=tau2_prof,
        skillsbench_process_profile=sb_prof)
    infer_s = time.perf_counter() - t0
    n_steps = sum(len(t.steps) for t in test_trajs)

    ids, scores, labels = traj_level(test_per_traj, test_trajs)
    n_fail = int(labels.sum())
    base = n_fail / len(labels)
    auroc = roc_auc_score(labels, scores)
    auprc = average_precision_score(labels, scores)

    # native per-prefix detection metrics (PrefixGuard's own headline
    # quantity): label = failure within `horizon` steps of this prefix
    from sklearn.metrics import average_precision_score as _ap, roc_auc_score as _ra
    prefix_auroc = _ra(te_labels, te_scores)
    prefix_auprc = _ap(te_labels, te_scores)

    # diagnosis: class-conditional trajectory length and per-position risk
    # (explains why per-prefix detection does not translate into
    # trajectory-level selectivity)
    len_f = [len(t.steps) for t in test_trajs if not t.final_success]
    len_s = [len(t.steps) for t in test_trajs if t.final_success]
    last_f, last_s = [], []
    for t in test_trajs:
        v = test_per_traj.get(t.trajectory_id)
        if v:
            (last_f if not t.final_success else last_s).append(float(v[-1]))
    diag = {
        "mean_steps_failed": round(float(np.mean(len_f)), 1),
        "mean_steps_success": round(float(np.mean(len_s)), 1),
        "mean_last_prefix_risk_failed": round(float(np.mean(last_f)), 4),
        "mean_last_prefix_risk_success": round(float(np.mean(last_s)), 4),
        "note": ("per-prefix labels are horizon-bounded detection labels "
                 "(failure within `horizon` steps); the strong prefix AUROC "
                 "reflects risk rising right before failure events, not "
                 "class discrimination between whole trajectories"),
    }

    # PrefixGuard's own operating point: their train-selected threshold,
    # trajectory intercepted iff any prefix risk crosses it
    flat_train_scores = [s for t in train_trajs
                         for s in train_per_traj.get(t.trajectory_id, [])]
    thr = _select_threshold(flat_train_scores, tr_labels)
    intercepted = np.array([
        max(test_per_traj[t.trajectory_id]) >= thr
        for t in test_trajs if t.trajectory_id in test_per_traj])
    own = intercept_stats(labels, intercepted.astype(float), int(intercepted.sum()))
    own["threshold"] = float(thr)

    # coverage-matched comparison with Table 3 (coverages of 1000 eval pool)
    table3_cov = {"k=1": 0.002, "k=3": 0.002, "k=5": 0.004, "k=10": 0.011,
                  "k=20": 0.032, "k=50": 0.043, "k=100": 0.067}
    matched = {}
    for name, cov in table3_cov.items():
        m = max(1, round(cov * len(labels)))
        matched[name] = intercept_stats(labels, scores, m)

    out = {
        "config": {k: cfg.get(k) for k in (
            "encoder_type", "representation_mode", "step_view_frontend",
            "num_symbols", "q_max", "horizon", "warning_model_type",
            "selection_metric", "seed", "epochs")},
        "pool": {"n_eval": len(labels), "n_fail": n_fail,
                 "base_fail_rate": round(base, 4)},
        "trajectory_level": {"auroc": round(float(auroc), 4),
                             "auprc": round(float(auprc), 4),
                             "score": "max prefix risk"},
        "prefix_level_native": {
            "auroc": round(float(prefix_auroc), 4),
            "auprc": round(float(prefix_auprc), 4),
            "n_prefixes": len(te_scores),
            "prefix_positive_rate": round(float(np.mean(te_labels)), 4),
            "label_semantics": ("failure within horizon=%d steps of the prefix "
                                "(PrefixGuard's native per-prefix detection "
                                "metric)" % horizon)},
        "diagnosis": diag,
        "prefixguard_own_operating_point": own,
        "coverage_matched_to_table3": matched,
        "overhead": {"inference_wall_s": round(infer_s, 2),
                     "eval_trajectories": len(test_trajs),
                     "eval_steps": n_steps,
                     "ms_per_step": round(1000 * infer_s / max(1, (
                         sum(len(t.steps) for t in train_trajs) + n_steps)), 3)},
    }
    with open(OUT, "w") as f:
        json.dump(out, f, indent=2)
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
