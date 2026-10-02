# Provenance log

Every entry below records one execution of one runner script: the exact command, when it ran, how long it took, the key settings, and every file it wrote.
Newest entries are appended at the bottom.

---

## `run_00_demo`

Interactive demonstration: event trace, live queue dashboard, and a single-week comparison of all five policies on one shared patient stream.

- **command**: `python scripts/run_00_demo.py --no-dashboard`
- **run at**: 2026-08-28 21:21:04  (**1.6 s**)
- **settings / key numbers**:
    - `patients_in_stream` = 2317
- **outputs**:
    - `results/tables/demo_single_week_comparison.csv` -- Single-replication, identical-stream comparison of all five scheduling policies (demo run)
    - `results/figures/demo_week_trace.png` -- Queue lengths and physician occupancy over one simulated week under SBP

---

## `run_01_validate_paper`

WP1: from-scratch rebuild of the base paper's emergency-department discrete-event model, validated against every published KPI, statistical test and equipment table.

- **command**: `python scripts/run_01_validate_paper.py --reps 100 --seed 20250402 --workers 14`
- **run at**: 2026-08-28 21:21:16  (**10.3 s**)
- **settings / key numbers**:
    - `n_replications` = 100
    - `base_seed` = 20250402
    - `crn` = True
    - `offered_load_rho` = 0.87
    - `E_initial_consult_min` = 9.0926
    - `E_followup_consult_min` = 12.841
    - `arrival_relative_L1_error` = 0.01672
    - `arrival_correlation_with_table2` = 0.999142
    - `service_sampler_in_bounds` = True
    - `qualitative_checks_passed` = 6
    - `qualitative_checks_total` = 6
- **outputs**:
    - `results/tables/wp1_paper_comparison.csv` -- WP1 validation: every KPI of the rebuilt simulator against the corresponding published value in the base paper
    - `results/tables/wp1_significance.csv` -- Paired t-tests with Bonferroni correction and Cohen's d, alongside the paper's Table 5 / Table 6 values
    - `results/tables/wp1_equipment_utilisation.csv` -- Equipment utilisation reproduced against the paper's Table 9
    - `results/raw/wp1_replications.csv`
    - `results/figures/wp1_arrival_validation.png` -- Validation of the non-homogeneous Poisson arrival process against Table 2 of the paper
    - `results/figures/wp1_waiting_boxplot.png` -- Reproduction of the paper's Figure 3: waiting-time distribution across replications, with the paper's published means overlaid
    - `results/figures/wp1_mean_wait_bars.png` -- Mean waiting time by policy with 95% CIs
    - `results/figures/wp1_service_level_l4.png` -- Level IV service level by policy (paper Table 7)

---

## `run_02_grid_search`

Reproduction of the base paper's brute-force two-stage grid search over the Slack-Based Policy thresholds, with the service-level constraint enforced by an exterior penalty. Also records the simulation budget the lattice consumes, which is the baseline for the WP3 optimiser comparison.

- **command**: `python scripts/run_02_grid_search.py --reps 100 --seed 20250402 --workers 14`
- **run at**: 2026-08-28 21:30:56  (**578.5 s**)
- **settings / key numbers**:
    - `grid_total_simulations` = 50415
    - `grid_optimum` = [4.1, 8.2]
    - `grid_optimum_objective` = 46.4601
- **outputs**:
    - `results/tables/wp2_grid_coarse_top5.csv` -- Best coarse-grid (step 1.0) threshold pairs -- our analogue of the paper's Table 3
    - `results/tables/wp2_grid_fine_top5.csv` -- Best fine-grid (step 0.1) threshold pairs -- our analogue of the paper's Table 4
    - `results/tables/wp2_grid_optimum_confirmation.csv` -- Our grid optimum vs the paper's published optimum, both re-evaluated at 100 replications
    - `results/raw/wp3_grid_budget.json`
    - `results/raw/wp2_grid_surface.json`
    - `results/figures/wp2_grid_objective_surface.png` -- Coarse-grid response surface of the penalised objective
    - `results/figures/wp2_grid_sl4_surface.png` -- Coarse-grid Level IV service level; the feasible region of Eq. (32) is the light band at high k2

---

## `run_03_wsept_policy`

WP2: implementation and evaluation of the c-mu rule (WSEPT) and the generalised c-mu rule as a fourth and fifth scheduling policy, added to the base paper's three heuristics.

- **command**: `python scripts/run_03_wsept_policy.py --reps 100 --seed 20250402 --workers 14`
- **run at**: 2026-08-28 21:31:14  (**15.3 s**)
- **settings / key numbers**:
    - `best_on_unweighted_wait` = WSEPT
    - `best_on_holding_cost` = WSEPT
    - `tfollow_spread` = {'WSEPT': 0.2412, 'GCMU': 0.1195}
