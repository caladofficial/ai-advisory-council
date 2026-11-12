"""Live health checks for local Ollama and configured free hosted providers."""

from __future__ import annotations

from datetime import datetime, timezone

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_providers_config
from app.database.models import ModelRegistryEntry
from app.models.provider_adapters import call_chat_completion, parse_structured_output
from app.schemas.model_registry import HealthCheckResult
from app.security.secrets import get_provider_api_key


class _PingSchema(BaseModel):
    ok: bool


async def check_single_model(provider: str, model_id: str, test_json: bool = True) -> HealthCheckResult:
    now = datetime.now(timezone.utc)
    if provider != "ollama":
        cfg = get_providers_config().get("providers", {}).get(provider, {})
        if not get_provider_api_key(cfg.get("api_key_env")):
            return HealthCheckResult(
                provider=provider,
                model_id=model_id,
                status="skipped_no_key",
                error="API key not configured",
                checked_at=now,
            )

    try:
        res = await call_chat_completion(
            provider=provider,
            model_id=model_id,
            system_prompt="Respond strictly with JSON matching {\"ok\": true}.",
            user_prompt="Ping test.",
            temperature=0.0,
            max_tokens=48,
            expect_json=test_json,
        )
        json_ok = True
        if test_json:
            try:
                parsed = parse_structured_output(res.content, _PingSchema)
                json_ok = bool(parsed.ok)
            except Exception:
                json_ok = False
        return HealthCheckResult(
            provider=provider,
            model_id=model_id,
            status="healthy",
            latency_ms=float(res.latency_ms),
            supports_json_verified=json_ok,
            checked_at=now,
        )
    except Exception as exc:
        return HealthCheckResult(
            provider=provider,
            model_id=model_id,
            status="unavailable",
            error=str(exc)[:300],
            checked_at=now,
        )


async def run_registry_health_checks(
    db: Session,
    *,
    provider: str | None = None,
    model_id: str | None = None,
    test_json: bool = True,
) -> list[HealthCheckResult]:
    query = select(ModelRegistryEntry).where(ModelRegistryEntry.enabled.is_(True))
    if provider:
        query = query.where(ModelRegistryEntry.provider == provider)
    if model_id:
        query = query.where(ModelRegistryEntry.model_id == model_id)
    entries = list(db.scalars(query.limit(20)).all())

    results: list[HealthCheckResult] = []
    for entry in entries:
        # Skip unconfigured hosted providers quickly unless specifically targeted
        if not provider and entry.provider != "ollama":
            cfg = get_providers_config().get("providers", {}).get(entry.provider, {})
            if not get_provider_api_key(cfg.get("api_key_env")):
                continue
        res = await check_single_model(entry.provider, entry.model_id, test_json=test_json)
        entry.availability_status = res.status
        entry.last_health_check = res.checked_at
        if res.latency_ms is not None:
            entry.latency_ms = res.latency_ms
        if res.status == "healthy":
            entry.supports_json = res.supports_json_verified
        results.append(res)

    db.flush()
    return results
