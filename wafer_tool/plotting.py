"""
plotting.py
===========
Core Matplotlib wafer-map rendering.

Two rendering modes
-------------------
* **discrete** (default) — one coloured cell per die; dies that were not tested
  (checkerboard skips, filtered-out, NaN) stay **grey**. Nothing is invented.
* **interpolate / extrapolate** — the smooth contour field, for genuinely
  full-coverage continuous parameters.

`draw_wafer_ax` is a dispatcher: it honours ``config.render_mode`` but, when an
interpolate/extrapolate map is requested on a **checkerboard / low-coverage**
parameter, it auto-overrides to the discrete die-map so skipped dies are never
fabricated.

Public API
----------
draw_wafer_ax(ax, df, wafer_id, config, show_legend, show_title, lot_sites) -> bool
draw_wafer_discrete_ax(...) -> bool
lot_die_sites(lot_df, extra) -> NDArray
"""
from __future__ import annotations

import numpy as np
from matplotlib.axes import Axes
from matplotlib.collections import PatchCollection
from matplotlib.patches import Circle, Patch, Rectangle

from .config import (PlotConfig, MIN_POINTS_FOR_PLOT, GRID_RESOLUTION,
                     WAFER_RADIUS_FACTOR, COLOR_MISSING, DIE_PITCH,
                     MAX_INTERP_DIST_CHIPS)
from .geometry import apply_transforms, build_wafer_grid, far_from_data_mask

__all__ = ["draw_wafer_ax", "draw_wafer_discrete_ax", "lot_die_sites"]

# Coverage below which (or a checkerboard at/under which) an interpolate request
# is auto-overridden to the honest discrete die-map.
_CHECKERBOARD_PARITY = 0.90     # share of tested dies on one (x+y) parity lattice
_CHECKERBOARD_COVER = 0.70      # ... combined with <= this fraction of the grid
_SPARSE_COVER = 0.60            # any coverage below this is too sparse to interpolate


def lot_die_sites(lot_df, extra=None) -> np.ndarray:
    """Unique (x, y) of every die measured on any wafer in *lot_df*, plus
    *extra* positions (e.g. dies removed by a value filter)."""
    pts = lot_df[["x", "y"]].to_numpy(dtype=np.float32)
    if extra is not None and len(extra):
        pts = np.concatenate([pts, np.asarray(extra, dtype=np.float32).reshape(-1, 2)])
    return np.unique(pts, axis=0)


# ---------------------------------------------------------------------------
# Dispatcher
# ---------------------------------------------------------------------------

def draw_wafer_ax(
    ax: Axes,
    df,
    wafer_id: str,
    config: PlotConfig,
    show_legend: bool = False,
    show_title:  bool = True,
    lot_sites=None,
) -> bool:
    """Render a single wafer onto *ax*, choosing discrete vs interpolated.

    Returns True when something was drawn, False when the wafer is empty or
    (for an interpolated request) has too few points to interpolate.
    """
    x = df["x"].to_numpy(dtype=np.float32, copy=False)
    y = df["y"].to_numpy(dtype=np.float32, copy=False)
    z = df["value"].to_numpy(dtype=np.float32, copy=False)
    n_meas = int(len(z))

    if n_meas == 0:                       # nothing survived (e.g. filtered empty)
        if show_title:
            ax.text(0.5, 0.5, "No data", ha="center", va="center",
                    fontsize=7, transform=ax.transAxes)
        ax.axis("off")
        return False

    mode = getattr(config, "render_mode", "discrete") or "discrete"
    note = None
    if mode in ("interpolate", "extrapolate"):
        # Never fabricate a checkerboard / sparse wafer: fall back to discrete.
        forced, _full, _tested, _cov = _coverage_forces_discrete(x, y)
        if forced or n_meas < MIN_POINTS_FOR_PLOT:
            note = "checkerboard: discrete" if forced else None
            mode = "discrete"

    if mode == "discrete":
        return draw_wafer_discrete_ax(ax, df, wafer_id, config,
                                      show_legend, show_title, lot_sites, note=note)

    return _draw_interpolated(ax, config, x, y, z, n_meas, lot_sites,
                              extrapolate=(mode == "extrapolate"),
                              show_legend=show_legend, show_title=show_title,
                              wafer_id=wafer_id)


