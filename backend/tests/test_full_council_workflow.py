"""Acceptance tests for Full 10+1 Workflow, Blind Isolation, Non-Majority Judge, Hard Blockers, Checkpoint Resume, and Exports."""

from __future__ import annotations

import json

import pytest

from app.database.models import AdvisorReport, Investigation, PrivateNote
from app.database.repository import create_investigation
from app.evaluation.independence import compute_independence_metrics
from app.models.provider_adapters import LLMCallResult
from app.orchestration.workflow import execute_investigation_workflow
from app.research.crawlers.base import RawSourceRecord
from app.schemas.investigation import ExecutionProfile, InvestigationCreate


def _stub_llm_router(monkeypatch, *, judge_verdict: str = "PILOT_FIRST", add_hard_blocker: bool = False):
    """Stub LLM calls offline so all 10 advisors + moderator + judge run deterministically without network."""

    async def fake_call(*, provider: str, model_id: str, system_prompt: str, user_prompt: str, **kwargs):
        if "INDEPENDENT CHIEF JUDGE" in system_prompt.upper():
            blockers = (
                [{"blocker_id": "BLK-01", "category": "Legal", "severity": "CRITICAL", "description": "Missing mandatory clinical regulatory approval", "evidence_ids": ["EVD-001"]}]
                if add_hard_blocker
                else []
            )
            payload = {
                "verdict": judge_verdict,
                "confidence": 0.78,
                "executive_summary": "Independent judge evaluated evidence across all 10 advisors.",
                "decision_rationale": "Evaluated verifiable evidence, contradictions, and financial bounds rather than majority count.",
                "dimension_scores": {
                    "technical_feasibility": 82,
                    "financial_feasibility": 64,
                    "market_user_value": 74,
                    "operational_feasibility": 60,
                    "legal_ethical_compliance": 45 if add_hard_blocker else 75,
                    "security_safety": 68,
                    "evidence_strength": 70,
                    "long_term_sustainability": 65,
                },
                "dimension_rationales": {"technical_feasibility": "Supported by open-source MIT baseline EVD-001."},
                "best_arguments_for": ["Strong technical baseline (EVD-001)."],
                "strongest_arguments_against": ["Operational cost uncertainty raised by Devil's Advocate."],
                "established_facts": ["MIT open-source baseline verified in EVD-001."],
                "uncertain_areas": ["Long-term retention beyond 12 months."],
                "contradicted_claims": [],
                "hard_blockers": blockers,
                "advisor_rationales": [{"advisor_id": "devils_advocate", "decision": "ACCEPTED", "reason": "Valid failure scenario."}],
                "preserved_minority_opinions": ["Devil's Advocate flagged maintenance bottleneck."],
                "required_changes": ["Run a 3-school pilot before full rollout."],
                "conditions_for_approval": ["Verify regulatory compliance prior to scale."],
                "prerequisites_needed": ["Baseline pilot metrics"],
                "risk_register": [{"risk_id": "RSK-01", "title": "Maintenance gap", "category": "Operations", "likelihood": "MEDIUM", "impact": "HIGH", "mitigation": "Remote telemetry", "owner_role": "Operations Expert", "evidence_ids": ["EVD-001"]}],
                "roadmap": [{"phase": "Phase 1", "title": "Controlled Pilot", "owner_role": "Implementation Strategist", "deliverable": "Pilot deployment", "acceptance_criterion": "80% weekly active usage", "stop_condition": "<40% retention at day 60"}],
                "kpis": ["Weekly active schools >= 80%"],
                "remaining_questions": ["Confirm ongoing grant renewal."],
                "evidence_ids_cited": ["EVD-001"],
                "disagreed_with_majority": judge_verdict in {"NO_GO", "PILOT_FIRST"},
            }
        elif "DEBATE MODERATOR" in system_prompt.upper():
            payload = {
                "challenges": [
                    {
                        "challenger_id": "devils_advocate",
                        "target_advisor_id": "technical_architect",
                        "target_claim_id": "CLAIM-001",
                        "disputed_claim_text": "Deployment is feasible under current budget",
                        "challenge_argument": "Maintenance and hardware failure rates could double operating burn.",
                        "evidence_ids": ["EVD-001"],
                        "requested_action": "Quantify hardware spares and revise estimate.",
                        "impact_score": 5,
                        "uncertainty_score": 4,
                        "relevance_score": 5,
                    },
                    {
                        "challenger_id": "financial_strategist",
                        "target_advisor_id": "implementation_strategist" if "implementation_strategist" in user_prompt else "devils_advocate",
                        "target_claim_id": "CLAIM-002",
                        "disputed_claim_text": "Rollout timeline and budget assumptions",
                        "challenge_argument": "Verify 12-month CAPEX/OPEX coverage under worst-case scenario.",
                        "evidence_ids": ["EVD-001"],
                        "requested_action": "Align MVP scope to budget ceiling.",
                        "impact_score": 4,
                        "uncertainty_score": 4,
                        "relevance_score": 4,
                    },
                ]
            }
        elif "disposition" in user_prompt.lower() and "challenge from" in user_prompt.lower():
            payload = {
                "disposition": "PARTIALLY_ACCEPTED",
                "position_change": "PARTIALLY_REVISED",
                "response_argument": "Acknowledged spare-part budget buffer; maintained technical feasibility on EVD-001.",
                "evidence_ids": ["EVD-001"],
                "revised_recommendation": "Add 15% hardware reserve.",
                "calculation_summary": "",
            }
        else:
            # Distinct per-role stance so independence metrics register multi-stance council
            is_adversarial = "DEVIL'S ADVOCATE" in system_prompt.upper() or "SECURITY" in system_prompt.upper()
            is_fin = "FINANCIAL" in system_prompt.upper()
            stance = "OPPOSE" if is_adversarial else ("CONDITIONAL" if is_fin else "SUPPORT")
            role_tag = system_prompt.splitlines()[18][:40] if len(system_prompt.splitlines()) > 18 else "Specialist"
            payload = {
                "interpretation": f"Scoped analysis from {role_tag}",
                "stance": stance,
                "confidence": 0.72 if not is_adversarial else 0.65,
                "executive_findings": f"{role_tag} findings grounded in EVD-001 and verified constraints.",
                "key_claims": [{"claim_id": "C1", "statement": "Baseline supported by EVD-001.", "classification": "FACT", "evidence_ids": ["EVD-001"]}],
                "advantages": ["Open-source MIT stack lowers initial cost (EVD-001)."],
                "risks_and_weaknesses": ["Requires sustained local support."],
                "self_identified_weakness": "Limited multi-year empirical longitudinal sample.",
                "assumptions": ["Local hardware uptime >= 90%"],
                "missing_evidence": ["District-level retention telemetry"],
                "recommendations": ["Start with a controlled 90-day pilot."],
                "evidence_ids_cited": ["EVD-001"],
                "private_working_notes": f"SECRET_NOTE_FOR_{role_tag}",
            }

        return LLMCallResult(
            content=json.dumps(payload),
            provider="ollama",
            model_id="llama3.2:3b",
            prompt_tokens=150,
            completion_tokens=120,
            latency_ms=15,
        )

    monkeypatch.setattr("app.models.router.call_chat_completion", fake_call)
    monkeypatch.setattr(
        "app.models.router.resolve_candidate_models",
        lambda db, aid: [("ollama", "llama3.2:3b")],
    )


