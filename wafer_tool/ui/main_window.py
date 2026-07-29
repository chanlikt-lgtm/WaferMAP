"""
main_window.py  (v2.3)
======================
Changes vs v2.2
---------------
  • Live Preview: 5×5 grid (25 wafers) rendered as thumbnails, all fit in one
    view.  Grid resets at run-start and fills left-to-right, top-to-bottom.
  • Tabs are NEVER locked during a run — user can freely switch between
    Live Preview, Scatter, and Histogram at any time.
  • Wafer orientation mini-diagram restored to left panel: live circle with
    quadrant labels 1–4 that rearrange as CW rotation / Mirror X / Mirror Y
    settings change.
"""
from __future__ import annotations

import os
import subprocess
import sys
from typing import Optional

import numpy as np

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.patches import Patch

from PyQt6.QtCore    import Qt, QRectF, QPointF, QSize
from PyQt6.QtGui     import (
    QPixmap, QPainter, QBrush, QPen, QColor, QFont
)
from PyQt6.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QDialog, QFileDialog,
    QFrame, QGridLayout, QGroupBox, QHBoxLayout, QLabel, QLineEdit,
    QMainWindow, QMessageBox, QProgressBar, QPushButton, QRadioButton, QButtonGroup,
    QSizePolicy, QSpacerItem, QSplitter, QStatusBar,
    QTabWidget, QVBoxLayout, QWidget,
)

from wafer_tool.config import PlotConfig
from wafer_tool.data_loader import read_wafer_data
from ..worker import ReportWorker
from ..eff_loader import scan_eff, EffScanError
from ..eff_worker import EffReportWorker, EffPreviewWorker
from .eff_param_dialog import EffParameterDialog
from .histogram_widget import HistogramWidget


# ─────────────────────────────────────────────────────────────────────────────
# Palette
# ─────────────────────────────────────────────────────────────────────────────
_DARK_BG  = "#1e1e2e"
_PANEL_BG = "#2a2a3e"
_ACCENT   = "#7c3aed"
_ACCENT_H = "#6d28d9"
_FG       = "#e2e8f0"
_MUTED    = "#94a3b8"
_GREEN    = "#22c55e"
_YELLOW   = "#eab308"
_RED      = "#ef4444"
_BORDER   = "#3f3f5e"
_MPL_BG   = "#ffffff"

# ─────────────────────────────────────────────────────────────────────────────
# Bright theme palette
# ─────────────────────────────────────────────────────────────────────────────
_BRIGHT_BG    = "#f5f5fa"
_BRIGHT_PANEL = "#ffffff"
_BRIGHT_FG    = "#1a1a2e"
_BRIGHT_MUTED = "#555577"
_BRIGHT_BORDER= "#ccccdd"

_BRIGHT_STYLESHEET = f"""
QMainWindow, QWidget {{
    background-color:{_BRIGHT_BG}; color:{_BRIGHT_FG};
    font-family:'Segoe UI','Helvetica Neue',Arial,sans-serif; font-size:13px;
}}
QGroupBox {{
    background-color:{_BRIGHT_PANEL}; border:1px solid {_BRIGHT_BORDER}; border-radius:8px;
    margin-top:14px; padding:10px 12px 12px 12px;
    font-weight:600; font-size:11px; color:{_BRIGHT_MUTED};
    letter-spacing:0.06em; text-transform:uppercase;
}}
QGroupBox::title {{ subcontrol-origin:margin; subcontrol-position:top left; padding:0 6px; left:10px; }}
QLineEdit, QComboBox {{
    background-color:{_BRIGHT_BG}; border:1px solid {_BRIGHT_BORDER}; border-radius:5px;
    padding:5px 8px; color:{_BRIGHT_FG}; selection-background-color:{_ACCENT};
}}
QLineEdit:focus, QComboBox:focus {{ border-color:{_ACCENT}; }}
QLineEdit[invalid="true"] {{ border-color:{_RED}; color:{_RED}; }}
QComboBox::drop-down {{ border:none; width:20px; }}
QComboBox QAbstractItemView {{ background-color:{_BRIGHT_PANEL}; border:1px solid {_BRIGHT_BORDER}; selection-background-color:{_ACCENT}; }}
QCheckBox, QRadioButton {{ spacing:6px; font-size:12px; }}
QCheckBox::indicator, QRadioButton::indicator {{
    width:15px; height:15px; border-radius:7px;
    border:1px solid {_BRIGHT_BORDER}; background-color:{_BRIGHT_BG};
}}
QCheckBox::indicator {{ border-radius:4px; }}
QCheckBox::indicator:checked {{ background-color:{_ACCENT}; border-color:{_ACCENT}; }}
QRadioButton::indicator:checked {{ background-color:{_ACCENT}; border-color:{_ACCENT}; }}
QPushButton#run_btn {{
    background-color:{_ACCENT}; color:white; border:none; border-radius:7px;
    padding:10px 24px; font-size:14px; font-weight:700;
}}
QPushButton#run_btn:hover   {{ background-color:{_ACCENT_H}; }}
QPushButton#run_btn:pressed {{ background-color:#5b21b6; }}
QPushButton#run_btn:disabled {{ background-color:#c0c0d8; color:#888899; }}
QPushButton#browse_btn, QPushButton#open_btn {{
    background-color:{_BRIGHT_PANEL}; color:{_BRIGHT_FG}; border:1px solid {_BRIGHT_BORDER};
    border-radius:5px; padding:5px 12px; font-weight:600;
}}
QPushButton#browse_btn:hover, QPushButton#open_btn:hover {{ border-color:{_ACCENT}; color:{_ACCENT}; }}
QPushButton#cancel_btn {{
    background-color:transparent; color:{_RED}; border:1px solid {_RED};
    border-radius:5px; padding:5px 14px; font-weight:600;
}}
QPushButton#cancel_btn:hover {{ background-color:{_RED}; color:white; }}
QPushButton#toggle_btn {{
    background-color:{_BRIGHT_PANEL}; color:{_BRIGHT_FG}; border:1px solid {_BRIGHT_BORDER};
    border-radius:5px; padding:4px 20px; font-size:12px;
}}
QPushButton#toggle_btn:hover {{ border-color:{_ACCENT}; color:{_ACCENT}; }}
QTabWidget::pane {{ border:1px solid {_BRIGHT_BORDER}; border-radius:6px; background:{_BRIGHT_PANEL}; }}
QTabBar::tab {{ background:{_BRIGHT_BG}; color:{_BRIGHT_MUTED}; padding:6px 16px; border-radius:5px 5px 0 0; border:1px solid {_BRIGHT_BORDER}; margin-right:2px; }}
QTabBar::tab:selected {{ background:{_BRIGHT_PANEL}; color:{_BRIGHT_FG}; border-bottom:2px solid {_ACCENT}; }}
QProgressBar {{ background-color:{_BRIGHT_BG}; border:1px solid {_BRIGHT_BORDER}; border-radius:5px; text-align:center; height:18px; font-size:11px; color:{_BRIGHT_FG}; }}
QProgressBar#wafer_bar::chunk   {{ background-color:{_ACCENT}; border-radius:4px; }}
QProgressBar#overall_bar::chunk {{ background-color:{_GREEN};  border-radius:4px; }}
QLabel#status_label {{ color:#b45309; font-size:12px; font-style:italic; padding:2px 0; }}
QLabel#stat_val {{ background-color:#f8f8f8; border:1px solid #cccccc; color:#111111; font-size:12px; padding:3px 6px; qproperty-alignment:AlignCenter; }}
QLabel#stat_hdr {{ color:{_BRIGHT_MUTED}; font-size:11px; font-weight:600; qproperty-alignment:AlignCenter; }}
QLabel#grid_cell {{
    background-color:#e8e8f0; border:1px solid {_BRIGHT_BORDER};
    border-radius:3px; color:{_BRIGHT_MUTED}; font-size:9px;
}}
QSplitter::handle {{ background-color:{_BRIGHT_BORDER}; }}
QStatusBar {{ color:{_BRIGHT_MUTED}; font-size:11px; }}
"""

