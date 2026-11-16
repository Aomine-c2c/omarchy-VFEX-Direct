#!/usr/bin/env python3
"""omarchy-VFEX-Direct: Victoria Falls Stock Exchange (VFEX) CLI & Waybar tracker."""

from __future__ import annotations

import argparse
import csv
import http.cookiejar
import io
import json
import os
import stat
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

DEFAULT_CONFIG_DIR = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "vfex-direct"

VFEX_DIRECT_API_BASE = "https://d3u8q0mxu6epjj.cloudfront.net/api/v1"
ZSE_DIRECT_API_BASE = "https://d17zh5y0djjrt1.cloudfront.net/api/v1"
VFEX_DIRECT_URL = f"{VFEX_DIRECT_API_BASE}/voms/price-sheets/active"
CTRADE_BASE_URL = "https://ctradenew.ctrade.co.zw"
CTRADE_VFEX_URL = f"{CTRADE_BASE_URL}/api/web-proxy/online.ctrade_php/marketwatchvx.php"
CTRADE_ZSE_URL = f"{CTRADE_BASE_URL}/api/mobile-proxy/marketwatchzsenew"

VOMS_PROVIDERS: dict[str, dict[str, Any]] = {
    "vfex_direct": {"base_url": VFEX_DIRECT_API_BASE, "currency": "USD", "strip_vx": True, "label": "VFEX-D", "title": "VFEX Direct"},
    "zse_direct": {"base_url": ZSE_DIRECT_API_BASE, "currency": "ZWG", "strip_vx": False, "label": "ZSE-D", "title": "ZSE Direct"},
}
PORTAL_LABELS: dict[str, str] = {"ctrade": "C-TRADE", "vfex_direct": "VFEX-D", "zse_direct": "ZSE-D"}

# Common VFEX listed equities (USD-denominated)
KNOWN_VFEX_SYMBOLS: dict[str, str] = {
    "ASUN": "African Sun Limited",
    "AXIA": "Axia Corporation Limited",
    "BIND": "Bindura Nickel Corporation",
    "CALD": "Caledonia Mining Corporation",
    "CMCL": "Caledonia Mining Corporation",
    "EAGLE": "Eagle REIT",
    "EDGR": "Edgars Stores Limited",
    "FCA": "First Capital Bank Limited",
    "INFR": "Econet Infrastructure Company Limited (InfraCo)",
    "INSC": "Innscor Africa Limited",
    "NTFD": "National Foods Holdings Limited",
    "PHL": "Padenga Holdings Limited",
    "SCIL": "Seed Co International Limited",
    "SIM": "Simbisa Brands Limited",
    "WTN": "WestProp Holdings Limited",
    "ZIMW": "Zimplow Holdings Limited",
}


def infer_currency(symbol: str, entry: dict[str, Any] | None = None) -> str:
    """Return 'ZWG' for ZSE '.ZW' tickers or ZWG-tagged entries, else 'USD'."""
    if entry and entry.get("currency") in ("USD", "ZWG"):
        return str(entry["currency"])
    return "ZWG" if symbol.upper().endswith(".ZW") else "USD"


def format_money(amount: float, currency: str = "USD", decimals: int = 2) -> str:
    """Format a monetary value in USD ($) or ZWG (ZiG)."""
    prefix = "ZiG " if currency == "ZWG" else "$"
    return f"{prefix}{amount:.{decimals}f}"


def _safe_float(val: Any) -> float | None:
    if val is None:
        return None
    s = str(val).strip().replace(",", "")
    if not s:
        return None
    try:
        return float(s)
    except ValueError:
        return None


def _safe_int(val: Any) -> int | None:
    f = _safe_float(val)
    return int(round(f)) if f is not None else None


def compute_xirr(cashflows: list[tuple[datetime, float]]) -> float | None:
    """Compute annualized XIRR percentage for dated cashflows (neg=outflow, pos=inflow)."""
    if len(cashflows) < 2:
        return None
    ordered = sorted(cashflows, key=lambda c: c[0])
    d0 = ordered[0][0]
    span_days = (ordered[-1][0] - d0).days
    if span_days < 7:
        return None
    if not (any(amt < 0 for _, amt in ordered) and any(amt > 0 for _, amt in ordered)):
        return None

    years = [(d - d0).days / 365.0 for d, _ in ordered]
    amts = [float(a) for _, a in ordered]

    def npv(rate: float) -> float:
        return sum(a / ((1.0 + rate) ** t) for t, a in zip(years, amts))

    lo, hi = -0.95, 10.0
    f_lo, f_hi = npv(lo), npv(hi)
    if f_lo * f_hi > 0:
        return None
    for _ in range(60):
        mid = (lo + hi) / 2.0
        f_mid = npv(mid)
        if abs(f_mid) < 1e-6:
            lo = hi = mid
            break
        if f_lo * f_mid <= 0:
            hi, f_hi = mid, f_mid
        else:
            lo, f_lo = mid, f_mid
    return round(((lo + hi) / 2.0) * 100.0, 1)


def compute_symbol_technicals(hist: list[dict[str, Any]], cur: float) -> dict[str, Any]:
    """Compute 20D/30D averages, rolling MA series, Z-score, and RSI-14 from candle history."""
    closes = [float(h.get("close", h.get("price", 0.0))) for h in hist if float(h.get("close", h.get("price", 0.0))) > 0]
    if not closes and cur > 0:
        closes = [cur]
    avg30 = sum(closes) / len(closes) if closes else cur
    drop30 = ((avg30 - cur) / avg30 * 100.0) if avg30 > 0 else 0.0

    ma_window = closes[-20:] if len(closes) >= 20 else closes
    ma20 = round(sum(ma_window) / len(ma_window), 4) if ma_window else None
    ma20_series: list[float] = []
    for idx in range(len(closes)):
        win = closes[max(0, idx - 19): idx + 1]
        ma20_series.append(round(sum(win) / len(win), 4))

    z_score = None
    if len(closes) >= 5 and ma20 is not None:
        mean = sum(ma_window) / len(ma_window)
        var = sum((x - mean) ** 2 for x in ma_window) / len(ma_window)
        std = var ** 0.5
        if std > 1e-9:
            z_score = round((cur - mean) / std, 2)

    rsi14 = None
    if len(closes) >= 4:
        deltas = [closes[i] - closes[i - 1] for i in range(1, len(closes))][-14:]
        gains = sum(d for d in deltas if d > 0) / len(deltas)
        losses = sum(-d for d in deltas if d < 0) / len(deltas)
        if losses <= 1e-9:
            rsi14 = 100.0 if gains > 0 else 50.0
        else:
            rs = gains / losses
            rsi14 = round(100.0 - (100.0 / (1.0 + rs)), 1)

    return {
        "avg30": round(avg30, 4),
        "drop30": round(drop30, 2),
        "ma20": ma20,
        "ma20_series": ma20_series,
        "z_score": z_score,
        "rsi14": rsi14,
    }


def compute_smart_limit(
    price: float,
    bid: float | None,
    ask: float | None,
    bid_vol: int | None,
    ask_vol: int | None,
    action: str = "BUY",
) -> dict[str, Any]:
    """Compute spread %, liquidity score (0-100), and optimal passive limit price."""
    b = float(bid or 0.0)
    a = float(ask or 0.0)
    bv = int(bid_vol or 0)
    av = int(ask_vol or 0)
    mid = (b + a) / 2.0 if (b > 0 and a > 0) else price
    spread_pct = round(((a - b) / mid * 100.0), 2) if (b > 0 and a > b and mid > 0) else None
    wide_spread = spread_pct is not None and spread_pct > 5.0

    # Liquidity score combines resting top-of-book depth and spread tightness
    liq = 0
    if bv > 0 and av > 0:
        liq += 40
    elif bv > 0 or av > 0:
        liq += 20
    total_vol = bv + av
    if total_vol >= 5000:
        liq += 35
    elif total_vol >= 500:
        liq += 25
    elif total_vol >= 50:
        liq += 15
    if spread_pct is not None:
        if spread_pct <= 2.0:
            liq += 25
        elif spread_pct <= 5.0:
            liq += 15
        elif spread_pct <= 12.0:
            liq += 5

    if action == "SELL":
        if a > b > 0 and spread_pct and spread_pct > 2.0:
            optimal = round(a - max(0.0005, (a - b) * 0.25), 4)
        else:
            optimal = round(b if b > 0 else price, 4)
    else:
        if a > b > 0 and spread_pct and spread_pct > 2.0:
            optimal = round(b + max(0.0005, (a - b) * 0.25), 4)
        else:
            optimal = round(a if a > 0 else price, 4)

    return {
        "spread_pct": spread_pct,
        "wide_spread": wide_spread,
        "liquidity_score": min(100, liq),
        "optimal_limit": optimal,
    }


