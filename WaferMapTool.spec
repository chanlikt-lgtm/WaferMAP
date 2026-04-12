# -*- mode: python ; coding: utf-8 -*-
"""
WaferMapTool.spec  —  STANDALONE single-file build
===================================================
Build:   py -m PyInstaller WaferMapTool.spec --noconfirm
Output:  dist\WaferMapTool.exe   (one file, no folder needed)
"""
from PyInstaller.utils.hooks import collect_data_files, collect_all

# Only the matplotlib fonts/styles are essential at runtime.
# Exclude scipy data (test fixtures etc.) — not needed.
mpl_data = collect_data_files("matplotlib")

# numpy: collect_all ensures C-extension DLLs (e.g. _multiarray_umath.pyd) are bundled.
# Without this, PyInstaller misses them and numpy fails to import at runtime.
numpy_datas, numpy_binaries, numpy_hidden = collect_all("numpy")

hidden = [
    # PyQt6 — only what the app actually touches
    "PyQt6.QtCore",
    "PyQt6.QtGui",
    "PyQt6.QtWidgets",
    "PyQt6.sip",

    # Matplotlib — only the two backends actually used
    "matplotlib.backends.backend_qtagg",   # Qt canvas for live plots
    "matplotlib.backends.backend_pdf",     # PdfPages for PDF export
    "matplotlib.backends.backend_agg",     # non-interactive renderer
    "matplotlib.figure",
    "matplotlib.pyplot",

    # matplotlib.tri — replaces scipy.griddata (same Qhull C lib, already bundled)
    "matplotlib.tri",

    # pandas — core only (CSV read + groupby + category dtype)
    "pandas",
    "pandas._libs.tslibs.np_datetime",
    "pandas._libs.tslibs.nattype",
    "pandas._libs.tslibs.timedeltas",

    # python-pptx
    "pptx",
    "pptx.util",
    "pptx.enum.text",

    # pypdf (PDF bookmark injection)
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
        # GUI toolkits not used
        "tkinter", "wx", "_tkinter",

        # scipy submodules not used by this app
        # scipy fully removed — replaced by matplotlib.tri in geometry.py
        "scipy",
        "scipy.interpolate", "scipy.spatial", "scipy.stats",
        "scipy.signal", "scipy.optimize", "scipy.fft",
        "scipy.linalg", "scipy.io", "scipy.ndimage",
        "scipy.odr", "scipy.sparse", "scipy.cluster",

        # pandas extras not used
        "pandas.io.formats.style",
        "pandas.io.clipboard",
        "pandas.tests",

        # database drivers pulled in by pandas — not used
        "sqlalchemy", "psycopg2", "MySQLdb", "pymysql",
        "pysqlite2", "sqlite3",

        # Qt modules not used
        "PyQt6.QtPrintSupport",
        "PyQt6.QtSvg",
        "PyQt6.QtNetwork",
        "PyQt6.QtBluetooth",
        "PyQt6.QtMultimedia",
        "PyQt6.QtOpenGL",
        "PyQt6.QtSql",
        "PyQt6.QtWebEngine",

        # Matplotlib backends not used
        "matplotlib.backends.backend_svg",
        "matplotlib.backends.backend_wxagg",
        "matplotlib.backends.backend_tkagg",
        "matplotlib.backends.backend_gtk3agg",
        "matplotlib.backends.backend_ps",

        # ReportLab — only used by generate_docs.py, not the app
        "reportlab",

        # Dev / test tools
        "IPython", "jupyter", "notebook",
        "pytest", "sphinx", "setuptools",
        "distutils", "unittest",

        # Image libs not needed
        "PIL.ImageQt",
    ],
    noarchive=False,
    optimize=1,              # strip docstrings → smaller bytecode
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    exclude_binaries=False,  # onefile — everything embedded
    name="WaferMapTool",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,           # no CMD window
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    # icon="wafer_tool.ico",
)