_STYLESHEET = f"""
QMainWindow, QWidget {{
    background-color:{_DARK_BG}; color:{_FG};
    font-family:'Segoe UI','Helvetica Neue',Arial,sans-serif; font-size:13px;
}}
QGroupBox {{
    background-color:{_PANEL_BG}; border:1px solid {_BORDER}; border-radius:8px;
    margin-top:14px; padding:10px 12px 12px 12px;
    font-weight:600; font-size:11px; color:{_MUTED};
    letter-spacing:0.06em; text-transform:uppercase;
}}
QGroupBox::title {{ subcontrol-origin:margin; subcontrol-position:top left; padding:0 6px; left:10px; }}
QLineEdit, QComboBox {{
    background-color:{_DARK_BG}; border:1px solid {_BORDER}; border-radius:5px;
    padding:5px 8px; color:{_FG}; selection-background-color:{_ACCENT};
}}
QLineEdit:focus, QComboBox:focus {{ border-color:{_ACCENT}; }}
QLineEdit[invalid="true"] {{ border-color:{_RED}; color:{_RED}; }}
QComboBox::drop-down {{ border:none; width:20px; }}
QComboBox QAbstractItemView {{ background-color:{_PANEL_BG}; border:1px solid {_BORDER}; selection-background-color:{_ACCENT}; }}
QCheckBox, QRadioButton {{ spacing:6px; font-size:12px; }}
QCheckBox::indicator, QRadioButton::indicator {{
    width:15px; height:15px; border-radius:7px;
    border:1px solid {_BORDER}; background-color:{_DARK_BG};
}}
QCheckBox::indicator {{ border-radius:4px; }}
QCheckBox::indicator:checked {{ background-color:{_ACCENT}; border-color:{_ACCENT}; }}
QRadioButton::indicator:checked {{ background-color:{_ACCENT}; border-color:{_ACCENT}; }}
QPushButton#run_btn {{
    background-color:{_ACCENT}; color:white; border:none; border-radius:7px;
    padding:10px 24px; font-size:14px; font-weight:700;
}}
QPushButton#run_btn:hover   {{ background-color:{_ACCENT_H}; }}
QPushButton#run_btn:pressed {{ background-color:#5b21b6; }}
QPushButton#run_btn:disabled {{ background-color:#4b4b6a; color:#6b6b8a; }}
QPushButton#browse_btn, QPushButton#open_btn {{
    background-color:{_PANEL_BG}; color:{_FG}; border:1px solid {_BORDER};
    border-radius:5px; padding:5px 12px; font-weight:600;
}}
QPushButton#browse_btn:hover, QPushButton#open_btn:hover {{ border-color:{_ACCENT}; color:{_ACCENT}; }}
QPushButton#cancel_btn {{
    background-color:transparent; color:{_RED}; border:1px solid {_RED};
    border-radius:5px; padding:5px 14px; font-weight:600;
}}
QPushButton#cancel_btn:hover {{ background-color:{_RED}; color:white; }}
QPushButton#toggle_btn {{
    background-color:{_PANEL_BG}; color:{_FG}; border:1px solid {_BORDER};
    border-radius:5px; padding:4px 20px; font-size:12px;
}}
QPushButton#toggle_btn:hover {{ border-color:{_ACCENT}; color:{_ACCENT}; }}
QTabWidget::pane {{ border:1px solid {_BORDER}; border-radius:6px; background:{_PANEL_BG}; }}
QTabBar::tab {{ background:{_DARK_BG}; color:{_MUTED}; padding:6px 16px; border-radius:5px 5px 0 0; border:1px solid {_BORDER}; margin-right:2px; }}
QTabBar::tab:selected {{ background:{_PANEL_BG}; color:{_FG}; border-bottom:2px solid {_ACCENT}; }}
QProgressBar {{ background-color:{_DARK_BG}; border:1px solid {_BORDER}; border-radius:5px; text-align:center; height:18px; font-size:11px; color:{_FG}; }}
QProgressBar#wafer_bar::chunk   {{ background-color:{_ACCENT}; border-radius:4px; }}
QProgressBar#overall_bar::chunk {{ background-color:{_GREEN};  border-radius:4px; }}
QLabel#status_label {{ color:{_YELLOW}; font-size:12px; font-style:italic; padding:2px 0; }}
QLabel#stat_val {{ background-color:#f8f8f8; border:1px solid #cccccc; color:#111111; font-size:12px; padding:3px 6px; qproperty-alignment:AlignCenter; }}
QLabel#stat_hdr {{ color:{_MUTED}; font-size:11px; font-weight:600; qproperty-alignment:AlignCenter; }}
QLabel#grid_cell {{
    background-color:#111122; border:1px solid {_BORDER};
    border-radius:3px; color:{_MUTED}; font-size:9px;
}}
QSplitter::handle {{ background-color:{_BORDER}; }}
QStatusBar {{ color:{_MUTED}; font-size:11px; }}
"""


# ─────────────────────────────────────────────────────────────────────────────
# Scientific-notation QLineEdit
# ─────────────────────────────────────────────────────────────────────────────

class SciLineEdit(QLineEdit):
    def __init__(self, default: float = 1e-5, parent=None) -> None:
        super().__init__(parent)
        self._default = default
        self.setText(f"{default:g}")
        self.setPlaceholderText("e.g. 1e-5 or -90")
        self.textChanged.connect(self._revalidate)

    def _revalidate(self, text: str) -> None:
        ok = self._parse(text) is not None
        self.setProperty("invalid", not ok)
        self.style().unpolish(self); self.style().polish(self)

    def _parse(self, text: str):
        try:    return float(text)
        except: return None

    def value(self) -> float:
        v = self._parse(self.text())
        return v if v is not None else self._default

    def is_valid(self) -> bool:
        return self._parse(self.text()) is not None


# ─────────────────────────────────────────────────────────────────────────────
# Wafer Orientation Preview widget  (QPainter circle with quadrant labels)
# ─────────────────────────────────────────────────────────────────────────────

class WaferOrientationWidget(QWidget):
    """
    Circular wafer diagram with quadrant labels 1–4.
    Labels rearrange live as rotation / mirror settings change.

        Default (0° CW, no mirror):
            1 | 2
            -----
            3 | 4
    """
    _BASE = np.array([[1, 2], [3, 4]])

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setFixedSize(130, 130)
        self._arr = self._BASE.copy()

    def update_orientation(self, rot_deg: int, mirror_x: bool, mirror_y: bool) -> None:
        arr = self._BASE.copy()
        if mirror_x:  arr = np.fliplr(arr)
        if mirror_y:  arr = np.flipud(arr)
        # np.rot90 is CCW; k=3 → 90° CW, k=2 → 180°, k=1 → 270° CW
        k = {0: 0, 90: 3, 180: 2, 270: 1}.get(rot_deg, 0)
        self._arr = np.rot90(arr, k=k)
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w, h   = self.width(), self.height()
        cx, cy = w / 2.0, h / 2.0
        r      = min(w, h) / 2.0 - 6

        # Outer wafer circle
        painter.setBrush(QBrush(QColor("#7dd3c0")))
        painter.setPen(QPen(QColor("#444444"), 1.5))
        painter.drawEllipse(QPointF(cx, cy), r, r)

        # "Wafer Preview" label centred
        painter.setPen(QColor("#1a1a2e"))
        f = QFont("Segoe UI", 7, QFont.Weight.Bold)
        painter.setFont(f)
        painter.drawText(QRectF(cx - 28, cy - 10, 56, 20),
                         Qt.AlignmentFlag.AlignCenter, "Wafer\nPreview")

        # Quadrant circles — positions: TL / TR / BL / BR
        offset = r * 0.48
        dot_r  = r * 0.26
        # arr[row][col]: row 0=top, row 1=bottom; col 0=left, col 1=right
        pos_map = [(-1, -1), (-1, +1), (+1, -1), (+1, +1)]  # (row_sign, col_sign) → (dy, dx)
        labels  = {
            (0, 0): self._arr[0, 0],
            (0, 1): self._arr[0, 1],
            (1, 0): self._arr[1, 0],
            (1, 1): self._arr[1, 1],
        }
        for (row, col), num in labels.items():
            dx = (+1 if col == 1 else -1) * offset
            dy = (+1 if row == 1 else -1) * offset
            px, py = cx + dx, cy + dy
            painter.setBrush(QBrush(QColor("white")))
            painter.setPen(QPen(QColor("#555555"), 1))
            painter.drawEllipse(QPointF(px, py), dot_r, dot_r)
            painter.setPen(QColor("#111111"))
            f2 = QFont("Segoe UI", 9, QFont.Weight.Bold)
            painter.setFont(f2)
            painter.drawText(
                QRectF(px - dot_r, py - dot_r, dot_r * 2, dot_r * 2),
                Qt.AlignmentFlag.AlignCenter,
                str(num),
            )

        painter.end()


# ─────────────────────────────────────────────────────────────────────────────
# 5×5 Wafer grid preview
# ─────────────────────────────────────────────────────────────────────────────

