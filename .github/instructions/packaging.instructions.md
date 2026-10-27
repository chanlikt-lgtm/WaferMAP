---
applyTo: "*.spec,main.py"
description: "Use when editing PyInstaller spec files or the app entry point / build packaging."
---

# Packaging Instructions

Two PyInstaller specs build the same app: `WaferMapTool.spec` (one-file exe) and
`WaferMapTool_folder.spec` (small exe + `_internal/` folder, faster startup).
Build with `py -m PyInstaller <spec> --noconfirm`; output lands in `dist/`.

## Do NOT exclude these — they crash the exe

The specs aggressively `excludes=[...]` to shrink the build. Two are required at
runtime and were the cause of startup/render crashes; keep them **out** of
`excludes` and bundled:

- **`scipy`** — `wafer_tool/geometry.py` imports `scipy.interpolate.griddata`
  (linear + nearest). The "replaced by matplotlib.tri" claim exists only in
  `generate_docs.py`/docs and was never applied to the code. Both specs collect
  it via `collect_all("scipy")` (bundles the Qhull/OpenBLAS DLLs).
- **`unittest`** — `pyparsing` (pulled in by matplotlib) imports it at import
  time, so excluding it raises `ModuleNotFoundError: No module named 'unittest'`
  before the window even appears.

When adding a new runtime dependency, add it to `hiddenimports` (and
`collect_all` if it ships C-extension DLLs, like numpy/scipy). `pywin32`
(Outlook email backend) needs `win32com`, `win32com.client`, `pythoncom`,
`pywintypes`, `win32timezone` as hidden imports.

## Entry point is dual-purpose

`main.py` must keep routing headless invocations to the runner: when `sys.argv`
contains `--run-job` / `--test-email`, or the first arg ends in `.wtjob`/`.json`,
it calls `wafer_tool.automation.runner.main(argv)` and exits instead of opening
the GUI. The scheduler launches the frozen build as
`WaferMapTool.exe --run-job <job>`, so removing this breaks scheduled tasks.

## Verifying a build (don't trust "it launched")

- The one-file bootloader stays alive while unpacking (~seconds); a short "is it
  still running" check can pass even when Python then crashes. Verify the actual
  Python startup.
- Best full check runs the whole pipeline through the exe headlessly:
  `WaferMapTool.exe --run-job <job.wtjob>` and confirm exit 0 + PDF/PPTX/CSV in
  the output folder.
- To find a wrongly-excluded module without repeated slow rebuilds: install a
  `sys.meta_path` finder that raises `ModuleNotFoundError` for each excluded
  name, then run `generate_report` from source (set `PYTHONUTF8=1` so the
  pipeline's check/cross glyphs don't crash a cp1252 console).
- Kill any running instance before rebuilding (`Get-Process WaferMapTool |
  Stop-Process`), or PyInstaller fails to overwrite `dist\WaferMapTool.exe` with
  `PermissionError: [WinError 5]`.
