"""
ui/histogram_widget.py
======================
Interactive histogram widget for loaded wafer measurement values.

Features
--------
- Auto-bins using Freedman-Diaconis rule (falls back to Sturges).
- Colour-coded bars: green / yellow / red zones match the PlotConfig thresholds.
- Stats panel: N, Min, Max, Mean, Median, Std displayed above the chart.
- Threshold lines drawn as vertical dashed lines with labels.
- Log-X axis toggle button (works even for data spanning many decades).
- Graceful placeholder when no data is loaded.

Public API
----------
HistogramWidget(parent=None)
    .set_data(values, t_low, t_high, high_is_green) — load / update data
    .refresh()                                        — redraw (called internally)
"""
from __future__ import annotations

import numpy as np
from matplotlib.figure import Figure
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.ticker import LogFormatterSciNotation, AutoLocator
import matplotlib.ticker as mticker

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QFrame,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont

from ..config import COLOR_GREEN, COLOR_YELLOW, COLOR_RED

__all__ = ["HistogramWidget"]

_PLACEHOLDER = "Load a data file to see the histogram."
_BIN_MAX     = 120   # hard cap on auto-bin count


class HistogramWidget(QWidget):
    """Histogram of all measurement values with stats, threshold lines, log toggle."""

    def __init__(self, parent=None):
        super().__init__(parent)

        self._values:       np.ndarray | None = None
        self._t_low:        float | None       = None
        self._t_high:       float | None       = None
        self._high_is_green: bool              = False
        self._log_x:        bool               = False

        self._build_ui()
        self._draw_placeholder()

    # ── Public API ────────────────────────────────────────────────────────

    def set_data(
        self,
        values:       np.ndarray | None,
        t_low:        float | None = None,
        t_high:       float | None = None,
        high_is_green: bool        = False,
    ) -> None:
        """Load new data and trigger a redraw."""
        self._values        = values
        self._t_low         = t_low
        self._t_high        = t_high
        self._high_is_green = high_is_green
        self.refresh()

    def update_thresholds(
        self,
        t_low:        float | None,
        t_high:       float | None,
        high_is_green: bool = False,
    ) -> None:
        """Update only the threshold lines without reloading data."""
        self._t_low         = t_low
        self._t_high        = t_high
        self._high_is_green = high_is_green
        self.refresh()

    def refresh(self) -> None:
        if self._values is None or len(self._values) == 0:
            self._draw_placeholder()
        else:
            self._draw_histogram()

    # ── UI construction ───────────────────────────────────────────────────

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(4, 4, 4, 4)
        root.setSpacing(4)

        # ── Stats bar ────────────────────────────────────────────────────
        self._stats_frame = QFrame()
        self._stats_frame.setFrameShape(QFrame.Shape.StyledPanel)
        self._stats_frame.setStyleSheet(
            "QFrame { background:#f5f5f5; border:1px solid #ccc; border-radius:4px; }"
        )
        stats_lay = QHBoxLayout(self._stats_frame)
        stats_lay.setContentsMargins(8, 4, 8, 4)
        stats_lay.setSpacing(20)

        self._stat_labels: dict[str, QLabel] = {}
        for key in ("N", "Min", "Max", "Mean", "Median", "Std"):
            col = QVBoxLayout()
            col.setSpacing(0)

            key_lbl = QLabel(key)
            key_font = QFont()
            key_font.setPointSize(8)
            key_font.setBold(True)
            key_lbl.setFont(key_font)
            key_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            key_lbl.setStyleSheet("color:#555;")

            val_lbl = QLabel("—")
            val_font = QFont()
            val_font.setPointSize(9)
            val_lbl.setFont(val_font)
            val_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            val_lbl.setStyleSheet("color:#111;")

            col.addWidget(key_lbl)
            col.addWidget(val_lbl)
            self._stat_labels[key] = val_lbl
            stats_lay.addLayout(col)

        root.addWidget(self._stats_frame)

        # ── Matplotlib canvas ─────────────────────────────────────────────
        self._fig    = Figure(figsize=(5, 4), dpi=100)
        self._ax     = self._fig.add_subplot(111)
        self._canvas = FigureCanvas(self._fig)
        self._fig.subplots_adjust(left=0.13, right=0.97, top=0.88, bottom=0.15)
        root.addWidget(self._canvas, stretch=1)

        # ── Log-X toggle button ───────────────────────────────────────────
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        self._btn_log = QPushButton("Toggle Log X-axis  (OFF)")
        self._btn_log.setCheckable(True)
        self._btn_log.setChecked(False)
        self._btn_log.setFixedWidth(220)
        self._btn_log.setStyleSheet(
            "QPushButton { padding:4px 10px; border:1px solid #888; border-radius:4px; }"
            "QPushButton:checked { background:#3a7bd5; color:white; font-weight:bold; }"
        )
        self._btn_log.toggled.connect(self._on_log_toggle)
        btn_row.addWidget(self._btn_log)
        btn_row.addStretch()
        root.addLayout(btn_row)

    # ── Slots ─────────────────────────────────────────────────────────────

    def _on_log_toggle(self, checked: bool) -> None:
        self._log_x = checked
        self._btn_log.setText(
            f"Toggle Log X-axis  ({'ON' if checked else 'OFF'})"
        )
        self.refresh()

    # ── Drawing ───────────────────────────────────────────────────────────

    def _draw_placeholder(self) -> None:
        ax = self._ax
        ax.clear()
        ax.text(
            0.5, 0.5, _PLACEHOLDER,
            ha="center", va="center", fontsize=11, color="#888",
            transform=ax.transAxes,
        )
        ax.axis("off")
        self._canvas.draw()
        self._reset_stats()

    def _draw_histogram(self) -> None:
        ax   = self._ax
        ax.clear()

        # ── Work in log space if requested ───────────────────────────────
        if self._log_x:
            pos = self._values[self._values > 0]   # filtered view, no full copy
            if len(pos) < 2:
                ax.text(0.5, 0.5,
                        "Log X requires positive values.\nSwitch to linear.",
                        ha="center", va="center", fontsize=10, color="#c00",
                        transform=ax.transAxes)
                ax.axis("off")
                self._canvas.draw()
                return
            plot_vals   = np.log10(pos)            # new array from filtered view
            t_low_plot  = np.log10(max(self._t_low,  1e-30)) if self._t_low  else None
            t_high_plot = np.log10(max(self._t_high, 1e-30)) if self._t_high else None
        else:
            plot_vals   = self._values             # read-only view — no copy needed
            t_low_plot  = self._t_low
            t_high_plot = self._t_high

        # ── Auto-bin count ────────────────────────────────────────────────
        n_bins = _fd_bins(plot_vals)

        # ── Build colour-coded bars ───────────────────────────────────────
        bin_edges = np.linspace(plot_vals.min(), plot_vals.max(), n_bins + 1)
        _draw_colored_bars(
            ax, plot_vals, bin_edges,
            t_low_plot, t_high_plot, self._high_is_green,
        )

        # ── Threshold vertical lines ──────────────────────────────────────
        cs = _zone_colors(self._high_is_green)
        for t_val, raw_val, color, va in [
            (t_low_plot,  self._t_low,  cs[0], "top"),
            (t_high_plot, self._t_high, cs[2], "bottom"),
        ]:
            if t_val is not None:
                ax.axvline(t_val, color="black", linewidth=1.8,
                           linestyle="--", zorder=5)
                label = f"{raw_val:.3e}"
                ylim  = ax.get_ylim()
                y_pos = ylim[1] * 0.97 if va == "top" else ylim[1] * 0.60
                ax.text(
                    t_val, y_pos, label,
                    rotation=90, va=va, ha="right",
                    fontsize=9, fontweight="bold", color="black",
                    bbox=dict(boxstyle="round,pad=0.2",
                              facecolor="white", alpha=0.8, edgecolor="gray"),
                    zorder=6,
                )

        # ── X-axis labels & formatting ────────────────────────────────────
        if self._log_x:
            _format_log_xaxis(ax)
            ax.set_xlabel("Measurement Value  (log₁₀ scale)", fontsize=11,
                          fontweight="bold", labelpad=6)
        else:
            ax.xaxis.set_major_locator(AutoLocator())
            ax.xaxis.set_major_formatter(
                mticker.FuncFormatter(lambda v, _: f"{v:.3g}")
            )
            ax.set_xlabel("Measurement Value", fontsize=11,
                          fontweight="bold", labelpad=6)

        ax.set_ylabel("Count", fontsize=11, fontweight="bold")
        ax.set_title("Data Distribution", fontsize=13, fontweight="bold", pad=8)
        ax.grid(axis="y", linestyle="--", alpha=0.4, zorder=0)
        ax.tick_params(axis="x", labelsize=9)
        ax.tick_params(axis="y", labelsize=9)

        # ── Legend ────────────────────────────────────────────────────────
        from matplotlib.patches import Patch
        low_c, mid_c, high_c = cs
        t_lo = self._t_low  if self._t_low  is not None else "?"
        t_hi = self._t_high if self._t_high is not None else "?"
        handles = [
            Patch(facecolor=low_c,  edgecolor="black", alpha=0.75,
                  label=f"< {t_lo:.3g}" if isinstance(t_lo, float) else f"< {t_lo}"),
            Patch(facecolor=mid_c,  edgecolor="black", alpha=0.75,
                  label=(f"{t_lo:.3g} – {t_hi:.3g}"
                         if isinstance(t_lo, float) and isinstance(t_hi, float)
                         else "Mid")),
            Patch(facecolor=high_c, edgecolor="black", alpha=0.75,
                  label=f"≥ {t_hi:.3g}" if isinstance(t_hi, float) else f"≥ {t_hi}"),
        ]
        ax.legend(handles=handles, loc="upper right", fontsize=8,
                  framealpha=0.85, edgecolor="gray")

        self._canvas.draw()
        self._update_stats(self._values)

    # ── Stats bar helpers ─────────────────────────────────────────────────

    def _update_stats(self, vals: np.ndarray) -> None:
        def fmt(v: float) -> str:
            return f"{v:.4g}" if abs(v) < 1e4 else f"{v:.3e}"

        self._stat_labels["N"].setText(f"{len(vals):,}")
        self._stat_labels["Min"].setText(fmt(float(vals.min())))
        self._stat_labels["Max"].setText(fmt(float(vals.max())))
        self._stat_labels["Mean"].setText(fmt(float(vals.mean())))
        self._stat_labels["Median"].setText(fmt(float(np.median(vals))))
        self._stat_labels["Std"].setText(fmt(float(vals.std())))

    def _reset_stats(self) -> None:
        for lbl in self._stat_labels.values():
            lbl.setText("—")


