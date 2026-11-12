"""Advisor profiles, isolated sessions, initial vs final reports, and independence metrics routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agents.advisor_factory import get_council_specs
from app.database.models import AdvisorReport, AdvisorSession, Investigation, PrivateNote
from app.database.session import get_db
from app.evaluation.independence import compute_independence_metrics
from app.schemas.advisor import AdvisorProfileOut, AdvisorReportPayload, AdvisorSessionOut
from app.schemas.evaluation import IndependenceMetricsOut

router = APIRouter(tags=["advisors"])


@router.get("/api/advisors/profiles", response_model=list[AdvisorProfileOut])
def list_advisor_profiles():
    specs = get_council_specs("full_10_plus_1")
    return [
        AdvisorProfileOut(
            advisor_id=s.advisor_id,
            name=s.name,
            title=s.title,
            role=s.role,
            priority=s.priority,
            temperature=s.temperature,
            preferred_capability=s.preferred_capability,
            tool_permissions=s.tool_permissions,
            evaluation_criteria=s.evaluation_criteria,
            bias_controls=s.bias_controls,
        )
        for s in specs
    ]


@router.get("/api/investigations/{investigation_id}/advisors", response_model=list[AdvisorSessionOut])
def get_investigation_advisors(investigation_id: str, db: Session = Depends(get_db)):
    inv = db.get(Investigation, investigation_id)
    if inv is None:
        raise HTTPException(status_code=404, detail="Investigation not found")

    sessions = {
        s.advisor_id: s
        for s in db.scalars(select(AdvisorSession).where(AdvisorSession.investigation_id == investigation_id)).all()
    }
    reports = list(
        db.scalars(select(AdvisorReport).where(AdvisorReport.investigation_id == investigation_id)).all()
    )
    notes = list(
        db.scalars(select(PrivateNote).where(PrivateNote.investigation_id == investigation_id)).all()
    )
    initial_map = {r.advisor_id: r.report_json for r in reports if r.phase == "initial"}
    final_map = {r.advisor_id: r.report_json for r in reports if r.phase == "final"}
    notes_map: dict[str, str] = {}
    for n in notes:
        notes_map[n.advisor_id] = (notes_map.get(n.advisor_id, "") + "\n" + n.note_text).strip()

    specs = get_council_specs(inv.execution_profile)
    out: list[AdvisorSessionOut] = []
    for sp in specs:
        sess = sessions.get(sp.advisor_id)
        init_json = initial_map.get(sp.advisor_id)
        fin_json = final_map.get(sp.advisor_id)
        out.append(
            AdvisorSessionOut(
                session_id=sess.session_id if sess else f"{investigation_id}-{sp.advisor_id}",
                investigation_id=investigation_id,
                advisor_id=sp.advisor_id,
                advisor_name=sp.name,
                advisor_role=sp.role,
                status=sess.status if sess else "pending",
                assigned_provider=sess.assigned_provider if sess else "pending",
                assigned_model=sess.assigned_model if sess else "pending",
                prompt_version=sess.prompt_version if sess else sp.prompt_version,
                initial_report=AdvisorReportPayload.model_validate(init_json) if init_json else None,
                final_report=AdvisorReportPayload.model_validate(fin_json) if fin_json else None,
                position_changed=sess.position_changed if sess else "UNCHANGED",
                unverified_citations=sess.unverified_citations_json if sess else [],
                private_notes=notes_map.get(sp.advisor_id, ""),
                updated_at=sess.updated_at if sess else inv.updated_at,
            )
        )
    return out


@router.get("/api/investigations/{investigation_id}/independence", response_model=IndependenceMetricsOut)
def get_advisor_independence(investigation_id: str, db: Session = Depends(get_db)):
    if db.get(Investigation, investigation_id) is None:
        raise HTTPException(status_code=404, detail="Investigation not found")
    return compute_independence_metrics(db, investigation_id)
