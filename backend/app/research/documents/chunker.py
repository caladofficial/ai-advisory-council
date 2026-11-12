"""Context-preserving passage chunker creating traceable EVD-001 evidence records."""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.research.deduplicator import compute_content_hash
from app.security.sanitization import sanitize_retrieved_text


@dataclass
class PassageChunk:
    section: str
    page: int | None
    paragraph_index: int
    content: str
    content_hash: str
    prompt_injection_flagged: bool


def chunk_text_passages(
    text: str,
    *,
    section: str = "main",
    page: int | None = None,
    max_chars: int = 900,
    min_chars: int = 80,
) -> list[PassageChunk]:
    """Split text along paragraph boundaries while preserving surrounding context."""
    cleaned, _ = sanitize_retrieved_text(text)
    if not cleaned:
        return []

    paragraphs = [p.strip() for p in re.split(r"\n{2,}", cleaned) if p.strip()]
    if len(paragraphs) <= 1 and len(cleaned) > max_chars:
        sentences = re.split(r"(?<=[.!?])\s+", cleaned)
        paragraphs = sentences

    chunks: list[PassageChunk] = []
    buf: list[str] = []
    buf_len = 0
    idx = 0

    for para in paragraphs:
        if buf_len + len(para) > max_chars and buf:
            combined = "\n".join(buf)
            safe_combined, flagged = sanitize_retrieved_text(combined)
            chunks.append(
                PassageChunk(
                    section=section,
                    page=page,
                    paragraph_index=idx,
                    content=safe_combined,
                    content_hash=compute_content_hash(safe_combined),
                    prompt_injection_flagged=flagged,
                )
            )
            idx += 1
            buf = [para]
            buf_len = len(para)
        else:
            buf.append(para)
            buf_len += len(para) + 1

    if buf:
        combined = "\n".join(buf)
        if len(combined) >= min_chars or not chunks:
            safe_combined, flagged = sanitize_retrieved_text(combined)
            chunks.append(
                PassageChunk(
                    section=section,
                    page=page,
                    paragraph_index=idx,
                    content=safe_combined,
                    content_hash=compute_content_hash(safe_combined),
                    prompt_injection_flagged=flagged,
                )
            )
        elif chunks:
            # Merge trailing tiny fragment into prior chunk so claims never lose context
            prev = chunks[-1]
            merged, flagged = sanitize_retrieved_text(f"{prev.content}\n{combined}")
            chunks[-1] = PassageChunk(
                section=prev.section,
                page=prev.page,
                paragraph_index=prev.paragraph_index,
                content=merged,
                content_hash=compute_content_hash(merged),
                prompt_injection_flagged=prev.prompt_injection_flagged or flagged,
            )
    return chunks
