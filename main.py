"""
main.py
=======
Application entry point — launch the PyQt6 GUI.

Usage
-----
    python main.py

Headless / programmatic use (no GUI required)
---------------------------------------------
    from wafer_tool import PlotConfig, generate_report

    config = PlotConfig(t_low=1e-5, t_high=1e-4, use_log=True, high_is_green=True)
    pdf, csv, pptx = generate_report("measurements.csv", config, out_dir="output/")
    print(f"PDF  → {pdf}")
    print(f"CSV  → {csv}")
    print(f"PPTX → {pptx}")
"""
import sys
import matplotlib
matplotlib.use("Agg")   # Non-interactive backend; Qt widgets use their own renderer

from wafer_tool.logger import log, session_start, log_exception

# ── Install global uncaught-exception handler BEFORE importing Qt ─────────────
def _excepthook(exc_type, exc_value, exc_tb):
    log_exception(exc_value, context="uncaught exception")
    sys.__excepthook__(exc_type, exc_value, exc_tb)

sys.excepthook = _excepthook

from PyQt6.QtWidgets import QApplication
from wafer_tool.ui.main_window import DataProcessorUI


def main() -> None:
    # ── Headless mode ────────────────────────────────────────────────────
    # The packaged exe doubles as the scheduled-task / CLI runner. When invoked
    # with a job (``WaferMapTool.exe --run-job job.wtjob`` or a bare
    # ``... job.wtjob``) or ``--test-email addr``, run without a GUI so Windows
    # Task Scheduler and command-line use work from the frozen exe too.
    argv = sys.argv[1:]
    if argv and ("--run-job" in argv or "--test-email" in argv
                 or argv[0].lower().endswith((".wtjob", ".json"))):
        from wafer_tool.automation.runner import main as runner_main
        raise SystemExit(runner_main(argv))

    session_start()
    try:
        app = QApplication(sys.argv)
        window = DataProcessorUI()
        window.show()
        log.info("UI ready")
        sys.exit(app.exec())
    except Exception as exc:
        log_exception(exc, context="main()")
        raise


if __name__ == "__main__":
    main()
