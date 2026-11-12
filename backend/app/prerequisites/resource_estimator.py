"""Execution Prerequisites, Quota Health, and Zero-Paid Cost Estimator."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_agents_config, get_settings
from app.database.models import Investigation, ModelRegistryEntry
from app.models.router import resolve_candidate_models
from app.schemas.prerequisites import ResourceEstimateOut


def estimate_execution_resources(db: Session, inv: Investigation) -> ResourceEstimateOut:
    """Verify healthy/configured free models and estimate token/latency/cost budget prior to debate."""
    settings = get_settings()
    agents_cfg = get_agents_config()
    exec_cfg = agents_cfg.get("execution", {})

    if inv.execution_profile == "prototype_3_plus_1":
        advisor_ids = exec_cfg.get("prototype_advisor_ids", ["technical_architect", "financial_strategist", "devils_advocate"])
    else:
        advisor_ids = [a["advisor_id"] for a in agents_cfg.get("advisors", [])]

    # Calls: initial analyses + ~4 targeted challenges/rebuttals + final submissions + 1 judge
    n_advisors = len(advisor_ids)
    estimated_calls = n_advisors * 2 + min(8, n_advisors * 2) + 2
    estimated_tokens = estimated_calls * 2200

    healthy_providers: set[str] = set()
    usable_models: set[str] = set()
    warnings: list[str] = []

    for aid in [*advisor_ids, "chief_judge"]:
        cands = resolve_candidate_models(db, aid)
        for prov, mid in cands[:2]:
            healthy_providers.add(prov)
            usable_models.add(f"{prov}:{mid}")

    registry_count = len(list(db.scalars(select(ModelRegistryEntry).where(ModelRegistryEntry.enabled.is_(True))).all()))
    if len(healthy_providers) == 1 and "ollama" in healthy_providers:
        warnings.append(
            "Running purely on local Ollama; configure optional free API keys (Groq/Gemini/HF/OpenRouter) in Model Registry for stronger cross-family model diversity."
        )

    is_local_only = healthy_providers == {"ollama"}
    est_duration = estimated_calls * (7 if is_local_only else 3)

    return ResourceEstimateOut(
        estimated_advisor_calls=estimated_calls,
        estimated_total_tokens=estimated_tokens,
        estimated_cost_usd=0.0,
        cost_policy_mode=settings.cost_policy_mode,
        estimated_duration_seconds=est_duration,
        available_models_count=max(len(usable_models), registry_count),
        providers_healthy=sorted(healthy_providers),
        fallback_ready=len(usable_models) >= 1,
        warnings=warnings,
    )
