"""GitHub REST API connector inspecting repositories, activity, open issues, and licenses."""

from __future__ import annotations

from app.config import get_settings
from app.research.crawlers.base import RawSourceRecord, safe_get_json


async def search_github(query: str, limit: int = 4) -> list[RawSourceRecord]:
    settings = get_settings()
    headers = {"Accept": "application/vnd.github+json"}
    if settings.github_token:
        headers["Authorization"] = f"Bearer {settings.github_token}"

    data = await safe_get_json(
        "https://api.github.com/search/repositories",
        params={"q": query, "sort": "stars", "order": "desc", "per_page": limit},
        headers=headers,
    )
    records: list[RawSourceRecord] = []
    for repo in data.get("items", []):
        full_name = repo.get("full_name", "")
        html_url = repo.get("html_url", "")
        if not full_name or not html_url:
            continue
        lic = (repo.get("license") or {}).get("spdx_id") or "NOASSERTION"
        stars = repo.get("stargazers_count", 0)
        issues = repo.get("open_issues_count", 0)
        pushed = (repo.get("pushed_at") or "")[:10]
        desc = repo.get("description") or "No description provided."
        lang = repo.get("language") or "Mixed"
        archived = bool(repo.get("archived"))

        limitations = []
        if lic in {"NOASSERTION", "NONE", None}:
            limitations.append("No explicit open-source license detected")
        elif "AGPL" in lic or "GPL" in lic:
            limitations.append(f"Copyleft license ({lic}) requires legal compatibility check")
        if archived:
            limitations.append("Repository is archived / unmaintained")

        content = (
            f"GitHub Repo: {full_name} | Language: {lang} | Stars: {stars} | Open Issues: {issues}\n"
            f"License: {lic} | Last Pushed: {pushed} | Archived: {archived}\n"
            f"Description: {desc}"
        )
        records.append(
            RawSourceRecord(
                url=html_url,
                title=f"GitHub: {full_name}",
                source_type="github",
                content=content,
                publisher="GitHub",
                author=(repo.get("owner") or {}).get("login", ""),
                published_at=pushed or None,
                canonical_identifier=f"github:{full_name}",
                license_name=lic,
                metadata={
                    "stars": stars,
                    "open_issues": issues,
                    "archived": archived,
                    "limitations": limitations,
                },
            )
        )
    return records
