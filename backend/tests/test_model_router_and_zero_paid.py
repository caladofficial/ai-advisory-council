"""Acceptance tests for Zero-Paid Cost Policy, awesome-freellm-apis import, and provider fallback."""

from __future__ import annotations

import pytest

from app.models.catalog_importer import load_freellm_catalog
from app.models.quota_manager import CostPolicyViolationError, quota_manager
from app.models.router import invoke_structured
from app.models.provider_adapters import LLMCallResult
from app.schemas.model_registry import HealthCheckRequest
from pydantic import BaseModel


class _DummyOut(BaseModel):
    answer: str


def test_zero_paid_blocks_paid_providers_and_non_free_openrouter():
    with pytest.raises(CostPolicyViolationError):
        quota_manager.assert_zero_paid_allowed("openai_paid", "gpt-4o")
    with pytest.raises(CostPolicyViolationError):
        quota_manager.assert_zero_paid_allowed("openrouter", "anthropic/claude-3.7-sonnet")
    quota_manager.assert_zero_paid_allowed("openrouter", "deepseek/deepseek-r1:free")
    quota_manager.assert_zero_paid_allowed("ollama", "llama3.2:3b")


def test_freellm_catalog_imported():
    cat = load_freellm_catalog()
    assert cat["status"]["summary"]["total_providers"] >= 30
    assert len(cat["models"]) >= 50


@pytest.mark.asyncio
async def test_router_provider_fallback_records_usage(isolated_app, monkeypatch):
    _, db_session = isolated_app
    calls: list[str] = []

    async def fake_call(*, provider: str, model_id: str, **kwargs):
        calls.append(provider)
        if provider != "ollama":
            raise RuntimeError("Simulated hosted quota limit 429")
        return LLMCallResult(
            content='{"answer": "Fallback succeeded on local Ollama"}',
            provider=provider,
            model_id=model_id,
            prompt_tokens=100,
            completion_tokens=20,
            latency_ms=42,
        )

    monkeypatch.setattr("app.models.router.call_chat_completion", fake_call)
    monkeypatch.setattr(
        "app.models.router.resolve_candidate_models",
        lambda db, aid: [("groq", "llama-3.3-70b-versatile"), ("ollama", "llama3.2:3b")],
    )

    with db_session.session_scope() as db:
        parsed, res = await invoke_structured(
            db,
            investigation_id=None,
            agent_id="technical_architect",
            system_prompt="Return JSON",
            user_prompt="Test",
            schema=_DummyOut,
        )
        assert parsed.answer == "Fallback succeeded on local Ollama"
        assert res.provider == "ollama"
        assert "groq" in calls and "ollama" in calls
