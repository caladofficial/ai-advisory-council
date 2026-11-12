"""Complete 16-state LangGraph StateGraph workflow with checkpoint recovery, gap loops, and SSE updates."""

from __future__ import annotations

import asyncio
from typing import Literal

from langgraph.graph import END, START, StateGraph
from sqlalchemy import select

from app.agents.advisor_factory import get_council_specs
from app.agents.advisor_runner import (
    ensure_advisor_session,
    run_advisor_final_submission_stateless,
    run_advisor_initial_analysis_stateless,
)
from app.agents.judge import run_chief_judge
from app.agents.moderator import (
    build_and_dispatch_challenges,
    publish_opening_round,
    run_rebuttal_round,
)
from app.config import get_agents_config
from app.database.models import AdvisorSession, Investigation, ResearchQuestion
from app.database.repository import log_audit_event, update_investigation_stage
from app.database.session import session_scope
from app.evidence.verifier import verify_investigation_evidence
from app.models.router import NoAvailableModelError
from app.orchestration.checkpointing import open_checkpointer
from app.orchestration.events import progress_broker
from app.orchestration.state import InvestigationState
from app.prerequisites.assessor import assess_prerequisites
from app.prerequisites.readiness_gate import evaluate_readiness_gate
from app.reports.generator import build_investigation_dossier
from app.research.collector import run_research_collection
from app.research.planner import build_investigation_brief, generate_research_plan
from app.schemas.investigation import InvestigationStatus
from app.schemas.prerequisites import ReadinessStatus


def _advisor_status_map(db, investigation_id: str) -> dict[str, str]:
    rows = db.scalars(select(AdvisorSession).where(AdvisorSession.investigation_id == investigation_id)).all()
    return {r.advisor_id: r.status for r in rows}


def _check_control_flags(db, inv_id: str) -> str | None:
    inv = db.get(Investigation, inv_id)
    if inv is None:
        return InvestigationStatus.FAILED.value
    if inv.cancel_requested:
        return InvestigationStatus.CANCELLED.value
    if inv.pause_requested:
        return InvestigationStatus.PAUSED.value
    return None


def _emit(db, inv_id: str, status: str, pct: int, message: str, *, actor: str = "orchestrator") -> None:
    update_investigation_stage(db, inv_id, status, pct)
    log_audit_event(db, investigation_id=inv_id, actor=actor, event_type=f"STAGE_{status}", stage=status, summary=message)
    adv_map = _advisor_status_map(db, inv_id)
    progress_broker.publish(inv_id, status=status, stage=status, progress_percent=pct, message=message, advisor_statuses=adv_map)


async def node_intake_validation(state: InvestigationState) -> dict:
    inv_id = state["investigation_id"]
    with session_scope() as db:
        if halted := _check_control_flags(db, inv_id):
            return {"halted_status": halted}
        inv = db.get(Investigation, inv_id)
        assert inv is not None
        build_investigation_brief(inv)
        _emit(db, inv_id, InvestigationStatus.INTAKE_VALIDATION.value, 10, "Investigation brief validated and domain classified.")
    return {}


async def node_planning(state: InvestigationState) -> dict:
    inv_id = state["investigation_id"]
    with session_scope() as db:
        if halted := _check_control_flags(db, inv_id):
            return {"halted_status": halted}
        inv = db.get(Investigation, inv_id)
        assert inv is not None
        questions = generate_research_plan(db, inv)
        _emit(db, inv_id, InvestigationStatus.PLANNING.value, 18, f"Generated {len(questions)} multi-perspective research questions.")
    return {}


async def node_prerequisite_check(state: InvestigationState) -> dict:
    inv_id = state["investigation_id"]
    with session_scope() as db:
        if halted := _check_control_flags(db, inv_id):
            return {"halted_status": halted}
        inv = db.get(Investigation, inv_id)
        assert inv is not None
        assess_prerequisites(db, inv)
        _emit(db, inv_id, InvestigationStatus.PREREQUISITE_CHECK.value, 25, "Evaluated 10 prerequisite categories and initial assumptions.")
    return {}


