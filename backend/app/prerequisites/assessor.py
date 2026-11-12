"""Topic-adaptive 10-category Prerequisite Assessor separating user inputs, researchables, and assumptions."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.models import (
    Claim,
    EvidenceChunk,
    Investigation,
    InvestigationAssumption,
    InvestigationRequirement,
)
from app.schemas.prerequisites import RequirementItemOut


def assess_prerequisites(
    db: Session,
    inv: Investigation,
) -> tuple[list[RequirementItemOut], list[str], list[str], list[str]]:
    """Evaluate 10 prerequisite dimensions against user intake, clarifications, and collected evidence."""
    clarifications = inv.user_clarifications_json or {}
    claims = list(db.scalars(select(Claim).where(Claim.investigation_id == inv.investigation_id)).all())
    chunks = list(db.scalars(select(EvidenceChunk).where(EvidenceChunk.investigation_id == inv.investigation_id)).all())
    corpus = " ".join([inv.topic, inv.objective] + [c.claim_text for c in claims] + [ch.content[:200] for ch in chunks[:8]]).lower()

    def _has_any(*words: str) -> bool:
        return any(w in corpus for w in words)

    has_budget = bool(inv.budget or clarifications.get("budget"))
    has_users = bool(inv.target_users or clarifications.get("target_users"))
    has_geo = bool(inv.geography and inv.geography.lower() != "global") or bool(clarifications.get("geography"))
    has_timeline = bool(inv.time_horizon or clarifications.get("time_horizon"))
    has_tech_evidence = _has_any("architecture", "api", "model", "github", "framework", "stack", "software")
    has_legal_evidence = _has_any("law", "regulation", "license", "privacy", "compliance", "gdpr", "policy", "ethics")
    has_market_evidence = _has_any("market", "competitor", "adoption", "demand", "alternative", "user")

    items: list[RequirementItemOut] = [
        RequirementItemOut(
            name="Problem definition & objective",
            category="problem_definition",
            requirement_type="mandatory_user_input",
            status="complete" if len(inv.topic.strip()) >= 15 else "partial",
            blocking=len(inv.topic.strip()) < 10,
            detail=inv.objective or "Goal derived from topic prompt.",
        ),
        RequirementItemOut(
            name="Target audience / users",
            category="target_audience",
            requirement_type="mandatory_user_input",
            status="complete" if has_users else ("partial" if has_market_evidence else "missing"),
            blocking=False,
            detail=inv.target_users or "Not explicitly specified by user; inferred or flagged for validation.",
        ),
        RequirementItemOut(
            name="Scope & geographic boundary",
            category="scope",
            requirement_type="mandatory_user_input",
            status="complete" if has_geo else "partial",
            blocking=False,
            detail=f"Geography: {inv.geography}",
        ),
        RequirementItemOut(
            name="Technical capabilities & architecture",
            category="technical_requirements",
            requirement_type="researchable",
            status="complete" if has_tech_evidence else "missing",
            blocking=False,
            detail="Covered via GitHub/Hugging Face/Technical evidence." if has_tech_evidence else "Needs technical source evidence.",
        ),
        RequirementItemOut(
            name="Operational resources & execution capacity",
            category="resources",
            requirement_type="operational_dependency",
            status="partial",
            blocking=False,
            detail="Team skills and infrastructure constraints not fully quantified; will be modeled as explicit assumptions.",
        ),
        RequirementItemOut(
            name="Financial budget & cost assumptions",
            category="financial_constraints",
            requirement_type="mandatory_user_input",
            status="complete" if has_budget else ("partial" if _has_any("cost", "pricing", "free", "budget") else "missing"),
            blocking=False,
            detail=inv.budget or "No explicit budget cap provided; advisors must state explicit cost assumptions.",
        ),
        RequirementItemOut(
            name="Legal, licensing & regulatory compliance",
            category="legal_requirements",
            requirement_type="researchable",
            status="complete" if has_legal_evidence else "partial",
            blocking=False,
            detail="Compliance & open-source licensing signals extracted." if has_legal_evidence else "Limited primary regulatory evidence found.",
        ),
        RequirementItemOut(
            name="Timeline & delivery horizon",
            category="time_constraints",
            requirement_type="optional",
            status="complete" if has_timeline else "partial",
            blocking=False,
            detail=f"Target horizon: {inv.time_horizon}",
        ),
        RequirementItemOut(
            name="Measurable success criteria",
            category="success_criteria",
            requirement_type="optional",
            status="complete" if inv.constraints_json else "partial",
            blocking=False,
            detail=f"Constraints/criteria count: {len(inv.constraints_json or [])}",
        ),
        RequirementItemOut(
            name="Risk tolerance & failure boundaries",
            category="risk_tolerance",
            requirement_type="optional",
            status="partial",
            blocking=False,
            detail="Default moderate risk posture unless constrained by high-impact domain rules.",
        ),
    ]

    assumptions: list[str] = []
    research_gaps: list[str] = []
    clarifying_questions: list[str] = []

    if not has_budget:
        assumptions.append("No fixed budget provided; Financial Strategist must evaluate lean MVP vs full-scale cost bands.")
        clarifying_questions.append("What is your target initial budget ceiling and acceptable monthly operating burn?")
    if not has_users:
        assumptions.append("Target user segment inferred from topic phrasing; adoption willingness remains unverified.")
        clarifying_questions.append("Who are the exact primary target users or institutions for initial rollout?")
    if not has_tech_evidence:
        research_gaps.append("Insufficient technical architecture and implementation benchmarks retrieved.")
    if not has_market_evidence:
        research_gaps.append("Insufficient independent market demand or competitor benchmark evidence.")
    if not has_legal_evidence and inv.mode in {"business_feasibility", "policy_analysis", "general_decision"}:
        research_gaps.append("Jurisdiction-specific legal and regulatory evidence is incomplete.")

    db.query(InvestigationRequirement).filter_by(investigation_id=inv.investigation_id).delete()
    for it in items:
        db.add(
            InvestigationRequirement(
                investigation_id=inv.investigation_id,
                name=it.name,
                category=it.category,
                requirement_type=it.requirement_type,
                status=it.status,
                blocking=it.blocking,
                detail=it.detail,
            )
        )

    db.query(InvestigationAssumption).filter_by(investigation_id=inv.investigation_id).delete()
    for a in assumptions:
        db.add(
            InvestigationAssumption(
                investigation_id=inv.investigation_id,
                assumption_text=a,
                source="prerequisite_assessor",
                verified=False,
            )
        )

    db.flush()
    return items, research_gaps, assumptions, clarifying_questions
