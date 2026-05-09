"""
Reading source lines, video [V#] segments, and HTML post-processing for AI readings.
"""

from __future__ import annotations

import re
from typing import Any

from courses.models import TrainingVideo

from study_content.models import CourseReadingSourceChunk


def _fmt_mmss(seconds: int) -> str:
    s = max(0, int(seconds))
    m, sec = divmod(s, 60)
    h, m = divmod(m, 60)
    if h:
        return f"{h:d}:{m:02d}:{sec:02d}"
    return f"{m:d}:{sec:02d}"


def _fmt_span(start_s: int, end_s: int) -> str:
    return f"{_fmt_mmss(start_s)}–{_fmt_mmss(end_s)}"


def book_source_display_line(chunk: CourseReadingSourceChunk) -> str:
    """One-line book source for Sources list and hover."""
    auth = (chunk.author or "").strip()
    title = (chunk.source_title or chunk.resource_title or "").strip()
    page = chunk.page_number
    idx = chunk.chunk_index
    if page is not None:
        parts = [p for p in (auth, title, f"p. {page}") if p]
        return ", ".join(parts) if parts else "Book excerpt"
    if idx is not None:
        from study_content.citation_format import author_surname

        sur = author_surname(auth or title or "Source")
        return f"{sur}, chunk {idx}"
    parts = [p for p in (auth, title) if p]
    return ", ".join(parts) if parts else "Book excerpt"


def build_video_citation_specs(
    video: TrainingVideo | None,
    *,
    max_refs: int = 12,
) -> list[dict[str, Any]]:
    """
    Build [V1], [V2], … from VideoSection rows, or from transcript paragraph timestamps.
    """
    if not video:
        return []
    sections = list(video.sections.order_by("start_seconds", "order", "pk"))
    out: list[dict[str, Any]] = []
    vtitle = (video.title or "Video").strip()
    if sections:
        for i, s in enumerate(sections[:max_refs], start=1):
            vid = f"V{i}"
            span = _fmt_span(int(s.start_seconds), int(s.end_seconds))
            label = f"{vtitle}, {span}"
            hover = f"{s.title} · {span} — {vtitle}"
            out.append(
                {
                    "id": vid,
                    "type": "video",
                    "label": label,
                    "section_title": s.title,
                    "video_title": vtitle,
                    "start_seconds": int(s.start_seconds),
                    "end_seconds": int(s.end_seconds),
                    "hover_title": hover,
                }
            )
        return out

    from courses.services.transcript_formatting import split_transcript_paragraphs

    paras = split_transcript_paragraphs(video.transcript or "")
    starts = video.transcript_paragraph_starts or []
    if not paras or not isinstance(starts, list) or len(starts) != len(paras):
        return [
            {
                "id": "V1",
                "type": "video",
                "label": f"{vtitle}, full video",
                "section_title": "Transcript",
                "video_title": vtitle,
                "start_seconds": 0,
                "end_seconds": 0,
                "hover_title": f"Transcript — {vtitle}",
            }
        ]
    n = min(len(paras), max_refs)
    for i in range(n):
        st = int(starts[i]) if i < len(starts) else 0
        if i + 1 < len(starts):
            en = max(st + 1, int(starts[i + 1]))
        else:
            en = st + 120
        vid = f"V{i + 1}"
        span = _fmt_span(st, en)
        label = f"{vtitle}, {span}"
        flat = paras[i].replace("\n", " ").strip()[:80]
        hover = f"{flat} · {span} — {vtitle}"
        out.append(
            {
                "id": vid,
                "type": "video",
                "label": label,
                "section_title": flat or f"Segment {i + 1}",
                "video_title": vtitle,
                "start_seconds": st,
                "end_seconds": en,
                "hover_title": hover,
            }
        )
    return out


