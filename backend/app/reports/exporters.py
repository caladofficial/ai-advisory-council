"""Export Investigation Dossiers to Markdown, JSON, HTML, PDF, CSV registers, and ZIP bundles."""

from __future__ import annotations

import csv
import html
import io
import json
import zipfile
from typing import Any

from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer


def export_html(dossier: dict[str, Any], markdown_text: str) -> str:
    cov = dossier.get("cover", {})
    title = html.escape(f"{cov.get('investigation_id', '')} — {cov.get('topic', '')}")
    body_lines = []
    for line in markdown_text.splitlines():
        esc = html.escape(line)
        if line.startswith("# "):
            body_lines.append(f"<h1>{esc[2:]}</h1>")
        elif line.startswith("## "):
            body_lines.append(f"<h2>{esc[3:]}</h2>")
        elif line.startswith("### "):
            body_lines.append(f"<h3>{esc[4:]}</h3>")
        elif line.startswith("- "):
            body_lines.append(f"<li>{esc[2:]}</li>")
        elif line.strip():
            body_lines.append(f"<p>{esc}</p>")
    return (
        "<!doctype html><html><head><meta charset='utf-8'>"
        f"<title>{title}</title>"
        "<style>body{font-family:system-ui,-apple-system,sans-serif;max-width:960px;margin:40px auto;padding:0 24px;line-height:1.6;color:#0f172a}"
        "h1,h2,h3{color:#1e293b}h2{border-bottom:1px solid #cbd5e1;padding-bottom:6px;margin-top:28px}li{margin:4px 0}</style>"
        f"</head><body>{''.join(body_lines)}</body></html>"
    )


def export_pdf_bytes(dossier: dict[str, Any], markdown_text: str) -> bytes:
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=LETTER, title=dossier.get("cover", {}).get("investigation_id", "Report"))
    styles = getSampleStyleSheet()
    story = []
    for line in markdown_text.splitlines():
        stripped = line.strip()
        if not stripped:
            story.append(Spacer(1, 6))
            continue
        safe = html.escape(stripped)
        if stripped.startswith("# "):
            story.append(Paragraph(safe[2:], styles["Title"]))
        elif stripped.startswith("## "):
            story.append(Paragraph(safe[3:], styles["Heading2"]))
        elif stripped.startswith("### "):
            story.append(Paragraph(safe[4:], styles["Heading3"]))
        else:
            story.append(Paragraph(safe, styles["BodyText"]))
    doc.build(story)
    return buf.getvalue()


def export_csv_registers(dossier: dict[str, Any]) -> dict[str, str]:
    files: dict[str, str] = {}

    # Evidence CSV
    ev_buf = io.StringIO()
    ev_writer = csv.writer(ev_buf)
    ev_writer.writerow(["evidence_id", "source_id", "quality_score", "content"])
    for e in dossier.get("evidence_register", []):
        ev_writer.writerow([e["evidence_id"], e["source_id"], e["quality_score"], e["content"]])
    files["evidence_register.csv"] = ev_buf.getvalue()

    # Risk CSV
    rk_buf = io.StringIO()
    rk_writer = csv.writer(rk_buf)
    rk_writer.writerow(["risk_id", "title", "category", "likelihood", "impact", "mitigation", "owner_role"])
    for r in dossier.get("risk_register", []):
        rk_writer.writerow([r["risk_id"], r["title"], r["category"], r["likelihood"], r["impact"], r["mitigation"], r["owner_role"]])
    files["risk_register.csv"] = rk_buf.getvalue()

    # Debate CSV
    db_buf = io.StringIO()
    db_writer = csv.writer(db_buf)
    db_writer.writerow(["message_id", "round", "sender", "receiver", "type", "disposition", "position_change", "evidence_ids", "argument"])
    for m in dossier.get("debate_summary", {}).get("transcript", []):
        db_writer.writerow([
            m["message_id"],
            m["round"],
            m["sender"],
            m["receiver"],
            m["type"],
            m.get("disposition") or "",
            m.get("position_change") or "",
            "|".join(m.get("evidence_ids") or []),
            m["argument"],
        ])
    files["debate_transcript.csv"] = db_buf.getvalue()
    return files


def export_zip_bundle(dossier: dict[str, Any], markdown_text: str) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("dossier.md", markdown_text)
        zf.writestr("dossier.json", json.dumps(dossier, indent=2, default=str))
        zf.writestr("dossier.html", export_html(dossier, markdown_text))
        zf.writestr("dossier.pdf", export_pdf_bytes(dossier, markdown_text))
        for fname, content in export_csv_registers(dossier).items():
            zf.writestr(fname, content)
    return buf.getvalue()
