"""Append-only Audit Events and Model Usage ledger routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.database.models import AuditEvent, ModelUsage
from app.database.session import get_db
from app.schemas.evaluation import AuditEventOut, ModelUsageOut

router = APIRouter(prefix="/api/audit", tags=["audit"])


@router.get("", response_model=list[AuditEventOut])
def list_global_audit_events(limit: int = 100, db: Session = Depends(get_db)):
    rows = db.scalars(select(AuditEvent).order_by(desc(AuditEvent.created_at)).limit(limit)).all()
    return [
        AuditEventOut(
            event_id=r.event_id,
            investigation_id=r.investigation_id,
            actor=r.actor,
            event_type=r.event_type,
            stage=r.stage,
            summary=r.summary,
            payload=r.payload_json or {},
            created_at=r.created_at,
        )
        for r in rows
    ]


@router.get("/usage", response_model=list[ModelUsageOut])
def list_global_model_usage(limit: int = 100, db: Session = Depends(get_db)):
    rows = db.scalars(select(ModelUsage).order_by(desc(ModelUsage.created_at)).limit(limit)).all()
    return [
        ModelUsageOut(
            usage_id=u.usage_id,
            investigation_id=u.investigation_id,
            agent_id=u.agent_id,
            provider=u.provider,
            model_id=u.model_id,
            prompt_version=u.prompt_version,
            prompt_tokens=u.prompt_tokens,
            completion_tokens=u.completion_tokens,
            total_tokens=u.total_tokens,
            latency_ms=u.latency_ms,
            estimated_cost_usd=u.estimated_cost_usd,
            status=u.status,
            error_message=u.error_message,
            created_at=u.created_at,
        )
        for u in rows
    ]


@router.get("/{investigation_id}")
def get_investigation_audit(investigation_id: str, db: Session = Depends(get_db)):
    events = db.scalars(
        select(AuditEvent)
        .where(AuditEvent.investigation_id == investigation_id)
        .order_by(AuditEvent.created_at)
    ).all()
    usages = db.scalars(
        select(ModelUsage)
        .where(ModelUsage.investigation_id == investigation_id)
        .order_by(ModelUsage.created_at)
    ).all()
    return {
        "investigation_id": investigation_id,
        "events": [
            AuditEventOut(
                event_id=r.event_id,
                investigation_id=r.investigation_id,
                actor=r.actor,
                event_type=r.event_type,
                stage=r.stage,
                summary=r.summary,
                payload=r.payload_json or {},
                created_at=r.created_at,
            )
            for r in events
        ],
        "model_usage": [
            ModelUsageOut(
                usage_id=u.usage_id,
                investigation_id=u.investigation_id,
                agent_id=u.agent_id,
                provider=u.provider,
                model_id=u.model_id,
                prompt_version=u.prompt_version,
                prompt_tokens=u.prompt_tokens,
                completion_tokens=u.completion_tokens,
                total_tokens=u.total_tokens,
                latency_ms=u.latency_ms,
                estimated_cost_usd=u.estimated_cost_usd,
                status=u.status,
                error_message=u.error_message,
                created_at=u.created_at,
            )
            for u in usages
        ],
    }
