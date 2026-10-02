"""
metrics.py -- STATISTICAL OUTPUT MODULE  (Figure 2, box 5 of the paper).

Turns the terminal state of one :class:`~src.engine.Simulation` into the KPI
set of the paper (Eqs. 24-30) plus a few diagnostics of our own.

--------------------------------------------------------------------------
Which "waiting time" does the paper report?  (an important reading decision)
--------------------------------------------------------------------------
The paper reports, for the SBP optimum, Level III = 10.48 min, Level IV =
43.89 min and "all patients" = 35.25 min.  Note that

        0.25 * 10.48 + 0.75 * 43.89 = 35.54  ~=  35.25                (*)

i.e. the headline number is the *patient-weighted* mean of the two per-level
numbers, with the 25/75 triage mix.  The same identity holds for IFP
(0.25*44.14 + 0.75*46.97 = 46.26) and ALT.  It does NOT hold if the per-level
figure is only the initial-consultation wait -- under IFP, Level III initial
consultations have absolute priority and could never average 44 min.

We therefore report, as the headline metric:

    W_l      = mean over Level-l patients of  (initial wait + follow-up wait)
    W_total  = mean over ALL patients of the same quantity

which reproduces (*) exactly and is also the operationally meaningful quantity
("how long did this patient spend waiting in total?").  The per-consultation
averages of Eqs. (24)-(26) are computed as well and reported alongside, so
nothing is hidden.

Service level (Eqs. 27-28) uses the INITIAL-consultation wait only, because the
triage target T_l is a time-to-be-seen target and because that is the only
reading under which the paper's IFP service level of 100% is attainable.

Censoring: like the paper, averages are taken over consultations that COMPLETED
within the simulated week; ``n_unfinished`` reports how many patients were left
in the system so that any censoring bias is visible rather than silent.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

import numpy as np

from . import config as C


@dataclass
class RunResult:
    """KPIs of a single replication."""

    policy: str
    seed: int

    # ---- headline: per-PATIENT total waiting time (initial + follow-up) ----
    wait_total: float = 0.0
    wait_l3: float = 0.0
    wait_l4: float = 0.0

    # ---- c-weighted holding cost (the objective the c-mu rule optimises) ---
    #   holding_cost = mean_i  w_i / T_{level(i)}
    # i.e. waiting measured in units of the patient's own clinical tolerance.
    # Reported because comparing WSEPT on raw mean wait alone would be unfair:
    # the c-mu rule is optimal for THIS objective, not for the unweighted mean.
    holding_cost: float = 0.0

    # ---- per-CONSULTATION waits, Eqs. (24)-(26) ---------------------------
    wait_init_l3: float = 0.0
    wait_init_l4: float = 0.0
    wait_init_all: float = 0.0
    wait_follow: float = 0.0
    wait_per_consult: float = 0.0

    # ---- service level, Eqs. (27)-(28) ------------------------------------
    delay_rate_l3: float = 0.0
    delay_rate_l4: float = 0.0
    sl_l3: float = 1.0
    sl_l4: float = 1.0

    # ---- utilisation, Eqs. (29)-(30) --------------------------------------
    physician_util: float = 0.0
    device_stats: Dict[str, dict] = field(default_factory=dict)

    # ---- volumes / diagnostics --------------------------------------------
    n_arrivals: int = 0
    n_initial_done: int = 0
    n_follow_done: int = 0
    n_pathway_done: int = 0
    n_unfinished: int = 0
    q_end_init3: int = 0
    q_end_init4: int = 0
    q_end_follow: int = 0
    n_events: int = 0
    max_queue_len: int = 0

    # ---- optional raw data -------------------------------------------------
    raw_total_wait: Optional[np.ndarray] = None
    raw_init_wait_l3: Optional[np.ndarray] = None
    raw_init_wait_l4: Optional[np.ndarray] = None
    queue_history: Optional[List] = None

    def drop_raw(self) -> "RunResult":
        self.raw_total_wait = None
        self.raw_init_wait_l3 = None
        self.raw_init_wait_l4 = None
        self.queue_history = None
        return self

    def as_row(self) -> dict:
        """Flat dict for pandas."""
        d = {k: v for k, v in self.__dict__.items()
             if not k.startswith("raw_") and k not in ("device_stats", "queue_history")}
        for name, st in self.device_stats.items():
            d[f"util_{name.lower()}"] = st["utilisation"]
            d[f"nexams_{name.lower()}"] = st["n_exams"]
        return d


def _safe_mean(a: List[float]) -> float:
    return float(np.mean(a)) if a else 0.0


def collect(sim, keep_raw: bool = False) -> RunResult:
    """Build a :class:`RunResult` from a finished :class:`Simulation`."""
    cfg = sim.cfg
    targets = cfg.targets()

    tot_all: List[float] = []
    tot_l3: List[float] = []
    tot_l4: List[float] = []
    hold: List[float] = []
    init_l3: List[float] = []
    init_l4: List[float] = []
    foll: List[float] = []

    n_initial_done = n_follow_done = n_pathway_done = 0
    viol3 = viol4 = 0

    for p in sim.patients:
        if p.completed_initial:
            n_initial_done += 1
            if p.level == C.LEVEL_III:
                init_l3.append(p.wait_initial)
                if p.wait_initial > targets[C.LEVEL_III]:
                    viol3 += 1
            else:
                init_l4.append(p.wait_initial)
                if p.wait_initial > targets[C.LEVEL_IV]:
                    viol4 += 1
        if p.completed_follow:
            n_follow_done += 1
            foll.append(p.wait_follow)

        # patient-level total wait, only for a COMPLETED pathway
        done = p.completed_initial and (p.completed_follow or not p.needs_exam)
        if done:
            n_pathway_done += 1
            w = p.wait_initial + (p.wait_follow if p.needs_exam else 0.0)
            tot_all.append(w)
            (tot_l3 if p.level == C.LEVEL_III else tot_l4).append(w)
            hold.append(w / targets[p.level])

    n_unfinished = len(sim.patients) - n_pathway_done

    per_consult_sum = sum(init_l3) + sum(init_l4) + sum(foll)
    per_consult_n = len(init_l3) + len(init_l4) + len(foll)

    res = RunResult(
        policy=sim.policy.key,
        seed=-1,
        wait_total=_safe_mean(tot_all),
        wait_l3=_safe_mean(tot_l3),
        wait_l4=_safe_mean(tot_l4),
        holding_cost=_safe_mean(hold),
        wait_init_l3=_safe_mean(init_l3),
        wait_init_l4=_safe_mean(init_l4),
        wait_init_all=_safe_mean(init_l3 + init_l4),
        wait_follow=_safe_mean(foll),
        wait_per_consult=(per_consult_sum / per_consult_n) if per_consult_n else 0.0,
        delay_rate_l3=(viol3 / len(init_l3)) if init_l3 else 0.0,
        delay_rate_l4=(viol4 / len(init_l4)) if init_l4 else 0.0,
        sl_l3=1.0 - ((viol3 / len(init_l3)) if init_l3 else 0.0),
        sl_l4=1.0 - ((viol4 / len(init_l4)) if init_l4 else 0.0),
        physician_util=sim.pool.utilisation,
        device_stats=sim.bank.summary(cfg.horizon),
        n_arrivals=len(sim.patients),
        n_initial_done=n_initial_done,
        n_follow_done=n_follow_done,
        n_pathway_done=n_pathway_done,
        n_unfinished=n_unfinished,
        q_end_init3=len(sim.q3),
        q_end_init4=len(sim.q4),
        q_end_follow=len(sim.qf),
        n_events=sim.n_events,
    )
    if keep_raw:
        res.raw_total_wait = np.asarray(tot_all)
        res.raw_init_wait_l3 = np.asarray(init_l3)
        res.raw_init_wait_l4 = np.asarray(init_l4)
    return res


# ---------------------------------------------------------------------------
# Aggregation across replications
# ---------------------------------------------------------------------------
SUMMARY_FIELDS = (
    "wait_total", "wait_l3", "wait_l4", "holding_cost",
    "wait_init_l3", "wait_init_l4", "wait_init_all", "wait_follow",
    "delay_rate_l3", "delay_rate_l4", "sl_l3", "sl_l4",
    "physician_util", "n_arrivals", "n_pathway_done", "n_unfinished",
)


def aggregate(results: List[RunResult]) -> Dict[str, Dict[str, float]]:
    """mean / sd / 95% CI half-width for every summary field."""
    out: Dict[str, Dict[str, float]] = {}
    n = len(results)
    for f in SUMMARY_FIELDS:
        vals = np.array([getattr(r, f) for r in results], dtype=float)
        mean = float(vals.mean())
        sd = float(vals.std(ddof=1)) if n > 1 else 0.0
        se = sd / np.sqrt(n) if n > 1 else 0.0
        # Student-t 95% half-width
        from scipy import stats as sps
        half = float(sps.t.ppf(0.975, n - 1) * se) if n > 1 else 0.0
        out[f] = {"mean": mean, "sd": sd, "se": se,
                  "ci_lo": mean - half, "ci_hi": mean + half,
                  "min": float(vals.min()), "max": float(vals.max()),
                  "median": float(np.median(vals))}
    return out


def device_table(results: List[RunResult]) -> Dict[str, Dict[str, float]]:
    """Average the per-modality equipment statistics across replications."""
    if not results:
        return {}
    names = list(results[0].device_stats.keys())
    out = {}
    for nm in names:
        out[nm] = {
            "n_exams": float(np.mean([r.device_stats[nm]["n_exams"] for r in results])),
            "mean_duration": float(np.mean([r.device_stats[nm]["mean_duration"] for r in results])),
            "total_duration": float(np.mean([r.device_stats[nm]["total_duration"] for r in results])),
            "available_minutes": results[0].device_stats[nm]["available_minutes"],
            "utilisation": float(np.mean([r.device_stats[nm]["utilisation"] for r in results])),
            "utilisation_sd": float(np.std([r.device_stats[nm]["utilisation"] for r in results], ddof=1)) if len(results) > 1 else 0.0,
            "mean_queue_delay": float(np.mean([r.device_stats[nm]["mean_queue_delay"] for r in results])),
        }
    return out
