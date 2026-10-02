### Optima from each method, re-evaluated at 100 replications on identical streams

| setting | k1_k2 | mean_wait_min | sd_min | SL3_pct | SL4_pct | constraint_status |
|---|---|---|---|---|---|---|
| Nelder-Mead optimum | (2.31, 8.37) | 44.18 | 11.95 | 95.42 | 95.64 | feasible |
| grid-search optimum | (4.10, 8.20) | 44.17 | 11.94 | 97.73 | 95.49 | feasible |
| paper optimum (13.1, 2.1) | (13.10, 2.10) | 44.08 | 11.91 | 99.99 | 89.40 | INFEASIBLE |

<sub>produced by: scripts/run_04_nelder_mead.py &middot; command    : python scripts/run_04_nelder_mead.py --reps 100 --seed 20250402 --workers 14 &middot; timestamp  : 2026-09-24 10:39:26 &middot; args       : {"reps": 100, "seed": 20250402, "workers": 14, "quick": false, "no_figures": false, "opt_reps": 50, "penalty_mu": 500.0, "max_iter": 80, "xtol": 0.05, "ftol": 0.02, "no_scipy": false}</sub>
