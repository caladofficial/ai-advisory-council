"""Schemas for the Eleventh AI — Independent Chief Judge & Verdict."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from app.schemas._coercion import coerce_str_list, coerce_to_str, coerce_unit_float


VerdictType = Literal[
    "GO",
    "CONDITIONAL_GO",
    "PILOT_FIRST",
    "PIVOT",
    "NO_GO",
    "INSUFFICIENT_EVIDENCE",
]


class ScorecardDimensionOut(BaseModel):
    dimension: str
    label: str
    weight: float
    score: float = Field(ge=0.0, le=100.0)
    weighted_contribution: float
    rationale: str
    evidence_ids: list[str] = Field(default_factory=list)


class HardBlockerOut(BaseModel):
    blocker_id: str = "BLK-01"
    category: str = "General"
    severity: Literal["CRITICAL", "HIGH"] = "CRITICAL"
    description: str = ""
    evidence_ids: list[str] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def _norm_blocker(cls, v: Any) -> Any:
        if isinstance(v, str):
            return {"description": v}
        if isinstance(v, dict):
            d = dict(v)
            if not d.get("description"):
                d["description"] = coerce_to_str(d.get("summary") or d.get("detail") or d.get("reason") or d.get("title") or d)
            sev = str(d.get("severity", "CRITICAL")).upper()
            d["severity"] = "HIGH" if "HIGH" in sev else "CRITICAL"
            d["evidence_ids"] = coerce_str_list(d.get("evidence_ids"))
            return d
        return v


class AdvisorAssessmentAction(BaseModel):
    advisor_id: str = "advisor"
    decision: Literal["ACCEPTED", "PARTIALLY_ACCEPTED", "REJECTED"] = "PARTIALLY_ACCEPTED"
    reason: str = ""

    @model_validator(mode="before")
    @classmethod
    def _norm_action(cls, v: Any) -> Any:
        if isinstance(v, str):
            return {"reason": v}
        if isinstance(v, dict):
            d = dict(v)
            if not d.get("reason"):
                d["reason"] = coerce_to_str(
                    d.get("rationale") or d.get("summary") or d.get("explanation") or d.get("assessment") or d.get("findings") or d
                )
            dec = str(d.get("decision") or d.get("status") or d.get("stance") or "PARTIALLY_ACCEPTED").upper()
            if "REJECT" in dec or "OPPOSE" in dec:
                d["decision"] = "REJECTED"
            elif "PART" in dec or "COND" in dec:
                d["decision"] = "PARTIALLY_ACCEPTED"
            elif "ACCEPT" in dec or "SUPPORT" in dec:
                d["decision"] = "ACCEPTED"
            else:
                d["decision"] = "PARTIALLY_ACCEPTED"
            return d
        return v


class RiskRegisterItemOut(BaseModel):
    risk_id: str = "RSK-01"
    title: str = "Identified Risk"
    category: str = "General"
    likelihood: str = "MEDIUM"
    impact: str = "MEDIUM"
    mitigation: str = ""
    owner_role: str = ""
    evidence_ids: list[str] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def _norm_risk(cls, v: Any) -> Any:
        if isinstance(v, str):
            return {"title": v[:120], "mitigation": v}
        if isinstance(v, dict):
            d = dict(v)
            if not d.get("title"):
                d["title"] = coerce_to_str(d.get("description") or d.get("risk") or "Identified Risk")[:120]
            if not d.get("mitigation"):
                d["mitigation"] = coerce_to_str(d.get("description") or d.get("recommendation") or d.get("title"))
            d["evidence_ids"] = coerce_str_list(d.get("evidence_ids"))
            return d
        return v


class MilestoneItemOut(BaseModel):
    phase: str = "Phase 1"
    title: str = "Milestone"
    owner_role: str = "Implementation Strategist"
    deliverable: str = ""
    acceptance_criterion: str = "Verified milestone acceptance"
    stop_condition: str = ""

    @model_validator(mode="before")
    @classmethod
    def _norm_milestone(cls, v: Any) -> Any:
        if isinstance(v, str):
            return {"title": v[:120], "deliverable": v}
        if isinstance(v, dict):
            d = dict(v)
            if not d.get("title"):
                d["title"] = coerce_to_str(d.get("deliverable") or d.get("description") or "Milestone")[:120]
            if not d.get("deliverable"):
                d["deliverable"] = coerce_to_str(d.get("description") or d.get("title"))
            return d
        return v


class JudgeVerdictPayload(BaseModel):
    verdict: VerdictType
    confidence: float = Field(ge=0.0, le=1.0)
    executive_summary: str
    decision_rationale: str
    dimension_scores: dict[str, float] = Field(
        default_factory=dict,
        description="Scores 0-100 for each of the 8 rubric dimensions.",
    )
    dimension_rationales: dict[str, str] = Field(default_factory=dict)
    best_arguments_for: list[str] = Field(default_factory=list)
    strongest_arguments_against: list[str] = Field(default_factory=list)
    established_facts: list[str] = Field(default_factory=list)
    uncertain_areas: list[str] = Field(default_factory=list)
    contradicted_claims: list[str] = Field(default_factory=list)
    hard_blockers: list[HardBlockerOut] = Field(default_factory=list)
    advisor_rationales: list[AdvisorAssessmentAction] = Field(default_factory=list)
    preserved_minority_opinions: list[str] = Field(default_factory=list)
    required_changes: list[str] = Field(default_factory=list)
    conditions_for_approval: list[str] = Field(default_factory=list)
    prerequisites_needed: list[str] = Field(default_factory=list)
    risk_register: list[RiskRegisterItemOut] = Field(default_factory=list)
    roadmap: list[MilestoneItemOut] = Field(default_factory=list)
    kpis: list[str] = Field(default_factory=list)
    remaining_questions: list[str] = Field(default_factory=list)
    evidence_ids_cited: list[str] = Field(default_factory=list)
    disagreed_with_majority: bool = False

    @field_validator("confidence", mode="before")
    @classmethod
    def _normalize_conf(cls, v: Any) -> float:
        return coerce_unit_float(v, 0.6)

    @field_validator("executive_summary", "decision_rationale", mode="before")
    @classmethod
    def _coerce_judge_text(cls, v: Any) -> str:
        return coerce_to_str(v)

    @field_validator(
        "best_arguments_for",
        "strongest_arguments_against",
        "established_facts",
        "uncertain_areas",
        "contradicted_claims",
        "preserved_minority_opinions",
        "required_changes",
        "conditions_for_approval",
        "prerequisites_needed",
        "kpis",
        "remaining_questions",
        "evidence_ids_cited",
        mode="before",
    )
    @classmethod
    def _coerce_judge_lists(cls, v: Any) -> list[str]:
        return coerce_str_list(v)

    @field_validator("verdict", mode="before")
    @classmethod
    def _normalize_verdict(cls, v: Any) -> str:
        s = str(v or "PILOT_FIRST").upper().strip().replace(" ", "_").replace("-", "_")
        if s in {"GO", "CONDITIONAL_GO", "PILOT_FIRST", "PIVOT", "NO_GO", "INSUFFICIENT_EVIDENCE"}:
            return s
        return "PILOT_FIRST"

    @field_validator("risk_register", mode="before")
    @classmethod
    def _coerce_risks(cls, v: Any) -> list[Any]:
        if not isinstance(v, list):
            return []
        out = []
        for idx, item in enumerate(v, start=1):
            if isinstance(item, str):
                out.append({"risk_id": f"RSK-{idx:02d}", "title": item[:100], "category": "General", "likelihood": "MEDIUM", "impact": "MEDIUM", "mitigation": item})
            elif isinstance(item, dict):
                out.append(item)
        return out

    @field_validator("roadmap", mode="before")
    @classmethod
    def _coerce_roadmap(cls, v: Any) -> list[Any]:
        if not isinstance(v, list):
            return []
        out = []
        for idx, item in enumerate(v, start=1):
            if isinstance(item, str):
                out.append({"phase": f"Phase {idx}", "title": item[:100], "owner_role": "Implementation Strategist", "deliverable": item, "acceptance_criterion": "Verified completion"})
            elif isinstance(item, dict):
                out.append(item)
        return out

    @field_validator("advisor_rationales", mode="before")
    @classmethod
    def _coerce_rationales(cls, v: Any) -> list[Any]:
        if not isinstance(v, list):
            return []
        out = []
        for idx, item in enumerate(v, start=1):
            if isinstance(item, str):
                out.append({"advisor_id": f"advisor_{idx}", "decision": "PARTIALLY_ACCEPTED", "reason": item})
            elif isinstance(item, dict):
                out.append(item)
        return out


class JudgeEvaluationOut(BaseModel):
    evaluation_id: str
    investigation_id: str
    model_used: str
    provider_used: str
    verdict: VerdictType
    feasibility_score: float
    confidence: float
    executive_summary: str
    decision_rationale: str
    scorecard: list[ScorecardDimensionOut] = Field(default_factory=list)
    hard_blockers: list[HardBlockerOut] = Field(default_factory=list)
    deterministic_checks: dict[str, object] = Field(default_factory=dict)
    best_arguments_for: list[str] = Field(default_factory=list)
    strongest_arguments_against: list[str] = Field(default_factory=list)
    advisor_rationales: list[AdvisorAssessmentAction] = Field(default_factory=list)
    preserved_minority_opinions: list[str] = Field(default_factory=list)
    required_changes: list[str] = Field(default_factory=list)
    conditions_for_approval: list[str] = Field(default_factory=list)
    prerequisites_needed: list[str] = Field(default_factory=list)
    risk_register: list[RiskRegisterItemOut] = Field(default_factory=list)
    roadmap: list[MilestoneItemOut] = Field(default_factory=list)
    kpis: list[str] = Field(default_factory=list)
    remaining_questions: list[str] = Field(default_factory=list)
    disagreed_with_majority: bool = False
    created_at: datetime
