# -*- mode: python ; coding: utf-8 -*-
"""
WaferMapTool_folder.spec
========================
Folder-mode build: small WaferMapTool.exe + _libs\ folder.
Fast startup (no extraction), easy to update individual files.

Build command:
    py -m PyInstaller WaferMapTool_folder.spec --noconfirm

Output: dist\WaferMapTool_folder\WaferMapTool.exe   (+ _libs\ next to it)
"""
from PyInstaller.utils.hooks import collect_data_files

hidden = [
    "PyQt6.QtCore", "PyQt6.QtGui", "PyQt6.QtWidgets",
    "PyQt6.QtPrintSupport", "PyQt6.sip",
    "matplotlib.backends.backend_qtagg",
    "matplotlib.backends.backend_pdf",
    "matplotlib.backends.backend_agg",
    "matplotlib.figure", "matplotlib.pyplot",
    "scipy.interpolate", "scipy.spatial",
    "scipy.spatial._ckdtree", "scipy.spatial._qhull",
    "pandas",
    "reportlab", "reportlab.platypus", "reportlab.lib",
    "pptx", "pptx.util",
    "pypdf",
]

a = Analysis(
    ["main.py"],
    pathex=[],
    binaries=[],
    datas=collect_data_files("matplotlib") + collect_data_files("scipy"),
    hiddenimports=hidden,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tkinter", "wx", "IPython", "jupyter", "notebook", "pytest", "sphinx"],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,      # keep DLLs in separate folder → small exe
    name="WaferMapTool",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="WaferMapTool_folder",   # → dist\WaferMapTool_folder\
)
