"""
exporters/csv_exporter.py
=========================
Exports a per-wafer colour-zone presence summary as a CSV file.

Each row represents one wafer and records whether any die point fell
inside the green, yellow, or red zone (1 = present, 0 = absent).

Public API
----------
export_color_summary_csv(filepath, config, out_dir) -> str | None
"""
from __future__ import annotations

import os
from datetime import datetime

import numpy as np
import pandas as pd

from ..config import PlotConfig
from ..data_loader import read_wafer_data

__all__ = ["export_color_summary_csv"]


def export_color_summary_csv(
    filepath: str,
    config: PlotConfig,
    out_dir: str,
) -> str | None:
    """
    Build and save a CSV summarising colour-zone presence per wafer.

    Parameters
    ----------
    filepath : str
        Original measurement file (re-read here for self-containment).
    config   : PlotConfig — thresholds and high_is_green flag are used.
    out_dir  : Directory where the CSV will be saved.

    Returns
    -------
    str | None
        Absolute path to the saved CSV, or None if no valid wafers found.
    """
    try:
        data = read_wafer_data(filepath)
    except Exception as exc:
        print(f"⚠  CSV export skipped — could not reload data: {exc}")
        return None

    if data.empty:
        return None

    rows: list[dict] = []

    for lot_id, lot_df in data.groupby("lot"):
        for wid, w_df in lot_df.groupby("wafer"):
            z = w_df["value"].values
            if len(z) < 4:
                continue

            has_low  = bool(np.any(z  < config.t_low))
            has_mid  = bool(np.any((z >= config.t_low) & (z <= config.t_high)))
            has_high = bool(np.any(z  > config.t_high))

            if config.high_is_green:
                green, yellow, red = int(has_high), int(has_mid), int(has_low)
            else:
                green, yellow, red = int(has_low),  int(has_mid), int(has_high)

            rows.append({
                "Lot ID":   lot_id,
                "Wafer ID": wid,
                "Green":    green,
                "Yellow":   yellow,
                "Red":      red,
            })

    if not rows:
        return None

    df_out    = pd.DataFrame(rows)
    base_name = os.path.splitext(os.path.basename(filepath))[0]
    now       = datetime.now().strftime("%Y_%m_%d_%H%M%S")
    csv_path  = os.path.join(
        out_dir,
        f"{base_name}{config.log_suffix}_color_summary_{now}.csv",
    )
    df_out.to_csv(csv_path, index=False)
    print(f"✓ CSV saved: {csv_path}")
    return csv_path
