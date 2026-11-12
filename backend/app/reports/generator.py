"""Builds immutable versioned 30-section Investigation Dossiers and Markdown renders."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

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
    InvestigationAssumption,
    InvestigationRequirement,
    JudgeEvaluation,
    ModelUsage,
    PrerequisiteCheck,
    ReportVersion,
    RiskItem,
    Source,
)
from app.evaluation.independence import compute_independence_metrics


def build_investigation_dossier(db: Session, inv: Investigation) -> ReportVersion:
    """Assemble and store an immutable versioned Investigation Dossier."""
    latest_ver = db.scalar(
        select(func.max(ReportVersion.version_number)).where(
            ReportVersion.investigation_id == inv.investigation_id
        )
    ) or 0
    next_ver = latest_ver + 1

    prereq = db.scalars(
        select(PrerequisiteCheck)
        .where(PrerequisiteCheck.investigation_id == inv.investigation_id)
        .order_by(PrerequisiteCheck.id.desc())
    ).first()
    requirements = list(
        db.scalars(select(InvestigationRequirement).where(InvestigationRequirement.investigation_id == inv.investigation_id)).all()
    )
    assumptions = list(
        db.scalars(select(InvestigationAssumption).where(InvestigationAssumption.investigation_id == inv.investigation_id)).all()
    )
    sources = list(db.scalars(select(Source).where(Source.investigation_id == inv.investigation_id)).all())
    chunks = list(db.scalars(select(EvidenceChunk).where(EvidenceChunk.investigation_id == inv.investigation_id)).all())
    claims = list(db.scalars(select(Claim).where(Claim.investigation_id == inv.investigation_id)).all())
    contradictions = list(db.scalars(select(Contradiction).where(Contradiction.investigation_id == inv.investigation_id)).all())
    sessions = list(db.scalars(select(AdvisorSession).where(AdvisorSession.investigation_id == inv.investigation_id)).all())
    reports = list(db.scalars(select(AdvisorReport).where(AdvisorReport.investigation_id == inv.investigation_id)).all())
    challenges = list(db.scalars(select(DebateChallenge).where(DebateChallenge.investigation_id == inv.investigation_id)).all())
    messages = list(
        db.scalars(
            select(DebateMessage)
            .where(DebateMessage.investigation_id == inv.investigation_id)
            .order_by(DebateMessage.round_number, DebateMessage.created_at)
        ).all()
    )
    judge = db.scalars(
        select(JudgeEvaluation)
        .where(JudgeEvaluation.investigation_id == inv.investigation_id)
        .order_by(JudgeEvaluation.created_at.desc())
    ).first()
    risks = list(db.scalars(select(RiskItem).where(RiskItem.investigation_id == inv.investigation_id)).all())
    milestones = list(
        db.scalars(select(ImplementationMilestone).where(ImplementationMilestone.investigation_id == inv.investigation_id)).all()
    )
    usages = list(db.scalars(select(ModelUsage).where(ModelUsage.investigation_id == inv.investigation_id)).all())
    independence = compute_independence_metrics(db, inv.investigation_id)

    initial_by_adv = {r.advisor_id: r.report_json for r in reports if r.phase == "initial"}
    final_by_adv = {r.advisor_id: r.report_json for r in reports if r.phase == "final"}

    judge_json = judge.evaluation_json if judge else {}

    dossier: dict[str, Any] = {
        "cover": {
            "investigation_id": inv.investigation_id,
            "version": next_ver,
            "topic": inv.topic,
            "objective": inv.objective,
            "mode": inv.mode,
            "execution_profile": inv.execution_profile,
            "domain": inv.domain,
            "geography": inv.geography,
            "time_horizon": inv.time_horizon,
            "verdict": inv.verdict or "PENDING",
            "feasibility_score": inv.feasibility_score,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        },
        "executive_summary": judge_json.get("executive_summary", ""),
        "scope_and_assumptions": {
            "budget": inv.budget or "Unspecified",
            "target_users": inv.target_users or "Unspecified",
            "constraints": inv.constraints_json or [],
            "assumptions": [a.assumption_text for a in assumptions],
        },
        "methodology": (
            "Four-engine AI Advisory Council pipeline: centralized multi-connector research & verification, "
            "100-point Pre-Debate Readiness Gate, blind independent specialist analyses with isolated private notes, "
            "4-round Challenge Graph debate (P = I x U x R), and an independent Chief Judge with deterministic audits."
        ),
        "prerequisite_assessment": {
            "readiness_score": inv.readiness_score,
            "readiness_status": inv.readiness_status,
            "rubric": prereq.rubric_json if prereq else {},
            "requirements": [
                {"name": r.name, "type": r.requirement_type, "status": r.status, "detail": r.detail}
                for r in requirements
            ],
            "research_gaps": prereq.research_gaps_json if prereq else [],
        },
        "research_coverage": {
            "total_sources": len(sources),
            "unique_sources": len([s for s in sources if not s.is_duplicate]),
            "duplicate_or_syndicated": len([s for s in sources if s.is_duplicate]),
            "evidence_chunks": len(chunks),
            "claims_extracted": len(claims),
            "contradictions_detected": len(contradictions),
            "by_source_type": {
                st: len([s for s in sources if s.source_type == st and not s.is_duplicate])
                for st in sorted({s.source_type for s in sources})
            },
        },
        "advisor_independence": independence.model_dump(),
        "advisor_reports": [
            {
                "advisor_id": s.advisor_id,
                "name": s.advisor_name,
                "role": s.advisor_role,
                "provider": s.assigned_provider,
                "model": s.assigned_model,
                "position_changed": s.position_changed,
                "unverified_citations": s.unverified_citations_json or [],
                "initial": initial_by_adv.get(s.advisor_id, {}),
                "final": final_by_adv.get(s.advisor_id, initial_by_adv.get(s.advisor_id, {})),
            }
            for s in sessions
        ],
        "debate_summary": {
            "total_messages": len(messages),
            "challenges": [
                {
                    "challenge_id": c.challenge_id,
                    "challenger": c.challenger_id,
                    "target": c.target_advisor_id,
                    "priority_score": c.priority_score,
                    "disputed_claim": c.disputed_claim_text,
                    "argument": c.challenge_argument,
                    "disposition": c.disposition,
                    "status": c.status,
                }
                for c in challenges
            ],
            "transcript": [
                {
                    "message_id": m.message_id,
                    "round": m.round_number,
                    "sender": m.sender,
                    "receiver": m.receiver,
                    "type": m.message_type,
                    "argument": m.argument,
                    "evidence_ids": m.evidence_ids_json or [],
                    "disposition": m.disposition,
                    "position_change": m.position_change,
                }
                for m in messages
            ],
        },
        "chief_judge_decision": judge_json,
        "risk_register": [
            {
                "risk_id": r.risk_id,
                "title": r.title,
                "category": r.category,
                "likelihood": r.likelihood,
                "impact": r.impact,
                "mitigation": r.mitigation,
                "owner_role": r.owner_role,
            }
            for r in risks
        ],
        "implementation_roadmap": [
            {
                "phase": m.phase,
                "title": m.title,
                "owner_role": m.owner_role,
                "deliverable": m.deliverable,
                "acceptance_criterion": m.acceptance_criterion,
                "stop_condition": m.stop_condition,
            }
            for m in milestones
        ],
        "evidence_register": [
            {
                "evidence_id": ch.evidence_id.replace(f"{inv.investigation_id}-", ""),
                "source_id": ch.source_id,
                "quality_score": ch.quality_score,
                "content": ch.content[:400],
            }
            for ch in chunks
        ],
        "sources_register": [
            {
                "source_id": s.source_id,
                "title": s.title,
                "url": s.url,
                "source_type": s.source_type,
                "published_at": s.published_at,
                "is_duplicate": s.is_duplicate,
                "syndicated_from_id": s.syndicated_from_id,
            }
            for s in sources
        ],
        "audit_and_usage": {
            "total_model_calls": len(usages),
            "total_tokens": sum(u.total_tokens for u in usages),
            "total_estimated_cost_usd": 0.0,
            "models_used": sorted({f"{u.provider}:{u.model_id}" for u in usages if u.status == "SUCCESS"}),
        },
    }

    markdown = render_dossier_markdown(dossier)
    rv = ReportVersion(
        investigation_id=inv.investigation_id,
        version_number=next_ver,
        dossier_json=dossier,
        markdown_content=markdown,
    )
    db.add(rv)
    db.flush()
    return rv


def render_dossier_markdown(dossier: dict[str, Any]) -> str:
    """Render structured Investigation Dossier into portable Markdown."""
    cov = dossier["cover"]
    judge = dossier.get("chief_judge_decision") or {}
    lines: list[str] = [
        f"# AI Advisory Council — Investigation Dossier ({cov['investigation_id']} v{cov['version']})",
        "",
        f"- **Topic:** {cov['topic']}",
        f"- **Objective:** {cov['objective']}",
        f"- **Mode:** `{cov['mode']}` | **Domain:** {cov['domain']} | **Geography:** {cov['geography']}",
        f"- **Verdict:** **{cov['verdict']}** | **Feasibility Score:** **{cov.get('feasibility_score', 'N/A')}/100**",
        f"- **Generated:** {cov['generated_at']}",
        "",
        "## 1. Executive Summary",
        dossier.get("executive_summary") or "(Pending)",
        "",
        "## 2. Pre-Debate Readiness & Prerequisites",
        f"- **Readiness Score:** {dossier['prerequisite_assessment'].get('readiness_score')} ({dossier['prerequisite_assessment'].get('readiness_status')})",
        "### Assumptions & Gaps",
    ]
    for a in dossier["scope_and_assumptions"].get("assumptions", []):
        lines.append(f"- {a}")
    for g in dossier["prerequisite_assessment"].get("research_gaps", []):
        lines.append(f"- [Gap] {g}")

    lines.extend(["", "## 3. Chief Judge Weighted Scorecard"])
    for dim in judge.get("scorecard", []):
        lines.append(
            f"- **{dim['label']}** (Weight {dim['weight']:.0%}): **{dim['score']}/100** — {dim['rationale']}"
        )

    if judge.get("hard_blockers"):
        lines.extend(["", "### Hard Blockers"])
        for hb in judge["hard_blockers"]:
            lines.append(f"- **[{hb['severity']}] {hb['category']}**: {hb['description']}")

    if judge.get("preserved_minority_opinions"):
        lines.extend(["", "### Preserved Minority Opinions"])
        for mo in judge["preserved_minority_opinions"]:
            lines.append(f"- {mo}")

    lines.extend(["", "## 4. Ten Advisor Positions (Initial vs Final)"])
    for adv in dossier.get("advisor_reports", []):
        fin = adv.get("final") or {}
        lines.append(
            f"### {adv['name']} ({adv['role']}) — `{adv['provider']}:{adv['model']}`"
        )
        lines.append(
            f"- **Final Stance:** `{fin.get('stance', 'N/A')}` (Confidence {fin.get('confidence', 0):.0%}) | Revision: `{adv['position_changed']}`"
        )
        lines.append(f"- **Findings:** {fin.get('executive_findings', '')}")
        lines.append(f"- **Evidence Cited:** {', '.join(fin.get('evidence_ids_cited', [])) or 'None'}")
        lines.append("")

    lines.extend(["## 5. Structured Debate & Challenge Graph"])
    for ch in dossier["debate_summary"].get("challenges", []):
        lines.append(
            f"- **{ch['challenge_id']}** (`{ch['challenger']}` -> `{ch['target']}`, P={ch['priority_score']}): {ch['argument']} -> **{ch.get('disposition') or ch['status']}**"
        )

    lines.extend(["", "## 6. Risk Register"])
    for r in dossier.get("risk_register", []):
        lines.append(f"- **{r['risk_id']} [{r['likelihood']}/{r['impact']}] {r['title']}**: {r['mitigation']}")

    lines.extend(["", "## 7. Implementation Roadmap"])
    for m in dossier.get("implementation_roadmap", []):
        lines.append(f"- **{m['phase']} — {m['title']}** ({m['owner_role']}): {m['deliverable']} | Gate: {m['acceptance_criterion']}")

    lines.extend(["", "## 8. Sources & Citations"])
    for s in dossier.get("sources_register", []):
        dup_tag = f" *(Duplicate of {s['syndicated_from_id']})*" if s.get("is_duplicate") else ""
        lines.append(f"- **{s['source_id']}** [{s['source_type']}]: [{s['title']}]({s['url']}){dup_tag}")

    return "\n".join(lines)
