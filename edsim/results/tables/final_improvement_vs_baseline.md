### Every policy's improvement over the Initial-First baseline, the paper's own reference point

| policy | mean_wait_min | delta_vs_ifp_min | delta_vs_ifp_pct | holding_cost_vs_ifp_pct | meets_sla |
|---|---|---|---|---|---|
| ALT | 42.39 | -10.04 | -19.15% | -48.16% | NO |
| SBP | 44.08 | -8.35 | -15.92% | -41.06% | NO |
| SBP* | 44.18 | -8.25 | -15.73% | -39.46% | yes |
| WSEPT | 42.32 | -10.11 | -19.28% | -50.15% | NO |
| GCMU | 44.05 | -8.38 | -15.98% | -39.23% | NO |

<sub>produced by: scripts/run_08_final_comparison.py &middot; command    : python scripts/run_08_final_comparison.py --reps 100 --seed 20250402 --workers 14 &middot; timestamp  : 2026-09-24 10:46:21 &middot; args       : {"reps": 100, "seed": 20250402, "workers": 14, "quick": false, "no_figures": false}</sub>
