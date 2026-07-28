"""
data_loader.py
==============
Reads and validates wafer measurement files (CSV / whitespace-delimited).
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from .exceptions import DataLoadError
from .logger import log

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

    log.info("Loading: %s  (%.1f MB)", filepath.name,
             filepath.stat().st_size / 1_048_576)

    raw = _try_read(filepath)

    if raw.empty:
        raise DataLoadError(f"File is empty: {filepath}")

    # Case 1: already split into 5+ columns
    if raw.shape[1] >= 5:
        lot_series   = raw.iloc[:, 0].astype(str).str.strip()
        wafer_series = raw.iloc[:, 1].astype(str).str.strip()
        x_series     = pd.to_numeric(raw.iloc[:, 2], errors="coerce").astype("float32")
        y_series     = pd.to_numeric(raw.iloc[:, 3], errors="coerce").astype("float32")
        val_series   = pd.to_numeric(raw.iloc[:, 4], errors="coerce").astype("float32")

    # Case 2: combined first column
    elif raw.shape[1] >= 4:
        combined = raw.iloc[:, 0].astype(str).str.strip()

        # Split "LotID WaferID" in one vectorized pass. str.split(n=1, expand)
        # is far faster on large files than split()+map(len)+str[0]/str[1],
        # which each iterate in Python over every row.
        split_df = combined.str.split(n=1, expand=True)
        if split_df.shape[1] < 2 or split_df.iloc[:, 1].isna().any():
            raise DataLoadError(
                "Could not split lot+wafer column. "
                "Expected either 5 columns or 'LotID WaferID' in column 0."
            )

        lot_series   = split_df.iloc[:, 0].str.strip()
        wafer_series = split_df.iloc[:, 1].str.strip()

        # 🚨 extra protection
        lot_series = lot_series.replace({"": "UNKNOWN"})
        del combined, split_df  # no longer needed

        x_series   = pd.to_numeric(raw.iloc[:, 1], errors="coerce").astype("float32")
        y_series   = pd.to_numeric(raw.iloc[:, 2], errors="coerce").astype("float32")
        val_series = pd.to_numeric(raw.iloc[:, 3], errors="coerce").astype("float32")

    else:
        raise DataLoadError(
            f"File has only {raw.shape[1]} column(s); at least 4 are required."
        )

    # Free the raw object-dtype DataFrame before building the typed one —
    # without this, raw + the five series + the final df all coexist in memory.
    del raw

    df = pd.DataFrame({
        "lot":   lot_series.astype("category"),
        "wafer": wafer_series.astype("category"),
        "x":     x_series,
        "y":     y_series,
        "value": val_series,
    })

    # Free the intermediate series now that df owns the data.
    del lot_series, wafer_series, x_series, y_series, val_series

    df.dropna(inplace=True)

    df = df[
        df["lot"].astype(str).str.len().gt(0) &
        df["wafer"].astype(str).str.len().gt(0)
    ]

    if df.empty:
        raise DataLoadError(
            "No valid rows remain after parsing. "
            "Check that the file format and column indices are correct."
        )

    log.info("Loaded %d rows, %d wafers",
             len(df), df.groupby(["lot", "wafer"]).ngroups)
    return df.reset_index(drop=True)


def _try_read(filepath: Path) -> pd.DataFrame:
    """Read the file into a DataFrame, fast.

    Two things keep large files fast:
      * the C engine with an explicit delimiter (tab, then comma) — the regex
        whitespace strategy uses pandas' pure-Python engine, which is minutes-
        slow on large files (it froze the UI on a 388k-row file) and is only a
        last resort;
      * numeric columns are parsed NATIVELY by the C engine instead of being
        read as text and converted afterwards with pd.to_numeric (that
        conversion alone was ~2.4 s of a 388k-row load). Only the identifier
        columns are forced to text so leading-zero wafer ids like "01" survive:
        col 0 always (lot, or "lot wafer"), and col 1 too when lot/wafer are
        already split into their own columns (5+ column files).
    """
    last_exc: Exception | None = None

    for label, sep in (("tab-delimited", "\t"), ("CSV (comma)", ",")):
        try:
            sample = pd.read_csv(filepath, header=None, sep=sep, engine="c",
                                 dtype=str, nrows=50)
        except Exception as exc:
            last_exc = exc
            continue
        if sample.shape[1] < 4:
            print(f"  {label}: only {sample.shape[1]} column(s) — skipping.")
            continue
        text_cols = {0: "str"} if sample.shape[1] == 4 else {0: "str", 1: "str"}
        try:
            df = pd.read_csv(filepath, header=None, sep=sep, engine="c", dtype=text_cols)
        except Exception as exc:
            print(f"  {label} parse failed: {exc}")
            last_exc = exc
            continue
        for c in text_cols:                 # keep empty identifiers as '' not NaN
            df[c] = df[c].fillna("")
        print(f"✓ Parsed '{filepath.name}' as {label}.")
        return df

    # Last resort: whitespace via the slow pure-Python regex engine.
    try:
        df = pd.read_csv(filepath, header=None, sep=r"\s+", engine="python",
                         dtype=str, keep_default_na=False)
        if df.shape[1] >= 4:
            print(f"✓ Parsed '{filepath.name}' as whitespace (regex, slow).")
            return df
    except Exception as exc:
        last_exc = exc

    raise DataLoadError(
        f"Could not parse '{filepath.name}' as CSV or delimited text. "
        f"Last error: {last_exc}"
    )
