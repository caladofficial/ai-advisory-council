"""Role-aware Model Router with multi-provider fallback, JSON repair retry, and telemetry."""

from __future__ import annotations

import json
from typing import TypeVar

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_agents_config, get_providers_config, get_settings
from app.database.models import ModelRegistryEntry
from app.database.repository import get_advisor_model_bindings, record_model_usage
from app.models.catalog_importer import discover_ollama_models
from app.models.provider_adapters import LLMCallResult, call_chat_completion, parse_structured_output
from app.models.quota_manager import quota_manager
from app.security.secrets import get_provider_api_key

T = TypeVar("T", bound=BaseModel)


class NoAvailableModelError(RuntimeError):
    """Raised when every free provider and local Ollama fallback fails or lacks keys."""


def _is_provider_configured(provider: str) -> bool:
    if provider == "ollama":
        return True
    cfg = get_providers_config().get("providers", {}).get(provider)
    if not cfg:
        return False
    return bool(get_provider_api_key(cfg.get("api_key_env")))


def resolve_candidate_models(db: Session, agent_id: str) -> list[tuple[str, str]]:
    """Return ordered list of (provider, model_id) candidates for an agent under zero-paid policy."""
    candidates: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()

    def _add(prov: str, mid: str) -> None:
        if (prov, mid) in seen or not _is_provider_configured(prov):
            return
        try:
            quota_manager.assert_zero_paid_allowed(prov, mid)
        except Exception:
            return
        seen.add((prov, mid))
        candidates.append((prov, mid))

    # 1. Explicit user binding override
    bindings = get_advisor_model_bindings(db)
    if agent_id in bindings:
        _add(*bindings[agent_id])

    # 2. Configured preferences from agents.yaml
    agents_cfg = get_agents_config()
    if agent_id == "chief_judge":
        prefs = agents_cfg.get("chief_judge", {}).get("model_preferences", [])
    else:
        advisor_map = {a["advisor_id"]: a for a in agents_cfg.get("advisors", [])}
        prefs = advisor_map.get(agent_id, {}).get("model_preferences", [])

    for pref in sorted(prefs, key=lambda x: x.get("priority", 99)):
        _add(pref["provider"], pref["model"])

    # 3. Healthy / enabled registry entries (preferring configured free APIs then local Ollama)
    entries = list(
        db.scalars(select(ModelRegistryEntry).where(ModelRegistryEntry.enabled.is_(True))).all()
    )
    entries.sort(
        key=lambda e: (
            0 if e.availability_status == "healthy" else 1,
            0 if e.execution_mode == "free_hosted" else 1,
        )
    )
    for e in entries:
        if e.availability_status != "unavailable":
            _add(e.provider, e.model_id)

    # 4. Guaranteed local Ollama discovery fallback
    settings = get_settings()
    for local in discover_ollama_models():
        _add("ollama", local["model_id"])
    _add("ollama", settings.ollama_default_model)

    return candidates


async def invoke_structured(
    db: Session | None,
    *,
    investigation_id: str | None,
    agent_id: str,
    system_prompt: str,
    user_prompt: str,
    schema: type[T],
    temperature: float = 0.2,
    max_tokens: int = 3000,
    prompt_version: str = "v1.0",
) -> tuple[T, LLMCallResult]:
    """Call the best eligible free model with automatic provider fallback and JSON schema validation."""
    from app.database.session import session_scope

    if db is not None:
        candidates = resolve_candidate_models(db, agent_id)
    else:
        with session_scope() as read_db:
            candidates = resolve_candidate_models(read_db, agent_id)
    if not candidates:
        raise NoAvailableModelError(f"No configured free or local models available for {agent_id}")

    schema_hint = json.dumps(schema.model_json_schema(), separators=(",", ":"))
    full_user_prompt = (
        f"{user_prompt}\n\n"
        f"IMPORTANT: Respond ONLY with a valid JSON object matching this schema (keep list entries concise plain strings, max 4 items per list):\n{schema_hint}"
    )

    def _log_usage(**kw) -> None:
        if db is not None:
            record_model_usage(db, **kw)
        else:
            with session_scope() as w_db:
                record_model_usage(w_db, **kw)

    errors: list[str] = []
    for provider, model_id in candidates[:4]:
        for attempt in range(2):
            prompt_to_send = full_user_prompt
            if attempt == 1:
                prompt_to_send += "\n\nYour previous reply was not valid JSON. Output ONLY raw JSON."
            try:
                res = await call_chat_completion(
                    provider=provider,
                    model_id=model_id,
                    system_prompt=system_prompt,
                    user_prompt=prompt_to_send,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    expect_json=True,
                )
                parsed = parse_structured_output(res.content, schema)
                _log_usage(
                    investigation_id=investigation_id,
                    agent_id=agent_id,
                    provider=provider,
                    model_id=model_id,
                    prompt_version=prompt_version,
                    prompt_tokens=res.prompt_tokens,
                    completion_tokens=res.completion_tokens,
                    latency_ms=res.latency_ms,
                    status="SUCCESS",
                )
                return parsed, res
            except Exception as exc:
                errors.append(f"{provider}:{model_id}[try {attempt + 1}] -> {exc}")
                _log_usage(
                    investigation_id=investigation_id,
                    agent_id=agent_id,
                    provider=provider,
                    model_id=model_id,
                    prompt_version=prompt_version,
                    prompt_tokens=0,
                    completion_tokens=0,
                    latency_ms=0,
                    status="FAILED",
                    error_message=str(exc)[:400],
                )

    raise NoAvailableModelError(
        f"All free/local model attempts failed for {agent_id}: " + " | ".join(errors[-4:])
    )
