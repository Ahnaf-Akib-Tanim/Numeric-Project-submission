# Numerical methods used in this project

This is a numerical-methods course project, so the numerical machinery is written out here
in full rather than being left implicit in the code. Every method below is **implemented
from scratch**; SciPy appears only for distribution quantiles, the t-distribution, and as a
deliberate cross-check of our own optimiser.

---

## 1. Sampling a non-homogeneous Poisson process — Lewis–Shedler thinning

**Problem.** Patients arrive with an intensity `λ(t)` that changes every hour and repeats
weekly (paper Table 2). Inverting the cumulative intensity `Λ(t) = ∫₀ᵗ λ(s) ds` is possible
here but fiddly and error-prone with 168 pieces; thinning needs no inversion at all.

**Method.** Pick a dominating constant `λ* ≥ max_t λ(t)` — here `λ* = 23.05/60` patients per
minute, Monday 20:00–21:00. Then:

1. Generate a homogeneous Poisson process of rate `λ*` by summing `Exp(1/λ*)` gaps.
2. Accept each candidate epoch `t` with probability `λ(t)/λ*`; reject otherwise.

The accepted epochs are distributed **exactly** as the NHPP with intensity `λ(t)`.

**Why it is exact.** In `[t, t+dt)` the candidate process produces a point with probability
`λ* dt`, and it survives with probability `λ(t)/λ*`; the product is `λ(t) dt`, which is the
defining property of the target process. Independence across disjoint intervals is inherited
from the dominating process.

**Cost.** Acceptance rate is `E[λ]/λ* ≈ 13.3/23.05 ≈ 58%`, so about 1.7 candidate draws per
accepted arrival — cheap, and no inversion table to get wrong.

**Implementation.** `src/rng.py::thinned_arrival_times`. Candidates are drawn in vectorised
blocks rather than one at a time. **Verified** by `test_thinning_reproduces_table2`, which
samples 120 weeks and checks the realised hourly means against Table 2 (relative L¹ error
< 3%, correlation > 0.995), and visually by `figures/wp1_arrival_validation`.

---

## 2. Sampling truncated distributions — inverse-CDF (inverse-transform)

**Problem.** Consultation times are `TruncExp(λ_k, [a_k, b_k])`. Rejection sampling would
work but consumes a variable number of uniforms per variate, which would destroy the
synchronisation that common random numbers depend on (§5).

**Method.** For `X ~ Exp(λ)` conditioned on `a ≤ X ≤ b`,

```
F(x) = (e^{-λa} − e^{-λx}) / (e^{-λa} − e^{-λb}),    a ≤ x ≤ b
```

Setting `F(x) = u` and solving,

```
x = −(1/λ) · ln( e^{-λa} − u·(e^{-λa} − e^{-λb}) )
```

**Exactly one uniform per variate**, always.

**Closed-form mean** (needed by the c·μ rule for `μ_ℓ = 1/E[S_ℓ]`, and by the offered-load
check):

```
E[X] = a + 1/λ − (b−a)·e^{−λ(b−a)} / (1 − e^{−λ(b−a)})
```

With the paper's parameters this gives

| consultation | λ | bounds | nominal mean | **realised mean** |
|---|---|---|---|---|
| initial | 1/9 | [5, 15] | 9 | **9.0926** |
| follow-up | 1/15 | [5, 25] | 15 | **12.8410** |

The follow-up figure matters: a truncated exponential on [5, 25] **cannot** have mean 15
(15 is the supremum, attained only as λ→0), so `λ = 1/15` is the only consistent reading of
the paper. The resulting offered load ρ ≈ 0.87 is what reproduces the paper's ~85%
utilisation.

**Truncated lognormal** (robustness study, paper Sec 3.4.3) uses the same construction with
the normal CDF/quantile, and the normal quantile is Acklam's rational approximation
(relative error < 1.15 × 10⁻⁹) so the inner sampling loop stays free of SciPy calls.

**Implementation.** `src/distributions.py`. **Verified** by
`test_truncexp_bounds_and_monotonicity`, `test_truncexp_mean_matches_sampling` (200 000
draws against the closed form), `test_normal_ppf_accuracy` and `test_trunclognormal_bounds`.

---

## 3. Discrete-event simulation — a priority-queue event loop

