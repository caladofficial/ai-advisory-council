# AI Advisory Council — System Architecture

## 1. High-Level Four-Engine Design

```
User Topic / Uploaded Docs
   │
   ▼
[Stage 1-2] Topic Analyzer & 12-Family Research Planner
   │
   ▼
[Engine 01] Centralized Research & Evidence Intelligence System (EIS)
   │  Connectors: OpenAlex · Crossref · arXiv · GitHub · HuggingFace · Wikipedia · Web/Crawl · Uploads
   │  Safety: SSRF block · HTML sanitization · Prompt-injection defense (<untrusted_evidence>)
   │  Pipeline: 3-Level Dedup -> Chunking (EVD-*) -> Atomic Claims (CLAIM-*) -> Quality Score -> Contradictions
   ▼
[Gate] Pre-Debate Intelligence & Readiness Gate (100-pt Rubric + Hard Gates + Cost/Quota Estimator)
   │  < 55 -> Auto Research-Gap Loop (max 2) or NEEDS_USER_INPUT / INSUFFICIENT_EVIDENCE
   ▼
[Engine 02] 10 Independent Advisors ("Separate Brains" — Blind Stage 5)
   │  Layer A: Specialist Prompt + Anti-Sycophancy Base + Role Criteria
   │  Layer B: Diversified Model Assignment (Ollama local + verified free APIs via Model Router)
   │  Layer C: Isolated Private Notes + Role-Filtered Evidence Lens (no cross-visibility)
   ▼
[Engine 03] Moderator & 4-Round Structured Debate
   │  R1 Opening Statements -> Challenge Graph (P = I * U * R) -> R2 Targeted Challenges
   │  -> R3 Rebuttals & Revisions (preserve original + revised) -> R4 Final Submissions
   ▼
[Final Authority] Independent Chief Judge (11th Agent)
   │  Read-only over Evidence, Contradictions, Citation Flags, Initial & Final Reports, Transcript
   │  8-Dimension Adaptive Scorecard + Deterministic Audits + Hard-Blocker Override + Minority Dissent
   │  Verdict: GO | CONDITIONAL_GO | PILOT_FIRST | PIVOT | NO_GO | INSUFFICIENT_EVIDENCE
   ▼
Immutable Versioned Dossier + Audit Trail + Exports (MD / JSON / HTML / PDF / CSV / ZIP)
```

## 2. State Machine & Checkpoint Recovery
States: `CREATED -> INTAKE_VALIDATION -> PLANNING -> PREREQUISITE_CHECK -> RESEARCHING -> EVIDENCE_VERIFICATION -> READINESS_GATE -> INDEPENDENT_ANALYSIS -> DEBATE_PREPARATION -> OPENING_ROUND -> CHALLENGE_ROUND -> REBUTTAL_ROUND -> FINAL_ADVISOR_REPORTS -> CHIEF_JUDGE -> REPORT_GENERATION -> COMPLETED` (plus `NEEDS_USER_INPUT`, `INSUFFICIENT_EVIDENCE`, `PAUSED`, `FAILED`, `CANCELLED`).

Every stage transitions atomically in SQLite/PostgreSQL and checkpoints via LangGraph `SqliteSaver`, ensuring pause/resume/cancel and failure recovery never duplicate completed advisor reports or research tasks.
