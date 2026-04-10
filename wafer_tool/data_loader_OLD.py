"""
data_loader.py
==============
Reads and validates wafer measurement files (CSV / whitespace-delimited).
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from .exceptions import DataLoadError

__all__ = ["read_wafer_data"]


def read_wafer_data(
    filepath: str | Path,
    lot_col: int = 0,
    x_col: int = 1,
    y_col: int = 2,
    val_col: int = 3,
) -> pd.DataFrame:

    filepath = Path(filepath)
    if not filepath.exists():
        raise DataLoadError(f"File not found: {filepath}")

    raw = _try_read(filepath)

    if raw.empty:
        raise DataLoadError(f"File is empty: {filepath}")

    # Case 1: already split into 5+ columns
    if raw.shape[1] >= 5:
        lot_series = raw.iloc[:, 0].astype(str).str.strip()
        wafer_series = raw.iloc[:, 1].astype(str).str.strip()

        x_series = pd.to_numeric(raw.iloc[:, 2], errors="coerce").astype("float32")
        y_series = pd.to_numeric(raw.iloc[:, 3], errors="coerce").astype("float32")
        val_series = pd.to_numeric(raw.iloc[:, 4], errors="coerce").astype("float32")

    # Case 2: combined first column
    elif raw.shape[1] >= 4:
        combined = raw.iloc[:, 0].astype(str).str.strip()

        # Split into lot + wafer
        id_split = combined.str.extract(r"^(.*?)\s+(\S+)$")

        if id_split.isna().any(axis=None):
            raise DataLoadError(
                "Could not split lot+wafer column. "
                "Expected either 5 columns or 'LotID WaferID' in column 0."
            )

        lot_series = id_split[0].astype(str).str.strip()
        wafer_series = id_split[1].astype(str).str.strip()

        x_series = pd.to_numeric(raw.iloc[:, 1], errors="coerce").astype("float32")
        y_series = pd.to_numeric(raw.iloc[:, 2], errors="coerce").astype("float32")
        val_series = pd.to_numeric(raw.iloc[:, 3], errors="coerce").astype("float32")

    else:
        raise DataLoadError(
            f"File has only {raw.shape[1]} column(s); at least 4 are required."
        )

    df = pd.DataFrame({
        "lot": lot_series,
        "wafer": wafer_series,
        "x": x_series,
        "y": y_series,
        "value": val_series,
    })

    df = df.dropna(subset=["lot", "wafer", "x", "y", "value"])

    df = df[
        df["lot"].astype(str).str.len().gt(0) &
        df["wafer"].astype(str).str.len().gt(0)
    ]

    if df.empty:
        raise DataLoadError(
            "No valid rows remain after parsing. "
            "Check that the file format and column indices are correct."
        )

    df["lot"] = df["lot"].astype("category")
    df["wafer"] = df["wafer"].astype("category")

    return df.reset_index(drop=True)


def _try_read(filepath: Path) -> pd.DataFrame:

    strategies = [
        ("CSV (comma)", {"sep": ","}),
        ("whitespace / tab", {"sep": r"\s+"}),
    ]

    last_exc: Exception | None = None

    for label, kwargs in strategies:
        try:
            df = pd.read_csv(
                filepath,
                header=None,
                engine="python",
                **kwargs,
            )
            if df.shape[1] >= 4:
                print(f"✓ Parsed '{filepath.name}' as {label}.")
                return df

            print(f"  {label}: only {df.shape[1]} column(s) — skipping.")
        except Exception as exc:
            print(f"  {label} parse failed: {exc}")
            last_exc = exc

    raise DataLoadError(
        f"Could not parse '{filepath.name}' as CSV or delimited text. "
        f"Last error: {last_exc}"
    )
