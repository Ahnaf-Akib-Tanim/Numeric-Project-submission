"""
stats.py -- the statistical machinery of Sec 3.3.1 of the paper, plus the
variance-reduction analysis of WP5.

Contents
--------
  paired_t          paired t-test on the per-replication means (Table 5)
  cohens_d          effect size for paired data (Table 6)
  bonferroni        family-wise error control across the pairwise comparisons
  compare_all       run every pairwise comparison and assemble a table
  crn_efficiency    variance-reduction factor and the "replications needed"
                    calculation that quantifies what CRN buys
  reps_for_halfwidth  how many replications a target CI half-width needs

Everything is computed from ``scipy.stats`` primitives (t distribution CDF /
quantiles only) -- the test statistics themselves are formed here so that the
formulas are visible.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from itertools import combinations
from typing import Dict, List, Sequence, Tuple

import numpy as np
from scipy import stats as sps


# ---------------------------------------------------------------------------
# Basic summaries
# ---------------------------------------------------------------------------
def mean_ci(x: Sequence[float], alpha: float = 0.05) -> Tuple[float, float, float, float]:
    """(mean, sd, ci_lo, ci_hi) using the Student-t interval."""
    a = np.asarray(x, dtype=float)
    n = a.size
    m = float(a.mean())
    sd = float(a.std(ddof=1)) if n > 1 else 0.0
    if n < 2:
        return m, sd, m, m
    h = float(sps.t.ppf(1 - alpha / 2, n - 1) * sd / math.sqrt(n))
    return m, sd, m - h, m + h


# ---------------------------------------------------------------------------
# Paired t-test  (paper Table 5)
# ---------------------------------------------------------------------------
@dataclass
class PairedTest:
    a: str
    b: str
    n: int
    mean_a: float
    mean_b: float
    mean_diff: float          # mean(a) - mean(b)
    sd_diff: float
    t_stat: float
    p_value: float
    df: int
    ci_lo: float
    ci_hi: float
    cohens_d: float
    significant: bool = False
    alpha_used: float = 0.05

    def row(self):
        return [f"{self.a} vs {self.b}", f"{self.mean_diff:.4f}",
                f"{self.t_stat:.6f}", f"{self.p_value:.6e}",
                f"[{self.ci_lo:.3f}, {self.ci_hi:.3f}]",
                f"{self.cohens_d:.4f}", "Yes" if self.significant else "No"]


def paired_t(a: Sequence[float], b: Sequence[float],
             name_a: str = "A", name_b: str = "B",
             alpha: float = 0.05) -> PairedTest:
    r"""Paired t-test on two equal-length vectors of per-replication means.

        d_r   = a_r - b_r
        t     = mean(d) / (sd(d) / sqrt(n))          with n-1 degrees of freedom

    Cohen's d for PAIRED data is ``mean(d) / sd(d)`` -- the standardised mean
    difference of the *differences*, which is the effect size that matches a
    paired design.  (The paper reports values >1.5 for its three comparisons;
    see ``cohens_d_independent`` for the pooled-SD variant if an unpaired
    effect size is wanted instead.)
    """
    x = np.asarray(a, dtype=float)
    y = np.asarray(b, dtype=float)
    if x.size != y.size:
        raise ValueError("paired_t needs equal-length samples")
    d = x - y
    n = d.size
    md = float(d.mean())
    sd = float(d.std(ddof=1))
    se = sd / math.sqrt(n) if sd > 0 else 0.0
    t = md / se if se > 0 else math.inf * (1 if md > 0 else -1 if md < 0 else 0)
    p = float(2 * sps.t.sf(abs(t), n - 1)) if se > 0 else 0.0
    h = float(sps.t.ppf(1 - alpha / 2, n - 1) * se) if se > 0 else 0.0
    return PairedTest(
        a=name_a, b=name_b, n=n,
        mean_a=float(x.mean()), mean_b=float(y.mean()),
        mean_diff=md, sd_diff=sd, t_stat=float(t), p_value=p, df=n - 1,
        ci_lo=md - h, ci_hi=md + h,
        cohens_d=(md / sd) if sd > 0 else math.inf,
        alpha_used=alpha,
    )


def cohens_d_independent(a: Sequence[float], b: Sequence[float]) -> float:
    """Effect size with a pooled SD (the unpaired convention)."""
    x, y = np.asarray(a, float), np.asarray(b, float)
    n1, n2 = x.size, y.size
    s = math.sqrt(((n1 - 1) * x.var(ddof=1) + (n2 - 1) * y.var(ddof=1)) / (n1 + n2 - 2))
    return float((x.mean() - y.mean()) / s) if s > 0 else math.inf


def interpret_d(d: float) -> str:
    """Conventional labels used in the paper's Table 6."""
    a = abs(d)
    if a >= 2.5:
        return "Huge effect"
    if a >= 1.2:
        return "Very large effect"
    if a >= 0.8:
        return "Large effect"
    if a >= 0.5:
        return "Medium effect"
    if a >= 0.2:
        return "Small effect"
    return "Negligible"


# ---------------------------------------------------------------------------
# Multiple-comparison control
# ---------------------------------------------------------------------------
def bonferroni(alpha: float, n_comparisons: int) -> float:
    """alpha_adj = alpha / m  (paper: 0.05 / 3 = 0.0167)."""
    return alpha / max(1, n_comparisons)


