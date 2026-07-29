"""
report.py
=========
High-level pipeline that orchestrates the full report generation workflow.

Responsibilities
----------------
- Load and validate data.
- Compute 8-condition statistics.
- Render individual wafer PNG files and per-page snapshots for PPTX export.
- Call each exporter (PDF → CSV → PPTX) in sequence.
- Clean up temporary directories.

Public API
----------
generate_report(filepath, config, out_dir,
                on_progress=None, on_wafer_ready=None) -> tuple[str, str | None, str]

Callback signatures
-------------------
on_progress(current: int, total: int, message: str) -> None
    Called once per wafer rendered plus once each for PDF/CSV/PPTX steps.
    Safe to call from any thread; connect to a Qt signal in the UI layer.

on_wafer_ready(lot_id: str, wafer_id: str, png_path: str) -> None
    Called immediately after a wafer PNG is written to disk.
    The UI can load it as a QPixmap for a live preview.
"""
from __future__ import annotations

import gc
import os
import shutil
from datetime import datetime
from typing import Callable

import matplotlib
matplotlib.use("Agg")          # non-interactive; safe on worker threads
import matplotlib.pyplot as plt

from .config import PlotConfig
from .data_loader import read_wafer_data
from .logger import log, log_exception
from .plotting import draw_wafer_ax
from .statistics import calculate_8_condition_statistics
from .exporters.pdf_exporter import generate_pdf
from .exporters.csv_exporter import export_color_summary_csv
from .exporters.pptx_exporter import create_powerpoint_report, HAS_PPTX

__all__ = ["generate_report"]

# Type aliases for readability
ProgressCallback   = Callable[[int, int, str], None]
WaferReadyCallback = Callable[[str, str, str], None]


