# -*- mode: python ; coding: utf-8 -*-
"""
WaferMapTool.spec
=================
PyInstaller spec for Wafer Map Tool.

Build command (run from repo root):
    py -m PyInstaller WaferMapTool.spec --noconfirm

Output: dist\WaferMapTool\WaferMapTool.exe   (folder distribution)
"""
import sys
from PyInstaller.utils.hooks import collect_submodules, collect_data_files

# ── Hidden imports ─────────────────────────────────────────────────────────
hidden = [
    # PyQt6 core
    "PyQt6.QtCore",
    "PyQt6.QtGui",
    "PyQt6.QtWidgets",
    "PyQt6.QtPrintSupport",
    "PyQt6.sip",

    # Matplotlib backends needed at runtime
    "matplotlib.backends.backend_qtagg",
    "matplotlib.backends.backend_pdf",
    "matplotlib.backends.backend_agg",
    "matplotlib.backends.backend_svg",
    "matplotlib.figure",
    "matplotlib.pyplot",

    # scipy — griddata / Delaunay
    "scipy.interpolate",
    "scipy.interpolate._rbfinterp_pythran",
    "scipy.spatial",
    "scipy.spatial._ckdtree",
    "scipy.spatial.transform",
    "scipy.spatial._qhull",

    # pandas
    "pandas",
    "pandas._libs.tslibs.np_datetime",
    "pandas._libs.tslibs.nattype",
    "pandas._libs.tslibs.timedeltas",

    # reportlab (docs generator, included so it works if user runs generate_docs)
    "reportlab",
    "reportlab.platypus",
    "reportlab.lib",
    "reportlab.lib.styles",
    "reportlab.lib.units",
    "reportlab.lib.colors",
    "reportlab.lib.pagesizes",

    # python-pptx (optional but bundle it)
    "pptx",
    "pptx.util",
    "pptx.enum.text",

    # pypdf (for PDF bookmarks)
    "pypdf",

    # encoding / locale support
    "encodings.utf_8",
    "encodings.cp1252",
]

# Collect all matplotlib data (fonts, style sheets, etc.)
mpl_data = collect_data_files("matplotlib")

# Collect scipy data
scipy_data = collect_data_files("scipy")

# ── Analysis ───────────────────────────────────────────────────────────────
a = Analysis(
    ["main.py"],
    pathex=[],
    binaries=[],
    datas=mpl_data + scipy_data,
    hiddenimports=hidden,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "tkinter",       # not used
        "wx",            # not used
        "IPython",
        "jupyter",
        "notebook",
        "pytest",
        "sphinx",
        "generate_docs", # doc generator — not needed at runtime
    ],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="WaferMapTool",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,          # no black console window — GUI app
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    # icon="wafer_tool.ico",  # uncomment and supply a .ico to add a taskbar icon
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="WaferMapTool",    # → dist\WaferMapTool\
)
