# -*- coding: utf-8 -*-
"""C7: Fisher exact tests on every operating point of the C4 full-interval
curve (k-curve and floor-curve), plus Wilson 95% CI for recall and lift.
Extends significance_tests.json (which only covered k <= 100) to the full
coverage interval demanded by R3.
Output: results/significance_c7.json
"""
import json
import math
import os

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # repository root
RES = os.path.join(REPO, "results")


def fisher_two_sided(a, b, c, d):
    """Fisher exact test on 2x2 [[a,b],[c,d]] (two-sided, hypergeometric)."""
    n = a + b + c + d
    r1, c1 = a + b, a + c
    def hypergeom(x):
        return (math.comb(c1, x) * math.comb(n - c1, r1 - x)) / math.comb(n, r1)
    p_obs = hypergeom(a)
    lo = max(0, r1 - (n - c1))
    hi = min(r1, c1)
    return sum(hypergeom(x) for x in range(lo, hi + 1)
               if hypergeom(x) <= p_obs + 1e-12)


def wilson_ci(p_hat, n, z=1.959964):
    if n == 0:
        return (0.0, 0.0)
    denom = 1 + z * z / n
    center = (p_hat + z * z / (2 * n)) / denom
    half = z * math.sqrt(p_hat * (1 - p_hat) / n + z * z / (4 * n * n)) / denom
    return (round(center - half, 4), round(center + half, 4))


def point_stats(p, n_eval=1000, n_fail=269):
    n_hit = round(p["coverage"] * n_eval)
    n_hit_fail = round(p["recall"] * n_fail)
    n_hit_succ = n_hit - n_hit_fail
    a, b = n_hit_fail, n_hit_succ
    c, d = n_fail - n_hit_fail, (n_eval - n_fail) - n_hit_succ
    return {
        "n_intercepted": n_hit,
        "n_intercepted_failed": n_hit_fail,
        "lift": p["lift"],
        "fisher_p": round(fisher_two_sided(a, b, c, d), 6),
        "recall_wilson95": wilson_ci(p["recall"], n_fail),
        "fpr_wilson95": wilson_ci(p["false_interception_rate"], max(1, n_hit)),
    }


def main():
    curve = json.load(open(os.path.join(RES, "guardrail_curve.json"), encoding="utf-8"))
    out = {"pool": curve["pool"],
           "note": "Fisher exact test: intercepted(fail/succ) vs unintercepted(fail/succ).",
           "k_curve": [], "floor_curve": []}
    for p in curve["k_curve"]:
        s = point_stats(p)
        s["k"] = p["k"]
        s["coverage"] = p["coverage"]
        s["recall"] = p["recall"]
        out["k_curve"].append(s)
        print("k=%-4d cov=%.3f recall=%.3f lift=%.2f fisher_p=%.5g CI=%s" %
              (s["k"], s["coverage"], s["recall"], s["lift"], s["fisher_p"],
               s["recall_wilson95"]))
    for p in curve["floor_curve"]:
        s = point_stats(p)
        s["min_contrast"] = p["min_contrast"]
        s["n_rules"] = p["n_rules"]
        s["coverage"] = p["coverage"]
        s["recall"] = p["recall"]
        out["floor_curve"].append(s)
        print("floor=%-5.1f cov=%.3f recall=%.3f lift=%.2f fisher_p=%.5g" %
              (s["min_contrast"], s["coverage"], s["recall"], s["lift"],
               s["fisher_p"]))
    with open(os.path.join(RES, "significance_c7.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print("DONE -> results/significance_c7.json")


if __name__ == "__main__":
    main()
