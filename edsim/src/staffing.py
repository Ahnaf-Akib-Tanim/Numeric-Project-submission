"""
staffing.py -- WP4.  Cost-based joint optimisation of STAFFING and thresholds.

The base paper treats staffing as a sensitivity knob: it re-runs seven fixed
rosters (Table 10) and observes that more physicians means shorter waits.  It
never answers the question a hospital actually asks -- *how many physicians
should we roster?* -- because it has no way to trade a doctor's salary against
a patient's waiting time.

This module supplies that missing objective:

    C(R, k1, k2) = alpha * (physician-hours per week)
                 + beta  * (total patient waiting-minutes per week)
                 + gamma * (number of SLA violations per week)

and then searches over integer rosters R = (R_morning, R_afternoon, R_night),
re-tuning (k1, k2) with the WP3 Nelder-Mead optimiser inside each candidate --
because the best thresholds for a 3-doctor night shift are not the best
thresholds for a 5-doctor night shift.  That inner re-tuning is what makes this
a *joint* optimisation rather than a staffing sweep at fixed parameters.

Search design
-------------
The full box 2..8 physicians on each of three shifts is 7^3 = 343 rosters, and
running a Nelder-Mead tuning inside every one of them is wasteful: most rosters
are either obviously unstable (the queue never clears) or obviously
over-staffed.  We therefore use two stages:

  Stage A -- SCREEN.  Every roster in the box is evaluated once, cheaply (few
             replications) at the incumbent (k1, k2).  Rosters whose queues do
             not clear are marked UNSTABLE and dropped; the rest are ranked by
             screening cost.
  Stage B -- REFINE.  The best ``n_refine`` rosters get the full treatment:
             a Nelder-Mead re-tune of (k1, k2) and a full-length evaluation.

Both stages are reported, so the pruning is visible and auditable rather than
hidden.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np

from . import config as C
from .metrics import RunResult


# ---------------------------------------------------------------------------
# Cost accounting
# ---------------------------------------------------------------------------
def physician_hours_per_week(shifts: Sequence[C.Shift]) -> float:
    """Total rostered physician-hours in one simulated week."""
    total = 0.0
    for s in shifts:
        length = (s.end_hour - s.start_hour) % 24 or 24
        total += length * s.physicians * C.DAYS_PER_WEEK
    return total


@dataclass
class CostBreakdown:
    """Weekly cost of one (roster, thresholds) combination."""
    staffing: Tuple[int, int, int]
    k1: float
    k2: float
    physician_hours: float
    staff_cost: float
    wait_minutes: float
    wait_cost: float
    n_violations: float
    violation_cost: float
    total_cost: float
    mean_wait: float
    sl_l3: float
    sl_l4: float
    utilisation: float
    unfinished: float
    stable: bool
    n_reps: int

    def row(self) -> List:
        return [f"({self.staffing[0]},{self.staffing[1]},{self.staffing[2]})",
                f"{self.k1:.2f}", f"{self.k2:.2f}",
                f"{self.physician_hours:.0f}",
                f"{self.mean_wait:.2f}",
                f"{self.sl_l3*100:.2f}", f"{self.sl_l4*100:.2f}",
                f"{self.utilisation*100:.1f}",
                f"{self.staff_cost:,.0f}", f"{self.wait_cost:,.0f}",
                f"{self.violation_cost:,.0f}", f"{self.total_cost:,.0f}",
                "yes" if self.stable else "NO"]


#: A roster is called unstable when this share of the week's patients are still
#: in the system at the horizon -- the queue is growing rather than clearing.
#: OUR CHOICE: 15%.  A well-behaved roster leaves ~1-2% (work in progress).
UNSTABLE_UNFINISHED_FRACTION = 0.15


def cost_of(runs: List[RunResult], shifts: Sequence[C.Shift],
            k1: float, k2: float,
            cost: C.CostParams = C.DEFAULT_COST) -> CostBreakdown:
    """Evaluate C(R, k1, k2) from a batch of replications.

    All three terms are per simulated week, so they are directly comparable.
    """
    hours = physician_hours_per_week(shifts)
    staff_cost = cost.alpha_physician_hour * hours

    # total patient waiting-minutes per week = (patients served) x (mean wait)
    wait_minutes = float(np.mean([r.wait_total * r.n_pathway_done for r in runs]))
    wait_cost = cost.beta_wait_minute * wait_minutes

    # SLA violations per week, counted on the initial-consultation wait
    viol = float(np.mean([
        r.delay_rate_l3 * r.n_initial_done * C.P_LEVEL_III
        + r.delay_rate_l4 * r.n_initial_done * C.P_LEVEL_IV
        for r in runs]))
    viol_cost = cost.gamma_sla_violation * viol

    unfinished = float(np.mean([r.n_unfinished / max(1, r.n_arrivals) for r in runs]))
    stable = unfinished <= UNSTABLE_UNFINISHED_FRACTION

    return CostBreakdown(
        staffing=tuple(s.physicians for s in shifts),      # type: ignore[arg-type]
        k1=k1, k2=k2,
        physician_hours=hours,
        staff_cost=staff_cost,
        wait_minutes=wait_minutes,
        wait_cost=wait_cost,
        n_violations=viol,
        violation_cost=viol_cost,
        total_cost=staff_cost + wait_cost + viol_cost,
        mean_wait=float(np.mean([r.wait_total for r in runs])),
        sl_l3=float(np.mean([r.sl_l3 for r in runs])),
        sl_l4=float(np.mean([r.sl_l4 for r in runs])),
        utilisation=float(np.mean([r.physician_util for r in runs])),
        unfinished=unfinished,
        stable=stable,
        n_reps=len(runs),
    )


# ---------------------------------------------------------------------------
# The staffing objective used inside the roster search
# ---------------------------------------------------------------------------
class StaffingObjective:
    """f(k1, k2) -> weekly cost, for one FIXED roster.

    Shares the interface of :class:`~src.optimizers.SimulationObjective` so the
    same hand-written Nelder-Mead drives it.  An unstable roster returns a
    large finite value (not ``inf``) so the simplex still has a usable gradient
    direction to escape along.
    """

    UNSTABLE_PENALTY = 5.0e6

    def __init__(self, cfg: C.SimConfig, n_reps: int, base_seed: int,
                 workers: int, cost: C.CostParams, policy_key: str = "SBP",
                 round_to: Optional[float] = 0.1, progress=None):
        self.cfg = cfg
        self.n_reps = n_reps
        self.base_seed = base_seed
        self.workers = workers
        self.cost = cost
        self.policy_key = policy_key
        self.round_to = round_to
        self.progress = progress
        self.cache: Dict[Tuple[float, float], CostBreakdown] = {}
        self.n_evaluations = 0
        self.n_simulations = 0

    def _key(self, x):
        r = self.round_to
        if r:
            return tuple(round(round(v / r) * r, 10) for v in x)
        return tuple(round(v, 10) for v in x)

    def breakdown(self, x) -> CostBreakdown:
        from .experiment import evaluate_points
        k = self._key(x)
        hit = self.cache.get(k)
        if hit is not None:
            return hit
        runs = evaluate_points(self.cfg, self.policy_key,
                               [{"k1": float(k[0]), "k2": float(k[1])}],
                               self.n_reps, self.base_seed, self.workers,
                               self.progress)[0]
        cb = cost_of(runs, self.cfg.shifts, float(k[0]), float(k[1]), self.cost)
        self.cache[k] = cb
        self.n_evaluations += 1
        self.n_simulations += self.n_reps
        return cb

    def __call__(self, x) -> float:
        cb = self.breakdown(x)
        return cb.total_cost if cb.stable else self.UNSTABLE_PENALTY + cb.total_cost


# ---------------------------------------------------------------------------
# Roster enumeration
# ---------------------------------------------------------------------------
def enumerate_rosters(lo: int = C.STAFFING_SEARCH_RANGE[0],
                      hi: int = C.STAFFING_SEARCH_RANGE[1],
                      monotone_night: bool = True) -> List[Tuple[int, int, int]]:
    """All integer rosters in the box [lo, hi]^3.

    ``monotone_night`` drops rosters that staff the quiet 22:00-07:00 shift
    more heavily than the busy daytime shifts.  Arrival rates in Table 2 are
    3-8x higher during the day, so such rosters are never sensible; excluding
    them cuts the screening set by roughly half without removing any candidate
    that could win.
    """
    out = []
    for m in range(lo, hi + 1):
        for a in range(lo, hi + 1):
            for n in range(lo, hi + 1):
                if monotone_night and (n > m or n > a):
                    continue
                out.append((m, a, n))
    return out
