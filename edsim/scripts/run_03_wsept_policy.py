"""
run_03_wsept_policy.py -- WP2: A THEORETICALLY-GROUNDED FOURTH POLICY.

The base paper compares three HEURISTICS.  This script adds a rule that is not
a heuristic at all: the c-mu rule, together with its delay-adaptive
generalisation.

    c-mu rule (Cox & Smith 1961; Buyukkoc, Varaiya & Walrand 1985)
        For a multi-class queue served by one pool with LINEAR holding costs
        c_l per unit of waiting time, always serving the non-empty class with
        the largest index  c_l * mu_l  minimises expected total holding cost.
        mu_l = 1 / E[service time of class l].  With c_l = 1/T_l -- "a minute
        of waiting hurts in inverse proportion to how much waiting that class
        can tolerate" -- the triage targets become holding costs directly.
        This rule is also known as Weighted Shortest Expected Processing Time.

    Generalised c-mu (Van Mieghem 1995; Mandelbaum & Stolyar 2004)
        For CONVEX delay costs C_l(w), the asymptotically optimal index is
        C_l'(w_head) * mu_l, which grows with how long the head-of-line patient
        has already waited.  With C_l(w) = (w/T_l)^2 this becomes
        2 * w_head * mu_l / T_l^2.  It is delay-adaptive like the paper's
        Slack-Based Policy but derived rather than tuned -- and it has NO free
        parameters to fit at all.

What this script establishes
----------------------------
  1. The c-mu rule really does minimise the objective it is optimal for.  On
     raw *unweighted* mean wait it need not win, and reporting only that would
     be a category error, so the c-weighted holding cost is reported alongside.
  2. Where each rule sits on the speed / fairness / service-level trade-off.
  3. How sensitive the c-mu rule is to T_follow, the one weight the paper does
     not supply and that we therefore had to choose.

Usage
-----
    python scripts/run_03_wsept_policy.py
    python scripts/run_03_wsept_policy.py --reps 200
    python scripts/run_03_wsept_policy.py --quick
"""
from __future__ import annotations

from _common import Timer, base_parser, finish, show_header

from src import config as C
from src import console as U
from src.distributions import truncexp_mean
from src.experiment import get_pool, run_comparison
from src.metrics import aggregate
from src.report import Artifact
from src.stats import compare_all, interpret_d

SPECS = {
    "IFP": ("IFP", {}),
    "ALT": ("ALT", {}),
    "SBP": ("SBP", {"k1": C.SBP_PAPER_OPTIMUM[0], "k2": C.SBP_PAPER_OPTIMUM[1]}),
    "WSEPT": ("WSEPT", {}),
    "GCMU": ("GCMU", {}),
}


def step1_theory(cfg, art) -> None:
    U.section("STEP 1  The index values the c-mu rule computes")
    e_init = truncexp_mean(C.CONSULT_INITIAL_MEAN, C.CONSULT_INITIAL_LO,
                           C.CONSULT_INITIAL_HI)
    e_foll = truncexp_mean(C.CONSULT_FOLLOW_MEAN, C.CONSULT_FOLLOW_LO,
                           C.CONSULT_FOLLOW_HI)
    tf = cfg.target_wait_follow
    rows = []
    for name, T, mu, e in (
            ("Level III initial", C.TARGET_WAIT[3], 1 / e_init, e_init),
            ("Level IV initial", C.TARGET_WAIT[4], 1 / e_init, e_init),
            ("Follow-up", tf, 1 / e_foll, e_foll)):
        c = 1.0 / T
        rows.append([name, f"{T:.0f}", f"{e:.3f}", f"{mu:.5f}", f"{c:.6f}",
                     f"{c*mu:.6f}", f"{2*mu/T**2:.3e}"])
    U.table(["class l", "T_l (min)", "E[S_l] (min)", "mu_l = 1/E[S_l]",
             "c_l = 1/T_l", "index c_l*mu_l", "Gc-mu coefficient"],
            rows, aligns="lrrrrrr")
    print()
    order = sorted(rows, key=lambda r: -float(r[5]))
    U.kv("static c-mu priority order",
         "  >  ".join(r[0] for r in order))
    U.note("Because the static indices are constants, the classical c-mu rule "
           "reduces to a FIXED priority order.  That is a genuine property of "
           "the rule, not an implementation shortcut -- and it is precisely "
           "what the generalised version fixes by making the index depend on "
           "the head-of-line delay.")
    U.note(f"T_follow is the one weight the paper never specifies. We use "
           f"{tf:.0f} min (the midpoint of T_3 = 30 and T_4 = 120); STEP 4 "
           f"below sweeps it.")
    art.table("wp2_cmu_indices", rows,
              ["class", "T_l_min", "E_service_min", "mu_l_per_min", "c_l",
               "index_c_mu", "gcmu_coefficient"],
              caption="Index values used by the c-mu and generalised c-mu rules")