# ---------------------------------------------------------------------------
# Discrete die-map
# ---------------------------------------------------------------------------

def _infer_die_grid(xr, yr):
    """Full integer die lattice within the convex hull of the measured dies.

    Die (x, y) are integer die indices, so the complete layout is the integer
    lattice (at the inferred pitch) lying inside the hull of the tested dies.
    Returns (set[(int, int)] full grid, int pitch).
    """
    xi = np.round(np.asarray(xr, float)).astype(int)
    yi = np.round(np.asarray(yr, float)).astype(int)
    ux = np.unique(xi); uy = np.unique(yi)
    px = int(np.min(np.diff(ux))) if ux.size > 1 else 1
    py = int(np.min(np.diff(uy))) if uy.size > 1 else 1
    pitch = max(1, min(px, py))
    tested = {(int(a), int(b)) for a, b in zip(xi, yi)}
    if ux.size < 2 or uy.size < 2:        # degenerate: nothing to infer between
        return set(tested), pitch
    gx = np.arange(xi.min(), xi.max() + 1, pitch)
    gy = np.arange(yi.min(), yi.max() + 1, pitch)
    grid = np.array([(a, b) for a in gx for b in gy], dtype=float)
    try:
        from scipy.spatial import Delaunay
        inside = Delaunay(np.column_stack([xi, yi]).astype(float)).find_simplex(grid) >= 0
    except Exception:
        inside = np.ones(len(grid), bool)
    full = {(int(a), int(b)) for (a, b), ok in zip(grid, inside) if ok}
    full |= tested                        # tested dies are always part of the grid
    return full, pitch


def _coverage_forces_discrete(xr, yr):
    """Decide whether this wafer must be shown discrete (checkerboard/sparse).
    Returns (forced: bool, full_grid: set, tested: set, coverage: float)."""
    full, _ = _infer_die_grid(xr, yr)
    tested = {(int(round(float(a))), int(round(float(b)))) for a, b in zip(xr, yr)}
    cov = len(tested) / max(1, len(full))
    if tested:
        par = np.array([(a + b) & 1 for a, b in tested])
        conc = float(max(par.mean(), 1.0 - par.mean()))
    else:
        conc = 0.0
    forced = (conc >= _CHECKERBOARD_PARITY and cov <= _CHECKERBOARD_COVER) or cov < _SPARSE_COVER
    return forced, full, tested, cov


def _band_color(v: float, config: PlotConfig):
    """Colour for a single value under the configured thresholds (log aware)."""
    cs = config.color_scheme
    if config.use_log:
        vv = np.log10(max(float(v), 1e-15))
        lo = np.log10(max(config.t_low, 1e-15)); hi = np.log10(max(config.t_high, 1e-15))
    else:
        vv, lo, hi = float(v), config.t_low, config.t_high
    lo, hi = min(lo, hi), max(lo, hi)
    if vv < lo:
        return cs.low
    return cs.high if vv >= hi else cs.mid


