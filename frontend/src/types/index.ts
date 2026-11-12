export type InvestigationMode =
  | "general_decision"
  | "business_feasibility"
  | "technical_feasibility"
  | "scientific_research"
  | "product_evaluation"
  | "policy_analysis";

export type ExecutionProfile = "full_10_plus_1" | "prototype_3_plus_1";

export type VerdictType =
  | "GO"
  | "CONDITIONAL_GO"
  | "PILOT_FIRST"
  | "PIVOT"
  | "NO_GO"
  | "INSUFFICIENT_EVIDENCE";

export interface Investigation {
  investigation_id: string;
  topic: string;
  objective: string;
  mode: InvestigationMode;
  execution_profile: ExecutionProfile;
  domain: string;
  geography: string;
  time_horizon: string;
  budget: string;
  target_users: string;
  constraints: string[];
  enabled_connectors: string[];
  status: string;
  current_stage: string;
  progress_percent: number;
  readiness_score: number | null;
  readiness_status: string | null;
  verdict: VerdictType | null;
  feasibility_score: number | null;
  error_message: string | null;
  brief_json: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface RequirementItem {
  name: string;
  category: string;
  requirement_type: string;
  status: string;
  blocking: boolean;
  detail: string;
}

export interface ReadinessRubric {
  topic_clarity: number;
  prerequisite_completeness: number;
  source_coverage: number;
  source_quality: number;
  information_freshness: number;
  contradictions_identified: number;
  total_score: number;
}

export interface ResourceEstimate {
  estimated_advisor_calls: number;
  estimated_total_tokens: number;
  estimated_cost_usd: number;
  cost_policy_mode: string;
  estimated_duration_seconds: number;
  available_models_count: number;
  providers_healthy: string[];
  fallback_ready: boolean;
  warnings: string[];
}

export interface PrerequisiteAssessment {
  investigation_id: string;
  readiness_status: string;
  readiness_score: number;
  rubric: ReadinessRubric;
  mandatory_items: RequirementItem[];
  research_gaps: string[];
  assumptions: string[];
  clarifying_questions: string[];
  hard_gates_triggered: string[];
  resource_estimate: ResourceEstimate;
  allowed_next_stage: boolean;
}

export interface SourceRecord {
  source_id: string;
  investigation_id: string;
  url: string;
  canonical_url: string;
  title: string;
  publisher: string;
  author: string;
  published_at: string | null;
  retrieved_at: string;
  source_type: string;
  domain: string;
  canonical_identifier: string | null;
  license_name: string | null;
  content_hash: string;
  is_duplicate: boolean;
  syndicated_from_id: string | null;
  reliability_score: number;
}

export interface EvidenceChunk {
  evidence_id: string;
  investigation_id: string;
  source_id: string;
  source_title: string;
  source_url: string;
  source_type: string;
  content: string;
  section: string;
  page: number | null;
  paragraph_index: number;
  content_hash: string;
  quality_score: number;
  quality_breakdown: {
    authority: number;
    methodology: number;
    relevance: number;
    corroboration: number;
    freshness: number;
    weighted_total: number;
    notes: string;
  };
  prompt_injection_flagged: boolean;
  limitations: string[];
}

export interface ClaimRecord {
  claim_id: string;
  investigation_id: string;
  claim_text: string;
  category: string;
  entity: string;
  value_unit: string;
  verification_status: string;
  confidence_score: number;
  evidence_ids: string[];
}

export interface ContradictionRecord {
  contradiction_id: string;
  claim_a_id: string;
  claim_b_id: string | null;
  evidence_a_id: string | null;
  evidence_b_id: string | null;
  summary: string;
  severity: string;
  resolved: boolean;
}

export interface AdvisorReportPayload {
  interpretation: string;
  stance: "SUPPORT" | "CONDITIONAL" | "OPPOSE" | "INSUFFICIENT_EVIDENCE";
  confidence: number;
  executive_findings: string;
  key_claims: Array<{
    claim_id: string;
    statement: string;
    classification: string;
    evidence_ids: string[];
  }>;
  advantages: string[];
  risks_and_weaknesses: string[];
  self_identified_weakness: string;
  assumptions: string[];
  missing_evidence: string[];
  recommendations: string[];
  evidence_ids_cited: string[];
  private_working_notes: string;
}

export interface AdvisorSession {
  session_id: string;
  investigation_id: string;
  advisor_id: string;
  advisor_name: string;
  advisor_role: string;
  status: string;
  assigned_provider: string;
  assigned_model: string;
  prompt_version: string;
  initial_report: AdvisorReportPayload | null;
  final_report: AdvisorReportPayload | null;
  position_changed: string;
  unverified_citations: string[];
  private_notes: string;
  updated_at: string;
}

export interface IndependenceMetrics {
  investigation_id: string;
  advisor_count: number;
  stance_distribution: Record<string, number>;
  pairwise_claim_overlap: number;
  lexical_similarity_mean: number;
  distinct_model_families: number;
  divergence_score: number;
  correlated_risk_warning: string | null;
}

export interface ChallengeEdge {
  challenge_id: string;
  round_number: number;
  challenger_id: string;
  target_advisor_id: string;
  target_claim_id: string;
  disputed_claim_text: string;
  challenge_argument: string;
  requested_action: string;
  impact_score: number;
  uncertainty_score: number;
  relevance_score: number;
  priority_score: number;
  status: string;
  disposition: string | null;
  evidence_ids: string[];
}

export interface DebateMessage {
  message_id: string;
  round_number: number;
  sender: string;
  receiver: string;
  message_type: string;
  target_claim_id: string | null;
  argument: string;
  evidence_ids: string[];
  unverified_evidence_ids: string[];
  requested_action: string | null;
  priority: string;
  disposition: string | null;
  position_change: string | null;
  created_at: string;
}

export interface DebateTranscript {
  investigation_id: string;
  total_rounds: number;
  messages: DebateMessage[];
  challenges: ChallengeEdge[];
  unresolved_disagreements: string[];
}

export interface JudgeEvaluation {
  evaluation_id: string;
  investigation_id: string;
  model_used: string;
  provider_used: string;
  verdict: VerdictType;
  feasibility_score: number;
  confidence: number;
  executive_summary: string;
  decision_rationale: string;
  scorecard: Array<{
    dimension: string;
    label: string;
    weight: number;
    score: number;
    weighted_contribution: number;
    rationale: string;
  }>;
  hard_blockers: Array<{
    blocker_id: string;
    category: string;
    severity: string;
    description: string;
    evidence_ids: string[];
  }>;
  deterministic_checks: Record<string, unknown>;
  best_arguments_for: string[];
  strongest_arguments_against: string[];
  advisor_rationales: Array<{
    advisor_id: string;
    decision: string;
    reason: string;
  }>;
  preserved_minority_opinions: string[];
  required_changes: string[];
  conditions_for_approval: string[];
  prerequisites_needed: string[];
  risk_register: Array<{
    risk_id: string;
    title: string;
    category: string;
    likelihood: string;
    impact: string;
    mitigation: string;
    owner_role: string;
  }>;
  roadmap: Array<{
    phase: string;
    title: string;
    owner_role: string;
    deliverable: string;
    acceptance_criterion: string;
    stop_condition: string;
  }>;
  kpis: string[];
  remaining_questions: string[];
  disagreed_with_majority: boolean;
  created_at: string;
}

export interface ProviderInfo {
  provider_id: string;
  display_name: string;
  protocol: string;
  base_url: string;
  api_key_url: string;
  is_free_tier: boolean;
  requires_credit_card: boolean;
  has_key_configured: boolean;
  masked_key: string;
  default_rpm: number;
  default_rpd: number;
  requests_today: number;
  free_models_count: number;
  max_context: number;
  status: string;
  tagline: string;
}

export interface ModelEntry {
  id: string;
  provider: string;
  model_id: string;
  display_name: string;
  execution_mode: string;
  family: string;
  capabilities: string[];
  supports_tools: boolean;
  supports_json: boolean;
  context_window: number | null;
  rate_limit_note: string;
  is_free: boolean;
  availability_status: string;
  last_health_check: string | null;
  latency_ms: number | null;
  enabled: boolean;
}

export interface AuditEventItem {
  event_id: number;
  investigation_id: string | null;
  actor: string;
  event_type: string;
  stage: string;
  summary: string;
  created_at: string;
}

export interface ModelUsageItem {
  usage_id: number;
  investigation_id: string | null;
  agent_id: string;
  provider: string;
  model_id: string;
  prompt_version: string;
  prompt_tokens: number;
  completion_tokens: number;
  total_tokens: number;
  latency_ms: number;
  estimated_cost_usd: number;
  status: string;
  error_message: string | null;
  created_at: string;
}

export interface BenchmarkRun {
  run_id: string;
  target: string;
  total_cases: number;
  passed_cases: number;
  overall_score: number;
  results: Array<{
    case_id: string;
    name: string;
    category: string;
    passed: boolean;
    score: number;
    details: string;
  }>;
  executed_at: string;
}
