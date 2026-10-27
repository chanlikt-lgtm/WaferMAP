"""
eff_param_dialog.py
===================
Modal dialog shown after the user picks an ``.eff`` file.

Lot / Wafer / X / Y are always loaded (they are the map coordinates and are
shown as fixed, non-editable), so the dialog only lets the user choose which
**measurement parameters** to turn into wafer maps.  At least one parameter
must be selected; the maximum is however many the file contains.  Each chosen
parameter later gets its own output folder.

The parameters are shown in a table so their **spec limits** (Lower / Upper,
read from the ``<LIMIT:SPEC:...>`` header rows) are visible beside each name.
A single, global **value filter** sits beside the spec columns: when enabled,
measurement values outside ``[min, max]`` are dropped during import so they
never reach the wafer map.  It is prefilled from the file's spec limits and is
fully editable.
"""
from __future__ import annotations

from typing import Iterable

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import (
    QAbstractItemView, QCheckBox, QDialog, QDialogButtonBox, QHBoxLayout,
    QHeaderView, QLabel, QLineEdit, QMessageBox, QPushButton, QTableWidget,
    QTableWidgetItem, QVBoxLayout,
)

from ..eff_loader import EffScan

# Table columns.
_COL_NAME = 0
_COL_TYPE = 1
_COL_LOWER = 2
_COL_UPPER = 3


def _fmt(value: float | None) -> str:
    """Scientific-notation display for a spec limit (trailing zeros trimmed),
    or an em dash when absent. e.g. 10 -> '1E+01', 30.5 -> '3.05E+01'."""
    if value is None:
        return "—"
    mantissa, exponent = f"{value:.6E}".split("E")
    mantissa = mantissa.rstrip("0").rstrip(".")
    return f"{mantissa}E{exponent}"



