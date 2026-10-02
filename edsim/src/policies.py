"""
policies.py -- STRATEGY EXECUTION MODULE  (Figure 2, box 4 of the paper).

A *policy* answers one question, at one decision epoch t:

    "R^t physicians just became free and the three queues
     W^t_init,3 / W^t_init,4 / W^t_follow hold these patients.
     Which R^t patients start service now, and in what order?"

Every policy returns an ordered list of at most R^t patients.  That list is the
concrete realisation of the paper's counts n_3, n_4, n_f, n_r (Eqs. 8-23).

Implemented here
----------------
  IFP    Initial-First Policy           [paper Eqs. 8-10]      -- reproduction
  ALT    Alternating 1:1 Policy         [paper Eqs. 11-13]     -- reproduction
  SBP    Slack-Based Policy (k1, k2)    [paper Eqs. 14-23]     -- reproduction
  WSEPT  c-mu rule / Weighted SEPT      [WP2, OUR CONTRIBUTION]
  GCMU   Generalised c-mu rule          [WP2, OUR CONTRIBUTION]

Uniform tie-break rule, applied by every policy [paper Sec 2.2.3]:
"patients with equal priority are processed based on who arrived earliest".
Because each queue is a FIFO deque that patients enter in time order and leave
only from the front, arrival ordering is maintained structurally -- we never
need to sort.
"""
from __future__ import annotations

import math
from typing import Deque, List, Optional, Tuple

from . import config as C
from .distributions import truncexp_mean
from .entities import Patient


# ---------------------------------------------------------------------------
# Base class
# ---------------------------------------------------------------------------
class Policy:
    """Interface every scheduling strategy implements."""

    #: short key used in filenames / dict keys
    key: str = "BASE"
    #: human-readable name for tables and plots
    name: str = "base"

    def bind(self, cfg: C.SimConfig) -> None:
        """Called once per run; lets a policy pre-compute constants."""
        self.cfg = cfg
        self.T = cfg.targets()

    def allocate(self, sim, now: float, R: int) -> List[Tuple[int, Patient]]:
        """Return up to ``R`` (queue_id, patient) pairs to start serving now.

        ``sim`` is the live :class:`~src.engine.Simulation`; the queues are
        ``sim.q3`` / ``sim.q4`` / ``sim.qf`` and ``R`` is the number of
        physicians free at this decision epoch.  Access to ``sim`` also lets a
        policy see standing state such as how many doctors are currently busy
        with initial versus follow-up work (ALT needs this).

        queue_id is 0 = init L3, 1 = init L4, 2 = follow-up.
        """
        raise NotImplementedError

    def describe(self) -> str:
        return self.name


# --- helper: take the first n patients of a deque without removing them ----
def _head(dq: Deque[Patient], n: int, qid: int) -> List[Tuple[int, Patient]]:
    out = []
    it = iter(dq)
    for _ in range(n):
        out.append((qid, next(it)))
    return out


# ---------------------------------------------------------------------------
# 1. Initial-First Policy  --  paper Eqs. (8)-(10)
# ---------------------------------------------------------------------------
class InitialFirstPolicy(Policy):
    """Initial consultations always take precedence.

        N_init3 = min(D_init3, R)                                    (8)
        N_init4 = min(D_init4, R - N_init3)                          (9)
        N_follow = min(D_follow, R - N_init3 - N_init4)             (10)

    Priority order: Level III initial > Level IV initial > follow-up.
    """
    key = "IFP"
    name = "Initial-First (IFP)"

    def allocate(self, sim, now, R):
        q3, q4, qf = sim.q3, sim.q4, sim.qf
        n3 = min(len(q3), R)
        n4 = min(len(q4), R - n3)
        nf = min(len(qf), R - n3 - n4)
        return _head(q3, n3, 0) + _head(q4, n4, 1) + _head(qf, nf, 2)


