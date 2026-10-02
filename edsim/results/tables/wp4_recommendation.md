### WP4 recommendation at alpha=120, beta=0.5, gamma=50, evaluated over 100 replications

| configuration | k1_k2 | physician_hours_week | mean_wait_min | SL3_pct | SL4_pct | staff_cost | wait_cost | sla_cost | total_cost_week | vs_paper |
|---|---|---|---|---|---|---|---|---|---|---|
| paper's fixed roster (5,5,3) | (2.31, 8.37) | 714 | 44.18 | 95.42 | 95.64 | 85,680 | 48,798 | 4,913 | 139,391 |  |
| cost-optimal roster (6, 6, 3) | (12.20, 23.40) | 819 | 10.97 | 99.99 | 99.93 | 98,280 | 12,174 | 60 | 110,513 | -20.7% |

<sub>produced by: scripts/run_05_staffing_cost.py &middot; command    : python scripts/run_05_staffing_cost.py --reps 100 --seed 20250402 --workers 14 &middot; timestamp  : 2026-09-24 10:42:46 &middot; args       : {"reps": 100, "seed": 20250402, "workers": 14, "quick": false, "no_figures": false, "alpha": 120.0, "beta": 0.5, "gamma": 50.0, "screen_reps": 8, "refine_reps": 25, "n_refine": 6, "lo": 2, "hi": 8}</sub>
