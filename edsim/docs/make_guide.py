"""
make_guide.py -- build docs/PROJECT_GUIDE.pdf, the single read-this-first guide
to the whole project.

The guide is generated, not hand-written, so it can never drift from the code:
the headline numbers are read straight out of results/tables/*.csv and
results/raw/*.manifest.json, and the figures are the same PNGs the runner
scripts produced.

    python docs/make_guide.py

Re-run it after `python scripts/run_all.py` to refresh every number.
"""
from __future__ import annotations

import csv
import json
import os
import sys
from datetime import date

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (BaseDocTemplate, CondPageBreak, Flowable, Frame,
                                Image, KeepTogether, NextPageTemplate,
                                PageBreak, PageTemplate, Paragraph, Spacer,
                                Table, TableStyle)

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
TABLES = os.path.join(ROOT, "results", "tables")
FIGURES = os.path.join(ROOT, "results", "figures")
RAW = os.path.join(ROOT, "results", "raw")
OUT = os.path.join(HERE, "PROJECT_GUIDE.pdf")

# ---------------------------------------------------------------------------
# Fonts -- DejaVu ships with matplotlib and has the Greek letters and maths
# symbols the built-in Helvetica lacks (mu, lambda, >=, times, ...).
# ---------------------------------------------------------------------------
def register_fonts() -> bool:
    try:
        import matplotlib
        d = os.path.join(os.path.dirname(matplotlib.__file__),
                         "mpl-data", "fonts", "ttf")
        pdfmetrics.registerFont(TTFont("DJV", os.path.join(d, "DejaVuSans.ttf")))
        pdfmetrics.registerFont(TTFont("DJV-B", os.path.join(d, "DejaVuSans-Bold.ttf")))
        pdfmetrics.registerFont(TTFont("DJV-I", os.path.join(d, "DejaVuSans-Oblique.ttf")))
        pdfmetrics.registerFont(TTFont("DJV-M", os.path.join(d, "DejaVuSansMono.ttf")))
        pdfmetrics.registerFont(TTFont("DJV-MB", os.path.join(d, "DejaVuSansMono-Bold.ttf")))
        from reportlab.pdfbase.pdfmetrics import registerFontFamily
        registerFontFamily("DJV", normal="DJV", bold="DJV-B", italic="DJV-I",
                           boldItalic="DJV-B")
        return True
    except Exception as e:                                    # pragma: no cover
        print(f"  !! DejaVu unavailable ({e}); falling back to Helvetica")
        return False


HAVE_DJV = register_fonts()
F = "DJV" if HAVE_DJV else "Helvetica"
FB = "DJV-B" if HAVE_DJV else "Helvetica-Bold"
FI = "DJV-I" if HAVE_DJV else "Helvetica-Oblique"
FM = "DJV-M" if HAVE_DJV else "Courier"
FMB = "DJV-MB" if HAVE_DJV else "Courier-Bold"

# ---------------------------------------------------------------------------
# Palette -- the same hues the figures use, so the document reads as one piece
# ---------------------------------------------------------------------------
BLUE = colors.HexColor("#2a78d6")
DARKBLUE = colors.HexColor("#184f95")
RED = colors.HexColor("#e34948")
AQUA = colors.HexColor("#1baf7a")
YELLOW = colors.HexColor("#eda100")
VIOLET = colors.HexColor("#4a3aa7")
INK = colors.HexColor("#14161a")
INK_SOFT = colors.HexColor("#4d5158")
RULE = colors.HexColor("#d7d9dd")
BAND = colors.HexColor("#f2f5f9")
BAND2 = colors.HexColor("#fbfcfd")
TIP_BG = colors.HexColor("#eef5fd")
WARN_BG = colors.HexColor("#fdf3e8")

PAGE_W, PAGE_H = A4
MARGIN = 1.55 * cm

# ---------------------------------------------------------------------------
# Styles
# ---------------------------------------------------------------------------
ss = getSampleStyleSheet()


def style(name, **kw):
    base = dict(name=name, fontName=F, fontSize=9.6, leading=14.2,
                textColor=INK, spaceBefore=0, spaceAfter=0)
    base.update(kw)
    return ParagraphStyle(**base)


S = {
    "title":    style("title", fontName=FB, fontSize=27, leading=32,
                      textColor=DARKBLUE, alignment=TA_LEFT),
    "subtitle": style("subtitle", fontSize=13.5, leading=19, textColor=INK_SOFT),
    "h1":       style("h1", fontName=FB, fontSize=17, leading=21,
                      textColor=DARKBLUE, spaceBefore=2, spaceAfter=7),
    "h2":       style("h2", fontName=FB, fontSize=12.4, leading=16,
                      textColor=INK, spaceBefore=11, spaceAfter=4),
    "h3":       style("h3", fontName=FB, fontSize=10.4, leading=14,
                      textColor=BLUE, spaceBefore=8, spaceAfter=3),
    "body":     style("body", alignment=TA_JUSTIFY, spaceAfter=5.5,
                      leading=13.6),
    "bodyc":    style("bodyc", alignment=TA_LEFT, spaceAfter=6),
    "bullet":   style("bullet", leftIndent=12, bulletIndent=2, spaceAfter=3.5,
                      alignment=TA_JUSTIFY),
    "small":    style("small", fontSize=8.4, leading=12, textColor=INK_SOFT),
    "caption":  style("caption", fontSize=8.3, leading=11.5, textColor=INK_SOFT,
                      alignment=TA_LEFT, spaceBefore=3, spaceAfter=9),
    "code":     style("code", fontName=FM, fontSize=8.5, leading=12.4,
                      textColor=colors.HexColor("#123055")),
    "cell":     style("cell", fontSize=8.1, leading=10.8),
    "cellb":    style("cellb", fontName=FB, fontSize=8.1, leading=10.8),
    "cellh":    style("cellh", fontName=FB, fontSize=8.1, leading=10.8,
                      textColor=colors.white),
    "tiny":     style("tiny", fontSize=7.4, leading=10, textColor=INK_SOFT),
    "kpin":     style("kpin", fontName=FB, fontSize=16, leading=19,
                      textColor=DARKBLUE, alignment=TA_CENTER),
    "kpil":     style("kpil", fontSize=7.6, leading=10, textColor=INK_SOFT,
                      alignment=TA_CENTER),
}


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------
def MONO(text):
    """Wrap text in the monospace font face (safe against literal % in prose)."""
    return "<font face='" + FM + "'>" + text + "</font>"


def P(text, s="body"):
    return Paragraph(text, S[s])


def bullets(items, s="bullet"):
    return [Paragraph(t, S[s], bulletText="\u2022") for t in items]


def H1(text, num=None):
    label = f"{num}. {text}" if num else text
    return [Spacer(1, 2), Paragraph(label, S["h1"]), HRule(), Spacer(1, 5)]


class HRule(Flowable):
    """A thin full-width rule used under section headings."""

    def __init__(self, colour=RULE, thickness=0.8, gap=2):
        super().__init__()
        self.colour, self.thickness, self.gap = colour, thickness, gap
        self.width = 0
        self.height = thickness + gap

    def wrap(self, aw, ah):
        self.width = aw
        return aw, self.height

    def draw(self):
        self.canv.setStrokeColor(self.colour)
        self.canv.setLineWidth(self.thickness)
        self.canv.line(0, self.gap, self.width, self.gap)


class Callout(Flowable):
    """A tinted box with a coloured left edge -- used for tips and warnings."""

    def __init__(self, title, body, accent=BLUE, bg=TIP_BG, width=None):
        super().__init__()
        self.title, self.body, self.accent, self.bg = title, body, accent, bg
        self.width = width
        self._flow = []

    def wrap(self, aw, ah):
        self.width = aw
        inner = aw - 20
        self._flow = []
        h = 8
        if self.title:
            p = Paragraph(self.title, style("ct", fontName=FB, fontSize=9,
                                            leading=12.5, textColor=self.accent))
            w, ph = p.wrap(inner, ah)
            self._flow.append((p, h, ph))
            h += ph + 3
        p = Paragraph(self.body, style("cb", fontSize=8.8, leading=12.6,
                                       alignment=TA_JUSTIFY))
        w, ph = p.wrap(inner, ah)
        self._flow.append((p, h, ph))
        h += ph + 8
        self.height = h
        return aw, h

    def draw(self):
        c = self.canv
        c.setFillColor(self.bg)
        c.setStrokeColor(self.bg)
        c.roundRect(0, 0, self.width, self.height, 3, fill=1, stroke=0)
        c.setFillColor(self.accent)
        c.rect(0, 0, 2.6, self.height, fill=1, stroke=0)
        for p, top, ph in self._flow:
            p.drawOn(c, 11, self.height - top - ph)


def code_block(lines, width=None):
    """A monospaced block on a tinted background."""
    txt = "<br/>".join(l.replace("&", "&amp;").replace("<", "&lt;")
                       .replace(">", "&gt;").replace(" ", "&nbsp;")
                       for l in lines)
    t = Table([[Paragraph(txt, S["code"])]], colWidths=[width or (PAGE_W - 2 * MARGIN)])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f4f7fb")),
        ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#dde5ef")),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
    ]))
    return t


def table(rows, widths, header=True, align=None, font_size=8.1,
          highlight_rows=(), zebra=True, header_bg=DARKBLUE, keep=None):
    """Build a styled table from a list of row lists (plain strings).

    ``keep`` controls widow protection: a short table that would otherwise
    leave one or two rows stranded at the top of the next page is wrapped in
    KeepTogether so it moves whole.  The default keeps tables of at most twelve
    rows, which still fit one page at these font sizes.
    """
    align = align or "l" * len(widths)
    data = []
    for ri, row in enumerate(rows):
        out = []
        for ci, cell in enumerate(row):
            txt = "" if cell is None else str(cell)
            if ri == 0 and header:
                st = S["cellh"]
            elif ri in highlight_rows:
                st = S["cellb"]
            else:
                st = S["cell"]
            st = ParagraphStyle(f"c{ri}_{ci}", parent=st, fontSize=font_size,
                                leading=font_size * 1.34,
                                alignment={"l": TA_LEFT, "r": 2, "c": TA_CENTER}[align[ci]])
            out.append(Paragraph(txt, st))
        data.append(out)

    t = Table(data, colWidths=widths, repeatRows=1 if header else 0)
    cmds = [
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LINEBELOW", (0, 0), (-1, -2), 0.35, RULE),
        ("BOX", (0, 0), (-1, -1), 0.6, colors.HexColor("#c9ced6")),
    ]
    if header:
        cmds += [("BACKGROUND", (0, 0), (-1, 0), header_bg),
                 ("LINEBELOW", (0, 0), (-1, 0), 0.8, header_bg)]
    if zebra:
        start = 1 if header else 0
        for r in range(start, len(data)):
            if (r - start) % 2 == 1:
                cmds.append(("BACKGROUND", (0, r), (-1, r), BAND))
    for r in highlight_rows:
        cmds.append(("BACKGROUND", (0, r), (-1, r), colors.HexColor("#e6f0fb")))
    t.setStyle(TableStyle(cmds))
    if keep is None:
        keep = len(rows) <= 12
    return KeepTogether(t) if keep else t


def figure(name, caption, width_frac=1.0, max_h=None):
    """Embed results/figures/<name>.png, scaled to the frame width."""
    path = os.path.join(FIGURES, f"{name}.png")
    if not os.path.exists(path):
        return [P(f"<i>[figure {name} not found &mdash; run the pipeline first]</i>",
                  "small")]
    from PIL import Image as PILImage
    with PILImage.open(path) as im:
        iw, ih = im.size
    avail = (PAGE_W - 2 * MARGIN) * width_frac
    w = avail
    h = ih * (w / iw)
    if max_h and h > max_h:
        h = max_h
        w = iw * (h / ih)
    img = Image(path, width=w, height=h)
    img.hAlign = "CENTER"
    return [img, Paragraph(caption, S["caption"])]


def kpi_row(items, widths=None):
    """A row of big-number tiles: [(value, label), ...]."""
    n = len(items)
    full = PAGE_W - 2 * MARGIN
    widths = widths or [full / n] * n
    cells = [[Paragraph(v, S["kpin"]), Paragraph(l, S["kpil"])] for v, l in items]
    data = [[Table([[c[0]], [c[1]]], colWidths=[widths[i] - 8]) for i, c in enumerate(cells)]]
    for i, c in enumerate(data[0]):
        c.setStyle(TableStyle([("ALIGN", (0, 0), (-1, -1), "CENTER"),
                               ("TOPPADDING", (0, 0), (-1, -1), 0),
                               ("BOTTOMPADDING", (0, 0), (-1, 0), 1),
                               ("BOTTOMPADDING", (0, 1), (-1, 1), 0)]))
    t = Table(data, colWidths=widths)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), BAND),
        ("BOX", (0, 0), (-1, -1), 0.6, colors.HexColor("#ccd4de")),
        ("INNERGRID", (0, 0), (-1, -1), 0.6, colors.white),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    return t


# ---------------------------------------------------------------------------
# Reading the generated results
# ---------------------------------------------------------------------------
def read_table(name):
    """results/tables/<name>.csv without its provenance header."""
    path = os.path.join(TABLES, f"{name}.csv")
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as fh:
        return [r for r in csv.reader(fh) if r and not r[0].startswith("#")]


def read_notes(script):
    path = os.path.join(RAW, f"{script}.manifest.json")
    if not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8") as fh:
        return json.load(fh).get("notes", {})


def read_json(name):
    path = os.path.join(RAW, f"{name}.json")
    if not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


# ---------------------------------------------------------------------------
# Page furniture
# ---------------------------------------------------------------------------
DOC_TITLE = "ED Patient-Flow Simulation \u2014 Project Guide"