def draw_wafer_discrete_ax(
    ax: Axes,
    df,
    wafer_id: str,
    config: PlotConfig,
    show_legend: bool = False,
    show_title:  bool = True,
    lot_sites=None,
    note: str | None = None,
) -> bool:
    """One coloured cell per die; untested/skipped dies are grey (or blank when
    ``show_missing_grey`` is off). No interpolation — nothing is invented."""
    xr = df["x"].to_numpy(dtype=float, copy=False)
    yr = df["y"].to_numpy(dtype=float, copy=False)
    zr = df["value"].to_numpy(dtype=float, copy=False)
    n_meas = int(len(zr))
    if n_meas == 0:
        ax.axis("off"); return False

    full, pitch = _infer_die_grid(xr, yr)
    tested = {}
    for a, b, v in zip(xr, yr, zr):
        tested[(int(round(a)), int(round(b)))] = v
    full |= set(tested)

    # Split into tested (coloured) and skipped (grey) cells, in die coordinates.
    t_xy = np.array(list(tested.keys()), dtype=float) if tested else np.empty((0, 2))
    t_v = np.array([tested[(int(a), int(b))] for a, b in t_xy]) if len(t_xy) else np.empty(0)
    skipped = [c for c in full if c not in tested]
    s_xy = np.array(skipped, dtype=float) if skipped else np.empty((0, 2))

    # Transform tested + skipped centres together so they share one orientation.
    nt = len(t_xy)
    allx = np.concatenate([t_xy[:, 0] if nt else np.empty(0),
                           s_xy[:, 0] if len(s_xy) else np.empty(0)])
    ally = np.concatenate([t_xy[:, 1] if nt else np.empty(0),
                           s_xy[:, 1] if len(s_xy) else np.empty(0)])
    allx, ally = apply_transforms(allx.astype(np.float32), ally.astype(np.float32),
                                  config.mirror_x, config.mirror_y, config.rot_deg)
    tx, ty = allx[:nt], ally[:nt]
    sx, sy = allx[nt:], ally[nt:]

    half = pitch / 2.0
    rects = []
    if len(sx) and config.show_missing_grey:          # grey skipped dies
        for cx, cy in zip(sx, sy):
            rects.append(Rectangle((cx - half, cy - half), pitch, pitch,
                                   facecolor=COLOR_MISSING, edgecolor="white", linewidth=0.3))
    for cx, cy, v in zip(tx, ty, t_v):                # coloured tested dies
        rects.append(Rectangle((cx - half, cy - half), pitch, pitch,
                               facecolor=_band_color(v, config), edgecolor="white", linewidth=0.3))
    if rects:
        ax.add_collection(PatchCollection(rects, match_original=True))

    # Wafer outline + framing from the full grid extent.
    gx = np.concatenate([tx, sx]) if len(sx) else tx
    gy = np.concatenate([ty, sy]) if len(sy) else ty
    x_mid, y_mid = (gx.min() + gx.max()) / 2, (gy.min() + gy.max()) / 2
    radius = max(gx.max() - gx.min(), gy.max() - gy.min()) / 2 + half
    ax.add_patch(Circle((x_mid, y_mid), radius, fill=False, color="#888888", linewidth=1.0))
    ax.set_xlim(x_mid - radius - half, x_mid + radius + half)
    ax.set_ylim(y_mid - radius - half, y_mid + radius + half)
    ax.set_aspect("equal")
    ax.axis("off")

    ax.text(0.01, 0.99, f"meas {n_meas}/{len(full)}", transform=ax.transAxes,
            ha="left", va="top", fontsize=5.5, color="#555555")
    if note:
        ax.text(0.5, 0.005, note, transform=ax.transAxes, ha="center", va="bottom",
                fontsize=6, style="italic", color="#C0392B")
    if show_title:
        ax.set_title(f"W: {wafer_id}", fontsize=10, fontweight="bold")
    if show_legend:
        _attach_legend(ax, config, discrete=True)
    return True


# ---------------------------------------------------------------------------
# Interpolated / extrapolated contour map
# ---------------------------------------------------------------------------

