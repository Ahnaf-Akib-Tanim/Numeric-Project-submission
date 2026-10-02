# Simulating and Optimizing Emergency-Department Patient Flow

**CSE 402 — Numerical Analysis, Simulation and Modeling Sessional · Section C**

Sudip Kumar Saha (2105152) · Ahnaf Akib Tanim (2105154) · Md. Shahjalal Rumman (2105165) ·
Md. Dulal Hossain (2105169) · Md. Shoaib Hossain (2105170)

---

## 1. What this project is

A from-scratch discrete-event simulation (DES) of a hospital emergency department, built to

1. **reproduce** the model and results of the base paper, and
2. **extend** it in four ways the paper explicitly does not attempt.

**Base paper.** Lv, W.; Liu, R.; Yan, F.; Wang, Y. (2026). *Discrete Event Simulation-Based
Analysis and Optimization of Emergency Patient Scheduling Strategies.* **Healthcare 14(1), 99.**
<https://doi.org/10.3390/healthcare14010099> (the PDF is in the parent directory as
`healthcare-14-00099-v2.pdf`).

The paper builds a DES of a Chinese tertiary-hospital ED serving triage Level III and IV
patients, compares three physician-scheduling policies — Initial-First (**IFP**),
Alternating 1:1 (**ALT**) and a Slack-Based Policy (**SBP**) with two tunable thresholds
`(k1, k2)` — and tunes those thresholds with a two-stage brute-force grid search.

| | Base paper does | Base paper does **not** do | Our work package |
|---|---|---|---|
| Search | grid search over `(k1, k2)` | optimise **staffing** jointly with thresholds | **WP4** |
| Policies | 3 heuristics | compare against a **provably optimal** queueing rule | **WP2** |
| Method | brute force, hundreds of full runs | a **derivative-free numerical optimiser** | **WP3** |
| Statistics | 100 independent replications | **variance reduction** (common random numbers) | **WP5** |
| Engine | not released; data not public | an open, from-scratch, validated rebuild | **WP1** |

The simulator is written with a hand-rolled `heapq` event loop — **no SimPy or other black-box
process library** — so every mechanism in the paper is visible and auditable in the code.

---

## 2. Quick start

> **New here?** Read **[`docs/PROJECT_GUIDE.pdf`](docs/PROJECT_GUIDE.pdf)** first — a 31-page
> illustrated guide covering the paper, the methods, the code map, the results and viva prep.
> Regenerate it after a fresh run with `python docs/make_guide.py`.

```bash
cd edsim
pip install -r requirements.txt

python tests/test_model.py            # 33 correctness checks, ~20 s
python scripts/run_00_demo.py         # WATCH the simulation run, ~15 s
python scripts/run_all.py --quick     # whole study, low fidelity, ~5 min
python scripts/run_all.py             # whole study, full fidelity, ~20 min
```

