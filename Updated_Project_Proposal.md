# Simulating and Optimizing Patient Flow using Discrete Event Simulation
### Numerical Analysis, Simulation and Modeling Sessional

Sudip Kumar Saha (2105152) · Ahnaf Akib Tanim (2105154) · Md. Shahjalal Rumman (2105165)
Md. Dulal Hossain (2105169) · Md. Shoaib Hossain (2105170) — Section C

---

## 1. Base Paper

**Lv, Liu, Yan & Wang (2025), "Discrete Event Simulation-Based Analysis and Optimization of
Emergency Patient Scheduling Strategies," *Healthcare* 14(1):99.**

- Builds a DES model of a Chinese tertiary-hospital ED (Level III/IV patients only).
- Compares three physician-scheduling policies: Initial-First (IFP), Alternating 1:1 (ALT),
  and a Slack-Based Policy (SBP) with two tunable urgency thresholds k1, k2.
- Tunes (k1, k2) with a two-stage **brute-force grid search** (coarse step 1.0, then fine step 0.1).
- Finds SBP (k1=13.1, k2=2.1) cuts mean wait time from 46.26 min (IFP) to 35.25 min, a 23.8%
  improvement, with 0% service-level violations.
- Validates statistical significance with paired t-tests, Bonferroni correction, Cohen's d.
- Parameterizes the model from hospital records that are **not public** — only summary
  statistics (hourly arrival rates, service-time distributions, exam probabilities, staffing
  levels) are given in the paper, which is sufficient to rebuild an equivalent simulator.

## 2. Gap in the Base Paper

| Base paper does | Base paper does NOT do |
|---|---|
| Grid search over (k1, k2) only | Optimize physician **staffing levels** jointly with thresholds |
| Compares 3 heuristic policies | Compare against a theoretically optimal scheduling rule from queueing theory |
| Brute-force search (hundreds of full simulation runs) | A derivative-free numerical optimization method (root-finding/optimization) |
| 100 independent replications, no variance reduction | Common random numbers to sharpen comparisons |

This is where our project adds genuine, gradable novelty rather than re-running the paper's code.

## 3. Our Contribution — Five Work Packages (one per team member)

### WP1 — Baseline DES Engine & Replication (Ahnaf)
Rebuild the simulator from scratch in Python, following the paper's five-module architecture
(Entity Definition, Event Scheduling, Resource Scheduling, Strategy Execution, Statistical
Output — Fig. 2 of the paper):
- Non-homogeneous Poisson arrivals via **thinning algorithm** using Table 2's hourly rates.
- Truncated-exponential service times (initial consult, follow-up) via inverse-CDF sampling.
- Implement IFP, ALT, SBP exactly as specified (Eqs. 8–23 of the paper).
- Run 100 replications and reproduce the paper's headline numbers (46.26 / 37.88 / 35.25 min)
  within statistical tolerance. This validation is itself a concrete, checkable deliverable and
  the foundation every other work package builds on.

### WP2 — Theoretically-Grounded Scheduling Rule (Shoaib)
Add a **fourth** scheduling policy grounded in classical queueing theory instead of a heuristic:
implement the **cμ-rule / Weighted Shortest Expected Processing Time (WSEPT)** — at each decision
epoch, serve the waiting class maximizing `c_l · μ_l`, where `μ_l = 1/E[service time]` and `c_l`
is a delay-cost weight derived from the target wait time `T_l` (e.g. `c_l = 1/T_l`). This rule is
provably optimal for minimizing linear holding costs in multi-class queues — a genuinely
different mechanism from the paper's fixed-lookahead slack rule — and slots directly into the
comparison table alongside IFP/ALT/SBP.

### WP3 — Numerical Optimizer vs. Grid Search (Rumman)
Replace the paper's brute-force grid search with a hand-implemented **Nelder-Mead simplex
optimizer** (directly tying the project to the course's optimization content) to jointly tune
(k1, k2). Handle the service-level constraint (`SL_ℓ ≥ SL_min`) with a **penalty-function**
method, since Nelder-Mead is unconstrained. Benchmark the *number of simulation evaluations
needed to converge* against the paper's grid search (which needed hundreds of full 100-replication
runs) — a concrete efficiency number for the report, not just an assertion.

### WP4 — Cost-Based Staffing Optimization (Sudip)
Directly answers the "right staffing level" question the base paper only touches via sensitivity
analysis. Define an economic objective `C(R, k1, k2) = α·(physician-hours) + β·(total patient
wait-minutes) + γ·(SLA violation penalty)`, with α, β, γ set from reasonable healthcare cost
assumptions (stated and justified in the report). For each candidate staffing vector
`R = (R_morning, R_afternoon, R_night)` in a small integer search space (e.g. 2–8
physicians/shift), reuse WP3's optimizer to find the best (k1, k2), then compare total cost `C`
across staffing levels. Deliverable: a staffing recommendation showing the cost-minimizing
physician count per shift vs. the paper's fixed 5/5/3.

### WP5 — Statistical Rigor & Final Comparison (Dulal)
Implement **Common Random Numbers (CRN)**: reuse identical arrival-time and service-time random
streams across all four policies within each replication, then re-run the paper's paired t-test /
Cohen's d analysis and show the narrower confidence intervals / fewer replications needed to
detect significance — a real variance-reduction result. Consolidate all final results (WP1–WP4)
into the paper's exact metrics (mean wait time, service level, utilization, Cohen's d) for one
clean comparison table across all four policies.

## 4. Tools

Python 3.x, `heapq`/priority-queue based custom DES engine (matches the base paper's approach —
no black-box library like SimPy, so every mechanism is transparent and gradable), NumPy/SciPy
(`scipy.optimize` may be used only as a cross-check baseline, not as the primary implementation —
Nelder-Mead should be hand-implemented since this is a numerical methods course),
Matplotlib for figures, pandas for result aggregation.

## 5. Timeline (12-week sessional)

| Week | Milestone |
|---|---|
| 1–2 | Paper deep-dive, environment/repo setup, finalize this proposal |
| 3–5 | WP1: build + validate baseline engine against paper's published numbers |
| 6–7 | WP2 and WP3 in parallel (both depend only on WP1's engine) |
| 8 | WP4 (depends on WP3's optimizer) |
| 9 | WP5 (depends on WP1's engine; runs alongside WP4) |
| 10 | Integration: full 4-policy comparative experiments |
| 11 | Report writing, figures, tables |
| 12 | Buffer + presentation prep |

## 6. Expected Deliverables

1. Validated open, from-scratch DES simulator reproducing the base paper's results.
2. A theoretically-grounded 4th scheduling policy (cμ/WSEPT) added to the comparison.
3. A hand-implemented Nelder-Mead optimizer with penalty constraints, benchmarked for
   efficiency against the paper's brute-force grid search.
4. A cost-based optimal staffing model answering "how many physicians per shift," not just
   sensitivity to it.
5. A variance-reduction (CRN) study sharpening the paper's statistical comparisons.
6. Final report + slides with a clear "paper vs. our extension" comparison throughout.
