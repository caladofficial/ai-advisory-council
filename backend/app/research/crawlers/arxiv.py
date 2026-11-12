"""arXiv preprint API connector (explicitly marks preprints vs peer-reviewed literature)."""

from __future__ import annotations

import xml.etree.ElementTree as ET

from app.research.crawlers.base import RawSourceRecord, safe_get_text

ATOM_NS = {"atom": "http://www.w3.org/2005/Atom"}


async def search_arxiv(query: str, limit: int = 4) -> list[RawSourceRecord]:
    xml_text, _ = await safe_get_text(
        "https://export.arxiv.org/api/query",
        params={"search_query": f"all:{query}", "start": 0, "max_results": limit},
    )
    root = ET.fromstring(xml_text)
    records: list[RawSourceRecord] = []
    for entry in root.findall("atom:entry", ATOM_NS):
        title = " ".join((entry.findtext("atom:title", default="", namespaces=ATOM_NS)).split())
        summary = " ".join((entry.findtext("atom:summary", default="", namespaces=ATOM_NS)).split())
        entry_id = (entry.findtext("atom:id", default="", namespaces=ATOM_NS)).strip()
        published = (entry.findtext("atom:published", default="", namespaces=ATOM_NS))[:10]
        authors = ", ".join(
            a.findtext("atom:name", default="", namespaces=ATOM_NS)
            for a in entry.findall("atom:author", ATOM_NS)[:3]
        )
        if not title or not entry_id:
            continue
        records.append(
            RawSourceRecord(
                url=entry_id,
                title=title,
                source_type="preprint",
                content=f"[Preprint - Not Peer-Reviewed] {title}\nPublished: {published}\nSummary: {summary}",
                publisher="arXiv",
                author=authors,
                published_at=published or None,
                canonical_identifier=entry_id,
                metadata={"preprint": True, "limitations": ["Preprint; not peer-reviewed"]},
            )
        )
    return records
