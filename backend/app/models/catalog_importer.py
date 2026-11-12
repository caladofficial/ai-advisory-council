"""Imports providers and models from awesome-freellm-apis, local YAML, Ollama, and Hugging Face Hub."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_models_config, get_providers_config, get_settings
from app.database.models import ModelRegistryEntry

SLUG_TO_CANONICAL = {
    "nvidia-nim": "nvidia_nim",
    "google-gemini": "google_gemini",
    "hugging-face": "huggingface",
    "mistral-ai": "mistral",
    "ollama-cloud": "ollama_cloud",
    "cloudflare-workers-ai": "cloudflare",
    "z-ai-zhipu-ai": "zhipu",
    "ovhcloud-ai-endpoints": "ovhcloud",
    "alibaba-cloud-model-studio": "alibaba_bailian",
}


def _canonical_provider(slug_or_name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", slug_or_name.lower()).strip("-")
    if slug in SLUG_TO_CANONICAL:
        return SLUG_TO_CANONICAL[slug]
    return slug.replace("-", "_")


def _parse_context_label(label: str) -> int | None:
    if not label:
        return None
    s = label.strip().upper()
    m = re.match(r"^(\d+(?:\.\d+)?)([KM]?)$", s)
    if not m:
        return None
    num = float(m.group(1))
    unit = m.group(2)
    if unit == "M":
        return int(num * 1_000_000)
    if unit == "K":
        return int(num * 1_000)
    return int(num)


def load_freellm_catalog() -> dict[str, Any]:
    """Load bundled awesome-freellm-apis status & model catalog JSON files."""
    settings = get_settings()
    status_path = Path(settings.catalog_dir) / "freellm_status.json"
    models_path = Path(settings.catalog_dir) / "freellm_models.json"
    status_data = json.loads(status_path.read_text(encoding="utf-8")) if status_path.exists() else {}
    models_data = json.loads(models_path.read_text(encoding="utf-8")) if models_path.exists() else {}
    return {"status": status_data, "models": models_data.get("models", [])}


def discover_ollama_models(base_url: str | None = None) -> list[dict[str, Any]]:
    """Query local Ollama daemon for pulled open-weight models."""
    settings = get_settings()
    url = (base_url or settings.ollama_base_url).rstrip("/") + "/api/tags"
    try:
        with httpx.Client(timeout=3.0) as client:
            resp = client.get(url)
            resp.raise_for_status()
            data = resp.json()
    except Exception:
        return []

    found: list[dict[str, Any]] = []
    for item in data.get("models", []):
        name = item.get("name") or item.get("model")
        if not name:
            continue
        details = item.get("details") or {}
        found.append(
            {
                "provider": "ollama",
                "model_id": name,
                "display_name": f"{name} (Local Ollama)",
                "execution_mode": "local",
                "family": details.get("family", "local"),
                "capabilities": item.get("capabilities") or ["general", "structured_json"],
                "supports_tools": "tools" in (item.get("capabilities") or []),
                "supports_json": True,
                "context_window": details.get("context_length") or 8192,
                "rate_limit_note": "Unlimited local compute",
                "is_free": True,
                "availability_status": "healthy",
                "enabled": True,
            }
        )
    return found


def discover_huggingface_models(query: str = "instruct", limit: int = 8) -> list[dict[str, Any]]:
    """Query Hugging Face Hub API for popular open-weight text-generation candidates."""
    try:
        with httpx.Client(timeout=6.0) as client:
            resp = client.get(
                "https://huggingface.co/api/models",
                params={
                    "search": query,
                    "pipeline_tag": "text-generation",
                    "sort": "downloads",
                    "direction": "-1",
                    "limit": limit,
                },
            )
            resp.raise_for_status()
            items = resp.json()
    except Exception:
        return []

    results: list[dict[str, Any]] = []
    for m in items:
        mid = m.get("id") or m.get("modelId")
        if not mid:
            continue
        results.append(
            {
                "provider": "huggingface",
                "model_id": mid,
                "display_name": f"{mid} (HF Hub)",
                "execution_mode": "free_hosted",
                "family": mid.split("/")[0].lower(),
                "capabilities": ["research", "general"],
                "supports_tools": False,
                "supports_json": True,
                "context_window": 32768,
                "rate_limit_note": "HF Inference Providers free monthly credit / router",
                "is_free": True,
                "availability_status": "untested",
                "enabled": True,
            }
        )
    return results


def sync_model_registry(db: Session, *, include_ollama: bool = True, include_hf: bool = False) -> int:
    """Seed or update the model_registry table from YAML, awesome-freellm-apis, and Ollama."""
    inserted_or_updated = 0
    existing = {
        (row.provider, row.model_id): row
        for row in db.scalars(select(ModelRegistryEntry)).all()
    }

    candidates: list[dict[str, Any]] = []
    # 1. Curated core models from config/models.yaml
    for item in get_models_config().get("models", []):
        candidates.append(item)

    # 2. Bundled models from awesome-freellm-apis catalog
    catalog = load_freellm_catalog()
    for row in catalog.get("models", []):
        prov = _canonical_provider(row.get("provider", ""))
        mid = (row.get("model_id") or "").strip()
        if not prov or not mid:
            continue
        # Respect zero-paid safeguard for OpenRouter models
        if prov == "openrouter" and ":free" not in mid:
            mid_candidate = f"{mid}:free"
        else:
            mid_candidate = mid
        candidates.append(
            {
                "provider": prov,
                "model_id": mid_candidate,
                "display_name": row.get("display_name") or mid_candidate,
                "execution_mode": "free_hosted",
                "family": mid_candidate.split("/")[0].split("-")[0].lower(),
                "capabilities": ["general", "structured_json"],
                "supports_tools": False,
                "supports_json": True,
                "context_window": _parse_context_label(row.get("context_label", "")),
                "rate_limit_note": row.get("rate_limit", "See provider free tier"),
                "is_free": True,
                "enabled": True,
            }
        )

    # 3. Live local Ollama models
    if include_ollama:
        candidates.extend(discover_ollama_models())

    # 4. Optional live Hugging Face Hub discovery
    if include_hf:
        candidates.extend(discover_huggingface_models())

    seen_keys: set[tuple[str, str]] = set()
    for item in candidates:
        prov = item["provider"]
        mid = item["model_id"]
        key = (prov, mid)
        if key in seen_keys:
            continue
        seen_keys.add(key)

        entry_id = f"{prov}:{mid}"[:128]
        if key in existing:
            rec = existing[key]
            if item.get("availability_status") == "healthy":
                rec.availability_status = "healthy"
            if item.get("context_window") and not rec.context_window:
                rec.context_window = item["context_window"]
            if item.get("rate_limit_note"):
                rec.rate_limit_note = item["rate_limit_note"]
        else:
            rec = ModelRegistryEntry(
                id=entry_id,
                provider=prov,
                model_id=mid,
                display_name=item.get("display_name", mid)[:200],
                execution_mode=item.get("execution_mode", "free_hosted"),
                family=item.get("family", "general")[:64],
                capabilities_json=item.get("capabilities", ["general"]),
                supports_tools=bool(item.get("supports_tools", False)),
                supports_json=bool(item.get("supports_json", True)),
                context_window=item.get("context_window"),
                rate_limit_note=str(item.get("rate_limit_note", ""))[:256],
                is_free=bool(item.get("is_free", True)),
                availability_status=item.get("availability_status", "untested"),
                enabled=bool(item.get("enabled", True)),
            )
            db.add(rec)
            existing[key] = rec
            inserted_or_updated += 1

    db.flush()
    return inserted_or_updated


def get_merged_provider_catalog(requests_today: dict[str, int]) -> list[dict[str, Any]]:
    """Combine providers.yaml canonical URLs with awesome-freellm-apis status metadata."""
    from app.security.secrets import get_provider_api_key, mask_secret

    yaml_providers = get_providers_config().get("providers", {})
    status_providers = load_freellm_catalog().get("status", {}).get("providers", [])
    status_by_canonical = {_canonical_provider(p.get("slug", p.get("provider", ""))): p for p in status_providers}

    merged: list[dict[str, Any]] = []
    seen: set[str] = set()

    for pid, cfg in yaml_providers.items():
        seen.add(pid)
        st = status_by_canonical.get(pid, {})
        env_name = cfg.get("api_key_env")
        raw_key = get_provider_api_key(env_name)
        has_key = True if pid == "ollama" else bool(raw_key)
        merged.append(
            {
                "provider_id": pid,
                "display_name": cfg.get("display_name", pid),
                "protocol": cfg.get("protocol", "openai_compatible"),
                "base_url": cfg.get("base_url", ""),
                "api_key_url": cfg.get("api_key_url") or st.get("api_key_url", ""),
                "is_free_tier": bool(cfg.get("is_free_tier", True)),
                "requires_credit_card": bool(cfg.get("requires_credit_card", False)),
                "has_key_configured": has_key,
                "masked_key": "local" if pid == "ollama" else mask_secret(raw_key),
                "default_rpm": int(cfg.get("default_rpm", 20)),
                "default_rpd": int(cfg.get("default_rpd", 1000)),
                "requests_today": requests_today.get(pid, 0),
                "free_models_count": int(st.get("free_models_count", 1 if pid == "ollama" else 0)),
                "max_context": int(st.get("max_context", 131072 if pid == "ollama" else 0)),
                "status": st.get("status", "Operational"),
                "tagline": st.get("tagline") or cfg.get("notes", ""),
            }
        )

    for canonical, st in status_by_canonical.items():
        if canonical in seen:
            continue
        merged.append(
            {
                "provider_id": canonical,
                "display_name": st.get("provider", canonical),
                "protocol": "openai_compatible",
                "base_url": st.get("base_url", ""),
                "api_key_url": st.get("api_key_url", ""),
                "is_free_tier": True,
                "requires_credit_card": False,
                "has_key_configured": False,
                "masked_key": "",
                "default_rpm": 20,
                "default_rpd": 500,
                "requests_today": requests_today.get(canonical, 0),
                "free_models_count": int(st.get("free_models_count", 0)),
                "max_context": int(st.get("max_context", 0)),
                "status": st.get("status", "Operational"),
                "tagline": st.get("tagline", ""),
            }
        )
    return merged