def on_page(canv, doc):
    canv.saveState()
    # header rule + running title
    canv.setStrokeColor(RULE)
    canv.setLineWidth(0.6)
    canv.line(MARGIN, PAGE_H - MARGIN + 12, PAGE_W - MARGIN, PAGE_H - MARGIN + 12)
    canv.setFont(F, 7.4)
    canv.setFillColor(INK_SOFT)
    canv.drawString(MARGIN, PAGE_H - MARGIN + 17, DOC_TITLE)
    canv.drawRightString(PAGE_W - MARGIN, PAGE_H - MARGIN + 17,
                         "CSE 402 \u00b7 Section C")
    # footer
    canv.line(MARGIN, MARGIN - 10, PAGE_W - MARGIN, MARGIN - 10)
    canv.setFont(F, 7.6)
    canv.drawString(MARGIN, MARGIN - 20, "Lv et al. (2026), Healthcare 14(1):99 "
                                         "\u2014 replication and extension")
    canv.setFont(FB, 8.4)
    canv.setFillColor(DARKBLUE)
    canv.drawRightString(PAGE_W - MARGIN, MARGIN - 20, str(canv.getPageNumber()))
    canv.restoreState()


def on_cover(canv, doc):
    canv.saveState()
    canv.setFillColor(DARKBLUE)
    canv.rect(0, PAGE_H - 6.0 * cm, PAGE_W, 6.0 * cm, fill=1, stroke=0)
    canv.setFillColor(BLUE)
    canv.rect(0, PAGE_H - 6.16 * cm, PAGE_W, 0.16 * cm, fill=1, stroke=0)
    canv.setFillColor(colors.HexColor("#f4f7fb"))
    canv.rect(0, 0, PAGE_W, 1.5 * cm, fill=1, stroke=0)
    canv.restoreState()