- **outputs**:
    - `results/tables/wp2_cmu_indices.csv` -- Index values used by the c-mu and generalised c-mu rules
    - `results/tables/wp2_policy_comparison.csv` -- Five-policy comparison: the paper's three heuristics plus the c-mu rule and its generalisation
    - `results/tables/wp2_cmu_significance.csv` -- Paired tests of the c-weighted holding cost, WSEPT against every other policy
    - `results/tables/wp2_tfollow_sensitivity.csv` -- Sensitivity of the c-mu rules to the follow-up delay weight T_follow, the one parameter not supplied by the paper
    - `results/figures/wp2_holding_cost_bars.png` -- Holding cost by policy: the c-mu rule's own objective
    - `results/figures/wp2_mean_wait_bars.png` -- Unweighted mean waiting time across all five policies
    - `results/figures/wp2_five_policy_boxplot.png` -- Waiting-time distributions, paper policies plus ours
    - `results/figures/wp2_tfollow_sensitivity.png` -- Mean wait under WSEPT and Gc-mu as T_follow varies

---

## `run_04_nelder_mead`

WP3: a hand-written Nelder-Mead simplex optimiser with an exterior penalty for the service-level constraint, benchmarked against the base paper's brute-force grid search on equal terms (same objective, same seeds, budget counted in week-long simulations).

- **command**: `python scripts/run_04_nelder_mead.py --reps 100 --seed 20250402 --workers 14`
- **run at**: 2026-08-28 21:34:23  (**186.9 s**)
- **settings / key numbers**:
    - `grid_simulations` = 50415
    - `nm_simulations` = 2650
    - `nm_speedup` = 19.02
    - `objective_gap_vs_grid_common_scoring` = 0.0064
    - `nelder_mead_optimum` = [2.312, 8.368]
- **outputs**:
    - `results/tables/wp3_multistart.csv` -- Multi-start Nelder-Mead: each start, where it converged, and what it cost
    - `results/tables/wp3_budget_comparison.csv` -- Simulation budget required by brute-force grid search versus the hand-implemented Nelder-Mead simplex
    - `results/tables/wp3_scipy_crosscheck.csv` -- Cross-check: our hand-written simplex against SciPy's implementation on the identical objective
    - `results/tables/wp3_optimum_confirmation.csv` -- Optima from each method, re-evaluated at 100 replications on identical streams
    - `results/raw/wp3_nelder_mead_optimum.json`
    - `results/figures/wp3_convergence.png` -- Best objective found so far versus the number of week-long simulations consumed
    - `results/figures/wp3_simplex_path.png` -- The simplex trajectory drawn on the response surface that the brute-force lattice had to evaluate in full

---

## `run_05_staffing_cost`

WP4: an explicit weekly cost model for the emergency department, used to search integer physician rosters with the Slack-Based thresholds re-optimised inside each candidate.

- **command**: `python scripts/run_05_staffing_cost.py --reps 100 --seed 20250402 --workers 14`
- **run at**: 2026-08-28 21:37:31  (**185.7 s**)
- **settings / key numbers**:
    - `recommended_roster` = [6, 6, 3]
    - `recommended_thresholds` = [12.2, 23.4]
    - `weekly_cost_saving_vs_paper` = 28877.9
- **outputs**:
    - `results/tables/wp4_screening_top12.csv` -- Screening stage: all rosters scored at the incumbent thresholds, best 12 shown
    - `results/tables/wp4_refined_rosters.csv` -- Best rosters after re-optimising (k1,k2) inside each
    - `results/tables/wp4_recommendation.csv` -- WP4 recommendation at alpha=120, beta=0.5, gamma=50, evaluated over 100 replications
    - `results/tables/wp4_table10_priced.csv` -- The base paper's seven staffing scenarios evaluated under our cost model
    - `results/tables/wp4_cost_sensitivity.csv` -- Sensitivity of the staffing recommendation to the economic weights
    - `results/figures/wp4_cost_decomposition.png` -- Weekly cost broken into physician, waiting and SLA components for the best screened rosters
    - `results/figures/wp4_table10_waiting.png` -- Reproduction of the paper's Figure 5 (staffing sensitivity)

---

## `run_06_crn_variance`

WP5: side-by-side experiment with Common Random Numbers and with independent streams, quantifying the variance reduction, the equivalent replication saving, and the sharpened confidence intervals.

- **command**: `python scripts/run_06_crn_variance.py --reps 100 --seed 20250402 --workers 14`
- **run at**: 2026-08-28 21:37:57  (**22.3 s**)
- **settings / key numbers**:
    - `median_variance_reduction` = 0.9895
    - `median_efficiency_gain` = 95.8
