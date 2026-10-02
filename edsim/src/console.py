"""
console.py -- terminal presentation helpers.

Every runner script is meant to *show* the simulation while it runs, not just
dump a file at the end.  This module supplies the shared vocabulary: banners,
progress bars, ASCII tables, sparkline/bar charts and a colour palette that
degrades gracefully when the terminal does not support ANSI.
"""
from __future__ import annotations

import os
import shutil
import sys
import time
from typing import Sequence

# ---------------------------------------------------------------------------
# Colour support
# ---------------------------------------------------------------------------
def _supports_colour() -> bool:
    if os.environ.get("NO_COLOR"):
        return False
    if not sys.stdout.isatty():
        return False
    if sys.platform == "win32":
        # Windows 10+ terminals understand VT sequences once enabled.
        try:
            import ctypes
            k = ctypes.windll.kernel32
            k.SetConsoleMode(k.GetStdHandle(-11), 7)
            return True
        except Exception:
            return False
    return True


_C = _supports_colour()


def _c(code: str) -> str:
    return code if _C else ""


RESET = _c("\033[0m")
BOLD = _c("\033[1m")
DIM = _c("\033[2m")
RED = _c("\033[31m")
GREEN = _c("\033[32m")
YELLOW = _c("\033[33m")
BLUE = _c("\033[34m")
MAGENTA = _c("\033[35m")
CYAN = _c("\033[36m")
GREY = _c("\033[90m")

POLICY_COLOUR = {"IFP": RED, "ALT": YELLOW, "SBP": GREEN,
                 "WSEPT": CYAN, "GCMU": MAGENTA}


def width(default: int = 100) -> int:
    try:
        return max(60, min(shutil.get_terminal_size().columns, 120))
    except Exception:
        return default


# ---------------------------------------------------------------------------
# Structure
# ---------------------------------------------------------------------------
def banner(title: str, subtitle: str = "") -> None:
    w = width()
    print()
    print(BOLD + BLUE + "=" * w + RESET)
    print(BOLD + BLUE + "  " + title + RESET)
    if subtitle:
        print(GREY + "  " + subtitle + RESET)
    print(BOLD + BLUE + "=" * w + RESET)


def section(title: str) -> None:
    w = width()
    print()
    print(BOLD + title + RESET)
    print(GREY + "-" * min(w, max(20, len(title) + 4)) + RESET)


def kv(key: str, value, unit: str = "", indent: int = 2) -> None:
    print(" " * indent + f"{key:<38s} {BOLD}{value}{RESET} {DIM}{unit}{RESET}")


def note(msg: str) -> None:
    print(f"  {DIM}{msg}{RESET}")


def ok(msg: str) -> None:
    print(f"  {GREEN}[OK]{RESET} {msg}")


def warn(msg: str) -> None:
    print(f"  {YELLOW}[!!]{RESET} {msg}")


def fail(msg: str) -> None:
    print(f"  {RED}[XX]{RESET} {msg}")


def saved(path: str) -> None:
    print(f"  {CYAN}saved{RESET} -> {path}")


# ---------------------------------------------------------------------------
# Progress
# ---------------------------------------------------------------------------
class Progress:
    """A minimal, dependency-free progress bar with ETA."""

    def __init__(self, total: int, label: str = "", bar_width: int = 34):
        self.total = max(1, total)
        self.label = label
        self.bar_width = bar_width
        self.n = 0
        self.t0 = time.time()
        self._last = 0.0
        self._enabled = sys.stdout.isatty()

    def update(self, k: int = 1, suffix: str = "") -> None:
        self.n += k
        now = time.time()
        if not self._enabled and self.n < self.total:
            return
        if now - self._last < 0.08 and self.n < self.total:
            return
        self._last = now
        frac = self.n / self.total
        filled = int(self.bar_width * frac)
        bar = "#" * filled + "." * (self.bar_width - filled)
        el = now - self.t0
        eta = (el / frac - el) if frac > 0 else 0.0
        line = (f"\r  {self.label:<26s} [{CYAN}{bar}{RESET}] "
                f"{self.n:>5d}/{self.total:<5d} {frac*100:5.1f}%  "
                f"{el:5.1f}s elapsed, {eta:5.1f}s left  {suffix}")
        sys.stdout.write(line[:width() + 40])
        sys.stdout.flush()
        if self.n >= self.total:
            sys.stdout.write("\n")
            sys.stdout.flush()

    def close(self) -> None:
        if self.n < self.total:
            self.n = self.total
            self.update(0)


# ---------------------------------------------------------------------------
# Tables
# ---------------------------------------------------------------------------
def table(headers: Sequence[str], rows: Sequence[Sequence], aligns: str = "",
          title: str = "", indent: int = 2) -> None:
    """Print a simple box-less ASCII table."""
    cols = len(headers)
    aligns = (aligns + "l" * cols)[:cols]
    body = [[("" if c is None else str(c)) for c in r] for r in rows]
    w = [max(len(headers[i]), *(len(r[i]) for r in body)) if body else len(headers[i])
         for i in range(cols)]
    pad = " " * indent

    def fmt(cells, bold=False):
        parts = []
        for i, c in enumerate(cells):
            parts.append(c.rjust(w[i]) if aligns[i] == "r" else c.ljust(w[i]))
        s = pad + "  ".join(parts)
        return (BOLD + s + RESET) if bold else s

    if title:
        print(f"{pad}{BOLD}{title}{RESET}")
    print(fmt(list(headers), bold=True))
    print(pad + GREY + "  ".join("-" * x for x in w) + RESET)
    for r in body:
        print(fmt(r))


def hbar(value: float, vmax: float, cells: int = 30, ch: str = "#") -> str:
    """A horizontal ASCII bar of ``value`` relative to ``vmax``."""
    if vmax <= 0:
        return ""
    k = int(round(cells * min(1.0, value / vmax)))
    return ch * k + "." * (cells - k)


_SPARK = "_.-=+*#%@"


def sparkline(values: Sequence[float]) -> str:
    """Compress a series into one line of characters (queue-length traces)."""
    if not values:
        return ""
    lo, hi = min(values), max(values)
    if hi <= lo:
        return _SPARK[0] * len(values)
    n = len(_SPARK) - 1
    return "".join(_SPARK[int(round(n * (v - lo) / (hi - lo)))] for v in values)


def fmt_p(p: float) -> str:
    """Format a p-value compactly."""
    if p == 0:
        return "<1e-300"
    if p < 1e-4:
        return f"{p:.3e}"
    return f"{p:.5f}"
