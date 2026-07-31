"""
eff_worker.py
=============
PyQt background thread that turns one ``.eff`` file into wafer-map reports for a
set of selected measurement parameters.

The real work lives in :func:`wafer_tool.eff_pipeline.process_eff` (GUI-free, and
shared with the headless / scheduled runner).  This worker is only a thin Qt
adapter: it forwards ``process_eff``'s progress / wafer / done callbacks onto Qt
signals and maps the cooperative ``stop_cb`` onto a cancel event, so the
interactive and automated paths run identical logic.

Signals mirror :class:`wafer_tool.worker.ReportWorker` (so the main window can
reuse its live-preview / progress plumbing), plus ``all_done`` carrying the
per-parameter results.
"""
from __future__ import annotations

import threading

from PyQt6.QtCore import QThread, pyqtSignal

from .config import PlotConfig
from .eff_loader import EffScan, extract_single_param_df
from .eff_pipeline import EffCancelled, process_eff
from .logger import log, log_exception


class EffReportWorker(QThread):
    """Extract selected parameters from an .eff and report each into its own folder."""

    progress       = pyqtSignal(int)              # 0–100 overall
    wafer_progress = pyqtSignal(int)              # 0–100 current parameter's render
    status_message = pyqtSignal(str)
    wafer_ready    = pyqtSignal(str, str, str)    # lot, wafer, png_path
    param_done     = pyqtSignal(str, str)         # param_name, folder
    all_done       = pyqtSignal(list)             # list[(param, folder, pdf, pptx)]
    error          = pyqtSignal(str)

    def __init__(
        self,
        eff_path: str,
        indices: list[int],
        config: PlotConfig,
        out_dir: str,
        scan: EffScan | None = None,
        filters: dict[int, tuple[float, float]] | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._eff_path = eff_path
        self._indices = list(indices)
        self._config = config
        self._out_dir = out_dir
        self._scan = scan
        self._filters = filters
        self._cancel_evt = threading.Event()

    # ── public ──────────────────────────────────────────────────────────────

    def cancel(self) -> None:
        self._cancel_evt.set()

    # ── QThread entry point ─────────────────────────────────────────────────

    def run(self) -> None:
        log.info("EffReportWorker started file=%s params=%d out=%s",
                 self._eff_path, len(self._indices), self._out_dir)
        try:
            results = process_eff(
                self._eff_path,
                self._indices,
                self._config,
                self._out_dir,
                scan=self._scan,
                filters=self._filters,
                progress=self._on_progress,
                on_wafer_ready=self._on_wafer,
                on_param_done=self.param_done.emit,
                stop_cb=self._cancel_evt.is_set,
            )
            if self._cancel_evt.is_set():
                self.error.emit("Cancelled by user.")
            else:
                self.all_done.emit(results)
        except EffCancelled:
            self.error.emit("Cancelled by user.")
        except Exception as exc:                       # noqa: BLE001
            log_exception(exc, context="EffReportWorker.run")
            self.error.emit(str(exc))

    # ── process_eff callbacks → Qt signals ──────────────────────────────────

    def _on_progress(self, overall: int, wafer: "int | None", message: str) -> None:
        self.progress.emit(overall)
        if wafer is not None:
            self.wafer_progress.emit(wafer)
        if message:
            self.status_message.emit(message)

    def _on_wafer(self, lot: str, wid: str, png: str) -> None:
        if not self._cancel_evt.is_set():
            self.wafer_ready.emit(lot, wid, png)


class EffPreviewWorker(QThread):
    """Read ONE parameter of an .eff in the background for the chart preview.

    Emits ``ready(df, param_name)`` with a lot/wafer/x/y/value DataFrame the
    scatter + histogram can consume, or ``failed(message)``.  Kept separate from
    the report worker so selecting an EFF never blocks the UI while a large file
    is read.
    """

    ready  = pyqtSignal(object, int)   # DataFrame, param column index
    failed = pyqtSignal(str)

    def __init__(self, eff_path: str, index: int, name: str,
                 scan: EffScan | None = None, max_rows: int | None = None,
                 value_range: tuple[float, float] | None = None,
                 parent=None) -> None:
        super().__init__(parent)
        self._eff_path = eff_path
        self._index = index
        self._name = name
        self._scan = scan
        self._max_rows = max_rows
        self._value_range = value_range
        self._cancel_evt = threading.Event()

    def cancel(self) -> None:
        self._cancel_evt.set()

    def run(self) -> None:
        try:
            df = extract_single_param_df(
                self._eff_path, self._index, scan=self._scan,
                max_rows=self._max_rows, value_range=self._value_range,
                stop_cb=self._cancel_evt.is_set,
            )
            if not self._cancel_evt.is_set():
                self.ready.emit(df, self._index)
        except Exception as exc:                       # noqa: BLE001
            if not self._cancel_evt.is_set():
                self.failed.emit(str(exc))