- **outputs**:
    - `results/tables/wp5_point_estimates.csv` -- CRN leaves the marginal distribution of each policy's estimator unchanged; only the joint distribution changes
    - `results/tables/wp5_correlations.csv` -- Correlation between the two policies' per-replication means; CRN is effective exactly to the extent this is positive
    - `results/tables/wp5_variance_reduction.csv` -- The core WP5 result: variance of every pairwise difference with and without Common Random Numbers
    - `results/tables/wp5_replications_needed.csv` -- Replications required to pin each pairwise difference to +/-0.5 minutes at 95% confidence
    - `results/tables/wp5_significance_both_arms.csv` -- The paper's statistical analysis repeated with and without CRN
    - `results/figures/wp5_crn_variance_reduction.png` -- Confidence-interval width and replication cost, with and without Common Random Numbers

---

## `run_07_sensitivity`

Reproduction of the base paper's sensitivity analysis (arrival rate, physician staffing, service-time distribution), extended to include the two c-mu policies contributed by this project.

- **command**: `python scripts/run_07_sensitivity.py --reps 100 --seed 20250402 --workers 14`
- **run at**: 2026-08-28 21:40:45  (**165.4 s**)
- **settings / key numbers**:
    - `policy_spread_light_load` = 1.643
    - `policy_spread_heavy_load` = 53.393
    - `ranking_truncexp` = ['WSEPT', 'ALT', 'GCMU', 'SBP', 'IFP']
    - `ranking_lognormal` = ['ALT', 'WSEPT', 'GCMU', 'SBP', 'IFP']
- **outputs**:
    - `results/tables/sens_arrival_rate.csv` -- Mean waiting time under each policy as the arrival rate is scaled -15% to +15% (paper Figure 4)
    - `results/figures/sens_arrival_rate.png` -- Paper Figure 4 reproduced and extended to five policies
    - `results/tables/sens_staffing.csv` -- Mean waiting time under each policy across the paper's seven staffing scenarios (paper Figure 5)
    - `results/figures/sens_staffing.png` -- Paper Figure 5 reproduced and extended to five policies
    - `results/tables/sens_service_distribution.csv` -- Robustness of the results to the service-time distribution (paper Sec 3.4.3)
    - `results/figures/sens_lognormal_bars.png` -- Waiting times under the lognormal robustness check

---

## `run_08_final_comparison`

Consolidated comparison of the base paper's three scheduling heuristics against our re-tuned Slack-Based Policy and our two c-mu policies, in the paper's own KPI vocabulary, under Common Random Numbers.

- **command**: `python scripts/run_08_final_comparison.py --reps 100 --seed 20250402 --workers 14`
- **run at**: 2026-08-28 21:41:17  (**19.5 s**)
- **settings / key numbers**:
    - `lens1_best_unweighted_wait` = WSEPT
    - `lens2_best_holding_cost` = WSEPT
    - `lens3_best_sla_feasible` = SBP*
    - `sla_feasible_policies` = ['IFP', 'SBP*']
- **outputs**:
    - `results/tables/final_master_comparison.csv` -- Master comparison of all scheduling policies over 100 common-random-number replications
    - `results/tables/final_improvement_vs_baseline.csv` -- Every policy's improvement over the Initial-First baseline, the paper's own reference point
    - `results/tables/final_significance_matrix.csv` -- Every pairwise paired t-test on the mean waiting time, Bonferroni-corrected across the whole family
    - `results/tables/final_equipment.csv` -- Diagnostic equipment utilisation -- identical across policies, confirming physicians are the bottleneck
    - `results/raw/final_replications.csv`
    - `results/figures/final_boxplot.png` -- Waiting-time distributions for every policy considered
    - `results/figures/final_mean_wait.png` -- Mean waiting time, all policies
    - `results/figures/final_tradeoff.png` -- Mean waiting time against Level IV service level; only policies above the dashed line are adoptable

---

## `run_00_demo`

Interactive demonstration: event trace, live queue dashboard, and a single-week comparison of all five policies on one shared patient stream.

- **command**: `python scripts/run_00_demo.py --no-dashboard`
- **run at**: 2026-08-28 21:43:14  (**1.5 s**)
- **settings / key numbers**:
    - `patients_in_stream` = 2317
- **outputs**:
    - `results/tables/demo_single_week_comparison.csv` -- Single-replication, identical-stream comparison of all five scheduling policies (demo run)
    - `results/figures/demo_week_trace.png` -- Queue lengths and physician occupancy over one simulated week under SBP

---

## `run_08_final_comparison`

Consolidated comparison of the base paper's three scheduling heuristics against our re-tuned Slack-Based Policy and our two c-mu policies, in the paper's own KPI vocabulary, under Common Random Numbers.

- **command**: `python scripts/run_08_final_comparison.py --reps 100 --workers 14`
- **run at**: 2026-08-28 21:44:07  (**12.4 s**)
- **settings / key numbers**:
    - `lens1_best_unweighted_wait` = WSEPT
    - `lens2_best_holding_cost` = WSEPT
    - `lens3_best_sla_feasible` = SBP*
    - `sla_feasible_policies` = ['IFP', 'SBP*']