class WaferGridWidget(QWidget):
    """
    Displays up to 25 wafer thumbnails in a 5×5 grid.
    Cells are QLabels; pixmaps are capped at _PIX_CAP×_PIX_CAP on load so
    we never hold 25 full-resolution PNGs (~62 MB) just for thumbnails.
    """
    COLS    = 5
    ROWS    = 5
    MAX     = COLS * ROWS   # 25
    _PIX_CAP = 300          # max stored dimension per cell (~360 KB ARGB vs ~2.5 MB full-res)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        layout = QGridLayout(self)
        layout.setSpacing(3)
        layout.setContentsMargins(4, 4, 4, 4)

        self._labels:  list[QLabel]   = []
        self._pixmaps: list[Optional[QPixmap]] = []
        self._tips:    list[str]      = []

        for i in range(self.MAX):
            row, col = divmod(i, self.COLS)
            lbl = QLabel()
            lbl.setObjectName("grid_cell")
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Ignored)
            lbl.setMinimumSize(40, 40)
            layout.addWidget(lbl, row, col)
            self._labels.append(lbl)
            self._pixmaps.append(None)
            self._tips.append("")

        # Every row and column gets equal share of available space
        for r in range(self.ROWS):
            layout.setRowStretch(r, 1)
        for c in range(self.COLS):
            layout.setColumnStretch(c, 1)

        self._count = 0

    # ── Public ────────────────────────────────────────────────────────────

    def reset(self) -> None:
        self._count = 0
        for i in range(self.MAX):
            self._labels[i].clear()
            self._labels[i].setText("")
            self._pixmaps[i] = None
            self._tips[i] = ""

    def add_wafer(self, lot: str, wid: str, png_path: str) -> None:
        # When the grid is full, clear all cells and start over from 0
        if self._count >= self.MAX:
            self.reset()
        idx = self._count
        pix = QPixmap(png_path)
        if not pix.isNull():
            # Cap stored resolution — thumbnails never need more than _PIX_CAP px
            if pix.width() > self._PIX_CAP or pix.height() > self._PIX_CAP:
                pix = pix.scaled(
                    QSize(self._PIX_CAP, self._PIX_CAP),
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
            self._pixmaps[idx] = pix
            self._tips[idx]    = f"Lot: {lot}  |  Wafer: {wid}"
            self._labels[idx].setToolTip(self._tips[idx])
            self._scale_cell(idx)
        self._count += 1

    # ── Resize: re-scale all visible cells ────────────────────────────────

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        for i in range(self._count):
            self._scale_cell(i)

    def _scale_cell(self, idx: int) -> None:
        pix = self._pixmaps[idx]
        if pix is None:
            return
        lbl  = self._labels[idx]
        # Use the label's actual allocated size; fall back to a square guess
        # based on the widget size divided evenly across the 5×5 grid.
        w = lbl.width()
        h = lbl.height()
        if w < 10 or h < 10:
            side = max(40, min(self.width(), self.height()) // self.COLS - 4)
            w = h = side
        lbl.setPixmap(
            pix.scaled(QSize(w, h),
                       Qt.AspectRatioMode.KeepAspectRatio,
                       Qt.TransformationMode.SmoothTransformation)
        )


# ─────────────────────────────────────────────────────────────────────────────
# Threshold Scatter canvas
# ─────────────────────────────────────────────────────────────────────────────

class ScatterCanvas(FigureCanvas):
    _MAX_SCATTER = 200_000   # points beyond this are overplotted anyway; downsample
    _MAX_XTICKS  = 60        # above this, per-wafer tick labels are unreadable AND
                             # slow — a 50k-wafer file froze the UI here; use sparse ticks

    def __init__(self) -> None:
        self.fig, self.ax = plt.subplots(figsize=(9, 6), dpi=100)
        super().__init__(self.fig)
        self.setMinimumHeight(520)
        self.fig.patch.set_facecolor(_MPL_BG)
        self._z:            np.ndarray | None = None   # value array only; no full df retained
        self._wafer_codes:  np.ndarray | None = None   # int32 per-die wafer code
        self._wafer_names:  list[str] | None  = None   # ordered wafer label strings
        self._t_low         = -90.0
        self._t_high        = -60.0
        self._high_is_green = False
        self._log_y         = False
        self._param_label   = ""    # parameter name shown in the title bracket
        self._show_placeholder()

    def set_param_label(self, label: str) -> None:
        """Set the parameter name shown in brackets in the chart title."""
        self._param_label = label or ""

    def _show_placeholder(self) -> None:
        self.ax.clear()
        self.ax.set_facecolor("#f5f5f5")
        self.ax.text(0.5, 0.5, "Browse a data file to see the scatter plot",
                     ha="center", va="center", fontsize=11, color="#888",
                     transform=self.ax.transAxes)
        self.ax.set_xticks([]); self.ax.set_yticks([])
        self.fig.tight_layout(); self.draw()

    def update_plot(
        self,
        z: np.ndarray,
        t_low,
        t_high,
        high_is_green,
        wafer_codes: np.ndarray | None = None,
        wafer_names: list[str] | None  = None,
    ) -> None:
        self._z = z
        self._wafer_codes = wafer_codes
        self._wafer_names = wafer_names
        self._t_low = t_low
        self._t_high = t_high
        self._high_is_green = high_is_green
        self._render()

    def toggle_log_y(self) -> bool:
        self._log_y = not self._log_y
        if self._z is not None:
            self._render()
        return self._log_y

    def _render(self) -> None:
        if self._z is None: return
        ax = self.ax; ax.clear(); ax.set_facecolor(_MPL_BG)
        z_full = self._z
        lo  = min(self._t_low, self._t_high)
        hi  = max(self._t_low, self._t_high)
        cb, cm, ca = (("#2ecc71","#f1c40f","#e74c3c") if not self._high_is_green
                      else ("#e74c3c","#f1c40f","#2ecc71"))

        wc   = self._wafer_codes   # int32 per-die wafer code (may be None)
        wnames = self._wafer_names or []
        n_wafers = len(wnames)

        # ── Downsample for display ────────────────────────────────────────
        n_full = len(z_full)
        rng = np.random.default_rng(seed=0)
        if n_full > self._MAX_SCATTER:
            keep = np.sort(rng.choice(n_full, size=self._MAX_SCATTER, replace=False))
            z  = z_full[keep]
            wc_s = wc[keep] if wc is not None else None
        else:
            z  = z_full
            wc_s = wc

        # ── Build X coordinates ───────────────────────────────────────────
        # Wafer-as-X: jitter each point horizontally within its column so
        # overplotted dies spread into a visible strip (strip / dot plot).
        if wc_s is not None and n_wafers > 0:
            jitter = rng.uniform(-0.35, 0.35, size=len(z)).astype(np.float32)
            x = wc_s.astype(np.float32) + jitter
            del jitter
        else:
            x = np.arange(len(z), dtype=np.float32)

        use_log_y = self._log_y and np.any(z_full > 0)

        if use_log_y:
            z_pos = z_full[z_full > 0]
            y_bot = z_pos.min() * 0.5
            y_top = z_full.max() * 2.0
            del z_pos
            if lo > y_bot:
                ax.axhspan(y_bot, max(lo, y_bot), facecolor=cb, alpha=0.28)
            if lo < hi:
                ax.axhspan(max(lo, y_bot), max(hi, y_bot), facecolor=cm, alpha=0.28)
            if hi < y_top:
                ax.axhspan(max(hi, y_bot), y_top, facecolor=ca, alpha=0.28)
        else:
            pad   = max((z_full.max() - z_full.min()) * 0.05, 1e-12)
            y_bot = z_full.min() - pad
            y_top = z_full.max() + pad
            ax.axhspan(y_bot, lo,    facecolor=cb, alpha=0.28)
            ax.axhspan(lo,    hi,    facecolor=cm, alpha=0.28)
            ax.axhspan(hi,    y_top, facecolor=ca, alpha=0.28)

        # Threshold lines
        for val, lbl_txt in [(lo, f"Limit = {lo:.3e}"), (hi, f"Limit = {hi:.3e}")]:
            if use_log_y and val <= 0:
                continue
            ax.axhline(val, color="#333", linewidth=1.2, linestyle="--")
            ax.text(0.98, val, lbl_txt, transform=ax.get_yaxis_transform(),
                    ha="right", va="bottom", fontsize=9,
                    bbox=dict(facecolor="white", edgecolor="#aaa",
                              boxstyle="round,pad=0.2", alpha=0.9))

        # ── Three scatter calls (one per zone) ────────────────────────────
        _kw = dict(s=4, alpha=0.55, linewidths=0)
        if use_log_y:
            pos_mask = z > 0
            z_p, x_p = z[pos_mask], x[pos_mask]
            del pos_mask
            ax.scatter(x_p[z_p < lo],                    z_p[z_p < lo],                    color=cb, **_kw)
            ax.scatter(x_p[(z_p >= lo) & (z_p <= hi)],   z_p[(z_p >= lo) & (z_p <= hi)],   color=cm, **_kw)
            ax.scatter(x_p[z_p > hi],                    z_p[z_p > hi],                    color=ca, **_kw)
            del z_p, x_p
            ax.set_yscale("log")
        else:
            ax.scatter(x[z < lo],                        z[z < lo],                        color=cb, **_kw)
            ax.scatter(x[(z >= lo) & (z <= hi)],          z[(z >= lo) & (z <= hi)],          color=cm, **_kw)
            ax.scatter(x[z > hi],                        z[z > hi],                        color=ca, **_kw)
            ax.set_ylim(y_bot, y_top)

        # ── X axis: wafer labels or die index ─────────────────────────────
        # Show only the wafer portion of the label (last token) to avoid
        # long "LotID WaferNum" strings overlapping each other on the axis.
        # If all names share a common lot prefix, display that lot in the
        # axis label instead.
        n_shown = len(z)
        if wnames:
            # Split "PF428324 01" → lot="PF428324", wnum="01"
            parts_list = [n.rsplit(" ", 1) for n in wnames]
            lots  = [p[0] for p in parts_list]
            wnums = [p[-1] for p in parts_list]
            common_lot = lots[0] if len(set(lots)) == 1 else None
            tick_labels = wnums if common_lot else wnames

            # With thousands of wafers, one Text label per wafer is unreadable
            # and pathologically slow to lay out (it froze the UI on a 50k-wafer
            # file). Above the cap, thin the ticks to an evenly-spaced subset.
            if n_wafers > self._MAX_XTICKS:
                idx = np.linspace(0, n_wafers - 1, self._MAX_XTICKS).round().astype(int)
                idx = np.unique(idx)
                ax.set_xticks(idx)
                ax.set_xticklabels([tick_labels[i] for i in idx],
                                   rotation=90, ha="center", fontsize=7)
            else:
                ax.set_xticks(np.arange(n_wafers))
                ax.set_xticklabels(tick_labels, rotation=0, ha="center", fontsize=8)
            ax.set_xlim(-0.6, n_wafers - 0.4)
            suffix = f"  (showing {n_shown:,} of {n_full:,} dies)" if n_full > self._MAX_SCATTER else ""
            many = f"  ·  {n_wafers:,} wafers" if n_wafers > self._MAX_XTICKS else ""
            xlabel = (f"Wafer — Lot {common_lot}{suffix}{many}" if common_lot
                      else f"Wafer{suffix}{many}")
        else:
            ax.set_xlim(-n_full * 0.01, n_full * 1.01)
            xlabel = (
                f"Die index  (showing {n_shown:,} of {n_full:,})" if n_full > self._MAX_SCATTER
                else "Die index"
            )
        ax.set_ylabel("Value", fontsize=10, fontweight="bold")
        ax.set_xlabel(xlabel, fontsize=9, color="#555")
        title = "Threshold Scatter"
        if self._param_label:
            title += f"  ({self._param_label})"
        ax.set_title(title, fontsize=12, fontweight="bold")
        ax.tick_params(axis="y", labelsize=8)
        ax.grid(axis="y", linestyle="--", alpha=0.4, color="#ccc")
        ax.grid(axis="x", linestyle=":",  alpha=0.25, color="#ccc")
        for sp in ax.spines.values(): sp.set_edgecolor("#ccc")
        self.fig.subplots_adjust(left=0.08, right=0.985, top=0.93, bottom=0.12)
        self.draw()
        self.fig.canvas.flush_events()   # release stale PathCollection refs from previous render


# ─────────────────────────────────────────────────────────────────────────────
# Histogram canvas  (with log toggle)
# ─────────────────────────────────────────────────────────────────────────────

class HistogramCanvas(FigureCanvas):
    def __init__(self) -> None:
        self.fig, self.ax = plt.subplots(figsize=(6, 4), dpi=95)
        super().__init__(self.fig)
        self.fig.patch.set_facecolor(_MPL_BG)
        self._z: np.ndarray | None = None; self._t_low = -90.0; self._t_high = -60.0
        self._high_is_green = False; self._log_x = False
        self._show_placeholder()

    def _show_placeholder(self) -> None:
        self.ax.clear(); self.ax.set_facecolor("#f5f5f5")
        self.ax.text(0.5, 0.5, "Browse a data file to see the histogram",
                     ha="center", va="center", fontsize=11, color="#888",
                     transform=self.ax.transAxes)
        self.ax.set_xticks([]); self.ax.set_yticks([])
        self.fig.tight_layout(); self.draw()

    def update_plot(self, z: np.ndarray, t_low, t_high, high_is_green, log_x=False) -> None:
        self._z = z
        self._t_low = t_low; self._t_high = t_high
        self._high_is_green = high_is_green; self._log_x = log_x
        self._render()

    def toggle_log(self) -> bool:
        self._log_x = not self._log_x
        if self._z is not None: self._render()
        return self._log_x

    def _render(self) -> None:
        if self._z is None: return
        ax = self.ax; ax.clear(); ax.set_facecolor(_MPL_BG)
        z  = self._z
        lo = min(self._t_low, self._t_high)
        hi = max(self._t_low, self._t_high)
        if self._high_is_green:
            cb, cm, ca = "#e74c3c", "#f1c40f", "#2ecc71"
            leg = [(ca, f"< {lo:.3g}"), (cm, f"{lo:.3g} – {hi:.3g}"), (cb, f"≥ {hi:.3g}")]
        else:
            cb, cm, ca = "#2ecc71", "#f1c40f", "#e74c3c"
            leg = [(cb, f"< {lo:.3g}"), (cm, f"{lo:.3g} – {hi:.3g}"), (ca, f"≥ {hi:.3g}")]

        # ── Separate positives first — log mode requires them ─────────────
        # Bug fix: z.min() > 0 fails silently when ANY value is 0 or negative.
        # Correct approach: filter to z_pos independently, then decide on log.
        z_pos   = z[z > 0]
        use_log = self._log_x and z_pos.size > 1

        if use_log:
            bins   = np.logspace(np.log10(z_pos.min()), np.log10(z_pos.max()), 61)
            plot_z = z_pos                    # only positive values on log scale
        else:
            bins   = 60
            plot_z = z

        counts, bin_edges, patches = ax.hist(plot_z, bins=bins, edgecolor="none")
        for patch, left in zip(patches, bin_edges[:-1]):
            patch.set_facecolor(cb if left < lo else cm if left <= hi else ca)

        y_max = counts.max() if counts.size else 1
        for val in (lo, hi):
            if use_log and val <= 0:          # skip non-positive limits on log axis
                continue
            ax.axvline(val, color="#333", linewidth=1.3, linestyle="--", zorder=5)
            ax.text(val, y_max * 0.98, f"{val:.3e}", rotation=90,
                    ha="right", va="top", fontsize=8,
                    bbox=dict(facecolor="white", edgecolor="#aaa",
                              boxstyle="round,pad=0.2", alpha=0.9))

        if use_log:
            ax.set_xscale("log")
        else:
            # Force scientific notation so small values (e.g. 5e-7) are readable
            import matplotlib.ticker as _mticker
            ax.xaxis.set_major_formatter(
                _mticker.FuncFormatter(
                    lambda v, _: f"{v:.2e}" if v != 0 else "0"
                )
            )
            ax.tick_params(axis="x", labelrotation=30)

        handles = [Patch(facecolor=c, edgecolor="black", label=l) for c, l in leg]
        ax.legend(handles=handles, loc="upper right", fontsize=8,
                  facecolor="white", edgecolor="#aaa")
        ax.set_xlabel("Measurement Value", fontsize=10, fontweight="bold")
        ax.set_ylabel("Count",             fontsize=10, fontweight="bold")
        ax.set_title("Data Distribution",  fontsize=12, fontweight="bold")
        ax.tick_params(axis="y", labelsize=8)
        ax.grid(axis="y", linestyle="--", alpha=0.4, color="#ccc", zorder=0)
        for sp in ax.spines.values(): sp.set_edgecolor("#ccc")
        self.fig.tight_layout(pad=1.2); self.draw()


# ─────────────────────────────────────────────────────────────────────────────
# Stats bar widget  (N / Min / Max / Mean / Median / Std)
# ─────────────────────────────────────────────────────────────────────────────

class StatsBar(QWidget):
    _FIELDS = ["N", "Min", "Max", "Mean", "Median", "Std"]

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setStyleSheet("background-color:#ffffff;")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4); layout.setSpacing(2)
        self._vals: dict[str, QLabel] = {}
        for field in self._FIELDS:
            col = QVBoxLayout(); col.setSpacing(1)
            hdr = QLabel(field); hdr.setObjectName("stat_hdr")
            val = QLabel("—");   val.setObjectName("stat_val")
            col.addWidget(hdr); col.addWidget(val)
            layout.addLayout(col)
            self._vals[field] = val
        self.setFixedHeight(60)

    def update_stats(self, z: np.ndarray) -> None:
        if z.size == 0:
            for v in self._vals.values(): v.setText("—"); return
        self._vals["N"].setText(f"{z.size:,}")
        self._vals["Min"].setText(f"{z.min():.4g}")
        self._vals["Max"].setText(f"{z.max():.4g}")
        self._vals["Mean"].setText(f"{z.mean():.4g}")
        self._vals["Median"].setText(f"{np.median(z):.4g}")
        self._vals["Std"].setText(f"{z.std():.4g}")

    def clear(self) -> None:
        for v in self._vals.values(): v.setText("—")


# ─────────────────────────────────────────────────────────────────────────────
# Main window
# ─────────────────────────────────────────────────────────────────────────────

class DataProcessorUI(QMainWindow):

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Wafer Map Tool  v2.3")
        self.resize(1450, 900)
        self.setMinimumSize(1100, 760)
        self.setStyleSheet(_STYLESHEET)

        self._worker = None
        # EFF-mode state: set when the loaded file is a raw .eff extraction.
        self._eff_mode = False
        self._eff_scan = None
        self._eff_indices: list[int] = []
        self._eff_selected: list[str] = []
        self._preview_worker = None   # background EFF single-parameter preview
        self._eff_preview_pos = 0     # which selected parameter is previewed
        self._preview_cache: dict[int, object] = {}  # param col index -> DataFrame
        self._chart_param_label = ""  # parameter name shown in chart titles
        self._wafer_count  = 0
        self._total_wafers = 0
        self._loaded_values: np.ndarray | None = None  # value column only; full df freed after load
        self._loaded_wafer_codes: np.ndarray | None = None  # int32 per-die wafer code
        self._loaded_wafer_names: list[str] | None = None   # ordered wafer label strings
        self._current_lot: str | None = None
        self._log_y_on     = False
        self._dark_mode    = True
        self._plot_paused  = False

        self._build_ui()
        self._wire()

    # ─────────────────────────────────────────────────────────────────────
    # Build UI
    # ─────────────────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        c = QWidget(); self.setCentralWidget(c)
        root = QHBoxLayout(c)
        root.setContentsMargins(10, 10, 10, 10); root.setSpacing(10)
        spl = QSplitter(Qt.Orientation.Horizontal)
        spl.setChildrenCollapsible(False)
        root.addWidget(spl)
        spl.addWidget(self._build_left())
        spl.addWidget(self._build_right())
        spl.setSizes([360, 920])
        bar = QStatusBar(); self.setStatusBar(bar)
        self._sb = QLabel("Ready."); bar.addWidget(self._sb)

    # ── LEFT panel ────────────────────────────────────────────────────────

    def _build_left(self) -> QWidget:
        w = QWidget(); w.setMaximumWidth(400)
        v = QVBoxLayout(w); v.setContentsMargins(0,0,0,0); v.setSpacing(8)
        v.addWidget(self._grp_file())
        v.addWidget(self._grp_thresh())
        v.addWidget(self._grp_opts())
        v.addWidget(self._grp_outdir())
        v.addSpacerItem(QSpacerItem(0,0,QSizePolicy.Policy.Minimum,QSizePolicy.Policy.Expanding))
        v.addWidget(self._grp_run())
        return w

    def _grp_file(self) -> QGroupBox:
        b = QGroupBox("Input File"); g = QGridLayout(b); g.setSpacing(6)
        self.file_edit = QLineEdit()
        self.file_edit.setPlaceholderText("Select a .csv / .txt data file…")
        self.file_edit.setReadOnly(True)
        btn = QPushButton("Browse…"); btn.setObjectName("browse_btn")
        btn.clicked.connect(self._browse_file)
        self._file_info = QLabel("")
        self._file_info.setStyleSheet(f"color:{_MUTED};font-size:10px;")
        self._file_info.setWordWrap(True)
        # ── Saved/scheduled jobs: track the newest file in the folder ───────
        self.newest_chk = QCheckBox("For saved / scheduled jobs, use the newest file in this folder")
        self.newest_chk.setToolTip(
            "When you Save Job, record the file's folder + a name pattern instead of "
            "this exact file, so each scheduled run picks the newest matching file.")
        self.pattern_edit = QLineEdit("*.txt")
        self.pattern_edit.setToolTip("Name pattern(s) to match; separate several with ';', e.g.  *.txt;*.csv")
        self.pattern_edit.setEnabled(False)
        self.newest_chk.toggled.connect(self.pattern_edit.setEnabled)
        g.addWidget(_L("Data file:"),  0, 0, 1, 2)
        g.addWidget(self.file_edit,    1, 0)
        g.addWidget(btn,               1, 1)
        g.addWidget(self._file_info,   2, 0, 1, 2)
        g.addWidget(self.newest_chk,   3, 0, 1, 2)
        g.addWidget(_L("Match pattern:"), 4, 0)
        g.addWidget(self.pattern_edit, 4, 1)
        return b

    def _grp_thresh(self) -> QGroupBox:
        b = QGroupBox("Parameters"); g = QGridLayout(b); g.setSpacing(6)
        # Shows which EFF parameter these limits belong to (hidden for txt/csv).
        self._param_name_lbl = QLabel("")
        self._param_name_lbl.setWordWrap(True)
        self._param_name_lbl.setStyleSheet(
            f"color:{_ACCENT};font-size:11px;font-weight:700;")
        self._param_name_lbl.setVisible(False)
        self.t_low_edit  = SciLineEdit(default=-90.0)
        self.t_high_edit = SciLineEdit(default=-60.0)
        self.t_low_edit.editingFinished.connect(self._refresh_charts)
        self.t_high_edit.editingFinished.connect(self._refresh_charts)
        g.addWidget(self._param_name_lbl,          0, 0, 1, 2)
        g.addWidget(_L("Limit 1 (Threshold 1):"), 1, 0)
        g.addWidget(self.t_low_edit,               1, 1)
        g.addWidget(_L("Limit 2 (Threshold 2):"), 2, 0)
        g.addWidget(self.t_high_edit,              2, 1)
        return b

    def _grp_opts(self) -> QGroupBox:
        b = QGroupBox("Options & Wafer Orientation")
        outer = QVBoxLayout(b); outer.setSpacing(8)

        # Checkboxes row
        chk_row = QHBoxLayout()
        self.log_chk = QCheckBox("Log scale")
        self.hig_chk = QCheckBox("Reverse  (High = Green)")
        chk_row.addWidget(self.log_chk); chk_row.addWidget(self.hig_chk)
        outer.addLayout(chk_row)

        outer.addWidget(_sep())

        # Orientation area: radio buttons + mirror + wafer diagram side by side
        orient_row = QHBoxLayout(); orient_row.setSpacing(12)

        left_col = QVBoxLayout(); left_col.setSpacing(4)
        left_col.addWidget(_L("Rotation:", muted=True))

        self._rot_group = QButtonGroup(self)
        for i, label in enumerate(["0° CW", "90° CW", "180° CW", "270° CW"]):
            rb = QRadioButton(label)
            if i == 0: rb.setChecked(True)
            self._rot_group.addButton(rb, i)
            left_col.addWidget(rb)

        left_col.addSpacing(6)
        left_col.addWidget(_sep())
        left_col.addWidget(_L("Mirror:", muted=True))
        self.mirx_chk = QCheckBox("Mirror X")
        self.miry_chk = QCheckBox("Mirror Y")
        left_col.addWidget(self.mirx_chk)
        left_col.addWidget(self.miry_chk)

        orient_row.addLayout(left_col)

        # Wafer diagram on the right
        self._wafer_orient = WaferOrientationWidget()
        orient_row.addWidget(self._wafer_orient, alignment=Qt.AlignmentFlag.AlignVCenter)

        outer.addLayout(orient_row)
        return b

    def _grp_outdir(self) -> QGroupBox:
        b = QGroupBox("Output Folder"); g = QGridLayout(b); g.setSpacing(6)
        self.out_edit = QLineEdit()
        self.out_edit.setText(os.path.expanduser("~/Desktop/wafer_output"))
        btn = QPushButton("Browse…"); btn.setObjectName("browse_btn")
        btn.clicked.connect(self._browse_out)
        g.addWidget(self.out_edit, 0, 0); g.addWidget(btn, 0, 1)
        return b

    def _grp_run(self) -> QWidget:
        w = QWidget(); v = QVBoxLayout(w)
        v.setContentsMargins(0,0,0,0); v.setSpacing(6)
        self.run_btn = QPushButton("▶  Generate Report")
        self.run_btn.setObjectName("run_btn")
        self.cancel_btn = QPushButton("✕  Cancel")
        self.cancel_btn.setObjectName("cancel_btn")
        self.cancel_btn.setEnabled(False)
        v.addWidget(self.run_btn); v.addWidget(self.cancel_btn)

        # ── Automation: save this run as a job, or schedule saved jobs ──────
        auto_row = QHBoxLayout(); auto_row.setSpacing(6)
        self.save_job_btn = QPushButton("💾  Save Job")
        self.save_job_btn.setObjectName("open_btn")
        self.save_job_btn.setToolTip(
            "Save the current data file, output folder and all plot settings as a "
            ".wtjob you can re-run or schedule offline.")
        self.save_job_btn.clicked.connect(self._save_job)
        self.schedule_btn = QPushButton("🕑  Schedule…")
        self.schedule_btn.setObjectName("open_btn")
        self.schedule_btn.setToolTip(
            "Schedule a saved .wtjob to run automatically (daily / weekly / monthly), "
            "offline via Windows Task Scheduler.")
        self.schedule_btn.clicked.connect(self._open_scheduler)
        auto_row.addWidget(self.save_job_btn); auto_row.addWidget(self.schedule_btn)
        v.addLayout(auto_row)
        return w

    def _build_eff_preview_bar(self) -> QWidget:
        """Selector to page through each selected EFF parameter's scatter /
        histogram preview. Hidden entirely for txt/csv files."""
        bar = QGroupBox("EFF Parameter Preview")
        row = QHBoxLayout(bar); row.setContentsMargins(8, 4, 8, 4); row.setSpacing(6)
        self._eff_prev_btn = QPushButton("◀ Prev")
        self._eff_prev_btn.setObjectName("toggle_btn"); self._eff_prev_btn.setFixedWidth(80)
        self._eff_prev_btn.clicked.connect(lambda: self._eff_preview_step(-1))
        self._eff_param_combo = QComboBox()
        self._eff_param_combo.currentIndexChanged.connect(self._eff_preview_combo_changed)
        self._eff_next_btn = QPushButton("Next ▶")
        self._eff_next_btn.setObjectName("toggle_btn"); self._eff_next_btn.setFixedWidth(80)
        self._eff_next_btn.clicked.connect(lambda: self._eff_preview_step(+1))
        self._eff_preview_status = QLabel("")
        self._eff_preview_status.setStyleSheet(f"color:{_MUTED};font-size:11px;")
        row.addWidget(self._eff_prev_btn)
        row.addWidget(self._eff_param_combo, stretch=1)
        row.addWidget(self._eff_next_btn)
        row.addWidget(self._eff_preview_status)
        self._eff_preview_bar = bar
        bar.setVisible(False)
        return bar

    # ── RIGHT panel ───────────────────────────────────────────────────────

    def _build_right(self) -> QWidget:
        w = QWidget(); v = QVBoxLayout(w)
        v.setContentsMargins(0,0,0,0); v.setSpacing(8)

        # ── Theme toggle (top-right) ──────────────────────────────────────
        theme_row = QHBoxLayout(); theme_row.setContentsMargins(0,0,4,0)
        theme_row.addStretch()
        self._theme_btn = QPushButton("☀  Bright Mode")
        self._theme_btn.setObjectName("toggle_btn")
        self._theme_btn.setFixedWidth(130)
        self._theme_btn.clicked.connect(self._toggle_theme)
        theme_row.addWidget(self._theme_btn)
        v.addLayout(theme_row)

        # ── EFF per-parameter preview selector (hidden unless in EFF mode) ──
        v.addWidget(self._build_eff_preview_bar())

        # Tab widget — ALWAYS fully interactive, never disabled
        self.tabs = QTabWidget()
        v.addWidget(self.tabs, stretch=4)

        # ── Tab 0: Live 5×5 grid preview ─────────────────────────────────
        grid_tab = QWidget(); gtv = QVBoxLayout(grid_tab)
        gtv.setContentsMargins(4,4,4,4); gtv.setSpacing(4)

        self._grid_label = QLabel("Wafer thumbnails appear here as they are rendered  (5 × 5 = 25 per view)")
        self._grid_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._grid_label.setStyleSheet(f"color:{_MUTED};font-size:11px;font-style:italic;")
        gtv.addWidget(self._grid_label)

        pause_row = QHBoxLayout()
        self._pause_btn = QPushButton("⏸  Pause Preview")
        self._pause_btn.setObjectName("toggle_btn")
        self._pause_btn.setFixedWidth(150)
        self._pause_btn.clicked.connect(self._toggle_pause)
        pause_row.addStretch(); pause_row.addWidget(self._pause_btn); pause_row.addStretch()
        gtv.addLayout(pause_row)

        self._wafer_grid = WaferGridWidget()
        self._wafer_grid.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        gtv.addWidget(self._wafer_grid)

        self.tabs.addTab(grid_tab, "🗺  Live Preview  (5×5)")

        # ── Tab 1: Threshold Scatter ──────────────────────────────────────
        scatter_tab = QWidget(); stv = QVBoxLayout(scatter_tab)
        stv.setContentsMargins(4,4,4,4); stv.setSpacing(4)
        self._scatter_canvas = ScatterCanvas()
        self._scatter_canvas.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        stv.addWidget(self._scatter_canvas)
        self._log_y_btn = QPushButton("Toggle Log Y-axis  (OFF)")
        self._log_y_btn.setObjectName("toggle_btn")
        self._log_y_btn.clicked.connect(self._toggle_log_y)
        sy_row = QHBoxLayout(); sy_row.addStretch()
        sy_row.addWidget(self._log_y_btn); sy_row.addStretch()
        stv.addLayout(sy_row)
        self.tabs.addTab(scatter_tab, "⬡  Threshold Scatter")

        # ── Tab 2: Histogram ──────────────────────────────────────────────
        hist_tab = QWidget(); htv = QVBoxLayout(hist_tab)
        htv.setContentsMargins(4,4,4,4); htv.setSpacing(0)
        self._hist_widget = HistogramWidget()
        self._hist_widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        htv.addWidget(self._hist_widget)
        self.tabs.addTab(hist_tab, "📊  Histogram")

        # ── Output location ───────────────────────────────────────────────
        ob = QGroupBox("Output Location"); obl = QHBoxLayout(ob)
        obl.setContentsMargins(8,6,8,6)
        self.out_path_lbl = QLabel("—")
        self.out_path_lbl.setStyleSheet(f"color:{_MUTED};font-size:11px;")
        self.out_path_lbl.setWordWrap(True)
        self.open_btn = QPushButton("Open Folder")
        self.open_btn.setObjectName("open_btn"); self.open_btn.setFixedWidth(110)
        self.open_btn.setEnabled(False); self.open_btn.clicked.connect(self._open_folder)
        obl.addWidget(self.out_path_lbl, stretch=1); obl.addWidget(self.open_btn)
        v.addWidget(ob, stretch=0)

        # ── Progress ──────────────────────────────────────────────────────
        pb = QGroupBox("Progress"); pl = QVBoxLayout(pb)
        pl.setContentsMargins(10,8,10,8); pl.setSpacing(5)
        self.status_label = QLabel("Idle — configure parameters and press Generate Report.")
        self.status_label.setObjectName("status_label"); self.status_label.setWordWrap(True)
        pl.addWidget(self.status_label); pl.addWidget(_sep())
        pl.addWidget(_L("Wafer render:", muted=True))
        self.wafer_bar = QProgressBar(); self.wafer_bar.setObjectName("wafer_bar")
        self.wafer_bar.setFormat("%p%  (wafer render)"); pl.addWidget(self.wafer_bar)
        pl.addWidget(_L("Overall pipeline:", muted=True))
        self.overall_bar = QProgressBar(); self.overall_bar.setObjectName("overall_bar")
        self.overall_bar.setFormat("%p%  (pipeline)"); pl.addWidget(self.overall_bar)
        v.addWidget(pb, stretch=0)
        return w

    # ─────────────────────────────────────────────────────────────────────
    # Signal wiring
    # ─────────────────────────────────────────────────────────────────────

    def _wire(self) -> None:
        self.run_btn.clicked.connect(self._run)
        self.cancel_btn.clicked.connect(self._cancel)
        # Orientation diagram updates
        self._rot_group.idClicked.connect(lambda _: self._update_orient())
        self.mirx_chk.stateChanged.connect(lambda _: self._update_orient())
        self.miry_chk.stateChanged.connect(lambda _: self._update_orient())
        # Re-render scatter/histogram on option changes
        self.hig_chk.stateChanged.connect(lambda _: self._refresh_charts())

    def _update_orient(self) -> None:
        rot = [0, 90, 180, 270][self._rot_group.checkedId()]
        self._wafer_orient.update_orientation(rot, self.mirx_chk.isChecked(), self.miry_chk.isChecked())

    # ─────────────────────────────────────────────────────────────────────
    # File / chart handling
    # ─────────────────────────────────────────────────────────────────────

    def _browse_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Select data file", "",
            "Wafer data (*.eff *.csv *.txt *.dat);;EFF extraction (*.eff);;"
            "Text / CSV (*.csv *.txt *.dat);;All files (*)"
        )
        if not path: return
        if path.lower().endswith(".eff"):
            self._handle_eff_pick(path)
        else:
            self._eff_mode = False
            self._eff_scan = None
            self._eff_indices = []
            self._eff_selected = []
            self._cancel_preview_worker()
            self._preview_cache.clear()
            if hasattr(self, "_eff_preview_bar"):
                self._eff_preview_bar.setVisible(False)
            self._param_name_lbl.setVisible(False)
            if self.pattern_edit.text().strip() == "*.eff":
                self.pattern_edit.setText("*.txt")
            self.file_edit.setText(path)
            self._load_preview(path)

    def _handle_eff_pick(self, path: str) -> None:
        """Scan a raw .eff file and let the user pick which parameters to map.

        Lot/Wafer/X/Y are auto-detected coordinates; the user chooses one or
        more measurement parameters, and each becomes its own output folder.
        """
        try:
            scan = scan_eff(path)
        except EffScanError as exc:
            self._file_info.setText(f"⚠  {exc}")
            self._file_info.setStyleSheet(f"color:{_RED};font-size:11px;")
            self._status(f"⚠  {exc}", _RED)
            return
        except Exception as exc:  # noqa: BLE001 — surface any read failure
            self._file_info.setText(f"⚠  Could not read EFF: {exc}")
            self._file_info.setStyleSheet(f"color:{_RED};font-size:11px;")
            return

        dlg = EffParameterDialog(scan, self, preselected=self._eff_selected or None)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            self._status("EFF parameter selection cancelled.", _YELLOW)
            return

        self._eff_mode    = True
        self._eff_scan    = scan
        self._eff_indices = dlg.selected_indices()
        self._eff_selected = dlg.selected_names()
        self.file_edit.setText(path)
        # Folder-mode scheduled EFF jobs should match .eff drops, not .txt.
        self.pattern_edit.setText("*.eff")

        rows_txt = f"~{scan.declared_rows:,} rows" if scan.declared_rows else "rows"
        self._file_info.setText(
            f"✓  EFF · {rows_txt} · {len(self._eff_indices)} of "
            f"{len(scan.parameters)} parameter(s) selected — "
            f"each becomes its own output folder."
        )
        self._file_info.setStyleSheet(f"color:{_GREEN};font-size:12px;font-weight:600;")

        # Set up the per-parameter preview: page through each selected
        # parameter's scatter / histogram with ◀ Prev / Next ▶.
        self._preview_cache.clear()
        self._eff_preview_pos = 0
        self._loaded_values = None
        self._loaded_wafer_codes = None
        self._loaded_wafer_names = None
        self._scatter_canvas._show_placeholder()

        self._eff_param_combo.blockSignals(True)
        self._eff_param_combo.clear()
        for i, name in enumerate(self._eff_selected):
            self._eff_param_combo.addItem(f"{i + 1}/{len(self._eff_selected)}  {name}")
        self._eff_param_combo.setCurrentIndex(0)
        self._eff_param_combo.blockSignals(False)
        multi = len(self._eff_selected) > 1
        self._eff_prev_btn.setEnabled(multi)
        self._eff_next_btn.setEnabled(multi)
        self._eff_preview_bar.setVisible(True)

        self._status(
            f"EFF ready — {len(self._eff_indices)} parameter(s). "
            f"Set thresholds & output folder, then press Generate Report.",
            _GREEN,
        )
        # Kick off the first parameter's preview (background — never blocks UI).
        self._eff_preview_goto(0)

    # ── EFF per-parameter preview navigation ─────────────────────────────────

    def _cancel_preview_worker(self) -> None:
        if self._preview_worker is not None:
            try:
                self._preview_worker.ready.disconnect()
                self._preview_worker.failed.disconnect()
            except (RuntimeError, TypeError):
                pass
            self._preview_worker.cancel()
            self._preview_worker.finished.connect(self._preview_worker.deleteLater)
            self._preview_worker = None

    def _eff_preview_step(self, delta: int) -> None:
        """◀ Prev / Next ▶ — wrap around the selected parameters."""
        if not self._eff_selected:
            return
        n = len(self._eff_selected)
        self._eff_preview_goto((self._eff_preview_pos + delta) % n)

    def _eff_preview_combo_changed(self, index: int) -> None:
        if index >= 0 and index != self._eff_preview_pos:
            self._eff_preview_goto(index)

    def _apply_param_limits(self, pos: int) -> None:
        """Set Limit 1 / Limit 2 to the pos-th parameter's EFF spec limits.

        Only overwrites a field when that limit exists in the file, so a
        parameter without spec limits keeps whatever is currently entered.
        """
        name = self._eff_selected[pos]
        param = (self._eff_scan.parameter_by_index(self._eff_indices[pos])
                 if self._eff_scan else None)
        lower = param.limit_lower if param else None
        upper = param.limit_upper if param else None

        if lower is not None:
            self.t_low_edit.setText(f"{lower:g}")
        if upper is not None:
            self.t_high_edit.setText(f"{upper:g}")

        if lower is not None or upper is not None:
            note = "spec limits applied"
            if lower is None or upper is None:
                note = "1 spec limit applied — check the other"
            suffix = f"  ·  {note}"
        else:
            suffix = "  ·  no spec limits in file — keeping current values"
        self._param_name_lbl.setText(f"Parameter:  {name}{suffix}")
        self._param_name_lbl.setVisible(True)

    def _eff_preview_goto(self, pos: int) -> None:
        """Show the scatter / histogram for the pos-th selected parameter."""
        if not self._eff_mode or not self._eff_selected:
            return
        pos = max(0, min(pos, len(self._eff_selected) - 1))
        self._eff_preview_pos = pos
        self._eff_param_combo.blockSignals(True)
        self._eff_param_combo.setCurrentIndex(pos)
        self._eff_param_combo.blockSignals(False)

        name = self._eff_selected[pos]
        col_index = self._eff_indices[pos]
        self._chart_param_label = name       # shown in scatter / histogram titles

        # Refresh the threshold limits to this parameter's spec limits.
        self._apply_param_limits(pos)

        cached = self._preview_cache.get(col_index)
        if cached is not None:                         # instant — no re-read
            n_pts, n_w = self._apply_preview_df(cached)
            self._eff_preview_status.setText(f"{name}: {n_pts:,} pts · {n_w} wafers")
            return

        # Not cached: read this parameter in the background.
        self._cancel_preview_worker()
        self._scatter_canvas._show_placeholder()
        self._loaded_values = None
        self._eff_preview_status.setText(f"loading {name}…")
        worker = EffPreviewWorker(self._eff_scan.path, col_index, name, scan=self._eff_scan)
        worker.ready.connect(self._on_eff_preview_ready)
        worker.failed.connect(self._on_eff_preview_failed)
        self._preview_worker = worker
        worker.start()

    def _on_eff_preview_ready(self, df, col_index: int) -> None:
        if col_index not in self._eff_indices:
            return
        self._preview_cache[col_index] = df            # cache even if paged away
        pos = self._eff_indices.index(col_index)
        if pos != self._eff_preview_pos:
            return                                     # stale — user moved on
        name = self._eff_selected[pos]
        if df is None or len(df) == 0:
            self._scatter_canvas._show_placeholder()
            self._eff_preview_status.setText(f"{name}: no data points")
            return
        n_pts, n_w = self._apply_preview_df(df)
        self._eff_preview_status.setText(f"{name}: {n_pts:,} pts · {n_w} wafers")

    def _on_eff_preview_failed(self, msg: str) -> None:
        self._eff_preview_status.setText(f"preview failed: {msg}")

    def _load_preview(self, path: str) -> None:
        self._chart_param_label = ""     # no parameter name for plain txt/csv
        try:
            df = read_wafer_data(path)
        except Exception as exc:
            self._file_info.setText(f"⚠ {exc}")
            self._file_info.setStyleSheet(f"color:{_RED};font-size:10px;")
            self._loaded_values = None
            self._loaded_wafer_codes = None
            self._loaded_wafer_names = None
            return
        n_pts, n_w = self._apply_preview_df(df)
        self._file_info.setText(f"✓  {n_pts:,} die points · {n_w} wafers")
        self._file_info.setStyleSheet(f"color:{_GREEN};font-size:13px;font-weight:700;")

    def _apply_preview_df(self, df) -> tuple[int, int]:
        """Load a lot/wafer/x/y/value DataFrame into the scatter + histogram.

        Shared by the txt/csv preview and the per-parameter EFF preview. Returns
        ``(n_points, n_wafers)``.
        """
        n_w = df.groupby(["lot", "wafer"]).ngroups
        self._total_wafers = n_w
        z = df["value"].to_numpy(dtype=np.float32, copy=False)  # view into df's buffer
        # Build per-die wafer label for scatter X axis
        wafer_cat = (df["lot"].astype(str) + " " + df["wafer"].astype(str)).astype("category")
        # int32, not int16: files can have far more than 32,767 wafers, and an
        # int16 code overflows past that — wrapping to negatives so every wafer
        # beyond #32767 plotted off-screen (dense block on the left, empty right).
        self._loaded_wafer_codes = wafer_cat.cat.codes.to_numpy(dtype=np.int32, copy=True)
        self._loaded_wafer_names = list(wafer_cat.cat.categories)
        del wafer_cat                                        # frees label temp; z keeps value alive
        self._loaded_values = z
        self._refresh_charts()
        return len(z), n_w

    def _refresh_charts(self) -> None:
        if self._loaded_values is None: return
        t_low  = self.t_low_edit.value()
        t_high = self.t_high_edit.value()
        hig    = self.hig_chk.isChecked()
        # Show the current parameter name in the chart titles (EFF mode).
        self._scatter_canvas.set_param_label(self._chart_param_label)
        self._hist_widget.set_param_label(self._chart_param_label)
        self._scatter_canvas.update_plot(
            self._loaded_values, t_low, t_high, hig,
            self._loaded_wafer_codes, self._loaded_wafer_names,
        )
        self._hist_widget.set_data(self._loaded_values, t_low, t_high, hig)

    def _toggle_log_y(self) -> None:
        self._log_y_on = self._scatter_canvas.toggle_log_y()
        self._log_y_btn.setText(f"Toggle Log Y-axis  ({'ON' if self._log_y_on else 'OFF'})")

    def _toggle_pause(self) -> None:
        self._plot_paused = not self._plot_paused
        if self._plot_paused:
            self._pause_btn.setText("▶  Resume Preview")
        else:
            self._pause_btn.setText("⏸  Pause Preview")

    def _toggle_theme(self) -> None:
        self._dark_mode = not self._dark_mode
        if self._dark_mode:
            self.setStyleSheet(_STYLESHEET)
            self._theme_btn.setText("☀  Bright Mode")
        else:
            self.setStyleSheet(_BRIGHT_STYLESHEET)
            self._theme_btn.setText("🌙  Dark Mode")

    # ─────────────────────────────────────────────────────────────────────
    # Run / cancel
    # ─────────────────────────────────────────────────────────────────────

    def _browse_out(self) -> None:
        p = QFileDialog.getExistingDirectory(self, "Select output directory")
        if p: self.out_edit.setText(p)

    def _open_folder(self) -> None:
        p = self.out_edit.text().strip()
        if os.path.isdir(p):
            if sys.platform == "win32":    os.startfile(p)
            elif sys.platform == "darwin": subprocess.Popen(["open", p])
            else:                          subprocess.Popen(["xdg-open", p])

    def _gather_job(self):
        """Validate the current inputs and return a WaferJob, or None (a status
        message is shown). Shared by Save Job; mirrors _run's validation."""
        from wafer_tool.automation.job import WaferJob
        fp  = self.file_edit.text().strip()
        out = self.out_edit.text().strip()
        if not fp or not os.path.isfile(fp):
            self._status("⚠  Select a valid data file.", _RED); return None
        if not out:
            self._status("⚠  Select an output directory.", _RED); return None
        if not self.t_low_edit.is_valid() or not self.t_high_edit.is_valid():
            self._status("⚠  Invalid threshold value.", _RED); return None
        t_low, t_high = self.t_low_edit.value(), self.t_high_edit.value()
        if t_low == t_high:
            self._status("⚠  Limit 1 and Limit 2 must differ.", _RED); return None
        rot_deg = [0, 90, 180, 270][self._rot_group.checkedId()]
        # Raw-EFF jobs carry the selected parameter names; an empty list would
        # mean "all parameters", so require an explicit selection here.
        eff_params = list(self._eff_selected) if self._eff_mode else []
        if self._eff_mode and not eff_params:
            self._status("⚠  Select at least one EFF parameter first.", _RED); return None
        # Folder mode: record the file's folder + pattern so each scheduled run
        # picks the newest matching file instead of this exact one.
        default_pattern = "*.eff" if self._eff_mode else "*.txt"
        input_dir, pattern = "", default_pattern
        if self.newest_chk.isChecked():
            input_dir = os.path.dirname(fp)
            pattern = self.pattern_edit.text().strip() or default_pattern
        return WaferJob(
            input_file=fp, out_dir=out, t_low=t_low, t_high=t_high,
            use_log=self.log_chk.isChecked(), high_is_green=self.hig_chk.isChecked(),
            mirror_x=self.mirx_chk.isChecked(), mirror_y=self.miry_chk.isChecked(),
            rot_deg=rot_deg, input_dir=input_dir, input_pattern=pattern,
            eff_params=eff_params,
        )

    def _save_job(self) -> None:
        """Save the current run as a .wtjob, then offer to open the scheduler."""
        from wafer_tool.automation.job import save_job, JOB_SUFFIX
        job = self._gather_job()
        if job is None:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Save Job", "wafer_job" + JOB_SUFFIX, f"Wafer Job (*{JOB_SUFFIX})")
        if not path:
            return
        saved = save_job(path, job)
        self._status(f"Saved job: {os.path.basename(saved)}", _GREEN)
        eff_note = (
            f"\n\nEFF job — maps {len(job.eff_params)} parameter(s), "
            f"one output folder each." if job.eff_params else "")
        ret = QMessageBox.question(
            self, "Job Saved",
            f"Saved {os.path.basename(saved)}.{eff_note}\n\nRuns offline with:\n"
            f"python run_job.py \"{saved}\"\n\nOpen the scheduler to run it automatically?")
        if ret == QMessageBox.StandardButton.Yes:
            from wafer_tool.automation.scheduler_dialog import SchedulerDialog
            SchedulerDialog(self, initial_job=str(saved)).exec()

    def _open_scheduler(self) -> None:
        from wafer_tool.automation.scheduler_dialog import SchedulerDialog
        SchedulerDialog(self).exec()

    def _run(self) -> None:
        if self._eff_mode:
            return self._run_eff()
        fp  = self.file_edit.text().strip()
        out = self.out_edit.text().strip()
        if not fp or not os.path.isfile(fp):
            return self._status("⚠  Select a valid data file.", _RED)
        if not out:
            return self._status("⚠  Select an output directory.", _RED)
        if not self.t_low_edit.is_valid() or not self.t_high_edit.is_valid():
            return self._status("⚠  Invalid threshold value.", _RED)
        t_low, t_high = self.t_low_edit.value(), self.t_high_edit.value()
        if t_low == t_high:
            return self._status("⚠  Limit 1 and Limit 2 must differ.", _RED)
        os.makedirs(out, exist_ok=True)
        rot_deg = [0, 90, 180, 270][self._rot_group.checkedId()]
        try:
            config = PlotConfig(
                t_low=t_low, t_high=t_high,
                use_log=self.log_chk.isChecked(),
                high_is_green=self.hig_chk.isChecked(),
                mirror_x=self.mirx_chk.isChecked(),
                mirror_y=self.miry_chk.isChecked(),
                rot_deg=rot_deg,
            )
        except ValueError as exc:
            return self._status(f"⚠  {exc}", _RED)

        # Reset state — grid clears, both bars reset, pause lifted
        self._wafer_count  = 0
        self._current_lot  = None
        self._plot_paused  = False
        self._pause_btn.setText("⏸  Pause Preview")
        self._wafer_grid.reset()
        self._grid_label.setText("Rendering wafers…")
        self.wafer_bar.setValue(0);   self.wafer_bar.setFormat("%p%  (wafer render)")
        self.overall_bar.setValue(0); self.overall_bar.setFormat("%p%  (pipeline)")
        self._status("Starting…", _YELLOW)
        self.run_btn.setEnabled(False); self.cancel_btn.setEnabled(True)
        self.open_btn.setEnabled(False)
        # Switch to grid preview at start; user is free to switch away anytime
        self.tabs.setCurrentIndex(0)

        if self._worker is not None:        # stale worker (shouldn't happen, safety net)
            self._worker.deleteLater()
            self._worker = None
        self._worker = ReportWorker(fp, config, out)
        self._worker.progress.connect(self.overall_bar.setValue)
        self._worker.wafer_progress.connect(self.wafer_bar.setValue)
        self._worker.status_message.connect(self._on_msg)
        self._worker.wafer_ready.connect(self._on_wafer)
        self._worker.report_done.connect(self._on_done)
        self._worker.error.connect(self._on_err)
        self._worker.start()

    def _run_eff(self) -> None:
        """Generate a wafer-map report per selected parameter of an .eff file."""
        out = self.out_edit.text().strip()
        if not self._eff_scan or not self._eff_indices:
            return self._status("⚠  Pick an EFF file and at least one parameter.", _RED)
        if not out:
            return self._status("⚠  Select an output directory.", _RED)
        if not self.t_low_edit.is_valid() or not self.t_high_edit.is_valid():
            return self._status("⚠  Invalid threshold value.", _RED)
        t_low, t_high = self.t_low_edit.value(), self.t_high_edit.value()
        if t_low == t_high:
            return self._status("⚠  Limit 1 and Limit 2 must differ.", _RED)
        os.makedirs(out, exist_ok=True)
        rot_deg = [0, 90, 180, 270][self._rot_group.checkedId()]
        try:
            config = PlotConfig(
                t_low=t_low, t_high=t_high,
                use_log=self.log_chk.isChecked(),
                high_is_green=self.hig_chk.isChecked(),
                mirror_x=self.mirx_chk.isChecked(),
                mirror_y=self.miry_chk.isChecked(),
                rot_deg=rot_deg,
            )
        except ValueError as exc:
            return self._status(f"⚠  {exc}", _RED)

        # Reset state — same as the txt path
        self._wafer_count  = 0
        self._current_lot  = None
        self._plot_paused  = False
        self._pause_btn.setText("⏸  Pause Preview")
        self._wafer_grid.reset()
        self._grid_label.setText("Reading EFF and splitting parameters…")
        self.wafer_bar.setValue(0);   self.wafer_bar.setFormat("%p%  (wafer render)")
        self.overall_bar.setValue(0); self.overall_bar.setFormat("%p%  (pipeline)")
        n = len(self._eff_indices)
        self._status(f"Starting EFF — {n} parameter(s)…", _YELLOW)
        self.run_btn.setEnabled(False); self.cancel_btn.setEnabled(True)
        self.open_btn.setEnabled(False)
        self.tabs.setCurrentIndex(0)

        if self._worker is not None:
            self._worker.deleteLater()
            self._worker = None
        self._worker = EffReportWorker(
            self._eff_scan.path, self._eff_indices, config, out,
            scan=self._eff_scan,
        )
        self._worker.progress.connect(self.overall_bar.setValue)
        self._worker.wafer_progress.connect(self.wafer_bar.setValue)
        self._worker.status_message.connect(self._on_msg)
        self._worker.wafer_ready.connect(self._on_wafer)
        self._worker.all_done.connect(self._on_eff_all_done)
        self._worker.error.connect(self._on_err)
        self._worker.start()

    def _cancel(self) -> None:
        if not (self._worker and self._worker.isRunning()):
            return
        # Disconnect signals immediately so late emissions don't confuse the UI.
        # Both worker types are handled — disconnect only signals that exist.
        for sig_name in ("report_done", "all_done", "error",
                         "status_message", "wafer_ready"):
            sig = getattr(self._worker, sig_name, None)
            if sig is not None:
                try:
                    sig.disconnect()
                except (RuntimeError, TypeError):
                    pass
        # Wire QThread.finished (now accessible since we renamed our signal)
        # so the dying thread auto-deletes once its run() returns.
        self._worker.finished.connect(self._worker.deleteLater)
        self._worker.cancel()
        self._worker = None
        # Re-enable the UI immediately — don't wait for the background thread
        self._status("Cancelled — ready to run again.", _YELLOW)
        self._sb.setText("Cancelled.")
        self.run_btn.setEnabled(True)
        self.cancel_btn.setEnabled(False)

    # ─────────────────────────────────────────────────────────────────────
    # Worker slots
    # ─────────────────────────────────────────────────────────────────────

    def _on_msg(self, msg: str) -> None:
        self._status(msg, _YELLOW); self._sb.setText(msg)
        if msg.startswith("Rendering"):
            self._wafer_count += 1

    def _on_wafer(self, lot: str, wid: str, png: str) -> None:
        """Add to grid — resets grid on lot change; auto-cycles every 25 wafers."""
        if self._plot_paused:
            return
        # Reset grid when entering a new lot
        if lot != self._current_lot:
            self._current_lot = lot
            self._wafer_grid.reset()
        self._wafer_grid.add_wafer(lot, wid, png)
        self._grid_label.setText(
            f"Lot: {lot}  —  Rendered: {self._wafer_count} wafer(s) total  "
            f"| latest: Wafer {wid}"
        )

    def _on_done(self, pdf: str, csv: str, pptx: str) -> None:
        self.overall_bar.setValue(100); self.overall_bar.setFormat("100%  (pipeline ✓)")
        self.wafer_bar.setValue(100)
        self._grid_label.setText(
            f"✓  Complete — {self._wafer_count} wafer(s) rendered"
        )
        lines = [f"✓  PDF:  {os.path.basename(pdf)}"]
        if csv:
            lines.append(f"✓  CSV:  {os.path.basename(csv)}")
        if os.path.isfile(pptx):
            lines.append(f"✓  PPTX: {os.path.basename(pptx)}")
        else:
            lines.append("⚠  PPTX: not generated — run:  py -m pip install python-pptx")
        self._status("\n".join(lines), _GREEN)
        self.out_path_lbl.setText(self.out_edit.text().strip())
        self.open_btn.setEnabled(True); self._reset()
        import gc; gc.collect()  # free matplotlib figure cache from render loop

    def _on_eff_all_done(self, results: list) -> None:
        """Completion slot for the multi-parameter EFF pipeline.

        ``results`` is a list of ``(param_name, folder, pdf_path, pptx_path)``.
        """
        self.overall_bar.setValue(100); self.overall_bar.setFormat("100%  (pipeline ✓)")
        self.wafer_bar.setValue(100)
        n = len(results)
        self._grid_label.setText(f"✓  Complete — {n} parameter map set(s) generated")
        lines = [f"✓  {n} parameter folder(s) written to the output directory:"]
        for name, folder, pdf, pptx in results[:12]:
            tag = "PDF + PPTX" if pptx else "PDF"
            lines.append(f"   • {os.path.basename(folder)}   ({tag})")
        if n > 12:
            lines.append(f"   … and {n - 12} more")
        self._status("\n".join(lines), _GREEN)
        self.out_path_lbl.setText(self.out_edit.text().strip())
        self.open_btn.setEnabled(True); self._reset()
        import gc; gc.collect()

    def _on_err(self, msg: str) -> None:
        if msg == "Cancelled by user.":
            self._status("Cancelled — ready to run again.", _YELLOW)
            self._sb.setText("Cancelled.")
        else:
            self._status(f"✗  {msg}", _RED)
            self._sb.setText(f"Error: {msg}")
        self._reset()

    # ─────────────────────────────────────────────────────────────────────
    # Helpers
    # ─────────────────────────────────────────────────────────────────────

    def _status(self, text: str, color: str = _FG) -> None:
        self.status_label.setText(text)
        self.status_label.setStyleSheet(
            f"color:{color};font-size:12px;font-style:italic;padding:2px 0;"
        )

    def _reset(self) -> None:
        self.run_btn.setEnabled(True); self.cancel_btn.setEnabled(False)
        if self._worker is not None:
            self._worker.deleteLater()   # safe: Qt defers until thread fully exits
            self._worker = None


# ─────────────────────────────────────────────────────────────────────────────
# Widget micro-factories
# ─────────────────────────────────────────────────────────────────────────────

def _L(text: str, muted: bool = False) -> QLabel:
    l = QLabel(text)
    if muted: l.setStyleSheet(f"color:{_MUTED};font-size:11px;")
    return l

def _sep() -> QFrame:
    f = QFrame(); f.setFrameShape(QFrame.Shape.HLine)
    f.setStyleSheet(f"color:{_BORDER};background-color:{_BORDER};")
    return f


# ─────────────────────────────────────────────────────────────────────────────
# Stand-alone run
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    app = QApplication(sys.argv)
    win = DataProcessorUI()
    win.show()
    sys.exit(app.exec())
