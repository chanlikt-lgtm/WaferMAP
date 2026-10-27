"""
waferplot_ORIN
==============
OriginLab export and side-by-side verification tools for wafer maps.

Generates OriginLab contour plots that replicate the 3-zone color scheme
produced by the Python/Matplotlib pipeline, then creates side-by-side
comparison images to verify color and format match.

Requirements
------------
- OriginLab Origin 2021 (or later) must be installed on this machine.
- Python package: originpro  (pip install originpro)
- All wafer_tool dependencies (numpy, scipy, pandas, matplotlib)

Quick start
-----------
    python -m waferplot_ORIN.run_verification \\
        --file "VT_FP.M1 805.txt" --t_low 1e-5 --t_high 1e-4
"""
from .origin_wafer_exporter import export_wafer_as_origin_png
from .verify_side_by_side import verify_wafer, verify_lot

__all__ = ["export_wafer_as_origin_png", "verify_wafer", "verify_lot"]