def generate_report(
    filepath: str,
    config: PlotConfig,
    out_dir: str,
    on_progress: ProgressCallback | None = None,
    on_wafer_ready: WaferReadyCallback | None = None,
    render_individual_pngs: bool | None = None,
    jobs: int | None = None,
) -> tuple[str, str | None, str]:
    """
    End-to-end report pipeline.

    Parameters
    ----------
    filepath : str
        Path to the raw measurement file.
    config   : PlotConfig
        All user-specified plotting parameters.
    out_dir  : str
        Root output directory (must already exist or be creatable).
    on_progress : callable(current, total, message), optional
        Progress callback invoked after each wafer PNG is rendered and after
        each export step (PDF, CSV, PPTX).  Safe to emit from a QThread.
    on_wafer_ready : callable(lot_id, wafer_id, png_path), optional
        Called immediately after each wafer PNG is written to disk, allowing
        the UI to display a live preview without waiting for the full report.

    Returns
    -------
    (pdf_path, csv_path, pptx_path_or_message) : tuple[str, str | None, str]
        - pdf_path   : absolute path to the generated PDF.
        - csv_path   : absolute path to the colour summary CSV (or None).
        - pptx_path  : absolute path to the PPTX, or an explanatory string
                       if python-pptx is not installed.

    Raises
    ------
    ValueError
        If the data file cannot be read or produces no valid rows.
    """
    # ── Load data ─────────────────────────────────────────────────────────
    data = read_wafer_data(filepath)
    if data is None or data.empty:
        raise ValueError(f"Failed to read or parse data from: {filepath}")

    # ── Count renderable wafers for accurate progress reporting ───────────
    wafer_pairs = list(data.groupby(["lot", "wafer"]).groups.keys())
    # Wafer renders + PDF + CSV + PPTX
    total_steps = len(wafer_pairs) + 3
    log.info("Pipeline: %d wafers to render, out_dir=%s", len(wafer_pairs), out_dir)
    del wafer_pairs  # only needed for the count

    # ── Pre-compute statistics ────────────────────────────────────────────
    condition_result = calculate_8_condition_statistics(data, config)

    # ── Set up directories ────────────────────────────────────────────────
    timestamp   = datetime.now().strftime("%Y_%m_%d_%H%M%S")
    base_name   = os.path.splitext(os.path.basename(filepath))[0]
    png_dir     = os.path.join(out_dir, f"individual_pngs_{timestamp}")

    pptx_page_dir = None

    # The per-wafer "individual" PNGs exist only to feed a live GUI preview via
    # on_wafer_ready — nothing in the PDF/CSV/PPTX uses them. So render them only
    # when someone is watching. Headless/scheduled runs (no on_wafer_ready) skip
    # this whole pass, which was ~40% of the runtime. Callers can force it either
    # way with render_individual_pngs=True/False.
    want_pngs = (on_wafer_ready is not None) if render_individual_pngs is None \
        else bool(render_individual_pngs)
    if want_pngs:
        os.makedirs(png_dir, exist_ok=True)
        if HAS_PPTX:
            pptx_page_dir = os.path.join(out_dir, f"temp_pptx_pages_{timestamp}")
            os.makedirs(pptx_page_dir, exist_ok=True)
        _render_wafer_pngs(
            data, config,
            png_dir=png_dir,
            total_steps=total_steps,
            on_progress=on_progress,
            on_wafer_ready=on_wafer_ready,
            jobs=jobs,
        )
        gc.collect()  # release matplotlib figure cache accumulated during render loop
    elif HAS_PPTX:
        pptx_page_dir = os.path.join(out_dir, f"temp_pptx_pages_{timestamp}")
        os.makedirs(pptx_page_dir, exist_ok=True)

    current_step = total_steps - 3

    # ── PDF ───────────────────────────────────────────────────────────────
    current_step += 1
    _emit(on_progress, current_step, total_steps, "Generating PDF…")
    pdf_path = generate_pdf(
        data=data,
        config=config,
        condition_result=condition_result,
        filepath=filepath,
        out_dir=out_dir,
        timestamp=timestamp,
        page_png_dir=pptx_page_dir if HAS_PPTX else None,
        jobs=jobs,
        on_page=lambda d, t: _emit(on_progress, current_step, total_steps,
                                   f"Generating PDF… page {d}/{t}"),
    )
    print(f"✓ PDF saved: {pdf_path}")

    # ── CSV ───────────────────────────────────────────────────────────────
    current_step += 1
    _emit(on_progress, current_step, total_steps, "Exporting CSV…")
    csv_path = export_color_summary_csv(filepath, config, out_dir, data=data)

    # data is no longer needed — free it before the PPTX step which only
    # reads pre-rendered PNGs from disk.
    del data
    gc.collect()

    # ── PowerPoint ────────────────────────────────────────────────────────
    current_step += 1
    if HAS_PPTX and pptx_page_dir is not None:
        _emit(on_progress, current_step, total_steps, "Building PowerPoint…")
        pptx_path = os.path.join(
            out_dir, f"{base_name}{config.log_suffix}_{timestamp}.pptx"
        )
        try:
            create_powerpoint_report(pptx_page_dir, pptx_path, base_name)
        finally:
            _safe_rmtree(pptx_page_dir)
    else:
        _emit(on_progress, current_step, total_steps, "Skipping PowerPoint (not installed)")
        pptx_path = (
            "PowerPoint NOT generated — "
            "install python-pptx first:  pip install python-pptx"
        )

    _emit(on_progress, total_steps, total_steps, "Done")
    return pdf_path, csv_path, pptx_path


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

# Process-pool spawn on Windows re-imports matplotlib in every worker (~7 s of
# fixed overhead), so parallel PNG rendering only pays off for large reports.
# Measured crossover is ~160 wafers (100: 0.57x slower; 500: 1.94x faster), so
# we stay sequential below this and only spin up workers when they clearly win.
_PNG_PARALLEL_MIN = 200


