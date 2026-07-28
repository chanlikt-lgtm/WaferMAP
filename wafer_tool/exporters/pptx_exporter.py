"""
exporters/pptx_exporter.py
==========================
Generates a PowerPoint report from ordered PNG snapshots of the PDF pages.

Gracefully degrades: if python-pptx is not installed, HAS_PPTX is False
and create_powerpoint_report raises ImportError with install instructions.

Template resolution order
--------------------------
1. <PyInstaller _MEIPASS>/Infineon Default Theme.pptx
2. <executable directory>/Infineon Default Theme.pptx
3. <this file's directory>/Infineon Default Theme.pptx
4. python-pptx blank presentation (fallback)

Public API
----------
HAS_PPTX : bool
create_powerpoint_report(page_png_dir, pptx_path, title_text)
"""
from __future__ import annotations

import os
import re
import sys

try:
    from pptx import Presentation
    from pptx.util import Pt
    HAS_PPTX = True
except ImportError:
    HAS_PPTX = False

__all__ = ["HAS_PPTX", "create_powerpoint_report"]

TEMPLATE_FILENAME = "Infineon Default Theme.pptx"


def create_powerpoint_report(
    page_png_dir: str,
    pptx_path: str,
    title_text: str,
) -> None:
    """
    Compile ordered PNG snapshots of PDF-style report pages into a .pptx file.

    Parameters
    ----------
    page_png_dir : Directory containing ordered report-page PNG files.
    pptx_path    : Destination path for the generated PowerPoint file.
    title_text   : Text displayed on the title slide.

    Raises
    ------
    ImportError
        If python-pptx is not installed.
    """
    if not HAS_PPTX:
        raise ImportError(
            "python-pptx is not installed.\n"
            "Install it with:  pip install python-pptx"
        )

    prs = _load_presentation()
    content_layout = _content_slide_layout(prs)

    # ── Title slide ───────────────────────────────────────────────────────
    title_slide = prs.slides.add_slide(prs.slide_layouts[0])
    if title_slide.shapes.title:
        title_slide.shapes.title.text = title_text

    # ── Report page slides ────────────────────────────────────────────────
    # Sort by the LEADING PAGE NUMBER numerically, not lexicographically: the
    # page-image names are zero-padded to only 3 digits, so a plain string sort
    # puts "1000_..." before "100_..." and "999_..." — scrambling every slide
    # past page 999 (e.g. a 2000+ page report from a large multi-lot file).
    def _page_order(fname: str):
        m = re.match(r"(\d+)", fname)
        return (int(m.group(1)) if m else 1 << 30, fname)

    png_files = sorted(
        (f for f in os.listdir(page_png_dir) if f.lower().endswith(".png")),
        key=_page_order,
    )
    for filename in png_files:
        img_path = os.path.join(page_png_dir, filename)
        slide = prs.slides.add_slide(content_layout)
        _set_slide_title(slide, _slide_title_from_filename(filename))
        _add_report_page(slide, prs, img_path)

    import gc; gc.collect()   # free any lingering PNG buffers before writing
    prs.save(pptx_path)
    print(f"✓ PowerPoint saved: {pptx_path}")


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _find_template() -> str | None:
    """Return the first existing template path, or None."""
    candidates: list[str] = []
    if getattr(sys, "frozen", False):
        candidates.append(os.path.join(sys._MEIPASS, TEMPLATE_FILENAME))
        candidates.append(os.path.join(os.path.dirname(sys.executable), TEMPLATE_FILENAME))
    candidates.append(
        os.path.join(os.path.dirname(os.path.abspath(__file__)), TEMPLATE_FILENAME)
    )
    return next((p for p in candidates if os.path.exists(p)), None)


def _load_presentation() -> "Presentation":
    template = _find_template()
    if template:
        try:
            prs = Presentation(template)
            print(f"✓ Loaded PPTX template: {template}")
            return prs
        except Exception as exc:
            print(f"⚠  Template load failed ({exc}). Using default.")
    else:
        print("⚠  No PPTX template found — using python-pptx default.")
    return Presentation()


def _content_slide_layout(prs: "Presentation"):
    """Return a layout with a title placeholder when available."""
    try:
        return prs.slide_layouts[5]
    except IndexError:
        return prs.slide_layouts[-1]


def _add_report_page(slide, prs: "Presentation", img_path: str) -> None:
    """Place a PDF-style page snapshot below the slide title with small margins."""
    margin = Pt(10)
    title_bottom = _title_bottom(slide)
    top = max(title_bottom + Pt(6), margin)
    picture = slide.shapes.add_picture(img_path, 0, 0, height=prs.slide_height - top - margin)
    picture.left = int((prs.slide_width - picture.width) / 2)
    picture.top = int(top)


def _set_slide_title(slide, text: str) -> None:
    """Populate the slide title so PowerPoint outline view can display it."""
    if slide.shapes.title is not None:
        slide.shapes.title.text = text
        return

    textbox = slide.shapes.add_textbox(Pt(20), Pt(10), Pt(700), Pt(30))
    textbox.text_frame.text = text


def _title_bottom(slide) -> int:
    if slide.shapes.title is None:
        return 0
    return slide.shapes.title.top + slide.shapes.title.height


def _slide_title_from_filename(filename: str) -> str:
    stem = os.path.splitext(filename)[0]
    stem = re.sub(r"^\d+_", "", stem)

    if stem.startswith("summary_report"):
        match = re.search(r"page_(\d+)$", stem)
        if match and match.group(1) != "1":
            return f"Summary Report ({match.group(1)})"
        return "Summary Report"

    if stem == "8_condition_distribution":
        return "8-Condition Distribution"

    match = re.match(r"lot_(.+?)_page_(\d+)$", stem)
    if match:
        lot_id, page_num = match.groups()
        lot_title = f"Lot ID: {lot_id}"
        if page_num != "1":
            return f"{lot_title} ({page_num})"
        return lot_title

    return stem.replace("_", " ").title()
