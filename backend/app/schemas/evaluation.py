"""Schemas for Evaluation Lab, Independence Analysis, Audit Logs, and Usage Ledger."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class IndependenceMetricsOut(BaseModel):
    investigation_id: str
    advisor_count: int
    stance_distribution: dict[str, int] = Field(default_factory=dict)
    pairwise_claim_overlap: float = 0.0
    lexical_similarity_mean: float = 0.0
    distinct_model_families: int = 1
    divergence_score: float = 0.0  # 0-100 higher means genuinely independent initial reports
    correlated_risk_warning: str | None = None


class BenchmarkCaseResult(BaseModel):
    case_id: str
    name: str
    category: str
    passed: bool
    score: float
    details: str


class BenchmarkRunOut(BaseModel):
    run_id: str
    target: str
    total_cases: int
    passed_cases: int
    overall_score: float
    results: list[BenchmarkCaseResult] = Field(default_factory=list)
    executed_at: datetime


class AuditEventOut(BaseModel):
    event_id: int
    investigation_id: str | None = None
    actor: str
    event_type: str
    stage: str
    summary: str
    payload: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime


class ModelUsageOut(BaseModel):
    usage_id: int
    investigation_id: str | None = None
    agent_id: str
    provider: str
    model_id: str
    prompt_version: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    latency_ms: int
    estimated_cost_usd: float = 0.0
    status: str
    error_message: str | None = None
    created_at: datetime