- **outputs**:
    - `results/tables/final_master_comparison.csv` -- Master comparison of all scheduling policies over 100 common-random-number replications
    - `results/tables/final_improvement_vs_baseline.csv` -- Every policy's improvement over the Initial-First baseline, the paper's own reference point
    - `results/tables/final_significance_matrix.csv` -- Every pairwise paired t-test on the mean waiting time, Bonferroni-corrected across the whole family
    - `results/tables/final_equipment.csv` -- Diagnostic equipment utilisation -- identical across policies, confirming physicians are the bottleneck
    - `results/raw/final_replications.csv`
    - `results/figures/final_boxplot.png` -- Waiting-time distributions for every policy considered
    - `results/figures/final_mean_wait.png` -- Mean waiting time, all policies
    - `results/figures/final_tradeoff.png` -- Mean waiting time against Level IV service level; only policies above the dashed line are adoptable

---

## `run_08_final_comparison`

Consolidated comparison of the base paper's three scheduling heuristics against our re-tuned Slack-Based Policy and our two c-mu policies, in the paper's own KPI vocabulary, under Common Random Numbers.

- **command**: `python scripts/run_08_final_comparison.py --reps 100 --workers 14`
- **run at**: 2026-08-28 21:45:00  (**14.8 s**)
- **settings / key numbers**:
    - `lens1_best_unweighted_wait` = WSEPT
    - `lens2_best_holding_cost` = WSEPT
    - `lens3_best_sla_feasible` = SBP*
    - `sla_feasible_policies` = ['IFP', 'SBP*']
- **outputs**:
    - `results/tables/final_master_comparison.csv` -- Master comparison of all scheduling policies over 100 common-random-number replications
    - `results/tables/final_improvement_vs_baseline.csv` -- Every policy's improvement over the Initial-First baseline, the paper's own reference point
    - `results/tables/final_significance_matrix.csv` -- Every pairwise paired t-test on the mean waiting time, Bonferroni-corrected across the whole family
    - `results/tables/final_equipment.csv` -- Diagnostic equipment utilisation -- identical across policies, confirming physicians are the bottleneck
    - `results/raw/final_replications.csv`
    - `results/figures/final_boxplot.png` -- Waiting-time distributions for every policy considered
    - `results/figures/final_mean_wait.png` -- Mean waiting time, all policies
    - `results/figures/final_tradeoff.png` -- Mean waiting time against Level IV service level; only policies above the dashed line are adoptable

---

## `run_08_final_comparison`

Consolidated comparison of the base paper's three scheduling heuristics against our re-tuned Slack-Based Policy and our two c-mu policies, in the paper's own KPI vocabulary, under Common Random Numbers.

- **command**: `python scripts/run_08_final_comparison.py --reps 100 --workers 14 --no-figures`
- **run at**: 2026-08-28 21:46:00  (**12.6 s**)
- **settings / key numbers**:
    - `lens1_best_unweighted_wait` = WSEPT
    - `lens2_best_holding_cost` = WSEPT
    - `lens3_best_sla_feasible` = SBP*
    - `sla_feasible_policies` = ['IFP', 'SBP*']
- **outputs**:
    - `results/tables/final_master_comparison.csv` -- Master comparison of all scheduling policies over 100 common-random-number replications
    - `results/tables/final_improvement_vs_baseline.csv` -- Every policy's improvement over the Initial-First baseline, the paper's own reference point
    - `results/tables/final_significance_matrix.csv` -- Every pairwise paired t-test on the mean waiting time, Bonferroni-corrected across the whole family
    - `results/tables/final_equipment.csv` -- Diagnostic equipment utilisation -- identical across policies, confirming physicians are the bottleneck
    - `results/raw/final_replications.csv`

---

## `run_08_final_comparison`

Consolidated comparison of the base paper's three scheduling heuristics against our re-tuned Slack-Based Policy and our two c-mu policies, in the paper's own KPI vocabulary, under Common Random Numbers.

- **command**: `python scripts/run_08_final_comparison.py --reps 100 --workers 14`
- **run at**: 2026-08-28 21:46:24  (**13.0 s**)
- **settings / key numbers**:
    - `lens1_best_unweighted_wait` = WSEPT
    - `lens2_best_holding_cost` = WSEPT
    - `lens3_best_sla_feasible` = SBP*
    - `sla_feasible_policies` = ['IFP', 'SBP*']
- **outputs**:
    - `results/tables/final_master_comparison.csv` -- Master comparison of all scheduling policies over 100 common-random-number replications
    - `results/tables/final_improvement_vs_baseline.csv` -- Every policy's improvement over the Initial-First baseline, the paper's own reference point
    - `results/tables/final_significance_matrix.csv` -- Every pairwise paired t-test on the mean waiting time, Bonferroni-corrected across the whole family
    - `results/tables/final_equipment.csv` -- Diagnostic equipment utilisation -- identical across policies, confirming physicians are the bottleneck
    - `results/raw/final_replications.csv`
    - `results/figures/final_boxplot.png` -- Waiting-time distributions for every policy considered
    - `results/figures/final_mean_wait.png` -- Mean waiting time, all policies
    - `results/figures/final_tradeoff.png` -- Mean waiting time against Level IV service level; only policies above the dashed line are adoptable

