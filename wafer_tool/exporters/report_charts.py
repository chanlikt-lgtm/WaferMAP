"""
exporters/report_charts.py
===========================
Headless (matplotlib-only) renderers for the report's overview charts — the
Threshold Scatter and the value Histogram — so the PDF/PPTX can carry the same
front-page summaries the GUI shows in its Scatter / Histogram tabs.

These draw onto a caller-supplied Axes (Agg backend), keeping them safe to call
from the report pipeline / worker threads. Colours follow the run's
``PlotConfig.color_scheme`` so the charts match the wafer maps in the same
report. Kept intentionally independent of the Qt canvases in the GUI.
"""
from __future__ import annotations

import numpy as np
from matplotlib.lines import Line2D
from matplotlib.patches import Patch

from ..config import PlotConfig

__all__ = ["draw_scatter", "draw_histogram", "wafer_codes_and_names"]

_MAX_SCATTER = 200_000   # beyond this, overplotting hides points anyway — sample
_MAX_XTICKS  = 60        # per-wafer x tick labels above this are unreadable/slow


def _zone_colors(config: PlotConfig) -> tuple[str, str, str]:
    cs = config.color_scheme
    return cs.low, cs.mid, cs.high


def draw_scatter(
    ax,
    z: np.ndarray,
    config: PlotConfig,
    wafer_codes: np.ndarray | None = None,
    wafer_names: list[str] | None = None,
    title: str | None = None,
) -> None:
    """Threshold scatter of all die values, colour-coded by zone.

    Points are drawn per wafer (jittered into a strip) when wafer labels are
    supplied, else against die index. Large sets are randomly downsampled for
    display; the threshold band shading uses the full range.
    """
    lo = min(config.t_low, config.t_high)
    hi = max(config.t_low, config.t_high)
    c_low, c_mid, c_high = _zone_colors(config)

    z_full = np.asarray(z, dtype=np.float32)
    if z_full.size == 0:
        ax.text(0.5, 0.5, "No data", ha="center", va="center",
                transform=ax.transAxes)
        ax.set_xticks([]); ax.set_yticks([])
        return

    n_full = z_full.size
    wnames = wafer_names or []
    n_wafers = len(wnames)

    # ── Downsample for display ────────────────────────────────────────────
    rng = np.random.default_rng(seed=0)
    if n_full > _MAX_SCATTER:
        keep = np.sort(rng.choice(n_full, size=_MAX_SCATTER, replace=False))
        z_s = z_full[keep]
        wc_s = wafer_codes[keep] if wafer_codes is not None else None
    else:
        z_s = z_full
        wc_s = wafer_codes

    # ── X coordinates: wafer strip (jittered) or die index ────────────────
    if wc_s is not None and n_wafers > 0:
        jitter = rng.uniform(-0.35, 0.35, size=z_s.size).astype(np.float32)
        x = wc_s.astype(np.float32) + jitter
    else:
        x = np.arange(z_s.size, dtype=np.float32)

    # ── Threshold band shading (full-range) ───────────────────────────────
    pad = max((z_full.max() - z_full.min()) * 0.05, 1e-12)
    y_bot, y_top = z_full.min() - pad, z_full.max() + pad
    ax.axhspan(y_bot, lo,    facecolor=c_low,  alpha=0.18)
    ax.axhspan(lo,    hi,    facecolor=c_mid,  alpha=0.18)
    ax.axhspan(hi,    y_top, facecolor=c_high, alpha=0.18)

    for val in (lo, hi):
        ax.axhline(val, color="#333", linewidth=1.2, linestyle="--")
        ax.text(0.995, val, f"{val:.3g}", transform=ax.get_yaxis_transform(),
                ha="right", va="bottom", fontsize=8,
                bbox=dict(facecolor="white", edgecolor="#aaa",
                          boxstyle="round,pad=0.2", alpha=0.9))

    # ── Points, one scatter per zone (distinct shape + colour per zone) ───
    # low = diamond, mid = square, high = circle — shape distinguishes zones
    # even in greyscale / print.
    kw = dict(s=20, alpha=0.6, linewidths=0.2, edgecolors="black")
    ax.scatter(x[z_s < lo],                    z_s[z_s < lo],                    color=c_low,  marker="D", **kw)
    ax.scatter(x[(z_s >= lo) & (z_s <= hi)],   z_s[(z_s >= lo) & (z_s <= hi)],   color=c_mid,  marker="s", **kw)
    ax.scatter(x[z_s > hi],                    z_s[z_s > hi],                    color=c_high, marker="o", **kw)
    ax.set_ylim(y_bot, y_top)

    # ── X axis ────────────────────────────────────────────────────────────
    if wnames:
        parts = [n.rsplit(" ", 1) for n in wnames]
        lots = [p[0] for p in parts]
        wnums = [p[-1] for p in parts]
        common_lot = lots[0] if len(set(lots)) == 1 else None
        tick_labels = wnums if common_lot else wnames
        if n_wafers > _MAX_XTICKS:
            idx = np.unique(np.linspace(0, n_wafers - 1, _MAX_XTICKS).round().astype(int))
            ax.set_xticks(idx)
            ax.set_xticklabels([tick_labels[i] for i in idx], rotation=90, fontsize=6)
        else:
            ax.set_xticks(np.arange(n_wafers))
            ax.set_xticklabels(tick_labels, rotation=90 if n_wafers > 20 else 0, fontsize=7)
        ax.set_xlim(-0.6, n_wafers - 0.4)
        shown = f"  (showing {z_s.size:,} of {n_full:,} dies)" if n_full > _MAX_SCATTER else ""
        xlabel = (f"Wafer — Lot {common_lot}{shown}" if common_lot else f"Wafer{shown}")
    else:
        ax.set_xlim(-n_full * 0.01, n_full * 1.01)
        xlabel = (f"Die index  (showing {z_s.size:,} of {n_full:,})"
                  if n_full > _MAX_SCATTER else "Die index")

    ax.set_ylabel("Value", fontsize=10, fontweight="bold")
    ax.set_xlabel(xlabel, fontsize=9, color="#555")
    ax.set_title(title or "Threshold Scatter", fontsize=13, fontweight="bold")
    ax.grid(axis="y", linestyle="--", alpha=0.35, color="#ccc")

    # Legend mirrors the per-zone shape + colour.
    def _mk(marker, color, label):
        return Line2D([0], [0], marker=marker, linestyle="", markerfacecolor=color,
                      markeredgecolor="black", markersize=8, label=label)
    handles = [
        _mk("D", c_low,  f"< {lo:.3g}"),
        _mk("s", c_mid,  f"{lo:.3g} – {hi:.3g}"),
        _mk("o", c_high, f"≥ {hi:.3g}"),
    ]
    ax.legend(handles=handles, loc="upper right", fontsize=8,
              framealpha=0.85, edgecolor="#aaa")


