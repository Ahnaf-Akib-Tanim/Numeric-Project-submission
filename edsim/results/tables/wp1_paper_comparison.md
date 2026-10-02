### WP1 validation: every KPI of the rebuilt simulator against the corresponding published value in the base paper

| policy | metric | ours_mean | ours_sd | paper_value | deviation |
|---|---|---|---|---|---|
| IFP | Mean waiting time, all patients (min) | 52.43 | 14.10 | 46.26 | +13.3% |
| IFP | Mean waiting time, Level III (min) | 50.88 | 14.81 | 44.14 | +15.3% |
| IFP | Mean waiting time, Level IV (min) | 52.94 | 13.98 | not published | n/a |
| IFP | Service level, Level III (%) | 100.00 | 0.00 | 100.00 | +0.0% |
| IFP | Service level, Level IV (%) | 100.00 | 0.00 | 100.00 | +0.0% |
| IFP | Physician utilisation (%) | 86.36 | 1.92 | 85.43 | +1.1% |
| ALT | Mean waiting time, all patients (min) | 42.39 | 10.70 | 37.88 | +11.9% |
| ALT | Mean waiting time, Level III (min) | 6.05 | 0.57 | 6.82 | -11.2% |
| ALT | Mean waiting time, Level IV (min) | 54.61 | 14.10 | not published | n/a |
| ALT | Service level, Level III (%) | 99.96 | 0.13 | 98.08 | +1.9% |
| ALT | Service level, Level IV (%) | 87.37 | 5.59 | 89.29 | -2.2% |
| ALT | Physician utilisation (%) | 86.34 | 1.93 | 85.41 | +1.1% |
| SBP | Mean waiting time, all patients (min) | 44.08 | 11.91 | 35.25 | +25.1% |
| SBP | Mean waiting time, Level III (min) | 12.35 | 6.04 | 10.48 | +17.9% |
| SBP | Mean waiting time, Level IV (min) | 54.74 | 14.07 | 43.89 | +24.7% |
| SBP | Service level, Level III (%) | 99.99 | 0.04 | 100.00 | -0.0% |
| SBP | Service level, Level IV (%) | 89.40 | 4.51 | 100.00 | -10.6% |
| SBP | Physician utilisation (%) | 86.34 | 1.93 | 84.98 | +1.6% |

<sub>produced by: scripts/run_01_validate_paper.py &middot; command    : python scripts/run_01_validate_paper.py --reps 100 --seed 20250402 --workers 14 &middot; timestamp  : 2026-09-24 10:24:42 &middot; args       : {"reps": 100, "seed": 20250402, "workers": 14, "quick": false, "no_figures": false}</sub>
