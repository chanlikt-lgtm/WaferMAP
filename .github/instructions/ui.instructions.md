---
applyTo: "wafer_tool/ui/**/*.py"
description: "Use when editing the PyQt6 UI layer, previews, widgets, signal wiring, or UI-driven validation in the wafer tool."
---

# UI Instructions

- Keep UI state changes inside the UI layer unless the task is explicitly about shared pipeline behavior.
- Treat `DataProcessorUI` in `wafer_tool/ui/main_window.py` as the integration point for file selection, threshold controls, live preview, histogram/scatter refresh, and worker lifecycle.
- Preserve the current signal flow: UI actions create a `PlotConfig`, start `ReportWorker`, and update controls via Qt signals rather than direct cross-thread widget access.
- If you change parser-facing behavior, check both `_load_preview()` and `_run()` call paths because the UI loads data directly for preview before report generation.
- Keep cancel behavior cooperative. The UI intentionally re-enables controls immediately after cancellation and disconnects worker signals to avoid stale updates.
- Avoid moving heavy work onto the main thread. Preview updates should remain lightweight and background generation should continue to flow through `wafer_tool/worker.py`.
- Keep theme, tab, and preview interactions additive. Do not disable the entire tab widget or remove the user's ability to inspect scatter and histogram views during a run unless the task explicitly requires it.
- Completion-time side effects (email via `_maybe_email`, run-history logging) live in `_on_done` (txt) and `_on_eff_all_done` (EFF). The same side effects also run in the headless `automation/runner.py`; wire any new "on every run" behavior into both places, not just one.
- Email/EFF-filter widget state (the email checkbox, recipients from `EmailRecipientsDialog`, the per-link checkboxes, EFF filter range) is per-session UI state gathered by `_gather_job()`; it is only persisted into a `.wtjob` on Save Job, not loaded back from one.
- When validating UI changes, prefer launching `python main.py` and exercising the touched interaction path over broad static refactors.

## Related Files

- `wafer_tool/worker.py` for background execution and progress/cancel semantics.
- `wafer_tool/config.py` for the `PlotConfig` contract shared with the pipeline.
- `wafer_tool/ui/orientation_widget.py`, `wafer_tool/ui/threshold_viz_widget.py`, and `wafer_tool/ui/histogram_widget.py` for preview widgets owned by the main window.