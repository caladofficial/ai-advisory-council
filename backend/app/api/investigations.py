"""Investigation lifecycle, control actions, prerequisites, additional research, and SSE live progress routes."""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session
from sse_starlette.sse import EventSourceResponse

from app.database.models import (
    AdvisorSession,
    Investigation,
    InvestigationAssumption,
    InvestigationRequirement,
    PrerequisiteCheck,
)
from app.database.repository import (
    create_investigation,
    list_investigations,
    log_audit_event,
    to_investigation_read,
    update_investigation_stage,
)
from app.database.session import get_db
from app.evidence.verifier import verify_investigation_evidence
from app.orchestration.events import progress_broker
from app.orchestration.workflow import ACTIVE_RUNS, execute_investigation_workflow
from app.prerequisites.readiness_gate import evaluate_readiness_gate
from app.prerequisites.resource_estimator import estimate_execution_resources
from app.research.collector import run_research_collection
from app.schemas.investigation import (
    AdditionalResearchRequest,
    ClarificationSubmit,
    InvestigationCreate,
    InvestigationRead,
    InvestigationStatus,
)
from app.schemas.prerequisites import (
    PrerequisiteAssessmentOut,
    ReadinessRubricOut,
    ReadinessStatus,
    RequirementItemOut,
)

router = APIRouter(prefix="/api/investigations", tags=["investigations"])


def _schedule_run(inv_id: str, force_warnings: bool = False) -> None:
    existing = ACTIVE_RUNS.get(inv_id)
    if existing and not existing.done():
        return
    task = asyncio.create_task(
        execute_investigation_workflow(inv_id, force_proceed_warnings=force_warnings)
    )
    ACTIVE_RUNS[inv_id] = task


@router.post("", response_model=InvestigationRead)
async def create_investigation_endpoint(
    payload: InvestigationCreate,
    db: Session = Depends(get_db),
):
    inv = create_investigation(db, payload)
    db.commit()
    db.refresh(inv)
    if payload.auto_start:
        _schedule_run(inv.investigation_id)
    return to_investigation_read(inv)


@router.get("", response_model=list[InvestigationRead])
def list_investigations_endpoint(limit: int = 100, db: Session = Depends(get_db)):
    return [to_investigation_read(i) for i in list_investigations(db, limit=limit)]


@router.get("/{investigation_id}", response_model=InvestigationRead)
def get_investigation_endpoint(investigation_id: str, db: Session = Depends(get_db)):
    inv = db.get(Investigation, investigation_id)
    if inv is None:
        raise HTTPException(status_code=404, detail="Investigation not found")
    return to_investigation_read(inv)


@router.delete("/{investigation_id}")
def delete_investigation_endpoint(investigation_id: str, db: Session = Depends(get_db)):
    inv = db.get(Investigation, investigation_id)
    if inv is None:
        raise HTTPException(status_code=404, detail="Investigation not found")
    if (task := ACTIVE_RUNS.get(investigation_id)) and not task.done():
        inv.cancel_requested = True
        task.cancel()
    db.delete(inv)
    log_audit_event(
        db,
        investigation_id=investigation_id,
        actor="user",
        event_type="INVESTIGATION_DELETED",
        stage="DELETED",
        summary=f"Deleted investigation {investigation_id} per user governance request.",
    )
    db.commit()
    return {"deleted": True, "investigation_id": investigation_id}


@router.post("/{investigation_id}/start")
async def start_investigation_endpoint(
    investigation_id: str,
    force_proceed_warnings: bool = False,
    db: Session = Depends(get_db),
):
    inv = db.get(Investigation, investigation_id)
    if inv is None:
        raise HTTPException(status_code=404, detail="Investigation not found")
    if inv.status == InvestigationStatus.COMPLETED.value:
        return {"status": "already_completed", "investigation_id": investigation_id}
    _schedule_run(investigation_id, force_warnings=force_proceed_warnings)
    return {"status": "started", "investigation_id": investigation_id}


