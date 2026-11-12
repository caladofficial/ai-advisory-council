"""Blind Stage-5 Independent Advisor Runner & Round-4 Final Position Updater (lock-free async I/O)."""

from __future__ import annotations

import json
import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agents.advisor_factory import AdvisorSpec
from app.agents.sandbox_tools import build_financial_sandbox_summary
from app.database.models import (
    AdvisorReport,
    AdvisorSession,
    DebateChallenge,
    DebateMessage,
    EvidenceChunk,
    Investigation,
    InvestigationAssumption,
    PrivateNote,
)
from app.database.session import session_scope
from app.evidence.retrieval import retrieve_evidence_for_advisor
from app.models.router import invoke_structured
from app.schemas.advisor import AdvisorReportPayload


def verify_cited_evidence_ids(
    cited_ids: list[str],
    valid_short_ids: set[str],
) -> list[str]:
    """Return any cited EVD-* IDs that do NOT exist in the investigation's retrieved evidence."""
    flagged: list[str] = []
    for raw in cited_ids:
        norm = raw.strip().upper()
        m = re.search(r"EVD-\d+", norm)
        short = m.group(0) if m else norm
        if short not in valid_short_ids:
            flagged.append(raw)
    return flagged


def ensure_advisor_session(
    db: Session,
    inv: Investigation,
    spec: AdvisorSpec,
) -> AdvisorSession:
    session_id = f"{inv.investigation_id}-{spec.advisor_id}"
    sess = db.get(AdvisorSession, session_id)
    if sess is None:
        sess = AdvisorSession(
            session_id=session_id,
            investigation_id=inv.investigation_id,
            advisor_id=spec.advisor_id,
            advisor_name=spec.name,
            advisor_role=spec.role,
            status="idle",
            prompt_version=spec.prompt_version,
        )
        db.add(sess)
        db.flush()
    return sess


async def run_advisor_initial_analysis_stateless(
    investigation_id: str,
    spec: AdvisorSpec,
) -> AdvisorReportPayload:
    """Execute Stage-5 blind initial assessment without holding DB write locks during LLM HTTP I/O."""
    with session_scope() as db:
        inv = db.get(Investigation, investigation_id)
        assert inv is not None
        sess = ensure_advisor_session(db, inv, spec)

        existing_initial = db.scalars(
            select(AdvisorReport).where(
                AdvisorReport.investigation_id == investigation_id,
                AdvisorReport.advisor_id == spec.advisor_id,
                AdvisorReport.phase == "initial",
            )
        ).first()
        if existing_initial is not None:
            return AdvisorReportPayload.model_validate(existing_initial.report_json)

        sess.status = "analyzing"
        all_chunks = list(
            db.scalars(select(EvidenceChunk).where(EvidenceChunk.investigation_id == investigation_id)).all()
        )
        valid_short_ids = {
            ch.evidence_id.replace(f"{investigation_id}-", "").upper() for ch in all_chunks
        }
        _, _, _, evidence_packet = retrieve_evidence_for_advisor(
            db,
            investigation_id,
            lens_keywords=spec.evidence_keywords,
            preferred_source_types=spec.evidence_source_types,
            topic=inv.topic,
            top_k=5,
        )
        assumptions = [
            a.assumption_text
            for a in db.scalars(
                select(InvestigationAssumption).where(InvestigationAssumption.investigation_id == investigation_id)
            ).all()
        ]
        sandbox_note = ""
        if "python_calculator" in spec.tool_permissions:
            sandbox_note = "\n\n" + build_financial_sandbox_summary(inv.budget)

        user_prompt = (
            f"INVESTIGATION BRIEF:\n{json.dumps(inv.brief_json or {'topic': inv.topic}, indent=2)}\n\n"
            f"READINESS STATUS: {inv.readiness_status} ({inv.readiness_score}/100)\n"
            f"DOCUMENTED ASSUMPTIONS / GAPS:\n" + "\n".join(f"- {a}" for a in assumptions) + "\n\n"
            f"{evidence_packet}{sandbox_note}\n\n"
            f"TASK: Conduct your BLIND independent initial assessment strictly from your {spec.name} perspective. "
            f"Cite exact EVD-* IDs from the packet above in evidence_ids_cited and key_claims. "
            f"You must identify at least one weakness in your own view (self_identified_weakness) and record isolated private_working_notes."
        )

    # Stateless LLM call (ZERO SQLite locks held during HTTP request)
    payload, llm_res = await invoke_structured(
        None,
        investigation_id=investigation_id,
        agent_id=spec.advisor_id,
        system_prompt=spec.system_prompt,
        user_prompt=user_prompt,
        schema=AdvisorReportPayload,
        temperature=spec.temperature,
        max_tokens=spec.max_output_tokens,
        prompt_version=spec.prompt_version,
    )

    all_cited = list(payload.evidence_ids_cited)
    for kc in payload.key_claims:
        all_cited.extend(kc.evidence_ids)
    unverified = verify_cited_evidence_ids(all_cited, valid_short_ids)

    with session_scope() as db:
        session_id = f"{investigation_id}-{spec.advisor_id}"
        sess = db.get(AdvisorSession, session_id)
        if sess is not None:
            sess.assigned_provider = llm_res.provider
            sess.assigned_model = llm_res.model_id
            sess.unverified_citations_json = sorted(set(unverified))
            sess.status = "initial_complete"

        if payload.private_working_notes:
            db.add(
                PrivateNote(
                    investigation_id=investigation_id,
                    advisor_id=spec.advisor_id,
                    stage="INDEPENDENT_ANALYSIS",
                    note_text=payload.private_working_notes,
                )
            )
        db.add(
            AdvisorReport(
                investigation_id=investigation_id,
                session_id=session_id,
                advisor_id=spec.advisor_id,
                phase="initial",
                stance=payload.stance,
                confidence=payload.confidence,
                report_json=payload.model_dump(),
            )
        )
    return payload


