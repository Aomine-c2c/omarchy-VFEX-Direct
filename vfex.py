#!/usr/bin/env python3
"""omarchy-VFEX-Direct: Victoria Falls Stock Exchange (VFEX) CLI & Waybar tracker."""

from __future__ import annotations

import argparse
import csv
import io
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

DEFAULT_CONFIG_DIR = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "vfex-direct"

# Common VFEX listed equities (USD-denominated)
KNOWN_VFEX_SYMBOLS: dict[str, str] = {
    "ASUN": "African Sun Limited",
    "AXIA": "Axia Corporation Limited",
    "BIND": "Bindura Nickel Corporation",
    "CALD": "Caledonia Mining Corporation",
    "ECO": "Econet Wireless Zimbabwe",
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
    ) -> None:
        sym = symbol.upper()
        now = datetime.now(timezone.utc)
        today = date or now.date().isoformat()
        price_entry: dict[str, Any] = {
            "price": round(price, 4),
            "source": source,
            "updated_at": now.isoformat(),
        }
        if open_price is not None:
            price_entry["open"] = round(float(open_price), 4)
        if change_pct is not None:
            price_entry["change_pct"] = round(float(change_pct), 2)
        self.state["prices"][sym] = price_entry

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
        self.save()

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

    def portfolio_summary(self) -> dict[str, Any]:
        items = []
        total_cost = 0.0
        total_value = 0.0
        targets = self.state.get("targets", {})
        dividends_list = self.state.get("dividends", [])
        div_by_sym: dict[str, float] = {}
        for d in dividends_list:
            s = str(d.get("symbol", "")).upper()
            div_by_sym[s] = div_by_sym.get(s, 0.0) + float(d.get("amount", 0.0))
        total_dividends = round(sum(div_by_sym.values()), 2)

        for sym, holding in sorted(self.state["portfolio"].items()):
            shares = float(holding["shares"])
            avg_cost = float(holding["avg_cost"])
            cost = shares * avg_cost
            current_price = self.get_price(sym)
            if current_price is None:
                current_price = avg_cost
            value = shares * current_price
            pnl = value - cost
            pnl_pct = (pnl / cost * 100.0) if cost > 0 else 0.0
            total_cost += cost
            total_value += value
            items.append({
                "symbol": sym,
                "shares": shares,
                "avg_cost": avg_cost,
                "price": current_price,
                "value": value,
                "pnl": pnl,
                "pnl_pct": pnl_pct,
                "dividends": round(div_by_sym.get(sym, 0.0), 2),
                "change_pct": self.get_daily_change(sym),
                "candles": self.get_candles(sym),
                "lots": holding.get("lots", []),
                "target_pct": targets.get(sym),
            })
        for item in items:
            item["alloc_pct"] = round((item["value"] / total_value) * 100.0, 1) if total_value > 0 else 0.0
        total_pnl = total_value - total_cost
        total_pnl_pct = (total_pnl / total_cost * 100.0) if total_cost > 0 else 0.0
        realized_pnl = round(float(self.state.get("realized_pnl", 0.0)), 2)
        return {
            "items": items,
            "total_cost": total_cost,
            "total_value": total_value,
            "total_pnl": total_pnl,
            "total_pnl_pct": total_pnl_pct,
            "realized_pnl": realized_pnl,
            "total_dividends": total_dividends,
            "total_return": round(total_pnl + total_dividends + realized_pnl, 2),
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

        targets = {s: float(p) for s, p in self.state.get("targets", {}).items() if float(p) > 0}
        if targets:
            total_t = sum(targets.values())
            weights = {s: p / total_t for s, p in sorted(targets.items())}
            mode = "targets"
        else:
            syms = sorted(set(self.state.get("portfolio", {}).keys()) | set(self.state.get("watchlist", [])))
            if not syms:
                return {"budget": round(budget, 2), "mode": "equal", "plan": []}
            weights = {s: 1.0 / len(syms) for s in syms}
            mode = "equal"

        summary = self.portfolio_summary()
        current_values = {item["symbol"]: float(item["value"]) for item in summary["items"]}
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


def fetch_vfex_prices(
    store: VFEXStore,
    url: str = "https://d3u8q0mxu6epjj.cloudfront.net/api/v1/voms/price-sheets/active",
    force: bool = False,
    ttl_seconds: int = 900,
) -> dict[str, Any]:
    """Fetch VFEX prices when cache TTL (15m default) expires or forced, preserving cached prices on fallback."""
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

    req = urllib.request.Request(url, headers={"User-Agent": "omarchy-VFEX-Direct/0.1", "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            status = resp.status
            payload = json.loads(resp.read().decode("utf-8"))
        data = payload.get("data") or {}
        updated = 0
        if isinstance(data, dict):
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
                        )
                        updated += 1
        store.state["last_fetch_date"] = today
        store.state["last_fetch_at"] = datetime.now(timezone.utc).isoformat()
        store.save()
        return {"ok": True, "cached": False, "status": status, "updated": updated, "message": f"VFEX updated {updated} prices ({today})."}
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, ValueError) as exc:
        return {"ok": False, "cached": True, "status": None, "message": f"Could not reach VFEX ({exc}). Using cached prices."}


def format_waybar(store: VFEXStore) -> dict[str, str]:
    """Build Waybar custom module JSON payload."""
    store.check_alerts(notify=True)
    summary = store.portfolio_summary()
    status_label = get_market_status()
    updated_label = get_last_updated_label(store)
    meta = f"Market: {status_label}" + (f" • Updated {updated_label}" if updated_label else "")
    tooltip_lines = ["VFEX Direct — Portfolio & Watchlist (USD)", meta]

    if summary["items"]:
        pnl = summary["total_pnl"]
        sign = "+" if pnl >= 0 else ""
        text = f"VFEX ${summary['total_value']:.2f} ({sign}${pnl:.2f})"
        css_class = "profit" if pnl >= 0 else "loss"
        tooltip_lines.append("")
        tooltip_lines.append("Holdings:")
        for item in summary["items"]:
            isign = "+" if item["pnl"] >= 0 else ""
            chg = item.get("change_pct")
            chg_str = f" | {'+' if chg >= 0 else ''}{chg:.1f}% today" if chg is not None else ""
            tooltip_lines.append(
                f"  {item['symbol']}: {item['shares']:g} @ ${item['price']:.4f} ({isign}${item['pnl']:.2f} / {isign}{item['pnl_pct']:.1f}%{chg_str})"
            )
    else:
        watch = store.state.get("watchlist", [])
        if watch:
            first = watch[0]
            p = store.get_price(first)
            chg = store.get_daily_change(first)
            chg_str = f" ({'+' if chg >= 0 else ''}{chg:.1f}%)" if chg is not None else ""
            text = f"VFEX {first} ${p:.4f}{chg_str}" if p is not None else f"VFEX {first} --"
        else:
            text = "VFEX --"
        css_class = "neutral"

    watch = store.state.get("watchlist", [])
    if watch:
        tooltip_lines.append("")
        tooltip_lines.append("Watchlist:")
        for sym in watch:
            p = store.get_price(sym)
            p_str = f"${p:.4f}" if p is not None else "N/A"
            chg = store.get_daily_change(sym)
            chg_str = f" ({'+' if chg >= 0 else ''}{chg:.1f}%)" if chg is not None else ""
            tooltip_lines.append(f"  {sym}: {p_str}{chg_str}")

    return {"text": text, "tooltip": "\n".join(tooltip_lines), "class": css_class}


def format_panel_json(store: VFEXStore) -> dict[str, Any]:
    """Build structured JSON for BarWidget.qml and Panel.qml."""
    fetch_res = fetch_vfex_prices(store, force=False)
    store.check_alerts(notify=True)
    wb = format_waybar(store)
    summary = store.portfolio_summary()
    recs = {r["symbol"]: r for r in store.buy_recommendations()}
    watchlist_items = []
    history_map = store.state.get("history", {})
    for sym in store.state.get("watchlist", []):
        hist = [h.get("close", h.get("price")) for h in history_map.get(sym, []) if ("close" in h or "price" in h)]
        watchlist_items.append({
            "symbol": sym,
            "price": store.get_price(sym),
            "buy": sym in recs,
            "history": hist,
            "candles": store.get_candles(sym),
            "change_pct": store.get_daily_change(sym),
        })

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
        "items": summary["items"],
        "watchlist": watchlist_items,
        "recommendations": list(recs.values()),
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
    sub.add_parser("panel-json", help="Output structured JSON for Omarchy BarWidget/Panel")
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
        print(json.dumps(format_panel_json(store)))
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
