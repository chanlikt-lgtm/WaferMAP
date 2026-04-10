"""
geometry.py
===========
Pure mathematical / geometric operations used during wafer plotting.

All functions are stateless and free of side-effects — no Matplotlib,
no pandas, no file I/O.  Easy to unit-test in isolation.

Public API
----------
signed_log10(a, eps)
apply_transforms(x, y, mirror_x, mirror_y, rot_deg)
build_wafer_grid(x, y, z, resolution, radius_factor)
"""
from __future__ import annotations

import numpy as np
from numpy.typing import NDArray
from scipy.interpolate import griddata

__all__ = ["signed_log10", "apply_transforms", "build_wafer_grid"]


def signed_log10(a: NDArray, eps: float = 1e-15) -> NDArray:
    """
    Sign-preserving base-10 logarithm.

    Handles zero and negative values without raising by clamping the
    magnitude to *eps* before taking the log.

    Parameters
    ----------
    a : array-like
    eps : float
        Floor applied to |a| before log, preventing log(0).

    Returns
    -------
    NDArray
        sign(a) * log10(max(|a|, eps))
    """
    a = np.asarray(a, dtype=float)
    return np.sign(a) * np.log10(np.maximum(np.abs(a), eps))


def apply_transforms(
    x: NDArray,
    y: NDArray,
    mirror_x: bool,
    mirror_y: bool,
    rot_deg: int,
) -> tuple[NDArray, NDArray]:
    """
    Apply mirror and clockwise-rotation transforms centred on the data centroid.

    Transform order: mirror first, then rotate.

    Parameters
    ----------
    x, y    : 1-D coordinate arrays.
    mirror_x: Flip horizontally (negate X around centroid).
    mirror_y: Flip vertically   (negate Y around centroid).
    rot_deg : Clockwise rotation in degrees — must be one of {0, 90, 180, 270}.

    Returns
    -------
    x_out, y_out : transformed coordinate arrays (same shape as input).
    """
    # Fast path: no transform needed — return original arrays unchanged
    if not (mirror_x or mirror_y or rot_deg):
        return x, y

    x = x.copy()
    y = y.copy()

    x_mid = (x.max() + x.min()) / 2.0
    y_mid = (y.max() + y.min()) / 2.0

    # Centre on origin
    xc, yc = x - x_mid, y - y_mid

    if mirror_x:
        xc = -xc
    if mirror_y:
        yc = -yc

    # Clockwise rotation mapping (standard 2-D rotation with sign flip)
    _rot = {
        90:  ( yc, -xc),
        180: (-xc, -yc),
        270: (-yc,  xc),
    }
    if rot_deg in _rot:
        xc, yc = _rot[rot_deg]

    return xc + x_mid, yc + y_mid


def build_wafer_grid(
    x: NDArray,
    y: NDArray,
    z: NDArray,
    resolution: int   = 150,
    radius_factor: float = 1.05,
) -> tuple[NDArray, NDArray, NDArray, float, float, float]:
    """
    Build a 2-D interpolated grid suitable for wafer contour plotting.

    Algorithm
    ---------
    1. Compute centroid (x_mid, y_mid) and wafer radius from data extents.
    2. Create a square meshgrid covering the wafer disc.
    3. Interpolate *z* onto the grid using linear interpolation, filling
       any remaining NaN regions with nearest-neighbour values.
    4. Clamp interpolated values to [z.min(), z.max()] to suppress
       overshoot artefacts.
    5. Mask grid cells that lie outside the wafer boundary with NaN.

    Parameters
    ----------
    x, y, z     : 1-D measurement arrays (same length).
    resolution  : Number of grid points along each axis.
    radius_factor: Multiplier applied to half the data span to set the
                   wafer boundary radius (> 1.0 adds a small margin).

    Returns
    -------
    xi, yi : 2-D meshgrid arrays.
    zi     : Interpolated values (NaN outside wafer boundary).
    x_mid, y_mid : Centroid coordinates.
    radius       : Wafer boundary radius used for masking.
    """
    x_mid = (x.max() + x.min()) / 2.0
    y_mid = (y.max() + y.min()) / 2.0

    max_range = max(x.max() - x.min(), y.max() - y.min())
    if max_range == 0:
        max_range = 10.0          # Bug-fix: original had '==' instead of '='

    radius = (max_range / 2.0) * radius_factor

    lin_x = np.linspace(x_mid - radius, x_mid + radius, resolution, dtype=np.float32)
    lin_y = np.linspace(y_mid - radius, y_mid + radius, resolution, dtype=np.float32)
    xi, yi = np.meshgrid(lin_x, lin_y)
    del lin_x, lin_y  # consumed by meshgrid; free them now

    # Primary interpolation — scipy works in float64 internally; cast result back
    zi = griddata((x, y), z, (xi, yi), method="linear").astype(np.float32)

    # Fill NaN holes with nearest-neighbour (avoids blank patches near edges)
    nan_mask = np.isnan(zi)
    if nan_mask.any():
        zi[nan_mask] = griddata(
            (x, y), z,
            (xi[nan_mask], yi[nan_mask]),
            method="nearest",
        )
    del nan_mask  # free ~resolution² booleans

    # Clamp to suppress Scipy's occasional interpolation overshoot
    zi = np.clip(zi, z.min(), z.max(), out=zi)  # out=zi avoids allocating a new array

    # Mask outside the wafer circle
    outside = (xi - x_mid) ** 2 + (yi - y_mid) ** 2 > radius ** 2
    zi[outside] = np.nan
    del outside  # free ~resolution² booleans

    return xi, yi, zi, x_mid, y_mid, radius
