"""Schedule Jobs dialog for the wafer tool (PyQt6).

A table of scheduled wafer-tool tasks plus a panel to schedule a saved .wtjob
daily / weekly / monthly, run one now, or remove it. Mirrors the eff-converter
scheduler dialog; everything it schedules runs offline via Windows Task Scheduler.
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

from PyQt6.QtCore import QTime
from PyQt6.QtWidgets import (
    QAbstractItemView, QComboBox, QDialog, QFileDialog, QHBoxLayout, QHeaderView,
    QLabel, QMessageBox, QPushButton, QSpinBox, QTableWidget, QTableWidgetItem,
    QTimeEdit, QVBoxLayout,
)

from . import scheduler


class SchedulerDialog(QDialog):
    def __init__(self, parent=None, initial_job: str | None = None):
        super().__init__(parent)
        self.setWindowTitle("Schedule Jobs")
        self.setMinimumSize(780, 460)
        self._selected_job_path: str | None = initial_job
        self._jobs: list = []

        root = QVBoxLayout(self)

        self._table = QTableWidget(0, 5)
        self._table.setHorizontalHeaderLabels(
            ["Task", "Job file", "Next run", "State", "Last result"])
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.Stretch)
        self._table.itemSelectionChanged.connect(self._on_row_selected)
        root.addWidget(self._table)

        row_btns = QHBoxLayout()
        for text, slot in (("Refresh", self._refresh), ("Run Now", self._run_selected),
                           ("Remove", self._remove_selected)):
            b = QPushButton(text)
            b.clicked.connect(slot)
            if text == "Refresh":
                row_btns.addWidget(b); row_btns.addStretch()
            else:
                row_btns.addWidget(b)
        root.addLayout(row_btns)

        root.addWidget(QLabel(
            "Schedule a .wtjob daily, weekly or monthly — or select a row above to "
            "edit its schedule, then Schedule to update it:"))
        new_row = QHBoxLayout()
        btn_pick = QPushButton("Choose .wtjob…")
        btn_pick.clicked.connect(self._pick_job)
        self._lbl_job = QLabel(Path(initial_job).name if initial_job else "(no job selected)")

        self._mode = QComboBox()
        self._mode.addItems(["Daily", "Weekly", "Monthly"])
        self._mode.setCurrentText("Weekly")
        self._mode.currentTextChanged.connect(self._on_mode_changed)

        self._day = QComboBox()
        self._day.addItems(scheduler.DAYS)
        self._day.setCurrentText("Sunday")

        self._dom = QSpinBox()
        self._dom.setRange(1, 31)
        self._dom.setValue(1)
        self._dom.setVisible(False)

        self._time = QTimeEdit(QTime(10, 0))
        self._time.setDisplayFormat("HH:mm")
        btn_schedule = QPushButton("Schedule")
        btn_schedule.clicked.connect(self._schedule)

        new_row.addWidget(btn_pick)
        new_row.addWidget(self._lbl_job)
        new_row.addStretch()
        new_row.addWidget(self._mode)
        self._lbl_every = QLabel("every")
        new_row.addWidget(self._lbl_every)
        new_row.addWidget(self._day)
        new_row.addWidget(self._dom)
        new_row.addWidget(QLabel("at"))
        new_row.addWidget(self._time)
        new_row.addWidget(btn_schedule)
        root.addLayout(new_row)

        close_row = QHBoxLayout()
        close_row.addStretch()
        btn_close = QPushButton("Close")
        btn_close.clicked.connect(self.accept)
        close_row.addWidget(btn_close)
        root.addLayout(close_row)

        self._refresh()

    def _refresh(self) -> None:
        jobs = scheduler.list_jobs()
        self._jobs = jobs
        self._table.setRowCount(len(jobs))
        for r, j in enumerate(jobs):
            vals = [j.task_name, Path(j.job_path).name if j.job_path else "?",
                    j.next_run or "—", j.state,
                    "OK" if j.last_result == 0 else f"code {j.last_result}"]
            for c, v in enumerate(vals):
                self._table.setItem(r, c, QTableWidgetItem(v))

    def _selected_task(self) -> str | None:
        rows = self._table.selectionModel().selectedRows()
        return self._table.item(rows[0].row(), 0).text() if rows else None

    def _on_row_selected(self) -> None:
        rows = self._table.selectionModel().selectedRows()
        if not rows:
            return
        row = rows[0].row()
        if not (0 <= row < len(self._jobs)):
            return
        j = self._jobs[row]
        if j.job_path:
            self._selected_job_path = j.job_path
            self._lbl_job.setText(Path(j.job_path).name)
        try:
            dt = datetime.strptime(j.next_run, "%Y-%m-%d %H:%M")
        except (ValueError, TypeError):
            return
        self._day.setCurrentText(dt.strftime("%A"))
        self._dom.setValue(dt.day)
        self._time.setTime(QTime(dt.hour, dt.minute))

    def _pick_job(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Choose Job", "", "Wafer Job (*.wtjob);;All Files (*)")
        if path:
            self._selected_job_path = path
            self._lbl_job.setText(Path(path).name)

    def _on_mode_changed(self, mode: str) -> None:
        self._day.setVisible(mode == "Weekly")
        self._dom.setVisible(mode == "Monthly")
        self._lbl_every.setVisible(mode != "Daily")
        self._lbl_every.setText("on day" if mode == "Monthly" else "every")

    def _schedule(self) -> None:
        if not self._selected_job_path:
            QMessageBox.information(self, "Schedule", "Choose a .wtjob file first.")
            return
        name = Path(self._selected_job_path).stem
        t = self._time.time()
        mode = self._mode.currentText()
        if mode == "Daily":
            when = "every day"
            ok, msg = scheduler.schedule_daily(
                self._selected_job_path, name, t.hour(), t.minute())
        elif mode == "Monthly":
            when = f"day {self._dom.value()} of each month"
            ok, msg = scheduler.schedule_monthly(
                self._selected_job_path, name, self._dom.value(), t.hour(), t.minute())
        else:
            when = f"every {self._day.currentText()}"
            ok, msg = scheduler.schedule_weekly(
                self._selected_job_path, name, self._day.currentText(), t.hour(), t.minute())
        if ok:
            QMessageBox.information(
                self, "Schedule",
                f"Scheduled '{name}' {when} at {t.toString('HH:mm')}.\n"
                f"Runs offline via Windows Task Scheduler.\nTask: {msg}")
            self._refresh()
        else:
            QMessageBox.warning(self, "Schedule failed", msg)

    def _run_selected(self) -> None:
        task = self._selected_task()
        if not task:
            QMessageBox.information(self, "Run Now", "Select a scheduled job first.")
            return
        if scheduler.run_now(task):
            QMessageBox.information(
                self, "Run Now",
                f"Started {task} in the background.\nRefresh to see its result.")
        else:
            QMessageBox.warning(self, "Run Now", f"Could not start {task}.")

    def _remove_selected(self) -> None:
        task = self._selected_task()
        if not task:
            QMessageBox.information(self, "Remove", "Select a scheduled job first.")
            return
        if QMessageBox.question(self, "Remove", f"Remove scheduled job {task}?") \
                != QMessageBox.StandardButton.Yes:
            return
        if scheduler.remove_job(task):
            self._refresh()
        else:
            QMessageBox.warning(self, "Remove", f"Could not remove {task}.")
