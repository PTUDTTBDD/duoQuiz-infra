"""PDF rendering to WebP previews via Poppler + Pillow."""

from __future__ import annotations

from pathlib import Path
from typing import TypedDict

from pdf2image import convert_from_path
from pypdf import PdfReader

MAX_PDF_PAGES = 150
MAX_PREVIEW_WIDTH = 1440
WEBP_QUALITY = 82


class RenderedPageInfo(TypedDict):
    page_number: int
    width: int
    height: int
    local_webp_path: str


def render_pages_to_webp(pdf_path: Path, output_dir: Path) -> list[RenderedPageInfo]:
    """Validate page count and render each PDF page as an optimized WebP image."""
    reader = PdfReader(str(pdf_path))
    total_pages = len(reader.pages)
    if total_pages == 0:
        raise ValueError("PDF file contains zero pages.")
    if total_pages > MAX_PDF_PAGES:
        raise ValueError(f"PDF exceeds maximum allowed {MAX_PDF_PAGES} pages (got {total_pages}).")

    output_dir.mkdir(parents=True, exist_ok=True)
    images = convert_from_path(str(pdf_path), dpi=150, fmt="png")
    results: list[RenderedPageInfo] = []

    for idx, img in enumerate(images, start=1):
        if img.width > MAX_PREVIEW_WIDTH:
            ratio = MAX_PREVIEW_WIDTH / float(img.width)
            target_size = (MAX_PREVIEW_WIDTH, max(1, int(img.height * ratio)))
            img = img.resize(target_size)

        webp_path = output_dir / f"page-{idx:04d}.webp"
        img.save(webp_path, format="WEBP", quality=WEBP_QUALITY, method=6)
        results.append(
            {
                "page_number": idx,
                "width": img.width,
                "height": img.height,
                "local_webp_path": str(webp_path),
            }
        )

    return results