def _draw_interpolated(
    ax: Axes,
    config: PlotConfig,
    x, y, z,
    n_meas: int,
    lot_sites,
    extrapolate: bool,
    show_legend: bool,
    show_title: bool,
    wafer_id: str,
) -> bool:
    """Smooth contour field (the original renderer). Used only for genuinely
    full-coverage continuous parameters."""
    if n_meas < MIN_POINTS_FOR_PLOT:
        if show_title:
            ax.text(0.5, 0.5, f"Insufficient pts\n({n_meas})",
                    ha="center", va="center", fontsize=7, transform=ax.transAxes)
        ax.axis("off")
        return False

    # ── Spatial transforms ────────────────────────────────────────────────
    sx = sy = None
    if lot_sites is not None and len(lot_sites):
        n = len(x)
        all_x = np.concatenate([x, lot_sites[:, 0].astype(np.float32)])
        all_y = np.concatenate([y, lot_sites[:, 1].astype(np.float32)])
        all_x, all_y = apply_transforms(all_x, all_y, config.mirror_x,
                                        config.mirror_y, config.rot_deg)
        x, y, sx, sy = all_x[:n], all_y[:n], all_x[n:], all_y[n:]
    else:
        x, y = apply_transforms(x, y, config.mirror_x, config.mirror_y, config.rot_deg)

    # ── Interpolation grid ─────────────────────────────────────────────────
    xi, yi, zi, x_mid, y_mid, radius = build_wafer_grid(
        x, y, z,
        resolution=GRID_RESOLUTION,
        radius_factor=WAFER_RADIUS_FACTOR,
        extent=None if sx is None else (sx, sy),
        die_margin=0.5 * DIE_PITCH,
    )
    if extrapolate:
        missing = None
    else:
        missing = (far_from_data_mask(xi, yi, x, y, MAX_INTERP_DIST_CHIPS * DIE_PITCH)
                   & ~np.isnan(zi))
        if not missing.any():
            missing = None
    del x, y, z, sx, sy

    # ── Threshold mapping (log or linear) ──────────────────────────────────
    if config.use_log:
        zi     = np.log10(np.maximum(zi, 1e-15))
        p_low  = np.log10(max(config.t_low,  1e-15))
        p_high = np.log10(max(config.t_high, 1e-15))
    else:
        p_low, p_high = config.t_low, config.t_high

    p_low, p_high = min(p_low, p_high), max(p_low, p_high)
    if p_low == p_high:
        p_high += 1e-9

    if missing is not None:
        zi[missing] = np.nan
    valid = zi[~np.isnan(zi)]
    s_min = min(valid.min() - 0.1 if valid.size else p_low  - 1, p_low  - 0.1)
    s_max = max(valid.max() + 0.1 if valid.size else p_high + 1, p_high + 0.1)

    # contourf requires STRICTLY increasing levels. A fixed +/-0.1 margin is
    # lost to float rounding when a threshold is huge (e.g. a 1e31 "no limit"
    # spec). Nudge any non-increasing level up by one ULP.
    levels = [s_min, p_low, p_high, s_max]
    for _k in range(1, len(levels)):
        if not levels[_k] > levels[_k - 1]:
            levels[_k] = float(np.nextafter(levels[_k - 1], np.inf))

    cs = config.color_scheme
    if valid.size > 0:
        ax.contourf(xi, yi, zi, levels=levels, colors=[cs.low, cs.mid, cs.high])
    if missing is not None and config.show_missing_grey:
        ax.contourf(xi, yi, np.where(missing, 1.0, np.nan),
                    levels=[0.5, 1.5], colors=[COLOR_MISSING])
    del xi, yi, zi, valid, missing

    ax.add_patch(Circle((x_mid, y_mid), radius, fill=False, color="#888888", linewidth=1.0))
    ax.set_aspect("equal")
    ax.axis("off")

    if extrapolate:
        ax.text(0.5, 0.005, "extrapolated", transform=ax.transAxes,
                ha="center", va="bottom", fontsize=6, style="italic", color="#C0392B")

    _cov = (f"{n_meas}/{len(lot_sites)}"
            if (lot_sites is not None and len(lot_sites)) else f"{n_meas}")
    ax.text(0.01, 0.99, f"meas {_cov}", transform=ax.transAxes, ha="left", va="top",
            fontsize=5.5, color="#555555")

    if show_title:
        ax.set_title(f"W: {wafer_id}", fontsize=10, fontweight="bold")
    if show_legend:
        _attach_legend(ax, config, extrapolate=extrapolate)
    return True


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _attach_legend(ax: Axes, config: PlotConfig,
                   extrapolate: bool = False, discrete: bool = False) -> None:
    cs = config.color_scheme
    handles = [
        Patch(facecolor=cs.low,  edgecolor="black", label=f"< {config.t_low:g}"),
        Patch(facecolor=cs.mid,  edgecolor="black",
              label=f"{config.t_low:g} – {config.t_high:g}"),
        Patch(facecolor=cs.high, edgecolor="black", label=f"≥ {config.t_high:g}"),
    ]
    if config.show_missing_grey and (discrete or not extrapolate):
        label = "Untested" if discrete else "No data"
        handles.append(Patch(facecolor=COLOR_MISSING, edgecolor="black", label=label))
    ax.legend(
        handles=handles,
        loc="center left",
        bbox_to_anchor=(1.05, 0.5),
        title="Thresholds",
        fontsize=9,
        frameon=True,
        shadow=True,
    )
