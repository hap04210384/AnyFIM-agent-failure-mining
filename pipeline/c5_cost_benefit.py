# -*- coding: utf-8 -*-
"""C5 cost-benefit: marginal interception return per additional deployed rule,
derived from the C4 full-interval curve (results/guardrail_curve.json).

Cost model: each deployed interception rule adds runtime-check and maintenance
cost; benefit = additional failing trajectories intercepted (recall gain) and
the preserved fail-rate lift. We report, along the k-curve:
  - marginal recall gain per 100-rule block
  - marginal coverage cost (additional success trajectories flagged) per block
  - the knee point: last k where marginal recall gain >= 1 percentage point
Output: results/cost_benefit_c5.json
"""
import json
import os

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # repository root
RES = os.path.join(REPO, "results")


def main():
    curve = json.load(open(os.path.join(RES, "guardrail_curve.json"), encoding="utf-8"))
    pts = curve["k_curve"]

    blocks = []
    for prev, cur in zip(pts, pts[1:]):
        dk = cur["k"] - prev["k"]
        d_recall = cur["recall"] - prev["recall"]
        d_cov = cur["coverage"] - prev["coverage"]
        d_fir = cur["false_interception_rate"] - prev["false_interception_rate"]
        blocks.append({
            "k_from": prev["k"], "k_to": cur["k"], "n_rules": dk,
            "marginal_recall_gain": round(d_recall, 4),
            "marginal_recall_gain_per_100_rules": round(d_recall / dk * 100, 4),
            "marginal_coverage_cost": round(d_cov, 4),
            "marginal_fir_change": round(d_fir, 4),
            "lift_at_to": cur["lift"],
        })

    knee = None
    for b in blocks:
        if b["marginal_recall_gain"] >= 0.01:
            knee = b["k_to"]
    # 终点汇总
    full = pts[-1]
    out = {
        "source": "guardrail_curve.json k_curve (admission c' >= 5)",
        "eval_pool": curve["pool"],
        "n_admissible_rules": curve["n_admissible"],
        "marginal_blocks": blocks,
        "knee_point_last_k_with_ge_1pp_gain": knee,
        "summary": {
            "first_100_rules": {
                "recall_gain": round(pts[5]["recall"] - pts[0]["recall"], 4)
                if len(pts) > 5 else None,
                "coverage_cost": round(pts[5]["coverage"] - pts[0]["coverage"], 4)
                if len(pts) > 5 else None,
            },
            "full_admission": {
                "k": full["k"], "coverage": full["coverage"],
                "recall": full["recall"], "lift": full["lift"],
                "false_interception_rate": full["false_interception_rate"],
            },
        },
    }
    with open(os.path.join(RES, "cost_benefit_c5.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)

    print("k-curve operating points:")
    for p in pts:
        print("k=%-4d cov=%.3f recall=%.3f lift=%.2f FIR=%.3f" %
              (p["k"], p["coverage"], p["recall"], p["lift"],
               p["false_interception_rate"]))
    print("\nmarginal blocks (per 100-rule gain):")
    for b in blocks:
        print("k %3d->%-4d gain/100=%.2fpp cov_cost=%.3f" %
              (b["k_from"], b["k_to"],
               b["marginal_recall_gain_per_100_rules"] * 100,
               b["marginal_coverage_cost"]))
    print("\nknee (last k with >=1pp gain):", knee)
    print("DONE -> results/cost_benefit_c5.json")


if __name__ == "__main__":
    main()
