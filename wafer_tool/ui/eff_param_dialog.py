"""
eff_param_dialog.py
===================
Modal dialog shown after the user picks an ``.eff`` file.

Lot / Wafer / X / Y are always loaded (they are the map coordinates), so the
dialog only lets the user choose which **measurement parameters** to turn into
wafer maps (at least one; the maximum is however many the file contains) and,
optionally, a per-parameter **value filter**: dies whose value falls outside the
parameter's ``[Min, Max]`` are excluded before mapping.

The filter defaults to a universal ±1000 range for every parameter (matching the
standalone eff-converter), but the Min/Max of any row can be edited, and the
whole filter can be switched off.
"""
from __future__ import annotations

from typing import Iterable

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QBrush, QColor
from PyQt6.QtWidgets import (
    QAbstractItemView, QCheckBox, QDialog, QDialogButtonBox, QHBoxLayout,
    QHeaderView, QLabel, QLineEdit, QMessageBox, QPushButton, QTableWidget,
    QTableWidgetItem, QVBoxLayout,
)

from ..eff_loader import EffScan

# Universal default value-filter range (same spirit as the eff-converter).
DEFAULT_FILTER_MIN = -1000.0
DEFAULT_FILTER_MAX = 1000.0

_COL_PARAM, _COL_MIN, _COL_MAX = 0, 1, 2
_ROLE_INDEX = Qt.ItemDataRole.UserRole
_ROLE_NAME  = Qt.ItemDataRole.UserRole + 1
_ROLE_LIMS  = Qt.ItemDataRole.UserRole + 2


