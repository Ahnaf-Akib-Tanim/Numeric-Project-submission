# Traceability: base paper → code

Every equation, table and figure of

> Lv, W.; Liu, R.; Yan, F.; Wang, Y. (2026). *Discrete Event Simulation-Based Analysis and
> Optimization of Emergency Patient Scheduling Strategies.* Healthcare **14**(1), 99.

mapped to the exact place it is implemented, and to the script that reproduces it.

---

## 1. Architecture (paper Figure 2)

The paper's five-module architecture is preserved one-to-one, so the code can be read
alongside the paper.

| Paper module | Our file |
|---|---|
| Entity Definition Module | [`src/entities.py`](../src/entities.py) |
| Event Scheduling Module | [`src/engine.py`](../src/engine.py) |
| Resource Scheduling Module | [`src/resources.py`](../src/resources.py) |
| Strategy Execution Module | [`src/policies.py`](../src/policies.py) |
| Statistical Output Module | [`src/metrics.py`](../src/metrics.py) |

---

## 2. Equations

| Eq. | Meaning | Implemented in | Notes |
|---|---|---|---|
| (1) | `d = ⌊t/1440⌋ mod 7`, `h = ⌊(t mod 1440)/60⌋` | `rng.rate_at()` | verified by `test_rate_at_indexing` |
| (2) | `N_{d,h} ~ Poisson(λ_{d,h})` | `rng.thinned_arrival_times()` | realised as a non-homogeneous Poisson **process** by Lewis–Shedler thinning, which gives the Poisson hourly counts of Eq. (2) as a consequence; verified by `test_thinning_reproduces_table2` |
| (3) | `x_{i,j} ∈ {0,1}` — does patient *i* need exam *j* | `rng.generate_patient_stream()` | independent Bernoulli draws at `p_j`, conditioned on ≥1 exam |
| (4) | `t_i^exam = max_k (t^start + τ_k + δ_k + ρ_k)`, exams sequential | `engine._start_exam()`, `engine._on_device_free()` | the `ρ_j` term arises from the FIFO device queue in `resources.Device`; verified by `test_exam_chain_follows_equation_4` |
| (5)–(7) | demand states `D_init,3`, `D_init,4`, `D_follow` | `engine.Simulation.q3 / q4 / qf` | the deques *are* the demand state; new arrivals are appended before dispatch, so `D = W + |A|` holds by construction |
| (8)–(10) | Initial-First allocation `N_init,3`, `N_init,4`, `N_follow` | `policies.InitialFirstPolicy.allocate()` | |
| (11)–(13) | Alternating 1:1 allocation, cap `⌊R/2⌋` on initial work | `policies.AlternatingPolicy.allocate()` | interpreted as a cap on *concurrent* initial consultations — see §5 below |
| (14) | urgency test `w_i(t) ≥ T_ℓ − k_ℓ` | `policies.SlackBasedPolicy._urgent_prefix()` | |
| (15) | urgent sets `U_3(k1)`, `U_4(k2)` | same | found as a queue *prefix*, since the deques are arrival-ordered |
| (16) | priority `U_3 > U_4 > F > H_init` | `policies.SlackBasedPolicy.allocate()` | |
| (17)–(20) | counts `n_3`, `n_4`, `n_f`, `n_r` | same | |
| (21)–(23) | queue carry-over `W^{t+1} = W^t + D^t − n` | `engine._dispatch()` | the deques carry over automatically; the equations are the bookkeeping identity our data structure enforces |
| (24)–(26) | mean waiting times | `metrics.collect()` → `wait_init_l3`, `wait_init_l4`, `wait_follow`, `wait_per_consult` | see §4 for the reading decision |
| (27) | overtime ratio `Δ_ℓ` | `metrics.collect()` → `delay_rate_l3/l4` | computed on the **initial-consultation** wait |
| (28) | service level `SL_ℓ = 1 − Δ_ℓ` | `metrics.collect()` → `sl_l3`, `sl_l4` | |
| (29) | physician utilisation `U_doc` | `resources.PhysicianPool.utilisation` | computed as a proper **time integral** of busy(t)/R(t), matching the paper's own words "ratio of busy time to total available time" |
| (30) | device utilisation `U_j` | `resources.Device.utilisation()` | busy device-minutes / available device-minutes |
| (31) | `min W_total(k1,k2)` | `optimizers.SimulationObjective` | |
| (32) | `SL_ℓ ≥ SL_ℓ^min` | `optimizers.SimulationObjective.penalty()` | enforced by an exterior penalty; the numeric `SL_min` is our choice (0.95) since the paper never prints it |

---

## 3. Tables and figures

