"""
wafer_tool
==========
Modular wafer plotting and reporting toolkit.

Quick-start (programmatic use without GUI)
------------------------------------------
    from wafer_tool import PlotConfig, generate_report

    config = PlotConfig(t_low=1e-5, t_high=1e-4, use_log=True)
    pdf, csv, pptx = generate_report("data.csv", config, out_dir="/tmp/out")

Quick-start (launch GUI)
------------------------
    python main.py
"""
from .config      import PlotConfig, ColorScheme
from .data_loader import read_wafer_data
from .report      import generate_report

__version__ = "2.0.0"
__all__ = [
    "PlotConfig",
    "ColorScheme",
    "read_wafer_data",
    "generate_report",
]
