"""Acceptance tests for Uploads, Evaluation Lab, Provider Registry, Non-Majority Judge, and Governance APIs."""

from __future__ import annotations

import json

import pytest

from app.agents.judge import run_chief_judge
from app.database.models import AdvisorReport, AdvisorSession, Investigation
from app.database.repository import create_investigation
from app.models.provider_adapters import LLMCallResult
from app.schemas.investigation import InvestigationCreate


def test_uploads_evaluation_registry_and_governance_routes(isolated_app):
    client, _ = isolated_app

    # Cost policy verification
    cp = client.get("/api/cost-policy").json()
    assert cp["mode"] == "zero_paid"
    assert cp["allow_paid_providers"] is False
    assert cp["allow_credit_card_fallback"] is False

    # Providers & Models catalog
    provs = client.get("/api/providers").json()
    assert len(provs) >= 30
    assert any(p["provider_id"] == "groq" for p in provs)

    # Configure free API key server-side & ensure raw secret is NEVER returned!
    secret = "gsk_testsecretkey1234567890"
    cfg_resp = client.post("/api/providers/configure-key", json={"provider_id": "groq", "api_key": secret})
    assert cfg_resp.status_code == 200
    provs_after = client.get("/api/providers").json()
    groq = next(p for p in provs_after if p["provider_id"] == "groq")
    assert groq["has_key_configured"] is True
    assert secret not in json.dumps(provs_after)

    # Assign advisor model & check zero-paid block on paid assignment
    ok_assign = client.post(
        "/api/models/assign-advisor",
        json={"advisor_id": "technical_architect", "provider": "ollama", "model_id": "llama3.2:3b"},
    )
    assert ok_assign.status_code == 200
    bad_assign = client.post(
        "/api/models/assign-advisor",
        json={"advisor_id": "technical_architect", "provider": "openrouter", "model_id": "openai/gpt-4o"},
    )
    assert bad_assign.status_code == 400

    # Evaluation lab suite
    bench = client.post("/api/evaluation/run?include_live_models=false").json()
    assert bench["passed_cases"] == bench["total_cases"]
    assert bench["overall_score"] == 100.0

    # Create investigation, upload document, reject disallowed extension, pause/cancel/delete
    inv_id = client.post(
        "/api/investigations",
        json={"topic": "Evaluate open-source local AI study assistant", "auto_start": False},
    ).json()["investigation_id"]

    bad_up = client.post(
        f"/api/investigations/{inv_id}/upload",
        files={"file": ("malware.exe", b"binary", "application/octet-stream")},
    )
    assert bad_up.status_code == 400

    good_up = client.post(
        f"/api/investigations/{inv_id}/upload",
        files={
            "file": (
                "internal_notes.md",
                b"Our pilot budget is strictly capped at $1500 and requires offline local execution.",
                "text/markdown",
            )
        },
    )
    assert good_up.status_code == 200
    assert good_up.json()["chunks_created"] >= 1

    cancel = client.post(f"/api/investigations/{inv_id}/cancel")
    assert cancel.status_code == 200
    assert client.get(f"/api/investigations/{inv_id}").json()["status"] == "CANCELLED"

    deleted = client.delete(f"/api/investigations/{inv_id}")
    assert deleted.status_code == 200
    assert client.get(f"/api/investigations/{inv_id}").status_code == 404


@pytest.mark.asyncio
async def test_judge_rejects_unsupported_majority_when_zero_evidence(isolated_app, monkeypatch):
    _, db_session = isolated_app

    async def fake_judge_call(**kwargs):
        return LLMCallResult(
            content=json.dumps({
                "verdict": "GO",
                "confidence": 0.9,
                "executive_summary": "All advisors said GO despite zero evidence.",
                "decision_rationale": "Test majority override.",
                "dimension_scores": {
                    "technical_feasibility": 90,
                    "financial_feasibility": 90,
                    "market_user_value": 90,
                    "operational_feasibility": 90,
                    "legal_ethical_compliance": 90,
                    "security_safety": 90,
                    "evidence_strength": 10,
                    "long_term_sustainability": 90,
                },
                "disagreed_with_majority": False,
            }),
            provider="ollama",
            model_id="llama3.2:3b",
            prompt_tokens=100,
            completion_tokens=100,
            latency_ms=10,
        )

    monkeypatch.setattr("app.models.router.call_chat_completion", fake_judge_call)
    monkeypatch.setattr("app.models.router.resolve_candidate_models", lambda db, aid: [("ollama", "llama3.2:3b")])

    with db_session.session_scope() as db:
        inv = create_investigation(db, InvestigationCreate(topic="Unverified perpetual motion generator startup"))
        sess = AdvisorSession(
            session_id=f"{inv.investigation_id}-technical_architect",
            investigation_id=inv.investigation_id,
            advisor_id="technical_architect",
            advisor_name="Technical Architect",
            advisor_role="Technical Feasibility",
            status="completed",
        )
        db.add(sess)
        db.flush()
        db.add(
            AdvisorReport(
                investigation_id=inv.investigation_id,
                session_id=sess.session_id,
                advisor_id="technical_architect",
                phase="final",
                stance="SUPPORT",
                confidence=0.95,
                report_json={"stance": "SUPPORT", "confidence": 0.95, "executive_findings": "Looks great!"},
            )
        )
        db.flush()

        # Zero EvidenceChunks exist -> Judge deterministic guardrail MUST block GO -> INSUFFICIENT_EVIDENCE!
        evaluation = await run_chief_judge(db, inv)
        assert evaluation.verdict == "INSUFFICIENT_EVIDENCE"
        assert evaluation.disagreed_with_majority is True
