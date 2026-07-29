"""
exporters/pdf_exporter.py
=========================
Generates the multi-page PDF report with bookmarks.

Structure
---------
1. Summary text page(s)   — lot/wafer counts, file metadata
2. 8-condition bar chart  — overview of colour distribution
3. Per-lot wafer pages    — 5×5 grid layout, one page per 25 wafers

The per-lot grid pages are the expensive part (one interpolated wafer map per
die group). They are independent, so they can be rendered in parallel across
processes: each worker writes a single-page **vector** PDF, and the main process
merges them with pypdf — so parallelism costs no quality. Falls back to
sequential rendering if a process pool can't be created.

Public API
----------
generate_pdf(data, config, condition_result, filepath,
             out_dir, timestamp, page_png_dir=None, jobs=None, on_page=None) -> str
"""
from __future__ import annotations

import os
import shutil
from datetime import datetime

import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.patches import Patch
from pypdf import PdfReader, PdfWriter

from ..config import PlotConfig, MAX_WAFERS_PER_PAGE, LINES_PER_SUMMARY_PAGE, PAGE_PNG_DPI
from ..plotting import draw_wafer_ax
from .report_charts import draw_scatter, draw_histogram, wafer_codes_and_names
from ..statistics import ConditionCounts, create_8_condition_summary_page

__all__ = ["generate_pdf"]

# Minimum grid-page count before parallel rendering is worth the Windows
# process-pool spawn overhead (~7 s). See _render_all_grid_pages.
_PDF_PARALLEL_MIN_PAGES = 8


# ---------------------------------------------------------------------------
# Worker: render ONE 5×5 grid page to a single-page vector PDF (+ optional PNG).
# Must stay top-level and picklable so it can run in a spawned process.
# ---------------------------------------------------------------------------
def _render_grid_page(job: tuple) -> int:
    (grid_seq, page_pdf_path, page_png_path, lot_id, base_name,
     display_counter, config, wafer_ids, page_df) = job

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as _plt
    from matplotlib.backends.backend_pdf import PdfPages as _PdfPages

    groups = {str(w): sub for w, sub in page_df.groupby("wafer")}
    fig, axes = _plt.subplots(5, 5, figsize=(11.69, 8.27))
    _plt.subplots_adjust(top=0.85, bottom=0.05, left=0.05, right=0.78,
                         hspace=0.4, wspace=0.3)
    _add_page_header(fig, lot_id, base_name, display_counter, config)
    _add_page_legend(fig, config)
    try:
        for j, ax in enumerate(axes.flat):
            if j < len(wafer_ids):
                draw_wafer_ax(ax, groups[wafer_ids[j]], wafer_ids[j], config,
                              show_legend=False, show_title=True)
            else:
                ax.axis("off")
        with _PdfPages(page_pdf_path) as pp:
            pp.savefig(fig)
        if page_png_path:
            fig.savefig(page_png_path, bbox_inches="tight", dpi=PAGE_PNG_DPI)
    finally:
        _plt.close(fig)
    return grid_seq


