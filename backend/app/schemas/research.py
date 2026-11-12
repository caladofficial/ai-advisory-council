"""Schemas for research planner questions, tasks, and collected sources."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class ResearchQuestionOut(BaseModel):
    question_id: str
    investigation_id: str
    query_family: str
    question: str
    search_query: str
    connector: str
    priority: str
    assigned_advisors: list[str] = Field(default_factory=list)


class ResearchTaskOut(BaseModel):
    task_id: str
    investigation_id: str
    connector: str
    query: str
    status: str
    items_found: int = 0
    error_message: str | None = None
    duration_ms: int = 0
    created_at: datetime


class SourceOut(BaseModel):
    source_id: str
    investigation_id: str
    url: str
    canonical_url: str
    title: str
    publisher: str
    author: str
    published_at: str | None = None
    retrieved_at: datetime
    source_type: str
    domain: str
    canonical_identifier: str | None = None
    license_name: str | None = None
    content_hash: str
    is_duplicate: bool = False
    syndicated_from_id: str | None = None
    reliability_score: float = 0.0
    metadata_json: dict[str, Any] = Field(default_factory=dict)
