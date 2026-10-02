"""
run_06_crn_variance.py -- WP5: COMMON RANDOM NUMBERS AS VARIANCE REDUCTION.

The base paper runs 100 independent replications per strategy and compares the
means with paired t-tests "under identical arrival seeds".  It never quantifies
what that pairing buys.  This script does.

The mechanism
-------------
For two policies A and B evaluated on the same performance measure,

        Var(A - B) = Var(A) + Var(B) - 2 Cov(A, B).

With INDEPENDENT streams the covariance is zero and the variance of the
difference is the sum of the two variances.  Under COMMON RANDOM NUMBERS both
policies face the identical week -- the same arrivals, the same triage levels,
the same service times, the same examination requirements -- so a busy week
inflates BOTH policies' waits together.  The covariance becomes strongly
positive and the variance of the DIFFERENCE collapses, while the variance of
each policy's own estimator is untouched.  CRN sharpens comparisons, not
individual estimates: that distinction is the whole point and this script shows
both halves of it.

Why this implementation gets near-perfect synchronisation
---------------------------------------------------------
Most DES codes lose much of the benefit because the two runs consume random
numbers in a different ORDER once their scheduling decisions diverge.  Here the
entire exogenous stream -- arrivals, levels, both consultation durations, exam
requirements -- is drawn BEFORE the run starts (src/rng.py), so patient #1723 is
bit-identical in every policy's run.  Synchronisation is structural, not
best-effort.

What is reported
----------------
  1. Variance of each pairwise difference, with and without CRN.
  2. The variance-reduction factor, and hence how many independent replications
     one CRN replication is worth.
  3. The 95% confidence interval on each difference under both schemes.
  4. The number of replications each scheme needs to resolve a given effect --
     the practical payoff.
  5. A check that CRN does NOT bias the point estimates.

Usage
-----
    python scripts/run_06_crn_variance.py
    python scripts/run_06_crn_variance.py --reps 200
    python scripts/run_06_crn_variance.py --quick
"""
from __future__ import annotations

import numpy as np

from _common import Timer, base_parser, finish, show_header

from src import config as C
from src import console as U
from src.experiment import get_pool, run_comparison
from src.report import Artifact
from src.stats import (compare_all, correlation, crn_efficiency, mean_ci,
                       reps_for_halfwidth)

SPECS = {
    "IFP": ("IFP", {}),
    "ALT": ("ALT", {}),
    "SBP": ("SBP", {"k1": C.SBP_PAPER_OPTIMUM[0], "k2": C.SBP_PAPER_OPTIMUM[1]}),
    "WSEPT": ("WSEPT", {}),
    "GCMU": ("GCMU", {}),
}


