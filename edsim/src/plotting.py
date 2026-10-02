"""
plotting.py -- one shared visual language for every figure in the project.

Design decisions (and why)
--------------------------
* **Fixed colour-per-policy.**  A policy keeps its colour in every figure, and
  colours are assigned by *entity*, never by rank or by position in a filtered
  list.  Readers learn "blue = SBP" once.

* **Validated categorical palette.**  The five hues below were checked with a
  colour-vision-deficiency validator over ALL pairs:
      normal-vision worst pair   Delta E 16.3   (floor 15)  PASS
      CVD worst pair             Delta E  6.9   (target 8)  WARN
  Because the CVD separation lands in the 6-8 band, colour is never the ONLY
  channel carrying identity: every policy also gets its own MARKER and its own
  LINESTYLE, and every multi-series figure carries a legend.  Two of the hues
  fall below 3:1 contrast on a white surface, which is why series are always
  labelled rather than left to the colour alone.

* **One y-axis, always.**  No twin-axis charts anywhere in this project; when
  two quantities have different units they get two panels.

* **Recessive chrome.**  Light dashed y-grid only, no top/right spines, grid
  behind the data.

* **Sequential = one hue.**  The (k1,k2) response-surface heatmaps use a single
  blue ramp light->dark, never a rainbow, so lightness is monotone in the
  quantity plotted.  Each figure's title states which direction is good, since
  "high" is good for a service level and bad for a waiting time.

All figures are written to results/figures/ as 200-dpi PNG plus a PDF twin for
the report.
"""
from __future__ import annotations

import os
from typing import Dict, Optional, Sequence, Tuple

import matplotlib
matplotlib.use("Agg")                       # headless-safe; scripts save files
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap
import numpy as np

# ---------------------------------------------------------------------------
# Palette
# ---------------------------------------------------------------------------
POLICY_COLOUR: Dict[str, str] = {
    "IFP":   "#e34948",     # red     -- the paper's baseline
    "ALT":   "#eda100",     # yellow
    "SBP":   "#2a78d6",     # blue    -- the paper's proposal
    "WSEPT": "#1baf7a",     # aqua    -- our c-mu rule
    "GCMU":  "#4a3aa7",     # violet  -- our generalised c-mu rule
}
POLICY_MARKER: Dict[str, str] = {
    "IFP": "o", "ALT": "s", "SBP": "^", "WSEPT": "D", "GCMU": "v",
}
POLICY_LINESTYLE: Dict[str, str] = {
    "IFP": "-", "ALT": "--", "SBP": "-", "WSEPT": "-.", "GCMU": (0, (3, 1, 1, 1)),
}
POLICY_LABEL: Dict[str, str] = {
    "IFP": "IFP (Initial-First)",
    "ALT": "ALT (Alternating 1:1)",
    "SBP": "SBP (Slack-Based)",
    "WSEPT": "WSEPT (c-mu rule)",
    "GCMU": "Gc-mu (generalised c-mu)",
}

# Level colours (two-series charts): blue / orange, an unambiguous pair.
LEVEL_COLOUR = {3: "#2a78d6", 4: "#eb6834", "all": "#4a3aa7"}

SURFACE = "#ffffff"
INK = "#111111"
INK_SOFT = "#52514e"
GRID = "#dcdcda"

#: single-hue sequential ramp (light -> dark blue), for magnitude heatmaps
BLUE_STEPS = ["#cde2fb", "#b7d3f6", "#9ec5f4", "#86b6ef", "#6da7ec", "#5598e7",
              "#3987e5", "#2a78d6", "#256abf", "#1c5cab", "#184f95", "#104281",
              "#0d366b"]
SEQ_CMAP = LinearSegmentedColormap.from_list("edsim_blue", BLUE_STEPS)
#: diverging blue <-> gray <-> red for signed differences
DIV_CMAP = LinearSegmentedColormap.from_list(
    "edsim_div", ["#0d366b", "#2a78d6", "#f0efec", "#e34948", "#7a1f1f"])