@router.post("/{investigation_id}/pause")
def pause_investigation_endpoint(investigation_id: str, db: Session = Depends(get_db)):
    inv = db.get(Investigation, investigation_id)
    if inv is None:
        raise HTTPException(status_code=404, detail="Investigation not found")
    inv.pause_requested = True
    log_audit_event(
        db,
        investigation_id=investigation_id,
        actor="user",
        event_type="PAUSE_REQUESTED",
        stage=inv.current_stage,
        summary="Pause requested; workflow will checkpoint at current boundary.",
    )
    db.commit()
    return {"status": "pause_requested", "investigation_id": investigation_id}


@router.post("/{investigation_id}/resume")
async def resume_investigation_endpoint(
    investigation_id: str,
    force_proceed_warnings: bool = True,
    db: Session = Depends(get_db),
):
    inv = db.get(Investigation, investigation_id)
    if inv is None:
        raise HTTPException(status_code=404, detail="Investigation not found")
    inv.pause_requested = False
    inv.cancel_requested = False
    db.commit()
    _schedule_run(investigation_id, force_warnings=force_proceed_warnings)
    return {"status": "resumed", "investigation_id": investigation_id}


@router.post("/{investigation_id}/cancel")
def cancel_investigation_endpoint(investigation_id: str, db: Session = Depends(get_db)):
    inv = db.get(Investigation, investigation_id)
    if inv is None:
        raise HTTPException(status_code=404, detail="Investigation not found")
    inv.cancel_requested = True
    update_investigation_stage(db, investigation_id, InvestigationStatus.CANCELLED.value, inv.progress_percent)
    log_audit_event(
        db,
        investigation_id=investigation_id,
        actor="user",
        event_type="CANCELLED",
        stage=inv.current_stage,
        summary="Investigation cancelled by user.",
    )
    db.commit()
    progress_broker.publish(
        investigation_id,
        status="CANCELLED",
        stage=inv.current_stage,
        progress_percent=inv.progress_percent,
        message="Investigation cancelled.",
    )
    return {"status": "cancelled", "investigation_id": investigation_id}


@router.post("/{investigation_id}/clarify")
async def clarify_investigation_endpoint(
    investigation_id: str,
    payload: ClarificationSubmit,
    db: Session = Depends(get_db),
):
    inv = db.get(Investigation, investigation_id)
    if inv is None:
        raise HTTPException(status_code=404, detail="Investigation not found")
    clar = dict(inv.user_clarifications_json or {})
    clar.update(payload.answers)
    inv.user_clarifications_json = clar
    if payload.answers.get("budget"):
        inv.budget = payload.answers["budget"]
    if payload.answers.get("target_users"):
        inv.target_users = payload.answers["target_users"]
    if payload.answers.get("geography"):
        inv.geography = payload.answers["geography"]
    if payload.additional_constraints:
        inv.constraints_json = list(inv.constraints_json or []) + payload.additional_constraints
    log_audit_event(
        db,
        investigation_id=investigation_id,
        actor="user",
        event_type="CLARIFICATION_SUBMITTED",
        stage=inv.current_stage,
        summary="Submitted missing prerequisite clarifications.",
        payload={"keys": list(payload.answers.keys())},
    )
    db.commit()
    _schedule_run(investigation_id, force_warnings=payload.proceed_with_warnings)
    return {"status": "clarified_and_resumed", "investigation_id": investigation_id}


