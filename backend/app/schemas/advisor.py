"""Schemas for the 10 Independent Advisors and structured advisor reports."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

from app.schemas._coercion import coerce_str_list, coerce_to_str, coerce_unit_float


class AdvisorClaimItem(BaseModel):
    claim_id: str = Field(default="")
    statement: str
    classification: Literal["FACT", "ESTIMATE", "ASSUMPTION", "JUDGMENT"] = "JUDGMENT"
    evidence_ids: list[str] = Field(default_factory=list)

    @field_validator("statement", mode="before")
    @classmethod
    def _v_stmt(cls, v: Any) -> str:
        return coerce_to_str(v)

    @field_validator("evidence_ids", mode="before")
    @classmethod
    def _v_evd(cls, v: Any) -> list[str]:
        return coerce_str_list(v)

    @field_validator("classification", mode="before")
    @classmethod
    def _v_cls(cls, v: Any) -> str:
        s = str(v or "JUDGMENT").upper().strip()
        return s if s in {"FACT", "ESTIMATE", "ASSUMPTION", "JUDGMENT"} else "JUDGMENT"


class AdvisorReportPayload(BaseModel):
    """Structured output returned by every advisor during Stage 5 and Round 4."""

    interpretation: str = Field(default="", description="Advisor's scoped interpretation of the decision question.")
    stance: Literal["SUPPORT", "CONDITIONAL", "OPPOSE", "INSUFFICIENT_EVIDENCE"] = "CONDITIONAL"
    confidence: float = Field(ge=0.0, le=1.0, default=0.6)
    executive_findings: str = Field(default="", description="Concise core findings from this specialist lens.")
    key_claims: list[AdvisorClaimItem] = Field(default_factory=list)
    advantages: list[str] = Field(default_factory=list)
    risks_and_weaknesses: list[str] = Field(default_factory=list)
    self_identified_weakness: str = Field(
        default="Potential gaps in unverified assumptions.",
        description="Mandatory weakness or blind spot in this advisor's own position.",
    )
    assumptions: list[str] = Field(default_factory=list)
    missing_evidence: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    evidence_ids_cited: list[str] = Field(default_factory=list)
    private_working_notes: str = Field(
        default="",
        description="Private isolated notes never shown to other advisors or the Judge.",
    )

    @field_validator("confidence", mode="before")
    @classmethod
    def _normalize_confidence(cls, v: Any) -> float:
        return coerce_unit_float(v, 0.6)

    @field_validator("interpretation", "executive_findings", "self_identified_weakness", "private_working_notes", mode="before")
    @classmethod
    def _coerce_strings(cls, v: Any) -> str:
        return coerce_to_str(v)

    @field_validator("advantages", "risks_and_weaknesses", "assumptions", "missing_evidence", "recommendations", "evidence_ids_cited", mode="before")
    @classmethod
    def _coerce_lists(cls, v: Any) -> list[str]:
        return coerce_str_list(v)

    @field_validator("stance", mode="before")
    @classmethod
    def _normalize_stance(cls, v: Any) -> str:
        s = str(v or "CONDITIONAL").upper().strip().replace(" ", "_")
        if s in {"SUPPORT", "CONDITIONAL", "OPPOSE", "INSUFFICIENT_EVIDENCE"}:
            return s
        if "OPPOSE" in s or "NO" in s:
            return "OPPOSE"
        if "SUPPORT" in s or "YES" in s or "GO" in s:
            return "SUPPORT"
        return "CONDITIONAL"

    @field_validator("key_claims", mode="before")
    @classmethod
    def _coerce_claims(cls, v: Any) -> list[Any]:
        if not isinstance(v, list):
            return []
        out = []
        for idx, item in enumerate(v, start=1):
            if isinstance(item, str):
                out.append({"claim_id": f"C{idx}", "statement": item, "classification": "JUDGMENT", "evidence_ids": []})
            elif isinstance(item, dict):
                out.append(item)
        return out


class AdvisorProfileOut(BaseModel):
    advisor_id: str
    name: str
    title: str
    role: str
    priority: str
    temperature: float
    preferred_capability: str
    tool_permissions: list[str] = Field(default_factory=list)
    evaluation_criteria: list[str] = Field(default_factory=list)
    bias_controls: list[str] = Field(default_factory=list)


class AdvisorSessionOut(BaseModel):
    session_id: str
    investigation_id: str
    advisor_id: str
    advisor_name: str
    advisor_role: str
    status: str
    assigned_provider: str
    assigned_model: str
    prompt_version: str
    initial_report: AdvisorReportPayload | None = None
    final_report: AdvisorReportPayload | None = None
    position_changed: str = "UNCHANGED"  # UNCHANGED | PARTIALLY_REVISED | FULLY_REVISED
    unverified_citations: list[str] = Field(default_factory=list)
    private_notes: str = ""
    updated_at: datetime
