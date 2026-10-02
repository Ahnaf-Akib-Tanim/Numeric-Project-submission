"""
optimizers.py -- WP3.  Two ways to tune the Slack-Based Policy's (k1, k2).

  1. ``grid_search``  -- the base paper's method: evaluate a full lattice of
     candidates, coarse (step 1.0) then fine (step 0.1).  Exhaustive, embarrassingly
     parallel, and extremely expensive: every lattice point costs a full batch
     of week-long replications.

  2. ``nelder_mead`` -- a HAND-IMPLEMENTED simplex method (Nelder & Mead 1965).
     Derivative-free, so it suits a simulation objective with no analytic
     gradient, and it typically needs one to two orders of magnitude fewer
     objective evaluations than a lattice of comparable resolution.

Both are driven through the same :class:`SimulationObjective`, so the
evaluation-count comparison between them is exactly like-for-like.

--------------------------------------------------------------------------
Making a stochastic objective usable by a deterministic optimiser
--------------------------------------------------------------------------
Nelder-Mead assumes it is minimising a deterministic function.  A raw
simulation is not deterministic, and simplex methods stall or wander on noisy
responses.  We use SAMPLE AVERAGE APPROXIMATION with COMMON RANDOM NUMBERS:
every candidate (k1, k2) is evaluated on the SAME fixed set of ``n_reps``
patient streams.  The resulting sample-average function is deterministic
(evaluating the same point twice returns exactly the same number) and much
smoother than the underlying expectation's noisy estimates, because the
seed-to-seed variation is common to all candidates and cancels in comparisons.

--------------------------------------------------------------------------
Handling the service-level constraint
--------------------------------------------------------------------------
The paper's problem is

        min  W_total(k1,k2)      s.t.   SL_l(k1,k2) >= SL_l^min      (Eqs 31-32)

Nelder-Mead is unconstrained, so the constraint is folded in with an EXTERIOR
PENALTY:

        F(k1,k2) = W_total + mu * sum_l max(0, SL_l^min - SL_l)

with ``mu`` in minutes per unit of service-level shortfall.  ``mu = 500`` (the
default) means "one percentage point of SLA shortfall is as bad as five extra
minutes of average waiting" -- large enough that infeasible points are never
optimal, small enough that the penalised surface stays smooth near the
boundary.  Box bounds are handled by projection (clipping) rather than by a
second penalty, which keeps the simplex inside the physically meaningful
region k >= 0.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Sequence, Tuple

import numpy as np

from . import config as C
from .console import Progress
from .experiment import evaluate_points
from .metrics import RunResult


# ---------------------------------------------------------------------------
# Objective
# ---------------------------------------------------------------------------
@dataclass
class EvalRecord:
    """One objective evaluation, kept for the convergence plots."""
    x: Tuple[float, ...]
    f: float
    wait: float
    sl3: float
    sl4: float
    penalty: float
    n_sims: int
    cached: bool
    wall: float


class SimulationObjective:
    """Callable f(k1, k2) -> penalised mean waiting time.

    Also records every evaluation so that the optimiser's search path and its
    simulation budget can be plotted and reported.
    """

    def __init__(self, cfg: C.SimConfig, n_reps: int,
                 base_seed: int = C.BASE_SEED, workers: int = 0,
                 penalty_mu: float = 500.0,
                 sl_min: Optional[Dict[int, float]] = None,
                 metric: str = "wait_total",
                 policy_key: str = "SBP",
                 round_to: Optional[float] = None,
                 progress: Optional[Progress] = None):
        self.cfg = cfg
        self.n_reps = n_reps
        self.base_seed = base_seed
        self.workers = workers
        self.penalty_mu = penalty_mu
        self.sl_min = dict(sl_min or C.SL_MIN)
        self.metric = metric
        self.policy_key = policy_key
        #: quantise the search space (e.g. 0.1) so the cache actually hits and
        #: the reported optimum is reproducible at the paper's precision
        self.round_to = round_to
        self.progress = progress

        self.cache: Dict[Tuple[float, float], EvalRecord] = {}
        self.history: List[EvalRecord] = []
        self.n_evaluations = 0        # distinct points actually simulated
        self.n_simulations = 0        # week-long replications actually run
        self.n_calls = 0              # calls including cache hits

    # -- helpers ------------------------------------------------------------
    def _key(self, x: Sequence[float]) -> Tuple[float, float]:
        if self.round_to:
            r = self.round_to
            return tuple(round(round(v / r) * r, 10) for v in x)  # type: ignore
        return tuple(round(v, 10) for v in x)                     # type: ignore

    def summarise(self, runs: List[RunResult]) -> Tuple[float, float, float]:
        wait = float(np.mean([getattr(r, self.metric) for r in runs]))
        sl3 = float(np.mean([r.sl_l3 for r in runs]))
        sl4 = float(np.mean([r.sl_l4 for r in runs]))
        return wait, sl3, sl4

    def penalty(self, sl3: float, sl4: float) -> float:
        v3 = max(0.0, self.sl_min.get(C.LEVEL_III, 0.0) - sl3)
        v4 = max(0.0, self.sl_min.get(C.LEVEL_IV, 0.0) - sl4)
        return self.penalty_mu * (v3 + v4)

    # -- the objective itself ------------------------------------------------
    def __call__(self, x: Sequence[float]) -> float:
        self.n_calls += 1
        k = self._key(x)
        hit = self.cache.get(k)
        if hit is not None:
            self.history.append(EvalRecord(k, hit.f, hit.wait, hit.sl3, hit.sl4,
                                           hit.penalty, 0, True, 0.0))
            return hit.f
        t0 = time.time()
        pt = {"k1": float(k[0]), "k2": float(k[1])}
        runs = evaluate_points(self.cfg, self.policy_key, [pt], self.n_reps,
                               self.base_seed, self.workers, self.progress)[0]
        wait, sl3, sl4 = self.summarise(runs)
        pen = self.penalty(sl3, sl4)
        rec = EvalRecord(k, wait + pen, wait, sl3, sl4, pen, self.n_reps,
                         False, time.time() - t0)
        self.cache[k] = rec
        self.history.append(rec)
        self.n_evaluations += 1
        self.n_simulations += self.n_reps
        return rec.f

    def evaluate_many(self, points: Sequence[Sequence[float]]) -> List[EvalRecord]:
        """Vectorised path used by the grid search (one parallel batch)."""
        keys = [self._key(p) for p in points]
        todo = [k for k in keys if k not in self.cache]
        # de-duplicate while preserving order
        seen = set()
        todo = [k for k in todo if not (k in seen or seen.add(k))]
        if todo:
            pts = [{"k1": float(k[0]), "k2": float(k[1])} for k in todo]
            batches = evaluate_points(self.cfg, self.policy_key, pts, self.n_reps,
                                      self.base_seed, self.workers, self.progress)
            for k, runs in zip(todo, batches):
                wait, sl3, sl4 = self.summarise(runs)
                pen = self.penalty(sl3, sl4)
                self.cache[k] = EvalRecord(k, wait + pen, wait, sl3, sl4, pen,
                                           self.n_reps, False, 0.0)
                self.n_evaluations += 1
                self.n_simulations += self.n_reps
        recs = [self.cache[k] for k in keys]
        self.history.extend(recs)
        self.n_calls += len(keys)
        return recs


# ---------------------------------------------------------------------------
# 1. Grid search -- the base paper's method
# ---------------------------------------------------------------------------
@dataclass
class GridResult:
    best_x: Tuple[float, float]
    best_f: float
    records: List[EvalRecord]
    n_points: int
    n_simulations: int
    stage: str

    def top(self, k: int = 5) -> List[EvalRecord]:
        return sorted(self.records, key=lambda r: r.f)[:k]


def _arange_inclusive(lo: float, hi: float, step: float) -> List[float]:
    n = int(round((hi - lo) / step))
    return [round(lo + i * step, 10) for i in range(n + 1)]


def grid_search(obj: SimulationObjective,
                k1_range: Tuple[float, float], k2_range: Tuple[float, float],
                step: float, stage: str = "coarse") -> GridResult:
    """Exhaustive lattice search -- the paper's two-stage procedure, one stage.

    Every lattice point costs ``obj.n_reps`` week-long replications, so the
    simulation budget is ``n_points * n_reps``.  That number is the baseline
    the Nelder-Mead run is measured against.
    """
    k1s = _arange_inclusive(*k1_range, step)
    k2s = _arange_inclusive(*k2_range, step)
    points = [(a, b) for a in k1s for b in k2s]
    before = obj.n_simulations
    recs = obj.evaluate_many(points)
    best = min(recs, key=lambda r: r.f)
    return GridResult(best_x=(best.x[0], best.x[1]), best_f=best.f,
                      records=recs, n_points=len(points),
                      n_simulations=obj.n_simulations - before, stage=stage)


# ---------------------------------------------------------------------------
# 2. Nelder-Mead -- hand implemented
# ---------------------------------------------------------------------------
@dataclass
class NelderMeadResult:
    x: Tuple[float, ...]
    f: float
    n_iterations: int
    n_function_calls: int
    n_simulations: int
    converged: bool
    message: str
    simplex_path: List[List[Tuple[float, ...]]] = field(default_factory=list)
    best_path: List[Tuple[Tuple[float, ...], float]] = field(default_factory=list)


def nelder_mead(f: Callable[[Sequence[float]], float],
                x0: Sequence[float],
                initial_step: Sequence[float] | float = 1.0,
                bounds: Optional[Sequence[Tuple[float, float]]] = None,
                alpha: float = 1.0, gamma: float = 2.0,
                rho: float = 0.5, sigma: float = 0.5,
                xtol: float = 1e-2, ftol: float = 1e-3,
                max_iter: int = 200,
                verbose: bool = False,
                on_iter: Optional[Callable[[int, list, list], None]] = None
                ) -> NelderMeadResult:
    r"""Downhill simplex method of Nelder & Mead (1965), written out in full.

    For an n-dimensional problem the simplex has n+1 vertices.  Each iteration
    orders them best-to-worst and tries, in this order:

        reflection    x_r = x_c + alpha (x_c - x_worst)
        expansion     x_e = x_c + gamma (x_r - x_c)          if x_r is the new best
        contraction   x_k = x_c + rho   (x_worst - x_c)      if x_r is no better
                                                              than the 2nd worst
        shrink        x_i = x_best + sigma (x_i - x_best)    if contraction fails

    where x_c is the centroid of all vertices except the worst.

    Parameters
    ----------
    initial_step : scalar or per-dimension vector used to build the initial
        simplex as ``x0`` plus one step along each coordinate axis.  For this
        problem the natural scale differs per dimension (k1 lives on ~[0,30],
        k2 on ~[0,120]), so a vector is the right choice.
    bounds : optional per-dimension (lo, hi); enforced by clipping every trial
        point back into the box (projection).
    xtol, ftol : convergence when the simplex is smaller than ``xtol`` in every
        coordinate AND the spread of vertex values is below ``ftol``.
    """
    x0 = np.asarray(x0, dtype=float)
    n = x0.size
    steps = (np.full(n, float(initial_step)) if np.isscalar(initial_step)
             else np.asarray(initial_step, dtype=float))

    def clip(v: np.ndarray) -> np.ndarray:
        if bounds is None:
            return v
        return np.array([min(max(v[i], bounds[i][0]), bounds[i][1])
                         for i in range(n)])

    # --- build the initial simplex: x0 and x0 + step_i * e_i ----------------
    simplex = [clip(x0.copy())]
    for i in range(n):
        p = x0.copy()
        p[i] += steps[i]
        simplex.append(clip(p))
    fvals = [f(p) for p in simplex]
    n_calls = len(simplex)

    path: List[List[Tuple[float, ...]]] = []
    best_path: List[Tuple[Tuple[float, ...], float]] = []
    converged = False
    message = "max iterations reached"
    it = 0

    for it in range(1, max_iter + 1):
        # 1. order
        order = np.argsort(fvals)
        simplex = [simplex[i] for i in order]
        fvals = [fvals[i] for i in order]
        path.append([tuple(p) for p in simplex])
        best_path.append((tuple(simplex[0]), fvals[0]))

        if verbose:
            print(f"    iter {it:3d}  best={fvals[0]:9.4f} at "
                  f"({simplex[0][0]:.3f}, {simplex[0][1]:.3f})  "
                  f"spread_f={fvals[-1]-fvals[0]:.4f}")

        if on_iter is not None:
            on_iter(it, simplex, fvals)

        # 2. convergence test
        span = np.max(np.abs(np.array(simplex[1:]) - simplex[0]), axis=0)
        if float(np.max(span)) <= xtol and (fvals[-1] - fvals[0]) <= ftol:
            converged = True
            message = f"converged: simplex span <= {xtol} and f-spread <= {ftol}"
            break

        best, worst = simplex[0], simplex[-1]
        fbest, fworst, fsecond = fvals[0], fvals[-1], fvals[-2]

        # 3. centroid of all but the worst
        centroid = np.mean(np.array(simplex[:-1]), axis=0)

        # 4. reflection
        xr = clip(centroid + alpha * (centroid - worst))
        fr = f(xr); n_calls += 1

        if fr < fbest:
            # 5. expansion
            xe = clip(centroid + gamma * (xr - centroid))
            fe = f(xe); n_calls += 1
            if fe < fr:
                simplex[-1], fvals[-1] = xe, fe
            else:
                simplex[-1], fvals[-1] = xr, fr
        elif fr < fsecond:
            simplex[-1], fvals[-1] = xr, fr
        else:
            # 6. contraction -- outside if the reflection improved on the worst
            if fr < fworst:
                xc = clip(centroid + rho * (xr - centroid))      # outside
            else:
                xc = clip(centroid + rho * (worst - centroid))   # inside
            fc = f(xc); n_calls += 1
            if fc < min(fr, fworst):
                simplex[-1], fvals[-1] = xc, fc
            else:
                # 7. shrink toward the best vertex
                for i in range(1, len(simplex)):
                    simplex[i] = clip(best + sigma * (simplex[i] - best))
                    fvals[i] = f(simplex[i]); n_calls += 1

    order = np.argsort(fvals)
    simplex = [simplex[i] for i in order]
    fvals = [fvals[i] for i in order]
    best_path.append((tuple(simplex[0]), fvals[0]))
    return NelderMeadResult(
        x=tuple(simplex[0]), f=fvals[0], n_iterations=it,
        n_function_calls=n_calls, n_simulations=0,
        converged=converged, message=message,
        simplex_path=path, best_path=best_path)


# ---------------------------------------------------------------------------
# Multi-start wrapper -- Nelder-Mead is a local method
# ---------------------------------------------------------------------------
def multistart_nelder_mead(obj: SimulationObjective,
                           starts: Sequence[Sequence[float]],
                           initial_step: Sequence[float],
                           bounds: Sequence[Tuple[float, float]],
                           **kw) -> Tuple[NelderMeadResult, List[NelderMeadResult]]:
    """Run Nelder-Mead from several starting points and keep the best.

    The simplex method only guarantees a LOCAL minimum, and the penalised
    waiting-time surface here has a long flat valley.  A handful of dispersed
    starts is the cheap standard defence, and the per-start results are also
    evidence about how multi-modal the surface actually is.
    """
    runs: List[NelderMeadResult] = []
    for s in starts:
        before = obj.n_simulations
        r = nelder_mead(obj, s, initial_step=initial_step, bounds=bounds, **kw)
        r.n_simulations = obj.n_simulations - before
        runs.append(r)
    best = min(runs, key=lambda r: r.f)
    return best, runs