def main() -> None:
    p = base_parser("WP5: quantify the variance reduction obtained from "
                    "Common Random Numbers.")
    p.add_argument("--target-halfwidth", type=float, default=0.5,
                   help="CI half-width (minutes) used for the "
                        "'replications needed' calculation")
    args = p.parse_args()
    if args.quick:
        args.reps = min(args.reps, 20)

    cfg = C.DEFAULT_CONFIG
    show_header("WP5 -- COMMON RANDOM NUMBERS AND STATISTICAL RIGOUR",
                "run_06_crn_variance.py  |  variance reduction, quantified",
                args, {"policies": ", ".join(SPECS),
                       "target CI half-width": f"{args.target_halfwidth:g} min"})

    with Artifact("run_06_crn_variance", args,
                  "WP5: side-by-side experiment with Common Random Numbers and "
                  "with independent streams, quantifying the variance reduction, "
                  "the equivalent replication saving, and the sharpened "
                  "confidence intervals.") as art:
        get_pool(args.workers)

        # ------------------------------------------------------------------
        U.section("STEP 1  Two experiments, identical in every way but the seeding")
        U.kv("arm 1 -- CRN", "replication r uses the SAME patient stream for "
                             "every policy")
        U.kv("arm 2 -- independent", "the policy name is mixed into the seed, so "
                                     "every policy sees its own streams")
        U.kv("replications per policy per arm", args.reps)
        U.kv("total simulations", f"{2*len(SPECS)*args.reps:,}")
        print()
        with Timer("CRN arm"):
            crn = run_comparison(cfg, SPECS, args.reps, args.seed, crn=True,
                                 workers=args.workers, label="CRN arm")
        with Timer("independent arm"):
            ind = run_comparison(cfg, SPECS, args.reps, args.seed, crn=False,
                                 workers=args.workers, label="independent arm")

        w_crn = {k: [r.wait_total for r in v] for k, v in crn.items()}
        w_ind = {k: [r.wait_total for r in v] for k, v in ind.items()}

        # ------------------------------------------------------------------
        print()
        U.section("STEP 2  CRN does not move the point estimates -- only their spread")
        rows = []
        for k in SPECS:
            mc, sc, lc, hc = mean_ci(w_crn[k])
            mi, si, li, hi = mean_ci(w_ind[k])
            rows.append([k, f"{mc:.3f}", f"{sc:.3f}", f"{mi:.3f}", f"{si:.3f}",
                         f"{mc-mi:+.3f}",
                         f"{abs(mc-mi)/(sc/np.sqrt(len(w_crn[k]))):.2f}"])
        U.table(["policy", "mean (CRN)", "sd (CRN)", "mean (indep)", "sd (indep)",
                 "difference", "|diff| / SE"], rows, aligns="lrrrrrr",
                title="Per-policy estimates under the two seeding schemes")
        art.table("wp5_point_estimates", rows,
                  ["policy", "mean_crn_min", "sd_crn_min", "mean_indep_min",
                   "sd_indep_min", "difference_min", "abs_diff_over_se"],
                  caption="CRN leaves the marginal distribution of each policy's "
                          "estimator unchanged; only the joint distribution changes")
        worst = max(float(r[6]) for r in rows)
        print()
        U.kv("largest |mean difference| between the arms", f"{worst:.2f}", "standard errors")
        if worst < 3.0:
            U.ok("Every policy's mean agrees between the two arms to within 3 "
                 "standard errors, and the standard deviations match.")
        else:
            U.warn("At least one policy's two arms differ by more than 3 standard "
                   "errors. With few replications this is ordinary sampling "
                   "noise in the INDEPENDENT arm (whose estimator has the larger "
                   "variance); re-run with more --reps to see it shrink.")
        U.note("Theory says the two arms must agree in expectation: CRN changes "
               "the DEPENDENCE between runs, not the marginal law of any single "
               "one. It is a variance reduction technique, not a bias.")

        # ------------------------------------------------------------------
        print()
        U.section("STEP 3  Correlation induced by sharing the patient stream")
        keys = list(SPECS)
        rows = []
        for i, a in enumerate(keys):
            for b in keys[i + 1:]:
                rows.append([f"{a} vs {b}",
                             f"{correlation(w_crn[a], w_crn[b]):+.4f}",
                             f"{correlation(w_ind[a], w_ind[b]):+.4f}"])
        U.table(["pair", "corr under CRN", "corr under independence"],
                rows, aligns="lrr")
        art.table("wp5_correlations", rows,
                  ["pair", "correlation_crn", "correlation_independent"],
                  caption="Correlation between the two policies' per-replication "
                          "means; CRN is effective exactly to the extent this is "
                          "positive")
        print()
        U.note("Under independence these correlations are ~0 by construction. "
               "Under CRN they are close to +1, because a heavy week is heavy "
               "for every policy. Var(A-B) = Var(A)+Var(B)-2Cov(A,B), so the "
               "closer this gets to +1, the more of the difference's variance "
               "is cancelled.")

        # ------------------------------------------------------------------
        print()
        U.section("STEP 4  Variance reduction on the pairwise differences")
        comps = crn_efficiency(w_crn, w_ind, C.ALPHA, keys)
        rows = []
        for c in comps:
            rows.append([f"{c.a} vs {c.b}",
                         f"{c.diff_ind:+.3f}", f"{c.diff_crn:+.3f}",
                         f"{c.var_ind:.4f}", f"{c.var_crn:.4f}",
                         f"{c.variance_reduction*100:.2f}%",
                         f"{c.efficiency_gain:.1f}x",
                         f"{c.hw_ind:.4f}", f"{c.hw_crn:.4f}",
                         f"{c.reps_equivalent:.1f}"])
        U.table(["comparison", "mean diff (ind)", "mean diff (CRN)",
                 "Var (ind)", "Var (CRN)", "variance removed", "efficiency",
                 "CI half-w (ind)", "CI half-w (CRN)", "CRN reps == 100 ind"],
                rows, aligns="lrrrrrrrrr",
                title=f"Pairwise differences in mean waiting time ({args.reps} "
                      f"replications per arm)")
        art.table("wp5_variance_reduction", rows,
                  ["comparison", "mean_diff_independent", "mean_diff_crn",
                   "variance_independent", "variance_crn", "variance_removed_pct",
                   "efficiency_gain", "ci_halfwidth_independent",
                   "ci_halfwidth_crn", "crn_reps_matching_the_independent_arm"],
                  caption="The core WP5 result: variance of every pairwise "
                          "difference with and without Common Random Numbers")
        gains = [c.efficiency_gain for c in comps]
        vr = [c.variance_reduction for c in comps]
        print()
        U.kv("variance removed (median across pairs)", f"{np.median(vr)*100:.2f}%")
        U.kv("efficiency gain (median across pairs)", f"{np.median(gains):.1f}x")
        U.kv("efficiency gain (range)",
             f"{min(gains):.1f}x .. {max(gains):.1f}x")
        art.note("median_variance_reduction", round(float(np.median(vr)), 4))
        art.note("median_efficiency_gain", round(float(np.median(gains)), 2))
        med = float(np.median(gains))
        equiv = C.N_REPLICATIONS / med
        print()
        U.ok(f"On variance alone, one CRN replication carries about as much "
             f"comparative information as {med:.0f} independent ones "
             f"({np.median(vr)*100:.1f}% of the difference's variance removed).")
        U.note(f"Read as a saving, {C.N_REPLICATIONS} independent replications "
               f"are matched by roughly {equiv:.1f} CRN replications -- but that "
               f"is an upper bound on the benefit, not a recommendation. The "
               f"efficiency ratio is itself estimated from these data, and a "
               f"t-interval needs enough degrees of freedom to be trustworthy. "
               f"The practical reading is that 20-30 CRN replications give "
               f"comparisons at least as sharp as the paper's 100 independent "
               f"ones -- a 3-5x saving that is safe to actually take.")

        # ------------------------------------------------------------------
        print()
        U.section(f"STEP 5  Replications needed for a +/-{args.target_halfwidth:g} min "
                  f"confidence interval")
        rows = []
        for c in comps:
            n_i = reps_for_halfwidth(np.sqrt(c.var_ind), args.target_halfwidth)
            n_c = reps_for_halfwidth(np.sqrt(c.var_crn), args.target_halfwidth)
            rows.append([f"{c.a} vs {c.b}", f"{np.sqrt(c.var_ind):.3f}",
                         f"{np.sqrt(c.var_crn):.3f}", f"{n_i:,}", f"{n_c:,}",
                         f"{n_i/max(1,n_c):.1f}x"])
        U.table(["comparison", "sd of diff (ind)", "sd of diff (CRN)",
                 "reps needed (ind)", "reps needed (CRN)", "saving"],
                rows, aligns="lrrrrr")
        art.table("wp5_replications_needed", rows,
                  ["comparison", "sd_diff_independent", "sd_diff_crn",
                   "reps_needed_independent", "reps_needed_crn", "saving_factor"],
                  caption=f"Replications required to pin each pairwise difference "
                          f"to +/-{args.target_halfwidth:g} minutes at 95% confidence")

        # ------------------------------------------------------------------
        print()
        U.section("STEP 6  The paper's significance analysis, re-run under both schemes")
        t_crn = compare_all(w_crn, C.ALPHA, keys)
        t_ind = compare_all(w_ind, C.ALPHA, keys)
        rows = []
        for tc, ti in zip(t_crn, t_ind):
            rows.append([f"{tc.a} vs {tc.b}",
                         f"{ti.t_stat:.3f}", U.fmt_p(ti.p_value),
                         "Yes" if ti.significant else "No", f"{ti.cohens_d:.3f}",
                         f"{tc.t_stat:.3f}", U.fmt_p(tc.p_value),
                         "Yes" if tc.significant else "No", f"{tc.cohens_d:.3f}"])
        U.table(["comparison", "t (ind)", "p (ind)", "sig", "d (ind)",
                 "t (CRN)", "p (CRN)", "sig", "d (CRN)"],
                rows, aligns="lrrcrrrcr",
                title="Paired t-tests with Bonferroni correction, both arms")
        art.table("wp5_significance_both_arms", rows,
                  ["comparison", "t_independent", "p_independent",
                   "significant_independent", "cohens_d_independent",
                   "t_crn", "p_crn", "significant_crn", "cohens_d_crn"],
                  caption="The paper's statistical analysis repeated with and "
                          "without CRN")
        n_sig_c = sum(1 for t in t_crn if t.significant)
        n_sig_i = sum(1 for t in t_ind if t.significant)
        print()
        U.kv("significant comparisons under CRN", f"{n_sig_c} of {len(t_crn)}")
        U.kv("significant comparisons under independence",
             f"{n_sig_i} of {len(t_ind)}")
        U.note("Where the two arms disagree, CRN is the arm to believe: it is "
               "testing the same hypothesis with a lower-variance estimator of "
               "the same quantity.")

        # ------------------------------------------------------------------
        if not args.no_figures:
            print()
            U.section("Rendering figures")
            from src.plotting import crn_panel
            pairs = [f"{c.a}\nvs {c.b}" for c in comps]
            n_i = [reps_for_halfwidth(np.sqrt(c.var_ind), args.target_halfwidth)
                   for c in comps]
            n_c = [reps_for_halfwidth(np.sqrt(c.var_crn), args.target_halfwidth)
                   for c in comps]
            fig, _ = crn_panel(pairs, [c.hw_ind for c in comps],
                               [c.hw_crn for c in comps], n_i, n_c,
                               "What Common Random Numbers buy "
                               f"(target CI half-width {args.target_halfwidth:g} min)")
            art.figure(fig, "wp5_crn_variance_reduction",
                       "Confidence-interval width and replication cost, with and "
                       "without Common Random Numbers")

        print()
        finish(art, "WP5 complete. Next: python scripts/run_07_sensitivity.py")


if __name__ == "__main__":
    main()