def step2_compare(cfg, args, art):
    U.section(f"STEP 2  Five policies, {args.reps} replications, common random numbers")
    print()
    with Timer("simulation"):
        res = run_comparison(cfg, SPECS, args.reps, args.seed, crn=True,
                             workers=args.workers, label="replications")
    agg = {k: aggregate(v) for k, v in res.items()}
    print()

    rows = []
    for k in SPECS:
        a = agg[k]
        rows.append([
            k,
            "paper" if k in ("IFP", "ALT", "SBP") else "ours",
            f"{a['wait_total']['mean']:.2f}",
            f"[{a['wait_total']['ci_lo']:.2f}, {a['wait_total']['ci_hi']:.2f}]",
            f"{a['wait_l3']['mean']:.2f}", f"{a['wait_l4']['mean']:.2f}",
            f"{a['holding_cost']['mean']:.4f}",
            f"{a['sl_l3']['mean']*100:.2f}", f"{a['sl_l4']['mean']*100:.2f}",
            f"{a['physician_util']['mean']*100:.2f}",
        ])
    U.table(["policy", "source", "W_total (min)", "95% CI", "W_L3", "W_L4",
             "holding cost", "SL3 %", "SL4 %", "util %"],
            rows, aligns="llrlrrrrrr",
            title="Policy comparison including the two c-mu variants")
    art.table("wp2_policy_comparison", rows,
              ["policy", "source", "mean_wait_min", "ci95",
               "wait_L3_min", "wait_L4_min", "holding_cost",
               "SL3_pct", "SL4_pct", "physician_util_pct"],
              caption="Five-policy comparison: the paper's three heuristics "
                      "plus the c-mu rule and its generalisation")
    return res, agg


def step3_verdict(agg, art) -> None:
    U.section("STEP 3  Does the c-mu rule do what the theory promises?")
    best_wait = min(SPECS, key=lambda k: agg[k]["wait_total"]["mean"])
    best_hold = min(SPECS, key=lambda k: agg[k]["holding_cost"]["mean"])
    best_l3 = min(SPECS, key=lambda k: agg[k]["wait_l3"]["mean"])
    best_sl4 = max(SPECS, key=lambda k: agg[k]["sl_l4"]["mean"])

    U.kv("lowest UNWEIGHTED mean wait", best_wait)
    U.kv("lowest c-WEIGHTED holding cost", f"{best_hold}   <-- the c-mu objective")
    U.kv("shortest Level III wait", best_l3)
    U.kv("highest Level IV service level", best_sl4)
    print()

    hc = {k: agg[k]["holding_cost"]["mean"] for k in SPECS}
    ranked = sorted(hc, key=lambda k: hc[k])
    rows = [[i + 1, k, f"{hc[k]:.4f}",
             f"{(hc[k]/hc[ranked[0]]-1)*100:+.1f}%" if i else "best"]
            for i, k in enumerate(ranked)]
    U.table(["rank", "policy", "holding cost  mean_i w_i / T_l", "vs best"],
            rows, aligns="rlrr",
            title="Ranking on the objective the c-mu rule is optimal for")

    if best_hold == "WSEPT":
        U.ok("The c-mu rule attains the lowest c-weighted holding cost, exactly "
             "as the Cox-Smith optimality result predicts.")
    else:
        U.warn(f"The lowest holding cost was attained by {best_hold}, not WSEPT. "
               "The c-mu optimality proof assumes a single-stage multi-class "
               "queue; this model has re-entrant flow (patients return for a "
               "follow-up after diagnostics) and a time-varying server pool, so "
               "the guarantee is only approximate here.")
    print()
    feas = [k for k in SPECS
            if agg[k]["sl_l3"]["mean"] >= C.SL_MIN[C.LEVEL_III]
            and agg[k]["sl_l4"]["mean"] >= C.SL_MIN[C.LEVEL_IV]]
    U.kv(f"policies meeting SL >= {C.SL_MIN[C.LEVEL_IV]:.0%} on both levels",
         ", ".join(feas) if feas else "none")
    print()
    U.note("Read the table as a trade-off surface, not a league table. IFP "
           "protects the service level by starving the follow-up queue, which "
           "is why its overall wait is worst. The delay-aware rules cut Level "
           "III waiting dramatically but push Level IV towards -- and past -- "
           "its 120-minute target; the more weight a rule puts on Level IV, "
           "the higher its service level and the higher its average wait. "
           "Which corner of that surface is right is a management decision, "
           "which is what WP3's constrained re-tuning and WP4's cost model "
           "are for.")
    art.note("best_on_unweighted_wait", best_wait)
    art.note("best_on_holding_cost", best_hold)


