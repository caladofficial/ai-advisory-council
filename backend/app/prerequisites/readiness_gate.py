"""100-Point Pre-Debate Intelligence & Readiness Gate."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_scoring_rubrics_config
from app.database.models import (
    Claim,
    Contradiction,
    EvidenceChunk,
    Investigation,
    PrerequisiteCheck,
    Source,
)
from app.prerequisites.assessor import assess_prerequisites
from app.prerequisites.resource_estimator import estimate_execution_resources
from app.schemas.prerequisites import (
    PrerequisiteAssessmentOut,
    ReadinessRubricOut,
    ReadinessStatus,
)


def evaluate_readiness_gate(
    db: Session,
    inv: Investigation,
    *,
    force_proceed_with_warnings: bool = False,
) -> PrerequisiteAssessmentOut:
    """Compute the 100-point Readiness Gate before allowing the 10 advisors to debate."""
    rubric_cfg = get_scoring_rubrics_config().get("readiness_gate", {})
    thresholds = rubric_cfg.get("thresholds", {})
    ready_min = float(thresholds.get("ready", 75))
    warn_min = float(thresholds.get("ready_with_warnings", 55))

    items, research_gaps, assumptions, clarifying_questions = assess_prerequisites(db, inv)
    resource_est = estimate_execution_resources(db, inv)

    sources = list(db.scalars(select(Source).where(Source.investigation_id == inv.investigation_id)).all())
    unique_sources = [s for s in sources if not s.is_duplicate]
    chunks = list(db.scalars(select(EvidenceChunk).where(EvidenceChunk.investigation_id == inv.investigation_id)).all())
    claims = list(db.scalars(select(Claim).where(Claim.investigation_id == inv.investigation_id)).all())
    contradictions = list(db.scalars(select(Contradiction).where(Contradiction.investigation_id == inv.investigation_id)).all())

    # 1. Topic clarity (0-20)
    topic_len = len(inv.topic.strip())
    topic_clarity = 12.0
    if topic_len >= 25:
        topic_clarity += 4.0
    if inv.objective:
        topic_clarity += 2.0
    if inv.geography:
        topic_clarity += 2.0
    topic_clarity = min(20.0, topic_clarity)

    # 2. Prerequisite completeness (0-20)
    complete_pts = sum(2.0 if it.status == "complete" else (1.1 if it.status == "partial" else 0.2) for it in items)
    prereq_score = min(20.0, round(complete_pts, 1))

    # 3. Relevant source coverage (0-20)
    distinct_types = len({s.source_type for s in unique_sources})
    source_cov = min(20.0, len(unique_sources) * 1.6 + distinct_types * 2.2)

    # 4. Source quality & credibility (0-20)
    avg_q = (sum(c.quality_score for c in chunks) / len(chunks)) if chunks else 0.0
    source_quality = round(min(20.0, avg_q * 22.0), 1)

    # 5. Information freshness (0-10)
    avg_fresh = (
        sum(float((c.quality_breakdown_json or {}).get("freshness", 0.6)) for c in chunks) / len(chunks)
        if chunks
        else 0.4
    )
    freshness_score = round(min(10.0, avg_fresh * 10.0), 1)

    # 6. Contradictions & unknowns identified (0-10)
    contra_score = 4.0
    if claims:
        contra_score += 3.0
    if contradictions or research_gaps:
        contra_score += 3.0
    contra_score = min(10.0, contra_score)

    total = round(
        topic_clarity + prereq_score + source_cov + source_quality + freshness_score + contra_score,
        1,
    )

    hard_gates: list[str] = []
    if any(it.blocking for it in items):
        hard_gates.append("Mandatory problem definition missing or too vague.")
    if not resource_est.fallback_ready:
        hard_gates.append("No healthy or configured zero-paid model available.")
    if len(chunks) == 0:
        hard_gates.append("Zero verified evidence passages retrieved from connectors or uploads.")

    if hard_gates:
        status = ReadinessStatus.NEEDS_USER_INPUT if any(it.blocking for it in items) else ReadinessStatus.NEEDS_MORE_RESEARCH
        allowed = False
    elif total >= ready_min:
        status = ReadinessStatus.READY
        allowed = True
    elif total >= warn_min or force_proceed_with_warnings:
        status = ReadinessStatus.READY_WITH_WARNINGS
        allowed = True
    else:
        status = ReadinessStatus.NEEDS_MORE_RESEARCH
        allowed = False

    rubric_out = ReadinessRubricOut(
        topic_clarity=round(topic_clarity, 1),
        prerequisite_completeness=round(prereq_score, 1),
        source_coverage=round(source_cov, 1),
        source_quality=round(source_quality, 1),
        information_freshness=round(freshness_score, 1),
        contradictions_identified=round(contra_score, 1),
        total_score=total,
    )

    inv.readiness_score = total
    inv.readiness_status = status.value

    db.add(
        PrerequisiteCheck(
            investigation_id=inv.investigation_id,
            readiness_status=status.value,
            readiness_score=total,
            rubric_json=rubric_out.model_dump(),
            research_gaps_json=research_gaps,
            clarifying_questions_json=clarifying_questions,
            hard_gates_json=hard_gates,
            resource_estimate_json=resource_est.model_dump(),
            allowed_next_stage=allowed,
        )
    )
    db.flush()

    return PrerequisiteAssessmentOut(
        investigation_id=inv.investigation_id,
        readiness_status=status,
        readiness_score=total,
        rubric=rubric_out,
        mandatory_items=items,
        research_gaps=research_gaps,
        assumptions=assumptions,
        clarifying_questions=clarifying_questions,
        hard_gates_triggered=hard_gates,
        resource_estimate=resource_est,
        allowed_next_stage=allowed,
    )