def generate_pdf(
    data,
    config: PlotConfig,
    condition_result: ConditionCounts,
    filepath: str,
    out_dir: str,
    timestamp: str,
    page_png_dir: str | None = None,
    jobs: int | None = None,
    on_page=None,
) -> str:
    """
    Build the complete PDF report.

    jobs : None → auto (min(cpu_count, 8)); 1 → sequential; N → N worker
           processes. Parallelism only kicks in for reports with a few grid
           pages (spawn overhead isn't worth it for tiny reports).
    on_page : optional callback(done, total) fired as grid pages complete.
    """
    base_name = os.path.splitext(os.path.basename(filepath))[0]
    final_pdf = os.path.join(out_dir, f"{base_name}{config.log_suffix}_{timestamp}.pdf")
    tmp_dir   = os.path.join(out_dir, f"_pdf_pages_{timestamp}")
    os.makedirs(tmp_dir, exist_ok=True)
    head_pdf  = os.path.join(tmp_dir, "head.pdf")

    lot_groups = data.groupby("lot")
    bookmarks: list[tuple[str, int]] = []

    # ── HEAD: summary text + 8-condition chart (main process; cheap) ────────
    with PdfPages(head_pdf) as pdf:
        bookmarks.append(("Summary Report", 0))
        display_counter, pdf_page_idx = _write_summary_text(
            pdf, lot_groups, filepath, config, 1, 0, page_png_dir=page_png_dir,
        )
        bookmarks.append(("8-Condition Distribution", pdf_page_idx))
        display_counter = create_8_condition_summary_page(
            pdf, condition_result, config, filepath, display_counter,
            save_png_path=_page_png_path(
                page_png_dir, display_counter, "8_condition_distribution"),
        )
        # Overview charts on the front pages (same as the GUI Scatter/Histogram
        # tabs). pdf_page_idx counts summary pages; the 8-condition page added
        # one, so these land right after it.
        bookmarks.append(("Threshold Scatter", pdf_page_idx + 1))
        display_counter = _add_scatter_page(
            pdf, data, config, base_name, display_counter, page_png_dir)
        bookmarks.append(("Value Histogram", pdf_page_idx + 2))
        display_counter = _add_histogram_page(
            pdf, data, config, base_name, display_counter, page_png_dir)
    n_head = len(PdfReader(head_pdf).pages)

    # ── Build the per-lot grid-page jobs ────────────────────────────────────
    grid_jobs: list[tuple] = []
    grid_seq = 0
    dc = display_counter
    for lot_id, lot_df in lot_groups:
        wafer_ids = [str(w) for w in sorted(lot_df["wafer"].astype(str).unique())]
        for batch_start in range(0, len(wafer_ids), MAX_WAFERS_PER_PAGE):
            batch = wafer_ids[batch_start: batch_start + MAX_WAFERS_PER_PAGE]
            if batch_start == 0:
                bookmarks.append((f"Lot: {lot_id}{config.log_suffix}", n_head + grid_seq))
            # Slice this page's data; drop the category dtype so the pickle sent
            # to a worker doesn't drag the whole (50k-wide) categorical index.
            mask = lot_df["wafer"].astype(str).isin(batch)
            sub = lot_df.loc[mask, ["wafer", "x", "y", "value"]].copy()
            sub["wafer"] = sub["wafer"].astype(str)
            png_path = _page_png_path(
                page_png_dir, dc,
                f"lot_{lot_id}_page_{batch_start // MAX_WAFERS_PER_PAGE + 1}")
            grid_jobs.append((
                grid_seq, os.path.join(tmp_dir, f"page_{grid_seq:04d}.pdf"),
                png_path, str(lot_id), base_name, dc, config, batch, sub,
            ))
            grid_seq += 1
            dc += 1

    # ── Render grid pages (parallel when it pays off, else sequential) ──────
    _render_all_grid_pages(grid_jobs, jobs, on_page)

    # ── Merge head + grid pages in order, attach bookmarks ──────────────────
    writer = PdfWriter()
    for page in PdfReader(head_pdf).pages:
        writer.add_page(page)
    for gs in range(len(grid_jobs)):
        page_pdf = os.path.join(tmp_dir, f"page_{gs:04d}.pdf")
        for page in PdfReader(page_pdf).pages:
            writer.add_page(page)
    for title, page_num in bookmarks:
        writer.add_outline_item(title=title, page_number=page_num)
    with open(final_pdf, "wb") as fh:
        writer.write(fh)

    shutil.rmtree(tmp_dir, ignore_errors=True)
    return final_pdf


def _render_all_grid_pages(grid_jobs, jobs, on_page) -> None:
    """Render every grid-page job to its temp PDF, in parallel if worthwhile."""
    total = len(grid_jobs)
    if total == 0:
        return

    want = (jobs is None or jobs > 1)
    n_workers = (jobs if (jobs and jobs > 1) else (os.cpu_count() or 1))
    n_workers = max(1, min(n_workers, 8, total))

    # Each grid page renders 25 wafers (~1.25 s). Windows process-pool spawn
    # costs ~7 s of fixed overhead (matplotlib re-import per worker), so parallel
    # only pays off past ~8 pages (~200 wafers); below that, sequential is faster.
    if want and n_workers > 1 and total >= _PDF_PARALLEL_MIN_PAGES:
        try:
            from concurrent.futures import ProcessPoolExecutor
            with ProcessPoolExecutor(max_workers=n_workers) as ex:
                for done, _ in enumerate(ex.map(_render_grid_page, grid_jobs), 1):
                    if on_page:
                        on_page(done, total)
            return
        except Exception as exc:  # pool unavailable / worker crash → sequential
            print(f"⚠  Parallel PDF render failed ({exc}); using sequential.")

    for done, job in enumerate(grid_jobs, 1):
        _render_grid_page(job)
        if on_page:
            on_page(done, total)


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _write_summary_text(
    pdf, lot_groups, filepath: str, config: PlotConfig,
    display_counter: int, pdf_page_idx: int,
    page_png_dir: str | None = None,
) -> tuple[int, int]:
    """Write one or more text-only summary pages to *pdf*."""
    header = (
        "MASTER WAFER REPORT\n"
        f"File: {filepath}\n"
        f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        f"Scale Mode: {'Log Scale' if config.use_log else 'Linear Scale'}\n\n"
    )
    lot_block = f"{'Lot ID':<20} | {'Wafers':<10}\n" + "-" * 35 + "\n"
    for lot_id, lot_df in lot_groups:
        lot_block += f"{str(lot_id):<20} | {lot_df['wafer'].nunique():<10}\n"

    all_lines = (header + lot_block).split("\n")

    for page_start in range(0, len(all_lines), LINES_PER_SUMMARY_PAGE):
        chunk = "\n".join(all_lines[page_start: page_start + LINES_PER_SUMMARY_PAGE])
        fig, ax = plt.subplots(figsize=(8.27, 11.69))
        ax.axis("off")
        ax.text(0.05, 0.95, chunk, family="monospace", fontsize=9, va="top")
        fig.text(0.98, 0.02, f"Page {display_counter}",
                 fontsize=11, fontweight="bold", ha="right", va="bottom")
        pdf.savefig(fig)
        page_png_path = _page_png_path(
            page_png_dir, display_counter, f"summary_report_page_{display_counter}"
        )
        if page_png_path:
            fig.savefig(page_png_path, bbox_inches="tight", dpi=PAGE_PNG_DPI)
        plt.close(fig)
        display_counter += 1
        pdf_page_idx    += 1

    return display_counter, pdf_page_idx


