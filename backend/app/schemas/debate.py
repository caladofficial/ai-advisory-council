"""Schemas for Moderator, Challenge Graph, Debate Messages, and Rebuttals."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

from app.schemas._coercion import coerce_str_list, coerce_to_str


MessageType = Literal[
    "OPENING",
    "CHALLENGE",
    "COUNTERARGUMENT",
    "REBUTTAL",
    "EVIDENCE_REQUEST",
    "REVISION",
    "AGREEMENT",
    "DISSENT",
    "FINAL_POSITION",
    "MODERATOR_NOTE",
]


class RebuttalPayload(BaseModel):
    disposition: Literal["ACCEPTED", "PARTIALLY_ACCEPTED", "REJECTED_WITH_EVIDENCE", "UNABLE_TO_DETERMINE"] = "PARTIALLY_ACCEPTED"
    position_change: Literal["MAINTAINED", "PARTIALLY_REVISED", "FULLY_REVISED"] = "MAINTAINED"
    response_argument: str = ""
    evidence_ids: list[str] = Field(default_factory=list)
    revised_recommendation: str = ""
    calculation_summary: str = ""

    @field_validator("disposition", mode="before")
    @classmethod
    def _v_disp(cls, v: Any) -> str:
        s = str(v or "PARTIALLY_ACCEPTED").upper().strip().replace(" ", "_")
        if s in {"ACCEPTED", "PARTIALLY_ACCEPTED", "REJECTED_WITH_EVIDENCE", "UNABLE_TO_DETERMINE"}:
            return s
        if "REJECT" in s:
            return "REJECTED_WITH_EVIDENCE"
        if "ACCEPT" in s:
            return "PARTIALLY_ACCEPTED"
        return "UNABLE_TO_DETERMINE"

    @field_validator("position_change", mode="before")
    @classmethod
    def _v_pos(cls, v: Any) -> str:
        s = str(v or "MAINTAINED").upper().strip().replace(" ", "_")
        if s in {"MAINTAINED", "PARTIALLY_REVISED", "FULLY_REVISED"}:
            return s
        return "PARTIALLY_REVISED" if "PART" in s else "MAINTAINED"

    @field_validator("response_argument", "revised_recommendation", "calculation_summary", mode="before")
    @classmethod
    def _v_txt(cls, v: Any) -> str:
        return coerce_to_str(v)

    @field_validator("evidence_ids", mode="before")
    @classmethod
    def _v_ev(cls, v: Any) -> list[str]:
        return coerce_str_list(v)


class ChallengeCandidate(BaseModel):
    challenger_id: str
    target_advisor_id: str
    target_claim_id: str = "CLAIM-001"
    disputed_claim_text: str = ""
    challenge_argument: str = ""
    evidence_ids: list[str] = Field(default_factory=list)
    requested_action: str = "Provide supporting evidence or revise position."
    impact_score: int = Field(ge=1, le=5, default=4)
    uncertainty_score: int = Field(ge=1, le=5, default=3)
    relevance_score: int = Field(ge=1, le=5, default=4)

    @field_validator("disputed_claim_text", "challenge_argument", "requested_action", mode="before")
    @classmethod
    def _v_ctxt(cls, v: Any) -> str:
        return coerce_to_str(v)

    @field_validator("evidence_ids", mode="before")
    @classmethod
    def _v_cev(cls, v: Any) -> list[str]:
        return coerce_str_list(v)

    @field_validator("impact_score", "uncertainty_score", "relevance_score", mode="before")
    @classmethod
    def _v_clamp(cls, v: Any) -> int:
        try:
            return max(1, min(5, int(round(float(v)))))
        except (TypeError, ValueError):
            return 3


class ChallengeEdgeOut(BaseModel):
    challenge_id: str
    investigation_id: str
    round_number: int
    challenger_id: str
    target_advisor_id: str
    target_claim_id: str
    disputed_claim_text: str
    challenge_argument: str
    requested_action: str
    impact_score: int
    uncertainty_score: int
    relevance_score: int
    priority_score: int
    status: str  # OPEN | RESOLVED | UNRESOLVED
    disposition: str | None = None
    evidence_ids: list[str] = Field(default_factory=list)


class DebateMessageOut(BaseModel):
    message_id: str
    investigation_id: str
    round_number: int
    sender: str
    receiver: str
    message_type: str
    target_claim_id: str | None = None
    argument: str
    evidence_ids: list[str] = Field(default_factory=list)
    unverified_evidence_ids: list[str] = Field(default_factory=list)
    requested_action: str | None = None
    priority: str = "MEDIUM"
    disposition: str | None = None
    position_change: str | None = None
    created_at: datetime


class DebateTranscriptOut(BaseModel):
    investigation_id: str
    total_rounds: int
    messages: list[DebateMessageOut] = Field(default_factory=list)
    challenges: list[ChallengeEdgeOut] = Field(default_factory=list)
    unresolved_disagreements: list[str] = Field(default_factory=list)
