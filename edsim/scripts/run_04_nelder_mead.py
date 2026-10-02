"""
run_04_nelder_mead.py -- WP3: A NUMERICAL OPTIMISER INSTEAD OF BRUTE FORCE.

The base paper tunes the Slack-Based Policy with an exhaustive two-stage
lattice.  That works, but its cost grows as the product of the per-dimension
resolutions: doubling the precision of two parameters quadruples the work, and
adding a third parameter multiplies it again.  The paper itself lists this as a
limitation ("it becomes slow and hard to use when there are lots of decision
variables").

This script replaces the lattice with a HAND-IMPLEMENTED Nelder-Mead simplex
(src/optimizers.py -- no scipy.optimize in the primary path) and answers one
concrete question:

    How many week-long simulations does each method need to reach the same
    quality of solution?

Three things make the comparison fair and the optimiser workable:

  * Both methods minimise the SAME penalised objective
        F(k1,k2) = W_total + mu * sum_l max(0, SL_l^min - SL_l)
    so the service-level constraint of Eq. (32) is respected by both.
  * Both use Sample Average Approximation with Common Random Numbers: every
    candidate is scored on the same fixed set of patient streams, which makes
    the objective deterministic and removes seed noise from the comparison
    between candidates.
  * The budget is counted in week-long SIMULATIONS, not seconds, so the result
    does not depend on the machine.

SciPy's own Nelder-Mead is run afterwards purely as a CROSS-CHECK that our
hand-written simplex reaches the same place -- it is never the primary result.

Usage
-----
    python scripts/run_04_nelder_mead.py               # needs run_02 first for
                                                       # the grid baseline
    python scripts/run_04_nelder_mead.py --opt-reps 30
    python scripts/run_04_nelder_mead.py --quick
"""
from __future__ import annotations

import json
import os

import numpy as np

from _common import Timer, base_parser, finish, show_header

from src import config as C
from src import console as U
from src.experiment import evaluate_points, get_pool
from src.optimizers import SimulationObjective, nelder_mead
from src.report import RAW, Artifact

GRID_BUDGET_FILE = os.path.join(RAW, "wp3_grid_budget.json")
GRID_SURFACE_FILE = os.path.join(RAW, "wp2_grid_surface.json")


def load_grid_baseline():
    if not os.path.exists(GRID_BUDGET_FILE):
        return None
    with open(GRID_BUDGET_FILE, encoding="utf-8") as fh:
        return json.load(fh)


def best_so_far(history):
    """Turn an objective's evaluation history into a (budget, best-f) curve."""
    xs, ys, cum, best = [], [], 0, float("inf")
    for rec in history:
        cum += rec.n_sims
        if rec.f < best:
            best = rec.f
        xs.append(max(cum, 1))
        ys.append(best)
    return xs, ys


