"""Multi-stage Evidence & Claim Verification Engine."""

from __future__ import annotations

import re
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.models import (
    Claim,
    ClaimEvidence,
    ClaimVerification,
    Contradiction,
    EvidenceChunk,
    Investigation,
    Source,
)
from app.evidence.claim_extractor import extract_claims_for_investigation
from app.evidence.contradiction import detect_contradictions
from app.evidence.quality_scorer import score_evidence_chunk
from app.schemas.evidence import VerificationStatus


def verify_investigation_evidence(db: Session, inv: Investigation) -> dict[str, int]:
    """Score all evidence chunks, extract atomic claims, detect contradictions, and verify claims."""
    sources = list(db.scalars(select(Source).where(Source.investigation_id == inv.investigation_id)).all())
    sources_by_id = {s.source_id: s for s in sources}
    chunks = list(db.scalars(select(EvidenceChunk).where(EvidenceChunk.investigation_id == inv.investigation_id)).all())

    # Count unique non-duplicate domains per source_type to reflect independent corroboration
    unique_origins = len({s.domain or s.canonical_url for s in sources if not s.is_duplicate})
    for chunk in chunks:
        src = sources_by_id.get(chunk.source_id)
        if not src:
            continue
        q_score, breakdown = score_evidence_chunk(
            chunk,
            src,
            topic=inv.topic,
            mode=inv.mode,
            independent_corroborators=max(1, min(4, unique_origins // 2)),
        )
        chunk.quality_score = q_score
        chunk.quality_breakdown_json = breakdown
        src.reliability_score = max(src.reliability_score, q_score)

    extract_claims_for_investigation(db, inv.investigation_id, inv.geography)
    contradictions = detect_contradictions(db, inv.investigation_id)

    contradicted_claim_ids: set[str] = set()
    for c in contradictions:
        contradicted_claim_ids.add(c.claim_a_id)
        if c.claim_b_id:
            contradicted_claim_ids.add(c.claim_b_id)

    claims = list(db.scalars(select(Claim).where(Claim.investigation_id == inv.investigation_id)).all())
    links = db.scalars(
        select(ClaimEvidence).where(ClaimEvidence.claim_id.in_([c.claim_id for c in claims]))
    ).all() if claims else []
    chunks_by_id = {ch.evidence_id: ch for ch in chunks}

    evd_ids_by_claim: dict[str, list[str]] = {}
    for lk in links:
        evd_ids_by_claim.setdefault(lk.claim_id, []).append(lk.evidence_id)

    db.query(ClaimVerification).filter_by(investigation_id=inv.investigation_id).delete()
    current_year = datetime.now(timezone.utc).year
    counts: dict[str, int] = {s.value: 0 for s in VerificationStatus}

    for claim in claims:
        evd_ids = evd_ids_by_claim.get(claim.claim_id, [])
        linked_chunks = [chunks_by_id[eid] for eid in evd_ids if eid in chunks_by_id]
        linked_sources = [sources_by_id[ch.source_id] for ch in linked_chunks if ch.source_id in sources_by_id]
        distinct_origins = len({s.domain or s.canonical_url for s in linked_sources if not s.is_duplicate})

        source_exists = bool(linked_sources)
        source_identity_clear = any(bool(s.publisher or s.author) for s in linked_sources)
        avg_quality = sum(ch.quality_score for ch in linked_chunks) / len(linked_chunks) if linked_chunks else 0.0
        has_contra = claim.claim_id in contradicted_claim_ids

        # Freshness check
        freshness_valid = True
        for s in linked_sources:
            if s.published_at:
                m = re.search(r"(19|20)\d{2}", s.published_at)
                if m and (current_year - int(m.group(0))) > 6 and claim.category in {"technical", "market", "financial"}:
                    freshness_valid = False

        # Passage entailment heuristic: check token overlap between claim and chunk
        claim_words = set(re.findall(r"[a-z0-9]{3,}", claim.claim_text.lower()))
        passage_match = 0.0
        if linked_chunks and claim_words:
            chunk_words = set(re.findall(r"[a-z0-9]{3,}", linked_chunks[0].content.lower()))
            passage_match = round(len(claim_words & chunk_words) / len(claim_words), 3)

        if has_contra:
            status = VerificationStatus.CONTRADICTED
        elif not freshness_valid:
            status = VerificationStatus.OUTDATED
        elif not linked_chunks or avg_quality < 0.40:
            status = VerificationStatus.UNVERIFIED
        elif distinct_origins >= 2 and avg_quality >= 0.60:
            status = VerificationStatus.CORROBORATED
        elif avg_quality >= 0.58 and passage_match >= 0.65:
            status = VerificationStatus.VERIFIED
        else:
            status = VerificationStatus.PARTIALLY_SUPPORTED

        claim.verification_status = status.value
        claim.confidence_score = round(min(0.96, avg_quality * (0.75 if has_contra else 1.0)), 3)
        counts[status.value] = counts.get(status.value, 0) + 1

        db.add(
            ClaimVerification(
                investigation_id=inv.investigation_id,
                claim_id=claim.claim_id,
                source_exists=source_exists,
                source_identity_clear=source_identity_clear,
                passage_match_score=passage_match,
                independent_corroboration_count=distinct_origins,
                contradiction_found=has_contra,
                freshness_valid=freshness_valid,
                deterministic_check_passed=not has_contra,
                status=status.value,
                notes_json={
                    "avg_quality": round(avg_quality, 3),
                    "distinct_origins": distinct_origins,
                },
            )
        )

    db.flush()
    return {
        "total_sources": len(sources),
        "unique_sources": len([s for s in sources if not s.is_duplicate]),
        "total_chunks": len(chunks),
        "total_claims": len(claims),
        "contradictions": len(contradictions),
        **counts,
    }