def colour(policy: str) -> str:
    return POLICY_COLOUR.get(policy, "#52514e")


def marker(policy: str) -> str:
    return POLICY_MARKER.get(policy, "o")


def linestyle(policy: str):
    return POLICY_LINESTYLE.get(policy, "-")


def label(policy: str) -> str:
    return POLICY_LABEL.get(policy, policy)


# ---------------------------------------------------------------------------
# Global style
# ---------------------------------------------------------------------------
def use_style() -> None:
    plt.rcParams.update({
        "figure.facecolor": SURFACE,
        "axes.facecolor": SURFACE,
        "savefig.facecolor": SURFACE,
        "font.family": ["DejaVu Sans"],
        "font.size": 10,
        "axes.titlesize": 12,
        "axes.titleweight": "bold",
        "axes.labelsize": 10.5,
        "axes.labelcolor": INK,
        "axes.edgecolor": "#9a9a97",
        "axes.linewidth": 0.9,
        "axes.grid": True,
        "axes.axisbelow": True,          # grid behind the data
        "axes.spines.top": False,
        "axes.spines.right": False,
        "grid.color": GRID,
        "grid.linestyle": "--",
        "grid.linewidth": 0.7,
        "grid.alpha": 0.9,
        "xtick.color": INK_SOFT,
        "ytick.color": INK_SOFT,
        "xtick.labelsize": 9.5,
        "ytick.labelsize": 9.5,
        "legend.frameon": False,
        "legend.fontsize": 9.5,
        "lines.linewidth": 2.0,
        "lines.markersize": 6,
        "figure.dpi": 110,
        "savefig.dpi": 200,
        "savefig.bbox": "tight",
    })


use_style()

FIG_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       "results", "figures")


def save(fig, name: str, also_pdf: bool = True, outdir: Optional[str] = None) -> str:
    """Save ``fig`` as PNG (and PDF) into results/figures/, return the PNG path."""
    d = outdir or FIG_DIR
    os.makedirs(d, exist_ok=True)
    png = os.path.join(d, f"{name}.png")
    fig.savefig(png)
    if also_pdf:
        fig.savefig(os.path.join(d, f"{name}.pdf"))
    plt.close(fig)
    return png


def _grid_y(ax) -> None:
    ax.grid(axis="y", which="major")
    ax.grid(axis="x", visible=False)


