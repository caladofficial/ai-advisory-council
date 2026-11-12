"""Server-side secret store, masking, and log redaction."""

from __future__ import annotations

import os
import re
from threading import Lock

from app.config import get_settings

_RUNTIME_KEYS: dict[str, str] = {}
_LOCK = Lock()

SECRET_VALUE_PATTERN = re.compile(
    r"(sk-[A-Za-z0-9\-_]{12,}|gsk_[A-Za-z0-9]{12,}|AIza[A-Za-z0-9\-_]{16,}|hf_[A-Za-z0-9]{12,}|nvapi-[A-Za-z0-9\-_]{12,}|ghp_[A-Za-z0-9]{12,})"
)


def mask_secret(value: str | None) -> str:
    """Return masked preview without exposing raw secret material."""
    if not value:
        return ""
    v = value.strip()
    if len(v) <= 8:
        return "*" * len(v)
    return f"{v[:4]}...{v[-4:]}"


def scrub_secrets_from_text(text: str) -> str:
    """Redact any accidentally embedded API tokens before logging."""
    if not text:
        return text
    scrubbed = SECRET_VALUE_PATTERN.sub("[REDACTED_SECRET]", text)
    with _LOCK:
        for val in _RUNTIME_KEYS.values():
            if val and len(val) > 6 and val in scrubbed:
                scrubbed = scrubbed.replace(val, "[REDACTED_SECRET]")
    return scrubbed


def set_provider_api_key(env_name: str, api_key: str) -> None:
    """Store a provider API key server-side in memory and process env."""
    cleaned = api_key.strip()
    with _LOCK:
        _RUNTIME_KEYS[env_name] = cleaned
    os.environ[env_name] = cleaned


def get_provider_api_key(env_name: str | None) -> str:
    """Resolve provider API key from runtime overrides, process env, or Settings."""
    if not env_name:
        return ""
    with _LOCK:
        if env_name in _RUNTIME_KEYS and _RUNTIME_KEYS[env_name]:
            return _RUNTIME_KEYS[env_name]
    if os.environ.get(env_name):
        return os.environ[env_name]
    settings = get_settings()
    return str(getattr(settings, env_name.lower(), "") or "")
