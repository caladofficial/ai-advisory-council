"""Model Registry, awesome-freellm-apis catalog, Health Checks, Quota Policy, and Advisor Assignment routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_providers_config, get_settings
from app.database.models import ModelRegistryEntry
from app.database.repository import (
    get_advisor_model_bindings,
    get_requests_today_by_provider,
    log_audit_event,
    upsert_advisor_model_binding,
)
from app.database.session import get_db
from app.models.catalog_importer import get_merged_provider_catalog, sync_model_registry
from app.models.health_checks import run_registry_health_checks
from app.models.quota_manager import quota_manager
from app.schemas.model_registry import (
    AdvisorModelOverrideIn,
    ApiKeyConfigureIn,
    CostPolicyOut,
    HealthCheckRequest,
    HealthCheckResult,
    ModelRegistryEntryOut,
    ProviderOut,
)
from app.security.secrets import set_provider_api_key

router = APIRouter(tags=["models"])


@router.get("/api/cost-policy", response_model=CostPolicyOut)
def get_cost_policy():
    s = get_settings()
    return CostPolicyOut(
        mode=s.cost_policy_mode,
        allow_paid_providers=s.allow_paid_providers,
        allow_credit_card_fallback=s.allow_credit_card_fallback,
        allow_over_quota_requests=s.allow_over_quota_requests,
    )


@router.get("/api/providers", response_model=list[ProviderOut])
def list_providers(db: Session = Depends(get_db)):
    req_today = get_requests_today_by_provider(db)
    # Combine DB counts and in-memory quota counter
    mem_counts = quota_manager.snapshot_usage()
    for k, v in mem_counts.items():
        req_today[k] = max(req_today.get(k, 0), v)
    return [ProviderOut.model_validate(item) for item in get_merged_provider_catalog(req_today)]


@router.post("/api/providers/configure-key")
def configure_provider_key(payload: ApiKeyConfigureIn, db: Session = Depends(get_db)):
    providers = get_providers_config().get("providers", {})
    cfg = providers.get(payload.provider_id)
    if not cfg:
        raise HTTPException(status_code=404, detail=f"Unknown or unverified provider {payload.provider_id!r}")
    env_name = cfg.get("api_key_env")
    if not env_name:
        raise HTTPException(status_code=400, detail="Provider does not require an API key")

    set_provider_api_key(env_name, payload.api_key)
    log_audit_event(
        db,
        investigation_id=None,
        actor="user",
        event_type="PROVIDER_KEY_CONFIGURED",
        stage="CONFIG",
        summary=f"Configured server-side free API key for provider {payload.provider_id}.",
    )
    db.commit()
    return {"configured": True, "provider_id": payload.provider_id}


@router.get("/api/models", response_model=list[ModelRegistryEntryOut])
def list_models(provider: str = "", db: Session = Depends(get_db)):
    query = select(ModelRegistryEntry)
    if provider:
        query = query.where(ModelRegistryEntry.provider == provider)
    rows = db.scalars(query).all()
    return [
        ModelRegistryEntryOut(
            id=r.id,
            provider=r.provider,
            model_id=r.model_id,
            display_name=r.display_name,
            execution_mode=r.execution_mode,
            family=r.family,
            capabilities=r.capabilities_json or [],
            supports_tools=r.supports_tools,
            supports_json=r.supports_json,
            context_window=r.context_window,
            rate_limit_note=r.rate_limit_note,
            is_free=r.is_free,
            availability_status=r.availability_status,
            last_health_check=r.last_health_check,
            quality_score=r.quality_score,
            latency_ms=r.latency_ms,
            enabled=r.enabled,
        )
        for r in rows
    ]


@router.post("/api/models/sync")
def sync_models_endpoint(include_hf: bool = False, db: Session = Depends(get_db)):
    added = sync_model_registry(db, include_ollama=True, include_hf=include_hf)
    db.commit()
    return {"synced_new_models": added}


@router.post("/api/models/health-check", response_model=list[HealthCheckResult])
async def health_check_models(payload: HealthCheckRequest, db: Session = Depends(get_db)):
    results = await run_registry_health_checks(
        db,
        provider=payload.provider,
        model_id=payload.model_id,
        test_json=payload.test_json,
    )
    db.commit()
    return results


@router.get("/api/models/assignments")
def get_advisor_assignments(db: Session = Depends(get_db)):
    bindings = get_advisor_model_bindings(db)
    return {aid: {"provider": p, "model_id": m} for aid, (p, m) in bindings.items()}


@router.post("/api/models/assign-advisor")
def assign_advisor_model(payload: AdvisorModelOverrideIn, db: Session = Depends(get_db)):
    try:
        quota_manager.assert_zero_paid_allowed(payload.provider, payload.model_id)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    upsert_advisor_model_binding(db, payload.advisor_id, payload.provider, payload.model_id)
    db.commit()
    return {"assigned": True, "advisor_id": payload.advisor_id, "provider": payload.provider, "model_id": payload.model_id}
