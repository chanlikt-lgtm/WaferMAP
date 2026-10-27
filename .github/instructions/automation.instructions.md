---
applyTo: "wafer_tool/automation/**/*.py,run_job.py"
description: "Use when editing headless job execution, the .wtjob format, or Windows Task Scheduler integration."
---

# Automation Instructions

- This layer runs offline with no GUI and no Qt event loop. Do not import UI modules (`wafer_tool/ui/**`) or start a `QApplication` from `runner.py`, `job.py`, or `scheduler.py`.
- `job.py` owns the `.wtjob` JSON format (`WaferJob` dataclass, `save_job`/`load_job`). Keep it backward compatible: when adding a field, give it a default and preserve the `format`/`version` metadata so older job files still load.
- Keep `WaferJob.plot_config_kwargs()` in sync with the `PlotConfig` contract in `wafer_tool/config.py`. UI and headless runs must produce identical reports from the same config.
- Support all three input modes in `runner.py`: fixed file (`input_file`), folder-mode (`input_dir` + `input_pattern`, resolves the newest match at run time), and raw `.eff` (dispatches to `wafer_tool/eff_pipeline.py`).
- Preserve the exit-code contract in `runner.py` (`EXIT_OK`, `EXIT_ERROR`, `EXIT_USAGE`, `EXIT_MISSING_INPUT`, `EXIT_NO_MATCH_IN_FOLDER`, `EXIT_BAD_JOB`, `EXIT_BAD_OUTPUT`, etc.). Windows Task Scheduler surfaces these as `LastTaskResult`, and `scheduler_dialog._STATUS_MAP` maps them to status text — changing a value is a breaking change and needs the map updated too.
- `WaferJob.precheck()` validates input resolves/exists and the output folder (or its parent) exists; `runner.main()` returns `EXIT_BAD_OUTPUT` when the output is unreachable. The GUI runs the same `precheck()` on Save Job.
- Keep scheduler task naming stable: `scheduler.task_name_for()` produces `WaferTool_Job_<safe_name>`. Renaming the scheme orphans existing scheduled tasks.
- `run_job.py` must keep inserting the repo root into `sys.path` before importing `wafer_tool`, because the scheduler can start the task from any working directory.

## Email notification

- Email fires only when `WaferJob.wants_email()` is true — i.e. `email_enabled` is set AND `email_to` is non-empty. The GUI runs the same email path from its completion handlers, so `notify.py` behavior must stay GUI/headless agnostic.
- Which links are included is per-job: `email_pdf` / `email_pptx` / `email_folder` (all default `True`). `runner._report_tuple()` blanks a link when its flag is off; `notify` omits any blank link from the message. The folder link is the output folder that holds all files (`out_dir` for txt, the parameter folder for EFF).
- Two backends, chosen by `WAFERTOOL_EMAIL_BACKEND` (`outlook` or `smtp`); default prefers Outlook when the `pywin32` COM bridge is importable, else SMTP. `notify.select_backend()` owns this rule.
- **Outlook backend** (`send_via_outlook`): sends through the locally installed Outlook using the signed-in profile — no host or password. Requires `pywin32` (optional dep, Windows-only). Caveat: Outlook must be able to run for the mail to leave the Outbox, so it is unsuitable for run-while-logged-off scheduled tasks — use SMTP there.
- **SMTP backend**: settings come from environment variables only (never the `.wtjob`): `WAFERTOOL_SMTP_HOST` (required), `WAFERTOOL_SMTP_PORT`, `WAFERTOOL_SMTP_USER`, `WAFERTOOL_SMTP_PASSWORD`, `WAFERTOOL_SMTP_FROM`, `WAFERTOOL_SMTP_SECURITY` (`none`/`starttls`/`ssl`, inferred from port when unset).
- Links are `file://` URLs plus absolute paths, so outputs should live on a shared drive. txt jobs force `render_individual_pngs=True` when email is on so the PNG folder exists; EFF param folders already contain flattened PNGs.
- A mail failure must only log a `[WARN]` and never change the job's exit code — a good report should still report success.
- Verify delivery without running a job: `python run_job.py --test-email <addr[,addr2]>`.

## Validation

- Run the unit tests after changes: `python -m pytest wafer_tool/automation/test_automation.py`.
- For end-to-end checks, run a sample job headlessly: `python run_job.py wafer_job.wtjob`.

## Related Files

- `wafer_tool/report.py` and `wafer_tool/eff_pipeline.py` are the pipelines `runner.py` drives.
- `wafer_tool/config.py` for the shared `PlotConfig` contract.
- Example jobs: `wafer_job.wtjob` (fixed `.txt`) and `C5 VBD.wtjob` (raw `.eff`, multi-parameter).
