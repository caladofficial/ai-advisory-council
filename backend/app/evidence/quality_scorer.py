"""Explainable 5-dimension source & evidence quality scorer (25/25/20/15/15 weights)."""

from __future__ import annotations

import math
import re
from datetime import datetime, timezone

from app.config import get_research_sources_config
from app.database.models import EvidenceChunk, Source


def _parse_year(published_at: str | None) -> int | None:
    if not published_at:
        return None
    m = re.search(r"(19|20)\d{2}", published_at)
    return int(m.group(0)) if m else None


def _keyword_overlap(text_a: str, text_b: str) -> float:
    ta = {w for w in re.findall(r"[a-z0-9]{3,}", (text_a or "").lower())}
    tb = {w for w in re.findall(r"[a-z0-9]{3,}", (text_b or "").lower())}
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / max(1, min(len(ta), 8))


def score_evidence_chunk(
    chunk: EvidenceChunk,
    source: Source,
    *,
    topic: str,
    mode: str,
    independent_corroborators: int = 1,
) -> tuple[float, dict[str, object]]:
    """Compute explainable quality score in [0, 1] and detailed rubric breakdown."""
    cfg = get_research_sources_config()
    weights = cfg.get("evidence_rubric", {}).get("weights", {})
    half_lives = cfg.get("evidence_rubric", {}).get("freshness_half_life_days", {})

    base_auth_map = {
        "academic": 0.90,
        "government": 0.92,
        "documentation": 0.85,
        "huggingface": 0.80,
        "github": 0.78,
        "upload": 0.75,
        "preprint": 0.70,
        "encyclopedia": 0.62,
        "web": 0.58,
    }
    authority = base_auth_map.get(source.source_type, 0.55)
    if source.author:
        authority = min(1.0, authority + 0.04)
    if source.canonical_identifier:
        authority = min(1.0, authority + 0.03)

    # Methodology & source rigor
    meta = source.metadata_json or {}
    methodology = 0.60
    if source.source_type == "academic":
        cites = int(meta.get("cited_by_count") or meta.get("referenced_by_count") or 0)
        methodology = min(0.98, 0.72 + 0.05 * math.log10(max(1, cites + 1)))
    elif source.source_type == "preprint":
        methodology = 0.58
    elif source.source_type == "github":
        stars = int(meta.get("stars") or 0)
        archived = bool(meta.get("archived"))
        methodology = 0.42 if archived else min(0.90, 0.55 + 0.06 * math.log10(max(1, stars + 1)))
    elif source.source_type == "huggingface":
        downloads = int(meta.get("downloads") or 0)
        methodology = min(0.90, 0.60 + 0.05 * math.log10(max(1, downloads + 1)))
    elif source.source_type == "upload":
        methodology = 0.72

    if chunk.prompt_injection_flagged:
        methodology = max(0.20, methodology - 0.30)

    # Relevance to topic
    overlap = _keyword_overlap(topic, f"{source.title} {chunk.content}")
    relevance = min(1.0, 0.35 + 0.65 * min(1.0, overlap))

    # Independent corroboration (distinct non-duplicate origins)
    corroboration = min(1.0, 0.35 + 0.25 * max(0, independent_corroborators - 1))

    # Freshness decay
    current_year = datetime.now(timezone.utc).year
    pub_year = _parse_year(source.published_at)
    half_life_days = float(half_lives.get(mode.split("_")[0], half_lives.get("general", 730)))
    if pub_year is None:
        freshness = 0.65
    else:
        age_days = max(0, (current_year - pub_year) * 365)
        freshness = max(0.25, math.exp(-0.693 * age_days / max(180.0, half_life_days)))

    w_auth = float(weights.get("authority", 0.25))
    w_meth = float(weights.get("methodology", 0.25))
    w_rel = float(weights.get("relevance", 0.20))
    w_corr = float(weights.get("corroboration", 0.15))
    w_fresh = float(weights.get("freshness", 0.15))

    total = round(
        authority * w_auth
        + methodology * w_meth
        + relevance * w_rel
        + corroboration * w_corr
        + freshness * w_fresh,
        3,
    )

    breakdown = {
        "authority": round(authority, 3),
        "methodology": round(methodology, 3),
        "relevance": round(relevance, 3),
        "corroboration": round(corroboration, 3),
        "freshness": round(freshness, 3),
        "weighted_total": total,
        "notes": (
            f"Type={source.source_type}, PubYear={pub_year or 'unknown'}, "
            f"Corroborators={independent_corroborators}"
        ),
    }
    return total, breakdown
