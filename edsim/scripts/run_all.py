"""
run_all.py -- run the whole study, in dependency order, in one command.

Order matters:

    run_01  validate the engine                       (independent)
    run_02  the paper's grid search                   -> writes the budget
                                                         baseline + the response
                                                         surface used by run_04
    run_03  the c-mu policies                         (independent)
    run_04  Nelder-Mead vs grid search                <- needs run_02
                                                      -> writes the tuned (k1,k2)
    run_05  cost-optimal staffing                     <- uses run_04's optimum
    run_06  common random numbers                     (independent)
    run_07  sensitivity / robustness                  (independent)
    run_08  consolidated final comparison             <- uses run_04's optimum

Modes
-----
    --quick      every script in --quick mode.  About 5 minutes end to end;
                 numbers are indicative only.  Use this to check the pipeline.
    (default)    the settings reported in the write-up.  About 20 minutes on a
                 16-core machine, of which the brute-force grid search (run_02)
                 is roughly half -- and that expense is itself the WP3 result.
    --skip 2,7   skip individual scripts by number.
    --only 1,8   run only these.

Every child script writes its own tables, figures and provenance entry, so the
pipeline is restartable: re-running one script simply overwrites its outputs.

Usage
-----
    python scripts/run_all.py --quick
    python scripts/run_all.py
    python scripts/run_all.py --only 4,8 --reps 200
"""
from __future__ import annotations

import os
import subprocess
import sys
import time

from _common import base_parser

from src import console as U
from src.report import RESULTS

HERE = os.path.dirname(os.path.abspath(__file__))

PIPELINE = [
    (1, "run_01_validate_paper", "WP1  rebuild and validate the base paper", []),
    (2, "run_02_grid_search", "     the paper's brute-force grid search", []),
    (3, "run_03_wsept_policy", "WP2  c-mu / WSEPT policies", []),
    (4, "run_04_nelder_mead", "WP3  Nelder-Mead vs grid search", [2]),
    (5, "run_05_staffing_cost", "WP4  cost-optimal staffing", [4]),
    (6, "run_06_crn_variance", "WP5  common random numbers", []),
    (7, "run_07_sensitivity", "     sensitivity and robustness", []),
    (8, "run_08_final_comparison", "     consolidated final comparison", [4]),
]


def parse_list(s):
    if not s:
        return set()
    return {int(x) for x in s.replace(" ", "").split(",") if x}


def main() -> None:
    p = base_parser("Run the complete study end to end.")
    p.add_argument("--skip", default="", help="comma-separated script numbers to skip")
    p.add_argument("--only", default="", help="comma-separated script numbers to run")
    p.add_argument("--demo", action="store_true",
                   help="also run the interactive demo (run_00) first")
    p.add_argument("--stop-on-error", action="store_true",
                   help="abort the pipeline if any script fails")
    args = p.parse_args()

    skip = parse_list(args.skip)
    only = parse_list(args.only)

    plan = [t for t in PIPELINE
            if (not only or t[0] in only) and t[0] not in skip]

    U.banner("EMERGENCY DEPARTMENT PATIENT-FLOW STUDY -- FULL PIPELINE",
             "run_all.py  |  every work package, in dependency order")
    U.section("Plan")
    for n, mod, desc, deps in plan:
        dep = f"  (needs {', '.join(str(d) for d in deps)})" if deps else ""
        U.kv(f"[{n}] {mod}", desc + dep)
    U.kv("mode", "QUICK (indicative numbers)" if args.quick else "FULL")
    U.kv("replications", args.reps)
    U.kv("workers", args.workers)
    print()
    missing = [d for _, _, _, deps in plan for d in deps
               if d not in {t[0] for t in plan}]
    if missing:
        U.warn(f"scripts {sorted(set(missing))} are not in this run; the "
               f"dependent scripts will fall back to the paper's published "
               f"parameters and say so.")

    common = ["--reps", str(args.reps), "--seed", str(args.seed),
              "--workers", str(args.workers)]
    if args.quick:
        common.append("--quick")
    if args.no_figures:
        common.append("--no-figures")

    if args.demo:
        plan = [(0, "run_00_demo", "     interactive demonstration", [])] + plan

    t_all = time.time()
    outcomes = []
    for n, mod, desc, _ in plan:
        print()
        U.banner(f"[{n}]  {mod}.py", desc)
        cmd = [sys.executable, os.path.join(HERE, f"{mod}.py")] + common
        if mod == "run_00_demo":
            cmd += ["--no-dashboard"]
        t0 = time.time()
        rc = subprocess.call(cmd)
        dt = time.time() - t0
        outcomes.append((n, mod, rc, dt))
        if rc != 0:
            U.fail(f"{mod} exited with code {rc} after {dt:.1f}s")
            if args.stop_on_error:
                break
        else:
            U.ok(f"{mod} finished in {dt:.1f}s")

    print()
    U.banner("PIPELINE COMPLETE",
             f"total wall-clock {time.time()-t_all:.1f} s")
    rows = [[n, mod, "ok" if rc == 0 else f"FAILED ({rc})", f"{dt:.1f}"]
            for n, mod, rc, dt in outcomes]
    U.table(["#", "script", "status", "seconds"], rows, aligns="rllr")
    print()
    U.section("Where everything went")
    U.kv("tables (CSV + Markdown)", os.path.join(RESULTS, "tables"))
    U.kv("figures (PNG + PDF)", os.path.join(RESULTS, "figures"))
    U.kv("per-replication data + manifests", os.path.join(RESULTS, "raw"))
    U.kv("headline digest", os.path.join(RESULTS, "RESULTS_SUMMARY.md"))
    U.kv("full provenance log", os.path.join(RESULTS, "PROVENANCE.md"))
    print()
    if all(rc == 0 for _, _, rc, _ in outcomes):
        U.ok("All scripts completed successfully.")
    else:
        U.warn("Some scripts failed -- see the table above.")
    print()


if __name__ == "__main__":
    main()
