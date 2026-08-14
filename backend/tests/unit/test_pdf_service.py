"""Tests for app.services.pdf_service.strip_references (no PDF parsing needed)."""

from app.services.pdf_service import strip_references


def test_no_references_heading_keeps_all_pages():
    pages = [
        {"page_number": 1, "text": "Intro text."},
        {"page_number": 2, "text": "Conclusion text."},
    ]
    result = strip_references(pages)
    assert result == pages


def test_references_heading_truncates_page_and_drops_rest():
    pages = [
        {"page_number": 1, "text": "Body text before references."},
        {"page_number": 2, "text": "More body.\n\nReferences\n\n[1] Some citation."},
        {"page_number": 3, "text": "[2] Another citation."},
    ]
    result = strip_references(pages)
    assert len(result) == 2
    assert result[0] == pages[0]
    assert result[1]["page_number"] == 2
    assert result[1]["text"] == "More body."


def test_bibliography_heading_is_also_detected():
    pages = [{"page_number": 1, "text": "Content.\n\nBibliography\n\n[1] X."}]
    result = strip_references(pages)
    assert result == [{"page_number": 1, "text": "Content."}]


def test_markdown_heading_prefixed_references_is_detected():
    pages = [{"page_number": 1, "text": "Content.\n\n## References\n\n[1] X."}]
    result = strip_references(pages)
    assert result == [{"page_number": 1, "text": "Content."}]


def test_case_insensitive_heading_match():
    pages = [{"page_number": 1, "text": "Content.\n\nREFERENCES\n\n[1] X."}]
    result = strip_references(pages)
    assert result == [{"page_number": 1, "text": "Content."}]


def test_references_on_first_page_yields_single_truncated_page():
    pages = [
        {"page_number": 1, "text": "References\n\n[1] X."},
        {"page_number": 2, "text": "Should be dropped."},
    ]
    result = strip_references(pages)
    assert result == [{"page_number": 1, "text": ""}]
