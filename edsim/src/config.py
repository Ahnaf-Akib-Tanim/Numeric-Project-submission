"""
config.py -- Single source of truth for every numeric parameter of the model.

EVERY number in this file is traceable to the base paper:

    Lv, W.; Liu, R.; Yan, F.; Wang, Y. (2026)
    "Discrete Event Simulation-Based Analysis and Optimization of Emergency
     Patient Scheduling Strategies", Healthcare 14(1), 99.
     https://doi.org/10.3390/healthcare14010099

Citations of the form [Sec 3.1] / [Table 2] refer to that paper.  Parameters
that the paper does NOT specify and that we had to choose ourselves are marked
with  ``OUR CHOICE``  and carry a justification.  Nothing is a magic number.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Dict, List, Tuple

# ---------------------------------------------------------------------------
# 1. TIME BASE
# ---------------------------------------------------------------------------
MINUTES_PER_HOUR = 60
HOURS_PER_DAY = 24
MINUTES_PER_DAY = MINUTES_PER_HOUR * HOURS_PER_DAY          # 1440   [Eq. 1]
DAYS_PER_WEEK = 7
WEEK_MINUTES = MINUTES_PER_DAY * DAYS_PER_WEEK              # 10080  [Sec 2.2.1]

# ---------------------------------------------------------------------------
# 2. ARRIVAL PROCESS -- Table 2 of the paper
#    lambda_{d,h} = mean number of Level-III + Level-IV arrivals per hour,
#    indexed [day][hour] with day 0 = Monday ... day 6 = Sunday.
#    Used by a non-homogeneous Poisson process with a weekly cycle [Eq. 1, 2].
# ---------------------------------------------------------------------------
# Table 2 is printed hour-major (rows = hours, columns = Mon..Sun).  We store
# it transposed as [day][hour] because the simulator indexes by day first.
_TABLE2_BY_HOUR: List[Tuple[float, ...]] = [
    # Mon    Tue    Wed    Thu    Fri    Sat    Sun          hour
    (7.84,   7.50,  7.51,  7.49,  7.49,  7.13,  7.12),   # 0-1
    (5.79,   5.37,  5.38,  5.35,  5.36,  5.07,  5.06),   # 1-2
    (4.94,   4.50,  4.51,  4.50,  4.49,  4.31,  4.32),   # 2-3
    (3.70,   3.33,  3.34,  3.30,  3.34,  3.11,  3.12),   # 3-4
    (2.19,   1.83,  1.81,  1.80,  1.82,  1.68,  1.68),   # 4-5
    (4.33,   3.58,  3.59,  3.54,  3.55,  3.21,  3.19),   # 5-6
    (6.78,   6.39,  6.40,  6.37,  6.36,  6.08,  6.07),   # 6-7
    (8.83,   8.23,  8.17,  8.18,  8.25,  7.98,  7.97),   # 7-8
    (15.23, 14.95, 14.93, 14.90, 14.90, 14.49, 14.48),   # 8-9
    (21.59, 21.26, 21.24, 21.23, 21.27, 20.64, 20.61),   # 9-10
    (21.71, 21.44, 21.43, 21.45, 21.43, 20.65, 20.64),   # 10-11
    (17.53, 17.11, 17.12, 17.11, 17.10, 16.59, 16.51),   # 11-12
    (15.55, 15.18, 15.17, 15.18, 15.17, 14.73, 14.72),   # 12-13
    (18.26, 17.93, 17.94, 17.92, 17.92, 17.43, 17.41),   # 13-14
    (20.87, 20.76, 20.77, 20.75, 20.77, 19.97, 19.96),   # 14-15
    (18.28, 18.14, 18.15, 18.13, 18.13, 17.33, 17.35),   # 15-16
    (17.31, 17.14, 17.15, 17.13, 17.14, 16.47, 16.45),   # 16-17
    (16.28, 16.10, 16.11, 16.08, 16.10, 15.38, 15.39),   # 17-18
    (16.87, 16.46, 16.44, 16.43, 16.44, 15.97, 15.98),   # 18-19
    (22.61, 22.47, 22.46, 22.43, 22.44, 21.64, 21.63),   # 19-20
    (23.05, 22.81, 22.80, 22.79, 22.79, 22.44, 22.43),   # 20-21
    (17.53, 17.23, 17.24, 17.21, 17.22, 16.75, 16.74),   # 21-22
    (12.49, 12.31, 12.30, 12.29, 12.29, 11.83, 11.82),   # 22-23
    (7.52,   7.23,  7.21,  7.22,  7.24,  7.03,  7.02),   # 23-0
]

# ARRIVAL_RATES[d][h]  (patients / hour)
ARRIVAL_RATES: Tuple[Tuple[float, ...], ...] = tuple(
    tuple(_TABLE2_BY_HOUR[h][d] for h in range(HOURS_PER_DAY))
    for d in range(DAYS_PER_WEEK)
)
DAY_NAMES = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")

#: Peak hourly rate over the whole week -- the majorising constant used by the
#: thinning algorithm for the non-homogeneous Poisson process.
LAMBDA_MAX = max(max(day) for day in ARRIVAL_RATES)          # 23.05 /h (Mon 20-21)

# ---------------------------------------------------------------------------
# 3. TRIAGE -- [Sec 3.1]
#    "Level III and Level IV patients accounted for 25% and 75% of arrivals."
#    "target waiting times were set at 30 min for Level III and 120 min for IV"
# ---------------------------------------------------------------------------
LEVEL_III = 3
LEVEL_IV = 4
TRIAGE_LEVELS = (LEVEL_III, LEVEL_IV)
P_LEVEL_III = 0.25
P_LEVEL_IV = 0.75
TARGET_WAIT: Dict[int, float] = {LEVEL_III: 30.0, LEVEL_IV: 120.0}   # T_l, minutes

#: Minimum service level used as the optimisation constraint [Eq. 32].
#: The paper writes SL_l >= SL_l^min but never prints the numeric value; the
#: reported optimum attains SL = 100%, so any value <= 1 is feasible there.
#: OUR CHOICE: 0.95 -- a standard ED service-level target, and strict enough
#: that the penalty term in WP3 actually bites for bad (k1,k2).
SL_MIN: Dict[int, float] = {LEVEL_III: 0.95, LEVEL_IV: 0.95}

# ---------------------------------------------------------------------------
# 4. CONSULTATION SERVICE TIMES -- [Sec 2.1.2, Sec 3.1]
#    T_i^(k) ~ TruncExp(lambda_k, [a_k, b_k]),  k = 1 initial, 2 follow-up.
#    "means of 9 and 15 min ... bounds 5-15 min for initial and 5-25 for
#     follow-up consultation."
#    => lambda_1 = 1/9, [5,15];  lambda_2 = 1/15, [5,25].
#    (The *realised* means after truncation are 9.09 and 12.84 min; see
#     src/distributions.py::truncexp_mean.)
# ---------------------------------------------------------------------------
CONSULT_INITIAL_MEAN = 9.0     # 1/lambda_1
CONSULT_INITIAL_LO = 5.0       # a_1
CONSULT_INITIAL_HI = 15.0      # b_1
CONSULT_FOLLOW_MEAN = 15.0     # 1/lambda_2
CONSULT_FOLLOW_LO = 5.0        # a_2
CONSULT_FOLLOW_HI = 25.0       # b_2

#: Robustness check [Sec 3.4.3]: truncated *lognormal* with the same nominal
#: means, mu = ln(m) - sigma^2/2, sigma = 0.3.
LOGNORMAL_SIGMA = 0.3

# ---------------------------------------------------------------------------
# 5. DIAGNOSTIC EXAMINATIONS -- [Sec 2.1.3, Sec 3.1, Table 9]
#    "Among initial patients, 60% required at least one diagnostic test, with
#     independent probabilities of undergoing laboratory, B-ultrasound, X-ray
#     and CT set at 92%, 22%, 29% and 55%."
#    Durations tau_j and report delays delta_j from Sec 3.1.
#    Exams are started in DESCENDING order of report delay delta_j [Sec 2.1.3].
# ---------------------------------------------------------------------------
P_NEEDS_EXAM = 0.60


@dataclass(frozen=True)
class Modality:
    """One diagnostic device type j."""
    name: str
    prob: float          # p_j     : P(exam j | patient needs exams)
    duration: float      # tau_j   : machine occupancy, minutes
    report_delay: float  # delta_j : result-reporting delay, minutes
    capacity: int        # C_j     : number of parallel devices


#: Table 9 reports "Available Time = 10080 min" per equipment for a 1-week run,
#: i.e. exactly one device-week per modality  ->  capacity C_j = 1.
MODALITIES: Tuple[Modality, ...] = (
    Modality("LABORATORY", prob=0.92, duration=1.19, report_delay=20.0, capacity=1),
    Modality("XRAY",       prob=0.29, duration=3.99, report_delay=30.0, capacity=1),
    Modality("CT",         prob=0.55, duration=2.45, report_delay=30.0, capacity=1),
    Modality("ULTRASOUND", prob=0.22, duration=6.58, report_delay=0.0,  capacity=1),
)

# ---------------------------------------------------------------------------
# 6. PHYSICIAN SHIFTS -- [Sec 3.1]
#    "three shifts per day: 07:00-15:00 with 5 physicians, 15:00-22:00 with 5,
#     22:00-07:00 with 3."
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class Shift:
    name: str
    start_hour: int     # inclusive
    end_hour: int       # exclusive; may wrap past midnight
    physicians: int


BASELINE_SHIFTS: Tuple[Shift, ...] = (
    Shift("MORNING",   7, 15, 5),
    Shift("AFTERNOON", 15, 22, 5),
    Shift("NIGHT",     22,  7, 3),   # wraps midnight
)

#: Table 10 -- the seven staffing scenarios of the paper's sensitivity study.
STAFFING_SCENARIOS: Dict[str, Tuple[int, int, int]] = {
    "S0": (5, 5, 3),   # baseline
    "S1": (5, 5, 4),
    "S2": (5, 5, 5),
    "S3": (5, 6, 5),
    "S4": (5, 7, 5),
    "S5": (6, 7, 5),
    "S6": (7, 7, 5),
}

# ---------------------------------------------------------------------------
# 7. SLACK-BASED POLICY THRESHOLDS -- [Sec 3.2, Tables 3-4]
# ---------------------------------------------------------------------------
SBP_PAPER_OPTIMUM = (13.1, 2.1)     # (k1, k2) -- the paper's fine-grid optimum
SBP_COARSE_OPTIMUM = (13.0, 2.0)    # the paper's coarse-grid optimum

#: Search box for the grid search / Nelder-Mead.  The paper does not print its
#: coarse-grid bounds, but Table 3 lists winners at k1 = 26 and k2 = 40, so the
#: box must cover at least that.  OUR CHOICE: k1 in [0,30], k2 in [0,40].
GRID_K1_RANGE = (0.0, 30.0)
GRID_K2_RANGE = (0.0, 40.0)
GRID_COARSE_STEP = 1.0
GRID_FINE_STEP = 0.1
GRID_FINE_K1_RANGE = (12.0, 14.0)   # [Sec 3.2] "range from 12 to 14"
GRID_FINE_K2_RANGE = (1.0, 3.0)     # [Sec 3.2] "and 1 to 3"

# ---------------------------------------------------------------------------
# 8. EXPERIMENT DEFAULTS
# ---------------------------------------------------------------------------
N_REPLICATIONS = 100            # [Sec 2.2.1] "100 independent replications"
HORIZON_MINUTES = WEEK_MINUTES  # "each run representing one full operational week"
BASE_SEED = 20250402            # OUR CHOICE: fixed so every result is reproducible
ALPHA = 0.05                    # [Sec 3.3.1] significance level before correction

# ---------------------------------------------------------------------------
# 9. COST MODEL for WP4 -- not in the paper; OUR CONTRIBUTION.
#    C(R, k1, k2) = alpha * physician-hours
#                 + beta  * total patient waiting-minutes
#                 + gamma * SLA-violation penalty
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class CostParams:
    """Economic weights for the staffing objective (WP4).

    Defaults are stated in *cost units* that we interpret as USD-equivalents so
    the trade-off is transparent:

    alpha  : fully-loaded cost of one physician-hour.  OUR CHOICE 120 -- an ED
             attending at ~USD 250k/yr loaded over ~2080 h/yr is ~120/h.
    beta   : societal/clinical cost of one patient-waiting-minute.  OUR CHOICE
             0.50 -- i.e. one patient-hour of waiting is valued at 30 units.
    gamma  : penalty per patient whose wait exceeds their triage target T_l.
             OUR CHOICE 50 -- a deliberate step penalty so that an SLA breach
             costs far more than the raw waiting minutes that produced it.

    All three are exposed on the CLI of scripts/run_05_staffing_cost.py so the
    sensitivity of the recommendation to these assumptions can be shown.
    """
    alpha_physician_hour: float = 120.0
    beta_wait_minute: float = 0.50
    gamma_sla_violation: float = 50.0


DEFAULT_COST = CostParams()

#: Integer search space for staffing (WP4): physicians per shift.
STAFFING_SEARCH_RANGE = (2, 8)   # inclusive, per the proposal ("2-8 per shift")

# ---------------------------------------------------------------------------
# 10. THE RUN-LEVEL CONFIGURATION OBJECT
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class SimConfig:
    """Everything one simulation replication needs.  Immutable; use
    ``dataclasses.replace(cfg, ...)`` or :meth:`with_` to derive variants."""

    horizon: float = HORIZON_MINUTES
    shifts: Tuple[Shift, ...] = BASELINE_SHIFTS
    arrival_scale: float = 1.0          # multiplies every lambda_{d,h}  [Sec 3.4.1]
    service_dist: str = "truncexp"      # or "trunclognormal"           [Sec 3.4.3]
    p_needs_exam: float = P_NEEDS_EXAM
    #: The paper says 60% of initial patients need AT LEAST ONE test, then
    #: gives independent per-modality probabilities that can jointly select
    #: none (probability 1.99%).  True = resample so "at least one" holds
    #: exactly; False = such a patient is simply discharged without exams.
    exam_require_at_least_one: bool = True
    modalities: Tuple[Modality, ...] = MODALITIES
    p_level_iii: float = P_LEVEL_III
    target_wait: Tuple[Tuple[int, float], ...] = ((LEVEL_III, 30.0), (LEVEL_IV, 120.0))
    #: Follow-up patients have no target in the paper.  OUR CHOICE for the
    #: cmu-rule (WP2) only: 60 min, the midpoint of T_III and T_IV.  Sensitivity
    #: to this value is reported by scripts/run_03_wsept_policy.py.
    target_wait_follow: float = 60.0

    def targets(self) -> Dict[int, float]:
        return dict(self.target_wait)

    def stream_key(self) -> tuple:
        """Identity of the EXOGENOUS randomness this config implies.

        The patient stream depends only on the arrival process, the triage mix,
        the service-time distribution and the examination model.  Staffing
        levels and waiting-time targets change how patients are *served*, never
        who arrives or what they need.  Caching streams under this reduced key
        means the staffing sweep (WP4) and the target sweeps re-use one set of
        sampled weeks instead of re-sampling for every roster -- which is both
        much faster and a second, structural guarantee of common random numbers
        across those experiments.
        """
        return (self.horizon, self.arrival_scale, self.service_dist,
                self.p_needs_exam, self.exam_require_at_least_one,
                self.modalities, self.p_level_iii)

    def with_(self, **kw) -> "SimConfig":
        return replace(self, **kw)

    def staffing_vector(self) -> Tuple[int, ...]:
        return tuple(s.physicians for s in self.shifts)


def shifts_from_vector(vec) -> Tuple[Shift, ...]:
    """Build a shift tuple (M, A, N) from an integer staffing vector."""
    m, a, n = vec
    return (
        Shift("MORNING",   7, 15, int(m)),
        Shift("AFTERNOON", 15, 22, int(a)),
        Shift("NIGHT",     22,  7, int(n)),
    )


DEFAULT_CONFIG = SimConfig()

# ---------------------------------------------------------------------------
# 11. PAPER'S PUBLISHED RESULTS -- used as validation targets by WP1.
# ---------------------------------------------------------------------------
PAPER_RESULTS = {
    "IFP": {"wait_total": 46.26, "wait_l3": 44.14, "wait_l4": None,
            "util": 0.8543, "util_sd": 0.0207,
            "sl3": 1.0000, "sl4": 1.0000, "ci": (43.76, 48.76)},
    "ALT": {"wait_total": 37.88, "wait_l3": 6.82, "wait_l4": None,
            "util": 0.8541, "util_sd": 0.0208,
            "sl3": 0.9808, "sl4": 0.8929, "ci": None},
    "SBP": {"wait_total": 35.25, "wait_l3": 10.48, "wait_l4": 43.89,
            "util": 0.8498, "util_sd": 0.0206,
            "sl3": 1.0000, "sl4": 1.0000, "ci": (34.06, 36.45)},
}

PAPER_TTESTS = {                      # Table 5
    ("IFP", "ALT"): {"mean_diff": 8.1000,  "t": 20.099377, "p": 1.015178e-36},
    ("IFP", "SBP"): {"mean_diff": 10.5521, "t": 28.244962, "p": 3.580432e-49},
    ("ALT", "SBP"): {"mean_diff": 2.4521,  "t": 15.436824, "p": 4.208457e-28},
}
PAPER_COHEN_D = {                     # Table 6
    ("IFP", "ALT"): 2.0099,
    ("IFP", "SBP"): 2.8245,
    ("ALT", "SBP"): 1.5437,
}
PAPER_EQUIPMENT = {                   # Table 9
    "XRAY":       {"n": 389,  "dur": 3.99, "util": 0.1520},
    "CT":         {"n": 715,  "dur": 2.45, "util": 0.1764},
    "LABORATORY": {"n": 1228, "dur": 1.19, "util": 0.1436},
    "ULTRASOUND": {"n": 266,  "dur": 6.58, "util": 0.1903},
}