**Method.** The state advances only at *events*, held in a min-heap (`heapq`) keyed by
`(time, event_type, sequence)`:

```
while the future-event list is non-empty:
    pop the earliest event
    if its time ≥ horizon: stop
    advance the clock, accrue the utilisation integrals
    apply the event's state transition
    call dispatch(now)          ← the single point where the policy acts
```

Five event types: `SHIFT_CHANGE`, `ARRIVAL`, `CONSULT_END`, `EXAM_DEVICE_FREE`,
`EXAM_RESULTS_READY`. The `event_type` field breaks time ties deterministically (a shift
change is visible to any dispatch at that instant), and the monotone `sequence` counter
makes the ordering total — so a replication is reproducible bit-for-bit.

**A performance note worth recording.** Events were first a `@dataclass(order=True)`.
Profiling showed Python-level `__lt__` calls were **22% of total runtime**, because `heapq`
compares on every sift. Replacing the dataclass with a plain 4-tuple moved the comparison
into C and cut per-replication time from ~0.20 s to ~0.076 s. That 2.6× is what makes the
50 000-simulation grid search of WP3 affordable at all.

**Implementation.** `src/engine.py`. **Verified** by `test_engine_conserves_patients`,
`test_never_more_busy_than_rostered_when_starting`,
`test_no_idle_physician_while_a_patient_waits` (work conservation, for every policy) and
`test_two_runs_of_the_same_input_are_identical`.

---

## 4. Optimisation of a stochastic function

### 4.1 Making the objective deterministic — Sample Average Approximation

A simulation objective is random: evaluating `F(k1, k2)` twice gives two different numbers.
Simplex methods stall or wander on such a surface, because they cannot tell a genuine
improvement from noise.

We therefore minimise the **sample average** over a *fixed* set of `n` patient streams:

```
F̂(k1,k2) = (1/n) Σ_{r=1..n} F(k1, k2 ; stream_r) + μ · Σ_ℓ max(0, SL_ℓ^min − SL_ℓ)
```

Because the streams are fixed and the engine is deterministic given a stream, `F̂` is a
genuine deterministic function — evaluating the same point twice returns the *identical*
value. This is also common random numbers applied to optimisation: seed noise is common to
all candidates and cancels when they are compared, which makes the surface far smoother than
the pointwise noise level would suggest.

### 4.2 Exterior penalty for the service-level constraint

The paper's problem (Eqs. 31–32) is constrained; Nelder-Mead is not. We use an exterior
penalty:

```
F(k1,k2) = W_total  +  μ · Σ_ℓ max(0, SL_ℓ^min − SL_ℓ)
```

with `μ = 500` minutes per unit of service-level shortfall — i.e. one percentage point of
SLA shortfall costs as much as five extra minutes of average waiting. Large enough that an
infeasible point is never optimal; small enough that the penalised surface stays smooth
near the boundary rather than becoming a cliff the simplex bounces off.

Box bounds (`k ≥ 0`) are handled by **projection** — each trial vertex is clipped back into
the box — rather than by a second penalty, so the simplex can slide *along* a bound instead
of being pushed away from it.

### 4.3 The Nelder-Mead downhill simplex, written out

For `n` variables the simplex has `n+1` vertices. Each iteration:

1. **Order** the vertices so `f(x₁) ≤ … ≤ f(x_{n+1})`.
2. **Stop** if the simplex span is below `xtol` in every coordinate *and* the spread of
   vertex values is below `ftol`.
3. **Centroid** `x_c` of all vertices except the worst.
4. **Reflect**: `x_r = x_c + α(x_c − x_{n+1})`, `α = 1`.
   - If `f(x_r) < f(x₁)`: **expand** `x_e = x_c + γ(x_r − x_c)`, `γ = 2`; keep whichever of
     `x_e`, `x_r` is better.
   - Else if `f(x_r) < f(x_n)`: accept `x_r`.
   - Else **contract** (outside if `f(x_r) < f(x_{n+1})`, inside otherwise) with `ρ = 0.5`;
     accept if it improves.
   - Else **shrink** every vertex toward the best: `x_i ← x₁ + σ(x_i − x₁)`, `σ = 0.5`.

**Per-dimension initial step.** The initial simplex is `x₀` plus one step along each
coordinate axis. `k1` lives on ~[0, 30] (against `T₃ = 30`) and `k2` on ~[0, 120] (against
`T₄ = 120`), so we use the vector step `(4, 15)`; a single scalar step would produce a badly
conditioned initial simplex and waste iterations just re-scaling itself.

