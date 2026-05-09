"""
Lightweight YouTube caption → readable prose (no LLM).

Joins short caption lines, removes common non-speech tokens, splits into
paragraphs using sentence boundaries, transition words, and length limits.
"""

from __future__ import annotations

import re
from typing import Any

# Inline / bracketed caption noise (case-insensitive where noted)
_NOISE_RE = re.compile(
    r"(?i)\[+\s*music\s*\]+|\(+music\)|\[\s*applause\s*\]|\[\s*crowd\s*\]|"
    r">>\s*\[+\s*music\s*\]+|>>\s*\(+music\)|♪+|♫+"
)

# Sentence split: period / question / exclamation followed by space + lookahead
_SENT_SPLIT_RE = re.compile(r"(?<=[.!?])\s+(?=\S)")

# New paragraph when a sentence starts with these (word boundary, case-insensitive)
_TRANSITION_RE = re.compile(
    r"^(Right|Okay|Ok|So|Now|Next|Then|Finally|First|Secondly|Third|"
    r"Therefore|However|Anyway|Well|Alright|All right)\b",
    re.IGNORECASE,
)

_PARA_MIN_CHARS = 500
_PARA_MAX_CHARS = 700
_TARGET_SENTENCES_PER_PARA = 4  # aim ~3–5


def split_transcript_paragraphs(text: str) -> list[str]:
    """
    Split transcript into paragraphs the same way readers see them: blank-line separated.

    Normalizes ``\\r\\n`` / ``\\r`` to ``\\n`` so counts match caption-derived timestamps
    (which assume ``\\n\\n`` between paragraphs).
    """
    if not (text or "").strip():
        return []
    t = (text or "").replace("\r\n", "\n").replace("\r", "\n")
    return [p.strip() for p in t.split("\n\n") if p.strip()]


def _normalize_whitespace(text: str) -> str:
    t = (text or "").replace("\r\n", "\n").replace("\r", "\n")
    t = _NOISE_RE.sub(" ", t)
    t = re.sub(r"[ \t]+", " ", t)
    t = re.sub(r"\n+", " ", t)
    return t.strip()


def _split_sentences(text: str) -> list[str]:
    """Rough sentence split on . ? ! followed by space."""
    t = text.strip()
    if not t:
        return []
    parts = _SENT_SPLIT_RE.split(t)
    if len(parts) == 1:
        return [parts[0].strip()] if parts[0].strip() else []
    out: list[str] = []
    for p in parts:
        p = p.strip()
        if p:
            out.append(p)
    return out


def _split_oversized_sentence(sentence: str, max_len: int) -> list[str]:
    """Hard-wrap very long sentences at word boundaries for paragraph limits."""
    if len(sentence) <= max_len:
        return [sentence]
    chunks: list[str] = []
    rest = sentence
    while len(rest) > max_len:
        cut = rest.rfind(" ", 0, max_len)
        if cut < max_len // 2:
            cut = max_len
        chunks.append(rest[:cut].strip())
        rest = rest[cut:].strip()
    if rest:
        chunks.append(rest)
    return chunks


def format_transcript_for_reading(raw_text: str) -> str:
    """
    Turn raw caption text into paragraphs separated by blank lines.

    Rules: normalize whitespace, strip music-style noise, join fragments,
    split on sentence punctuation, new paragraph every ~3–5 sentences or on
    transition words at sentence start, cap paragraph length ~500–700 chars.
    """
    text = _normalize_whitespace(raw_text)
    if not text:
        return ""

    sentences = _split_sentences(text)
    expanded: list[str] = []
    for s in sentences:
        expanded.extend(_split_oversized_sentence(s, _PARA_MAX_CHARS))

    paragraphs: list[str] = []
    buf: list[str] = []
    buf_len = 0

    def flush() -> None:
        nonlocal buf, buf_len
        if buf:
            paragraphs.append(" ".join(buf))
            buf = []
            buf_len = 0

    for sent in expanded:
        st = sent.strip()
        if not st:
            continue
        if _TRANSITION_RE.match(st) and buf:
            flush()
        buf.append(st)
        buf_len += len(st) + 1
        sent_count = len(buf)
        if sent_count >= _TARGET_SENTENCES_PER_PARA and buf_len >= _PARA_MIN_CHARS:
            flush()
        elif buf_len >= _PARA_MAX_CHARS:
            flush()

    flush()

    # Merge tiny tail paragraphs into previous
    if len(paragraphs) >= 2 and len(paragraphs[-1]) < 120:
        paragraphs[-2] = paragraphs[-2] + " " + paragraphs[-1]
        paragraphs.pop()

    return "\n\n".join(p for p in paragraphs if p.strip())


