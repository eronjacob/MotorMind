"""
Harden AI-generated Mermaid for Mermaid v11: strip fences, normalize syntax,
validate, and fall back to a safe diagram so student pages never break.
"""

from __future__ import annotations

import re
from typing import Any

# Safe fallback (quoted labels, simple IDs) — used when validation fails.
MERMAID_FALLBACK_FLOWCHART = """flowchart TD
    A["Symptoms and fault codes"] --> B["Check wiring diagram"]
    B --> C["Identify shared fuse"]
    C --> D["Test fuse and circuit"]
    D --> E["Trace short circuit"]
    E --> F["Confirm faulty component"]
"""

_VALID_FIRST = re.compile(
    r"^\s*(flowchart|graph|sequenceDiagram|stateDiagram|classDiagram|erDiagram|gantt|pie)\b",
    re.IGNORECASE | re.MULTILINE,
)


def strip_markdown_fences(code: str) -> str:
    s = (code or "").replace("\r\n", "\n").strip()
    s = re.sub(r"^\s*```mermaid\s*\n?", "", s, flags=re.IGNORECASE)
    s = re.sub(r"^\s*```\s*\n?", "", s)
    s = re.sub(r"\n```\s*$", "", s)
    return s.strip()


def _first_substantive_line(s: str) -> str:
    for line in s.split("\n"):
        t = line.strip()
        if not t or t.startswith("%%"):
            continue
        return t
    return ""


def _mermaid_structure_valid(s: str) -> bool:
    if not s.strip():
        return False
    if "```" in s:
        return False
    first = _first_substantive_line(s)
    if not first or not _VALID_FIRST.match(first):
        return False
    return True


def _sanitize_label_text(inner: str) -> str:
    """Normalize text for inside quoted Mermaid labels (do not mangle quotes)."""
    t = inner.strip().replace("&", " and ").replace("~", " ")
    t = re.sub(r"\s+", " ", t).strip()
    return t[:220]


def _quote_rect_nodes(s: str) -> str:
    def rect(m: re.Match[str]) -> str:
        nid, inner = m.group(1), m.group(2)
        inner_st = inner.strip()
        if inner_st.startswith('"') and inner_st.endswith('"'):
            return m.group(0)
        esc = _sanitize_label_text(inner)
        if not esc:
            esc = "…"
        return f'{nid}["{esc}"]'

    return re.sub(
        r"([A-Za-z_][A-Za-z0-9_]*)\[([^\]\n]+)\]",
        rect,
        s,
    )


def _quote_diamond_nodes(s: str) -> str:
    def dia(m: re.Match[str]) -> str:
        nid, inner = m.group(1), m.group(2)
        inner_st = inner.strip()
        if inner_st.startswith('"') and inner_st.endswith('"'):
            return m.group(0)
        esc = _sanitize_label_text(inner)
        if not esc:
            esc = "?"
        return f'{nid}{{"{esc}"}}'

    return re.sub(
        r"([A-Za-z_][A-Za-z0-9_]*)\{([^}\n]+)\}",
        dia,
        s,
    )


def _edges_to_quoted_middle(s: str) -> str:
    # A -->|label| B  ->  A -- "label" --> B
    edge_arrow = re.compile(
        r"(?P<l>[A-Za-z_][A-Za-z0-9_]*)\s*-->\s*\|(?P<t>[^\|\n]+)\|\s*(?P<r>[A-Za-z_][A-Za-z0-9_]*)"
    )

    def ea(m: re.Match[str]) -> str:
        t = _sanitize_label_text(m.group("t"))
        t = t.replace('"', "'")
        return f'{m.group("l")} -- "{t}" --> {m.group("r")}'

    s = edge_arrow.sub(ea, s)

    # A -- label --> B (legacy) -> A -- "label" --> B
    edge_mid = re.compile(
        r"(?P<l>[A-Za-z_][A-Za-z0-9_]*)\s+--\s+(?P<t>[^-\n]+?)\s+-->\s+(?P<r>[A-Za-z_][A-Za-z0-9_]*)"
    )

    def em(m: re.Match[str]) -> str:
        raw_t = m.group("t").strip().strip('"').strip("'")
        t = _sanitize_label_text(raw_t)
        t = t.replace('"', "'")
        return f'{m.group("l")} -- "{t}" --> {m.group("r")}'

    s = edge_mid.sub(em, s)
    return s


def _strip_trailing_semicolons(s: str) -> str:
    lines = []
    for line in s.split("\n"):
        t = line.rstrip()
        if t.endswith(";"):
            t = t[:-1].rstrip()
        lines.append(t)
    return "\n".join(lines)


def _rename_reserved_targets(s: str) -> str:
    # Bare target node "End" is problematic in some Mermaid builds.
    return re.sub(r"(-->\s*)End(\b)", r'\1O["Finish"]\2', s)


def prepare_mermaid_code(code: str) -> tuple[str, str | None]:
    """
    Return (safe_code, warning_message_or_none).
    If the diagram cannot be validated, code is replaced with MERMAID_FALLBACK_FLOWCHART.
    """
    raw = strip_markdown_fences(code or "")
    if not raw:
        return MERMAID_FALLBACK_FLOWCHART, "Empty Mermaid diagram replaced with a safe default."

    s = raw
    s = re.sub(r"^\s*graph(\s+)", r"flowchart\1", s, flags=re.IGNORECASE | re.MULTILINE)
    s = _edges_to_quoted_middle(s)
    s = _quote_rect_nodes(s)
    s = _quote_diamond_nodes(s)
    s = _edges_to_quoted_middle(s)
    s = _rename_reserved_targets(s)
    s = _strip_trailing_semicolons(s)
    s = s.strip()

    if not _mermaid_structure_valid(s):
        return (
            MERMAID_FALLBACK_FLOWCHART,
            "Mermaid diagram failed validation and was replaced with a safe default. Edit the diagrams JSON to refine.",
        )

    return s, None


def normalize_mermaid_diagram_code(code: str) -> str:
    """Backward-compatible: return only the safe code string."""
    safe, _w = prepare_mermaid_code(code)
    return safe


def normalize_diagrams_list(diagrams: Any) -> list[Any]:
    """Copy diagram dicts; each mermaid entry gets validated `code` and optional `mermaid_warning`."""
    if not isinstance(diagrams, list):
        return []
    out: list[Any] = []
    for d in diagrams:
        if isinstance(d, dict):
            entry = dict(d)
            if str(entry.get("type", "")).lower() == "mermaid" and entry.get("code"):
                safe, warn = prepare_mermaid_code(str(entry["code"]))
                entry["code"] = safe
                if warn:
                    entry["mermaid_warning"] = warn
                else:
                    entry.pop("mermaid_warning", None)
            out.append(entry)
        else:
            out.append(d)
    return out