---

## `run_06_crn_variance`

WP5: side-by-side experiment with Common Random Numbers and with independent streams, quantifying the variance reduction, the equivalent replication saving, and the sharpened confidence intervals.

- **command**: `python scripts/run_06_crn_variance.py --reps 100 --workers 14`
- **run at**: 2026-08-28 21:47:29  (**17.3 s**)
- **settings / key numbers**:
    - `median_variance_reduction` = 0.9895
    - `median_efficiency_gain` = 95.8
- **outputs**:
    - `results/tables/wp5_point_estimates.csv` -- CRN leaves the marginal distribution of each policy's estimator unchanged; only the joint distribution changes
    - `results/tables/wp5_correlations.csv` -- Correlation between the two policies' per-replication means; CRN is effective exactly to the extent this is positive
    - `results/tables/wp5_variance_reduction.csv` -- The core WP5 result: variance of every pairwise difference with and without Common Random Numbers
    - `results/tables/wp5_replications_needed.csv` -- Replications required to pin each pairwise difference to +/-0.5 minutes at 95% confidence
    - `results/tables/wp5_significance_both_arms.csv` -- The paper's statistical analysis repeated with and without CRN
    - `results/figures/wp5_crn_variance_reduction.png` -- Confidence-interval width and replication cost, with and without Common Random Numbers

---

## `run_05_staffing_cost`

WP4: an explicit weekly cost model for the emergency department, used to search integer physician rosters with the Slack-Based thresholds re-optimised inside each candidate.

- **command**: `python scripts/run_05_staffing_cost.py --reps 100 --workers 14`
- **run at**: 2026-08-28 21:51:04  (**181.2 s**)
- **settings / key numbers**:
    - `recommended_roster` = [6, 6, 3]
    - `recommended_thresholds` = [12.2, 23.4]
    - `weekly_cost_saving_vs_paper` = 28877.9
- **outputs**:
    - `results/tables/wp4_screening_top12.csv` -- Screening stage: all rosters scored at the incumbent thresholds, best 12 shown
    - `results/tables/wp4_refined_rosters.csv` -- Best rosters after re-optimising (k1,k2) inside each
    - `results/tables/wp4_recommendation.csv` -- WP4 recommendation at alpha=120, beta=0.5, gamma=50, evaluated over 100 replications
    - `results/tables/wp4_table10_priced.csv` -- The base paper's seven staffing scenarios evaluated under our cost model
    - `results/tables/wp4_cost_sensitivity.csv` -- Sensitivity of the staffing recommendation to the economic weights
    - `results/figures/wp4_cost_decomposition.png` -- Weekly cost broken into physician, waiting and SLA components for the best screened rosters
    - `results/figures/wp4_table10_waiting.png` -- Reproduction of the paper's Figure 5 (staffing sensitivity)

---

## `run_07_sensitivity`

Reproduction of the base paper's sensitivity analysis (arrival rate, physician staffing, service-time distribution), extended to include the two c-mu policies contributed by this project.

- **command**: `python scripts/run_07_sensitivity.py --reps 100 --workers 14`
- **run at**: 2026-08-28 21:53:08  (**151.7 s**)
- **settings / key numbers**:
    - `policy_spread_light_load` = 1.643
    - `policy_spread_heavy_load` = 53.393
    - `ranking_truncexp` = ['WSEPT', 'ALT', 'GCMU', 'SBP', 'IFP']
    - `ranking_lognormal` = ['ALT', 'WSEPT', 'GCMU', 'SBP', 'IFP']
- **outputs**:
    - `results/tables/sens_arrival_rate.csv` -- Mean waiting time under each policy as the arrival rate is scaled -15% to +15% (paper Figure 4)
    - `results/figures/sens_arrival_rate.png` -- Paper Figure 4 reproduced and extended to five policies
    - `results/tables/sens_staffing.csv` -- Mean waiting time under each policy across the paper's seven staffing scenarios (paper Figure 5)
    - `results/figures/sens_staffing.png` -- Paper Figure 5 reproduced and extended to five policies
    - `results/tables/sens_service_distribution.csv` -- Robustness of the results to the service-time distribution (paper Sec 3.4.3)
    - `results/figures/sens_lognormal_bars.png` -- Waiting times under the lognormal robustness check

---

## `run_07_sensitivity`

Reproduction of the base paper's sensitivity analysis (arrival rate, physician staffing, service-time distribution), extended to include the two c-mu policies contributed by this project.