# ---------------------------------------------------------------------------
# 1. Grouped box plot of waiting times by policy  (paper Figure 3)
# ---------------------------------------------------------------------------
def boxplot_waits(data: Dict[str, Dict[str, Sequence[float]]], title: str,
                  ylabel: str = "Average waiting time per replication (min)",
                  paper_ref: Optional[Dict[str, float]] = None):
    """``data[policy] = {"Level III": [...], "Level IV": [...], "All": [...]}``.

    Reproduces the paper's Figure 3 layout: three boxes per policy.  The three
    within-policy series are separated by lightness of the same policy hue plus
    a hatch on the middle box, so the grouping reads without relying on colour.
    """
    policies = list(data.keys())
    series = list(next(iter(data.values())).keys())
    fig, ax = plt.subplots(figsize=(1.9 * len(policies) + 3.2, 5.0))
    n_s = len(series)
    box_w = 0.72 / n_s
    hatches = ["", "///", ""]

    for pi, pol in enumerate(policies):
        base = colour(pol)
        for si, s in enumerate(series):
            pos = pi + (si - (n_s - 1) / 2) * box_w
            vals = np.asarray(data[pol][s], dtype=float)
            shade = _lighten(base, 0.55 - 0.25 * si)
            bp = ax.boxplot([vals], positions=[pos], widths=box_w * 0.88,
                            patch_artist=True, showfliers=True, manage_ticks=False,
                            flierprops=dict(marker=".", markersize=3.2,
                                            markerfacecolor=base,
                                            markeredgecolor="none", alpha=0.55),
                            medianprops=dict(color=INK, linewidth=1.5),
                            whiskerprops=dict(color=base, linewidth=1.1),
                            capprops=dict(color=base, linewidth=1.1),
                            boxprops=dict(facecolor=shade, edgecolor=base,
                                          linewidth=1.2))
            if hatches[si % len(hatches)]:
                bp["boxes"][0].set_hatch(hatches[si % len(hatches)])

    # paper reference markers, if supplied
    if paper_ref:
        for pi, pol in enumerate(policies):
            v = paper_ref.get(pol)
            if v is None:
                continue
            ax.plot([pi - 0.42, pi + 0.42], [v, v], color=INK, lw=1.4,
                    ls=(0, (2, 2)), zorder=5)
            ax.annotate(f"paper {v:.2f}", (pi + 0.42, v), xytext=(3, 0),
                        textcoords="offset points", fontsize=8, color=INK_SOFT,
                        va="center")

    ax.set_xticks(range(len(policies)))
    ax.set_xticklabels(policies)
    ax.set_ylabel(ylabel)
    ax.set_title(title, loc="left")
    _grid_y(ax)

    handles = [plt.Rectangle((0, 0), 1, 1, facecolor=_lighten("#52514e", 0.55 - 0.25 * i),
                             edgecolor="#52514e",
                             hatch=hatches[i % len(hatches)])
               for i in range(n_s)]
    ax.legend(handles, series, loc="upper left", ncols=n_s,
              bbox_to_anchor=(0, 1.02), borderaxespad=0)
    fig.tight_layout()
    return fig, ax


def _lighten(hex_colour: str, amount: float) -> str:
    """Blend ``hex_colour`` toward white by ``amount`` in [0,1]."""
    h = hex_colour.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    r = int(r + (255 - r) * amount)
    g = int(g + (255 - g) * amount)
    b = int(b + (255 - b) * amount)
    return f"#{r:02x}{g:02x}{b:02x}"


# ---------------------------------------------------------------------------
# 2. Policy comparison bar chart with CI whiskers
# ---------------------------------------------------------------------------
def bar_policies(values: Dict[str, float], errors: Optional[Dict[str, float]],
                 title: str, ylabel: str, annotate_fmt: str = "{:.2f}",
                 baseline: Optional[str] = None):
    """One bar per policy, direct-labelled (<= 5 series, so no legend needed)."""
    keys = list(values.keys())
    fig, ax = plt.subplots(figsize=(1.35 * len(keys) + 3.0, 4.4))
    xs = np.arange(len(keys))
    vals = [values[k] for k in keys]
    errs = [errors[k] for k in keys] if errors else None
    ax.bar(xs, vals, width=0.62,
                  color=[colour(k) for k in keys],
                  edgecolor=SURFACE, linewidth=2.0, zorder=3)
    if errs:
        ax.errorbar(xs, vals, yerr=errs, fmt="none", ecolor=INK,
                    elinewidth=1.2, capsize=4, zorder=4)
    top = max(v + (e if errs else 0) for v, e in zip(vals, errs or [0] * len(vals)))
    for x, v in zip(xs, vals):
        ax.annotate(annotate_fmt.format(v), (x, v), xytext=(0, 9),
                    textcoords="offset points", ha="center",
                    fontsize=9.5, fontweight="bold", color=INK)
    if baseline in values:
        ax.axhline(values[baseline], color=INK_SOFT, lw=1.0, ls=(0, (3, 3)),
                   zorder=2)
        ax.annotate(f"{baseline} baseline", (len(keys) - 0.45, values[baseline]),
                    xytext=(0, 4), textcoords="offset points", ha="right",
                    fontsize=8.5, color=INK_SOFT)
    ax.set_xticks(xs)
    ax.set_xticklabels(keys)
    ax.set_ylabel(ylabel)
    ax.set_ylim(0, top * 1.18)
    ax.set_title(title, loc="left")
    _grid_y(ax)
    fig.tight_layout()
    return fig, ax


