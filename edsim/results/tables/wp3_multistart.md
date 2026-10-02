### Multi-start Nelder-Mead: each start, where it converged, and what it cost

| start_point | converged_to | objective_min | iterations | simulations | converged |
|---|---|---|---|---|---|
| (2, 5) | (3.292, 8.669) | 46.4817 | 20 | 2,100 | yes |
| (10, 30) | (2.312, 8.368) | 46.4668 | 24 | 2,650 | yes |
| (20, 70) | (20.551, 9.136) | 46.5885 | 25 | 2,500 | yes |
| (28, 110) | (25.963, 8.490) | 46.6215 | 24 | 2,550 | yes |

<sub>produced by: scripts/run_04_nelder_mead.py &middot; command    : python scripts/run_04_nelder_mead.py --reps 100 --seed 20250402 --workers 14 &middot; timestamp  : 2026-09-24 10:38:51 &middot; args       : {"reps": 100, "seed": 20250402, "workers": 14, "quick": false, "no_figures": false, "opt_reps": 50, "penalty_mu": 500.0, "max_iter": 80, "xtol": 0.05, "ftol": 0.02, "no_scipy": false}</sub>
