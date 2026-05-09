"""
ISBN metadata lookup: Open Library (primary) + Google Books (fallback / enrichment).

Uses the direct Open Library ISBN endpoint and resolves author keys via /authors/*.json
and work keys via /works/*.json when the edition record has no inline authors.
"""

from __future__ import annotations

import logging
import re
from typing import Any

import requests
from django.conf import settings

from resources.services.isbn import clean_isbn, normalise_isbn

logger = logging.getLogger(__name__)

TIMEOUT = 10.0
HEADERS = {"User-Agent": "CarHoot/1.0 (educational prototype)"}


def _get_json(url: str) -> tuple[int, dict[str, Any] | None, str]:
    """HTTP GET returning (status_code, json_dict_or_none, error_message)."""
    try:
        r = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
        logger.info("book_metadata GET %s -> status=%s", url, r.status_code)
        if r.status_code != 200:
            return r.status_code, None, f"HTTP {r.status_code}"
        return r.status_code, r.json(), ""
    except requests.RequestException as exc:
        logger.warning("book_metadata request failed %s: %s", url, exc)
        return 0, None, str(exc)


def _truncate_for_raw(obj: Any, max_chars: int = 4000) -> Any:
    """Avoid storing/logging enormous blobs unless DEBUG."""
    if settings.DEBUG:
        return obj
    if isinstance(obj, str) and len(obj) > max_chars:
        return obj[:max_chars] + "…(truncated)"
    if isinstance(obj, dict):
        return {k: _truncate_for_raw(v, max_chars // max(len(obj), 1)) for k, v in list(obj.items())[:40]}
    if isinstance(obj, list):
        return [_truncate_for_raw(x, max_chars) for x in obj[:30]]
    return obj


def _parse_year(value: Any) -> str:
    if value is None:
        return ""
    s = str(value).strip()
    if not s:
        return ""
    m = re.search(r"(\d{4})", s)
    return m.group(1) if m else ""


def _author_url(key: str) -> str:
    key = (key or "").strip()
    if not key.startswith("/"):
        key = "/" + key
    return f"https://openlibrary.org{key}.json"


def _resolve_author_name(author_key: str) -> str:
    """Fetch /authors/OL....json; failures are non-fatal."""
    if not author_key:
        return ""
    url = _author_url(author_key)
    status, data, err = _get_json(url)
    logger.info("book_metadata author lookup %s title_found=%s err=%s", url, bool(data and data.get("name")), err)
    if not data or not isinstance(data, dict):
        return ""
    return (data.get("name") or data.get("personal_name") or "").strip()


def _authors_from_edition_obj(edition: dict) -> list[str]:
    names: list[str] = []
    for entry in edition.get("authors") or []:
        if not isinstance(entry, dict):
            continue
        if entry.get("name"):
            names.append(str(entry["name"]).strip())
            continue
        key = entry.get("key")
        if key:
            n = _resolve_author_name(str(key))
            if n:
                names.append(n)
    return names


def _authors_from_work_obj(work: dict) -> list[str]:
    names: list[str] = []
    for entry in work.get("authors") or []:
        if not isinstance(entry, dict):
            continue
        auth = entry.get("author")
        if isinstance(auth, dict) and auth.get("key"):
            n = _resolve_author_name(str(auth["key"]))
            if n:
                names.append(n)
    return names


def _fetch_open_library(isbn: str) -> tuple[dict[str, Any] | None, dict[str, Any], str]:
    """
    Primary path: GET https://openlibrary.org/isbn/{isbn}.json

    Returns (normalized_dict_or_none, raw_fragments, error_message).
    """
    url = f"https://openlibrary.org/isbn/{isbn}.json"
    status, edition, err = _get_json(url)
    raw: dict[str, Any] = {
        "open_library_isbn_url": url,
        "open_library_isbn_status": status,
    }
    if not edition or not isinstance(edition, dict):
        msg = err or "empty or invalid Open Library edition JSON"
        raw["error"] = msg
        logger.info("book_metadata Open Library edition: no usable JSON (%s)", msg)
        return None, raw, msg

    if settings.DEBUG:
        raw["open_library_edition"] = _truncate_for_raw(edition)

    title = (edition.get("title") or "").strip()
    subtitle = (edition.get("subtitle") or "").strip()
    if subtitle and title:
        title = f"{title}: {subtitle}"
    elif subtitle:
        title = subtitle

    publishers = edition.get("publishers") or []
    publisher = ", ".join(
        p.strip() for p in publishers if isinstance(p, str) and p.strip()
    )

    year = _parse_year(edition.get("publish_date"))

    description = ""
    notes = edition.get("notes")
    if isinstance(notes, str):
        description = notes.strip()
    elif isinstance(notes, dict):
        description = str(notes.get("value", "")).strip()

    edition_name = (edition.get("edition_name") or "").strip()
    n_pages = edition.get("number_of_pages")
    number_of_pages: int | None
    try:
        number_of_pages = int(n_pages) if n_pages is not None else None
    except (TypeError, ValueError):
        number_of_pages = None

    authors = _authors_from_edition_obj(edition)
    if not authors:
        works = edition.get("works") or []
        if works and isinstance(works[0], dict) and works[0].get("key"):
            wkey = str(works[0]["key"])
            work_url = f"https://openlibrary.org{wkey}.json" if wkey.startswith("/") else f"https://openlibrary.org/{wkey}.json"
            wstatus, work, werr = _get_json(work_url)
            raw["open_library_work_url"] = work_url
            raw["open_library_work_status"] = wstatus
            logger.info(
                "book_metadata Open Library work: status=%s title_found=%s err=%s",
                wstatus,
                bool(work and work.get("title")),
                werr,
            )
            if settings.DEBUG and work:
                raw["open_library_work"] = _truncate_for_raw(work)
            if work and isinstance(work, dict):
                authors = _authors_from_work_obj(work)
                if not title:
                    title = (work.get("title") or "").strip()

    norm: dict[str, Any] = {
        "isbn": isbn,
        "title": title,
        "source_title": title,
        "authors": authors,
        "author": ", ".join(authors) if authors else "",
        "publisher": publisher,
        "year": year,
        "description": description,
        "edition": edition_name,
        "number_of_pages": number_of_pages,
    }
    logger.info(
        "book_metadata Open Library normalized: title_found=%s author_found=%s publisher_found=%s",
        bool(title.strip()),
        bool(norm["author"]),
        bool(publisher),
    )
    return norm, raw, ""


def _fetch_google_books(isbn: str) -> tuple[dict[str, Any] | None, dict[str, Any], str]:
    url = f"https://www.googleapis.com/books/v1/volumes?q=isbn:{isbn}"
    status, data, err = _get_json(url)
    raw: dict[str, Any] = {"google_books_url": url, "google_books_status": status}
    if data is not None and settings.DEBUG:
        raw["google_books_preview"] = _truncate_for_raw(data)
    if not data or not isinstance(data.get("items"), list) or not data["items"]:
        msg = err or (data.get("error", {}).get("message") if isinstance(data, dict) else "") or "no items"
        raw["error"] = msg
        logger.info("book_metadata Google Books: no volume (%s)", msg)
        return None, raw, str(msg)

    info = data["items"][0].get("volumeInfo") or {}
    title = (info.get("title") or "").strip()
    subtitle = (info.get("subtitle") or "").strip()
    if subtitle and title:
        title = f"{title}: {subtitle}"
    elif subtitle:
        title = subtitle
    authors = [a.strip() for a in (info.get("authors") or []) if isinstance(a, str) and a.strip()]
    publisher = (info.get("publisher") or "").strip()
    year = _parse_year(info.get("publishedDate"))
    desc = (info.get("description") or "").strip()
    try:
        page_count = int(info["pageCount"]) if info.get("pageCount") is not None else None
    except (TypeError, ValueError):
        page_count = None

    norm = {
        "isbn": isbn,
        "title": title,
        "source_title": title,
        "authors": authors,
        "author": ", ".join(authors) if authors else "",
        "publisher": publisher,
        "year": year,
        "description": desc,
        "edition": "",
        "number_of_pages": page_count,
    }
    logger.info(
        "book_metadata Google Books normalized: title_found=%s author_found=%s",
        bool(title.strip()),
        bool(norm["author"]),
    )
    return norm, raw, ""


def _merge_enrich(
    ol: dict[str, Any] | None,
    gb: dict[str, Any] | None,
    isbn: str,
    raw_parts: dict[str, Any],
) -> dict[str, Any]:
    """Pick best base record, then fill missing fields from Google Books."""
    base_source = "none"
    base: dict[str, Any] | None = None
    if ol and (ol.get("title") or "").strip():
        base = dict(ol)
        base_source = "open_library"
    elif gb and (gb.get("title") or "").strip():
        base = dict(gb)
        base_source = "google_books"

    if base is None:
        base = {
            "isbn": isbn,
            "title": "",
            "source_title": "",
            "authors": [],
            "author": "",
            "publisher": "",
            "year": "",
            "description": "",
            "edition": "",
            "number_of_pages": None,
        }

    if gb and base_source == "open_library":
        if not (base.get("author") or "").strip() and (gb.get("author") or "").strip():
            base["author"] = gb["author"]
            base["authors"] = list(gb.get("authors") or [])
        if not (base.get("publisher") or "").strip() and (gb.get("publisher") or "").strip():
            base["publisher"] = gb["publisher"]
        if not (base.get("year") or "").strip() and (gb.get("year") or "").strip():
            base["year"] = gb["year"]
        if not (base.get("description") or "").strip() and (gb.get("description") or "").strip():
            base["description"] = gb["description"]
        if base.get("number_of_pages") in (None, 0) and gb.get("number_of_pages"):
            base["number_of_pages"] = gb["number_of_pages"]

    title_ok = bool((base.get("title") or "").strip())
    err = ""
    if not title_ok:
        err = "No title found from Open Library or Google Books."

    merged_source = base_source

    out = {
        "isbn": isbn,
        "title": (base.get("title") or "").strip(),
        "source_title": (base.get("source_title") or base.get("title") or "").strip(),
        "authors": list(base.get("authors") or []),
        "author": (base.get("author") or "").strip(),
        "publisher": (base.get("publisher") or "").strip(),
        "year": (base.get("year") or "").strip(),
        "description": (base.get("description") or "").strip(),
        "edition": (base.get("edition") or "").strip(),
        "number_of_pages": base.get("number_of_pages"),
        "metadata_source": merged_source if title_ok else "none",
        "raw": _truncate_for_raw(raw_parts),
        "error": err,
    }
    logger.info(
        "book_metadata final: source=%s title=%r author=%r publisher=%r year=%r err=%r",
        out["metadata_source"],
        (out["title"] or "")[:80],
        (out["author"] or "")[:80],
        (out["publisher"] or "")[:40],
        out["year"],
        out["error"],
    )
    return out


def lookup_book_metadata_by_isbn(isbn: str) -> dict[str, Any]:
    """
    Normalised metadata for an ISBN (ISBN-13 preferred internally).

    Never raises: returns dict with `error` populated on total failure.
    """
    cleaned = clean_isbn(isbn)
    norm = normalise_isbn(cleaned) if cleaned else normalise_isbn(isbn) if isbn else ""
    if not norm:
        return {
            "isbn": cleaned or isbn or "",
            "title": "",
            "source_title": "",
            "authors": [],
            "author": "",
            "publisher": "",
            "year": "",
            "description": "",
            "edition": "",
            "number_of_pages": None,
            "metadata_source": "none",
            "raw": {},
            "error": "Invalid ISBN",
        }

    raw_parts: dict[str, Any] = {}
    ol_norm, ol_raw, ol_err = _fetch_open_library(norm)
    raw_parts["open_library"] = ol_raw
    gb_norm, gb_raw, gb_err = _fetch_google_books(norm)
    raw_parts["google_books"] = gb_raw

    merged = _merge_enrich(ol_norm, gb_norm, norm, raw_parts)
    if not (merged.get("title") or "").strip():
        parts: list[str] = []
        if (merged.get("error") or "").strip():
            parts.append(str(merged["error"]).strip())
        if ol_err and not ol_norm:
            parts.append(f"Open Library: {ol_err}")
        if gb_err and not gb_norm:
            parts.append(f"Google Books: {gb_err}")
        merged["error"] = " | ".join(parts) if parts else "No title found from Open Library or Google Books."

    return merged