# ---------------------------------------------------------------------------
# 3. Line chart over a scenario axis (sensitivity studies)
# ---------------------------------------------------------------------------
def line_by_policy(x: Sequence, series: Dict[str, Sequence[float]],
                   title: str, xlabel: str, ylabel: str,
                   xticklabels: Optional[Sequence[str]] = None,
                   direct_label: bool = True, logy: bool = False):
    """One line per policy: colour + marker + linestyle all carry identity."""
    fig, ax = plt.subplots(figsize=(7.6, 4.6))
    for pol, ys in series.items():
        ax.plot(x, ys, color=colour(pol), marker=marker(pol),
                linestyle=linestyle(pol), label=label(pol),
                markeredgecolor=SURFACE, markeredgewidth=1.0, zorder=3)
    # End-of-line labels, but only when they can actually be told apart.  The
    # separation is measured against the FULL plotted range, not the spread of
    # the end points: where every policy converges to the same value (e.g. the
    # richest staffing scenario) the labels would otherwise stack on top of one
    # another, and the legend already carries the identity.
    if direct_label and len(series) <= 6:
        all_vals = [v for ys in series.values() for v in ys]
        full = max(all_vals) - min(all_vals)
        ends = sorted(series.items(), key=lambda kv: kv[1][-1])
        spread = ends[-1][1][-1] - ends[0][1][-1]
        if full > 0 and spread >= 0.06 * full:
            sep = 0.045 * full
            placed = -float("inf")
            for pol, ys in ends:
                ylab = max(ys[-1], placed + sep)
                placed = ylab
                ax.annotate(pol, (x[-1], ylab), xytext=(7, 0),
                            textcoords="offset points", va="center",
                            fontsize=9, fontweight="bold", color=colour(pol))
    if logy:
        ax.set_yscale("log")
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    ax.set_title(title, loc="left")
    if xticklabels is not None:
        ax.set_xticks(list(x))
        ax.set_xticklabels(xticklabels)
    ax.legend(loc="best")
    ax.margins(x=0.10, y=0.06)
    _grid_y(ax)
    fig.tight_layout()
    return fig, ax


# ---------------------------------------------------------------------------
# 4. Response-surface heatmap over (k1, k2)
# ---------------------------------------------------------------------------
def heatmap_surface(k1s: Sequence[float], k2s: Sequence[float],
                    Z: np.ndarray, title: str, cbar_label: str,
                    mark: Optional[Sequence[Tuple[float, float, str, str]]] = None,
                    path: Optional[Sequence[Tuple[float, float]]] = None,
                    cmap=None):
    """Magnitude over the 2-D threshold space -- single-hue sequential ramp.

    ``mark`` items are ``(k1, k2, marker, text)`` annotations (e.g. the paper's
    optimum vs ours); ``path`` draws an optimiser trajectory on top.
    """
    fig, ax = plt.subplots(figsize=(7.4, 5.2))
    im = ax.pcolormesh(np.asarray(k1s), np.asarray(k2s), Z,
                       cmap=cmap or SEQ_CMAP, shading="auto")
    cb = fig.colorbar(im, ax=ax, pad=0.02)
    cb.set_label(cbar_label)
    cb.outline.set_visible(False)

    if path:
        px = [p[0] for p in path]
        py = [p[1] for p in path]
        ax.plot(px, py, color="#ffffff", lw=2.6, alpha=0.85, zorder=4)
        ax.plot(px, py, color="#e34948", lw=1.4, zorder=5,
                marker="o", markersize=3.4, label="Nelder-Mead path")
    if mark:
        for (a, b, mk, txt) in mark:
            ax.plot([a], [b], marker=mk, markersize=11, markerfacecolor="none",
                    markeredgecolor="#ffffff", markeredgewidth=3.0, zorder=6)
            ax.plot([a], [b], marker=mk, markersize=11, markerfacecolor="none",
                    markeredgecolor=INK, markeredgewidth=1.6, zorder=7)
            ax.annotate(txt, (a, b), xytext=(9, 8), textcoords="offset points",
                        fontsize=9, fontweight="bold", color=INK, zorder=8,
                        bbox=dict(boxstyle="round,pad=0.22", fc="#ffffffcc",
                                  ec="none"))
    ax.set_xlabel("$k_1$  (Level III slack, min)")
    ax.set_ylabel("$k_2$  (Level IV slack, min)")
    ax.set_title(title, loc="left")
    ax.grid(False)
    if path:
        ax.legend(loc="upper right")
    fig.tight_layout()
    return fig, ax