def draw_histogram(
    ax,
    z: np.ndarray,
    config: PlotConfig,
    title: str | None = None,
) -> None:
    """Value distribution with bars colour-coded by threshold zone."""
    lo = min(config.t_low, config.t_high)
    hi = max(config.t_low, config.t_high)
    c_low, c_mid, c_high = _zone_colors(config)

    z = np.asarray(z, dtype=np.float32)
    if z.size == 0:
        ax.text(0.5, 0.5, "No data", ha="center", va="center",
                transform=ax.transAxes)
        ax.set_xticks([]); ax.set_yticks([])
        return

    counts, bin_edges, patches = ax.hist(z, bins=60, edgecolor="none")
    for patch, left in zip(patches, bin_edges[:-1]):
        patch.set_facecolor(c_low if left < lo else c_mid if left <= hi else c_high)

    y_max = counts.max() if counts.size else 1
    for val in (lo, hi):
        ax.axvline(val, color="#333", linewidth=1.3, linestyle="--", zorder=5)
        ax.text(val, y_max * 0.98, f"{val:.3g}", rotation=90, ha="right", va="top",
                fontsize=8, bbox=dict(facecolor="white", edgecolor="#aaa",
                                      boxstyle="round,pad=0.2", alpha=0.9))

    import matplotlib.ticker as mticker
    ax.xaxis.set_major_formatter(
        mticker.FuncFormatter(lambda v, _: f"{v:.3g}" if v != 0 else "0"))
    ax.tick_params(axis="x", labelrotation=30)

    handles = [
        Patch(facecolor=c_low,  edgecolor="black", label=f"< {lo:.3g}"),
        Patch(facecolor=c_mid,  edgecolor="black", label=f"{lo:.3g} – {hi:.3g}"),
        Patch(facecolor=c_high, edgecolor="black", label=f"≥ {hi:.3g}"),
    ]
    ax.legend(handles=handles, loc="upper right", fontsize=8,
              framealpha=0.85, edgecolor="#aaa")
    ax.set_xlabel("Measurement Value", fontsize=10, fontweight="bold")
    ax.set_ylabel("Count", fontsize=10, fontweight="bold")
    ax.set_title(title or "Data Distribution", fontsize=13, fontweight="bold")
    ax.grid(axis="y", linestyle="--", alpha=0.4, color="#ccc", zorder=0)


def wafer_codes_and_names(data):
    """Build per-die int32 wafer codes and ordered 'lot wafer' labels from a
    report DataFrame (lot, wafer columns), matching the GUI scatter's X axis."""
    cat = (data["lot"].astype(str) + " " + data["wafer"].astype(str)).astype("category")
    codes = cat.cat.codes.to_numpy(dtype=np.int32, copy=True)
    names = list(cat.cat.categories)
    return codes, names
