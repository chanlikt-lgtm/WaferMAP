"""Replay a saved .wtjob headlessly: build the PlotConfig and run the report.

No GUI is created — this drives ``wafer_tool.generate_report`` directly (which
uses the matplotlib Agg backend), so it runs offline from a scheduled task or
the command line. Invoke via the app-root launcher (run_job.py) or:

    python -m wafer_tool.automation.runner <job.wtjob>
"""
from __future__ import annotations

import sys
from pathlib import Path

from .job import load_job


def _force_utf8_stdout() -> None:
    """The pipeline prints check/cross glyphs; under a scheduled task stdout is a
    cp1252 pipe and those raise UnicodeEncodeError. Make stdout/stderr UTF-8 and
    error-tolerant so a scheduled run can never die on a console print."""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass


def run_job(job_path: str | Path, *, progress=None) -> tuple[str, str | None, str]:
    """Load a .wtjob and generate its report. Returns (pdf, csv, pptx)."""
    from wafer_tool import PlotConfig, generate_report

    job = load_job(job_path)
    config = PlotConfig(**job.plot_config_kwargs())
    input_file = job.resolve_input_file()   # newest-in-folder jobs pick the latest file here

    def on_progress(cur, total, msg):
        line = f"[{cur}/{total}] {msg}"
        if progress:
            progress(line)
        else:
            print(line, flush=True)

    return generate_report(input_file, config, job.out_dir, on_progress=on_progress)


def main(argv: list[str] | None = None) -> int:
    _force_utf8_stdout()
    args = argv if argv is not None else sys.argv[1:]
    # Accept both "--run-job <job>" and a bare "<job>".
    job = None
    if args:
        job = args[args.index("--run-job") + 1] if "--run-job" in args else args[0]
    if not job:
        print("usage: python -m wafer_tool.automation.runner <job.wtjob>", file=sys.stderr)
        return 2
    try:
        pdf, csv, pptx = run_job(job)
    except Exception as exc:  # surfaced as a non-zero exit for the scheduler
        print(f"job failed: {exc}", file=sys.stderr)
        return 1
    print(f"PDF  -> {pdf}")
    print(f"CSV  -> {csv}")
    print(f"PPTX -> {pptx}")
    return 0 if pdf else 3


if __name__ == "__main__":
    raise SystemExit(main())
