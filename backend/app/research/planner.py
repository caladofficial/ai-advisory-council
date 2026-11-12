"""Topic Analyzer and 12-family Research Query Planner."""

from __future__ import annotations

import re
from typing import Any

from sqlalchemy.orm import Session

from app.database.models import Investigation, ResearchQuestion

STOPWORDS = {
    "the", "and", "for", "with", "that", "this", "from", "into", "about", "can",
    "would", "should", "could", "build", "make", "create", "platform", "system",
    "using", "used", "evaluate", "whether", "feasible", "feasibility", "idea",
    "project", "proposal", "software", "solution", "help", "need", "want",
}

DOMAIN_RULES: list[tuple[str, set[str]]] = [
    ("Healthcare & Life Sciences", {"health", "medical", "patient", "clinical", "hospital", "diagnosis", "doctor"}),
    ("Education & EdTech", {"education", "student", "school", "learning", "teacher", "curriculum", "rural"}),
    ("Financial & FinTech", {"finance", "bank", "payment", "loan", "trading", "crypto", "tax", "investment"}),
    ("AI & Software Engineering", {"ai", "llm", "agent", "model", "software", "api", "app", "saas", "code", "rag"}),
    ("Climate & Energy", {"energy", "solar", "climate", "carbon", "grid", "battery", "ev"}),
    ("Governance & Policy", {"policy", "government", "law", "regulation", "public", "civic", "compliance"}),
]


def infer_domain(topic: str, mode: str) -> str:
    tokens = set(re.findall(r"[a-z0-9]+", topic.lower()))
    best_domain = "Cross-Disciplinary"
    best_hits = 0
    for domain_name, keywords in DOMAIN_RULES:
        hits = len(tokens & keywords)
        if hits > best_hits:
            best_hits = hits
            best_domain = domain_name
    if best_hits == 0:
        return mode.replace("_", " ").title()
    return best_domain


def extract_core_keywords(topic: str, max_terms: int = 6) -> str:
    words = re.findall(r"[A-Za-z0-9\-\+]{3,}", topic)
    filtered = [w for w in words if w.lower() not in STOPWORDS]
    if not filtered:
        filtered = words
    # Deduplicate preserving order
    seen: set[str] = set()
    unique: list[str] = []
    for w in filtered:
        wl = w.lower()
        if wl not in seen:
            seen.add(wl)
            unique.append(w)
    return " ".join(unique[:max_terms])


def build_investigation_brief(inv: Investigation) -> dict[str, Any]:
    """Convert raw user intake into a structured investigation brief."""
    domain = infer_domain(inv.topic, inv.mode)
    inv.domain = domain
    keywords = extract_core_keywords(inv.topic)
    brief = {
        "investigation_id": inv.investigation_id,
        "topic": inv.topic,
        "objective": inv.objective,
        "domain": domain,
        "mode": inv.mode,
        "execution_profile": inv.execution_profile,
        "geography": inv.geography,
        "time_horizon": inv.time_horizon,
        "budget": inv.budget or "Unspecified (requires research/assumption)",
        "target_users": inv.target_users or "Unspecified (requires clarification/research)",
        "constraints": inv.constraints_json or [],
        "core_keywords": keywords,
        "status": inv.status,
    }
    inv.brief_json = brief
    return brief


def generate_research_plan(db: Session, inv: Investigation) -> list[ResearchQuestion]:
    """Generate topic-scoped questions across research families routed to suitable connectors."""
    core = extract_core_keywords(inv.topic, max_terms=5)
    geo = "" if inv.geography.lower() in {"global", "worldwide", ""} else inv.geography
    enabled = set(inv.enabled_connectors_json or [])

    def _pick(*preferred: str) -> str:
        for c in preferred:
            if c in enabled:
                return c
        return next(iter(enabled), "web_search")

    templates = [
        (
            "definition",
            f"What are the foundational definitions, standards, and scope of {core}?",
            f"{core} overview architecture standards",
            _pick("wikipedia", "web_search"),
            "HIGH",
            ["technical_architect", "user_advocate"],
        ),
        (
            "technical",
            f"What open-source implementations, dependencies, and technical limitations exist for {core}?",
            f"{core}",
            _pick("github", "web_search"),
            "HIGH",
            ["technical_architect", "operations_expert", "security_guardian"],
        ),
        (
            "ai_models",
            f"Which open-weight AI models, datasets, and licenses exist on Hugging Face for {core}?",
            f"{core}",
            _pick("huggingface", "github", "web_search"),
            "HIGH",
            ["technical_architect", "legal_ethics"],
        ),
        (
            "academic",
            f"What peer-reviewed empirical evidence, benchmarks, and limitations exist for {core}?",
            f"{core} empirical evaluation effectiveness",
            _pick("openalex", "crossref", "arxiv"),
            "HIGH",
            ["scientific_analyst", "technical_architect"],
        ),
        (
            "preprints",
            f"What recent scientific preprints or experimental methodologies address {core}?",
            f"{core}",
            _pick("arxiv", "openalex"),
            "MEDIUM",
            ["scientific_analyst", "devils_advocate"],
        ),
        (
            "market",
            f"What is the existing market demand, user adoption, and competitor landscape in {geo or 'target markets'}?",
            f"{core} {geo} market adoption competitors statistics".strip(),
            _pick("web_search", "wikipedia"),
            "HIGH",
            ["market_analyst", "user_advocate"],
        ),
        (
            "financial",
            f"What are realistic development, infrastructure, API, and operating costs for {core}?",
            f"{core} pricing infrastructure cost ROI",
            _pick("web_search", "github"),
            "HIGH",
            ["financial_strategist", "operations_expert"],
        ),
        (
            "legal_security",
            f"What regulatory, privacy, licensing, and cybersecurity requirements apply in {geo or 'target jurisdictions'}?",
            f"{core} {geo} regulations data privacy compliance security risks".strip(),
            _pick("web_search", "crossref"),
            "HIGH",
            ["legal_ethics", "security_guardian"],
        ),
        (
            "failure",
            f"Why have comparable {core} projects failed or faced adoption bottlenecks?",
            f"{core} project failure risks challenges limitations",
            _pick("web_search", "openalex"),
            "HIGH",
            ["devils_advocate", "implementation_strategist"],
        ),
    ]

    db.query(ResearchQuestion).filter_by(investigation_id=inv.investigation_id).delete()
    created: list[ResearchQuestion] = []
    for idx, (family, question, sq, connector, prio, advisors) in enumerate(templates, start=1):
        rq = ResearchQuestion(
            question_id=f"{inv.investigation_id}-RQ-{idx:02d}",
            investigation_id=inv.investigation_id,
            query_family=family,
            question=question,
            search_query=" ".join(sq.split()),
            connector=connector,
            priority=prio,
            assigned_advisors_json=advisors,
        )
        db.add(rq)
        created.append(rq)
    db.flush()
    return created
