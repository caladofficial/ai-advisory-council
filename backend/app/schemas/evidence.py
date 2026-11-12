"""Schemas for evidence passages, atomic claims, verifications, and contradictions."""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class VerificationStatus(str, Enum):
    VERIFIED = "VERIFIED"
    CORROBORATED = "CORROBORATED"
    PARTIALLY_SUPPORTED = "PARTIALLY_SUPPORTED"
    CONTRADICTED = "CONTRADICTED"
    UNVERIFIED = "UNVERIFIED"
    OUTDATED = "OUTDATED"


class QualityRubricBreakdown(BaseModel):
    authority: float = 0.0
    methodology: float = 0.0
    relevance: float = 0.0
    corroboration: float = 0.0
    freshness: float = 0.0
    weighted_total: float = 0.0
    notes: str = ""


class EvidenceChunkOut(BaseModel):
    evidence_id: str
    investigation_id: str
    source_id: str
    source_title: str = ""
    source_url: str = ""
    source_type: str = ""
    content: str
    section: str = ""
    page: int | None = None
    paragraph_index: int = 0
    content_hash: str
    quality_score: float = 0.0
    quality_breakdown: QualityRubricBreakdown = Field(default_factory=QualityRubricBreakdown)
    prompt_injection_flagged: bool = False
    limitations: list[str] = Field(default_factory=list)


class ClaimOut(BaseModel):
    claim_id: str
    investigation_id: str
    claim_text: str
    category: str
    entity: str = ""
    predicate: str = ""
    value_unit: str = ""
    time_period: str = ""
    geographic_scope: str = ""
    verification_status: VerificationStatus = VerificationStatus.UNVERIFIED
    confidence_score: float = 0.0
    evidence_ids: list[str] = Field(default_factory=list)
    verification_notes: dict[str, Any] = Field(default_factory=dict)


class ContradictionOut(BaseModel):
    contradiction_id: str
    investigation_id: str
    claim_a_id: str
    claim_b_id: str | None = None
    evidence_a_id: str | None = None
    evidence_b_id: str | None = None
    summary: str
    severity: str = "MEDIUM"
    resolved: bool = False
