### Our grid optimum vs the paper's published optimum, both re-evaluated at 100 replications

| setting | k1_k2 | mean_wait_min | sd_min | SL3_pct | SL4_pct | constraint_status |
|---|---|---|---|---|---|---|
| our grid optimum | (4.1, 8.2) | 44.17 | 11.94 | 97.73 | 95.49 | feasible |
| paper optimum (13.1, 2.1) | (13.1, 2.1) | 44.08 | 11.91 | 99.99 | 89.40 | INFEASIBLE |

<sub>produced by: scripts/run_02_grid_search.py &middot; command    : python scripts/run_02_grid_search.py --reps 100 --seed 20250402 --workers 14 &middot; timestamp  : 2026-09-24 10:35:55 &middot; args       : {"reps": 100, "seed": 20250402, "workers": 14, "quick": false, "no_figures": false, "coarse_reps": 15, "fine_reps": 50, "coarse_step": 1.0, "fine_step": 0.1, "k1_max": 30.0, "k2_max": 60.0, "penalty_mu": 500.0}</sub>