- **command**: `python scripts/run_07_sensitivity.py --reps 100 --workers 14`
- **run at**: 2026-08-29 20:57:20  (**127.9 s**)
- **settings / key numbers**:
    - `policy_spread_light_load` = 1.643
    - `policy_spread_heavy_load` = 53.393
    - `ranking_truncexp` = ['WSEPT', 'ALT', 'GCMU', 'SBP', 'IFP']
    - `ranking_lognormal` = ['ALT', 'WSEPT', 'GCMU', 'SBP', 'IFP']
- **outputs**:
    - `results/tables/sens_arrival_rate.csv` -- Mean waiting time under each policy as the arrival rate is scaled -15% to +15% (paper Figure 4)
    - `results/figures/sens_arrival_rate.png` -- Paper Figure 4 reproduced and extended to five policies
    - `results/tables/sens_staffing.csv` -- Mean waiting time under each policy across the paper's seven staffing scenarios (paper Figure 5)
    - `results/figures/sens_staffing.png` -- Paper Figure 5 reproduced and extended to five policies
    - `results/tables/sens_service_distribution.csv` -- Robustness of the results to the service-time distribution (paper Sec 3.4.3)
    - `results/figures/sens_lognormal_bars.png` -- Waiting times under the lognormal robustness check

---

## `run_00_demo`

Interactive demonstration: event trace, live queue dashboard, and a single-week comparison of all five policies on one shared patient stream.

- **command**: `python scripts/run_00_demo.py --no-dashboard --trace-hours 0 --no-figures`
- **run at**: 2026-08-29 21:04:57  (**0.4 s**)
- **settings / key numbers**:
    - `patients_in_stream` = 2317
- **outputs**:
    - `results/tables/demo_single_week_comparison.csv` -- Single-replication, identical-stream comparison of all five scheduling policies (demo run)

---

## `run_00_demo`

Interactive demonstration: event trace, live queue dashboard, and a single-week comparison of all five policies on one shared patient stream.

- **command**: `python scripts/run_00_demo.py --no-dashboard`
- **run at**: 2026-09-24 10:24:25  (**2.2 s**)
- **settings / key numbers**:
    - `patients_in_stream` = 2317
- **outputs**:
    - `results/tables/demo_single_week_comparison.csv` -- Single-replication, identical-stream comparison of all five scheduling policies (demo run)
    - `results/figures/demo_week_trace.png` -- Queue lengths and physician occupancy over one simulated week under SBP

---

## `run_01_validate_paper`

WP1: from-scratch rebuild of the base paper's emergency-department discrete-event model, validated against every published KPI, statistical test and equipment table.

- **command**: `python scripts/run_01_validate_paper.py --reps 100 --seed 20250402 --workers 14`
- **run at**: 2026-09-24 10:24:44  (**14.3 s**)
- **settings / key numbers**:
    - `n_replications` = 100
    - `base_seed` = 20250402
    - `crn` = True
    - `offered_load_rho` = 0.87
    - `E_initial_consult_min` = 9.0926
    - `E_followup_consult_min` = 12.841
    - `arrival_relative_L1_error` = 0.01672
    - `arrival_correlation_with_table2` = 0.999142
    - `service_sampler_in_bounds` = True
    - `qualitative_checks_passed` = 6
    - `qualitative_checks_total` = 6
- **outputs**:
    - `results/tables/wp1_paper_comparison.csv` -- WP1 validation: every KPI of the rebuilt simulator against the corresponding published value in the base paper
    - `results/tables/wp1_significance.csv` -- Paired t-tests with Bonferroni correction and Cohen's d, alongside the paper's Table 5 / Table 6 values
    - `results/tables/wp1_equipment_utilisation.csv` -- Equipment utilisation reproduced against the paper's Table 9
    - `results/raw/wp1_replications.csv`
    - `results/figures/wp1_arrival_validation.png` -- Validation of the non-homogeneous Poisson arrival process against Table 2 of the paper
    - `results/figures/wp1_waiting_boxplot.png` -- Reproduction of the paper's Figure 3: waiting-time distribution across replications, with the paper's published means overlaid
    - `results/figures/wp1_mean_wait_bars.png` -- Mean waiting time by policy with 95% CIs
    - `results/figures/wp1_service_level_l4.png` -- Level IV service level by policy (paper Table 7)

---

## `run_02_grid_search`

Reproduction of the base paper's brute-force two-stage grid search over the Slack-Based Policy thresholds, with the service-level constraint enforced by an exterior penalty. Also records the simulation budget the lattice consumes, which is the baseline for the WP3 optimiser comparison.

- **command**: `python scripts/run_02_grid_search.py --reps 100 --seed 20250402 --workers 14`
- **run at**: 2026-09-24 10:35:59  (**672.3 s**)
- **settings / key numbers**:
    - `grid_total_simulations` = 50415
    - `grid_optimum` = [4.1, 8.2]
    - `grid_optimum_objective` = 46.4601
