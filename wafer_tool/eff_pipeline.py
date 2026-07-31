"""
eff_pipeline.py
===============
GUI-free orchestration for turning one ``.eff`` file into wafer-map reports for
a set of measurement parameters.  Shared by:

* :mod:`wafer_tool.eff_worker`      — the PyQt background worker (interactive), and
* :mod:`wafer_tool.automation.runner` — the headless / scheduled runner.

Keeping the logic here (not in the Qt worker) means the interactive and the
automated paths behave identically: same extraction, same "drop empty
parameters" rule, same per-parameter folder + PNG-flatten.

``process_eff`` streams the file once (one text file per parameter), then runs
the existing :func:`wafer_tool.report.generate_report` for each parameter into
its own folder.  Progress and cancellation are surfaced through plain callables
so neither Qt nor a console is required.
"""
from __future__ import annotations

import os
from typing import Callable

from .config import PlotConfig
from .eff_loader import (
    EffScan, ExtractedParameter, extract_parameters, flatten_param_pngs, scan_eff,
)
from .logger import log
from .report import generate_report

__all__ = ["process_eff", "EffCancelled", "resolve_indices"]

# progress(overall_pct, wafer_pct_or_None, message)
ProgressCallback = Callable[[int, "int | None", str], None]
WaferReadyCallback = Callable[[str, str, str], None]
ParamDoneCallback = Callable[[str, str], None]

# Share of the overall progress bar given to the one-pass extraction phase.
_EXTRACT_SHARE = 0.30


class EffCancelled(Exception):
    """Raised to unwind the pipeline when a caller's ``stop_cb`` returns True."""


def resolve_indices(scan: EffScan, names: list[str] | None) -> tuple[list[int], list[str]]:
    """Map requested parameter *names* to column indices in *scan*.

    ``names`` empty / None means "every measurement parameter in the file" — the
    automation-friendly default so a scheduled job maps whatever the newest drop
    contains.  Returns ``(indices, missing_names)``; unknown names are skipped
    (and reported) rather than aborting the whole run.
    """
    if not names:
        return [p.index for p in scan.parameters], []
    wanted = list(dict.fromkeys(names))            # de-dup, preserve order
    by_name: dict[str, int] = {}
    for p in scan.parameters:                      # first occurrence wins
        by_name.setdefault(p.name, p.index)
    indices = [by_name[n] for n in wanted if n in by_name]
    missing = [n for n in wanted if n not in by_name]
    return indices, missing


def process_eff(
    eff_path: str,
    indices: list[int],
    config: PlotConfig,
    out_dir: str,
    *,
    scan: EffScan | None = None,
    filters: dict[int, tuple[float, float]] | None = None,
    progress: ProgressCallback | None = None,
    on_wafer_ready: WaferReadyCallback | None = None,
    on_param_done: ParamDoneCallback | None = None,
    stop_cb: Callable[[], bool] | None = None,
) -> list[tuple[str, str, str, str]]:
    """Extract *indices* from *eff_path* and report each into its own folder.

    Returns a list of ``(param_name, folder, pdf_path, pptx_path)`` — one entry
    per parameter that yielded data.  ``pptx_path`` is "" when python-pptx is
    unavailable.
    """
    os.makedirs(out_dir, exist_ok=True)
    scan = scan or scan_eff(eff_path)
    if not indices:
        raise ValueError("No parameters selected to process.")

    def _emit(overall: int, wafer: "int | None", message: str) -> None:
        if progress is not None:
            progress(overall, wafer, message)

    def _check_cancel() -> None:
        if stop_cb is not None and stop_cb():
            raise EffCancelled()

    # ── Phase 1: one streaming pass → one txt per parameter ────────────────
    _emit(0, None, "Reading EFF and splitting parameters…")
    extract_cap = int(_EXTRACT_SHARE * 100)

    def _extract_progress(done: int, total: int) -> None:
        _check_cancel()
        pct = int(done / total * extract_cap) if total else 0
        _emit(min(pct, extract_cap), None, f"Reading EFF… {done:,} / {total:,} rows")

    extracted = extract_parameters(
        eff_path, indices, out_dir, scan=scan, filters=filters,
        progress_cb=_extract_progress, stop_cb=stop_cb,
    )
    _check_cancel()

    usable = [e for e in extracted if e.rows_written > 0]
    if not usable:
        raise ValueError(
            "None of the selected parameters contained any valid data rows.")

    # ── Phase 2: report each parameter into its own folder ─────────────────
    results: list[tuple[str, str, str, str]] = []
    n = len(usable)
    report_share = 1.0 - _EXTRACT_SHARE
    for i, param in enumerate(usable):
        _check_cancel()
        base = _EXTRACT_SHARE + report_share * (i / n)
        slice_ = report_share / n
        _emit(int(base * 100), None, f"[{i + 1}/{n}] {param.name}: generating report…")

        def _on_progress(cur: int, total: int, message: str,
                         _base=base, _slice=slice_, _i=i, _name=param.name) -> None:
            # generate_report treats a RuntimeError from here as a cancel and
            # re-raises it; anything else it swallows, so cancel MUST be a
            # RuntimeError to actually abort the render.
            if stop_cb is not None and stop_cb():
                raise RuntimeError("Cancelled by user.")
            frac = (cur / total) if total else 0.0
            wafer_pct: "int | None" = None
            wafer_total = max(total - 3, 1)
            if message.startswith("Rendering"):
                wafer_pct = min(int(cur / wafer_total * 100), 99)
            elif any(k in message for k in ("PDF", "CSV", "PowerPoint", "Done")):
                wafer_pct = 100
            _emit(int((_base + _slice * frac) * 100), wafer_pct,
                  f"[{_i + 1}/{n}] {_name}: {message}")

        try:
            pdf, _csv, pptx = generate_report(
                filepath=param.txt_path,
                config=config,
                out_dir=param.folder,
                on_progress=_on_progress,
                on_wafer_ready=on_wafer_ready,
                # Always emit the per-wafer PNGs so each parameter folder holds
                # its images even on headless / scheduled runs (where no live
                # preview is attached to trigger them).
                render_individual_pngs=True,
            )
        except RuntimeError as exc:
            if "Cancel" in str(exc):
                raise EffCancelled() from exc
            raise

        # Keep images alongside the PDF / PPTX / CSV in the one folder.
        flatten_param_pngs(param.folder)
        results.append((param.name, param.folder, pdf,
                        pptx if os.path.isfile(pptx) else ""))
        if on_param_done is not None:
            on_param_done(param.name, param.folder)

    _emit(100, 100, "Done")
    log.info("process_eff: %d parameter(s) reported from %s",
             len(results), os.path.basename(eff_path))
    return results
