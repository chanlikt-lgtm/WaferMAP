"""Automation for the wafer tool: save a run as a job, run it offline, schedule it.

Mirrors the eff-converter / ADAML automation. A job (.wtjob) bundles the input
data file, output directory and every PlotConfig setting; the runner replays it
headless via ``wafer_tool.generate_report`` (no GUI); the scheduler registers a
Windows task that runs it daily / weekly / monthly, fully offline.
"""
from .job import WaferJob, JOB_SUFFIX, save_job, load_job
from .runner import run_job

__all__ = ["WaferJob", "JOB_SUFFIX", "save_job", "load_job", "run_job"]
