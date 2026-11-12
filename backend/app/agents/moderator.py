"""Structured Debate Moderator: Challenge Graph (P = I * U * R), Targeted Challenges, and Rebuttals."""

from __future__ import annotations

import json

from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agents.advisor_factory import AdvisorSpec, load_prompt_file
from app.agents.advisor_runner import verify_cited_evidence_ids
from app.database.models import (
    AdvisorReport,
    AdvisorSession,
    Contradiction,
    DebateChallenge,
    DebateMessage,
    DebateRound,
    EvidenceChunk,
    Investigation,
)
from app.evidence.retrieval import retrieve_evidence_for_advisor
from app.models.router import invoke_structured
from app.schemas.debate import ChallengeCandidate, RebuttalPayload


class ChallengePlanPayload(BaseModel):
    challenges: list[ChallengeCandidate] = Field(default_factory=list)


def publish_opening_round(
    db: Session,
    inv: Investigation,
    specs: list[AdvisorSpec],
) -> list[DebateMessage]:
    """Round 1: Publish every advisor's independent blind opening statement after all have finished."""
    existing = list(
        db.scalars(
            select(DebateMessage).where(
                DebateMessage.investigation_id == inv.investigation_id,
                DebateMessage.round_number == 1,
            )
        ).all()
    )
    if existing:
        return existing

    reports = {
        r.advisor_id: r.report_json
        for r in db.scalars(
            select(AdvisorReport).where(
                AdvisorReport.investigation_id == inv.investigation_id,
                AdvisorReport.phase == "initial",
            )
        ).all()
    }
    valid_short_ids = {
        ch.evidence_id.replace(f"{inv.investigation_id}-", "").upper()
        for ch in db.scalars(select(EvidenceChunk).where(EvidenceChunk.investigation_id == inv.investigation_id)).all()
    }

    db.add(
        DebateRound(
            investigation_id=inv.investigation_id,
            round_number=1,
            name="Opening Statements",
            status="COMPLETED",
            summary="Blind Stage-5 assessments published simultaneously.",
        )
    )

    created: list[DebateMessage] = []
    for idx, spec in enumerate(specs, start=1):
        rep = reports.get(spec.advisor_id, {})
        cited = list(rep.get("evidence_ids_cited") or [])
        unverified = verify_cited_evidence_ids(cited, valid_short_ids)
        stance = rep.get("stance", "CONDITIONAL")
        conf = rep.get("confidence", 0.5)
        findings = rep.get("executive_findings", "")
        weakness = rep.get("self_identified_weakness", "")
        msg = DebateMessage(
            message_id=f"{inv.investigation_id}-MSG-R1-{idx:02d}",
            investigation_id=inv.investigation_id,
            round_number=1,
            sender=spec.advisor_id,
            receiver="council",
            message_type="OPENING",
            target_claim_id=f"{spec.advisor_id}:initial_stance",
            argument=f"[{stance} | Confidence {conf:.0%}] {findings}\nSelf-identified weakness: {weakness}",
            evidence_ids_json=cited,
            unverified_evidence_ids_json=unverified,
            priority="HIGH" if spec.priority in {"high", "critical"} else "MEDIUM",
        )
        db.add(msg)
        created.append(msg)

    db.flush()
    return created


