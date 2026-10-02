"""
run_02_grid_search.py -- reproduce the base paper's BRUTE-FORCE tuning of the
Slack-Based Policy, and record exactly what it costs.

The paper (Sec 3.2) tunes (k1, k2) with a two-stage lattice search:

    stage 1  coarse, step size 1.0   -> best pair (13, 2),   36.38 min
    stage 2  fine,   step size 0.1,  searching k1 in [12,14], k2 in [1,3]
                                     -> best pair (13.1, 2.1), 35.25 min

We repeat that procedure on our rebuilt model, subject to the service-level
constraint of Eq. (32) enforced through the exterior penalty described in
src/optimizers.py.  Two things come out of it:

  * OUR optimum for OUR model.  The paper's (13.1, 2.1) is optimal for the
    paper's system; it is not automatically optimal for ours, and finding out
    is the entire point of re-tuning rather than copying.
  * The SIMULATION BUDGET the lattice consumed.  That number is written to
    results/raw/wp3_grid_budget.json and becomes the baseline that WP3's
    Nelder-Mead optimiser is measured against.

Runtime
-------
This is the expensive script -- deliberately so, because its expense IS the
result.  With the default settings it evaluates 2 332 lattice points at a cost
of 50 415 week-long simulations, about 10 minutes on 14 workers.  Use --quick
for a 1-minute smoke test, or shrink --coarse-step / --coarse-reps.

Usage
-----
    python scripts/run_02_grid_search.py
    python scripts/run_02_grid_search.py --coarse-reps 10 --fine-reps 30
    python scripts/run_02_grid_search.py --quick
"""
from __future__ import annotations

import numpy as np

from _common import Timer, base_parser, finish, show_header

from src import config as C
from src import console as U
from src.experiment import evaluate_points, get_pool
from src.optimizers import SimulationObjective, grid_search
from src.report import Artifact


def describe_records(recs, k: int = 5, title: str = ""):
    top = sorted(recs, key=lambda r: r.f)[:k]
    rows = []
    for i, r in enumerate(top, 1):
        rows.append([i, f"({r.x[0]:g}, {r.x[1]:g})", f"{r.wait:.2f}",
                     f"{r.sl3*100:.2f}", f"{r.sl4*100:.2f}",
                     f"{r.penalty:.2f}", f"{r.f:.2f}"])
    U.table(["rank", "(k1, k2)", "mean wait (min)", "SL3 %", "SL4 %",
             "penalty", "objective"], rows, aligns="rlrrrrr", title=title)
    return rows, top


