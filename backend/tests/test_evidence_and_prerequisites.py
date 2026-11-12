"""Acceptance tests for Evidence verification, Contradiction detection, and 100-pt Readiness Gate."""

from __future__ import annotations

from app.database.models import Claim, Contradiction, Investigation
from app.evidence.verifier import verify_investigation_evidence
from app.prerequisites.readiness_gate import evaluate_readiness_gate
from app.research.collector import persist_raw_records
from app.research.crawlers.base import RawSourceRecord
from app.schemas.investigation import InvestigationCreate
from app.database.repository import create_investigation


def test_evidence_contradictions_and_readiness_gate(isolated_app):
    _, db_session = isolated_app
    with db_session.session_scope() as db:
        inv = create_investigation(
            db,
            InvestigationCreate(
                topic="Build an affordable offline AI education platform for rural secondary schools in India",
                budget="INR 500000",
                target_users="Rural secondary school students and teachers",
                geography="India",
            ),
        )
        records = [
            RawSourceRecord(
                url="https://doi.org/10.1000/study-a",
                title="Peer-Reviewed Offline AI Study",
                source_type="academic",
                publisher="Journal of EdTech",
                author="Dr. Patel",
                published_at="2026-04-10",
                canonical_identifier="https://doi.org/10.1000/study-a",
                content=(
                    "Offline quantized education models deployed in rural Indian secondary schools are feasible, "
                    "affordable, and scalable on refurbished tablet hardware under INR 500000."
                ),
            ),
            RawSourceRecord(
                url="https://github.com/edtech/offline-tutor",
                title="GitHub: edtech/offline-tutor",
                source_type="github",
                publisher="GitHub",
                published_at="2026-09-01",
                canonical_identifier="github:edtech/offline-tutor",
                license_name="MIT",
                content=(
                    "Offline quantized education models deployed in rural Indian secondary schools face "
                    "prohibitive maintenance bottlenecks, high battery failure risk, and are not reliable without solar backups."
                ),
            ),
        ]
        persist_raw_records(db, inv.investigation_id, records)
        stats = verify_investigation_evidence(db, inv)
        assert stats["total_claims"] >= 2
        assert stats["contradictions"] >= 1

        gate = evaluate_readiness_gate(db, inv)
        assert gate.readiness_score > 50
        assert gate.allowed_next_stage is True

        contras = db.query(Contradiction).filter_by(investigation_id=inv.investigation_id).all()
        assert len(contras) >= 1
        claims = db.query(Claim).filter_by(investigation_id=inv.investigation_id).all()
        assert any(c.verification_status == "CONTRADICTED" for c in claims)