async def node_researching(state: InvestigationState) -> dict:
    inv_id = state["investigation_id"]
    cycle = state.get("research_cycle", 0)
    with session_scope() as db:
        if halted := _check_control_flags(db, inv_id):
            return {"halted_status": halted}
        inv = db.get(Investigation, inv_id)
        assert inv is not None
        from app.database.models import ResearchTask
        existing_tasks = db.scalars(select(ResearchTask).where(ResearchTask.investigation_id == inv_id)).first()
        if cycle == 0 and existing_tasks is not None:
            _emit(db, inv_id, InvestigationStatus.RESEARCHING.value, 42, "Resumed from checkpoint: reusing previously collected research sources.")
            return {"research_cycle": 1}

        _emit(db, inv_id, InvestigationStatus.RESEARCHING.value, 35 + cycle * 4, f"Executing research cycle {cycle + 1} across enabled source connectors...")
        questions = list(db.scalars(select(ResearchQuestion).where(ResearchQuestion.investigation_id == inv_id)).all())
        extra = None
        if cycle > 0:
            # Focused gap-fill cycle querying web & academic benchmarks
            core = (inv.brief_json or {}).get("core_keywords") or inv.topic[:60]
            extra = [("web_search", f"{core} cost failure risks empirical evidence"), ("openalex", core)]
        summary = await run_research_collection(db, inv, questions, extra_queries=extra)
        _emit(
            db,
            inv_id,
            InvestigationStatus.RESEARCHING.value,
            42 + cycle * 3,
            f"Collected {summary['sources_added']} sources and {summary['evidence_chunks_added']} evidence chunks.",
        )
    return {"research_cycle": cycle + 1}


async def node_evidence_verification(state: InvestigationState) -> dict:
    inv_id = state["investigation_id"]
    with session_scope() as db:
        if halted := _check_control_flags(db, inv_id):
            return {"halted_status": halted}
        inv = db.get(Investigation, inv_id)
        assert inv is not None
        stats = verify_investigation_evidence(db, inv)
        _emit(
            db,
            inv_id,
            InvestigationStatus.EVIDENCE_VERIFICATION.value,
            50,
            f"Verified {stats['total_claims']} atomic claims across {stats['unique_sources']} unique sources ({stats['contradictions']} contradictions).",
        )
    return {}


async def node_readiness_gate(state: InvestigationState) -> dict:
    inv_id = state["investigation_id"]
    force_warn = bool(state.get("force_proceed_warnings", False))
    with session_scope() as db:
        if halted := _check_control_flags(db, inv_id):
            return {"halted_status": halted}
        inv = db.get(Investigation, inv_id)
        assert inv is not None
        gate = evaluate_readiness_gate(db, inv, force_proceed_with_warnings=force_warn)
        _emit(
            db,
            inv_id,
            InvestigationStatus.READINESS_GATE.value,
            55,
            f"Readiness Gate: {gate.readiness_status.value} ({gate.readiness_score}/100).",
        )
        return {
            "readiness_allowed": gate.allowed_next_stage,
            "readiness_status": gate.readiness_status.value,
        }