- **outputs**:
    - `results/tables/wp2_grid_coarse_top5.csv` -- Best coarse-grid (step 1.0) threshold pairs -- our analogue of the paper's Table 3
    - `results/tables/wp2_grid_fine_top5.csv` -- Best fine-grid (step 0.1) threshold pairs -- our analogue of the paper's Table 4
    - `results/tables/wp2_grid_optimum_confirmation.csv` -- Our grid optimum vs the paper's published optimum, both re-evaluated at 100 replications
    - `results/raw/wp3_grid_budget.json`
    - `results/raw/wp2_grid_surface.json`
    - `results/figures/wp2_grid_objective_surface.png` -- Coarse-grid response surface of the penalised objective
    - `results/figures/wp2_grid_sl4_surface.png` -- Coarse-grid Level IV service level; the feasible region of Eq. (32) is the light band at high k2

---

## `run_03_wsept_policy`

WP2: implementation and evaluation of the c-mu rule (WSEPT) and the generalised c-mu rule as a fourth and fifth scheduling policy, added to the base paper's three heuristics.

- **command**: `python scripts/run_03_wsept_policy.py --reps 100 --seed 20250402 --workers 14`
- **run at**: 2026-09-24 10:36:18  (**15.1 s**)
- **settings / key numbers**:
    - `best_on_unweighted_wait` = WSEPT
    - `best_on_holding_cost` = WSEPT
    - `tfollow_spread` = {'WSEPT': 0.2412, 'GCMU': 0.1195}
- **outputs**:
    - `results/tables/wp2_cmu_indices.csv` -- Index values used by the c-mu and generalised c-mu rules
    - `results/tables/wp2_policy_comparison.csv` -- Five-policy comparison: the paper's three heuristics plus the c-mu rule and its generalisation
    - `results/tables/wp2_cmu_significance.csv` -- Paired tests of the c-weighted holding cost, WSEPT against every other policy
    - `results/tables/wp2_tfollow_sensitivity.csv` -- Sensitivity of the c-mu rules to the follow-up delay weight T_follow, the one parameter not supplied by the paper
    - `results/figures/wp2_holding_cost_bars.png` -- Holding cost by policy: the c-mu rule's own objective
    - `results/figures/wp2_mean_wait_bars.png` -- Unweighted mean waiting time across all five policies
    - `results/figures/wp2_five_policy_boxplot.png` -- Waiting-time distributions, paper policies plus ours
    - `results/figures/wp2_tfollow_sensitivity.png` -- Mean wait under WSEPT and Gc-mu as T_follow varies

---

## `run_04_nelder_mead`

WP3: a hand-written Nelder-Mead simplex optimiser with an exterior penalty for the service-level constraint, benchmarked against the base paper's brute-force grid search on equal terms (same objective, same seeds, budget counted in week-long simulations).

- **command**: `python scripts/run_04_nelder_mead.py --reps 100 --seed 20250402 --workers 14`
- **run at**: 2026-09-24 10:39:29  (**189.0 s**)
- **settings / key numbers**:
    - `grid_simulations` = 50415
    - `nm_simulations` = 2650
    - `nm_speedup` = 19.02
    - `objective_gap_vs_grid_common_scoring` = 0.0064
    - `nelder_mead_optimum` = [2.312, 8.368]
- **outputs**:
    - `results/tables/wp3_multistart.csv` -- Multi-start Nelder-Mead: each start, where it converged, and what it cost
    - `results/tables/wp3_budget_comparison.csv` -- Simulation budget required by brute-force grid search versus the hand-implemented Nelder-Mead simplex
    - `results/tables/wp3_scipy_crosscheck.csv` -- Cross-check: our hand-written simplex against SciPy's implementation on the identical objective
    - `results/tables/wp3_optimum_confirmation.csv` -- Optima from each method, re-evaluated at 100 replications on identical streams
    - `results/raw/wp3_nelder_mead_optimum.json`
    - `results/figures/wp3_convergence.png` -- Best objective found so far versus the number of week-long simulations consumed
    - `results/figures/wp3_simplex_path.png` -- The simplex trajectory drawn on the response surface that the brute-force lattice had to evaluate in full

---

## `run_05_staffing_cost`

WP4: an explicit weekly cost model for the emergency department, used to search integer physician rosters with the Slack-Based thresholds re-optimised inside each candidate.

- **command**: `python scripts/run_05_staffing_cost.py --reps 100 --seed 20250402 --workers 14`
- **run at**: 2026-09-24 10:43:10  (**218.3 s**)
- **settings / key numbers**:
    - `recommended_roster` = [6, 6, 3]
    - `recommended_thresholds` = [12.2, 23.4]
    - `weekly_cost_saving_vs_paper` = 28877.9