def _stub_research_connectors(monkeypatch):
    async def fake_collect(db, inv, questions, extra_queries=None):
        from app.research.collector import persist_raw_records
        recs = [
            RawSourceRecord(
                url="https://doi.org/10.1000/pilot",
                title="Rural AI Pilot Evaluation",
                source_type="academic",
                publisher="Open Research Press",
                author="K. Verma",
                published_at="2026-06-01",
                canonical_identifier="https://doi.org/10.1000/pilot",
                content="Controlled rural AI tutoring pilot achieved 22% score gains under INR 500000 budget using MIT-licensed open models.",
            ),
            RawSourceRecord(
                url="https://github.com/open-edu/rural-tutor",
                title="GitHub: open-edu/rural-tutor",
                source_type="github",
                publisher="GitHub",
                published_at="2026-09-15",
                canonical_identifier="github:open-edu/rural-tutor",
                license_name="MIT",
                content="MIT licensed Python backend and offline sync architecture with 800 stars and active maintenance.",
            ),
        ]
        srcs, chs = persist_raw_records(db, inv.investigation_id, recs)
        return {"tasks_completed": 2, "tasks_failed": 0, "sources_added": len(srcs), "evidence_chunks_added": len(chs)}

    monkeypatch.setattr("app.orchestration.workflow.run_research_collection", fake_collect)