def _add_scatter_page(pdf, data, config: PlotConfig, base_name: str,
                      display_counter: int, page_png_dir: str | None) -> int:
    """Write the overview Threshold Scatter as one landscape PDF page (+ PNG)."""
    z = data["value"].to_numpy(dtype="float32", copy=False)
    codes, names = wafer_codes_and_names(data)
    fig, ax = plt.subplots(figsize=(11.69, 8.27))
    try:
        draw_scatter(ax, z, config, wafer_codes=codes, wafer_names=names,
                     title=f"Threshold Scatter — {base_name}")
        fig.text(0.98, 0.02, f"Page {display_counter}", fontsize=11,
                 fontweight="bold", ha="right", va="bottom")
        fig.tight_layout()
        pdf.savefig(fig)
        png = _page_png_path(page_png_dir, display_counter, "threshold_scatter")
        if png:
            fig.savefig(png, bbox_inches="tight", dpi=PAGE_PNG_DPI)
    finally:
        plt.close(fig)
    return display_counter + 1


def _add_histogram_page(pdf, data, config: PlotConfig, base_name: str,
                        display_counter: int, page_png_dir: str | None) -> int:
    """Write the overview value Histogram as one landscape PDF page (+ PNG)."""
    z = data["value"].to_numpy(dtype="float32", copy=False)
    fig, ax = plt.subplots(figsize=(11.69, 8.27))
    try:
        draw_histogram(ax, z, config, title=f"Value Histogram — {base_name}")
        fig.text(0.98, 0.02, f"Page {display_counter}", fontsize=11,
                 fontweight="bold", ha="right", va="bottom")
        fig.tight_layout()
        pdf.savefig(fig)
        png = _page_png_path(page_png_dir, display_counter, "value_histogram")
        if png:
            fig.savefig(png, bbox_inches="tight", dpi=PAGE_PNG_DPI)
    finally:
        plt.close(fig)
    return display_counter + 1


def _add_page_header(fig, lot_id: str, base_name: str,
                     display_counter: int, config: PlotConfig) -> None:
    fig.text(0.05, 0.96, f"Lot ID: {lot_id}{config.log_suffix}",
             fontsize=18, fontweight="bold", ha="left", va="top")
    fig.text(0.98, 0.96, f"File: {base_name}\nPage {display_counter}",
             fontsize=11, fontweight="bold", ha="right", va="top", linespacing=1.5)


def _add_page_legend(fig, config: PlotConfig) -> None:
    cs = config.color_scheme
    handles = [
        Patch(facecolor=cs.low,  edgecolor="black", label=f"< {config.t_low:g}"),
        Patch(facecolor=cs.mid,  edgecolor="black",
              label=f"{config.t_low:g} – {config.t_high:g}"),
        Patch(facecolor=cs.high, edgecolor="black", label=f"≥ {config.t_high:g}"),
    ]
    fig.legend(
        handles=handles, loc="upper right",
        bbox_to_anchor=(0.98, 0.75), title="Thresholds",
        fontsize=9, frameon=True, edgecolor="black", shadow=True,
    )


def _page_png_path(
    page_png_dir: str | None,
    page_number: int,
    label: str,
) -> str | None:
    if not page_png_dir:
        return None

    safe_label = "".join(ch if ch.isalnum() else "_" for ch in str(label)).strip("_")
    if not safe_label:
        safe_label = "page"
    return os.path.join(page_png_dir, f"{page_number:03d}_{safe_label}.png")