def _render_one_wafer_png(job: tuple) -> tuple:
    """Render ONE wafer's square archive PNG. Top-level + picklable so it can
    run in a spawned worker process. Returns (lot_id, wafer_id, path, valid)."""
    lot_id, wid, out_path, config, sub = job

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as _plt

    fig = None
    valid = False
    try:
        fig, ax = _plt.subplots(figsize=(8, 8), dpi=100)
        fig.subplots_adjust(left=0, right=1, top=1, bottom=0)
        valid = draw_wafer_ax(ax, sub, wid, config,
                              show_legend=False, show_title=False)
        if valid:
            fig.savefig(out_path, bbox_inches="tight", pad_inches=0)
    except Exception:
        valid = False
    finally:
        if fig is not None:
            _plt.close(fig)
    return (lot_id, wid, out_path, valid)


def _render_wafer_pngs(
    data,
    config: PlotConfig,
    png_dir: str,
    total_steps: int,
    on_progress: ProgressCallback | None,
    on_wafer_ready: WaferReadyCallback | None,
    jobs: int | None = None,
) -> None:
    """
    Render one square archive PNG per valid wafer.

    These per-wafer maps are independent, so they render in parallel across
    worker processes (each does its own grid interpolation + savefig) — the
    same strategy the PDF grid pages use. Results are consumed in submission
    order so the live GUI preview still fills lot-by-lot; small reports fall
    back to sequential rendering where spawn overhead wouldn't pay off.

    jobs : None → auto (min(cpu_count, 8)); 1 → sequential; N → N workers.
    """
    # Build one job per wafer, in lot→wafer order. The slice keeps only the
    # numeric columns so the pickle sent to a worker stays tiny (no category
    # index dragged along).
    render_jobs: list[tuple] = []
    for lot_id, lot_df in data.groupby("lot"):
        for wid, w_df in lot_df.groupby("wafer"):
            filename = f"{lot_id}_{wid}{config.log_suffix}.png"
            sub = w_df[["x", "y", "value"]].copy()
            render_jobs.append(
                (str(lot_id), str(wid), os.path.join(png_dir, filename), config, sub)
            )

    total = len(render_jobs)
    if total == 0:
        return

    def _consume(step: int, result: tuple) -> None:
        lot_id, wid, out_path, valid = result
        _emit(on_progress, step, total_steps, f"Rendering {lot_id} W{wid}…")
        if valid:
            if on_wafer_ready is not None:
                on_wafer_ready(lot_id, wid, out_path)   # live preview, in order
        else:
            log.warning("Skipped lot=%s wafer=%s — too few points", lot_id, wid)

    want = (jobs is None or jobs > 1)
    n_workers = jobs if (jobs and jobs > 1) else (os.cpu_count() or 1)
    n_workers = max(1, min(n_workers, 8, total))

    if want and n_workers > 1 and total >= _PNG_PARALLEL_MIN:
        try:
            from concurrent.futures import ProcessPoolExecutor
            with ProcessPoolExecutor(max_workers=n_workers) as ex:
                # ex.map preserves submission order, so previews stay ordered.
                for step, result in enumerate(ex.map(_render_one_wafer_png, render_jobs), 1):
                    _consume(step, result)
            return
        except Exception as exc:  # pool unavailable / worker crash → sequential
            print(f"⚠  Parallel PNG render failed ({exc}); using sequential.")

    for step, job in enumerate(render_jobs, 1):
        _consume(step, _render_one_wafer_png(job))


def _emit(
    callback: ProgressCallback | None,
    current: int,
    total: int,
    message: str,
) -> None:
    """Fire the progress callback if one is connected.
    Re-raises RuntimeError so cancellation propagates out of the pipeline."""
    if callback is not None:
        try:
            callback(current, total, message)
        except RuntimeError:
            raise   # cancellation signal — let it propagate
        except Exception:
            pass    # never let other UI callback errors crash the pipeline


def _safe_rmtree(path: str) -> None:
    """Remove a directory tree, ignoring any errors."""
    try:
        shutil.rmtree(path)
    except Exception as exc:
        print(f"⚠  Could not remove temp directory '{path}': {exc}")
