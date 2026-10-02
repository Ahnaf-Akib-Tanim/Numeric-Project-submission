### Paired t-tests with Bonferroni correction and Cohen's d, alongside the paper's Table 5 / Table 6 values

| comparison | mean_diff_min | t_stat | p_value | significant_after_bonferroni | cohens_d | interpretation | paper_mean_diff_min | paper_cohens_d |
|---|---|---|---|---|---|---|---|---|
| IFP vs ALT | 10.0415 | 28.4706 | 1.774e-49 | Yes | 2.8471 | Huge effect | 8.1000 | 2.0099 |
| IFP vs SBP | 8.3457 | 33.7338 | 4.294e-56 | Yes | 3.3734 | Huge effect | 10.5521 | 2.8245 |
| ALT vs SBP | -1.6958 | -11.5769 | 4.145e-20 | Yes | -1.1577 | Large effect | 2.4521 | 1.5437 |

<sub>produced by: scripts/run_01_validate_paper.py &middot; command    : python scripts/run_01_validate_paper.py --reps 100 --seed 20250402 --workers 14 &middot; timestamp  : 2026-09-24 10:24:42 &middot; args       : {"reps": 100, "seed": 20250402, "workers": 14, "quick": false, "no_figures": false}</sub>
