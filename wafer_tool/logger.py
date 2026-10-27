"""
logger.py
=========
Central logging setup for Wafer Map Tool.

All modules import `log` from here.  Log file is written to the same
directory as main.py so it is always easy to find:

    E:\\claude\\Wafer_tool_NEW2\\wafer_tool.log

Each run APPENDS (does not overwrite) so history is preserved.
A visible separator line marks the start of every new session.
"""
from __future__ import annotations

import csv
import logging
import os
import sys
import traceback
from datetime import datetime

# ── Log file location ─────────────────────────────────────────────────────────
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # repo root
LOG_PATH = os.path.join(_ROOT, "wafer_tool.log")
# Structured, one-row-per-run audit log (GUI, headless and scheduled runs).
RUN_LOG_PATH = os.path.join(_ROOT, "run_history.csv")
_RUN_LOG_FIELDS = ("timestamp", "source", "status", "input", "out_dir",
                   "detail", "message")

# ── Formatter ─────────────────────────────────────────────────────────────────
_FMT  = "%(asctime)s  %(levelname)-8s  %(name)s — %(message)s"
_DATEFMT = "%Y-%m-%d %H:%M:%S"

# ── Root logger ───────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.DEBUG,
    format=_FMT,
    datefmt=_DATEFMT,
    handlers=[
        logging.FileHandler(LOG_PATH, encoding="utf-8", mode="a"),
        logging.StreamHandler(sys.stdout),
    ],
)

# Silence noisy third-party loggers
for _noisy in ("matplotlib", "PIL", "fontTools"):
    logging.getLogger(_noisy).setLevel(logging.WARNING)

log: logging.Logger = logging.getLogger("wafer_tool")


def session_start() -> None:
    """Write a visible separator at the top of every new run."""
    sep = "=" * 72
    ts  = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(f"\n{sep}\n  NEW SESSION  {ts}\n{sep}\n")
    log.info("Wafer Map Tool started  (log → %s)", LOG_PATH)


def log_exception(exc: BaseException, context: str = "") -> None:
    """Log a full traceback for any caught exception."""
    tb = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
    log.error("EXCEPTION%s:\n%s", f" in {context}" if context else "", tb)


def log_run(*, source: str, status: str, input: str = "", out_dir: str = "",
            detail: str = "", message: str = "") -> None:
    """Append one row to the run-history CSV, recording every report run
    (GUI, headless ``run_job.py`` or a scheduled task) for auditing.

    Columns: timestamp, source, status, input, out_dir, detail, message.
    A header is written when the file is first created. Never raises — a logging
    failure must not break a run.
    """
    try:
        new = not os.path.exists(RUN_LOG_PATH)
        with open(RUN_LOG_PATH, "a", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            if new:
                writer.writerow(_RUN_LOG_FIELDS)
            writer.writerow([
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                source, status, input, out_dir, detail, message,
            ])
    except OSError as exc:
        log.warning("Could not write run history to %s: %s", RUN_LOG_PATH, exc)