async def node_independent_analysis(state: InvestigationState) -> dict:
    inv_id = state["investigation_id"]
    max_par = int(get_agents_config().get("execution", {}).get("max_parallel_advisors", 3))
    with session_scope() as db:
        if halted := _check_control_flags(db, inv_id):
            return {"halted_status": halted}
        inv = db.get(Investigation, inv_id)
        assert inv is not None
        specs = get_council_specs(inv.execution_profile)
        for sp in specs:
            ensure_advisor_session(db, inv, sp)
        _emit(db, inv_id, InvestigationStatus.INDEPENDENT_ANALYSIS.value, 60, f"Launching {len(specs)} blind independent advisor assessments...")

    sem = asyncio.Semaphore(max(1, max_par))

    async def _run_one(spec) -> None:
        async with sem:
            await run_advisor_initial_analysis_stateless(inv_id, spec)
            with session_scope() as sub_db:
                progress_broker.publish(
                    inv_id,
                    status=InvestigationStatus.INDEPENDENT_ANALYSIS.value,
                    stage=InvestigationStatus.INDEPENDENT_ANALYSIS.value,
                    progress_percent=66,
                    message=f"{spec.name} completed blind Stage-5 assessment.",
                    advisor_statuses=_advisor_status_map(sub_db, inv_id),
                )

    try:
        await asyncio.gather(*[_run_one(s) for s in specs])
    except NoAvailableModelError as exc:
        with session_scope() as db:
            update_investigation_stage(db, inv_id, InvestigationStatus.PAUSED.value, 65, error_message=str(exc))
            progress_broker.publish(inv_id, status="PAUSED", stage="INDEPENDENT_ANALYSIS", progress_percent=65, message=f"Paused at checkpoint: {exc}")
        return {"halted_status": InvestigationStatus.PAUSED.value, "error_message": str(exc)}

    with session_scope() as db:
        _emit(db, inv_id, InvestigationStatus.INDEPENDENT_ANALYSIS.value, 70, "All blind initial advisor reports completed and isolated.")
    return {}


async def node_debate_preparation(state: InvestigationState) -> dict:
    inv_id = state["investigation_id"]
    try:
        with session_scope() as db:
            if halted := _check_control_flags(db, inv_id):
                return {"halted_status": halted}
            inv = db.get(Investigation, inv_id)
            assert inv is not None
            specs = get_council_specs(inv.execution_profile)
            publish_opening_round(db, inv, specs)
            _emit(db, inv_id, InvestigationStatus.OPENING_ROUND.value, 75, "Round 1: Published all independent opening statements.")
            challenges = await build_and_dispatch_challenges(db, inv, specs)
            _emit(db, inv_id, InvestigationStatus.CHALLENGE_ROUND.value, 80, f"Round 2: Dispatched {len(challenges)} prioritized challenges (P = I x U x R).")
    except NoAvailableModelError as exc:
        with session_scope() as db:
            update_investigation_stage(db, inv_id, InvestigationStatus.PAUSED.value, 78, error_message=str(exc))
        return {"halted_status": InvestigationStatus.PAUSED.value, "error_message": str(exc)}
    return {}


async def node_rebuttal_round(state: InvestigationState) -> dict:
    inv_id = state["investigation_id"]
    try:
        with session_scope() as db:
            if halted := _check_control_flags(db, inv_id):
                return {"halted_status": halted}
            inv = db.get(Investigation, inv_id)
            assert inv is not None
            specs = get_council_specs(inv.execution_profile)
            rebuttals = await run_rebuttal_round(db, inv, specs)
            _emit(db, inv_id, InvestigationStatus.REBUTTAL_ROUND.value, 85, f"Round 3: Completed {len(rebuttals)} evidence-grounded rebuttals.")
    except NoAvailableModelError as exc:
        with session_scope() as db:
            update_investigation_stage(db, inv_id, InvestigationStatus.PAUSED.value, 83, error_message=str(exc))
        return {"halted_status": InvestigationStatus.PAUSED.value, "error_message": str(exc)}
    return {}


