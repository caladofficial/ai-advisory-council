# AI Advisory Council — REST & SSE API Contract

All endpoints run under the FastAPI backend (`http://127.0.0.1:8000` by default). Interactive OpenAPI documentation is available at `/docs`.

## Investigations & Control
- `POST /api/investigations` — Submit a topic, mode (`general_decision`, `business_feasibility`, `technical_feasibility`, `scientific_research`, `product_evaluation`, `policy_analysis`), execution profile (`full_10_plus_1` | `prototype_3_plus_1`), constraints, and connectors.
- `GET /api/investigations` — List all investigations.
- `GET /api/investigations/{id}` — Retrieve full investigation summary.
- `DELETE /api/investigations/{id}` — Delete investigation and cascade all records.
- `POST /api/investigations/{id}/start` — Launch LangGraph state machine.
- `POST /api/investigations/{id}/pause` — Checkpoint pause at next node boundary.
- `POST /api/investigations/{id}/resume` — Resume cleanly from saved checkpoint without duplicating completed reports.
- `POST /api/investigations/{id}/cancel` — Cancel workflow.
- `POST /api/investigations/{id}/clarify` — Submit missing prerequisites and resume past `NEEDS_USER_INPUT`.
- `GET /api/investigations/{id}/progress` — Live snapshot of stage, percent, and per-advisor status.
- `GET /api/investigations/{id}/progress/stream` — Server-Sent Events (SSE) live stream.

## Research, Evidence, & Prerequisites
- `GET /api/investigations/{id}/prerequisites` — 100-pt readiness score, 10-category checklist, assumptions, gaps, and zero-paid token/cost estimate.
- `POST /api/investigations/{id}/additional-research` — Trigger additional targeted queries across connectors.
- `POST /api/investigations/{id}/upload` — Upload `.pdf`, `.md`, `.txt`, `.csv`, `.json` documents safely.
- `GET /api/investigations/{id}/sources` — Deduped/syndicated sources register.
- `GET /api/investigations/{id}/evidence` — Passage chunks (`EVD-*`) with 5-dimension quality scores.
- `GET /api/investigations/{id}/claims` — Atomic claims filterable by verification status (`?status=CONTRADICTED`, etc.).
- `GET /api/investigations/{id}/contradictions` — Detected conflicts across sources.

## Advisors, Debate, Judge, & Exports
- `GET /api/advisors/profiles` — All 10 specialist advisor specifications.
- `GET /api/investigations/{id}/advisors` — Live advisor statuses, initial vs final reports, citation flags, and isolated private notes.
- `GET /api/investigations/{id}/independence` — Correlated-error divergence & lexical similarity telemetry.
- `GET /api/investigations/{id}/debate` — Challenge Graph (`P = I * U * R`) + 4-round structured transcript.
- `GET /api/investigations/{id}/judge` — Independent Chief Judge verdict, 8-dimension adaptive scorecard, deterministic checks, blockers, risk register, and roadmap.
- `GET /api/investigations/{id}/report` — Immutable versioned dossier JSON + Markdown.
- `GET /api/investigations/{id}/export/{fmt}` — Download `md`, `json`, `html`, `pdf`, `csv`, or `zip`.

## Models, Evaluation, & Audit
- `GET /api/cost-policy` — Active zero-paid policy rules.
- `GET /api/providers` — 31+ free providers from `awesome-freellm-apis` + Ollama status.
- `POST /api/providers/configure-key` — Store free API key server-side (masked in UI, scrubbed from logs).
- `GET /api/models`, `POST /api/models/sync`, `POST /api/models/health-check`, `POST /api/models/assign-advisor`.
- `POST /api/evaluation/run` — Run Evaluation Lab security, deduplication, citation, math, and optional live model benchmarks.
- `GET /api/audit` & `GET /api/audit/{id}` — Append-only event stream & token usage ledger.
