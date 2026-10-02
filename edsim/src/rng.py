"""
rng.py -- Random-number control and the pre-generated PATIENT STREAM.

This module is the technical heart of WP5 (Common Random Numbers).

--------------------------------------------------------------------------
Why the patient stream is generated up-front
--------------------------------------------------------------------------
A naive DES draws random numbers as it runs.  If you then compare two
scheduling policies, the two runs consume their uniforms in a different ORDER,
so patient #17 gets a 6-minute consultation under IFP and a 13-minute
consultation under SBP.  The difference you measure is then part policy effect
and part noise -- which is exactly the noise CRN is meant to remove.

We therefore split the model into
    (a) an EXOGENOUS stream  -- arrivals, triage levels, service durations,
        examination requirements.  None of these depend on the policy.
    (b) an ENDOGENOUS response -- who is served when, and hence all waiting
        times.  This is the only thing the policy touches.

``generate_patient_stream(cfg, seed)`` materialises (a) once.  Every policy is
then run against the *same* list of ``Patient`` objects (deep-copied so state
does not leak between runs).  Comparisons become exactly paired.

--------------------------------------------------------------------------
Independent substreams
--------------------------------------------------------------------------
Six independent bit generators are spawned from one ``SeedSequence`` -- one per
random dimension.  This gives *synchronisation robustness*: changing how many
uniforms the service-time dimension consumes cannot shift the arrival stream.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import List, Sequence, Tuple

import numpy as np

from . import config as C
from .distributions import service_ppf
from .entities import ExamOrder, Patient


# ---------------------------------------------------------------------------
# Substream bundle
# ---------------------------------------------------------------------------
_STREAM_NAMES = ("arrival", "level", "svc_initial", "svc_follow",
                 "exam_need", "exam_pick")


@dataclass
class StreamBundle:
    """Six independent PCG64 generators derived from one integer seed."""
    arrival: np.random.Generator
    level: np.random.Generator
    svc_initial: np.random.Generator
    svc_follow: np.random.Generator
    exam_need: np.random.Generator
    exam_pick: np.random.Generator

    @classmethod
    def from_seed(cls, seed: int) -> "StreamBundle":
        children = np.random.SeedSequence(seed).spawn(len(_STREAM_NAMES))
        gens = [np.random.Generator(np.random.PCG64(c)) for c in children]
        return cls(*gens)


# ---------------------------------------------------------------------------
# Non-homogeneous Poisson arrivals -- Lewis & Shedler THINNING
# ---------------------------------------------------------------------------
def rate_at(t: float, arrival_scale: float = 1.0) -> float:
    """lambda_{d,h} in patients per MINUTE at simulation time ``t`` minutes.

    Day/hour indices follow Eq. (1) of the paper:
        d = floor(t / 1440) mod 7,   h = floor((t mod 1440) / 60)
    """
    d = int(t // C.MINUTES_PER_DAY) % C.DAYS_PER_WEEK
    h = int((t % C.MINUTES_PER_DAY) // C.MINUTES_PER_HOUR)
    return C.ARRIVAL_RATES[d][h] * arrival_scale / C.MINUTES_PER_HOUR


def thinned_arrival_times(rng: np.random.Generator, horizon: float,
                          arrival_scale: float = 1.0) -> List[float]:
    """Sample arrival epochs of an NHPP on [0, horizon) by thinning.

    Algorithm (Lewis-Shedler 1979):
        1.  Let lambda* = max_{d,h} lambda_{d,h}  (a dominating constant rate).
        2.  Generate a homogeneous Poisson process of rate lambda*.
        3.  Keep each candidate epoch t with probability lambda(t) / lambda*.

    The kept epochs are distributed exactly as the NHPP with intensity
    lambda(t).  This is the paper's stated arrival mechanism [Eq. 1-2] and is
    implemented from scratch (no ``scipy.stats`` process sampler).
    """
    lam_star = C.LAMBDA_MAX * arrival_scale / C.MINUTES_PER_HOUR   # per minute
    times: List[float] = []
    t = 0.0
    # Draw candidate gaps in blocks -- roughly lam_star*horizon are needed.
    block = max(256, int(lam_star * horizon * 1.2) + 64)
    while True:
        gaps = rng.exponential(1.0 / lam_star, size=block)
        accepts = rng.random(size=block)
        for gap, u in zip(gaps, accepts):
            t += gap
            if t >= horizon:
                return times
            if u <= rate_at(t, arrival_scale) / lam_star:
                times.append(t)


# ---------------------------------------------------------------------------
# Patient stream
# ---------------------------------------------------------------------------
def _ordered_exam_indices(cfg: C.SimConfig) -> List[int]:
    """Modality indices sorted by DESCENDING report delay delta_j.

    Paper, Sec 2.1.3: "The scheduling sequence is prioritized in descending
    order of reporting delay, such that delta_{j1} >= delta_{j2} >= ... which
    ensures that tests with the longest reporting times are initiated first."
    Ties (X-ray and CT both delay 30 min) are broken by modality index so the
    ordering is deterministic.
    """
    idx = list(range(len(cfg.modalities)))
    idx.sort(key=lambda j: (-cfg.modalities[j].report_delay, j))
    return idx


def generate_patient_stream(cfg: C.SimConfig, seed: int) -> List[Patient]:
    """Materialise one replication's exogenous randomness.

    Returns a list of :class:`Patient` in arrival order with every random
    attribute already drawn.  The returned objects are *templates*: the engine
    copies them (see :func:`clone_stream`) before mutating run state.
    """
    st = StreamBundle.from_seed(seed)
    arrivals = thinned_arrival_times(st.arrival, cfg.horizon, cfg.arrival_scale)
    n = len(arrivals)
    if n == 0:
        return []

    # --- triage levels: Pr(l) = 25% Level III, 75% Level IV ------------------
    lv_u = st.level.random(n)
    levels = np.where(lv_u < cfg.p_level_iii, C.LEVEL_III, C.LEVEL_IV)

    # --- consultation durations (inverse-CDF, one uniform each) --------------
    u_init = st.svc_initial.random(n)
    u_foll = st.svc_follow.random(n)

    # --- examination requirement --------------------------------------------
    u_need = st.exam_need.random(n)
    needs = u_need < cfg.p_needs_exam
    n_mod = len(cfg.modalities)
    probs = np.array([m.prob for m in cfg.modalities])
    u_pick = st.exam_pick.random((n, n_mod))
    picked = u_pick < probs                     # (n, n_mod) boolean

    # "60% required AT LEAST ONE diagnostic test" [Sec 3.1].  A patient flagged
    # as needing exams whose independent draws happened to select nothing is
    # re-drawn, i.e. we sample from the distribution CONDITIONAL on >= 1 exam.
    # P(no exam | needs) = 0.08*0.78*0.71*0.45 = 1.99%, so this correction is
    # tiny but it keeps the stated "at least one" semantics exact.
    if cfg.exam_require_at_least_one:
        empty = needs & (~picked.any(axis=1))
        guard = 0
        while empty.any() and guard < 64:
            redraw = st.exam_pick.random((int(empty.sum()), n_mod)) < probs
            picked[empty] = redraw
            empty = needs & (~picked.any(axis=1))
            guard += 1

    order = _ordered_exam_indices(cfg)
    mods = cfg.modalities

    dist = cfg.service_dist
    sig = C.LOGNORMAL_SIGMA
    patients: List[Patient] = []
    for i in range(n):
        need = bool(needs[i])
        if need:
            ex = tuple(j for j in order if picked[i, j])
        else:
            ex = ()
        p = Patient(
            pid=i,
            arrival_time=float(arrivals[i]),
            level=int(levels[i]),
            initial_duration=service_ppf(
                float(u_init[i]), "initial", dist,
                C.CONSULT_INITIAL_MEAN, C.CONSULT_INITIAL_LO,
                C.CONSULT_INITIAL_HI, sig),
            follow_duration=service_ppf(
                float(u_foll[i]), "follow", dist,
                C.CONSULT_FOLLOW_MEAN, C.CONSULT_FOLLOW_LO,
                C.CONSULT_FOLLOW_HI, sig),
            needs_exam=need and len(ex) > 0,
            exams=ex,
        )
        p.exam_orders = [ExamOrder(j, mods[j].duration, mods[j].report_delay)
                         for j in ex]
        patients.append(p)
    return patients


def clone_stream(stream: Sequence[Patient]) -> List[Patient]:
    """Fast deep copy of a patient stream, resetting all run-time state.

    ~5x faster than ``copy.deepcopy`` because we know the schema.  Called once
    per (policy, replication) so that the same exogenous stream can be reused
    across policies without one run's state contaminating another's.
    """
    out: List[Patient] = []
    for p in stream:
        q = Patient(
            pid=p.pid,
            arrival_time=p.arrival_time,
            level=p.level,
            initial_duration=p.initial_duration,
            follow_duration=p.follow_duration,
            needs_exam=p.needs_exam,
            exams=p.exams,
        )
        q.exam_orders = [ExamOrder(e.modality_index, e.duration, e.report_delay)
                         for e in p.exam_orders]
        out.append(q)
    return out


# ---------------------------------------------------------------------------
# Seed policy -- this is what makes WP5's comparison meaningful
# ---------------------------------------------------------------------------
def replication_seed(base_seed: int, rep: int, policy_key: str = "",
                     crn: bool = True) -> int:
    """Return the stream seed for replication ``rep``.

    crn = True   -> seed depends ONLY on (base_seed, rep).  Every policy in
                    replication ``rep`` therefore sees an identical patient
                    stream.  This is Common Random Numbers.
    crn = False  -> the policy name is folded into the seed, so each policy
                    gets an independent stream.  This is the "no variance
                    reduction" control arm used by run_06_crn_variance.py.
    """
    if crn:
        return int(base_seed + 7919 * rep)
    h = 0
    for ch in policy_key:
        h = (h * 131 + ord(ch)) & 0xFFFFFFFF
    return int((base_seed + 7919 * rep + 104729 * (h % 9973)) & 0x7FFFFFFF)


# ---------------------------------------------------------------------------
# Diagnostics
# ---------------------------------------------------------------------------
def expected_weekly_arrivals(arrival_scale: float = 1.0) -> float:
    """Analytic E[#arrivals in one week] = sum over all (d,h) of lambda_{d,h}."""
    return sum(sum(day) for day in C.ARRIVAL_RATES) * arrival_scale


def offered_load(cfg: C.SimConfig) -> Tuple[float, float, float]:
    """(physician-minutes demanded, physician-minutes supplied, rho) per week.

    A quick analytic sanity check printed by run_01_validate_paper.py -- if rho
    is not close to the paper's ~85% utilisation, the parameterisation is wrong.
    """
    from .distributions import truncexp_mean
    n = expected_weekly_arrivals(cfg.arrival_scale)
    e_init = truncexp_mean(C.CONSULT_INITIAL_MEAN, C.CONSULT_INITIAL_LO,
                           C.CONSULT_INITIAL_HI)
    e_foll = truncexp_mean(C.CONSULT_FOLLOW_MEAN, C.CONSULT_FOLLOW_LO,
                           C.CONSULT_FOLLOW_HI)
    p_ex = cfg.p_needs_exam
    demand = n * e_init + n * p_ex * e_foll
    supply = 0.0
    for s in cfg.shifts:
        length = (s.end_hour - s.start_hour) % 24
        supply += length * 60.0 * s.physicians * C.DAYS_PER_WEEK
    return demand, supply, demand / supply if supply else math.inf
