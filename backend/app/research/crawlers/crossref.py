"""Crossref DOI metadata connector."""

from __future__ import annotations

import re

from app.research.crawlers.base import RawSourceRecord, safe_get_json


async def search_crossref(query: str, limit: int = 4) -> list[RawSourceRecord]:
    data = await safe_get_json(
        "https://api.crossref.org/works",
        params={"query": query, "rows": limit},
    )
    items = (data.get("message") or {}).get("items", [])
    records: list[RawSourceRecord] = []
    for item in items:
        titles = item.get("title") or []
        title = titles[0] if titles else ""
        doi = item.get("DOI")
        if not title or not doi:
            continue
        url = f"https://doi.org/{doi}"
        abstract = re.sub(r"<[^>]+>", " ", item.get("abstract") or "").strip()
        authors = ", ".join(
            f"{a.get('given', '')} {a.get('family', '')}".strip()
            for a in (item.get("author") or [])[:3]
        )
        date_parts = ((item.get("published") or {}).get("date-parts") or [[]])[0]
        pub_date = "-".join(f"{int(p):02d}" for p in date_parts[:3]) if date_parts else None
        content = (
            f"DOI: {doi} | Publisher: {item.get('publisher', 'Unknown')} | Citations: {item.get('is-referenced-by-count', 0)}\n"
            f"Title: {title}\n"
            f"Abstract: {abstract or 'Metadata record verified via Crossref.'}"
        )
        records.append(
            RawSourceRecord(
                url=url,
                title=title,
                source_type="academic",
                content=content,
                publisher=item.get("publisher", "Crossref"),
                author=authors,
                published_at=pub_date,
                canonical_identifier=f"https://doi.org/{doi}",
                metadata={"doi": doi, "referenced_by_count": item.get("is-referenced-by-count", 0)},
            )
        )
    return records
