"""Tests for the wafer-tool automation (job + scheduler). Pure logic only;
Windows task registration is verified live.

Run:  python -m pytest wafer_tool/automation/test_automation.py
"""
from __future__ import annotations

import json

import pytest

from . import scheduler
from .job import WaferJob, save_job, load_job, JOB_SUFFIX


# ── job round-trip ───────────────────────────────────────────────────────────

def test_job_round_trips(tmp_path):
    j = WaferJob(input_file=r"E:\d\a.txt", out_dir=r"E:\out",
                 t_low=-110, t_high=-80, use_log=True, high_is_green=True,
                 mirror_x=True, rot_deg=270)
    p = save_job(tmp_path / "job1", j)
    assert p.suffix == JOB_SUFFIX
    k = load_job(p)
    assert k == j
    assert k.plot_config_kwargs() == {
        "t_low": -110, "t_high": -80, "use_log": True, "high_is_green": True,
        "mirror_x": True, "mirror_y": False, "rot_deg": 270}


def test_job_forces_suffix_and_writes_metadata(tmp_path):
    p = save_job(tmp_path / "noext", WaferJob("a.txt", "o", -1, 1))
    assert p.name == "noext" + JOB_SUFFIX
    d = json.loads(p.read_text())
    assert d["format"] == "wafer-tool-job" and d["input_file"] == "a.txt"


def test_load_rejects_foreign_json(tmp_path):
    bad = tmp_path / "bad.wtjob"
    bad.write_text('{"format": "something-else"}', encoding="utf-8")
    with pytest.raises(ValueError):
        load_job(bad)


def test_load_rejects_missing_required_fields(tmp_path):
    bad = tmp_path / "part.wtjob"
    bad.write_text('{"format": "wafer-tool-job", "input_file": "a.txt"}', encoding="utf-8")
    with pytest.raises(ValueError):
        load_job(bad)


def test_fixed_file_resolves_to_itself():
    j = WaferJob("E:/d/a.txt", "o", -1, 1)
    assert j.resolve_input_file() == "E:/d/a.txt"


def test_folder_mode_picks_newest_matching_file(tmp_path):
    import os, time
    (tmp_path / "old.txt").write_text("1"); time.sleep(0.01)
    (tmp_path / "new.txt").write_text("2")
    (tmp_path / "ignore.csv").write_text("x")
    # make new.txt clearly the most recent
    os.utime(tmp_path / "new.txt", (time.time() + 5, time.time() + 5))
    j = WaferJob("", "o", -1, 1, input_dir=str(tmp_path), input_pattern="*.txt")
    assert j.resolve_input_file() == str(tmp_path / "new.txt")


def test_folder_mode_multiple_patterns(tmp_path):
    import os, time
    (tmp_path / "a.txt").write_text("1")
    (tmp_path / "b.csv").write_text("2")
    os.utime(tmp_path / "b.csv", (time.time() + 5, time.time() + 5))
    j = WaferJob("", "o", -1, 1, input_dir=str(tmp_path), input_pattern="*.txt;*.csv")
    assert j.resolve_input_file().endswith("b.csv")


def test_folder_mode_raises_when_empty(tmp_path):
    j = WaferJob("", "o", -1, 1, input_dir=str(tmp_path), input_pattern="*.txt")
    with pytest.raises(FileNotFoundError):
        j.resolve_input_file()


def test_folder_mode_round_trips_and_loads_without_input_file(tmp_path):
    j = WaferJob("", "o", -110, -80, input_dir=r"E:\drop", input_pattern="*.txt;*.csv")
    p = save_job(tmp_path / "folderjob", j)
    k = load_job(p)
    assert k.input_dir == r"E:\drop" and k.input_pattern == "*.txt;*.csv"
    assert k.input_file == ""


def test_plot_config_kwargs_build_a_real_plotconfig(tmp_path):
    from wafer_tool import PlotConfig
    j = WaferJob("a.txt", "o", t_low=-80, t_high=-110, rot_deg=90)  # reversed limits
    cfg = PlotConfig(**j.plot_config_kwargs())
    assert cfg.t_low == -110 and cfg.t_high == -80   # PlotConfig normalises order
    assert cfg.rot_deg == 90


# ── scheduler (pure parts) ───────────────────────────────────────────────────

def test_task_name_sanitises_and_prefixes():
    assert scheduler.task_name_for("wafer_demo") == "WaferTool_Job_wafer_demo"
    assert scheduler.task_name_for("my job/2") == "WaferTool_Job_my_job_2"


def test_days_complete():
    assert len(scheduler.DAYS) == 7 and scheduler.DAYS[-1] == "Sunday"


def test_schedule_weekly_rejects_bad_day():
    ok, msg = scheduler.schedule_weekly("x.wtjob", "j", "Someday", 10, 0)
    assert ok is False and "invalid day" in msg


def test_schedule_monthly_rejects_bad_day_of_month():
    for bad in (0, 32, -1):
        ok, msg = scheduler.schedule_monthly("x.wtjob", "j", bad, 10, 0)
        assert ok is False and "1-31" in msg


def test_runner_command_dev_uses_run_job_launcher(monkeypatch):
    monkeypatch.setattr(scheduler.sys, "frozen", False, raising=False)
    parts = scheduler.runner_command("job.wtjob", python_exe="py.exe", repo_root="R")
    assert parts[0] == "py.exe"
    assert any(p.endswith("run_job.py") for p in parts)
    assert parts[-1].endswith("job.wtjob")


def test_runner_command_frozen_uses_exe(monkeypatch):
    monkeypatch.setattr(scheduler.sys, "frozen", True, raising=False)
    monkeypatch.setattr(scheduler.sys, "executable", r"C:\App\Wafer.exe", raising=False)
    parts = scheduler.runner_command("job.wtjob")
    assert parts == [r"C:\App\Wafer.exe", "--run-job", parts[-1]]
    assert parts[-1].endswith("job.wtjob")


def test_extract_job_path_finds_wtjob():
    assert scheduler._extract_job_path(
        r'"E:\app\run_job.py" "E:\d\j1.wtjob"') == r"E:\d\j1.wtjob"
    assert scheduler._extract_job_path('--run-job "E:/d/j2.wtjob"') == "E:/d/j2.wtjob"
    assert scheduler._extract_job_path("") == ""


def test_monthly_xml_is_wellformed_and_complete():
    import xml.dom.minidom as minidom
    long_args = '"E:\\app\\run_job.py" "E:\\a really\\long\\path\\job.wtjob"'
    xml = scheduler._TASK_XML.format(
        name="j", start="2026-08-01T09:15:00", day=12,
        months="".join(f"<{m}/>" for m in scheduler._MONTHS),
        exe="python.exe", args=scheduler._xml_escape(long_args))
    minidom.parseString(xml)
    assert "<Day>12</Day>" in xml and xml.count("/>") >= 12
    assert "job.wtjob" in xml
