"""Safe document parser for uploaded PDF, Markdown, TXT, CSV, and JSON files."""

from __future__ import annotations

import csv
import io
import json
from dataclasses import dataclass
from pathlib import Path

from pypdf import PdfReader


@dataclass
class ParsedSection:
    section: str
    page: int | None
    text: str


def parse_document_bytes(filename: str, raw_bytes: bytes) -> list[ParsedSection]:
    """Extract readable sections/pages from user-uploaded files safely without code execution."""
    ext = Path(filename).suffix.lower()
    if ext == ".pdf":
        reader = PdfReader(io.BytesIO(raw_bytes))
        sections: list[ParsedSection] = []
        for idx, page in enumerate(reader.pages, start=1):
            txt = (page.extract_text() or "").strip()
            if txt:
                sections.append(ParsedSection(section=f"Page {idx}", page=idx, text=txt))
        return sections or [ParsedSection(section="PDF", page=1, text="(No selectable text extracted from PDF)")]

    text = raw_bytes.decode("utf-8", errors="replace").strip()
    if ext == ".json":
        try:
            parsed = json.loads(text)
            text = json.dumps(parsed, indent=2, ensure_ascii=False)
        except Exception:
            pass
    elif ext == ".csv":
        try:
            reader = csv.reader(io.StringIO(text))
            rows = [", ".join(r) for r in list(reader)[:250]]
            text = "\n".join(rows)
        except Exception:
            pass

    return [ParsedSection(section="Document Body", page=None, text=text)]