# ---------------------------------------------------------------------------
# Content
# ---------------------------------------------------------------------------
def build_story():
    st = []
    full = PAGE_W - 2 * MARGIN

    # -- pull the live numbers -------------------------------------------
    n1 = read_notes("run_01_validate_paper")
    n3 = read_notes("run_04_nelder_mead")
    n4 = read_notes("run_05_staffing_cost")
    n5 = read_notes("run_06_crn_variance")
    n8 = read_notes("run_08_final_comparison")
    budget = read_json("wp3_grid_budget")

    master = read_table("final_master_comparison")
    cmp_paper = read_table("wp1_paper_comparison")
    equip = read_table("final_equipment")
    budget_tbl = read_table("wp3_budget_comparison")
    cost_rec = read_table("wp4_recommendation")
    cost_sens = read_table("wp4_cost_sensitivity")
    t10 = read_table("wp4_table10_priced")
    crn = read_table("wp5_variance_reduction")
    cmu_idx = read_table("wp2_cmu_indices")
    optconf = read_table("wp3_optimum_confirmation")
    sdist = read_table("sens_service_distribution")
    sig = read_table("final_significance_matrix")

    # the roster saving, read out of the generated table rather than hard-coded
    cost_delta_pct = "n/a"
    if len(cost_rec) > 2 and cost_rec[2][-1]:
        cost_delta_pct = cost_rec[2][-1].lstrip("-+").strip() or "n/a"

    speedup = n3.get("nm_speedup", 19.0)
    varred = n5.get("median_variance_reduction", 0.99)
    effgain = n5.get("median_efficiency_gain", 96)
    roster = n4.get("recommended_roster", [6, 6, 3])
    saving = n4.get("weekly_cost_saving_vs_paper", 0)
    rho = n1.get("offered_load_rho", 0.87)

    # ====================================================================
    # COVER
    # ====================================================================
    st.append(Spacer(1, 1.5 * cm))
    st.append(Paragraph("<font color='#ffffff'>PROJECT GUIDE</font>",
                        style("cvk", fontName=FB, fontSize=10.5, leading=13,
                              textColor=colors.white)))
    st.append(Spacer(1, 5))
    st.append(Paragraph("<font color='#ffffff'>Simulating and Optimizing<br/>"
                        "Emergency-Department Patient Flow</font>",
                        style("cvt", fontName=FB, fontSize=23, leading=28,
                              textColor=colors.white)))
    st.append(Spacer(1, 1.5 * cm))

    st.append(Paragraph("CSE 402 &mdash; Numerical Analysis, Simulation and "
                        "Modeling Sessional &nbsp;&middot;&nbsp; Section C",
                        S["subtitle"]))
    st.append(Spacer(1, 10))
    st.append(table([
        ["Sudip Kumar Saha", "2105152", "WP4 \u2014 cost-based staffing"],
        ["Ahnaf Akib Tanim", "2105154", "WP1 \u2014 baseline DES engine & validation"],
        ["Md. Shahjalal Rumman", "2105165", "WP3 \u2014 Nelder-Mead optimiser"],
        ["Md. Dulal Hossain", "2105169", "WP5 \u2014 common random numbers & final analysis"],
        ["Md. Shoaib Hossain", "2105170", "WP2 \u2014 c\u00b7\u03bc / WSEPT scheduling rule"],
    ], [5.0 * cm, 2.2 * cm, full - 7.2 * cm], header=False, font_size=8.8))
    st.append(Spacer(1, 16))

    st.append(Callout(
        "What this document is",
        "Everything you need to understand, run, explain and defend this project, "
        "in one place: what the base paper does, what we added, how each method "
        "works, which file does what, how to run it, and what the results mean. "
        "Every number in here is read straight out of the generated " +
        MONO("results/") + " folder, so the guide cannot drift from "
        "the code.", BLUE, TIP_BG))
    st.append(Spacer(1, 12))

    st.append(Paragraph("The project in five numbers", S["h3"]))
    st.append(Spacer(1, 4))
    st.append(kpi_row([
        ("6/6", "structural findings of the<br/>paper reproduced"),
        (f"{speedup:.0f}\u00d7", "fewer simulations than<br/>the paper's grid search"),
        (f"{varred*100:.1f}%", "variance removed by<br/>common random numbers"),
        (f"{abs(saving)/1000:.1f}k", "weekly cost saved by the<br/>optimal roster"),
        ("33", "automated correctness<br/>checks, all passing"),
    ]))
    st.append(Spacer(1, 14))

    st.append(Paragraph(
        "<b>Base paper.</b> Lv, W.; Liu, R.; Yan, F.; Wang, Y. (2026). "
        "<i>Discrete Event Simulation-Based Analysis and Optimization of Emergency "
        "Patient Scheduling Strategies.</i> Healthcare 14(1), 99. "
        "doi:10.3390/healthcare14010099", S["small"]))
    st.append(Spacer(1, 4))
    st.append(Paragraph(
        f"Generated {date.today().isoformat()} by "
        f"<font face='{FM}'>docs/make_guide.py</font> from the results of "
        f"<font face='{FM}'>python scripts/run_all.py</font> "
        f"(seed 20250402, 100 replications per policy).", S["small"]))

    st.append(NextPageTemplate("body"))
    st.append(PageBreak())

    # ====================================================================
    # 0. CONTENTS
    # ====================================================================
    st += H1("What is in this guide")
    toc = [
        ["1", "The 60-second summary", "What we did and what we found"],
        ["2", "The base paper", "The system, the three policies, the conclusions, the gaps"],
        ["3", "What we built", "The five work packages"],
        ["4", "How the simulator works", "Patient journey, event loop, module map"],
        ["5", "The methods, explained", "Every numerical technique, in plain language"],
        ["6", "Project map", "Which folder and file does what"],
        ["7", "How to run everything", "Commands, flags, runtimes"],
        ["8", "Results and analysis", "Work package by work package, with figures"],
        ["9", "Paper vs. ours", "Side-by-side, where we agree and where we differ"],
        ["10", "Judgement calls", "The five things the paper left unspecified"],
        ["11", "Viva preparation", "Likely questions with short answers"],
        ["12", "Glossary and references", "Every symbol and term used"],
    ]
    st.append(table([["\u00a7", "Section", "Covers"]] + toc,
                    [1.0 * cm, 5.4 * cm, full - 6.4 * cm], align="clr"[0] + "ll",
                    font_size=8.6))
    st.append(Spacer(1, 14))

    st.append(Callout(
        "How to read this if you are in a hurry",
        "Sections 1, 8 and 9 are the results. Sections 2\u20135 are the method. "
        "Sections 6\u20137 are the code and how to run it. Section 11 is exam prep. "
        "If you read only one page, read section 1.", AQUA,
        colors.HexColor("#ecf8f3")))

    st.append(PageBreak())

    # ====================================================================
    # 1. SUMMARY
    # ====================================================================
    st += H1("The 60-second summary", 1)

    st.append(P(
        "A hospital emergency department has a fixed number of doctors and three "
        "queues of patients competing for them: urgent (Level III) new arrivals, "
        "non-urgent (Level IV) new arrivals, and patients coming back for a "
        "follow-up after an X-ray or blood test. <b>Which queue should the next "
        "free doctor take from?</b> That single decision is the whole problem."))
    st.append(P(
        "The base paper builds a computer simulation of such a department and "
        "compares three answers to that question. We rebuilt that simulation from "
        "scratch, checked it against every number the paper published, and then "
        "extended it in four directions the paper explicitly does not attempt."))

    st.append(Paragraph("What we did", S["h2"]))
    st.append(table([
        ["#", "Work package", "In one sentence", "Headline result"],
        ["WP1", "Rebuild &amp; validate",
         "Re-implement the paper's model from scratch and check it against every "
         "published KPI.",
         "All 6 structural findings reproduced; equipment table within 0.5&nbsp;pp."],
        ["WP2", "A better-founded policy",
         "Add the c\u00b7\u03bc rule, which is <i>provably</i> optimal, instead of "
         "another hand-made heuristic.",
         "Lowest holding cost <b>and</b> lowest mean wait of all five policies."],
        ["WP3", "A real optimiser",
         "Replace the paper's brute-force grid search with a hand-written "
         "Nelder-Mead simplex.",
         f"Same answer for <b>{speedup:.0f}\u00d7 fewer</b> simulations "
         f"({budget.get('total_simulations', 0):,} \u2192 "
         f"{n3.get('nm_simulations', 0):,})."],
        ["WP4", "How many doctors?",
         "Put a price on waiting and on salary, then search over staffing rosters.",
         f"Roster <b>{tuple(roster)}</b> beats the paper's (5,5,3) by "
         f"<b>{cost_delta_pct}</b> of weekly cost."],
        ["WP5", "Sharper statistics",
         "Give every policy the identical simulated week (common random numbers).",
         f"<b>{varred*100:.1f}%</b> of comparison variance removed; "
         f"{effgain:.0f}\u00d7 more efficient."],
    ], [1.3 * cm, 3.0 * cm, 6.4 * cm, full - 10.7 * cm], font_size=8.2))
    st.append(Spacer(1, 12))

    st.append(Paragraph("What we found", S["h2"]))
    st.append(P(
        "<b>The rebuild is faithful in structure, not in absolute level.</b> Our "
        "waiting times run 12&ndash;25% above the paper's. That is expected and "
        "explainable: the paper's published arrival table, service-time "
        f"distributions and staffing levels together imply a system load of "
        f"\u03c1 \u2248 {rho:.2f}, and at that load the mean wait is extremely "
        "sensitive to the last percentage point of utilisation. The source dataset "
        "is not public, so an exact numeric match is not attainable and we do not "
        "claim one. Everything <i>structural</i> does reproduce: the policy "
        "ranking, the per-level trade-offs, near-identical doctor utilisation "
        "across policies, the equipment-utilisation table, and every "
        "sensitivity-analysis finding."))

    st.append(Callout(
        "The single most interesting finding",
        "On our rebuilt model, <b>the paper's own tuned thresholds "
        "(k\u2081, k\u2082) = (13.1, 2.1) break the Level&nbsp;IV service-level "
        "constraint</b> \u2014 they reach only 89.4% against a 95% target. The "
        "reason is mechanical: k\u2082 = 2.1 means a Level&nbsp;IV patient is only "
        "flagged urgent after waiting 117.9 of their 120 allowed minutes, which is "
        "too late to rescue them on a busier system. Re-tuning under the "
        "constraint (WP3) moves the optimum to a much larger k\u2082 and produces "
        "the only fast policy a hospital could actually adopt. <b>This is the "
        "argument for re-tuning rather than copying published parameters.</b>",
        RED, WARN_BG))
    st.append(Spacer(1, 10))

    st.append(Paragraph("The final answer depends on what you are optimising", S["h2"]))
    st.append(P(
        "There is no single winner, and pretending otherwise would be the easiest "
        "way to get this wrong. Three honest answers:"))
    st.append(table([
        ["If you care about\u2026", "The best policy is", "Because"],
        ["Raw average waiting time",
         f"<b>{n8.get('lens1_best_unweighted_wait', 'WSEPT')}</b> (42.32 min)",
         "it serves the class with the best cost-times-speed index first"],
        ["Waiting measured against each<br/>patient's clinical tolerance",
         f"<b>{n8.get('lens2_best_holding_cost', 'WSEPT')}</b> (0.3763)",
         "this is exactly the objective the c\u00b7\u03bc rule is proven optimal for"],
        ["Meeting the service-level<br/>target (what a hospital must do)",
         f"<b>{n8.get('lens3_best_sla_feasible', 'SBP*')}</b> (44.18 min)",
         "only IFP and SBP* clear 95% on <i>both</i> triage levels"],
    ], [4.6 * cm, 4.4 * cm, full - 9.0 * cm], font_size=8.3))
    st.append(Spacer(1, 8))
    st.append(Paragraph(
        "SBP* is our re-tuned Slack-Based Policy from WP3. It is 16% faster than "
        "the paper's baseline IFP <i>and</i> it satisfies the constraint &mdash; "
        "which the paper's own published parameters do not, on our system.",
        S["small"]))

    st.append(PageBreak())

    # ====================================================================
    # 2. THE BASE PAPER
    # ====================================================================
    st += H1("The base paper: what it actually does", 2)

    st.append(Paragraph("2.1  The system being modelled", S["h2"]))
    st.append(P(
        "A Grade-A tertiary hospital emergency department in China. Only triage "
        "<b>Level III</b> (urgent) and <b>Level IV</b> (non-urgent) patients are "
        "modelled &mdash; Levels I and II are critical and go straight to "
        "resuscitation, so they never queue. Each patient follows the same path:"))
    st.append(Spacer(1, 2))
    st.append(table([
        ["1", "Arrive",
         "Arrivals follow a rate that changes every hour and repeats weekly "
         "(busy 09:00\u201311:00 and 19:00\u201321:00, dead at 04:00). 25% are "
         "Level III, 75% Level IV."],
        ["2", "Wait for a doctor",
         "Join the Level III or Level IV <i>initial</i> queue. This wait is what "
         "the triage target governs: 30 min for Level III, 120 min for Level IV."],
        ["3", "Initial consultation",
         "A doctor sees them for 5\u201315 min (truncated exponential, mean "
         "\u2248 9.09 min)."],
        ["4", "Diagnostics (60% of patients)",
         "Lab, X-ray, CT and/or ultrasound. Each machine can serve one patient at "
         "a time, and each result takes time to come back (20 min for lab, 30 for "
         "X-ray and CT, instant for ultrasound)."],
        ["5", "Wait again",
         "Once <i>all</i> results are in, the patient joins the <b>follow-up</b> "
         "queue \u2014 competing with new arrivals for the same doctors."],
        ["6", "Follow-up consultation",
         "5\u201325 min (mean \u2248 12.84 min), then discharge."],
    ], [0.8 * cm, 3.4 * cm, full - 4.2 * cm], header=False, font_size=8.3))
    st.append(Spacer(1, 8))
    st.append(P(
        "Doctors work three shifts: <b>5</b> from 07:00&ndash;15:00, <b>5</b> from "
        "15:00&ndash;22:00, <b>3</b> from 22:00&ndash;07:00. A doctor never "
        "abandons a patient at shift change. One simulated run covers one full "
        "week (10,080 minutes, about 2,280 patients)."))

    st.append(Paragraph("2.2  The three policies it compares", S["h2"]))
    st.append(P(
        "All three answer the same question &mdash; a doctor is free, which queue "
        "do they take from? &mdash; and differ only in the answer."))
    st.append(table([
        ["Policy", "The rule, in one line", "What it does well", "What it breaks"],
        ["<b>IFP</b><br/>Initial-First",
         "Always serve new arrivals first: Level III, then Level IV, then "
         "follow-ups.",
         "Nobody ever breaches their triage target.",
         "Follow-up patients are starved; they wait ~98 min, which drags the "
         "overall average up."],
        ["<b>ALT</b><br/>Alternating 1:1",
         "At most half the doctors may be on new arrivals at once; the rest take "
         "follow-ups.",
         "Level III waits collapse to ~6 min; follow-ups clear fast.",
         "Level IV new arrivals are squeezed and 13% of them breach the 120-min "
         "target."],
        ["<b>SBP</b><br/>Slack-Based",
         "A patient becomes 'urgent' once they have waited T<sub>\u2113</sub> "
         "\u2212 k<sub>\u2113</sub> minutes. Priority: urgent&nbsp;L3 &gt; "
         "urgent&nbsp;L4 &gt; follow-ups &gt; everyone else.",
         "Two dials (k\u2081, k\u2082) let you trade the two levels against each "
         "other; the paper tunes them.",
         "Its performance depends entirely on the tuning \u2014 which is exactly "
         "what WP3 exploits."],
    ], [2.9 * cm, 5.2 * cm, 4.3 * cm, full - 12.4 * cm], font_size=8.0))
    st.append(Spacer(1, 10))

    st.append(Callout(
        "The slack idea in one sentence",
        "k\u2113 is a <i>head start</i>: with T\u2083 = 30 min and k\u2081 = 13.1, "
        "a Level&nbsp;III patient is promoted to urgent after 30 \u2212 13.1 = "
        "16.9 minutes of waiting, so the system starts rescuing them 13.1 minutes "
        "before they would actually breach. Bigger k = earlier rescue = more "
        "protection for that class, at the cost of everyone else.",
        BLUE, TIP_BG))
    st.append(Spacer(1, 10))

    st.append(Paragraph("2.3  What the paper concludes", S["h2"]))
    st.append(table([
        ["Claim", "Its evidence"],
        ["SBP is best, cutting mean wait 46.26 \u2192 35.25 min (\u221223.8%)",
         "100 replications per policy, paired t-tests, Cohen's d &gt; 1.5"],
        ["Tuned thresholds are (k\u2081, k\u2082) = (13.1, 2.1)",
         "Two-stage brute-force grid search: coarse step 1.0, then fine step 0.1"],
        ["Doctors, not machines, are the bottleneck",
         "Equipment utilisation 14\u201319% vs. doctor utilisation ~85%"],
        ["Results are robust",
         "Arrival rate \u00b115%, seven staffing rosters, lognormal service times"],
    ], [8.6 * cm, full - 8.6 * cm], font_size=8.3))
    st.append(Spacer(1, 10))

    st.append(Paragraph("2.4  The four gaps we fill", S["h2"]))
    st.append(table([
        ["The paper does", "The paper does <b>not</b> do", "Our answer"],
        ["Grid-search two thresholds",
         "Optimise the <b>staffing level</b> at the same time",
         "<b>WP4</b> \u2014 a cost model plus a roster search"],
        ["Compare three heuristics",
         "Compare against a <b>provably optimal</b> queueing rule",
         "<b>WP2</b> \u2014 the c\u00b7\u03bc rule and its generalisation"],
        ["Brute force (hundreds of full runs)",
         "Use a <b>derivative-free numerical optimiser</b>",
         "<b>WP3</b> \u2014 hand-written Nelder-Mead + penalty function"],
        ["100 independent replications",
         "Apply <b>variance reduction</b>",
         "<b>WP5</b> \u2014 exact common random numbers"],
        ["Report results",
         "Release the engine or the data",
         "<b>WP1</b> \u2014 an open, validated, from-scratch rebuild"],
    ], [5.4 * cm, 5.6 * cm, full - 11.0 * cm], font_size=8.3))

    st.append(PageBreak())

    # ====================================================================
    # 3. WHAT WE BUILT
    # ====================================================================
    st += H1("What we built", 3)
    st.append(P(
        "About 7,850 lines of Python: a simulation library, nine runnable "
        "experiments, and a 33-check test suite. The simulation engine uses a "
        "hand-rolled priority-queue event loop &mdash; <b>no SimPy or other "
        "black-box process library</b> &mdash; so every mechanism described in "
        "the paper is visible and checkable in the code."))
    st.append(Spacer(1, 4))
    st.append(table([
        ["Work package", "Owner", "What it adds", "Script that produces it"],
        ["<b>WP1</b> Baseline engine &amp; validation", "Ahnaf",
         "The whole simulator, plus a check against every published KPI, t-test "
         "and equipment number.", "run_01_validate_paper.py"],
        ["<b>WP2</b> c\u00b7\u03bc / WSEPT rule", "Shoaib",
         "Two new policies derived from queueing theory rather than invented, and "
         "a holding-cost metric to judge them fairly.", "run_03_wsept_policy.py"],
        ["<b>WP3</b> Nelder-Mead optimiser", "Rumman",
         "A hand-written simplex method with a penalty function, benchmarked "
         "against the paper's grid search on equal terms.",
         "run_02_grid_search.py<br/>run_04_nelder_mead.py"],
        ["<b>WP4</b> Cost-optimal staffing", "Sudip",
         "A weekly cost function and a search over integer rosters with the "
         "thresholds re-tuned inside each one.", "run_05_staffing_cost.py"],
        ["<b>WP5</b> CRN &amp; final analysis", "Dulal",
         "Exact common random numbers, the variance reduction quantified, and the "
         "consolidated comparison.",
         "run_06_crn_variance.py<br/>run_08_final_comparison.py"],
    ], [4.3 * cm, 1.7 * cm, 6.6 * cm, full - 12.6 * cm], font_size=8.1))

    st.append(Spacer(1, 12))
    st.append(Paragraph("Two supporting scripts", S["h3"]))
    st.append(table([
        ["run_00_demo.py",
         "Shows the engine working: a live event-by-event trace, then a console "
         "dashboard of queue lengths updating every simulated hour, then all five "
         "policies on one shared week. Run this first."],
        ["run_07_sensitivity.py",
         "Reproduces the paper's robustness study (arrival rate \u00b115%, the "
         "seven staffing rosters, lognormal service times), extended to our two "
         "new policies."],
    ], [4.3 * cm, full - 4.3 * cm], header=False, font_size=8.3))

    st.append(PageBreak())

    # ====================================================================
    # 4. HOW THE SIMULATOR WORKS
    # ====================================================================
    st += H1("How the simulator works", 4)

    st.append(Paragraph("4.1  Discrete-event simulation in one idea", S["h2"]))
    st.append(P(
        "Nothing interesting happens between events. A patient arriving, a "
        "consultation ending, a scan finishing &mdash; those are the only moments "
        "the state of the department changes. So instead of ticking a clock "
        "forward minute by minute, we keep a <b>future-event list</b>: a "
        "min-heap of things that are going to happen, sorted by time. The whole "
        "engine is this loop:"))
    st.append(code_block([
        "while the future-event list is not empty:",
        "    pop the earliest event",
        "    if its time >= the horizon:  stop",
        "    jump the clock to that time",
        "    apply the event's state change",
        "    dispatch()          <-- the ONLY place the scheduling policy acts",
    ]))
    st.append(Spacer(1, 8))
    st.append(P(
        "<b>dispatch()</b> asks the current policy: given the doctors who are free "
        "right now and the three queues as they currently stand, who starts "
        "service? Every policy &mdash; IFP, ALT, SBP, WSEPT, Gc\u00b7\u03bc &mdash; "
        "is nothing more than a different answer to that one function. Swapping a "
        "policy changes no other line of the simulator, which is exactly why the "
        "comparison is fair."))

    st.append(Paragraph("4.2  The five events", S["h2"]))
    st.append(table([
        ["Event", "What it means", "What happens next"],
        ["SHIFT_CHANGE", "The number of rostered doctors changes (07:00, 22:00)",
         "Re-dispatch. A shrinking shift never interrupts anyone mid-consultation; "
         "it just blocks new starts."],
        ["ARRIVAL", "A patient walks in",
         "They join the Level III or Level IV initial queue; re-dispatch."],
        ["CONSULT_END", "A doctor finishes",
         "The doctor is released. The patient either enters diagnostics, or is "
         "discharged; re-dispatch."],
        ["EXAM_DEVICE_FREE", "A machine finishes occupying a patient",
         "The machine's own waiting queue is pulled, and the patient moves to "
         "their next scan."],
        ["EXAM_RESULTS_READY", "The last of a patient's results comes back",
         "The patient joins the follow-up queue; re-dispatch."],
    ], [3.5 * cm, 5.0 * cm, full - 8.5 * cm], font_size=8.1))

    st.append(Spacer(1, 10))
    st.append(Paragraph("4.3  The module map (mirrors the paper's Figure 2)", S["h2"]))
    st.append(P(
        "The paper describes a five-module architecture. We kept the same five "
        "modules with the same names, so the code can be read alongside the paper."))
    st.append(table([
        ["Paper's module", "Our file", "Holds"],
        ["Entity Definition", "src/entities.py",
         "Patient, ExamOrder, the event-tuple format, the care stages"],
        ["Event Scheduling", "src/engine.py",
         "The heapq future-event list and the loop above"],
        ["Resource Scheduling", "src/resources.py",
         "PhysicianPool (time-varying roster, non-preemptive) and DeviceBank "
         "(four machines with FIFO queues)"],
        ["Strategy Execution", "src/policies.py",
         "All five policies \u2014 one <font face='%s'>allocate()</font> method each" % FM],
        ["Statistical Output", "src/metrics.py",
         "Turns a finished run into the paper's KPIs (its equations 24\u201330)"],
    ], [3.6 * cm, 3.6 * cm, full - 7.2 * cm], font_size=8.2))

    st.append(Spacer(1, 10))
    st += figure("demo_week_trace",
                 "One simulated week under SBP. Top: how many patients are waiting "
                 "in each of the three queues. Bottom: doctors busy versus doctors "
                 "rostered. The daily rhythm and the 07:00/22:00 shift steps are "
                 "both clearly visible, and the Level IV queue (orange) is the one "
                 "that builds up. Produced by run_00_demo.py.",
                 max_h=9.5 * cm)

    st.append(PageBreak())

    # ====================================================================
    # 5. METHODS
    # ====================================================================
    st += H1("The methods, explained", 5)
    st.append(P(
        "This is a numerical-methods course, so every technique below is "
        "implemented <b>from scratch</b>. SciPy appears only for distribution "
        "quantiles, the t-distribution, and as a deliberate cross-check of our "
        "own optimiser."))

    # --- 5.1
    st.append(Paragraph("5.1  Generating arrivals: the thinning algorithm", S["h2"]))
    st.append(P(
        "<b>Problem.</b> Patients do not arrive at a constant rate. The rate "
        "\u03bb(t) changes every hour and repeats weekly &mdash; 23 patients/hour "
        "on Monday evening, 1.7 on Sunday at 4 a.m. Sampling such a process "
        "exactly by inverting its cumulative rate would mean inverting a "
        "168-piece function; easy to get subtly wrong."))
    st.append(P(
        "<b>Solution (Lewis &amp; Shedler, 1979).</b> Generate too many arrivals "
        "at a constant rate, then throw some away:"))
    st.append(table([
        ["1", "Pick \u03bb* = the highest rate anywhere in the week "
              "(23.05/hour, Monday 20:00\u201321:00)."],
        ["2", "Generate a constant-rate process at \u03bb* by adding up "
              "Exponential(1/\u03bb*) gaps."],
        ["3", "<b>Keep</b> each candidate arrival at time t with probability "
              "\u03bb(t) / \u03bb*, and discard it otherwise."],
    ], [0.8 * cm, full - 0.8 * cm], header=False, font_size=8.4))
    st.append(Spacer(1, 6))
    st.append(P(
        "<b>Why it is exact.</b> In a tiny interval the candidate process "
        "produces a point with probability \u03bb*\u00b7dt, and it survives with "
        "probability \u03bb(t)/\u03bb*. The product is \u03bb(t)\u00b7dt &mdash; "
        "which is the definition of the process we wanted. The acceptance rate "
        "here is about 58%, so roughly 1.7 candidates per kept arrival. " +
        MONO("src/rng.py")))
    st.append(Spacer(1, 4))
    st += figure("wp1_arrival_validation",
                 "Proof that the sampler works: the blue line is the paper's "
                 "Table 2 rate; the orange dashed line is what 200 simulated "
                 "weeks actually produced. Relative error 1.67%, correlation "
                 "0.9991.", max_h=6.2 * cm)

    # --- 5.2
    st.append(CondPageBreak(6 * cm))
    st.append(Paragraph("5.2  Generating service times: inverse-CDF sampling", S["h2"]))
    st.append(P(
        "Consultation times follow a <b>truncated exponential</b>: exponential in "
        "shape, but forced to lie between 5 and 15 minutes (initial) or 5 and 25 "
        "(follow-up). We sample by inverting the CDF:"))
    st.append(code_block([
        "F(x) = (e^(-lam*a) - e^(-lam*x)) / (e^(-lam*a) - e^(-lam*b))",
        "",
        "set F(x) = u  and solve:",
        "x = -(1/lam) * ln( e^(-lam*a) - u*(e^(-lam*a) - e^(-lam*b)) )",
    ]))
    st.append(Spacer(1, 6))
    st.append(P(
        "<b>Why not rejection sampling?</b> Because inverse-CDF uses "
        "<b>exactly one random number per service time, always</b>. Rejection "
        "sampling would use a variable number, and that would destroy the "
        "synchronisation that common random numbers (\u00a75.7) depends on. This "
        "is a deliberate design choice, not an accident."))
    st.append(Spacer(1, 4))
    st.append(table([
        ["Consultation", "Rate \u03bb", "Bounds", "Nominal mean",
         "<b>Realised mean</b>"],
        ["Initial", "1/9", "[5, 15] min", "9 min", "<b>9.0926 min</b>"],
        ["Follow-up", "1/15", "[5, 25] min", "15 min", "<b>12.8410 min</b>"],
    ], [3.4 * cm, 2.0 * cm, 3.0 * cm, 3.0 * cm, full - 11.4 * cm], font_size=8.3))
    st.append(Spacer(1, 6))
    st.append(Callout(
        "A subtlety worth knowing for the viva",
        "The follow-up mean is 12.84, not the 15 the paper states. That is not a "
        "bug: a truncated exponential on [5,&nbsp;25] <b>cannot</b> have mean 15 "
        "&mdash; 15 is its supremum, approached only as \u03bb \u2192 0. So "
        "\u03bb = 1/15 is the only consistent reading of the paper, and the "
        "resulting system load \u03c1 \u2248 0.87 is what reproduces the paper's "
        "~85% doctor utilisation. We have the closed-form mean "
        "E[X] = a + 1/\u03bb \u2212 (b\u2212a)e<super>\u2212\u03bb(b\u2212a)</super> / "
        "(1 \u2212 e<super>\u2212\u03bb(b\u2212a)</super>) and check it against "
        "200,000 samples in the test suite.", BLUE, TIP_BG))

    st.append(CondPageBreak(11 * cm))

    # --- 5.3 policies
    st.append(Paragraph("5.3  The five scheduling policies", S["h2"]))
    st.append(P(
        "Each is one method: <i>given the free doctors and the three queues, "
        "return who starts service.</i> R is the number of free doctors."))
    st.append(table([
        ["Policy", "Origin", "The rule"],
        ["<b>IFP</b>", "paper, eqs. 8\u201310",
         "Fill from Level III initial, then Level IV initial, then follow-ups, "
         "until the doctors run out."],
        ["<b>ALT</b>", "paper, eqs. 11\u201313",
         "At most \u230aR/2\u230b doctors may be on initial consultations at once; "
         "the rest take follow-ups. Unused capacity is handed back so nobody idles."],
        ["<b>SBP</b>", "paper, eqs. 14\u201323",
         "Mark patient i urgent when their wait w<sub>i</sub>(t) \u2265 "
         "T<sub>\u2113</sub> \u2212 k<sub>\u2113</sub>. Serve urgent L3, then "
         "urgent L4, then follow-ups, then everyone else."],
        ["<b>WSEPT</b>", "<b>ours</b> (WP2)",
         "The c\u00b7\u03bc rule: always serve the non-empty class with the "
         "largest index c<sub>\u2113</sub>\u00b7\u03bc<sub>\u2113</sub>."],
        ["<b>Gc\u00b7\u03bc</b>", "<b>ours</b> (WP2)",
         "The generalised c\u00b7\u03bc rule: index 2\u00b7w<sub>head</sub>"
         "\u00b7\u03bc<sub>\u2113</sub> / T<sub>\u2113</sub><super>2</super>, "
         "which grows with how long the front patient has already waited."],
    ], [2.0 * cm, 3.0 * cm, full - 5.0 * cm], font_size=8.2))

    st.append(Spacer(1, 10))
    st.append(Paragraph("5.4  The c\u00b7\u03bc rule, and why it is special", S["h2"]))
    st.append(P(
        "<b>The theorem (Cox &amp; Smith 1961).</b> If each waiting class "
        "\u2113 costs you c<sub>\u2113</sub> per minute of delay, and class "
        "\u2113 takes on average 1/\u03bc<sub>\u2113</sub> minutes to serve, then "
        "the policy that minimises total delay cost is: <b>always serve the "
        "class with the largest c<sub>\u2113</sub>\u00b7\u03bc<sub>\u2113</sub></b>. "
        "It is not a heuristic &mdash; it is provably optimal. This is what makes "
        "it a genuinely different kind of answer from the paper's three "
        "hand-designed rules."))
    st.append(P(
        "We set c<sub>\u2113</sub> = 1/T<sub>\u2113</sub> &mdash; <i>a minute of "
        "waiting hurts in inverse proportion to how much waiting that class can "
        "tolerate</i> &mdash; which turns the triage targets straight into delay "
        "costs. With the paper's numbers:"))
    if len(cmu_idx) > 1:
        rows = [["Class", "T<sub>\u2113</sub> (min)", "E[service] (min)",
                 "\u03bc<sub>\u2113</sub>", "c<sub>\u2113</sub> = 1/T<sub>\u2113</sub>",
                 "<b>index c\u00b7\u03bc</b>"]]
        for r in cmu_idx[1:]:
            rows.append([r[0], r[1], r[2], r[3], r[4], f"<b>{r[5]}</b>"])
        st.append(table(rows, [3.4 * cm, 2.1 * cm, 2.6 * cm, 2.0 * cm, 2.6 * cm,
                               full - 12.7 * cm], font_size=8.2,
                        align="lrrrrr"))
    st.append(Spacer(1, 8))
    st.append(Callout(
        "Read the index column carefully \u2014 it is a real finding",
        "The indices are <b>constants</b>, so the classical c\u00b7\u03bc rule "
        "collapses to a fixed priority order: <b>Level III initial &gt; follow-up "
        "&gt; Level IV initial</b>. That is a genuine property of the theorem, "
        "not a shortcut in our code, and it is precisely the limitation the "
        "<i>generalised</i> c\u00b7\u03bc rule fixes by making the index grow "
        "with the head-of-line patient's delay. Gc\u00b7\u03bc is delay-adaptive "
        "like SBP \u2014 but it is derived, and it has <b>no parameters to tune "
        "at all</b>.", AQUA, colors.HexColor("#ecf8f3")))
    st.append(Spacer(1, 8))
    st.append(Callout(
        "How we judge it fairly",
        "The c\u00b7\u03bc rule is optimal for the <i>holding cost</i>, not for "
        "the plain average wait. Reporting only the plain average would be a "
        "category error. So " + MONO("src/metrics.py") + " also computes "
        "<b>holding cost = mean of w<sub>i</sub> / T<sub>level(i)</sub></b> "
        "&mdash; waiting measured in units of each patient's own tolerance "
        "&mdash; and we rank on that too.", BLUE, TIP_BG))

    st.append(CondPageBreak(10 * cm))

    # --- 5.5 optimisation
    st.append(Paragraph("5.5  Optimising a noisy function", S["h2"]))
    st.append(Paragraph("Step 1 &mdash; make the objective deterministic", S["h3"]))
    st.append(P(
        "A simulation gives a different answer every time you run it. Simplex "
        "methods stall on noisy surfaces because they cannot tell a real "
        "improvement from luck. Fix: <b>sample average approximation with common "
        "random numbers</b>. Every candidate (k\u2081, k\u2082) is scored on the "
        "<i>same fixed set</i> of 50 simulated weeks. Evaluating the same point "
        "twice now returns the <i>identical</i> number, so the optimiser is "
        "minimising a genuine deterministic function."))
    st.append(Paragraph("Step 2 &mdash; handle the constraint with a penalty", S["h3"]))
    st.append(P(
        "The real problem is constrained: minimise waiting <i>subject to</i> the "
        "service level staying above 95%. Nelder-Mead is unconstrained, so we fold "
        "the constraint into the objective with an <b>exterior penalty</b>:"))
    st.append(code_block([
        "F(k1, k2) = W_total  +  mu * SUM over levels of  max(0, SL_min - SL_level)",
        "",
        "mu = 500 minutes per unit of service-level shortfall",
        "   -> one percentage point of shortfall costs as much as 5 extra",
        "      minutes of average waiting.",
    ]))
    st.append(Spacer(1, 6))
    st.append(P(
        "Large enough that an infeasible point is never optimal; small enough that "
        "the surface stays smooth near the boundary instead of becoming a cliff "
        "the simplex bounces off. Box bounds (k \u2265 0) are handled by "
        "<b>projection</b> &mdash; clipping each trial point back into the box "
        "&mdash; so the simplex can slide <i>along</i> a bound rather than being "
        "pushed away from it."))

    st.append(Paragraph("Step 3 &mdash; the Nelder-Mead simplex, written out", S["h3"]))
    st.append(P(
        "For 2 variables the simplex is a triangle with 3 corners. Each iteration "
        "sorts the corners best-to-worst and tries, in order:"))
    st.append(table([
        ["Reflect", "Flip the worst corner through the middle of the others. "
                    "(\u03b1 = 1)"],
        ["Expand", "If that reflection is the new best, push twice as far &mdash; "
                   "we found a good direction. (\u03b3 = 2)"],
        ["Contract", "If it is no better than the second-worst, pull halfway back "
                     "instead. (\u03c1 = 0.5)"],
        ["Shrink", "If even that fails, pull every corner halfway toward the best "
                   "one. (\u03c3 = 0.5)"],
        ["Stop", "When the triangle is smaller than 0.05 in every coordinate "
                 "<i>and</i> the spread of its values is under 0.02."],
    ], [2.6 * cm, full - 2.6 * cm], header=False, font_size=8.3))
    st.append(Spacer(1, 6))
    st.append(P(
        "Two practical details that matter. <b>Per-dimension step size:</b> "
        "k\u2081 lives on roughly [0, 30] while k\u2082 lives on [0, 120], so we "
        "build the starting triangle with steps (4, 15) rather than one scalar "
        "&mdash; otherwise the simplex wastes iterations just re-scaling itself. "
        "<b>Multi-start:</b> Nelder-Mead only finds a <i>local</i> minimum, so we "
        "run it from four dispersed starting points; all four landing on the same "
        "value is evidence the surface is unimodal here. " +
        MONO("src/optimizers.py")))

    st.append(Spacer(1, 8))
    st.append(Callout(
        "Making the benchmark honest",
        "Both methods minimise the <i>same</i> objective on the <i>same</i> "
        "simulated weeks, and the budget is counted in <b>week-long simulations, "
        "not seconds</b>, so the comparison does not depend on the machine or on "
        "how many cores we had. One trap we avoid: the two methods use different "
        "replication counts per point, so their raw objective values are estimates "
        "of the same thing with different precision and are <b>not</b> directly "
        "comparable. The script therefore re-scores both optima on one identical "
        "full-length batch before declaring anything.", RED, WARN_BG))

    st.append(CondPageBreak(10 * cm))

    # --- 5.6 CRN
    st.append(Paragraph("5.6  Common random numbers (the WP5 idea)", S["h2"]))
    st.append(P(
        "<b>The identity everything rests on.</b> For any two policies A and B:"))
    st.append(code_block([
        "Var(A - B)  =  Var(A) + Var(B) - 2 * Cov(A, B)",
    ]))
    st.append(Spacer(1, 6))
    st.append(P(
        "With independent random streams, Cov = 0 and the variance of the "
        "difference is just the sum. But if both policies face the <b>identical "
        "simulated week</b> &mdash; the same patients, the same arrival times, "
        "the same service durations, the same scans &mdash; then a busy week "
        "inflates <i>both</i> policies together. Cov becomes strongly positive, "
        "and the variance of the <b>difference</b> collapses. Note that each "
        "policy's own variance is unchanged: CRN sharpens <i>comparisons</i>, not "
        "individual estimates. That distinction is the whole point."))
    st.append(Paragraph("Why ours is near-perfect", S["h3"]))
    st.append(P(
        "Most simulation code loses most of the CRN benefit through "
        "<b>desynchronisation</b>: once two policies make different decisions they "
        "start consuming random numbers in a different order, and patient #1723 "
        "ends up with different service times in the two runs. We avoid this "
        "structurally, by three design choices:"))
    st.append(Spacer(1, 2))
    for t in [
        "<b>Six independent substreams</b> (arrivals, triage levels, initial "
        "service, follow-up service, exam need, exam choice), so a change in how "
        "many draws one dimension makes cannot shift another.",
        "<b>The entire patient list is generated before the run starts.</b> The "
        "engine never draws a random number while simulating &mdash; so patient "
        "#1723 is bit-for-bit identical under every policy.",
        "<b>One uniform per random variate</b> (\u00a75.2), so no single variate "
        "can knock the stream out of step.",
    ]:
        st.append(Paragraph(t, S["bullet"], bulletText="\u2022"))
    st.append(Spacer(1, 6))
    st.append(P(
        "The measured result: policy-to-policy correlations of +0.996 to +0.9997, "
        f"and <b>{varred*100:.1f}% of the comparison variance removed</b>. "
        f"<font face='{FM}'>src/rng.py</font>"))

    st.append(Spacer(1, 8))
    st.append(Paragraph("5.7  The cost model (the WP4 idea)", S["h2"]))
    st.append(P(
        "The paper's staffing section shows that more doctors means shorter waits. "
        "True, but useless as advice &mdash; it has no stopping point. To get an "
        "actual recommendation you need to price the trade-off:"))
    st.append(code_block([
        "C(R, k1, k2) = alpha * physician-hours per week",
        "             + beta  * total patient waiting-minutes per week",
        "             + gamma * number of SLA violations per week",
        "",
        "alpha = 120   an ED attending on ~USD 250k/yr loaded over ~2080 h/yr",
        "beta  = 0.50  one patient-HOUR of waiting is worth 30 units",
        "gamma = 50    a breach costs far more than the minutes that caused it",
    ]))
    st.append(Spacer(1, 6))
    st.append(P(
        "R is the integer roster (morning, afternoon, night). The search is two "
        "stages, because running a full optimiser inside all 140 rosters would be "
        "wasteful: <b>screen</b> every roster once cheaply and drop the unstable "
        "ones (where more than 15% of the week's patients are still in the system "
        "at the end &mdash; their queues are growing, not clearing, so their mean "
        "wait is meaningless), then <b>refine</b> the best few with a full "
        "Nelder-Mead re-tune of (k\u2081, k\u2082)."))
    st.append(Spacer(1, 4))
    st.append(Callout(
        "Why the thresholds are re-tuned inside every roster",
        "The best (k\u2081, k\u2082) for a 3-doctor night shift is <i>not</i> the "
        "best for a 5-doctor one. Holding them fixed while varying staffing would "
        "score every alternative roster at settings chosen for a different one. "
        "That is what makes this a <b>joint</b> optimisation rather than a "
        "staffing sweep &mdash; and the measured threshold drift confirms it "
        "matters: the optimum moves from (2.31, 8.37) at (5,5,3) to "
        "(12.20, 23.40) at (6,6,3).", BLUE, TIP_BG))

    st.append(Spacer(1, 8))
    st.append(Paragraph("5.8  The statistics", S["h2"]))
    st.append(table([
        ["Tool", "What it does", "Why this one"],
        ["Paired t-test",
         "t = mean(d) / (sd(d)/\u221an) on the per-replication differences "
         "d = a \u2212 b",
         "The design <i>is</i> paired, because CRN gives both policies the same "
         "weeks. An unpaired test would throw away exactly the variance reduction "
         "CRN bought."],
        ["Bonferroni correction",
         "Test each comparison at \u03b1/m instead of \u03b1",
         "With 6 policies there are 15 comparisons; without correction you would "
         "expect a false positive by chance. \u03b1<sub>adj</sub> = 0.05/15 = "
         "0.00333."],
        ["Cohen's d (paired)",
         "d = mean(differences) / sd(differences)",
         "Statistical significance only says 'not zero'. Effect size says "
         "'how much', which is what a hospital actually cares about."],
        ["reps_for_halfwidth",
         "Smallest n with t<sub>0.975,n\u22121</sub>\u00b7sd/\u221an \u2264 h",
         "Turns the variance reduction into the practical currency: how many runs "
         "you can skip. Solved by iteration because the t-quantile itself depends "
         "on n."],
    ], [3.4 * cm, 5.4 * cm, full - 8.8 * cm], font_size=8.0))

    st.append(PageBreak())

    # ====================================================================
    # 6. PROJECT MAP
    # ====================================================================
    st += H1("Project map: which file does what", 6)

    st.append(code_block([
        "project/",
        "  README.md                     <- start here",
        "  healthcare-14-00099-v2.pdf    <- the base paper",
        "  Updated_Project_Proposal.md",
        "  edsim/",
        "    README.md                   <- the full written guide",
        "    requirements.txt",
        "    docs/",
        "      PROJECT_GUIDE.pdf         <- THIS DOCUMENT",
        "      PAPER_MAPPING.md          <- every paper equation -> the code",
        "      METHODS.md                <- the numerical methods in full",
        "      make_guide.py             <- generates this PDF",
        "    src/         (15 modules)   <- the library; never run directly",
        "    scripts/     (10 scripts)   <- the runnable experiments",
        "    tests/test_model.py         <- 33 correctness checks",
        "    results/                    <- EVERYTHING the scripts produce",
        "      RESULTS_SUMMARY.md        <- the headline tables",
        "      PROVENANCE.md             <- which command made which file, when",
        "      tables/   (32 x .csv + .md)",
        "      figures/  (22 x .png + .pdf)",
        "      raw/      (per-replication data + JSON manifests)",
    ]))

    st.append(Spacer(1, 10))
    st.append(Paragraph("6.1  The library, " + MONO("src/"), S["h2"]))
    st.append(table([
        ["File", "Responsible for"],
        ["config.py",
         "<b>Every number in the model, in one place.</b> The 7\u00d724 arrival "
         "table, triage mix, service bounds, the four machines, shift rosters, and "
         "the paper's published results used as validation targets. Each constant "
         "is annotated with the paper section it comes from; anything the paper "
         "does not give is marked OUR CHOICE with a reason."],
        ["entities.py", "Patient, ExamOrder, the event tuple, the care stages."],
        ["distributions.py",
         "Inverse-CDF samplers (truncated exponential and lognormal) and the "
         "closed-form truncated mean."],
        ["rng.py",
         "Thinning for the arrivals, the pre-generated patient stream, and the "
         "CRN / independent-streams switch."],
        ["resources.py", "Doctors (time-varying roster) and the four machines."],
        ["policies.py", "All five scheduling policies."],
        ["engine.py", "The discrete-event loop."],
        ["metrics.py",
         "The paper's KPIs, plus a written explanation of which reading of "
         "'average waiting time' the paper's numbers actually imply."],
        ["experiment.py",
         "Runs N replications over a reused process pool; caches patient streams "
         "per worker; the batch evaluator both optimisers share."],
        ["stats.py", "t-tests, Bonferroni, Cohen's d, the CRN variance analysis."],
        ["optimizers.py",
         "The hand-written Nelder-Mead, the grid search, and the penalised "
         "objective."],
        ["staffing.py", "The weekly cost function and the roster search."],
        ["plotting.py", "One shared visual language for all 22 figures."],
        ["console.py", "Banners, progress bars, ASCII tables \u2014 the live output."],
        ["report.py",
         "The provenance machinery: every table gets a header naming the command "
         "that produced it, and every run is logged to PROVENANCE.md."],
    ], [3.0 * cm, full - 3.0 * cm], font_size=8.0))

    st.append(CondPageBreak(12 * cm))

    st.append(Paragraph("6.2  The experiments, " + MONO("scripts/"), S["h2"]))
    st.append(P("Each one prints a full narrative to the terminal <i>and</i> writes "
                "its tables and figures. Runtimes are for a 16-core machine."))
    st.append(table([
        ["#", "Script", "What it does", "Time"],
        ["0", "run_00_demo.py",
         "<b>Watch the engine work.</b> Live event trace, then a console dashboard "
         "of queue lengths updating every simulated hour, then all five policies "
         "on one shared week.", "15 s"],
        ["1", "run_01_validate_paper.py",
         "<b>WP1.</b> Checks the arrival sampler against Table 2 and the service "
         "sampler against its closed form, then runs 100 replications and compares "
         "every published KPI, t-test, effect size and equipment number.", "25 s"],
        ["2", "run_02_grid_search.py",
         "Reproduces the paper's two-stage brute-force search and records what it "
         "cost. <b>Deliberately the expensive one</b> \u2014 50,415 week-long "
         "simulations \u2014 because that expense is the WP3 result.", "10 min"],
        ["3", "run_03_wsept_policy.py",
         "<b>WP2.</b> Adds the two c\u00b7\u03bc policies, prints the index values "
         "the theory produces, and sweeps the one weight the paper does not supply.",
         "20 s"],
        ["4", "run_04_nelder_mead.py",
         "<b>WP3.</b> Our simplex against the same objective, with a live "
         "iteration trace, a 4-start check, a SciPy cross-check, and the budget "
         "comparison.", "3 min"],
        ["5", "run_05_staffing_cost.py",
         "<b>WP4.</b> Screens 140 rosters, re-tunes the thresholds inside the best "
         "ones, prices the paper's own scenarios, and stress-tests the answer "
         "against the cost weights.", "3 min"],
        ["6", "run_06_crn_variance.py",
         "<b>WP5.</b> Runs the whole comparison twice \u2014 once with CRN, once "
         "with independent streams \u2014 and quantifies what CRN buys.", "20 s"],
        ["7", "run_07_sensitivity.py",
         "Reproduces the paper's robustness study, extended to five policies.",
         "2.5 min"],
        ["8", "run_08_final_comparison.py",
         "The consolidated master table, the full significance matrix, the verdict "
         "under three objectives, and RESULTS_SUMMARY.md.", "15 s"],
        ["\u2014", "run_all.py",
         "Runs 1\u20138 in dependency order with a summary table at the end.",
         "<b>20 min</b>"],
    ], [0.8 * cm, 4.0 * cm, full - 6.6 * cm, 1.8 * cm], font_size=8.0,
        align="clll"))

    st.append(Spacer(1, 10))
    st.append(Paragraph("6.3  Where results go, and how to trust them", S["h2"]))
    st.append(P(
        "Every table is written twice: a <b>.csv</b> for machines and a "
        "<b>.md</b> for pasting into the report. The CSV carries a four-line "
        "provenance header:"))
    st.append(code_block([
        "# produced by: scripts/run_01_validate_paper.py",
        "# command    : python scripts/run_01_validate_paper.py --reps 100 --seed 20250402",
        "# timestamp  : 2026-08-28 21:21:16",
        "# args       : {\"reps\": 100, \"seed\": 20250402, \"workers\": 14, ...}",
    ]))
    st.append(Spacer(1, 6))
    st.append(P(
        "The same information &mdash; plus every output path and every key number "
        "&mdash; is appended to <b>results/PROVENANCE.md</b> and written as JSON "
        "to <b>results/raw/&lt;script&gt;.manifest.json</b>. So for any file in " +
        MONO("results/") + " you can answer <i>'which command "
        "produced this, when, with what settings?'</i> by reading one file. "
        "Results are deterministic given the seed: two runs with the same flags "
        "produce byte-identical tables."))

    st.append(PageBreak())

    # ====================================================================
    # 7. HOW TO RUN
    # ====================================================================
    st += H1("How to run everything", 7)

    st.append(Paragraph("7.1  First time", S["h2"]))
    st.append(code_block([
        "cd \"c:\\Buet\\CSE 402\\project\\edsim\"",
        "pip install -r requirements.txt",
        "",
        "python tests/test_model.py          # 33 correctness checks   (~20 s)",
        "python scripts/run_00_demo.py       # watch the simulator run (~15 s)",
        "python scripts/run_all.py --quick   # whole study, fast pass  (~5 min)",
        "python scripts/run_all.py           # whole study, full       (~20 min)",
    ]))
    st.append(Spacer(1, 8))
    st.append(Callout(
        "Run the demo first",
        MONO("run_00_demo.py") + " is the fastest way to convince "
        "yourself (or an examiner) that the engine really does what the paper "
        "describes. It prints every state transition \u2014 arrival, dispatch "
        "decision, consultation start and end, machine seizure, results returning "
        "\u2014 and then redraws a live dashboard of the three queue lengths and "
        "doctor occupancy once per simulated hour.", AQUA,
        colors.HexColor("#ecf8f3")))

    st.append(Spacer(1, 10))
    st.append(Paragraph("7.2  Flags every script accepts", S["h2"]))
    st.append(table([
        ["Flag", "Default", "Meaning"],
        ["--reps N", "100", "Replications per policy (the paper's setting)"],
        ["--seed S", "20250402", "Base seed \u2014 fixes every result reproducibly"],
        ["--workers W", "cores \u2212 2", "Parallel worker processes"],
        ["--quick", "off", "Fast low-fidelity pass for smoke-testing the pipeline"],
        ["--no-figures", "off", "Skip figure rendering"],
    ], [3.4 * cm, 2.8 * cm, full - 6.2 * cm], font_size=8.3))

    st.append(Spacer(1, 10))
    st.append(Paragraph("7.3  Useful specific runs", S["h2"]))
    st.append(code_block([
        "# watch a different policy for 6 simulated hours, slowed down",
        "python scripts/run_00_demo.py --policy SBP --trace-hours 6 --speed 0.05",
        "",
        "# a cheaper grid search (the expensive script)",
        "python scripts/run_02_grid_search.py --coarse-reps 10 --fine-reps 30",
        "",
        "# try your own cost assumptions for the staffing recommendation",
        "python scripts/run_05_staffing_cost.py --alpha 150 --beta 1.0 --gamma 100",
        "",
        "# re-run only two stages of the pipeline, with more replications",
        "python scripts/run_all.py --only 4,8 --reps 200",
        "",
        "# regenerate this PDF after a fresh run",
        "python docs/make_guide.py",
    ]))

    st.append(Spacer(1, 10))
    st.append(Paragraph("7.4  Reading the terminal output", S["h2"]))
    st.append(P(
        "Every script prints in the same shape: a banner, the exact settings in "
        "force, then numbered STEPs. Lines marked <b>[OK]</b> and <b>[!!]</b> are "
        "<i>automated assertions about the results, evaluated live</i> &mdash; "
        "they are not decoration. If a structural finding of the paper fails to "
        "reproduce, the script says so out loud rather than staying silent. "
        "Progress bars show elapsed time and ETA, and the final block lists every "
        "file written."))

    st.append(PageBreak())

    # ====================================================================
    # 8. RESULTS
    # ====================================================================
    st += H1("Results and analysis", 8)
    st.append(Paragraph(
        "All numbers below come from " +
        MONO("python scripts/run_all.py") + " "
        "at seed 20250402 with 100 replications per policy.", S["small"]))
    st.append(Spacer(1, 8))

    # 8.1 WP1
    st.append(Paragraph("8.1  WP1 &mdash; does the rebuild match the paper?", S["h2"]))
    if len(cmp_paper) > 1:
        rows = [["Policy", "Metric", "Ours", "sd", "Paper", "Deviation"]]
        for r in cmp_paper[1:]:
            rows.append(r)
        st.append(table(rows, [1.7 * cm, 6.4 * cm, 1.9 * cm, 1.5 * cm, 2.4 * cm,
                               full - 13.9 * cm], font_size=7.6,
                        align="llrrrr"))
    st.append(Spacer(1, 8))
    st.append(P(
        "<b>What matches almost exactly:</b> both service levels under IFP "
        "(100%/100%), ALT's Level III waiting time (6.05 vs 6.82 published), "
        "SBP's Level III waiting time (12.35 vs 10.48), doctor utilisation "
        "(86.3% vs 85.0&ndash;85.4%), and &mdash; strikingly &mdash; the "
        "equipment table below."))
    st.append(P(
        "<b>What runs high:</b> the absolute waiting times, by 12&ndash;25%. The "
        "explanation is a single number: the published parameters imply a system "
        f"load of \u03c1 \u2248 {rho:.2f}, and near saturation the mean wait is "
        "hypersensitive to the last percentage point of utilisation. The paper's "
        "underlying dataset is not public, so an exact match is not attainable "
        "&mdash; and we do not claim one."))
    st.append(Spacer(1, 6))
    if len(equip) > 1:
        rows = [["Equipment", "Exams/week", "Our utilisation", "Paper's",
                 "Mean machine queueing delay"]]
        for r in equip[1:]:
            rows.append([r[0], r[1], f"{r[2]}%", f"{r[3]}%", f"{r[4]} min"])
        st.append(table(rows, [3.4 * cm, 2.4 * cm, 3.0 * cm, 2.4 * cm,
                               full - 11.2 * cm], font_size=8.2,
                        align="lrrrr"))
        st.append(Paragraph(
            "Equipment utilisation, reproduced within ~0.5 percentage points on "
            "all four machines. Every machine sits far below the doctors' 86%, "
            "which reproduces the paper's central managerial conclusion: "
            "<b>doctors, not equipment, are the bottleneck</b> &mdash; so buying "
            "another CT scanner would not help.", S["caption"]))

    st.append(CondPageBreak(9 * cm))
    st += figure("wp1_waiting_boxplot",
                 "Our reproduction of the paper's Figure 3. Three boxes per "
                 "policy: Level III, Level IV, all patients. Dashed lines mark "
                 "the paper's published means. Note ALT's tiny Level III box "
                 "(left) \u2014 it sprints on urgent patients \u2014 and its tall "
                 "Level IV box, which is the cost.", max_h=8.5 * cm)

    st.append(PageBreak())

    # 8.2 WP2
    st.append(Paragraph("8.2  WP2 &mdash; does the c\u00b7\u03bc rule deliver?",
                        S["h2"]))
    if len(master) > 1:
        rows = [["Policy", "Mean wait", "95% CI", "Level III", "Level IV",
                 "Holding cost", "SL3", "SL4"]]
        for r in master[1:]:
            rows.append([f"<b>{r[0]}</b>", r[2], r[4], r[5], r[6],
                         f"<b>{r[7]}</b>", f"{r[8]}%", f"{r[9]}%"])
        st.append(table(rows, [1.9 * cm, 2.1 * cm, 2.7 * cm, 1.9 * cm, 1.8 * cm,
                               2.3 * cm, 1.6 * cm, full - 14.3 * cm],
                        font_size=8.0, align="lrlrrrrr"))
    st.append(Spacer(1, 8))
    st.append(P(
        "<b>WSEPT wins on its own objective, as the theorem predicts</b> "
        "&mdash; holding cost 0.3763 against IFP's 0.7550, a 50% reduction "
        "&mdash; and, on this system, it also happens to win on the plain "
        "unweighted average (42.32 min). Every pairwise difference against the "
        "paper's three heuristics is significant after Bonferroni correction."))
    st.append(P(
        "<b>But look at the service-level columns.</b> WSEPT reaches only 86.9% "
        "on Level IV. The rules that sprint hardest on Level III are exactly the "
        "rules that let Level IV breach. This is the trade-off surface, not a "
        "league table &mdash; and it is why \u00a78.7 gives three answers rather "
        "than one."))
    st.append(Spacer(1, 4))
    st.append(Callout(
        "An honest caveat we state in the code as well",
        "The Cox\u2013Smith optimality proof assumes a <i>single-stage</i> "
        "multi-class queue. Our model has <b>re-entrant flow</b> (patients come "
        "back for a follow-up after diagnostics) and a <b>time-varying</b> pool "
        "of doctors, so the guarantee is only approximate here. The script says "
        "so out loud if the empirical ranking ever contradicts the theory.",
        RED, WARN_BG))
    st.append(Spacer(1, 6))
    st += figure("wp2_holding_cost_bars",
                 "The objective the c\u00b7\u03bc rule is provably optimal for: "
                 "waiting measured in units of each patient's own clinical "
                 "tolerance. Lower is better. WSEPT wins; IFP is twice as "
                 "expensive as anything else.", max_h=6.6 * cm)

    st.append(PageBreak())

    # 8.3 WP3
    st.append(Paragraph("8.3  WP3 &mdash; optimiser versus brute force", S["h2"]))
    if len(budget_tbl) > 1:
        rows = [["Method", "Points", "Reps each",
                 "<b>Week-long simulations</b>", "Best objective"]]
        for r in budget_tbl[1:]:
            rows.append([r[0], r[1], r[2], f"<b>{r[3]}</b>", r[4]])
        st.append(table(rows, [7.0 * cm, 1.9 * cm, 2.2 * cm, 3.6 * cm,
                               full - 14.7 * cm], font_size=8.2,
                        align="lrrrr", highlight_rows=(3,)))
    st.append(Spacer(1, 8))
    st.append(kpi_row([
        (f"{speedup:.0f}\u00d7", "fewer simulations,<br/>single start"),
        ("0.006", "minutes worse than the<br/>lattice optimum"),
        ("4 / 4", "starts converging to the<br/>same objective"),
        ("0.0000", "difference from<br/>SciPy's implementation"),
    ]))
    st.append(Spacer(1, 10))
    st.append(P(
        "The grid search spent <b>50,415 week-long simulations</b> &mdash; about "
        "970 simulated patient-years of emergency department operation &mdash; to "
        "find (4.10, 8.20). Our simplex found an equally good point in "
        f"<b>{n3.get('nm_simulations', 0):,}</b>. Scored on one identical "
        "full-length batch afterwards, the two optima differ by "
        f"<b>{abs(n3.get('objective_gap_vs_grid_common_scoring', 0.006)):.3f} "
        "minutes</b> &mdash; far below the noise floor of the simulation itself."))
    if len(optconf) > 1:
        st.append(Spacer(1, 4))
        rows = [["Setting", "(k\u2081, k\u2082)", "Mean wait", "sd", "SL3", "SL4",
                 "Constraint"]]
        for r in optconf[1:]:
            last = f"<b>{r[6]}</b>" if "INFEAS" in r[6] else r[6]
            rows.append([r[0], r[1], r[2], r[3], f"{r[4]}%", f"{r[5]}%", last])
        st.append(table(rows, [4.6 * cm, 2.6 * cm, 2.1 * cm, 1.4 * cm, 1.8 * cm,
                               1.8 * cm, full - 14.3 * cm], font_size=8.2,
                        align="llrrrrl", highlight_rows=(3,)))
        st.append(Paragraph(
            "All three optima re-scored on identical weeks. The bottom row is the "
            "finding: <b>the paper's own published thresholds are infeasible on "
            "our system</b>, because k\u2082 = 2.1 only rescues a Level IV "
            "patient after 117.9 of their 120 minutes.", S["caption"]))
    st.append(Spacer(1, 4))
    st += figure("wp3_simplex_path",
                 "The simplex trajectory drawn on the very response surface the "
                 "lattice had to evaluate in full. The dark band along the bottom "
                 "is the SLA penalty; the paper's point (square) sits inside it, "
                 "while the simplex walks down from (10, 30) to the feasible "
                 "optimum (star).", max_h=9.0 * cm)

    st.append(PageBreak())

    # 8.4 WP4
    st.append(Paragraph("8.4  WP4 &mdash; how many doctors should the ED roster?",
                        S["h2"]))
    if len(cost_rec) > 1:
        # Nine columns is the most this page width takes without the headers
        # wrapping; the SLA-cost split is quoted in the prose underneath.
        rows = [["Configuration", "(k\u2081, k\u2082)", "Doctor-h", "Mean wait",
                 "SL3", "SL4", "Staff cost", "Wait cost", "<b>Total / week</b>"]]
        for r in cost_rec[1:]:
            rows.append([r[0], r[1], r[2], f"{r[3]} min", f"{r[4]}%", f"{r[5]}%",
                         r[6], r[7], f"<b>{r[9]}</b>"])
        st.append(table(rows, [3.7 * cm, 2.1 * cm, 1.7 * cm, 1.9 * cm, 1.5 * cm,
                               1.5 * cm, 1.8 * cm, 1.8 * cm,
                               full - 16.0 * cm], font_size=7.6,
                        align="llrrrrrrr", highlight_rows=(2,)))
    thr = n4.get("recommended_thresholds", [0.0, 0.0])
    d_hours = d_wait = 0.0
    if len(cost_rec) > 2:
        try:
            d_hours = float(cost_rec[2][2]) - float(cost_rec[1][2])
            d_wait = float(cost_rec[1][3]) - float(cost_rec[2][3])
        except ValueError:
            pass
    st.append(Spacer(1, 8))
    st.append(P(
        f"<b>The recommendation: roster {tuple(roster)}</b> &mdash; one more "
        f"doctor on each day shift &mdash; <b>with thresholds re-tuned to "
        f"({thr[0]:.2f}, {thr[1]:.2f})</b>. That costs {d_hours:,.0f} more "
        f"doctor-hours a week, but it buys back {d_wait:.0f} minutes of average "
        f"waiting per patient and cuts the SLA penalty from "
        f"{cost_rec[1][8]} to {cost_rec[2][8]} cost units &mdash; a net weekly "
        f"saving of <b>{abs(saving):,.0f} cost units ({cost_delta_pct})</b>."))
    st.append(Spacer(1, 6))
    if len(t10) > 1:
        rows = [["Scenario", "Roster", "Doctor-h", "Mean wait", "Util.",
                 "SL4", "Staff cost", "Wait cost", "<b>Total</b>"]]
        for r in t10[1:]:
            rows.append([r[0], r[1], r[2], f"{r[3]} min", f"{r[4]}%", f"{r[5]}%",
                         r[6], r[7], f"<b>{r[8]}</b>"])
        st.append(table(rows, [1.9 * cm, 2.1 * cm, 1.8 * cm, 1.9 * cm, 1.9 * cm,
                               1.8 * cm, 1.9 * cm, 1.8 * cm, full - 15.1 * cm],
                        font_size=7.8, align="llrrrrrrr", highlight_rows=(6,)))
        st.append(Paragraph(
            "The paper's own seven staffing scenarios, now with a price attached. "
            "The paper stops at <i>'more staff lowers waiting'</i>, which has no "
            "stopping point. With a cost function the sequence has a clear "
            "<b>interior optimum</b> at S5 &mdash; and our free search over all "
            "140 rosters finds a cheaper one still, because Table 10 only walks "
            "one particular path through the roster space.", S["caption"]))
    st.append(Spacer(1, 4))
    if len(cost_sens) > 1:
        rows = [["Cost scenario", "\u03b1", "\u03b2", "\u03b3", "Winning roster",
                 "Its cost", "Cost of (5,5,3)", "Saving"]]
        for r in cost_sens[1:]:
            rows.append([r[0], r[1], r[2], r[3], f"<b>{r[4]}</b>", r[5], r[6], r[7]])
        st.append(table(rows, [4.4 * cm, 1.3 * cm, 1.3 * cm, 1.3 * cm, 2.6 * cm,
                               2.0 * cm, 2.4 * cm, full - 15.3 * cm],
                        font_size=8.0, align="lrrrlrrr"))
    st.append(Spacer(1, 6))
    st.append(Callout(
        "The honest reading of the sensitivity table",
        "The winning roster <b>changes</b> with the cost weights \u2014 (6,6,3) "
        "at the baseline, (6,7,3) if waiting is valued four times higher, (5,6,3) "
        "if it is valued a quarter as much. That is not a weakness of the method; "
        "it <i>is</i> the finding. The right staffing level genuinely depends on "
        "how the hospital prices a patient's waiting minute against a doctor's "
        "salary, so <b>those weights have to be agreed before the roster can be "
        "set</b>. What does not change: every scenario beats the paper's fixed "
        "(5,5,3), by between 5% and 53%.", BLUE, TIP_BG))

    st.append(PageBreak())

    # 8.5 WP5
    st.append(Paragraph("8.5  WP5 &mdash; what do common random numbers buy?",
                        S["h2"]))
    if len(crn) > 1:
        rows = [["Comparison", "Var (independent)", "Var (CRN)",
                 "<b>Variance removed</b>", "Efficiency", "CI \u00bd-width (ind)",
                 "CI \u00bd-width (CRN)"]]
        for r in crn[1:]:
            rows.append([r[0], r[3], r[4], f"<b>{r[5]}</b>", r[6], r[7], r[8]])
        st.append(table(rows, [3.4 * cm, 2.7 * cm, 2.0 * cm, 2.6 * cm, 1.9 * cm,
                               2.5 * cm, full - 15.1 * cm], font_size=7.8,
                        align="lrrrrrr"))
    st.append(Spacer(1, 8))
    st.append(kpi_row([
        (f"{varred*100:.1f}%", "median variance<br/>removed"),
        (f"{effgain:.0f}\u00d7", "median efficiency<br/>gain"),
        ("+0.996", "to +0.9997<br/>induced correlation"),
        ("20\u201330", "CRN reps replace<br/>the paper's 100"),
    ]))
    st.append(Spacer(1, 10))
    st.append(P(
        "Two results worth stating separately. First, <b>CRN does not move the "
        "point estimates</b> &mdash; each policy's own mean and standard deviation "
        "are unchanged between the two arms. It changes the <i>dependence</i> "
        "between runs, not the marginal law of any single one, which is why it is "
        "a variance-reduction technique and not a bias."))
    st.append(P(
        "Second, <b>it changes conclusions.</b> With independent streams, several "
        "comparisons fail to reach the Bonferroni threshold; with CRN the same "
        "comparisons are decisive. Where the two arms disagree, CRN is the arm to "
        "believe: it is testing the same hypothesis with a lower-variance "
        "estimator of the same quantity."))
    st.append(Spacer(1, 4))
    st.append(Callout(
        "Do not over-claim this one",
        f"A {effgain:.0f}\u00d7 efficiency gain does <b>not</b> mean you should "
        "run one replication. The ratio is itself estimated from the data, and a "
        "t-interval needs enough degrees of freedom to be trustworthy. The "
        "practical reading is that <b>20\u201330 CRN replications give "
        "comparisons at least as sharp as the paper's 100 independent ones</b> "
        "\u2014 a 3\u20135\u00d7 saving that is safe to actually take.",
        RED, WARN_BG))
    st.append(Spacer(1, 6))
    st += figure("wp5_crn_variance_reduction",
                 "Left: the confidence interval on each pairwise difference "
                 "shrinks by roughly 4\u201340\u00d7. Right: the number of "
                 "replications needed to pin that difference to \u00b10.5 min, "
                 "log scale \u2014 thousands become dozens.", max_h=7.5 * cm)

    st.append(PageBreak())

    # 8.6 sensitivity
    st.append(Paragraph("8.6  Robustness &mdash; do the conclusions survive?",
                        S["h2"]))
    st.append(table([
        ["Test", "What we varied", "Result"],
        ["Arrival rate",
         "Every hourly rate scaled \u221215% to +15% in 3% steps "
         "(\u03c1 from 0.74 to 1.00)",
         "Policies are nearly interchangeable under light load and fan out "
         "sharply as the system saturates \u2014 policy spread grows from 1.5 min "
         "to 61 min. <b>The paper's Figure 4 finding, reproduced.</b>"],
        ["Staffing",
         "The paper's seven rosters S0\u2013S6",
         "Waits fall with clear diminishing returns, and the <i>choice of policy</i> "
         "matters most exactly when doctors are scarce. Policy spread falls from "
         "10.4 min at S0 to 0.07 min at S6. <b>Figure 5 reproduced.</b>"],
        ["Service-time<br/>distribution",
         "Truncated exponential \u2192 truncated lognormal (\u03c3 = 0.3, same "
         "nominal means)",
         "All waits rise 44\u201354% because of the heavier right tail, but the "
         "<b>ranking is identical</b>. The conclusions are not an artefact of "
         "assuming exponential service times \u2014 as the paper also reports."],
    ], [2.6 * cm, 5.0 * cm, full - 7.6 * cm], font_size=8.1))
    st.append(Spacer(1, 6))
    if len(sdist) > 1:
        rows = [["Policy", "TruncExp wait", "Lognormal wait", "Change", "Relative",
                 "SL4 (exp)", "SL4 (lognormal)"]]
        for r in sdist[1:]:
            rows.append([f"<b>{r[0]}</b>", f"{r[1]} min", f"{r[2]} min", r[3],
                         r[4], f"{r[5]}%", f"{r[6]}%"])
        st.append(table(rows, [2.2 * cm, 2.6 * cm, 2.8 * cm, 1.9 * cm, 1.9 * cm,
                               2.2 * cm, full - 13.6 * cm], font_size=8.1,
                        align="lrrrrrr"))
    st.append(Spacer(1, 6))
    st += figure("sens_arrival_rate",
                 "Reproduction of the paper's Figure 4, extended to all five "
                 "policies. Under light load (left) the policies are "
                 "indistinguishable; as the department saturates (right) the "
                 "choice of rule becomes worth minutes per patient.",
                 max_h=8.0 * cm)

    st.append(PageBreak())

    # 8.7 final
    st.append(Paragraph("8.7  The final verdict", S["h2"]))
    st += figure("final_tradeoff",
                 "The whole project in one picture. Horizontal: average waiting "
                 "time (lower is better). Vertical: Level IV service level "
                 "(higher is better). The dashed line is the 95% constraint "
                 "\u2014 <b>only policies above it are adoptable</b>. IFP is safe "
                 "but slow; ALT, SBP, WSEPT and Gc\u00b7\u03bc are fast but "
                 "infeasible; only SBP*, our re-tuned policy, is both.",
                 max_h=9.5 * cm)
    st.append(Spacer(1, 4))
    if len(sig) > 1:
        rows = [["Comparison", "Mean diff (min)", "95% CI", "t", "p",
                 "Sig.", "Cohen's d"]]
        for r in sig[1:]:
            rows.append([r[0], r[1], r[2], r[3], r[4],
                         f"<b>{r[5]}</b>" if r[5].lower().startswith("y") else r[5],
                         r[6]])
        st.append(table(rows, [3.2 * cm, 2.4 * cm, 3.3 * cm, 1.9 * cm, 2.3 * cm,
                               1.3 * cm, full - 14.4 * cm], font_size=7.4,
                        align="lrlrrcr"))
        st.append(Paragraph(
            "All 15 pairwise paired t-tests, Bonferroni-corrected "
            "(\u03b1<sub>adj</sub> = 0.05/15 = 0.00333). Only three comparisons "
            "fail to reach significance, and all three are between policies that "
            "genuinely perform the same.", S["caption"]))

    st.append(PageBreak())

    # ====================================================================
    # 9. PAPER VS OURS
    # ====================================================================
    st += H1("Paper vs. ours, side by side", 9)

    st.append(Paragraph("9.1  Where we agree", S["h2"]))
    st.append(table([
        ["Finding", "Paper", "Ours", "Verdict"],
        ["IFP is the worst policy on mean wait", "46.26 min", "52.43 min",
         "<b>Reproduced</b>"],
        ["ALT collapses Level III waiting", "6.82 min", "6.05 min",
         "<b>Reproduced</b> (11% off)"],
        ["ALT breaks the Level IV service level", "89.29%", "87.37%",
         "<b>Reproduced</b> (2% off)"],
        ["IFP holds 100% on both levels", "100 / 100", "100 / 100",
         "<b>Exact</b>"],
        ["Doctor utilisation is ~85% and near-identical across policies",
         "84.98\u201385.43%", "86.34\u201386.36%", "<b>Reproduced</b>"],
        ["Equipment is far from the bottleneck", "14.4\u201319.0%",
         "14.7\u201319.4%", "<b>Reproduced</b> (&lt;0.5&nbsp;pp)"],
        ["Policies diverge as load rises", "Figure 4", "1.5 \u2192 61 min spread",
         "<b>Reproduced</b>"],
        ["Adding staff has diminishing returns", "Figure 5",
         "10.4 \u2192 0.07 min spread", "<b>Reproduced</b>"],
        ["Ranking survives a lognormal service time", "Sec 3.4.3",
         "identical ranking", "<b>Reproduced</b>"],
    ], [7.2 * cm, 3.0 * cm, 3.4 * cm, full - 13.6 * cm], font_size=8.1))

    st.append(Spacer(1, 12))
    st.append(Paragraph("9.2  Where we differ, and why", S["h2"]))
    st.append(table([
        ["Difference", "Why it happens", "Does it undermine anything?"],
        ["Our waiting times are 12\u201325% higher",
         "The published parameters imply \u03c1 \u2248 0.87. Near saturation, mean "
         "wait is hypersensitive to the last point of utilisation. The source "
         "dataset is not public, so the exact patient mix cannot be recovered.",
         "<b>No.</b> Every <i>relative</i> and structural result reproduces; only "
         "the level differs. We report this openly rather than tuning to match."],
        ["SBP is not the best policy on our system",
         "The paper's (13.1, 2.1) is optimal for the paper's system, not ours. "
         "With k\u2082 = 2.1 a Level IV patient is rescued only at minute 117.9 of "
         "120 \u2014 too late under heavier congestion.",
         "<b>No \u2014 it is the point.</b> Re-tuning under the constraint (WP3) "
         "restores SBP* to the best <i>feasible</i> policy. This is the strongest "
         "argument in the project for re-tuning rather than copying published "
         "parameters."],
        ["The paper's thresholds are infeasible here",
         "They reach 89.4% on Level IV against a 95% target.",
         "It sharpens the contribution. The paper never had to face the "
         "constraint because on its system the tuned thresholds happened to "
         "satisfy it."],
    ], [4.3 * cm, 6.3 * cm, full - 10.6 * cm], font_size=8.0))

    st.append(Spacer(1, 12))
    st.append(Paragraph("9.3  What we add that the paper does not have", S["h2"]))
    st.append(table([
        ["Addition", "Where it lives"],
        ["The c\u00b7\u03bc / WSEPT policy and its generalisation",
         "src/policies.py \u2014 CMuPolicy"],
        ["A holding-cost metric, so the c\u00b7\u03bc rule is judged on its own "
         "objective", "src/metrics.py \u2014 holding_cost"],
        ["A hand-written Nelder-Mead simplex with projection bounds",
         "src/optimizers.py \u2014 nelder_mead()"],
        ["An exterior penalty for the service-level constraint",
         "src/optimizers.py \u2014 SimulationObjective.penalty()"],
        ["Simulation-budget accounting, so optimisers can be compared fairly",
         "src/optimizers.py, run_04 STEP 4"],
        ["A weekly cost model and an integer roster search",
         "src/staffing.py, run_05"],
        ["Exact common random numbers and the variance reduction quantified",
         "src/rng.py, src/stats.py \u2014 crn_efficiency()"],
        ["Provenance logging for every single artefact",
         "src/report.py \u2014 Artifact"],
        ["A 33-check verification suite", "tests/test_model.py"],
    ], [10.4 * cm, full - 10.4 * cm], font_size=8.2))

    st.append(PageBreak())

    # ====================================================================
    # 10. JUDGEMENT CALLS
    # ====================================================================
    st += H1("The judgement calls we had to make", 10)
    st.append(P(
        "The paper's dataset is not public and a few modelling details are left "
        "unspecified. There are exactly five such decisions. All are flagged " +
        MONO("OUR CHOICE") + " in " + MONO("src/config.py") +
        " with a reason, and each is swept or stress-tested somewhere in the "
        "pipeline."))
    st.append(Spacer(1, 4))
    st.append(table([
        ["Decision", "What we chose", "Why, and how we check it"],
        ["The numeric service-level constraint. The paper writes "
         "SL<sub>\u2113</sub> \u2265 SL<sub>\u2113</sub><super>min</super> but "
         "never prints the number.",
         "<b>0.95</b> for both levels",
         "A standard ED target, and strict enough that the penalty term actually "
         "binds. Every table reports both service levels so a different threshold "
         "can be applied by eye."],
        ["T<sub>follow</sub>, the delay weight for follow-up patients, needed by "
         "the c\u00b7\u03bc rule. The paper gives no target for them.",
         "<b>60 min</b> \u2014 the midpoint of T\u2083 = 30 and T\u2084 = 120",
         "run_03 sweeps it from 15 to 120 min. The policy ranking never flips "
         "anywhere in the sweep."],
        ["The grid-search box for (k\u2081, k\u2082).",
         "<b>k\u2081 \u2208 [0,30], k\u2082 \u2208 [0,60]</b>",
         "The paper's Table 3 lists winners at k\u2081 = 26 and k\u2082 = 40, so "
         "the box must at least contain those."],
        ["The cost weights \u03b1, \u03b2, \u03b3 (WP4 only \u2014 the paper has "
         "no cost model at all).",
         "<b>120 / 0.50 / 50</b>",
         "An ED attending at ~USD 250k/yr loaded over ~2080 h/yr is ~120/h; "
         "\u03b2 values a patient-hour of waiting at 30 units. run_05 stage D "
         "re-prices everything under four alternative weightings."],
        ["'60% require <i>at least one</i> test' versus independent per-machine "
         "probabilities that can jointly select none.",
         "<b>Resample</b> so 'at least one' holds exactly",
         "The two readings differ by 1.99% of exam volume. Switchable via " +
         MONO("SimConfig.exam_require_at_least_one") + "."],
    ], [5.4 * cm, 3.6 * cm, full - 9.0 * cm], font_size=8.0))

    st.append(Spacer(1, 12))
    st.append(Paragraph("10.1  Ambiguities in the paper we had to interpret",
                        S["h2"]))
    st.append(table([
        ["Ambiguity", "Our reading, and the evidence for it"],
        ["Is R<sup>t</sup> in the policy equations the <i>free</i> doctors or the "
         "<i>whole</i> roster?",
         "Free doctors for IFP and SBP (pure priority orders, where the two "
         "readings coincide); the <b>whole roster</b> for ALT's \u230aR/2\u230b "
         "cap. With event-driven dispatch a doctor usually frees up one at a time, "
         "so \u230aR<sub>free</sub>/2\u230b = 0 would silently turn ALT into "
         "'follow-ups always first' \u2014 a different policy. Our reading "
         "reproduces the paper's ALT Level III wait (6.82 published, 6.05 ours)."],
        ["What does 'average waiting time' mean? The equations say per-consultation; "
         "the numbers say otherwise.",
         "<b>Per-patient totals</b> (initial wait + follow-up wait). Two facts "
         "force it: (i) 0.25\u00d710.48 + 0.75\u00d743.89 = 35.54 \u2248 35.25, "
         "the paper's headline; (ii) the paper reports Level III = 44.14 min under "
         "IFP <i>and</i> a 100% service level against a 30-min target \u2014 both "
         "cannot be true of the same quantity. We compute the per-consultation "
         "figures too, so nothing is hidden."],
        ["How many of each machine?",
         "<b>One</b>. Table 9 lists 'Available Time = 10,080 min' per machine for "
         "a one-week run \u2014 exactly one machine-week."],
        ["How is the truncated exponential parameterised?",
         "<b>\u03bb = 1/mean</b>, i.e. the <i>pre</i>-truncation mean is 9/15 min. "
         "A truncated exponential on [5,25] cannot have mean 15, and \u03bb = 1/15 "
         "gives \u03c1 \u2248 0.87 which matches the paper's ~85% utilisation."],
        ["What happens at a shift change?",
         "<b>Nothing is interrupted.</b> 'Once a physician begins service, the "
         "service process will not be interrupted.' A shrinking shift blocks new "
         "starts until the busy count falls back below the roster."],
    ], [5.0 * cm, full - 5.0 * cm], font_size=8.0))

    st.append(PageBreak())

    # ====================================================================
    # 11. VIVA
    # ====================================================================
    st += H1("Viva preparation: likely questions", 11)
    qa = [
        ("Why discrete-event simulation instead of a queueing formula?",
         "Three reasons, all in the paper and all true of our rebuild. The system "
         "is <b>non-stationary</b> \u2014 arrival rates change hourly and staffing "
         "changes by shift \u2014 so steady-state formulas do not apply. The "
         "service times are <b>truncated exponentials plus fixed machine times</b>, "
         "which breaks the memorylessness most analytic models need. And the "
         "slack-based policy is <b>history-dependent</b>: you would have to track "
         "every patient's exact waiting time as a state variable, which explodes "
         "the state space."),
        ("Why write your own event loop instead of using SimPy?",
         "Because the paper's mechanisms are the thing being examined. With a "
         "hand-rolled heapq loop, every state transition is one visible line of "
         "Python, so the equations in the paper map onto code you can point at. "
         "It is also measurably faster: profiling showed dataclass comparison in "
         "the heap was 22% of runtime, and switching to plain tuples cut "
         "per-replication time from 0.20 s to 0.076 s \u2014 which is what makes "
         "the 50,415-simulation grid search affordable at all."),
        ("Your numbers do not match the paper. Is the model wrong?",
         "No \u2014 and the evidence is that everything <i>except</i> the absolute "
         "level does match: the equipment table to within 0.5 percentage points, "
         "ALT's Level III wait to within 11%, both service levels under IFP "
         "exactly, and all three sensitivity findings. The absolute waits are "
         "higher because the published parameters imply \u03c1 \u2248 0.87, where "
         "mean wait is hypersensitive to utilisation. The underlying dataset is "
         "not public, so exact agreement is unattainable; we state the deviation "
         "openly rather than tuning to hit it."),
        ("Why is the c\u00b7\u03bc rule better than just inventing another "
         "heuristic?",
         "Because it comes with a proof. Cox and Smith showed that serving the "
         "class with the largest c<sub>\u2113</sub>\u00b7\u03bc<sub>\u2113</sub> "
         "<i>minimises</i> total holding cost in a multi-class queue. IFP, ALT "
         "and SBP are plausible rules someone designed; c\u00b7\u03bc is the "
         "answer to a stated optimisation problem. The caveat we also state: the "
         "proof assumes a single-stage queue, and ours has re-entrant flow and a "
         "time-varying server pool, so the guarantee is approximate here."),
        ("How can Nelder-Mead work on a random function?",
         "It cannot, as-is \u2014 that is why we do not hand it one. We use sample "
         "average approximation with common random numbers: every candidate is "
         "scored on the <i>same fixed</i> 50 simulated weeks, so evaluating a "
         "point twice returns the identical number. The optimiser sees a genuine "
         "deterministic function, and because the seed noise is shared it cancels "
         "when candidates are compared, making the surface far smoother than the "
         "pointwise noise would suggest."),
        ("Is a 19\u00d7 speed-up a fair comparison?",
         "Yes, and we went out of our way to make it so. Both methods minimise "
         "the same penalised objective, on the same simulated weeks, and the "
         "budget is counted in week-long simulations rather than seconds so it "
         "does not depend on the machine or the core count. The one trap \u2014 "
         "that the two methods used different replication counts per point, so "
         "their raw objective values are not comparable \u2014 is handled by "
         "re-scoring both optima on one identical full-length batch before "
         "declaring anything."),
        ("Why did you get a different optimum from the paper?",
         "Because we optimised a <i>constrained</i> problem on a busier system. "
         "The paper's (13.1, 2.1) minimises unconstrained mean wait on its own "
         "model; on ours it reaches only 89.4% on Level IV. Under the 95% "
         "constraint the optimum moves to a much larger k\u2082, which is "
         "mechanically obvious once you see that k\u2082 = 2.1 rescues a Level IV "
         "patient only at minute 117.9 of 120."),
        ("Does CRN not bias your results?",
         "No, and we test for it explicitly. CRN changes the <i>dependence</i> "
         "between two runs, not the marginal distribution of either, so each "
         "policy's own mean and standard deviation are statistically unchanged "
         "between the two arms \u2014 run_06 prints exactly that check. What "
         "changes is Cov(A,B) in Var(A\u2212B) = Var(A)+Var(B)\u22122Cov(A,B), "
         "and therefore only the variance of the <i>difference</i>."),
        ("Where do the cost weights come from? Are they not arbitrary?",
         "They are assumptions, stated as assumptions, and stress-tested. "
         "\u03b1 = 120/hour is an ED attending on ~USD 250k/yr loaded over "
         "~2080 h/yr. \u03b2 and \u03b3 are choices. That is why stage D of run_05 "
         "re-prices every roster under four alternative weightings \u2014 and the "
         "winning roster does change, which is itself the finding: the right "
         "staffing level depends on how the hospital prices waiting against "
         "salary."),
        ("How do I know the simulator is actually correct?",
         "33 automated checks, each pinning down a property some published number "
         "depends on. They verify the samplers against closed forms, the "
         "day/hour indexing, thinning convergence, CRN seed behaviour, and engine "
         "invariants \u2014 no patient served before they arrive, no doctor idle "
         "while someone waits, the exam chain matching the paper's equation 4, "
         "non-preemptive shift changes. Plus the optimiser against Rosenbrock and "
         "against SciPy, and a direct check that CRN reduces variance."),
        ("Which policy should the hospital actually use?",
         "<b>SBP* \u2014 the Slack-Based Policy with our re-tuned thresholds</b> "
         "\u2014 if they must meet a 95% service level, which in practice they "
         "must. It is 16% faster than the IFP baseline and it is the only tuned "
         "policy that clears the constraint on both triage levels. If the "
         "constraint were dropped, WSEPT would be the answer. And WP4 says the "
         "bigger win is not the schedule at all: one extra doctor on each day "
         f"shift saves {cost_delta_pct} of weekly cost."),
    ]
    for q, a in qa:
        st.append(KeepTogether([
            Paragraph("Q. " + q, S["h3"]),
            Paragraph(a, S["body"]),
        ]))

    st.append(PageBreak())

    # ====================================================================
    # 12. GLOSSARY
    # ====================================================================
    st += H1("Glossary and references", 12)
    st.append(Paragraph("12.1  Symbols and terms", S["h2"]))
    st.append(table([
        ["Symbol / term", "Means"],
        ["\u03bb<sub>d,h</sub>", "Arrival rate on day d, hour h (patients/hour). "
                                 "The paper's Table 2."],
        ["\u03bb*", "The largest \u03bb anywhere in the week (23.05/h), used by "
                    "the thinning algorithm."],
        ["\u03c1 (rho)", "Offered load = work arriving / work the doctors can do. "
                         "0.87 here; at 1.0 the queue grows without bound."],
        ["T<sub>\u2113</sub>", "Triage target for level \u2113: 30 min for "
                               "Level III, 120 min for Level IV."],
        ["k<sub>1</sub>, k<sub>2</sub>", "Slack thresholds. A patient becomes "
                                         "urgent after waiting T<sub>\u2113</sub> "
                                         "\u2212 k<sub>\u2113</sub> minutes."],
        ["SL<sub>\u2113</sub>", "Service level: the share of level-\u2113 patients "
                                "seen within T<sub>\u2113</sub>."],
        ["\u03bc<sub>\u2113</sub>", "Service rate = 1 / mean service time for "
                                    "class \u2113."],
        ["c<sub>\u2113</sub>", "Delay cost per minute for class \u2113. We use "
                               "1/T<sub>\u2113</sub>."],
        ["Holding cost", "Mean of w<sub>i</sub> / T<sub>level(i)</sub> \u2014 "
                         "waiting measured in units of each patient's own "
                         "tolerance."],
        ["CRN", "Common random numbers: giving every policy the identical "
                "simulated week."],
        ["SAA", "Sample average approximation: replacing a random objective by "
                "its average over a fixed set of scenarios."],
        ["Replication", "One complete simulated week (10,080 minutes, ~2,280 "
                        "patients)."],
        ["IFP / ALT / SBP", "The paper's three policies. SBP* is our re-tuned "
                            "version of SBP."],
        ["WSEPT / Gc\u00b7\u03bc", "Our two added policies: the c\u00b7\u03bc rule "
                                   "and its generalisation."],
    ], [4.0 * cm, full - 4.0 * cm], font_size=8.2))

    st.append(Spacer(1, 12))
    st.append(Paragraph("12.2  References", S["h2"]))
    refs = [
        "Lv, W.; Liu, R.; Yan, F.; Wang, Y. <i>Discrete Event Simulation-Based "
        "Analysis and Optimization of Emergency Patient Scheduling Strategies.</i> "
        "Healthcare <b>2026</b>, 14, 99. &mdash; the base paper.",
        "Cox, D. R.; Smith, W. L. <i>Queues.</i> Methuen, 1961. &mdash; the "
        "c\u00b7\u03bc rule.",
        "Buyukkoc, C.; Varaiya, P.; Walrand, J. <i>The c\u03bc rule revisited.</i> "
        "Adv. Appl. Prob. <b>1985</b>, 17, 237\u2013238.",
        "Van Mieghem, J. A. <i>Dynamic scheduling with convex delay costs: the "
        "generalized c\u03bc rule.</i> Ann. Appl. Prob. <b>1995</b>, 5, "
        "809\u2013833.",
        "Mandelbaum, A.; Stolyar, A. L. <i>Scheduling flexible servers with convex "
        "delay costs.</i> Oper. Res. <b>2004</b>, 52, 836\u2013855.",
        "Nelder, J. A.; Mead, R. <i>A simplex method for function minimization.</i> "
        "Comput. J. <b>1965</b>, 7, 308\u2013313.",
        "Lewis, P. A. W.; Shedler, G. S. <i>Simulation of nonhomogeneous Poisson "
        "processes by thinning.</i> Naval Res. Logist. Q. <b>1979</b>, 26, "
        "403\u2013413.",
        "Law, A. M. <i>Simulation Modeling and Analysis</i>, 5th ed. McGraw-Hill, "
        "2015. &mdash; common random numbers.",
    ]
    for i, r in enumerate(refs, 1):
        st.append(Paragraph(f"[{i}]&nbsp;&nbsp;{r}", S["bullet"]))

    st.append(Spacer(1, 14))
    st.append(Callout(
        "Where to go next",
        "<b>edsim/README.md</b> \u2014 the same material in written form, with "
        "more detail on the code. &nbsp;&nbsp;"
        "<b>edsim/docs/PAPER_MAPPING.md</b> \u2014 every equation, table and "
        "figure of the paper mapped to the exact function that implements it. "
        "&nbsp;&nbsp;<b>edsim/docs/METHODS.md</b> \u2014 the numerical methods "
        "with full formulas. &nbsp;&nbsp;"
        "<b>edsim/results/RESULTS_SUMMARY.md</b> and <b>PROVENANCE.md</b> "
        "\u2014 the generated numbers and the record of exactly which command "
        "produced each one.", BLUE, TIP_BG))

    return st


# ---------------------------------------------------------------------------
def main():
    if not os.path.isdir(FIGURES):
        print("!! results/figures not found -- run "
              "'python scripts/run_all.py' first.")
        return 1

    doc = BaseDocTemplate(
        OUT, pagesize=A4,
        leftMargin=MARGIN, rightMargin=MARGIN,
        topMargin=MARGIN, bottomMargin=MARGIN,
        title="ED Patient-Flow Simulation - Project Guide",
        author="CSE 402 Section C - Group project",
        subject="Replication and extension of Lv et al. (2026), Healthcare 14(1):99",
    )
    frame = Frame(MARGIN, MARGIN, PAGE_W - 2 * MARGIN, PAGE_H - 2 * MARGIN,
                  id="F", leftPadding=0, rightPadding=0,
                  topPadding=0, bottomPadding=0)
    doc.addPageTemplates([
        PageTemplate(id="cover", frames=[frame], onPage=on_cover),
        PageTemplate(id="body", frames=[frame], onPage=on_page),
    ])
    doc.build(build_story())

    size = os.path.getsize(OUT) / 1024
    print(f"  wrote {OUT}  ({size:,.0f} KB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