def build_reading_citations_json(
    chunks: list[CourseReadingSourceChunk],
    video_specs: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Structured citations for storage and the Sources list."""
    from study_content.citation_format import author_surname, chunk_hover_title

    out: list[dict[str, Any]] = []
    for c in chunks:
        cid = (c.citation_label or "").strip() or f"B{len(out) + 1}"
        line = book_source_display_line(c)
        out.append(
            {
                "id": cid,
                "type": "book",
                "label": line,
                "surname": author_surname(c.author or ""),
                "hover_title": chunk_hover_title(c),
                "author": c.author or "",
                "source_title": (c.source_title or c.resource_title or "").strip(),
                "page_number": c.page_number,
                "chunk_index": c.chunk_index,
            }
        )
    for v in video_specs:
        out.append(
            {
                "id": v["id"],
                "type": "video",
                "label": v.get("label") or v.get("video_title") or "Video",
                "hover_title": v.get("hover_title") or "",
                "video_title": v.get("video_title") or "",
                "start_seconds": v.get("start_seconds"),
                "end_seconds": v.get("end_seconds"),
                "section_title": v.get("section_title") or "",
            }
        )
    return out


def dedupe_sources_display(citations: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[tuple[Any, ...]] = set()
    rows: list[dict[str, Any]] = []
    for c in citations:
        if not isinstance(c, dict):
            continue
        key = (
            c.get("type"),
            c.get("id"),
            c.get("label"),
            c.get("page_number"),
            c.get("start_seconds"),
            c.get("end_seconds"),
        )
        if key in seen:
            continue
        seen.add(key)
        rows.append(c)
    return rows


def replace_citation_labels_in_html(
    html_in: str,
    chunks: list[CourseReadingSourceChunk],
    video_specs: list[dict[str, Any]],
) -> str:
    """Replace [B#] and [V#] with <abbr> showing the bracket id and a rich title."""
    from study_content.citation_format import abbr_citation_html

    out = html_in or ""
    for c in chunks:
        label = (c.citation_label or "").strip()
        if not label:
            continue
        tip = book_source_display_line(c)
        rep = abbr_citation_html(label, tip, video=False, visible_brackets=True)
        pattern = re.compile(re.escape(f"[{label}]"), re.IGNORECASE)
        out = pattern.sub(rep, out)
    for v in video_specs:
        vid = (v.get("id") or "").strip()
        if not vid or not re.match(r"^V\d+$", vid, re.I):
            continue
        tip = (v.get("hover_title") or v.get("label") or "").strip()
        rep = abbr_citation_html(vid, tip, video=True, visible_brackets=True)
        pattern = re.compile(re.escape(f"[{vid}]"), re.IGNORECASE)
        out = pattern.sub(rep, out)
    return out


def postprocess_reading_html(
    html_in: str,
    *,
    chunks: list[CourseReadingSourceChunk],
    video_specs: list[dict[str, Any]],
    valid_ids: set[str],
) -> str:
    """
    Heal naked 'Video' / author surnames when unambiguous; drop unknown [Xy] markers.
    """
    from study_content.citation_format import author_surname

    out = html_in or ""
    norm_valid = {str(v).strip().upper() for v in valid_ids if v}

    if len(video_specs) == 1:
        v0 = str(video_specs[0].get("id", "V1")).strip()
        if v0.upper() in norm_valid:
            out = re.sub(r"\bVideo\b", f"[{v0}]", out, flags=re.IGNORECASE)

    surname_to_b: dict[str, str] = {}
    for c in chunks:
        lab = (c.citation_label or "").strip()
        if not lab:
            continue
        sur = author_surname(c.author or "")
        if sur and sur.lower() not in ("source", "video"):
            if sur.lower() not in surname_to_b:
                surname_to_b[sur.lower()] = lab

    if len(surname_to_b) == 1:
        only_sur, only_lab = next(iter(surname_to_b.items()))
        if only_lab.upper() in norm_valid:
            out = re.sub(
                r"\b" + re.escape(only_sur) + r"\b",
                f"[{only_lab}]",
                out,
                flags=re.IGNORECASE,
            )

    def _strip_bad_cite(m: re.Match[str]) -> str:
        inner = m.group(1).upper()
        if inner in norm_valid:
            return m.group(0)
        return ""

    out = re.sub(r"\[(B\d+|V\d+)\]", _strip_bad_cite, out, flags=re.I)
    return out


def append_sources_section_html(
    html_in: str,
    citations: list[dict[str, Any]],
) -> str:
    """Append a machine-readable sources block if the body has no 'Sources' heading yet."""
    import html as h

    if not citations:
        return html_in
    if re.search(r"<h[1-6][^>]*>\s*Sources\s*</h", html_in or "", re.I):
        return html_in
    lines = []
    for c in dedupe_sources_display(citations):
        cid = c.get("id") or "—"
        lab = (c.get("label") or "").strip()
        if not lab:
            continue
        lines.append(f"<li>[{h.escape(str(cid))}] {h.escape(lab)}.</li>")
    if not lines:
        return html_in
    block = (
        '<h2 class="h5 mt-4">Sources</h2><ul class="small reading-sources-appended">'
        + "".join(lines)
        + "</ul>"
    )
    return (html_in or "").rstrip() + "\n\n" + block