def main() -> None:
    p = base_parser("Reproduce the paper's two-stage brute-force grid search "
                    "for the Slack-Based Policy thresholds (k1, k2).")
    p.add_argument("--coarse-reps", type=int, default=15,
                   help="replications per lattice point in the coarse stage")
    p.add_argument("--fine-reps", type=int, default=50,
                   help="replications per lattice point in the fine stage")
    p.add_argument("--coarse-step", type=float, default=C.GRID_COARSE_STEP)
    p.add_argument("--fine-step", type=float, default=C.GRID_FINE_STEP)
    p.add_argument("--k1-max", type=float, default=C.GRID_K1_RANGE[1])
    p.add_argument("--k2-max", type=float, default=60.0,
                   help="upper bound on k2; must be wide enough to contain the "
                        "region where the Level IV service level is met")
    p.add_argument("--penalty-mu", type=float, default=500.0)
    args = p.parse_args()
    if args.quick:
        args.coarse_reps, args.fine_reps, args.reps = 4, 6, 12
        args.coarse_step, args.k1_max, args.k2_max = 5.0, 30.0, 60.0

    cfg = C.DEFAULT_CONFIG
    show_header("PAPER'S METHOD -- TWO-STAGE BRUTE-FORCE GRID SEARCH",
                "run_02_grid_search.py  |  reproduces Sec 3.2 / Tables 3-4",
                args, {"coarse step": args.coarse_step,
                       "fine step": args.fine_step,
                       "coarse reps/point": args.coarse_reps,
                       "fine reps/point": args.fine_reps,
                       "SL constraint": f"SL_3 >= {C.SL_MIN[3]:.0%}, "
                                        f"SL_4 >= {C.SL_MIN[4]:.0%}",
                       "penalty mu": f"{args.penalty_mu:g} min per unit SL shortfall"})

    with Artifact("run_02_grid_search", args,
                  "Reproduction of the base paper's brute-force two-stage grid "
                  "search over the Slack-Based Policy thresholds, with the "
                  "service-level constraint enforced by an exterior penalty. "
                  "Also records the simulation budget the lattice consumes, "
                  "which is the baseline for the WP3 optimiser comparison.") as art:

        get_pool(args.workers)          # warm the workers before timing anything

        obj = SimulationObjective(cfg, args.coarse_reps, args.seed, args.workers,
                                  penalty_mu=args.penalty_mu, round_to=None)

        # ------------------------------------------------------------------
        U.section("STAGE 1  Coarse lattice, step = %g" % args.coarse_step)
        n1 = int(args.k1_max / args.coarse_step) + 1
        n2 = int(args.k2_max / args.coarse_step) + 1
        U.kv("k1 grid", f"0 .. {args.k1_max:g} step {args.coarse_step:g}  ({n1} values)")
        U.kv("k2 grid", f"0 .. {args.k2_max:g} step {args.coarse_step:g}  ({n2} values)")
        U.kv("lattice points", f"{n1*n2:,}")
        U.kv("simulations required", f"{n1*n2*args.coarse_reps:,}")
        print()
        obj.progress = U.Progress(n1 * n2 * args.coarse_reps, "coarse lattice")
        with Timer("stage 1"):
            g1 = grid_search(obj, (0.0, args.k1_max), (0.0, args.k2_max),
                             args.coarse_step, "coarse")
        obj.progress.close()
        print()
        rows1, top1 = describe_records(
            g1.records, 5, "Top 5 coarse-lattice combinations (paper Table 3)")
        art.table("wp2_grid_coarse_top5", rows1,
                  ["rank", "k1_k2", "mean_wait_min", "SL3_pct", "SL4_pct",
                   "penalty_min", "objective_min"],
                  caption="Best coarse-grid (step 1.0) threshold pairs -- our "
                          "analogue of the paper's Table 3")
        coarse_best = g1.best_x
        print()
        U.ok(f"coarse optimum: k1 = {coarse_best[0]:g}, k2 = {coarse_best[1]:g}  "
             f"(objective {g1.best_f:.2f} min)")
        U.note(f"the paper's coarse optimum was "
               f"(k1={C.SBP_COARSE_OPTIMUM[0]:g}, k2={C.SBP_COARSE_OPTIMUM[1]:g}) "
               f"at 36.38 min")

        # ------------------------------------------------------------------
        print()
        U.section("STAGE 2  Fine lattice, step = %g, around the coarse optimum"
                  % args.fine_step)
        lo1 = max(0.0, coarse_best[0] - 1.0)
        hi1 = min(args.k1_max, coarse_best[0] + 1.0)
        lo2 = max(0.0, coarse_best[1] - 1.0)
        hi2 = min(args.k2_max, coarse_best[1] + 1.0)
        m1 = int(round((hi1 - lo1) / args.fine_step)) + 1
        m2 = int(round((hi2 - lo2) / args.fine_step)) + 1
        U.kv("k1 window", f"[{lo1:g}, {hi1:g}]  ({m1} values)")
        U.kv("k2 window", f"[{lo2:g}, {hi2:g}]  ({m2} values)")
        U.kv("lattice points", f"{m1*m2:,}")
        U.kv("replications per point", args.fine_reps)
        U.kv("simulations required", f"{m1*m2*args.fine_reps:,}")
        print()
        obj_fine = SimulationObjective(cfg, args.fine_reps, args.seed, args.workers,
                                       penalty_mu=args.penalty_mu, round_to=None)
        obj_fine.progress = U.Progress(m1 * m2 * args.fine_reps, "fine lattice")
        with Timer("stage 2"):
            g2 = grid_search(obj_fine, (lo1, hi1), (lo2, hi2), args.fine_step, "fine")
        obj_fine.progress.close()
        print()
        rows2, top2 = describe_records(
            g2.records, 5, "Top 5 fine-lattice combinations (paper Table 4)")
        art.table("wp2_grid_fine_top5", rows2,
                  ["rank", "k1_k2", "mean_wait_min", "SL3_pct", "SL4_pct",
                   "penalty_min", "objective_min"],
                  caption="Best fine-grid (step 0.1) threshold pairs -- our "
                          "analogue of the paper's Table 4")
        best = g2.best_x
        print()
        U.ok(f"GRID-SEARCH OPTIMUM: k1 = {best[0]:.1f}, k2 = {best[1]:.1f}")

        # ------------------------------------------------------------------
        print()
        U.section("STAGE 3  Confirming the optimum at full replication count")
        U.note(f"Re-evaluating our optimum and the paper's (13.1, 2.1) at "
               f"{args.reps} replications each, on identical streams.")
        print()
        cand = [{"k1": float(best[0]), "k2": float(best[1])},
                {"k1": C.SBP_PAPER_OPTIMUM[0], "k2": C.SBP_PAPER_OPTIMUM[1]}]
        names = ["our grid optimum", "paper optimum (13.1, 2.1)"]
        prog = U.Progress(len(cand) * args.reps, "confirmation runs")
        batches = evaluate_points(cfg, "SBP", cand, args.reps, args.seed,
                                  args.workers, prog)
        prog.close()
        print()
        rows3 = []
        for nm, pt, runs in zip(names, cand, batches):
            w = np.array([r.wait_total for r in runs])
            s3 = float(np.mean([r.sl_l3 for r in runs]))
            s4 = float(np.mean([r.sl_l4 for r in runs]))
            feas = s3 >= C.SL_MIN[3] and s4 >= C.SL_MIN[4]
            rows3.append([nm, f"({pt['k1']:g}, {pt['k2']:g})",
                          f"{w.mean():.2f}", f"{w.std(ddof=1):.2f}",
                          f"{s3*100:.2f}", f"{s4*100:.2f}",
                          "feasible" if feas else "INFEASIBLE"])
        U.table(["setting", "(k1, k2)", "mean wait", "sd", "SL3 %", "SL4 %",
                 "constraint"], rows3, aligns="llrrrrl")
        art.table("wp2_grid_optimum_confirmation", rows3,
                  ["setting", "k1_k2", "mean_wait_min", "sd_min", "SL3_pct",
                   "SL4_pct", "constraint_status"],
                  caption=f"Our grid optimum vs the paper's published optimum, "
                          f"both re-evaluated at {args.reps} replications")

        # ------------------------------------------------------------------
        print()
        U.section("Simulation budget consumed by the brute-force search")
        total_pts = g1.n_points + g2.n_points
        total_sims = g1.n_simulations + g2.n_simulations
        U.kv("stage 1 lattice points", f"{g1.n_points:,}")
        U.kv("stage 1 simulations", f"{g1.n_simulations:,}")
        U.kv("stage 2 lattice points", f"{g2.n_points:,}")
        U.kv("stage 2 simulations", f"{g2.n_simulations:,}")
        U.kv("TOTAL lattice points", f"{total_pts:,}")
        U.kv("TOTAL week-long simulations", f"{total_sims:,}")
        U.kv("equivalent simulated time",
             f"{total_sims * C.HORIZON_MINUTES / 60 / 24 / 365:.1f}", "patient-years of ED operation")
        budget = {
            "coarse": {"points": g1.n_points, "reps": args.coarse_reps,
                       "simulations": g1.n_simulations,
                       "best_x": list(g1.best_x), "best_f": g1.best_f},
            "fine": {"points": g2.n_points, "reps": args.fine_reps,
                     "simulations": g2.n_simulations,
                     "best_x": list(g2.best_x), "best_f": g2.best_f},
            "total_points": total_pts, "total_simulations": total_sims,
            "penalty_mu": args.penalty_mu,
            "sl_min": {str(k): v for k, v in C.SL_MIN.items()},
        }
        art.raw("wp3_grid_budget", budget)

        # Persist the coarse response surface so run_04 can draw the
        # Nelder-Mead trajectory on top of the very surface it searched.
        k1s = sorted({r.x[0] for r in g1.records})
        k2s = sorted({r.x[1] for r in g1.records})
        lut = {(r.x[0], r.x[1]): r for r in g1.records}
        art.raw("wp2_grid_surface", {
            "k1s": k1s, "k2s": k2s,
            "objective": [[lut[(a, b)].f for a in k1s] for b in k2s],
            "mean_wait": [[lut[(a, b)].wait for a in k1s] for b in k2s],
            "sl4": [[lut[(a, b)].sl4 for a in k1s] for b in k2s],
            "reps_per_point": args.coarse_reps,
            "penalty_mu": args.penalty_mu,
        })
        art.note("grid_total_simulations", total_sims)
        art.note("grid_optimum", [round(best[0], 2), round(best[1], 2)])
        art.note("grid_optimum_objective", round(g2.best_f, 4))

        # ------------------------------------------------------------------
        if not args.no_figures:
            print()
            U.section("Rendering the response surface")
            from src.plotting import heatmap_surface
            Zf = np.array([[lut[(a, b)].f for a in k1s] for b in k2s])
            Zs = np.array([[lut[(a, b)].sl4 * 100 for a in k1s] for b in k2s])

            marks = [(best[0], best[1], "*", f"our optimum ({best[0]:g}, {best[1]:g})"),
                     (C.SBP_PAPER_OPTIMUM[0], C.SBP_PAPER_OPTIMUM[1], "s",
                      "paper (13.1, 2.1)")]
            fig, _ = heatmap_surface(
                k1s, k2s, np.clip(Zf, None, np.percentile(Zf, 97)),
                "Penalised objective over the threshold space "
                "(darker = worse; clipped at the 97th percentile)",
                "objective: mean wait + SLA penalty (min)", mark=marks)
            art.figure(fig, "wp2_grid_objective_surface",
                       "Coarse-grid response surface of the penalised objective")

            fig, _ = heatmap_surface(
                k1s, k2s, Zs,
                "Level IV service level over the threshold space "
                "(darker = better; the pale band is infeasible)",
                "SL_4  (% seen within 120 min)", mark=marks)
            art.figure(fig, "wp2_grid_sl4_surface",
                       "Coarse-grid Level IV service level; the feasible region "
                       "of Eq. (32) is the light band at high k2")

        print()
        finish(art, f"Grid search complete: optimum (k1={best[0]:.1f}, "
                    f"k2={best[1]:.1f}) found with {total_sims:,} simulations. "
                    f"Next: python scripts/run_04_nelder_mead.py")


if __name__ == "__main__":
    main()
