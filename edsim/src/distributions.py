"""
distributions.py -- Random-variate generation by *inverse-CDF sampling*.

Only elementary uniforms are consumed, one uniform per variate.  This matters:
because every variate is a deterministic function of exactly one uniform, the
Common Random Numbers scheme in WP5 (src/rng.py) can hand identical uniform
streams to different scheduling policies and be certain that every patient in
every policy's run gets *bit-identical* service times.

Implemented:
  * truncated exponential      TruncExp(lambda, [a, b])   -- baseline model
  * truncated lognormal        TruncLN(mu, sigma, [a, b]) -- robustness study
  * NHPP arrival times via Lewis-Shedler thinning         -- see arrivals.py
"""
from __future__ import annotations

import math
from typing import Sequence

# ---------------------------------------------------------------------------
# Truncated exponential
# ---------------------------------------------------------------------------
# If X ~ Exp(lambda) conditioned on a <= X <= b, then
#     F(x) = (e^{-lambda a} - e^{-lambda x}) / (e^{-lambda a} - e^{-lambda b})
# and inverting F(x) = u gives
#     x = -(1/lambda) * ln( e^{-lambda a} - u * (e^{-lambda a} - e^{-lambda b}) )
# ---------------------------------------------------------------------------


def truncexp_ppf(u: float, mean: float, lo: float, hi: float) -> float:
    """Inverse CDF of TruncExp(lambda = 1/mean) on [lo, hi].

    Parameters
    ----------
    u    : uniform(0,1) variate
    mean : 1/lambda -- the *untruncated* exponential mean (9 or 15 in the paper)
    lo, hi : truncation bounds a_k, b_k
    """
    lam = 1.0 / mean
    ea = math.exp(-lam * lo)
    eb = math.exp(-lam * hi)
    return -math.log(ea - u * (ea - eb)) / lam


def truncexp_mean(mean: float, lo: float, hi: float) -> float:
    """Analytic mean of TruncExp(1/mean, [lo, hi]).

    E[X] = a + 1/lam - (b-a) * e^{-lam (b-a)} / (1 - e^{-lam (b-a)})

    Used by the cmu-rule (WP2), which needs mu_l = 1 / E[service time], and by
    the load calculation printed in run_01_validate_paper.py.
    """
    lam = 1.0 / mean
    d = hi - lo
    z = math.exp(-lam * d)
    return lo + 1.0 / lam - d * z / (1.0 - z)


# ---------------------------------------------------------------------------
# Truncated lognormal  [paper Sec 3.4.3]
# ---------------------------------------------------------------------------
def _norm_cdf(x: float) -> float:
    return 0.5 * math.erfc(-x / math.sqrt(2.0))


def _norm_ppf(p: float) -> float:
    """Acklam's rational approximation to the standard normal quantile.

    Max relative error ~1.15e-9 -- far tighter than anything the simulation
    resolves, and it avoids a SciPy call inside the innermost sampling loop.
    """
    if p <= 0.0:
        return -math.inf
    if p >= 1.0:
        return math.inf
    a = (-3.969683028665376e+01, 2.209460984245205e+02, -2.759285104469687e+02,
         1.383577518672690e+02, -3.066479806614716e+01, 2.506628277459239e+00)
    b = (-5.447609879822406e+01, 1.615858368580409e+02, -1.556989798598866e+02,
         6.680131188771972e+01, -1.328068155288572e+01)
    c = (-7.784894002430293e-03, -3.223964580411365e-01, -2.400758277161838e+00,
         -2.549732539343734e+00, 4.374664141464968e+00, 2.938163982698783e+00)
    d = (7.784695709041462e-03, 3.224671290700398e-01, 2.445134137142996e+00,
         3.754408661907416e+00)
    plow, phigh = 0.02425, 1.0 - 0.02425
    if p < plow:
        q = math.sqrt(-2.0 * math.log(p))
        return (((((c[0]*q + c[1])*q + c[2])*q + c[3])*q + c[4])*q + c[5]) / \
               ((((d[0]*q + d[1])*q + d[2])*q + d[3])*q + 1.0)
    if p > phigh:
        q = math.sqrt(-2.0 * math.log(1.0 - p))
        return -(((((c[0]*q + c[1])*q + c[2])*q + c[3])*q + c[4])*q + c[5]) / \
                ((((d[0]*q + d[1])*q + d[2])*q + d[3])*q + 1.0)
    q = p - 0.5
    r = q * q
    return (((((a[0]*r + a[1])*r + a[2])*r + a[3])*r + a[4])*r + a[5]) * q / \
           (((((b[0]*r + b[1])*r + b[2])*r + b[3])*r + b[4])*r + 1.0)


def trunclognormal_ppf(u: float, mean: float, sigma: float,
                       lo: float, hi: float) -> float:
    """Inverse CDF of a lognormal truncated to [lo, hi].

    Following the paper's Sec 3.4.3 calibration, the underlying normal has
    ``mu = ln(mean) - sigma^2 / 2`` so that the *untruncated* lognormal mean is
    exactly ``mean``.
    """
    mu = math.log(mean) - 0.5 * sigma * sigma
    za = (math.log(lo) - mu) / sigma
    zb = (math.log(hi) - mu) / sigma
    fa, fb = _norm_cdf(za), _norm_cdf(zb)
    z = _norm_ppf(fa + u * (fb - fa))
    return math.exp(mu + sigma * z)


# ---------------------------------------------------------------------------
# Dispatcher used by the patient-stream generator
# ---------------------------------------------------------------------------
def service_ppf(u: float, kind: str, dist: str,
                mean: float, lo: float, hi: float, sigma: float) -> float:
    """Return one consultation duration from uniform ``u``.

    ``dist`` is ``"truncexp"`` (baseline) or ``"trunclognormal"`` (robustness).
    ``kind`` is only carried for readability/debugging.
    """
    if dist == "truncexp":
        return truncexp_ppf(u, mean, lo, hi)
    if dist == "trunclognormal":
        return trunclognormal_ppf(u, mean, sigma, lo, hi)
    raise ValueError(f"unknown service distribution {dist!r} (kind={kind})")


# ---------------------------------------------------------------------------
# Small helpers used in reporting
# ---------------------------------------------------------------------------
def empirical_mean(xs: Sequence[float]) -> float:
    return sum(xs) / len(xs) if xs else 0.0
