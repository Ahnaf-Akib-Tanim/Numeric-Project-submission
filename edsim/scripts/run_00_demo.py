"""
run_00_demo.py -- WATCH THE SIMULATION RUN.

This script exists to make the discrete-event machinery visible.  It does three
things, in order:

  1. EVENT TRACE      -- prints the future-event list being consumed, one event
                         at a time, for a configurable slice of simulated time:
                         arrivals, dispatch decisions, consultation starts and
                         ends, diagnostic device seizures, results returning.
  2. LIVE DASHBOARD   -- redraws an in-place console dashboard every simulated
                         hour: queue lengths as bars, physicians busy vs
                         rostered, running mean waits, the clock.
  3. WEEK SUMMARY     -- runs the full week for every policy on the SAME patient
                         stream and prints the side-by-side result, then saves
                         a queue/occupancy trace figure.

Nothing here is used by the other scripts; it is purely an inspection tool, and
the fastest way to convince yourself the engine does what the paper describes.

Examples
--------
    python scripts/run_00_demo.py                    # trace the first 3 hours
    python scripts/run_00_demo.py --policy SBP --trace-hours 6
    python scripts/run_00_demo.py --no-trace         # dashboard + summary only
    python scripts/run_00_demo.py --speed 0.02       # slow the dashboard down
"""
from __future__ import annotations

import sys
import time

from _common import base_parser, finish, show_header

from src import config as C
from src import console as U
from src.engine import Simulation
from src.metrics import RunResult
from src.policies import ALL_POLICIES, make_policy
from src.report import Artifact
from src.rng import clone_stream, generate_patient_stream


