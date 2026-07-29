"""
eff_param_dialog.py
===================
Modal dialog shown after the user picks an ``.eff`` file.

Lot / Wafer / X / Y are always loaded (they are the map coordinates and are
shown as fixed, non-editable), so the dialog only lets the user choose which
**measurement parameters** to turn into wafer maps.  At least one parameter
must be selected; the maximum is however many the file contains.  Each chosen
parameter later gets its own output folder.
"""
from __future__ import annotations

from typing import Iterable

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import (
    QAbstractItemView, QDialog, QDialogButtonBox, QHBoxLayout, QLabel,
    QLineEdit, QListWidget, QListWidgetItem, QMessageBox, QPushButton,
    QVBoxLayout,
)

from ..eff_loader import EffScan


class EffParameterDialog(QDialog):
    """Pick which measurement parameters to render from an .eff file."""

    def __init__(self, scan: EffScan, parent=None,
                 preselected: Iterable[str] | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Choose Parameters to Map")
        self.resize(560, 560)

        self._scan = scan
        self._items: list[QListWidgetItem] = []
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

        # Filter box
        filt_row = QHBoxLayout()
        filt_row.addWidget(QLabel("Filter:"))
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

        # Parameter list
        self._list = QListWidget()
        self._list.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self._list.setUniformItemSizes(True)
        self._list.setUpdatesEnabled(False)
        try:
            for p in scan.parameters:
                label = f"{p.name}    [{p.dtype or '?'}]"
                if p.has_limits:
                    label += "  (limits)"
                it = QListWidgetItem(label)
                it.setFlags(it.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                checked = (preset is None) or (p.name in preset)
                it.setCheckState(Qt.CheckState.Checked if checked
                                 else Qt.CheckState.Unchecked)
                it.setData(Qt.ItemDataRole.UserRole, p.index)
                it.setData(Qt.ItemDataRole.UserRole + 1, p.name.lower())
                it.setData(Qt.ItemDataRole.UserRole + 2, p.has_limits)
                self._list.addItem(it)
                self._items.append(it)
        finally:
            self._list.setUpdatesEnabled(True)
        root.addWidget(self._list, 1)

        self._count = QLabel()
        self._list.itemChanged.connect(lambda _: self._update_count())
        self._update_count()
        root.addWidget(self._count)

        bb = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        bb.accepted.connect(self._on_accept)
        bb.rejected.connect(self.reject)
        root.addWidget(bb)

    # ── behaviour ──────────────────────────────────────────────────────────

    def _apply_filter(self) -> None:
        needle = self._search.text().strip().lower()
        for it in self._items:
            name = it.data(Qt.ItemDataRole.UserRole + 1) or ""
            it.setHidden(bool(needle) and needle not in name)

    def _set_visible(self, state: Qt.CheckState) -> None:
        self._list.blockSignals(True)
        try:
            for it in self._items:
                if not it.isHidden():
                    it.setCheckState(state)
        finally:
            self._list.blockSignals(False)
        self._update_count()

    def _select_with_limits(self) -> None:
        self._list.blockSignals(True)
        try:
            for it in self._items:
                has = bool(it.data(Qt.ItemDataRole.UserRole + 2))
                it.setCheckState(Qt.CheckState.Checked if has
                                 else Qt.CheckState.Unchecked)
        finally:
            self._list.blockSignals(False)
        self._update_count()

    def _update_count(self) -> None:
        n = sum(1 for it in self._items
                if it.checkState() == Qt.CheckState.Checked)
        self._count.setText(f"<i>{n} of {len(self._items)} parameter(s) selected</i>")

    def _on_accept(self) -> None:
        if not self.selected_indices():
            QMessageBox.warning(
                self, "No parameters selected",
                "Select at least one measurement parameter to generate maps.")
            return
        self.accept()

    # ── results ────────────────────────────────────────────────────────────

    def selected_indices(self) -> list[int]:
        return [it.data(Qt.ItemDataRole.UserRole) for it in self._items
                if it.checkState() == Qt.CheckState.Checked]

    def selected_names(self) -> list[str]:
        by_index = {p.index: p.name for p in self._scan.parameters}
        return [by_index[i] for i in self.selected_indices() if i in by_index]
