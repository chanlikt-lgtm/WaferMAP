# -*- mode: python ; coding: utf-8 -*-
"""
WaferMapTool_folder.spec  —  FOLDER build (small exe + lib folder)
===================================================================
Build:   py -m PyInstaller WaferMapTool_folder.spec --noconfirm
Output:  dist\WaferMapTool_folder\WaferMapTool.exe  (+ _internal\ next to it)
"""
from PyInstaller.utils.hooks import collect_data_files, collect_all

mpl_data = collect_data_files("matplotlib")

# numpy: collect_all ensures C-extension DLLs are bundled.
numpy_datas, numpy_binaries, numpy_hidden = collect_all("numpy")

hidden = [
    "PyQt6.QtCore",
    "PyQt6.QtGui",
    "PyQt6.QtWidgets",
    "PyQt6.sip",
    "matplotlib.backends.backend_qtagg",
    "matplotlib.backends.backend_pdf",
    "matplotlib.backends.backend_agg",
    "matplotlib.figure",
    "matplotlib.pyplot",
    "matplotlib.tri",          # replaces scipy.griddata
    "pandas",
    "pandas._libs.tslibs.np_datetime",
    "pandas._libs.tslibs.nattype",
    "pandas._libs.tslibs.timedeltas",
    "pptx",
    "pptx.util",
    "pptx.enum.text",
    "pypdf",
]

a = Analysis(
    ["main.py"],
    pathex=[],
    binaries=numpy_binaries,
    datas=mpl_data + numpy_datas,
    hiddenimports=hidden + numpy_hidden,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "tkinter", "wx", "_tkinter",
        "scipy", "scipy.interpolate", "scipy.spatial",
        "scipy.stats", "scipy.signal", "scipy.optimize",
        "scipy.fft", "scipy.linalg", "scipy.io",
        "scipy.ndimage", "scipy.odr", "scipy.sparse",
        "scipy.cluster",
        "pandas.io.formats.style",
        "pandas.io.clipboard",
        "pandas.tests",
        "sqlalchemy", "psycopg2", "MySQLdb", "pymysql",
        "pysqlite2", "sqlite3",
        "PyQt6.QtPrintSupport",
        "PyQt6.QtSvg",
        "PyQt6.QtNetwork",
        "PyQt6.QtBluetooth",
        "PyQt6.QtMultimedia",
        "PyQt6.QtOpenGL",
        "PyQt6.QtSql",
        "PyQt6.QtWebEngine",
        "matplotlib.backends.backend_svg",
        "matplotlib.backends.backend_wxagg",
        "matplotlib.backends.backend_tkagg",
        "matplotlib.backends.backend_gtk3agg",
        "matplotlib.backends.backend_ps",
        "reportlab",
        "IPython", "jupyter", "notebook",
        "pytest", "sphinx", "setuptools",
        "distutils", "unittest",
        "PIL.ImageQt",
    ],
    noarchive=False,
    optimize=1,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,   # folder mode — DLLs stay separate
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
    # icon="wafer_tool.ico",
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="WaferMapTool_folder",
)
