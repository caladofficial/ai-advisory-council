"""Deterministic Python calculation helpers so financial/technical advisors and the Judge do not rely on LLM mental math."""

from __future__ import annotations

import re
from typing import Any


def parse_budget_hint(budget_text: str) -> dict[str, Any]:
    """Extract numeric amount and currency cue from a user budget string if present."""
    text = (budget_text or "").strip()
    if not text:
        return {"has_explicit_budget": False, "amount": None, "currency": None}

    currency = "INR" if ("₹" in text or "inr" in text.lower() or "lakh" in text.lower() or "crore" in text.lower()) else (
        "EUR" if ("€" in text or "eur" in text.lower()) else "USD"
    )
    m = re.search(r"(\d+(?:[.,]\d+)?)", text.replace(",", ""))
    if not m:
        return {"has_explicit_budget": True, "raw": text, "amount": None, "currency": currency}

    val = float(m.group(1))
    lower = text.lower()
    if "lakh" in lower:
        val *= 100_000
    elif "crore" in lower:
        val *= 10_000_000
    elif "million" in lower or re.search(r"\b\d+m\b", lower):
        val *= 1_000_000
    elif re.search(r"\b\d+k\b", lower):
        val *= 1_000

    return {
        "has_explicit_budget": True,
        "raw": text,
        "amount": round(val, 2),
        "currency": currency,
    }


def compute_unit_economics_scenarios(
    *,
    initial_capex: float,
    monthly_opex: float,
    monthly_revenue_base: float,
    horizon_months: int = 12,
) -> dict[str, Any]:
    """Deterministically calculate best/base/worst net cash flow, ROI, and break-even month."""
    scenarios: dict[str, dict[str, float | int | None]] = {}
    for name, rev_mult, cost_mult in (
        ("best_case", 1.35, 0.90),
        ("base_case", 1.00, 1.00),
        ("worst_case", 0.55, 1.25),
    ):
        m_rev = monthly_revenue_base * rev_mult
        m_cost = monthly_opex * cost_mult
        net_monthly = m_rev - m_cost
        total_outflow = initial_capex + m_cost * horizon_months
        total_inflow = m_rev * horizon_months
        net_profit = total_inflow - total_outflow
        roi_pct = (net_profit / total_outflow * 100.0) if total_outflow > 0 else 0.0
        break_even_months = (
            round(initial_capex / net_monthly, 1) if net_monthly > 0 else None
        )
        scenarios[name] = {
            "monthly_revenue": round(m_rev, 2),
            "monthly_opex": round(m_cost, 2),
            "net_monthly_cashflow": round(net_monthly, 2),
            "horizon_net_profit": round(net_profit, 2),
            "horizon_roi_percent": round(roi_pct, 1),
            "break_even_months": break_even_months,
        }
    return scenarios


def build_financial_sandbox_summary(budget_text: str) -> str:
    """Provide deterministic baseline financial context for Financial/Operations/Strategy advisors."""
    parsed = parse_budget_hint(budget_text)
    if parsed.get("amount"):
        amt = float(parsed["amount"])
        cur = parsed["currency"]
        scenarios = compute_unit_economics_scenarios(
            initial_capex=amt * 0.6,
            monthly_opex=max(100.0, (amt * 0.4) / 12.0),
            monthly_revenue_base=max(150.0, (amt * 0.55) / 12.0),
            horizon_months=12,
        )
        return (
            f"Deterministic Financial Sandbox (User Budget={amt:,.0f} {cur}):\n"
            f"- Best Case 12m ROI: {scenarios['best_case']['horizon_roi_percent']}% (break-even ~{scenarios['best_case']['break_even_months']} mo)\n"
            f"- Base Case 12m ROI: {scenarios['base_case']['horizon_roi_percent']}% (break-even ~{scenarios['base_case']['break_even_months']} mo)\n"
            f"- Worst Case 12m Net Profit: {scenarios['worst_case']['horizon_net_profit']:,.0f} {cur}"
        )
    return (
        "Deterministic Financial Sandbox: No numeric budget specified by user. "
        "Zero-paid open-source stack baseline assumes $0 software licensing + hardware/hosted quota limits; "
        "any commercial hosting/API scaling costs must be explicitly flagged as ESTIMATE."
    )