**Multi-start.** Nelder-Mead converges to a *local* minimum. Four dispersed starts are run;
if they all reach the same objective value, the box is effectively unimodal, and if they do
not, that is itself reported.

**Implementation.** `src/optimizers.py::nelder_mead`. **Verified** by
`test_nelder_mead_on_rosenbrock` (the standard hard test function, solved to `|x − (1,1)| <
10⁻³`), `test_nelder_mead_respects_bounds`, and `test_nelder_mead_matches_scipy` (agrees
with `scipy.optimize.minimize` to `10⁻⁶` on a common objective).

### 4.4 The benchmark against brute force

Both methods minimise the identical objective on the identical streams, and the budget is
counted in **week-long simulations** — not seconds — so the comparison does not depend on
the machine or the level of parallelism.

One subtlety the script handles explicitly: the grid and the simplex use different
replication counts per point, so their raw objective values are estimates of the same
quantity with different precision and are **not** directly comparable. `run_04` therefore
re-scores both optima on one identical full-length batch before declaring a winner.

---

## 5. Variance reduction — Common Random Numbers

**The identity.** For any two policies A and B,

```
Var(A − B) = Var(A) + Var(B) − 2·Cov(A, B)
```

With independent streams `Cov = 0`. Under CRN both policies face the *same* simulated week,
so a heavy week inflates both together, `Cov` becomes strongly positive, and the variance of
the **difference** collapses — while the variance of each individual estimator is untouched.
CRN sharpens *comparisons*, not individual estimates.

**Getting it exact.** The usual failure mode is loss of synchronisation: once two policies
make different decisions they consume random numbers in a different order, and patient #1723
ends up with different service times in the two runs. We avoid this structurally:

- every random attribute is drawn from **six independent substreams** (arrivals, levels,
  initial service, follow-up service, exam need, exam selection), so a change in how many
  draws one dimension makes cannot shift another;
- the **entire** exogenous stream is materialised *before* the run starts, so the engine
  draws no random numbers at all;
- each variate consumes **exactly one uniform** (§2), so no variate can desynchronise the
  stream.

The result is bit-identical patients across policies, and measured correlations of ≈ +0.996
to +0.9997 between policies' per-replication means.

**What is reported.** `src/stats.py::crn_efficiency` computes, per pair:

- variance of the difference under both schemes, and the fraction removed;
- the efficiency gain `Var_ind / Var_CRN` — which, because CI half-width scales as `1/√n`,
  is exactly the factor by which the replication count could be reduced at equal precision;
- 95% confidence intervals on the difference under both schemes;
- `reps_for_halfwidth()`: the smallest `n` with `t_{0.975, n−1}·sd/√n ≤ h`, solved by
  iteration because the t-quantile itself depends on `n`.

**Verified** by `test_crn_actually_reduces_variance_of_the_difference`, which asserts a
≥ 5× variance reduction directly.

---

## 6. Statistical inference

**Paired t-test.** With `d_r = a_r − b_r` over `n` replications,
`t = mean(d) / (sd(d)/√n)` on `n−1` degrees of freedom. Paired because CRN makes the design
paired; using an unpaired test would throw away exactly the variance reduction CRN bought.
**Verified** against `scipy.stats.ttest_rel` to `10⁻¹²`.

**Bonferroni correction.** With `m` pairwise comparisons in the family, each is tested at
`α/m`. The paper uses `0.05/3 = 0.0167`; our final comparison has six policies, hence 15
comparisons and `α_adj = 0.00333`.

**Cohen's d, paired form:** `d = mean(differences) / sd(differences)`. This is the effect
size that matches a paired design. It is *larger* than the unpaired pooled-SD version by
construction, precisely because CRN shrinks `sd(d)` — so the paired `d` should be read as
"how reliably does A beat B on the same week?", not as "how far apart are the two
distributions?".

**Confidence intervals** use the Student-t interval throughout; `n ≥ 30` replications keeps
the normal approximation to the replication means comfortable.

**Implementation.** `src/stats.py`.

---

## 7. Cost model and integer search (WP4)

**Objective.**

```
C(R, k1, k2) = α · (physician-hours per week)
             + β · (total patient waiting-minutes per week)
             + γ · (SLA violations per week)
```