class VFEXStore:
    """Manages persistent state for portfolio, watchlist, prices, and alerts."""

    def __init__(self, config_dir: Path | None = None) -> None:
        self.config_dir = config_dir or DEFAULT_CONFIG_DIR
        self.config_dir.mkdir(parents=True, exist_ok=True)
        self.state_file = self.config_dir / "state.json"
        self.state: dict[str, Any] = self._load()

    def _load(self) -> dict[str, Any]:
        if self.state_file.exists():
            try:
                return json.loads(self.state_file.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                pass
        return {
            "watchlist": ["INSC", "SIM", "PHL"],
            "prices": {},
            "history": {},
            "portfolio": {},
            "alerts": [],
            "targets": {},
            "trades": [],
            "realized_pnl": 0.0,
            "dividends": [],
        }

    def save(self) -> None:
        self.state_file.write_text(json.dumps(self.state, indent=2) + "\n", encoding="utf-8")

    def set_price(
        self,
        symbol: str,
        price: float,
        source: str = "manual",
        open_price: float | None = None,
        change_pct: float | None = None,
        date: str | None = None,
        best_bid: float | None = None,
        best_ask: float | None = None,
        bid_volume: int | None = None,
        ask_volume: int | None = None,
        currency: str | None = None,
        company_name: str | None = None,
        track_history: bool = True,
        save: bool = True,
    ) -> None:
        sym = symbol.upper()
        now = datetime.now(timezone.utc)
        today = date or now.date().isoformat()
        prev_entry = self.state["prices"].get(sym, {})
        cur_code = currency or infer_currency(sym, prev_entry)
        price_entry: dict[str, Any] = {
            "price": round(price, 4),
            "source": source,
            "currency": cur_code,
            "updated_at": now.isoformat(),
        }
        if open_price is not None:
            price_entry["open"] = round(float(open_price), 4)
        if change_pct is not None:
            price_entry["change_pct"] = round(float(change_pct), 2)

        self._apply_depth_fields(
            price_entry,
            best_bid=best_bid if best_bid is not None else prev_entry.get("best_bid"),
            best_ask=best_ask if best_ask is not None else prev_entry.get("best_ask"),
            bid_volume=bid_volume if bid_volume is not None else prev_entry.get("bid_volume"),
            ask_volume=ask_volume if ask_volume is not None else prev_entry.get("ask_volume"),
            currency=cur_code,
            company_name=company_name or prev_entry.get("company_name"),
        )
        self.state["prices"][sym] = price_entry

        if track_history:
            open_val = float(open_price) if open_price is not None else float(price)
            history = self.state.setdefault("history", {}).setdefault(sym, [])
            if history and history[-1].get("date") == today:
                cur = history[-1]
                cur_open = float(open_price) if open_price is not None else float(cur.get("open", cur.get("price", price)))
                cur_high = max(float(cur.get("high", cur.get("price", price))), float(price), cur_open)
                cur_low = min(float(cur.get("low", cur.get("price", price))), float(price), cur_open)
                cur["open"] = round(cur_open, 4)
                cur["high"] = round(cur_high, 4)
                cur["low"] = round(cur_low, 4)
                cur["close"] = round(price, 4)
                cur["price"] = round(price, 4)
            else:
                history.append({
                    "date": today,
                    "open": round(open_val, 4),
                    "high": round(max(open_val, price), 4),
                    "low": round(min(open_val, price), 4),
                    "close": round(price, 4),
                    "price": round(price, 4),
                })
                if len(history) > 30:
                    self.state["history"][sym] = history[-30:]
        if save:
            self.save()

    @staticmethod
    def _apply_depth_fields(
        entry: dict[str, Any],
        best_bid: float | None = None,
        best_ask: float | None = None,
        bid_volume: int | None = None,
        ask_volume: int | None = None,
        currency: str | None = None,
        company_name: str | None = None,
    ) -> None:
        if currency:
            entry["currency"] = currency
        if company_name:
            entry["company_name"] = str(company_name).strip()
        if best_bid is not None and float(best_bid) > 0:
            entry["best_bid"] = round(float(best_bid), 4)
        if best_ask is not None and float(best_ask) > 0:
            entry["best_ask"] = round(float(best_ask), 4)
        if bid_volume is not None and int(bid_volume) >= 0:
            entry["bid_volume"] = int(bid_volume)
        if ask_volume is not None and int(ask_volume) >= 0:
            entry["ask_volume"] = int(ask_volume)
        if "best_bid" in entry and "best_ask" in entry:
            entry["spread"] = round(float(entry["best_ask"]) - float(entry["best_bid"]), 4)

    def attach_depth(
        self,
        symbol: str,
        best_bid: float | None = None,
        best_ask: float | None = None,
        bid_volume: int | None = None,
        ask_volume: int | None = None,
        currency: str | None = None,
        company_name: str | None = None,
    ) -> None:
        """Attach bid/ask depth metadata to an existing price entry without altering its price."""
        entry = self.state["prices"].get(symbol.upper())
        if entry:
            self._apply_depth_fields(entry, best_bid, best_ask, bid_volume, ask_volume, currency, company_name)

    def get_price_entry(self, symbol: str) -> dict[str, Any]:
        return self.state.get("prices", {}).get(symbol.upper(), {})

    def get_price(self, symbol: str) -> float | None:
        entry = self.state["prices"].get(symbol.upper())
        return float(entry["price"]) if entry else None

    def get_daily_change(self, symbol: str) -> float | None:
        """Return API percentage change if recorded, else % change between the last two history points."""
        entry = self.state.get("prices", {}).get(symbol.upper(), {})
        if entry.get("change_pct") is not None:
            return round(float(entry["change_pct"]), 2)
        hist = self.state.get("history", {}).get(symbol.upper(), [])
        if len(hist) < 2:
            return None
        prev = float(hist[-2].get("close", hist[-2].get("price", 0.0)))
        cur = float(hist[-1].get("close", hist[-1].get("price", 0.0)))
        if prev <= 0:
            return None
        return round(((cur - prev) / prev) * 100.0, 2)

    def get_candles(self, symbol: str) -> list[dict[str, Any]]:
        """Return normalized 30-day OHLC candle dicts for a symbol."""
        candles = []
        for h in self.state.get("history", {}).get(symbol.upper(), []):
            close_p = float(h.get("close", h.get("price", 0.0)))
            open_p = float(h.get("open", close_p))
            high_p = float(h.get("high", max(open_p, close_p)))
            low_p = float(h.get("low", min(open_p, close_p)))
            candles.append({
                "date": h.get("date", ""),
                "open": round(open_p, 4),
                "high": round(high_p, 4),
                "low": round(low_p, 4),
                "close": round(close_p, 4),
            })
        return candles

    @staticmethod
    def _normalize_date(date: str | None) -> str:
        """Validate common date formats (YYYY-MM-DD, YYYY/MM/DD, DD/MM/YYYY) or default to today."""
        if not date or not str(date).strip():
            return datetime.now(timezone.utc).strftime("%Y-%m-%d")
        raw = str(date).strip()
        for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y.%m.%d", "%d/%m/%Y", "%d-%m-%Y"):
            try:
                return datetime.strptime(raw, fmt).strftime("%Y-%m-%d")
            except ValueError:
                continue
        raise ValueError(f"Invalid date '{raw}'. Use YYYY-MM-DD or YYYY/MM/DD.")

    def buy(self, symbol: str, shares: float, price: float, date: str | None = None) -> None:
        if shares <= 0 or price < 0:
            raise ValueError("Shares must be positive and price non-negative.")
        sym = symbol.upper()
        holding = self.state["portfolio"].get(sym, {"shares": 0.0, "avg_cost": 0.0, "lots": []})
        old_shares = float(holding["shares"])
        old_cost = float(holding["avg_cost"])
        new_shares = old_shares + shares
        new_avg = ((old_shares * old_cost) + (shares * price)) / new_shares
        lots = list(holding.get("lots", []))
        lot_date = self._normalize_date(date)
        lots.append({"date": lot_date, "shares": round(shares, 6), "price": round(price, 4)})
        lots.sort(key=lambda lot: lot.get("date", ""))
        self.state["portfolio"][sym] = {
            "shares": round(new_shares, 6),
            "avg_cost": round(new_avg, 4),
            "lots": lots,
        }
        trades = self.state.setdefault("trades", [])
        trades.append({
            "date": lot_date,
            "action": "BUY",
            "symbol": sym,
            "shares": round(shares, 6),
            "price": round(price, 4),
            "realized_pnl": 0.0,
        })
        trades.sort(key=lambda tr: tr.get("date", ""))
        if sym not in self.state["prices"]:
            self.set_price(sym, price, source="trade")
        else:
            self.save()

    def sell(self, symbol: str, shares: float, price: float | None = None, date: str | None = None) -> float:
        if shares <= 0:
            raise ValueError("Shares must be positive.")
        if price is not None and price < 0:
            raise ValueError("Price must be non-negative.")
        sym = symbol.upper()
        holding = self.state["portfolio"].get(sym)
        if not holding or float(holding["shares"]) < shares - 1e-9:
            raise ValueError(f"Insufficient shares of {sym} to sell.")

        sale_price = float(price) if price is not None else (self.get_price(sym) or float(holding["avg_cost"]))
        lots = list(holding.get("lots", []))
        to_sell = float(shares)
        cost_basis = 0.0

        if lots:
            new_lots = []
            for lot in lots:
                lot_sh = float(lot["shares"])
                lot_pr = float(lot["price"])
                if to_sell <= 1e-9:
                    new_lots.append(lot)
                elif lot_sh <= to_sell + 1e-9:
                    cost_basis += lot_sh * lot_pr
                    to_sell -= lot_sh
                else:
                    cost_basis += to_sell * lot_pr
                    new_lots.append({**lot, "shares": round(lot_sh - to_sell, 6)})
                    to_sell = 0.0
            lots = new_lots
        else:
            cost_basis = float(shares) * float(holding["avg_cost"])

        realized = round((float(shares) * sale_price) - cost_basis, 4)
        self.state["realized_pnl"] = round(float(self.state.get("realized_pnl", 0.0)) + realized, 4)
        trade_date = self._normalize_date(date)
        trades = self.state.setdefault("trades", [])
        trades.append({
            "date": trade_date,
            "action": "SELL",
            "symbol": sym,
            "shares": round(shares, 6),
            "price": round(sale_price, 4),
            "realized_pnl": round(realized, 2),
        })
        trades.sort(key=lambda tr: tr.get("date", ""))

        remaining = float(holding["shares"]) - float(shares)
        if remaining <= 1e-9:
            del self.state["portfolio"][sym]
        else:
            holding["shares"] = round(remaining, 6)
            if lots:
                holding["lots"] = lots
                rem_cost = sum(float(l["shares"]) * float(l["price"]) for l in lots)
                holding["avg_cost"] = round(rem_cost / remaining, 4)
        self.save()
        return realized

    def add_dividend(self, symbol: str, amount: float, date: str | None = None) -> None:
        """Record a cash dividend received in USD for a symbol."""
        if amount <= 0:
            raise ValueError("Dividend amount must be positive.")
        div_date = self._normalize_date(date)
        self.state.setdefault("dividends", []).append({
            "date": div_date,
            "symbol": symbol.upper(),
            "amount": round(amount, 4),
        })
        self.save()

    def _rebuild_portfolio_from_trades(self) -> None:
        """Recompute holdings, FIFO lots, and realized P&L from trade ledger."""
        portfolio: dict[str, dict[str, Any]] = {}
        realized_total = 0.0
        for tr in self.state.get("trades", []):
            sym = str(tr.get("symbol") or "").upper()
            action = str(tr.get("action") or "").upper()
            shares = float(tr.get("shares") or 0.0)
            price = float(tr.get("price") or 0.0)
            dt = str(tr.get("date") or "")
            if action == "BUY":
                h = portfolio.setdefault(sym, {"shares": 0.0, "avg_cost": 0.0, "lots": []})
                old_sh = float(h["shares"])
                old_avg = float(h["avg_cost"])
                new_sh = old_sh + shares
                h["shares"] = round(new_sh, 6)
                h["avg_cost"] = round(((old_sh * old_avg) + (shares * price)) / new_sh, 4) if new_sh > 0 else 0.0
                h["lots"].append({"date": dt, "shares": round(shares, 6), "price": round(price, 4)})
            elif action == "SELL" and sym in portfolio:
                h = portfolio[sym]
                lots = list(h.get("lots", []))
                to_sell = shares
                cost_basis = 0.0
                new_lots = []
                for lot in lots:
                    lot_sh = float(lot["shares"])
                    lot_pr = float(lot["price"])
                    if to_sell <= 1e-9:
                        new_lots.append(lot)
                    elif lot_sh <= to_sell + 1e-9:
                        cost_basis += lot_sh * lot_pr
                        to_sell -= lot_sh
                    else:
                        cost_basis += to_sell * lot_pr
                        new_lots.append({**lot, "shares": round(lot_sh - to_sell, 6)})
                        to_sell = 0.0
                realized = round((shares * price) - cost_basis, 4)
                tr["realized_pnl"] = round(realized, 2)
                realized_total += realized
                rem = float(h["shares"]) - shares
                if rem <= 1e-9:
                    portfolio.pop(sym, None)
                else:
                    h["shares"] = round(rem, 6)
                    h["lots"] = new_lots
                    if new_lots:
                        rem_cost = sum(float(l["shares"]) * float(l["price"]) for l in new_lots)
                        h["avg_cost"] = round(rem_cost / rem, 4)
        self.state["portfolio"] = portfolio
        self.state["realized_pnl"] = round(realized_total, 4)

    def delete_trade(self, index: int) -> dict[str, Any]:
        """Remove a trade by index from history and recompute FIFO holdings."""
        trades = self.state.get("trades", [])
        if index < 0 or index >= len(trades):
            raise IndexError(f"Trade index {index} out of range.")
        removed = trades.pop(index)
        self._rebuild_portfolio_from_trades()
        self.save()
        return removed

    def set_note(self, symbol: str, text: str) -> None:
        """Save or clear an investment thesis note for a symbol."""
        sym = symbol.upper()
        notes = self.state.setdefault("notes", {})
        clean = text.strip()
        if clean:
            notes[sym] = clean
        else:
            notes.pop(sym, None)
        self.save()

    def get_notes(self) -> dict[str, str]:
        return dict(self.state.get("notes", {}))

    def add_trailing_stop(self, symbol: str, trail_pct: float) -> dict[str, Any]:
        """Configure or update a trailing stop-loss percentage for a symbol."""
        if trail_pct <= 0 or trail_pct >= 90:
            raise ValueError("Trailing stop % must be between 0 and 90.")
        sym = symbol.upper()
        cur = self.get_price(sym) or 0.0
        stops = self.state.setdefault("trailing_stops", {})
        entry = {
            "symbol": sym,
            "trail_pct": round(float(trail_pct), 2),
            "peak_price": round(float(cur), 4),
            "triggered": False,
            "created_at": datetime.now(timezone.utc).date().isoformat(),
        }
        stops[sym] = entry
        self.save()
        return entry

    def remove_trailing_stop(self, symbol: str) -> bool:
        stops = self.state.get("trailing_stops", {})
        removed = stops.pop(symbol.upper(), None) is not None
        if removed:
            self.save()
        return removed

    def check_trailing_stops(self, notify: bool = True) -> list[dict[str, Any]]:
        """Update peak prices on trailing stops and fire notification if drawdown hits trail_pct."""
        stops = self.state.get("trailing_stops", {})
        hits: list[dict[str, Any]] = []
        changed = False
        for sym, stop in list(stops.items()):
            cur = self.get_price(sym)
            if cur is None or cur <= 0:
                continue
            peak = float(stop.get("peak_price") or 0.0)
            if cur > peak:
                stop["peak_price"] = round(cur, 4)
                stop["triggered"] = False
                peak = cur
                changed = True
            trail = float(stop.get("trail_pct") or 0.0)
            stop_price = round(peak * (1.0 - trail / 100.0), 4)
            if cur <= stop_price and not stop.get("triggered"):
                stop["triggered"] = True
                changed = True
                hits.append({**stop, "current_price": cur, "stop_price": stop_price})
                if notify:
                    cur_code = infer_currency(sym, self.get_price_entry(sym))
                    send_notification(
                        f"VFEX Trailing Stop: {sym}",
                        f"{sym} hit {format_money(cur, cur_code, 4)} (-{trail:.1f}% from peak {format_money(peak, cur_code, 4)})",
                    )
        if changed:
            self.save()
        return hits

    def _build_holding_item(
        self,
        sym: str,
        shares: float,
        avg_cost: float,
        cur_code: str,
        source_tag: str,
        is_synced: bool,
        lots: list[dict[str, Any]],
        div_amount: float,
        targets: dict[str, float],
        fee_pct: float,
        provider: str | None = None,
    ) -> dict[str, Any]:
        p_entry = self.get_price_entry(sym)
        current_price = self.get_price(sym)
        if current_price is None:
            current_price = avg_cost
        cost = shares * avg_cost
        value = shares * current_price
        pnl = value - cost
        pnl_pct = (pnl / cost * 100.0) if cost > 0 else 0.0

        f = max(0.0, fee_pct) / 100.0
        net_cost = cost * (1.0 + f)
        net_val = value * (1.0 - f)
        net_pnl = net_val - net_cost
        net_pnl_pct = (net_pnl / net_cost * 100.0) if net_cost > 0 else 0.0
        breakeven = (avg_cost * (1.0 + f) / (1.0 - f)) if f < 0.5 else avg_cost

        days_held: int | None = None
        xirr_pct: float | None = None
        lot_dates = [str(l.get("date", "")) for l in lots if l.get("date")]
        if lot_dates:
            try:
                now_dt = datetime.now(timezone.utc)
                earliest = datetime.strptime(min(lot_dates), "%Y-%m-%d").date()
                days_held = max(0, (now_dt.date() - earliest).days)
                cfs: list[tuple[datetime, float]] = []
                for l in lots:
                    ld = datetime.strptime(str(l["date"]), "%Y-%m-%d").replace(tzinfo=timezone.utc)
                    cfs.append((ld, -(float(l["shares"]) * float(l["price"]) * (1.0 + f))))
                for d in self.state.get("dividends", []):
                    if str(d.get("symbol", "")).upper() == sym and d.get("date"):
                        dd = datetime.strptime(str(d["date"]), "%Y-%m-%d").replace(tzinfo=timezone.utc)
                        cfs.append((dd, float(d["amount"])))
                cfs.append((now_dt, net_val))
                xirr_pct = compute_xirr(cfs)
            except ValueError:
                days_held = None

        stop = self.state.get("trailing_stops", {}).get(sym)
        stop_pct = float(stop["trail_pct"]) if stop else None
        peak_price = float(stop.get("peak_price") or current_price) if stop else None
        stop_price = round(peak_price * (1.0 - stop_pct / 100.0), 4) if (stop_pct and peak_price) else None
        stop_dist_pct = round(((current_price - stop_price) / current_price * 100.0), 1) if (stop_price and current_price > 0) else None

        hist = self.state.get("history", {}).get(sym, [])
        tech = compute_symbol_technicals(hist, current_price)

        item: dict[str, Any] = {
            "symbol": sym,
            "source_tag": source_tag,
            "is_synced": is_synced,
            "currency": cur_code,
            "shares": shares,
            "avg_cost": avg_cost,
            "breakeven_price": round(breakeven, 4),
            "cost": round(cost, 2),
            "price": current_price,
            "value": value,
            "pnl": pnl,
            "pnl_pct": pnl_pct,
            "net_pnl": round(net_pnl, 2),
            "net_pnl_pct": round(net_pnl_pct, 1),
            "days_held": days_held,
            "xirr_pct": xirr_pct,
            "dividends": round(div_amount, 2),
            "change_pct": self.get_daily_change(sym),
            "best_bid": p_entry.get("best_bid"),
            "best_ask": p_entry.get("best_ask"),
            "bid_volume": p_entry.get("bid_volume"),
            "ask_volume": p_entry.get("ask_volume"),
            "spread": p_entry.get("spread"),
            "company_name": p_entry.get("company_name"),
            "candles": self.get_candles(sym),
            "ma20": tech["ma20"],
            "ma20_series": tech["ma20_series"],
            "rsi14": tech["rsi14"],
            "z_score": tech["z_score"],
            "lots": lots,
            "target_pct": targets.get(sym),
            "stop_pct": stop_pct,
            "stop_price": stop_price,
            "peak_price": peak_price,
            "stop_distance_pct": stop_dist_pct,
        }
        if provider:
            item["provider"] = provider
        return item

    def portfolio_summary(self, vfex_fee_pct: float = 0.0, zse_fee_pct: float = 0.0) -> dict[str, Any]:
        items: list[dict[str, Any]] = []
        total_cost = 0.0
        total_value = 0.0
        net_total_cost = 0.0
        net_total_value = 0.0
        zwg_cost = 0.0
        zwg_value = 0.0
        targets = self.state.get("targets", {})
        dividends_list = self.state.get("dividends", [])
        div_by_sym: dict[str, float] = {}
        for d in dividends_list:
            s = str(d.get("symbol", "")).upper()
            div_by_sym[s] = div_by_sym.get(s, 0.0) + float(d.get("amount", 0.0))

        usd_dividends = round(
            sum(amt for sym, amt in div_by_sym.items() if infer_currency(sym, self.get_price_entry(sym)) == "USD"),
            2,
        )
        zwg_dividends = round(
            sum(amt for sym, amt in div_by_sym.items() if infer_currency(sym, self.get_price_entry(sym)) == "ZWG"),
            2,
        )

        for sym, holding in sorted(self.state["portfolio"].items()):
            cur_code = infer_currency(sym, self.get_price_entry(sym))
            fee = zse_fee_pct if cur_code == "ZWG" else vfex_fee_pct
            item = self._build_holding_item(
                sym=sym,
                shares=float(holding["shares"]),
                avg_cost=float(holding["avg_cost"]),
                cur_code=cur_code,
                source_tag="Manual",
                is_synced=False,
                lots=holding.get("lots", []),
                div_amount=div_by_sym.get(sym, 0.0),
                targets=targets,
                fee_pct=fee,
            )
            items.append(item)

        wallet_cash_usd = 0.0
        wallet_cash_zwg = 0.0
        for prov, acct_data in sorted(self.state.get("synced_accounts", {}).items()):
            if not isinstance(acct_data, dict):
                continue
            wallet_cash_usd += float(acct_data.get("cash_usd") or 0.0)
            wallet_cash_zwg += float(acct_data.get("cash_zwg") or 0.0)
            tag = PORTAL_LABELS.get(prov, prov.upper())
            for sh_row in acct_data.get("holdings", []):
                sym = str(sh_row.get("symbol") or "").upper()
                shares = float(sh_row.get("shares") or 0.0)
                if not sym or shares <= 0:
                    continue
                cur_code = str(sh_row.get("currency") or infer_currency(sym, self.get_price_entry(sym)))
                fee = zse_fee_pct if cur_code == "ZWG" else vfex_fee_pct
                items.append(self._build_holding_item(
                    sym=sym,
                    shares=shares,
                    avg_cost=float(sh_row.get("avg_cost") or 0.0),
                    cur_code=cur_code,
                    source_tag=tag,
                    is_synced=True,
                    lots=[],
                    div_amount=0.0,
                    targets=targets,
                    fee_pct=fee,
                    provider=prov,
                ))

        for item in items:
            c = float(item["shares"]) * float(item["avg_cost"])
            v = float(item["value"])
            if item["currency"] == "ZWG":
                zwg_cost += c
                zwg_value += v
            else:
                f = max(0.0, vfex_fee_pct) / 100.0
                total_cost += c
                total_value += v
                net_total_cost += c * (1.0 + f)
                net_total_value += v * (1.0 - f)

        for item in items:
            denom = zwg_value if item["currency"] == "ZWG" else total_value
            item["alloc_pct"] = round((item["value"] / denom) * 100.0, 1) if denom > 0 else 0.0

        total_pnl = total_value - total_cost
        total_pnl_pct = (total_pnl / total_cost * 100.0) if total_cost > 0 else 0.0
        net_total_pnl = net_total_value - net_total_cost
        net_total_pnl_pct = (net_total_pnl / net_total_cost * 100.0) if net_total_cost > 0 else 0.0
        zwg_pnl = zwg_value - zwg_cost
        zwg_pnl_pct = (zwg_pnl / zwg_cost * 100.0) if zwg_cost > 0 else 0.0
        realized_pnl = round(float(self.state.get("realized_pnl", 0.0)), 2)

        # Portfolio-wide USD XIRR from trades + dividends + current USD value
        port_cfs: list[tuple[datetime, float]] = []
        f_usd = max(0.0, vfex_fee_pct) / 100.0
        for tr in self.state.get("trades", []):
            sym = str(tr.get("symbol") or "").upper()
            if infer_currency(sym, self.get_price_entry(sym)) != "USD" or not tr.get("date"):
                continue
            try:
                td = datetime.strptime(str(tr["date"]), "%Y-%m-%d").replace(tzinfo=timezone.utc)
                gross = float(tr["shares"]) * float(tr["price"])
                amt = -(gross * (1.0 + f_usd)) if tr.get("action") == "BUY" else (gross * (1.0 - f_usd))
                port_cfs.append((td, amt))
            except ValueError:
                pass
        for d in dividends_list:
            sym = str(d.get("symbol") or "").upper()
            if infer_currency(sym, self.get_price_entry(sym)) == "USD" and d.get("date"):
                try:
                    dd = datetime.strptime(str(d["date"]), "%Y-%m-%d").replace(tzinfo=timezone.utc)
                    port_cfs.append((dd, float(d["amount"])))
                except ValueError:
                    pass
        if net_total_value > 0:
            port_cfs.append((datetime.now(timezone.utc), net_total_value))
        portfolio_xirr_pct = compute_xirr(port_cfs)

        return {
            "items": items,
            "total_cost": total_cost,
            "total_value": total_value,
            "total_pnl": total_pnl,
            "total_pnl_pct": total_pnl_pct,
            "net_total_pnl": round(net_total_pnl, 2),
            "net_total_pnl_pct": round(net_total_pnl_pct, 1),
            "portfolio_xirr_pct": portfolio_xirr_pct,
            "realized_pnl": realized_pnl,
            "total_dividends": usd_dividends,
            "total_return": round(total_pnl + usd_dividends + realized_pnl, 2),
            "zwg_cost": round(zwg_cost, 2),
            "zwg_value": round(zwg_value, 2),
            "zwg_pnl": round(zwg_pnl, 2),
            "zwg_pnl_pct": round(zwg_pnl_pct, 2),
            "zwg_dividends": zwg_dividends,
            "has_zwg": zwg_cost > 0 or zwg_value > 0 or zwg_dividends > 0,
            "wallet_cash_usd": round(wallet_cash_usd, 2),
            "wallet_cash_zwg": round(wallet_cash_zwg, 2),
        }

    def set_target(self, symbol: str, pct: float) -> None:
        """Set or remove (when pct == 0) a target allocation percentage for a symbol."""
        if pct < 0 or pct > 100:
            raise ValueError("Target percentage must be between 0 and 100.")
        sym = symbol.upper()
        targets = self.state.setdefault("targets", {})
        if pct == 0:
            targets.pop(sym, None)
        else:
            targets[sym] = round(pct, 2)
        self.save()

    def get_targets(self) -> dict[str, float]:
        """Return configured target allocation percentages keyed by symbol."""
        return dict(self.state.get("targets", {}))

    def plan_dca(self, budget: float) -> dict[str, Any]:
        """Compute how to allocate a USD budget across target or watchlist/portfolio symbols."""
        if budget <= 0:
            raise ValueError("DCA budget must be positive.")

        targets = {
            s: float(p)
            for s, p in self.state.get("targets", {}).items()
            if float(p) > 0 and infer_currency(s, self.get_price_entry(s)) == "USD"
        }
        if targets:
            total_t = sum(targets.values())
            weights = {s: p / total_t for s, p in sorted(targets.items())}
            mode = "targets"
        else:
            syms = sorted(
                s for s in (set(self.state.get("portfolio", {}).keys()) | set(self.state.get("watchlist", [])))
                if infer_currency(s, self.get_price_entry(s)) == "USD"
            )
            if not syms:
                return {"budget": round(budget, 2), "mode": "equal", "plan": []}
            weights = {s: 1.0 / len(syms) for s in syms}
            mode = "equal"

        summary = self.portfolio_summary()
        current_values = {item["symbol"]: float(item["value"]) for item in summary["items"] if item["currency"] == "USD"}
        current_total = float(summary["total_value"])
        projected_total = current_total + budget

        shortfalls = {
            sym: max(0.0, projected_total * w - current_values.get(sym, 0.0))
            for sym, w in weights.items()
        }
        total_shortfall = sum(shortfalls.values())

        plan = []
        for sym, w in weights.items():
            alloc = (
                budget * (shortfalls[sym] / total_shortfall)
                if total_shortfall > 0
                else budget * w
            )
            price = self.get_price(sym)
            cur_val = current_values.get(sym, 0.0)
            cur_pct = round((cur_val / current_total) * 100.0, 1) if current_total > 0 else 0.0
            shares = round(alloc / price, 4) if price and price > 0 else 0.0
            whole_shares = int(alloc // price) if price and price > 0 else 0
            plan.append({
                "symbol": sym,
                "target_pct": round(w * 100.0, 1),
                "current_pct": cur_pct,
                "alloc_usd": round(alloc, 2),
                "price": price,
                "shares": shares,
                "whole_shares": whole_shares,
            })

        return {"budget": round(budget, 2), "mode": mode, "plan": plan}

    def add_alert(self, symbol: str, direction: str, target: float) -> None:
        if direction not in ("above", "below"):
            raise ValueError("Direction must be 'above' or 'below'.")
        self.state["alerts"].append({
            "symbol": symbol.upper(),
            "direction": direction,
            "target": round(target, 4),
            "triggered": False,
        })
        self.save()

    def remove_alert(self, index: int) -> None:
        """Remove an alert by its 0-based index."""
        alerts = self.state.get("alerts", [])
        if index < 0 or index >= len(alerts):
            raise IndexError(f"Alert index {index} out of range.")
        alerts.pop(index)
        self.save()

    def clear_triggered_alerts(self) -> int:
        """Remove all triggered alerts and return how many were cleared."""
        alerts = self.state.get("alerts", [])
        remaining = [a for a in alerts if not a.get("triggered")]
        removed = len(alerts) - len(remaining)
        if removed:
            self.state["alerts"] = remaining
            self.save()
        return removed

    def format_alert_text(self, alert: dict[str, Any]) -> str:
        """Format an alert into a human-readable string."""
        price = self.get_price(alert["symbol"])
        now_part = f" (now ${price:.4f})" if price is not None else ""
        return f"{alert['symbol']} {alert['direction']} ${float(alert['target']):.4f}{now_part}"

    def check_alerts(self, notify: bool = True) -> list[dict[str, Any]]:
        triggered_now = []
        for alert in self.state["alerts"]:
            if alert.get("triggered"):
                continue
            price = self.get_price(alert["symbol"])
            if price is None:
                continue
            hit = (
                (alert["direction"] == "above" and price >= alert["target"])
                or (alert["direction"] == "below" and price <= alert["target"])
            )
            if hit:
                alert["triggered"] = True
                triggered_now.append({**alert, "current_price": price})
                if notify:
                    send_notification(
                        f"VFEX Alert: {alert['symbol']}",
                        f"{alert['symbol']} is ${price:.4f} ({alert['direction']} ${alert['target']:.4f})",
                    )
        if triggered_now:
            self.save()
        return triggered_now

    def buy_recommendations(self, discount_pct: float = 5.0) -> list[dict[str, Any]]:
        """Return symbols trading >= discount_pct below 30-day average or below a target alert."""
        recs: list[dict[str, Any]] = []
        history_map = self.state.get("history", {})
        below_targets = {
            a["symbol"]: float(a["target"])
            for a in self.state.get("alerts", [])
            if a.get("direction") == "below"
        }
        for sym, entry in sorted(self.state.get("prices", {}).items()):
            cur = float(entry["price"])
            hist = history_map.get(sym, [])
            avg30 = sum(float(h["price"]) for h in hist) / len(hist) if hist else cur
            drop_pct = ((avg30 - cur) / avg30 * 100.0) if avg30 > 0 else 0.0
            target = below_targets.get(sym)
            reasons = []
            if len(hist) >= 2 and drop_pct >= discount_pct:
                reasons.append(f"{drop_pct:.1f}% below 30d avg (${avg30:.4f})")
            if target is not None and cur <= target:
                reasons.append(f"at/below target (${target:.4f})")
            if reasons:
                recs.append({"symbol": sym, "price": cur, "avg30": round(avg30, 4), "reasons": reasons})
        return recs

    def trade_signals(
        self,
        discount_pct: float = 3.0,
        include_zse: bool = True,
        profit_take_pct: float = 15.0,
        limit: int = 8,
    ) -> list[dict[str, Any]]:
        """Score live VFEX/ZSE counters on order-book pressure, pullbacks, targets, and profit-take levels."""
        summary = self.portfolio_summary()
        holdings = {item["symbol"]: item for item in summary["items"]}
        targets = self.get_targets()
        history_map = self.state.get("history", {})
        below_targets = {
            a["symbol"]: float(a["target"])
            for a in self.state.get("alerts", [])
            if a.get("direction") == "below"
        }
        watchlist_set = set(self.state.get("watchlist", []))
        signals: list[dict[str, Any]] = []

        for sym, entry in sorted(self.state.get("prices", {}).items()):
            cur = float(entry.get("price") or 0.0)
            if cur <= 0:
                continue
            cur_code = infer_currency(sym, entry)
            if not include_zse and cur_code != "USD":
                continue

            hist = history_map.get(sym, [])
            avg30 = sum(float(h.get("close", h.get("price", cur))) for h in hist) / len(hist) if hist else cur
            drop30 = ((avg30 - cur) / avg30 * 100.0) if avg30 > 0 else 0.0
            chg_pct = entry.get("change_pct")
            bid = float(entry.get("best_bid") or 0.0)
            ask = float(entry.get("best_ask") or 0.0)
            bid_vol = int(entry.get("bid_volume") or 0)
            ask_vol = int(entry.get("ask_volume") or 0)
            spread_pct = ((ask - bid) / cur * 100.0) if (bid > 0 and ask > bid) else None

            buy_score = 0
            buy_reasons: list[str] = []
            if len(hist) >= 2 and drop30 >= discount_pct:
                buy_score += min(40, int(round(drop30 * 3.0)))
                buy_reasons.append(f"-{drop30:.1f}% vs 30d avg")
            dip_floor = max(1.5, discount_pct * 0.67)
            if chg_pct is not None and float(chg_pct) <= -dip_floor:
                buy_score += min(30, int(round(abs(float(chg_pct)) * 4.0)))
                buy_reasons.append(f"{float(chg_pct):.1f}% today")
            if bid > 0 and bid_vol >= 50 and (ask_vol == 0 or bid_vol >= 2 * ask_vol):
                buy_score += 25
                if spread_pct is not None and spread_pct <= 5.0:
                    buy_score += 10
                buy_reasons.append(f"Bid vol {bid_vol} > Ask {ask_vol}")
            if sym in below_targets and cur <= below_targets[sym]:
                buy_score += 35
                buy_reasons.append(f"<= target {format_money(below_targets[sym], cur_code, 4)}")
            if cur_code == "USD" and sym in targets:
                cur_alloc = float(holdings[sym]["alloc_pct"]) if sym in holdings else 0.0
                if cur_alloc < float(targets[sym]) - 5.0:
                    buy_score += 20
                    buy_reasons.append(f"Alloc {cur_alloc:.0f}% < {float(targets[sym]):.0f}%")

            if buy_score > 0:
                if sym in watchlist_set or sym in holdings:
                    buy_score += 5
                signals.append({
                    "symbol": sym,
                    "action": "BUY",
                    "score": buy_score,
                    "currency": cur_code,
                    "price": cur,
                    "limit_price": round(ask if ask > 0 else cur, 4),
                    "best_bid": entry.get("best_bid"),
                    "best_ask": entry.get("best_ask"),
                    "bid_volume": entry.get("bid_volume"),
                    "ask_volume": entry.get("ask_volume"),
                    "change_pct": chg_pct,
                    "reasons": buy_reasons,
                    "headline": f"BUY {sym} ({buy_reasons[0]})",
                })

            if sym in holdings:
                held = holdings[sym]
                sell_score = 0
                sell_reasons: list[str] = []
                if float(held.get("pnl_pct") or 0.0) >= profit_take_pct:
                    sell_score += 30
                    sell_reasons.append(f"+{float(held['pnl_pct']):.1f}% gain")
                if held.get("target_pct") is not None and float(held.get("alloc_pct") or 0.0) > float(held["target_pct"]) + 10.0:
                    sell_score += 20
                    sell_reasons.append(f"Alloc {float(held['alloc_pct']):.0f}% > {float(held['target_pct']):.0f}%")
                if chg_pct is not None and float(chg_pct) >= 8.0 and ask > 0 and ask_vol >= 2 * max(1, bid_vol):
                    sell_score += 20
                    sell_reasons.append(f"+{float(chg_pct):.1f}% spike / heavy ask")
                if sell_score > 0:
                    signals.append({
                        "symbol": sym,
                        "action": "SELL",
                        "score": sell_score,
                        "currency": cur_code,
                        "price": cur,
                        "limit_price": round(bid if bid > 0 else cur, 4),
                        "best_bid": entry.get("best_bid"),
                        "best_ask": entry.get("best_ask"),
                        "bid_volume": entry.get("bid_volume"),
                        "ask_volume": entry.get("ask_volume"),
                        "change_pct": chg_pct,
                        "reasons": sell_reasons,
                        "headline": f"SELL {sym} ({sell_reasons[0]})",
                    })

        signals.sort(key=lambda s: (-int(s["score"]), s["symbol"]))
        return signals[:limit]

    def notify_trade_signals(self, signals: list[dict[str, Any]], min_score: int = 30) -> list[dict[str, Any]]:
        """Send one desktop notification per day for each high-conviction signal."""
        today = datetime.now(timezone.utc).date().isoformat()
        seen_today = [k for k in self.state.get("notified_signals", []) if k.startswith(today + ":")]
        seen_set = set(seen_today)
        sent: list[dict[str, Any]] = []
        for sig in signals:
            if int(sig.get("score", 0)) < min_score:
                continue
            key = f"{today}:{sig['action']}:{sig['symbol']}"
            if key in seen_set:
                continue
            seen_set.add(key)
            seen_today.append(key)
            cur_code = sig.get("currency", "USD")
            body = f"{format_money(sig['price'], cur_code, 4)} — {', '.join(sig.get('reasons', []))}"
            send_notification(f"VFEX Signal: {sig['action']} {sig['symbol']}", body)
            sent.append(sig)
        if len(seen_today) != len(self.state.get("notified_signals", [])) or sent:
            self.state["notified_signals"] = seen_today
            self.save()
        return sent

    @property
    def ctrade_file(self) -> Path:
        return self.config_dir / "ctrade.json"

    @property
    def accounts_file(self) -> Path:
        return self.config_dir / "accounts.json"

    @staticmethod
    def _mask_email(email: str) -> str:
        if "@" not in email:
            return email[:2] + "***" if email else ""
        local, domain = email.split("@", 1)
        return (local[:2] + "***@" + domain) if len(local) > 2 else ("***@" + domain)

    def _load_accounts(self) -> dict[str, Any]:
        data: dict[str, Any] = {}
        if self.accounts_file.exists():
            try:
                loaded = json.loads(self.accounts_file.read_text(encoding="utf-8"))
                if isinstance(loaded, dict):
                    data = loaded
            except json.JSONDecodeError:
                pass
        if "ctrade" not in data and self.ctrade_file.exists():
            try:
                legacy = json.loads(self.ctrade_file.read_text(encoding="utf-8"))
                if isinstance(legacy, dict) and legacy:
                    data["ctrade"] = legacy
            except json.JSONDecodeError:
                pass
        return data

    def _save_accounts(self, data: dict[str, Any]) -> None:
        self.accounts_file.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
        os.chmod(self.accounts_file, stat.S_IRUSR | stat.S_IWUSR)

    def _load_ctrade_creds(self) -> dict[str, Any]:
        return dict(self._load_accounts().get("ctrade") or {})

    def _save_ctrade_creds(self, data: dict[str, Any]) -> None:
        self.ctrade_file.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
        os.chmod(self.ctrade_file, stat.S_IRUSR | stat.S_IWUSR)
        accounts = self._load_accounts()
        accounts["ctrade"] = data
        self._save_accounts(accounts)

    def _provider_status(self, provider: str) -> dict[str, Any]:
        creds = self._load_accounts().get(provider) or {}
        synced = self.state.get("synced_accounts", {}).get(provider) or {}
        legacy_ct = self.state.get("ctrade_account", {}) if provider == "ctrade" else {}
        email = str(creds.get("email") or legacy_ct.get("email") or "")
        connected = bool(
            (provider == "ctrade" and creds.get("email") and creds.get("password"))
            or (provider != "ctrade" and creds.get("access_token"))
        )
        mfa_pending = bool(creds.get("mfa_pending") and creds.get("mfa_token"))
        return {
            "provider": provider,
            "connected": connected,
            "mfa_pending": mfa_pending,
            "mfa_message": str(creds.get("mfa_message") or ""),
            "email_masked": self._mask_email(email) if email else "",
            "cds_number": str(creds.get("cds_number") or legacy_ct.get("cds_number") or ""),
            "last_sync": str(synced.get("last_sync") or legacy_ct.get("last_sync") or ""),
            "holdings_count": len(synced.get("holdings", [])) or int(legacy_ct.get("holdings_count") or 0),
            "cash_usd": round(float(synced.get("cash_usd") or 0.0), 2),
            "cash_zwg": round(float(synced.get("cash_zwg") or 0.0), 2),
        }

    def accounts_status(self) -> dict[str, Any]:
        """Return redacted connection, MFA, and balance metadata for all 3 portals."""
        return {
            prov: self._provider_status(prov)
            for prov in ("ctrade", "vfex_direct", "zse_direct")
        }

    def ctrade_status(self) -> dict[str, Any]:
        return self._provider_status("ctrade")

    def ctrade_logout(self) -> None:
        self.portal_logout("ctrade")

    def portal_logout(self, provider: str) -> None:
        if provider == "ctrade" and self.ctrade_file.exists():
            self.ctrade_file.unlink()
        accounts = self._load_accounts()
        accounts.pop(provider, None)
        self._save_accounts(accounts)
        if provider == "ctrade":
            self.state.pop("ctrade_account", None)
        self.state.setdefault("synced_accounts", {}).pop(provider, None)
        self.save()

    @staticmethod
    def _voms_request(url: str, method: str = "GET", body: dict[str, Any] | None = None, token: str | None = None) -> Any:
        headers = {"Accept": "application/json", "User-Agent": "omarchy-VFEX-Direct/0.1"}
        raw_body = None
        if body is not None:
            raw_body = json.dumps(body).encode("utf-8")
            headers["Content-Type"] = "application/json"
        if token:
            headers["Authorization"] = f"Bearer {token}"
        req = urllib.request.Request(url, data=raw_body, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            err_txt = exc.read().decode("utf-8", "ignore")
            try:
                err_json = json.loads(err_txt)
                msg = err_json.get("message") or err_txt
            except json.JSONDecodeError:
                msg = err_txt
            raise ValueError(f"HTTP {exc.code}: {str(msg)[:140]}") from exc
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            raise ValueError(f"Network error: {exc}") from exc

    @staticmethod
    def _extract_voms_rows(payload: Any) -> list[dict[str, Any]]:
        if isinstance(payload, list):
            return [r for r in payload if isinstance(r, dict)]
        if isinstance(payload, dict):
            data = payload.get("data", payload)
            if isinstance(data, list):
                return [r for r in data if isinstance(r, dict)]
            if isinstance(data, dict):
                for key in ("holdings", "items", "positions", "portfolio", "wallets", "content"):
                    val = data.get(key)
                    if isinstance(val, list):
                        return [r for r in val if isinstance(r, dict)]
        return []

    def _voms_sync_with_token(self, provider: str, token: str, base_url: str | None = None) -> dict[str, Any]:
        cfg = VOMS_PROVIDERS[provider]
        base = base_url or cfg["base_url"]
        cur_default = cfg["currency"]
        strip_vx = bool(cfg["strip_vx"])
        title = cfg["title"]

        holdings: list[dict[str, Any]] = []
        for ep in ("/voms/portfolios", "/voms/portfolio", "/voms/holdings", "/portfolio"):
            try:
                payload = self._voms_request(f"{base}{ep}", method="GET", token=token)
                rows = self._extract_voms_rows(payload)
                for r in rows:
                    raw_sym = str(r.get("symbol") or r.get("ticker") or r.get("counter") or "").strip().upper()
                    if not raw_sym:
                        continue
                    sym = raw_sym[:-3] if (strip_vx and raw_sym.endswith(".VX")) else raw_sym
                    qty = _safe_float(r.get("quantity") or r.get("shares") or r.get("totalUnits") or r.get("units") or r.get("balance") or r.get("availableQuantity"))
                    avg = _safe_float(r.get("averagePrice") or r.get("avgCost") or r.get("averageCost") or r.get("costPrice") or r.get("currentPrice")) or self.get_price(sym) or 0.0
                    cur = str(r.get("currency") or cur_default).upper()
                    if cur not in ("USD", "ZWG"):
                        cur = cur_default
                    if qty and qty > 0:
                        holdings.append({"symbol": sym, "shares": round(qty, 6), "avg_cost": round(avg, 4), "currency": cur})
                        if sym not in self.state["watchlist"]:
                            self.state["watchlist"].append(sym)
                break
            except ValueError as exc:
                if "HTTP 401" in str(exc):
                    raise
                continue

        cash_usd = 0.0
        cash_zwg = 0.0
        for wep in ("/voms/wallet", "/voms/wallets", "/wallet", "/wallets"):
            try:
                wpayload = self._voms_request(f"{base}{wep}", method="GET", token=token)
                wdata = wpayload.get("data", wpayload) if isinstance(wpayload, dict) else wpayload
                wrows = [wdata] if isinstance(wdata, dict) and any(k in wdata for k in ("balance", "availableBalance", "cashBalance")) else self._extract_voms_rows(wpayload)
                for w in wrows:
                    bal = _safe_float(w.get("availableBalance") or w.get("cashBalance") or w.get("balance") or w.get("amount"))
                    if bal is None:
                        continue
                    wcur = str(w.get("currency") or w.get("currencyCode") or cur_default).upper()
                    if wcur in ("ZWG", "ZWL", "ZIG"):
                        cash_zwg += bal
                    else:
                        cash_usd += bal
                if wrows:
                    break
            except ValueError:
                continue

        now_iso = datetime.now(timezone.utc).isoformat()
        self.state.setdefault("synced_accounts", {})[provider] = {
            "holdings": holdings,
            "cash_usd": round(cash_usd, 2),
            "cash_zwg": round(cash_zwg, 2),
            "last_sync": now_iso,
        }
        self.save()
        cash_part = f", cash {format_money(cash_zwg if cur_default == 'ZWG' else cash_usd, cur_default, 2)}"
        return {
            "ok": True,
            "provider": provider,
            "holdings_synced": len(holdings),
            "cash_usd": round(cash_usd, 2),
            "cash_zwg": round(cash_zwg, 2),
            "message": f"Synced {title}: {len(holdings)} holding(s){cash_part}.",
        }

    def portal_login(
        self,
        provider: str,
        email: str | None = None,
        password: str | None = None,
        base_url: str | None = None,
    ) -> dict[str, Any]:
        """Log into ctrade, vfex_direct, or zse_direct (handles VOMS MFA OTP challenge)."""
        if provider == "ctrade":
            return self.ctrade_login_and_sync(email=email, password=password, base_url=base_url or CTRADE_BASE_URL)
        if provider not in VOMS_PROVIDERS:
            raise ValueError(f"Unknown provider: {provider}")

        cfg = VOMS_PROVIDERS[provider]
        base = base_url or cfg["base_url"]
        accounts = self._load_accounts()
        saved = accounts.get(provider) or {}
        em = (email or saved.get("email") or "").strip()
        pw = password if password is not None else saved.get("password")
        if not em or not pw:
            raise ValueError(f"{cfg['title']} email and password required.")

        resp = self._voms_request(f"{base}/auth/login", method="POST", body={"email": em, "password": pw})
        data = resp.get("data") if isinstance(resp, dict) else None
        if not isinstance(data, dict):
            raise ValueError(str(resp.get("message") if isinstance(resp, dict) else "Login rejected."))

        if data.get("requiresMfa") and data.get("mfaToken"):
            accounts[provider] = {
                **saved,
                "email": em,
                "password": pw,
                "mfa_pending": True,
                "mfa_token": str(data["mfaToken"]),
                "mfa_message": str(data.get("message") or "Enter 6-digit OTP code"),
            }
            self._save_accounts(accounts)
            return {
                "ok": True,
                "requires_mfa": True,
                "provider": provider,
                "message": f"{cfg['title']}: 6-digit OTP sent — enter code to verify.",
            }

        token = data.get("accessToken")
        if not token:
            raise ValueError(f"{cfg['title']}: no accessToken or MFA token returned.")
        accounts[provider] = {
            "email": em,
            "password": pw,
            "access_token": str(token),
            "mfa_pending": False,
        }
        self._save_accounts(accounts)
        return self._voms_sync_with_token(provider, str(token), base_url=base)

    def portal_verify_mfa(self, provider: str, code: str, base_url: str | None = None) -> dict[str, Any]:
        """Submit 6-digit OTP verification code for vfex_direct or zse_direct and sync portfolio."""
        if provider not in VOMS_PROVIDERS:
            raise ValueError(f"MFA is only used for vfex_direct or zse_direct, not {provider}.")
        clean_code = code.strip()
        if not clean_code.isdigit() or len(clean_code) != 6:
            raise ValueError("Verification code must be exactly 6 digits.")
        cfg = VOMS_PROVIDERS[provider]
        base = base_url or cfg["base_url"]
        accounts = self._load_accounts()
        saved = accounts.get(provider) or {}
        mfa_token = str(saved.get("mfa_token") or "")
        if not mfa_token:
            raise ValueError(f"{cfg['title']}: no pending MFA session. Connect with email & password first.")

        resp = self._voms_request(f"{base}/auth/verify-mfa", method="POST", body={"mfaToken": mfa_token, "code": clean_code})
        data = resp.get("data") if isinstance(resp, dict) else None
        token = data.get("accessToken") if isinstance(data, dict) else None
        if not token:
            raise ValueError(str(resp.get("message") if isinstance(resp, dict) else "MFA verification failed."))

        accounts[provider] = {
            "email": saved.get("email", ""),
            "password": saved.get("password", ""),
            "access_token": str(token),
            "mfa_pending": False,
        }
        self._save_accounts(accounts)
        return self._voms_sync_with_token(provider, str(token), base_url=base)

    def portal_sync(self, provider: str = "all") -> dict[str, Any]:
        """Sync one connected portal or all connected portals."""
        targets = ["ctrade", "vfex_direct", "zse_direct"] if provider == "all" else [provider]
        accounts = self._load_accounts()
        synced_msgs: list[str] = []
        for prov in targets:
            saved = accounts.get(prov) or {}
            if prov == "ctrade":
                if saved.get("email") and saved.get("password"):
                    res = self.ctrade_login_and_sync()
                    synced_msgs.append(res["message"])
            elif prov in VOMS_PROVIDERS:
                tok = saved.get("access_token")
                if tok:
                    try:
                        res = self._voms_sync_with_token(prov, str(tok))
                        synced_msgs.append(res["message"])
                    except ValueError as exc:
                        if "HTTP 401" in str(exc) and saved.get("email") and saved.get("password"):
                            res = self.portal_login(prov)
                            synced_msgs.append(res["message"])
                        else:
                            raise
        if not synced_msgs:
            raise ValueError("No connected accounts ready to sync.")
        return {"ok": True, "message": " | ".join(synced_msgs)}

    def ctrade_login_and_sync(
        self,
        email: str | None = None,
        password: str | None = None,
        sync_portfolio: bool = True,
        base_url: str = CTRADE_BASE_URL,
    ) -> dict[str, Any]:
        """Authenticate against C-TRADE portal and sync holdings (storing creds 0600 locally only on success)."""
        saved = self._load_ctrade_creds()
        em = (email or saved.get("email") or "").strip()
        pw = password if password is not None else saved.get("password")
        if not em or not pw:
            raise ValueError("C-TRADE email and password required.")

        jar = http.cookiejar.CookieJar()
        opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
        login_req = urllib.request.Request(
            f"{base_url}/api/auth/login",
            data=json.dumps({"Email": em, "Password": pw}).encode("utf-8"),
            headers={"Content-Type": "application/json", "Accept": "application/json", "User-Agent": "omarchy-VFEX-Direct/0.1"},
            method="POST",
        )
        try:
            with opener.open(login_req, timeout=15) as resp:
                auth_payload = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            err_body = exc.read().decode("utf-8", "ignore")
            raise ValueError(f"C-TRADE login failed (HTTP {exc.code}): {err_body[:120]}") from exc
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            raise ValueError(f"Could not reach C-TRADE login ({exc}).") from exc

        if not auth_payload.get("success") or not isinstance(auth_payload.get("data"), dict):
            msg = auth_payload.get("message") or "Invalid C-TRADE credentials or login rejected."
            raise ValueError(str(msg))

        user_data = auth_payload["data"]
        cds = str(user_data.get("cdsNumber") or user_data.get("cds_number") or "")
        self._save_ctrade_creds({"email": em, "password": pw, "cds_number": cds})

        imported_holdings: list[dict[str, Any]] = []
        if sync_portfolio and cds:
            for endpoint, default_cur, strip_vx in (
                ("PortfolioByTypeVFEX", "USD", True),
                ("PortfolioByType", "ZWG", False),
            ):
                q = urllib.parse.urlencode({"cdsNumber": cds, "type": "equity"})
                p_req = urllib.request.Request(
                    f"{base_url}/api/mobile-proxy/{endpoint}?{q}",
                    headers={"Accept": "application/json", "User-Agent": "omarchy-VFEX-Direct/0.1"},
                )
                try:
                    with opener.open(p_req, timeout=15) as presp:
                        pdata = json.loads(presp.read().decode("utf-8"))
                    rows = pdata if isinstance(pdata, list) else (pdata.get("data") if isinstance(pdata, dict) else [])
                    if isinstance(rows, list):
                        for r in rows:
                            if not isinstance(r, dict):
                                continue
                            raw_sym = str(r.get("counter") or r.get("symbol") or r.get("Ticker") or "").strip().upper()
                            sym = raw_sym[:-3] if (strip_vx and raw_sym.endswith(".VX")) else raw_sym
                            qty = _safe_float(r.get("total_units") or r.get("shares") or r.get("Quantity") or r.get("balance"))
                            avg = _safe_float(r.get("average_price") or r.get("avg_price") or r.get("Current_price")) or self.get_price(sym) or 0.0
                            if sym and qty and qty > 0:
                                imported_holdings.append({
                                    "symbol": sym,
                                    "shares": round(qty, 6),
                                    "avg_cost": round(avg, 4),
                                    "currency": default_cur,
                                })
                                if sym not in self.state["watchlist"]:
                                    self.state["watchlist"].append(sym)
                except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, ValueError):
                    continue

        now_iso = datetime.now(timezone.utc).isoformat()
        self.state["ctrade_account"] = {
            "email": em,
            "cds_number": cds,
            "last_sync": now_iso,
            "holdings_count": len(imported_holdings),
        }
        self.state.setdefault("synced_accounts", {})["ctrade"] = {
            "holdings": imported_holdings,
            "cash_usd": 0.0,
            "cash_zwg": 0.0,
            "last_sync": now_iso,
        }
        self.save()
        return {
            "ok": True,
            "cds_number": cds,
            "email_masked": self._mask_email(em),
            "holdings_synced": len(imported_holdings),
            "message": f"Connected C-TRADE ({cds or self._mask_email(em)}); synced {len(imported_holdings)} holding(s).",
        }

    def import_csv(self, csv_path: Path) -> int:
        """Import symbol,price rows from a VFEX Direct CSV export."""
        count = 0
        with csv_path.open("r", encoding="utf-8", newline="") as fh:
            reader = csv.DictReader(fh)
            for row in reader:
                sym = (row.get("symbol") or row.get("Symbol") or row.get("SYMBOL") or "").strip().upper()
                raw_price = (row.get("price") or row.get("Price") or row.get("PRICE") or "").strip()
                if sym and raw_price:
                    self.set_price(sym, float(raw_price), source="csv")
                    count += 1
        return count

    def export_report(self, fmt: str = "md") -> str:
        """Export holdings, trades, dividends, and P&L summary as Markdown or CSV."""
        summary = self.portfolio_summary()
        trades = self.state.get("trades", [])
        dividends = self.state.get("dividends", [])

        if fmt == "csv":
            buf = io.StringIO()
            writer = csv.writer(buf)
            writer.writerow(["record_type", "date", "symbol", "shares", "price", "value_or_amount", "pnl"])
            for item in summary["items"]:
                writer.writerow([
                    "HOLDING",
                    "",
                    item["symbol"],
                    f"{item['shares']:g}",
                    f"{item['price']:.4f}",
                    f"{item['value']:.2f}",
                    f"{item['pnl']:.2f}",
                ])
            for t in trades:
                writer.writerow([
                    t["action"],
                    t["date"],
                    t["symbol"],
                    f"{t['shares']:g}",
                    f"{t['price']:.4f}",
                    f"{float(t['shares']) * float(t['price']):.2f}",
                    f"{float(t.get('realized_pnl', 0.0)):.2f}",
                ])
            for d in dividends:
                writer.writerow(["DIVIDEND", d["date"], d["symbol"], "", "", f"{float(d['amount']):.2f}", ""])
            return buf.getvalue()

        lines = [
            "# VFEX Portfolio Report",
            "",
            f"- **Total Value:** ${summary['total_value']:.2f}",
            f"- **Total Cost:** ${summary['total_cost']:.2f}",
            f"- **Unrealized P&L:** {'+' if summary['total_pnl'] >= 0 else ''}${summary['total_pnl']:.2f} ({summary['total_pnl_pct']:.1f}%)",
            f"- **Realized P&L:** {'+' if summary['realized_pnl'] >= 0 else ''}${summary['realized_pnl']:.2f}",
            f"- **Dividends:** +${summary['total_dividends']:.2f}",
            f"- **Total Return:** {'+' if summary['total_return'] >= 0 else ''}${summary['total_return']:.2f}",
            "",
            "## Holdings",
            "",
            "| Symbol | Shares | Avg Cost | Price | Value | P&L | Alloc % |",
            "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
        for item in summary["items"]:
            psign = "+" if item["pnl"] >= 0 else ""
            lines.append(
                f"| {item['symbol']} | {item['shares']:g} | ${item['avg_cost']:.4f} | ${item['price']:.4f} | ${item['value']:.2f} | {psign}${item['pnl']:.2f} | {item['alloc_pct']:.1f}% |"
            )
        if trades:
            lines.extend(["", "## Trade Ledger", "", "| Date | Action | Symbol | Shares | Price | Realized P&L |", "| --- | --- | --- | ---: | ---: | ---: |"])
            for t in trades:
                rp = f"${float(t.get('realized_pnl', 0.0)):.2f}" if t["action"] == "SELL" else "-"
                lines.append(f"| {t['date']} | {t['action']} | {t['symbol']} | {t['shares']:g} | ${t['price']:.4f} | {rp} |")
        if dividends:
            lines.extend(["", "## Dividends", "", "| Date | Symbol | Amount |", "| --- | --- | ---: |"])
            for d in dividends:
                lines.append(f"| {d['date']} | {d['symbol']} | +${float(d['amount']):.2f} |")
        return "\n".join(lines) + "\n"


def send_notification(title: str, body: str) -> None:
    """Send a desktop notification via notify-send if available."""
    try:
        subprocess.run(["notify-send", title, body], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except FileNotFoundError:
        pass


CAT_TZ = timezone(timedelta(hours=2))


def get_market_status(now: datetime | None = None) -> str:
    """Return 'Open' during VFEX trading hours (Mon-Fri, 09:00-13:00 CAT), else 'Closed'."""
    dt = (now or datetime.now(timezone.utc)).astimezone(CAT_TZ)
    if dt.weekday() < 5 and 9 <= dt.hour < 13:
        return "Open"
    return "Closed"


def get_last_updated_label(store: VFEXStore) -> str:
    """Return a compact CAT timestamp string for the most recent price update."""
    raw = store.state.get("last_fetch_at")
    if not raw:
        timestamps = [
            str(entry.get("updated_at", ""))
            for entry in store.state.get("prices", {}).values()
            if entry.get("updated_at")
        ]
        raw = max(timestamps) if timestamps else ""
    if not raw:
        return ""
    try:
        dt = datetime.fromisoformat(raw).astimezone(CAT_TZ)
    except ValueError:
        return ""
    today_cat = datetime.now(timezone.utc).astimezone(CAT_TZ).date()
    return dt.strftime("%H:%M") if dt.date() == today_cat else dt.strftime("%Y-%m-%d %H:%M")


def _fetch_json(target_url: str, timeout: int = 10) -> tuple[int, Any]:
    req = urllib.request.Request(
        target_url,
        headers={"User-Agent": "omarchy-VFEX-Direct/0.1", "Accept": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.status, json.loads(resp.read().decode("utf-8"))


def _ingest_vfex_direct_payload(store: VFEXStore, payload: Any) -> int:
    data = payload.get("data") if isinstance(payload, dict) else None
    if not isinstance(data, dict):
        return 0
    updated = 0
    for group_items in data.values():
        if not isinstance(group_items, list):
            continue
        for item in group_items:
            raw_sym = str(item.get("symbol") or "").strip().upper()
            sym = raw_sym[:-3] if raw_sym.endswith(".VX") else raw_sym
            raw_price = item.get("closingPrice")
            if raw_price is None:
                raw_price = item.get("openingPrice")
            if sym and raw_price is not None:
                open_p = item.get("openingPrice")
                chg_p = item.get("percentagePriceChange")
                stats_d = item.get("statsDate")
                store.set_price(
                    sym,
                    float(raw_price),
                    source="vfex-direct",
                    open_price=float(open_p) if open_p is not None else None,
                    change_pct=float(chg_p) if chg_p is not None else None,
                    date=str(stats_d) if stats_d else None,
                    currency="USD",
                    company_name=item.get("symbolName"),
                    save=False,
                )
                updated += 1
    return updated


def _ingest_ctrade_rows(
    store: VFEXStore,
    rows: Any,
    currency: str,
    strip_vx: bool,
    today: str,
    tracked_zse: set[str],
) -> int:
    if not isinstance(rows, list):
        return 0
    updated = 0
    for item in rows:
        if not isinstance(item, dict):
            continue
        raw_sym = str(item.get("Ticker") or "").strip().upper()
        if not raw_sym:
            continue
        sym = raw_sym[:-3] if (strip_vx and raw_sym.endswith(".VX")) else raw_sym
        cur_p = _safe_float(item.get("Current_price"))
        prev_p = _safe_float(item.get("PrevPrice"))
        prev_per = _safe_float(item.get("PrevPer"))
        bid = _safe_float(item.get("Best_bid"))
        ask = _safe_float(item.get("Best_Ask"))
        bid_vol = _safe_int(item.get("Bid_Volume"))
        ask_vol = _safe_int(item.get("Ask_Volume"))
        cname = str(item.get("FullCompanyName") or "").strip() or None
        track_hist = (currency == "USD") or (sym in tracked_zse)

        effective_price = cur_p if (cur_p is not None and cur_p > 0) else (
            prev_p if (prev_p is not None and prev_p > 0 and sym not in store.state["prices"]) else None
        )
        if effective_price is not None:
            store.set_price(
                sym,
                effective_price,
                source="c-trade-vfex" if currency == "USD" else "c-trade-zse",
                open_price=prev_p if (prev_p is not None and prev_p > 0) else None,
                change_pct=prev_per,
                date=today,
                best_bid=bid,
                best_ask=ask,
                bid_volume=bid_vol,
                ask_volume=ask_vol,
                currency=currency,
                company_name=cname,
                track_history=track_hist,
                save=False,
            )
            updated += 1
        elif sym in store.state["prices"]:
            store.attach_depth(
                sym,
                best_bid=bid,
                best_ask=ask,
                bid_volume=bid_vol,
                ask_volume=ask_vol,
                currency=currency,
                company_name=cname,
            )
            updated += 1
    return updated


def fetch_vfex_prices(
    store: VFEXStore,
    url: str = VFEX_DIRECT_URL,
    force: bool = False,
    ttl_seconds: int = 900,
    ctrade_vfex_url: str | None = CTRADE_VFEX_URL,
    ctrade_zse_url: str | None = CTRADE_ZSE_URL,
) -> dict[str, Any]:
    """Fetch VFEX + C-TRADE prices & market depth when TTL expires or forced, preserving cached data on failure."""
    now = datetime.now(timezone.utc)
    today = now.date().isoformat()
    if not force:
        last_at = store.state.get("last_fetch_at")
        if last_at:
            try:
                if (now - datetime.fromisoformat(last_at)).total_seconds() < ttl_seconds:
                    return {"ok": True, "cached": True, "message": "Using recent cached prices."}
            except ValueError:
                pass
        elif store.state.get("last_fetch_date") == today:
            return {"ok": True, "cached": True, "message": f"Already fetched today ({today}); using cached prices."}

    custom_override = url != VFEX_DIRECT_URL
    tracked_zse = set(store.state.get("watchlist", [])) | set(store.state.get("portfolio", {}).keys())
    updated = 0
    statuses: list[int] = []
    errors: list[str] = []

    try:
        st, payload = _fetch_json(url)
        statuses.append(st)
        updated += _ingest_vfex_direct_payload(store, payload)
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, ValueError) as exc:
        errors.append(str(exc))

    if not custom_override and ctrade_vfex_url:
        try:
            st, ct_vfex = _fetch_json(ctrade_vfex_url)
            statuses.append(st)
            updated += _ingest_ctrade_rows(store, ct_vfex, "USD", True, today, tracked_zse)
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, ValueError) as exc:
            errors.append(str(exc))

    if not custom_override and ctrade_zse_url:
        try:
            st, ct_zse = _fetch_json(ctrade_zse_url)
            statuses.append(st)
            updated += _ingest_ctrade_rows(store, ct_zse, "ZWG", False, today, tracked_zse)
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, ValueError) as exc:
            errors.append(str(exc))

    if not statuses:
        reason = errors[0] if errors else "network error"
        return {"ok": False, "cached": True, "status": None, "message": f"Could not reach VFEX ({reason}). Using cached prices."}

    store.state["last_fetch_date"] = today
    store.state["last_fetch_at"] = datetime.now(timezone.utc).isoformat()
    store.save()
    return {
        "ok": True,
        "cached": False,
        "status": statuses[0],
        "updated": updated,
        "message": f"Updated {updated} quotes ({today}).",
    }


def format_waybar(store: VFEXStore) -> dict[str, str]:
    """Build Waybar custom module JSON payload."""
    store.check_alerts(notify=True)
    summary = store.portfolio_summary()
    status_label = get_market_status()
    updated_label = get_last_updated_label(store)
    meta = f"Market: {status_label}" + (f" • Updated {updated_label}" if updated_label else "")
    tooltip_lines = ["VFEX Direct & C-TRADE — Portfolio & Watchlist", meta]

    usd_items = [i for i in summary["items"] if i["currency"] == "USD"]
    if usd_items:
        pnl = summary["total_pnl"]
        sign = "+" if pnl >= 0 else ""
        text = f"VFEX ${summary['total_value']:.2f} ({sign}${pnl:.2f})"
        css_class = "profit" if pnl >= 0 else "loss"
    elif summary["items"]:
        zpnl = summary["zwg_pnl"]
        sign = "+" if zpnl >= 0 else ""
        text = f"ZSE ZiG {summary['zwg_value']:.2f} ({sign}ZiG {zpnl:.2f})"
        css_class = "profit" if zpnl >= 0 else "loss"
    else:
        watch = store.state.get("watchlist", [])
        if watch:
            first = watch[0]
            p = store.get_price(first)
            cur_code = infer_currency(first, store.get_price_entry(first))
            chg = store.get_daily_change(first)
            chg_str = f" ({'+' if chg >= 0 else ''}{chg:.1f}%)" if chg is not None else ""
            text = f"VFEX {first} {format_money(p, cur_code, 4)}{chg_str}" if p is not None else f"VFEX {first} --"
        else:
            text = "VFEX --"
        css_class = "neutral"

    if summary["items"]:
        tooltip_lines.append("")
        tooltip_lines.append("Holdings:")
        for item in summary["items"]:
            cur_code = item["currency"]
            isign = "+" if item["pnl"] >= 0 else "-"
            chg = item.get("change_pct")
            chg_str = f" | {'+' if chg >= 0 else ''}{chg:.1f}% today" if chg is not None else ""
            tooltip_lines.append(
                f"  {item['symbol']}: {item['shares']:g} @ {format_money(item['price'], cur_code, 4)} ({isign}{format_money(abs(item['pnl']), cur_code, 2)} / {'+' if item['pnl_pct'] >= 0 else ''}{item['pnl_pct']:.1f}%{chg_str})"
            )

    watch = store.state.get("watchlist", [])
    if watch:
        tooltip_lines.append("")
        tooltip_lines.append("Watchlist:")
        for sym in watch:
            p_entry = store.get_price_entry(sym)
            cur_code = infer_currency(sym, p_entry)
            p = store.get_price(sym)
            p_str = format_money(p, cur_code, 4) if p is not None else "N/A"
            chg = store.get_daily_change(sym)
            chg_str = f" ({'+' if chg >= 0 else ''}{chg:.1f}%)" if chg is not None else ""
            depth_str = ""
            if p_entry.get("best_bid") and p_entry.get("best_ask"):
                depth_str = f" | B:{format_money(p_entry['best_bid'], cur_code, 4)} A:{format_money(p_entry['best_ask'], cur_code, 4)}"
            tooltip_lines.append(f"  {sym}: {p_str}{chg_str}{depth_str}")

    return {"text": text, "tooltip": "\n".join(tooltip_lines), "class": css_class}


def format_panel_json(
    store: VFEXStore,
    include_zse: bool = True,
    discount_pct: float = 3.0,
    notify_signals: bool = False,
) -> dict[str, Any]:
    """Build structured JSON for BarWidget.qml and Panel.qml."""
    fetch_res = fetch_vfex_prices(store, force=False)
    store.check_alerts(notify=True)
    wb = format_waybar(store)
    summary = store.portfolio_summary()
    recs = {r["symbol"]: r for r in store.buy_recommendations(discount_pct=discount_pct)}
    signals = store.trade_signals(discount_pct=discount_pct, include_zse=include_zse)
    if notify_signals and get_market_status() == "Open":
        store.notify_trade_signals(signals)
    watchlist_items = []
    history_map = store.state.get("history", {})
    for sym in store.state.get("watchlist", []):
        p_entry = store.get_price_entry(sym)
        hist = [h.get("close", h.get("price")) for h in history_map.get(sym, []) if ("close" in h or "price" in h)]
        watchlist_items.append({
            "symbol": sym,
            "currency": infer_currency(sym, p_entry),
            "price": store.get_price(sym),
            "buy": sym in recs or any(s["symbol"] == sym and s["action"] == "BUY" for s in signals),
            "history": hist,
            "candles": store.get_candles(sym),
            "change_pct": store.get_daily_change(sym),
            "best_bid": p_entry.get("best_bid"),
            "best_ask": p_entry.get("best_ask"),
            "bid_volume": p_entry.get("bid_volume"),
            "ask_volume": p_entry.get("ask_volume"),
            "spread": p_entry.get("spread"),
            "company_name": p_entry.get("company_name"),
            "source": p_entry.get("source"),
        })

    zse_symbols = sorted(
        sym for sym, entry in store.state.get("prices", {}).items()
        if infer_currency(sym, entry) == "ZWG"
    )

    triggered_alerts = []
    active_alerts = []
    for idx, alert in enumerate(store.state.get("alerts", [])):
        entry = {
            "index": idx,
            "symbol": alert["symbol"],
            "direction": alert["direction"],
            "target": alert["target"],
            "text": store.format_alert_text(alert),
        }
        if alert.get("triggered"):
            triggered_alerts.append(entry)
        else:
            active_alerts.append(entry)

    return {
        **wb,
        "total_value": round(summary["total_value"], 2),
        "total_cost": round(summary["total_cost"], 2),
        "total_pnl": round(summary["total_pnl"], 2),
        "total_pnl_pct": round(summary["total_pnl_pct"], 2),
        "realized_pnl": summary["realized_pnl"],
        "total_dividends": summary["total_dividends"],
        "total_return": summary["total_return"],
        "zwg_value": summary["zwg_value"],
        "zwg_cost": summary["zwg_cost"],
        "zwg_pnl": summary["zwg_pnl"],
        "zwg_pnl_pct": summary["zwg_pnl_pct"],
        "zwg_dividends": summary["zwg_dividends"],
        "has_zwg": summary["has_zwg"],
        "zse_symbols": zse_symbols,
        "items": summary["items"],
        "watchlist": watchlist_items,
        "recommendations": list(recs.values()),
        "signals": signals,
        "top_signal": signals[0] if signals else None,
        "account": store.ctrade_status(),
        "accounts": store.accounts_status(),
        "connected_count": sum(1 for v in store.accounts_status().values() if v.get("connected")),
        "wallet_cash_usd": summary["wallet_cash_usd"],
        "wallet_cash_zwg": summary["wallet_cash_zwg"],
        "alerts": [a["text"] for a in triggered_alerts],
        "triggered_alerts": triggered_alerts,
        "active_alerts": active_alerts,
        "targets": store.get_targets(),
        "market_status": get_market_status(),
        "last_updated": get_last_updated_label(store),
        "fetch_error": "" if fetch_res.get("ok") else str(fetch_res.get("message", "Fetch failed")),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="vfex", description="Victoria Falls Stock Exchange (VFEX) CLI & Waybar tracker")
    sub = parser.add_subparsers(dest="command", required=True)

    p_price = sub.add_parser("price", help="Get or set a stock price in USD")
    p_price.add_argument("symbol", help="Ticker symbol (e.g. INSC, SIM)")
    p_price.add_argument("value", type=float, nargs="?", help="New price in USD")

    sub.add_parser("fetch", help="Check VFEX connectivity and refresh")

    p_watch = sub.add_parser("watch", help="Manage watchlist")
    p_watch.add_argument("action", choices=["add", "remove", "list"])
    p_watch.add_argument("symbol", nargs="?")

    p_buy = sub.add_parser("buy", help="Record a stock purchase")
    p_buy.add_argument("symbol")
    p_buy.add_argument("shares", type=float)
    p_buy.add_argument("price", type=float)
    p_buy.add_argument("--date", default=None, help="Purchase date (YYYY-MM-DD, defaults to today)")

    p_sell = sub.add_parser("sell", help="Record a stock sale")
    p_sell.add_argument("symbol")
    p_sell.add_argument("shares", type=float)
    p_sell.add_argument("price", type=float, nargs="?", help="Sale price in USD (defaults to current price)")
    p_sell.add_argument("--date", default=None, help="Sale date (YYYY-MM-DD, defaults to today)")

    sub.add_parser("portfolio", help="Show portfolio holdings and P&L")
    sub.add_parser("history", help="Show trade ledger (buys & sells)")

    p_alert = sub.add_parser("alert", help="Manage price alerts")
    p_alert.add_argument("action", choices=["add", "list", "check", "remove", "clear"])
    p_alert.add_argument("symbol", nargs="?", help="Symbol (for add) or 0-based index (for remove)")
    p_alert.add_argument("direction", nargs="?", choices=["above", "below"])
    p_alert.add_argument("target", nargs="?", type=float)

    sub.add_parser("waybar", help="Output Waybar JSON")
    p_panel = sub.add_parser("panel-json", help="Output structured JSON for Omarchy BarWidget/Panel")
    p_panel.add_argument("--market", choices=["all", "vfex"], default="all", help="Signal scope (all=VFEX+ZSE, vfex=VFEX USD only)")
    p_panel.add_argument("--discount", type=float, default=3.0, help="Pullback discount threshold pct")
    p_panel.add_argument("--notify-signals", action="store_true", help="Send notify-send alerts for top market-hours trade signals")

    p_signals = sub.add_parser("signals", help="Show ranked BUY/SELL trade opportunities")
    p_signals.add_argument("--market", choices=["all", "vfex"], default="all")
    p_signals.add_argument("--discount", type=float, default=3.0)
    p_signals.add_argument("--json", action="store_true")

    p_ctrade = sub.add_parser("ctrade", help="Manage local C-TRADE account login and portfolio sync")
    p_ctrade.add_argument("action", choices=["login", "sync", "status", "logout"])
    p_ctrade.add_argument("--email", default=None)
    p_ctrade.add_argument("--password-stdin", action="store_true", help="Read password securely from stdin")

    p_acct = sub.add_parser("account", help="Manage local credentials & sync for C-TRADE, VFEX Direct, and ZSE Direct")
    p_acct.add_argument("action", choices=["login", "verify-mfa", "sync", "status", "logout"])
    p_acct.add_argument("--provider", choices=["ctrade", "vfex_direct", "zse_direct", "all"], default="ctrade")
    p_acct.add_argument("--email", default=None)
    p_acct.add_argument("--code", default=None, help="6-digit OTP verification code for VFEX/ZSE Direct")
    p_acct.add_argument("--password-stdin", action="store_true", help="Read password securely from stdin")
    sub.add_parser("recommend", help="Show BUY recommendations based on 30d avg and targets")
    p_import = sub.add_parser("import", help="Import prices from a CSV file (symbol,price)")
    p_import.add_argument("file", help="Path to CSV file")
    sub.add_parser("symbols", help="List known VFEX symbols")

    p_target = sub.add_parser("target", help="Manage target portfolio allocations (pct)")
    p_target.add_argument("action", choices=["set", "remove", "list"])
    p_target.add_argument("symbol", nargs="?")
    p_target.add_argument("pct", nargs="?", type=float)

    p_dca = sub.add_parser("dca", help="Plan how to invest a USD budget across targets")
    p_dca.add_argument("budget", type=float, help="Budget in USD")
    p_dca.add_argument("--json", action="store_true", help="Output structured JSON")

    p_div = sub.add_parser("dividend", help="Record or list USD dividends")
    p_div.add_argument("action", choices=["add", "list"])
    p_div.add_argument("symbol", nargs="?")
    p_div.add_argument("amount", nargs="?", type=float)
    p_div.add_argument("--date", default=None, help="Dividend date (YYYY-MM-DD, defaults to today)")

    p_export = sub.add_parser("export", help="Export portfolio, trades, and dividends")
    p_export.add_argument("--format", choices=["md", "csv"], default="md")
    p_export.add_argument("--out", type=Path, help="Optional output file path")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    store = VFEXStore()
    try:
        return _dispatch(args, store)
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


def _dispatch(args: argparse.Namespace, store: VFEXStore) -> int:

    if args.command == "price":
        if args.value is not None:
            store.set_price(args.symbol, args.value)
            print(f"{args.symbol.upper()} price set to ${args.value:.4f}")
        else:
            p = store.get_price(args.symbol)
            print(f"{args.symbol.upper()}: ${p:.4f}" if p is not None else f"{args.symbol.upper()}: N/A")
    elif args.command == "fetch":
        res = fetch_vfex_prices(store, force=True)
        print(res["message"])
    elif args.command == "watch":
        if args.action == "list":
            for sym in store.state["watchlist"]:
                p = store.get_price(sym)
                print(f"{sym}: ${p:.4f}" if p is not None else f"{sym}: N/A")
        elif args.action == "add" and args.symbol:
            sym = args.symbol.upper()
            if sym not in store.state["watchlist"]:
                store.state["watchlist"].append(sym)
                store.save()
            print(f"Added {sym} to watchlist.")
        elif args.action == "remove" and args.symbol:
            sym = args.symbol.upper()
            store.state["watchlist"] = [s for s in store.state["watchlist"] if s != sym]
            store.save()
            print(f"Removed {sym} from watchlist.")
    elif args.command == "buy":
        store.buy(args.symbol, args.shares, args.price, date=args.date)
        print(f"Bought {args.shares:g} {args.symbol.upper()} @ ${args.price:.4f}")
    elif args.command == "sell":
        realized = store.sell(args.symbol, args.shares, price=args.price, date=args.date)
        rsign = "+" if realized >= 0 else ""
        print(f"Sold {args.shares:g} {args.symbol.upper()} (Realized P&L: {rsign}${realized:.2f})")
    elif args.command == "history":
        trades = store.state.get("trades", [])
        if not trades:
            print("No trades recorded yet.")
        else:
            for t in trades:
                pnl_part = f" | P&L {'+' if t['realized_pnl'] >= 0 else ''}${t['realized_pnl']:.2f}" if t["action"] == "SELL" else ""
                print(f"{t['date']}  {t['action']:<4}  {t['symbol']:<6}  {t['shares']:g} sh @ ${t['price']:.4f}{pnl_part}")
    elif args.command == "portfolio":
        summary = store.portfolio_summary()
        if not summary["items"]:
            print("Portfolio is empty. Use `vfex buy <SYMBOL> <SHARES> <PRICE>` to add holdings.")
            return 0
        for item in summary["items"]:
            sign = "+" if item["pnl"] >= 0 else ""
            print(
                f"{item['symbol']:<6} {item['shares']:>8g} sh | avg ${item['avg_cost']:.4f} | cur ${item['price']:.4f} | val ${item['value']:.2f} | P&L {sign}${item['pnl']:.2f} ({sign}{item['pnl_pct']:.1f}%)"
            )
        tsign = "+" if summary["total_pnl"] >= 0 else ""
        print(f"\nTotal Value: ${summary['total_value']:.2f} | Cost: ${summary['total_cost']:.2f} | P&L: {tsign}${summary['total_pnl']:.2f} ({tsign}{summary['total_pnl_pct']:.1f}%)")
    elif args.command == "alert":
        if args.action == "add" and args.symbol and args.direction and args.target is not None:
            store.add_alert(args.symbol, args.direction, args.target)
            print(f"Alert added: {args.symbol.upper()} {args.direction} ${args.target:.4f}")
        elif args.action == "list":
            for idx, a in enumerate(store.state["alerts"]):
                status = "TRIGGERED" if a["triggered"] else "ACTIVE"
                print(f"[{idx}] [{status}] {a['symbol']} {a['direction']} ${a['target']:.4f}")
        elif args.action == "check":
            hits = store.check_alerts(notify=True)
            print(f"Triggered {len(hits)} alert(s).")
        elif args.action == "remove" and args.symbol is not None:
            store.remove_alert(int(args.symbol))
            print(f"Removed alert #{args.symbol}.")
        elif args.action == "clear":
            cleared = store.clear_triggered_alerts()
            print(f"Cleared {cleared} triggered alert(s).")
    elif args.command == "waybar":
        print(json.dumps(format_waybar(store)))
    elif args.command == "panel-json":
        print(json.dumps(format_panel_json(
            store,
            include_zse=(args.market == "all"),
            discount_pct=args.discount,
            notify_signals=args.notify_signals,
        )))
    elif args.command == "signals":
        sigs = store.trade_signals(discount_pct=args.discount, include_zse=(args.market == "all"))
        if args.json:
            print(json.dumps(sigs))
        elif not sigs:
            print("No trade signals right now.")
        else:
            for s in sigs:
                print(f"[{s['score']}] {s['action']:<4} {s['symbol']:<8} {format_money(s['price'], s['currency'], 4)} ({', '.join(s['reasons'])})")
    elif args.command == "ctrade":
        if args.action == "status":
            print(json.dumps(store.ctrade_status()))
        elif args.action == "logout":
            store.ctrade_logout()
            print("Disconnected C-TRADE account and removed saved credentials.")
        elif args.action == "sync":
            res = store.ctrade_login_and_sync()
            print(res["message"])
        elif args.action == "login":
            pw = sys.stdin.readline().rstrip("\r\n") if args.password_stdin else None
            if pw == "":
                pw = None
            res = store.ctrade_login_and_sync(email=args.email, password=pw)
            print(res["message"])
    elif args.command == "account":
        prov = args.provider
        if args.action == "status":
            print(json.dumps(store.accounts_status()))
        elif args.action == "logout":
            if prov == "all":
                for p in ("ctrade", "vfex_direct", "zse_direct"):
                    store.portal_logout(p)
                print("Disconnected all saved accounts.")
            else:
                store.portal_logout(prov)
                print(f"Disconnected {PORTAL_LABELS.get(prov, prov)}.")
        elif args.action == "sync":
            res = store.portal_sync(provider=prov)
            print(res["message"])
        elif args.action == "verify-mfa":
            if not args.code:
                raise ValueError("--code is required for verify-mfa.")
            res = store.portal_verify_mfa(prov, args.code)
            print(res["message"])
        elif args.action == "login":
            pw = sys.stdin.readline().rstrip("\r\n") if args.password_stdin else None
            if pw == "":
                pw = None
            res = store.portal_login(prov, email=args.email, password=pw)
            print(res["message"])
    elif args.command == "recommend":
        recs = store.buy_recommendations()
        if not recs:
            print("No BUY signals right now.")
        else:
            for r in recs:
                print(f"BUY {r['symbol']}: ${r['price']:.4f} ({', '.join(r['reasons'])})")
    elif args.command == "import":
        count = store.import_csv(Path(args.file))
        print(f"Imported {count} price(s) from {args.file}.")
    elif args.command == "symbols":
        for sym, name in sorted(KNOWN_VFEX_SYMBOLS.items()):
            print(f"{sym:<6} {name}")
    elif args.command == "target":
        if args.action == "list":
            targets = store.get_targets()
            if not targets:
                print("No target allocations set. Use `vfex target set <SYMBOL> <PCT>`.")
            else:
                for sym, pct in sorted(targets.items()):
                    print(f"{sym:<6} {pct:>6.1f}%")
                print(f"Total: {sum(targets.values()):.1f}%")
        elif args.action == "set" and args.symbol and args.pct is not None:
            store.set_target(args.symbol, args.pct)
            print(f"Target for {args.symbol.upper()} set to {args.pct:.1f}%")
        elif args.action == "remove" and args.symbol:
            store.set_target(args.symbol, 0.0)
            print(f"Removed target for {args.symbol.upper()}.")
    elif args.command == "dca":
        res = store.plan_dca(args.budget)
        if args.json:
            print(json.dumps(res))
            return 0
        if not res["plan"]:
            print("No targets, portfolio holdings, or watchlist symbols to plan for.")
            return 0
        print(f"DCA Plan for ${res['budget']:.2f} ({res['mode']}):")
        for row in res["plan"]:
            p_str = f"${row['price']:.4f}" if row["price"] is not None else "N/A"
            print(
                f"  {row['symbol']:<6} cur {row['current_pct']:>5.1f}% -> tgt {row['target_pct']:>5.1f}% | alloc ${row['alloc_usd']:>7.2f} @ {p_str} -> {row['shares']:g} sh (whole: {row['whole_shares']})"
            )
    elif args.command == "dividend":
        if args.action == "add" and args.symbol and args.amount is not None:
            store.add_dividend(args.symbol, args.amount, date=args.date)
            print(f"Recorded ${args.amount:.2f} dividend for {args.symbol.upper()}.")
        elif args.action == "list":
            divs = store.state.get("dividends", [])
            if not divs:
                print("No dividends recorded yet.")
            else:
                for d in divs:
                    print(f"{d['date']}  {d['symbol']:<6}  +${d['amount']:.2f}")
                print(f"Total Dividends: +${sum(float(d['amount']) for d in divs):.2f}")
    elif args.command == "export":
        report = store.export_report(fmt=args.format)
        if args.out:
            args.out.write_text(report, encoding="utf-8")
            print(f"Exported {args.format} report -> {args.out}")
        else:
            print(report, end="")
    return 0


if __name__ == "__main__":
    sys.exit(main())