# ---------------------------------------------------------------------------
def clock(t: float) -> str:
    """Format simulated minutes as 'Day HH:MM'."""
    d = int(t // C.MINUTES_PER_DAY)
    rem = t % C.MINUTES_PER_DAY
    return f"{C.DAY_NAMES[d % 7]} {int(rem // 60):02d}:{int(rem % 60):02d}"


# ---------------------------------------------------------------------------
# 1. Event trace
# ---------------------------------------------------------------------------
def run_trace(cfg, policy_key, stream, hours: float, limit: int) -> None:
    U.section(f"1. Event trace -- policy {policy_key}, first {hours:g} simulated hours")
    U.note("Every line is one state transition inside the event loop. "
           "Columns: simulated clock | event | detail")
    print()
    horizon = hours * 60.0
    shown = {"n": 0}

    def tracer(now, msg, key):
        if now > horizon or shown["n"] >= limit:
            return
        shown["n"] += 1
        col = U.POLICY_COLOUR.get(key, "")
        head = msg.split()[0]
        print(f"  {U.GREY}{clock(now):>10s}{U.RESET} "
              f"{U.DIM}t={now:8.2f}{U.RESET}  {col}{head:<13s}{U.RESET}"
              f"{msg[len(head):]}")

    sim = Simulation(cfg, make_policy(policy_key), clone_stream(stream), trace=tracer)
    sim.run()
    print()
    U.note(f"({shown['n']} events shown; the full week processes "
           f"{sim.n_events:,} events)")


# ---------------------------------------------------------------------------
# 2. Live dashboard
# ---------------------------------------------------------------------------
def run_dashboard(cfg, policy_key, stream, days: float, speed: float) -> RunResult:
    U.section(f"2. Live dashboard -- policy {policy_key}, {days:g} simulated days")
    U.note("Redraws once per simulated hour.  Bars are queue lengths; "
           "the occupancy line is physicians busy / rostered.")
    print()

    sim = Simulation(cfg, make_policy(policy_key), clone_stream(stream))
    sim.record_history = True

    # Monkey-patch the dispatch hook to render once per simulated hour.
    state = {"next": 0.0, "lines": 0}
    horizon = days * C.MINUTES_PER_DAY
    orig = sim._dispatch

    def hooked(now):
        orig(now)
        if now >= state["next"] and now <= horizon:
            state["next"] = (int(now // 60) + 1) * 60.0
            render(sim, now, state)

    sim._dispatch = hooked                                   # type: ignore[method-assign]
    state["speed"] = speed
    res = sim.run()
    sys.stdout.write("\n")
    return res


_TTY = sys.stdout.isatty()


def render(sim, now, state) -> None:
    q3, q4, qf = len(sim.q3), len(sim.q4), len(sim.qf)
    cap = sim.pool.capacity_at(now)
    busy = sim.pool.busy
    served = sim.pool.n_consults
    biggest = max(24, q3, q4, qf)

    done = [p for p in sim.patients if p.wait_initial >= 0]
    mw = (sum(p.wait_initial for p in done) / len(done)) if done else 0.0

    lines = [
        f"  {U.BOLD}{clock(now):>10s}{U.RESET}  "
        f"{U.DIM}t = {now:8.1f} min{U.RESET}     "
        f"consultations completed: {U.BOLD}{served:5d}{U.RESET}     "
        f"mean initial wait so far: {U.BOLD}{mw:6.2f}{U.RESET} min",
        "",
        f"  Level III initial  {U.RED}{U.hbar(q3, biggest, 46)}{U.RESET} {q3:4d}",
        f"  Level IV  initial  {U.YELLOW}{U.hbar(q4, biggest, 46)}{U.RESET} {q4:4d}",
        f"  Follow-up          {U.CYAN}{U.hbar(qf, biggest, 46)}{U.RESET} {qf:4d}",
        "",
        f"  Physicians busy    {U.GREEN}{U.hbar(busy, cap, 46, '|')}{U.RESET} "
        f"{busy:2d}/{cap:<2d}  ({busy/cap*100 if cap else 0:5.1f}% of shift)",
    ]
    if _TTY:
        # redraw in place: jump back over the previous frame, then clear each row
        if state["lines"]:
            sys.stdout.write(f"\033[{state['lines']}A")
        for ln in lines:
            sys.stdout.write("\033[2K" + ln + "\n")
        state["lines"] = len(lines)
    else:
        # piped or redirected: no cursor control available, so print a frame
        # every 6 simulated hours to keep the captured log readable
        if int(now // 60) % 6 == 0:
            for ln in lines:
                sys.stdout.write(ln + "\n")
    sys.stdout.flush()
    if state.get("speed"):
        time.sleep(state["speed"])


# ---------------------------------------------------------------------------
# 3. Whole-week comparison on one shared patient stream
# ---------------------------------------------------------------------------
def run_summary(cfg, stream, art) -> None:
    U.section("3. One week, every policy, identical patient stream")
    U.note("Because the patient stream is generated up front, all five runs see "
           "exactly the same arrivals, triage levels, service times and exam "
           "requirements.  Every difference below is caused by scheduling alone.")
    print()
    rows = []
    traces = {}
    for key in ALL_POLICIES:
        t0 = time.time()
        sim = Simulation(cfg, make_policy(key), clone_stream(stream))
        sim.record_history = True
        r = sim.run()
        traces[key] = sim.queue_history
        rows.append([key,
                     f"{r.wait_total:.2f}", f"{r.wait_l3:.2f}", f"{r.wait_l4:.2f}",
                     f"{r.wait_init_l3:.2f}", f"{r.wait_init_l4:.2f}",
                     f"{r.wait_follow:.2f}",
                     f"{r.sl_l3*100:.1f}", f"{r.sl_l4*100:.1f}",
                     f"{r.physician_util*100:.1f}",
                     f"{r.n_pathway_done}", f"{r.n_unfinished}",
                     f"{time.time()-t0:.2f}"])
    U.table(
        ["policy", "W_total", "W_L3", "W_L4", "init L3", "init L4", "follow",
         "SL3 %", "SL4 %", "util %", "done", "unfin", "sec"],
        rows, aligns="l" + "r" * 12,
        title="Per-patient waiting time (min) and KPIs -- single replication")
    print()
    U.note("W_total / W_L3 / W_L4 are per-PATIENT totals (initial + follow-up "
           "wait); 'init' and 'follow' columns break that down per consultation.")

    art.table("demo_single_week_comparison",
              rows,
              ["policy", "W_total_min", "W_L3_min", "W_L4_min",
               "wait_initial_L3_min", "wait_initial_L4_min", "wait_followup_min",
               "SL_L3_pct", "SL_L4_pct", "physician_util_pct",
               "patients_completed", "patients_unfinished", "runtime_s"],
              caption="Single-replication, identical-stream comparison of all "
                      "five scheduling policies (demo run)")
    return traces


# ---------------------------------------------------------------------------
def main() -> None:
    p = base_parser("Interactive demonstration of the ED discrete-event simulator.")
    p.add_argument("--policy", default="SBP", choices=list(ALL_POLICIES),
                   help="policy used for the trace and the dashboard")
    p.add_argument("--trace-hours", type=float, default=3.0,
                   help="simulated hours of event trace to print")
    p.add_argument("--trace-limit", type=int, default=120,
                   help="hard cap on traced lines")
    p.add_argument("--dash-days", type=float, default=2.0,
                   help="simulated days shown in the live dashboard")
    p.add_argument("--speed", type=float, default=0.0,
                   help="seconds of real time per simulated hour (0 = as fast "
                        "as possible)")
    p.add_argument("--no-trace", action="store_true")
    p.add_argument("--no-dashboard", action="store_true")
    args = p.parse_args()

    cfg = C.DEFAULT_CONFIG
    show_header("ED PATIENT-FLOW SIMULATOR -- LIVE DEMONSTRATION",
                "run_00_demo.py  |  watch the discrete-event engine work",
                args, {"demo policy": args.policy})

    with Artifact("run_00_demo", args,
                  "Interactive demonstration: event trace, live queue dashboard, "
                  "and a single-week comparison of all five policies on one "
                  "shared patient stream.") as art:

        U.section("Generating the exogenous patient stream")
        t0 = time.time()
        stream = generate_patient_stream(cfg, args.seed)
        U.kv("patients generated", f"{len(stream):,}")
        U.kv("Level III share",
             f"{sum(p.level == 3 for p in stream)/len(stream)*100:.1f}", "%")
        U.kv("needing diagnostics",
             f"{sum(p.needs_exam for p in stream)/len(stream)*100:.1f}", "%")
        U.kv("mean initial consult",
             f"{sum(p.initial_duration for p in stream)/len(stream):.2f}", "min")
        U.kv("mean follow-up consult",
             f"{sum(p.follow_duration for p in stream)/len(stream):.2f}", "min")
        U.kv("generation time", f"{time.time()-t0:.3f}", "s")
        art.note("patients_in_stream", len(stream))

        if not args.no_trace:
            print()
            run_trace(cfg, args.policy, stream, args.trace_hours, args.trace_limit)

        if not args.no_dashboard:
            print()
            run_dashboard(cfg, args.policy, stream, args.dash_days, args.speed)

        print()
        traces = run_summary(cfg, stream, art)

        if not args.no_figures:
            print()
            U.section("Rendering the week trace")
            from src.plotting import queue_trace
            h = traces[args.policy]
            fig, _ = queue_trace([r[0] for r in h], [r[1] for r in h],
                                 [r[2] for r in h], [r[3] for r in h],
                                 [r[4] for r in h], [r[5] for r in h],
                                 f"One simulated week under {args.policy}: "
                                 f"queue lengths and physician occupancy")
            art.figure(fig, "demo_week_trace",
                       f"Queue lengths and physician occupancy over one "
                       f"simulated week under {args.policy}")

        finish(art, "Demo complete. Try: python scripts/run_01_validate_paper.py")


if __name__ == "__main__":
    main()
