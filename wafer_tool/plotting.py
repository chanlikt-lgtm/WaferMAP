"""
plotting.py
===========
Core Matplotlib wafer-map rendering.

Public API
----------
draw_wafer_ax(ax, df, wafer_id, config, show_legend, show_title) -> bool
    Renders a single wafer contour map onto *ax*.
    Returns True on success, False when there are too few data points.
"""
from __future__ import annotations

import numpy as np
from matplotlib.axes import Axes
from matplotlib.patches import Circle, Patch

from .config import PlotConfig, MIN_POINTS_FOR_PLOT, GRID_RESOLUTION, WAFER_RADIUS_FACTOR
from .geometry import apply_transforms, build_wafer_grid

__all__ = ["draw_wafer_ax"]


def draw_wafer_ax(
    ax: Axes,
    df,
    wafer_id: str,
    config: PlotConfig,
    show_legend: bool = False,
    show_title:  bool = True,
) -> bool:
    """
    Draw a colour-coded contour map for a single wafer onto *ax*.

    Parameters
    ----------
    ax       : Matplotlib Axes to draw on.
    df       : DataFrame slice for this wafer (must have x, y, value columns).
    wafer_id : Label used for the subplot title.
    config   : PlotConfig controlling thresholds, scale, transforms, colours.
    show_legend : If True, attach a colour-band legend outside the axes.
    show_title  : If True, set the axes title to "W: {wafer_id}".

    Returns
    -------
    bool
        True  — wafer drawn successfully.
        False — fewer than MIN_POINTS_FOR_PLOT data points; axes turned off.
    """
    x = df["x"].to_numpy(dtype=np.float32, copy=False)
    y = df["y"].to_numpy(dtype=np.float32, copy=False)
    z = df["value"].to_numpy(dtype=np.float32, copy=False)

    if len(z) < MIN_POINTS_FOR_PLOT:
        if show_title:
            ax.text(0.5, 0.5, f"Insufficient pts\n({len(z)})",
                    ha="center", va="center", fontsize=7, transform=ax.transAxes)
        ax.axis("off")
        return False

    # ── Spatial transforms ────────────────────────────────────────────────
    x, y = apply_transforms(x, y, config.mirror_x, config.mirror_y, config.rot_deg)

    # ── Interpolation grid ────────────────────────────────────────────────
    xi, yi, zi, x_mid, y_mid, radius = build_wafer_grid(
        x, y, z,
        resolution=GRID_RESOLUTION,
        radius_factor=WAFER_RADIUS_FACTOR,
    )
    del x, y, z  # consumed by build_wafer_grid; free before contourf

    # ── Threshold mapping (log or linear) ─────────────────────────────────
    if config.use_log:
        zi     = np.log10(np.maximum(zi, 1e-15))
        p_low  = np.log10(max(config.t_low,  1e-15))
        p_high = np.log10(max(config.t_high, 1e-15))
    else:
        p_low, p_high = config.t_low, config.t_high

    # Ensure strictly ascending levels (required by contourf)
    p_low, p_high = min(p_low, p_high), max(p_low, p_high)
    if p_low == p_high:
        p_high += 1e-9

    valid = zi[~np.isnan(zi)]
    s_min = min(valid.min() - 0.1 if valid.size else p_low  - 1, p_low  - 0.1)
    s_max = max(valid.max() + 0.1 if valid.size else p_high + 1, p_high + 0.1)

    # ── Rendering ─────────────────────────────────────────────────────────
    cs = config.color_scheme
    if valid.size > 0:
        ax.contourf(
            xi, yi, zi,
            levels=[s_min, p_low, p_high, s_max],
            colors=[cs.low, cs.mid, cs.high],
        )
    del xi, yi, zi, valid   # free ~240–960 KB of grid data immediately

    ax.add_patch(
        Circle((x_mid, y_mid), radius, fill=False, color="white", linewidth=0.8)
    )
    ax.set_aspect("equal")
    ax.axis("off")

    if show_title:
        ax.set_title(f"W: {wafer_id}", fontsize=10, fontweight="bold")

    if show_legend:
        _attach_legend(ax, config)

    return True


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _attach_legend(ax: Axes, config: PlotConfig) -> None:
    cs = config.color_scheme
    handles = [
        Patch(facecolor=cs.low,  edgecolor="black", label=f"< {config.t_low:g}"),
        Patch(facecolor=cs.mid,  edgecolor="black",
              label=f"{config.t_low:g} – {config.t_high:g}"),
        Patch(facecolor=cs.high, edgecolor="black", label=f"≥ {config.t_high:g}"),
    ]
    ax.legend(
        handles=handles,
        loc="center left",
        bbox_to_anchor=(1.05, 0.5),
        title="Thresholds",
        fontsize=9,
        frameon=True,
        shadow=True,
    )