class EffParameterDialog(QDialog):
    """Pick which measurement parameters to render from an .eff file."""

    def __init__(self, scan: EffScan, parent=None,
                 preselected: Iterable[str] | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Choose Parameters to Map")
        self.resize(640, 600)

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
            f"Tick the measurement parameters to turn into wafer maps "
            f"(at least one). Each becomes its own output folder."
        )
        header.setWordWrap(True)
        root.addWidget(header)

        # Filter-by-name box
        filt_row = QHBoxLayout()
        filt_row.addWidget(QLabel("Find:"))
        self._search = QLineEdit()
        self._search.setPlaceholderText("type to filter parameter names…")
        self._filter_timer = QTimer(self)
        self._filter_timer.setSingleShot(True)
        self._filter_timer.setInterval(150)
        self._filter_timer.timeout.connect(self._apply_filter)
        self._search.textChanged.connect(lambda _: self._filter_timer.start())
        filt_row.addWidget(self._search)
        root.addLayout(filt_row)

        # Quick-select buttons
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

        # Parameter table: name (checkable) | type | spec lower | spec upper
        self._table = QTableWidget(len(scan.parameters), 4)
        self._table.setHorizontalHeaderLabels(
            ["Parameter", "Type", "Spec Lower", "Spec Upper"])
        self._table.verticalHeader().setVisible(False)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        hh = self._table.horizontalHeader()
        hh.setSectionResizeMode(_COL_NAME, QHeaderView.ResizeMode.Stretch)
        for c in (_COL_TYPE, _COL_LOWER, _COL_UPPER):
            hh.setSectionResizeMode(c, QHeaderView.ResizeMode.ResizeToContents)

        self._table.setUpdatesEnabled(False)
        try:
            for r, p in enumerate(scan.parameters):
                name_it = QTableWidgetItem(p.name)
                name_it.setFlags(Qt.ItemFlag.ItemIsUserCheckable
                                 | Qt.ItemFlag.ItemIsEnabled)
                checked = (preset is None) or (p.name in preset)
                name_it.setCheckState(Qt.CheckState.Checked if checked
                                      else Qt.CheckState.Unchecked)
                name_it.setData(Qt.ItemDataRole.UserRole, p.index)
                name_it.setData(Qt.ItemDataRole.UserRole + 1, p.name.lower())
                name_it.setData(Qt.ItemDataRole.UserRole + 2, p.has_limits)
                self._table.setItem(r, _COL_NAME, name_it)
                self._table.setItem(r, _COL_TYPE, QTableWidgetItem(p.dtype or "?"))
                low = QTableWidgetItem(_fmt(p.limit_lower))
                up = QTableWidgetItem(_fmt(p.limit_upper))
                align = Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
                low.setTextAlignment(align)
                up.setTextAlignment(align)
                self._table.setItem(r, _COL_LOWER, low)
                self._table.setItem(r, _COL_UPPER, up)
        finally:
            self._table.setUpdatesEnabled(True)
        root.addWidget(self._table, 1)

        # ── Global value filter (beside the spec columns) ──────────────────
        # Default to a ±1000 guard band, enabled; the spec columns above stay
        # for reference. Edit or uncheck as needed.
        default_min, default_max = -1000.0, 1000.0
        filt = QHBoxLayout()
        self._filter_chk = QCheckBox("Apply value filter — drop values outside")
        self._filter_chk.setToolTip(
            "When checked, any measurement value below Min or above Max is dropped "
            "during import for every selected parameter, so it never reaches the "
            "wafer map. Defaults to ±1000; edit as needed.")
        self._min_edit = QLineEdit(); self._min_edit.setPlaceholderText("Min")
        self._min_edit.setFixedWidth(90)
        self._max_edit = QLineEdit(); self._max_edit.setPlaceholderText("Max")
        self._max_edit.setFixedWidth(90)
        self._min_edit.setText(str(int(default_min)))
        self._max_edit.setText(str(int(default_max)))
        self._filter_chk.setChecked(True)
        self._filter_chk.toggled.connect(self._min_edit.setEnabled)
        self._filter_chk.toggled.connect(self._max_edit.setEnabled)
        filt.addWidget(self._filter_chk)
        filt.addWidget(QLabel("Min:")); filt.addWidget(self._min_edit)
        filt.addWidget(QLabel("Max:")); filt.addWidget(self._max_edit)
        filt.addStretch(1)
        root.addLayout(filt)

        self._count = QLabel()
        self._table.itemChanged.connect(lambda _: self._update_count())
        self._update_count()
        root.addWidget(self._count)

        bb = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        bb.accepted.connect(self._on_accept)
        bb.rejected.connect(self.reject)
        root.addWidget(bb)

    # ── helpers ────────────────────────────────────────────────────────────

    def _name_items(self):
        for r in range(self._table.rowCount()):
            yield r, self._table.item(r, _COL_NAME)

    # ── behaviour ──────────────────────────────────────────────────────────

    def _apply_filter(self) -> None:
        needle = self._search.text().strip().lower()
        for r, it in self._name_items():
            name = it.data(Qt.ItemDataRole.UserRole + 1) or ""
            self._table.setRowHidden(r, bool(needle) and needle not in name)

    def _set_visible(self, state: Qt.CheckState) -> None:
        self._table.blockSignals(True)
        try:
            for r, it in self._name_items():
                if not self._table.isRowHidden(r):
                    it.setCheckState(state)
        finally:
            self._table.blockSignals(False)
        self._update_count()

    def _select_with_limits(self) -> None:
        self._table.blockSignals(True)
        try:
            for _r, it in self._name_items():
                has = bool(it.data(Qt.ItemDataRole.UserRole + 2))
                it.setCheckState(Qt.CheckState.Checked if has
                                 else Qt.CheckState.Unchecked)
        finally:
            self._table.blockSignals(False)
        self._update_count()

    def _update_count(self) -> None:
        n = sum(1 for _r, it in self._name_items()
                if it.checkState() == Qt.CheckState.Checked)
        self._count.setText(
            f"<i>{n} of {self._table.rowCount()} parameter(s) selected</i>")

    def _parse_filter(self) -> tuple[float | None, float | None] | None:
        """Return (min, max) when the filter is enabled and valid, (None, None)
        when disabled, or None when the inputs are invalid (a message is shown)."""
        if not self._filter_chk.isChecked():
            return (None, None)
        try:
            fmin = float(self._min_edit.text().strip())
            fmax = float(self._max_edit.text().strip())
        except ValueError:
            QMessageBox.warning(
                self, "Invalid filter range",
                "Enter numeric Min and Max values, or uncheck the value filter.")
            return None
        if fmin >= fmax:
            QMessageBox.warning(
                self, "Invalid filter range", "Filter Min must be less than Max.")
            return None
        return (fmin, fmax)

    def _on_accept(self) -> None:
        if not self.selected_indices():
            QMessageBox.warning(
                self, "No parameters selected",
                "Select at least one measurement parameter to generate maps.")
            return
        if self._parse_filter() is None:
            return
        self.accept()

    # ── results ────────────────────────────────────────────────────────────

    def selected_indices(self) -> list[int]:
        return [it.data(Qt.ItemDataRole.UserRole) for _r, it in self._name_items()
                if it.checkState() == Qt.CheckState.Checked]

    def selected_names(self) -> list[str]:
        by_index = {p.index: p.name for p in self._scan.parameters}
        return [by_index[i] for i in self.selected_indices() if i in by_index]

    def filter_range(self) -> tuple[float | None, float | None]:
        """The enabled (min, max) value filter, or (None, None) when disabled."""
        parsed = self._parse_filter()
        return parsed if parsed is not None else (None, None)

