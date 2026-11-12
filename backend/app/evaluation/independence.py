"""Measures genuine inter-advisor independence and detects correlated-error echo chambers."""

from __future__ import annotations

import re
from collections import Counter

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.models import AdvisorReport, AdvisorSession, ModelRegistryEntry
from app.schemas.evaluation import IndependenceMetricsOut

STOPWORDS = {"the", "and", "for", "with", "that", "this", "from", "should", "will", "have", "must"}


def _word_set(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-z0-9]{4,}", (text or "").lower()) if w not in STOPWORDS}


def compute_independence_metrics(db: Session, investigation_id: str) -> IndependenceMetricsOut:
    """Quantify stance diversity, pairwise lexical overlap, and model-family heterogeneity."""
    reports = list(
        db.scalars(
            select(AdvisorReport).where(
                AdvisorReport.investigation_id == investigation_id,
                AdvisorReport.phase == "initial",
            )
        ).all()
    )
    sessions = list(
        db.scalars(select(AdvisorSession).where(AdvisorSession.investigation_id == investigation_id)).all()
    )
    reg_families = {
        (e.provider, e.model_id): e.family
        for e in db.scalars(select(ModelRegistryEntry)).all()
    }

    stances = dict(Counter(r.stance for r in reports))
    families = {
        reg_families.get((s.assigned_provider, s.assigned_model), s.assigned_model.split(":")[0])
        for s in sessions
    }

    # Compute pairwise Jaccard similarity of initial findings + cited evidence overlap
    lex_sims: list[float] = []
    evd_overlaps: list[float] = []
    for i in range(len(reports)):
        ra = reports[i].report_json or {}
        wa = _word_set(str(ra.get("executive_findings", "")))
        ea = set(ra.get("evidence_ids_cited") or [])
        for j in range(i + 1, len(reports)):
            rb = reports[j].report_json or {}
            wb = _word_set(str(rb.get("executive_findings", "")))
            eb = set(rb.get("evidence_ids_cited") or [])
            if wa and wb:
                lex_sims.append(len(wa & wb) / len(wa | wb))
            if ea and eb:
                evd_overlaps.append(len(ea & eb) / len(ea | eb))

    mean_lex = round(sum(lex_sims) / len(lex_sims), 3) if lex_sims else 0.0
    mean_evd = round(sum(evd_overlaps) / len(evd_overlaps), 3) if evd_overlaps else 0.0

    # Divergence score (0-100): rewards stance spread, low lexical mimicry, and multi-family models
    stance_diversity = min(1.0, (len(stances) - 1) / 2.0) if len(reports) > 1 else 0.0
    family_bonus = min(1.0, len(families) / 3.0) if families else 0.0
    divergence = round(
        100.0 * (0.45 * (1.0 - mean_lex) + 0.35 * stance_diversity + 0.20 * family_bonus),
        1,
    )

    warning = None
    if len(reports) >= 3:
        if len(families) <= 1 and len(stances) <= 1:
            warning = (
                "Correlated-risk alert: all advisors share 1 model family and converged on identical initial stance."
            )
        elif mean_lex > 0.55:
            warning = (
                f"High lexical similarity ({mean_lex:.0%}) across initial reports; verify advisors are not mimicking boilerplate."
            )

    return IndependenceMetricsOut(
        investigation_id=investigation_id,
        advisor_count=len(reports),
        stance_distribution=stances,
        pairwise_claim_overlap=mean_evd,
        lexical_similarity_mean=mean_lex,
        distinct_model_families=len(families),
        divergence_score=divergence,
        correlated_risk_warning=warning,
    )
