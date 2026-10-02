### Simulation budget required by brute-force grid search versus the hand-implemented Nelder-Mead simplex

| method | points_evaluated | reps_per_point | week_long_simulations | best_objective_min |
|---|---|---|---|---|
| Grid search, coarse stage (paper's method) | 1,891 | 15 | 28,365 | 47.6105 |
| Grid search, fine stage (paper's method) | 441 | 50 | 22,050 | 46.4601 |
| Grid search, TOTAL | 2,332 | - | 50,415 | 46.4601 |
| Nelder-Mead, single start (ours) | 53 | 50 | 2,650 | 46.4668 |
| Nelder-Mead, 4 starts (ours) | 196 | 50 | 9,800 | 46.4668 |

<sub>produced by: scripts/run_04_nelder_mead.py &middot; command    : python scripts/run_04_nelder_mead.py --reps 100 --seed 20250402 --workers 14 &middot; timestamp  : 2026-09-24 10:38:51 &middot; args       : {"reps": 100, "seed": 20250402, "workers": 14, "quick": false, "no_figures": false, "opt_reps": 50, "penalty_mu": 500.0, "max_iter": 80, "xtol": 0.05, "ftol": 0.02, "no_scipy": false}</sub>