Everything is written to `results/` — see [§6](#6-where-the-results-go).

> **Windows / PowerShell note.** All commands are plain `python …`; no shell-specific
> syntax is used. The scripts spawn worker processes, so always run them as scripts
> (`python scripts/run_01_validate_paper.py`), never by pasting the code into a REPL.

---

## 3. What each Python file does

### 3.1 `src/` — the library (never run directly)

The five modules in **bold** correspond one-to-one to the five boxes of the base paper's
Figure 2 ("Modular architecture of the emergency department DES system").

| File | Role | What is inside |
|---|---|---|
| `src/config.py` | **parameters** | Every numeric constant, each annotated with the paper section it comes from. Table 2's 7×24 arrival-rate matrix, triage mix, service-time bounds, the four diagnostic modalities, shift rosters, Table 10 scenarios, the paper's published results (used as validation targets), and the WP4 cost weights. Parameters the paper does *not* give are marked `OUR CHOICE` with a justification. |
| `src/entities.py` | **Entity Definition Module** | `Patient`, `ExamOrder`, `Stage`, `EventType`, and the future-event-list entry format. A `Patient` carries **all** of its random attributes, drawn before the run starts. |
| `src/distributions.py` | random variates | Inverse-CDF samplers: truncated exponential (baseline) and truncated lognormal (robustness check), plus the closed-form truncated-exponential mean. One uniform per variate — the property that makes CRN exact. |
| `src/rng.py` | randomness & CRN | Lewis–Shedler **thinning** for the non-homogeneous Poisson arrivals; `generate_patient_stream()` which materialises one replication's entire exogenous randomness; `replication_seed()` which implements the CRN / independent-streams switch; `offered_load()` for the analytic sanity check. |
| `src/resources.py` | **Resource Scheduling Module** | `PhysicianPool` (time-varying roster, non-preemptive service, time-weighted utilisation) and `DeviceBank` (four modalities, FIFO device queues → the `rho_j` term of Eq. 4). |
| `src/policies.py` | **Strategy Execution Module** | `IFP` (Eqs. 8–10), `ALT` (Eqs. 11–13), `SBP` (Eqs. 14–23), plus our `WSEPT` (c·μ rule) and `GCMU` (generalised c·μ). Every policy implements one method: given the free physicians and the three queues, return who starts service. |
| `src/engine.py` | **Event Scheduling Module** | The DES core: a `heapq` future-event list, five event types, and a single `_dispatch()` call site where the policy plugs in. |
| `src/metrics.py` | **Statistical Output Module** | Turns a finished run into the paper's KPIs (Eqs. 24–30) plus diagnostics; documents *which* reading of "average waiting time" the paper's numbers imply and why. |
| `src/experiment.py` | replication driver | Runs N replications across a persistent process pool; per-worker patient-stream cache; the CRN switch; `evaluate_points()` used by both optimisers. |
| `src/stats.py` | inference | Paired t-tests, Bonferroni correction, Cohen's d, confidence intervals, the CRN variance-reduction analysis, and `reps_for_halfwidth()`. |
| `src/optimizers.py` | **WP3** | `SimulationObjective` (sample-average approximation + exterior penalty), `grid_search()` (the paper's method), and a **hand-written** `nelder_mead()` with projection bounds and multi-start. |
| `src/staffing.py` | **WP4** | The weekly cost function `C(R,k1,k2)`, the roster enumerator, and the staffing objective that the Nelder-Mead optimiser minimises inside each candidate roster. |
| `src/plotting.py` | figures | One shared visual language: fixed colour + marker + linestyle per policy (validated for colour-vision deficiency), single-hue sequential ramp for heatmaps, no dual-axis charts. |
| `src/console.py` | terminal output | Banners, progress bars with ETA, ASCII tables and bar charts — the machinery that makes the scripts *show* their work. |
| `src/report.py` | provenance | The `Artifact` context manager: writes every table as CSV + Markdown with a provenance header, writes a JSON manifest, and appends to `results/PROVENANCE.md`. |

### 3.2 `scripts/` — the runnable experiments

Each script prints a full narrative to the terminal *and* writes its tables and figures.
Run them in this order (or use `run_all.py`).

| # | Script | Work package | What it does | Full runtime |
|---|---|---|---|---|
| 0 | `run_00_demo.py` | — | **Watch the engine work.** Prints a live event-by-event trace, then an in-place console dashboard of queue lengths and physician occupancy updating every simulated hour, then runs all five policies on one shared week. | ~15 s |
| 1 | `run_01_validate_paper.py` | **WP1** | Rebuilds and validates the paper. Checks the arrival sampler against Table 2, the service sampler against its closed-form mean, then runs IFP/ALT/SBP for 100 replications and compares **every** published KPI, the Table 5 t-tests, the Table 6 effect sizes and the Table 9 equipment utilisation. | ~25 s |
| 2 | `run_02_grid_search.py` | — | Reproduces the paper's **two-stage brute-force grid search** (coarse step 1.0, then fine step 0.1) under the service-level constraint. Records the simulation budget it consumed — the baseline WP3 is measured against. **This is the expensive script, on purpose**: 50 415 week-long simulations. | ~10 min |
| 3 | `run_03_wsept_policy.py` | **WP2** | Adds the **c·μ rule / WSEPT** and the **generalised c·μ rule**, prints the index values the theory produces, compares all five policies, and sweeps the one weight the paper does not supply (`T_follow`). | ~20 s |
| 4 | `run_04_nelder_mead.py` | **WP3** | Runs our **hand-implemented Nelder-Mead** simplex with a penalty function against the same objective, live-traces the iterations, does a 4-start robustness check, cross-checks against SciPy, and reports the **simulation-budget speed-up** over the grid search. | ~3 min |
| 5 | `run_05_staffing_cost.py` | **WP4** | Screens 140 integer rosters, re-tunes `(k1,k2)` inside the best ones with Nelder-Mead, prices the paper's own Table 10 scenarios, and stress-tests the recommendation against the cost weights. | ~3 min |
| 6 | `run_06_crn_variance.py` | **WP5** | Runs the whole comparison **twice** — once with common random numbers, once with independent streams — and quantifies the variance reduction, the induced correlation, the sharpened confidence intervals and the replication saving. | ~20 s |
| 7 | `run_07_sensitivity.py` | — | Reproduces the paper's Sec 3.4: arrival rate ±15%, the seven Table 10 rosters, and the truncated-lognormal service-time robustness check — extended to all five policies. | ~2.5 min |
| 8 | `run_08_final_comparison.py` | **WP5** | The consolidated master table, the full pairwise significance matrix, the verdict under three explicit objectives, and `results/RESULTS_SUMMARY.md`. | ~15 s |
| — | `run_all.py` | — | Runs 1–8 in dependency order with a summary table at the end. | **~20 min** |
| — | `scripts/_common.py` | — | Shared bootstrap: `sys.path` setup and the common CLI options. Not runnable. |

### 3.3 `tests/test_model.py`

33 checks, each pinning down a property some published number depends on: the samplers,
the Eq. (1) day/hour indexing, thinning convergence, CRN seed behaviour, engine invariants
(no patient served before arrival, no idle physician while patients wait, Eq. 4's exam
chain, non-preemptive shift changes), policy behaviour (IFP starves follow-ups, raising
`k2` monotonically improves the Level IV service level, the c·μ indices rank as theory
predicts), the Nelder-Mead implementation against Rosenbrock and against SciPy, and a
direct verification that CRN reduces the variance of the difference.

```bash
python tests/test_model.py       # plain runner, no pytest required
```

---

## 4. Command-line options

Every runner script accepts:

| Flag | Default | Meaning |
|---|---|---|
| `--reps N` | `100` | replications per policy (the paper's setting) |
| `--seed S` | `20250402` | base seed — fixes every result reproducibly |
| `--workers W` | cores − 2 | worker processes |
| `--quick` | off | fast, low-fidelity pass for smoke-testing the pipeline |
| `--no-figures` | off | skip figure rendering |

Script-specific flags (see `--help` on each):

```bash
python scripts/run_00_demo.py   --policy SBP --trace-hours 6 --dash-days 3 --speed 0.05
python scripts/run_02_grid_search.py  --coarse-reps 10 --fine-reps 30 --k2-max 60
python scripts/run_04_nelder_mead.py  --opt-reps 30 --penalty-mu 500 --xtol 0.05
python scripts/run_05_staffing_cost.py --alpha 150 --beta 1.0 --gamma 100 --n-refine 8
python scripts/run_06_crn_variance.py --target-halfwidth 0.5
python scripts/run_07_sensitivity.py  --arrival-span 15 --arrival-step 3
python scripts/run_all.py --only 4,8 --reps 200
```

---

## 5. How the results are produced — the honest chain

This is the part to read if you want to check the work rather than take it on faith.

### 5.1 Parameters → code

Every number in the model lives in exactly one place, `src/config.py`, and carries the
paper section it came from. Nothing is hard-coded anywhere else. Values the paper does not
publish are marked `OUR CHOICE` with an explicit justification — there are only five of
them, and they are listed in [§7](#7-what-we-had-to-decide-ourselves).

### 5.2 Randomness → reproducibility

For replication *r*, `replication_seed(base_seed, r)` produces one integer. That integer
seeds a `SeedSequence` which spawns six independent PCG64 generators — one each for
arrivals, triage levels, initial service times, follow-up service times, examination need
and examination selection. From those, `generate_patient_stream()` builds the complete list
of patients **before the simulation starts**: arrival time, level, both consultation
durations, whether diagnostics are needed and which ones.

Two consequences:

- **The engine never draws a random number while running.** Every difference between two
  policies' results is caused by scheduling, not by sampling.
- **Common random numbers are exact, not approximate.** Patient #1723 is bit-identical
  across every policy in replication *r*. Most DES codes lose most of the CRN benefit
  because the two runs consume uniforms in a different order once decisions diverge; here
  the synchronisation is structural. This is why WP5's measured variance reduction is so
  large, and `tests/test_model.py::test_crn_actually_reduces_variance_of_the_difference`
  checks it directly.

### 5.3 Simulation → metrics

`src/metrics.py` documents a reading decision that matters. The paper reports, for its SBP
optimum, Level III = 10.48 min, Level IV = 43.89 min, all patients = 35.25 min, and

```
0.25 × 10.48 + 0.75 × 43.89 = 35.54 ≈ 35.25
```

so the headline figure is the patient-weighted mean of the two per-level figures. It cannot
be the *initial-consultation* wait alone, because the paper simultaneously reports a 100%
Level III service level against a 30-minute target while quoting 44.14 min for Level III
under IFP. We therefore report

- **`W_l`** = mean over Level-*l* patients of (initial wait + follow-up wait), and
- **`W_total`** = the same over all patients,

while the per-consultation averages of Eqs. 24–26 are computed and reported alongside so
nothing is hidden. The **service level** (Eqs. 27–28) uses the initial-consultation wait
only, since `T_l` is a time-to-be-seen target — the only reading under which the paper's
100% IFP service level is attainable.

Like the paper, averages are taken over consultations that *completed* within the simulated
week; `n_unfinished` is reported in every table so the censoring is visible.

### 5.4 Metrics → tables and figures

Each script wraps its work in an `Artifact` context (`src/report.py`). Every table it writes
gets a provenance header:

```
# produced by: scripts/run_01_validate_paper.py
# command    : python scripts/run_01_validate_paper.py --reps 100 --seed 20250402
# timestamp  : 2026-08-28 21:14:07
# args       : {"reps": 100, "seed": 20250402, "workers": 14, ...}
```

and the same information, plus every output path and the key numbers, is appended to
**`results/PROVENANCE.md`** and written as JSON to `results/raw/<script>.manifest.json`.

So for any file in `results/`, you can answer "which command produced this, when, with what
settings?" by grepping one file.

### 5.5 Optimisation → a fair benchmark

Both the grid search and Nelder-Mead minimise the *same* penalised objective

```
F(k1,k2) = W_total(k1,k2) + μ · Σ_l max(0, SL_l^min − SL_l(k1,k2))
```

on the *same* fixed set of patient streams (sample-average approximation with CRN, which
makes the objective deterministic — evaluating a point twice returns the identical number).
Budget is counted in **week-long simulations**, not seconds, so the comparison is
hardware-independent. Because the two methods use different replication counts per point,
their raw objective values are not directly comparable; `run_04` therefore re-scores both
optima on one identical full-length batch before pronouncing a verdict.

---

## 6. Where the results go

```
results/
├── PROVENANCE.md            ← append-only log: every run, its command, its outputs
├── RESULTS_SUMMARY.md       ← headline digest, written by run_08
├── tables/                  ← every table as .csv (with provenance header) AND .md
├── figures/                 ← every figure as .png (200 dpi) AND .pdf
└── raw/
    ├── *.manifest.json      ← machine-readable record of each script execution
    ├── wp1_replications.csv ← per-replication KPIs, one row per (policy, replication)
    ├── final_replications.csv
    ├── wp2_grid_surface.json, wp3_grid_budget.json, wp3_nelder_mead_optimum.json
    └── full_pipeline_console.log
```

### Figure and table index

| Produced by | Figures | Tables |
|---|---|---|
| `run_00_demo` | `demo_week_trace` | `demo_single_week_comparison` |
| `run_01` (WP1) | `wp1_arrival_validation`, `wp1_waiting_boxplot`, `wp1_mean_wait_bars`, `wp1_service_level_l4` | `wp1_paper_comparison`, `wp1_significance`, `wp1_equipment_utilisation` |
| `run_02` | `wp2_grid_objective_surface`, `wp2_grid_sl4_surface` | `wp2_grid_coarse_top5`, `wp2_grid_fine_top5`, `wp2_grid_optimum_confirmation` |
| `run_03` (WP2) | `wp2_holding_cost_bars`, `wp2_mean_wait_bars`, `wp2_five_policy_boxplot`, `wp2_tfollow_sensitivity` | `wp2_cmu_indices`, `wp2_policy_comparison`, `wp2_cmu_significance`, `wp2_tfollow_sensitivity` |
| `run_04` (WP3) | `wp3_convergence`, `wp3_simplex_path` | `wp3_multistart`, `wp3_budget_comparison`, `wp3_scipy_crosscheck`, `wp3_optimum_confirmation` |
| `run_05` (WP4) | `wp4_cost_decomposition`, `wp4_table10_waiting` | `wp4_screening_top12`, `wp4_refined_rosters`, `wp4_recommendation`, `wp4_table10_priced`, `wp4_cost_sensitivity` |
| `run_06` (WP5) | `wp5_crn_variance_reduction` | `wp5_point_estimates`, `wp5_correlations`, `wp5_variance_reduction`, `wp5_replications_needed`, `wp5_significance_both_arms` |
| `run_07` | `sens_arrival_rate`, `sens_staffing`, `sens_lognormal_bars` | `sens_arrival_rate`, `sens_staffing`, `sens_service_distribution` |
| `run_08` | `final_boxplot`, `final_mean_wait`, `final_tradeoff` | `final_master_comparison`, `final_improvement_vs_baseline`, `final_significance_matrix`, `final_equipment` |

---

## 7. What we had to decide ourselves

The paper's dataset is not public and a few modelling details are not specified. There are
exactly five such decisions; all are flagged `OUR CHOICE` in `src/config.py`.

| Decision | Value | Why |
|---|---|---|
| `SL_min` — the numeric service-level constraint of Eq. (32) | 0.95 for both levels | The paper writes the constraint but never prints the number. 95% is a standard ED target and is strict enough that the penalty term actually binds. |
| `T_follow` — the delay weight for follow-up patients, needed by the c·μ rule | 60 min | The midpoint of `T_3 = 30` and `T_4 = 120`. `run_03` sweeps it from 15 to 120 min and shows the policy ranking never flips. |
| Grid-search box | `k1 ∈ [0,30]`, `k2 ∈ [0,60]` | The paper's Table 3 lists winners at `k1 = 26` and `k2 = 40`, so the box must at least contain those. |
| Cost weights `α, β, γ` (WP4 only) | 120 / 0.50 / 50 | An ED attending at ~USD 250k/yr loaded over ~2080 h/yr is ~120/h; β values a patient-hour of waiting at 30 units; γ makes an SLA breach cost far more than the raw minutes causing it. `run_05` stage D re-prices everything under four alternative weightings. |
| "60% require **at least one** test" vs. independent per-modality draws | resample so "at least one" holds exactly | The two readings differ by 1.99% of exam volume. Switchable via `SimConfig.exam_require_at_least_one`. |

---

## 8. Headline findings

Produced by `python scripts/run_all.py` at the default `--seed 20250402 --reps 100`.
These are copied here for convenience; the generated
`results/RESULTS_SUMMARY.md` and `results/PROVENANCE.md` are the source of truth.

**WP1 — the rebuild is faithful in structure.** All six automated qualitative checks pass.
The arrival sampler matches Table 2 to a 1.67% L¹ error (correlation 0.9991); the
diagnostic-equipment table lands within ~0.5 percentage points of the paper's Table 9 on
all four modalities; physician utilisation is 86.3–86.4% against the paper's 85.0–85.4%,
and is near-identical across policies exactly as the paper reports. Absolute waiting times
run 12–25% above the paper's — see [§9](#9-how-faithful-is-the-replication).

**WP2 — the c·μ rule wins on its own objective, and on the raw one too.** WSEPT attains
the lowest c-weighted holding cost (0.3763 against IFP's 0.7550, a 50% reduction) and also
the lowest unweighted mean wait (42.32 min). Every pairwise difference against the paper's
three heuristics is significant after Bonferroni correction. Its ranking does not flip
anywhere in the `T_follow` sweep from 15 to 120 min.

**WP3 — Nelder-Mead is ~19× cheaper than brute force, for the same answer.**

| | lattice points | week-long simulations | optimum |
|---|---|---|---|
| Grid search (paper's method) | 2 332 | **50 415** | (4.10, 8.20) |
| Nelder-Mead, single start | 53 | **2 650** | (2.31, 8.37) |
| Nelder-Mead, 4 starts | 196 | 9 800 | (2.31, 8.37) |

Scored on one identical full-length batch, the two optima differ by **0.006 min**. All four
starts converge to the same objective, and our hand-written simplex agrees with
`scipy.optimize` to 0.0000 min.

**WP4 — the cost-minimising roster is (6, 6, 3), not the paper's (5, 5, 3).** With
`(k1, k2)` re-tuned to (12.20, 23.40) inside it, weekly cost falls **20.7%** (139 391 →
110 513 cost units): +105 physician-hours buys back 33 min of mean waiting per patient and
eliminates the SLA penalty. The winner shifts to (5, 6, 3) or (6, 6, 4) under other cost
weightings, which is itself the finding — the right staffing level depends on how the
hospital prices waiting against salary.

**WP5 — CRN removes 98.95% of the variance of the pairwise differences.** Median efficiency
gain **95.8×**; policy-to-policy correlations rise from ≈0 to +0.996…+0.9997. Under
independent streams several comparisons are *not* significant at the Bonferroni threshold
that CRN resolves decisively.

**Final verdict — "best" depends on the objective, and only two policies are adoptable.**

| Lens | Winner |
|---|---|
| shortest unweighted mean wait | `WSEPT` (42.32 min) |
| lowest c-weighted holding cost | `WSEPT` (0.3763) |
| fastest policy that meets SL ≥ 95% on both levels | `SBP*` (44.18 min) |

Only `IFP` and `SBP*` (our re-tuned Slack-Based Policy) satisfy the service-level
constraint on our system. The paper's published thresholds (13.1, 2.1) reach only 89.4% on
Level IV — see [§9](#9-how-faithful-is-the-replication) for why.

---

## 9. How faithful is the replication?

Run `python scripts/run_01_validate_paper.py` and read STEP 5. The short version:

**Reproduced closely** — the diagnostic-equipment table (all four modalities within ~0.5
percentage points of the paper's Table 9), the physician utilisation band, the near-identical
utilisation across policies, ALT's Level III waiting time, SBP's Level III waiting time, the
Level IV service-level collapse under ALT, and every finding of the Sec 3.4 sensitivity
analysis.

**Systematically higher** — the absolute waiting times, by roughly 10–25%. The published
arrival table, service-time distributions and staffing levels together imply an analytic
offered load of **ρ ≈ 0.87**, and at that load the mean wait is extremely sensitive to the
last percentage point of utilisation. Since the underlying dataset is not public, an exact
numeric match is not attainable and we do not claim one. What is reproduced is the
*structure* of every result.

**One ranking difference, and it is informative.** On our rebuild, the paper's tuned
thresholds `(k1, k2) = (13.1, 2.1)` **violate** the Level IV service-level constraint
(≈88% against a 95% target), because `k2 = 2.1` means a Level IV patient only becomes
urgent after waiting 117.9 of their 120 available minutes — a safety valve that works on
the paper's less congested system but not on ours. Re-tuning under the constraint (WP3)
moves the optimum to a much larger `k2` and produces the fastest policy that a hospital
could actually adopt. That is the case for re-tuning rather than copying published
parameters, and it is the central finding of the extension.

---

## 10. Reading the terminal output

Every script prints in the same shape:

```
================================================================================
  WP1 -- REPLICATION AND VALIDATION OF THE BASE PAPER
  run_01_validate_paper.py  |  Lv et al. (2026), Healthcare 14(1):99
================================================================================

Run settings
--------------------
  replications per policy                100
  ...

STEP 1  Model parameterisation and analytic load
    ...
  [OK]  a check that passed
  [!!]  a check that needs attention
  saved -> results/tables/wp1_paper_comparison.csv
```

`[OK]` / `[!!]` lines are automated assertions about the results, evaluated live — they are
not decoration. If a structural finding of the paper fails to reproduce, the script says so
rather than staying silent.

---

## 11. Project layout

```
edsim/
├── README.md                  ← this file
├── requirements.txt
├── docs/PROJECT_GUIDE.pdf     ← the illustrated guide (generated)
├── src/                       ← the library (14 modules, ~4000 lines)
├── scripts/                   ← 9 runnable experiments + the orchestrator
├── tests/test_model.py        ← 33 correctness checks
└── results/                   ← everything the scripts produce  (~7 850 lines of Python in all)
    ├── PROVENANCE.md
    ├── RESULTS_SUMMARY.md
    ├── tables/  figures/  raw/
```

## 12. References

1. Lv, W.; Liu, R.; Yan, F.; Wang, Y. *Discrete Event Simulation-Based Analysis and
   Optimization of Emergency Patient Scheduling Strategies.* Healthcare **2026**, 14, 99.
2. Cox, D.R.; Smith, W.L. *Queues.* Methuen, 1961. — the c·μ rule.
3. Buyukkoc, C.; Varaiya, P.; Walrand, J. *The cμ rule revisited.* Adv. Appl. Prob. **1985**, 17, 237–238.
4. Van Mieghem, J.A. *Dynamic scheduling with convex delay costs: the generalized cμ rule.*
   Ann. Appl. Prob. **1995**, 5, 809–833.
5. Mandelbaum, A.; Stolyar, A.L. *Scheduling flexible servers with convex delay costs.*
   Oper. Res. **2004**, 52, 836–855.
6. Nelder, J.A.; Mead, R. *A simplex method for function minimization.* Comput. J. **1965**, 7, 308–313.
7. Lewis, P.A.W.; Shedler, G.S. *Simulation of nonhomogeneous Poisson processes by thinning.*
   Naval Res. Logist. Q. **1979**, 26, 403–413.
8. Law, A.M. *Simulation Modeling and Analysis*, 5th ed. McGraw-Hill, 2015. — common random numbers.
