# WaferMap AutoPlotting Tool

A modular, scalable Python toolkit for semiconductor wafer measurement
visualisation and reporting.

---

## Project Structure

```
wafer_tool/
├── main.py                         ← GUI entry point
├── requirements.txt
└── wafer_tool/
    ├── __init__.py                 ← Public API surface
    ├── config.py                   ← PlotConfig dataclass, ColorScheme, constants
    ├── exceptions.py               ← Custom exception hierarchy
    ├── data_loader.py              ← File reading & validation
    ├── geometry.py                 ← Pure math: transforms, interpolation grid
    ├── plotting.py                 ← draw_wafer_ax() — Matplotlib rendering
    ├── statistics.py               ← 8-condition classification + bar chart
    ├── report.py                   ← Pipeline orchestrator
    ├── exporters/
    │   ├── __init__.py
    │   ├── pdf_exporter.py         ← Multi-page PDF with bookmarks
    │   ├── csv_exporter.py         ← Colour-zone summary CSV
    │   └── pptx_exporter.py        ← PowerPoint deck
    └── ui/
        ├── __init__.py
        ├── main_window.py          ← DataProcessorUI (root QWidget)
        ├── orientation_widget.py   ← Mirror/rotation controls + preview
        └── threshold_viz_widget.py ← Real-time threshold scatter chart
```

---

## Installation

```bash
pip install -r requirements.txt
```

> **python-pptx is optional.** If it is not installed, the PPTX output is
> skipped gracefully; PDF and CSV are always produced.

---

## Usage

### GUI

```bash
python main.py
```

### Programmatic (headless, no GUI)

```python
from wafer_tool import PlotConfig, generate_report

config = PlotConfig(
    t_low=1e-5,
    t_high=1e-4,
    use_log=True,
    high_is_green=True,
    mirror_x=False,
    mirror_y=False,
    rot_deg=0,          # 0 | 90 | 180 | 270
)

pdf_path, csv_path, pptx_path = generate_report(
    filepath="measurements.csv",
    config=config,
    out_dir="output/",
)
print(f"PDF  → {pdf_path}")
print(f"CSV  → {csv_path}")
print(f"PPTX → {pptx_path}")
```

---

## Module Responsibilities

| Module | Responsibility |
|---|---|
| `config.py` | All constants, `PlotConfig` dataclass, `ColorScheme` |
| `exceptions.py` | `WaferToolError` hierarchy |
| `data_loader.py` | Parse CSV / tab-delimited files → clean DataFrame |
| `geometry.py` | `signed_log10`, coordinate transforms, interpolation grid |
| `plotting.py` | `draw_wafer_ax()` — renders one wafer onto a Matplotlib Axes |
| `statistics.py` | 8-condition classification, bar-chart summary page |
| `report.py` | End-to-end pipeline orchestrator |
| `exporters/pdf_exporter.py` | PDF with 5×5 grid pages and PDF bookmarks |
| `exporters/csv_exporter.py` | Colour-zone presence CSV |
| `exporters/pptx_exporter.py` | PowerPoint report (optional dependency) |
| `ui/main_window.py` | Root PyQt6 application window |
| `ui/orientation_widget.py` | Mirror + rotation controls with live preview |
| `ui/threshold_viz_widget.py` | Threshold band + scatter visualisation |

---

## Key Improvements Over v1

| Area | v1 (monolith) | v2 (modular) |
|---|---|---|
| Structure | Single 500-line file | 12 focused modules |
| Configuration | Loose kwargs everywhere | `PlotConfig` dataclass |
| Error handling | `print()` + bare returns | Custom exception hierarchy |
| Bug fix | `max_range == 10` (no-op) | `max_range = 10` (fixed) |
| Interpolation | Mixed cubic/linear | Consistent linear + nearest fallback |
| UI / logic coupling | Mixed in one class | UI calls `generate_report()` only |
| Type safety | None | Full type hints throughout |
| Testability | Untestable monolith | Each module independently testable |
| Scalability | Add code to one file | Add/swap modules without touching others |
