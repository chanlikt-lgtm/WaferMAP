"""
ui/threshold_viz_widget.py
==========================
PyQt6 widget that renders a real-time threshold visualisation:
    - Colour bands (green / yellow / red) marking the three zones.
    - Dashed threshold lines with value labels.
    - Optional scatter of actual measurement values for context.

The widget has no knowledge of the main window's other controls — it
simply exposes a `refresh()` method that accepts parsed threshold values.

Public API
----------
ThresholdVizWidget(parent=None)
    .set_data(values)        — cache 1-D measurement array for scatter overlay
    .refresh(t1, t2, ...)    — redraw the visualisation
"""
from __future__ import annotations

import numpy as np
from matplotlib.figure import Figure
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas

from PyQt6.QtWidgets import QWidget, QVBoxLayout

from ..config import COLOR_GREEN, COLOR_YELLOW, COLOR_RED
from ..geometry import signed_log10

__all__ = ["ThresholdVizWidget"]

MAX_SCATTER_POINTS = 3_000


class ThresholdVizWidget(QWidget):
    """Live threshold-band chart with optional measurement scatter."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._data_values: np.ndarray | None = None

        self._fig    = Figure(figsize=(4, 6), dpi=100)
        self._ax     = self._fig.add_subplot(111)
        self._canvas = FigureCanvas(self._fig)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._canvas)

    # ── Public API ────────────────────────────────────────────────────────

    def set_data(self, values: np.ndarray | None) -> None:
        """Cache measurement values used for the scatter overlay."""
        self._data_values = values

    def refresh(
        self,
        t1: float | None,
        t2: float | None,
        high_is_green: bool,
        use_log: bool,
    ) -> None:
        """
        Redraw the threshold visualisation.

        Parameters
        ----------
        t1, t2        : Threshold values (order does not matter; auto-sorted).
                        Pass None for either to show a placeholder message.
        high_is_green : Colour zone assignment.
        use_log       : Display Y-axis in log scale.
        """
        ax = self._ax
        ax.clear()

        if t1 is None or t2 is None:
            ax.text(0.5, 0.5, "Awaiting threshold input…",
                    ha="center", va="center", color="gray",
                    transform=ax.transAxes)
            ax.axis("off")
            self._canvas.draw()
            return

        t_low,  t_high  = min(t1, t2), max(t1, t2)
        low_c, mid_c, high_c = _zone_colors(high_is_green)

        # Compute Y-axis extents
        if use_log:
            tl, th   = signed_log10(t_low), signed_log10(t_high)
            span     = th - tl
            margin   = span * 0.3 if span > 0 else 1.0
            y_min, y_max = tl - margin, th + margin
            thresh_low, thresh_high = tl, th
            y_label = "Value (Log₁₀ Scale)"
        else:
            span   = t_high - t_low
            margin = span * 0.3 if span > 0 else max(abs(t_low), abs(t_high)) * 0.3 or 1.0
            y_min, y_max = t_low - margin, t_high + margin
            thresh_low, thresh_high = t_low, t_high
            y_label = "Value"

        # Colour bands
        ax.axhspan(y_min,        thresh_low,  alpha=0.45, color=low_c,  zorder=1)
        ax.axhspan(thresh_low,   thresh_high, alpha=0.45, color=mid_c,  zorder=1)
        ax.axhspan(thresh_high,  y_max,       alpha=0.45, color=high_c, zorder=1)

        # Threshold lines
        ax.axhline(thresh_low,  color="black", linewidth=2, linestyle="--", zorder=2)
        ax.axhline(thresh_high, color="black", linewidth=2, linestyle="--", zorder=2)

        # Scatter overlay
        self._draw_scatter(ax, use_log)

        # Threshold labels
        label_style = dict(boxstyle="round", facecolor="white", alpha=0.85)
        ax.text(0.5, thresh_high, f"Limit = {t_high:.2e}",
                va="bottom", ha="center", fontsize=11, fontweight="bold",
                bbox=label_style, zorder=3)
        ax.text(0.5, thresh_low,  f"Limit = {t_low:.2e}",
                va="bottom", ha="center", fontsize=11, fontweight="bold",
                bbox=label_style, zorder=3)

        ax.set_ylim(y_min, y_max)
        ax.set_xlim(0, 1)
        ax.set_ylabel(y_label, fontsize=12, fontweight="bold")
        ax.set_xticks([])
        self._canvas.draw()

    # ── Private ───────────────────────────────────────────────────────────

    def _draw_scatter(self, ax, use_log: bool) -> None:
        vals = self._data_values
        if vals is None or len(vals) == 0:
            return

        if len(vals) > MAX_SCATTER_POINTS:
            rng  = np.random.default_rng(42)
            vals = rng.choice(vals, MAX_SCATTER_POINTS, replace=False)

        y   = signed_log10(vals) if use_log else vals
        rng = np.random.default_rng(123)
        x   = rng.uniform(0.1, 0.9, size=len(vals))
        ax.scatter(x, y, color="black", s=4, alpha=0.5, edgecolors="none", zorder=4)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _zone_colors(high_is_green: bool) -> tuple[str, str, str]:
    """Return (low_color, mid_color, high_color) based on polarity."""
    if high_is_green:
        return COLOR_RED, COLOR_YELLOW, COLOR_GREEN
    return COLOR_GREEN, COLOR_YELLOW, COLOR_RED
