#!/usr/bin/env python3
"""
NOTHING Investment Terminal — Complete Investment Planning Engine
-----------------------------------------------------------------
Uses actual VFEX/ZSE/C-TRADE portfolio data to provide:
1. Investment Goals (persisted in ~/.config/vfex/investment_goals.json)
2. Contribution Planner ($5/$10/$25/$50/$100/custom, multiple frequencies, fee-aware)
3. Asset Allocation & Concentration Analysis
4. Opportunity Evaluation (compared against existing holdings)
5. Non-Destructive What-If Portfolio Simulator
6. Liquidity- & Fee-Aware Rebalancing
7. Personalised Investment Recommendations
8. Bull / Base / Bear Scenario Analysis (explicitly labeled hypothetical)
9. Investment Calendar (dividends, announcements, macro, contributions, reviews)
"""

from __future__ import annotations

import copy
import json
import math
import sys
import uuid
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

FREQ_PER_YEAR = {
    "weekly": 52,
    "biweekly": 26,
    "monthly": 12,
    "quarterly": 4,
    "annual": 1,
}


def compute_required_monthly(current_val: float, target_val: float, years: float, annual_cagr_pct: float = 10.0, fee_pct: float = 1.04) -> float:
    """Compute required monthly contribution to reach target_val in `years` (net of fee_pct)."""
    if target_val <= current_val or years <= 0:
        return 0.0
    n = max(1, int(round(years * 12)))
    r = (annual_cagr_pct / 100.0) / 12.0
    fv_existing = current_val * ((1.0 + r) ** n)
    gap = max(0.0, target_val - fv_existing)
    if gap <= 0:
        return 0.0
    if r <= 1e-9:
        net_pmt = gap / n
    else:
        net_pmt = gap * r / (((1.0 + r) ** n) - 1.0)
    # Gross up for entry fee drag
    gross_pmt = net_pmt / max(0.5, 1.0 - (fee_pct / 100.0))
    return round(gross_pmt, 2)


def simulate_contributions(
    current_value: float,
    available_cash: float,
    amount: float,
    frequency: str = "monthly",
    years: int = 5,
    annual_cagr_pct: float = 10.0,
    fee_pct: float = 1.04,
    fx_drag_pct: float = 0.0,
) -> dict[str, Any]:
    """Hypothetical future value projection accounting for fees, cash, frequency, and FX drag."""
    freq_n = FREQ_PER_YEAR.get(frequency.lower(), 12)
    eff_cagr = (annual_cagr_pct - fx_drag_pct) / 100.0
    r_p = eff_cagr / freq_n
    net_contrib = max(0.0, float(amount)) * (1.0 - max(0.0, fee_pct) / 100.0)
    total_periods = max(1, int(years) * freq_n)

    val = max(0.0, float(current_value)) + max(0.0, float(available_cash))
    total_contributed = 0.0
    total_fees = 0.0
    yearly_curve: list[dict[str, Any]] = []

    for p in range(1, total_periods + 1):
        val = val * (1.0 + r_p) + net_contrib
        total_contributed += float(amount)
        total_fees += float(amount) * (max(0.0, fee_pct) / 100.0)
        if p % freq_n == 0:
            yearly_curve.append({
                "year": p // freq_n,
                "projected_value": round(val, 2),
                "total_contributed": round(total_contributed, 2),
                "hypothetical_gain": round(val - (current_value + available_cash + total_contributed), 2),
            })

    return {
        "hypothetical_disclaimer": "HYPOTHETICAL PROJECTION ONLY — NOT GUARANTEED.",
        "amount": float(amount),
        "frequency": frequency.lower(),
        "years": int(years),
        "annual_cagr_pct": float(annual_cagr_pct),
        "fee_pct": float(fee_pct),
        "fx_drag_pct": float(fx_drag_pct),
        "starting_capital": round(current_value + available_cash, 2),
        "total_contributed": round(total_contributed, 2),
        "estimated_fees": round(total_fees, 2),
        "projected_end_value": round(val, 2),
        "yearly_curve": yearly_curve,
    }


def run_scenarios(
    current_value: float,
    available_cash: float,
    monthly_amount: float = 50.0,
    years: int = 5,
    fee_pct: float = 1.04,
) -> dict[str, Any]:
    """Bull / Base / Bear hypothetical scenario modeling."""
    return {
        "hypothetical_disclaimer": "ALL SCENARIOS ARE HYPOTHETICAL ESTIMATES — NOT GUARANTEED RETURNS.",
        "bull": simulate_contributions(current_value, available_cash, monthly_amount, "monthly", years, annual_cagr_pct=18.0, fee_pct=fee_pct, fx_drag_pct=0.0),
        "base": simulate_contributions(current_value, available_cash, monthly_amount, "monthly", years, annual_cagr_pct=10.0, fee_pct=fee_pct, fx_drag_pct=1.0),
        "bear": simulate_contributions(current_value, available_cash, monthly_amount, "monthly", years, annual_cagr_pct=2.0, fee_pct=fee_pct, fx_drag_pct=3.0),
    }


