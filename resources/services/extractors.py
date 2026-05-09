"""
Extract plain text from uploaded learning resources (PDF, TXT, MD, DOCX).

Raises ValueError with a clear message for unsupported types or empty extraction.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)


def extract_text_from_pdf(file_path: str | Path) -> list[dict]:
    """Return list of {page_number, text} for each PDF page (1-based page_number)."""
    try:
        from pypdf import PdfReader
    except ImportError as exc:  # pragma: no cover
        raise ValueError(
            "pypdf is not installed. Add it to requirements.txt and reinstall."
        ) from exc

    path = Path(file_path)
    reader = PdfReader(str(path))
    pages: list[dict] = []
    for i, page in enumerate(reader.pages, start=1):
        try:
            text = page.extract_text() or ""
        except Exception as exc:  # pragma: no cover
            logger.warning("PDF page %s extract failed: %s", i, exc)
            text = ""
        pages.append({"page_number": i, "text": text.strip()})
    if not any(p["text"] for p in pages):
        raise ValueError("PDF contained no extractable text (may be scanned images only).")
    return pages


def extract_text_from_txt(file_path: str | Path) -> list[dict]:
    path = Path(file_path)
    text = path.read_text(encoding="utf-8", errors="replace").strip()
    if not text:
        raise ValueError("Text file is empty.")
    return [{"page_number": 1, "text": text}]


def extract_text_from_markdown(file_path: str | Path) -> list[dict]:
    # Treat Markdown as plain text for chunking; rendering is not required for RAG.
    return extract_text_from_txt(file_path)


def extract_text_from_docx(file_path: str | Path) -> list[dict]:
    try:
        import docx  # type: ignore
    except ImportError as exc:  # pragma: no cover
        raise ValueError(
            "python-docx is not installed. Add it to requirements.txt and reinstall."
        ) from exc

    path = Path(file_path)
    document = docx.Document(str(path))
    parts: list[str] = []
    for para in document.paragraphs:
        if para.text and para.text.strip():
            parts.append(para.text.strip())
    text = "\n\n".join(parts).strip()
    if not text:
        raise ValueError("DOCX contained no paragraph text.")
    return [{"page_number": 1, "text": text}]


def extract_resource_text(resource) -> list[dict]:
    """
    Dispatch extractor based on file extension.

    Returns a list of page dicts: {"page_number": int, "text": str}.
    """
    path = getattr(resource.uploaded_file, "path", None)
    if not path or not os.path.isfile(path):
        raise ValueError("Uploaded file is missing on disk.")

    name = (resource.original_filename or Path(path).name or "").lower()
    ext = Path(name).suffix.lower()
    if ext == ".pdf":
        return extract_text_from_pdf(path)
    if ext in (".txt", ".text"):
        return extract_text_from_txt(path)
    if ext in (".md", ".markdown"):
        return extract_text_from_markdown(path)
    if ext == ".docx":
        return extract_text_from_docx(path)
    raise ValueError(f"Unsupported file extension for ingestion: {ext or 'unknown'}")
