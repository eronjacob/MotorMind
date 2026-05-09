"""
Create `Resource` rows from minimal upload input (file + courses + optional type).

ISBN + metadata lookup applies when `resource_type` is `book` (including PDF auto-default).
"""

from __future__ import annotations

from pathlib import Path

from django.core.exceptions import ValidationError

from resources.models import Resource
from resources.services.book_metadata import lookup_book_metadata_by_isbn
from resources.services.isbn import extract_isbn_from_filename, normalise_isbn

UPLOAD_ISBN_ERROR = (
    "Please rename the file to a valid ISBN, for example 9780415725774.pdf"
)
API_UPLOAD_ISBN_ERROR = (
    "Book PDF filenames must be valid ISBNs, for example 9780415725774.pdf"
)


def infer_resource_type(extension: str, explicit_type: str) -> str:
    """If explicit_type empty, infer from extension."""
    ext = (extension or "").lower()
    t = (explicit_type or "").strip()
    if t:
        return t
    if ext == ".pdf":
        return Resource.ResourceType.BOOK
    if ext in (".txt", ".md", ".markdown", ".docx"):
        return Resource.ResourceType.NOTES
    return Resource.ResourceType.OTHER


def isbn_required_for(resource_type: str) -> bool:
    return resource_type == Resource.ResourceType.BOOK


def _parse_year_int(year_raw: str) -> int | None:
    if not year_raw:
        return None
    m = str(year_raw).strip()[:4]
    if m.isdigit():
        y = int(m)
        if 1000 <= y <= 2100:
            return y
    return None


def build_resource_from_minimal_upload(
    *,
    uploaded_file,
    original_filename: str,
    explicit_resource_type: str,
    user,
) -> Resource:
    """
    Construct an unsaved `Resource` with metadata populated from ISBN lookup when applicable.

    Raises ValidationError for invalid ISBN-on-book uploads.
    """
    name = original_filename or getattr(uploaded_file, "name", "") or ""
    ext = Path(name).suffix.lower()
    rt = infer_resource_type(ext, explicit_resource_type)

    if isbn_required_for(rt):
        extracted = extract_isbn_from_filename(name)
        norm = normalise_isbn(extracted) if extracted else ""
        if not norm:
            raise ValidationError(UPLOAD_ISBN_ERROR)

        meta = lookup_book_metadata_by_isbn(norm)
        raw_meta = dict(meta) if meta else {}
        title_present = bool((meta.get("title") or "").strip())
        if title_present:
            lookup_status = Resource.MetadataLookupStatus.SUCCESS
            lookup_err = ""
        else:
            lookup_status = Resource.MetadataLookupStatus.FAILED
            lookup_err = (meta.get("error") or "").strip() or (
                "Metadata lookup returned no title from Open Library or Google Books. "
                "You can edit details manually."
            )

        title = (meta.get("title") or "").strip() or norm
        source_title = (meta.get("source_title") or meta.get("title") or "").strip() or norm
        author = (meta.get("author") or "").strip()[:255]
        publisher = (meta.get("publisher") or "").strip()[:255]
        edition = (meta.get("edition") or "").strip()[:64]
        description = (meta.get("description") or "").strip()
        year = _parse_year_int(meta.get("year") or "")
        nop = meta.get("number_of_pages")
        try:
            number_of_pages = int(nop) if nop is not None else None
        except (TypeError, ValueError):
            number_of_pages = None

        return Resource(
            title=title[:255],
            resource_type=rt,
            original_filename=name,
            description=description,
            author=author,
            source_title=source_title[:255],
            edition=edition,
            publisher=publisher,
            year=year,
            number_of_pages=number_of_pages,
            uploaded_by=user if getattr(user, "is_authenticated", False) else None,
            status=Resource.Status.UPLOADED,
            isbn=norm,
            metadata_lookup_status=lookup_status,
            metadata_lookup_error=lookup_err,
            raw_metadata=raw_meta,
        )

    # Non-book uploads: filename becomes a provisional title; no ISBN / lookup.
    stem = Path(name).stem or "Untitled resource"
    return Resource(
        title=stem[:255],
        resource_type=rt,
        original_filename=name,
        description="",
        author="",
        source_title=stem[:255],
        edition="",
        publisher="",
        year=None,
        number_of_pages=None,
        uploaded_by=user if getattr(user, "is_authenticated", False) else None,
        status=Resource.Status.UPLOADED,
        isbn="",
        metadata_lookup_status=Resource.MetadataLookupStatus.NOT_REQUIRED,
        metadata_lookup_error="",
        raw_metadata={},
    )


def apply_metadata_lookup_to_resource(resource: Resource) -> None:
    """
    Refresh metadata from `resource.isbn` (used by management command).

    Mutates `resource` fields in-memory; caller should save().
    """
    isbn = (resource.isbn or "").strip()
    if not isbn:
        resource.metadata_lookup_status = Resource.MetadataLookupStatus.NOT_REQUIRED
        resource.metadata_lookup_error = ""
        resource.raw_metadata = {}
        return

    norm = normalise_isbn(isbn)
    if not norm:
        resource.metadata_lookup_status = Resource.MetadataLookupStatus.FAILED
        resource.metadata_lookup_error = "Stored ISBN is invalid; update it and retry."
        return

    meta = lookup_book_metadata_by_isbn(norm)
    resource.isbn = norm
    resource.raw_metadata = dict(meta) if meta else {}
    title_present = bool((meta.get("title") or "").strip())
    if title_present:
        resource.metadata_lookup_status = Resource.MetadataLookupStatus.SUCCESS
        resource.metadata_lookup_error = ""
        resource.title = ((meta.get("title") or "").strip() or resource.title)[:255]
        resource.source_title = (
            (meta.get("source_title") or meta.get("title") or "").strip() or resource.source_title
        )[:255]
        resource.author = (meta.get("author") or "").strip()[:255]
        resource.publisher = (meta.get("publisher") or "").strip()[:255]
        resource.edition = (meta.get("edition") or "").strip()[:64]
        resource.description = (meta.get("description") or "").strip()
        y = _parse_year_int(meta.get("year") or "")
        resource.year = y
        nop = meta.get("number_of_pages")
        try:
            resource.number_of_pages = int(nop) if nop is not None else None
        except (TypeError, ValueError):
            resource.number_of_pages = None
    else:
        resource.metadata_lookup_status = Resource.MetadataLookupStatus.FAILED
        resource.metadata_lookup_error = (meta.get("error") or "").strip() or (
            "Metadata lookup returned no title. You can edit details manually."
        )
