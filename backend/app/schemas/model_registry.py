"""Schemas for Model Registry, Free API Catalog, Health Checks, and Quota Policy."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class CostPolicyOut(BaseModel):
    mode: str
    allow_paid_providers: bool
    allow_credit_card_fallback: bool
    allow_over_quota_requests: bool


class ProviderOut(BaseModel):
    provider_id: str
    display_name: str
    protocol: str
    base_url: str
    api_key_url: str = ""
    is_free_tier: bool = True
    requires_credit_card: bool = False
    has_key_configured: bool = False
    masked_key: str = ""
    default_rpm: int = 20
    default_rpd: int = 1000
    requests_today: int = 0
    free_models_count: int = 0
    max_context: int = 0
    status: str = "Operational"
    tagline: str = ""


class ModelRegistryEntryOut(BaseModel):
    id: str
    provider: str
    model_id: str
    display_name: str
    execution_mode: str  # local | free_hosted
    family: str
    capabilities: list[str] = Field(default_factory=list)
    supports_tools: bool = False
    supports_json: bool = True
    context_window: int | None = None
    rate_limit_note: str = ""
    is_free: bool = True
    availability_status: str = "untested"  # healthy | untested | degraded | unavailable
    last_health_check: datetime | None = None
    quality_score: float | None = None
    latency_ms: float | None = None
    enabled: bool = True


class HealthCheckRequest(BaseModel):
    provider: str | None = None
    model_id: str | None = None
    test_json: bool = True


class HealthCheckResult(BaseModel):
    provider: str
    model_id: str
    status: str  # healthy | degraded | unavailable | skipped_no_key
    latency_ms: float | None = None
    supports_json_verified: bool = False
    error: str | None = None
    checked_at: datetime


class ApiKeyConfigureIn(BaseModel):
    provider_id: str
    api_key: str = Field(..., min_length=4, max_length=512)


class AdvisorModelOverrideIn(BaseModel):
    advisor_id: str
    provider: str
    model_id: str
    extra: dict[str, Any] = Field(default_factory=dict)
