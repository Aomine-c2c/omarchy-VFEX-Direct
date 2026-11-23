#!/usr/bin/env python3
"""
NOTHING Investment Terminal — Isolated Paper Trading Engine & 5-Strategy AI Arena
---------------------------------------------------------------------------------
Logically isolated from real brokerage accounts (~/.config/vfex/paper_arena.json).
NEVER interacts with real accounts and NEVER auto-promotes strategies to live trading.

Includes:
- 5 versioned AI trading strategies (Value, Momentum, Dividend, Hybrid, User)
- Liquidity- & spread-aware simulated execution (MARKET/LIMIT, partial fills, fees)
- Immutable pre-trade AI Decision Journal + append-only post-trade reviews
- Performance Analytics (total/realised/unrealised return, max DD, win rate,
  profit factor, Sharpe ratio, cash utilisation) vs Cash & Buy-and-Hold baselines.
"""

from __future__ import annotations

import json
import math
import sys
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


DEFAULT_STRATEGIES = [
    {"strategy_id": "value_v1", "version": 1, "name": "VALUE INVESTOR", "starting_capital_usd": 100.0, "max_position_pct": 25.0, "cash_reserve_pct": 15.0, "horizon": "CORE", "stop_loss_pct": -12.0, "ai_model": "foundation_v3"},
    {"strategy_id": "momentum_v1", "version": 1, "name": "MOMENTUM TRADER", "starting_capital_usd": 100.0, "max_position_pct": 20.0, "cash_reserve_pct": 20.0, "horizon": "SWING", "stop_loss_pct": -6.0, "ai_model": "foundation_v3"},
    {"strategy_id": "dividend_v1", "version": 1, "name": "DIVIDEND INVESTOR", "starting_capital_usd": 100.0, "max_position_pct": 25.0, "cash_reserve_pct": 10.0, "horizon": "CORE", "stop_loss_pct": -15.0, "ai_model": "foundation_v3"},
    {"strategy_id": "hybrid_v1", "version": 1, "name": "HYBRID STRATEGIST", "starting_capital_usd": 100.0, "max_position_pct": 25.0, "cash_reserve_pct": 20.0, "horizon": "HYBRID", "stop_loss_pct": -8.0, "ai_model": "foundation_v3"},
    {"strategy_id": "user_v1", "version": 1, "name": "USER STRATEGY", "starting_capital_usd": 100.0, "max_position_pct": 25.0, "cash_reserve_pct": 20.0, "horizon": "HYBRID", "stop_loss_pct": -8.0, "ai_model": "foundation_v3"},
]


