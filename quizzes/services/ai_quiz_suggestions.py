"""
AI-generated multiple-choice question suggestions for the quiz editor.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any

from courses.models import Course, TrainingVideo, VideoSection

logger = logging.getLogger(__name__)

MIN_READING_CHUNKS_FOR_QUIZ_AI = 5


def get_quiz_ai_gate(course: Course) -> dict[str, Any]:
    """
    UI/API gate: quiz AI needs ≥1 linked training video and ≥5 saved reading chunks
    on the latest CourseReadingContext (from “Find top 5 chunks”).
    """
    video_count = course.videos.count()
    chunk_count = 0
    try:
        from study_content.models import CourseReadingContext

        ctx = CourseReadingContext.objects.filter(course=course).order_by("-pk").first()
        if ctx:
            chunk_count = ctx.source_chunks.count()
    except ImportError:
        chunk_count = 0

    ready = video_count >= 1 and chunk_count >= MIN_READING_CHUNKS_FOR_QUIZ_AI
    parts: list[str] = []
    if video_count < 1:
        parts.append("Link at least one training video to this course.")
    if chunk_count < MIN_READING_CHUNKS_FOR_QUIZ_AI:
        parts.append(
            f'In the course editor, open Reading and run “Find top 5 chunks” so at least '
            f"{MIN_READING_CHUNKS_FOR_QUIZ_AI} chunks are saved for the latest reading context."
        )
    message = " ".join(parts) if parts else ""
    return {
        "ready": ready,
        "video_count": video_count,
        "chunk_count": chunk_count,
        "message": message,
    }


def _video_transcript_paragraph_meta(video: TrainingVideo | None) -> str:
    """Prompt block: paragraph index → approximate jump time from caption alignment."""
    if not video:
        return ""
    from courses.services.transcript_formatting import split_transcript_paragraphs

    paras = split_transcript_paragraphs(video.transcript or "")
    starts = video.transcript_paragraph_starts or []
    if not paras or not isinstance(starts, list) or len(starts) != len(paras):
        return ""
    lines: list[str] = []
    for i, (p, st) in enumerate(zip(paras, starts)):
        snip = p.replace("\n", " ")[:160]
        try:
            sec = int(max(0, float(st)))
        except (TypeError, ValueError):
            sec = 0
        lines.append(f"- Paragraph {i + 1} starts at ~{sec}s in this video: {snip}")
    return "Transcript paragraph timing (seconds in this video; use for timestamp_seconds when relevant):\n" + "\n".join(
        lines
    )


def _sections_catalog_for_prompt(course: Course, video_id: int | None) -> tuple[str, set[int]]:
    qs = VideoSection.objects.filter(video__course_id=course.pk).select_related("video")
    if video_id:
        qs = qs.filter(video_id=video_id)
    ids: set[int] = set()
    lines: list[str] = []
    for s in qs.order_by("video_id", "order", "pk"):
        ids.add(s.pk)
        lines.append(
            f"- section_id={s.pk}: {s.title!r} on video {s.video.title!r} "
            f"({s.start_seconds}s–{s.end_seconds}s)"
        )
    if not lines:
        return "", ids
    return (
        "Video sections (set section_id to one of these integers when a question clearly belongs "
        "in that span; otherwise null):\n" + "\n".join(lines),
        ids,
    )


def _transcript_for_quiz(course: Course, video_id: int | None) -> str:
    if video_id:
        v = TrainingVideo.objects.filter(pk=video_id, course_id=course.pk).first()
        if v:
            return (v.transcript or "").strip()
    parts: list[str] = []
    for v in course.videos.order_by("pk"):
        t = (v.transcript or "").strip()
        if t:
            parts.append(t)
    return "\n\n".join(parts).strip()


def _resolve_question_count(mode: str, manual: int | None, transcript_len: int) -> int:
    if mode == "manual" and manual is not None:
        return max(1, min(20, int(manual)))
    # automatic: scale lightly with length, default band 5–10
    base = 5 + min(5, transcript_len // 4000)
    return max(5, min(10, base))


def _load_source_chunks(course: Course):
    """Return saved chunks for the latest reading context only (no auto-retrieval)."""
    try:
        from study_content.models import CourseReadingContext
    except ImportError:
        return []

    ctx = CourseReadingContext.objects.filter(course=course).order_by("-pk").first()
    if ctx and ctx.source_chunks.exists():
        return list(ctx.source_chunks.all())
    return []


def generate_quiz_question_suggestions(
    course: Course,
    *,
    video_id: int | None,
    question_count_mode: str,
    question_count: int | None,
) -> dict[str, Any]:
    """
    Return {"success": bool, "questions": [...], "error": str}.

    Uses transcript + saved reading source chunks on the latest context (≥5 required).
    """
    gate = get_quiz_ai_gate(course)
    if not gate["ready"]:
        return {
            "success": False,
            "questions": [],
            "error": gate["message"] or "Prerequisites for AI quiz suggestions are not met.",
        }

    api_key = (os.environ.get("GOOGLE_API_KEY") or "").strip()
    if not api_key:
        return {
            "success": False,
            "questions": [],
            "error": "AI suggestions are not configured. Set GOOGLE_API_KEY.",
        }

    transcript = _transcript_for_quiz(course, video_id)
    if not transcript.strip():
        return {
            "success": False,
            "questions": [],
            "error": "No video transcript available for this course. Add transcripts first.",
        }

    chunks = _load_source_chunks(course)
    if len(chunks) < MIN_READING_CHUNKS_FOR_QUIZ_AI:
        return {
            "success": False,
            "questions": [],
            "error": (
                f"Need at least {MIN_READING_CHUNKS_FOR_QUIZ_AI} saved reading chunks. "
                'Run “Find top 5 chunks” in the course Reading section, then try again.'
            ),
        }

    chunk_lines = []
    for c in chunks:
        chunk_lines.append(
            f"- [{c.citation_label}] {c.resource_title or c.source_title or 'Reading'} "
            f"(resource_id={c.resource_id or 'n/a'}): {_snippet(c.chunk_text, 900)}"
        )
    chunks_text = "\n".join(chunk_lines)

    n_q = _resolve_question_count(
        question_count_mode or "auto",
        question_count,
        len(transcript),
    )

    model_name = (os.environ.get("GOOGLE_MODEL_NAME") or "gemma-3-27b-it").strip()
    tr_snip = transcript[:14000]

    focus_video: TrainingVideo | None = None
    if video_id:
        focus_video = TrainingVideo.objects.filter(pk=video_id, course_id=course.pk).first()
    para_meta = _video_transcript_paragraph_meta(focus_video)
    sec_block, valid_section_ids = _sections_catalog_for_prompt(course, video_id)

    json_shape = (
        "Return STRICT JSON: {\"questions\":[{\"question_text\":...,\"explanation\":...,"
        "\"timestamp_seconds\":<non-negative integer seconds in the training video or null>,"
        "\"section_id\":<integer from the section catalog below or null>,"
        "\"answers\":[{\"answer_text\":...,\"is_correct\":true/false},...],"
        "\"source_refs\":[\"V1\",\"B2\"]}]}\n\n"
    )

    prompt = (
        "You write assessment items for an automotive electronics / diagnostics course. "
        f"Generate exactly {n_q} multiple-choice questions. "
        "Each question must test understanding and diagnostic reasoning, not trivia. "
        "Use ONLY the transcript excerpt and reading excerpts below. Do not invent facts. "
        "Prefer 4 answer options per question with exactly one correct answer. "
        "Include a concise explanation per question. "
        "Add source_refs as a list of citation ids like [\"V1\",\"B2\"] referencing transcript [V1] or book chunk labels [B1]..[B5]. "
        "When paragraph timing is provided, set timestamp_seconds to the best matching jump time. "
        "When sections are listed, set section_id only if the question clearly fits that span. "
        + json_shape
        + f"Transcript excerpt (cite as [V1]):\n{tr_snip}\n\n"
    )
    if para_meta:
        prompt += para_meta + "\n\n"
    if sec_block:
        prompt += sec_block + "\n\n"
    prompt += f"Reading excerpts:\n{chunks_text}\n"

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
        except Exception:
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
        logger.exception("Quiz AI suggestions failed")
        return {"success": False, "questions": [], "error": f"AI request failed: {exc}"}

    questions = data.get("questions") if isinstance(data, dict) else None
    if not isinstance(questions, list):
        return {"success": False, "questions": [], "error": "Invalid AI response shape."}

    cleaned: list[dict[str, Any]] = []
    for q in questions[:20]:
        if not isinstance(q, dict):
            continue
        qtext = (q.get("question_text") or "").strip()
        if not qtext:
            continue
        answers_in = q.get("answers") if isinstance(q.get("answers"), list) else []
        answers_out = []
        for a in answers_in[:6]:
            if not isinstance(a, dict):
                continue
            at = (a.get("answer_text") or "").strip()
            if not at:
                continue
            answers_out.append(
                {
                    "answer_text": at[:500],
                    "is_correct": bool(a.get("is_correct")),
                }
            )
        if len(answers_out) < 2:
            continue
        refs = q.get("source_refs")
        if not isinstance(refs, list):
            refs = []
        refs = [str(x).strip() for x in refs if str(x).strip()][:8]

        ts_val = None
        ts_raw = q.get("timestamp_seconds")
        if ts_raw is not None and str(ts_raw).strip() not in ("", "null", "None"):
            try:
                ts_val = int(float(ts_raw))
            except (TypeError, ValueError):
                ts_val = None
            if ts_val is not None:
                ts_val = max(0, min(ts_val, 86400 * 2))

        sec_id = None
        sec_raw = q.get("section_id")
        if sec_raw is not None and str(sec_raw).strip() not in ("", "null", "None"):
            try:
                cand = int(sec_raw)
            except (TypeError, ValueError):
                cand = None
            if cand is not None and cand in valid_section_ids:
                sec_id = cand

        cleaned.append(
            {
                "question_text": qtext,
                "explanation": (q.get("explanation") or "").strip(),
                "timestamp_seconds": ts_val,
                "section_id": sec_id,
                "answers": answers_out,
                "source_refs": refs,
            }
        )

    if not cleaned:
        return {
            "success": False,
            "questions": [],
            "error": "The model did not return usable questions.",
        }

    return {"success": True, "questions": cleaned, "error": ""}


def _snippet(text: str, limit: int) -> str:
    t = (text or "").replace("\n", " ").strip()
    return t[:limit] if len(t) > limit else t
