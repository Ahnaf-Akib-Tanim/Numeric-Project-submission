"""
_common.py -- shared bootstrap for every runner script.

Adds the project root to ``sys.path`` (so ``python scripts/run_xx.py`` works
from anywhere without installing a package), and defines the command-line
options that every script understands.

Every script accepts at minimum::

    --reps N        replications per policy      (default 100, the paper's)
    --seed S        base seed                    (default 20250402)
    --workers W     parallel processes           (default: cores - 2)
    --quick         a fast, low-fidelity pass for demos and smoke tests
    --no-figures    skip figure rendering
"""
from __future__ import annotations

import argparse
import os
import sys
import time

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from src import config as C                                  # noqa: E402
from src import console as U                                 # noqa: E402
from src.experiment import default_workers                   # noqa: E402


def base_parser(description: str) -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description=description,
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    p.add_argument("--reps", type=int, default=C.N_REPLICATIONS,
                   help="replications per policy")
    p.add_argument("--seed", type=int, default=C.BASE_SEED, help="base seed")
    p.add_argument("--workers", type=int, default=default_workers(),
                   help="parallel worker processes (1 = serial)")
    p.add_argument("--quick", action="store_true",
                   help="fast low-fidelity pass (fewer reps / coarser search)")
    p.add_argument("--no-figures", action="store_true", help="skip figures")
    return p


def show_header(title: str, subtitle: str, args, extra: dict | None = None) -> None:
    """Print the run banner and echo the exact settings in force."""
    U.banner(title, subtitle)
    U.section("Run settings")
    U.kv("replications per policy", args.reps)
    U.kv("base seed", args.seed)
    U.kv("worker processes", args.workers)
    U.kv("horizon", f"{C.HORIZON_MINUTES:.0f}", "min  (1 operational week)")
    U.kv("quick mode", "ON (results are indicative only)" if args.quick else "off")
    for k, v in (extra or {}).items():
        U.kv(k, v)


class Timer:
    def __init__(self, label: str):
        self.label = label

    def __enter__(self):
        self.t0 = time.time()
        return self

    def __exit__(self, *a):
        self.dt = time.time() - self.t0
        U.note(f"{self.label}: {self.dt:.1f} s")
        return False


def finish(art, extra_msg: str = "") -> None:
    """Uniform closing block telling the user where the outputs went."""
    U.section("Outputs")
    for o in art.outputs:
        U.saved(o["path"])
    U.note("provenance appended to results/PROVENANCE.md")
    if extra_msg:
        print()
        U.ok(extra_msg)
    print()