class EffParameterDialog(QDialog):
    """Pick measurement parameters (and an optional per-parameter value filter)."""

    def __init__(self, scan: EffScan, parent=None,
                 preselected: Iterable[str] | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Choose Parameters to Map")
        self.resize(680, 600)

        self._scan = scan
        preset = set(preselected) if preselected is not None else None

        root = QVBoxLayout(self)

        rows_txt = (f"about {scan.declared_rows:,} rows"
                    if scan.declared_rows else "rows")
        header = QLabel(
            f"<b>{scan.filename}</b><br>"
            f"{rows_txt} &times; <b>{len(scan.parameters)} parameter(s)</b><br>"
            f"<span style='color:#22c55e'>Lot&nbsp;+&nbsp;Wafer, X and Y are "
            f"always loaded as the map coordinates.</span><br>"
            f"Tick the parameters to map (at least one). Each becomes its own "
            f"output folder."
        )
        header.setWordWrap(True)
        root.addWidget(header)

        # Filter box (search) + quick-select
        filt_row = QHBoxLayout()
        filt_row.addWidget(QLabel("Find:"))
        self._search = QLineEdit()
        self._search.setPlaceholderText("type to filter parameter names…")
        self._filter_timer = QTimer(self)
        self._filter_timer.setSingleShot(True)
        self._filter_timer.setInterval(150)
        self._filter_timer.timeout.connect(self._apply_search)
        self._search.textChanged.connect(lambda _: self._filter_timer.start())
        filt_row.addWidget(self._search)
        root.addLayout(filt_row)

        btn_row = QHBoxLayout()
        b_all = QPushButton("Select All (visible)")
        b_none = QPushButton("Deselect All (visible)")
        b_lim = QPushButton("With Spec Limits")
        b_all.clicked.connect(lambda: self._set_visible(Qt.CheckState.Checked))
        b_none.clicked.connect(lambda: self._set_visible(Qt.CheckState.Unchecked))
        b_lim.clicked.connect(self._select_with_limits)
        for b in (b_all, b_none, b_lim):
            btn_row.addWidget(b)
        btn_row.addStretch(1)
        root.addLayout(btn_row)

        # ── Value filter enable + default range ───────────────────────────
        vf_row = QHBoxLayout()
        self._enable_filter = QCheckBox("Value filter — exclude dies outside")
        self._enable_filter.setChecked(True)
        self._enable_filter.toggled.connect(self._on_filter_toggled)
        vf_row.addWidget(self._enable_filter)
        vf_row.addWidget(QLabel("default Min"))
        self._def_min = QLineEdit(f"{DEFAULT_FILTER_MIN:g}")
        self._def_min.setFixedWidth(80)
        vf_row.addWidget(self._def_min)
        vf_row.addWidget(QLabel("Max"))
        self._def_max = QLineEdit(f"{DEFAULT_FILTER_MAX:g}")
        self._def_max.setFixedWidth(80)
        vf_row.addWidget(self._def_max)
        b_apply_def = QPushButton("Apply to all")
        b_apply_def.setToolTip("Fill every parameter's Min/Max with the default range above.")
        b_apply_def.clicked.connect(self._apply_default_range)
        vf_row.addWidget(b_apply_def)
        vf_row.addStretch(1)
        root.addLayout(vf_row)

        # ── Parameter table: [check + name] | Min | Max ───────────────────
        self._table = QTableWidget(len(scan.parameters), 3)
        self._table.setHorizontalHeaderLabels(["Parameter", "Filter Min", "Filter Max"])
        self._table.verticalHeader().setVisible(False)
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.horizontalHeader().setSectionResizeMode(
            _COL_PARAM, QHeaderView.ResizeMode.Stretch)
        self._table.horizontalHeader().setSectionResizeMode(
            _COL_MIN, QHeaderView.ResizeMode.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(
            _COL_MAX, QHeaderView.ResizeMode.ResizeToContents)
        self._table.setColumnWidth(_COL_MIN, 100)
        self._table.setColumnWidth(_COL_MAX, 100)

        self._table.setUpdatesEnabled(False)
        for r, p in enumerate(scan.parameters):
            label = f"{p.name}    [{p.dtype or '?'}]"
            if p.has_limits:
                label += "  (limits)"
            name_it = QTableWidgetItem(label)
            name_it.setFlags(
                Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable
                | Qt.ItemFlag.ItemIsUserCheckable)
            checked = (preset is None) or (p.name in preset)
            name_it.setCheckState(Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked)
            name_it.setData(_ROLE_INDEX, p.index)
            name_it.setData(_ROLE_NAME, p.name.lower())
            name_it.setData(_ROLE_LIMS, p.has_limits)
            self._table.setItem(r, _COL_PARAM, name_it)
            self._table.setItem(r, _COL_MIN, QTableWidgetItem(f"{DEFAULT_FILTER_MIN:g}"))
            self._table.setItem(r, _COL_MAX, QTableWidgetItem(f"{DEFAULT_FILTER_MAX:g}"))
        self._table.setUpdatesEnabled(True)
        self._table.itemChanged.connect(lambda _=None: self._update_count())
        root.addWidget(self._table, 1)

        self._count = QLabel()
        root.addWidget(self._count)

        bb = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        bb.accepted.connect(self._on_accept)
        bb.rejected.connect(self.reject)
        root.addWidget(bb)

        self._on_filter_toggled(self._enable_filter.isChecked())
        self._update_count()

    # ── search / selection helpers ───────────────────────────────────────────

    def _apply_search(self) -> None:
        needle = self._search.text().strip().lower()
        for r in range(self._table.rowCount()):
            name = self._table.item(r, _COL_PARAM).data(_ROLE_NAME) or ""
            self._table.setRowHidden(r, bool(needle) and needle not in name)

    def _set_visible(self, state: Qt.CheckState) -> None:
        self._table.blockSignals(True)
        try:
            for r in range(self._table.rowCount()):
                if not self._table.isRowHidden(r):
                    self._table.item(r, _COL_PARAM).setCheckState(state)
        finally:
            self._table.blockSignals(False)
        self._update_count()

    def _select_with_limits(self) -> None:
        self._table.blockSignals(True)
        try:
            for r in range(self._table.rowCount()):
                it = self._table.item(r, _COL_PARAM)
                has = bool(it.data(_ROLE_LIMS))
                it.setCheckState(Qt.CheckState.Checked if has else Qt.CheckState.Unchecked)
        finally:
            self._table.blockSignals(False)
        self._update_count()

    # ── value-filter helpers ─────────────────────────────────────────────────

    def _on_filter_toggled(self, on: bool) -> None:
        """Enable/disable editing of the Min/Max cells and mute them when off."""
        self._table.blockSignals(True)
        try:
            grey = QBrush(QColor("#9aa0b4"))
            normal = self._table.item(0, _COL_MIN).foreground() if self._table.rowCount() else QBrush()
            for r in range(self._table.rowCount()):
                for c in (_COL_MIN, _COL_MAX):
                    it = self._table.item(r, c)
                    flags = Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable
                    if on:
                        flags |= Qt.ItemFlag.ItemIsEditable
                    it.setFlags(flags)
                    it.setForeground(grey if not on else normal)
        finally:
            self._table.blockSignals(False)
        for w in (self._def_min, self._def_max):
            w.setEnabled(on)

    def _apply_default_range(self) -> None:
        try:
            mn = float(self._def_min.text()); mx = float(self._def_max.text())
        except ValueError:
            QMessageBox.warning(self, "Value filter", "Default Min/Max must be numbers.")
            return
        self._table.blockSignals(True)
        try:
            for r in range(self._table.rowCount()):
                self._table.item(r, _COL_MIN).setText(f"{mn:g}")
                self._table.item(r, _COL_MAX).setText(f"{mx:g}")
        finally:
            self._table.blockSignals(False)

    # ── counts / accept ──────────────────────────────────────────────────────

    def _update_count(self) -> None:
        n = sum(1 for r in range(self._table.rowCount())
                if self._table.item(r, _COL_PARAM).checkState() == Qt.CheckState.Checked)
        note = ""
        if self._enable_filter.isChecked():
            note = "  ·  value filter ON"
        self._count.setText(
            f"<i>{n} of {self._table.rowCount()} parameter(s) selected{note}</i>")

    def _on_accept(self) -> None:
        if not self.selected_indices():
            QMessageBox.warning(self, "No parameters selected",
                                "Select at least one measurement parameter.")
            return
        # Validate the Min/Max of the checked rows when filtering is on.
        if self._enable_filter.isChecked():
            for r in self._checked_rows():
                name = self._table.item(r, _COL_PARAM).text().split("  ")[0]
                try:
                    mn = float(self._table.item(r, _COL_MIN).text())
                    mx = float(self._table.item(r, _COL_MAX).text())
                except ValueError:
                    QMessageBox.warning(
                        self, "Value filter",
                        f"'{name}' has a non-numeric Min/Max. Fix it or turn the "
                        f"value filter off.")
                    return
                if mn >= mx:
                    QMessageBox.warning(
                        self, "Value filter",
                        f"'{name}' has Min ≥ Max ({mn:g} ≥ {mx:g}).")
                    return
        self.accept()

    # ── results ──────────────────────────────────────────────────────────────

    def _checked_rows(self) -> list[int]:
        return [r for r in range(self._table.rowCount())
                if self._table.item(r, _COL_PARAM).checkState() == Qt.CheckState.Checked]

    def selected_indices(self) -> list[int]:
        return [self._table.item(r, _COL_PARAM).data(_ROLE_INDEX)
                for r in self._checked_rows()]

    def selected_names(self) -> list[str]:
        by_index = {p.index: p.name for p in self._scan.parameters}
        return [by_index[i] for i in self.selected_indices() if i in by_index]

    def selected_filters(self) -> dict[int, tuple[float, float]]:
        """Return ``{column_index: (min, max)}`` for checked rows when the value
        filter is enabled; empty when the filter is off."""
        if not self._enable_filter.isChecked():
            return {}
        out: dict[int, tuple[float, float]] = {}
        for r in self._checked_rows():
            idx = self._table.item(r, _COL_PARAM).data(_ROLE_INDEX)
            try:
                mn = float(self._table.item(r, _COL_MIN).text())
                mx = float(self._table.item(r, _COL_MAX).text())
            except ValueError:
                continue
            if mn < mx:
                out[idx] = (mn, mx)
        return out
