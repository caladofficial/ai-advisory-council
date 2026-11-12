"""Parallel Research Collector orchestrating connectors, deduplication, and chunk persistence."""

from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable
from urllib.parse import urlparse

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database.models import EvidenceChunk, Investigation, ResearchQuestion, ResearchTask, Source
from app.research.crawlers.arxiv import search_arxiv
from app.research.crawlers.base import RawSourceRecord
from app.research.crawlers.crossref import search_crossref
from app.research.crawlers.github import search_github
from app.research.crawlers.huggingface import search_huggingface
from app.research.crawlers.openalex import search_openalex
from app.research.crawlers.web import search_web
from app.research.crawlers.wikipedia import search_wikipedia
from app.research.deduplicator import DeduplicationIndex, canonicalize_url, compute_content_hash
from app.research.documents.chunker import chunk_text_passages
from app.research.documents.parser import parse_document_bytes

ConnectorFn = Callable[[str, int], Awaitable[list[RawSourceRecord]]]

CONNECTOR_REGISTRY: dict[str, ConnectorFn] = {
    "openalex": search_openalex,
    "crossref": search_crossref,
    "arxiv": search_arxiv,
    "github": search_github,
    "huggingface": search_huggingface,
    "wikipedia": search_wikipedia,
    "web_search": search_web,
}


async def _execute_connector(connector: str, query: str) -> tuple[str, str, list[RawSourceRecord], int, str | None]:
    fn = CONNECTOR_REGISTRY.get(connector, search_web)
    t0 = time.perf_counter()
    try:
        items = await fn(query, 4)
        return connector, query, items, int((time.perf_counter() - t0) * 1000), None
    except Exception as exc:
        return connector, query, [], int((time.perf_counter() - t0) * 1000), str(exc)[:300]


def persist_raw_records(
    db: Session,
    investigation_id: str,
    records: list[RawSourceRecord],
) -> tuple[list[Source], list[EvidenceChunk]]:
    """Deduplicate, store Source records, and create EvidenceChunk passages."""
    existing_sources = list(
        db.scalars(select(Source).where(Source.investigation_id == investigation_id)).all()
    )
    dedup = DeduplicationIndex()
    for s in existing_sources:
        dedup.check_and_register(
            s.source_id,
            canonical_url=s.canonical_url,
            canonical_identifier=s.canonical_identifier,
            content_hash=s.content_hash,
            text=s.raw_excerpt,
        )

    src_seq = len(existing_sources)
    evd_seq = db.scalar(
        select(func.count(EvidenceChunk.evidence_id)).where(EvidenceChunk.investigation_id == investigation_id)
    ) or 0

    new_sources: list[Source] = []
    new_chunks: list[EvidenceChunk] = []

    for rec in records:
        canon_url = canonicalize_url(rec.url)
        c_hash = compute_content_hash(rec.content)
        src_seq += 1
        source_id = f"{investigation_id}-SRC-{src_seq:03d}"

        is_dup, orig_id = dedup.check_and_register(
            source_id,
            canonical_url=canon_url,
            canonical_identifier=rec.canonical_identifier,
            content_hash=c_hash,
            text=rec.content,
        )

        domain = urlparse(canon_url).netloc if canon_url.startswith("http") else rec.publisher
        src = Source(
            source_id=source_id,
            investigation_id=investigation_id,
            url=rec.url,
            canonical_url=canon_url or rec.url,
            title=rec.title[:500],
            publisher=rec.publisher[:256],
            author=rec.author[:256],
            published_at=rec.published_at,
            source_type=rec.source_type,
            domain=domain[:256],
            canonical_identifier=rec.canonical_identifier,
            license_name=rec.license_name,
            content_hash=c_hash,
            raw_excerpt=rec.content[:4000],
            is_duplicate=is_dup,
            syndicated_from_id=orig_id,
            metadata_json=rec.metadata,
        )
        db.add(src)
        db.flush()
        new_sources.append(src)

        if is_dup:
            # Keep duplicate Source provenance visible, but do not inflate evidence chunks with syndications!
            continue

        limitations = list((rec.metadata or {}).get("limitations", []))
        for chunk in chunk_text_passages(rec.content):
            evd_seq += 1
            evd_id = f"EVD-{evd_seq:03d}"
            evd = EvidenceChunk(
                evidence_id=f"{investigation_id}-{evd_id}",
                investigation_id=investigation_id,
                source_id=source_id,
                content=chunk.content,
                section=chunk.section,
                page=chunk.page,
                paragraph_index=chunk.paragraph_index,
                content_hash=chunk.content_hash,
                prompt_injection_flagged=chunk.prompt_injection_flagged,
                limitations_json=limitations,
            )
            db.add(evd)
            new_chunks.append(evd)

    db.flush()
    return new_sources, new_chunks


