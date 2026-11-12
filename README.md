# AI Advisory Council

An evidence-first, provider-independent **10 AI Advisors + 1 Independent Chief Judge** research, structured debate, and feasibility adjudication platform.

## Architectural Principles

1. **Evidence Before Opinions** — Centralized Research & Evidence Intelligence System (`OpenAlex`, `Crossref`, `arXiv`, `GitHub REST`, `Hugging Face Hub`, `Wikipedia`, `Web Search/Crawl`, and uploaded documents) normalizes, deduplicates across 3 levels (including syndicated press-release detection), extracts atomic claims, detects contradictions, and runs multi-stage verification before advisors speak.
2. **Pre-Debate Intelligence & Readiness Gate** — Evaluates 10 prerequisite dimensions on a 100-point rubric with hard gates and a `$0.00` resource/token estimator before launching council debate.
3. **Separate Brains (Anti-Correlated-Error Design)** — Each of the 10 specialist advisors uses distinct prompts, bias controls, isolated private working notes, lens-filtered evidence retrieval, and diversified free/local model assignments. Initial Stage-5 reports execute blind before cross-visibility.
4. **Structured Challenge Graph Debate** — Moderator constructs targeted claim challenges prioritized by `P = Impact × Uncertainty × Relevance` rather than unstructured round-robin chatter. Original and revised positions are both preserved.
5. **Independent Chief Judge (Eleventh Authority)** — Read-only over the full evidence register, deterministic citation/math audit flags, contradictions, and debate record. Never relies on majority vote; enforces hard-blocker overrides and supports `INSUFFICIENT_EVIDENCE`.
6. **Strict Zero-Paid Mode** — Local `Ollama` + curated directory of 31+ free API providers imported from [`awesome-freellm-apis`](https://github.com/open-free-llm-api/awesome-freellm-apis) with server-side key protection, quota tracking, and automatic fallback.

## Quick Start (Local Zero-Cost Mode)

### 1. Start Backend (FastAPI + LangGraph + SQLite)
```powershell
cd backend
..\.venv\Scripts\uvicorn.exe app.main:app --host 127.0.0.1 --port 8000 --reload
```

### 2. Start Frontend (React + Vite + TypeScript + Tailwind)
```powershell
cd frontend
pnpm dev
```
Open `http://localhost:5173`.

Or run `.\start_council.ps1` from the repository root to launch both servers cleanly.

### Optional: Production PostgreSQL + pgvector via Docker
```bash
docker compose up --build
```

## Running Automated Acceptance Tests
```powershell
$env:PYTHONPATH="backend"
.\.venv\Scripts\pytest.exe backend/tests -v
```

## Reference Projects Studied
See [docs/REFERENCE_ANALYSIS.md](docs/REFERENCE_ANALYSIS.md) and [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).
