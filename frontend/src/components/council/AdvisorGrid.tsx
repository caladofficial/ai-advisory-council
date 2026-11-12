import React, { useState } from "react";
import { AlertCircle, Brain, ChevronDown, ChevronUp, Lock } from "lucide-react";
import type { AdvisorSession, IndependenceMetrics } from "../../types";
import { Card, EvidenceChip, StanceBadge, StatusBadge } from "../ui/Badges";

interface AdvisorGridProps {
  advisors: AdvisorSession[];
  independence: IndependenceMetrics | null;
  liveStatuses?: Record<string, string>;
  onSelectEvidence: (evdId: string) => void;
}

export function AdvisorGrid({
  advisors,
  independence,
  liveStatuses = {},
  onSelectEvidence,
}: AdvisorGridProps) {
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [showPrivateId, setShowPrivateId] = useState<string | null>(null);

  return (
    <div className="space-y-5">
      {independence && independence.advisor_count > 0 && (
        <Card className="p-4 flex flex-col md:flex-row md:items-center justify-between gap-4 border-indigo-500/30 bg-indigo-950/20">
          <div className="flex items-start gap-3">
            <Brain className="w-5 h-5 text-indigo-400 shrink-0 mt-0.5" />
            <div>
              <div className="flex items-center gap-2">
                <h3 className="text-sm font-semibold text-white">
                  Council Independence &amp; Anti-Correlation Telemetry
                </h3>
                <span className="px-2 py-0.5 rounded bg-indigo-500/20 text-indigo-300 font-mono text-xs font-semibold">
                  Divergence {independence.divergence_score}/100
                </span>
              </div>
              <p className="text-xs text-slate-300 mt-1">
                Model families active: <span className="font-mono text-white">{independence.distinct_model_families}</span> ·
                Mean lexical overlap: <span className="font-mono text-white">{(independence.lexical_similarity_mean * 100).toFixed(1)}%</span> ·
                Initial stances:{" "}
                {Object.entries(independence.stance_distribution)
                  .map(([k, v]) => `${k}: ${v}`)
                  .join(" | ")}
              </p>
              {independence.correlated_risk_warning && (
                <p className="text-xs text-amber-300 mt-1 flex items-center gap-1.5">
                  <AlertCircle className="w-3.5 h-3.5 shrink-0" />
                  <span>{independence.correlated_risk_warning}</span>
                </p>
              )}
            </div>
          </div>
        </Card>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {advisors.map((adv) => {
          const liveSt = liveStatuses[adv.advisor_id] || adv.status;
          const activeRep = adv.final_report || adv.initial_report;
          const isExpanded = expandedId === adv.advisor_id;
          const showPrivate = showPrivateId === adv.advisor_id;

          return (
            <Card key={adv.advisor_id} className="p-4 space-y-3">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <div className="flex items-center gap-2 flex-wrap">
                    <h4 className="font-semibold text-sm text-white">{adv.advisor_name}</h4>
                    <StatusBadge status={liveSt} />
                    {activeRep && <StanceBadge stance={activeRep.stance} />}
                  </div>
                  <p className="text-xs text-slate-400 mt-0.5">{adv.advisor_role}</p>
                </div>
                <div className="text-right shrink-0">
                  <div className="text-[11px] font-mono text-slate-300 bg-slate-950 border border-slate-800 px-2 py-0.5 rounded">
                    {adv.assigned_provider}:{adv.assigned_model}
                  </div>
                  {adv.position_changed !== "UNCHANGED" && (
                    <div className="text-[10px] font-mono text-amber-300 mt-1">
                      {adv.position_changed}
                    </div>
                  )}
                </div>
              </div>

              {activeRep ? (
                <>
                  <p className="text-xs text-slate-200 leading-relaxed line-clamp-3">
                    {activeRep.executive_findings}
                  </p>
                  <div className="flex items-center flex-wrap gap-1.5">
                    <span className="text-[11px] text-slate-400 mr-1">
                      Confidence: <strong className="text-slate-200">{(activeRep.confidence * 100).toFixed(0)}%</strong>
                    </span>
                    {activeRep.evidence_ids_cited.slice(0, 5).map((eid) => (
                      <EvidenceChip key={eid} id={eid} onClick={onSelectEvidence} />
                    ))}
                    {adv.unverified_citations.length > 0 && (
                      <span className="text-[11px] px-1.5 py-0.5 rounded bg-rose-500/15 text-rose-300 border border-rose-500/30">
                        {adv.unverified_citations.length} unverified cite(s)
                      </span>
                    )}
                  </div>
                </>
              ) : (
                <p className="text-xs text-slate-500 italic">Awaiting blind independent Stage-5 analysis...</p>
              )}

              <div className="flex items-center justify-between pt-2 border-t border-slate-800/80 text-xs">
                <button
                  type="button"
                  onClick={() => setExpandedId(isExpanded ? null : adv.advisor_id)}
                  className="inline-flex items-center gap-1 text-amber-300 hover:text-amber-200 cursor-pointer"
                >
                  {isExpanded ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
                  <span>{isExpanded ? "Hide Initial vs Final" : "Inspect Full Report"}</span>
                </button>
                {adv.private_notes && (
                  <button
                    type="button"
                    onClick={() => setShowPrivateId(showPrivate ? null : adv.advisor_id)}
                    className="inline-flex items-center gap-1 text-slate-400 hover:text-slate-200 cursor-pointer"
                  >
                    <Lock className="w-3 h-3" />
                    <span>{showPrivate ? "Hide Private Notes" : "Isolated Scratchpad"}</span>
                  </button>
                )}
              </div>

              {showPrivate && adv.private_notes && (
                <div className="p-3 rounded-lg bg-slate-950 border border-amber-500/20 text-xs text-slate-300 space-y-1">
                  <div className="text-[10px] font-mono uppercase text-amber-400">
                    Private Memory Namespace (Hidden from Peers &amp; Judge)
                  </div>
                  <p className="whitespace-pre-wrap">{adv.private_notes}</p>
                </div>
              )}

              {isExpanded && activeRep && (
                <div className="p-3 rounded-lg bg-slate-950 border border-slate-800 text-xs space-y-3">
                  {adv.initial_report && adv.final_report && (
                    <div className="flex items-center gap-2 text-[11px] font-mono text-slate-400">
                      <span>Blind Initial: {adv.initial_report.stance} ({(adv.initial_report.confidence * 100).toFixed(0)}%)</span>
                      <span>→</span>
                      <span className="text-white">Final: {adv.final_report.stance} ({(adv.final_report.confidence * 100).toFixed(0)}%)</span>
                    </div>
                  )}
                  <div>
                    <div className="font-semibold text-slate-300 mb-1">Self-Identified Weakness</div>
                    <p className="text-slate-400">{activeRep.self_identified_weakness}</p>
                  </div>
                  {activeRep.risks_and_weaknesses.length > 0 && (
                    <div>
                      <div className="font-semibold text-rose-300 mb-1">Identified Risks</div>
                      <ul className="list-disc list-inside text-slate-300 space-y-0.5">
                        {activeRep.risks_and_weaknesses.map((r, i) => (
                          <li key={i}>{r}</li>
                        ))}
                      </ul>
                    </div>
                  )}
                  {activeRep.recommendations.length > 0 && (
                    <div>
                      <div className="font-semibold text-emerald-300 mb-1">Recommendations</div>
                      <ul className="list-disc list-inside text-slate-300 space-y-0.5">
                        {activeRep.recommendations.map((r, i) => (
                          <li key={i}>{r}</li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>
              )}
            </Card>
          );
        })}
      </div>
    </div>
  );
}
