"""OpenAlex scholarly API connector with inverted-index abstract reconstruction."""

from __future__ import annotations

from app.config import get_settings
from app.research.crawlers.base import RawSourceRecord, safe_get_json

OPENALEX_FIELDS = "id,doi,title,publication_year,cited_by_count,abstract_inverted_index,primary_location,authorships,type"


def rebuild_abstract(inverted_index: dict[str, list[int]] | None) -> str:
    """Reconstruct readable abstract text from OpenAlex inverted index."""
    if not inverted_index:
        return ""
    positions = {pos: word for word, places in inverted_index.items() for pos in places}
    return " ".join(positions[i] for i in sorted(positions))


async def search_openalex(query: str, limit: int = 5) -> list[RawSourceRecord]:
    settings = get_settings()
    params: dict[str, object] = {
        "search": query,
        "per_page": limit,
        "select": OPENALEX_FIELDS,
        "filter": "has_abstract:true",
    }
    if settings.openalex_api_key:
        params["api_key"] = settings.openalex_api_key
    if settings.openalex_email:
        params["mailto"] = settings.openalex_email

    data = await safe_get_json("https://api.openalex.org/works", params=params)
    records: list[RawSourceRecord] = []
    for work in data.get("results", []):
        title = (work.get("title") or "").strip()
        if not title:
            continue
        abstract = rebuild_abstract(work.get("abstract_inverted_index"))
        doi = work.get("doi")
        url = doi or work.get("id") or ""
        if not url:
            continue
        authors = ", ".join(
            (a.get("author") or {}).get("display_name", "")
            for a in (work.get("authorships") or [])[:3]
        ).strip(", ")
        source_info = ((work.get("primary_location") or {}).get("source") or {})
        publisher = source_info.get("display_name") or "OpenAlex Indexed Publication"
        pub_year = work.get("publication_year")
        cited = work.get("cited_by_count", 0)
        work_type = work.get("type", "article")
        content = (
            f"Title: {title}\n"
            f"Type: {work_type} | Year: {pub_year} | Citations: {cited}\n"
            f"Abstract: {abstract}"
        )
        records.append(
            RawSourceRecord(
                url=url,
                title=title,
                source_type="academic",
                content=content,
                publisher=publisher,
                author=authors,
                published_at=f"{pub_year}-01-01" if pub_year else None,
                canonical_identifier=doi or work.get("id"),
                metadata={"cited_by_count": cited, "work_type": work_type, "peer_reviewed_hint": work_type == "article"},
            )
        )
    return records