# ---------------------------------------------------------------------------
# 5. Optimiser convergence -- objective vs simulation budget
# ---------------------------------------------------------------------------
def convergence(curves: Dict[str, Tuple[Sequence[float], Sequence[float]]],
                title: str, xlabel: str = "cumulative week-long simulations",
                ylabel: str = "best penalised objective so far (min)",
                colours: Optional[Dict[str, str]] = None,
                logx: bool = True):
    """Best-so-far objective against simulation budget, one line per method."""
    fig, ax = plt.subplots(figsize=(7.6, 4.6))
    default = {"Grid search": "#e34948", "Nelder-Mead": "#2a78d6",
               "Nelder-Mead (multi-start)": "#4a3aa7"}
    mk = {"Grid search": "o", "Nelder-Mead": "^",
          "Nelder-Mead (multi-start)": "D"}
    for name, (xs, ys) in curves.items():
        c = (colours or default).get(name, "#52514e")
        ax.step(xs, ys, where="post", color=c, label=name, zorder=3)
        ax.plot([xs[-1]], [ys[-1]], marker=mk.get(name, "o"), color=c,
                markeredgecolor=SURFACE, markeredgewidth=1.2, zorder=4)
        ax.annotate(f"{ys[-1]:.2f}", (xs[-1], ys[-1]), xytext=(7, 0),
                    textcoords="offset points", va="center", fontsize=9,
                    fontweight="bold", color=c)
    if logx:
        ax.set_xscale("log")
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    ax.set_title(title, loc="left")
    ax.legend(loc="upper right")
    ax.margins(x=0.12)
    _grid_y(ax)
    fig.tight_layout()
    return fig, ax


# ---------------------------------------------------------------------------
# 6. Queue-length / occupancy trace of a single week
# ---------------------------------------------------------------------------
def queue_trace(times: Sequence[float], q3: Sequence[float], q4: Sequence[float],
                qf: Sequence[float], busy: Sequence[float], cap: Sequence[float],
                title: str):
    """Two stacked panels: queue lengths, and physicians busy vs rostered.

    Two panels rather than one twin-axis chart -- patients and physicians are
    different units and must never share a y-scale.
    """
    fig, axes = plt.subplots(2, 1, figsize=(9.4, 6.2), sharex=True,
                             gridspec_kw={"height_ratios": [2.1, 1],
                                          "hspace": 0.32})
    t = np.asarray(times) / 60.0                  # hours
    ax = axes[0]
    for ys, c, lab_, ls in ((q3, LEVEL_COLOUR[3], "Level III initial", "-"),
                            (q4, LEVEL_COLOUR[4], "Level IV initial", "--"),
                            (qf, "#1baf7a", "Follow-up", "-.")):
        ax.plot(t, ys, color=c, lw=1.3, ls=ls, label=lab_)
    ax.set_ylabel("patients waiting")
    ax.set_title(title, loc="left", pad=26)
    # legend in its own row ABOVE the axes, so it never sits on top of a peak
    ax.legend(loc="lower left", bbox_to_anchor=(0, 1.0), ncols=3,
              borderaxespad=0)
    ax.margins(y=0.06)
    _grid_y(ax)

    ax = axes[1]
    # busy first and filled, roster line LAST so it stays visible where the
    # two coincide (which, at ~86% utilisation, is most of the day)
    ax.step(t, busy, where="post", color="#4a3aa7", lw=1.4,
            label="physicians busy", zorder=3)
    ax.fill_between(t, 0, busy, step="post", color="#4a3aa7", alpha=0.15,
                    zorder=2)
    ax.step(t, cap, where="post", color=INK, lw=1.6, ls=(0, (4, 2)),
            label="physicians rostered $R^t$", zorder=5)
    ax.set_ylabel("physicians")
    ax.set_xlabel("simulated time (hours from Monday 00:00)")
    ax.set_ylim(0, max(cap) + 0.6)
    ax.legend(loc="lower left", bbox_to_anchor=(0, 1.0), ncols=2,
              borderaxespad=0)
    _grid_y(ax)

    for a in axes:
        for d in range(1, 7):
            a.axvline(d * 24, color=GRID, lw=0.8, zorder=1)
    return fig, axes


