"""Headless job launcher for scheduled wafer-tool tasks:

    python run_job.py <job.wtjob>

Adds this folder to sys.path so ``wafer_tool`` imports no matter what working
directory the Windows scheduler starts the task in, then runs the report
offline (no GUI / no network). Analogous to the eff-converter run_job.py.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from wafer_tool.automation.runner import main

if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