def main() -> None:
    p = base_parser("WP3: hand-implemented Nelder-Mead with a penalty function, "
                    "benchmarked against the paper's grid search.")
    p.add_argument("--opt-reps", type=int, default=50,
                   help="replications per objective evaluation during the search")
    p.add_argument("--penalty-mu", type=float, default=500.0)
    p.add_argument("--max-iter", type=int, default=80)
    p.add_argument("--xtol", type=float, default=0.05,
                   help="simplex span at which the search stops (in minutes of "
                        "slack, so 0.05 is finer than the paper's 0.1 grid)")
    p.add_argument("--ftol", type=float, default=0.02)
    p.add_argument("--no-scipy", action="store_true",
                   help="skip the SciPy cross-check")
    args = p.parse_args()
    if args.quick:
        args.opt_reps, args.reps, args.max_iter = 8, 12, 25

    cfg = C.DEFAULT_CONFIG
    show_header("WP3 -- NELDER-MEAD SIMPLEX vs BRUTE-FORCE GRID SEARCH",
                "run_04_nelder_mead.py  |  hand-implemented, penalty-constrained",
                args, {"reps per evaluation": args.opt_reps,
                       "penalty mu": args.penalty_mu,
                       "stopping xtol / ftol": f"{args.xtol} / {args.ftol}"})

    with Artifact("run_04_nelder_mead", args,
                  "WP3: a hand-written Nelder-Mead simplex optimiser with an "
                  "exterior penalty for the service-level constraint, benchmarked "
                  "against the base paper's brute-force grid search on equal "
                  "terms (same objective, same seeds, budget counted in "
                  "week-long simulations).") as art:
        get_pool(args.workers)
        bounds = [(0.0, C.GRID_K1_RANGE[1]), (0.0, 120.0)]

        # ------------------------------------------------------------------
        U.section("STEP 1  The optimisation problem")
        U.kv("decision variables", "k1 (Level III slack), k2 (Level IV slack)")
        U.kv("objective", "minimise W_total(k1,k2) -- mean waiting time per patient")
        U.kv("constraint", f"SL_3 >= {C.SL_MIN[3]:.0%},  SL_4 >= {C.SL_MIN[4]:.0%}"
                           "   [paper Eq. 32]")
        U.kv("penalised form",
             f"F = W_total + {args.penalty_mu:g} * sum_l max(0, SL_min - SL_l)")
        U.kv("box bounds", f"k1 in [{bounds[0][0]:g}, {bounds[0][1]:g}], "
                           f"k2 in [{bounds[1][0]:g}, {bounds[1][1]:g}]")
        U.kv("noise handling", f"sample average over {args.opt_reps} fixed CRN streams")
        print()
        U.note("Bounds are enforced by PROJECTION (each trial vertex is clipped "
               "back into the box) rather than by a second penalty term, so the "
               "simplex can slide along a bound instead of being pushed away "
               "from it.")

        # ------------------------------------------------------------------
        print()
        U.section("STEP 2  Single-start Nelder-Mead (live iteration trace)")
        obj = SimulationObjective(cfg, args.opt_reps, args.seed, args.workers,
                                  penalty_mu=args.penalty_mu, round_to=0.01)
        x0 = [10.0, 30.0]
        step = [4.0, 15.0]
        U.kv("initial vertex x0", f"({x0[0]:g}, {x0[1]:g})")
        U.kv("initial simplex step", f"({step[0]:g}, {step[1]:g})")
        U.note("A per-dimension step is used because k1 and k2 live on different "
               "scales (k1 in ~[0,30] against T_3 = 30, k2 in ~[0,120] against "
               "T_4 = 120); one scalar step would make the initial simplex "
               "badly conditioned.")
        print()
        print(f"  {'iter':>6s} {'best f':>10s} {'k1':>8s} {'k2':>8s} "
              f"{'f-spread':>10s} {'sims':>8s}")
        print("  " + U.GREY + "-" * 56 + U.RESET)

        def on_iter(it, simplex, fvals):
            print(f"  {it:6d} {fvals[0]:10.4f} {simplex[0][0]:8.3f} "
                  f"{simplex[0][1]:8.3f} {fvals[-1]-fvals[0]:10.4f} "
                  f"{obj.n_simulations:8,d}")

        with Timer("single-start Nelder-Mead"):
            nm = nelder_mead(obj, x0, initial_step=step, bounds=bounds,
                             xtol=args.xtol, ftol=args.ftol,
                             max_iter=args.max_iter, on_iter=on_iter)
        nm.n_simulations = obj.n_simulations
        print()
        U.kv("result", f"k1 = {nm.x[0]:.3f}, k2 = {nm.x[1]:.3f}")
        U.kv("objective", f"{nm.f:.4f}")
        U.kv("iterations", nm.n_iterations)
        U.kv("objective calls (incl. cache hits)", obj.n_calls)
        U.kv("distinct points simulated", obj.n_evaluations)
        U.kv("week-long simulations used", f"{obj.n_simulations:,}")
        U.kv("termination", nm.message)
        single_hist = list(obj.history)

        # ------------------------------------------------------------------
        print()
        U.section("STEP 3  Multi-start Nelder-Mead (guarding against local minima)")
        U.note("The simplex method converges to a LOCAL minimum. Four dispersed "
               "starts test whether the penalised surface has more than one.")
        obj_ms = SimulationObjective(cfg, args.opt_reps, args.seed, args.workers,
                                     penalty_mu=args.penalty_mu, round_to=0.01)
        starts = [[2.0, 5.0], [10.0, 30.0], [20.0, 70.0], [28.0, 110.0]]
        if args.quick:
            starts = starts[:2]
        print()
        prog = U.Progress(len(starts), "starts")
        results_ms = []
        for s in starts:
            before = obj_ms.n_simulations
            r = nelder_mead(obj_ms, s, initial_step=step, bounds=bounds,
                            xtol=args.xtol, ftol=args.ftol, max_iter=args.max_iter)
            r.n_simulations = obj_ms.n_simulations - before
            results_ms.append(r)
            prog.update(1)
        prog.close()
        best_ms = min(results_ms, key=lambda r: r.f)
        print()
        rows = [[f"({s[0]:g}, {s[1]:g})", f"({r.x[0]:.3f}, {r.x[1]:.3f})",
                 f"{r.f:.4f}", r.n_iterations, f"{r.n_simulations:,}",
                 "yes" if r.converged else "no"]
                for s, r in zip(starts, results_ms)]
        U.table(["start", "converged to", "objective", "iters", "sims", "converged"],
                rows, aligns="llrrrc",
                title="Nelder-Mead from four dispersed starting points")
        art.table("wp3_multistart", rows,
                  ["start_point", "converged_to", "objective_min", "iterations",
                   "simulations", "converged"],
                  caption="Multi-start Nelder-Mead: each start, where it converged, "
                          "and what it cost")
        spread = max(r.f for r in results_ms) - min(r.f for r in results_ms)
        print()
        U.kv("best of the multi-start", f"({best_ms.x[0]:.3f}, {best_ms.x[1]:.3f})  "
                                        f"-> {best_ms.f:.4f}")
        U.kv("objective spread across starts", f"{spread:.4f} min")
        if spread < 1.0:
            U.ok("All starts land on essentially the same objective value -- the "
                 "penalised surface is effectively unimodal in this box.")
        else:
            U.warn("Starts disagree by more than 1 minute: the surface has "
                   "multiple basins, so multi-start is not optional here.")

        # ------------------------------------------------------------------
        print()
        U.section("STEP 4  Budget comparison against the paper's grid search")
        grid = load_grid_baseline()
        nm_sims = obj.n_simulations
        ms_sims = obj_ms.n_simulations
        rows = []
        if grid:
            rows.append(["Grid search, coarse stage (paper's method)",
                         f"{grid['coarse']['points']:,}",
                         f"{grid['coarse']['reps']}",
                         f"{grid['coarse']['simulations']:,}",
                         f"{grid['coarse']['best_f']:.4f}"])
            rows.append(["Grid search, fine stage (paper's method)",
                         f"{grid['fine']['points']:,}",
                         f"{grid['fine']['reps']}",
                         f"{grid['fine']['simulations']:,}",
                         f"{grid['fine']['best_f']:.4f}"])
            rows.append(["Grid search, TOTAL", f"{grid['total_points']:,}", "-",
                         f"{grid['total_simulations']:,}",
                         f"{grid['fine']['best_f']:.4f}"])
        rows.append(["Nelder-Mead, single start (ours)",
                     f"{obj.n_evaluations:,}", f"{args.opt_reps}",
                     f"{nm_sims:,}", f"{nm.f:.4f}"])
        rows.append(["Nelder-Mead, 4 starts (ours)",
                     f"{obj_ms.n_evaluations:,}", f"{args.opt_reps}",
                     f"{ms_sims:,}", f"{best_ms.f:.4f}"])
        U.table(["method", "points evaluated", "reps/point",
                 "week-long simulations", "best objective (min)"],
                rows, aligns="lrrrr")
        art.table("wp3_budget_comparison", rows,
                  ["method", "points_evaluated", "reps_per_point",
                   "week_long_simulations", "best_objective_min"],
                  caption="Simulation budget required by brute-force grid search "
                          "versus the hand-implemented Nelder-Mead simplex")

        if grid:
            g_sims = grid["total_simulations"]
            print()
            U.kv("speed-up, single start",
                 f"{g_sims / max(1, nm_sims):.1f}x  fewer simulations "
                 f"({g_sims:,} -> {nm_sims:,})")
            U.kv("speed-up, 4-start",
                 f"{g_sims / max(1, ms_sims):.1f}x  fewer simulations "
                 f"({g_sims:,} -> {ms_sims:,})")
            art.note("grid_simulations", g_sims)
            art.note("nm_simulations", nm_sims)
            art.note("nm_speedup", round(g_sims / max(1, nm_sims), 2))
            print()
            U.note("The 'best objective' column is NOT comparable across rows "
                   "when the methods used different replication counts per "
                   "point -- a sample average over 50 streams is a different "
                   "estimator from one over 15.  STEP 6 therefore re-scores "
                   "every optimum on one identical, full-length batch; that is "
                   "the comparison to quote.")
        else:
            U.warn("No grid-search baseline found. Run "
                   "'python scripts/run_02_grid_search.py' first to produce "
                   "results/raw/wp3_grid_budget.json.")

        # ------------------------------------------------------------------
        if not args.no_scipy:
            print()
            U.section("STEP 5  Cross-check against scipy.optimize (not the primary result)")
            from scipy.optimize import minimize
            obj_sp = SimulationObjective(cfg, args.opt_reps, args.seed, args.workers,
                                         penalty_mu=args.penalty_mu, round_to=0.01)

            def f_sp(v):
                v = [min(max(v[0], bounds[0][0]), bounds[0][1]),
                     min(max(v[1], bounds[1][0]), bounds[1][1])]
                return obj_sp(v)

            sp = minimize(f_sp, x0, method="Nelder-Mead",
                          options={"xatol": args.xtol, "fatol": args.ftol,
                                   "maxiter": args.max_iter,
                                   "initial_simplex": [x0,
                                                       [x0[0] + step[0], x0[1]],
                                                       [x0[0], x0[1] + step[1]]]})
            rows = [["ours (hand-written)", f"({nm.x[0]:.3f}, {nm.x[1]:.3f})",
                     f"{nm.f:.4f}", nm.n_iterations, f"{obj.n_simulations:,}"],
                    ["scipy.optimize.minimize", f"({sp.x[0]:.3f}, {sp.x[1]:.3f})",
                     f"{sp.fun:.4f}", int(sp.nit), f"{obj_sp.n_simulations:,}"]]
            U.table(["implementation", "optimum", "objective", "iterations",
                     "simulations"], rows, aligns="llrrr")
            art.table("wp3_scipy_crosscheck", rows,
                      ["implementation", "optimum_k1_k2", "objective_min",
                       "iterations", "simulations"],
                      caption="Cross-check: our hand-written simplex against "
                              "SciPy's implementation on the identical objective")
            d = abs(nm.f - float(sp.fun))
            print()
            (U.ok if d < 0.5 else U.warn)(
                f"the two implementations agree on the objective to {d:.4f} min")

        # ------------------------------------------------------------------
        print()
        U.section("STEP 6  Confirming the optimum at full replication count")
        cand = [{"k1": float(best_ms.x[0]), "k2": float(best_ms.x[1])},
                {"k1": C.SBP_PAPER_OPTIMUM[0], "k2": C.SBP_PAPER_OPTIMUM[1]}]
        names = ["Nelder-Mead optimum", "paper optimum (13.1, 2.1)"]
        if grid:
            cand.insert(1, {"k1": grid["fine"]["best_x"][0],
                            "k2": grid["fine"]["best_x"][1]})
            names.insert(1, "grid-search optimum")
        prog = U.Progress(len(cand) * args.reps, "confirmation")
        batches = evaluate_points(cfg, "SBP", cand, args.reps, args.seed,
                                  args.workers, prog)
        prog.close()
        print()
        rows = []
        for nm_, pt, runs in zip(names, cand, batches):
            w = np.array([r.wait_total for r in runs])
            s3 = float(np.mean([r.sl_l3 for r in runs]))
            s4 = float(np.mean([r.sl_l4 for r in runs]))
            rows.append([nm_, f"({pt['k1']:.2f}, {pt['k2']:.2f})",
                         f"{w.mean():.2f}", f"{w.std(ddof=1):.2f}",
                         f"{s3*100:.2f}", f"{s4*100:.2f}",
                         "feasible" if (s3 >= C.SL_MIN[3] and s4 >= C.SL_MIN[4])
                         else "INFEASIBLE"])
        U.table(["setting", "(k1, k2)", "mean wait", "sd", "SL3 %", "SL4 %",
                 "constraint"], rows, aligns="llrrrrl")

        # Fair, like-for-like verdict: both optima scored on the same batch.
        scored = {}
        for nm_, runs in zip(names, batches):
            w = float(np.mean([r.wait_total for r in runs]))
            s3 = float(np.mean([r.sl_l3 for r in runs]))
            s4 = float(np.mean([r.sl_l4 for r in runs]))
            pen = args.penalty_mu * (max(0.0, C.SL_MIN[3] - s3)
                                     + max(0.0, C.SL_MIN[4] - s4))
            scored[nm_] = w + pen
        print()
        if grid and "grid-search optimum" in scored:
            gap = scored["Nelder-Mead optimum"] - scored["grid-search optimum"]
            U.kv("penalised objective, Nelder-Mead optimum",
                 f"{scored['Nelder-Mead optimum']:.4f} min")
            U.kv("penalised objective, grid optimum",
                 f"{scored['grid-search optimum']:.4f} min")
            U.kv("difference (Nelder-Mead - grid)", f"{gap:+.4f} min")
            art.note("objective_gap_vs_grid_common_scoring", round(gap, 4))
            print()
            g_sims = grid["total_simulations"]
            if gap <= 0.0:
                U.ok(f"Nelder-Mead found a solution at least as good as the "
                     f"lattice ({gap:+.3f} min) using {g_sims/max(1,ms_sims):.0f}x "
                     f"fewer simulations.")
            elif gap <= 0.25:
                U.ok(f"Nelder-Mead matched the lattice optimum to within "
                     f"{gap:.3f} min while using {g_sims/max(1,ms_sims):.0f}x "
                     f"fewer simulations.")
            else:
                U.warn(f"Nelder-Mead's optimum is {gap:.3f} min worse than the "
                       f"lattice's. The penalised surface has a long flat "
                       f"valley, so the simplex can stop early; tighten --xtol "
                       f"or add starting points.")
        art.table("wp3_optimum_confirmation", rows,
                  ["setting", "k1_k2", "mean_wait_min", "sd_min", "SL3_pct",
                   "SL4_pct", "constraint_status"],
                  caption=f"Optima from each method, re-evaluated at {args.reps} "
                          f"replications on identical streams")
        art.raw("wp3_nelder_mead_optimum",
                {"k1": float(best_ms.x[0]), "k2": float(best_ms.x[1]),
                 "objective": best_ms.f, "simulations": ms_sims,
                 "opt_reps": args.opt_reps})
        art.note("nelder_mead_optimum", [round(best_ms.x[0], 3), round(best_ms.x[1], 3)])

        # ------------------------------------------------------------------
        if not args.no_figures:
            print()
            U.section("Rendering figures")
            from src.plotting import convergence, heatmap_surface

            curves = {}
            if grid:
                # the lattice's best-so-far, in the order the points were visited
                curves["Grid search"] = (
                    [grid["coarse"]["simulations"],
                     grid["coarse"]["simulations"] + grid["fine"]["simulations"]],
                    [grid["coarse"]["best_f"], grid["fine"]["best_f"]])
            curves["Nelder-Mead"] = best_so_far(single_hist)
            curves["Nelder-Mead (multi-start)"] = best_so_far(obj_ms.history)
            fig, _ = convergence(curves,
                                 "Solution quality against simulation budget")
            art.figure(fig, "wp3_convergence",
                       "Best objective found so far versus the number of "
                       "week-long simulations consumed")

            if os.path.exists(GRID_SURFACE_FILE):
                with open(GRID_SURFACE_FILE, encoding="utf-8") as fh:
                    surf = json.load(fh)
                Z = np.array(surf["objective"])
                path = [(v[0][0], v[0][1]) for v in nm.best_path]
                fig, _ = heatmap_surface(
                    surf["k1s"], surf["k2s"],
                    np.clip(Z, None, np.percentile(Z, 97)),
                    "Nelder-Mead trajectory over the grid-search response surface",
                    "objective: mean wait + SLA penalty (min)",
                    mark=[(best_ms.x[0], best_ms.x[1], "*", "Nelder-Mead optimum"),
                          (C.SBP_PAPER_OPTIMUM[0], C.SBP_PAPER_OPTIMUM[1], "s",
                           "paper (13.1, 2.1)")],
                    path=path)
                art.figure(fig, "wp3_simplex_path",
                           "The simplex trajectory drawn on the response surface "
                           "that the brute-force lattice had to evaluate in full")
            else:
                U.note("run_02_grid_search.py has not been run, so the response "
                       "surface overlay is skipped.")

        print()
        finish(art, "WP3 complete. Next: python scripts/run_05_staffing_cost.py")


if __name__ == "__main__":
    main()
