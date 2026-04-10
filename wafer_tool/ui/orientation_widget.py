"""
ui/orientation_widget.py
========================
Self-contained PyQt6 widget that combines:
    - Mirror X / Mirror Y checkboxes
    - 0° / 90° / 180° / 270° clockwise rotation radio buttons
    - A live Matplotlib canvas showing how the wafer orientation changes

Emits a `changed` signal whenever any control is toggled.

Public API
----------
OrientationWidget(parent=None)
    .mirror_x  : bool  (property)
    .mirror_y  : bool  (property)
    .rot_deg   : int   (property, one of {0, 90, 180, 270})
    .changed   : pyqtSignal()
"""
from __future__ import annotations

import numpy as np
from matplotlib.figure import Figure
from matplotlib.patches import Circle
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout,
    QCheckBox, QRadioButton, QButtonGroup,
)

__all__ = ["OrientationWidget"]

# Quadrant labels and their un-transformed positions on the wafer
_QUADRANT_LABELS = [
    ("1", -0.4,  0.4),
    ("2",  0.4,  0.4),
    ("3", -0.4, -0.4),
    ("4",  0.4, -0.4),
]


class OrientationWidget(QWidget):
    """Mirror + rotation controls with an inline wafer orientation preview."""

    changed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()
        self.refresh_preview()

    # ── Public properties ─────────────────────────────────────────────────

    @property
    def mirror_x(self) -> bool:
        return self._chk_mirror_x.isChecked()

    @property
    def mirror_y(self) -> bool:
        return self._chk_mirror_y.isChecked()

    @property
    def rot_deg(self) -> int:
        for btn, deg in self._rot_buttons:
            if btn.isChecked():
                return deg
        return 0

    # ── Construction ──────────────────────────────────────────────────────

    def _build_ui(self):
        layout = QHBoxLayout(self)

        # Mirror checkboxes — signals connected AFTER canvas exists (see end of method)
        mirror_col = QVBoxLayout()
        self._chk_mirror_x = QCheckBox("Mirror X")
        self._chk_mirror_y = QCheckBox("Mirror Y")
        mirror_col.addWidget(self._chk_mirror_x)
        mirror_col.addWidget(self._chk_mirror_y)
        layout.addLayout(mirror_col)

        # Rotation radio buttons — setChecked(True) fires toggled, so connect AFTER canvas
        rot_col = QVBoxLayout()
        self._rot_buttons: list[tuple[QRadioButton, int]] = []
        self._btn_group = QButtonGroup(self)
        for label, deg in [("0° CW", 0), ("90° CW", 90), ("180° CW", 180), ("270° CW", 270)]:
            btn = QRadioButton(label)
            self._btn_group.addButton(btn)
            self._rot_buttons.append((btn, deg))
            rot_col.addWidget(btn)
        self._rot_buttons[0][0].setChecked(True)   # default: 0° — safe, no signal yet
        layout.addLayout(rot_col)

        # Matplotlib preview canvas — must exist before signals are connected
        self._fig    = Figure(figsize=(2, 2), dpi=80)
        self._ax     = self._fig.add_subplot(111)
        self._canvas = FigureCanvas(self._fig)
        layout.addWidget(self._canvas)

        # Connect signals NOW — after self._ax exists — so the toggled event
        # fired by setChecked(True) above cannot reach refresh_preview early.
        self._chk_mirror_x.stateChanged.connect(self._on_change)
        self._chk_mirror_y.stateChanged.connect(self._on_change)
        for btn, _deg in self._rot_buttons:
            btn.toggled.connect(self._on_change)

    def _on_change(self):
        self.refresh_preview()
        self.changed.emit()

    # ── Drawing ───────────────────────────────────────────────────────────

    def refresh_preview(self):
        ax = self._ax
        ax.clear()
        ax.set_xlim(-1.2, 1.2)
        ax.set_ylim(-1.2, 1.2)
        ax.set_aspect("equal")
        ax.axis("off")

        # Wafer disc
        ax.add_patch(
            Circle((0, 0), 1, facecolor="#A8E6CF", edgecolor="#3b444b",
                   linewidth=1.5, zorder=1)
        )

        # Flat / notch at the bottom
        notch_x = np.array([-0.08, 0.0,   0.08])
        notch_y = np.array([-1.00, -0.92, -1.00])
        ax.fill(notch_x, notch_y, color="white", zorder=2)
        ax.plot(notch_x, notch_y, color="#3b444b", linewidth=1.5, zorder=2)

        # Quadrant labels (rotated with the wafer)
        text_rotation = -self.rot_deg
        for label, bx, by in _QUADRANT_LABELS:
            tx, ty = self._transform(bx, by)
            ax.text(
                tx, ty, label,
                ha="center", va="center", fontsize=12,
                fontweight="bold", zorder=3,
                rotation=text_rotation,
                bbox=dict(boxstyle="circle,pad=0.2",
                          facecolor="white", edgecolor="black", alpha=0.8),
            )

        ax.text(0, 0, "Wafer\nPreview", ha="center", va="center",
                fontsize=8, color="#555555", fontweight="bold", zorder=4)
        self._canvas.draw()

    def _transform(self, x: float, y: float) -> tuple[float, float]:
        """Apply current mirror + rotation to a single preview point."""
        if self.mirror_x:
            x = -x
        if self.mirror_y:
            y = -y
        _rot_map = {90: (y, -x), 180: (-x, -y), 270: (-y, x)}
        return _rot_map.get(self.rot_deg, (x, y))
