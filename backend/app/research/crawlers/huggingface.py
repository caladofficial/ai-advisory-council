"""Hugging Face Hub API connector for discovering models, datasets, tags, and licenses."""

from __future__ import annotations

from app.research.crawlers.base import RawSourceRecord, safe_get_json


async def search_huggingface(query: str, limit: int = 4) -> list[RawSourceRecord]:
    records: list[RawSourceRecord] = []
    models = await safe_get_json(
        "https://huggingface.co/api/models",
        params={"search": query, "sort": "downloads", "direction": "-1", "limit": limit},
    )
    for m in models:
        mid = m.get("id") or m.get("modelId")
        if not mid:
            continue
        tags = m.get("tags") or []
        lic = next((t.replace("license:", "") for t in tags if t.startswith("license:")), "unknown")
        downloads = m.get("downloads", 0)
        likes = m.get("likes", 0)
        pipeline = m.get("pipeline_tag") or "general"
        url = f"https://huggingface.co/{mid}"
        content = (
            f"Hugging Face Model: {mid} | Task: {pipeline} | License: {lic}\n"
            f"Downloads: {downloads} | Likes: {likes} | Tags: {', '.join(tags[:8])}"
        )
        records.append(
            RawSourceRecord(
                url=url,
                title=f"HF Model: {mid}",
                source_type="huggingface",
                content=content,
                publisher="Hugging Face Hub",
                author=mid.split("/")[0],
                published_at=(m.get("lastModified") or "")[:10] or None,
                canonical_identifier=f"hf-model:{mid}",
                license_name=lic,
                metadata={"downloads": downloads, "likes": likes, "pipeline_tag": pipeline},
            )
        )

    try:
        datasets = await safe_get_json(
            "https://huggingface.co/api/datasets",
            params={"search": query, "sort": "downloads", "direction": "-1", "limit": 2},
        )
        for ds in datasets:
            did = ds.get("id")
            if not did:
                continue
            tags = ds.get("tags") or []
            lic = next((t.replace("license:", "") for t in tags if t.startswith("license:")), "unknown")
            url = f"https://huggingface.co/datasets/{did}"
            records.append(
                RawSourceRecord(
                    url=url,
                    title=f"HF Dataset: {did}",
                    source_type="huggingface",
                    content=f"Hugging Face Dataset: {did} | License: {lic} | Downloads: {ds.get('downloads', 0)}",
                    publisher="Hugging Face Hub",
                    author=did.split("/")[0],
                    canonical_identifier=f"hf-dataset:{did}",
                    license_name=lic,
                    metadata={"downloads": ds.get("downloads", 0), "kind": "dataset"},
                )
            )
    except Exception:
        pass

    return records
