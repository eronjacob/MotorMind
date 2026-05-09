"""
AI generation for course Reading pages (Gemini / Google AI).
"""

from __future__ import annotations

import json
import logging
import os

from courses.models import Course, TrainingVideo
from study_content.mermaid_sanitize import normalize_diagrams_list
from study_content.models import CourseReadingContext, CourseReadingPage
from study_content.reading_citations import (
    build_reading_citations_json,
    build_video_citation_specs,
    postprocess_reading_html,
    replace_citation_labels_in_html,
)

logger = logging.getLogger(__name__)


def _snippet(text: str, limit: int = 3500) -> str:
    t = (text or "").strip()
    return t[:limit] if len(t) > limit else t


def _book_refs_text(chunks: list) -> str:
    lines = []
    for c in chunks:
        from study_content.reading_citations import book_source_display_line

        lab = (c.citation_label or "").strip()
        lines.append(
            f"- [{lab}] label={book_source_display_line(c)!r} "
            f"author={c.author!r} page_number={c.page_number!r} chunk_index={c.chunk_index!r}\n"
            f"  excerpt: {_snippet(c.chunk_text, 1200)!r}"
        )
    return "\n".join(lines)


def _video_refs_text(specs: list[dict]) -> str:
    if not specs:
        return "(No video timing segments — cite video only as [V1] if a single block is provided.)"
    import json as _json

    return _json.dumps(specs, indent=2)


def generate_course_reading(
    course: Course,
    context: CourseReadingContext,
    user=None,
) -> CourseReadingPage:
    """
    Build / update `CourseReadingPage` from course metadata, transcript, and saved chunks.

    Expects `context.source_chunks` to be populated (run retrieval first).
    """
    api_key = (os.environ.get("GOOGLE_API_KEY") or "").strip()
    if not api_key:
        raise ValueError(
            "Reading generation is not configured. Set GOOGLE_API_KEY."
        )

    model_name = (os.environ.get("GOOGLE_MODEL_NAME") or "gemma-3-27b-it").strip()

    chunks = list(context.source_chunks.select_related("resource", "video").all())
    if not chunks:
        raise ValueError(
            "No saved source chunks for this context. Run “Find top 5 chunks” first."
        )

    video = context.video or course.videos.order_by("created_at").first()
    if context.video:
        v_title = context.video.title
        transcript = _snippet(context.video.transcript or "")
    else:
        v_title = "Course videos (combined)"
        transcript = _snippet(context.query_text)

    video_specs = build_video_citation_specs(video)
    book_refs = _book_refs_text(chunks)
    video_refs = _video_refs_text(video_specs)

    prompt = (
        "You are an automotive / technical education author writing a BBC Bitesize-style reading. "
        "Use ONLY the transcript excerpt and the book/video source definitions below. "
        "Every factual claim must be cited using ONLY the bracket ids provided: [B1], [B2], … for books and "
        "[V1], [V2], … for video time segments. "
        "Never write naked author surnames (e.g. 'Denton') or the word 'Video' as a citation — always use [B#] or [V#]. "
        "Do not invent citation ids; use only ids listed below. "
        "Do not add a 'Sources' or 'References' section in content_html — the application renders Sources automatically. "
        "Include: a short introduction, main sections, a “Key takeaways” section, and a “Common mistakes” section. "
        "Include at least one Mermaid flowchart when it helps. "
        "Mermaid rules (must follow — invalid diagrams are discarded):\n"
        '- First line must be exactly: flowchart TD\n'
        "- Use only simple node ids: A, B, C, D, E, F, … (single letters or A1 style if needed).\n"
        '- Every node label must be double-quoted inside brackets or braces, e.g. A["Short label"] and D{"Question text"}.\n'
        '- Use only ASCII letters, spaces, commas, and periods inside labels; write "and" instead of "&".\n'
        '- For labeled edges use: A -- "Yes" --> B (never A -->|Yes| B).\n'
        "- Do not use semicolons at ends of lines. Do not use markdown ``` fences.\n"
        "- Do not use End, Done, or graph as a node id.\n"
        "In content_html, place each diagram using "
        '<div data-diagram-id=\"DIAGRAM_ID\" class=\"reading-diagram float-end\"></div> '
        "where DIAGRAM_ID matches an entry in the diagrams array. "
        "Return STRICT JSON only with this shape:\n"
        '{"title": string, "summary": string, "content_html": string, '
        '"diagrams": ['
        '{"id": string, "title": string, "type": "mermaid", "code": string, "caption": string}'
        "]}\n\n"
        f"Course title: {course.title}\n"
        f"Course description: {_snippet(course.description or '', 800)}\n\n"
        f"Video title for transcript: {v_title}\n"
        f"Transcript excerpt:\n{transcript}\n\n"
        f"BOOK source definitions (citation ids and labels — use [B#] in the text only):\n{book_refs}\n\n"
        f"VIDEO segment definitions (citation ids and labels — use [V#] in the text only):\n{video_refs}\n"
    )

    try:
        import google.generativeai as genai

        genai.configure(api_key=api_key)
        model = genai.GenerativeModel(model_name)
        try:
            from google.generativeai.types import GenerationConfig

            response = model.generate_content(
                prompt,
                generation_config=GenerationConfig(response_mime_type="application/json"),
            )
        except (ImportError, TypeError, ValueError):
            response = model.generate_content(prompt)
        raw_text = (getattr(response, "text", None) or "").strip()
        if not raw_text and getattr(response, "candidates", None):
            parts = []
            for c in response.candidates:
                for p in getattr(c, "content", None).parts or []:
                    if getattr(p, "text", None):
                        parts.append(p.text)
            raw_text = "\n".join(parts).strip()
        data = json.loads(raw_text)
    except Exception as exc:
        logger.exception("Reading generation failed")
        raise ValueError(f"AI reading generation failed: {exc}") from exc

    if not isinstance(data, dict):
        raise ValueError("Model returned invalid JSON root.")

    title = (data.get("title") or f"{course.title} reading")[:255]
    content_html = (data.get("content_html") or "").strip()
    diagrams = data.get("diagrams") if isinstance(data.get("diagrams"), list) else []
    diagrams = normalize_diagrams_list(diagrams)

    mermaid_warnings = [
        d["mermaid_warning"]
        for d in diagrams
        if isinstance(d, dict) and d.get("mermaid_warning")
    ]
    diagrams_for_storage: list = []
    for d in diagrams:
        if isinstance(d, dict):
            e = dict(d)
            e.pop("mermaid_warning", None)
            diagrams_for_storage.append(e)
        else:
            diagrams_for_storage.append(d)

    citations = build_reading_citations_json(chunks, video_specs)
    valid_ids = {str(c.get("id", "")).strip() for c in citations if c.get("id")}

    content_html = postprocess_reading_html(
        content_html,
        chunks=chunks,
        video_specs=video_specs,
        valid_ids=valid_ids,
    )
    content_html = replace_citation_labels_in_html(content_html, chunks, video_specs)

    page, _created = CourseReadingPage.objects.get_or_create(course=course)
    page.context = context
    page.title = title
    page.content_html = content_html
    page.citations = citations
    page.diagrams = diagrams_for_storage
    page.editor_json = {
        "summary": data.get("summary") or "",
        "generated": True,
        "mermaid_warnings": mermaid_warnings,
    }
    page.generated_by_model = model_name
    page.generated_from = {
        "context_id": context.pk,
        "chunk_ids": [c.pk for c in chunks],
        "video_id": video.pk if video else None,
    }
    page.is_teacher_edited = False
    page.save()
    return page
