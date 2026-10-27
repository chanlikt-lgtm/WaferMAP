"""
origin_wafer_exporter.py
========================
Generates OriginLab color-fill contour plots from wafer measurement data,
replicating the exact 3-zone color scheme and spatial layout of the
Python/Matplotlib output.

How it works
------------
1.  Loads a single-wafer DataFrame slice (x, y, value columns).
2.  Applies the same coordinate transforms and SciPy grid interpolation
    as the Python side (via wafer_tool.geometry).
3.  Imports the 2-D interpolated grid into an Origin Matrix.
4.  Creates a Color-Fill Contour graph from that matrix.
5.  Sets the colormap to exactly 3 fill zones using the same
    threshold values and hex colours as the Python plot.
6.  Hides axes and adds a title label.
7.  Exports a PNG at the requested pixel size.

Color encoding
--------------
Origin stores custom RGB colours as a 32-bit packed integer:
    OColor = 0x01000000 | R | (G << 8) | (B << 16)

The 0x01000000 flag tells Origin this is a custom RGB value (not an
indexed colour from the 24-entry named palette).

Fill-zone LabTalk property names
---------------------------------
After creating the contour DataPlot, the fill-zone colours are set via
LabTalk range-property assignment:
    range __r = [GraphName]1!plotIdx;
    __r.cmap.clr1 = OColor_for_zone1;
    __r.cmap.clr2 = OColor_for_zone2;
    __r.cmap.clr3 = OColor_for_zone3;
    __r.cmap.lineVisible = 0;   // hide contour lines

If the colours do not apply (visible in the side-by-side comparison),
try replacing 'cmap.clr{n}' with 'cmap.fillcolor{n}' or
'cmap.fc{n}' — the exact property name may differ between Origin
versions.  The level boundaries are always set reliably via the
Python dp.zlevels API.

Public API
----------
export_wafer_as_origin_png(df, wafer_id, config, out_png, width_px) -> bool
    Render one wafer in Origin and write a PNG.  Returns True on success.
"""
from __future__ import annotations

import sys
import numpy as np
from pathlib import Path
from typing import TYPE_CHECKING

# ── Project root on path so wafer_tool can be imported ────────────────────
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from wafer_tool.config import (
    PlotConfig,
    GRID_RESOLUTION,
    WAFER_RADIUS_FACTOR,
    MIN_POINTS_FOR_PLOT,
)
from wafer_tool.geometry import apply_transforms, build_wafer_grid

__all__ = ["export_wafer_as_origin_png"]


# ---------------------------------------------------------------------------
# Colour helpers (no Origin/LabTalk required – pure arithmetic)
# ---------------------------------------------------------------------------

def _hex_to_ocolor(hex_str: str) -> int:
    """
    Convert a CSS hex colour (#RRGGBB) to Origin's packed OColor integer.

    Formula: 0x01000000 | R | (G << 8) | (B << 16)
    The 0x01000000 flag distinguishes a custom RGB colour from a named
    palette index (1-24) in Origin's colour system.
    """
    h = hex_str.lstrip("#")
    r = int(h[0:2], 16)
    g = int(h[2:4], 16)
    b = int(h[4:6], 16)
    return 0x01000000 | r | (g << 8) | (b << 16)


def _safe_id(wafer_id: str, max_len: int = 20) -> str:
    """Return a string safe for use as an Origin window name."""
    return (
        str(wafer_id)
        .replace(" ", "_")
        .replace(".", "_")
        .replace("-", "_")
        [:max_len]
    )


# ---------------------------------------------------------------------------
# Public export function
# ---------------------------------------------------------------------------

