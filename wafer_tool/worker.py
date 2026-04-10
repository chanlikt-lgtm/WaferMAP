"""
worker.py
=========
PyQt6 worker thread for the wafer report pipeline.

Usage (inside DataProcessorUI or any QWidget)
----------------------------------------------
    from wafer_tool.ui.worker import ReportWorker

    def run_report(self):
        self._worker = ReportWorker(filepath, config, out_dir)

        # Progress bar (0–100)
        self._worker.progress.connect(self.progress_bar.setValue)

        # Status label text
        self._worker.status_message.connect(self.status_label.setText)

        # Live wafer preview
        self._worker.wafer_ready.connect(self._show_wafer_preview)

        # Completion
        self._worker.finished.connect(self._on_report_done)
        self._worker.error.connect(self._on_report_error)

        self._worker.start()

    def _show_wafer_preview(self, lot_id, wafer_id, png_path):
        pix = QPixmap(png_path).scaledToHeight(
            self.preview_label.height(), Qt.TransformationMode.SmoothTransformation
        )
        self.preview_label.setPixmap(pix)

    def _on_report_done(self, pdf_path, csv_path, pptx_path):
        QMessageBox.information(self, "Done", f"PDF saved:\\n{pdf_path}")

    def _on_report_error(self, message):
        QMessageBox.critical(self, "Error", message)

Cancel support
--------------
    self._worker.cancel()     # sets a flag checked between wafers
    # The worker emits error("Cancelled by user.") and exits cleanly.
"""
from __future__ import annotations

import threading

from PyQt6.QtCore import QThread, pyqtSignal

from wafer_tool.config import PlotConfig
from wafer_tool.report import generate_report


class ReportWorker(QThread):
    """
    Run :func:`generate_report` on a background thread.

    Signals
    -------
    progress(int)
        Percentage complete (0–100).  Connect to QProgressBar.setValue.
    status_message(str)
        Human-readable step description.  Connect to a QLabel.
    wafer_ready(str, str, str)
        Emitted after each wafer PNG is written: (lot_id, wafer_id, png_path).
        Use to update a live preview QLabel.
    finished(str, str, str)
        (pdf_path, csv_path, pptx_path) on success.
    error(str)
        Error message on failure or cancellation.
    """

    progress       = pyqtSignal(int)          # 0–100
    status_message = pyqtSignal(str)
    wafer_ready    = pyqtSignal(str, str, str) # lot_id, wafer_id, png_path
    report_done    = pyqtSignal(str, str, str) # pdf, csv, pptx  (renamed to free QThread.finished)
    error          = pyqtSignal(str)

    def __init__(
        self,
        filepath: str,
        config: PlotConfig,
        out_dir: str,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._filepath   = filepath
        self._config     = config
        self._out_dir    = out_dir
        self._cancel_evt = threading.Event()  # thread-safe; plain bool has no memory barrier

    # ------------------------------------------------------------------
    # Public
    # ------------------------------------------------------------------

    def cancel(self) -> None:
        """Request a graceful stop.  Takes effect between wafer renders."""
        self._cancel_evt.set()

    # ------------------------------------------------------------------
    # QThread entry-point
    # ------------------------------------------------------------------

    def run(self) -> None:
        try:
            pdf, csv, pptx = generate_report(
                filepath=self._filepath,
                config=self._config,
                out_dir=self._out_dir,
                on_progress=self._on_progress,
                on_wafer_ready=self._on_wafer_ready,
            )
            if self._cancel_evt.is_set():
                self.error.emit("Cancelled by user.")
            else:
                self.report_done.emit(pdf, csv or "", pptx)
        except Exception as exc:
            self.error.emit(str(exc))

    # ------------------------------------------------------------------
    # Private callbacks (called from inside generate_report)
    # ------------------------------------------------------------------

    def _on_progress(self, current: int, total: int, message: str) -> None:
        """
        Translate (current, total) into a 0–100 percentage and emit signals.
        Also checks the cancellation flag — raises RuntimeError to abort
        the pipeline cleanly if the user pressed Cancel.
        """
        if self._cancel_evt.is_set():
            raise RuntimeError("Cancelled by user.")

        pct = int(current / total * 100) if total > 0 else 0
        self.progress.emit(pct)
        self.status_message.emit(message)

    def _on_wafer_ready(self, lot_id: str, wafer_id: str, png_path: str) -> None:
        """Forward the wafer-ready event to the UI thread via a Qt signal."""
        if not self._cancel_evt.is_set():
            self.wafer_ready.emit(lot_id, wafer_id, png_path)
