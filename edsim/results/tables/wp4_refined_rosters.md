### Best rosters after re-optimising (k1,k2) inside each

| roster | k1 | k2 | physician_hours | mean_wait_min | SL3_pct | SL4_pct | utilisation_pct | staff_cost | wait_cost | sla_cost | total_cost | stable |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| (6,6,3) | 12.20 | 23.40 | 819 | 11.34 | 100.00 | 99.99 | 75.8 | 98,280 | 12,582 | 8 | 110,870 | yes |
| (6,7,3) | 14.20 | 25.60 | 868 | 6.95 | 100.00 | 100.00 | 71.6 | 104,160 | 7,720 | 0 | 111,880 | yes |
| (5,7,3) | 15.00 | 11.50 | 812 | 14.30 | 100.00 | 99.98 | 76.5 | 97,440 | 15,875 | 20 | 113,335 | yes |
| (7,6,3) | 19.60 | 19.30 | 875 | 8.97 | 100.00 | 100.00 | 71.0 | 105,000 | 9,960 | 4 | 114,964 | yes |
| (6,6,4) | 7.90 | 15.60 | 882 | 8.38 | 100.00 | 100.00 | 70.5 | 105,840 | 9,312 | 0 | 115,152 | yes |
| (5,6,3) | 11.30 | 22.70 | 763 | 21.44 | 99.98 | 99.92 | 81.4 | 91,560 | 23,789 | 76 | 115,425 | yes |

<sub>produced by: scripts/run_05_staffing_cost.py &middot; command    : python scripts/run_05_staffing_cost.py --reps 100 --seed 20250402 --workers 14 &middot; timestamp  : 2026-09-24 10:42:42 &middot; args       : {"reps": 100, "seed": 20250402, "workers": 14, "quick": false, "no_figures": false, "alpha": 120.0, "beta": 0.5, "gamma": 50.0, "screen_reps": 8, "refine_reps": 25, "n_refine": 6, "lo": 2, "hi": 8}</sub>