All three terms are per simulated week, so they are directly comparable. `R` is the integer
roster `(R_morning, R_afternoon, R_night)`.

**Why a two-stage search.** The box `2..8` on three shifts is `7³ = 343` rosters; excluding
those that staff the quiet night above the busy day leaves 140. Running a full Nelder-Mead
re-tune inside each would cost ~10⁶ simulations for no benefit, since most rosters are
either unstable or plainly over-staffed. So:

- **Stage A (screen).** Every roster once, cheaply, at the incumbent thresholds. Rosters
  where more than 15% of the week's patients are still in the system at the horizon are
  marked **unstable** and dropped — their queues are growing, not clearing, so their mean
  waiting time is meaningless.
- **Stage B (refine).** The best few get a full Nelder-Mead re-tune of `(k1, k2)`.

This is a *joint* optimisation, not a staffing sweep: the best thresholds for a 3-doctor
night shift are not the best thresholds for a 5-doctor one, so holding them fixed while
varying staff would compare rosters at handicapped settings.

**Unstable rosters return a large finite penalty**, not `inf`, so the simplex still has a
usable descent direction to escape along.

**Stress test.** The recommendation is re-priced under four alternative weightings
(waiting valued 4× and ¼×, physicians 1.5× dearer, SLA breaches 10× dearer). If the winner
changes, that is reported as the finding — the right staffing level genuinely depends on how
the hospital prices waiting against salary.

**Implementation.** `src/staffing.py`, `scripts/run_05_staffing_cost.py`.

---

## 8. The c·μ rule and its generalisation (WP2)

**Classical c·μ rule** (Cox & Smith 1961; Buyukkoc, Varaiya & Walrand 1985). For a
multi-class queue served by one pool with **linear** holding costs `c_ℓ` per unit waiting
time, the policy minimising expected total holding cost always serves the non-empty class
with the largest index

```
index_ℓ = c_ℓ · μ_ℓ ,        μ_ℓ = 1 / E[service time of class ℓ]
```

Setting `c_ℓ = 1/T_ℓ` — "a minute of waiting hurts in inverse proportion to how much waiting
that class can tolerate" — turns the triage targets directly into holding costs. With the
paper's numbers:

| class | `T_ℓ` | `E[S_ℓ]` | `μ_ℓ` | `c_ℓ·μ_ℓ` |
|---|---|---|---|---|
| Level III initial | 30 | 9.093 | 0.10998 | 0.003666 |
| Level IV initial | 120 | 9.093 | 0.10998 | 0.000917 |
| Follow-up | 60 | 12.841 | 0.07788 | 0.001298 |

Note what this says: the indices are **constants**, so the classical rule degenerates to a
fixed priority order — Level III initial > follow-up > Level IV initial. That is a genuine
property of the rule, not an implementation shortcut, and it is exactly what the generalised
version fixes.

**Generalised c·μ** (Van Mieghem 1995; Mandelbaum & Stolyar 2004). For **convex** delay
costs `C_ℓ(w)` the asymptotically optimal index is `C_ℓ'(w_head)·μ_ℓ`. With
`C_ℓ(w) = (w/T_ℓ)²`:

```
index_ℓ(t) = 2 · w_head · μ_ℓ / T_ℓ²
```

which grows with how long the head-of-line patient has already waited. This is
delay-adaptive like the paper's Slack-Based Policy, but **derived rather than tuned** — it
has no free parameters to fit at all.

**Reporting it honestly.** The c·μ rule is optimal for the *holding cost*, not for the
unweighted mean wait, so `src/metrics.py` computes

```
holding_cost = mean_i ( w_i / T_{level(i)} )
```

— waiting measured in units of each patient's own clinical tolerance — and `run_03` ranks
the policies on it. Judging the rule only by unweighted mean wait would be a category error.
**Verified** by `test_cmu_indices_rank_as_theory_predicts` and
`test_cmu_minimises_its_own_objective_against_the_paper_policies`.

**Caveat stated in the script.** The Cox–Smith optimality proof assumes a single-stage
multi-class queue. This model has **re-entrant flow** (patients return for a follow-up after
diagnostics) and a **time-varying** server pool, so the guarantee is approximate here. The
script says so if the empirical ranking ever contradicts the theory.
