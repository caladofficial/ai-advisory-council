"""Schemas for investigation lifecycle, briefs, control commands, and progress."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class InvestigationStatus(str, Enum):
    CREATED = "CREATED"
    INTAKE_VALIDATION = "INTAKE_VALIDATION"
    PLANNING = "PLANNING"
    PREREQUISITE_CHECK = "PREREQUISITE_CHECK"
    RESEARCHING = "RESEARCHING"
    EVIDENCE_VERIFICATION = "EVIDENCE_VERIFICATION"
    READINESS_GATE = "READINESS_GATE"
    INDEPENDENT_ANALYSIS = "INDEPENDENT_ANALYSIS"
    DEBATE_PREPARATION = "DEBATE_PREPARATION"
    OPENING_ROUND = "OPENING_ROUND"
    CHALLENGE_ROUND = "CHALLENGE_ROUND"
    REBUTTAL_ROUND = "REBUTTAL_ROUND"
    FINAL_ADVISOR_REPORTS = "FINAL_ADVISOR_REPORTS"
    CHIEF_JUDGE = "CHIEF_JUDGE"
    REPORT_GENERATION = "REPORT_GENERATION"
    COMPLETED = "COMPLETED"
    # Recovery / terminal states
    NEEDS_USER_INPUT = "NEEDS_USER_INPUT"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    PAUSED = "PAUSED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class InvestigationMode(str, Enum):
    GENERAL_DECISION = "general_decision"
    BUSINESS_FEASIBILITY = "business_feasibility"
    TECHNICAL_FEASIBILITY = "technical_feasibility"
    SCIENTIFIC_RESEARCH = "scientific_research"
    PRODUCT_EVALUATION = "product_evaluation"
    POLICY_ANALYSIS = "policy_analysis"


class ExecutionProfile(str, Enum):
    FULL_COUNCIL = "full_10_plus_1"
    PROTOTYPE_THREE = "prototype_3_plus_1"


ORDERED_PIPELINE_STAGES = [
    InvestigationStatus.INTAKE_VALIDATION,
    InvestigationStatus.PLANNING,
    InvestigationStatus.PREREQUISITE_CHECK,
    InvestigationStatus.RESEARCHING,
    InvestigationStatus.EVIDENCE_VERIFICATION,
    InvestigationStatus.READINESS_GATE,
    InvestigationStatus.INDEPENDENT_ANALYSIS,
    InvestigationStatus.DEBATE_PREPARATION,
    InvestigationStatus.OPENING_ROUND,
    InvestigationStatus.CHALLENGE_ROUND,
    InvestigationStatus.REBUTTAL_ROUND,
    InvestigationStatus.FINAL_ADVISOR_REPORTS,
    InvestigationStatus.CHIEF_JUDGE,
    InvestigationStatus.REPORT_GENERATION,
    InvestigationStatus.COMPLETED,
]


class InvestigationCreate(BaseModel):
    topic: str = Field(..., min_length=5, max_length=2000)
    objective: str = Field(default="Evaluate overall feasibility, risks, and implementation requirements", max_length=1000)
    mode: InvestigationMode = InvestigationMode.GENERAL_DECISION
    execution_profile: ExecutionProfile = ExecutionProfile.FULL_COUNCIL
    geography: str = Field(default="Global", max_length=200)
    time_horizon: str = Field(default="12 months", max_length=120)
    budget: str = Field(default="", max_length=200)
    target_users: str = Field(default="", max_length=500)
    constraints: list[str] = Field(default_factory=list)
    enabled_connectors: list[str] = Field(
        default_factory=lambda: ["openalex", "crossref", "arxiv", "github", "huggingface", "wikipedia", "web_search"]
    )
    auto_start: bool = False


class ClarificationSubmit(BaseModel):
    answers: dict[str, str] = Field(default_factory=dict)
    additional_constraints: list[str] = Field(default_factory=list)
    proceed_with_warnings: bool = True


class AdditionalResearchRequest(BaseModel):
    query: str = Field(..., min_length=3, max_length=500)
    connectors: list[str] = Field(default_factory=lambda: ["web_search", "openalex", "github"])


class InvestigationRead(BaseModel):
    investigation_id: str
    topic: str
    objective: str
    mode: InvestigationMode
    execution_profile: ExecutionProfile
    domain: str
    geography: str
    time_horizon: str
    budget: str
    target_users: str
    constraints: list[str]
    enabled_connectors: list[str]
    status: InvestigationStatus
    current_stage: str
    progress_percent: int
    readiness_score: float | None = None
    readiness_status: str | None = None
    verdict: str | None = None
    feasibility_score: float | None = None
    error_message: str | None = None
    brief_json: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime


class ProgressEvent(BaseModel):
    investigation_id: str
    status: str
    stage: str
    progress_percent: int
    message: str
    advisor_statuses: dict[str, str] = Field(default_factory=dict)
    timestamp: datetime