@pytest.mark.asyncio
async def test_full_10_plus_1_council_and_exports(isolated_app, monkeypatch):
    client, db_session = isolated_app
    _stub_llm_router(monkeypatch, judge_verdict="GO", add_hard_blocker=True)
    _stub_research_connectors(monkeypatch)

    resp = client.post(
        "/api/investigations",
        json={
            "topic": "Deploy an AI tutoring system for rural schools in India",
            "mode": "education_feasibility" if False else "business_feasibility",
            "execution_profile": ExecutionProfile.FULL_COUNCIL.value,
            "geography": "India",
            "budget": "INR 500000",
            "target_users": "Secondary school students",
            "auto_start": False,
        },
    )
    assert resp.status_code == 200
    inv_id = resp.json()["investigation_id"]

    await execute_investigation_workflow(inv_id, force_proceed_warnings=True)

    inv_data = client.get(f"/api/investigations/{inv_id}").json()
    assert inv_data["status"] == "COMPLETED"
    # Hard blocker overrides GO -> CONDITIONAL_GO!
    assert inv_data["verdict"] == "CONDITIONAL_GO"

    advisors = client.get(f"/api/investigations/{inv_id}/advisors").json()
    assert len(advisors) == 10
    for adv in advisors:
        assert adv["initial_report"] is not None
        assert adv["final_report"] is not None

    ind = client.get(f"/api/investigations/{inv_id}/independence").json()
    assert ind["advisor_count"] == 10
    assert ind["divergence_score"] > 0

    debate = client.get(f"/api/investigations/{inv_id}/debate").json()
    assert len(debate["challenges"]) >= 2
    assert any(m["message_type"] == "REBUTTAL" for m in debate["messages"])

    judge = client.get(f"/api/investigations/{inv_id}/judge").json()
    assert judge["verdict"] == "CONDITIONAL_GO"
    assert len(judge["scorecard"]) == 8
    assert len(judge["hard_blockers"]) == 1

    # Verify all export formats work cleanly!
    for fmt, expected_ct in [
        ("md", "text/markdown"),
        ("json", "application/json"),
        ("html", "text/html"),
        ("pdf", "application/pdf"),
        ("csv", "text/csv"),
        ("zip", "application/zip"),
    ]:
        exp = client.get(f"/api/investigations/{inv_id}/export/{fmt}")
        assert exp.status_code == 200
        assert expected_ct in exp.headers["content-type"]
        assert len(exp.content) > 50

    # Verify private notes were stored strictly per-advisor and audit trail recorded
    with db_session.session_scope() as db:
        notes = db.query(PrivateNote).filter_by(investigation_id=inv_id).all()
        assert len(notes) == 10
        reports = db.query(AdvisorReport).filter_by(investigation_id=inv_id).all()
        assert len(reports) == 20  # 10 initial + 10 final preserved separately!

    # Resume idempotency check: re-running workflow must NOT duplicate initial/final reports!
    await execute_investigation_workflow(inv_id, force_proceed_warnings=True)
    with db_session.session_scope() as db:
        reports_after = db.query(AdvisorReport).filter_by(investigation_id=inv_id).all()
        assert len(reports_after) == 20
