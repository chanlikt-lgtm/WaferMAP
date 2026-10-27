# AGENTS.md

This repository is a Windows-first Python desktop app for wafer-map visualization and report generation.

## Start Here

- Treat `Wafer_tool_slim/` as the repository root. If VS Code is opened at the parent `Wafer MAP/` folder, change into `Wafer_tool_slim` before running commands.
- Run the GUI with `python main.py`.
- Run a saved job headlessly (no GUI) with `python run_job.py <job.wtjob>`.
- Install dependencies with `pip install -r requirements.txt`.
- Build Windows executables with `py -m PyInstaller WaferMapTool.spec --noconfirm` or `py -m PyInstaller WaferMapTool_folder.spec --noconfirm`.
- Generate the bundled technical documentation with `py generate_docs.py`.
- The only automated tests cover the automation layer: `python -m pytest wafer_tool/automation/test_automation.py`. There is no lint or typecheck command. For code outside `automation/`, prefer validating the narrowest affected flow directly.

## Code Layout

- `main.py` is the GUI entry point.
- `wafer_tool/ui/main_window.py` owns the PyQt6 application shell, previews, and user interactions.
- `wafer_tool/worker.py` runs report generation on a background `QThread` and emits Qt signals for progress, completion, and cancellation.
- `wafer_tool/report.py` is the main orchestration boundary for report generation.
- `wafer_tool/data_loader.py` handles parsing and normalization of measurement files.
- `wafer_tool/geometry.py` contains pure math and coordinate transforms.
- `wafer_tool/statistics.py` contains wafer classification and summary-chart logic.
- `wafer_tool/config.py` defines the shared `PlotConfig` and `ColorScheme` contract.
- `wafer_tool/exporters/` contains format-specific export code for PDF, CSV, and PPTX outputs.
- `wafer_tool/eff_loader.py`, `eff_pipeline.py`, and `eff_worker.py` handle raw `.eff` (eSquare) files: scan headers, extract per-parameter data, and run one report per selected parameter.
- `wafer_tool/automation/` is the headless/scheduling layer: `job.py` defines the `.wtjob` JSON format, `runner.py` executes a job offline (used by `run_job.py`), and `scheduler.py`/`scheduler_dialog.py` wire jobs into Windows Task Scheduler.
- `waferplot_ORIN/` contains Origin comparison and verification utilities; avoid changing it unless the task is specifically about Origin parity.

## Working Conventions

- Keep changes localized to the owning layer. UI changes belong in `wafer_tool/ui/`; report pipeline changes usually belong in `wafer_tool/report.py` or a lower-level module.
- Treat `PlotConfig` as the shared contract between UI state and the report pipeline.
- Preserve the current memory-conscious style in the data and report pipeline. Avoid introducing unnecessary copies of large `DataFrame`s or plot images.
- The app uses Matplotlib's `Agg` backend for non-interactive rendering. Do not switch global backends casually.
- Prefer updating current modules over reviving legacy files such as `wafer_tool/data_loader_OLD.py` and `wafer_tool/statistics_old.py`.
- Keep optional PPTX behavior graceful. `python-pptx` may be unavailable in some environments even though it is listed in `requirements.txt`.

## Pitfalls

- The UI is not a thin wrapper around `generate_report()`. It also reads wafer data directly for preview, histogram, and threshold visualization, so parser changes can affect both preview and export behavior.
- **Two run paths exist and must stay in sync.** The GUI runs via `wafer_tool/worker.py` (`ReportWorker`) and `wafer_tool/eff_worker.py` (`EffReportWorker`); headless/scheduled runs go through `wafer_tool/automation/runner.py`. A behavior that should happen on *every* run (e.g. sending email, run-history logging) must be wired into BOTH the GUI completion handlers (`main_window._on_done` / `_on_eff_all_done`) and the runner — adding it to only one silently skips the other.
- **The frozen exe is also the headless runner.** `main.py` routes `--run-job <job>`, `--test-email`, or a bare `*.wtjob`/`*.json` argument to `wafer_tool.automation.runner.main` instead of opening the GUI; the scheduler invokes the frozen build as `WaferMapTool.exe --run-job <job>`. Do not remove this dispatch.
- Cancellation is cooperative. `ReportWorker.cancel()` only stops between wafer renders.
- Logging is mixed with some direct console output in parts of the pipeline. Be careful when changing error-reporting behavior because the app is also packaged as a GUI executable. `runner._force_utf8_stdout()` exists because scheduled tasks get a cp1252 stdout pipe that would otherwise crash on the pipeline's check/cross glyphs.
- The PPTX exporter looks for an external theme template. If that asset is missing, generation should still fall back cleanly.
- Every run appends a row to `run_history.csv` via `logger.log_run()`; the general log is `wafer_tool.log`. Keep both writes non-fatal.

## Documentation Notes

- Read `README.md` for the high-level overview, but prefer the code when they disagree. The README currently lags the implementation in a few places.
- Notable mismatches:
  - The README's project tree is outdated; `main.py` and `requirements.txt` live at the repo root.
  - The UI layer does more than just call `generate_report()`.
  - The worker module docstring still references an old import path.
  - Version strings are inconsistent across files.

## Change Guidance

- For parser or configuration changes, check both `wafer_tool/report.py` and `wafer_tool/ui/main_window.py` call paths before editing.
- For packaging issues, inspect the `.spec` files and `generate_docs.py` before changing import or asset behavior. See [.github/instructions/packaging.instructions.md](.github/instructions/packaging.instructions.md) — some excludes (`scipy`, `unittest`) will crash the exe if removed from the build.
- For output regressions, validate with a small real input file from the repo root when possible instead of relying on broad manual inspection.
- Do not add broad new infrastructure such as test frameworks, formatters, or packaging changes unless the task explicitly asks for it.

## Reference

- High-level overview: [README.md](README.md)
- Scoped instructions: [.github/instructions/ui.instructions.md](.github/instructions/ui.instructions.md)
- Scoped instructions: [.github/instructions/pipeline.instructions.md](.github/instructions/pipeline.instructions.md)
- Scoped instructions: [.github/instructions/automation.instructions.md](.github/instructions/automation.instructions.md)
- Scoped instructions: [.github/instructions/packaging.instructions.md](.github/instructions/packaging.instructions.md)