"""LangGraph state schema for the AI Advisory Council execution lifecycle."""

from __future__ import annotations

from typing import TypedDict


class InvestigationState(TypedDict, total=False):
    investigation_id: str
    research_cycle: int
    max_research_cycles: int
    readiness_allowed: bool
    readiness_status: str
    force_proceed_warnings: bool
    halted_status: str | None
    error_message: str | None