async def build_and_dispatch_challenges(
    db: Session,
    inv: Investigation,
    specs: list[AdvisorSpec],
    *,
    max_challenges: int = 6,
) -> list[DebateChallenge]:
    """Stage 6 + Round 2: Build Challenge Graph prioritized by P = I * U * R and route targeted challenges."""
    existing = list(
        db.scalars(
            select(DebateChallenge).where(DebateChallenge.investigation_id == inv.investigation_id)
        ).all()
    )
    if existing:
        return existing

    reports = {
        r.advisor_id: r.report_json
        for r in db.scalars(
            select(AdvisorReport).where(
                AdvisorReport.investigation_id == inv.investigation_id,
                AdvisorReport.phase == "initial",
            )
        ).all()
    }
    contradictions = list(
        db.scalars(select(Contradiction).where(Contradiction.investigation_id == inv.investigation_id)).all()
    )

    advisor_summaries = []
    for spec in specs:
        rep = reports.get(spec.advisor_id, {})
        advisor_summaries.append(
            {
                "advisor_id": spec.advisor_id,
                "stance": rep.get("stance"),
                "confidence": rep.get("confidence"),
                "findings": str(rep.get("executive_findings", ""))[:450],
                "key_claims": rep.get("key_claims", [])[:3],
                "risks": rep.get("risks_and_weaknesses", [])[:3],
                "evidence_ids": rep.get("evidence_ids_cited", [])[:5],
            }
        )

    mod_prompt = load_prompt_file("moderator.txt")
    valid_ids = [s.advisor_id for s in specs]
    user_prompt = (
        f"TOPIC: {inv.topic}\n"
        f"VALID ADVISOR IDS: {', '.join(valid_ids)}\n\n"
        f"DETECTED EVIDENCE CONTRADICTIONS:\n"
        + ("\n".join(f"- {c.summary}" for c in contradictions[:6]) or "(None)")
        + "\n\nINITIAL ADVISOR SUBMISSIONS:\n"
        + json.dumps(advisor_summaries, indent=2)
        + f"\n\nTASK: Generate between 3 and {max_challenges} high-value targeted challenges between distinct advisors "
        f"(challenger_id != target_advisor_id, both must be in VALID ADVISOR IDS). "
        f"Prioritize Devil's Advocate, Financial vs Technical cost/feasibility clashes, Security vs Architecture, and Legal blockers."
    )

    plan, _ = await invoke_structured(
        db,
        investigation_id=inv.investigation_id,
        agent_id="moderator",
        system_prompt=mod_prompt,
        user_prompt=user_prompt,
        schema=ChallengePlanPayload,
        temperature=0.2,
        max_tokens=2200,
    )

    valid_set = set(valid_ids)
    filtered: list[ChallengeCandidate] = []
    for ch in plan.challenges:
        if ch.challenger_id in valid_set and ch.target_advisor_id in valid_set and ch.challenger_id != ch.target_advisor_id:
            if len(ch.challenge_argument.strip()) >= 15:
                filtered.append(ch)

    # Guarantee at least 2 structured cross-role challenges if LLM returned fewer valid pairs
    if len(filtered) < 2 and len(valid_ids) >= 2:
        adv_from = "devils_advocate" if "devils_advocate" in valid_set else valid_ids[-1]
        adv_to = "technical_architect" if "technical_architect" in valid_set and adv_from != "technical_architect" else valid_ids[0]
        filtered.append(
            ChallengeCandidate(
                challenger_id=adv_from,
                target_advisor_id=adv_to,
                target_claim_id=f"{adv_to}:core_feasibility",
                disputed_claim_text="Primary technical and delivery feasibility conclusion",
                challenge_argument="Verify critical single points of failure, hidden integration effort, and worst-case constraint resilience.",
                requested_action="Cite verified EVD-* evidence or revise confidence and conditions.",
                impact_score=5,
                uncertainty_score=4,
                relevance_score=5,
            )
        )

    # Sort descending by P = I * U * R
    filtered.sort(key=lambda c: c.impact_score * c.uncertainty_score * c.relevance_score, reverse=True)
    filtered = filtered[:max_challenges]

    db.add(
        DebateRound(
            investigation_id=inv.investigation_id,
            round_number=2,
            name="Targeted Challenges",
            status="COMPLETED",
            summary=f"Moderator built challenge graph with {len(filtered)} prioritized edges (P = I * U * R).",
        )
    )

    created_challenges: list[DebateChallenge] = []
    for idx, ch in enumerate(filtered, start=1):
        p_score = ch.impact_score * ch.uncertainty_score * ch.relevance_score
        cid = f"{inv.investigation_id}-CHG-{idx:03d}"
        prio_label = "CRITICAL" if p_score >= 80 else ("HIGH" if p_score >= 45 else "MEDIUM")
        row = DebateChallenge(
            challenge_id=cid,
            investigation_id=inv.investigation_id,
            round_number=2,
            challenger_id=ch.challenger_id,
            target_advisor_id=ch.target_advisor_id,
            target_claim_id=ch.target_claim_id or f"{ch.target_advisor_id}:claim_{idx}",
            disputed_claim_text=ch.disputed_claim_text,
            challenge_argument=ch.challenge_argument,
            requested_action=ch.requested_action,
            impact_score=ch.impact_score,
            uncertainty_score=ch.uncertainty_score,
            relevance_score=ch.relevance_score,
            priority_score=p_score,
            status="OPEN",
            evidence_ids_json=ch.evidence_ids,
        )
        db.add(row)
        created_challenges.append(row)

        db.add(
            DebateMessage(
                message_id=f"{inv.investigation_id}-MSG-R2-{idx:02d}",
                investigation_id=inv.investigation_id,
                round_number=2,
                sender=ch.challenger_id,
                receiver=ch.target_advisor_id,
                message_type="CHALLENGE",
                target_claim_id=row.target_claim_id,
                argument=f"[Priority P={p_score} ({ch.impact_score}x{ch.uncertainty_score}x{ch.relevance_score})] {ch.challenge_argument}",
                evidence_ids_json=ch.evidence_ids,
                requested_action=ch.requested_action,
                priority=prio_label,
            )
        )

    db.flush()
    return created_challenges