def analyze_allocation(panel_data: dict[str, Any], concentration_limit_pct: float = 25.0) -> dict[str, Any]:
    items = panel_data.get("items") or []
    inv_val = float(panel_data.get("total_value") or 0.0)
    cash_usd = float(panel_data.get("wallet_cash_usd") or 0.0)
    total_cap = inv_val + cash_usd

    by_exchange: dict[str, float] = {}
    by_currency: dict[str, float] = {}
    by_company: dict[str, float] = {}
    concentration_flags: list[dict[str, Any]] = []

    for it in items:
        sym = str(it.get("symbol") or "")
        val = float(it.get("value") or 0.0)
        cur = str(it.get("currency") or "USD")
        exch = "ZSE" if cur == "ZWG" else "VFEX"
        pct = round((val / total_cap) * 100.0, 2) if total_cap > 0 else 0.0
        by_exchange[exch] = round(by_exchange.get(exch, 0.0) + pct, 2)
        by_currency[cur] = round(by_currency.get(cur, 0.0) + pct, 2)
        by_company[sym] = pct
        if pct > concentration_limit_pct:
            concentration_flags.append({"symbol": sym, "allocation_pct": pct, "limit_pct": concentration_limit_pct})

    cash_pct = round((cash_usd / total_cap) * 100.0, 2) if total_cap > 0 else 100.0
    gaps = []
    if len(items) < 3:
        gaps.append("Fewer than 3 holdings — high idiosyncratic single-company risk.")
    if "VFEX" not in by_exchange and inv_val > 0:
        gaps.append("No USD-denominated VFEX exposure.")
    if cash_pct < 10.0 and total_cap > 0:
        gaps.append("Cash buffer below 10% — limited dry powder for pullbacks.")

    return {
        "total_capital_usd": round(total_cap, 2),
        "invested_pct": round(100.0 - cash_pct, 2),
        "cash_pct": cash_pct,
        "by_exchange_pct": by_exchange,
        "by_currency_pct": by_currency,
        "by_company_pct": by_company,
        "concentration_flags": concentration_flags,
        "diversification_gaps": gaps,
    }


def simulate_what_if(panel_data: dict[str, Any], scenario: dict[str, Any]) -> dict[str, Any]:
    """
    Non-destructive What-If Portfolio Simulator.
    Never modifies `panel_data`. Supports:
      - {"type": "invest_cash", "amount": 20.0}
      - {"type": "sell_holding", "symbol": "INFR", "pct": 100.0}
      - {"type": "price_shock", "symbol": "INFR", "shock_pct": -10.0}
    """
    sim_items = copy.deepcopy(panel_data.get("items") or [])
    sim_cash = float(panel_data.get("wallet_cash_usd") or 0.0)
    orig_val = float(panel_data.get("total_value") or 0.0)
    orig_total = orig_val + sim_cash

    stype = str(scenario.get("type") or "")
    note = ""
    if stype == "invest_cash":
        amt = float(scenario.get("amount") or 20.0)
        fee = round(amt * 0.0104, 2)
        orig_val += max(0.0, amt - fee)
        note = f"Hypothetically invested ${amt:.2f} (est. fee ${fee:.2f})."
    elif stype == "sell_holding":
        sym = str(scenario.get("symbol") or "").upper()
        pct = max(0.0, min(100.0, float(scenario.get("pct") or 100.0))) / 100.0
        for it in sim_items:
            if str(it.get("symbol") or "").upper() == sym:
                sold_val = float(it.get("value") or 0.0) * pct
                fee = round(sold_val * 0.0104, 2)
                it["value"] = round(float(it.get("value") or 0.0) - sold_val, 2)
                sim_cash += max(0.0, sold_val - fee)
                note = f"Hypothetically sold {pct*100:.0f}% of {sym} (net +${sold_val - fee:.2f} cash)."
        orig_val = sum(float(i.get("value") or 0.0) for i in sim_items)
    elif stype == "price_shock":
        sym = str(scenario.get("symbol") or "").upper()
        shock = float(scenario.get("shock_pct") or -10.0)
        for it in sim_items:
            if not sym or str(it.get("symbol") or "").upper() == sym:
                it["value"] = round(float(it.get("value") or 0.0) * (1.0 + shock / 100.0), 2)
        orig_val = sum(float(i.get("value") or 0.0) for i in sim_items)
        note = f"Hypothetical {shock:+.1f}% price shock on {sym or 'all holdings'}."

    new_total = round(orig_val + sim_cash, 2)
    return {
        "hypothetical": True,
        "scenario": scenario,
        "note": note,
        "before_total_usd": round(orig_total, 2),
        "after_total_usd": new_total,
        "delta_usd": round(new_total - orig_total, 2),
        "after_invested_usd": round(orig_val, 2),
        "after_cash_usd": round(sim_cash, 2),
    }


