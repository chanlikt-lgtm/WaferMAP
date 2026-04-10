"""
exporters/pdf_exporter.py
=========================
Generates the multi-page PDF report with bookmarks.

Structure
---------
1. Summary text page(s)   — lot/wafer counts, file metadata
2. 8-condition bar chart  — overview of colour distribution
3. Per-lot wafer pages    — 5×5 grid layout, one page per 25 wafers

Bookmarks are injected via pypdf after the temp PDF is written.

Public API
----------
generate_pdf(data, config, condition_result, filepath,
             out_dir, timestamp, summary_8_png) -> str
"""
from __future__ import annotations

import os
from datetime import datetime

import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.patches import Patch
from pypdf import PdfReader, PdfWriter

from ..config import PlotConfig, MAX_WAFERS_PER_PAGE, LINES_PER_SUMMARY_PAGE
from ..plotting import draw_wafer_ax
from ..statistics import ConditionCounts, create_8_condition_summary_page

__all__ = ["generate_pdf"]


def generate_pdf(
    data,
    config: PlotConfig,
    condition_result: ConditionCounts,
    filepath: str,
    out_dir: str,
    timestamp: str,
    summary_8_png: str | None = None,
) -> str:
    """
    Build the complete PDF report.

    Parameters
    ----------
    data             : Full wafer DataFrame (lot, wafer, x, y, value).
    config           : PlotConfig with all user settings.
    condition_result : Pre-computed 8-condition statistics.
    filepath         : Original input file (used for naming and metadata).
    out_dir          : Output directory.
    timestamp        : Timestamp string used in the file name.
    summary_8_png    : Optional path to also save the bar-chart page as PNG.

    Returns
    -------
    str : Absolute path to the final PDF.
    """
    base_name = os.path.splitext(os.path.basename(filepath))[0]
    temp_pdf  = os.path.join(out_dir, f"temp_{base_name}{config.log_suffix}_{timestamp}.pdf")
    final_pdf = os.path.join(out_dir, f"{base_name}{config.log_suffix}_{timestamp}.pdf")

    bookmarks:       list[tuple[str, int]] = []
    pdf_page_idx:    int = 0
    display_counter: int = 1

    lot_groups = data.groupby("lot")

    with PdfPages(temp_pdf) as pdf:

        # ── 1. Summary text ───────────────────────────────────────────────
        bookmarks.append(("Summary Report", pdf_page_idx))
        display_counter, pdf_page_idx = _write_summary_text(
            pdf, lot_groups, filepath, config, display_counter, pdf_page_idx
        )

        # ── 2. 8-condition chart ──────────────────────────────────────────
        bookmarks.append(("8-Condition Distribution", pdf_page_idx))
        display_counter = create_8_condition_summary_page(
            pdf, condition_result, config, filepath, display_counter,
            save_png_path=summary_8_png,
        )
        pdf_page_idx = display_counter - 1

        # ── 3. Per-lot wafer grid pages ───────────────────────────────────
        for lot_id, lot_df in lot_groups:
            bookmarks.append((f"Lot: {lot_id}{config.log_suffix}", pdf_page_idx))
            wafer_ids    = sorted(lot_df["wafer"].unique())
            wafer_groups = lot_df.groupby("wafer")

            for batch_start in range(0, len(wafer_ids), MAX_WAFERS_PER_PAGE):
                batch = wafer_ids[batch_start: batch_start + MAX_WAFERS_PER_PAGE]
                fig, axes = plt.subplots(5, 5, figsize=(11.69, 8.27))
                plt.subplots_adjust(
                    top=0.85, bottom=0.05, left=0.05, right=0.78,
                    hspace=0.4, wspace=0.3,
                )

                _add_page_header(fig, lot_id, base_name, display_counter, config)
                _add_page_legend(fig, config)

                for j, ax in enumerate(axes.flat):
                    abs_idx = batch_start + j
                    if abs_idx < len(wafer_ids):
                        draw_wafer_ax(
                            ax, wafer_groups.get_group(wafer_ids[abs_idx]),
                            wafer_ids[abs_idx], config,
                            show_legend=False, show_title=True,
                        )
                    else:
                        ax.axis("off")

                pdf.savefig(fig)
                plt.close(fig)
                display_counter += 1
                pdf_page_idx    += 1

    _attach_bookmarks(temp_pdf, final_pdf, bookmarks)
    return final_pdf


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _write_summary_text(
    pdf, lot_groups, filepath: str, config: PlotConfig,
    display_counter: int, pdf_page_idx: int,
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
        plt.close(fig)
        display_counter += 1
        pdf_page_idx    += 1

    return display_counter, pdf_page_idx


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


def _attach_bookmarks(
    temp_path: str,
    final_path: str,
    bookmarks: list[tuple[str, int]],
) -> None:
    """Copy pages from *temp_path* into *final_path*, adding PDF bookmarks."""
    reader = PdfReader(temp_path)
    writer = PdfWriter()
    for page in reader.pages:
        writer.add_page(page)
    for title, page_num in bookmarks:
        writer.add_outline_item(title=title, page_number=page_num)
    with open(final_path, "wb") as fh:
        writer.write(fh)
    if os.path.exists(temp_path):
        os.remove(temp_path)