# ---------------------------------------------------------------------------
# 2. Alternating 1:1 Policy  --  paper Eqs. (11)-(13)
# ---------------------------------------------------------------------------
class AlternatingPolicy(Policy):
    """Physicians split 1:1 between initial and follow-up work.

        N_init3 + N_init4 = min(D_init3 + D_init4, floor(R/2))      (11)
        N_init3 = min(D_init3, floor(R/2))                          (12)
        N_init4 = min(D_init4, floor(R/2)) - N_init3
        N_follow = min(D_follow, R - N_init3 - N_init4)             (13)

    "When a queue contains fewer patients than what it was allocated, the
     remainder of the capacity is dynamically reassigned to other queues to
     maximize the use of resources."  -- implemented as the final top-up loop,
    which is what keeps physicians from idling while patients wait.
    """
    key = "ALT"
    name = "Alternating 1:1 (ALT)"

    def allocate(self, sim, now, R):
        q3, q4, qf = sim.q3, sim.q4, sim.qf
        # floor(R^t / 2) is a cap on the number of physicians CONCURRENTLY
        # doing initial consultations, where R^t is the full rostered staff.
        # Subtracting those already busy with an initial consultation turns the
        # paper's epoch-wise allocation into an equivalent standing 1:1 split
        # under non-preemptive service.
        cap_init = sim.pool.capacity_at(now) // 2
        room_init = max(0, cap_init - sim.busy_initial)

        n3 = min(len(q3), room_init, R)
        n4 = min(len(q4), room_init - n3, R - n3)
        nf = min(len(qf), R - n3 - n4)

        # dynamic re-assignment of unused capacity back to the initial queues
        rem = R - n3 - n4 - nf
        if rem > 0:
            add3 = min(len(q3) - n3, rem)
            n3 += add3
            rem -= add3
        if rem > 0:
            n4 += min(len(q4) - n4, rem)
        return _head(q3, n3, 0) + _head(q4, n4, 1) + _head(qf, nf, 2)


# ---------------------------------------------------------------------------
# 3. Slack-Based Policy  --  paper Eqs. (14)-(23)
# ---------------------------------------------------------------------------
class SlackBasedPolicy(Policy):
    """Delay-tolerance policy with thresholds (k1, k2).

        urgent_l  <=>  w_i(t) >= T_l - k_l                           (14)
        U3(k1) = {i in W_init,3 : w_i(t) >= T3 - k1}                 (15)
        U4(k2) = {i in W_init,4 : w_i(t) >= T4 - k2}
        priority:  U3 > U4 > follow-up > non-urgent initial          (16)
        n3 = min(|U3|, R)                                            (17)
        n4 = min(|U4|, R - n3)                                       (18)
        nf = min(|F|,  R - n3 - n4)                                  (19)
        nr = min(|H_init|, R - n3 - n4 - nf)                         (20)

    Implementation note: because each initial queue is FIFO-ordered by arrival
    time, the urgent set U_l is always a *prefix* of that queue.  We therefore
    find |U_l| by walking the front of the deque until the urgency test fails
    -- O(|U_l|) rather than O(queue length), and no sorting.
    """
    key = "SBP"

    def __init__(self, k1: float = C.SBP_PAPER_OPTIMUM[0],
                 k2: float = C.SBP_PAPER_OPTIMUM[1]):
        self.k1 = float(k1)
        self.k2 = float(k2)

    @property
    def name(self) -> str:                       # type: ignore[override]
        return f"Slack-Based (SBP, k1={self.k1:g}, k2={self.k2:g})"

    def bind(self, cfg):
        super().bind(cfg)
        # slack thresholds: a patient is urgent once it has waited this long
        self._thr3 = self.T[C.LEVEL_III] - self.k1
        self._thr4 = self.T[C.LEVEL_IV] - self.k2

    @staticmethod
    def _urgent_prefix(dq: Deque[Patient], now: float, thr: float) -> int:
        n = 0
        for p in dq:
            if now - p.queue_entry_time >= thr:
                n += 1
            else:
                break                            # FIFO => rest are younger
        return n

    def allocate(self, sim, now, R):
        q3, q4, qf = sim.q3, sim.q4, sim.qf
        u3 = self._urgent_prefix(q3, now, self._thr3)
        u4 = self._urgent_prefix(q4, now, self._thr4)

        n3 = min(u3, R)
        n4 = min(u4, R - n3)
        nf = min(len(qf), R - n3 - n4)
        rem = R - n3 - n4 - nf
        # H_init: remaining NON-urgent initial patients, Level III before IV
        if rem > 0:
            add3 = min(len(q3) - n3, rem)
            n3 += add3
            rem -= add3
        if rem > 0:
            n4 += min(len(q4) - n4, rem)
        return _head(q3, n3, 0) + _head(q4, n4, 1) + _head(qf, nf, 2)


