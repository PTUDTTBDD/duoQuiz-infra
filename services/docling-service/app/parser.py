"""Docling PDF parser with OCR, normalized [0..1] bbox, and skipped-page detection."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any, Literal, TypedDict

from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import PdfPipelineOptions
from docling.document_converter import DocumentConverter, PdfFormatOption

from app.page_renderer import RenderedPageInfo


class NormalizedBBoxDict(TypedDict):
    x: float
    y: float
    width: float
    height: float


class ChunkDict(TypedDict):
    chunk_index: int
    element_type: Literal["paragraph", "list", "table", "ocr_text"]
    content: str
    bbox: NormalizedBBoxDict | None
    content_hash: str


class ParsedPageDict(TypedDict):
    page_number: int
    width: int
    height: int
    local_webp_path: str
    text_char_count: int
    is_skipped: bool
    skip_reason: str | None
    chunks: list[ChunkDict]


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, value))


def _normalize_bbox(prov: Any, page_width: float, page_height: float) -> NormalizedBBoxDict | None:
    bbox = getattr(prov, "bbox", None)
    if bbox is None or page_width <= 0 or page_height <= 0:
        return None

    left = float(getattr(bbox, "l", 0.0))
    right = float(getattr(bbox, "r", 0.0))
    top = float(getattr(bbox, "t", 0.0))
    bottom = float(getattr(bbox, "b", 0.0))

    coord_origin = str(getattr(bbox, "coord_origin", "BOTTOMLEFT")).upper()
    if "BOTTOMLEFT" in coord_origin:
        y_top = page_height - max(top, bottom)
        y_bottom = page_height - min(top, bottom)
    else:
        y_top = min(top, bottom)
        y_bottom = max(top, bottom)

    x_min = _clamp01(min(left, right) / page_width)
    y_min = _clamp01(y_top / page_height)
    width = _clamp01((max(left, right) - min(left, right)) / page_width)
    height = _clamp01((y_bottom - y_top) / page_height)
    return {"x": round(x_min, 5), "y": round(y_min, 5), "width": round(width, 5), "height": round(height, 5)}


def _map_element_type(label: str) -> Literal["paragraph", "list", "table", "ocr_text"]:
    lowered = label.lower()
    if "table" in lowered:
        return "table"
    if "list" in lowered:
        return "list"
    return "paragraph"


def parse_pdf_document(
    pdf_path: Path,
    rendered_pages: list[RenderedPageInfo],
    min_chars_per_page: int = 40,
) -> list[ParsedPageDict]:
    """Parse PDF with Docling (OCR enabled) and attach chunks to each rendered page."""
    pipeline_options = PdfPipelineOptions()
    pipeline_options.do_ocr = True
    pipeline_options.do_table_structure = True

    converter = DocumentConverter(
        format_options={
            InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options),
        }
    )
    conv_result = converter.convert(str(pdf_path))
    doc = conv_result.document

    page_dimensions: dict[int, tuple[float, float]] = {}
    for page_no, page_obj in getattr(doc, "pages", {}).items():
        size = getattr(page_obj, "size", None)
        if size is not None:
            page_dimensions[int(page_no)] = (float(size.width), float(size.height))

    chunks_by_page: dict[int, list[ChunkDict]] = {p["page_number"]: [] for p in rendered_pages}

    for item, _level in doc.iterate_items():
        text = (getattr(item, "text", None) or "").strip()
        if not text:
            continue

        provs = getattr(item, "prov", None) or []
        if not provs:
            continue

        prov = provs[0]
        page_no = int(getattr(prov, "page_no", 1))
        if page_no not in chunks_by_page:
            continue

        page_w, page_h = page_dimensions.get(page_no, (1.0, 1.0))
        norm_bbox = _normalize_bbox(prov, page_w, page_h)
        label = str(getattr(item, "label", "paragraph"))

        page_chunks = chunks_by_page[page_no]
        page_chunks.append(
            {
                "chunk_index": len(page_chunks),
                "element_type": _map_element_type(label),
                "content": text,
                "bbox": norm_bbox,
                "content_hash": hashlib.sha256(text.encode("utf-8")).hexdigest(),
            }
        )

    results: list[ParsedPageDict] = []
    for rendered in rendered_pages:
        page_no = rendered["page_number"]
        page_chunks = chunks_by_page.get(page_no, [])
        char_count = sum(len(c["content"]) for c in page_chunks)
        is_skipped = char_count < min_chars_per_page
        skip_reason = "LOW_TEXT_CONTENT" if is_skipped else None

        results.append(
            {
                "page_number": page_no,
                "width": rendered["width"],
                "height": rendered["height"],
                "local_webp_path": rendered["local_webp_path"],
                "text_char_count": char_count,
                "is_skipped": is_skipped,
                "skip_reason": skip_reason,
                "chunks": page_chunks,
            }
        )

    return results

