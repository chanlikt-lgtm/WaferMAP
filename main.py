"""
main.py
=======
Application entry point — launch the PyQt6 GUI.

Usage
-----
    python main.py

Headless / programmatic use (no GUI required)
---------------------------------------------
    from wafer_tool import PlotConfig, generate_report

    config = PlotConfig(t_low=1e-5, t_high=1e-4, use_log=True, high_is_green=True)
    pdf, csv, pptx = generate_report("measurements.csv", config, out_dir="output/")
    print(f"PDF  → {pdf}")
    print(f"CSV  → {csv}")
    print(f"PPTX → {pptx}")
"""
import sys
import matplotlib
matplotlib.use("Agg")   # Non-interactive backend; Qt widgets use their own renderer

from PyQt6.QtWidgets import QApplication
from wafer_tool.ui.main_window import DataProcessorUI


def main() -> None:
    app = QApplication(sys.argv)
    window = DataProcessorUI()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