def _normalize_whitespace_with_times(text: str, times: list[float]) -> tuple[str, list[float]]:
    """
    Mirror `_normalize_whitespace` while keeping one timestamp per output character
    (timestamp = caption start of the contributing input character; min when merging).
    """
    if not text:
        return "", []
    if len(text) != len(times):
        return _normalize_whitespace(text), []

    chars = list(text)
    tms = list(times)
    i = 0
    nc: list[str] = []
    nt: list[float] = []
    while i < len(chars):
        if i + 1 < len(chars) and chars[i] == "\r" and chars[i + 1] == "\n":
            nc.append("\n")
            nt.append(min(tms[i], tms[i + 1]))
            i += 2
        elif chars[i] == "\r":
            nc.append("\n")
            nt.append(tms[i])
            i += 1
        else:
            nc.append(chars[i])
            nt.append(tms[i])
            i += 1

    s = "".join(nc)
    tm = nt
    out_c: list[str] = []
    out_t: list[float] = []
    pos = 0
    for m in _NOISE_RE.finditer(s):
        if m.start() > pos:
            for j in range(pos, m.start()):
                out_c.append(s[j])
                out_t.append(tm[j])
        if m.start() < m.end():
            out_c.append(" ")
            out_t.append(min(tm[m.start() : m.end()]))
        pos = m.end()
    if pos < len(s):
        for j in range(pos, len(s)):
            out_c.append(s[j])
            out_t.append(tm[j])

    def _re_collapse_chars(chars: list[str], tms: list[float], rx: re.Pattern) -> tuple[list[str], list[float]]:
        s2 = "".join(chars)
        out_ch: list[str] = []
        out_tm: list[float] = []
        pos2 = 0
        for m in rx.finditer(s2):
            if m.start() > pos2:
                for j in range(pos2, m.start()):
                    out_ch.append(s2[j])
                    out_tm.append(tms[j])
            if m.start() < m.end():
                out_ch.append(" ")
                out_tm.append(min(tms[m.start() : m.end()]))
            pos2 = m.end()
        if pos2 < len(s2):
            for j in range(pos2, len(s2)):
                out_ch.append(s2[j])
                out_tm.append(tms[j])
        return out_ch, out_tm

    fc, ft = _re_collapse_chars(out_c, out_t, re.compile(r"[ \t]+"))
    fc, ft = _re_collapse_chars(fc, ft, re.compile(r"\n+"))

    while fc and fc[0] in " \t\n":
        fc.pop(0)
        ft.pop(0)
    while fc and fc[-1] in " \t\n":
        fc.pop()
        ft.pop()
    return "".join(fc), ft


def _sentence_char_starts(norm: str, sentences: list[str]) -> list[int]:
    """Start index in `norm` of each stripped sentence from `_split_sentences`."""
    starts: list[int] = []
    pos = 0
    for s in sentences:
        st = s.strip()
        if not st:
            starts.append(min(pos, max(0, len(norm) - 1)))
            continue
        j = pos
        while j < len(norm) and norm[j].isspace():
            j += 1
        if j + len(st) <= len(norm) and norm[j : j + len(st)] == st:
            starts.append(j)
            pos = j + len(st)
        else:
            k = norm.find(st, j)
            if k < 0:
                k = j
            starts.append(k)
            pos = k + len(st)
    return starts


