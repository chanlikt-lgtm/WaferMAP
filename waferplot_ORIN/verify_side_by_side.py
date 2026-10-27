"""
verify_side_by_side.py
======================
Side-by-side visual verification of Python/Matplotlib vs. OriginLab
wafer map outputs.

For each wafer requested, this module:
  1. Generates a Python/Matplotlib PNG  (wafer_tool.plotting.draw_wafer_ax)
  2. Generates an Origin PNG            (origin_wafer_exporter)
  3. Stitches them side-by-side with    difference metrics and saves a
     comparison PNG.

Output folder layout
--------------------
<out_dir>/
    python_pngs/    <wafer_id>_python.png
    origin_pngs/    <wafer_id>_origin.png
    comparisons/    <wafer_id>_compare.png  ← side-by-side diff

Public API
----------
verify_wafer(data_df, wafer_id, config, out_dir) -> Path | None
    Generate all three images for one wafer.

verify_lot(data_file, config, out_dir, max_wafers) -> list[Path]
    Run verify_wafer for up to max_wafers wafers from a data file.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import matplotlib
matplotlib.use("Agg")                   # headless – no GUI window
import matplotlib.pyplot as plt
import matplotlib.image as mpimg

# ── Project root on path ───────────────────────────────────────────────────
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from wafer_tool.config import PlotConfig
from wafer_tool.plotting import draw_wafer_ax
from .origin_wafer_exporter import export_wafer_as_origin_png

__all__ = ["verify_wafer", "verify_lot"]


# ---------------------------------------------------------------------------
# Python-side PNG generation
# ---------------------------------------------------------------------------

def _python_png(df, wafer_id: str, config: PlotConfig, out_png: Path) -> bool:
    """
    Render one wafer with Python/Matplotlib and save to *out_png*.

    Uses the same draw_wafer_ax() function called by the production pipeline
    so the output is bit-for-bit identical to the main report renders.
    """
    fig, ax = plt.subplots(figsize=(4, 4), dpi=100)
    fig.patch.set_facecolor("white")
    success = draw_wafer_ax(
        ax, df, wafer_id, config,
        show_legend=False, show_title=True,
    )
    out_png.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(str(out_png), bbox_inches="tight", dpi=100, facecolor="white")
    plt.close(fig)
    return success


# ---------------------------------------------------------------------------
# Comparison image
# ---------------------------------------------------------------------------

def _make_comparison(
    py_png: Path,
    orig_png: Path,
    comp_png: Path,
    wafer_label: str,
) -> None:
    """
    Create a 3-panel comparison figure:
      Panel 1 : Python/Matplotlib output
      Panel 2 : OriginLab output
      Panel 3 : Absolute pixel-difference heat-map (RMSE annotated)

    The RMSE is computed on the RGB channels after resizing both images
    to the same pixel dimensions for a fair comparison.
    """
    img_py   = _load_rgb(py_png)
    img_orig = _load_rgb(orig_png)

    # Resize Origin image to match Python image dimensions for diff
    img_orig_r = _resize_to(img_orig, img_py.shape[:2])

    # Absolute difference across RGB channels
    diff = np.abs(img_py.astype(float) - img_orig_r.astype(float))
    rmse = float(np.sqrt(np.mean(diff ** 2)))

    fig, axes = plt.subplots(1, 3, figsize=(15, 5))
    fig.patch.set_facecolor("white")
    fig.suptitle(
        f"Side-by-Side Verification  |  Wafer: {wafer_label}",
        fontsize=13, fontweight="bold", y=1.01,
    )

    axes[0].imshow(img_py)
    axes[0].set_title("Python / Matplotlib", fontsize=11, fontweight="bold")
    axes[0].axis("off")

    axes[1].imshow(img_orig)
    axes[1].set_title("OriginLab (Origin 2021)", fontsize=11, fontweight="bold")
    axes[1].axis("off")

    # Difference panel – normalise to [0, 255] range for visibility
    diff_norm = (diff.mean(axis=2) / 255.0)  # mean over RGB channels, 0-1
    im = axes[2].imshow(diff_norm, cmap="hot", vmin=0, vmax=1)
    axes[2].set_title(
        f"Pixel Difference  (RMSE = {rmse:.1f})", fontsize=11, fontweight="bold"
    )
    axes[2].axis("off")
    plt.colorbar(im, ax=axes[2], fraction=0.046, pad=0.04,
                 label="Abs diff / 255")

    plt.tight_layout(rect=[0, 0, 1, 0.97])
    comp_png.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(str(comp_png), dpi=120, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def _load_rgb(path: Path) -> np.ndarray:
    """Load a PNG as an (H, W, 3) uint8 RGB array."""
    img = mpimg.imread(str(path))
    if img.dtype != np.uint8:
        img = (img * 255).clip(0, 255).astype(np.uint8)
    return img[..., :3]          # drop alpha channel if present


def _resize_to(img: np.ndarray, target_hw: tuple[int, int]) -> np.ndarray:
    """Resize *img* to (height, width) using nearest-neighbour sampling."""
    th, tw = target_hw
    sh, sw = img.shape[:2]
    if (sh, sw) == (th, tw):
        return img
    # Use pillow if available; fall back to a simple numpy zoom
    try:
        from PIL import Image as _PILImage
        pil = _PILImage.fromarray(img).resize((tw, th), _PILImage.NEAREST)
        return np.asarray(pil)
    except ImportError:
        # Nearest-neighbour resize via index mapping
        row_idx = (np.linspace(0, sh - 1, th)).astype(int)
        col_idx = (np.linspace(0, sw - 1, tw)).astype(int)
        return img[np.ix_(row_idx, col_idx)]


# ---------------------------------------------------------------------------
# Public functions
# ---------------------------------------------------------------------------

def verify_wafer(
    data_df,
    wafer_id: str,
    config: PlotConfig,
    out_dir: Path,
) -> Path | None:
    """
    Generate Python PNG, Origin PNG, and side-by-side comparison for one wafer.

    Parameters
    ----------
    data_df  : Full DataFrame (all wafers) from read_wafer_data().
    wafer_id : Wafer identifier to process.
    config   : PlotConfig with thresholds, scale, transforms, colours.
    out_dir  : Root output directory; sub-folders are created automatically.

    Returns
    -------
    Path to the comparison PNG, or None if the wafer was skipped
    (too few points or not found).
    """
    out_dir = Path(out_dir)
    wdf = data_df[data_df["wafer"] == wafer_id]
    if wdf.empty:
        return None

    safe   = str(wafer_id).replace(" ", "_").replace(".", "_").replace("-", "_")
    py_png   = out_dir / "python_pngs" / f"{safe}_python.png"
    orig_png = out_dir / "origin_pngs" / f"{safe}_origin.png"
    comp_png = out_dir / "comparisons"  / f"{safe}_compare.png"

    # Python render
    ok_py = _python_png(wdf, wafer_id, config, py_png)
    if not ok_py:
        print(f"    [skip] wafer {wafer_id}: insufficient data for Python plot")
        return None

    # Origin render
    ok_orig = export_wafer_as_origin_png(wdf, wafer_id, config, orig_png)
    if not ok_orig:
        print(f"    [skip] wafer {wafer_id}: insufficient data for Origin plot")
        return None

    # Side-by-side + diff
    _make_comparison(py_png, orig_png, comp_png, str(wafer_id))
    return comp_png


def verify_lot(
    data_file: str | Path,
    config: PlotConfig,
    out_dir: Path,
    max_wafers: int = 5,
) -> list[Path]:
    """
    Run verify_wafer for up to *max_wafers* wafers from *data_file*.

    Parameters
    ----------
    data_file  : Path to input CSV / tab-delimited wafer data file.
    config     : PlotConfig controlling thresholds, scale, and transforms.
    out_dir    : Root directory for all outputs.
    max_wafers : Maximum number of wafers to process (default 5).

    Returns
    -------
    List of Path objects pointing to the generated comparison PNGs.
    """
    from wafer_tool.data_loader import read_wafer_data

    data_file = Path(data_file)
    out_dir   = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    df = read_wafer_data(data_file)
    wafer_ids = df["wafer"].unique()[:max_wafers]

    comparisons: list[Path] = []
    for wid in wafer_ids:
        print(f"  Processing wafer {wid} …", end="  ")
        comp = verify_wafer(df, wid, config, out_dir)
        if comp:
            print(f"→ {comp.name}")
            comparisons.append(comp)
        else:
            print("skipped")

    return comparisons