- **outputs**:
    - `results/tables/wp4_screening_top12.csv` -- Screening stage: all rosters scored at the incumbent thresholds, best 12 shown
    - `results/tables/wp4_refined_rosters.csv` -- Best rosters after re-optimising (k1,k2) inside each
    - `results/tables/wp4_recommendation.csv` -- WP4 recommendation at alpha=120, beta=0.5, gamma=50, evaluated over 100 replications
    - `results/tables/wp4_table10_priced.csv` -- The base paper's seven staffing scenarios evaluated under our cost model
    - `results/tables/wp4_cost_sensitivity.csv` -- Sensitivity of the staffing recommendation to the economic weights
    - `results/figures/wp4_cost_decomposition.png` -- Weekly cost broken into physician, waiting and SLA components for the best screened rosters
    - `results/figures/wp4_table10_waiting.png` -- Reproduction of the paper's Figure 5 (staffing sensitivity)

---

## `run_06_crn_variance`

WP5: side-by-side experiment with Common Random Numbers and with independent streams, quantifying the variance reduction, the equivalent replication saving, and the sharpened confidence intervals.

- **command**: `python scripts/run_06_crn_variance.py --reps 100 --seed 20250402 --workers 14`
- **run at**: 2026-09-24 10:43:32  (**19.0 s**)
- **settings / key numbers**:
    - `median_variance_reduction` = 0.9895
    - `median_efficiency_gain` = 95.8
- **outputs**:
    - `results/tables/wp5_point_estimates.csv` -- CRN leaves the marginal distribution of each policy's estimator unchanged; only the joint distribution changes
    - `results/tables/wp5_correlations.csv` -- Correlation between the two policies' per-replication means; CRN is effective exactly to the extent this is positive
    - `results/tables/wp5_variance_reduction.csv` -- The core WP5 result: variance of every pairwise difference with and without Common Random Numbers
    - `results/tables/wp5_replications_needed.csv` -- Replications required to pin each pairwise difference to +/-0.5 minutes at 95% confidence
    - `results/tables/wp5_significance_both_arms.csv` -- The paper's statistical analysis repeated with and without CRN
    - `results/figures/wp5_crn_variance_reduction.png` -- Confidence-interval width and replication cost, with and without Common Random Numbers

---

## `run_07_sensitivity`

Reproduction of the base paper's sensitivity analysis (arrival rate, physician staffing, service-time distribution), extended to include the two c-mu policies contributed by this project.

- **command**: `python scripts/run_07_sensitivity.py --reps 100 --seed 20250402 --workers 14`
- **run at**: 2026-09-24 10:46:01  (**145.0 s**)
- **settings / key numbers**:
    - `policy_spread_light_load` = 1.643
    - `policy_spread_heavy_load` = 53.393
    - `ranking_truncexp` = ['WSEPT', 'ALT', 'GCMU', 'SBP', 'IFP']
    - `ranking_lognormal` = ['ALT', 'WSEPT', 'GCMU', 'SBP', 'IFP']
- **outputs**:
    - `results/tables/sens_arrival_rate.csv` -- Mean waiting time under each policy as the arrival rate is scaled -15% to +15% (paper Figure 4)
    - `results/figures/sens_arrival_rate.png` -- Paper Figure 4 reproduced and extended to five policies
    - `results/tables/sens_staffing.csv` -- Mean waiting time under each policy across the paper's seven staffing scenarios (paper Figure 5)
    - `results/figures/sens_staffing.png` -- Paper Figure 5 reproduced and extended to five policies
    - `results/tables/sens_service_distribution.csv` -- Robustness of the results to the service-time distribution (paper Sec 3.4.3)
    - `results/figures/sens_lognormal_bars.png` -- Waiting times under the lognormal robustness check

---

## `run_08_final_comparison`

Consolidated comparison of the base paper's three scheduling heuristics against our re-tuned Slack-Based Policy and our two c-mu policies, in the paper's own KPI vocabulary, under Common Random Numbers.

- **command**: `python scripts/run_08_final_comparison.py --reps 100 --seed 20250402 --workers 14`
- **run at**: 2026-09-24 10:46:24  (**13.6 s**)
- **settings / key numbers**:
    - `lens1_best_unweighted_wait` = WSEPT
    - `lens2_best_holding_cost` = WSEPT
    - `lens3_best_sla_feasible` = SBP*
    - `sla_feasible_policies` = ['IFP', 'SBP*']
- **outputs**:
    - `results/tables/final_master_comparison.csv` -- Master comparison of all scheduling policies over 100 common-random-number replications
    - `results/tables/final_improvement_vs_baseline.csv` -- Every policy's improvement over the Initial-First baseline, the paper's own reference point
    - `results/tables/final_significance_matrix.csv` -- Every pairwise paired t-test on the mean waiting time, Bonferroni-corrected across the whole family
    - `results/tables/final_equipment.csv` -- Diagnostic equipment utilisation -- identical across policies, confirming physicians are the bottleneck
    - `results/raw/final_replications.csv`
    - `results/figures/final_boxplot.png` -- Waiting-time distributions for every policy considered
    - `results/figures/final_mean_wait.png` -- Mean waiting time, all policies
    - `results/figures/final_tradeoff.png` -- Mean waiting time against Level IV service level; only policies above the dashed line are adoptable
