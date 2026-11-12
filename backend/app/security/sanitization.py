"""HTML cleaning and prompt-injection detection for retrieved untrusted content."""

from __future__ import annotations

import re
from bs4 import BeautifulSoup

INJECTION_PATTERNS = [
    re.compile(r"ignore\s+(all\s+)?(previous|prior|above)\s+instructions", re.I),
    re.compile(r"disregard\s+(the\s+)?system\s+prompt", re.I),
    re.compile(r"you\s+are\s+now\s+(in\s+)?developer\s+mode", re.I),
    re.compile(r"reveal\s+(your\s+)?(api[_\s]?key|system\s+prompt|secret)", re.I),
    re.compile(r"</?untrusted_evidence>", re.I),
    re.compile(r"<\s*script\b", re.I),
]


def clean_html_to_text(html: str) -> str:
    """Strip scripts, styles, and navigation boilerplate from HTML pages."""
    soup = BeautifulSoup(html, "lxml")
    for tag in soup(["script", "style", "noscript", "iframe", "svg", "nav", "footer"]):
        tag.decompose()
    text = soup.get_text(separator="\n")
    lines = [re.sub(r"\s+", " ", line).strip() for line in text.splitlines()]
    return "\n".join(line for line in lines if line)


def detect_prompt_injection(text: str) -> list[str]:
    """Return matched prompt-injection heuristics found inside retrieved text."""
    findings: list[str] = []
    for pattern in INJECTION_PATTERNS:
        if pattern.search(text or ""):
            findings.append(pattern.pattern)
    return findings


def sanitize_retrieved_text(text: str) -> tuple[str, bool]:
    """Neutralize delimiter breakouts and flag prompt-injection patterns."""
    cleaned = (text or "").replace("</untrusted_evidence>", "[/untrusted_evidence]")
    cleaned = cleaned.replace("<untrusted_evidence>", "[untrusted_evidence]")
    cleaned = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", cleaned)
    flagged = bool(detect_prompt_injection(cleaned))
    return cleaned.strip(), flagged


def wrap_untrusted_evidence(evidence_id: str, source_title: str, content: str) -> str:
    """Wrap external passage so models strictly treat it as untrusted data, never instructions."""
    safe_content, _ = sanitize_retrieved_text(content)
    return (
        f'<untrusted_evidence id="{evidence_id}" source="{source_title}">\n'
        f"{safe_content}\n"
        f"</untrusted_evidence>"
    )
