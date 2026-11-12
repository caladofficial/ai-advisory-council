"""Eleventh AI — Independent Chief Judge with deterministic verification checks, adaptive rubric, and hard blockers."""

from __future__ import annotations

import json
from collections import Counter

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agents.advisor_factory import load_prompt_file
from app.config import get_scoring_rubrics_config
from app.database.models import (
    AdvisorReport,
    AdvisorSession,
    Claim,
    Contradiction,
    DebateChallenge,
    DebateMessage,
    EvidenceChunk,
    ImplementationMilestone,
    Investigation,
    JudgeEvaluation,
    PrerequisiteCheck,
    RiskItem,
)
from app.models.router import invoke_structured
from app.schemas.judge import JudgeVerdictPayload, ScorecardDimensionOut

DIMENSION_LABELS = {
    "technical_feasibility": "Technical Feasibility",
    "financial_feasibility": "Financial Feasibility",
    "market_user_value": "Market & User Value",
    "operational_feasibility": "Operational Feasibility",
    "legal_ethical_compliance": "Legal & Ethical Compliance",
    "security_safety": "Security & Safety",
    "evidence_strength": "Evidence Strength",
    "long_term_sustainability": "Long-Term Sustainability",
}


def run_deterministic_audit(db: Session, inv: Investigation) -> dict[str, object]:
    """Perform programmatic, non-LLM checks before final adjudication."""
    chunks = list(db.scalars(select(EvidenceChunk).where(EvidenceChunk.investigation_id == inv.investigation_id)).all())
    claims = list(db.scalars(select(Claim).where(Claim.investigation_id == inv.investigation_id)).all())
    contradictions = list(db.scalars(select(Contradiction).where(Contradiction.investigation_id == inv.investigation_id)).all())
    sessions = list(db.scalars(select(AdvisorSession).where(AdvisorSession.investigation_id == inv.investigation_id)).all())
    challenges = list(db.scalars(select(DebateChallenge).where(DebateChallenge.investigation_id == inv.investigation_id)).all())

    hallucinated_citations = sum(len(s.unverified_citations_json or []) for s in sessions)
    high_contradictions = [c for c in contradictions if c.severity == "HIGH" and not c.resolved]
    unresolved_challenges = [ch for ch in challenges if ch.status != "RESOLVED"]
    verified_claims = [c for c in claims if c.verification_status in {"VERIFIED", "CORROBORATED"}]
    avg_quality = round(sum(c.quality_score for c in chunks) / len(chunks), 3) if chunks else 0.0

    return {
        "evidence_chunks_count": len(chunks),
        "claims_count": len(claims),
        "verified_or_corroborated_claims": len(verified_claims),
        "average_evidence_quality": avg_quality,
        "high_severity_contradictions": len(high_contradictions),
        "hallucinated_citation_flags": hallucinated_citations,
        "unresolved_challenges": len(unresolved_challenges),
        "readiness_score": inv.readiness_score,
        "readiness_status": inv.readiness_status,
    }


