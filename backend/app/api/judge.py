"""Independent Chief Judge verdict, scorecard, blockers, and roadmap routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.models import Investigation, JudgeEvaluation
from app.database.session import get_db
from app.schemas.judge import JudgeEvaluationOut

router = APIRouter(prefix="/api/investigations/{investigation_id}", tags=["judge"])


@router.get("/judge", response_model=JudgeEvaluationOut)
def get_judge_evaluation(investigation_id: str, db: Session = Depends(get_db)):
    if db.get(Investigation, investigation_id) is None:
        raise HTTPException(status_code=404, detail="Investigation not found")
    row = db.scalars(
        select(JudgeEvaluation)
        .where(JudgeEvaluation.investigation_id == investigation_id)
        .order_by(JudgeEvaluation.created_at.desc())
    ).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Chief Judge evaluation not yet generated")

    ev = row.evaluation_json or {}
    return JudgeEvaluationOut(
        evaluation_id=row.evaluation_id,
        investigation_id=row.investigation_id,
        model_used=row.model_used,
        provider_used=row.provider_used,
        verdict=row.verdict,  # type: ignore[arg-type]
        feasibility_score=row.feasibility_score,
        confidence=row.confidence,
        executive_summary=ev.get("executive_summary", ""),
        decision_rationale=ev.get("decision_rationale", ""),
        scorecard=ev.get("scorecard", []),
        hard_blockers=ev.get("hard_blockers", []),
        deterministic_checks=row.deterministic_checks_json or {},
        best_arguments_for=ev.get("best_arguments_for", []),
        strongest_arguments_against=ev.get("strongest_arguments_against", []),
        advisor_rationales=ev.get("advisor_rationales", []),
        preserved_minority_opinions=ev.get("preserved_minority_opinions", []),
        required_changes=ev.get("required_changes", []),
        conditions_for_approval=ev.get("conditions_for_approval", []),
        prerequisites_needed=ev.get("prerequisites_needed", []),
        risk_register=ev.get("risk_register", []),
        roadmap=ev.get("roadmap", []),
        kpis=ev.get("kpis", []),
        remaining_questions=ev.get("remaining_questions", []),
        disagreed_with_majority=row.disagreed_with_majority,
        created_at=row.created_at,
    )
