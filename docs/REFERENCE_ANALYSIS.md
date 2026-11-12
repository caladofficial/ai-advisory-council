# Reference Application Analysis & Architectural Synthesis

This document records the line-by-line analysis of the five reference projects studied before building the **AI Advisory Council** platform.

## 1. `zamaniali1995/debate-agent`
**Inspected Structure (`src/debate_agent/`):**
- `graph.py`: LangGraph `StateGraph` with `START -> setup -> opening_pro -> opening_con -> rebuttal_pro -> rebuttal_con -> moderator -> closing -> judge -> human_vote -> save_memory`.
- `state.py`: `DebateState` with `operator.add` reducer for `transcript`/`flags` and `merge_dicts` for private `notes` & `sources`.
- `agents/debater.py`: ReAct debater factory with `retrieved_urls()` & `unverified_citations()` comparing cited URLs against actual tool responses.
- `tools/openalex.py` & `wikipedia.py`: Inverted-index abstract reconstruction (`rebuild_abstract`) and Wikipedia REST integration.
- `llm.py`: Provider chain fallback across Groq, Google Gemini, NVIDIA NIM, OpenRouter, and local Ollama.

**Adopted & Upgraded:**
- Adopted `SqliteSaver` checkpointing, isolated per-agent `notes`, inverted-index OpenAlex parsing, and deterministic citation checking (`flags`).
- Upgraded from 2-party debate to a **10-seat specialist council + Moderator + Independent Chief Judge**, replaced uncoordinated per-turn web searches with a **Centralized Evidence Intelligence System (EIS)**, and added a **Pre-Debate Readiness Gate**.

## 2. `starshine-f/Agent-Debate`
**Inspected Structure (`app/`):**
- `graph.py`, `agent.py`, `config.py`, `api.py`: FastAPI backend supporting `MODEL_PROFILES`, `PERSONA_PRESETS`, multi-role graph orchestration, and NDJSON streaming (`/debate/stream`).

**Adopted & Upgraded:**
- Adopted decoupled model profiles + persona presets + streaming API responses.
- Replaced sequential fixed turn-taking with parallel blind Stage-5 initial analysis, a moderator-computed **Challenge Graph ($P = I \times U \times R$)**, and **Server-Sent Events (SSE)** backed by persistent SQLite/PostgreSQL checkpoint state.

## 3. `neuhai/MAJ-Eval`
**Inspected Structure:**
- `persona_creation.py` & `evaluation_debate.py`: Stakeholder extraction from research papers and multi-agent evaluation debate.

**Adopted & Upgraded:**
- Adopted structured stakeholder perspective schemas and multi-dimensional debate evaluation logs.
- Replaced hardcoded OpenAI/Bedrock calls with a provider-independent **Zero-Paid Model Router** and explicit independence safeguards against correlated model errors.

## 4. `varshithreddym/AI_Debate` (Hugging Face Spaces)
**Inspected Structure:**
- `debate_engine.py`, `agents.py`, `prompts.py`, `winner.py`: Multi-judge breakdown across Logic, Evidence, and Practicality dimensions.

**Adopted & Upgraded:**
- Adopted multi-dimensional evaluation criteria, while eliminating naive majority voting in favor of an **Independent Chief Judge** with deterministic rubric math, hard-blocker overrides, and `INSUFFICIENT_EVIDENCE` support.

## 5. `open-free-llm-api/awesome-freellm-apis`
**Inspected Structure:**
- `status.json` (31 providers, 538+ free models) & `README.md` (rate limits, context windows, OpenAI-compatible endpoints, local engines including Ollama).

**Adopted & Upgraded:**
- Bundled `status.json` & parsed model catalog into `data/catalog/`.
- Fixed upstream `status.json` URL discrepancies observed during inspection (e.g., mapping Google Gemini to `https://generativelanguage.googleapis.com/v1beta/openai/` and Cohere to `https://api.cohere.ai/compatibility/v1`) and wrapped all providers with live health checks, quota tracking, and a strict **`zero_paid`** policy.