async def node_final_advisor_reports(state: InvestigationState) -> dict:
    inv_id = state["investigation_id"]
    max_par = int(get_agents_config().get("execution", {}).get("max_parallel_advisors", 3))
    with session_scope() as db:
        if halted := _check_control_flags(db, inv_id):
            return {"halted_status": halted}
        inv = db.get(Investigation, inv_id)
        assert inv is not None
        specs = get_council_specs(inv.execution_profile)

    sem = asyncio.Semaphore(max(1, max_par))

    async def _run_final(spec) -> None:
        async with sem:
            await run_advisor_final_submission_stateless(inv_id, spec)

    try:
        await asyncio.gather(*[_run_final(s) for s in specs])
    except NoAvailableModelError as exc:
        with session_scope() as db:
            update_investigation_stage(db, inv_id, InvestigationStatus.PAUSED.value, 88, error_message=str(exc))
        return {"halted_status": InvestigationStatus.PAUSED.value, "error_message": str(exc)}

    with session_scope() as db:
        _emit(db, inv_id, InvestigationStatus.FINAL_ADVISOR_REPORTS.value, 90, "Round 4: Recorded final advisor submissions while preserving initial reports.")
    return {}


async def node_chief_judge(state: InvestigationState) -> dict:
    inv_id = state["investigation_id"]
    try:
        with session_scope() as db:
            if halted := _check_control_flags(db, inv_id):
                return {"halted_status": halted}
            inv = db.get(Investigation, inv_id)
            assert inv is not None
            evaluation = await run_chief_judge(db, inv)
            _emit(
                db,
                inv_id,
                InvestigationStatus.CHIEF_JUDGE.value,
                95,
                f"Chief Judge Verdict: {evaluation.verdict} (Feasibility {evaluation.feasibility_score}/100).",
                actor="chief_judge",
            )
    except NoAvailableModelError as exc:
        with session_scope() as db:
            update_investigation_stage(db, inv_id, InvestigationStatus.PAUSED.value, 92, error_message=str(exc))
        return {"halted_status": InvestigationStatus.PAUSED.value, "error_message": str(exc)}
    return {}


async def node_report_generation(state: InvestigationState) -> dict:
    inv_id = state["investigation_id"]
    with session_scope() as db:
        inv = db.get(Investigation, inv_id)
        assert inv is not None
        rv = build_investigation_dossier(db, inv)
        _emit(
            db,
            inv_id,
            InvestigationStatus.COMPLETED.value,
            100,
            f"Completed Dossier v{rv.version_number} ({inv.verdict}).",
            actor="report_generator",
        )
    return {}


def _route_after_halt_or(next_node: str):
    def _router(state: InvestigationState) -> str:
        if state.get("halted_status"):
            return END
        return next_node
    return _router


def _route_readiness_gate(state: InvestigationState) -> Literal["researching", "independent_analysis", "__end__"]:
    if state.get("halted_status"):
        return END
    if state.get("readiness_allowed"):
        return "independent_analysis"

    inv_id = state["investigation_id"]
    status = state.get("readiness_status", "")
    cycle = state.get("research_cycle", 1)
    max_cycles = state.get("max_research_cycles", 2)

    if status == ReadinessStatus.NEEDS_MORE_RESEARCH.value and cycle < max_cycles:
        return "researching"

    # Pause cleanly for user input or insufficient evidence if gap loops exhausted
    target_state = (
        InvestigationStatus.NEEDS_USER_INPUT.value
        if status == ReadinessStatus.NEEDS_USER_INPUT.value
        else InvestigationStatus.INSUFFICIENT_EVIDENCE.value
    )
    with session_scope() as db:
        _emit(db, inv_id, target_state, 55, f"Workflow halted at Readiness Gate: {status}.")
    return END


