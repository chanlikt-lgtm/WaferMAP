"""
generate_docs.py
================
Generates a detailed technical PDF documentation for the Wafer Map Tool.
Run from repo root:  py generate_docs.py
Output:  WaferMapTool_Documentation.pdf
"""
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm, mm
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, PageBreak, Preformatted, KeepTogether
)
from reportlab.platypus.tableofcontents import TableOfContents
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_JUSTIFY
from reportlab.platypus import BaseDocTemplate, Frame, PageTemplate
from reportlab.platypus import NextPageTemplate
from datetime import datetime

OUT = "WaferMapTool_Documentation.pdf"

# ── Colours ────────────────────────────────────────────────────────────────
C_PURPLE   = colors.HexColor("#7c3aed")
C_DARKBG   = colors.HexColor("#1e1e2e")
C_ACCENT   = colors.HexColor("#e2e8f0")
C_GREEN    = colors.HexColor("#00AA00")
C_YELLOW   = colors.HexColor("#ccaa00")
C_RED      = colors.HexColor("#CC0000")
C_CODEBG   = colors.HexColor("#f4f4f8")
C_BORDER   = colors.HexColor("#d0d0e0")
C_HEADER   = colors.HexColor("#4c1d95")
C_SUBHEAD  = colors.HexColor("#5b21b6")
C_MUTED    = colors.HexColor("#6b7280")
C_TABLE_H  = colors.HexColor("#ede9fe")
C_TABLE_R  = colors.HexColor("#f9f8ff")
C_WHITE    = colors.white
C_BLACK    = colors.black

W, H = A4


# ── Style sheet ────────────────────────────────────────────────────────────
def make_styles():
    base = getSampleStyleSheet()

    def add(name, **kw):
        base.add(ParagraphStyle(name=name, **kw))

    add("CoverTitle",
        fontSize=28, leading=34, textColor=C_WHITE,
        alignment=TA_CENTER, fontName="Helvetica-Bold", spaceAfter=8)
    add("CoverSubtitle",
        fontSize=14, leading=18, textColor=colors.HexColor("#c4b5fd"),
        alignment=TA_CENTER, fontName="Helvetica", spaceAfter=4)
    add("CoverMeta",
        fontSize=10, leading=14, textColor=colors.HexColor("#a5b4fc"),
        alignment=TA_CENTER, fontName="Helvetica")

    add("H1",
        fontSize=18, leading=24, textColor=C_HEADER,
        fontName="Helvetica-Bold", spaceBefore=18, spaceAfter=8,
        borderPad=4)
    add("H2",
        fontSize=14, leading=18, textColor=C_SUBHEAD,
        fontName="Helvetica-Bold", spaceBefore=14, spaceAfter=6)
    add("H3",
        fontSize=11, leading=15, textColor=C_PURPLE,
        fontName="Helvetica-Bold", spaceBefore=10, spaceAfter=4)
    add("H4",
        fontSize=10, leading=13, textColor=colors.HexColor("#6d28d9"),
        fontName="Helvetica-BoldOblique", spaceBefore=8, spaceAfter=3)

    add("Body",
        fontSize=9.5, leading=14, textColor=C_BLACK,
        fontName="Helvetica", spaceAfter=6, alignment=TA_JUSTIFY)
    add("WBullet",
        fontSize=9.5, leading=13, textColor=C_BLACK,
        fontName="Helvetica", spaceAfter=3,
        leftIndent=14, bulletIndent=4, bulletFontSize=9)
    add("Bullet2",
        fontSize=9, leading=12, textColor=colors.HexColor("#374151"),
        fontName="Helvetica", spaceAfter=2,
        leftIndent=28, bulletIndent=18, bulletFontSize=8)

    add("WCode",
        fontSize=8, leading=11, textColor=colors.HexColor("#1e1b4b"),
        fontName="Courier", backColor=C_CODEBG,
        borderPad=6, leftIndent=8, rightIndent=8,
        spaceBefore=4, spaceAfter=6)
    add("Caption",
        fontSize=8.5, leading=11, textColor=C_MUTED,
        fontName="Helvetica-Oblique", alignment=TA_CENTER, spaceAfter=8)
    add("TOCEntry1",
        fontSize=11, leading=16, fontName="Helvetica-Bold",
        textColor=C_PURPLE, leftIndent=0)
    add("TOCEntry2",
        fontSize=9.5, leading=14, fontName="Helvetica",
        textColor=C_BLACK, leftIndent=16)
    add("TOCEntry3",
        fontSize=9, leading=13, fontName="Helvetica",
        textColor=C_MUTED, leftIndent=30)
    add("SectionNote",
        fontSize=9, leading=12, textColor=colors.HexColor("#374151"),
        fontName="Helvetica-Oblique", leftIndent=8, spaceBefore=2, spaceAfter=6)

    return base

S = make_styles()


# ── Helpers ────────────────────────────────────────────────────────────────
def h1(text):  return Paragraph(text, S["H1"])
def h2(text):  return Paragraph(text, S["H2"])
def h3(text):  return Paragraph(text, S["H3"])
def h4(text):  return Paragraph(text, S["H4"])
def p(text):   return Paragraph(text, S["Body"])
def note(text): return Paragraph(f"<i>{text}</i>", S["SectionNote"])
def sp(n=6):   return Spacer(1, n)
def hr():      return HRFlowable(width="100%", thickness=0.5,
                                  color=C_BORDER, spaceAfter=8, spaceBefore=4)
def pb():      return PageBreak()

def bullet(text, level=1):
    style = S["WBullet"] if level == 1 else S["Bullet2"]
    return Paragraph(f"• {text}", style)

def code(text):
    return Preformatted(text, S["WCode"])

