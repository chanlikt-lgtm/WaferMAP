"""Schedule wafer-tool jobs via Windows Task Scheduler.

Same design as the eff-converter / ADAML scheduler. Each job becomes a task
named ``WaferTool_Job_<name>`` that runs a saved .wtjob headless (via run_job.py,
or the packaged exe when frozen) on a daily / weekly / monthly trigger. Daily and
weekly use PowerShell's ScheduledTasks cmdlets; monthly uses Task Scheduler XML
(schtasks /TR truncates long paths and PowerShell has no monthly trigger cmdlet).
Runs as the current user when logged on -- no stored password, no network.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from xml.sax.saxutils import escape as _xml_escape

TASK_PREFIX = "WaferTool_Job_"
# scheduler.py -> automation -> wafer_tool -> app root (holds run_job.py, main.py)
REPO_ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_PYTHON = sys.executable

DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday",
        "Friday", "Saturday", "Sunday"]


@dataclass
class ScheduledJob:
    task_name: str
    job_path: str
    state: str
    next_run: str
    last_run: str
    last_result: int


def task_name_for(job_name: str) -> str:
    safe = "".join(ch if (ch.isalnum() or ch in "_-") else "_" for ch in job_name) or "job"
    return TASK_PREFIX + safe


def runner_command(job_path: str | Path, *, python_exe: str = DEFAULT_PYTHON,
                   repo_root: str | Path = REPO_ROOT) -> list[str]:
    """Command parts that run one job headless (dev script or frozen exe).

    - frozen: ``[App.exe, --run-job, <job>]``.
    - dev: ``[python.exe, <root>/run_job.py, <job>]`` -- run_job.py fixes sys.path
      itself, so the task needs no working directory.
    """
    job = str(Path(job_path))
    if getattr(sys, "frozen", False):
        return [sys.executable, "--run-job", job]
    return [str(python_exe), str(Path(repo_root) / "run_job.py"), job]


def _quote_args(parts: list[str]) -> str:
    return " ".join(p if p.startswith("--") else f'"{p}"' for p in parts)


def _ps(script: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
        capture_output=True, text=True,
    )


def _register_ps(tn: str, job_name: str, parts: list[str], trigger_ps: str) -> tuple[bool, str]:
    script = (
        f"$a = New-ScheduledTaskAction -Execute '{parts[0]}' "
        f"-Argument '{_quote_args(parts[1:])}';"
        f"$t = {trigger_ps};"
        f"$s = New-ScheduledTaskSettingsSet -StartWhenAvailable "
        f"-ExecutionTimeLimit (New-TimeSpan -Hours 4);"
        f"Register-ScheduledTask -TaskName '{tn}' -Action $a -Trigger $t "
        f"-Settings $s -Description 'wafer-tool job {job_name}' -Force | Out-Null"
    )
    r = _ps(script)
    return (r.returncode == 0, tn if r.returncode == 0 else (r.stderr.strip() or "register failed"))


def schedule_daily(job_path, job_name, hour, minute, *,
                   python_exe=DEFAULT_PYTHON, repo_root=REPO_ROOT) -> tuple[bool, str]:
    tn = task_name_for(job_name)
    at = f"{int(hour):02d}:{int(minute):02d}"
    parts = runner_command(job_path, python_exe=python_exe, repo_root=repo_root)
    return _register_ps(tn, job_name, parts, f"New-ScheduledTaskTrigger -Daily -At {at}")


def schedule_weekly(job_path, job_name, day_of_week, hour, minute, *,
                    python_exe=DEFAULT_PYTHON, repo_root=REPO_ROOT) -> tuple[bool, str]:
    if day_of_week not in DAYS:
        return False, f"invalid day: {day_of_week}"
    tn = task_name_for(job_name)
    at = f"{int(hour):02d}:{int(minute):02d}"
    parts = runner_command(job_path, python_exe=python_exe, repo_root=repo_root)
    return _register_ps(tn, job_name, parts,
                        f"New-ScheduledTaskTrigger -Weekly -DaysOfWeek {day_of_week} -At {at}")


_MONTHS = ("January February March April May June July August September "
           "October November December").split()

_TASK_XML = """<?xml version="1.0"?>
<Task version="1.2" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
  <RegistrationInfo><Description>wafer-tool job {name}</Description></RegistrationInfo>
  <Triggers>
    <CalendarTrigger>
      <StartBoundary>{start}</StartBoundary>
      <Enabled>true</Enabled>
      <ScheduleByMonth>
        <DaysOfMonth><Day>{day}</Day></DaysOfMonth>
        <Months>{months}</Months>
      </ScheduleByMonth>
    </CalendarTrigger>
  </Triggers>
  <Principals>
    <Principal id="Author"><LogonType>InteractiveToken</LogonType><RunLevel>LeastPrivilege</RunLevel></Principal>
  </Principals>
  <Settings>
    <StartWhenAvailable>true</StartWhenAvailable>
    <ExecutionTimeLimit>PT4H</ExecutionTimeLimit>
    <Enabled>true</Enabled>
    <MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy>
  </Settings>
  <Actions Context="Author">
    <Exec><Command>{exe}</Command><Arguments>{args}</Arguments></Exec>
  </Actions>
