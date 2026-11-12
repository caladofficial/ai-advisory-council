"""Wikipedia REST API connector for background definitions (requires corroboration)."""

from __future__ import annotations

from urllib.parse import quote

from app.research.crawlers.base import RawSourceRecord, safe_get_json


async def search_wikipedia(query: str, limit: int = 3) -> list[RawSourceRecord]:
    data = await safe_get_json(
        "https://en.wikipedia.org/w/rest.php/v1/search/page",
        params={"q": query, "limit": limit},
    )
    records: list[RawSourceRecord] = []
    for page in data.get("pages", []):
        title = page.get("title")
        if not title:
            continue
        try:
            summary = await safe_get_json(
                f"https://en.wikipedia.org/api/rest_v1/page/summary/{quote(title.replace(' ', '_'))}"
            )
        except Exception:
            continue
        url = ((summary.get("content_urls") or {}).get("desktop") or {}).get("page") or ""
        extract = summary.get("extract") or ""
        if not url or not extract:
            continue
        records.append(
            RawSourceRecord(
                url=url,
                title=f"Wikipedia: {summary.get('title', title)}",
                source_type="encyclopedia",
                content=extract,
                publisher="Wikipedia",
                published_at=(summary.get("timestamp") or "")[:10] or None,
                canonical_identifier=f"wikipedia:{summary.get('pageid', title)}",
                license_name="CC-BY-SA-4.0",
                metadata={"limitations": ["Encyclopedia summary; corroborate critical claims with primary sources"]},
            )
        )
    return records