| Paper item | Content | Reproduced by | Our output |
|---|---|---|---|
| Table 1 | notation | — | mirrored in the docstrings and field names |
| **Table 2** | hourly arrival rates λ_{d,h} | `config.ARRIVAL_RATES` (verbatim, transposed to `[day][hour]`) | `run_01` STEP 2 → `figures/wp1_arrival_validation` |
| **Table 3** | top-5 coarse grid results | `run_02_grid_search.py` stage 1 | `tables/wp2_grid_coarse_top5` |
| **Table 4** | top-5 fine grid results | `run_02_grid_search.py` stage 2 | `tables/wp2_grid_fine_top5` |
| **Table 5** | paired t-tests | `run_01` STEP 6 | `tables/wp1_significance` (our values printed beside the paper's) |
| **Table 6** | Cohen's d | `run_01` STEP 6 | same table |
| **Table 7** | delay rate / service level | `run_01` STEP 5 | `tables/wp1_paper_comparison` |
| **Table 8** | physician utilisation | `run_01` STEP 5 | same table |
| **Table 9** | equipment utilisation | `run_01` STEP 7 | `tables/wp1_equipment_utilisation` |
| **Table 10** | seven staffing scenarios S0–S6 | `config.STAFFING_SCENARIOS` | `run_05` stage C2, `run_07` §3.4.2 |
| Figure 1 | ED flowchart | the pathway in `engine.py` | `figures/demo_week_trace` shows it running |
| Figure 2 | module architecture | the `src/` layout | §1 above |
| **Figure 3** | waiting-time box plot | `run_01` STEP 8 | `figures/wp1_waiting_boxplot` (with the paper's means overlaid as dashed reference lines) |
| **Figure 4** | arrival-rate sensitivity | `run_07` §3.4.1 | `figures/sens_arrival_rate` |
| **Figure 5** | staffing sensitivity | `run_07` §3.4.2 | `figures/sens_staffing` |
| Sec 3.4.3 | lognormal robustness | `run_07` §3.4.3 | `tables/sens_service_distribution`, `figures/sens_lognormal_bars` |

---

## 4. The one substantive reading decision

The paper's Eqs. (24)–(26) define averages over *consultations*, but the numbers it reports
are only consistent with per-**patient** totals. Two facts force this:

1. **The weighted identity.** For SBP the paper gives Level III = 10.48, Level IV = 43.89,
   all patients = 35.25, and `0.25·10.48 + 0.75·43.89 = 35.54 ≈ 35.25`. The same holds for
   IFP and ALT. So the headline is the triage-weighted mean of the per-level figures.
2. **The service level rules out "initial wait only".** Under IFP the paper reports a Level
   III waiting time of 44.14 min *and* a 100% Level III service level against a 30-minute
   target. Both cannot be true of the same quantity. Under IFP, Level III initial
   consultations have absolute priority, so their initial wait is a couple of minutes — the
   44 min must include the follow-up wait, which IFP starves.

We therefore report `W_ℓ` = mean over Level-ℓ patients of (initial wait + follow-up wait),
and compute the per-consultation quantities of Eqs. (24)–(26) alongside so both readings are
available. The service level uses the initial wait only, which is the only reading under
which IFP's 100% is attainable. All of this is documented at the top of
[`src/metrics.py`](../src/metrics.py).

---

## 5. Places where the paper is ambiguous, and what we did

| Ambiguity | Our resolution | Why |
|---|---|---|
| Is `R^t` in Eqs. (8)–(23) the *free* physicians or the *whole* roster? | Free physicians for IFP and SBP (pure priority orders, where the two readings coincide); the **whole roster** for ALT's `⌊R/2⌋` cap | With event-driven dispatch a physician usually frees up one at a time, so `⌊R_free/2⌋ = 0` would silently turn ALT into "follow-ups always first" — a different policy. Capping *concurrent* initial consultations at `⌊R_roster/2⌋` is the reading that actually implements a 1:1 split, and it reproduces the paper's ALT Level III waiting time (6.82 min published, ~6.2 min ours). |
| Device capacity `C_j` | 1 per modality | Table 9 lists "Available Time = 10 080 min" per device for a one-week run — exactly one device-week. |
| Truncated-exponential parameterisation | `λ_k = 1/mean`, i.e. the *pre*-truncation mean is 9 / 15 min | A truncated exponential on [5, 25] cannot have mean 15 (its supremum is 15, attained only as λ→0). With `λ = 1/15` the realised mean is 12.84 min, and the resulting offered load ρ ≈ 0.87 matches the paper's ~85% utilisation. |
| Tie-break between equal-priority patients | earliest arrival | The paper states this in Sec 2.2.3; our FIFO deques enforce it structurally. |
| Service interruption at shift change | never | "Once a physician begins service, the service process will not be interrupted" (after Eq. 10). A shrinking shift blocks new starts until the busy count falls back below the roster; verified by `test_non_preemptive_capacity_drop`. |
| Exam ordering when report delays tie (X-ray and CT are both 30 min) | by modality index | Deterministic, so runs are reproducible; the paper only specifies descending delay. |
| "60% require **at least one** test" vs. independent per-modality probabilities | resample so "at least one" holds exactly | The independent draws select nothing with probability 1.99%. Switchable via `SimConfig.exam_require_at_least_one`. |

---

## 6. What we added that is not in the paper

| Addition | Where | Work package |
|---|---|---|
| c·μ rule / WSEPT policy | `policies.CMuPolicy(mode="static")` | WP2 |
| Generalised c·μ rule (convex delay costs) | `policies.CMuPolicy(mode="gcmu")` | WP2 |
| c-weighted holding cost metric | `metrics.RunResult.holding_cost` | WP2 |
| Hand-written Nelder-Mead simplex | `optimizers.nelder_mead()` | WP3 |
| Exterior penalty for the SL constraint | `optimizers.SimulationObjective.penalty()` | WP3 |
| Multi-start local-minimum check | `optimizers.multistart_nelder_mead()` | WP3 |
| Simulation-budget accounting | `optimizers.EvalRecord`, `run_04` STEP 4 | WP3 |
| Weekly cost model `C(R,k1,k2)` | `staffing.cost_of()` | WP4 |
| Integer roster search with inner re-tuning | `run_05_staffing_cost.py` | WP4 |
| Cost-weight stress test | `run_05` stage D | WP4 |
| Exact common random numbers | `rng.generate_patient_stream()` + `rng.replication_seed()` | WP5 |
| Variance-reduction quantification | `stats.crn_efficiency()` | WP5 |
| Replications-needed calculation | `stats.reps_for_halfwidth()` | WP5 |
| Provenance logging for every artefact | `report.Artifact` | — |
| 33-check verification suite | `tests/test_model.py` | — |