def _expanded_sentence_items(norm: str) -> list[tuple[str, int]]:
    """(sentence_chunk_text, char_index_in_norm_for_timing) in paragraphizer order."""
    sentences = _split_sentences(norm)
    if not sentences:
        return []
    starts = _sentence_char_starts(norm, sentences)
    out: list[tuple[str, int]] = []
    for si, s in enumerate(sentences):
        st = s.strip()
        if not st:
            continue
        sc = starts[si] if si < len(starts) else 0
        for chunk in _split_oversized_sentence(st, _PARA_MAX_CHARS):
            c = chunk.strip()
            if c:
                out.append((c, sc))
    return out


def _paragraphize_with_starts(
    norm: str, norm_times: list[float]
) -> tuple[list[str], list[int]]:
    """
    Same paragraph boundaries as `format_transcript_for_reading` on normalized text,
    plus integer start-second per paragraph from `norm_times` at first sentence char.
    """
    if not norm or len(norm) != len(norm_times):
        return [], []

    expanded = _expanded_sentence_items(norm)
    paragraphs: list[str] = []
    para_starts: list[int] = []
    buf: list[str] = []
    buf_start_chars: list[int] = []
    buf_len = 0

    def flush() -> None:
        nonlocal buf, buf_len, buf_start_chars
        if buf:
            paragraphs.append(" ".join(buf))
            ci = buf_start_chars[0]
            t0 = norm_times[ci] if 0 <= ci < len(norm_times) else 0.0
            para_starts.append(int(max(0, t0)))
            buf = []
            buf_len = 0
            buf_start_chars = []

    for text, char_idx in expanded:
        st = text.strip()
        if not st:
            continue
        if _TRANSITION_RE.match(st) and buf:
            flush()
        buf.append(st)
        buf_start_chars.append(char_idx)
        buf_len += len(st) + 1
        sent_count = len(buf)
        if sent_count >= _TARGET_SENTENCES_PER_PARA and buf_len >= _PARA_MIN_CHARS:
            flush()
        elif buf_len >= _PARA_MAX_CHARS:
            flush()

    flush()

    if len(paragraphs) >= 2 and len(paragraphs[-1]) < 120:
        paragraphs[-2] = paragraphs[-2] + " " + paragraphs[-1]
        paragraphs.pop()
        para_starts.pop()

    return paragraphs, para_starts


def format_transcript_segments_with_paragraph_starts(
    segments: list[dict[str, Any]],
) -> tuple[str, list[int]]:
    """
    Join timed caption segments, format into reading paragraphs, and return
    (transcript_text, start_seconds_per_paragraph) aligned with ``\\n\\n`` splits.

    When captions are missing, returns ("", []).
    """
    pieces: list[tuple[str, float]] = []
    for seg in segments or []:
        if not isinstance(seg, dict):
            continue
        t = (seg.get("text") or "").replace("\n", " ").strip()
        if not t:
            continue
        pieces.append((t, float(seg.get("start", 0.0))))
    if not pieces:
        return "", []

    joined_parts: list[str] = []
    char_times: list[float] = []
    for i, (tex, st) in enumerate(pieces):
        if i:
            joined_parts.append(" ")
            char_times.append(st)
        for _ch in tex:
            joined_parts.append(_ch)
            char_times.append(st)
    joined = "".join(joined_parts)
    norm, norm_times = _normalize_whitespace_with_times(joined, char_times)
    if not norm:
        return "", []
    paragraphs, para_starts = _paragraphize_with_starts(norm, norm_times)
    return "\n\n".join(paragraphs), para_starts


def format_transcript_segments(segments: list[dict[str, Any]]) -> str:
    """Join segment texts in order, then apply the same reading formatter as autofill."""
    text, _ = format_transcript_segments_with_paragraph_starts(segments)
    return text
