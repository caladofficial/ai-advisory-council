"""Base source record dataclass and safe async HTTP client helpers."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import httpx

from app.config import get_settings
from app.security.validation import validate_external_url

DEFAULT_HEADERS = {
    "User-Agent": "AI-Advisory-Council-Researcher/1.0 (https://github.com/ai-advisory-council)"
}


@dataclass
class RawSourceRecord:
    url: str
    title: str
    source_type: str
    content: str
    publisher: str = ""
    author: str = ""
    published_at: str | None = None
    canonical_identifier: str | None = None
    license_name: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


async def safe_get_json(url: str, params: dict[str, Any] | None = None, headers: dict[str, str] | None = None) -> Any:
    validate_external_url(url)
    settings = get_settings()
    merged_headers = {**DEFAULT_HEADERS, **(headers or {})}
    async with httpx.AsyncClient(timeout=settings.request_timeout_seconds, follow_redirects=True) as client:
        resp = await client.get(url, params=params, headers=merged_headers)
        resp.raise_for_status()
        validate_external_url(str(resp.url))
        return resp.json()


async def safe_get_text(url: str, params: dict[str, Any] | None = None, headers: dict[str, str] | None = None) -> tuple[str, str]:
    validate_external_url(url)
    settings = get_settings()
    merged_headers = {**DEFAULT_HEADERS, **(headers or {})}
    async with httpx.AsyncClient(timeout=settings.request_timeout_seconds, follow_redirects=True) as client:
        resp = await client.get(url, params=params, headers=merged_headers)
        resp.raise_for_status()
        final_url = validate_external_url(str(resp.url))
        body = resp.text[: settings.max_crawl_bytes]
        return body, final_url
