"""Research sources, evidence passages, atomic claims, contradictions, and document upload routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database.models import (
    Claim,
    ClaimEvidence,
    ClaimVerification,
    Contradiction,
    EvidenceChunk,
    Investigation,
    ResearchQuestion,
    ResearchTask,
    Source,
)
from app.database.repository import log_audit_event
from app.database.session import get_db
from app.evidence.verifier import verify_investigation_evidence
from app.research.collector import ingest_uploaded_document
from app.schemas.evidence import (
    ClaimOut,
    ContradictionOut,
    EvidenceChunkOut,
    QualityRubricBreakdown,
    VerificationStatus,
)
from app.schemas.research import ResearchQuestionOut, ResearchTaskOut, SourceOut
from app.security.validation import validate_upload_filename

router = APIRouter(prefix="/api/investigations/{investigation_id}", tags=["research"])


def _require_inv(db: Session, investigation_id: str) -> Investigation:
    inv = db.get(Investigation, investigation_id)
    if inv is None:
        raise HTTPException(status_code=404, detail="Investigation not found")
    return inv


@router.get("/questions", response_model=list[ResearchQuestionOut])
def list_questions(investigation_id: str, db: Session = Depends(get_db)):
    _require_inv(db, investigation_id)
    rows = db.scalars(select(ResearchQuestion).where(ResearchQuestion.investigation_id == investigation_id)).all()
    return [
        ResearchQuestionOut(
            question_id=r.question_id,
            investigation_id=r.investigation_id,
            query_family=r.query_family,
            question=r.question,
            search_query=r.search_query,
            connector=r.connector,
            priority=r.priority,
            assigned_advisors=r.assigned_advisors_json or [],
        )
        for r in rows
    ]


@router.get("/tasks", response_model=list[ResearchTaskOut])
def list_tasks(investigation_id: str, db: Session = Depends(get_db)):
    _require_inv(db, investigation_id)
    rows = db.scalars(select(ResearchTask).where(ResearchTask.investigation_id == investigation_id)).all()
    return [
        ResearchTaskOut(
            task_id=r.task_id,
            investigation_id=r.investigation_id,
            connector=r.connector,
            query=r.query,
            status=r.status,
            items_found=r.items_found,
            error_message=r.error_message,
            duration_ms=r.duration_ms,
            created_at=r.created_at,
        )
        for r in rows
    ]


@router.get("/sources", response_model=list[SourceOut])
def list_sources(investigation_id: str, db: Session = Depends(get_db)):
    _require_inv(db, investigation_id)
    rows = db.scalars(select(Source).where(Source.investigation_id == investigation_id)).all()
    return [
        SourceOut(
            source_id=s.source_id,
            investigation_id=s.investigation_id,
            url=s.url,
            canonical_url=s.canonical_url,
            title=s.title,
            publisher=s.publisher,
            author=s.author,
            published_at=s.published_at,
            retrieved_at=s.retrieved_at,
            source_type=s.source_type,
            domain=s.domain,
            canonical_identifier=s.canonical_identifier,
            license_name=s.license_name,
            content_hash=s.content_hash,
            is_duplicate=s.is_duplicate,
            syndicated_from_id=s.syndicated_from_id,
            reliability_score=s.reliability_score,
            metadata_json=s.metadata_json or {},
        )
        for s in rows
    ]


@router.get("/evidence", response_model=list[EvidenceChunkOut])
def list_evidence(investigation_id: str, q: str = "", db: Session = Depends(get_db)):
    _require_inv(db, investigation_id)
    sources = {
        s.source_id: s
        for s in db.scalars(select(Source).where(Source.investigation_id == investigation_id)).all()
    }
    chunks = db.scalars(select(EvidenceChunk).where(EvidenceChunk.investigation_id == investigation_id)).all()
    needle = q.strip().lower()
    out: list[EvidenceChunkOut] = []
    for ch in chunks:
        src = sources.get(ch.source_id)
        if needle and needle not in ch.content.lower() and (not src or needle not in src.title.lower()):
            continue
        out.append(
            EvidenceChunkOut(
                evidence_id=ch.evidence_id.replace(f"{investigation_id}-", ""),
                investigation_id=ch.investigation_id,
                source_id=ch.source_id,
                source_title=src.title if src else "",
                source_url=src.url if src else "",
                source_type=src.source_type if src else "",
                content=ch.content,
                section=ch.section,
                page=ch.page,
                paragraph_index=ch.paragraph_index,
                content_hash=ch.content_hash,
                quality_score=ch.quality_score,
                quality_breakdown=QualityRubricBreakdown.model_validate(ch.quality_breakdown_json or {}),
                prompt_injection_flagged=ch.prompt_injection_flagged,
                limitations=ch.limitations_json or [],
            )
        )
    return out


@router.get("/claims", response_model=list[ClaimOut])
def list_claims(investigation_id: str, status: str = "", db: Session = Depends(get_db)):
    _require_inv(db, investigation_id)
    query = select(Claim).where(Claim.investigation_id == investigation_id)
    if status:
        query = query.where(Claim.verification_status == status.upper())
    claims = list(db.scalars(query).all())
    links = db.scalars(
        select(ClaimEvidence).where(ClaimEvidence.claim_id.in_([c.claim_id for c in claims]))
    ).all() if claims else []
    verifs = {
        v.claim_id: v
        for v in db.scalars(select(ClaimVerification).where(ClaimVerification.investigation_id == investigation_id)).all()
    }
    ev_map: dict[str, list[str]] = {}
    for lk in links:
        ev_map.setdefault(lk.claim_id, []).append(lk.evidence_id.replace(f"{investigation_id}-", ""))

    return [
        ClaimOut(
            claim_id=c.claim_id.replace(f"{investigation_id}-", ""),
            investigation_id=c.investigation_id,
            claim_text=c.claim_text,
            category=c.category,
            entity=c.entity,
            predicate=c.predicate,
            value_unit=c.value_unit,
            time_period=c.time_period,
            geographic_scope=c.geographic_scope,
            verification_status=VerificationStatus(c.verification_status),
            confidence_score=c.confidence_score,
            evidence_ids=ev_map.get(c.claim_id, []),
            verification_notes=(verifs[c.claim_id].notes_json if c.claim_id in verifs else {}),
        )
        for c in claims
    ]


@router.get("/contradictions", response_model=list[ContradictionOut])
def list_contradictions(investigation_id: str, db: Session = Depends(get_db)):
    _require_inv(db, investigation_id)
    rows = db.scalars(select(Contradiction).where(Contradiction.investigation_id == investigation_id)).all()
    return [
        ContradictionOut(
            contradiction_id=ct.contradiction_id.replace(f"{investigation_id}-", ""),
            investigation_id=ct.investigation_id,
            claim_a_id=ct.claim_a_id.replace(f"{investigation_id}-", ""),
            claim_b_id=ct.claim_b_id.replace(f"{investigation_id}-", "") if ct.claim_b_id else None,
            evidence_a_id=ct.evidence_a_id.replace(f"{investigation_id}-", "") if ct.evidence_a_id else None,
            evidence_b_id=ct.evidence_b_id.replace(f"{investigation_id}-", "") if ct.evidence_b_id else None,
            summary=ct.summary,
            severity=ct.severity,
            resolved=ct.resolved,
        )
        for ct in rows
    ]


@router.post("/upload")
async def upload_document(
    investigation_id: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    inv = _require_inv(db, investigation_id)
    settings = get_settings()
    raw_bytes = await file.read()
    try:
        safe_name = validate_upload_filename(file.filename or "document.txt", len(raw_bytes), settings.max_upload_bytes)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    src, chunks = ingest_uploaded_document(db, investigation_id, safe_name, raw_bytes)
    stats = verify_investigation_evidence(db, inv)
    log_audit_event(
        db,
        investigation_id=investigation_id,
        actor="user",
        event_type="DOCUMENT_UPLOADED",
        stage=inv.current_stage,
        summary=f"Uploaded '{safe_name}' -> {len(chunks)} evidence chunks.",
    )
    db.commit()
    return {"source_id": src.source_id, "filename": safe_name, "chunks_created": len(chunks), "verification": stats}
