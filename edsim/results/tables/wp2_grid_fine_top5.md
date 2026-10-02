### Best fine-grid (step 0.1) threshold pairs -- our analogue of the paper's Table 4

| rank | k1_k2 | mean_wait_min | SL3_pct | SL4_pct | penalty_min | objective_min |
|---|---|---|---|---|---|---|
| 1 | (4.1, 8.2) | 46.46 | 97.52 | 95.00 | 0.00 | 46.46 |
| 2 | (3.9, 8.1) | 46.47 | 97.34 | 95.00 | 0.00 | 46.47 |
| 3 | (3.5, 8.3) | 46.47 | 96.96 | 95.02 | 0.00 | 46.47 |
| 4 | (3.8, 8.1) | 46.47 | 97.26 | 95.00 | 0.00 | 46.47 |
| 5 | (3.8, 8.4) | 46.47 | 97.35 | 95.05 | 0.00 | 46.47 |

<sub>produced by: scripts/run_02_grid_search.py &middot; command    : python scripts/run_02_grid_search.py --reps 100 --seed 20250402 --workers 14 &middot; timestamp  : 2026-09-24 10:35:52 &middot; args       : {"reps": 100, "seed": 20250402, "workers": 14, "quick": false, "no_figures": false, "coarse_reps": 15, "fine_reps": 50, "coarse_step": 1.0, "fine_step": 0.1, "k1_max": 30.0, "k2_max": 60.0, "penalty_mu": 500.0}</sub>