async def run_advisor_final_submission_stateless(
    investigation_id: str,
    spec: AdvisorSpec,
) -> AdvisorReportPayload:
    """Round 4: Advisor submits final assessment without holding DB locks across LLM HTTP calls."""
    with session_scope() as db:
        inv = db.get(Investigation, investigation_id)
        assert inv is not None
        sess = ensure_advisor_session(db, inv, spec)

        existing_final = db.scalars(
            select(AdvisorReport).where(
                AdvisorReport.investigation_id == investigation_id,
                AdvisorReport.advisor_id == spec.advisor_id,
                AdvisorReport.phase == "final",
            )
        ).first()
        if existing_final is not None:
            return AdvisorReportPayload.model_validate(existing_final.report_json)

        initial_row = db.scalars(
            select(AdvisorReport).where(
                AdvisorReport.investigation_id == investigation_id,
                AdvisorReport.advisor_id == spec.advisor_id,
                AdvisorReport.phase == "initial",
            )
        ).first()
        initial_payload = initial_row.report_json if initial_row else {}

        challenges = list(
            db.scalars(
                select(DebateChallenge).where(
                    DebateChallenge.investigation_id == investigation_id,
                    (DebateChallenge.target_advisor_id == spec.advisor_id)
                    | (DebateChallenge.challenger_id == spec.advisor_id),
                )
            ).all()
        )
        rebuttals = list(
            db.scalars(
                select(DebateMessage).where(
                    DebateMessage.investigation_id == investigation_id,
                    DebateMessage.round_number.in_([2, 3]),
                )
            ).all()
        )
        private_notes = "\n".join(
            n.note_text
            for n in db.scalars(
                select(PrivateNote).where(
                    PrivateNote.investigation_id == investigation_id,
                    PrivateNote.advisor_id == spec.advisor_id,
                )
            ).all()
        )
        all_chunks = list(
            db.scalars(select(EvidenceChunk).where(EvidenceChunk.investigation_id == investigation_id)).all()
        )
        valid_short_ids = {
            ch.evidence_id.replace(f"{investigation_id}-", "").upper() for ch in all_chunks
        }
        sess.status = "finalizing"

        debate_summary = "\n".join(
            f"- [R{m.round_number} | {m.sender} -> {m.receiver} | {m.message_type}] {m.argument[:320]} (Evidence: {', '.join(m.evidence_ids_json)})"
            for m in rebuttals[:18]
        )
        challenge_summary = "\n".join(
            f"- Challenge {c.challenge_id} (P={c.priority_score}): {c.challenger_id} challenged {c.target_advisor_id}: {c.challenge_argument}"
            for c in challenges[:8]
        )

        user_prompt = (
            f"TOPIC: {inv.topic}\n\n"
            f"YOUR INITIAL REPORT (Blind Stage 5):\n{json.dumps(initial_payload, indent=2)[:2600]}\n\n"
            f"YOUR ISOLATED PRIVATE NOTES:\n{private_notes or '(none)'}\n\n"
            f"RELEVANT DEBATE CHALLENGES:\n{challenge_summary or '(none)'}\n\n"
            f"DEBATE EXCHANGES:\n{debate_summary or '(none)'}\n\n"
            f"TASK: Submit your Round-4 FINAL assessment. Revise ONLY if debate evidence warrants it — NEVER bow to peer pressure or majority agreement without evidence."
        )

    payload, _ = await invoke_structured(
        None,
        investigation_id=investigation_id,
        agent_id=spec.advisor_id,
        system_prompt=spec.system_prompt,
        user_prompt=user_prompt,
        schema=AdvisorReportPayload,
        temperature=spec.temperature,
        max_tokens=spec.max_output_tokens,
        prompt_version=spec.prompt_version,
    )

    init_stance = initial_payload.get("stance")
    init_conf = float(initial_payload.get("confidence", 0.5))
    if init_stance and payload.stance != init_stance:
        pos_changed = "FULLY_REVISED"
    elif abs(payload.confidence - init_conf) >= 0.15 or payload.recommendations != initial_payload.get("recommendations"):
        pos_changed = "PARTIALLY_REVISED"
    else:
        pos_changed = "UNCHANGED"

    extra_flags = verify_cited_evidence_ids(payload.evidence_ids_cited, valid_short_ids)

    with session_scope() as db:
        session_id = f"{investigation_id}-{spec.advisor_id}"
        sess = db.get(AdvisorSession, session_id)
        if sess is not None:
            sess.position_changed = pos_changed
            sess.status = "completed"
            if extra_flags:
                sess.unverified_citations_json = sorted(set((sess.unverified_citations_json or []) + extra_flags))

        db.add(
            AdvisorReport(
                investigation_id=investigation_id,
                session_id=session_id,
                advisor_id=spec.advisor_id,
                phase="final",
                stance=payload.stance,
                confidence=payload.confidence,
                report_json=payload.model_dump(),
            )
        )
    return payload