def export_wafer_as_origin_png(
    df,
    wafer_id: str,
    config: PlotConfig,
    out_png: Path,
    width_px: int = 400,
) -> bool:
    """
    Create an OriginLab color-fill contour plot for one wafer and export PNG.

    Uses the **identical** interpolated grid and threshold values as the
    Python/Matplotlib path so that the two images are directly comparable.

    Parameters
    ----------
    df        : DataFrame slice for this wafer (must have x, y, value columns).
    wafer_id  : Label shown as the graph title (e.g. "05").
    config    : PlotConfig carrying thresholds, transforms, and colour scheme.
    out_png   : Destination PNG file path.  Parent directories are created.
    width_px  : Export width in pixels.  Height follows the graph aspect ratio.

    Returns
    -------
    bool
        True on success, False when there are fewer than MIN_POINTS_FOR_PLOT
        data points (matching the Python skip condition).
    """
    import originpro as op  # deferred import — Origin must be running first

    # ── 1. Raw data ────────────────────────────────────────────────────────
    x = df["x"].to_numpy(dtype=float)
    y = df["y"].to_numpy(dtype=float)
    z = df["value"].to_numpy(dtype=float)

    if len(z) < MIN_POINTS_FOR_PLOT:
        return False

    # ── 2. Same transforms + interpolation as Python side ─────────────────
    x, y = apply_transforms(x, y, config.mirror_x, config.mirror_y, config.rot_deg)

    xi, yi, zi, x_mid, y_mid, radius = build_wafer_grid(
        x, y, z,
        resolution=GRID_RESOLUTION,
        radius_factor=WAFER_RADIUS_FACTOR,
    )

    # ── 3. Threshold mapping (log or linear) ──────────────────────────────
    if config.use_log:
        zi     = np.log10(np.maximum(zi, 1e-15))
        p_low  = np.log10(max(config.t_low,  1e-15))
        p_high = np.log10(max(config.t_high, 1e-15))
    else:
        p_low, p_high = config.t_low, config.t_high

    p_low, p_high = min(p_low, p_high), max(p_low, p_high)
    if p_low == p_high:
        p_high += 1e-9

    valid = zi[~np.isnan(zi)]
    s_min = min(valid.min() - 0.1 if valid.size else p_low  - 1.0, p_low  - 0.1)
    s_max = max(valid.max() + 0.1 if valid.size else p_high + 1.0, p_high + 0.1)

    cs  = config.color_scheme
    sid = _safe_id(wafer_id)

    # ── 4. Create Origin Matrix ────────────────────────────────────────────
    # Origin matrix: row 1 = y_min (bottom), last row = y_max (top).
    # numpy meshgrid: row 0 = y_min, last row = y_max.
    # → same orientation; no vertical flip needed.
    mb = op.new_book("m", lname=f"WM_{sid}", hidden=True)
    ms = mb[0]

    x_min = float(xi[0, 0]);   x_max = float(xi[0, -1])
    y_min = float(yi[0, 0]);   y_max = float(yi[-1, 0])

    # from_np sets the matrix dimensions and loads the 2-D array
    ms.from_np(zi.astype(np.float64))
    # Set the X/Y coordinate range for the matrix axes
    ms.xymap = (x_min, x_max, y_min, y_max)

    # ── 5. Create contour graph ────────────────────────────────────────────
    gr = op.new_graph(template="contour", lname=f"GW_{sid}", hidden=True)
    gl = gr[0]

    # add_plot with a MSheet + colz=0 selects matrix object 0 as the Z data
    dp = gl.add_plot(ms, colz=0, type="contour")
    gl.rescale()

    # ── 6. Set 3-zone colormap to match Python colours ─────────────────────
    _set_3zone_colormap(dp, gr, s_min, p_low, p_high, s_max, cs, op)

    # ── 7. Format: white background, no axes, title label ─────────────────
    title = f"W: {wafer_id}" + (" (LOG)" if config.use_log else "")
    _format_graph(gr, title, op)

    # ── 8. Export PNG ──────────────────────────────────────────────────────
    out_png = Path(out_png)
    out_png.parent.mkdir(parents=True, exist_ok=True)
    gr.save_fig(str(out_png), type="png", width=width_px)

    return True


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _set_3zone_colormap(dp, gr, s_min, p_low, p_high, s_max, cs, op) -> None:
    """
    Configure the contour DataPlot colormap to exactly 3 fill zones:

        Zone 1  [s_min  → p_low ]:  cs.low
        Zone 2  [p_low  → p_high]:  cs.mid
        Zone 3  [p_high → s_max ]:  cs.high

    Level boundaries are set via the Python API (dp.zlevels).
    Fill colours are set via LabTalk range-property assignment.
    """
    # ── Level boundaries (Python API – confirmed reliable) ─────────────────
    dp.zlevels = {
        "minors":  0,
        "levels": [s_min, p_low, p_high, s_max],
    }

    # ── Fill colours (LabTalk range-property assignment) ───────────────────
    oc_low  = _hex_to_ocolor(cs.low)
    oc_mid  = _hex_to_ocolor(cs.mid)
    oc_high = _hex_to_ocolor(cs.high)

    gr_name  = gr.name
    plot_idx = dp.index() + 1   # 1-based in LabTalk range syntax

    # Assign colours to the three fill zones and hide contour lines.
    # Property names 'cmap.clr{n}' are Origin's internal fill-zone colour
    # properties for a contour DataPlot (verified on Origin 2021).
    # If a future Origin version renames them, try 'cmap.fillcolor{n}'.
    lt = f"""
win -a {gr_name};
range __rwm = [{gr_name}]1!{plot_idx};
__rwm.cmap.clr1 = {oc_low};
__rwm.cmap.clr2 = {oc_mid};
__rwm.cmap.clr3 = {oc_high};
__rwm.cmap.lineVisible = 0;
del -v __rwm;
"""
    op.lt_exec(lt)


def _format_graph(gr, title: str, op) -> None:
    """
    Apply visual formatting to match the Python output:
      - White page and layer background
      - Axes and border hidden
      - Bold centred title label at the top
    """
    gr_name = gr.name
    lt = f"""
win -a {gr_name};
// White page background
page.color = color(255,255,255);
// White layer background, no border
layer.color = color(255,255,255);
layer.border.show = 0;
// Hide all axis elements
layer.x.show = 0;
layer.y.show = 0;
layer.x.showAxes = 0;
layer.y.showAxes = 0;
layer.x.tickLabels = 0;
layer.y.tickLabels = 0;
// Centred title label (x=50% width, y=98% height from bottom)
label -s -p 50 98 -j 0 -f 1 -h 11 "{title}";
"""
    op.lt_exec(lt)