async def run_chief_judge(db: Session, inv: Investigation) -> JudgeEvaluation:
    """Run the independent 11th Judge over the immutable investigation archive (excluding private notes)."""
    existing = db.scalars(
        select(JudgeEvaluation).where(JudgeEvaluation.investigation_id == inv.investigation_id)
    ).first()
    if existing is not None:
        return existing

    rubrics_cfg = get_scoring_rubrics_config()
    weights = rubrics_cfg.get("judge_scorecards", {}).get(
        inv.mode, rubrics_cfg.get("judge_scorecards", {}).get("general_decision", {})
    )
    verdict_rules = rubrics_cfg.get("verdict_rules", {})

    audit = run_deterministic_audit(db, inv)

    prereq = db.scalars(
        select(PrerequisiteCheck)
        .where(PrerequisiteCheck.investigation_id == inv.investigation_id)
        .order_by(PrerequisiteCheck.id.desc())
    ).first()
    claims = list(db.scalars(select(Claim).where(Claim.investigation_id == inv.investigation_id)).all())
    contradictions = list(db.scalars(select(Contradiction).where(Contradiction.investigation_id == inv.investigation_id)).all())
    final_reports = list(
        db.scalars(
            select(AdvisorReport).where(
                AdvisorReport.investigation_id == inv.investigation_id,
                AdvisorReport.phase == "final",
            )
        ).all()
    )
    if not final_reports:
        final_reports = list(
            db.scalars(
                select(AdvisorReport).where(
                    AdvisorReport.investigation_id == inv.investigation_id,
                    AdvisorReport.phase == "initial",
                )
            ).all()
        )
    debate_msgs = list(
        db.scalars(
            select(DebateMessage)
            .where(DebateMessage.investigation_id == inv.investigation_id)
            .order_by(DebateMessage.round_number, DebateMessage.created_at)
        ).all()
    )

    stance_counts = Counter(r.stance for r in final_reports)
    majority_stance = stance_counts.most_common(1)[0][0] if stance_counts else "CONDITIONAL"

    advisor_dossier = [
        {
            "advisor_id": r.advisor_id,
            "stance": r.stance,
            "confidence": r.confidence,
            "findings": str((r.report_json or {}).get("executive_findings", ""))[:500],
            "risks": (r.report_json or {}).get("risks_and_weaknesses", [])[:4],
            "recommendations": (r.report_json or {}).get("recommendations", [])[:3],
            "evidence_cited": (r.report_json or {}).get("evidence_ids_cited", [])[:6],
        }
        for r in final_reports
    ]
    debate_excerpt = [
        f"R{m.round_number} {m.sender}->{m.receiver} [{m.message_type} | {m.disposition or ''}]: {m.argument[:260]}"
        for m in debate_msgs[:24]
    ]

    judge_prompt = load_prompt_file("chief_judge.txt")
    user_prompt = (
        f"INVESTIGATION BRIEF:\n{json.dumps(inv.brief_json or {'topic': inv.topic}, indent=2)}\n\n"
        f"ADAPTIVE RUBRIC WEIGHTS FOR MODE '{inv.mode}':\n{json.dumps(weights, indent=2)}\n\n"
        f"DETERMINISTIC AUDIT CHECKS:\n{json.dumps(audit, indent=2)}\n\n"
        f"PREREQUISITE GAPS & ASSUMPTIONS:\n{json.dumps(prereq.research_gaps_json if prereq else [], indent=2)}\n\n"
        f"EXTRACTED CLAIMS SUMMARY:\n"
        + "\n".join(f"- {c.claim_id.replace(inv.investigation_id + '-', '')} [{c.verification_status}]: {c.claim_text}" for c in claims[:16])
        + "\n\nCONTRADICTIONS:\n"
        + ("\n".join(f"- [{ct.severity}] {ct.summary}" for ct in contradictions[:8]) or "(None)")
        + "\n\nFINAL ADVISOR REPORTS (Private working notes strictly excluded):\n"
        + json.dumps(advisor_dossier, indent=2)
        + "\n\nDEBATE LOG EXCERPT:\n"
        + "\n".join(debate_excerpt)
        + "\n\nTASK: Issue your independent, evidence-grounded feasibility evaluation and final verdict."
    )

    verdict_payload, llm_res = await invoke_structured(
        db,
        investigation_id=inv.investigation_id,
        agent_id="chief_judge",
        system_prompt=judge_prompt,
        user_prompt=user_prompt,
        schema=JudgeVerdictPayload,
        temperature=0.1,
        max_tokens=4000,
    )

    # Deterministic weighted score calculation: F = sum(W_i * S_i)
    scorecard: list[ScorecardDimensionOut] = []
    weighted_sum = 0.0
    total_w = 0.0
    for dim_key, weight_val in weights.items():
        w = float(weight_val)
        raw_s = float(verdict_payload.dimension_scores.get(dim_key, 55.0))
        clamped_s = max(0.0, min(100.0, raw_s))
        contrib = round(w * clamped_s, 2)
        weighted_sum += contrib
        total_w += w
        scorecard.append(
            ScorecardDimensionOut(
                dimension=dim_key,
                label=DIMENSION_LABELS.get(dim_key, dim_key.replace("_", " ").title()),
                weight=w,
                score=round(clamped_s, 1),
                weighted_contribution=contrib,
                rationale=verdict_payload.dimension_rationales.get(
                    dim_key, "Evaluated against verified evidence and advisor debate."
                ),
            )
        )

    final_score = round((weighted_sum / total_w) if total_w > 0 else 50.0, 1)

    # Hard-constraint & insufficient-evidence guardrail overrides
    effective_verdict = verdict_payload.verdict
    if int(audit["evidence_chunks_count"]) == 0 and effective_verdict == "GO":
        effective_verdict = "INSUFFICIENT_EVIDENCE"
    elif verdict_payload.hard_blockers and effective_verdict == "GO":
        effective_verdict = str(verdict_rules.get("hard_blocker_max_verdict", "CONDITIONAL_GO"))
    elif final_score < float(verdict_rules.get("pivot_min_score", 35)) and effective_verdict in {"GO", "CONDITIONAL_GO"}:
        effective_verdict = "PIVOT"

    # Determine if Judge diverged from advisor majority stance
    disagreed_with_majority = verdict_payload.disagreed_with_majority or (
        (majority_stance == "SUPPORT" and effective_verdict in {"NO_GO", "PIVOT", "INSUFFICIENT_EVIDENCE"})
        or (majority_stance == "OPPOSE" and effective_verdict in {"GO", "CONDITIONAL_GO"})
    )

    eval_id = f"{inv.investigation_id}-JUDGE-01"
    eval_dict = verdict_payload.model_dump()
    eval_dict["verdict"] = effective_verdict
    eval_dict["scorecard"] = [s.model_dump() for s in scorecard]
    eval_dict["feasibility_score"] = final_score
    eval_dict["disagreed_with_majority"] = disagreed_with_majority

    judge_row = JudgeEvaluation(
        evaluation_id=eval_id,
        investigation_id=inv.investigation_id,
        model_used=llm_res.model_id,
        provider_used=llm_res.provider,
        verdict=effective_verdict,
        feasibility_score=final_score,
        confidence=verdict_payload.confidence,
        evaluation_json=eval_dict,
        deterministic_checks_json=audit,
        disagreed_with_majority=disagreed_with_majority,
    )
    db.add(judge_row)

    # Populate relational risk_register & implementation_milestones tables
    db.query(RiskItem).filter_by(investigation_id=inv.investigation_id).delete()
    for idx, r in enumerate(verdict_payload.risk_register, start=1):
        db.add(
            RiskItem(
                investigation_id=inv.investigation_id,
                risk_id=r.risk_id or f"RSK-{idx:02d}",
                title=r.title[:256],
                category=r.category[:64],
                likelihood=r.likelihood[:32],
                impact=r.impact[:32],
                mitigation=r.mitigation,
                owner_role=r.owner_role[:128],
                evidence_ids_json=r.evidence_ids,
            )
        )

    db.query(ImplementationMilestone).filter_by(investigation_id=inv.investigation_id).delete()
    for m in verdict_payload.roadmap:
        db.add(
            ImplementationMilestone(
                investigation_id=inv.investigation_id,
                phase=m.phase[:64],
                title=m.title[:256],
                owner_role=m.owner_role[:128],
                deliverable=m.deliverable,
                acceptance_criterion=m.acceptance_criterion,
                stop_condition=m.stop_condition,
            )
        )

    inv.verdict = effective_verdict
    inv.feasibility_score = final_score
    db.flush()
    return judge_row