# ---------------------------------------------------------------------------
# 7. Arrival-rate profile (input validation)
# ---------------------------------------------------------------------------
def arrival_profile(rates: Sequence[Sequence[float]], day_names: Sequence[str],
                    empirical: Optional[Sequence[float]] = None,
                    title: str = "Non-homogeneous arrival intensity"):
    """Table-2 intensity across the week, with the simulated counts overlaid."""
    fig, ax = plt.subplots(figsize=(9.6, 4.2))
    flat = [r for day in rates for r in day]
    hours = np.arange(len(flat))
    ax.plot(hours, flat, color="#2a78d6", lw=1.8,
            label=r"Table 2 rate $\lambda_{d,h}$")
    if empirical is not None:
        ax.plot(hours, empirical, color="#eb6834", lw=1.1, ls="--", alpha=0.9,
                label="simulated arrivals (mean per hour)")
    ax.set_xticks(np.arange(0, len(flat) + 1, 24))
    ax.set_xticklabels(list(day_names) + [""])
    ax.set_xlabel("day of week")
    ax.set_ylabel("arrivals per hour")
    ax.set_title(title, loc="left")
    ax.legend(loc="upper right")
    ax.margins(x=0.01)
    _grid_y(ax)
    fig.tight_layout()
    return fig, ax


