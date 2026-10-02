"""
tests/test_model.py -- correctness checks for the simulator.

These are not unit tests for their own sake: each one pins down a property that
a result in the write-up depends on.  If any of them fails, some number in
results/ is wrong.

Run with:
    python tests/test_model.py          # plain runner, no pytest needed
    pytest tests/test_model.py -q       # or under pytest, if installed
"""
from __future__ import annotations

import math
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import config as C
from src.distributions import (truncexp_mean, truncexp_ppf,
                               trunclognormal_ppf, _norm_ppf)
from src.engine import Simulation, simulate
from src.optimizers import nelder_mead
from src.policies import make_policy
from src.resources import PhysicianPool
from src.rng import (clone_stream, generate_patient_stream, offered_load,
                     rate_at, replication_seed, thinned_arrival_times)
from src.stats import paired_t, reps_for_halfwidth

CFG = C.DEFAULT_CONFIG


# ---------------------------------------------------------------------------
# Distributions
# ---------------------------------------------------------------------------
def test_truncexp_bounds_and_monotonicity():
    """Inverse CDF maps [0,1] onto exactly [a,b] and is increasing."""
    lo, hi = C.CONSULT_INITIAL_LO, C.CONSULT_INITIAL_HI
    us = np.linspace(1e-9, 1 - 1e-9, 2001)
    xs = np.array([truncexp_ppf(u, C.CONSULT_INITIAL_MEAN, lo, hi) for u in us])
    assert xs.min() >= lo - 1e-9, xs.min()
    assert xs.max() <= hi + 1e-9, xs.max()
    assert np.all(np.diff(xs) > 0), "PPF must be strictly increasing"
    assert abs(truncexp_ppf(0.0, C.CONSULT_INITIAL_MEAN, lo, hi) - lo) < 1e-9
    assert abs(truncexp_ppf(1.0, C.CONSULT_INITIAL_MEAN, lo, hi) - hi) < 1e-9


def test_truncexp_mean_matches_sampling():
    """The closed-form mean agrees with a large Monte-Carlo sample."""
    for mean, lo, hi in ((9.0, 5.0, 15.0), (15.0, 5.0, 25.0), (3.0, 1.0, 4.0)):
        analytic = truncexp_mean(mean, lo, hi)
        rng = np.random.default_rng(7)
        xs = np.array([truncexp_ppf(u, mean, lo, hi) for u in rng.random(200_000)])
        assert abs(xs.mean() - analytic) < 0.02, (mean, xs.mean(), analytic)


def test_paper_service_means():
    """The paper's stated 9 and 15 min give these realised (truncated) means."""
    assert abs(truncexp_mean(9.0, 5.0, 15.0) - 9.0926) < 1e-3
    assert abs(truncexp_mean(15.0, 5.0, 25.0) - 12.8410) < 1e-3


def test_normal_ppf_accuracy():
    """Acklam's approximation is accurate enough to trust in the sampler."""
    from scipy.stats import norm
    for p in (1e-6, 0.001, 0.02, 0.1, 0.5, 0.9, 0.98, 0.999, 1 - 1e-6):
        assert abs(_norm_ppf(p) - norm.ppf(p)) < 1e-6, p


def test_trunclognormal_bounds():
    lo, hi = 5.0, 15.0
    xs = [trunclognormal_ppf(u, 9.0, 0.3, lo, hi)
          for u in np.linspace(1e-9, 1 - 1e-9, 1001)]
    assert min(xs) >= lo - 1e-9 and max(xs) <= hi + 1e-9
    assert all(b > a for a, b in zip(xs, xs[1:]))


# ---------------------------------------------------------------------------
# Arrival process
# ---------------------------------------------------------------------------
def test_arrival_table_shape_and_peak():
    assert len(C.ARRIVAL_RATES) == 7
    assert all(len(d) == 24 for d in C.ARRIVAL_RATES)
    # Table 2, Monday 20-21 is the weekly peak
    assert abs(C.LAMBDA_MAX - 23.05) < 1e-9
    assert abs(C.ARRIVAL_RATES[0][20] - 23.05) < 1e-9
    # Sunday 04-05 is the trough
    assert abs(min(min(d) for d in C.ARRIVAL_RATES) - 1.68) < 1e-9


def test_rate_at_indexing():
    """Eq. (1): d = floor(t/1440) mod 7,  h = floor((t mod 1440)/60)."""
    # Wednesday (d=2) at 10:30 -> t = 2*1440 + 630
    t = 2 * 1440 + 630
    assert abs(rate_at(t) * 60 - C.ARRIVAL_RATES[2][10]) < 1e-12
    # wraps after one week
    assert abs(rate_at(t) - rate_at(t + 7 * 1440)) < 1e-12


