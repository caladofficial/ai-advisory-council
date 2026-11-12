"""Schemas for Pre-Debate Intelligence, Requirements, and Readiness Gate."""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class ReadinessStatus(str, Enum):
    READY = "READY"
    READY_WITH_WARNINGS = "READY_WITH_WARNINGS"
    NEEDS_MORE_RESEARCH = "NEEDS_MORE_RESEARCH"
    NEEDS_USER_INPUT = "NEEDS_USER_INPUT"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"


class RequirementItemOut(BaseModel):
    name: str
    category: str
    requirement_type: str  # mandatory_user_input | researchable | operational_dependency | optional
    status: str  # complete | partial | missing
    blocking: bool = False
    detail: str = ""


class ResourceEstimateOut(BaseModel):
    estimated_advisor_calls: int
    estimated_total_tokens: int
    estimated_cost_usd: float = 0.0
    cost_policy_mode: str = "zero_paid"
    estimated_duration_seconds: int
    available_models_count: int
    providers_healthy: list[str] = Field(default_factory=list)
    fallback_ready: bool = True
    warnings: list[str] = Field(default_factory=list)


class ReadinessRubricOut(BaseModel):
    topic_clarity: float = 0.0
    prerequisite_completeness: float = 0.0
    source_coverage: float = 0.0
    source_quality: float = 0.0
    information_freshness: float = 0.0
    contradictions_identified: float = 0.0
    total_score: float = 0.0


class PrerequisiteAssessmentOut(BaseModel):
    investigation_id: str
    readiness_status: ReadinessStatus
    readiness_score: float
    rubric: ReadinessRubricOut
    mandatory_items: list[RequirementItemOut] = Field(default_factory=list)
    research_gaps: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    clarifying_questions: list[str] = Field(default_factory=list)
    hard_gates_triggered: list[str] = Field(default_factory=list)
    resource_estimate: ResourceEstimateOut
    allowed_next_stage: bool
    raw_metadata: dict[str, Any] = Field(default_factory=dict)
