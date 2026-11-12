"""Three-level deduplication and syndication detection for retrieved sources."""

from __future__ import annotations

import hashlib
import re
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

TRACKING_PARAMS = {"utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content", "ref", "fbclid", "gclid"}


def canonicalize_url(url: str) -> str:
    """Normalize URL scheme, host, trailing slashes, and strip tracking parameters."""
    raw = (url or "").strip()
    if not raw:
        return ""
    parsed = urlparse(raw)
    scheme = parsed.scheme.lower() or "https"
    netloc = parsed.netloc.lower()
    if netloc.startswith("www."):
        netloc = netloc[4:]
    if netloc == "dx.doi.org":
        netloc = "doi.org"
    path = re.sub(r"/+$", "", parsed.path or "")
    filtered_qs = [
        (k, v) for k, v in parse_qsl(parsed.query, keep_blank_values=False) if k.lower() not in TRACKING_PARAMS
    ]
    query = urlencode(sorted(filtered_qs))
    return urlunparse((scheme, netloc, path, "", query, ""))


def compute_content_hash(text: str) -> str:
    normalized = re.sub(r"\s+", " ", (text or "").strip().lower())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _shingles(text: str, size: int = 4) -> set[str]:
    words = re.findall(r"[a-z0-9]+", (text or "").lower())
    if len(words) < size:
        return {" ".join(words)} if words else set()
    return {" ".join(words[i : i + size]) for i in range(len(words) - size + 1)}


def jaccard_similarity(text_a: str, text_b: str) -> float:
    sa = _shingles(text_a)
    sb = _shingles(text_b)
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / len(sa | sb)


class DeduplicationIndex:
    """Detects exact canonical URL/DOI matches, SHA-256 matches, and syndicated near-duplicates."""

    def __init__(self, similarity_threshold: float = 0.72) -> None:
        self.similarity_threshold = similarity_threshold
        self._by_url: dict[str, str] = {}
        self._by_identifier: dict[str, str] = {}
        self._by_hash: dict[str, str] = {}
        self._texts: list[tuple[str, str]] = []  # (source_id, text)

    def check_and_register(
        self,
        source_id: str,
        *,
        canonical_url: str,
        canonical_identifier: str | None,
        content_hash: str,
        text: str,
    ) -> tuple[bool, str | None]:
        """Return (is_duplicate_or_syndicated, original_source_id)."""
        if canonical_url and canonical_url in self._by_url:
            return True, self._by_url[canonical_url]
        if canonical_identifier and canonical_identifier.lower() in self._by_identifier:
            return True, self._by_identifier[canonical_identifier.lower()]
        if content_hash in self._by_hash:
            return True, self._by_hash[content_hash]

        for orig_id, orig_text in self._texts:
            if jaccard_similarity(text, orig_text) >= self.similarity_threshold:
                return True, orig_id

        if canonical_url:
            self._by_url[canonical_url] = source_id
        if canonical_identifier:
            self._by_identifier[canonical_identifier.lower()] = source_id
        self._by_hash[content_hash] = source_id
        if len(text) > 80:
            self._texts.append((source_id, text[:3000]))
        return False, None