def compare_all(series: Dict[str, Sequence[float]], alpha: float = 0.05,
                order: Sequence[str] = ()) -> List[PairedTest]:
    """Every pairwise paired t-test, Bonferroni-corrected as a family."""
    keys = list(order) if order else list(series.keys())
    pairs = list(combinations(keys, 2))
    a_adj = bonferroni(alpha, len(pairs))
    out = []
    for ka, kb in pairs:
        t = paired_t(series[ka], series[kb], ka, kb, alpha=a_adj)
        t.significant = t.p_value < a_adj
        t.alpha_used = a_adj
        out.append(t)
    return out


# ---------------------------------------------------------------------------
# WP5: what does CRN actually buy?
# ---------------------------------------------------------------------------
@dataclass
class CRNComparison:
    """Side-by-side of one pairwise comparison with and without CRN."""
    a: str
    b: str
    n: int
    diff_crn: float
    diff_ind: float
    var_crn: float
    var_ind: float
    hw_crn: float                 # 95% CI half-width of the mean difference
    hw_ind: float
    t_crn: float
    t_ind: float
    p_crn: float
    p_ind: float

    @property
    def variance_reduction(self) -> float:
        """1 - Var_CRN / Var_IND -- the fraction of variance removed."""
        return 1.0 - (self.var_crn / self.var_ind) if self.var_ind > 0 else 0.0

    @property
    def efficiency_gain(self) -> float:
        """Var_IND / Var_CRN.

        Because CI half-width shrinks as 1/sqrt(n), this ratio is exactly the
        factor by which the number of replications could be REDUCED while
        keeping the same precision.
        """
        return (self.var_ind / self.var_crn) if self.var_crn > 0 else math.inf

    @property
    def reps_equivalent(self) -> float:
        """Replications under CRN that match ``n`` independent replications."""
        return self.n / self.efficiency_gain if self.efficiency_gain > 0 else math.inf


def crn_efficiency(crn: Dict[str, Sequence[float]],
                   ind: Dict[str, Sequence[float]],
                   alpha: float = 0.05,
                   order: Sequence[str] = ()) -> List[CRNComparison]:
    r"""Quantify the variance reduction from Common Random Numbers.

    For a difference of two policy means,

        Var(A - B) = Var(A) + Var(B) - 2 Cov(A, B)

    With independent streams Cov = 0.  CRN induces a positive correlation
    between the two runs (they see the same patients), so the covariance term
    is positive and the variance of the DIFFERENCE falls -- while the variance
    of each individual estimator is unchanged.  That is the whole mechanism,
    and it is why CRN sharpens *comparisons* specifically.
    """
    keys = list(order) if order else list(crn.keys())
    out: List[CRNComparison] = []
    for ka, kb in combinations(keys, 2):
        dc = np.asarray(crn[ka], float) - np.asarray(crn[kb], float)
        di = np.asarray(ind[ka], float) - np.asarray(ind[kb], float)
        n = dc.size
        vc, vi = float(dc.var(ddof=1)), float(di.var(ddof=1))
        tq = float(sps.t.ppf(1 - alpha / 2, n - 1))
        hc = tq * math.sqrt(vc / n)
        hi = tq * math.sqrt(vi / n)
        tc = float(dc.mean() / math.sqrt(vc / n)) if vc > 0 else math.inf
        ti = float(di.mean() / math.sqrt(vi / n)) if vi > 0 else math.inf
        out.append(CRNComparison(
            a=ka, b=kb, n=n,
            diff_crn=float(dc.mean()), diff_ind=float(di.mean()),
            var_crn=vc, var_ind=vi, hw_crn=hc, hw_ind=hi,
            t_crn=tc, t_ind=ti,
            p_crn=float(2 * sps.t.sf(abs(tc), n - 1)) if vc > 0 else 0.0,
            p_ind=float(2 * sps.t.sf(abs(ti), n - 1)) if vi > 0 else 0.0,
        ))
    return out


def reps_for_halfwidth(sd: float, halfwidth: float, alpha: float = 0.05,
                       max_n: int = 1_000_000) -> int:
    """Smallest n with  t_{1-a/2, n-1} * sd / sqrt(n) <= halfwidth.

    Solved by iteration because the t quantile itself depends on n.
    """
    if halfwidth <= 0 or sd <= 0:
        return 2
    n = 2
    while n < max_n:
        h = float(sps.t.ppf(1 - alpha / 2, n - 1)) * sd / math.sqrt(n)
        if h <= halfwidth:
            return n
        # jump ahead using the normal approximation, then refine
        z = float(sps.norm.ppf(1 - alpha / 2))
        guess = int(math.ceil((z * sd / halfwidth) ** 2))
        n = max(n + 1, min(guess, n * 2))
    return max_n


def correlation(a: Sequence[float], b: Sequence[float]) -> float:
    """Pearson correlation between two paired replication series."""
    x, y = np.asarray(a, float), np.asarray(b, float)
    if x.std() == 0 or y.std() == 0:
        return 0.0
    return float(np.corrcoef(x, y)[0, 1])