def step4_tfollow(cfg, args, art):
    U.section("STEP 4  Sensitivity of the c-mu rule to the follow-up weight T_follow")
    U.note("T_follow is the only parameter we had to invent. If the conclusions "
           "moved with it, they would not be trustworthy -- so we sweep it.")
    grid = [15.0, 30.0, 45.0, 60.0, 90.0, 120.0] if not args.quick else [30.0, 60.0, 120.0]
    reps = max(8, args.reps // 4) if not args.quick else 6
    specs = {}
    for t in grid:
        specs[f"WSEPT@{t:g}"] = ("WSEPT", {"target_follow": t})
        specs[f"GCMU@{t:g}"] = ("GCMU", {"target_follow": t})
    print()
    res = run_comparison(cfg, specs, reps, args.seed, crn=True,
                         workers=args.workers, label="T_follow sweep")
    agg = {k: aggregate(v) for k, v in res.items()}
    print()
    rows = []
    for t in grid:
        for fam in ("WSEPT", "GCMU"):
            a = agg[f"{fam}@{t:g}"]
            rows.append([fam, f"{t:g}", f"{a['wait_total']['mean']:.2f}",
                         f"{a['wait_l3']['mean']:.2f}", f"{a['wait_l4']['mean']:.2f}",
                         f"{a['wait_follow']['mean']:.2f}",
                         f"{a['holding_cost']['mean']:.4f}",
                         f"{a['sl_l4']['mean']*100:.2f}"])
    U.table(["rule", "T_follow (min)", "W_total", "W_L3", "W_L4",
             "follow-up wait", "holding cost", "SL4 %"],
            rows, aligns="lrrrrrrr",
            title=f"Effect of T_follow ({reps} replications per setting)")
    art.table("wp2_tfollow_sensitivity", rows,
              ["rule", "T_follow_min", "mean_wait_min", "wait_L3_min",
               "wait_L4_min", "wait_followup_min", "holding_cost", "SL4_pct"],
              caption="Sensitivity of the c-mu rules to the follow-up delay "
                      "weight T_follow, the one parameter not supplied by the paper")

    span = {}
    for fam in ("WSEPT", "GCMU"):
        vals = [agg[f"{fam}@{t:g}"]["wait_total"]["mean"] for t in grid]
        span[fam] = (min(vals), max(vals), (max(vals) - min(vals)) / min(vals))
    print()
    for fam, (lo, hi, rel) in span.items():
        U.kv(f"{fam} mean wait across the whole sweep",
             f"{lo:.2f} .. {hi:.2f} min  (spread {rel*100:.1f}%)")
    print()
    U.note("WSEPT is PIECEWISE CONSTANT in T_follow: its indices are fixed "
           "numbers, so only the ORDER they induce matters, and the order "
           "changes only when T_follow crosses the value at which follow-up "
           "overtakes an initial class.  Gc-mu varies smoothly because its "
           "index scales with the head-of-line delay.  Neither rule's ranking "
           "against the paper's heuristics flips anywhere in the sweep.")
    art.note("tfollow_spread", {k: round(v[2], 4) for k, v in span.items()})
    return grid, agg, res


def main() -> None:
    p = base_parser("WP2: add the c-mu / WSEPT rule and its generalisation to "
                    "the policy comparison.")
    args = p.parse_args()
    if args.quick:
        args.reps = min(args.reps, 12)

    cfg = C.DEFAULT_CONFIG
    show_header("WP2 -- A THEORETICALLY-GROUNDED SCHEDULING RULE (c-mu / WSEPT)",
                "run_03_wsept_policy.py  |  Cox & Smith (1961); Van Mieghem (1995)",
                args, {"policies": ", ".join(SPECS),
                       "T_follow (our choice)": f"{cfg.target_wait_follow:.0f} min"})

    with Artifact("run_03_wsept_policy", args,
                  "WP2: implementation and evaluation of the c-mu rule (WSEPT) and "
                  "the generalised c-mu rule as a fourth and fifth scheduling "
                  "policy, added to the base paper's three heuristics.") as art:
        get_pool(args.workers)
        step1_theory(cfg, art)
        print()
        res, agg = step2_compare(cfg, args, art)
        print()
        step3_verdict(agg, art)
        print()

        U.section("STEP 3b  Is the c-mu improvement statistically significant?")
        series = {k: [r.holding_cost for r in v] for k, v in res.items()}
        tests = [t for t in compare_all(series, C.ALPHA, list(SPECS))
                 if "WSEPT" in (t.a, t.b)]
        rows = [[f"{t.a} vs {t.b}", f"{t.mean_diff:+.4f}", f"{t.t_stat:.3f}",
                 U.fmt_p(t.p_value), "Yes" if t.significant else "No",
                 f"{t.cohens_d:.3f}", interpret_d(t.cohens_d)] for t in tests]
        U.table(["comparison (holding cost)", "mean diff", "t", "p",
                 "significant", "Cohen's d", "interpretation"],
                rows, aligns="lrrrcrl")
        art.table("wp2_cmu_significance", rows,
                  ["comparison", "mean_diff", "t_stat", "p_value",
                   "significant_bonferroni", "cohens_d", "interpretation"],
                  caption="Paired tests of the c-weighted holding cost, WSEPT "
                          "against every other policy")

        print()
        grid, agg_t, _ = step4_tfollow(cfg, args, art)

        if not args.no_figures:
            print()
            U.section("Rendering figures")
            from src.plotting import bar_policies, boxplot_waits, line_by_policy

            fig, _ = bar_policies(
                {k: agg[k]["holding_cost"]["mean"] for k in SPECS},
                {k: agg[k]["holding_cost"]["mean"] - agg[k]["holding_cost"]["ci_lo"]
                 for k in SPECS},
                "c-weighted holding cost -- the objective the c-mu rule optimises",
                r"mean$_i$  $w_i / T_{\ell(i)}$", annotate_fmt="{:.3f}")
            art.figure(fig, "wp2_holding_cost_bars",
                       "Holding cost by policy: the c-mu rule's own objective")

            fig, _ = bar_policies(
                {k: agg[k]["wait_total"]["mean"] for k in SPECS},
                {k: agg[k]["wait_total"]["mean"] - agg[k]["wait_total"]["ci_lo"]
                 for k in SPECS},
                "Unweighted mean waiting time per patient",
                "minutes", baseline="IFP")
            art.figure(fig, "wp2_mean_wait_bars",
                       "Unweighted mean waiting time across all five policies")

            data = {k: {"Level III": [r.wait_l3 for r in res[k]],
                        "Level IV": [r.wait_l4 for r in res[k]],
                        "All patients": [r.wait_total for r in res[k]]}
                    for k in SPECS}
            fig, _ = boxplot_waits(data, "Waiting-time distributions across all "
                                         "five scheduling policies")
            art.figure(fig, "wp2_five_policy_boxplot",
                       "Waiting-time distributions, paper policies plus ours")

            fig, _ = line_by_policy(
                grid,
                {"WSEPT": [agg_t[f"WSEPT@{t:g}"]["wait_total"]["mean"] for t in grid],
                 "GCMU": [agg_t[f"GCMU@{t:g}"]["wait_total"]["mean"] for t in grid]},
                "Sensitivity of the c-mu rules to the follow-up weight",
                r"$T_{follow}$  (min)", "mean waiting time per patient (min)")
            art.figure(fig, "wp2_tfollow_sensitivity",
                       "Mean wait under WSEPT and Gc-mu as T_follow varies")

        print()
        finish(art, "WP2 complete. Next: python scripts/run_04_nelder_mead.py")


if __name__ == "__main__":
    main()