</Task>"""


def _register_xml(tn: str, xml: str) -> tuple[bool, str]:
    fd, path = tempfile.mkstemp(suffix=".xml")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(xml)
        r = _ps(
            f"Register-ScheduledTask -Xml (Get-Content -Raw -Encoding UTF8 '{path}') "
            f"-TaskName '{tn}' -Force | Out-Null"
        )
    finally:
        os.unlink(path)
    return (r.returncode == 0, tn if r.returncode == 0 else (r.stderr.strip() or "register failed"))


def schedule_monthly(job_path, job_name, day_of_month, hour, minute, *,
                     python_exe=DEFAULT_PYTHON, repo_root=REPO_ROOT) -> tuple[bool, str]:
    day = int(day_of_month)
    if not (1 <= day <= 31):
        return False, "day of month must be 1-31"
    tn = task_name_for(job_name)
    parts = runner_command(job_path, python_exe=python_exe, repo_root=repo_root)
    start = f"{datetime.now():%Y-%m-%d}T{int(hour):02d}:{int(minute):02d}:00"
    xml = _TASK_XML.format(
        name=_xml_escape(job_name), start=start, day=day,
        months="".join(f"<{m}/>" for m in _MONTHS),
        exe=_xml_escape(parts[0]), args=_xml_escape(_quote_args(parts[1:])),
    )
    return _register_xml(tn, xml)


def _extract_job_path(args: str) -> str:
    m = re.search(r'"([^"]*\.wtjob)"', args)
    if m:
        return m.group(1)
    return args.split('"')[1] if '"' in args else ""


def list_jobs() -> list[ScheduledJob]:
    script = (
        f"$out = Get-ScheduledTask -TaskName '{TASK_PREFIX}*' -ErrorAction SilentlyContinue "
        f"| ForEach-Object {{ $i = $_ | Get-ScheduledTaskInfo; "
        f"$arg = ($_.Actions | Select-Object -First 1).Arguments; "
        f"[pscustomobject]@{{ name=$_.TaskName; state=$_.State.ToString(); "
        f"next= if($i.NextRunTime){{$i.NextRunTime.ToString('yyyy-MM-dd HH:mm')}}else{{''}}; "
        f"last= if($i.LastRunTime){{$i.LastRunTime.ToString('yyyy-MM-dd HH:mm')}}else{{''}}; "
        f"result=$i.LastTaskResult; args=$arg }} }}; "
        f"if($out){{ ConvertTo-Json -InputObject @($out) -Depth 3 }}"
    )
    r = _ps(script)
    if r.returncode != 0 or not r.stdout.strip():
        return []
    try:
        data = json.loads(r.stdout)
    except json.JSONDecodeError:
        return []
    if isinstance(data, dict):
        data = [data]
    jobs: list[ScheduledJob] = []
    for d in data:
        args = str(d.get("args", ""))
        jobs.append(ScheduledJob(
            task_name=str(d.get("name", "")),
            job_path=_extract_job_path(args),
            state=str(d.get("state", "")),
            next_run=str(d.get("next", "")),
            last_run=str(d.get("last", "")),
            last_result=int(d.get("result", 0) or 0),
        ))
    return jobs


def remove_job(task_name: str) -> bool:
    r = _ps(f"Unregister-ScheduledTask -TaskName '{task_name}' -Confirm:$false")
    return r.returncode == 0


def run_now(task_name: str) -> bool:
    r = _ps(f"Start-ScheduledTask -TaskName '{task_name}'")
    return r.returncode == 0