def compute_rebalancing(panel_data: dict[str, Any]) -> dict[str, Any]:
    """Compare current vs target allocations and compute fee- & liquidity-aware adjustments."""
    targets = panel_data.get("targets") or {}
    items = {str(i.get("symbol") or "").upper(): i for i in (panel_data.get("items") or [])}
    screener = {str(r.get("symbol") or "").upper(): r for r in (panel_data.get("screener") or [])}
    total_cap = float(panel_data.get("total_value") or 0.0) + float(panel_data.get("wallet_cash_usd") or 0.0)

    actions: list[dict[str, Any]] = []
    for sym, tgt_pct in targets.items():
        s = str(sym).upper()
        cur_val = float((items.get(s) or {}).get("value") or 0.0)
        cur_pct = round((cur_val / total_cap) * 100.0, 2) if total_cap > 0 else 0.0
        tgt_val = total_cap * (float(tgt_pct) / 100.0)
        diff_usd = round(tgt_val - cur_val, 2)
        row = screener.get(s) or {}
        fee_rate = 0.0218 if row.get("currency") == "ZWG" else 0.0104
        est_fee = round(abs(diff_usd) * fee_rate, 2)
        risks = []
        if row.get("wide_spread"):
            risks.append(f"Wide spread ({row.get('spread_pct', 0):.1f}%)")
        if float(row.get("liquidity_score") or 50) < 35:
            risks.append("Low liquidity")
        actions.append({
            "symbol": s,
            "current_pct": cur_pct,
            "target_pct": float(tgt_pct),
            "adjustment_usd": diff_usd,
            "action": "BUY" if diff_usd > 1.0 else ("TRIM" if diff_usd < -1.0 else "HOLD"),
            "estimated_cost_usd": est_fee,
            "risks": risks,
        })
    return {"total_capital_usd": round(total_cap, 2), "adjustments": actions}


def build_investment_calendar(panel_data: dict[str, Any]) -> list[dict[str, Any]]:
    today = date.today()
    events: list[dict[str, Any]] = []
    # Next planned monthly contribution (1st of next month)
    next_month = (today.replace(day=1) + timedelta(days=32)).replace(day=1)
    events.append({"date": next_month.isoformat(), "type": "CONTRIBUTION", "title": "Planned Monthly DCA Contribution"})
    # Next quarterly portfolio review
    q_review = today + timedelta(days=30)
    events.append({"date": q_review.isoformat(), "type": "REVIEW", "title": "Scheduled Portfolio Rebalancing & Risk Review"})
    # Recent official announcements / dividends from news
    for n in (panel_data.get("news") or [])[:12]:
        if n.get("official") or "dividend" in str(n.get("title") or "").lower():
            events.append({
                "date": str(n.get("date") or today.isoformat())[:10],
                "type": "DIVIDEND" if "dividend" in str(n.get("title") or "").lower() else "ANNOUNCEMENT",
                "title": str(n.get("title") or ""),
            })
    events.sort(key=lambda e: e["date"])
    return events[:12]


def build_planner_payload(panel_data: dict[str, Any], monthly_amount: float = 50.0, years: int = 5) -> dict[str, Any]:
    val = float(panel_data.get("total_value") or 0.0)
    cash = float(panel_data.get("wallet_cash_usd") or 0.0)
    presets = {
        f"${amt}": simulate_contributions(val, cash, amt, "monthly", years, 10.0, 1.04)["projected_end_value"]
        for amt in (5, 10, 25, 50, 100)
    }
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "allocation": analyze_allocation(panel_data),
        "contribution_presets_5y": presets,
        "scenarios": run_scenarios(val, cash, monthly_amount, years),
        "rebalancing": compute_rebalancing(panel_data),
        "what_if_examples": {
            "invest_20": simulate_what_if(panel_data, {"type": "invest_cash", "amount": 20.0}),
            "market_drop_10pct": simulate_what_if(panel_data, {"type": "price_shock", "shock_pct": -10.0}),
            "market_rise_20pct": simulate_what_if(panel_data, {"type": "price_shock", "shock_pct": 20.0}),
        },
        "calendar": build_investment_calendar(panel_data),
    }


def main() -> int:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import vfex
    store = vfex.VFEXStore()
    panel_data = vfex.format_panel_json(store)
    print(json.dumps(build_planner_payload(panel_data), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
