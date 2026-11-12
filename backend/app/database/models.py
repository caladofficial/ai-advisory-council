"""Normalized relational database schema covering all investigation, evidence, council, debate, judge, and audit entities."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.session import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Investigation(Base):
    __tablename__ = "investigations"

    investigation_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    topic: Mapped[str] = mapped_column(Text, nullable=False)
    objective: Mapped[str] = mapped_column(Text, nullable=False, default="")
    mode: Mapped[str] = mapped_column(String(64), nullable=False, default="general_decision")
    execution_profile: Mapped[str] = mapped_column(String(64), nullable=False, default="full_10_plus_1")
    domain: Mapped[str] = mapped_column(String(128), nullable=False, default="General")
    geography: Mapped[str] = mapped_column(String(200), nullable=False, default="Global")
    time_horizon: Mapped[str] = mapped_column(String(120), nullable=False, default="12 months")
    budget: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    target_users: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    constraints_json: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    enabled_connectors_json: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    brief_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)

    status: Mapped[str] = mapped_column(String(64), nullable=False, default="CREATED")
    current_stage: Mapped[str] = mapped_column(String(64), nullable=False, default="CREATED")
    progress_percent: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    readiness_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    readiness_status: Mapped[str | None] = mapped_column(String(64), nullable=True)
    verdict: Mapped[str | None] = mapped_column(String(64), nullable=True)
    feasibility_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    pause_requested: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    cancel_requested: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    user_clarifications_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)

    requirements: Mapped[list[InvestigationRequirement]] = relationship(cascade="all, delete-orphan")
    assumptions: Mapped[list[InvestigationAssumption]] = relationship(cascade="all, delete-orphan")
    prerequisite_checks: Mapped[list[PrerequisiteCheck]] = relationship(cascade="all, delete-orphan")
    research_questions: Mapped[list[ResearchQuestion]] = relationship(cascade="all, delete-orphan")
    research_tasks: Mapped[list[ResearchTask]] = relationship(cascade="all, delete-orphan")
    sources: Mapped[list[Source]] = relationship(cascade="all, delete-orphan")
    evidence_chunks: Mapped[list[EvidenceChunk]] = relationship(cascade="all, delete-orphan")
    claims: Mapped[list[Claim]] = relationship(cascade="all, delete-orphan")
    contradictions: Mapped[list[Contradiction]] = relationship(cascade="all, delete-orphan")
    advisor_sessions: Mapped[list[AdvisorSession]] = relationship(cascade="all, delete-orphan")
    debate_messages: Mapped[list[DebateMessage]] = relationship(cascade="all, delete-orphan")
    debate_challenges: Mapped[list[DebateChallenge]] = relationship(cascade="all, delete-orphan")
    judge_evaluations: Mapped[list[JudgeEvaluation]] = relationship(cascade="all, delete-orphan")
    report_versions: Mapped[list[ReportVersion]] = relationship(cascade="all, delete-orphan")


class InvestigationRequirement(Base):
    __tablename__ = "investigation_requirements"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    investigation_id: Mapped[str] = mapped_column(ForeignKey("investigations.investigation_id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    category: Mapped[str] = mapped_column(String(64), nullable=False)
    requirement_type: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    blocking: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    detail: Mapped[str] = mapped_column(Text, nullable=False, default="")


class InvestigationAssumption(Base):
    __tablename__ = "investigation_assumptions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    investigation_id: Mapped[str] = mapped_column(ForeignKey("investigations.investigation_id", ondelete="CASCADE"), index=True)
    assumption_text: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[str] = mapped_column(String(64), nullable=False, default="system_inferred")
    verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class PrerequisiteCheck(Base):
    __tablename__ = "prerequisite_checks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    investigation_id: Mapped[str] = mapped_column(ForeignKey("investigations.investigation_id", ondelete="CASCADE"), index=True)
    readiness_status: Mapped[str] = mapped_column(String(64), nullable=False)
    readiness_score: Mapped[float] = mapped_column(Float, nullable=False)
    rubric_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    research_gaps_json: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    clarifying_questions_json: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    hard_gates_json: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    resource_estimate_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    allowed_next_stage: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class ResearchQuestion(Base):
    __tablename__ = "research_questions"

    question_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    investigation_id: Mapped[str] = mapped_column(ForeignKey("investigations.investigation_id", ondelete="CASCADE"), index=True)
    query_family: Mapped[str] = mapped_column(String(64), nullable=False)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    search_query: Mapped[str] = mapped_column(Text, nullable=False)
    connector: Mapped[str] = mapped_column(String(64), nullable=False)
    priority: Mapped[str] = mapped_column(String(32), nullable=False, default="MEDIUM")
    assigned_advisors_json: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)


class ResearchTask(Base):
    __tablename__ = "research_tasks"

    task_id: Mapped[str] = mapped_column(String(48), primary_key=True)
    investigation_id: Mapped[str] = mapped_column(ForeignKey("investigations.investigation_id", ondelete="CASCADE"), index=True)
    connector: Mapped[str] = mapped_column(String(64), nullable=False)
    query: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="PENDING")
    items_found: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    duration_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class Source(Base):
    __tablename__ = "sources"

    source_id: Mapped[str] = mapped_column(String(48), primary_key=True)
    investigation_id: Mapped[str] = mapped_column(ForeignKey("investigations.investigation_id", ondelete="CASCADE"), index=True)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    canonical_url: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    publisher: Mapped[str] = mapped_column(String(256), nullable=False, default="")
    author: Mapped[str] = mapped_column(String(256), nullable=False, default="")
    published_at: Mapped[str | None] = mapped_column(String(64), nullable=True)
    retrieved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    source_type: Mapped[str] = mapped_column(String(64), nullable=False)
    domain: Mapped[str] = mapped_column(String(256), nullable=False, default="")
    canonical_identifier: Mapped[str | None] = mapped_column(String(256), nullable=True)
    license_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    content_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    raw_excerpt: Mapped[str] = mapped_column(Text, nullable=False, default="")
    is_duplicate: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    syndicated_from_id: Mapped[str | None] = mapped_column(String(48), nullable=True)
    reliability_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.5)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)


class EvidenceChunk(Base):
    __tablename__ = "evidence_chunks"

    evidence_id: Mapped[str] = mapped_column(String(48), primary_key=True)
    investigation_id: Mapped[str] = mapped_column(ForeignKey("investigations.investigation_id", ondelete="CASCADE"), index=True)
    source_id: Mapped[str] = mapped_column(ForeignKey("sources.source_id", ondelete="CASCADE"), index=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    section: Mapped[str] = mapped_column(String(128), nullable=False, default="main")
    page: Mapped[int | None] = mapped_column(Integer, nullable=True)
    paragraph_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    content_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    quality_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.5)
    quality_breakdown_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    prompt_injection_flagged: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    limitations_json: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class Claim(Base):
    __tablename__ = "claims"

    claim_id: Mapped[str] = mapped_column(String(48), primary_key=True)
    investigation_id: Mapped[str] = mapped_column(ForeignKey("investigations.investigation_id", ondelete="CASCADE"), index=True)
    claim_text: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(String(64), nullable=False, default="general")
    entity: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    predicate: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    value_unit: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    time_period: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    geographic_scope: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    verification_status: Mapped[str] = mapped_column(String(64), nullable=False, default="UNVERIFIED")
    confidence_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.5)


class ClaimEvidence(Base):
    __tablename__ = "claim_evidence"
    __table_args__ = (UniqueConstraint("claim_id", "evidence_id", name="uq_claim_evidence"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    claim_id: Mapped[str] = mapped_column(ForeignKey("claims.claim_id", ondelete="CASCADE"), index=True)
    evidence_id: Mapped[str] = mapped_column(ForeignKey("evidence_chunks.evidence_id", ondelete="CASCADE"), index=True)
    relation: Mapped[str] = mapped_column(String(32), nullable=False, default="SUPPORTS")


class ClaimVerification(Base):
    __tablename__ = "claim_verifications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    investigation_id: Mapped[str] = mapped_column(ForeignKey("investigations.investigation_id", ondelete="CASCADE"), index=True)
    claim_id: Mapped[str] = mapped_column(ForeignKey("claims.claim_id", ondelete="CASCADE"), index=True)
    source_exists: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    source_identity_clear: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    passage_match_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    independent_corroboration_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    contradiction_found: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    freshness_valid: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    deterministic_check_passed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    status: Mapped[str] = mapped_column(String(64), nullable=False, default="UNVERIFIED")
    notes_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)


class Contradiction(Base):
    __tablename__ = "contradictions"

    contradiction_id: Mapped[str] = mapped_column(String(48), primary_key=True)
    investigation_id: Mapped[str] = mapped_column(ForeignKey("investigations.investigation_id", ondelete="CASCADE"), index=True)
    claim_a_id: Mapped[str] = mapped_column(ForeignKey("claims.claim_id", ondelete="CASCADE"))
    claim_b_id: Mapped[str | None] = mapped_column(ForeignKey("claims.claim_id", ondelete="SET NULL"), nullable=True)
    evidence_a_id: Mapped[str | None] = mapped_column(String(48), nullable=True)
    evidence_b_id: Mapped[str | None] = mapped_column(String(48), nullable=True)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    severity: Mapped[str] = mapped_column(String(32), nullable=False, default="MEDIUM")
    resolved: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class AdvisorSession(Base):
    __tablename__ = "advisor_sessions"
    __table_args__ = (UniqueConstraint("investigation_id", "advisor_id", name="uq_inv_advisor"),)

    session_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    investigation_id: Mapped[str] = mapped_column(ForeignKey("investigations.investigation_id", ondelete="CASCADE"), index=True)
    advisor_id: Mapped[str] = mapped_column(String(64), nullable=False)
    advisor_name: Mapped[str] = mapped_column(String(128), nullable=False)
    advisor_role: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="idle")
    assigned_provider: Mapped[str] = mapped_column(String(64), nullable=False, default="ollama")
    assigned_model: Mapped[str] = mapped_column(String(200), nullable=False, default="llama3.2:3b")
    prompt_version: Mapped[str] = mapped_column(String(32), nullable=False, default="v1.0")
    position_changed: Mapped[str] = mapped_column(String(32), nullable=False, default="UNCHANGED")
    unverified_citations_json: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)


class AdvisorReport(Base):
    __tablename__ = "advisor_reports"
    __table_args__ = (UniqueConstraint("investigation_id", "advisor_id", "phase", name="uq_inv_adv_phase"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    investigation_id: Mapped[str] = mapped_column(ForeignKey("investigations.investigation_id", ondelete="CASCADE"), index=True)
    session_id: Mapped[str] = mapped_column(ForeignKey("advisor_sessions.session_id", ondelete="CASCADE"))
    advisor_id: Mapped[str] = mapped_column(String(64), nullable=False)
    phase: Mapped[str] = mapped_column(String(32), nullable=False)  # initial | final
    stance: Mapped[str] = mapped_column(String(64), nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.5)
    report_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class PrivateNote(Base):
    """Isolated per-advisor scratchpad; NEVER shared across advisors or Judge."""

    __tablename__ = "private_notes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    investigation_id: Mapped[str] = mapped_column(ForeignKey("investigations.investigation_id", ondelete="CASCADE"), index=True)
    advisor_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    stage: Mapped[str] = mapped_column(String(64), nullable=False)
    note_text: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class DebateRound(Base):
    __tablename__ = "debate_rounds"
    __table_args__ = (UniqueConstraint("investigation_id", "round_number", name="uq_inv_round"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    investigation_id: Mapped[str] = mapped_column(ForeignKey("investigations.investigation_id", ondelete="CASCADE"), index=True)
    round_number: Mapped[int] = mapped_column(Integer, nullable=False)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="COMPLETED")
    summary: Mapped[str] = mapped_column(Text, nullable=False, default="")


class DebateMessage(Base):
    __tablename__ = "debate_messages"

    message_id: Mapped[str] = mapped_column(String(48), primary_key=True)
    investigation_id: Mapped[str] = mapped_column(ForeignKey("investigations.investigation_id", ondelete="CASCADE"), index=True)
    round_number: Mapped[int] = mapped_column(Integer, nullable=False)
    sender: Mapped[str] = mapped_column(String(64), nullable=False)
    receiver: Mapped[str] = mapped_column(String(64), nullable=False, default="council")
    message_type: Mapped[str] = mapped_column(String(32), nullable=False)
    target_claim_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    argument: Mapped[str] = mapped_column(Text, nullable=False)
    evidence_ids_json: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    unverified_evidence_ids_json: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    requested_action: Mapped[str | None] = mapped_column(Text, nullable=True)
    priority: Mapped[str] = mapped_column(String(32), nullable=False, default="MEDIUM")
    disposition: Mapped[str | None] = mapped_column(String(64), nullable=True)
    position_change: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class DebateChallenge(Base):
    __tablename__ = "debate_challenges"

    challenge_id: Mapped[str] = mapped_column(String(48), primary_key=True)
    investigation_id: Mapped[str] = mapped_column(ForeignKey("investigations.investigation_id", ondelete="CASCADE"), index=True)
    round_number: Mapped[int] = mapped_column(Integer, nullable=False, default=2)
    challenger_id: Mapped[str] = mapped_column(String(64), nullable=False)
    target_advisor_id: Mapped[str] = mapped_column(String(64), nullable=False)
    target_claim_id: Mapped[str] = mapped_column(String(64), nullable=False)
    disputed_claim_text: Mapped[str] = mapped_column(Text, nullable=False)
    challenge_argument: Mapped[str] = mapped_column(Text, nullable=False)
    requested_action: Mapped[str] = mapped_column(Text, nullable=False)
    impact_score: Mapped[int] = mapped_column(Integer, nullable=False)
    uncertainty_score: Mapped[int] = mapped_column(Integer, nullable=False)
    relevance_score: Mapped[int] = mapped_column(Integer, nullable=False)
    priority_score: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="OPEN")
    disposition: Mapped[str | None] = mapped_column(String(64), nullable=True)
    evidence_ids_json: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)


class JudgeEvaluation(Base):
    __tablename__ = "judge_evaluations"

    evaluation_id: Mapped[str] = mapped_column(String(48), primary_key=True)
    investigation_id: Mapped[str] = mapped_column(ForeignKey("investigations.investigation_id", ondelete="CASCADE"), index=True)
    model_used: Mapped[str] = mapped_column(String(200), nullable=False)
    provider_used: Mapped[str] = mapped_column(String(64), nullable=False)
    verdict: Mapped[str] = mapped_column(String(64), nullable=False)
    feasibility_score: Mapped[float] = mapped_column(Float, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    evaluation_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    deterministic_checks_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    disagreed_with_majority: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class RiskItem(Base):
    __tablename__ = "risk_register"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    investigation_id: Mapped[str] = mapped_column(ForeignKey("investigations.investigation_id", ondelete="CASCADE"), index=True)
    risk_id: Mapped[str] = mapped_column(String(32), nullable=False)
    title: Mapped[str] = mapped_column(String(256), nullable=False)
    category: Mapped[str] = mapped_column(String(64), nullable=False)
    likelihood: Mapped[str] = mapped_column(String(32), nullable=False)
    impact: Mapped[str] = mapped_column(String(32), nullable=False)
    mitigation: Mapped[str] = mapped_column(Text, nullable=False)
    owner_role: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    evidence_ids_json: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)


class ImplementationMilestone(Base):
    __tablename__ = "implementation_milestones"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    investigation_id: Mapped[str] = mapped_column(ForeignKey("investigations.investigation_id", ondelete="CASCADE"), index=True)
    phase: Mapped[str] = mapped_column(String(64), nullable=False)
    title: Mapped[str] = mapped_column(String(256), nullable=False)
    owner_role: Mapped[str] = mapped_column(String(128), nullable=False)
    deliverable: Mapped[str] = mapped_column(Text, nullable=False)
    acceptance_criterion: Mapped[str] = mapped_column(Text, nullable=False)
    stop_condition: Mapped[str] = mapped_column(Text, nullable=False, default="")


class ReportVersion(Base):
    __tablename__ = "report_versions"
    __table_args__ = (UniqueConstraint("investigation_id", "version_number", name="uq_inv_report_ver"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    investigation_id: Mapped[str] = mapped_column(ForeignKey("investigations.investigation_id", ondelete="CASCADE"), index=True)
    version_number: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    dossier_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    markdown_content: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class AuditEvent(Base):
    """Append-only system and decision event log."""

    __tablename__ = "audit_events"

    event_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    investigation_id: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    actor: Mapped[str] = mapped_column(String(64), nullable=False)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    stage: Mapped[str] = mapped_column(String(64), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    payload_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class ModelUsage(Base):
    __tablename__ = "model_usage"

    usage_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    investigation_id: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    agent_id: Mapped[str] = mapped_column(String(64), nullable=False)
    provider: Mapped[str] = mapped_column(String(64), nullable=False)
    model_id: Mapped[str] = mapped_column(String(200), nullable=False)
    prompt_version: Mapped[str] = mapped_column(String(32), nullable=False, default="v1.0")
    prompt_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    completion_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    latency_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    estimated_cost_usd: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="SUCCESS")
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class ModelRegistryEntry(Base):
    __tablename__ = "model_registry"
    __table_args__ = (UniqueConstraint("provider", "model_id", name="uq_provider_model"),)

    id: Mapped[str] = mapped_column(String(128), primary_key=True)
    provider: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    model_id: Mapped[str] = mapped_column(String(200), nullable=False)
    display_name: Mapped[str] = mapped_column(String(200), nullable=False)
    execution_mode: Mapped[str] = mapped_column(String(32), nullable=False, default="free_hosted")
    family: Mapped[str] = mapped_column(String(64), nullable=False, default="general")
    capabilities_json: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    supports_tools: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    supports_json: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    context_window: Mapped[int | None] = mapped_column(Integer, nullable=True)
    rate_limit_note: Mapped[str] = mapped_column(String(256), nullable=False, default="")
    is_free: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    availability_status: Mapped[str] = mapped_column(String(32), nullable=False, default="untested")
    last_health_check: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    quality_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    latency_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class AdvisorModelBinding(Base):
    """Stores custom user overrides assigning specific provider/model per advisor or judge."""

    __tablename__ = "advisor_model_bindings"

    advisor_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    provider: Mapped[str] = mapped_column(String(64), nullable=False)
    model_id: Mapped[str] = mapped_column(String(200), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)
