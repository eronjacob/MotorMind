"""
ISBN-10 / ISBN-13 parsing, validation, and normalisation (no external deps).

Normalised form: ISBN-13 digits only (no hyphens), derived from valid ISBN-10 when needed.
"""

from __future__ import annotations

import re
from pathlib import Path


def clean_isbn(value: str) -> str:
    """Remove hyphens, spaces, and any non ISBN-10/13 characters except digits and trailing X."""
    if not value:
        return ""
    v = value.strip().upper()
    v = re.sub(r"[^0-9X]", "", v)
    return v


def is_valid_isbn10(isbn: str) -> bool:
    """Validate ISBN-10 check digit (last may be X representing 10)."""
    s = clean_isbn(isbn)
    if len(s) != 10:
        return False
    if not re.fullmatch(r"\d{9}[\dX]", s):
        return False
    total = 0
    for i, ch in enumerate(s, start=1):
        val = 10 if ch == "X" else int(ch)
        total += val * i
    return total % 11 == 0


def is_valid_isbn13(isbn: str) -> bool:
    """Validate ISBN-13 (EAN-13) check digit."""
    s = clean_isbn(isbn)
    if len(s) != 13 or not s.isdigit():
        return False
    if s[:3] not in ("978", "979"):
        # Still validate checksum for any 13-digit publisher prefix if present.
        pass
    digits = [int(c) for c in s]
    checksum = sum(d * (1 if i % 2 == 0 else 3) for i, d in enumerate(digits[:12]))
    check = (10 - (checksum % 10)) % 10
    return check == digits[12]


def _isbn10_to_isbn13(isbn10: str) -> str:
    """Convert a valid ISBN-10 body to ISBN-13 with 978 prefix."""
    s = clean_isbn(isbn10)
    if len(s) != 10:
        raise ValueError("ISBN-10 must be 10 characters")
    core = "978" + s[:9]
    digits = [int(c) for c in core]
    checksum = sum(d * (1 if i % 2 == 0 else 3) for i, d in enumerate(digits))
    check = (10 - (checksum % 10)) % 10
    return core + str(check)


def normalise_isbn(isbn: str) -> str:
    """
    Return ISBN-13 string with digits only (no hyphens).

    Accepts ISBN-10 or ISBN-13; invalid input returns empty string.
    """
    s = clean_isbn(isbn)
    if len(s) == 13 and s.isdigit() and is_valid_isbn13(s):
        return s
    if len(s) == 10 and is_valid_isbn10(s):
        return _isbn10_to_isbn13(s)
    return ""


def extract_isbn_from_filename(filename: str) -> str | None:
    """
    Extract a valid ISBN from a filename stem.

    Primary: strip extension, remove hyphens/spaces only, validate whole stem.
    Fallback: scan a digits+X-only compaction for embedded 13- or 10-digit ISBNs.
    """
    stem = Path(filename or "").stem
    if not stem:
        return None

    primary = re.sub(r"[\s\-]", "", stem)
    if re.fullmatch(r"\d{13}", primary) and is_valid_isbn13(primary):
        return primary
    p10 = primary.upper()
    if re.fullmatch(r"\d{9}[\dX]", p10) and is_valid_isbn10(p10):
        return _isbn10_to_isbn13(p10)

    compact = re.sub(r"[^0-9Xx]", "", stem).upper()
    for length, validator in ((13, is_valid_isbn13), (10, is_valid_isbn10)):
        for i in range(0, max(0, len(compact) - length + 1)):
            chunk = compact[i : i + length]
            if length == 13 and not re.fullmatch(r"\d{13}", chunk):
                continue
            if length == 10 and not re.fullmatch(r"\d{9}[\dX]", chunk):
                continue
            if validator(chunk):
                return normalise_isbn(chunk)
    return None