# ---------------------------------------------------------------------------
# 8. CRN variance-reduction figure
# ---------------------------------------------------------------------------
def crn_panel(pairs: Sequence[str], hw_ind: Sequence[float], hw_crn: Sequence[float],
              reps_ind: Sequence[float], reps_crn: Sequence[float],
              title: str):
    """Two panels: CI half-width, and replications needed for equal precision.

    With ten policy pairs the category axis is crowded, so the labels are
    rotated and the legends are lifted into their own row above each panel --
    otherwise they land on top of the tallest bars.
    """
    n = len(pairs)
    fig, axes = plt.subplots(1, 2, figsize=(max(11.0, 1.15 * n + 3.0), 5.4))
    x = np.arange(n)
    w = 0.38
    labels = [str(p).replace(chr(10), " ") for p in pairs]

    def panel(ax, a_vals, b_vals, ylabel, subtitle, log=False, fmt="{:.2f}"):
        ax.bar(x - w / 2, a_vals, w, color="#e34948", edgecolor=SURFACE,
               linewidth=2.0, label="independent streams", zorder=3)
        ax.bar(x + w / 2, b_vals, w, color="#2a78d6", edgecolor=SURFACE,
               linewidth=2.0, label="common random numbers", zorder=3)
        if log:
            ax.set_yscale("log")
            ax.set_ylim(max(0.7, min(b_vals) * 0.5), max(a_vals) * 6.0)
        else:
            ax.set_ylim(0, max(a_vals) * 1.22)
        for xi, (a, b) in enumerate(zip(a_vals, b_vals)):
            ax.annotate(fmt.format(a), (xi - w / 2, a), xytext=(0, 4),
                        textcoords="offset points", ha="center", fontsize=8,
                        color=INK_SOFT)
            ax.annotate(fmt.format(b), (xi + w / 2, b), xytext=(0, 4),
                        textcoords="offset points", ha="center", fontsize=8,
                        fontweight="bold", color=INK)
        ax.set_xticks(x)
        ax.set_xticklabels(labels, rotation=38, ha="right", fontsize=8.5)
        ax.set_ylabel(ylabel)
        ax.set_title(subtitle, loc="left", fontsize=11, pad=26)
        ax.legend(loc="lower left", bbox_to_anchor=(0, 1.0), ncols=2,
                  borderaxespad=0, fontsize=9)
        _grid_y(ax)

    panel(axes[0], list(hw_ind), list(hw_crn),
          "95% CI half-width of mean difference (min)",
          "Precision of the paired comparison")
    panel(axes[1], list(reps_ind), list(reps_crn),
          "replications for the same precision",
          "Cost of an equally precise answer", log=True, fmt="{:.0f}")

    fig.suptitle(title, x=0.005, ha="left", fontsize=12.5, fontweight="bold")
    fig.tight_layout(rect=(0, 0, 1, 0.94))
    return fig, axes


# ---------------------------------------------------------------------------
# 9. Cost decomposition for the staffing study (stacked bars)
# ---------------------------------------------------------------------------
def cost_stack(labels: Sequence[str], staff: Sequence[float],
               wait: Sequence[float], viol: Sequence[float],
               title: str, highlight: Optional[int] = None):
    """Stacked weekly cost, with a 2px surface gap between segments."""
    fig, ax = plt.subplots(figsize=(max(7.0, 0.62 * len(labels) + 3.0), 4.8))
    x = np.arange(len(labels))
    ax.bar(x, staff, 0.66, color="#2a78d6", edgecolor=SURFACE,
                linewidth=2.0, label="physician cost", zorder=3)
    ax.bar(x, wait, 0.66, bottom=staff, color="#eda100",
                edgecolor=SURFACE, linewidth=2.0, label="waiting cost", zorder=3)
    bot2 = np.asarray(staff) + np.asarray(wait)
    ax.bar(x, viol, 0.66, bottom=bot2, color="#e34948",
                edgecolor=SURFACE, linewidth=2.0, label="SLA penalty", zorder=3)
    totals = bot2 + np.asarray(viol)
    for xi, tv in zip(x, totals):
        ax.annotate(f"{tv/1000:.1f}k", (xi, tv), xytext=(0, 5),
                    textcoords="offset points", ha="center", fontsize=8.5,
                    fontweight="bold" if xi == highlight else "normal",
                    color=INK if xi == highlight else INK_SOFT)
    if highlight is not None:
        # placed well clear of the bar's own value label, and anchored to the
        # left so it cannot run off the edge when the winner is the first bar
        ax.annotate("cost-minimising roster", (highlight, totals[highlight]),
                    xytext=(10, 42), textcoords="offset points", ha="left",
                    fontsize=9.5, fontweight="bold", color="#2a78d6",
                    arrowprops=dict(arrowstyle="-|>", color="#2a78d6", lw=1.4,
                                    shrinkB=14,
                                    connectionstyle="angle3,angleA=0,angleB=90"))
    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=45, ha="right", fontsize=8.5)
    ax.set_ylabel("weekly cost (cost units)")
    ax.set_title(title, loc="left")
    ax.legend(loc="upper left", ncols=3)
    ax.set_ylim(0, totals.max() * 1.28)
    _grid_y(ax)
    fig.tight_layout()
    return fig, ax
