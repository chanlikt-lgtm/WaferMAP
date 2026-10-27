"""
run_verification.py
===================
Command-line entry point for the waferplot_ORIN pipeline.

Steps executed
--------------
1.  Starts / connects to OriginLab.
2.  Reads the data file.
3.  For each wafer (up to --max_wafers):
      a. Renders a Python/Matplotlib PNG (same as the main report).
      b. Imports the interpolated grid into Origin and renders a
         Color-Fill Contour PNG with matching 3-zone colours.
      c. Saves a side-by-side + pixel-diff comparison image.
4.  Saves the Origin project (.opju) to the output folder.

Usage examples
--------------
# Basic (first 5 wafers, linear scale, high=red)
python -m waferplot_ORIN.run_verification \\
    --file "VT_FP.M1 805.txt" --t_low 1e-5 --t_high 1e-4

# Log scale, high values = green, 10 wafers
python -m waferplot_ORIN.run_verification \\
    --file "VT_FP.M1 805.txt" --t_low 1e-5 --t_high 1e-4 \\
    --log --high_green --max_wafers 10

# Custom output directory
python -m waferplot_ORIN.run_verification \\
    --file data.csv --t_low 0.01 --t_high 0.1 \\
    --out_dir C:/results/verification

Output layout
-------------
<out_dir>/
    python_pngs/   <id>_python.png   — Matplotlib renders
    origin_pngs/   <id>_origin.png   — OriginLab renders
    comparisons/   <id>_compare.png  — 3-panel side-by-side + diff
    wafer_origin_plots.opju          — saved Origin project
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path


# ── Project root ──────────────────────────────────────────────────────────
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="OriginLab wafer map export & side-by-side verification",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__.split("Output layout")[0].split("Usage examples")[1].strip(),
    )
    # Required
    p.add_argument(
        "--file", required=True, metavar="PATH",
        help="Input data file (CSV / tab-delimited wafer measurement data)",
    )
    p.add_argument("--t_low",  type=float, required=True, metavar="FLOAT",
                   help="Low threshold value")
    p.add_argument("--t_high", type=float, required=True, metavar="FLOAT",
                   help="High threshold value")

    # Optional plot settings
    p.add_argument("--log",        action="store_true",
                   help="Use log10 scale for threshold mapping")
    p.add_argument("--high_green", action="store_true",
                   help="High values = green (default: high values = red)")
    p.add_argument("--mirror_x",   action="store_true",
                   help="Mirror X coordinates")
    p.add_argument("--mirror_y",   action="store_true",
                   help="Mirror Y coordinates")
    p.add_argument("--rot_deg",    type=int, default=0,
                   choices=[0, 90, 180, 270],
                   metavar="{0,90,180,270}",
                   help="Clockwise rotation in degrees (default: 0)")

    # Optional pipeline settings
    p.add_argument("--max_wafers", type=int, default=5, metavar="N",
                   help="Maximum number of wafers to verify (default: 5)")
    p.add_argument("--out_dir",    default=None, metavar="PATH",
                   help="Output directory (default: waferplot_ORIN/output)")
    p.add_argument("--hide_origin", action="store_true",
                   help="Run Origin hidden (no GUI window shown)")

    return p.parse_args()


def main() -> None:
    args = _parse_args()

    # ── Imports (deferred so --help works without Origin installed) ────────
    import originpro as op
    from wafer_tool.config import PlotConfig
    from .verify_side_by_side import verify_lot

    config = PlotConfig(
        t_low=args.t_low,
        t_high=args.t_high,
        use_log=args.log,
        high_is_green=args.high_green,
        mirror_x=args.mirror_x,
        mirror_y=args.mirror_y,
        rot_deg=args.rot_deg,
    )

    data_file = Path(args.file)
    out_dir   = (
        Path(args.out_dir)
        if args.out_dir
        else Path(__file__).parent / "output"
    )

    # ── Banner ─────────────────────────────────────────────────────────────
    sep = "─" * 58
    print(f"\n{sep}")
    print("  WaferMap  ▸  OriginLab Export & Side-by-Side Verification")
    print(sep)
    print(f"  Data file   : {data_file.name}")
    print(f"  t_low/high  : {config.t_low}  /  {config.t_high}")
    print(f"  Log scale   : {config.use_log}")
    print(f"  High=green  : {config.high_is_green}")
    print(f"  Transforms  : mirror_x={config.mirror_x}  mirror_y={config.mirror_y}"
          f"  rot={config.rot_deg}°")
    print(f"  Max wafers  : {args.max_wafers}")
    print(f"  Output dir  : {out_dir}")
    print(sep)

    # ── Connect to / start OriginLab ───────────────────────────────────────
    print("\n[1/3]  Connecting to OriginLab …")
    op.set_show(not args.hide_origin)
    # Trigger connection by querying Origin version
    ver = op.lt_float("@V")
    print(f"       Origin version: {ver:.2f}")

    # ── Verify wafers ──────────────────────────────────────────────────────
    print(f"\n[2/3]  Generating Python + Origin plots …")
    comparisons = verify_lot(
        data_file=data_file,
        config=config,
        out_dir=out_dir,
        max_wafers=args.max_wafers,
    )

    # ── Save Origin project ────────────────────────────────────────────────
    print(f"\n[3/3]  Saving Origin project …")
    proj_path = out_dir / "wafer_origin_plots.opju"
    op.save(str(proj_path))
    print(f"       Saved: {proj_path}")

    # ── Summary ────────────────────────────────────────────────────────────
    print(f"\n{sep}")
    if comparisons:
        print(f"  Verification complete — {len(comparisons)} wafer(s) compared.")
        print(f"  Comparisons: {out_dir / 'comparisons'}")
        print(f"  Python PNGs: {out_dir / 'python_pngs'}")
        print(f"  Origin PNGs: {out_dir / 'origin_pngs'}")
    else:
        print("  No comparisons generated.")
        print("  Check: does the data file exist?  Are thresholds appropriate?")
    print(sep + "\n")


if __name__ == "__main__":
    main()