async def run_research_collection(
    db: Session,
    inv: Investigation,
    questions: list[ResearchQuestion],
    extra_queries: list[tuple[str, str]] | None = None,
) -> dict[str, int]:
    """Run all planned research connector tasks in parallel and persist evidence."""
    jobs: list[tuple[str, str]] = [(q.connector, q.search_query) for q in questions]
    if extra_queries:
        jobs.extend(extra_queries)

    # Deduplicate identical (connector, query) pairs
    seen_jobs: set[tuple[str, str]] = set()
    unique_jobs: list[tuple[str, str]] = []
    for conn, q in jobs:
        key = (conn, q.strip().lower())
        if key not in seen_jobs and q.strip():
            seen_jobs.add(key)
            unique_jobs.append((conn, q.strip()))

    results = await asyncio.gather(*[_execute_connector(c, q) for c, q in unique_jobs])

    existing_task_count = db.scalar(
        select(func.count(ResearchTask.task_id)).where(ResearchTask.investigation_id == inv.investigation_id)
    ) or 0

    all_records: list[RawSourceRecord] = []
    tasks_completed = 0
    tasks_failed = 0
    for idx, (conn, query, items, dur_ms, err) in enumerate(results, start=1):
        status = "FAILED" if err else "COMPLETED"
        if err:
            tasks_failed += 1
        else:
            tasks_completed += 1
            all_records.extend(items)
        task = ResearchTask(
            task_id=f"{inv.investigation_id}-TSK-{existing_task_count + idx:03d}",
            investigation_id=inv.investigation_id,
            connector=conn,
            query=query,
            status=status,
            items_found=len(items),
            error_message=err,
            duration_ms=dur_ms,
        )
        db.add(task)

    new_sources, new_chunks = persist_raw_records(db, inv.investigation_id, all_records)
    return {
        "tasks_completed": tasks_completed,
        "tasks_failed": tasks_failed,
        "sources_added": len(new_sources),
        "evidence_chunks_added": len(new_chunks),
    }


def ingest_uploaded_document(
    db: Session,
    investigation_id: str,
    filename: str,
    raw_bytes: bytes,
) -> tuple[Source, list[EvidenceChunk]]:
    """Parse and persist a user-uploaded document into the shared Evidence Knowledge Base."""
    sections = parse_document_bytes(filename, raw_bytes)
    full_text = "\n\n".join(f"[{s.section}]\n{s.text}" for s in sections)
    rec = RawSourceRecord(
        url=f"upload://{filename}",
        title=f"Uploaded Document: {filename}",
        source_type="upload",
        content=full_text,
        publisher="User Upload",
        canonical_identifier=f"upload:{compute_content_hash(full_text)[:16]}",
        metadata={"filename": filename, "sections": len(sections)},
    )
    sources, _ = persist_raw_records(db, investigation_id, [rec])
    src = sources[0]

    # If sections had distinct page numbers, attach granular section/page chunks if none created yet
    existing_chunks = list(
        db.scalars(select(EvidenceChunk).where(EvidenceChunk.source_id == src.source_id)).all()
    )
    return src, existing_chunks
