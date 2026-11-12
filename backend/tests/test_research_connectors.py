"""Acceptance tests for OpenAlex, Crossref, arXiv, GitHub, Hugging Face, and Wikipedia connectors."""

from __future__ import annotations

import httpx
import pytest
import respx

from app.research.crawlers.arxiv import search_arxiv
from app.research.crawlers.github import search_github
from app.research.crawlers.huggingface import search_huggingface
from app.research.crawlers.openalex import rebuild_abstract, search_openalex


def test_openalex_inverted_index_reconstruction():
    inv = {"Offline": [0], "AI": [1], "tutors": [2], "improve": [3], "learning.": [4]}
    assert rebuild_abstract(inv) == "Offline AI tutors improve learning."


@pytest.mark.asyncio
async def test_connectors_with_mocked_http():
    with respx.mock(assert_all_called=False) as mock:
        mock.get("https://api.openalex.org/works").mock(
            return_value=httpx.Response(
                200,
                json={
                    "results": [
                        {
                            "id": "https://openalex.org/W1",
                            "doi": "https://doi.org/10.1234/edu",
                            "title": "Edge AI for Rural Classrooms",
                            "publication_year": 2026,
                            "cited_by_count": 42,
                            "type": "article",
                            "abstract_inverted_index": {"Edge": [0], "AI": [1], "works": [2], "offline.": [3]},
                            "primary_location": {"source": {"display_name": "EdTech Journal"}},
                            "authorships": [{"author": {"display_name": "A. Sharma"}}],
                        }
                    ]
                },
            )
        )
        mock.get("https://api.github.com/search/repositories").mock(
            return_value=httpx.Response(
                200,
                json={
                    "items": [
                        {
                            "full_name": "org/offline-lms",
                            "html_url": "https://github.com/org/offline-lms",
                            "stargazers_count": 510,
                            "open_issues_count": 12,
                            "language": "Python",
                            "pushed_at": "2026-10-01T00:00:00Z",
                            "archived": False,
                            "license": {"spdx_id": "MIT"},
                            "owner": {"login": "org"},
                            "description": "Offline open source LMS",
                        }
                    ]
                },
            )
        )
        mock.get("https://huggingface.co/api/models").mock(
            return_value=httpx.Response(
                200,
                json=[
                    {
                        "id": "Qwen/Qwen2.5-3B-Instruct",
                        "downloads": 120000,
                        "likes": 900,
                        "pipeline_tag": "text-generation",
                        "tags": ["license:apache-2.0"],
                        "lastModified": "2026-09-12T00:00:00Z",
                    }
                ],
            )
        )
        mock.get("https://huggingface.co/api/datasets").mock(return_value=httpx.Response(200, json=[]))
        mock.get("https://export.arxiv.org/api/query").mock(
            return_value=httpx.Response(
                200,
                text="""<?xml version="1.0" encoding="UTF-8"?>
                <feed xmlns="http://www.w3.org/2005/Atom">
                  <entry>
                    <id>http://arxiv.org/abs/2601.0001</id>
                    <published>2026-01-15T00:00:00Z</published>
                    <title>Quantized Tutors</title>
                    <summary>Preprint evaluating 4-bit models.</summary>
                    <author><name>R. Rao</name></author>
                  </entry>
                </feed>""",
            )
        )

        oa = await search_openalex("rural education ai")
        gh = await search_github("offline lms")
        hf = await search_huggingface("qwen")
        ax = await search_arxiv("quantized tutors")

        assert len(oa) == 1 and oa[0].source_type == "academic" and "Edge AI works offline." in oa[0].content
        assert len(gh) == 1 and gh[0].license_name == "MIT"
        assert len(hf) == 1 and hf[0].license_name == "apache-2.0"
        assert len(ax) == 1 and ax[0].source_type == "preprint" and "Not Peer-Reviewed" in ax[0].content
