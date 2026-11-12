"""Atomic claim extractor turning evidence passages into independently testable CLAIM-001 records."""

from __future__ import annotations

import re

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database.models import Claim, ClaimEvidence, EvidenceChunk, Source

CATEGORY_KEYWORDS: list[tuple[str, set[str]]] = [
    ("financial", {"cost", "price", "usd", "inr", "dollar", "rupee", "budget", "roi", "revenue", "margin", "fee", "free"}),
    ("security", {"security", "privacy", "vulnerability", "encrypt", "auth", "breach", "attack", "injection", "owasp"}),
    ("legal", {"law", "regulation", "compliance", "license", "mit", "apache", "gpl", "agpl", "gdpr", "dpdp", "policy"}),
    ("market", {"market", "adoption", "user", "customer", "demand", "competitor", "survey", "growth", "share"}),
    ("technical", {"model", "api", "architecture", "latency", "benchmark", "accuracy", "open", "github", "parameter", "gpu"}),
]

METRIC_RE = re.compile(r"(\$|₹|€|\b\d+(?:\.\d+)?%|\b\d+(?:,\d{3})+\b|\b\d+(?:\.\d+)?\s*(?:ms|s|GB|MB|K|M|B|RPM|RPD|users|papers)\b)", re.I)


def _classify_claim(sentence: str) -> str:
    tokens = set(re.findall(r"[a-z0-9]+", sentence.lower()))
    best_cat = "general"
    best_hits = 0
    for cat, kws in CATEGORY_KEYWORDS:
        hits = len(tokens & kws)
        if hits > best_hits:
            best_hits = hits
            best_cat = cat
    return best_cat


def _split_candidate_sentences(text: str) -> list[str]:
    cleaned = re.sub(r"\s+", " ", (text or "")).strip()
    parts = re.split(r"(?<=[.!?])\s+|\n+", cleaned)
    candidates: list[str] = []
    for p in parts:
        p = p.strip(" -•*\t")
        if 35 <= len(p) <= 320 and len(p.split()) >= 6:
            candidates.append(p)
    return candidates


def extract_claims_for_investigation(db: Session, investigation_id: str, geography: str) -> list[Claim]:
    """Extract atomic claims linked directly to their supporting EvidenceChunk passages."""
    chunks = list(
        db.scalars(
            select(EvidenceChunk).where(EvidenceChunk.investigation_id == investigation_id)
        ).all()
    )
    sources_by_id = {
        s.source_id: s
        for s in db.scalars(select(Source).where(Source.investigation_id == investigation_id)).all()
    }

    existing_claims = list(
        db.scalars(select(Claim).where(Claim.investigation_id == investigation_id)).all()
    )
    existing_texts = {c.claim_text.lower(): c for c in existing_claims}
    claim_seq = len(existing_claims)

    created: list[Claim] = []
    for chunk in chunks:
        src = sources_by_id.get(chunk.source_id)
        sentences = _split_candidate_sentences(chunk.content)
        # Prioritize sentences carrying metrics, licenses, findings, or clear propositions
        scored_sentences = sorted(
            sentences,
            key=lambda s: (
                1 if METRIC_RE.search(s) else 0,
                1 if any(k in s.lower() for k in ("license", "cost", "benchmark", "result", "support", "risk", "fail", "require")) else 0,
            ),
            reverse=True,
        )
        for sent in scored_sentences[:2]:
            key = sent.lower()
            if key in existing_texts:
                claim = existing_texts[key]
                exists_link = db.scalar(
                    select(func.count(ClaimEvidence.id)).where(
                        ClaimEvidence.claim_id == claim.claim_id,
                        ClaimEvidence.evidence_id == chunk.evidence_id,
                    )
                )
                if not exists_link:
                    db.add(ClaimEvidence(claim_id=claim.claim_id, evidence_id=chunk.evidence_id, relation="SUPPORTS"))
                continue

            claim_seq += 1
            cid = f"{investigation_id}-CLAIM-{claim_seq:03d}"
            metric_match = METRIC_RE.search(sent)
            claim = Claim(
                claim_id=cid,
                investigation_id=investigation_id,
                claim_text=sent,
                category=_classify_claim(sent),
                entity=(src.title[:160] if src else "Source"),
                predicate="establishes",
                value_unit=metric_match.group(0) if metric_match else "",
                time_period=(src.published_at[:10] if src and src.published_at else ""),
                geographic_scope=geography,
                verification_status="UNVERIFIED",
                confidence_score=0.5,
            )
            db.add(claim)
            db.flush()
            db.add(ClaimEvidence(claim_id=cid, evidence_id=chunk.evidence_id, relation="SUPPORTS"))
            existing_texts[key] = claim
            created.append(claim)

    db.flush()
    return created
