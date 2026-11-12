"""Investigation Dossier viewer and multi-format export routes (MD, JSON, HTML, PDF, CSV, ZIP)."""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.models import Investigation, ReportVersion
from app.database.session import get_db
from app.reports.exporters import export_csv_registers, export_html, export_pdf_bytes, export_zip_bundle
from app.reports.generator import build_investigation_dossier

router = APIRouter(prefix="/api/investigations/{investigation_id}", tags=["reports"])


def _latest_report(db: Session, investigation_id: str) -> ReportVersion:
    inv = db.get(Investigation, investigation_id)
    if inv is None:
        raise HTTPException(status_code=404, detail="Investigation not found")
    rv = db.scalars(
        select(ReportVersion)
        .where(ReportVersion.investigation_id == investigation_id)
        .order_by(ReportVersion.version_number.desc())
    ).first()
    if rv is None:
        rv = build_investigation_dossier(db, inv)
        db.commit()
    return rv


@router.get("/report")
def get_report(investigation_id: str, db: Session = Depends(get_db)):
    rv = _latest_report(db, investigation_id)
    versions = [
        {"version": r.version_number, "created_at": r.created_at.isoformat()}
        for r in db.scalars(
            select(ReportVersion)
            .where(ReportVersion.investigation_id == investigation_id)
            .order_by(ReportVersion.version_number.desc())
        ).all()
    ]
    return {
        "investigation_id": investigation_id,
        "version": rv.version_number,
        "versions": versions,
        "dossier": rv.dossier_json,
        "markdown": rv.markdown_content,
        "created_at": rv.created_at.isoformat(),
    }


@router.get("/export/{fmt}")
def export_report(investigation_id: str, fmt: str, db: Session = Depends(get_db)):
    rv = _latest_report(db, investigation_id)
    fmt_lower = fmt.lower().strip()
    dossier = rv.dossier_json
    md = rv.markdown_content

    if fmt_lower in {"md", "markdown"}:
        return Response(
            content=md,
            media_type="text/markdown; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="{investigation_id}_v{rv.version_number}.md"'},
        )
    if fmt_lower == "json":
        return Response(
            content=json.dumps(dossier, indent=2, default=str),
            media_type="application/json",
            headers={"Content-Disposition": f'attachment; filename="{investigation_id}_v{rv.version_number}.json"'},
        )
    if fmt_lower == "html":
        return Response(
            content=export_html(dossier, md),
            media_type="text/html; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="{investigation_id}_v{rv.version_number}.html"'},
        )
    if fmt_lower == "pdf":
        pdf_bytes = export_pdf_bytes(dossier, md)
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="{investigation_id}_v{rv.version_number}.pdf"'},
        )
    if fmt_lower == "csv":
        csvs = export_csv_registers(dossier)
        return Response(
            content=csvs["evidence_register.csv"],
            media_type="text/csv; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="{investigation_id}_evidence.csv"'},
        )
    if fmt_lower == "zip":
        z_bytes = export_zip_bundle(dossier, md)
        return Response(
            content=z_bytes,
            media_type="application/zip",
            headers={"Content-Disposition": f'attachment; filename="{investigation_id}_full_archive.zip"'},
        )
    raise HTTPException(status_code=400, detail=f"Unsupported export format: {fmt}")
