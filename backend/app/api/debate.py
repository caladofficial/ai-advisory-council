"""Debate messages, Challenge Graph (P = I * U * R), and unresolved disagreements routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.models import DebateChallenge, DebateMessage, DebateRound, Investigation
from app.database.session import get_db
from app.schemas.debate import ChallengeEdgeOut, DebateMessageOut, DebateTranscriptOut

router = APIRouter(prefix="/api/investigations/{investigation_id}", tags=["debate"])


@router.get("/debate", response_model=DebateTranscriptOut)
def get_debate_transcript(investigation_id: str, db: Session = Depends(get_db)):
    if db.get(Investigation, investigation_id) is None:
        raise HTTPException(status_code=404, detail="Investigation not found")

    rounds = list(db.scalars(select(DebateRound).where(DebateRound.investigation_id == investigation_id)).all())
    msgs = list(
        db.scalars(
            select(DebateMessage)
            .where(DebateMessage.investigation_id == investigation_id)
            .order_by(DebateMessage.round_number, DebateMessage.created_at)
        ).all()
    )
    challenges = list(
        db.scalars(
            select(DebateChallenge)
            .where(DebateChallenge.investigation_id == investigation_id)
            .order_by(DebateChallenge.priority_score.desc())
        ).all()
    )
    unresolved = [
        f"{c.challenger_id} vs {c.target_advisor_id} ({c.target_claim_id}): {c.challenge_argument}"
        for c in challenges
        if c.status != "RESOLVED"
    ]

    return DebateTranscriptOut(
        investigation_id=investigation_id,
        total_rounds=len(rounds),
        messages=[
            DebateMessageOut(
                message_id=m.message_id,
                investigation_id=m.investigation_id,
                round_number=m.round_number,
                sender=m.sender,
                receiver=m.receiver,
                message_type=m.message_type,
                target_claim_id=m.target_claim_id,
                argument=m.argument,
                evidence_ids=m.evidence_ids_json or [],
                unverified_evidence_ids=m.unverified_evidence_ids_json or [],
                requested_action=m.requested_action,
                priority=m.priority,
                disposition=m.disposition,
                position_change=m.position_change,
                created_at=m.created_at,
            )
            for m in msgs
        ],
        challenges=[
            ChallengeEdgeOut(
                challenge_id=c.challenge_id,
                investigation_id=c.investigation_id,
                round_number=c.round_number,
                challenger_id=c.challenger_id,
                target_advisor_id=c.target_advisor_id,
                target_claim_id=c.target_claim_id,
                disputed_claim_text=c.disputed_claim_text,
                challenge_argument=c.challenge_argument,
                requested_action=c.requested_action,
                impact_score=c.impact_score,
                uncertainty_score=c.uncertainty_score,
                relevance_score=c.relevance_score,
                priority_score=c.priority_score,
                status=c.status,
                disposition=c.disposition,
                evidence_ids=c.evidence_ids_json or [],
            )
            for c in challenges
        ],
        unresolved_disagreements=unresolved,
    )
