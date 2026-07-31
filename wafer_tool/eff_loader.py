"""
eff_loader.py
=============
Self-contained reader for AMD/eSquare **.eff** extraction files, added so the
Wafer Map Tool can ingest raw ``.eff`` files directly instead of only the
pre-converted per-parameter ``.txt`` files.

An ``.eff`` file is a semicolon-delimited text export.  After a block of
``<<Section>>`` metadata it carries a set of ``<...>`` header rows followed by
the measurement data rows::

    <DataType>;Text;Int;Int;Int;...;Double;Double;...
    <+ParameterName>;Lot;Wafer;X;Y;...;RON_VD__10_75;...
    <SourceTable>;;;MeasPartPos;MeasPartPos;...;MeasPartVals;...
    <LIMIT:SPEC:LOWER_VALUE>;;;;;...;0.0;...
    ...
    <data row>;1E351778;01;8;5;...;-113.25;...

Two things this module exposes:

``scan_eff(path)``
    Fast, header-only scan.  Returns an :class:`EffScan` describing the
    auto-detected coordinate columns (``lot``/``wafer``/``x``/``y`` — always
    required) and the list of selectable measurement :class:`EffParameter`
    objects (min 1, max = however many the file has).

``extract_parameters(path, indices, out_base_dir, ...)``
    Single streaming pass over the whole file.  For every selected parameter it
    writes one ``lot wafer<TAB>x<TAB>y<TAB>value`` text file into its *own*
    sub-folder ``<out_base_dir>/<parameter>/<parameter>.txt`` — the exact
    4-column layout :func:`wafer_tool.data_loader.read_wafer_data` already
    accepts.  That per-parameter folder then becomes the home for every image /
    PDF / PPTX the report pipeline produces for that parameter.

The coordinate-resolution and measurement-column rules mirror the standalone
``eff_converter`` tool so both produce identical parameter sets from the same
file.
"""
from __future__ import annotations

import glob
import os
import re
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from .logger import log

__all__ = [
    "EffParameter",
    "EffScan",
    "EffScanError",
    "scan_eff",
    "extract_parameters",
    "extract_single_param_df",
    "flatten_param_pngs",
    "safe_param_name",
]

# Characters that are illegal in Windows file/folder names — parameter names
# such as "GK.RON_VD/10" must be sanitised before they become folder names.
_UNSAFE_CHARS = re.compile(r'[<>:"/\\|?*]')
# Column names that are coordinates, never selectable measurement parameters.
_COORD_KEYS = {"lot", "lotnumber", "wafer", "x", "y"}
# Values with magnitude >= this are sentinel/invalid readings in eSquare data.
_INVALID_MAGNITUDE = 1e10
_PROGRESS_UPDATE_STEPS = 200
_WRITE_BUFFER_CHARS = 1 << 16


class EffScanError(Exception):
    """Raised when an .eff file cannot be understood (no header / no coords)."""


@dataclass(slots=True)
class EffParameter:
    """One selectable measurement parameter found in an .eff file."""
    index: int          # column index in the raw row
    name: str           # original parameter name from <+ParameterName>
    dtype: str          # value from <DataType> (e.g. "Double"), may be ""
    has_limits: bool    # True when spec limits are defined for this column
    limit_lower: float | None = None   # <LIMIT:SPEC:LOWER_VALUE> for this column
    limit_upper: float | None = None   # <LIMIT:SPEC:UPPER_VALUE> for this column


@dataclass(slots=True)
class EffScan:
    """Result of a header-only scan of an .eff file."""
    path: str
    declared_rows: int
    declared_cols: int
    coord_indices: dict[str, int]        # keys: lot, wafer, x, y
    parameters: list[EffParameter] = field(default_factory=list)

    @property
    def filename(self) -> str:
        return os.path.basename(self.path)

    @property
    def has_coords(self) -> bool:
        return {"lot", "wafer", "x", "y"} <= set(self.coord_indices)

    def parameter_by_index(self, index: int) -> EffParameter | None:
        for p in self.parameters:
            if p.index == index:
                return p
        return None


