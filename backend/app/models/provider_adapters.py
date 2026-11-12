"""Unified provider adapters for local Ollama and free OpenAI-compatible hosted LLM endpoints."""

from __future__ import annotations

import asyncio
import json
import re
import time
from dataclasses import dataclass
from typing import Any, TypeVar
from weakref import WeakKeyDictionary

import httpx
from openai import AsyncOpenAI
from pydantic import BaseModel

from app.config import get_providers_config, get_settings
from app.models.quota_manager import quota_manager
from app.security.secrets import get_provider_api_key

T = TypeVar("T", bound=BaseModel)
_OLLAMA_SEMS: WeakKeyDictionary[asyncio.AbstractEventLoop, asyncio.Semaphore] = WeakKeyDictionary()


def _get_ollama_semaphore() -> asyncio.Semaphore:
    loop = asyncio.get_running_loop()
    sem = _OLLAMA_SEMS.get(loop)
    if sem is None:
        sem = asyncio.Semaphore(1)
        _OLLAMA_SEMS[loop] = sem
    return sem


@dataclass
class LLMCallResult:
    content: str
    provider: str
    model_id: str
    prompt_tokens: int
    completion_tokens: int
    latency_ms: int


def extract_json_object(raw_text: str) -> dict[str, Any]:
    """Robustly extract a JSON object from LLM text, including markdown code fences."""
    text = (raw_text or "").strip()
    if not text:
        raise ValueError("Empty model response")

    # Strip thinking tags emitted by reasoning models like deepseek-r1 or qwen3
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.S).strip()

    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, flags=re.S)
    if fenced:
        text = fenced.group(1)
    else:
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end > start:
            text = text[start : end + 1]

    return json.loads(text)


def _provider_endpoint(provider: str) -> tuple[str, str]:
    settings = get_settings()
    if provider == "ollama":
        return settings.ollama_base_url.rstrip("/") + "/v1", "ollama"

    cfg = get_providers_config().get("providers", {}).get(provider, {})
    base_url = str(cfg.get("base_url", "")).strip()
    if provider == "cloudflare" and "{account_id}" in base_url:
        base_url = base_url.replace("{account_id}", settings.cloudflare_account_id or "")
    api_key = get_provider_api_key(cfg.get("api_key_env"))
    if not base_url or not api_key:
        raise RuntimeError(f"Provider {provider!r} missing base_url or API key")
    return base_url, api_key


async def call_chat_completion(
    *,
    provider: str,
    model_id: str,
    system_prompt: str,
    user_prompt: str,
    temperature: float = 0.2,
    max_tokens: int = 3000,
    expect_json: bool = False,
) -> LLMCallResult:
    """Invoke local Ollama or an OpenAI-compatible free endpoint under zero-paid policy."""
    quota_manager.assert_zero_paid_allowed(provider, model_id)
    allowed, reason = quota_manager.can_dispatch(provider)
    if not allowed:
        raise RuntimeError(reason)

    settings = get_settings()
    t0 = time.perf_counter()
    quota_manager.record_request(provider)

    if provider == "ollama":
        native_url = settings.ollama_base_url.rstrip("/") + "/api/chat"
        payload: dict[str, Any] = {
            "model": model_id,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "stream": False,
            "options": {"temperature": temperature, "num_predict": min(max_tokens, 2200)},
        }
        if expect_json:
            payload["format"] = "json"
        timeout = httpx.Timeout(connect=10.0, read=max(600.0, settings.llm_timeout_seconds), write=30.0, pool=30.0)
        try:
            async with _get_ollama_semaphore():
                async with httpx.AsyncClient(timeout=timeout) as client:
                    resp = await client.post(native_url, json=payload)
                    resp.raise_for_status()
                    data = resp.json()
        except Exception as exc:
            raise RuntimeError(f"Ollama call failed for {model_id}: {type(exc).__name__}: {exc}") from exc

        latency_ms = int((time.perf_counter() - t0) * 1000)
        msg = (data.get("message") or {}).get("content", "")
        return LLMCallResult(
            content=msg,
            provider=provider,
            model_id=model_id,
            prompt_tokens=int(data.get("prompt_eval_count") or len(system_prompt + user_prompt) // 4),
            completion_tokens=int(data.get("eval_count") or len(msg) // 4),
            latency_ms=latency_ms,
        )

    base_url, api_key = _provider_endpoint(provider)
    client = AsyncOpenAI(
        base_url=base_url,
        api_key=api_key,
        timeout=settings.llm_timeout_seconds,
        max_retries=1,
    )
    kwargs: dict[str, Any] = {
        "model": model_id,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    if expect_json:
        kwargs["response_format"] = {"type": "json_object"}

    try:
        completion = await client.chat.completions.create(**kwargs)
    except Exception as exc:
        err_str = str(exc)
        # Some models reject response_format={"type":"json_object"}; retry without it once
        if expect_json and ("response_format" in err_str.lower() or "400" in err_str):
            kwargs.pop("response_format", None)
            completion = await client.chat.completions.create(**kwargs)
        else:
            if "429" in err_str or "rate" in err_str.lower():
                quota_manager.trigger_cooldown(provider, 45.0)
            raise RuntimeError(f"Hosted provider {provider}:{model_id} failed: {exc}") from exc

    latency_ms = int((time.perf_counter() - t0) * 1000)
    content = completion.choices[0].message.content or ""
    usage = completion.usage
    return LLMCallResult(
        content=content,
        provider=provider,
        model_id=model_id,
        prompt_tokens=int(getattr(usage, "prompt_tokens", 0) or len(system_prompt + user_prompt) // 4),
        completion_tokens=int(getattr(usage, "completion_tokens", 0) or len(content) // 4),
        latency_ms=latency_ms,
    )


def parse_structured_output(raw_text: str, schema: type[T]) -> T:
    """Validate extracted JSON payload against a Pydantic v2 schema."""
    obj = extract_json_object(raw_text)
    return schema.model_validate(obj)
