#!/usr/bin/env python3
"""omarchy-VFEX-Direct: Victoria Falls Stock Exchange (VFEX) CLI & Waybar tracker."""

from __future__ import annotations

import argparse
import csv
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
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
        }

    def save(self) -> None:
        self.state_file.write_text(json.dumps(self.state, indent=2) + "\n", encoding="utf-8")

    def set_price(self, symbol: str, price: float, source: str = "manual") -> None:
        sym = symbol.upper()
        now = datetime.now(timezone.utc)
        today = now.date().isoformat()
        self.state["prices"][sym] = {
            "price": round(price, 4),
            "source": source,
            "updated_at": now.isoformat(),
        }
        history = self.state.setdefault("history", {}).setdefault(sym, [])
        if history and history[-1].get("date") == today:
            history[-1]["price"] = round(price, 4)
        else:
            history.append({"date": today, "price": round(price, 4)})
            if len(history) > 30:
                self.state["history"][sym] = history[-30:]
        self.save()

    def get_price(self, symbol: str) -> float | None:
        entry = self.state["prices"].get(symbol.upper())
        return float(entry["price"]) if entry else None

    def buy(self, symbol: str, shares: float, price: float) -> None:
        if shares <= 0 or price < 0:
            raise ValueError("Shares must be positive and price non-negative.")
        sym = symbol.upper()
        holding = self.state["portfolio"].get(sym, {"shares": 0.0, "avg_cost": 0.0})
        old_shares = float(holding["shares"])
        old_cost = float(holding["avg_cost"])
        new_shares = old_shares + shares
        new_avg = ((old_shares * old_cost) + (shares * price)) / new_shares
        self.state["portfolio"][sym] = {
            "shares": round(new_shares, 6),
            "avg_cost": round(new_avg, 4),
        }
        if sym not in self.state["prices"]:
            self.set_price(sym, price, source="trade")
        else:
            self.save()

    def sell(self, symbol: str, shares: float) -> None:
        if shares <= 0:
            raise ValueError("Shares must be positive.")
        sym = symbol.upper()
        holding = self.state["portfolio"].get(sym)
        if not holding or float(holding["shares"]) < shares:
            raise ValueError(f"Insufficient shares of {sym} to sell.")
        remaining = float(holding["shares"]) - shares
        if remaining <= 1e-9:
            del self.state["portfolio"][sym]
        else:
            holding["shares"] = round(remaining, 6)
        self.save()

    def portfolio_summary(self) -> dict[str, Any]:
        items = []
        total_cost = 0.0
        total_value = 0.0
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
            })
        total_pnl = total_value - total_cost
        total_pnl_pct = (total_pnl / total_cost * 100.0) if total_cost > 0 else 0.0
        return {
            "items": items,
            "total_cost": total_cost,
            "total_value": total_value,
            "total_pnl": total_pnl,
            "total_pnl_pct": total_pnl_pct,
        }

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


def send_notification(title: str, body: str) -> None:
    """Send a desktop notification via notify-send if available."""
    try:
        subprocess.run(["notify-send", title, body], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except FileNotFoundError:
        pass


def fetch_vfex_prices(
    store: VFEXStore,
    url: str = "https://d3u8q0mxu6epjj.cloudfront.net/api/v1/voms/price-sheets/active",
    force: bool = False,
) -> dict[str, Any]:
    """Fetch VFEX prices once per day (or when forced), preserving cached prices on fallback."""
    today = datetime.now(timezone.utc).date().isoformat()
    if not force and store.state.get("last_fetch_date") == today:
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
                        store.set_price(sym, float(raw_price), source="vfex-direct")
                        updated += 1
        store.state["last_fetch_date"] = today
        store.save()
        return {"ok": True, "cached": False, "status": status, "updated": updated, "message": f"VFEX updated {updated} prices ({today})."}
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, ValueError) as exc:
        return {"ok": False, "cached": True, "status": None, "message": f"Could not reach VFEX ({exc}). Using cached prices."}


