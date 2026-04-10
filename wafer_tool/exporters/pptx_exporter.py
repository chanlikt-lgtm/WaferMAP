"""
exporters/pptx_exporter.py
==========================
Generates a PowerPoint report from pre-rendered wafer PNG images.

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
create_powerpoint_report(png_dir, pptx_path, title_text, summary_imgs)
"""
from __future__ import annotations

import os
import sys

try:
    from pptx import Presentation
    from pptx.util import Pt
    from pptx.enum.text import PP_ALIGN
    HAS_PPTX = True
except ImportError:
    HAS_PPTX = False

__all__ = ["HAS_PPTX", "create_powerpoint_report"]

TEMPLATE_FILENAME = "Infineon Default Theme.pptx"


def create_powerpoint_report(
    png_dir:      str,
    pptx_path:    str,
    title_text:   str,
    summary_imgs: list[tuple[str, str]] | None = None,
) -> None:
    """
    Compile wafer PNG images (and optional summary charts) into a .pptx file.

    Parameters
    ----------
    png_dir      : Directory containing individual wafer PNG files (sorted alphabetically).
    pptx_path    : Destination path for the generated PowerPoint file.
    title_text   : Text displayed on the title slide.
    summary_imgs : Optional list of (slide_title, image_path) for summary slides
                   inserted after the title slide and before individual wafers.

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

    # ── Summary slides ────────────────────────────────────────────────────
    for img_title, img_path in (summary_imgs or []):
        if not os.path.exists(img_path):
            print(f"⚠  Summary image not found, skipped: {img_path}")
            continue
        slide = prs.slides.add_slide(content_layout)
        _set_title(slide, img_title)
        slide.shapes.add_picture(img_path, Pt(100), Pt(70), width=Pt(500))

    # ── Individual wafer slides ───────────────────────────────────────────
    png_files = sorted(
        f for f in os.listdir(png_dir) if f.lower().endswith(".png")
    )
    for filename in png_files:
        img_path = os.path.join(png_dir, filename)
        slide = prs.slides.add_slide(content_layout)
        _set_title(slide, os.path.splitext(filename)[0])
        slide.shapes.add_picture(img_path, Pt(100), Pt(100))

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
    """Return layout index 5 (blank with title) or the last available layout."""
    try:
        return prs.slide_layouts[5]
    except IndexError:
        return prs.slide_layouts[-1]


def _set_title(slide, text: str) -> None:
    """Format the slide title with Arial 24 pt bold left-aligned."""
    shape = slide.shapes.title
    if shape is None:
        return
    shape.text = text
    for para in shape.text_frame.paragraphs:
        para.alignment = PP_ALIGN.LEFT
        for run in para.runs:
            run.font.name = "Arial"
            run.font.size = Pt(24)
            run.font.bold = True
