"""Replay a saved .wtjob headlessly: build the PlotConfig and run the report.

No GUI is created — this drives ``wafer_tool.generate_report`` directly (which
uses the matplotlib Agg backend), so it runs offline from a scheduled task or
the command line. Invoke via the app-root launcher (run_job.py) or:

    python -m wafer_tool.automation.runner <job.wtjob>
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

from .job import load_job
from ..logger import log_run

# Exit codes surfaced to Windows Task Scheduler as LastTaskResult, so the
# Schedule Jobs dialog can show a meaningful per-job status. Keep in sync with
# scheduler_dialog._status_for().
EXIT_OK = 0                 # report generated
EXIT_ERROR = 1              # unexpected error during generation
EXIT_USAGE = 2              # no job path given
EXIT_NO_OUTPUT = 3          # ran but produced no PDF
EXIT_MISSING_INPUT = 10     # the job's input file (e.g. .eff) does not exist
EXIT_NO_MATCH_IN_FOLDER = 11  # folder-mode job: nothing matched the pattern
EXIT_BAD_JOB = 12           # the .wtjob file is missing / invalid
EXIT_BAD_OUTPUT = 13        # the output folder is unreachable (parent missing)


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
    """Load a .wtjob and generate its report.

    Returns ``(pdf, csv, pptx)``.  For a raw ``.eff`` job this maps one or more
    parameters, each into its own output folder; the returned tuple then refers
    to the *last* parameter processed (its ``pdf`` still drives the exit code),
    and every parameter folder is printed as it completes.
    """
    job = load_job(job_path)
    input_file = job.resolve_input_file()   # newest-in-folder jobs pick the latest file here
    return _run_loaded(job, input_file, progress=progress)


def _run_loaded(job, input_file: str, *, progress=None) -> tuple[str, str | None, str]:
    """Generate the report for an already-loaded job + resolved input file."""
    from wafer_tool import PlotConfig, generate_report

    config = PlotConfig(**job.plot_config_kwargs())

    def _log(line: str) -> None:
        if progress:
            progress(line)
        else:
            print(line, flush=True)

    if job.is_eff_input(input_file):
        return _run_eff_job(job, input_file, config, _log)

    def on_progress(cur, total, msg):
        _log(f"[{cur}/{total}] {msg}")

    # Force the per-wafer PNGs only when the recipients want a folder link (so
    # the output folder actually contains the images); otherwise stay fast.
    render_pngs = True if (job.wants_email() and job.email_folder) else None
    pdf, csv, pptx = generate_report(input_file, config, job.out_dir,
                                     on_progress=on_progress,
                                     render_individual_pngs=render_pngs,
                                     filter_min=job.eff_filter_min,
                                     filter_max=job.eff_filter_max)
    if job.wants_email():
        label = os.path.splitext(os.path.basename(input_file))[0]
        # Folder link points at out_dir, which holds the PDF/CSV/PPTX (and the
        # per-wafer PNG subfolder) — i.e. all the files for this run.
        _notify(job, [_report_tuple(job, label, pdf, pptx, job.out_dir)], _log)
    return pdf, csv, pptx


def _run_eff_job(job, input_file, config, log_line) -> tuple[str, str | None, str]:
    """Map the requested parameters of a raw .eff file (one folder each)."""
    from wafer_tool.eff_loader import scan_eff
    from wafer_tool.eff_pipeline import process_eff, resolve_indices

    scan = scan_eff(input_file)
    indices, missing = resolve_indices(scan, job.eff_params)
    if missing:
        log_line(f"[WARN] parameter(s) not in {os.path.basename(input_file)}, "
                 f"skipped: {', '.join(missing)}")
    if not indices:
        raise ValueError(
            f"no matching parameters to map in {os.path.basename(input_file)} "
            f"(requested: {job.eff_params or 'all'})")

    which = "all parameters" if not job.eff_params else f"{len(indices)} parameter(s)"
    log_line(f"EFF job: {os.path.basename(input_file)} -> {which}")

    _last = {"pct": -1}

    def on_progress(overall: int, wafer, message: str) -> None:
        # Sparse logging: only when the whole-number percent advances.
        if overall != _last["pct"]:
            _last["pct"] = overall
            log_line(f"[{overall}%] {message}")

    results = process_eff(input_file, indices, config, job.out_dir,
                          scan=scan, progress=on_progress,
                          filter_min=job.eff_filter_min,
                          filter_max=job.eff_filter_max)

    log_line(f"Done: {len(results)} parameter folder(s) written under {job.out_dir}")
    for name, folder, pdf, pptx in results:
        log_line(f"  - {name}: {folder}")

    # Record the run so a later interactive (GUI) run of the same unchanged .eff
    # can warn the user. Automation itself never prompts.
    try:
        from wafer_tool.eff_loader import record_eff_run
        record_eff_run(input_file, job.out_dir,
                       [folder for _n, folder, _p, _q in results])
    except Exception:
        pass

    if job.wants_email():
        # Each EFF parameter folder holds that parameter's PDF/PPTX/CSV/PNGs.
        _notify(job, [_report_tuple(job, name, pdf, pptx, folder)
                      for name, folder, pdf, pptx in results], log_line)

    if not results:
        return "", None, ""
    _name, _folder, pdf, pptx = results[-1]
    return pdf, None, pptx


def _report_tuple(job, label: str, pdf: str, pptx: str, folder: str):
    """(label, pdf, pptx, folder) with each link blanked when the job disables
    it, so the email only includes the requested link types."""
    return (label,
            pdf if job.email_pdf else "",
            pptx if job.email_pptx else "",
            folder if job.email_folder else "")


def _notify(job, report_tuples, log_line) -> None:
    """Email the job's recipients links to each report's requested outputs
    (PDF / PPTX / output folder). A mail failure is logged but never fails an
    otherwise-good run.

    ``report_tuples`` is a list of ``(label, pdf, pptx, folder)``.
    """
    if not job.wants_email():
        return
    try:
        from .notify import Report, EmailNotConfigured, send_report_email
    except Exception as exc:  # pragma: no cover - defensive import guard
        log_line(f"[WARN] email module unavailable: {exc}")
        return

    reports = [Report(label=label, pdf=pdf, pptx=pptx, folder=folder)
               for (label, pdf, pptx, folder) in report_tuples]
    first = reports[0].label if reports else "report"
    extra = f" (+{len(reports) - 1} more)" if len(reports) > 1 else ""
    subject = f"Wafer report ready: {first}{extra}"
    try:
        send_report_email(job.email_to, subject, reports)
        log_line(f"Email sent to {', '.join(job.email_to)}")
    except EmailNotConfigured as exc:
        log_line(f"[WARN] email requested but not configured: {exc}. "
                 f"Set WAFERTOOL_SMTP_HOST (and related) to enable it.")
    except Exception as exc:
        log_line(f"[WARN] email not sent: {exc}")


def main(argv: list[str] | None = None) -> int:
    _force_utf8_stdout()
    args = argv if argv is not None else sys.argv[1:]

    # "--test-email <addr[,addr2]>": send a one-off confirmation email and exit,
    # so a user can verify delivery before scheduling any job.
    if "--test-email" in args:
        try:
            addrs = args[args.index("--test-email") + 1]
        except IndexError:
            print("usage: --test-email <addr[,addr2,...]>", file=sys.stderr)
            return EXIT_USAGE
        recipients = [a for a in addrs.replace(";", ",").split(",") if a.strip()]
        from .notify import send_test_email
        try:
            backend = send_test_email(recipients)
        except Exception as exc:
            print(f"test email failed: {exc}", file=sys.stderr)
            return EXIT_ERROR
        print(f"test email sent to {', '.join(recipients)} via {backend}")
        return EXIT_OK

    # Accept both "--run-job <job>" and a bare "<job>".
    job = None
    if args:
        job = args[args.index("--run-job") + 1] if "--run-job" in args else args[0]
    if not job:
        print("usage: python -m wafer_tool.automation.runner <job.wtjob>", file=sys.stderr)
        return EXIT_USAGE

    # Each step maps to a distinct exit code so the scheduler UI can say *why*
    # a run failed (missing input vs. bad job vs. other error).
    try:
        wafer_job = load_job(job)
    except Exception as exc:
        print(f"bad job file: {exc}", file=sys.stderr)
        log_run(source="headless", status="BAD_JOB", input=str(job),
                message=str(exc))
        return EXIT_BAD_JOB

    try:
        input_file = wafer_job.resolve_input_file()
    except FileNotFoundError as exc:
        print(f"no matching input file in folder: {exc}", file=sys.stderr)
        log_run(source="headless", status="NO_MATCH_IN_FOLDER",
                input=wafer_job.input_dir or wafer_job.input_file,
                out_dir=wafer_job.out_dir, message=str(exc))
        return EXIT_NO_MATCH_IN_FOLDER

    detail = (f"eff:{','.join(wafer_job.eff_params) or 'all'}"
              if wafer_job.is_eff_input(input_file) else "txt")

    if not os.path.isfile(input_file):
        print(f"input file not found: {input_file}", file=sys.stderr)
        log_run(source="headless", status="MISSING_INPUT", input=input_file,
                out_dir=wafer_job.out_dir, detail=detail)
        return EXIT_MISSING_INPUT

    # Pre-check the output folder is reachable (exists, or its parent does so it
    # can be created) before starting a long report.
    out_dir = Path(wafer_job.out_dir)
    if not wafer_job.out_dir or not (out_dir.exists() or out_dir.parent.exists()):
        print(f"output folder unavailable (parent missing): {wafer_job.out_dir}",
              file=sys.stderr)
        log_run(source="headless", status="BAD_OUTPUT", input=input_file,
                out_dir=wafer_job.out_dir, detail=detail)
        return EXIT_BAD_OUTPUT

    try:
        pdf, csv, pptx = _run_loaded(wafer_job, input_file)
    except FileNotFoundError as exc:
        print(f"input file not found: {exc}", file=sys.stderr)
        log_run(source="headless", status="MISSING_INPUT", input=input_file,
                out_dir=wafer_job.out_dir, detail=detail, message=str(exc))
        return EXIT_MISSING_INPUT
    except Exception as exc:  # surfaced as a non-zero exit for the scheduler
        print(f"job failed: {exc}", file=sys.stderr)
        log_run(source="headless", status="ERROR", input=input_file,
                out_dir=wafer_job.out_dir, detail=detail, message=str(exc))
        return EXIT_ERROR

    print(f"PDF  -> {pdf}")
    print(f"CSV  -> {csv}")
    print(f"PPTX -> {pptx}")
    log_run(source="headless", status="OK" if pdf else "NO_OUTPUT",
            input=input_file, out_dir=wafer_job.out_dir, detail=detail,
            message=pdf or "no PDF produced")
    return EXIT_OK if pdf else EXIT_NO_OUTPUT


if __name__ == "__main__":
    raise SystemExit(main())
