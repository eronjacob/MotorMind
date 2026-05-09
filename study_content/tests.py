from django.test import SimpleTestCase

from study_content.citation_format import author_surname, chunk_hover_title
from study_content.mermaid_sanitize import (
    MERMAID_FALLBACK_FLOWCHART,
    normalize_diagrams_list,
    normalize_mermaid_diagram_code,
    prepare_mermaid_code,
)
from study_content.reading_citations import postprocess_reading_html


class CitationFormatTests(SimpleTestCase):
    def test_author_surname_natural_order(self):
        self.assertEqual(author_surname("Tom Denton"), "Denton")

    def test_author_surname_comma(self):
        self.assertEqual(author_surname("Denton, Tom"), "Denton")

    def test_chunk_hover_includes_section_and_page(self):
        class Fake:
            metadata = {"section_title": "Fuses and relays"}
            source_title = "Auto Systems"
            resource_title = ""
            author = "Tom Denton"
            page_number = 112

        tip = chunk_hover_title(Fake())
        self.assertIn("Auto Systems", tip)
        self.assertIn("Fuses", tip)
        self.assertIn("112", tip)

    def test_chunk_hover_chunk_index_when_no_page(self):
        class Fake:
            metadata = {}
            source_title = "Book"
            resource_title = ""
            author = "A Author"
            page_number = None
            chunk_index = 14

        tip = chunk_hover_title(Fake())
        self.assertIn("14", tip)


class MermaidSanitizeTests(SimpleTestCase):
    def test_graph_keyword_and_legacy_edge_becomes_quoted_middle(self):
        raw = "graph TD\n  A --> B\n  F -- Yes --> G\n  H -- No --> L\n"
        out = normalize_mermaid_diagram_code(raw)
        self.assertTrue(out.lower().startswith("flowchart"))
        self.assertIn('F -- "Yes" --> G', out)
        self.assertIn('H -- "No" --> L', out)
        self.assertNotRegex(out, r"\b--\s+Yes\s+-->")

    def test_arrow_edge_label_form(self):
        raw = "flowchart TD\nA -->|No| B\n"
        out = normalize_mermaid_diagram_code(raw)
        self.assertIn('A -- "No" --> B', out)

    def test_ampersand_sanitized_in_rectangle(self):
        raw = "flowchart LR\nK[Physically Inspect & Repair Fault]\n"
        out = normalize_mermaid_diagram_code(raw)
        self.assertIn("and", out)
        self.assertIn('K["', out)

    def test_rhombus_ampersand_and_end_target(self):
        raw = (
            "graph TD\n"
            "B{Scan Tool & Symptoms}\n"
            "L --> End;\n"
        )
        out = normalize_mermaid_diagram_code(raw)
        self.assertIn("and", out)
        self.assertIn('O["Finish"]', out)
        self.assertNotIn("L --> End", out)

    def test_strip_mermaid_fence(self):
        raw = "```mermaid\nflowchart TD\nA --> B\n```"
        out, w = prepare_mermaid_code(raw)
        self.assertNotIn("```", out)
        self.assertTrue(out.startswith("flowchart"))

    def test_invalid_root_falls_back(self):
        raw = "notmermaid\nA --> B\n"
        out, w = prepare_mermaid_code(raw)
        self.assertEqual(out.strip(), MERMAID_FALLBACK_FLOWCHART.strip())
        self.assertIsNotNone(w)

    def test_normalize_diagrams_list_wraps_mermaid(self):
        raw = [{"id": "d1", "type": "mermaid", "code": "graph TD\nA -- x --> B;\n"}]
        out = normalize_diagrams_list(raw)
        self.assertEqual(len(out), 1)
        self.assertIn("flowchart", out[0]["code"])
        self.assertIn('-- "x" -->', out[0]["code"])


class ReadingCitationsTests(SimpleTestCase):
    def test_postprocess_video_singleton(self):
        html = "<p>Video shows the fault.</p>"
        out = postprocess_reading_html(
            html,
            chunks=[],
            video_specs=[{"id": "V1", "label": "X, 0:00-0:30"}],
            valid_ids={"V1"},
        )
        self.assertIn("[V1]", out)
