from __future__ import annotations

import argparse
import json
import re
import zipfile
from pathlib import Path
import xml.etree.ElementTree as ET

from pypdf import PdfReader


NS_P = {"p": "http://schemas.openxmlformats.org/presentationml/2006/main"}
NS_A = {"a": "http://schemas.openxmlformats.org/drawingml/2006/main"}
NS_R = {"r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships"}
PKG_REL_NS = {"pr": "http://schemas.openxmlformats.org/package/2006/relationships"}


def inspect_pdf(pdf_path: Path, lot_id: str | None) -> dict:
    reader = PdfReader(str(pdf_path))
    pages = []
    contexts = []

    if lot_id:
        outline_entries = _flatten_outline(reader)
        summary_end = _summary_end_page(outline_entries, len(reader.pages))

        for index in range(1, summary_end + 1):
            _maybe_add_pdf_hit(reader, index, lot_id, pages, contexts)

        for title, index in outline_entries:
            if lot_id not in title:
                continue
            _maybe_add_pdf_hit(reader, index, lot_id, pages, contexts, fallback_text=title)

        if not pages:
            for index, _page in enumerate(reader.pages, start=1):
                _maybe_add_pdf_hit(reader, index, lot_id, pages, contexts)

    return {
        "path": str(pdf_path),
        "pages": len(reader.pages),
        "lot_pages": pages,
        "lot_context": contexts,
    }


def inspect_pptx(pptx_path: Path, lot_id: str | None) -> dict:
    with zipfile.ZipFile(pptx_path) as archive:
        presentation = ET.fromstring(archive.read("ppt/presentation.xml"))
        relationships = ET.fromstring(archive.read("ppt/_rels/presentation.xml.rels"))
        rel_map = {
            rel.attrib["Id"]: rel.attrib["Target"].lstrip("/")
            for rel in relationships.findall("pr:Relationship", PKG_REL_NS)
        }

        slide_id_list = presentation.find("p:sldIdLst", NS_P)
        slide_parts: list[str] = []
        if slide_id_list is not None:
            for slide_id in slide_id_list.findall("p:sldId", NS_P):
                rel_id = slide_id.attrib.get(f"{{{NS_R['r']}}}id")
                target = rel_map.get(rel_id)
                if not target:
                    continue
                if not target.startswith("ppt/"):
                    target = f"ppt/{target.lstrip('/')}"
                slide_parts.append(target)

        lot_text_slides = []
        slide_flags = []

        for index, part in enumerate(slide_parts, start=1):
            slide_xml = ET.fromstring(archive.read(part))
            texts = [node.text or "" for node in slide_xml.findall(".//a:t", NS_A)]
            joined = "\n".join(texts)
            pic_count = len(slide_xml.findall(".//p:pic", NS_P))
            has_text = any(text.strip() for text in texts)

            if lot_id and lot_id in joined:
                lot_text_slides.append(index)

            slide_flags.append({"slide": index, "has_text": has_text, "pic_count": pic_count})

    return {
        "path": str(pptx_path),
        "slides": len(slide_parts),
        "lot_text_slides": lot_text_slides,
        "slide_flags": slide_flags,
    }


def build_report(pdf_info: dict, pptx_info: dict, lot_id: str | None) -> dict:
    pdf_pages = pdf_info["pages"]
    ppt_slides = pptx_info["slides"]
    delta = ppt_slides - pdf_pages

    if delta == 1:
        parity = "page-based: title slide + one slide per PDF page"
        inferred_slides = [page + 1 for page in pdf_info["lot_pages"]]
    elif delta == 0:
        parity = "page-based: one slide per PDF page"
        inferred_slides = list(pdf_info["lot_pages"])
    else:
        parity = f"mismatch: {ppt_slides} slides for {pdf_pages} PDF pages"
        inferred_slides = []

    report = {
        "pdf": pdf_info,
        "pptx": pptx_info,
        "parity": parity,
    }

    if lot_id:
        report["lot"] = {
            "id": lot_id,
            "pdf_pages": pdf_info["lot_pages"],
            "pdf_context": pdf_info["lot_context"],
            "ppt_text_slides": pptx_info["lot_text_slides"],
            "ppt_inferred_slides": inferred_slides,
        }

    return report


def _flatten_outline(reader: PdfReader) -> list[tuple[str, int]]:
    entries: list[tuple[str, int]] = []

    def walk(nodes) -> None:
        for node in nodes:
            if isinstance(node, list):
                walk(node)
                continue
            title = getattr(node, "title", None)
            if not title:
                continue
            try:
                page_index = reader.get_destination_page_number(node) + 1
            except Exception:
                continue
            entries.append((str(title), page_index))

    try:
        walk(reader.outline)
    except Exception:
        return []

    return entries


def _summary_end_page(outline_entries: list[tuple[str, int]], page_count: int) -> int:
    for title, page_index in outline_entries:
        if title.startswith("8-Condition Distribution"):
            return max(page_index - 1, 1)
    return min(page_count, 10)


def _maybe_add_pdf_hit(
    reader: PdfReader,
    index: int,
    lot_id: str,
    pages: list[int],
    contexts: list[dict],
    fallback_text: str | None = None,
) -> None:
    if index in pages:
        return

    text = reader.pages[index - 1].extract_text() or ""
    if lot_id not in text and fallback_text is None:
        return

    pages.append(index)
    lines = [line.strip() for line in text.splitlines() if lot_id in line]
    if lines:
        contexts.append({"page": index, "match_lines": lines[:3]})
        return

    if fallback_text:
        contexts.append({"page": index, "match_lines": [fallback_text]})
        return

    match = re.search(rf".{{0,80}}{re.escape(lot_id)}.{{0,80}}", text, re.S)
    contexts.append(
        {
            "page": index,
            "match_excerpt": match.group(0).replace("\n", " ") if match else lot_id,
        }
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check PDF/PPT export parity for wafer reports.")
    parser.add_argument("pdf", type=Path, help="Path to the exported PDF")
    parser.add_argument("pptx", type=Path, help="Path to the exported PPTX")
    parser.add_argument("--lot", dest="lot_id", help="Optional lot ID to trace across both outputs")
    parser.add_argument("--json", action="store_true", help="Emit JSON instead of plain text")
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    pdf_path = args.pdf.resolve()
    pptx_path = args.pptx.resolve()
    if not pdf_path.is_file():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")
    if not pptx_path.is_file():
        raise FileNotFoundError(f"PPTX not found: {pptx_path}")

    pdf_info = inspect_pdf(pdf_path, args.lot_id)
    pptx_info = inspect_pptx(pptx_path, args.lot_id)
    report = build_report(pdf_info, pptx_info, args.lot_id)

    if args.json:
        print(json.dumps(report, indent=2))
        return 0

    print(f"PDF:   {pdf_info['path']}")
    print(f"PPTX:  {pptx_info['path']}")
    print(f"Pages: {pdf_info['pages']}")
    print(f"Slides: {pptx_info['slides']}")
    print(f"Parity: {report['parity']}")

    if args.lot_id:
        lot = report["lot"]
        print(f"Lot: {lot['id']}")
        print(f"PDF lot pages: {lot['pdf_pages']}")
        print(f"PPT text slides: {lot['ppt_text_slides']}")
        print(f"PPT inferred slides: {lot['ppt_inferred_slides']}")
        for item in lot["pdf_context"]:
            if "match_lines" in item:
                snippet = " | ".join(item["match_lines"])
            else:
                snippet = item["match_excerpt"]
            print(f"PDF page {item['page']}: {snippet}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())