# ---------------------------------------------------------------------------
# Public: fast header scan
# ---------------------------------------------------------------------------

def scan_eff(path: str | Path) -> EffScan:
    """Read only the header of *path* and return an :class:`EffScan`.

    Stops as soon as the first data row is reached, so this is fast even for
    multi-gigabyte files (the header lives in the first few kilobytes).
    """
    path = str(path)
    if not os.path.isfile(path):
        raise EffScanError(f"File not found: {path}")

    declared_rows = 0
    declared_cols = 0
    headers_list: list[str] = []
    source_tables_list: list[str] = []
    data_types_list: list[str] = []
    limit_lower_list: list[str] = []
    limit_upper_list: list[str] = []
    limit_target_list: list[str] = []

    with open(path, "r", encoding="utf-8", errors="ignore") as fh:
        for line in fh:
            if not line.strip():
                continue

            row = [item.strip('"') for item in line.rstrip("\n").split(";")]
            if not row:
                continue

            first = row[0]
            if first.startswith("<"):
                header = first.lower()
                # The <<EFF>> metadata line carries "Rows=" / "Columns=" as
                # semicolon-separated tokens, e.g.
                #   <<EFF:1.00>>;Headers=24;Rows=1527;Columns=109;...
                if header.startswith("<<") and (declared_rows == 0 or declared_cols == 0):
                    for token in row:
                        low = token.lower()
                        if declared_rows == 0 and low.startswith("rows="):
                            declared_rows = _safe_int(token.split("=", 1)[1])
                        elif declared_cols == 0 and low.startswith("columns="):
                            declared_cols = _safe_int(token.split("=", 1)[1])
                if header == "<+parametername>":
                    headers_list = row
                elif header == "<sourcetable>":
                    source_tables_list = row
                elif header == "<datatype>":
                    data_types_list = row
                elif header == "<limit:spec:lower_value>":
                    limit_lower_list = row
                elif header == "<limit:spec:upper_value>":
                    limit_upper_list = row
                elif header == "<limit:spec:target_value>":
                    limit_target_list = row
                continue

            # First non-header, non-metadata row => data has started.
            if headers_list:
                break
            # No parameter header yet: keep scanning (still in metadata).

    if not headers_list:
        raise EffScanError(
            "No <+ParameterName> header row found — this does not look like a "
            "valid .eff extraction file."
        )

    coord_indices = _resolve_coord_indices(headers_list)
    parameters = _collect_parameters(
        headers_list, source_tables_list, data_types_list,
        limit_lower_list, limit_upper_list, limit_target_list,
    )

    if not parameters:
        raise EffScanError(
            "No measurement parameters found in this .eff file."
        )

    log.info(
        "Scanned EFF %s: %d params, ~%d rows, %d cols",
        os.path.basename(path), len(parameters), declared_rows, declared_cols,
    )
    return EffScan(
        path=path,
        declared_rows=declared_rows,
        declared_cols=declared_cols or len(headers_list) - 1,
        coord_indices=coord_indices,
        parameters=parameters,
    )


# ---------------------------------------------------------------------------
# Public: streaming extraction of selected parameters
# ---------------------------------------------------------------------------

@dataclass(slots=True)
class ExtractedParameter:
    """Where a single parameter's data landed on disk."""
    name: str           # original parameter name
    safe_name: str      # sanitised, unique folder/file stem
    folder: str         # per-parameter output folder
    txt_path: str       # the lot/wafer/x/y/value text file
    rows_written: int = 0