@router.get("/{investigation_id}/prerequisites", response_model=PrerequisiteAssessmentOut)
def get_prerequisites_endpoint(investigation_id: str, db: Session = Depends(get_db)):
    inv = db.get(Investigation, investigation_id)
    if inv is None:
        raise HTTPException(status_code=404, detail="Investigation not found")
    latest = db.scalars(
        select(PrerequisiteCheck)
        .where(PrerequisiteCheck.investigation_id == investigation_id)
        .order_by(PrerequisiteCheck.id.desc())
    ).first()
    if latest is None:
        res = evaluate_readiness_gate(db, inv)
        db.commit()
        return res

    reqs = list(
        db.scalars(select(InvestigationRequirement).where(InvestigationRequirement.investigation_id == investigation_id)).all()
    )
    assumptions = [
        a.assumption_text
        for a in db.scalars(select(InvestigationAssumption).where(InvestigationAssumption.investigation_id == investigation_id)).all()
    ]
    res_est = latest.resource_estimate_json or estimate_execution_resources(db, inv).model_dump()
    return PrerequisiteAssessmentOut(
        investigation_id=investigation_id,
        readiness_status=ReadinessStatus(latest.readiness_status),
        readiness_score=latest.readiness_score,
        rubric=ReadinessRubricOut.model_validate(latest.rubric_json or {}),
        mandatory_items=[
            RequirementItemOut(
                name=r.name,
                category=r.category,
                requirement_type=r.requirement_type,
                status=r.status,
                blocking=r.blocking,
                detail=r.detail,
            )
            for r in reqs
        ],
        research_gaps=latest.research_gaps_json or [],
        assumptions=assumptions,
        clarifying_questions=latest.clarifying_questions_json or [],
        hard_gates_triggered=latest.hard_gates_json or [],
        resource_estimate=res_est,
        allowed_next_stage=latest.allowed_next_stage,
    )


@router.post("/{investigation_id}/additional-research")
async def additional_research_endpoint(
    investigation_id: str,
    payload: AdditionalResearchRequest,
    db: Session = Depends(get_db),
):
    inv = db.get(Investigation, investigation_id)
    if inv is None:
        raise HTTPException(status_code=404, detail="Investigation not found")
    extra_jobs = [(conn, payload.query) for conn in payload.connectors]
    summary = await run_research_collection(db, inv, [], extra_queries=extra_jobs)
    verify_stats = verify_investigation_evidence(db, inv)
    evaluate_readiness_gate(db, inv)
    log_audit_event(
        db,
        investigation_id=investigation_id,
        actor="user",
        event_type="ADDITIONAL_RESEARCH",
        stage=inv.current_stage,
        summary=f"Executed additional research query '{payload.query}' -> +{summary['sources_added']} sources.",
    )
    db.commit()
    return {"collection": summary, "verification": verify_stats}


@router.get("/{investigation_id}/progress")
def get_progress_endpoint(investigation_id: str, db: Session = Depends(get_db)):
    inv = db.get(Investigation, investigation_id)
    if inv is None:
        raise HTTPException(status_code=404, detail="Investigation not found")
    sessions = list(
        db.scalars(select(AdvisorSession).where(AdvisorSession.investigation_id == investigation_id)).all()
    )
    return {
        "investigation_id": inv.investigation_id,
        "status": inv.status,
        "stage": inv.current_stage,
        "progress_percent": inv.progress_percent,
        "advisor_statuses": {s.advisor_id: s.status for s in sessions},
        "error_message": inv.error_message,
        "updated_at": inv.updated_at.isoformat(),
    }


@router.get("/{investigation_id}/progress/stream")
async def stream_progress_endpoint(investigation_id: str, db: Session = Depends(get_db)):
    inv = db.get(Investigation, investigation_id)
    if inv is None:
        raise HTTPException(status_code=404, detail="Investigation not found")

    initial_snapshot = {
        "investigation_id": inv.investigation_id,
        "status": inv.status,
        "stage": inv.current_stage,
        "progress_percent": inv.progress_percent,
        "message": f"Connected to stream (current stage: {inv.current_stage})",
        "advisor_statuses": {
            s.advisor_id: s.status
            for s in db.scalars(select(AdvisorSession).where(AdvisorSession.investigation_id == investigation_id)).all()
        },
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    async def event_generator():
        q = progress_broker.subscribe(investigation_id)
        try:
            yield {"event": "progress", "data": json.dumps(initial_snapshot)}
            while True:
                try:
                    msg = await asyncio.wait_for(q.get(), timeout=15.0)
                    yield {"event": "progress", "data": json.dumps(msg)}
                    if msg.get("status") in {"COMPLETED", "CANCELLED", "FAILED"}:
                        break
                except asyncio.TimeoutError:
                    yield {"event": "heartbeat", "data": json.dumps({"ts": datetime.now(timezone.utc).isoformat()})}
        finally:
            progress_broker.unsubscribe(investigation_id, q)

    return EventSourceResponse(event_generator())
