import React, { useCallback, useEffect, useState } from "react";
import {
  AlertTriangle,
  Download,
  FileText,
  Pause,
  Play,
  RotateCcw,
  Search,
  Square,
  Upload,
} from "lucide-react";
import { api } from "../services/api";
import { useSSEProgress } from "../hooks/useSSEProgress";
import type {
  AdvisorSession,
  AuditEventItem,
  ClaimRecord,
  ContradictionRecord,
  DebateTranscript,
  EvidenceChunk,
  IndependenceMetrics,
  Investigation,
  JudgeEvaluation,
  ModelUsageItem,
  PrerequisiteAssessment,
  SourceRecord,
} from "../types";
import { Card, EvidenceChip, StatusBadge, VerdictBadge, VerificationBadge } from "../components/ui/Badges";
import { AdvisorGrid } from "../components/council/AdvisorGrid";
import { DebateTimeline } from "../components/debate/DebateTimeline";
import { EvidenceDrawer } from "../components/evidence/EvidenceDrawer";
import { ScorecardPanel } from "../components/judge/ScorecardPanel";

type WorkspaceTab = "council" | "preflight" | "evidence" | "debate" | "judge" | "report" | "audit";

export function InvestigationWorkspacePage({ investigationId }: { investigationId: string }) {
  const [tab, setTab] = useState<WorkspaceTab>("council");
  const [inv, setInv] = useState<Investigation | null>(null);
  const [prereq, setPrereq] = useState<PrerequisiteAssessment | null>(null);
  const [sources, setSources] = useState<SourceRecord[]>([]);
  const [evidence, setEvidence] = useState<EvidenceChunk[]>([]);
  const [claims, setClaims] = useState<ClaimRecord[]>([]);
  const [contradictions, setContradictions] = useState<ContradictionRecord[]>([]);
  const [advisors, setAdvisors] = useState<AdvisorSession[]>([]);
  const [independence, setIndependence] = useState<IndependenceMetrics | null>(null);
  const [debate, setDebate] = useState<DebateTranscript | null>(null);
  const [judge, setJudge] = useState<JudgeEvaluation | null>(null);
  const [reportMd, setReportMd] = useState("");
  const [auditEvents, setAuditEvents] = useState<AuditEventItem[]>([]);
  const [usageRows, setUsageRows] = useState<ModelUsageItem[]>([]);

  const [selectedEvidence, setSelectedEvidence] = useState<EvidenceChunk | null>(null);
  const [claimFilter, setClaimFilter] = useState("");
  const [extraQuery, setExtraQuery] = useState("");
  const [clarifyBudget, setClarifyBudget] = useState("");
  const [clarifyUsers, setClarifyUsers] = useState("");

  const isRunning = Boolean(
    inv && !["CREATED", "COMPLETED", "FAILED", "CANCELLED", "PAUSED", "NEEDS_USER_INPUT", "INSUFFICIENT_EVIDENCE"].includes(inv.status)
  );
  const live = useSSEProgress(investigationId, isRunning);

  const loadAll = useCallback(async () => {
    const invData = await api.getInvestigation(investigationId);
    setInv(invData);

    const [srcRes, evdRes, clmRes, ctrRes, advRes, indRes, debRes, audRes] = await Promise.all([
      api.getSources(investigationId),
      api.getEvidence(investigationId),
      api.getClaims(investigationId, claimFilter),
      api.getContradictions(investigationId),
      api.getAdvisors(investigationId),
      api.getIndependence(investigationId),
      api.getDebate(investigationId),
      api.getInvestigationAudit(investigationId),
    ]);
    setSources(srcRes);
    setEvidence(evdRes);
    setClaims(clmRes);
    setContradictions(ctrRes);
    setAdvisors(advRes);
    setIndependence(indRes);
    setDebate(debRes);
    setAuditEvents(audRes.events);
    setUsageRows(audRes.model_usage);

    if (invData.readiness_score !== null) {
      api.getPrerequisites(investigationId).then(setPrereq).catch(() => {});
    }
    if (invData.verdict) {
      api.getJudge(investigationId).then(setJudge).catch(() => {});
    }
    if (invData.status === "COMPLETED") {
      api.getReport(investigationId).then((r) => setReportMd(r.markdown)).catch(() => {});
    }
  }, [investigationId, claimFilter]);

  useEffect(() => {
    loadAll();
  }, [loadAll]);

  useEffect(() => {
    if (live) {
      loadAll();
    }
  }, [live, loadAll]);

  const openEvidenceById = (evdId: string) => {
    const norm = evdId.replace(`${investigationId}-`, "");
    const match = evidence.find((e) => e.evidence_id === norm || e.evidence_id === evdId);
    if (match) setSelectedEvidence(match);
  };

  const handleUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    await api.uploadDocument(investigationId, file);
    await loadAll();
  };

  const handleExtraResearch = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!extraQuery.trim()) return;
    await api.additionalResearch(investigationId, extraQuery.trim(), ["web_search", "openalex", "github"]);
    setExtraQuery("");
    await loadAll();
  };

  if (!inv) {
    return <div className="text-sm text-slate-400">Loading investigation workspace...</div>;
  }

  const pct = live?.progress_percent ?? inv.progress_percent;
  const currentStatus = live?.status ?? inv.status;

  return (
    <div className="space-y-6">
      <Card className="p-5 space-y-4">
        <div className="flex flex-col lg:flex-row lg:items-start justify-between gap-4">
          <div className="space-y-1.5">
            <div className="flex items-center gap-2 flex-wrap">
              <span className="font-mono text-xs px-2 py-0.5 rounded bg-amber-500/15 text-amber-300 font-semibold">
                {inv.investigation_id}
              </span>
              <StatusBadge status={currentStatus} />
              <VerdictBadge verdict={inv.verdict} />
              <span className="text-xs text-slate-400">{inv.domain} · {inv.geography}</span>
            </div>
            <h1 className="font-editorial text-2xl text-white">{inv.topic}</h1>
            <p className="text-xs text-slate-400">
              {live?.message || `Current Stage: ${currentStatus} (${pct}%)`}
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-2 shrink-0">
            {inv.status === "CREATED" && (
              <button
                type="button"
                onClick={() => api.startInvestigation(investigationId).then(loadAll)}
                className="px-3.5 py-2 rounded-lg bg-amber-500 hover:bg-amber-400 text-slate-950 text-xs font-semibold inline-flex items-center gap-1.5 cursor-pointer"
              >
                <Play className="w-3.5 h-3.5" />
                <span>Start Council</span>
              </button>
            )}
            {isRunning && (
              <>
                <button
                  type="button"
                  onClick={() => api.pauseInvestigation(investigationId).then(loadAll)}
                  className="px-3 py-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-xs text-slate-200 inline-flex items-center gap-1.5 cursor-pointer"
                >
                  <Pause className="w-3.5 h-3.5" />
                  <span>Pause</span>
                </button>
                <button
                  type="button"
                  onClick={() => api.cancelInvestigation(investigationId).then(loadAll)}
                  className="px-3 py-2 rounded-lg bg-rose-500/15 border border-rose-500/30 text-xs text-rose-300 inline-flex items-center gap-1.5 cursor-pointer"
                >
                  <Square className="w-3.5 h-3.5" />
                  <span>Cancel</span>
                </button>
              </>
            )}
            {["PAUSED", "FAILED", "INSUFFICIENT_EVIDENCE"].includes(inv.status) && (
              <button
                type="button"
                onClick={() => api.resumeInvestigation(investigationId).then(loadAll)}
                className="px-3.5 py-2 rounded-lg bg-emerald-500 hover:bg-emerald-400 text-slate-950 text-xs font-semibold inline-flex items-center gap-1.5 cursor-pointer"
              >
                <RotateCcw className="w-3.5 h-3.5" />
                <span>Resume Checkpoint</span>
              </button>
            )}
          </div>
        </div>

        <div className="space-y-1">
          <div className="h-2 rounded-full bg-slate-800 overflow-hidden">
            <div
              className="h-full bg-gradient-to-r from-amber-500 to-emerald-400 transition-all duration-300"
              style={{ width: `${pct}%` }}
            />
          </div>
        </div>

        {inv.error_message && (
          <div className="p-3 rounded-lg bg-rose-500/10 border border-rose-500/30 text-xs text-rose-300">
            {inv.error_message}
          </div>
        )}

        {inv.status === "NEEDS_USER_INPUT" && (
          <div className="p-4 rounded-lg bg-amber-500/10 border border-amber-500/30 space-y-3">
            <div className="flex items-center gap-2 text-amber-300 text-sm font-semibold">
              <AlertTriangle className="w-4 h-4" />
              <span>Readiness Gate Paused — Clarifications Requested</span>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              <input
                value={clarifyBudget}
                onChange={(e) => setClarifyBudget(e.target.value)}
                placeholder="Target budget ceiling (optional)"
                className="rounded-lg bg-slate-950 border border-slate-800 p-2 text-xs text-white"
              />
              <input
                value={clarifyUsers}
                onChange={(e) => setClarifyUsers(e.target.value)}
                placeholder="Target users / institutions"
                className="rounded-lg bg-slate-950 border border-slate-800 p-2 text-xs text-white"
              />
            </div>
            <button
              type="button"
              onClick={() =>
                api
                  .submitClarification(investigationId, {
                    ...(clarifyBudget ? { budget: clarifyBudget } : {}),
                    ...(clarifyUsers ? { target_users: clarifyUsers } : {}),
                  })
                  .then(loadAll)
              }
              className="px-4 py-1.5 rounded-lg bg-amber-500 text-slate-950 text-xs font-semibold cursor-pointer"
            >
              Submit &amp; Proceed to Council
            </button>
          </div>
        )}
      </Card>

      <div className="flex flex-wrap gap-1.5 border-b border-slate-800 pb-2">
        {[
          { id: "council", label: `Live Council (${advisors.length})` },
          { id: "preflight", label: `Preflight Gate${inv.readiness_score !== null ? ` (${inv.readiness_score})` : ""}` },
          { id: "evidence", label: `Evidence & Claims (${evidence.length})` },
          { id: "debate", label: `Debate Room (${debate?.messages.length || 0})` },
          { id: "judge", label: "Chief Judge" },
          { id: "report", label: "Dossier & Exports" },
          { id: "audit", label: `Audit & Usage (${usageRows.length})` },
        ].map((item) => (
          <button
            key={item.id}
            type="button"
            onClick={() => setTab(item.id as WorkspaceTab)}
            className={`px-3.5 py-2 rounded-lg text-xs font-medium cursor-pointer transition-colors ${
              tab === item.id
                ? "bg-amber-500 text-slate-950 font-semibold"
                : "bg-slate-900 text-slate-300 hover:bg-slate-800"
            }`}
          >
            {item.label}
          </button>
        ))}
      </div>

      {tab === "council" && (
        <AdvisorGrid
          advisors={advisors}
          independence={independence}
          liveStatuses={live?.advisor_statuses}
          onSelectEvidence={openEvidenceById}
        />
      )}

      {tab === "preflight" && (
        <div className="space-y-4">
          {!prereq ? (
            <Card className="p-6 text-sm text-slate-400">
              Preflight assessment will populate once research verification finishes.
            </Card>
          ) : (
            <>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <Card className="p-5">
                  <div className="text-xs text-slate-400">Readiness Score</div>
                  <div className="text-3xl font-bold font-mono text-amber-400 mt-1">
                    {prereq.readiness_score}/100
                  </div>
                  <div className="mt-2"><StatusBadge status={prereq.readiness_status} /></div>
                </Card>
                <Card className="p-5">
                  <div className="text-xs text-slate-400">Estimated Token &amp; Call Budget</div>
                  <div className="text-xl font-bold font-mono text-white mt-1">
                    {prereq.resource_estimate.estimated_advisor_calls} calls · ~{prereq.resource_estimate.estimated_total_tokens.toLocaleString()} tok
                  </div>
                  <div className="text-xs text-emerald-300 mt-1">
                    Cost: $0.00 ({prereq.resource_estimate.cost_policy_mode})
                  </div>
                </Card>
                <Card className="p-5">
                  <div className="text-xs text-slate-400">Active Free / Local Providers</div>
                  <div className="text-sm font-mono text-white mt-1">
                    {prereq.resource_estimate.providers_healthy.join(", ") || "ollama"}
                  </div>
                  <div className="text-xs text-slate-400 mt-1">
                    Est. duration: ~{prereq.resource_estimate.estimated_duration_seconds}s
                  </div>
                </Card>
              </div>

              <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                <Card className="p-5 space-y-3">
                  <h3 className="text-sm font-semibold text-white">10-Category Prerequisite Checklist</h3>
                  <div className="space-y-2">
                    {prereq.mandatory_items.map((it) => (
                      <div key={it.category} className="p-2.5 rounded bg-slate-950 border border-slate-800 flex items-start justify-between gap-3 text-xs">
                        <div>
                          <div className="font-medium text-white">{it.name}</div>
                          <div className="text-slate-400 mt-0.5">{it.detail}</div>
                        </div>
                        <StatusBadge status={it.status} />
                      </div>
                    ))}
                  </div>
                </Card>

                <Card className="p-5 space-y-4">
                  <h3 className="text-sm font-semibold text-white">100-Point Rubric &amp; Documented Gaps</h3>
                  <div className="space-y-2 text-xs">
                    {[
                      ["Topic Clarity (20)", prereq.rubric.topic_clarity, 20],
                      ["Prerequisites (20)", prereq.rubric.prerequisite_completeness, 20],
                      ["Source Coverage (20)", prereq.rubric.source_coverage, 20],
                      ["Source Quality (20)", prereq.rubric.source_quality, 20],
                      ["Freshness (10)", prereq.rubric.information_freshness, 10],
                      ["Contradictions Tracked (10)", prereq.rubric.contradictions_identified, 10],
                    ].map(([label, val, max]) => (
                      <div key={String(label)}>
                        <div className="flex justify-between text-slate-300">
                          <span>{label}</span>
                          <span className="font-mono">{val}/{max}</span>
                        </div>
                        <div className="h-1.5 rounded bg-slate-800 mt-0.5 overflow-hidden">
                          <div className="h-full bg-amber-400" style={{ width: `${(Number(val) / Number(max)) * 100}%` }} />
                        </div>
                      </div>
                    ))}
                  </div>
                  {prereq.research_gaps.length > 0 && (
                    <div>
                      <h4 className="text-xs font-semibold text-amber-300 mb-1">Flagged Research Gaps</h4>
                      <ul className="list-disc list-inside text-xs text-slate-300 space-y-1">
                        {prereq.research_gaps.map((g, i) => <li key={i}>{g}</li>)}
                      </ul>
                    </div>
                  )}
                </Card>
              </div>
            </>
          )}
        </div>
      )}

      {tab === "evidence" && (
        <div className="space-y-5">
          <Card className="p-4 flex flex-col md:flex-row items-stretch md:items-center justify-between gap-3">
            <form onSubmit={handleExtraResearch} className="flex-1 flex gap-2">
              <div className="relative flex-1">
                <Search className="w-4 h-4 text-slate-500 absolute left-3 top-2.5" />
                <input
                  value={extraQuery}
                  onChange={(e) => setExtraQuery(e.target.value)}
                  placeholder="Request additional targeted research query..."
                  className="w-full pl-9 pr-3 py-2 rounded-lg bg-slate-950 border border-slate-800 text-xs text-white"
                />
              </div>
              <button
                type="submit"
                className="px-3.5 py-2 rounded-lg bg-sky-500/20 border border-sky-500/40 text-sky-300 text-xs font-semibold cursor-pointer"
              >
                Run Extra Research
              </button>
            </form>

            <label className="px-3.5 py-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-xs font-medium text-slate-200 inline-flex items-center gap-1.5 cursor-pointer shrink-0">
              <Upload className="w-3.5 h-3.5" />
              <span>Upload PDF/TXT/CSV</span>
              <input type="file" className="hidden" accept=".pdf,.txt,.md,.csv,.json" onChange={handleUpload} />
            </label>
          </Card>

          {contradictions.length > 0 && (
            <Card className="p-4 border-rose-500/30 bg-rose-950/15 space-y-2">
              <h3 className="text-xs font-semibold uppercase tracking-wider text-rose-300">
                Detected Evidence Contradictions ({contradictions.length})
              </h3>
              {contradictions.map((ct) => (
                <div key={ct.contradiction_id} className="text-xs text-slate-200 flex items-center justify-between gap-2 bg-slate-950/70 p-2.5 rounded border border-slate-800">
                  <span>{ct.summary}</span>
                  <div className="flex gap-1 shrink-0">
                    {ct.evidence_a_id && <EvidenceChip id={ct.evidence_a_id} onClick={openEvidenceById} />}
                    {ct.evidence_b_id && <EvidenceChip id={ct.evidence_b_id} onClick={openEvidenceById} />}
                  </div>
                </div>
              ))}
            </Card>
          )}

          <Card className="p-5 space-y-3">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <h3 className="text-sm font-semibold text-white">Atomic Claims &amp; Verification Status</h3>
              <div className="flex flex-wrap gap-1">
                {["", "VERIFIED", "CORROBORATED", "PARTIALLY_SUPPORTED", "CONTRADICTED", "UNVERIFIED", "OUTDATED"].map((st) => (
                  <button
                    key={st || "ALL"}
                    type="button"
                    onClick={() => setClaimFilter(st)}
                    className={`px-2 py-1 rounded text-[11px] font-medium cursor-pointer ${
                      claimFilter === st ? "bg-amber-500 text-slate-950" : "bg-slate-800 text-slate-300"
                    }`}
                  >
                    {st ? st.replace(/_/g, " ") : "ALL"}
                  </button>
                ))}
              </div>
            </div>
            <div className="space-y-2">
              {claims.map((c) => (
                <div key={c.claim_id} className="p-3 rounded-lg bg-slate-950 border border-slate-800 flex flex-col md:flex-row md:items-center justify-between gap-2">
                  <div className="space-y-1">
                    <div className="flex items-center gap-2">
                      <span className="font-mono text-xs text-slate-400">{c.claim_id}</span>
                      <VerificationBadge status={c.verification_status} />
                      <span className="text-[11px] text-slate-500 uppercase">{c.category}</span>
                    </div>
                    <p className="text-xs text-slate-200">{c.claim_text}</p>
                  </div>
                  <div className="flex flex-wrap gap-1 shrink-0">
                    {c.evidence_ids.map((eid) => (
                      <EvidenceChip key={eid} id={eid} onClick={openEvidenceById} />
                    ))}
                  </div>
                </div>
              ))}
            </div>
          </Card>

          <Card className="p-5 space-y-3">
            <h3 className="text-sm font-semibold text-white">Collected Sources ({sources.length})</h3>
            <div className="space-y-2">
              {sources.map((s) => (
                <div key={s.source_id} className="p-3 rounded-lg bg-slate-950 border border-slate-800 flex items-center justify-between gap-3 text-xs">
                  <div className="min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="font-mono text-slate-400">{s.source_id}</span>
                      <span className="px-1.5 py-0.5 rounded bg-slate-800 text-slate-300 uppercase text-[10px]">{s.source_type}</span>
                      {s.is_duplicate && (
                        <span className="px-1.5 py-0.5 rounded bg-amber-500/15 text-amber-300 text-[10px]">
                          Syndicated/Duplicate of {s.syndicated_from_id}
                        </span>
                      )}
                    </div>
                    <a href={s.url} target="_blank" rel="noreferrer" className="text-sky-400 hover:underline font-medium block truncate mt-1">
                      {s.title}
                    </a>
                  </div>
                  <span className="font-mono text-slate-400 shrink-0">Rel {(s.reliability_score * 100).toFixed(0)}%</span>
                </div>
              ))}
            </div>
          </Card>
        </div>
      )}

      {tab === "debate" && debate && (
        <DebateTimeline debate={debate} onSelectEvidence={openEvidenceById} />
      )}

      {tab === "judge" && (
        judge ? (
          <ScorecardPanel judge={judge} />
        ) : (
          <Card className="p-8 text-center text-sm text-slate-400">
            Chief Judge adjudication runs automatically after Round-4 advisor final submissions.
          </Card>
        )
      )}

      {tab === "report" && (
        <Card className="p-5 space-y-4">
          <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-800 pb-4">
            <div className="flex items-center gap-2">
              <FileText className="w-4 h-4 text-amber-400" />
              <h3 className="text-sm font-semibold text-white">Complete Investigation Dossier &amp; Exports</h3>
            </div>
            <div className="flex flex-wrap gap-2">
              {[
                ["pdf", "PDF Report"],
                ["md", "Markdown"],
                ["html", "HTML"],
                ["json", "JSON"],
                ["csv", "Evidence CSV"],
                ["zip", "Full ZIP Archive"],
              ].map(([fmt, label]) => (
                <a
                  key={fmt}
                  href={api.exportUrl(investigationId, fmt)}
                  target="_blank"
                  rel="noreferrer"
                  className="px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-xs font-medium text-slate-200 inline-flex items-center gap-1.5"
                >
                  <Download className="w-3.5 h-3.5" />
                  <span>{label}</span>
                </a>
              ))}
            </div>
          </div>

          <pre className="p-4 rounded-lg bg-slate-950 border border-slate-800 text-xs text-slate-200 whitespace-pre-wrap overflow-x-auto leading-relaxed max-h-[650px]">
            {reportMd || "Complete dossier will be rendered once Chief Judge evaluation finishes."}
          </pre>
        </Card>
      )}

      {tab === "audit" && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
          <Card className="p-5 space-y-3">
            <h3 className="text-sm font-semibold text-white">Append-Only Audit Trail ({auditEvents.length})</h3>
            <div className="space-y-2 max-h-[540px] overflow-y-auto">
              {auditEvents.map((ev) => (
                <div key={ev.event_id} className="p-2.5 rounded bg-slate-950 border border-slate-800 text-xs space-y-1">
                  <div className="flex justify-between font-mono text-[11px] text-slate-400">
                    <span>{ev.actor} · {ev.event_type}</span>
                    <span>{new Date(ev.created_at).toLocaleTimeString()}</span>
                  </div>
                  <p className="text-slate-200">{ev.summary}</p>
                </div>
              ))}
            </div>
          </Card>

          <Card className="p-5 space-y-3">
            <h3 className="text-sm font-semibold text-white">Model Usage &amp; Zero-Paid Ledger ({usageRows.length})</h3>
            <div className="space-y-2 max-h-[540px] overflow-y-auto">
              {usageRows.map((u) => (
                <div key={u.usage_id} className="p-2.5 rounded bg-slate-950 border border-slate-800 text-xs flex items-center justify-between gap-2">
                  <div>
                    <div className="font-mono text-white">{u.agent_id} → {u.provider}:{u.model_id}</div>
                    <div className="text-[11px] text-slate-400">
                      {u.total_tokens} tok · {u.latency_ms}ms · {u.status}
                    </div>
                  </div>
                  <span className="font-mono text-emerald-300 text-xs">$0.00</span>
                </div>
              ))}
            </div>
          </Card>
        </div>
      )}

      <EvidenceDrawer evidence={selectedEvidence} onClose={() => setSelectedEvidence(null)} />
    </div>
  );
}
