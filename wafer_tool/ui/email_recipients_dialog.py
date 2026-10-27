"""
email_recipients_dialog.py
==========================
Small popup for managing the notification recipient list as a table — one email
address per row, with Add / Remove — instead of a single comma-separated line.
Returned by :meth:`recipients` as a de-duplicated list.
"""
from __future__ import annotations

from typing import Iterable

from PyQt6.QtWidgets import (
    QAbstractItemView, QDialog, QDialogButtonBox, QHBoxLayout, QHeaderView,
    QLabel, QMessageBox, QPushButton, QTableWidget, QTableWidgetItem,
    QVBoxLayout,
)


def _looks_like_email(text: str) -> bool:
    """A light sanity check (not full RFC 5322): one @, a dotted domain, no
    spaces. Good enough to catch typos before a job is saved."""
    text = text.strip()
    if text.count("@") != 1 or " " in text:
        return False
    local, _, domain = text.partition("@")
    return bool(local) and "." in domain and not domain.startswith(".") \
        and not domain.endswith(".")


class EmailRecipientsDialog(QDialog):
    """Edit the list of notification recipients in a small table."""

    def __init__(self, recipients: Iterable[str] | None = None, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Email Recipients")
        self.resize(440, 340)

        root = QVBoxLayout(self)
        root.addWidget(QLabel(
            "One email address per row. These receive the report links when "
            "the job finishes (including scheduled runs)."))

        self._table = QTableWidget(0, 1)
        self._table.setHorizontalHeaderLabels(["Email address"])
        self._table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Stretch)
        self._table.verticalHeader().setVisible(False)
        self._table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows)
        root.addWidget(self._table, 1)

        btn_row = QHBoxLayout()
        add = QPushButton("＋  Add")
        rem = QPushButton("－  Remove")
        add.clicked.connect(self._add_row)
        rem.clicked.connect(self._remove_selected)
        btn_row.addWidget(add)
        btn_row.addWidget(rem)
        btn_row.addStretch(1)
        root.addLayout(btn_row)

        for addr in (recipients or []):
            self._append(addr)
        if self._table.rowCount() == 0:
            self._add_row()

        bb = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel)
        bb.accepted.connect(self._on_accept)
        bb.rejected.connect(self.reject)
        root.addWidget(bb)

    # ── behaviour ──────────────────────────────────────────────────────────

    def _append(self, text: str = "") -> None:
        r = self._table.rowCount()
        self._table.insertRow(r)
        self._table.setItem(r, 0, QTableWidgetItem(text))

    def _add_row(self) -> None:
        self._append("")
        r = self._table.rowCount() - 1
        self._table.setCurrentCell(r, 0)
        self._table.editItem(self._table.item(r, 0))

    def _remove_selected(self) -> None:
        rows = sorted({i.row() for i in self._table.selectedIndexes()},
                      reverse=True)
        for r in rows:
            self._table.removeRow(r)

    def _collected(self) -> list[str]:
        seen: list[str] = []
        for r in range(self._table.rowCount()):
            it = self._table.item(r, 0)
            val = it.text().strip() if it else ""
            if val and val not in seen:
                seen.append(val)
        return seen

    def _on_accept(self) -> None:
        bad = [e for e in self._collected() if not _looks_like_email(e)]
        if bad:
            QMessageBox.warning(
                self, "Invalid address",
                "These don't look like valid emails:\n  " + "\n  ".join(bad))
            return
        self.accept()

    # ── result ─────────────────────────────────────────────────────────────

    def recipients(self) -> list[str]:
        """The de-duplicated, non-empty addresses entered."""
        return self._collected()
