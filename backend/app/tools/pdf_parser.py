from __future__ import annotations

from pathlib import Path

from pypdf import PdfReader


def parse_pdf_report(path: Path) -> list[dict[str, object]]:
    """Return page-level text. Page numbers remain one-based for evidence links."""
    reader = PdfReader(str(path))
    pages: list[dict[str, object]] = []
    for number, page in enumerate(reader.pages, start=1):
        pages.append({"page_number": number, "text": page.extract_text() or ""})
    return pages

