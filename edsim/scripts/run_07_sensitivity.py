"""
run_07_sensitivity.py -- reproduce the base paper's ROBUSTNESS study (Sec 3.4),
extended to the two policies we added.

Three experiments, matching the paper section by section:

  3.4.1  ARRIVAL RATE.   Scale every lambda_{d,h} by -15% .. +15% in 3% steps
         and re-evaluate every policy.  The paper's Figure 4 shows the policies
         indistinguishable under light load and fanning out sharply as the
         system saturates.
  3.4.2  PHYSICIAN STAFFING.  Re-run the seven rosters S0-S6 of Table 10.  The
         paper's Figure 5 shows waits falling with diminishing returns.
  3.4.3  SERVICE-TIME DISTRIBUTION.  Replace the truncated exponential
         consultation times with truncated LOGNORMALS calibrated to the same
         means (mu = ln(m) - sigma^2/2, sigma = 0.3).  The paper reports that
         waits rise across the board but the RANKING of the strategies is
         unchanged -- i.e. the conclusions are not an artefact of the
         distributional assumption.

Every experiment uses Common Random Numbers within each scenario, so the
policy-to-policy differences at each point on the x-axis are exactly paired.

Usage
-----
    python scripts/run_07_sensitivity.py
    python scripts/run_07_sensitivity.py --reps 50
    python scripts/run_07_sensitivity.py --quick
"""
from __future__ import annotations

import numpy as np

from _common import Timer, base_parser, finish, show_header

from src import config as C
from src import console as U
from src.experiment import get_pool, run_comparison
from src.metrics import aggregate
from src.report import Artifact
from src.rng import offered_load

SPECS = {
    "IFP": ("IFP", {}),
    "ALT": ("ALT", {}),
    "SBP": ("SBP", {"k1": C.SBP_PAPER_OPTIMUM[0], "k2": C.SBP_PAPER_OPTIMUM[1]}),
    "WSEPT": ("WSEPT", {}),
    "GCMU": ("GCMU", {}),
}


def sweep(cfg_list, labels, args, label):
    """Run every policy on every configuration; return {policy: [means]}."""
    out = {k: [] for k in SPECS}
    extra = {k: [] for k in SPECS}
    prog = U.Progress(len(cfg_list) * len(SPECS) * args.reps, label)
    for cfg in cfg_list:
        res = run_comparison(cfg, SPECS, args.reps, args.seed, crn=True,
                             workers=args.workers, label=label, progress=prog)
        agg = {k: aggregate(v) for k, v in res.items()}
        for k in SPECS:
            out[k].append(agg[k]["wait_total"]["mean"])
            extra[k].append((agg[k]["sl_l3"]["mean"], agg[k]["sl_l4"]["mean"],
                             agg[k]["physician_util"]["mean"],
                             agg[k]["n_unfinished"]["mean"]))
    prog.close()
    return out, extra