# ---------------------------------------------------------------------------
# 4. c-mu rule / WSEPT   --  WP2, OUR CONTRIBUTION (not in the paper)
# ---------------------------------------------------------------------------
class CMuPolicy(Policy):
    r"""Weighted Shortest Expected Processing Time (the c-mu rule).

    Classical result (Cox & Smith 1961; Buyukkoc et al. 1985): for a
    multi-class single-pool queue with linear holding costs c_l per unit
    waiting time, the policy that minimises expected total holding cost is to
    always serve the non-empty class with the largest index

        index_l = c_l * mu_l ,      mu_l = 1 / E[service time of class l].

    This is a *provably optimal* rule, structurally different from the paper's
    fixed-lookahead slack heuristic, which is why it is worth adding to the
    comparison.

    Classes and their parameters here
    ---------------------------------
      class            c_l          mu_l
      init Level III   1 / T_3      1 / E[TruncExp initial]
      init Level IV    1 / T_4      1 / E[TruncExp initial]
      follow-up        1 / T_f      1 / E[TruncExp follow]

    The delay weight ``c_l = 1 / T_l`` encodes "a minute of waiting hurts in
    inverse proportion to how much waiting that class can tolerate", which is
    the natural translation of a triage target into a holding cost.  T_f (the
    follow-up target) is not defined by the paper; see
    ``SimConfig.target_wait_follow`` -- run_03_wsept_policy.py sweeps it.

    Two modes
    ---------
    ``mode="static"`` -- the textbook c-mu rule.  Indices are constants, so the
        rule degenerates to a fixed priority order (with the default numbers:
        Level III initial > follow-up > Level IV initial).

    ``mode="gcmu"``   -- the GENERALISED c-mu rule (Van Mieghem 1995; Mandelbaum
        & Stolyar 2004), which is asymptotically optimal for *convex* delay
        costs.  With C_l(w) = (w / T_l)^2 the index becomes

            index_l(t) = C_l'(w_head) * mu_l = 2 * w_head / T_l^2 * mu_l

        i.e. it grows with how long the head-of-line patient has already
        waited.  This makes the rule delay-adaptive like SBP but derived from
        optimality theory rather than tuned by search -- and it needs NO
        parameters to be fitted at all.
    """
    key = "WSEPT"
    name = "c-mu / WSEPT"

    def __init__(self, mode: str = "static", target_follow: Optional[float] = None):
        if mode not in ("static", "gcmu"):
            raise ValueError("mode must be 'static' or 'gcmu'")
        self.mode = mode
        self._target_follow_override = target_follow
        self.key = "WSEPT" if mode == "static" else "GCMU"
        self.name = "c-mu / WSEPT" if mode == "static" else "Generalised c-mu (Gc-mu)"

    def bind(self, cfg):
        super().bind(cfg)
        # mu_l -- reciprocal of the *realised* (post-truncation) mean service
        # time, computed analytically, not estimated from the run.
        e_init = truncexp_mean(C.CONSULT_INITIAL_MEAN, C.CONSULT_INITIAL_LO,
                               C.CONSULT_INITIAL_HI)
        e_foll = truncexp_mean(C.CONSULT_FOLLOW_MEAN, C.CONSULT_FOLLOW_LO,
                               C.CONSULT_FOLLOW_HI)
        self.mu_init = 1.0 / e_init
        self.mu_follow = 1.0 / e_foll
        tf = self._target_follow_override or cfg.target_wait_follow
        self.t3 = self.T[C.LEVEL_III]
        self.t4 = self.T[C.LEVEL_IV]
        self.tf = tf
        # static indices  c_l * mu_l
        self.idx_static = (
            (1.0 / self.t3) * self.mu_init,
            (1.0 / self.t4) * self.mu_init,
            (1.0 / tf) * self.mu_follow,
        )
        # gcmu coefficients  (2 / T_l^2) * mu_l ; multiplied by w at run time
        self.idx_gcmu_coef = (
            2.0 * self.mu_init / (self.t3 ** 2),
            2.0 * self.mu_init / (self.t4 ** 2),
            2.0 * self.mu_follow / (tf ** 2),
        )

    def describe(self) -> str:
        i = self.idx_static
        return (f"{self.name}: mu_init={self.mu_init:.5f}/min, "
                f"mu_follow={self.mu_follow:.5f}/min, "
                f"T=({self.t3:g},{self.t4:g},{self.tf:g}), "
                f"static indices c*mu = (L3 {i[0]:.6f}, L4 {i[1]:.6f}, F {i[2]:.6f})")

    def allocate(self, sim, now, R):
        q3, q4, qf = sim.q3, sim.q4, sim.qf
        lens = (len(q3), len(q4), len(qf))
        dqs = (q3, q4, qf)
        plan: List[Tuple[int, Patient]] = []
        # cached iterators to look at the (taken[i])-th element cheaply
        heads: List[Optional[Patient]] = []
        iters = [iter(dq) for dq in dqs]
        for it, L in zip(iters, lens):
            heads.append(next(it) if L else None)

        for _ in range(R):
            best, best_idx = -1, -math.inf
            for cls in range(3):
                p = heads[cls]
                if p is None:
                    continue
                if self.mode == "static":
                    val = self.idx_static[cls]
                else:
                    w = now - p.queue_entry_time
                    val = self.idx_gcmu_coef[cls] * max(w, 0.0)
                    # An empty-handed tie at w = 0 would be arbitrary; break it
                    # with the static index so the rule stays well-defined.
                    if val <= 0.0:
                        val = 1e-12 * self.idx_static[cls]
                if val > best_idx:
                    best_idx, best = val, cls
            if best < 0:
                break
            plan.append((best, heads[best]))     # type: ignore[arg-type]
            heads[best] = next(iters[best], None)
        return plan


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------
def make_policy(key: str, **kw) -> Policy:
    """Factory used by every runner script and by the optimisers.

    ``make_policy("SBP", k1=13.1, k2=2.1)``
    """
    k = key.upper()
    if k == "IFP":
        return InitialFirstPolicy()
    if k == "ALT":
        return AlternatingPolicy()
    if k == "SBP":
        return SlackBasedPolicy(kw.get("k1", C.SBP_PAPER_OPTIMUM[0]),
                                kw.get("k2", C.SBP_PAPER_OPTIMUM[1]))
    if k in ("WSEPT", "CMU"):
        return CMuPolicy("static", kw.get("target_follow"))
    if k == "GCMU":
        return CMuPolicy("gcmu", kw.get("target_follow"))
    raise KeyError(f"unknown policy {key!r}")


#: Policies reproduced from the base paper.
PAPER_POLICIES = ("IFP", "ALT", "SBP")
#: Policies contributed by this project.
OUR_POLICIES = ("WSEPT", "GCMU")
ALL_POLICIES = PAPER_POLICIES + OUR_POLICIES
