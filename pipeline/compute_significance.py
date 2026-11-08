# ASC revision: statistical significance tests (added 2026-10-03)
# 1) Fisher exact test on interception enrichment per k (guardrail_eval.json)
# 2) Spearman rank correlation of baseline grid output/runtime vs sigma
# 3) Sensitivity sweep mean/std of recall@100
import json, statistics as st
from scipy import stats

RES = 'results'
out = {}

# 1) Fisher
g = json.load(open(f'{RES}/guardrail_eval.json', encoding='utf-8'))
n_eval = g['pool']['n_eval']; n_fail = g['pool']['n_fail']
fisher = []
for e in g['chain_rules']:
    n_int = round(e['coverage'] * n_eval)
    a = round(e['recall'] * n_fail); b = n_int - a
    c = n_fail - a; d = (n_eval - n_fail) - b
    _, p = stats.fisher_exact([[a, b], [c, d]])
    fisher.append({'k': e['k'], 'n_intercepted': n_int, 'n_intercepted_failed': a,
                   'lift': e['lift'], 'false_interception_rate': e['false_interception_rate'],
                   'fisher_p': float(p)})
out['interception_fisher'] = fisher

# 2) Spearman per algo
sp = {}
for f, kind in [('baselines_itemset.json', 'itemset'), ('baselines_sequence.json', 'sequence')]:
    d = json.load(open(f'{RES}/{f}', encoding='utf-8'))
    grid = d['grid']
    algos = {}
    for idx, r in enumerate(d['runs']):
        algos.setdefault(r['algo'], []).append((grid[idx % 20], r))
    for algo, runs in algos.items():
        ok = [(gg, r) for gg, r in runs if not r['timeout'] and r['n_patterns'] is not None]
        rho_n, p_n = stats.spearmanr([gg for gg, r in ok], [r['n_patterns'] for gg, r in ok])
        ts = [min(r['wall_s'] if r['wall_s'] is not None else 120.0, 120.0) for gg, r in runs]
        rho_t, p_t = stats.spearmanr([gg for gg, r in runs], ts)
        sp[algo] = {'n_runs': len(runs), 'n_timeouts': sum(1 for gg, r in runs if r['timeout']),
                    'patterns_spearman_rho': float(rho_n), 'patterns_p': float(p_n),
                    'time_spearman_rho': float(rho_t), 'time_p': float(p_t)}
out['baseline_grid_spearman'] = sp

# 3) sweep
d = json.load(open(f'{RES}/m4a_recall_sweep.json', encoding='utf-8'))
rec = [r['recall_at'].get('100') for r in d['results'] if r['recall_at'].get('100') is not None]
out['sweep_recall100'] = {'n': len(rec), 'mean': st.mean(rec), 'std': st.stdev(rec),
                          'min': min(rec), 'max': max(rec)}

json.dump(out, open(f'{RES}/significance_tests.json', 'w', encoding='utf-8'), indent=2, ensure_ascii=False)
print(json.dumps(out, indent=1, ensure_ascii=False)[:1200])
