"""
plotting.py
===========
Core Matplotlib wafer-map rendering.

Public API
----------
draw_wafer_ax(ax, df, wafer_id, config, show_legend, show_title, lot_sites) -> bool
    Renders a single wafer contour map onto *ax*.
    Returns True on success, False when there are too few data points.
lot_die_sites(lot_df, extra) -> NDArray
    Every die (x, y) in a lot, used to give all wafers of a lot one outline.
"""
from __future__ import annotations

import numpy as np
from matplotlib.axes import Axes
from matplotlib.patches import Circle, Patch

from .config import (PlotConfig, MIN_POINTS_FOR_PLOT, GRID_RESOLUTION,
                     WAFER_RADIUS_FACTOR, COLOR_MISSING, DIE_PITCH,
                     MAX_INTERP_DIST_CHIPS)
from .geometry import apply_transforms, build_wafer_grid, far_from_data_mask

__all__ = ["draw_wafer_ax", "lot_die_sites"]


def lot_die_sites(lot_df, extra=None) -> np.ndarray:
    """Unique (x, y) of every die measured on any wafer in *lot_df*, plus
    *extra* positions (e.g. dies removed by a value filter)."""
    pts = lot_df[["x", "y"]].to_numpy(dtype=np.float32)
    if extra is not None and len(extra):
        pts = np.concatenate([pts, np.asarray(extra, dtype=np.float32).reshape(-1, 2)])
    return np.unique(pts, axis=0)


def draw_wafer_ax(
    ax: Axes,
    df,
    wafer_id: str,
    config: PlotConfig,
    show_legend: bool = False,
    show_title:  bool = True,
    lot_sites=None,
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
    lot_sites   : Optional (N, 2) array from :func:`lot_die_sites`. When given,
                  the wafer is drawn at lot size. Areas farther than
                  MAX_INTERP_DIST_CHIPS from any measured die are shown grey.

    Returns
    -------
    bool
        True  — wafer drawn successfully.
        False — fewer than MIN_POINTS_FOR_PLOT data points; axes turned off.
    """
    x = df["x"].to_numpy(dtype=np.float32, copy=False)
    y = df["y"].to_numpy(dtype=np.float32, copy=False)
    z = df["value"].to_numpy(dtype=np.float32, copy=False)
    n_meas = int(len(z))            # measured sites on this wafer (audit CHK-0410)

    if len(z) < MIN_POINTS_FOR_PLOT:
        if show_title:
            ax.text(0.5, 0.5, f"Insufficient pts\n({len(z)})",
                    ha="center", va="center", fontsize=7, transform=ax.transAxes)
        ax.axis("off")
        return False

    # ── Spatial transforms ────────────────────────────────────────────────
    sx = sy = None
    if lot_sites is not None and len(lot_sites):
        # Transform dies and sites together so both share one rotation centre.
        n = len(x)
        all_x = np.concatenate([x, lot_sites[:, 0].astype(np.float32)])
        all_y = np.concatenate([y, lot_sites[:, 1].astype(np.float32)])
        all_x, all_y = apply_transforms(all_x, all_y, config.mirror_x,
                                        config.mirror_y, config.rot_deg)
        x, y, sx, sy = all_x[:n], all_y[:n], all_x[n:], all_y[n:]
    else:
        x, y = apply_transforms(x, y, config.mirror_x, config.mirror_y, config.rot_deg)

    # ── Interpolation grid ────────────────────────────────────────────────────────────────
    xi, yi, zi, x_mid, y_mid, radius = build_wafer_grid(
        x, y, z,
        resolution=GRID_RESOLUTION,
        radius_factor=WAFER_RADIUS_FACTOR,
        extent=None if sx is None else (sx, sy),
        die_margin=0.5 * DIE_PITCH,
    )
    # Which interpolated cells count as "no data":
    #   interpolate mode -> cells farther than MAX_INTERP_DIST_CHIPS from any
    #                       measured die (a fill beyond that isn't trustworthy)
    #   extrapolate mode -> none; the nearest-neighbour fill already spans the disc
    if config.extrapolate:
        missing = None
    else:
        missing = (far_from_data_mask(xi, yi, x, y, MAX_INTERP_DIST_CHIPS * DIE_PITCH)
                   & ~np.isnan(zi))
        if not missing.any():
            missing = None
    del x, y, z, sx, sy  # consumed by build_wafer_grid; free before contourf

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

    if missing is not None:
        zi[missing] = np.nan          # drop "no data" cells from the colour fill
    valid = zi[~np.isnan(zi)]
    s_min = min(valid.min() - 0.1 if valid.size else p_low  - 1, p_low  - 0.1)
    s_max = max(valid.max() + 0.1 if valid.size else p_high + 1, p_high + 0.1)

    # contourf requires STRICTLY increasing levels. A fixed +/-0.1 margin is
    # lost to float rounding when a threshold is huge — e.g. an eSquare "no
    # upper limit" spec of 1e31 makes s_max == p_high — which previously raised
    # "Contour levels must be increasing". Nudge any non-increasing level up by
    # one ULP so every threshold/value magnitude renders instead of crashing.
    levels = [s_min, p_low, p_high, s_max]
    for _k in range(1, len(levels)):
        if not levels[_k] > levels[_k - 1]:
            levels[_k] = float(np.nextafter(levels[_k - 1], np.inf))

    # ── Rendering ─────────────────────────────────────────────────────────
    cs = config.color_scheme
    if valid.size > 0:
        ax.contourf(
            xi, yi, zi,
            levels=levels,
            colors=[cs.low, cs.mid, cs.high],
        )
    # Grey "No data" overlay: only in interpolate mode AND when the user ticks it.
    # Unticked -> those cells stay unpainted (white, inside the wafer outline).
    if missing is not None and config.show_missing_grey:
        ax.contourf(xi, yi, np.where(missing, 1.0, np.nan),
                    levels=[0.5, 1.5], colors=[COLOR_MISSING])
    del xi, yi, zi, valid, missing   # free ~240–960 KB of grid data immediately

    # Wafer outline in a neutral grey so it is visible on any background —
    # white (report / grey-off), dark (GUI preview) or over a colour fill.
    ax.add_patch(
        Circle((x_mid, y_mid), radius, fill=False, color="#888888", linewidth=1.0)
    )
    ax.set_aspect("equal")
    ax.axis("off")

    # Make extrapolated (whole-disc) maps self-identifying — a fully-filled wafer
    # must not be mistaken for full measured coverage (audit F-01 / CHK-0409).
    if config.extrapolate:
        ax.text(0.5, 0.005, "extrapolated", transform=ax.transAxes,
                ha="center", va="bottom", fontsize=6, style="italic", color="#C0392B")

    # Measured-site coverage so a reader can tell how much was actually measured
    # (audit F-03 / CHK-0410). "/N" is the lot die-map size when supplied.
    _cov = (f"{n_meas}/{len(lot_sites)}"
            if (lot_sites is not None and len(lot_sites)) else f"{n_meas}")
    ax.text(0.01, 0.99, f"meas {_cov}", transform=ax.transAxes, ha="left", va="top",
            fontsize=5.5, color="#555555")

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
    if config.show_missing_grey and not config.extrapolate:
        handles.append(Patch(facecolor=COLOR_MISSING, edgecolor="black", label="No data"))
    ax.legend(
        handles=handles,
        loc="center left",
        bbox_to_anchor=(1.05, 0.5),
        title="Thresholds",
        fontsize=9,
        frameon=True,
        shadow=True,
    )
