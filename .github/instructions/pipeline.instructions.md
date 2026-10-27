---
applyTo: "wafer_tool/{report,data_loader,geometry,statistics,worker}.py,wafer_tool/exporters/**/*.py"
description: "Use when editing the wafer report pipeline, parsing, geometry, statistics, worker callbacks, or export code."
---

# Pipeline Instructions

- Keep responsibilities separated: `data_loader.py` parses input, `geometry.py` handles transforms/math, `statistics.py` computes summaries, `report.py` orchestrates, and `exporters/` format outputs.
- Prefer fixing behavior at the owning layer instead of compensating in `report.py` for lower-level issues.
- Preserve the memory-conscious style in parsing and rendering code. Avoid unnecessary `DataFrame` copies, keep `float32` and categorical usage where practical, and release temporary plotting objects promptly.
- `generate_report()` is the orchestration boundary. Keep progress reporting, wafer-ready callbacks, and cleanup behavior compatible with `wafer_tool/worker.py`.
- Treat callback failures defensively. UI callback problems should not crash the pipeline except for intentional cancellation via `RuntimeError`.
- Keep PPTX generation optional and degradable. If you touch `pptx_exporter.py` or PPTX call sites, preserve clean fallback behavior when `python-pptx` or the theme template is unavailable.
- Be careful with logging and console output because this code runs both from the GUI and from packaged executables.
- Do not modify `data_loader_OLD.py` or `statistics_old.py` unless the task explicitly targets legacy code.

## Validation

- Prefer a narrow real-input validation path over broad refactors: run the touched pipeline path with a small sample file from the repo root when available.
- For parsing changes, validate both direct `read_wafer_data()` behavior and the UI preview path.
- For report/export changes, validate at least one end-to-end `generate_report()` or GUI run if the environment allows it.

## Related Files

- `main.py` for the GUI entry point.
- `wafer_tool/ui/main_window.py` for the caller that constructs `PlotConfig` and consumes worker signals.
- `README.md` for a high-level overview, but prefer code when it conflicts with implementation.