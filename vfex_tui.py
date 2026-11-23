#!/usr/bin/env python3
"""
NOTHING Investment Terminal — Complementary Curses TUI (vfex-tui)
-----------------------------------------------------------------
Zero-dependency, keyboard-first terminal interface for Omarchy Linux
(Alacritty / Ghostty / Kitty / Foot).

Keys:
  1: Overview & Portfolio   2: Holdings      3: Market Watch (VFEX/ZSE)
  4: Watchlist              5: Newsroom      6: Alerts & Mahoraga AI
  r: Refresh data           q: Quit
"""

from __future__ import annotations

import curses
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
import vfex


def load_snapshot() -> dict[str, Any]:
    store = vfex.VFEXStore()
    return vfex.format_panel_json(store)


def render_tab_lines(tab: int, data: dict[str, Any]) -> list[str]:
    lines: list[str] = []
    if tab == 1:
        lines.append(f"  TOTAL PORTFOLIO VALUE (USD):  ${float(data.get('total_value') or 0):,.2f}")
        lines.append(f"  UNREALISED P&L (USD):         ${float(data.get('total_pnl') or 0):+,.2f} ({float(data.get('total_pnl_pct') or 0):+.2f}%)")
        lines.append(f"  AVAILABLE CASH:               USD ${float(data.get('wallet_cash_usd') or 0):,.2f}  |  ZWG {float(data.get('wallet_cash_zwg') or 0):,.2f}")
        lines.append(f"  MARKET STATUS:                {data.get('market_status', 'Closed')} ({data.get('market_countdown', '')})")
        ag = data.get("paper_agent") or {}
        gk = ag.get("grok") or {}
        lines.append(f"  MAHORAGA AI:                  Equity ${float(ag.get('equity_usd') or 0):,.2f} ({float(ag.get('net_pnl_pct') or 0):+.2f}%) | {gk.get('status', 'Ready')}")
    elif tab == 2:
        lines.append(f"  {'SYMBOL':<8} {'QTY':>8} {'AVG COST':>10} {'LAST':>10} {'VALUE':>10} {'P&L %':>8}")
        lines.append("  " + "-" * 60)
        for it in data.get("items") or []:
            lines.append(f"  {str(it.get('symbol','')):<8} {float(it.get('shares') or 0):>8.0f} {float(it.get('avg_cost') or 0):>10.4f} {float(it.get('price') or 0):>10.4f} {float(it.get('value') or 0):>10.2f} {float(it.get('pnl_pct') or 0):>+7.2f}%")
        if not (data.get("items") or []):
            lines.append("  No holdings recorded.")
    elif tab == 3:
        lines.append(f"  {'COUNTER':<8} {'CUR':<4} {'PRICE':>10} {'CHG %':>8} {'LIQ':>5} {'SIGNAL':<10} COMPANY")
        lines.append("  " + "-" * 72)
        for r in (data.get("screener") or [])[:25]:
            sig = f"{r.get('signal_action') or '--'} {r.get('signal_score') or ''}".strip()
            lines.append(f"  {str(r.get('symbol','')):<8} {str(r.get('currency','USD')):<4} {float(r.get('price') or 0):>10.4f} {float(r.get('change_pct') or 0):>+7.2f}% {float(r.get('liquidity_score') or 0):>5.0f} {sig:<10} {str(r.get('company_name',''))[:28]}")
    elif tab == 4:
        lines.append(f"  {'WATCH':<8} {'CUR':<4} {'PRICE':>10} {'CHG %':>8} {'SPREAD %':>9}")
        lines.append("  " + "-" * 48)
        for w in data.get("watchlist") or []:
            lines.append(f"  {str(w.get('symbol','')):<8} {str(w.get('currency','USD')):<4} {float(w.get('price') or 0):>10.4f} {float(w.get('change_pct') or 0):>+7.2f}% {float(w.get('spread_pct') or 0):>8.2f}%")
    elif tab == 5:
        for n in (data.get("news") or [])[:18]:
            tag = "OFFICIAL" if n.get("official") else "NEWS"
            lines.append(f"  [{tag:<8}] ({n.get('age_label','')}) {str(n.get('title',''))[:68]}")
    elif tab == 6:
        ag = data.get("paper_agent") or {}
        lines.append("  ALERTS & MAHORAGA AI ACTIVITY")
        lines.append("  " + "-" * 60)
        for a in (data.get("triggered_alerts") or data.get("active_alerts") or [])[:6]:
            lines.append(f"  ALERT: {a.get('symbol')} {a.get('direction')} {a.get('target_price')}")
        for les in (ag.get("lessons") or [])[-8:]:
            lines.append(f"  [{les.get('date')}] {les.get('summary','')[:68]}")
    return lines


def _tui_main(stdscr: Any) -> None:
    curses.curs_set(0)
    stdscr.nodelay(False)
    tab = 1
    data = load_snapshot()

    while True:
        stdscr.erase()
        h, w = stdscr.getmaxyx()
        header = " NOTHING // INVESTMENT TERMINAL (TUI)  |  [1]Overview [2]Holdings [3]Markets [4]Watch [5]News [6]AI  [r]Refresh [q]Quit "
        stdscr.addnstr(0, 0, header.ljust(w), w - 1, curses.A_REVERSE)
        lines = render_tab_lines(tab, data)
        for idx, line in enumerate(lines[: max(1, h - 3)]):
            stdscr.addnstr(idx + 2, 0, line, w - 1)
        stdscr.refresh()
        ch = stdscr.getch()
        if ch in (ord("q"), ord("Q"), 27):
            break
        elif ch in (ord("1"), ord("2"), ord("3"), ord("4"), ord("5"), ord("6")):
            tab = int(chr(ch))
        elif ch in (ord("r"), ord("R")):
            data = load_snapshot()


def main() -> int:
    if "--dump" in sys.argv:
        data = load_snapshot()
        print("\n".join(render_tab_lines(1, data)))
        return 0
    curses.wrapper(_tui_main)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
