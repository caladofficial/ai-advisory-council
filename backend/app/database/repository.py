"""Typed database repository helpers for investigations, evidence, council sessions, debate, judge, and append-only audit logs."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from app.database.models import (
    AdvisorModelBinding,
    AdvisorReport,
    AdvisorSession,
    AuditEvent,
    Claim,
    ClaimEvidence,
    ClaimVerification,
    Contradiction,
    DebateChallenge,
    DebateMessage,
    DebateRound,
    EvidenceChunk,
    ImplementationMilestone,
    Investigation,
    InvestigationAssumption,
    InvestigationRequirement,
    JudgeEvaluation,
    ModelRegistryEntry,
    ModelUsage,
    PrerequisiteCheck,
    PrivateNote,
    ReportVersion,
    ResearchQuestion,
    ResearchTask,
    RiskItem,
    Source,
)
from app.schemas.investigation import InvestigationCreate, InvestigationRead, InvestigationStatus
from app.security.secrets import scrub_secrets_from_text


def _next_investigation_id(db: Session) -> str:
    count = db.scalar(select(func.count(Investigation.investigation_id))) or 0
    candidate = f"INV-{count + 1:04d}"
    while db.get(Investigation, candidate) is not None:
        candidate = f"INV-{uuid4().hex[:6].upper()}"
    return candidate


def create_investigation(db: Session, payload: InvestigationCreate) -> Investigation:
    inv_id = _next_investigation_id(db)
    inv = Investigation(
        investigation_id=inv_id,
        topic=payload.topic.strip(),
        objective=payload.objective.strip(),
        mode=payload.mode.value,
        execution_profile=payload.execution_profile.value,
        geography=payload.geography.strip() or "Global",
        time_horizon=payload.time_horizon.strip() or "12 months",
        budget=payload.budget.strip(),
        target_users=payload.target_users.strip(),
        constraints_json=payload.constraints,
        enabled_connectors_json=payload.enabled_connectors,
        status=InvestigationStatus.CREATED.value,
        current_stage=InvestigationStatus.CREATED.value,
        progress_percent=0,
    )
    db.add(inv)
    db.flush()
    log_audit_event(
        db,
        investigation_id=inv_id,
        actor="user",
        event_type="INVESTIGATION_CREATED",
        stage=InvestigationStatus.CREATED.value,
        summary=f"Created investigation {inv_id}: {inv.topic[:120]}",
        payload={"mode": inv.mode, "execution_profile": inv.execution_profile},
    )
    return inv


def to_investigation_read(inv: Investigation) -> InvestigationRead:
    return InvestigationRead(
        investigation_id=inv.investigation_id,
        topic=inv.topic,
        objective=inv.objective,
        mode=inv.mode,  # type: ignore[arg-type]
        execution_profile=inv.execution_profile,  # type: ignore[arg-type]
        domain=inv.domain,
        geography=inv.geography,
        time_horizon=inv.time_horizon,
        budget=inv.budget,
        target_users=inv.target_users,
        constraints=inv.constraints_json or [],
        enabled_connectors=inv.enabled_connectors_json or [],
        status=InvestigationStatus(inv.status),
        current_stage=inv.current_stage,
        progress_percent=inv.progress_percent,
        readiness_score=inv.readiness_score,
        readiness_status=inv.readiness_status,
        verdict=inv.verdict,
        feasibility_score=inv.feasibility_score,
        error_message=inv.error_message,
        brief_json=inv.brief_json or {},
        created_at=inv.created_at,
        updated_at=inv.updated_at,
    )


def update_investigation_stage(
    db: Session,
    investigation_id: str,
    status: str,
    progress_percent: int,
    *,
    error_message: str | None = None,
) -> Investigation | None:
    inv = db.get(Investigation, investigation_id)
    if inv is None:
        return None
    inv.status = status
    inv.current_stage = status
    inv.progress_percent = max(0, min(100, progress_percent))
    if error_message is not None:
        inv.error_message = scrub_secrets_from_text(error_message)
    inv.updated_at = datetime.now(timezone.utc)
    db.flush()
    return inv


def log_audit_event(
    db: Session,
    *,
    investigation_id: str | None,
    actor: str,
    event_type: str,
    stage: str,
    summary: str,
    payload: dict[str, Any] | None = None,
) -> AuditEvent:
    ev = AuditEvent(
        investigation_id=investigation_id,
        actor=actor,
        event_type=event_type,
        stage=stage,
        summary=scrub_secrets_from_text(summary),
        payload_json=payload or {},
    )
    db.add(ev)
    db.flush()
    return ev


def record_model_usage(
    db: Session,
    *,
    investigation_id: str | None,
    agent_id: str,
    provider: str,
    model_id: str,
    prompt_version: str,
    prompt_tokens: int,
    completion_tokens: int,
    latency_ms: int,
    status: str = "SUCCESS",
    error_message: str | None = None,
) -> ModelUsage:
    usage = ModelUsage(
        investigation_id=investigation_id,
        agent_id=agent_id,
        provider=provider,
        model_id=model_id,
        prompt_version=prompt_version,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=prompt_tokens + completion_tokens,
        latency_ms=latency_ms,
        estimated_cost_usd=0.0,  # Zero-paid enforcement
        status=status,
        error_message=scrub_secrets_from_text(error_message or "") or None,
    )
    db.add(usage)
    db.flush()
    return usage


def list_investigations(db: Session, limit: int = 100) -> list[Investigation]:
    return list(
        db.scalars(select(Investigation).order_by(desc(Investigation.created_at)).limit(limit)).all()
    )


def get_advisor_model_bindings(db: Session) -> dict[str, tuple[str, str]]:
    rows = db.scalars(select(AdvisorModelBinding)).all()
    return {row.advisor_id: (row.provider, row.model_id) for row in rows}


def upsert_advisor_model_binding(db: Session, advisor_id: str, provider: str, model_id: str) -> None:
    existing = db.get(AdvisorModelBinding, advisor_id)
    if existing:
        existing.provider = provider
        existing.model_id = model_id
    else:
        db.add(AdvisorModelBinding(advisor_id=advisor_id, provider=provider, model_id=model_id))
    db.flush()


def get_requests_today_by_provider(db: Session) -> dict[str, int]:
    start_of_day = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    rows = db.execute(
        select(ModelUsage.provider, func.count(ModelUsage.usage_id))
        .where(ModelUsage.created_at >= start_of_day)
        .group_by(ModelUsage.provider)
    ).all()
    return {prov: int(cnt) for prov, cnt in rows}


def clear_debate_and_judge_artifacts(db: Session, investigation_id: str) -> None:
    """Helper used only when explicitly re-running from scratch; never deletes completed evidence."""
    db.query(DebateMessage).filter_by(investigation_id=investigation_id).delete()
    db.query(DebateChallenge).filter_by(investigation_id=investigation_id).delete()
    db.query(DebateRound).filter_by(investigation_id=investigation_id).delete()
    db.query(JudgeEvaluation).filter_by(investigation_id=investigation_id).delete()
    db.query(RiskItem).filter_by(investigation_id=investigation_id).delete()
    db.query(ImplementationMilestone).filter_by(investigation_id=investigation_id).delete()
    db.flush()


__all__ = [
    "AdvisorModelBinding",
    "AdvisorReport",
    "AdvisorSession",
    "AuditEvent",
    "Claim",
    "ClaimEvidence",
    "ClaimVerification",
    "Contradiction",
    "DebateChallenge",
    "DebateMessage",
    "DebateRound",
    "EvidenceChunk",
    "ImplementationMilestone",
    "Investigation",
    "InvestigationAssumption",
    "InvestigationRequirement",
    "JudgeEvaluation",
    "ModelRegistryEntry",
    "ModelUsage",
    "PrerequisiteCheck",
    "PrivateNote",
    "ReportVersion",
    "ResearchQuestion",
    "ResearchTask",
    "RiskItem",
    "Source",
    "create_investigation",
    "get_advisor_model_bindings",
    "get_requests_today_by_provider",
    "list_investigations",
    "log_audit_event",
    "record_model_usage",
    "to_investigation_read",
    "update_investigation_stage",
    "upsert_advisor_model_binding",
    "clear_debate_and_judge_artifacts",
]
