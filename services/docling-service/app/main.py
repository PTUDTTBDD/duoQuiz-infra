"""Internal HTTP sidecar for PDF parsing, OCR, bbox extraction, and WebP rendering."""

from __future__ import annotations

import logging
import os
import tempfile
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from app.page_renderer import render_pages_to_webp
from app.parser import parse_pdf_document
from app.storage_client import S3StorageClient

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("docling-service")

app = FastAPI(title="DuoQuiz Docling Sidecar", version="0.1.0")


class ParseDocumentRequest(BaseModel):
    document_id: str = Field(..., min_length=1)
    storage_key: str = Field(..., min_length=1)
    preview_prefix: str = Field(..., min_length=1)
    min_chars_per_page: int = Field(default=40, ge=0, le=1000)


class NormalizedBBox(BaseModel):
    x: float
    y: float
    width: float
    height: float


class ExtractedChunk(BaseModel):
    chunk_index: int
    element_type: Literal["paragraph", "list", "table", "ocr_text"]
    content: str
    bbox: NormalizedBBox | None
    content_hash: str


class ExtractedPage(BaseModel):
    page_number: int
    width: int
    height: int
    image_storage_key: str
    text_char_count: int
    is_skipped: bool
    skip_reason: str | None = None
    chunks: list[ExtractedChunk]


class SkippedPageInfo(BaseModel):
    page_number: int
    reason: str


class ParseDocumentResponse(BaseModel):
    document_id: str
    page_count: int
    skipped_pages: list[SkippedPageInfo]
    pages: list[ExtractedPage]


def get_storage_client() -> S3StorageClient:
    return S3StorageClient(
        endpoint_url=os.environ.get("S3_ENDPOINT", "http://minio:9000"),
        bucket=os.environ.get("S3_BUCKET", "duoquiz-media"),
        access_key=os.environ.get("S3_ACCESS_KEY", "minioadmin"),
        secret_key=os.environ.get("S3_SECRET_KEY", "minioadmin"),
    )


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "docling-service"}


@app.post("/internal/parse", response_model=ParseDocumentResponse)
def parse_document(payload: ParseDocumentRequest) -> ParseDocumentResponse:
    storage = get_storage_client()
    with tempfile.TemporaryDirectory(prefix=f"docling_{payload.document_id}_") as tmp_dir:
        tmp_path = Path(tmp_dir)
        pdf_path = tmp_path / "source.pdf"

        try:
            storage.download_file(payload.storage_key, pdf_path)
        except Exception as exc:
            logger.exception("Failed to download PDF from storage")
            raise HTTPException(status_code=404, detail=f"Storage object not found: {exc}") from exc

        try:
            rendered_pages = render_pages_to_webp(pdf_path, tmp_path / "pages")
            parsed_pages = parse_pdf_document(
                pdf_path=pdf_path,
                rendered_pages=rendered_pages,
                min_chars_per_page=payload.min_chars_per_page,
            )

            response_pages: list[ExtractedPage] = []
            skipped_pages: list[SkippedPageInfo] = []

            for page in parsed_pages:
                image_key = f"{payload.preview_prefix.rstrip('/')}/page-{page['page_number']:04d}.webp"
                storage.upload_file(Path(page["local_webp_path"]), image_key, content_type="image/webp")

                if page["is_skipped"] and page["skip_reason"]:
                    skipped_pages.append(
                        SkippedPageInfo(page_number=page["page_number"], reason=page["skip_reason"])
                    )

                response_pages.append(
                    ExtractedPage(
                        page_number=page["page_number"],
                        width=page["width"],
                        height=page["height"],
                        image_storage_key=image_key,
                        text_char_count=page["text_char_count"],
                        is_skipped=page["is_skipped"],
                        skip_reason=page["skip_reason"],
                        chunks=[ExtractedChunk(**chunk) for chunk in page["chunks"]],
                    )
                )

            return ParseDocumentResponse(
                document_id=payload.document_id,
                page_count=len(response_pages),
                skipped_pages=skipped_pages,
                pages=response_pages,
            )
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        except Exception as exc:
            logger.exception("Unhandled error while parsing PDF")
            raise HTTPException(status_code=500, detail=f"PDF processing failed: {exc}") from exc

