#!/usr/bin/env python3
"""
NOTHING Investment Terminal — Deterministic Decimal-Safe Paper Trading Engine
-----------------------------------------------------------------------------
Strictly isolated simulation engine for VFEX, C-TRADE, and ZSE.
Uses `decimal.Decimal` for all monetary arithmetic.
Never interacts with real brokerage accounts, real balances, or real orders.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

Q2 = Decimal("0.01")
Q4 = Decimal("0.0001")
Q6 = Decimal("0.000001")


def _d(val: Any) -> Decimal:
    return Decimal(str(val))


def _q2(val: Decimal) -> Decimal:
    return val.quantize(Q2, rounding=ROUND_HALF_UP)


def _q4(val: Decimal) -> Decimal:
    return val.quantize(Q4, rounding=ROUND_HALF_UP)


@dataclass(frozen=True)
class FeeSchedule:
    exchange: str
    brokerage: str
    side: str  # BUY | SELL
    rate_pct: Decimal
    min_fee: Decimal = Decimal("0.00")
    is_verified_schedule: bool = False  # Explicitly distinguishes verified vs assumed rates
    notes: str = "Configurable simulation fee schedule"

    def compute(self, gross: Decimal) -> Decimal:
        raw = gross * (self.rate_pct / Decimal("100"))
        fee = max(self.min_fee, raw) if gross > 0 else Decimal("0.00")
        return _q2(fee)


@dataclass
class VirtualPortfolio:
    portfolio_id: str
    starting_capital: Decimal
    currency: str = "USD"
    max_position_pct: Decimal = Decimal("25.0")
    min_cash_reserve_pct: Decimal = Decimal("10.0")
    available_cash: Decimal = field(init=False)
    holdings: dict[str, dict[str, Decimal]] = field(default_factory=dict)  # sec_id -> {qty, avg_cost}
    pending_orders: list[dict[str, Any]] = field(default_factory=list)
    executed_orders: list[dict[str, Any]] = field(default_factory=list)
    cancelled_orders: list[dict[str, Any]] = field(default_factory=list)
    dividends: list[dict[str, Any]] = field(default_factory=list)
    realised_pnl: Decimal = Decimal("0.00")
    total_fees: Decimal = Decimal("0.00")
    equity_history: list[dict[str, Any]] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.available_cash = _q2(self.starting_capital)


class DeterministicPaperEngine:
    """Decimal-safe, deterministic, strictly isolated paper trading engine."""

    ISOLATED_SIMULATION_NAMESPACE = "paper_engine_isolated"

    def __init__(self) -> None:
        self.portfolios: dict[str, VirtualPortfolio] = {}
        self.fee_schedules: dict[tuple[str, str, str], FeeSchedule] = {
            ("VFEX", "DEFAULT", "BUY"): FeeSchedule("VFEX", "DEFAULT", "BUY", Decimal("1.04"), Decimal("0.01"), False),
            ("VFEX", "DEFAULT", "SELL"): FeeSchedule("VFEX", "DEFAULT", "SELL", Decimal("1.04"), Decimal("0.01"), False),
            ("ZSE", "DEFAULT", "BUY"): FeeSchedule("ZSE", "DEFAULT", "BUY", Decimal("2.18"), Decimal("0.01"), False),
            ("ZSE", "DEFAULT", "SELL"): FeeSchedule("ZSE", "DEFAULT", "SELL", Decimal("3.18"), Decimal("0.01"), False),
            ("CTRADE", "DEFAULT", "BUY"): FeeSchedule("CTRADE", "DEFAULT", "BUY", Decimal("1.04"), Decimal("0.01"), False),
            ("CTRADE", "DEFAULT", "SELL"): FeeSchedule("CTRADE", "DEFAULT", "SELL", Decimal("1.04"), Decimal("0.01"), False),
        }

    def set_fee_schedule(self, sched: FeeSchedule) -> None:
        key = (sched.exchange.upper(), sched.brokerage.upper(), sched.side.upper())
        self.fee_schedules[key] = sched

    def create_portfolio(self, portfolio_id: str, starting_capital: str | float | Decimal, currency: str = "USD", max_position_pct: str = "25.0", min_cash_reserve_pct: str = "10.0") -> VirtualPortfolio:
        vp = VirtualPortfolio(
            portfolio_id=portfolio_id,
            starting_capital=_d(starting_capital),
            currency=currency.upper(),
            max_position_pct=_d(max_position_pct),
            min_cash_reserve_pct=_d(min_cash_reserve_pct),
        )
        self.portfolios[portfolio_id] = vp
        return vp

    def submit_order(
        self,
        portfolio_id: str,
        agent_id: str,
        strategy_version: str,
        exchange: str,
        security: str,
        side: str,
        order_type: str,  # MARKET | LIMIT
        quantity: str | float | Decimal,
        quote: dict[str, Any],
        limit_price: str | float | Decimal | None = None,
        brokerage: str = "DEFAULT",
        market_open: bool = True,
        max_quote_age_sec: int = 900,
    ) -> dict[str, Any]:
        vp = self.portfolios[portfolio_id]
        ex = exchange.upper()
        act = side.upper()
        otype = order_type.upper()
        qty = _d(quantity)
        now = datetime.now(timezone.utc)
        decision_ts = now.isoformat()
        quote_ts = str(quote.get("timestamp") or decision_ts)

        def _reject(reason: str) -> dict[str, Any]:
            return {"status": "REJECTED", "reason": reason, "agent_id": agent_id, "strategy_version": strategy_version, "security": security, "exchange": ex}

        # 1. Quantity & market status validation
        if qty <= 0:
            return _reject("Order quantity must be positive.")
        if not market_open:
            return _reject(f"Market {ex} is closed.")

        # 2. Price freshness validation
        try:
            q_dt = datetime.fromisoformat(quote_ts.replace("Z", "+00:00"))
            if (now - q_dt).total_seconds() > max_quote_age_sec:
                return _reject(f"Stale market quote ({quote_ts}).")
        except Exception:
            pass

        # 3. Determine execution price & liquidity WITHOUT inventing order-book depth
        assumptions: list[str] = []
        ref_px = _d(quote.get("price") or 0)
        if act == "BUY" and quote.get("best_ask") is not None:
            exec_px = _d(quote["best_ask"])
            avail_qty = _d(quote["ask_volume"]) if quote.get("ask_volume") is not None else qty
            assumptions.append("EXECUTED_AT_VERIFIED_BEST_ASK")
        elif act == "SELL" and quote.get("best_bid") is not None:
            exec_px = _d(quote["best_bid"])
            avail_qty = _d(quote["bid_volume"]) if quote.get("bid_volume") is not None else qty
            assumptions.append("EXECUTED_AT_VERIFIED_BEST_BID")
        elif ref_px > 0:
            slip = Decimal("1.005") if act == "BUY" else Decimal("0.995")
            exec_px = _q4(ref_px * slip)
            avail_qty = qty
            assumptions.append("LAST_PRICE_WITH_0.5PCT_ASSUMED_SLIPPAGE_NO_ORDERBOOK")
        else:
            return _reject("No valid market price available.")

        # 4. Limit price check -> unfilled stays PENDING
        if otype == "LIMIT":
            if limit_price is None:
                return _reject("Limit order requires limit_price.")
            lpx = _d(limit_price)
            if (act == "BUY" and exec_px > lpx) or (act == "SELL" and exec_px < lpx):
                pending = {
                    "order_id": uuid.uuid4().hex[:10],
                    "status": "PENDING",
                    "agent_id": agent_id,
                    "strategy_version": strategy_version,
                    "decision_timestamp": decision_ts,
                    "market_data_timestamp": quote_ts,
                    "security": security,
                    "exchange": ex,
                    "side": act,
                    "order_type": otype,
                    "order_quantity": str(qty),
                    "limit_price": str(lpx),
                    "fill_quantity": "0",
                    "remaining_quantity": str(qty),
                    "execution_assumptions": assumptions,
                }
                vp.pending_orders.append(pending)
                return pending

        fill_qty = min(qty, avail_qty)
        if fill_qty <= 0:
            return _reject("Zero available liquidity at top of book.")

        sched = self.fee_schedules.get((ex, brokerage.upper(), act)) or FeeSchedule(ex, brokerage, act, Decimal("1.04"))
        gross = fill_qty * exec_px
        fee = sched.compute(gross)
        sec_key = f"{ex}:{security.upper()}"

        # 5. Cash, position limit, and cash reserve checks
        if act == "BUY":
            total_cost = _q2(gross + fee)
            if vp.available_cash < total_cost:
                return _reject(f"Insufficient virtual cash: need {total_cost}, have {vp.available_cash}.")
            min_reserve = _q2(vp.starting_capital * (vp.min_cash_reserve_pct / Decimal("100")))
            if (vp.available_cash - total_cost) < min_reserve:
                return _reject(f"Breaches minimum cash reserve ({vp.min_cash_reserve_pct}%).")
            cur_val = vp.holdings[sec_key]["qty"] * exec_px if sec_key in vp.holdings else Decimal("0")
            max_pos = vp.starting_capital * (vp.max_position_pct / Decimal("100"))
            if (cur_val + gross) > max_pos:
                return _reject(f"Breaches max position limit ({vp.max_position_pct}%).")

            vp.available_cash = _q2(vp.available_cash - total_cost)
            h = vp.holdings.get(sec_key, {"qty": Decimal("0"), "avg_cost": Decimal("0")})
            new_q = h["qty"] + fill_qty
            new_avg = _q4(((h["qty"] * h["avg_cost"]) + total_cost) / new_q)
            vp.holdings[sec_key] = {"qty": new_q, "avg_cost": new_avg}
        else:
            h = vp.holdings.get(sec_key)
            if not h or h["qty"] < fill_qty:
                return _reject(f"Insufficient virtual shares of {sec_key}.")
            net_proc = _q2(gross - fee)
            realised = _q2(net_proc - (fill_qty * h["avg_cost"]))
            vp.available_cash = _q2(vp.available_cash + net_proc)
            vp.realised_pnl = _q2(vp.realised_pnl + realised)
            rem_h = h["qty"] - fill_qty
            if rem_h <= Decimal("0"):
                del vp.holdings[sec_key]
            else:
                h["qty"] = rem_h

        vp.total_fees = _q2(vp.total_fees + fee)
        rem_order = qty - fill_qty
        status = "FILLED" if rem_order == Decimal("0") else "PARTIALLY_FILLED"

        record = {
            "order_id": uuid.uuid4().hex[:10],
            "status": status,
            "agent_id": agent_id,
            "strategy_version": strategy_version,
            "decision_timestamp": decision_ts,
            "market_data_timestamp": quote_ts,
            "security": security.upper(),
            "exchange": ex,
            "side": act,
            "order_type": otype,
            "order_quantity": str(qty),
            "reference_price": str(ref_px),
            "execution_price": str(exec_px),
            "fees": str(fee),
            "fee_verified": sched.is_verified_schedule,
            "fill_quantity": str(fill_qty),
            "remaining_quantity": str(rem_order),
            "execution_assumptions": assumptions,
        }
        vp.executed_orders.append(record)
        return record

    def cancel_pending_order(self, portfolio_id: str, order_id: str) -> dict[str, Any]:
        vp = self.portfolios[portfolio_id]
        for idx, o in enumerate(vp.pending_orders):
            if o["order_id"] == order_id:
                cancelled = vp.pending_orders.pop(idx)
                cancelled["status"] = "CANCELLED"
                vp.cancelled_orders.append(cancelled)
                return cancelled
        raise KeyError(f"Pending order {order_id} not found.")

    def record_dividend(self, portfolio_id: str, security: str, amount: str | float | Decimal) -> None:
        vp = self.portfolios[portfolio_id]
        amt = _q2(_d(amount))
        vp.available_cash = _q2(vp.available_cash + amt)
        vp.dividends.append({"security": security, "amount": str(amt), "timestamp": datetime.now(timezone.utc).isoformat()})

    def mark_to_market(self, portfolio_id: str, prices: dict[str, str | float | Decimal]) -> dict[str, Any]:
        vp = self.portfolios[portfolio_id]
        mv = Decimal("0.00")
        cost = Decimal("0.00")
        for sec_key, h in vp.holdings.items():
            px = _d(prices.get(sec_key, h["avg_cost"]))
            mv += h["qty"] * px
            cost += h["qty"] * h["avg_cost"]
        unr = _q2(mv - cost)
        eq = _q2(vp.available_cash + mv)
        snap = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "available_cash": str(vp.available_cash),
            "market_value": str(_q2(mv)),
            "total_equity": str(eq),
            "realised_pnl": str(vp.realised_pnl),
            "unrealised_pnl": str(unr),
            "total_fees": str(vp.total_fees),
        }
        vp.equity_history.append(snap)
        return snap
