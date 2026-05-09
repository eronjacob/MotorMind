"""
Simple character-based chunking with overlap.

Chunk text is stored only in ChromaDB as the document body — not in SQLite.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

DEFAULT_CHUNK_SIZE = 1000
DEFAULT_OVERLAP = 200


def chunk_text(
    text: str,
    metadata: dict[str, Any] | None = None,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    overlap: int = DEFAULT_OVERLAP,
) -> list[dict[str, Any]]:
    """
    Split `text` into overlapping windows of roughly `chunk_size` characters.

    Each chunk dict: text, char_start, char_end, chunk_index, plus copied metadata keys.
    """
    metadata = metadata or {}
    text = text or ""
    if not text.strip():
        return []

    chunk_size = max(200, min(chunk_size, 1200))
    overlap = max(50, min(overlap, 250))
    if overlap >= chunk_size:
        overlap = max(50, chunk_size // 4)

    chunks: list[dict[str, Any]] = []
    start = 0
    idx = 0
    n = len(text)
    while start < n:
        end = min(n, start + chunk_size)
        piece = text[start:end].strip()
        if piece:
            row = {
                "text": piece,
                "char_start": start,
                "char_end": end,
                "chunk_index": idx,
                **metadata,
            }
            chunks.append(row)
            idx += 1
        if end >= n:
            break
        start = end - overlap
    logger.debug("chunk_text produced %s chunks (size=%s overlap=%s)", len(chunks), chunk_size, overlap)
    return chunks


def chunk_pages(
    pages: list[dict],
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    overlap: int = DEFAULT_OVERLAP,
) -> list[dict[str, Any]]:
    """
    Chunk each page's text separately so page_number metadata stays accurate.

    `pages`: list of {"page_number": int, "text": str}.
    """
    all_chunks: list[dict[str, Any]] = []
    global_index = 0
    for page in pages:
        page_no = int(page.get("page_number") or 1)
        body = (page.get("text") or "").strip()
        if not body:
            continue
        for c in chunk_text(
            body,
            metadata={"page_number": page_no, "section_title": ""},
            chunk_size=chunk_size,
            overlap=overlap,
        ):
            c["chunk_index"] = global_index
            global_index += 1
            all_chunks.append(c)
    return all_chunks