def extract_parameters(
    path: str | Path,
    indices: list[int],
    out_base_dir: str | Path,
    scan: EffScan | None = None,
    filters: dict[int, tuple[float, float]] | None = None,
    progress_cb: Callable[[int, int], None] | None = None,
    stop_cb: Callable[[], bool] | None = None,
) -> list[ExtractedParameter]:
    """Stream *path* once, writing one text file per selected parameter.

    Parameters
    ----------
    path : .eff file to read.
    indices : column indices (``EffParameter.index``) to extract.  Must be >= 1.
    out_base_dir : root folder; each parameter gets ``<root>/<parameter>/``.
    scan : optional pre-computed :class:`EffScan` (avoids re-reading the header).
    filters : optional ``{column_index: (min, max)}`` — dies whose value falls
        outside a parameter's ``[min, max]`` are excluded from that parameter's
        output (in addition to the always-on ``>= 1e10`` sentinel). Parameters
        absent from the mapping are not filtered.
    progress_cb(rows_done, rows_total) : optional progress callback.  Raising
        from it (as the worker does on cancel) aborts the pass cleanly.
    stop_cb() -> bool : optional cooperative-cancel check.

    Returns the list of :class:`ExtractedParameter` (in the given order).
    """
    path = str(path)
    out_base_dir = str(out_base_dir)
    if scan is None:
        scan = scan_eff(path)
    if not indices:
        raise ValueError("Select at least one parameter to extract.")

    coord = scan.coord_indices
    min_coord_col = max(coord.values())

    # Build one output target per selected parameter.
    targets: list[ExtractedParameter] = []
    used_names: set[str] = set()
    handles: dict[int, _BufferedWriter] = {}
    for idx in indices:
        param = scan.parameter_by_index(idx)
        name = param.name if param else f"col{idx}"
        safe = _reserve_name(safe_param_name(name), used_names)
        folder = os.path.join(out_base_dir, safe)
        os.makedirs(folder, exist_ok=True)
        txt_path = os.path.join(folder, f"{safe}.txt")
        extracted = ExtractedParameter(name=name, safe_name=safe,
                                       folder=folder, txt_path=txt_path)
        targets.append(extracted)
        handles[idx] = _BufferedWriter(txt_path)

    total = scan.declared_rows or _estimate_rows(path)
    update_every = max(total // _PROGRESS_UPDATE_STEPS, 1)
    max_col_needed = max(min_coord_col, max(indices))

    rows_done = 0
    data_started = False
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as fh:
            for line in fh:
                if stop_cb is not None and stop_cb():
                    break

                if line[0:1] == "<" or not line.strip():
                    # header/metadata rows never start a data value we care
                    # about; only a genuine data row lacks the leading '<'.
                    if not data_started:
                        continue
                    # after data has started, a stray '<' line is unexpected;
                    # skip defensively.
                    if line[0:1] == "<":
                        continue

                row = [item.strip('"') for item in line.rstrip("\n").split(";")]
                if len(row) <= max_col_needed:
                    continue

                data_started = True
                lot_val = row[coord["lot"]]
                wafer_val = row[coord["wafer"]].zfill(2)
                x_val = row[coord["x"]]
                y_val = row[coord["y"]]
                if not lot_val or not x_val or not y_val:
                    continue
                prefix = f"{lot_val} {wafer_val}\t{x_val}\t{y_val}\t"

                for idx in indices:
                    raw = row[idx].strip()
                    if not raw:
                        continue
                    try:
                        val = float(raw)
                    except ValueError:
                        continue
                    if abs(val) >= _INVALID_MAGNITUDE:
                        continue
                    rng = filters.get(idx) if filters else None
                    if rng is not None and (val < rng[0] or val > rng[1]):
                        continue    # outside this parameter's value filter
                    handles[idx].write(prefix + raw + "\n")

                rows_done += 1
                if progress_cb is not None and rows_done % update_every == 0:
                    progress_cb(rows_done, max(total, rows_done))
    finally:
        for writer in handles.values():
            writer.close()

    # Record per-parameter line counts (cheap: the writers tracked them).
    for extracted, idx in zip(targets, indices):
        extracted.rows_written = handles[idx].lines_written

    if progress_cb is not None:
        progress_cb(total, total)

    log.info("Extracted %d parameter(s) from %s", len(targets), os.path.basename(path))
    return targets


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def extract_single_param_df(
    path: str | Path,
    index: int,
    scan: EffScan | None = None,
    max_rows: int | None = None,
    value_range: tuple[float, float] | None = None,
    stop_cb: Callable[[], bool] | None = None,
):
    """Read one parameter of an .eff into an in-memory DataFrame (no disk write).

    Returns a DataFrame with the same columns/dtypes as
    :func:`wafer_tool.data_loader.read_wafer_data` — ``lot`` / ``wafer``
    (category), ``x`` / ``y`` / ``value`` (float32) — so the chart code can
    consume it unchanged.  Used to build the scatter / histogram preview for the
    first selected parameter.  ``max_rows`` caps the scan (a fast look on huge
    files); ``stop_cb`` allows a background worker to abort early.
    """
    import numpy as np
    import pandas as pd

    path = str(path)
    if scan is None:
        scan = scan_eff(path)
    coord = scan.coord_indices
    max_col = max(max(coord.values()), index)

    lots: list[str] = []
    wafers: list[str] = []
    xs: list[str] = []
    ys: list[str] = []
    vals: list[float] = []
    data_started = False

    with open(path, "r", encoding="utf-8", errors="ignore") as fh:
        for line in fh:
            if stop_cb is not None and stop_cb():
                break
            if line[0:1] == "<" or not line.strip():
                if not data_started or line[0:1] == "<":
                    continue
            row = [item.strip('"') for item in line.rstrip("\n").split(";")]
            if len(row) <= max_col:
                continue
            data_started = True
            raw = row[index].strip()
            if not raw:
                continue
            try:
                v = float(raw)
            except ValueError:
                continue
            if abs(v) >= _INVALID_MAGNITUDE:
                continue
            if value_range is not None and (v < value_range[0] or v > value_range[1]):
                continue    # outside the value filter — mirror extract_parameters
            lot = row[coord["lot"]]
            if not lot:
                continue
            lots.append(lot)
            wafers.append(row[coord["wafer"]].zfill(2))
            xs.append(row[coord["x"]])
            ys.append(row[coord["y"]])
            vals.append(v)
            if max_rows and len(vals) >= max_rows:
                break

    df = pd.DataFrame({
        "lot":   pd.Series(lots, dtype="category"),
        "wafer": pd.Series(wafers, dtype="category"),
        "x":     pd.to_numeric(pd.Series(xs), errors="coerce").astype("float32"),
        "y":     pd.to_numeric(pd.Series(ys), errors="coerce").astype("float32"),
        "value": np.asarray(vals, dtype="float32"),
    })
    df.dropna(inplace=True)
    return df.reset_index(drop=True)


def flatten_param_pngs(folder: str) -> None:
    """Move per-wafer PNGs from ``individual_pngs_<ts>/`` up into *folder*.

    The report pipeline writes each wafer image into a timestamped
    ``individual_pngs_<ts>`` subfolder. The EFF workflow wants a single flat
    folder per parameter, so the images join the PDF / PPTX / CSV; the emptied
    subfolder is removed. Failures are non-fatal — a stray file left behind must
    never sink the run.
    """
    for png_dir in glob.glob(os.path.join(folder, "individual_pngs_*")):
        if not os.path.isdir(png_dir):
            continue
        for png in glob.glob(os.path.join(png_dir, "*.png")):
            dest = os.path.join(folder, os.path.basename(png))
            try:
                if os.path.exists(dest):
                    os.remove(dest)
                shutil.move(png, dest)
            except OSError as exc:
                log.warning("Could not move %s -> %s: %s", png, dest, exc)
        try:
            os.rmdir(png_dir)
        except OSError:
            pass  # non-empty (unexpected) — leave it rather than fail


def safe_param_name(name: str) -> str:
    """Sanitise a parameter name into a safe file/folder stem."""
    cleaned = _UNSAFE_CHARS.sub("_", name).strip().strip(".")
    return cleaned or "param"


def _reserve_name(base: str, used: set[str]) -> str:
    if base not in used:
        used.add(base)
        return base
    n = 2
    while f"{base}_{n}" in used:
        n += 1
    unique = f"{base}_{n}"
    used.add(unique)
    return unique


def _resolve_coord_indices(headers_list: list[str]) -> dict[str, int]:
    lower = [h.lower() for h in headers_list]
    lot_key = "lot" if "lot" in lower else ("lotnumber" if "lotnumber" in lower else None)
    missing = [
        key for key in ((lot_key or "lot"), "wafer", "x", "y")
        if key not in lower
    ]
    if lot_key is None or missing:
        raise EffScanError(
            f"Required coordinate column(s) not found: {missing}. "
            f"An .eff file must contain Lot, Wafer, X and Y columns."
        )
    return {
        "lot": lower.index(lot_key),
        "wafer": lower.index("wafer"),
        "x": lower.index("x"),
        "y": lower.index("y"),
    }


def _collect_parameters(
    headers_list: list[str],
    source_tables_list: list[str],
    data_types_list: list[str],
    limit_lower_list: list[str],
    limit_upper_list: list[str],
    limit_target_list: list[str],
) -> list[EffParameter]:
    limit_lists = (limit_lower_list, limit_upper_list, limit_target_list)
    params: list[EffParameter] = []
    for idx, name in enumerate(headers_list):
        if not name or name.startswith("<") or name.lower() in _COORD_KEYS:
            continue
        if not _is_measurement_column(idx, source_tables_list, data_types_list, limit_lists):
            continue
        dtype = data_types_list[idx] if idx < len(data_types_list) else ""
        lower = _cell_float(limit_lower_list, idx)
        upper = _cell_float(limit_upper_list, idx)
        has_limits = any(
            lst and idx < len(lst) and lst[idx] != "" for lst in limit_lists
        )
        params.append(EffParameter(index=idx, name=name, dtype=dtype,
                                    has_limits=has_limits,
                                    limit_lower=lower, limit_upper=upper))
    return params


def _is_measurement_column(
    idx: int,
    source_tables_list: list[str],
    data_types_list: list[str],
    limit_lists: tuple[list[str], ...],
) -> bool:
    """Mirror eff_converter: a column is a measurement value when its
    SourceTable is 'MeasPartVals', or (fallback) it is a floating type that
    carries spec limits."""
    if source_tables_list and idx < len(source_tables_list):
        return source_tables_list[idx].lower() == "measpartvals"
    if data_types_list and idx < len(data_types_list):
        if data_types_list[idx].lower() in ("double", "float", "real"):
            return any(lst and idx < len(lst) and lst[idx] != "" for lst in limit_lists)
    return False


def _cell_float(row: list[str], idx: int) -> float | None:
    """Parse ``row[idx]`` as a float, or None when empty / missing / non-numeric."""
    if not row or idx >= len(row):
        return None
    token = row[idx].strip()
    if not token or token == "*":
        return None
    try:
        return float(token)
    except ValueError:
        return None


def _safe_int(text: str) -> int:
    try:
        return int(text.strip())
    except (ValueError, AttributeError):
        return 0


def _estimate_rows(path: str) -> int:
    """Estimate row count from file size when the header lacks Rows=."""
    try:
        size = os.path.getsize(path)
        with open(path, "r", encoding="utf-8", errors="ignore") as fh:
            sample = fh.read(65536)
        lines = sample.count("\n") or 1
        avg = max(len(sample.encode("utf-8")) / lines, 1)
        return max(int(size / avg), 1)
    except OSError:
        return 1


class _BufferedWriter:
    """Minimal append-buffered text writer; keeps one file handle open."""

    def __init__(self, path: str) -> None:
        # Truncate any stale file from a previous run, then keep appending.
        self._fh = open(path, "w", encoding="utf-8", newline="")
        self._buf: list[str] = []
        self._buf_chars = 0
        self.lines_written = 0

    def write(self, line: str) -> None:
        self._buf.append(line)
        self._buf_chars += len(line)
        self.lines_written += 1
        if self._buf_chars >= _WRITE_BUFFER_CHARS:
            self._flush()

    def _flush(self) -> None:
        if self._buf:
            self._fh.write("".join(self._buf))
            self._buf.clear()
            self._buf_chars = 0

    def close(self) -> None:
        try:
            self._flush()
        finally:
            self._fh.close()
