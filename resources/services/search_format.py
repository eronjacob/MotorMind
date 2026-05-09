"""
Format Chroma hits for API / HTML previews (metadata + citations).

Chunk bodies come from Chroma only — SQLite Resource rows carry no per-chunk text.
"""

from __future__ import annotations

import json
from typing import Any

from resources.models import Resource


def _parse_course_ids(meta: dict[str, Any]) -> list[int]:
    csv = str(meta.get("course_ids_csv") or "")
    ids: list[int] = []
    for part in csv.split(","):
        part = part.strip()
        if not part:
            continue
        try:
            ids.append(int(part))
        except ValueError:
            continue
    if ids:
        return ids
    raw = meta.get("course_ids_json")
    if not raw:
        return []
    try:
        data = json.loads(raw) if isinstance(raw, str) else raw
        return [int(x) for x in data]
    except (TypeError, ValueError, json.JSONDecodeError):
        return []


def format_api_results(hits: list[dict[str, Any]], text_preview_chars: int | None = None) -> list[dict[str, Any]]:
    """Shape matches /api/resources/search/ contract."""
    out: list[dict[str, Any]] = []
    for h in hits:
        meta = dict(h.get("metadata") or {})
        rid = int(h.get("resource_id") or meta.get("resource_id") or 0)
        resource = Resource.objects.filter(pk=rid).prefetch_related("courses").first()
        courses_payload = (
            [{"id": c.id, "title": c.title} for c in resource.courses.all()]
            if resource
            else []
        )
        page_number = meta.get("page_number")
        try:
            page_display = int(page_number) if page_number is not None else None
        except (TypeError, ValueError):
            page_display = None
        title = resource.title if resource else meta.get("resource_title", "")
        source_title = (resource.source_title if resource else None) or meta.get("source_title", "")
        author = (resource.author if resource else None) or meta.get("author", "")
        text = h.get("text") or ""
        if text_preview_chars is not None:
            text = text[:text_preview_chars]
        if page_display and page_display > 0:
            citation = f"{source_title or title}, p.{page_display}"
        else:
            citation = f"{source_title or title}"
        course_ids = _parse_course_ids(meta)
        meta_out = {
            "page_number": page_display,
            "chunk_index": int(meta.get("chunk_index", 0)),
            "course_ids": course_ids,
        }
        out.append(
            {
                "vector_id": h.get("vector_id"),
                "text": text,
                "score": h.get("score"),
                "resource": {
                    "id": resource.id if resource else rid,
                    "title": title,
                    "source_title": source_title,
                    "author": author,
                    "courses": courses_payload,
                },
                "metadata": meta_out,
                "citation": citation,
            }
        )
    return out