def build_council_graph(checkpointer=None):
    """Build and compile the complete AI Advisory Council LangGraph StateGraph."""
    g = StateGraph(InvestigationState)
    g.add_node("intake_validation", node_intake_validation)
    g.add_node("planning", node_planning)
    g.add_node("prerequisite_check", node_prerequisite_check)
    g.add_node("researching", node_researching)
    g.add_node("evidence_verification", node_evidence_verification)
    g.add_node("readiness_gate", node_readiness_gate)
    g.add_node("independent_analysis", node_independent_analysis)
    g.add_node("debate_preparation", node_debate_preparation)
    g.add_node("rebuttal_round", node_rebuttal_round)
    g.add_node("final_advisor_reports", node_final_advisor_reports)
    g.add_node("chief_judge", node_chief_judge)
    g.add_node("report_generation", node_report_generation)

    g.add_edge(START, "intake_validation")
    g.add_conditional_edges("intake_validation", _route_after_halt_or("planning"))
    g.add_conditional_edges("planning", _route_after_halt_or("prerequisite_check"))
    g.add_conditional_edges("prerequisite_check", _route_after_halt_or("researching"))
    g.add_conditional_edges("researching", _route_after_halt_or("evidence_verification"))
    g.add_conditional_edges("evidence_verification", _route_after_halt_or("readiness_gate"))
    g.add_conditional_edges("readiness_gate", _route_readiness_gate)
    g.add_conditional_edges("independent_analysis", _route_after_halt_or("debate_preparation"))
    g.add_conditional_edges("debate_preparation", _route_after_halt_or("rebuttal_round"))
    g.add_conditional_edges("rebuttal_round", _route_after_halt_or("final_advisor_reports"))
    g.add_conditional_edges("final_advisor_reports", _route_after_halt_or("chief_judge"))
    g.add_conditional_edges("chief_judge", _route_after_halt_or("report_generation"))
    g.add_edge("report_generation", END)

    return g.compile(checkpointer=checkpointer)


# Track active background execution tasks cleanly
ACTIVE_RUNS: dict[str, asyncio.Task] = {}


async def execute_investigation_workflow(
    investigation_id: str,
    *,
    force_proceed_warnings: bool = False,
) -> None:
    """Run or resume an investigation inside LangGraph with persistent SqliteSaver checkpoints."""
    with session_scope() as db:
        inv = db.get(Investigation, investigation_id)
        if inv is None:
            return
        inv.pause_requested = False
        inv.cancel_requested = False
        inv.error_message = None

    try:
        async with open_checkpointer() as checkpointer:
            graph = build_council_graph(checkpointer=checkpointer)
            config = {"configurable": {"thread_id": investigation_id}}
            snap = await graph.aget_state(config)

            if snap and snap.next:
                # Resume paused checkpoint cleanly from next node!
                await graph.ainvoke(None, config=config)
            else:
                init_state: InvestigationState = {
                    "investigation_id": investigation_id,
                    "research_cycle": 0,
                    "max_research_cycles": int(
                        get_agents_config().get("execution", {}).get("max_research_gap_cycles", 2)
                    ),
                    "force_proceed_warnings": force_proceed_warnings,
                    "halted_status": None,
                }
                await graph.ainvoke(init_state, config=config)

        # If halted cleanly due to pause/cancel request, reflect final DB status
        with session_scope() as db:
            inv = db.get(Investigation, investigation_id)
            if inv:
                if inv.cancel_requested and inv.status != InvestigationStatus.CANCELLED.value:
                    _emit(db, investigation_id, InvestigationStatus.CANCELLED.value, inv.progress_percent, "Investigation cancelled by user.")
                elif inv.pause_requested and inv.status not in {InvestigationStatus.PAUSED.value, InvestigationStatus.COMPLETED.value}:
                    _emit(db, investigation_id, InvestigationStatus.PAUSED.value, inv.progress_percent, "Investigation paused at checkpoint.")
    except Exception as exc:
        with session_scope() as db:
            update_investigation_stage(
                db,
                investigation_id,
                InvestigationStatus.FAILED.value,
                0,
                error_message=str(exc),
            )
            log_audit_event(
                db,
                investigation_id=investigation_id,
                actor="orchestrator",
                event_type="WORKFLOW_ERROR",
                stage="FAILED",
                summary=f"Workflow failed: {exc}",
            )
            progress_broker.publish(
                investigation_id,
                status="FAILED",
                stage="FAILED",
                progress_percent=0,
                message=f"Workflow failed: {exc}",
            )
    finally:
        ACTIVE_RUNS.pop(investigation_id, None)
