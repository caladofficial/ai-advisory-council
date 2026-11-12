import React from "react";
import { AlertTriangle, ExternalLink, X } from "lucide-react";
import type { EvidenceChunk } from "../../types";

interface EvidenceDrawerProps {
  evidence: EvidenceChunk | null;
  onClose: () => void;
}

export function EvidenceDrawer({ evidence, onClose }: EvidenceDrawerProps) {
  if (!evidence) return null;
  const qb = evidence.quality_breakdown;

  return (
    <div className="fixed inset-0 z-50 flex justify-end bg-black/60 backdrop-blur-xs" onClick={onClose}>
      <div
        className="w-full max-w-xl bg-slate-900 border-l border-slate-700 h-full overflow-y-auto p-6 shadow-2xl space-y-5"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-start justify-between gap-4 border-b border-slate-800 pb-4">
          <div>
            <div className="flex items-center gap-2">
              <span className="px-2 py-0.5 rounded bg-sky-500/20 text-sky-300 font-mono text-xs font-semibold">
                {evidence.evidence_id}
              </span>
              <span className="text-xs text-slate-400 uppercase">{evidence.source_type}</span>
              <span className="text-xs text-emerald-300 font-mono">
                Quality {(evidence.quality_score * 100).toFixed(0)}%
              </span>
            </div>
            <h3 className="text-base font-semibold text-white mt-2">{evidence.source_title}</h3>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 cursor-pointer"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {evidence.prompt_injection_flagged && (
          <div className="p-3 rounded-lg bg-rose-500/10 border border-rose-500/30 flex items-center gap-2 text-xs text-rose-300">
            <AlertTriangle className="w-4 h-4 shrink-0" />
            <span>Prompt-injection heuristics detected inside raw webpage; sanitized and isolated as untrusted data.</span>
          </div>
        )}

        <div>
          <h4 className="text-xs font-semibold uppercase tracking-wider text-slate-400 mb-2">
            Extracted Verbatim Passage
          </h4>
          <div className="p-4 rounded-lg bg-slate-950 border border-slate-800 text-sm text-slate-200 whitespace-pre-wrap leading-relaxed">
            {evidence.content}
          </div>
          <p className="text-[11px] font-mono text-slate-500 mt-1.5">
            Section: {evidence.section} {evidence.page ? `| Page ${evidence.page}` : ""} | SHA-256: {evidence.content_hash.slice(0, 16)}...
          </p>
        </div>

        {evidence.source_url && (
          <div>
            <h4 className="text-xs font-semibold uppercase tracking-wider text-slate-400 mb-1.5">
              Original Source Provenance
            </h4>
            <a
              href={evidence.source_url}
              target="_blank"
              rel="noreferrer"
              className="inline-flex items-center gap-1.5 text-sm text-sky-400 hover:text-sky-300 break-all"
            >
              <span>{evidence.source_url}</span>
              <ExternalLink className="w-3.5 h-3.5 shrink-0" />
            </a>
          </div>
        )}

        <div>
          <h4 className="text-xs font-semibold uppercase tracking-wider text-slate-400 mb-2">
            5-Dimension Quality Rubric
          </h4>
          <div className="space-y-2 text-xs">
            {[
              { label: "Authority & Provenance (25%)", val: qb?.authority ?? 0 },
              { label: "Methodology Quality (25%)", val: qb?.methodology ?? 0 },
              { label: "Direct Claim Relevance (20%)", val: qb?.relevance ?? 0 },
              { label: "Independent Corroboration (15%)", val: qb?.corroboration ?? 0 },
              { label: "Information Freshness (15%)", val: qb?.freshness ?? 0 },
            ].map((row) => (
              <div key={row.label}>
                <div className="flex justify-between text-slate-300 mb-0.5">
                  <span>{row.label}</span>
                  <span className="font-mono">{(row.val * 100).toFixed(0)}%</span>
                </div>
                <div className="h-1.5 rounded-full bg-slate-800 overflow-hidden">
                  <div className="h-full bg-amber-400" style={{ width: `${Math.min(100, row.val * 100)}%` }} />
                </div>
              </div>
            ))}
          </div>
        </div>

        {evidence.limitations.length > 0 && (
          <div>
            <h4 className="text-xs font-semibold uppercase tracking-wider text-amber-400 mb-1.5">
              Source Limitations
            </h4>
            <ul className="list-disc list-inside text-xs text-slate-300 space-y-1">
              {evidence.limitations.map((l, i) => (
                <li key={i}>{l}</li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </div>
  );
}
