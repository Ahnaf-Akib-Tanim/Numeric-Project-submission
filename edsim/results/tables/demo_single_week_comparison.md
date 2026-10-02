### Single-replication, identical-stream comparison of all five scheduling policies (demo run)

| policy | W_total_min | W_L3_min | W_L4_min | wait_initial_L3_min | wait_initial_L4_min | wait_followup_min | SL_L3_pct | SL_L4_pct | physician_util_pct | patients_completed | patients_unfinished | runtime_s |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| IFP | 60.55 | 59.87 | 60.78 | 1.85 | 4.24 | 98.14 | 100.0 | 100.0 | 88.8 | 2290 | 27 | 0.06 |
| ALT | 49.73 | 6.86 | 64.30 | 3.30 | 61.21 | 5.47 | 100.0 | 82.9 | 88.8 | 2295 | 22 | 0.06 |
| SBP | 53.14 | 16.58 | 65.58 | 5.65 | 51.27 | 23.02 | 100.0 | 86.2 | 88.8 | 2297 | 20 | 0.08 |
| WSEPT | 50.13 | 4.04 | 65.80 | 1.75 | 63.47 | 3.96 | 100.0 | 83.0 | 88.8 | 2297 | 20 | 0.05 |
| GCMU | 51.47 | 16.48 | 63.36 | 4.53 | 51.49 | 20.37 | 100.0 | 87.7 | 88.8 | 2296 | 21 | 0.08 |

<sub>produced by: scripts/run_00_demo.py &middot; command    : python scripts/run_00_demo.py --no-dashboard &middot; timestamp  : 2026-09-24 10:24:22 &middot; args       : {"reps": 100, "seed": 20250402, "workers": 14, "quick": false, "no_figures": false, "policy": "SBP", "trace_hours": 3.0, "trace_limit": 120, "dash_days": 2.0, "speed": 0.0, "no_trace": false, "no_dashboard": true}</sub>