async def run_rebuttal_round(
    db: Session,
    inv: Investigation,
    specs: list[AdvisorSpec],
) -> list[DebateMessage]:
    """Round 3: Only challenged advisors respond with evidence-backed rebuttals and explicit position status."""
    existing = list(
        db.scalars(
            select(DebateMessage).where(
                DebateMessage.investigation_id == inv.investigation_id,
                DebateMessage.round_number == 3,
            )
        ).all()
    )
    if existing:
        return existing

    challenges = list(
        db.scalars(
            select(DebateChallenge)
            .where(DebateChallenge.investigation_id == inv.investigation_id)
            .order_by(DebateChallenge.priority_score.desc())
        ).all()
    )
    spec_map = {s.advisor_id: s for s in specs}
    valid_short_ids = {
        ch.evidence_id.replace(f"{inv.investigation_id}-", "").upper()
        for ch in db.scalars(select(EvidenceChunk).where(EvidenceChunk.investigation_id == inv.investigation_id)).all()
    }

    db.add(
        DebateRound(
            investigation_id=inv.investigation_id,
            round_number=3,
            name="Rebuttals & Revisions",
            status="COMPLETED",
            summary=f"Challenged advisors responded to {len(challenges)} targeted disputes.",
        )
    )

    messages: list[DebateMessage] = []
    for idx, ch in enumerate(challenges, start=1):
        target_spec = spec_map.get(ch.target_advisor_id)
        if not target_spec:
            continue

        sess = db.get(AdvisorSession, f"{inv.investigation_id}-{target_spec.advisor_id}")
        if sess:
            sess.status = "revising"
            db.flush()

        _, _, _, packet = retrieve_evidence_for_advisor(
            db,
            inv.investigation_id,
            lens_keywords=target_spec.evidence_keywords + ch.challenge_argument.split()[:5],
            preferred_source_types=target_spec.evidence_source_types,
            topic=inv.topic,
            top_k=5,
        )

        user_prompt = (
            f"TOPIC: {inv.topic}\n\n"
            f"CHALLENGE FROM {ch.challenger_id} (ID: {ch.challenge_id}, Claim: {ch.target_claim_id}):\n"
            f"Disputed Claim: {ch.disputed_claim_text}\n"
            f"Challenge Argument: {ch.challenge_argument}\n"
            f"Requested Action: {ch.requested_action}\n\n"
            f"{packet}\n\n"
            f"TASK: Respond directly to this challenge. State your disposition (ACCEPTED / PARTIALLY_ACCEPTED / REJECTED_WITH_EVIDENCE / UNABLE_TO_DETERMINE) "
            f"and whether your position is MAINTAINED, PARTIALLY_REVISED, or FULLY_REVISED. Cite exact EVD-* IDs."
        )

        reb, _ = await invoke_structured(
            db,
            investigation_id=inv.investigation_id,
            agent_id=target_spec.advisor_id,
            system_prompt=target_spec.system_prompt,
            user_prompt=user_prompt,
            schema=RebuttalPayload,
            temperature=target_spec.temperature,
            max_tokens=1500,
            prompt_version=target_spec.prompt_version,
        )

        unverified = verify_cited_evidence_ids(reb.evidence_ids, valid_short_ids)
        ch.disposition = reb.disposition
        ch.status = "RESOLVED" if reb.disposition in {"ACCEPTED", "REJECTED_WITH_EVIDENCE"} else "UNRESOLVED"

        msg = DebateMessage(
            message_id=f"{inv.investigation_id}-MSG-R3-{idx:02d}",
            investigation_id=inv.investigation_id,
            round_number=3,
            sender=target_spec.advisor_id,
            receiver=ch.challenger_id,
            message_type="REBUTTAL",
            target_claim_id=ch.target_claim_id,
            argument=reb.response_argument,
            evidence_ids_json=reb.evidence_ids,
            unverified_evidence_ids_json=unverified,
            priority="HIGH",
            disposition=reb.disposition,
            position_change=reb.position_change,
        )
        db.add(msg)
        messages.append(msg)

    db.flush()
    return messages