# ---------------------------------------------------------------------------
# Module-level helpers (pure functions, easy to unit-test)
# ---------------------------------------------------------------------------

def _fd_bins(vals: np.ndarray) -> int:
    """Freedman-Diaconis bin count, capped at _BIN_MAX."""
    n  = len(vals)
    iq = np.percentile(vals, 75) - np.percentile(vals, 25)
    if iq > 0 and n > 0:
        h = 2.0 * iq / (n ** (1 / 3))
        span = vals.max() - vals.min()
        if h > 0:
            return min(int(np.ceil(span / h)), _BIN_MAX)
    # Fallback: Sturges
    return min(max(int(np.ceil(np.log2(n))) + 1, 10), _BIN_MAX)


def _zone_colors(high_is_green: bool) -> tuple[str, str, str]:
    """Return (low_color, mid_color, high_color)."""
    if high_is_green:
        return COLOR_RED, COLOR_YELLOW, COLOR_GREEN
    return COLOR_GREEN, COLOR_YELLOW, COLOR_RED


def _draw_colored_bars(
    ax,
    vals:       np.ndarray,
    bin_edges:  np.ndarray,
    t_low:      float | None,
    t_high:     float | None,
    high_is_green: bool,
) -> None:
    """
    Draw histogram bars, colour-coded by which threshold zone the bin centre
    falls in.  Bins that span a boundary are split proportionally.
    """
    low_c, mid_c, high_c = _zone_colors(high_is_green)
    counts, _ = np.histogram(vals, bins=bin_edges)

    for i, count in enumerate(counts):
        if count == 0:
            continue
        left  = bin_edges[i]
        right = bin_edges[i + 1]
        mid   = (left + right) / 2.0
        width = right - left

        if   t_low  is not None and mid < t_low:  color = low_c
        elif t_high is not None and mid > t_high:  color = high_c
        else:                                       color = mid_c

        ax.bar(
            left, count,
            width=width, align="edge",
            color=color, edgecolor="white",
            linewidth=0.4, alpha=0.80, zorder=2,
        )


def _format_log_xaxis(ax) -> None:
    """Apply log-decade tick labels on an axis already in log10 space."""
    # The data is in log10 space (not a log-scale axis), so we just format
    # the numeric ticks to show 10^n notation.
    def _log_fmt(val, _pos):
        exp = int(round(val))
        frac = val - exp
        if abs(frac) < 0.05:
            return f"$10^{{{exp}}}$"
        return f"$10^{{{val:.1f}}}$"

    ax.xaxis.set_major_locator(AutoLocator())
    ax.xaxis.set_major_formatter(mticker.FuncFormatter(_log_fmt))