def main() -> None:
    p = base_parser("Sensitivity and robustness study (paper Sec 3.4), extended "
                    "to the c-mu policies.")
    p.add_argument("--arrival-span", type=float, default=15.0,
                   help="+/- percentage span for the arrival-rate sweep")
    p.add_argument("--arrival-step", type=float, default=3.0)
    p.add_argument("--skip-arrival", action="store_true")
    p.add_argument("--skip-staffing", action="store_true")
    p.add_argument("--skip-distribution", action="store_true")
    args = p.parse_args()
    if args.quick:
        args.reps = min(args.reps, 8)
        args.arrival_step = 7.5

    cfg = C.DEFAULT_CONFIG
    show_header("ROBUSTNESS -- ARRIVAL RATE, STAFFING, SERVICE DISTRIBUTION",
                "run_07_sensitivity.py  |  reproduces paper Sec 3.4.1 - 3.4.3",
                args, {"policies": ", ".join(SPECS)})

    with Artifact("run_07_sensitivity", args,
                  "Reproduction of the base paper's sensitivity analysis "
                  "(arrival rate, physician staffing, service-time distribution), "
                  "extended to include the two c-mu policies contributed by "
                  "this project.") as art:
        get_pool(args.workers)

        # ==================================================================
        if not args.skip_arrival:
            U.section("3.4.1  Sensitivity to the patient arrival rate")
            deltas = np.arange(-args.arrival_span, args.arrival_span + 1e-9,
                               args.arrival_step)
            cfgs = [cfg.with_(arrival_scale=1.0 + d / 100.0) for d in deltas]
            U.kv("arrival-rate multipliers",
                 ", ".join(f"{d:+.0f}%" for d in deltas))
            rows0 = [[f"{d:+.0f}%", f"{c.arrival_scale:.3f}",
                      f"{offered_load(c)[2]:.4f}"] for d, c in zip(deltas, cfgs)]
            U.table(["arrival change", "scale", "analytic offered load rho"],
                    rows0, aligns="rrr",
                    title="How far each scenario pushes the system")
            print()
            with Timer("arrival sweep"):
                waits, extra = sweep(cfgs, deltas, args, "arrival sweep")
            print()
            rows = []
            for i, d in enumerate(deltas):
                rows.append([f"{d:+.0f}%", f"{offered_load(cfgs[i])[2]:.3f}"]
                            + [f"{waits[k][i]:.2f}" for k in SPECS]
                            + [f"{extra['SBP'][i][3]:.0f}"])
            U.table(["arrival change", "rho"] + list(SPECS) + ["unfinished (SBP)"],
                    rows, aligns="rr" + "r" * (len(SPECS) + 1),
                    title="Mean waiting time per patient (min) by arrival rate")
            art.table("sens_arrival_rate", rows,
                      ["arrival_change", "offered_load_rho"]
                      + [f"{k}_mean_wait_min" for k in SPECS]
                      + ["unfinished_patients_sbp"],
                      caption="Mean waiting time under each policy as the arrival "
                              "rate is scaled -15% to +15% (paper Figure 4)")
            print()
            lo, hi = waits["IFP"][0], waits["IFP"][-1]
            U.kv("IFP wait, lightest -> heaviest load", f"{lo:.2f} -> {hi:.2f} min "
                                                        f"({hi/lo:.1f}x)")
            spread_lo = max(waits[k][0] for k in SPECS) - min(waits[k][0] for k in SPECS)
            spread_hi = max(waits[k][-1] for k in SPECS) - min(waits[k][-1] for k in SPECS)
            U.kv("policy spread at the lightest load", f"{spread_lo:.2f} min")
            U.kv("policy spread at the heaviest load", f"{spread_hi:.2f} min")
            print()
            if spread_hi > spread_lo:
                U.ok("Policies are nearly interchangeable under light load and "
                     "diverge sharply as the system saturates -- the paper's "
                     "Figure 4 finding, reproduced.")
            else:
                U.warn("The policy spread did not widen with load; check the "
                       "arrival scaling.")
            art.note("policy_spread_light_load", round(spread_lo, 3))
            art.note("policy_spread_heavy_load", round(spread_hi, 3))

            if not args.no_figures:
                from src.plotting import line_by_policy
                fig, _ = line_by_policy(
                    list(deltas), {k: waits[k] for k in SPECS},
                    "Impact of the arrival rate on mean waiting time",
                    "arrival-rate change (%)",
                    "mean waiting time per patient (min)",
                    xticklabels=[f"{d:+.0f}" for d in deltas])
                art.figure(fig, "sens_arrival_rate",
                           "Paper Figure 4 reproduced and extended to five policies")

        # ==================================================================
        if not args.skip_staffing:
            print()
            U.section("3.4.2  Sensitivity to physician staffing (Table 10, S0-S6)")
            scen = list(C.STAFFING_SCENARIOS.items())
            if args.quick:
                scen = scen[::2]
            cfgs = [cfg.with_(shifts=C.shifts_from_vector(R)) for _, R in scen]
            rows0 = [[n, f"{R}", f"{sum((s.end_hour-s.start_hour)%24*s.physicians for s in c.shifts)*7:.0f}",
                      f"{offered_load(c)[2]:.4f}"]
                     for (n, R), c in zip(scen, cfgs)]
            U.table(["scenario", "roster (M,A,N)", "physician-hours/week",
                     "offered load rho"], rows0, aligns="llrr")
            print()
            with Timer("staffing sweep"):
                waits_s, extra_s = sweep(cfgs, [n for n, _ in scen], args,
                                         "staffing sweep")
            print()
            rows = []
            for i, (n, R) in enumerate(scen):
                rows.append([n, f"{R}"] + [f"{waits_s[k][i]:.2f}" for k in SPECS]
                            + [f"{extra_s['SBP'][i][2]*100:.1f}",
                               f"{extra_s['SBP'][i][1]*100:.2f}"])
            U.table(["scenario", "roster"] + list(SPECS)
                    + ["util % (SBP)", "SL4 % (SBP)"],
                    rows, aligns="ll" + "r" * (len(SPECS) + 2),
                    title="Mean waiting time per patient (min) by staffing scenario")
            art.table("sens_staffing", rows,
                      ["scenario", "roster"] + [f"{k}_mean_wait_min" for k in SPECS]
                      + ["utilisation_pct_sbp", "SL4_pct_sbp"],
                      caption="Mean waiting time under each policy across the "
                              "paper's seven staffing scenarios (paper Figure 5)")
            print()
            gaps = [max(waits_s[k][i] for k in SPECS) - min(waits_s[k][i] for k in SPECS)
                    for i in range(len(scen))]
            U.kv("policy spread, scarcest staffing", f"{gaps[0]:.2f} min")
            U.kv("policy spread, richest staffing", f"{gaps[-1]:.2f} min")
            if gaps[-1] < gaps[0]:
                U.ok("The choice of scheduling policy matters most when "
                     "physicians are scarce and washes out once capacity is "
                     "ample -- the paper's Figure 5 finding, reproduced.")
            else:
                U.warn("Policy differences did not shrink with added staff.")

            if not args.no_figures:
                from src.plotting import line_by_policy
                fig, _ = line_by_policy(
                    list(range(len(scen))), {k: waits_s[k] for k in SPECS},
                    "Impact of physician staffing on mean waiting time",
                    "staffing scenario", "mean waiting time per patient (min)",
                    xticklabels=[f"{n}\n{R}" for n, R in scen])
                art.figure(fig, "sens_staffing",
                           "Paper Figure 5 reproduced and extended to five policies")

        # ==================================================================
        if not args.skip_distribution:
            print()
            U.section("3.4.3  Robustness to the service-time distribution")
            U.note("Replacing TruncExp with a truncated lognormal calibrated to "
                   "the same nominal means (sigma = 0.3). The lognormal has a "
                   "heavier right tail, which queueing theory says should raise "
                   "congestion; the question is whether it changes the RANKING.")
            cfg_ln = cfg.with_(service_dist="trunclognormal")
            print()
            with Timer("distribution comparison"):
                base = run_comparison(cfg, SPECS, args.reps, args.seed, crn=True,
                                      workers=args.workers, label="truncexp")
                logn = run_comparison(cfg_ln, SPECS, args.reps, args.seed, crn=True,
                                      workers=args.workers, label="trunclognormal")
            ab = {k: aggregate(v) for k, v in base.items()}
            al = {k: aggregate(v) for k, v in logn.items()}
            print()
            rows = []
            for k in SPECS:
                b, l = ab[k]["wait_total"]["mean"], al[k]["wait_total"]["mean"]
                rows.append([k, f"{b:.2f}", f"{l:.2f}", f"{l-b:+.2f}",
                             f"{(l/b-1)*100:+.1f}%",
                             f"{ab[k]['sl_l4']['mean']*100:.2f}",
                             f"{al[k]['sl_l4']['mean']*100:.2f}"])
            U.table(["policy", "TruncExp wait", "Lognormal wait", "change",
                     "relative", "SL4 % (exp)", "SL4 % (lognormal)"],
                    rows, aligns="lrrrrrr",
                    title="Effect of swapping the consultation-time distribution")
            art.table("sens_service_distribution", rows,
                      ["policy", "truncexp_mean_wait_min", "lognormal_mean_wait_min",
                       "change_min", "relative_change", "SL4_pct_truncexp",
                       "SL4_pct_lognormal"],
                      caption="Robustness of the results to the service-time "
                              "distribution (paper Sec 3.4.3)")
            rb = sorted(SPECS, key=lambda k: ab[k]["wait_total"]["mean"])
            rl = sorted(SPECS, key=lambda k: al[k]["wait_total"]["mean"])
            print()
            U.kv("ranking under TruncExp", " < ".join(rb))
            U.kv("ranking under truncated lognormal", " < ".join(rl))
            print()
            if rb == rl:
                U.ok("The ranking is identical under both distributions -- the "
                     "comparative conclusions are not an artefact of assuming "
                     "exponential service times, exactly as the paper reports.")
            else:
                U.warn("The ranking changed between the two service-time "
                       "distributions. Any conclusion about which policy is best "
                       "must therefore be stated together with the distributional "
                       "assumption it rests on.")
            art.note("ranking_truncexp", rb)
            art.note("ranking_lognormal", rl)

            if not args.no_figures:
                from src.plotting import bar_policies
                fig, _ = bar_policies(
                    {k: al[k]["wait_total"]["mean"] for k in SPECS},
                    {k: al[k]["wait_total"]["mean"] - al[k]["wait_total"]["ci_lo"]
                     for k in SPECS},
                    "Mean waiting time under truncated-lognormal service times",
                    "minutes", baseline="IFP")
                art.figure(fig, "sens_lognormal_bars",
                           "Waiting times under the lognormal robustness check")

        print()
        finish(art, "Sensitivity study complete. "
                    "Next: python scripts/run_08_final_comparison.py")


if __name__ == "__main__":
    main()
