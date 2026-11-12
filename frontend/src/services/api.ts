import type {
  AdvisorSession,
  AuditEventItem,
  BenchmarkRun,
  ClaimRecord,
  ContradictionRecord,
  DebateTranscript,
  EvidenceChunk,
  IndependenceMetrics,
  Investigation,
  JudgeEvaluation,
  ModelEntry,
  ModelUsageItem,
  PrerequisiteAssessment,
  ProviderInfo,
  SourceRecord,
} from "../types";

const BASE = (import.meta.env.VITE_API_BASE_URL || "").replace(/\/$/, "");

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: {
      ...(init?.body instanceof FormData ? {} : { "Content-Type": "application/json" }),
      ...(init?.headers || {}),
    },
    ...init,
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || `HTTP ${res.status}`);
  }
  return res.json() as Promise<T>;
}

export const api = {
  listInvestigations: () => apiFetch<Investigation[]>("/api/investigations"),
  getInvestigation: (id: string) => apiFetch<Investigation>(`/api/investigations/${id}`),
  createInvestigation: (body: {
    topic: string;
    objective: string;
    mode: string;
    execution_profile: string;
    geography: string;
    time_horizon: string;
    budget: string;
    target_users: string;
    constraints: string[];
    enabled_connectors: string[];
    auto_start: boolean;
  }) => apiFetch<Investigation>("/api/investigations", { method: "POST", body: JSON.stringify(body) }),
  deleteInvestigation: (id: string) => apiFetch<{ deleted: boolean }>(`/api/investigations/${id}`, { method: "DELETE" }),

  startInvestigation: (id: string, forceWarnings = false) =>
    apiFetch<{ status: string }>(`/api/investigations/${id}/start?force_proceed_warnings=${forceWarnings}`, { method: "POST" }),
  pauseInvestigation: (id: string) =>
    apiFetch<{ status: string }>(`/api/investigations/${id}/pause`, { method: "POST" }),
  resumeInvestigation: (id: string) =>
    apiFetch<{ status: string }>(`/api/investigations/${id}/resume`, { method: "POST" }),
  cancelInvestigation: (id: string) =>
    apiFetch<{ status: string }>(`/api/investigations/${id}/cancel`, { method: "POST" }),
  submitClarification: (id: string, answers: Record<string, string>) =>
    apiFetch<{ status: string }>(`/api/investigations/${id}/clarify`, {
      method: "POST",
      body: JSON.stringify({ answers, additional_constraints: [], proceed_with_warnings: true }),
    }),
  additionalResearch: (id: string, query: string, connectors: string[]) =>
    apiFetch(`/api/investigations/${id}/additional-research`, {
      method: "POST",
      body: JSON.stringify({ query, connectors }),
    }),

  getPrerequisites: (id: string) => apiFetch<PrerequisiteAssessment>(`/api/investigations/${id}/prerequisites`),
  getSources: (id: string) => apiFetch<SourceRecord[]>(`/api/investigations/${id}/sources`),
  getEvidence: (id: string, q = "") =>
    apiFetch<EvidenceChunk[]>(`/api/investigations/${id}/evidence${q ? `?q=${encodeURIComponent(q)}` : ""}`),
  getClaims: (id: string, status = "") =>
    apiFetch<ClaimRecord[]>(`/api/investigations/${id}/claims${status ? `?status=${status}` : ""}`),
  getContradictions: (id: string) => apiFetch<ContradictionRecord[]>(`/api/investigations/${id}/contradictions`),
  uploadDocument: (id: string, file: File) => {
    const fd = new FormData();
    fd.append("file", file);
    return apiFetch<{ source_id: string; chunks_created: number }>(`/api/investigations/${id}/upload`, {
      method: "POST",
      body: fd,
    });
  },

  getAdvisors: (id: string) => apiFetch<AdvisorSession[]>(`/api/investigations/${id}/advisors`),
  getIndependence: (id: string) => apiFetch<IndependenceMetrics>(`/api/investigations/${id}/independence`),
  getDebate: (id: string) => apiFetch<DebateTranscript>(`/api/investigations/${id}/debate`),
  getJudge: (id: string) => apiFetch<JudgeEvaluation>(`/api/investigations/${id}/judge`),
  getReport: (id: string) =>
    apiFetch<{ version: number; dossier: Record<string, unknown>; markdown: string; created_at: string }>(
      `/api/investigations/${id}/report`
    ),
  exportUrl: (id: string, fmt: string) => `${BASE}/api/investigations/${id}/export/${fmt}`,
  sseProgressUrl: (id: string) => `${BASE}/api/investigations/${id}/progress/stream`,

  getInvestigationAudit: (id: string) =>
    apiFetch<{ events: AuditEventItem[]; model_usage: ModelUsageItem[] }>(`/api/audit/${id}`),
  getGlobalAudit: () => apiFetch<AuditEventItem[]>("/api/audit"),
  getGlobalUsage: () => apiFetch<ModelUsageItem[]>("/api/audit/usage"),

  getCostPolicy: () =>
    apiFetch<{ mode: string; allow_paid_providers: boolean; allow_credit_card_fallback: boolean; allow_over_quota_requests: boolean }>(
      "/api/cost-policy"
    ),
  getProviders: () => apiFetch<ProviderInfo[]>("/api/providers"),
  configureProviderKey: (provider_id: string, api_key: string) =>
    apiFetch<{ configured: boolean }>("/api/providers/configure-key", {
      method: "POST",
      body: JSON.stringify({ provider_id, api_key }),
    }),
  getModels: (provider = "") =>
    apiFetch<ModelEntry[]>(`/api/models${provider ? `?provider=${encodeURIComponent(provider)}` : ""}`),
  syncModels: (includeHf = false) =>
    apiFetch<{ synced_new_models: number }>(`/api/models/sync?include_hf=${includeHf}`, { method: "POST" }),
  healthCheckModels: (provider?: string, model_id?: string) =>
    apiFetch("/api/models/health-check", {
      method: "POST",
      body: JSON.stringify({ provider: provider || null, model_id: model_id || null, test_json: true }),
    }),
  getAdvisorAssignments: () => apiFetch<Record<string, { provider: string; model_id: string }>>("/api/models/assignments"),
  assignAdvisorModel: (advisor_id: string, provider: string, model_id: string) =>
    apiFetch("/api/models/assign-advisor", {
      method: "POST",
      body: JSON.stringify({ advisor_id, provider, model_id }),
    }),
  getAdvisorProfiles: () =>
    apiFetch<Array<{ advisor_id: string; name: string; role: string }>>("/api/advisors/profiles"),

  runBenchmarks: (includeLiveModels = false) =>
    apiFetch<BenchmarkRun>(`/api/evaluation/run?include_live_models=${includeLiveModels}`, { method: "POST" }),
};