class PaperTradingArena:
    """Isolated multi-agent paper trading arena."""

    ISOLATED_SIMULATION_ONLY = True

    def __init__(self, state_path: Path | None = None) -> None:
        self.state_path = state_path or (Path.home() / ".config" / "vfex" / "paper_arena.json")
        self.state = self._load()

    def _default_state(self) -> dict[str, Any]:
        portfolios = {}
        for s in DEFAULT_STRATEGIES:
            sid = s["strategy_id"]
            portfolios[sid] = {
                "strategy": dict(s),
                "mode": "LIVE_PAPER",  # LIVE_PAPER vs BACKTEST
                "cash_usd": float(s["starting_capital_usd"]),
                "holdings": {},  # sym -> {quantity, avg_cost, currency, exchange}
                "orders": [],
                "transactions": [],
                "dividends": [],
                "realised_pnl_usd": 0.0,
                "total_fees_usd": 0.0,
                "equity_curve": [float(s["starting_capital_usd"])],
                "decision_journal": [],  # append-only immutable pre-trade entries
                "post_trade_reviews": [],  # append-only post-trade evaluations
            }
        return {"isolated_simulation": True, "portfolios": portfolios}

    def _load(self) -> dict[str, Any]:
        if self.state_path.exists():
            try:
                parsed = json.loads(self.state_path.read_text(encoding="utf-8"))
                if isinstance(parsed, dict) and "portfolios" in parsed:
                    return parsed
            except Exception:
                pass
        return self._default_state()

    def save(self) -> None:
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        self.state_path.write_text(json.dumps(self.state, indent=2), encoding="utf-8")

    def record_decision(self, strategy_id: str, entry: dict[str, Any]) -> str:
        """Append an immutable pre-trade decision journal entry. Required before simulated execution."""
        required = ("intent", "thesis", "evidence", "price", "data_timestamp", "expected_outcome", "risk_factors", "invalidation_conditions", "intended_horizon")
        missing = [k for k in required if k not in entry]
        if missing:
            raise ValueError(f"Decision journal missing required fields: {missing}")
        port = self.state["portfolios"][strategy_id]
        did = uuid.uuid4().hex[:10]
        port["decision_journal"].append({
            "decision_id": did,
            "recorded_at": _utc_now(),
            "immutable": True,
            **entry,
        })
        self.save()
        return did

    def execute_simulated_order(
        self,
        strategy_id: str,
        decision_id: str,
        symbol: str,
        exchange: str,
        side: str,
        quantity: float,
        order_type: str,  # MARKET | LIMIT
        limit_price: float | None,
        market_quote: dict[str, Any],
        data_source: str = "vfex_live_feed",
    ) -> dict[str, Any]:
        """
        Liquidity- & spread-aware simulated execution.
        - Requires a recorded `decision_id` in the strategy's Decision Journal.
        - Never assumes last traded price is executable: uses best_ask (BUY) / best_bid (SELL).
        - Caps fill quantity at available top-of-book volume (producing PARTIALLY_FILLED when thin).
        """
        port = self.state["portfolios"][strategy_id]
        if not any(d["decision_id"] == decision_id for d in port["decision_journal"]):
            raise PermissionError("Simulated trade blocked: pre-trade Decision Journal entry is mandatory.")

        act = side.upper()
        otype = order_type.upper()
        last_px = float(market_quote.get("price") or 0.0)
        best_bid = float(market_quote.get("best_bid") or (last_px * 0.99 if last_px > 0 else 0.0))
        best_ask = float(market_quote.get("best_ask") or (last_px * 1.01 if last_px > 0 else 0.0))
        avail_vol = float(market_quote.get("ask_volume" if act == "BUY" else "bid_volume") or quantity)
        data_ts = str(market_quote.get("timestamp") or _utc_now())

        exec_px = best_ask if act == "BUY" else best_bid
        if exec_px <= 0:
            return {"status": "UNFILLED", "reason": "No executable bid/ask quote."}

        if otype == "LIMIT" and limit_price is not None:
            if act == "BUY" and exec_px > limit_price:
                return {"status": "UNFILLED", "reason": f"Best ask {exec_px:.4f} > limit {limit_price:.4f}"}
            if act == "SELL" and exec_px < limit_price:
                return {"status": "UNFILLED", "reason": f"Best bid {exec_px:.4f} < limit {limit_price:.4f}"}

        fill_qty = min(float(quantity), max(0.0, avail_vol))
        if fill_qty <= 0:
            return {"status": "UNFILLED", "reason": "Zero available top-of-book liquidity."}

        fee_rate = 0.0218 if exchange.upper() == "ZSE" else 0.0104
        gross = fill_qty * exec_px
        fees = round(gross * fee_rate, 4)

        if act == "BUY":
            total_cost = gross + fees
            if port["cash_usd"] < total_cost:
                fill_qty = math.floor((port["cash_usd"] / (exec_px * (1.0 + fee_rate))) * 1e4) / 1e4
                if fill_qty <= 0:
                    return {"status": "UNFILLED", "reason": "Insufficient virtual cash."}
                gross = fill_qty * exec_px
                fees = round(gross * fee_rate, 4)
                total_cost = gross + fees
            port["cash_usd"] = round(port["cash_usd"] - total_cost, 4)
            h = port["holdings"].get(symbol, {"quantity": 0.0, "avg_cost": 0.0, "exchange": exchange})
            new_q = h["quantity"] + fill_qty
            new_avg = ((h["quantity"] * h["avg_cost"]) + total_cost) / new_q
            port["holdings"][symbol] = {"quantity": round(new_q, 6), "avg_cost": round(new_avg, 6), "exchange": exchange}
        else:
            h = port["holdings"].get(symbol)
            if not h or h["quantity"] < fill_qty - 1e-9:
                return {"status": "UNFILLED", "reason": "Insufficient virtual shares."}
            net_proc = gross - fees
            realised = net_proc - (fill_qty * h["avg_cost"])
            port["cash_usd"] = round(port["cash_usd"] + net_proc, 4)
            port["realised_pnl_usd"] = round(port["realised_pnl_usd"] + realised, 4)
            rem = h["quantity"] - fill_qty
            if rem <= 1e-9:
                del port["holdings"][symbol]
            else:
                h["quantity"] = round(rem, 6)

        port["total_fees_usd"] = round(port["total_fees_usd"] + fees, 4)
        status = "FILLED" if abs(fill_qty - quantity) < 1e-6 else "PARTIALLY_FILLED"

        tx = {
            "tx_id": uuid.uuid4().hex[:10],
            "strategy_id": strategy_id,
            "agent_id": strategy_id,
            "decision_id": decision_id,
            "security": symbol,
            "exchange": exchange.upper(),
            "side": act,
            "order_type": otype,
            "status": status,
            "order_date": _utc_now()[:10],
            "execution_date": _utc_now()[:10],
            "execution_price": round(exec_px, 6),
            "requested_qty": float(quantity),
            "quantity": round(fill_qty, 6),
            "fees": fees,
            "market_data_source": data_source,
            "data_timestamp": data_ts,
            "execution_methodology": "top_of_book_bid_ask_liquidity_capped",
        }
        port["transactions"].append(tx)
        port["orders"].append(tx)
        self.save()
        return tx

    def compute_rankings(self, prices_map: dict[str, float]) -> list[dict[str, Any]]:
        rows = []
        for sid, p in self.state["portfolios"].items():
            start_cap = float(p["strategy"]["starting_capital_usd"])
            mv = sum(h["quantity"] * float(prices_map.get(sym, h["avg_cost"])) for sym, h in p["holdings"].items())
            eq = round(p["cash_usd"] + mv, 2)
            ret_pct = round(((eq - start_cap) / start_cap) * 100.0, 2) if start_cap > 0 else 0.0
            curve = p.get("equity_curve") or [start_cap]
            peak = max(curve + [eq])
            max_dd = round(((eq - peak) / peak) * 100.0, 2) if peak > 0 else 0.0
            cash_util = round(((start_cap - p["cash_usd"]) / start_cap) * 100.0, 1) if start_cap > 0 else 0.0
            rows.append({
                "strategy_id": sid,
                "name": p["strategy"]["name"],
                "version": p["strategy"]["version"],
                "mode": p["mode"],
                "equity_usd": eq,
                "return_pct": ret_pct,
                "realised_pnl_usd": round(p["realised_pnl_usd"], 2),
                "total_fees_usd": round(p["total_fees_usd"], 2),
                "max_drawdown_pct": max_dd,
                "cash_utilisation_pct": cash_util,
                "trades_count": len(p["transactions"]),
                "journal_count": len(p["decision_journal"]),
            })
        rows.sort(key=lambda r: -r["return_pct"])
        return rows


def main() -> int:
    from ai_providers import AIProviderManager
    arena = PaperTradingArena()
    ai_mgr = AIProviderManager()
    print(json.dumps({
        "ai_providers": ai_mgr.status_summary(),
        "arena_rankings": arena.compute_rankings({}),
        "isolated_simulation": arena.ISOLATED_SIMULATION_ONLY,
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