def test_thinning_reproduces_table2():
    """The thinned NHPP converges to lambda_{d,h} (this is the WP1 STEP 2 check)."""
    rng = np.random.default_rng(11)
    counts = np.zeros(168)
    weeks = 120
    for _ in range(weeks):
        ts = thinned_arrival_times(rng, C.WEEK_MINUTES)
        idx = (np.asarray(ts) // 60).astype(int)
        counts += np.bincount(idx[idx < 168], minlength=168)
    emp = counts / weeks
    target = np.array([C.ARRIVAL_RATES[d][h] for d in range(7) for h in range(24)])
    rel = np.abs(emp - target).sum() / target.sum()
    # 120 sampled weeks leave ~2% Monte-Carlo noise per hourly cell; the point
    # is that the sampler is UNBIASED, which these tolerances pin down.
    assert rel < 0.03, f"relative L1 error {rel:.4f}"
    assert np.corrcoef(emp, target)[0, 1] > 0.995
    assert abs(emp.sum() / target.sum() - 1.0) < 0.01, "weekly volume must match"


def test_offered_load_is_in_the_papers_band():
    """rho must be close to the paper's ~85% utilisation, or the model is wrong."""
    _, _, rho = offered_load(CFG)
    assert 0.80 < rho < 0.92, rho


# ---------------------------------------------------------------------------
# Patient stream / CRN
# ---------------------------------------------------------------------------
def test_stream_is_deterministic_in_the_seed():
    a = generate_patient_stream(CFG, 4242)
    b = generate_patient_stream(CFG, 4242)
    assert len(a) == len(b)
    for x, y in zip(a, b):
        assert x.arrival_time == y.arrival_time
        assert x.level == y.level
        assert x.initial_duration == y.initial_duration
        assert x.follow_duration == y.follow_duration
        assert x.exams == y.exams


def test_stream_composition_matches_the_paper():
    st = generate_patient_stream(CFG, 999)
    n = len(st)
    p3 = sum(p.level == C.LEVEL_III for p in st) / n
    pex = sum(p.needs_exam for p in st) / n
    assert abs(p3 - C.P_LEVEL_III) < 0.03, p3
    assert abs(pex - C.P_NEEDS_EXAM) < 0.03, pex
    # exams ordered by DESCENDING report delay (paper Sec 2.1.3)
    for p in st:
        delays = [CFG.modalities[j].report_delay for j in p.exams]
        assert delays == sorted(delays, reverse=True), p.exams


def test_crn_gives_every_policy_the_identical_stream():
    """The property WP5 rests on."""
    seeds = [replication_seed(C.BASE_SEED, r, k, True)
             for r in range(3) for k in ("IFP", "SBP", "WSEPT")]
    assert len(set(seeds)) == 3, "CRN seeds must not depend on the policy"
    seeds_i = [replication_seed(C.BASE_SEED, 0, k, False)
               for k in ("IFP", "SBP", "WSEPT")]
    assert len(set(seeds_i)) == 3, "independent seeds must differ per policy"


def test_clone_stream_isolates_run_state():
    st = generate_patient_stream(CFG, 5)
    a = clone_stream(st)
    simulate(CFG, make_policy("IFP"), a)
    b = clone_stream(st)
    assert all(p.wait_initial < 0 for p in b), "clone must reset run state"
    assert all(p.arrival_time == q.arrival_time for p, q in zip(st, b))


# ---------------------------------------------------------------------------
# Resources
# ---------------------------------------------------------------------------
def test_shift_schedule_covers_every_hour():
    pool = PhysicianPool(C.BASELINE_SHIFTS)
    assert [pool.capacity_at(h * 60) for h in range(24)] == \
        [3] * 7 + [5] * 8 + [5] * 7 + [3] * 2
    assert pool.capacity_at(7 * 60) == 5      # shift starts are inclusive
    assert pool.capacity_at(22 * 60) == 3
    # 07:00 is a 3 -> 5 change and 22:00 is a 5 -> 3 change; 15:00 is NOT a
    # change, because the morning and afternoon shifts both roster 5 doctors,
    # so no re-dispatch is needed there.
    assert sorted(pool.shift_change_times(1440)) == [420.0, 1320.0]
    assert sorted(PhysicianPool(C.shifts_from_vector((5, 7, 3)))
                  .shift_change_times(1440)) == [420.0, 900.0, 1320.0]


def test_non_preemptive_capacity_drop():
    """A shrinking shift never interrupts service; it just blocks new starts."""
    pool = PhysicianPool(C.BASELINE_SHIFTS)
    for _ in range(5):
        pool.acquire()
    assert pool.busy == 5
    assert pool.free(21 * 60) == 0            # 5 rostered, 5 busy
    assert pool.free(23 * 60) == 0            # 3 rostered, 5 still busy -> 0
    pool.release(); pool.release(); pool.release()
    assert pool.free(23 * 60) == 1            # 3 rostered, 2 busy


# ---------------------------------------------------------------------------
# Engine invariants
# ---------------------------------------------------------------------------
def test_engine_conserves_patients():
    st = generate_patient_stream(CFG, 31)
    for key in ("IFP", "ALT", "SBP", "WSEPT", "GCMU"):
        sim = Simulation(CFG, make_policy(key), clone_stream(st))
        res = sim.run()
        # every patient is in exactly one terminal state or still in flight
        waiting_initial = len(sim.q3) + len(sim.q4)
        served_initial = sum(1 for p in sim.patients if p.completed_initial)
        assert waiting_initial + served_initial <= len(sim.patients)
        # a patient in the follow-up queue must already have had their initial
        for p in sim.qf:
            assert p.completed_initial and p.needs_exam
        # nobody appears in two queues at once
        ids = [id(p) for p in list(sim.q3) + list(sim.q4) + list(sim.qf)]
        assert len(ids) == len(set(ids))
        assert res.n_arrivals == len(st)
        assert res.n_pathway_done + res.n_unfinished == len(st)
        # nobody is served before they arrive
        for p in sim.patients:
            if p.completed_initial:
                assert p.initial_start >= p.arrival_time - 1e-9
                assert p.wait_initial >= -1e-9


def test_never_more_busy_than_rostered_when_starting():
    """Occupancy may exceed a shrunken roster only through carried-over work."""
    st = generate_patient_stream(CFG, 77)
    sim = Simulation(CFG, make_policy("SBP"), clone_stream(st))
    orig = sim._begin_service

    def checked(p, qid, now):
        assert sim.pool.busy < sim.pool.capacity_at(now), (
            f"started service at t={now} with {sim.pool.busy} busy of "
            f"{sim.pool.capacity_at(now)} rostered")
        orig(p, qid, now)

    sim._begin_service = checked
    sim.run()


def test_no_idle_physician_while_a_patient_waits():
    """Every policy must be work-conserving: capacity is never left unused."""
    st = generate_patient_stream(CFG, 8)
    for key in ("IFP", "ALT", "SBP", "WSEPT", "GCMU"):
        sim = Simulation(CFG, make_policy(key), clone_stream(st))
        orig = sim._dispatch

        def checked(now, _sim=sim, _orig=orig):
            _orig(now)
            waiting = len(_sim.q3) + len(_sim.q4) + len(_sim.qf)
            free = _sim.pool.free(now)
            assert not (free > 0 and waiting > 0), (
                f"{key}: {free} physicians idle with {waiting} patients waiting "
                f"at t={now}")

        sim._dispatch = checked
        sim.run()


def test_exam_chain_follows_equation_4():
    """t_i^exam = max_k (start + tau + delta); exams are sequential per patient."""
    st = generate_patient_stream(CFG, 12)
    sim = Simulation(CFG, make_policy("IFP"), clone_stream(st))
    sim.run()
    checked = 0
    for p in sim.patients:
        if not p.needs_exam or p.exam_ready < 0:
            continue
        starts = [o.start_time for o in p.exam_orders if o.start_time >= 0]
        if len(starts) < 2:
            continue
        # sequential: each exam starts no earlier than the previous one ended
        for a, b in zip(p.exam_orders, p.exam_orders[1:]):
            if a.start_time >= 0 and b.start_time >= 0:
                assert b.start_time >= a.start_time + a.duration - 1e-9
        ready = [o.ready_time for o in p.exam_orders if o.ready_time >= 0]
        if len(ready) == len(p.exam_orders):
            assert abs(p.exam_ready - max(ready)) < 1e-9
        checked += 1
    assert checked > 20, f"only {checked} multi-exam patients checked"


def test_follow_up_only_after_results():
    st = generate_patient_stream(CFG, 13)
    sim = Simulation(CFG, make_policy("ALT"), clone_stream(st))
    sim.run()
    for p in sim.patients:
        if p.completed_follow:
            assert p.follow_start >= p.exam_ready - 1e-9
            assert p.exam_ready >= p.initial_end - 1e-9


def test_two_runs_of_the_same_input_are_identical():
    st = generate_patient_stream(CFG, 21)
    a = simulate(CFG, make_policy("SBP", k1=13.1, k2=2.1), clone_stream(st))
    b = simulate(CFG, make_policy("SBP", k1=13.1, k2=2.1), clone_stream(st))
    assert a.wait_total == b.wait_total
    assert a.physician_util == b.physician_util
    assert a.n_events == b.n_events


# ---------------------------------------------------------------------------
# Policy behaviour
# ---------------------------------------------------------------------------
def test_ifp_gives_absolute_priority_to_initial_consultations():
    st = generate_patient_stream(CFG, 41)
    r = simulate(CFG, make_policy("IFP"), clone_stream(st))
    assert r.wait_init_l3 < r.wait_init_l4, "Level III must precede Level IV"
    assert r.wait_follow > r.wait_init_l4, \
        "IFP must starve the follow-up queue relative to initial consultations"


def test_alt_caps_concurrent_initial_consultations():
    """The 1:1 split: at most floor(R/2) doctors on initial work at once."""
    st = generate_patient_stream(CFG, 42)
    sim = Simulation(CFG, make_policy("ALT"), clone_stream(st))
    orig = sim._dispatch
    seen_capped = [0]

    def checked(now):
        orig(now)
        cap = sim.pool.capacity_at(now) // 2
        # busy_initial may exceed the cap only when the follow-up queue was
        # empty and capacity was re-assigned, which the policy allows.
        if sim.busy_initial > cap and len(sim.qf) > 0:
            seen_capped[0] += 1

    sim._dispatch = checked
    sim.run()
    # the reassignment rule means over-cap states can exist, but the ALT run
    # must still leave the follow-up queue far shorter than IFP does
    r_alt = simulate(CFG, make_policy("ALT"), clone_stream(st))
    r_ifp = simulate(CFG, make_policy("IFP"), clone_stream(st))
    assert r_alt.wait_follow < r_ifp.wait_follow / 2


def test_sbp_thresholds_change_behaviour_monotonically():
    """Raising k2 gives Level IV patients priority sooner, so SL4 must improve."""
    st = generate_patient_stream(CFG, 43)
    sl4 = []
    for k2 in (0.0, 20.0, 60.0, 110.0):
        r = simulate(CFG, make_policy("SBP", k1=13.0, k2=k2), clone_stream(st))
        sl4.append(r.sl_l4)
    assert sl4 == sorted(sl4), sl4
    assert sl4[-1] > sl4[0]


def test_sbp_with_zero_slack_is_close_to_a_follow_up_first_rule():
    """k1 = k2 = 0 means nobody is ever urgent, so follow-ups outrank initials."""
    st = generate_patient_stream(CFG, 44)
    r = simulate(CFG, make_policy("SBP", k1=0.0, k2=0.0), clone_stream(st))
    assert r.wait_follow < r.wait_init_l4


def test_cmu_indices_rank_as_theory_predicts():
    pol = make_policy("WSEPT")
    pol.bind(CFG)
    i3, i4, ifo = pol.idx_static
    assert i3 > ifo > i4, (i3, ifo, i4)
    assert abs(pol.mu_init - 1 / truncexp_mean(9.0, 5.0, 15.0)) < 1e-12
    assert abs(pol.mu_follow - 1 / truncexp_mean(15.0, 5.0, 25.0)) < 1e-12


def test_cmu_minimises_its_own_objective_against_the_paper_policies():
    """The Cox-Smith prediction, on a small but honest sample."""
    hold = {}
    for key in ("IFP", "ALT", "SBP", "WSEPT"):
        vals = []
        for rep in range(6):
            st = generate_patient_stream(CFG, replication_seed(C.BASE_SEED, rep))
            vals.append(simulate(CFG, make_policy(key), clone_stream(st)).holding_cost)
        hold[key] = float(np.mean(vals))
    assert hold["WSEPT"] == min(hold.values()), hold


# ---------------------------------------------------------------------------
# Optimiser
# ---------------------------------------------------------------------------
def test_nelder_mead_on_rosenbrock():
    """The hand-written simplex must solve a standard hard test function."""
    def rosen(v):
        return (1 - v[0]) ** 2 + 100 * (v[1] - v[0] ** 2) ** 2

    r = nelder_mead(rosen, [-1.2, 1.0], initial_step=0.5,
                    xtol=1e-8, ftol=1e-10, max_iter=4000)
    assert abs(r.x[0] - 1.0) < 1e-3, r.x
    assert abs(r.x[1] - 1.0) < 1e-3, r.x
    assert r.f < 1e-6, r.f
    assert r.converged


def test_nelder_mead_respects_bounds():
    def f(v):
        return (v[0] - 100.0) ** 2 + (v[1] + 50.0) ** 2

    r = nelder_mead(f, [1.0, 1.0], initial_step=1.0,
                    bounds=[(0.0, 10.0), (0.0, 10.0)],
                    xtol=1e-6, ftol=1e-8, max_iter=500)
    assert 0.0 <= r.x[0] <= 10.0 and 0.0 <= r.x[1] <= 10.0, r.x
    assert abs(r.x[0] - 10.0) < 1e-3 and abs(r.x[1] - 0.0) < 1e-3, r.x


def test_nelder_mead_matches_scipy():
    from scipy.optimize import minimize

    def f(v):
        return (v[0] - 3.0) ** 4 + (v[1] + 1.0) ** 2 + 0.5 * v[0] * v[1]

    ours = nelder_mead(f, [0.0, 0.0], initial_step=1.0,
                       xtol=1e-9, ftol=1e-12, max_iter=3000)
    theirs = minimize(f, [0.0, 0.0], method="Nelder-Mead",
                      options={"xatol": 1e-9, "fatol": 1e-12, "maxiter": 3000})
    assert abs(ours.f - float(theirs.fun)) < 1e-6, (ours.f, theirs.fun)


# ---------------------------------------------------------------------------
# Statistics
# ---------------------------------------------------------------------------
def test_paired_t_matches_scipy():
    from scipy.stats import ttest_rel
    rng = np.random.default_rng(3)
    a = rng.normal(50, 10, 60)
    b = a - 2.5 + rng.normal(0, 1, 60)
    ours = paired_t(a, b)
    ref = ttest_rel(a, b)
    assert abs(ours.t_stat - float(ref.statistic)) < 1e-9
    assert abs(ours.p_value - float(ref.pvalue)) < 1e-12


def test_reps_for_halfwidth_is_self_consistent():
    from scipy import stats as sps
    sd, hw = 12.0, 1.0
    n = reps_for_halfwidth(sd, hw)
    got = sps.t.ppf(0.975, n - 1) * sd / math.sqrt(n)
    assert got <= hw + 1e-12
    prev = sps.t.ppf(0.975, n - 2) * sd / math.sqrt(n - 1)
    assert prev > hw, "n must be the SMALLEST sufficient sample size"


def test_crn_actually_reduces_variance_of_the_difference():
    """The headline WP5 claim, verified directly."""
    d_crn, d_ind = [], []
    for rep in range(12):
        s = replication_seed(C.BASE_SEED, rep, "", True)
        st = generate_patient_stream(CFG, s)
        a = simulate(CFG, make_policy("IFP"), clone_stream(st)).wait_total
        b = simulate(CFG, make_policy("ALT"), clone_stream(st)).wait_total
        d_crn.append(a - b)

        sa = replication_seed(C.BASE_SEED, rep, "IFP", False)
        sb = replication_seed(C.BASE_SEED, rep, "ALT", False)
        a = simulate(CFG, make_policy("IFP"),
                     clone_stream(generate_patient_stream(CFG, sa))).wait_total
        b = simulate(CFG, make_policy("ALT"),
                     clone_stream(generate_patient_stream(CFG, sb))).wait_total
        d_ind.append(a - b)

    v_crn = float(np.var(d_crn, ddof=1))
    v_ind = float(np.var(d_ind, ddof=1))
    assert v_crn < v_ind / 5.0, (v_crn, v_ind)


# ---------------------------------------------------------------------------
# Plain runner
# ---------------------------------------------------------------------------
def main() -> int:
    tests = [(n, f) for n, f in sorted(globals().items())
             if n.startswith("test_") and callable(f)]
    width = max(len(n) for n, _ in tests)
    passed = failed = 0
    print(f"\nRunning {len(tests)} checks\n" + "-" * (width + 22))
    import time
    for name, fn in tests:
        t0 = time.time()
        try:
            fn()
            print(f"  PASS  {name:<{width}s}  {time.time()-t0:6.2f}s")
            passed += 1
        except AssertionError as e:
            print(f"  FAIL  {name:<{width}s}  {time.time()-t0:6.2f}s  -> {e}")
            failed += 1
        except Exception as e:                                  # noqa: BLE001
            print(f"  ERROR {name:<{width}s}  {time.time()-t0:6.2f}s  "
                  f"-> {type(e).__name__}: {e}")
            failed += 1
    print("-" * (width + 22))
    print(f"  {passed} passed, {failed} failed\n")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
