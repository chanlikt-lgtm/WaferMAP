"""
statistics.py
=============
Wafer-level colour-zone statistics and the 8-condition summary chart.

Public API
----------
calculate_8_condition_statistics(data, config) -> ConditionCounts
create_8_condition_summary_page(pdf, result, config, filepath,
                                display_page_counter, save_png_path) -> int
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Dict

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

from .config import PlotConfig, PAGE_PNG_DPI

__all__ = [
    "CONDITION_DISPLAY_ORDER",
    "ConditionCounts",
    "calculate_8_condition_statistics",
    "create_8_condition_summary_page",
]

# ---------------------------------------------------------------------------
# Display spec — order, human label, and bar colour for each 3-bit code (GYR)
# ---------------------------------------------------------------------------
CONDITION_DISPLAY_ORDER: list[tuple[str, str, str]] = [
    ("100", "Green only",           "#00CC00"),
    ("110", "Green + Yellow",       "#9ACD32"),
    ("010", "Yellow only",          "#FFD700"),
    ("111", "Green + Yellow + Red", "#A9A9A9"),
    ("101", "Green + Red",          "#B8860B"),
    ("011", "Yellow + Red",         "#FF8C00"),
    ("001", "Red only",             "#CC0000"),
    ("000", "No colour",            "#D3D3D3"),
]


# ---------------------------------------------------------------------------
# Data container
# ---------------------------------------------------------------------------
@dataclass
class ConditionCounts:
    """Per-code wafer counts and total."""
    counts: Dict[str, int] = field(
        default_factory=lambda: {code: 0 for code, *_ in CONDITION_DISPLAY_ORDER}
    )
    total_wafers: int = 0


# ---------------------------------------------------------------------------
# Classification
# ---------------------------------------------------------------------------
def calculate_8_condition_statistics(
    data: pd.DataFrame,
    config: PlotConfig,
) -> ConditionCounts:
    """
    Classify every wafer into one of 8 green / yellow / red presence codes.

    The 3-bit binary code is **GYR** (Green, Yellow, Red):
        bit 2 (G) = wafer has at least one die in the green zone
        bit 1 (Y) = wafer has at least one die in the yellow zone
        bit 0 (R) = wafer has at least one die in the red zone

    Which zone maps to which colour depends on *config.high_is_green*:
        high_is_green=True  → high values → green, low values → red
        high_is_green=False → low values  → green, high values → red

    Wafers with fewer than 4 die points are skipped.
    """
    result = ConditionCounts()

    for (_lot, _wid), w_df in data.groupby(["lot", "wafer"]):
        # copy=False avoids a per-wafer allocation when the underlying
        # float32 array is already contiguous (the common case).
        z = w_df["value"].to_numpy(dtype=float, copy=False)
        if len(z) < 4:
            continue

        result.total_wafers += 1

        has_low  = bool(np.any(z  < config.t_low))
        has_mid  = bool(np.any((z >= config.t_low) & (z <= config.t_high)))
        has_high = bool(np.any(z  > config.t_high))

        if config.high_is_green:
            g, y, r = has_high, has_mid, has_low
        else:
            g, y, r = has_low,  has_mid, has_high

        code = f"{int(g)}{int(y)}{int(r)}"
        result.counts[code] = result.counts.get(code, 0) + 1

    return result


# ---------------------------------------------------------------------------
# Summary bar-chart page
# ---------------------------------------------------------------------------
def create_8_condition_summary_page(
    pdf,
    result: ConditionCounts,
    config: PlotConfig,
    filepath: str,
    display_page_counter: int,
    save_png_path: str | None = None,
) -> int:
    """
    Render the 8-condition distribution bar chart to *pdf* (and optionally PNG).

    Parameters
    ----------
    pdf                  : Active PdfPages context.
    result               : Pre-computed ConditionCounts.
    config               : PlotConfig (used for log-suffix in title).
    filepath             : Original data file path (for header text).
    display_page_counter : Current human-readable page number.
    save_png_path        : If given, also save the figure as a PNG at this path.

    Returns
    -------
    int : display_page_counter + 1
    """
    title_suffix = " (LOG)" if config.use_log else ""
    base_name    = os.path.basename(filepath)
    total        = result.total_wafers

    fig = plt.figure(figsize=(11.69, 8.27))
    fig.suptitle(
        f"Wafer Condition Distribution — 8 Possible Outcomes{title_suffix}",
        fontsize=20, fontweight="bold", y=0.95,
    )
    fig.text(0.5,  0.90, f"File: {base_name}",           fontsize=12, ha="center")
    fig.text(0.98, 0.02, f"Page {display_page_counter}",
             fontsize=11, fontweight="bold", ha="right", va="bottom")

    ax = fig.add_axes([0.15, 0.20, 0.70, 0.65])

    labels, values, colors = [], [], []
    for code, label, color in CONDITION_DISPLAY_ORDER:
        labels.append(label)
        values.append(result.counts.get(code, 0))
        colors.append(color)

    bars  = ax.bar(labels, values, color=colors, edgecolor="black", zorder=3)
    y_max = max(values) if values else 1
    ax.grid(axis="y", linestyle="--", alpha=0.7, zorder=0)

    for bar, count in zip(bars, values):
        pct = (count / total * 100) if total > 0 else 0.0
        ax.text(
            bar.get_x() + bar.get_width() / 2.0,
            bar.get_height() + y_max * 0.02,
            f"{count}\n({pct:.1f}%)",
            ha="center", va="bottom", fontsize=10, fontweight="bold",
        )

    ax.set_ylabel("Number of Wafers", fontsize=12, fontweight="bold")
    ax.set_title("Wafer Count by Colour Combination", fontsize=14, pad=10)
    plt.xticks(rotation=45, ha="right", fontsize=12)
    ax.text(
        0.98, 0.95, f"Total Wafers: {total}",
        transform=ax.transAxes, ha="right", va="top",
        fontsize=12, fontweight="bold",
        bbox=dict(facecolor="white", alpha=0.8, edgecolor="black"),
    )

    if save_png_path:
        fig.savefig(save_png_path, bbox_inches="tight", dpi=PAGE_PNG_DPI)

    pdf.savefig(fig)
    plt.close(fig)
    return display_page_counter + 1