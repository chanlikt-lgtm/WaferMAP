"""The .wtjob format: a saved wafer-report run (input + output + all settings).

A job captures exactly what the GUI's Generate Report needs: the input data
file, the output directory, and every PlotConfig field. It round-trips through
JSON so it can be re-run or scheduled offline.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, asdict, field
from datetime import datetime
from pathlib import Path

JOB_SUFFIX = ".wtjob"
JOB_FORMAT = "wafer-tool-job"
JOB_VERSION = 1

# .eff extensions this job type recognises as "raw EFF, not a converted txt".
_EFF_EXTS = (".eff",)

_PLOT_KEYS = ("t_low", "t_high", "use_log", "high_is_green",
              "mirror_x", "mirror_y", "rot_deg")


@dataclass
class WaferJob:
    """One saved wafer-report run.

    Input is either a fixed ``input_file`` or, when ``input_dir`` is set, the
    newest file in that folder matching ``input_pattern`` (resolved at run time,
    so each scheduled run picks up the latest drop).
    """
    input_file: str
    out_dir: str
    t_low: float
    t_high: float
    use_log: bool = False
    high_is_green: bool = False
    mirror_x: bool = False
    mirror_y: bool = False
    rot_deg: int = 0
    input_dir: str = ""              # when set, use newest match in this folder
    input_pattern: str = "*.txt"     # ';'-separated globs, e.g. "*.txt;*.csv"
    # Raw-EFF jobs: the measurement parameter names to map (each -> its own
    # output folder). Empty list means "every parameter in the file", the
    # automation-friendly default. Ignored for txt/csv jobs.
    eff_params: list[str] = field(default_factory=list)
    # Optional per-parameter value filter for raw-EFF jobs: parameter name ->
    # [min, max]. Dies outside the range are excluded. Name-keyed so it survives
    # re-scanning the newest file in folder mode. Empty means no filter.
    eff_filters: dict[str, list[float]] = field(default_factory=dict)

    def plot_config_kwargs(self) -> dict:
        """The subset of fields that construct a PlotConfig."""
        return {k: getattr(self, k) for k in _PLOT_KEYS}

    def is_eff_input(self, resolved_path: str | None = None) -> bool:
        """True when this job's (resolved) input is a raw .eff extraction."""
        path = resolved_path if resolved_path is not None else self.input_file
        return bool(path) and path.lower().endswith(_EFF_EXTS)

    def resolve_input_file(self) -> str:
        """The data file this job should process right now.

        Fixed-file jobs return ``input_file``. Folder jobs return the
        most-recently-modified file in ``input_dir`` matching any pattern in
        ``input_pattern``; raises FileNotFoundError if the folder has no match.
        """
        if not self.input_dir:
            return self.input_file
        folder = Path(self.input_dir)
        patterns = [p.strip() for p in self.input_pattern.split(";") if p.strip()] or ["*"]
        candidates = [f for pat in patterns for f in folder.glob(pat) if f.is_file()]
        if not candidates:
            raise FileNotFoundError(
                f"no file matching {self.input_pattern!r} in {self.input_dir}")
        return str(max(candidates, key=lambda f: f.stat().st_mtime))

    def to_dict(self) -> dict:
        d = {"format": JOB_FORMAT, "version": JOB_VERSION,
             "created": datetime.now().isoformat(timespec="seconds")}
        d.update(asdict(self))
        return d


def save_job(path: str | Path, job: WaferJob) -> Path:
    """Write a .wtjob (suffix forced). Returns the written path."""
    out = Path(path)
    if out.suffix.lower() not in (JOB_SUFFIX, ".json"):
        out = out.with_suffix(JOB_SUFFIX)
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", encoding="utf-8") as handle:
        json.dump(job.to_dict(), handle, indent=2)
    return out


def load_job(path: str | Path) -> WaferJob:
    """Read a .wtjob back into a WaferJob (ignores metadata keys)."""
    with open(path, "r", encoding="utf-8") as handle:
        data = json.load(handle)
    if data.get("format") != JOB_FORMAT:
        raise ValueError(f"not a {JOB_FORMAT} file: {path}")
    fields = ("input_file", "out_dir", *_PLOT_KEYS, "input_dir", "input_pattern",
              "eff_params", "eff_filters")
    missing = [f for f in ("out_dir", "t_low", "t_high") if f not in data]
    if missing:
        raise ValueError(f"job is missing required fields: {', '.join(missing)}")
    if not (data.get("input_file") or data.get("input_dir")):
        raise ValueError("job must set either input_file or input_dir")
    kwargs = {k: data[k] for k in fields if k in data}
    kwargs.setdefault("input_file", "")   # folder-mode jobs may omit it
    return WaferJob(**kwargs)
