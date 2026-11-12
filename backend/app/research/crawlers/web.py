"""Web search & sanitized webpage extractor (Tavily when configured, or zero-key DuckDuckGo + httpx/BS4)."""

from __future__ import annotations

from urllib.parse import parse_qs, unquote, urlparse

import httpx
from bs4 import BeautifulSoup

from app.config import get_settings
from app.research.crawlers.base import DEFAULT_HEADERS, RawSourceRecord, safe_get_text
from app.security.sanitization import clean_html_to_text
from app.security.validation import UnsafeURLError, validate_external_url


def _unwrap_ddg_url(href: str) -> str:
    if href.startswith("//"):
        href = "https:" + href
    parsed = urlparse(href)
    if "duckduckgo.com" in parsed.netloc and parsed.path.startswith("/l/"):
        qs = parse_qs(parsed.query)
        if "uddg" in qs and qs["uddg"]:
            return unquote(qs["uddg"][0])
    return href


async def _fetch_clean_page(url: str, fallback_snippet: str) -> str:
    try:
        validate_external_url(url, resolve_dns=True)
        html, _ = await safe_get_text(url)
        cleaned = clean_html_to_text(html)
        if len(cleaned) > 120:
            return cleaned[:4500]
    except (UnsafeURLError, Exception):
        pass
    return fallback_snippet


async def search_web(query: str, limit: int = 4) -> list[RawSourceRecord]:
    settings = get_settings()
    # Optional Tavily API connector if user supplied a free key
    if settings.tavily_api_key:
        try:
            async with httpx.AsyncClient(timeout=settings.request_timeout_seconds) as client:
                resp = await client.post(
                    "https://api.tavily.com/search",
                    json={
                        "api_key": settings.tavily_api_key,
                        "query": query,
                        "max_results": limit,
                        "include_raw_content": False,
                    },
                )
                resp.raise_for_status()
                data = resp.json()
            records: list[RawSourceRecord] = []
            for item in data.get("results", []):
                url = item.get("url") or ""
                if not url:
                    continue
                validate_external_url(url)
                records.append(
                    RawSourceRecord(
                        url=url,
                        title=item.get("title") or url,
                        source_type="web",
                        content=item.get("content") or "",
                        publisher=urlparse(url).netloc,
                    )
                )
            if records:
                return records
        except Exception:
            pass

    # Zero-key DuckDuckGo Lite/HTML discovery + sanitized page extraction
    records = []
    async with httpx.AsyncClient(timeout=settings.request_timeout_seconds, follow_redirects=True) as client:
        resp = await client.post(
            "https://html.duckduckgo.com/html/",
            data={"q": query},
            headers={**DEFAULT_HEADERS, "Content-Type": "application/x-www-form-urlencoded"},
        )
        resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "lxml")
    candidates: list[tuple[str, str, str]] = []
    for res in soup.select(".result"):
        link_el = res.select_one("a.result__a")
        snip_el = res.select_one(".result__snippet")
        if not link_el:
            continue
        href = _unwrap_ddg_url(str(link_el.get("href", "")))
        title = link_el.get_text(" ", strip=True)
        snippet = snip_el.get_text(" ", strip=True) if snip_el else ""
        try:
            validate_external_url(href)
        except UnsafeURLError:
            continue
        candidates.append((href, title, snippet))
        if len(candidates) >= limit:
            break

    for href, title, snippet in candidates:
        page_text = await _fetch_clean_page(href, snippet)
        records.append(
            RawSourceRecord(
                url=href,
                title=title or href,
                source_type="web",
                content=page_text or snippet or title,
                publisher=urlparse(href).netloc,
            )
        )
    return records