def table(data, col_widths=None, header=True):
    t = Table(data, colWidths=col_widths, repeatRows=1 if header else 0)
    style = [
        ("BACKGROUND",  (0, 0), (-1, 0 if header else -1), C_TABLE_H),
        ("TEXTCOLOR",   (0, 0), (-1, 0), C_PURPLE),
        ("FONTNAME",    (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE",    (0, 0), (-1, 0), 9),
        ("FONTNAME",    (0, 1), (-1, -1), "Helvetica"),
        ("FONTSIZE",    (0, 1), (-1, -1), 8.5),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [C_WHITE, C_TABLE_R]),
        ("GRID",        (0, 0), (-1, -1), 0.4, C_BORDER),
        ("VALIGN",      (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING",  (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING",(0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING",(0, 0), (-1, -1), 6),
    ]
    t.setStyle(TableStyle(style))
    return t


def signal_table(rows):
    """Two-col table: Signal → Description."""
    data = [["Signal / Method", "Description"]] + rows
    return table(data, col_widths=[6*cm, 10.5*cm])

def field_table(rows):
    data = [["Field", "Type", "Default", "Description"]] + rows
    return table(data, col_widths=[3.5*cm, 2.5*cm, 2.5*cm, 8*cm])


# ── Cover page ─────────────────────────────────────────────────────────────
def cover_page(canvas, doc):
    canvas.saveState()
    # Dark background
    canvas.setFillColor(C_DARKBG)
    canvas.rect(0, 0, W, H, fill=1, stroke=0)
    # Purple accent band
    canvas.setFillColor(C_PURPLE)
    canvas.rect(0, H * 0.42, W, 5, fill=1, stroke=0)
    canvas.rect(0, H * 0.62, W, 5, fill=1, stroke=0)
    # Wafer icon (simple circle)
    canvas.setStrokeColor(colors.HexColor("#7c3aed"))
    canvas.setFillColor(colors.HexColor("#2d1b69"))
    canvas.setLineWidth(3)
    canvas.circle(W / 2, H * 0.77, 55, fill=1, stroke=1)
    # Inner circle rings
    canvas.setStrokeColor(colors.HexColor("#a78bfa"))
    canvas.setLineWidth(1)
    canvas.circle(W / 2, H * 0.77, 38, fill=0, stroke=1)
    canvas.circle(W / 2, H * 0.77, 20, fill=0, stroke=1)
    # Cross-hairs
    cx, cy = W / 2, H * 0.77
    canvas.line(cx - 55, cy, cx + 55, cy)
    canvas.line(cx, cy - 55, cx, cy + 55)
    # Footer band
    canvas.setFillColor(colors.HexColor("#12101f"))
    canvas.rect(0, 0, W, 2*cm, fill=1, stroke=0)
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(colors.HexColor("#6b7280"))
    canvas.drawCentredString(W / 2, 0.7*cm,
        f"Generated {datetime.now().strftime('%Y-%m-%d %H:%M')}  ·  Wafer Map Tool v2.3")
    canvas.restoreState()


def later_pages(canvas, doc):
    canvas.saveState()
    # Top purple bar
    canvas.setFillColor(C_PURPLE)
    canvas.rect(0, H - 1.1*cm, W, 1.1*cm, fill=1, stroke=0)
    canvas.setFont("Helvetica-Bold", 9)
    canvas.setFillColor(C_WHITE)
    canvas.drawString(1.5*cm, H - 0.7*cm, "Wafer Map Tool — Technical Documentation")
    canvas.drawRightString(W - 1.5*cm, H - 0.7*cm, f"v2.3")
    # Bottom bar
    canvas.setFillColor(colors.HexColor("#f0edfb"))
    canvas.rect(0, 0, W, 1*cm, fill=1, stroke=0)
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(C_MUTED)
    canvas.drawCentredString(W / 2, 0.35*cm, f"Page {doc.page}")
    canvas.restoreState()


# ── Document builder ───────────────────────────────────────────────────────
class DocBuilder(BaseDocTemplate):
    def __init__(self, filename):
        super().__init__(filename, pagesize=A4,
                         leftMargin=1.8*cm, rightMargin=1.8*cm,
                         topMargin=1.7*cm, bottomMargin=1.5*cm)
        cover_frame  = Frame(0, 0, W, H, id="cover")
        normal_frame = Frame(self.leftMargin, self.bottomMargin + 1*cm,
                             W - self.leftMargin - self.rightMargin,
                             H - self.topMargin - self.bottomMargin - 1.2*cm,
                             id="normal")
        self.addPageTemplates([
            PageTemplate(id="Cover",  frames=[cover_frame],  onPage=cover_page),
            PageTemplate(id="Normal", frames=[normal_frame], onPage=later_pages),
        ])

    def afterFlowable(self, flowable):
        """Register headings for TOC."""
        if isinstance(flowable, Paragraph):
            style = flowable.style.name
            txt   = flowable.getPlainText()
            if style == "H1":
                self.notify("TOCEntry", (0, txt, self.page, None))
            elif style == "H2":
                self.notify("TOCEntry", (1, txt, self.page, None))
            elif style == "H3":
                self.notify("TOCEntry", (2, txt, self.page, None))


# ── Content sections ───────────────────────────────────────────────────────
def content():
    story = []

    # ── Cover ──────────────────────────────────────────────────────────────
    story += [
        NextPageTemplate("Cover"),
        Spacer(1, H * 0.55),
        Paragraph("Wafer Map Tool", S["CoverTitle"]),
        Paragraph("Technical Documentation", S["CoverSubtitle"]),
        Spacer(1, 6),
        Paragraph("Architecture · Pipeline · API · UI Reference", S["CoverMeta"]),
        Spacer(1, 4),
        Paragraph("Version 2.3", S["CoverMeta"]),
        pb(),
    ]

    # ── TOC ────────────────────────────────────────────────────────────────
    story.append(NextPageTemplate("Normal"))
    story.append(h1("Table of Contents"))
    toc = TableOfContents()
    toc.levelStyles = [S["TOCEntry1"], S["TOCEntry2"], S["TOCEntry3"]]
    toc.dotsMinLevel = 0
    story.append(toc)
    story.append(pb())

    # ══════════════════════════════════════════════════════════════════════
    # 1. SYSTEM OVERVIEW
    # ══════════════════════════════════════════════════════════════════════
    story.append(h1("1. System Overview"))
    story.append(p(
        "The <b>Wafer Map Tool</b> is a desktop application for analysing semiconductor wafer "
        "measurement data. It provides a PyQt6 graphical interface and a headless programmatic "
        "API. Given a plain-text measurement file it produces three output artefacts: a "
        "multi-page PDF report, a colour-summary CSV, and an optional PowerPoint presentation."
    ))

    story.append(h2("1.1 Technology Stack"))
    tech = [
        ["Layer", "Library / Framework", "Purpose"],
        ["Frontend UI", "PyQt6", "Main window, widgets, threading"],
        ["Visualisation", "Matplotlib (Agg backend)", "Wafer contour maps, charts, PDF pages"],
        ["Data Processing", "NumPy · Pandas · SciPy", "Array maths, DataFrames, griddata interpolation"],
        ["PDF Export", "Matplotlib PdfPages + pypdf", "Multi-page PDF + bookmarks"],
        ["PPTX Export", "python-pptx (optional)", "PowerPoint slides"],
        ["Logging", "Python logging", "File + console, session separators"],
        ["Threading", "QThread + threading.Event", "Non-blocking background worker"],
    ]
    story.append(table(tech, col_widths=[3.5*cm, 5*cm, 8*cm]))

    story.append(h2("1.2 Entry Point"))
    story.append(p("<b>main.py</b> is the application launcher. It:"))
    story += [
        bullet("Installs a global <code>sys.excepthook</code> so unhandled exceptions are "
               "written to the log file before the process exits."),
        bullet("Calls <code>session_start()</code> to write a timestamped separator to <b>wafer_tool.log</b>."),
        bullet("Creates a <code>QApplication</code>, instantiates <b>DataProcessorUI</b>, "
               "and enters the Qt event loop."),
        bullet("The same package can be imported headlessly "
               "(<code>from wafer_tool import PlotConfig, generate_report</code>) without touching Qt."),
    ]

    story.append(h2("1.3 File Structure"))
    story.append(code("""\
E:\\claude\\Wafer_tool_NEW2\\
├── main.py                          Entry point — PyQt6 GUI launcher
├── generate_docs.py                 This documentation generator
├── wafer_tool.log                   Append-only session log
└── wafer_tool\\
    ├── __init__.py                  Public API surface
    ├── config.py                    PlotConfig dataclass + constants
    ├── data_loader.py               CSV / whitespace file parser
    ├── report.py                    Pipeline orchestrator
    ├── statistics.py                8-condition classification & bar chart
    ├── geometry.py                  Pure maths: transforms, interpolation
    ├── plotting.py                  draw_wafer_ax() contour renderer
    ├── logger.py                    Centralised logging setup
    ├── exceptions.py                Custom exception hierarchy
    ├── worker.py                    ReportWorker (QThread)
    ├── exporters\\
    │   ├── pdf_exporter.py          Multi-page PDF with bookmarks
    │   ├── csv_exporter.py          Per-wafer colour-summary CSV
    │   └── pptx_exporter.py        PowerPoint report (optional)
    └── ui\\
        ├── main_window.py           DataProcessorUI + all inline widgets
        ├── histogram_widget.py      Integrated histogram + stats bar
        ├── orientation_widget.py    Reusable wafer-orientation selector
        └── threshold_viz_widget.py  Threshold band visualisation"""))
    story.append(pb())

    # ══════════════════════════════════════════════════════════════════════
    # 2. PIPELINE
    # ══════════════════════════════════════════════════════════════════════
    story.append(h1("2. Processing Pipeline"))
    story.append(p(
        "The pipeline is orchestrated by <b>report.py → generate_report()</b>. "
        "All heavy computation runs on a background <b>QThread</b> (worker.py) so the "
        "UI remains responsive. The diagram below shows the complete data flow."
    ))
    story.append(code("""\
  measurement file (.csv / .txt / .dat)
          │
          ▼
  ┌───────────────────────────────────┐
  │  data_loader.read_wafer_data()    │  Parse → DataFrame[lot,wafer,x,y,value]
  └────────────────┬──────────────────┘
                   │
          ┌────────┴────────┐
          ▼                 ▼
  ┌───────────────┐  ┌──────────────────────────────────┐
  │  statistics.  │  │  report._render_wafer_pngs()     │
  │  calculate_   │  │  ┌─────────────────────────────┐ │
  │  8_condition_ │  │  │ Per (lot, wafer):            │ │
  │  statistics() │  │  │  geometry.apply_transforms() │ │
  └───────┬───────┘  │  │  geometry.build_wafer_grid() │ │
          │          │  │  plotting.draw_wafer_ax()    │ │
          │          │  │  → square PNG (archive)      │ │
          │          │  │  → wide PNG  (PPTX)          │ │
          │          │  └─────────────────────────────┘ │
          │          └──────────────┬───────────────────┘
          │                         │
          ▼                         ▼
  ┌───────────────────────────────────────────────────────┐
  │               Exporters (parallel outputs)            │
  ├──────────────────┬────────────────┬───────────────────┤
  │ pdf_exporter     │ csv_exporter   │ pptx_exporter     │
  │ generate_pdf()   │ export_color_  │ create_power-     │
  │                  │ summary_csv()  │ point_report()    │
  │ • Summary text   │                │                   │
  │ • 8-cond chart   │ • Lot/Wafer ID │ • Title slide     │
  │ • 5×5 wafer grid │ • G/Y/R binary │ • Summary slides  │
  │ • PDF bookmarks  │ • One row/wafer│ • Wafer slides    │
  └──────────────────┴────────────────┴───────────────────┘
          │                │                  │
          ▼                ▼                  ▼
      report.pdf    color_summary.csv   report.pptx"""))

    story.append(h2("2.1 Step-by-Step Walkthrough"))

    story.append(h3("Step 1 — Load Data"))
    story += [
        p("Called via <code>read_wafer_data(filepath)</code>. Tries two parse strategies in order:"),
        bullet("CSV (comma-separated) — fast C engine."),
        bullet("Whitespace/tab-separated — Python engine (required for regex separator <code>\\s+</code>)."),
        p("Accepts two input layouts:"),
        bullet("<b>5-column</b>: Lot | Wafer | X | Y | Value"),
        bullet("<b>4-column</b>: \"LotID WaferID\" (space-joined) | X | Y | Value"),
        p("All numeric columns are coerced to <b>float32</b> to halve memory. "
          "Lot and wafer IDs use <b>category</b> dtype. Rows with NaN are dropped."),
    ]

    story.append(h3("Step 2 — Pre-compute Statistics"))
    story += [
        p("Called via <code>calculate_8_condition_statistics(data, config)</code>. "
          "Classifies each wafer with ≥4 die points into one of <b>8 conditions</b> "
          "based on which colour zones are present:"),
    ]
    cond_data = [
        ["Code", "Meaning", "Zones Present"],
        ["100", "Green only",          "High zone only"],
        ["110", "Green + Yellow",       "High + Mid zones"],
        ["010", "Yellow only",          "Mid zone only"],
        ["111", "Green + Yellow + Red", "All three zones"],
        ["101", "Green + Red",          "High + Low zones"],
        ["011", "Yellow + Red",         "Mid + Low zones"],
        ["001", "Red only",             "Low zone only"],
        ["000", "No colour",            "No die assigned (< 4 pts or all in one zone edge)"],
    ]
    story.append(table(cond_data, col_widths=[2*cm, 5*cm, 9.5*cm]))
    story += [
        sp(4),
        p("Zone boundaries are derived from <code>PlotConfig.t_low</code> and <code>t_high</code>. "
          "Colour polarity is controlled by <code>high_is_green</code>:"),
        bullet("<b>high_is_green=True</b>: value > t_high → Green, t_low–t_high → Yellow, < t_low → Red."),
        bullet("<b>high_is_green=False</b>: colour assignment reversed."),
    ]

    story.append(h3("Step 3 — Render Wafer PNGs"))
    story += [
        p("The inner loop in <code>_render_wafer_pngs()</code> runs once per (lot, wafer) pair:"),
        bullet("Creates a square 8×8 inch, 100 dpi Matplotlib figure."),
        bullet("Calls <code>draw_wafer_ax()</code> which applies transforms, "
               "builds the 2-D interpolation grid, and renders a contourf map."),
        bullet("Saves to <code>individual_pngs_{timestamp}/</code>."),
        bullet("If python-pptx is installed, creates a second wide 8×6 inch figure "
               "with legend to <code>temp_pptx_images/</code>."),
        bullet("Immediately closes and nulls each figure before opening the next "
               "to keep peak memory to one figure at a time."),
        bullet("Fires <code>on_wafer_ready(lot_id, wafer_id, png_path)</code> callback "
               "for the UI live-preview grid."),
    ]

    story.append(h3("Step 4 — PDF Export"))
    story += [
        p("Calls <code>generate_pdf()</code>. The PDF is built with Matplotlib's "
          "<b>PdfPages</b> context and then post-processed with <b>pypdf</b> to inject "
          "named bookmarks. Structure:"),
        bullet("Summary text page(s): file path, timestamp, lot table (55 lines per page)."),
        bullet("8-Condition bar chart page (from statistics module)."),
        bullet("Per-lot wafer grid pages: 5×5 = 25 wafers per page, "
               "each with its contour map, legend, and page header."),
        bullet("PDF bookmarks: Summary Report → 8-Condition Distribution → one per lot."),
    ]

    story.append(h3("Step 5 — CSV Export"))
    story += [
        p("Calls <code>export_color_summary_csv()</code>. Re-reads the data file and for "
          "each wafer with ≥4 points emits a row:"),
        bullet("Columns: <b>Lot ID | Wafer ID | Green | Yellow | Red</b> (binary 0/1)."),
        bullet("Returns None gracefully if no valid wafers or file cannot be re-read."),
    ]

    story.append(h3("Step 6 — PowerPoint Export"))
    story += [
        p("Calls <code>create_powerpoint_report()</code> if python-pptx is installed."),
        bullet("Searches for <b>Infineon Default Theme.pptx</b> template; "
               "falls back to python-pptx blank presentation."),
        bullet("Slides: Title → Summary slides → One slide per wafer PNG (sorted alphabetically)."),
        bullet("Temp directories (<code>temp_pptx_images/</code>, <code>temp_summary_images/</code>) "
               "are deleted after the PPTX is written."),
    ]
    story.append(pb())

    # ══════════════════════════════════════════════════════════════════════
    # 3. MODULES
    # ══════════════════════════════════════════════════════════════════════
    story.append(h1("3. Module Reference"))

    # ── config.py ──────────────────────────────────────────────────────────
    story.append(h2("3.1  config.py — Configuration & Constants"))
    story.append(h3("PlotConfig (dataclass)"))
    story.append(field_table([
        ["t_low",        "float", "—",     "Lower threshold boundary (auto-sorted with t_high)"],
        ["t_high",       "float", "—",     "Upper threshold boundary"],
        ["use_log",      "bool",  "False", "Apply log10 scale to measurement values"],
        ["high_is_green","bool",  "False", "Color polarity: True → high values are green"],
        ["mirror_x",     "bool",  "False", "Flip wafer map horizontally"],
        ["mirror_y",     "bool",  "False", "Flip wafer map vertically"],
        ["rot_deg",      "int",   "0",     "Clockwise rotation: 0, 90, 180, or 270 degrees"],
    ]))
    story += [sp(4), p("<b>Derived properties:</b>")]
    story += [
        bullet("<code>color_scheme</code> → <b>ColorScheme</b> with low/mid/high hex colours."),
        bullet("<code>log_suffix</code> → empty string or <code>\"_LOG\"</code> (used in filenames)."),
    ]

    story.append(h3("ColorScheme (frozen dataclass)"))
    story += [
        p("Holds three hex colour strings: <code>low</code>, <code>mid</code>, <code>high</code>."),
        bullet("<b>Factory:</b> <code>ColorScheme.from_mode(high_is_green: bool)</code>"),
        bullet("high_is_green=True  → low=#CC0000 (red), mid=#FFD700 (yellow), high=#00CC00 (green)"),
        bullet("high_is_green=False → low=#00CC00 (green), mid=#FFD700 (yellow), high=#CC0000 (red)"),
    ]

    story.append(h3("Module-Level Constants"))
    const_data = [
        ["Constant",              "Value",  "Purpose"],
        ["GRID_RESOLUTION",       "100",    "Interpolation points per axis (100×100 grid)"],
        ["WAFER_RADIUS_FACTOR",   "1.05",   "Expand boundary 5 % beyond data extent"],
        ["MIN_POINTS_FOR_PLOT",   "4",      "Skip wafers with fewer die points than this"],
        ["MAX_WAFERS_PER_PAGE",   "25",     "5×5 wafer thumbnails per PDF page"],
        ["LINES_PER_SUMMARY_PAGE","55",     "Text lines per summary page in PDF"],
    ]
    story.append(table(const_data, col_widths=[5*cm, 2.5*cm, 9*cm]))

    # ── data_loader.py ─────────────────────────────────────────────────────
    story.append(h2("3.2  data_loader.py — File Parsing"))
    story.append(h3("read_wafer_data(filepath, ...) → pd.DataFrame"))
    story += [
        p("Reads and validates a wafer measurement file. Accepts comma-separated or "
          "whitespace-delimited text. Column format:"),
    ]
    col_data = [
        ["Layout",   "Col 0",            "Col 1", "Col 2", "Col 3", "Col 4"],
        ["5-column", "Lot ID",           "Wafer ID","X",   "Y",     "Value"],
        ["4-column", "\"Lot Wafer\"",    "X",      "Y",    "Value", "(none)"],
    ]
    story.append(table(col_data, col_widths=[2.5*cm, 3*cm, 2.5*cm, 2*cm, 2*cm, 2.5*cm]))
    story += [
        sp(4),
        p("<b>Output DataFrame columns:</b> lot (category), wafer (category), "
          "x (float32), y (float32), value (float32). NaN rows are dropped."),
        p("<b>Errors:</b> raises <code>DataLoadError</code> on file not found, "
          "too few columns, or no valid rows after cleaning."),
    ]

    story.append(h3("Internal: _try_read(filepath) → pd.DataFrame"))
    story += [
        bullet("Strategy 1: comma separator, C engine (fastest)."),
        bullet("Strategy 2: regex <code>\\s+</code>, Python engine (required for regex)."),
        bullet("Raises <code>DataLoadError</code> if both strategies fail or "
               "neither produces ≥4 columns."),
    ]

    # ── geometry.py ────────────────────────────────────────────────────────
    story.append(h2("3.3  geometry.py — Coordinate Transforms & Interpolation"))
    story.append(h3("signed_log10(a, eps=1e-15) → NDArray"))
    story += [
        p("Sign-preserving log10 transform: <code>sign(a) × log10(max(|a|, eps))</code>. "
          "Safe for zero and negative values."),
    ]
    story.append(h3("apply_transforms(x, y, mirror_x, mirror_y, rot_deg) → (x, y)"))
    story += [
        p("Applies mirror and rotation transforms around the data centroid. "
          "Fast path: returns original arrays unchanged if all flags are False/0."),
        bullet("Mirror X: negate x around centroid."),
        bullet("Mirror Y: negate y around centroid."),
        bullet("Rotation map: 90° → (y, −x), 180° → (−x, −y), 270° → (−y, x)."),
    ]
    story.append(h3("build_wafer_grid(x, y, z, resolution, radius_factor) → (xi, yi, zi, x_mid, y_mid, r)"))
    story += [
        p("Creates a regular 2-D grid and interpolates sparse die measurements onto it:"),
        bullet("Computes data centroid and radius (max extent × radius_factor)."),
        bullet("Builds <code>resolution × resolution</code> meshgrid (float32)."),
        bullet("Interpolates via <b>scipy.griddata</b>: linear first, then nearest-neighbour "
               "to fill NaN holes left by linear."),
        bullet("Clamps to [z.min(), z.max()] to prevent contourf overshoot."),
        bullet("Sets grid cells outside the wafer circle to NaN (masked)."),
    ]

    # ── plotting.py ────────────────────────────────────────────────────────
    story.append(h2("3.4  plotting.py — Wafer Contour Renderer"))
    story.append(h3("draw_wafer_ax(ax, df, wafer_id, config, show_legend, show_title) → bool"))
    story += [
        p("Renders a single wafer onto a Matplotlib <code>Axes</code> object. "
          "Returns <b>True</b> if rendered, <b>False</b> if skipped (insufficient points)."),
        p("Rendering steps:"),
        bullet("Extract x, y, value as float32 (copy=False where possible)."),
        bullet("Return False if fewer than MIN_POINTS_FOR_PLOT (4) points."),
        bullet("Apply transforms via geometry.apply_transforms()."),
        bullet("Build interpolation grid via geometry.build_wafer_grid() (100×100)."),
        bullet("Apply log10 if config.use_log (signed_log10 on grid)."),
        bullet("Render 3-level <code>ax.contourf()</code> with the ColorScheme colours."),
        bullet("Draw white boundary circle to mask outside the wafer."),
        bullet("Optionally add legend patches (show_legend=True) at axes-right."),
        bullet("Optionally add wafer ID title above the plot (show_title=True)."),
    ]

    # ── statistics.py ──────────────────────────────────────────────────────
    story.append(h2("3.5  statistics.py — 8-Condition Classification"))
    story.append(h3("calculate_8_condition_statistics(data, config) → ConditionCounts"))
    story += [
        p("Classifies every wafer (with ≥4 die points) into one of 8 binary-coded "
          "conditions based on which colour zones are present. "
          "Returns a <b>ConditionCounts</b> named tuple:"),
        bullet("<code>counts: dict[str, int]</code> — 8 keys (\"000\"–\"111\"), each value is the number of wafers."),
        bullet("<code>total_wafers: int</code> — total wafers with ≥4 points."),
    ]
    story.append(h3("create_8_condition_summary_page(pdf, result, config, filepath, ...) → int"))
    story += [
        p("Renders a full-page Matplotlib bar chart showing wafer count and percentage "
          "for each of the 8 conditions. Inserts into a PdfPages object. "
          "Optionally saves a PNG copy (for PPTX). Returns updated page counter."),
    ]

    # ── report.py ──────────────────────────────────────────────────────────
    story.append(h2("3.6  report.py — Pipeline Orchestrator"))
    story.append(h3("generate_report(filepath, config, out_dir, on_progress, on_wafer_ready)"))
    story += [
        p("The top-level public function. Runs the complete pipeline and returns:"),
        bullet("<b>pdf_path</b>: absolute path to the generated PDF."),
        bullet("<b>csv_path</b>: absolute path to the colour summary CSV (or None)."),
        bullet("<b>pptx_path</b>: absolute path to the PPTX, or an explanatory string "
               "if python-pptx is not installed."),
        p("<b>Callback signatures:</b>"),
    ]
    story.append(code("""\
on_progress(current: int, total: int, message: str) -> None
    # total = num_wafers + 3  (PDF + CSV + PPTX steps)
    # Called once per wafer and once per export step.
    # Raise RuntimeError to cancel the pipeline cleanly.

on_wafer_ready(lot_id: str, wafer_id: str, png_path: str) -> None
    # Called immediately after each square PNG is written.
    # Use to update a live preview widget."""))

    story.append(h3("Private: _emit(callback, current, total, message)"))
    story += [
        p("Calls the progress callback inside a try/except. "
          "<b>RuntimeError is re-raised</b> (cancellation). "
          "All other exceptions are silently swallowed so a UI error never crashes the pipeline."),
    ]

    # ── worker.py ──────────────────────────────────────────────────────────
    story.append(h2("3.7  worker.py — Background Thread"))
    story.append(h3("ReportWorker (QThread)"))
    story.append(signal_table([
        ["progress(int)",              "Overall pipeline percentage 0–100. Connect to overall_bar.setValue."],
        ["wafer_progress(int)",        "Wafer-render-phase percentage 0–100. Connect to wafer_bar.setValue."],
        ["status_message(str)",        "Human-readable step description. Connect to a QLabel."],
        ["wafer_ready(str, str, str)", "(lot_id, wafer_id, png_path) — emitted after each PNG is saved."],
        ["report_done(str, str, str)", "(pdf_path, csv_path, pptx_path) — emitted on success."],
        ["error(str)",                 "Error or cancellation message. Connect to an error dialog."],
        ["cancel()",                   "Public method — sets a threading.Event. Takes effect between wafers."],
    ]))
    story += [
        sp(4),
        p("<b>Cancellation mechanism:</b> <code>cancel()</code> sets a <code>threading.Event</code>. "
          "The <code>_on_progress()</code> callback checks the flag before each emit and raises "
          "<code>RuntimeError(\"Cancelled by user.\")</code>, which propagates through "
          "<code>_emit()</code> and exits <code>generate_report()</code> cleanly."),
    ]

    story.append(pb())

    # ── Exporters ──────────────────────────────────────────────────────────
    story.append(h1("4. Exporters"))

    story.append(h2("4.1  pdf_exporter.py"))
    story.append(h3("generate_pdf(...) → str"))
    story += [
        p("Produces a multi-page A4 PDF. Implementation uses "
          "<b>matplotlib.backends.backend_pdf.PdfPages</b> for page rendering, "
          "then <b>pypdf PdfReader/PdfWriter</b> for bookmark injection."),
        p("<b>Output structure:</b>"),
        bullet("Summary text page(s) — 55 lines per page, monospace."),
        bullet("8-Condition bar chart — full page."),
        bullet("Lot wafer grid pages — 5×5 thumbnails (25 max per page), "
               "lot header, threshold legend, page number."),
        p("<b>Bookmarks:</b> \"Summary Report\", \"8-Condition Distribution\", "
          "one per lot (\"Lot: XXX\")."),
        p("<b>File naming:</b> <code>{basename}{log_suffix}_{timestamp}.pdf</code>"),
    ]

    story.append(h2("4.2  csv_exporter.py"))
    story.append(h3("export_color_summary_csv(filepath, config, out_dir) → str | None"))
    story += [
        p("Produces a CSV with one row per wafer (≥4 die points):"),
        bullet("Columns: <b>Lot ID, Wafer ID, Green, Yellow, Red</b> (binary 0/1)."),
        bullet("Green/Yellow/Red indicate whether ≥1 die falls in that colour zone."),
        bullet("Returns None if no valid wafers exist or file cannot be re-read."),
        p("<b>File naming:</b> <code>{basename}{log_suffix}_color_summary_{timestamp}.csv</code>"),
    ]

    story.append(h2("4.3  pptx_exporter.py"))
    story.append(h3("create_powerpoint_report(png_dir, pptx_path, title_text, summary_imgs) → None"))
    story += [
        p("Produces a PowerPoint presentation. Requires python-pptx "
          "(<code>HAS_PPTX</code> flag checked at import time)."),
        p("<b>Template search order:</b>"),
        bullet("PyInstaller <code>_MEIPASS</code> directory (bundled app)."),
        bullet("Executable / script directory."),
        bullet("Falls back to python-pptx blank presentation."),
        p("<b>Slide order:</b>"),
        bullet("Slide 1: Title (title_text)."),
        bullet("Slides 2-N: Summary images (e.g., 8-condition chart)."),
        bullet("Remaining slides: one PNG per wafer, sorted alphabetically."),
    ]

    story.append(pb())

    # ══════════════════════════════════════════════════════════════════════
    # 5. UI ARCHITECTURE
    # ══════════════════════════════════════════════════════════════════════
    story.append(h1("5. UI Architecture"))

    story.append(h2("5.1  Window Layout"))
    story += [
        p("The main window is a <b>QMainWindow</b> split into two panels via a "
          "<b>QSplitter</b>. The left panel (360 px, fixed) holds all input controls. "
          "The right panel (expanding) shows the visualisation tabs and progress."),
    ]
    story.append(code("""\
┌──────────────────────────┬────────────────────────────────────────────┐
│ LEFT PANEL (360 px)      │ RIGHT PANEL (expanding)                   │
│                          │                                            │
│  [Input File]            │  [☀ Bright Mode]          (top-right btn) │
│   • Browse button        │                                            │
│   • File path edit       │  ┌──────┬──────┬──────────────────────┐   │
│   • ✓ N die · W wafers   │  │🗺    │⬡    │📊                   │   │
│                          │  │Live  │Scat- │Histo-               │   │
│  [Parameters]            │  │Prev. │ter   │gram                 │   │
│   • Limit 1 (SciLineEdit)│  └──────┴──────┴──────────────────────┘   │
│   • Limit 2 (SciLineEdit)│                                            │
│                          │  [5×5 WaferGridWidget]                     │
│  [Options]               │    or ScatterCanvas                        │
│   • Log scale checkbox   │    or HistogramWidget                      │
│   • High=Green checkbox  │                                            │
│   • 4 rotation radios    │  [⏸ Pause Preview]       (Live tab only)  │
│   • Mirror X/Y checkboxes│                                            │
│   • WaferOrientationWidget  ├──────────────────────────────────────────┤
│                          │  [Output Location label + Open Folder btn] │
│  [Output Folder]         ├──────────────────────────────────────────────┤
│   • Folder path edit     │  [Progress Group]                          │
│   • Browse button        │   Status label (yellow italic)             │
│                          │   Wafer render bar  (purple, 0–100%)       │
│  [▶ Generate Report]     │   Overall pipeline bar (green, 0–100%)     │
│  [✕ Cancel (disabled)]   │                                            │
│                          │ STATUS BAR: "Ready." / step message        │
└──────────────────────────┴────────────────────────────────────────────┘"""))

    story.append(h2("5.2  Theme System"))
    theme_data = [
        ["Property",        "Dark Mode (default)",  "Bright Mode"],
        ["Background",      "#1e1e2e",              "#f5f5fa"],
        ["Panel",           "#2a2a3e",              "#ffffff"],
        ["Accent (buttons)","#7c3aed",              "#7c3aed"],
        ["Foreground text", "#e2e8f0",              "#1a1a2e"],
        ["Muted text",      "#94a3b8",              "#4b5563"],
        ["Border",          "#4a4a6a",              "#d1d5db"],
        ["Toggle button",   "☀  Bright Mode",      "🌙  Dark Mode"],
    ]
    story.append(table(theme_data, col_widths=[4*cm, 5.5*cm, 5.5*cm]))

    story.append(h2("5.3  Tab Widgets"))

    story.append(h3("Tab 0 — Live Preview (WaferGridWidget)"))
    story += [
        bullet("5×5 grid of QLabel cells (25 thumbnails, auto-reset every 25 wafers)."),
        bullet("Pixmaps capped at 300×300 px to limit memory (~360 KB ARGB vs "
               "~2.5 MB at 800 px)."),
        bullet("Tooltip on each cell: \"Lot: X | Wafer: Y\"."),
        bullet("<b>Pause button</b>: suppresses <code>_on_wafer()</code> so the current grid "
               "stays frozen for review. Resumes on next run or manual toggle."),
        bullet("Grid resets automatically when a new lot ID is encountered."),
    ]

    story.append(h3("Tab 1 — Threshold Scatter (ScatterCanvas)"))
    story += [
        bullet("X-axis: die index; Y-axis: measurement value (linear or log)."),
        bullet("Three scatter series (low/mid/high zones) for efficient rendering."),
        bullet("Horizontal threshold lines with value labels."),
        bullet("Shaded zone bands (axhspan) for visual context."),
        bullet("Downsampled to 200 000 points if data exceeds that count (deterministic seed)."),
    ]

    story.append(h3("Tab 2 — Histogram (HistogramWidget)"))
    story += [
        bullet("Stats bar: N, Min, Max, Mean, Median, Std — computed from raw values."),
        bullet("Bin count: <b>Freedman-Diaconis rule</b> (h = 2 × IQR / n^(1/3)). "
               "Fallback to Sturges if IQR ≤ 0. Hard cap: 120 bins."),
        bullet("Each bar is individually coloured by zone membership (midpoint vs thresholds)."),
        bullet("Vertical threshold lines with rotated labels."),
        bullet("Log X-axis toggle button."),
    ]

    story.append(h2("5.4  Supporting Widgets"))
    story.append(h3("SciLineEdit"))
    story += [
        p("Custom <b>QLineEdit</b> that accepts float/scientific notation "
          "(e.g., <code>1e-5</code>, <code>-3.14</code>). Validates on each keystroke; "
          "turns the border red on invalid input. "
          "Methods: <code>value() → float</code>, <code>is_valid() → bool</code>."),
    ]
    story.append(h3("WaferOrientationWidget"))
    story += [
        p("130×130 px QPainter widget. Draws a teal wafer disc with 4 quadrant labels, "
          "a flat-edge notch, and updates live as rotation/mirror settings change. "
          "Labels counter-rotate so they remain upright."),
    ]
    story.append(h3("OrientationWidget (reusable)"))
    story += [
        p("Standalone widget combining Mirror X/Y checkboxes, 4 rotation radio buttons, "
          "and a Matplotlib wafer preview canvas. Emits <code>changed()</code> signal."),
    ]
    story.append(h3("ThresholdVizWidget"))
    story += [
        p("Real-time threshold band visualisation. Available but not wired in "
          "the main window v2.3. Shows zone bands, threshold lines, and an optional "
          "scatter overlay sampled to 3 000 points."),
    ]

    story.append(pb())

    # ══════════════════════════════════════════════════════════════════════
    # 6. THREADING & SIGNALS
    # ══════════════════════════════════════════════════════════════════════
    story.append(h1("6. Threading & Signal Architecture"))
    story.append(p(
        "The GUI runs on the <b>main thread</b>. All heavy computation "
        "(file load, render loop, PDF/CSV/PPTX export) runs on a "
        "<b>ReportWorker QThread</b>. Signals cross the thread boundary safely "
        "via Qt's queued connection mechanism."
    ))
    story.append(code("""\
  Main Thread (UI)                    Worker Thread (ReportWorker.run)
  ═══════════════════════════════════════════════════════════════════════
  _run()                              │
    ├─ create ReportWorker            │
    ├─ connect signals                │
    └─ worker.start() ───────────────►│ run()
                                      │  ├─ generate_report()
  progress ◄───────────────────────── │  │   ├─ read_wafer_data()
  wafer_progress ◄─────────────────── │  │   ├─ per-wafer render loop
  status_message ◄─────────────────── │  │   │     _on_progress() emits
  wafer_ready ◄────────────────────── │  │   │     _on_wafer_ready() emits
                                      │  │   ├─ generate_pdf()
  report_done ◄────────────────────── │  │   ├─ export_csv()
  error ◄──────────────────────────── │  │   └─ create_pptx()
                                      │  └─ exits run()
  _cancel()                           │
    ├─ disconnect signals             │
    ├─ worker.cancel() ──────────────►│  _on_progress() checks Event
    ├─ reset UI immediately          │  raises RuntimeError → exits
    └─ wire finished→deleteLater     │  emits error("Cancelled by user.")"""))

    story.append(h2("6.1  Cancellation Flow"))
    story += [
        bullet("<code>ReportWorker.cancel()</code> sets a <code>threading.Event</code>."),
        bullet("On the next <code>_on_progress()</code> call (between wafers or export steps), "
               "the flag is detected and <code>RuntimeError</code> is raised."),
        bullet("<code>_emit()</code> in report.py re-raises <code>RuntimeError</code> "
               "while suppressing all other exceptions."),
        bullet("The pipeline exits, worker emits <code>error(\"Cancelled by user.\")</code>."),
        bullet("The UI disconnects signals <i>before</i> calling <code>cancel()</code> so "
               "stale signal emissions after cancellation do not update the UI."),
    ]

    story.append(h2("6.2  Why report_done Instead of finished"))
    story += [
        p("QThread already defines a <code>finished</code> signal (zero arguments) that "
          "fires when <code>run()</code> returns. If a subclass defines its own "
          "<code>finished = pyqtSignal(str, str, str)</code>, it shadows the built-in "
          "signal — making it impossible to connect to the thread-exit event for cleanup."),
        p("The worker therefore uses the name <b>report_done</b> for the success payload "
          "signal, leaving QThread's <code>finished</code> intact for <code>deleteLater()</code> "
          "wiring on cancel."),
    ]
    story.append(pb())

    # ══════════════════════════════════════════════════════════════════════
    # 7. MEMORY OPTIMISATION
    # ══════════════════════════════════════════════════════════════════════
    story.append(h1("7. Memory Optimisation"))

    story.append(h2("7.1  Data Type Shrinking"))
    dtype_data = [
        ["Array",          "Before",   "After",   "Saving"],
        ["x, y coords",    "float64",  "float32", "50 %"],
        ["value/z",        "float64",  "float32", "50 %"],
        ["Interp grid zi", "float64",  "float32", "50 %"],
        ["Lot, Wafer IDs", "object",   "category","~80 % for repeated strings"],
        ["Meshgrid xi, yi","float64",  "float32", "50 %"],
    ]
    story.append(table(dtype_data, col_widths=[4*cm, 3*cm, 3*cm, 6.5*cm]))

    story.append(h2("7.2  Explicit Array Deletion"))
    story += [
        p("Intermediate arrays are deleted with <code>del</code> immediately after use "
          "to release memory before the next allocation:"),
        bullet("<code>del raw</code> in data_loader after building typed DataFrame."),
        bullet("<code>del lot_series, wafer_series, x_series, y_series, val_series</code> "
               "after DataFrame assembly."),
        bullet("<code>del x, y, z</code> in plotting after grid is built."),
        bullet("<code>del data</code> in report.py after PNG rendering, before PPTX step."),
        bullet("<code>gc.collect()</code> after the wafer render loop and after report completion "
               "to release Matplotlib's figure cache."),
    ]

    story.append(h2("7.3  Figure Lifecycle"))
    story += [
        p("Each figure is created, saved, and closed in a <code>try/finally</code> block. "
          "The square figure is closed and set to <code>None</code> <i>before</i> the wide "
          "(PPTX) figure is opened — so only one figure exists in memory at a time per wafer."),
    ]

    story.append(h2("7.4  Scatter / Preview Downsampling"))
    mem_data = [
        ["Location",            "Full data", "Sampled to",   "Method"],
        ["ScatterCanvas (UI)",  "any size",  "200 000 pts",  "Deterministic numpy.random.seed(0)"],
        ["ThresholdVizWidget",  "any size",  "3 000 pts",    "Same deterministic sample"],
        ["WaferGridWidget cells","800 px PNG","300×300 px",  "QPixmap.scaledToWidth()"],
    ]
    story.append(table(mem_data, col_widths=[4*cm, 2.5*cm, 2.5*cm, 7.5*cm]))
    story += [
        sp(4),
        p("With these strategies combined, a typical 13 M-point, 300-wafer file sees "
          "<b>~25–35 % reduction in peak memory</b> and <b>~15–25 % faster</b> load and render times "
          "compared to float64/object dtype equivalents."),
    ]
    story.append(pb())

    # ══════════════════════════════════════════════════════════════════════
    # 8. LOGGING & ERROR HANDLING
    # ══════════════════════════════════════════════════════════════════════
    story.append(h1("8. Logging & Error Handling"))

    story.append(h2("8.1  logger.py"))
    story += [
        bullet("<b>Log file:</b> <code>{repo_root}/wafer_tool.log</code> — append mode, "
               "survives across runs."),
        bullet("<b>Handlers:</b> FileHandler (UTF-8) + StreamHandler (stdout)."),
        bullet("<b>Level:</b> DEBUG (all messages captured)."),
        bullet("<b>Format:</b> <code>YYYY-MM-DD HH:MM:SS  LEVEL     name — message</code>"),
        bullet("<b>Silenced:</b> matplotlib, PIL, fontTools loggers set to WARNING."),
    ]
    story.append(h3("session_start()"))
    story += [
        p("Writes a visual separator and timestamp at the start of each run:"),
    ]
    story.append(code("""\
========================================================================
  NEW SESSION  2026-04-10 12:03:31
========================================================================"""))

    story.append(h3("log_exception(exc, context='')"))
    story += [
        p("Logs a full Python traceback at ERROR level. "
          "Called from: worker.py on run failure, report.py per-wafer errors, "
          "main.py global excepthook."),
    ]

    story.append(h2("8.2  Exception Hierarchy"))
    story.append(code("""\
WaferToolError (base)
├─ DataLoadError           — file not found, parse failure, no valid rows
├─ InsufficientDataError   — too few die points (< MIN_POINTS_FOR_PLOT)
└─ ReportGenerationError   — PDF / CSV / PPTX export failure"""))

    story.append(h2("8.3  Error Flow"))
    story += [
        bullet("<b>DataLoadError</b> → raised by data_loader → caught in report.py → "
               "re-raised as ValueError → caught in worker.run → emitted as error signal → "
               "shown in UI as \"✗ error message\"."),
        bullet("<b>Per-wafer render exceptions</b> → caught in _render_wafer_pngs, "
               "logged with log_exception, wafer skipped."),
        bullet("<b>Callback RuntimeError</b> → re-raised by _emit() → propagates out of "
               "generate_report → caught in worker.run as generic Exception → emitted as error."),
        bullet("<b>Uncaught exceptions</b> → caught by sys.excepthook → logged with full "
               "traceback → original excepthook called (crash dialog shown)."),
    ]
    story.append(pb())

    # ══════════════════════════════════════════════════════════════════════
    # 9. PROGRAMMATIC API
    # ══════════════════════════════════════════════════════════════════════
    story.append(h1("9. Programmatic (Headless) API"))
    story += [
        p("The tool can be used without the GUI by importing directly from the package. "
          "No Qt installation required for headless use:"),
    ]
    story.append(code("""\
from wafer_tool import PlotConfig, generate_report

# 1. Define configuration
config = PlotConfig(
    t_low        = 1e-5,       # lower threshold
    t_high       = 1e-4,       # upper threshold
    use_log      = True,       # log10 scale
    high_is_green= True,       # high value = green
    mirror_x     = False,
    mirror_y     = False,
    rot_deg      = 0,          # 0 / 90 / 180 / 270
)

# 2. Optional progress callback
def on_progress(current, total, message):
    print(f"[{current}/{total}] {message}")

# 3. Run the pipeline (blocking)
pdf_path, csv_path, pptx_path = generate_report(
    filepath    = "measurements.csv",
    config      = config,
    out_dir     = "/tmp/wafer_output",
    on_progress = on_progress,
)

print(f"PDF  → {pdf_path}")
print(f"CSV  → {csv_path}")
print(f"PPTX → {pptx_path}")"""))
    story += [
        sp(6),
        p("<b>Output directory</b> is created if it does not exist. "
          "All three output files are written to <code>out_dir</code> with timestamped names."),
        p("<b>Cancellation (headless):</b> raise <code>RuntimeError</code> from the "
          "<code>on_progress</code> callback at any point to abort the pipeline cleanly."),
    ]
    story.append(pb())

    # ══════════════════════════════════════════════════════════════════════
    # 10. EXPORT FORMAT SPECS
    # ══════════════════════════════════════════════════════════════════════
    story.append(h1("10. Export Format Specifications"))

    story.append(h2("10.1  PDF"))
    pdf_data = [
        ["Property",      "Value"],
        ["Page size",     "A4 (210 × 297 mm), portrait"],
        ["Summary pages", "~55 lines each, monospace font"],
        ["Chart page",    "8-condition bar chart, full page"],
        ["Wafer pages",   "5 × 5 grid = 25 wafers per page"],
        ["Bookmarks",     "Summary Report, 8-Condition Distribution, one per lot"],
        ["File naming",   "{basename}{log_suffix}_{timestamp}.pdf"],
    ]
    story.append(table(pdf_data, col_widths=[5*cm, 11.5*cm], header=False))

    story.append(h2("10.2  CSV"))
    story.append(code("""\
Lot ID,Wafer ID,Green,Yellow,Red
LOT001,1,1,0,0
LOT001,2,1,1,1
LOT001,3,0,1,1
..."""))
    story += [
        bullet("One row per wafer with ≥4 die points."),
        bullet("Green/Yellow/Red: 1 if ≥1 die in that zone, else 0."),
        bullet("File naming: <code>{basename}{log_suffix}_color_summary_{timestamp}.csv</code>"),
    ]

    story.append(h2("10.3  PPTX"))
    pptx_data = [
        ["Slide",        "Content"],
        ["1",            "Title slide with dataset name"],
        ["2 … N",        "Summary slides (8-condition bar chart)"],
        ["N+1 … end",    "Individual wafer slides (one PNG per slide, sorted A–Z)"],
    ]
    story.append(table(pptx_data, col_widths=[2*cm, 14.5*cm]))
    story += [
        sp(4),
        bullet("Template: Infineon Default Theme.pptx if found; python-pptx blank otherwise."),
        bullet("File naming: <code>{basename}{log_suffix}_{timestamp}.pptx</code>"),
        bullet("Requires: <code>py -m pip install python-pptx</code>"),
    ]
    story.append(pb())

    # ══════════════════════════════════════════════════════════════════════
    # 11. CONFIGURATION QUICK-REFERENCE
    # ══════════════════════════════════════════════════════════════════════
    story.append(h1("11. Configuration Quick Reference"))

    story.append(h2("11.1  PlotConfig Fields"))
    story.append(field_table([
        ["t_low",        "float", "—",     "Lower threshold (any finite float, scientific notation OK)"],
        ["t_high",       "float", "—",     "Upper threshold (must differ from t_low)"],
        ["use_log",      "bool",  "False", "Log10 scale applied to measurement values and grid"],
        ["high_is_green","bool",  "False", "True → high=green/low=red; False → high=red/low=green"],
        ["mirror_x",     "bool",  "False", "Horizontally flip the wafer map"],
        ["mirror_y",     "bool",  "False", "Vertically flip the wafer map"],
        ["rot_deg",      "int",   "0",     "Clockwise rotation in degrees: 0, 90, 180, or 270"],
    ]))

    story.append(h2("11.2  Constants (config.py)"))
    story.append(table([
        ["Constant",               "Value", "Where Used"],
        ["GRID_RESOLUTION",        "100",   "geometry.build_wafer_grid() — grid dimensions"],
        ["WAFER_RADIUS_FACTOR",    "1.05",  "geometry.build_wafer_grid() — radius expansion"],
        ["MIN_POINTS_FOR_PLOT",    "4",     "plotting.draw_wafer_ax() — skip threshold"],
        ["MAX_WAFERS_PER_PAGE",    "25",    "pdf_exporter — wafers per page"],
        ["LINES_PER_SUMMARY_PAGE", "55",    "pdf_exporter — text lines per summary page"],
    ], col_widths=[5*cm, 2*cm, 9.5*cm]))

    story.append(h2("11.3  Log File Location"))
    story.append(code("E:\\claude\\Wafer_tool_NEW2\\wafer_tool.log"))
    story += [
        p("Append-only. A new session separator is written each time <code>main.py</code> starts. "
          "To read it after a crash or error, open the file in any text editor or share it "
          "for remote diagnosis."),
    ]
    story.append(pb())

    # ══════════════════════════════════════════════════════════════════════
    # 12. BUILDING THE EXECUTABLE
    # ══════════════════════════════════════════════════════════════════════
    story.append(h1("12. Building the Executable (.exe)"))
    story += [
        p("The tool ships two PyInstaller build configurations. "
          "Both are Windows 64-bit and require no Python installation on the target machine. "
          "PyInstaller bundles the Python interpreter, all dependencies "
          "(PyQt6, Matplotlib, SciPy, NumPy, Pandas, ReportLab, python-pptx, pypdf), "
          "and all Matplotlib/SciPy data files into the output."),
    ]

    story.append(h2("12.1  Prerequisites"))
    story += [
        bullet("Python 3.11+ with all project dependencies installed "
               "(<code>py -m pip install -r requirements.txt</code>)."),
        bullet("PyInstaller 6.x: <code>py -m pip install pyinstaller</code>"),
        bullet("Run all build commands from the repository root "
               "(<code>E:\\claude\\Wafer_tool_NEW2\\</code>)."),
    ]

    story.append(h2("12.2  Option A — Standalone Single-File EXE"))
    story += [
        p("Everything packed into one <b>114 MB</b> <code>.exe</code>. "
          "Copy the single file to any Windows PC and double-click — no folder, no DLLs."),
        p("<b>Spec file:</b> <code>WaferMapTool.spec</code>"),
    ]
    story.append(code("py -m PyInstaller WaferMapTool.spec --noconfirm"))
    story += [
        p("<b>Output:</b>"),
    ]
    story.append(code("dist\\WaferMapTool.exe          (114 MB — single file)"))
    story += [
        p("<b>Trade-off:</b> On first launch the bootloader extracts all files to the OS "
          "temp directory (<code>%TEMP%\\_{MEI...}</code>). This adds ~3–8 seconds to the "
          "very first startup. Subsequent launches from the same temp extraction are faster. "
          "Antivirus software may flag single-file PyInstaller exes — add an exception if needed."),
    ]

    story.append(h2("12.3  Option B — Folder Distribution (small EXE + lib folder)"))
    story += [
        p("A <b>23 MB</b> launcher exe sits alongside a <code>_internal/</code> folder "
          "containing all DLLs and data files (~262 MB total). "
          "Faster startup than the single-file version (no extraction step)."),
        p("<b>Spec file:</b> <code>WaferMapTool_folder.spec</code>"),
    ]
    story.append(code("py -m PyInstaller WaferMapTool_folder.spec --noconfirm"))
    story += [
        p("<b>Output:</b>"),
    ]
    story.append(code("""\
dist\\WaferMapTool_folder\\
    WaferMapTool.exe        (23 MB — launcher)
    _internal\\              (239 MB — DLLs, data, Python runtime)
        PyQt6\\
        matplotlib\\
        scipy\\
        numpy\\
        pandas\\
        ... (all dependencies)"""))
    story += [
        p("<b>To distribute:</b> Zip the entire <code>WaferMapTool_folder\\</code> directory. "
          "The small exe will <b>not</b> run if separated from its <code>_internal\\</code> folder."),
    ]

    story.append(h2("12.4  Comparison"))
    story.append(table([
        ["Property",          "Standalone EXE",         "Folder Distribution"],
        ["File to share",     "1 file (114 MB)",        "1 folder (~262 MB zipped)"],
        ["EXE size",          "114 MB",                 "23 MB"],
        ["First launch",      "~5–10 s (extraction)",   "~2–3 s (direct load)"],
        ["Subsequent launch", "~2–3 s",                 "~2–3 s"],
        ["Antivirus risk",    "Moderate",               "Low"],
        ["Easy to update",    "Rebuild whole exe",      "Replace individual files"],
        ["Spec file",         "WaferMapTool.spec",      "WaferMapTool_folder.spec"],
        ["Build command",     "PyInstaller WaferMapTool.spec", "PyInstaller WaferMapTool_folder.spec"],
    ], col_widths=[4*cm, 5.5*cm, 7*cm]))

    story.append(h2("12.5  What Is Bundled"))
    story.append(table([
        ["Package",         "Version",  "Purpose in App"],
        ["Python",          "3.11",     "Runtime interpreter"],
        ["PyQt6",           "latest",   "GUI framework (widgets, signals, QThread)"],
        ["Matplotlib",      "latest",   "Wafer contour maps, PDF pages, histogram/scatter"],
        ["NumPy",           "latest",   "Float32 array maths"],
        ["SciPy",           "latest",   "griddata interpolation (Delaunay triangulation)"],
        ["Pandas",          "latest",   "DataFrame for wafer data (CSV parsing)"],
        ["pypdf",           "latest",   "PDF bookmark injection"],
        ["python-pptx",     "latest",   "PowerPoint report generation (optional)"],
        ["ReportLab",       "4.x",      "Documentation PDF generator"],
        ["PyInstaller",     "6.x",      "Build tool (not included in output)"],
    ], col_widths=[3*cm, 2.5*cm, 11*cm]))

    story.append(h2("12.6  Rebuild After Code Changes"))
    story += [
        p("After modifying any <code>.py</code> file, rebuild with the same command. "
          "PyInstaller detects changed files automatically:"),
    ]
    story.append(code("""\
cd E:\\claude\\Wafer_tool_NEW2

# Rebuild standalone (replaces dist\\WaferMapTool.exe)
py -m PyInstaller WaferMapTool.spec --noconfirm

# Rebuild folder version (replaces dist\\WaferMapTool_folder\\)
py -m PyInstaller WaferMapTool_folder.spec --noconfirm"""))
    story += [
        p("The <code>build\\</code> cache is reused between rebuilds to speed up the process. "
          "Delete <code>build\\</code> manually if you encounter stale-cache issues."),
    ]

    story.append(h2("12.7  Adding a Custom Icon"))
    story += [
        p("To set a custom taskbar/exe icon, supply a <code>.ico</code> file and uncomment "
          "the icon line in both spec files:"),
    ]
    story.append(code("""\
# In WaferMapTool.spec or WaferMapTool_folder.spec, inside EXE():
icon="wafer_tool.ico",    # path relative to repo root"""))
    story += [
        p("Convert a PNG to ICO online (e.g., convertio.co) or with Pillow:"),
    ]
    story.append(code("""\
from PIL import Image
img = Image.open("wafer_tool.png")
img.save("wafer_tool.ico", format="ICO",
         sizes=[(16,16),(32,32),(48,48),(256,256)])"""))

    return story


# ── Build ──────────────────────────────────────────────────────────────────
def build():
    doc = DocBuilder(OUT)
    story = content()
    doc.multiBuild(story)
    print(f"OK  Documentation written to: {OUT}")


if __name__ == "__main__":
    build()