def format_waybar(store: VFEXStore) -> dict[str, str]:
    """Build Waybar custom module JSON payload."""
    store.check_alerts(notify=True)
    summary = store.portfolio_summary()
    tooltip_lines = ["VFEX Direct — Portfolio & Watchlist (USD)"]

    if summary["items"]:
        pnl = summary["total_pnl"]
        sign = "+" if pnl >= 0 else ""
        text = f"VFEX ${summary['total_value']:.2f} ({sign}${pnl:.2f})"
        css_class = "profit" if pnl >= 0 else "loss"
        tooltip_lines.append("")
        tooltip_lines.append("Holdings:")
        for item in summary["items"]:
            isign = "+" if item["pnl"] >= 0 else ""
            tooltip_lines.append(
                f"  {item['symbol']}: {item['shares']:g} @ ${item['price']:.4f} ({isign}${item['pnl']:.2f} / {isign}{item['pnl_pct']:.1f}%)"
            )
    else:
        watch = store.state.get("watchlist", [])
        if watch:
            first = watch[0]
            p = store.get_price(first)
            text = f"VFEX {first} ${p:.4f}" if p is not None else f"VFEX {first} --"
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
            tooltip_lines.append(f"  {sym}: {p_str}")

    return {"text": text, "tooltip": "\n".join(tooltip_lines), "class": css_class}


def format_panel_json(store: VFEXStore) -> dict[str, Any]:
    """Build structured JSON for BarWidget.qml and Panel.qml."""
    fetch_vfex_prices(store, force=False)
    wb = format_waybar(store)
    summary = store.portfolio_summary()
    recs = {r["symbol"]: r for r in store.buy_recommendations()}
    watchlist_items = []
    for sym in store.state.get("watchlist", []):
        watchlist_items.append({"symbol": sym, "price": store.get_price(sym), "buy": sym in recs})
    return {
        **wb,
        "total_value": round(summary["total_value"], 2),
        "total_cost": round(summary["total_cost"], 2),
        "total_pnl": round(summary["total_pnl"], 2),
        "total_pnl_pct": round(summary["total_pnl_pct"], 2),
        "items": summary["items"],
        "watchlist": watchlist_items,
        "recommendations": list(recs.values()),
        "alerts": store.check_alerts(notify=False),
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

    p_sell = sub.add_parser("sell", help="Record a stock sale")
    p_sell.add_argument("symbol")
    p_sell.add_argument("shares", type=float)

    sub.add_parser("portfolio", help="Show portfolio holdings and P&L")

    p_alert = sub.add_parser("alert", help="Manage price alerts")
    p_alert.add_argument("action", choices=["add", "list", "check"])
    p_alert.add_argument("symbol", nargs="?")
    p_alert.add_argument("direction", nargs="?", choices=["above", "below"])
    p_alert.add_argument("target", nargs="?", type=float)

    sub.add_parser("waybar", help="Output Waybar JSON")
    sub.add_parser("panel-json", help="Output structured JSON for Omarchy BarWidget/Panel")
    sub.add_parser("recommend", help="Show BUY recommendations based on 30d avg and targets")
    p_import = sub.add_parser("import", help="Import prices from a CSV file (symbol,price)")
    p_import.add_argument("file", help="Path to CSV file")
    sub.add_parser("symbols", help="List known VFEX symbols")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    store = VFEXStore()

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
        store.buy(args.symbol, args.shares, args.price)
        print(f"Bought {args.shares:g} {args.symbol.upper()} @ ${args.price:.4f}")
    elif args.command == "sell":
        store.sell(args.symbol, args.shares)
        print(f"Sold {args.shares:g} {args.symbol.upper()}")
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
            for a in store.state["alerts"]:
                status = "TRIGGERED" if a["triggered"] else "ACTIVE"
                print(f"[{status}] {a['symbol']} {a['direction']} ${a['target']:.4f}")
        elif args.action == "check":
            hits = store.check_alerts(notify=True)
            print(f"Triggered {len(hits)} alert(s).")
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
    return 0


if __name__ == "__main__":
    sys.exit(main())
