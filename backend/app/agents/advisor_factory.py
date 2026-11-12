"""Advisor Factory loading isolated specialist configurations and prompt contracts."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from app.config import get_agents_config

PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"


def load_prompt_file(filename: str) -> str:
    path = PROMPTS_DIR / filename
    return path.read_text(encoding="utf-8").strip() if path.exists() else ""


@dataclass
class AdvisorSpec:
    advisor_id: str
    name: str
    title: str
    role: str
    priority: str
    temperature: float
    max_output_tokens: int
    preferred_capability: str
    evidence_source_types: list[str]
    evidence_keywords: list[str]
    tool_permissions: list[str]
    evaluation_criteria: list[str]
    bias_controls: list[str]
    system_prompt: str
    prompt_version: str = "v1.0"
    model_preferences: list[dict] = field(default_factory=list)


def get_council_specs(execution_profile: str = "full_10_plus_1") -> list[AdvisorSpec]:
    """Construct independent AdvisorSpec objects for either full 10-seat council or 3-seat prototype."""
    cfg = get_agents_config()
    shared_base = load_prompt_file("shared_base.txt")
    proto_ids = set(cfg.get("execution", {}).get("prototype_advisor_ids", []))
    specs: list[AdvisorSpec] = []

    for item in cfg.get("advisors", []):
        aid = item["advisor_id"]
        if execution_profile == "prototype_3_plus_1" and proto_ids and aid not in proto_ids:
            continue
        role_prompt = load_prompt_file(f"{aid}.txt")
        lens = item.get("evidence_lens", {})
        bias = item.get("bias_controls", [])
        criteria = item.get("evaluation_criteria", [])

        full_system = (
            f"{shared_base}\n\n"
            f"{role_prompt}\n\n"
            f"EVALUATION CRITERIA:\n" + "\n".join(f"- {c}" for c in criteria) + "\n\n"
            f"BIAS CONTROLS:\n" + "\n".join(f"- {b}" for b in bias)
        )
        specs.append(
            AdvisorSpec(
                advisor_id=aid,
                name=item["name"],
                title=item.get("title", item["name"]),
                role=item["role"],
                priority=item.get("priority", "medium"),
                temperature=float(item.get("temperature", 0.2)),
                max_output_tokens=int(item.get("max_output_tokens", 3000)),
                preferred_capability=item.get("preferred_capability", "general"),
                evidence_source_types=list(lens.get("source_types", [])),
                evidence_keywords=list(lens.get("keywords", [])),
                tool_permissions=list(item.get("tool_permissions", ["evidence_search"])),
                evaluation_criteria=criteria,
                bias_controls=bias,
                system_prompt=full_system,
                model_preferences=list(item.get("model_preferences", [])),
            )
        )
    return specs
