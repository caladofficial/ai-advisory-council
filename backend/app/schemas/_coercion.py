"""Shared Pydantic field coercion helpers for resilient structured output across diverse free/local LLMs."""

from __future__ import annotations

from typing import Any


def coerce_to_str(value: Any) -> str:
    """Convert dict/list/scalar LLM outputs into clean flat text."""
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, dict):
        for key in ("description", "text", "statement", "summary", "reason", "title", "detail"):
            if key in value and value[key]:
                prefix = value.get("risk_id") or value.get("assumption_id") or value.get("id")
                body = str(value[key]).strip()
                return f"{prefix}: {body}" if prefix else body
        return "; ".join(f"{k}: {v}" for k, v in value.items() if v is not None)
    if isinstance(value, list):
        return "; ".join(coerce_to_str(x) for x in value if x is not None)
    return str(value)


def coerce_str_list(value: Any) -> list[str]:
    """Coerce a field expected to be list[str], flattening dict elements returned by smaller LLMs."""
    if value is None:
        return []
    if isinstance(value, str):
        return [value.strip()] if value.strip() else []
    if isinstance(value, dict):
        return [coerce_to_str(value)]
    if isinstance(value, list):
        out: list[str] = []
        for item in value:
            s = coerce_to_str(item)
            if s:
                out.append(s)
        return out
    return [str(value)]


def coerce_unit_float(value: Any, default: float = 0.6) -> float:
    """Normalize confidence values whether expressed in [0, 1] or [0, 100]."""
    try:
        num = float(value)
    except (TypeError, ValueError):
        return default
    if num > 1.0:
        num = num / 100.0
    return max(0.0, min(1.0, num))
