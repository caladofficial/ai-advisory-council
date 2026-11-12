"""Contradiction detector identifying conflicting claims across independent sources."""

from __future__ import annotations

import re

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database.models import Claim, ClaimEvidence, Contradiction

POSITIVE_SIGNALS = {
    "feasible", "scalable", "affordable", "effective", "improves", "reduces", "reliable",
    "low-cost", "open-source", "mit", "apache", "validated", "adopted", "ready", "free",
}
NEGATIVE_SIGNALS = {
    "infeasible", "fails", "failed", "limitation", "prohibitive", "expensive", "unreliable",
    "deprecated", "archived", "agpl", "violation", "risk", "insufficient", "barrier", "not", "cannot",
}
STOPWORDS = {"the", "and", "for", "with", "that", "this", "from", "are", "was", "were", "have", "has", "not"}


def _content_tokens(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-z0-9]{4,}", text.lower()) if w not in STOPWORDS}


def detect_contradictions(db: Session, investigation_id: str) -> list[Contradiction]:
    """Compare extracted claims across different evidence chunks for opposing polarity or numeric conflicts."""
    claims = list(db.scalars(select(Claim).where(Claim.investigation_id == investigation_id)).all())
    links = db.scalars(
        select(ClaimEvidence).where(ClaimEvidence.claim_id.in_([c.claim_id for c in claims]))
    ).all() if claims else []

    evd_by_claim: dict[str, list[str]] = {}
    for link in links:
        evd_by_claim.setdefault(link.claim_id, []).append(link.evidence_id)

    db.query(Contradiction).filter_by(investigation_id=investigation_id).delete()
    existing_count = 0
    found: list[Contradiction] = []

    for i in range(len(claims)):
        ca = claims[i]
        ta = _content_tokens(ca.claim_text)
        pos_a = len(ta & POSITIVE_SIGNALS)
        neg_a = len(ta & NEGATIVE_SIGNALS)
        if pos_a == 0 and neg_a == 0:
            continue

        for j in range(i + 1, len(claims)):
            cb = claims[j]
            if ca.category != cb.category and ca.category != "general" and cb.category != "general":
                continue
            ev_a = evd_by_claim.get(ca.claim_id, [])
            ev_b = evd_by_claim.get(cb.claim_id, [])
            if ev_a and ev_b and set(ev_a) == set(ev_b):
                continue

            tb = _content_tokens(cb.claim_text)
            shared_subject = (ta & tb) - POSITIVE_SIGNALS - NEGATIVE_SIGNALS
            if len(shared_subject) < 2:
                continue

            pos_b = len(tb & POSITIVE_SIGNALS)
            neg_b = len(tb & NEGATIVE_SIGNALS)

            polarity_conflict = (pos_a > neg_a and neg_b > pos_b) or (neg_a > pos_a and pos_b > neg_b)
            numeric_conflict = bool(
                ca.value_unit and cb.value_unit and ca.value_unit != cb.value_unit and len(shared_subject) >= 3
            )

            if polarity_conflict or numeric_conflict:
                existing_count += 1
                cid = f"{investigation_id}-CONTRA-{existing_count:03d}"
                reason = "Numeric divergence" if numeric_conflict and not polarity_conflict else "Opposing polarity on shared topic"
                contra = Contradiction(
                    contradiction_id=cid,
                    investigation_id=investigation_id,
                    claim_a_id=ca.claim_id,
                    claim_b_id=cb.claim_id,
                    evidence_a_id=ev_a[0] if ev_a else None,
                    evidence_b_id=ev_b[0] if ev_b else None,
                    summary=f"{reason} ({', '.join(sorted(shared_subject)[:4])}): '{ca.claim_text[:110]}' vs '{cb.claim_text[:110]}'",
                    severity="HIGH" if ca.category in {"financial", "legal", "security"} else "MEDIUM",
                    resolved=False,
                )
                db.add(contra)
                found.append(contra)
                if len(found) >= 15:
                    db.flush()
                    return found

    db.flush()
    return found
