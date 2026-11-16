# omarchy-VFEX-Direct

A lightweight **Victoria Falls Stock Exchange (VFEX)** portfolio tracker, price alert tool, and **Waybar** status bar plugin for Omarchy.

## Features

- **Portfolio & Lot Tracking (USD):** Record `buy` / `sell` trades with FIFO lot reduction, purchase dates, realized & unrealized P&L, and full trade ledger (`history`).
- **Dividends & Total Return:** Record cash dividends per symbol and view combined total return.
- **Target Allocations & DCA Planner:** Set target `%` per symbol and compute share allocations for any USD budget (`vfex dca <USD>`).
- **Watchlist, Sparklines & Daily % Change:** Track VFEX symbols with inline 30-day sparklines, daily `%` moves, and `BUY` recommendations.
- **Price Alerts & Market Status:** Desktop notifications (`notify-send`), persistent triggered/active alerts in the panel, VFEX market hours (`Open`/`Closed` CAT), and 15-minute auto-fetch TTL.
- **Omarchy & Waybar Integration:** Quickshell `BarWidget.qml` / `Panel.qml` with interactive Manual Entry (`Price`, `Buy`, `Sell`, `+Watch`, `Alert`, `Div`, `Target`, `DCA`) and `Enter`/`Tab` keyboard navigation.
- **Export:** Export holdings, trade ledger, and dividends to Markdown or CSV (`vfex export`).

## Installation

```bash
./install.sh
```

This symlinks `vfex.py` to `~/.local/bin/vfex` and symlinks `Panel.qml`, `BarWidget.qml`, `manifest.json`, and `vfex.py` into `~/.config/omarchy/plugins/io.github.aomine-c2c.vfex-direct/`.

## CLI Usage

```bash
# List known VFEX symbols & fetch live prices
vfex symbols
vfex fetch

# Update or check a stock price (USD)
vfex price INFR 0.25

# Record trades, view portfolio & trade ledger
vfex buy INFR 100 0.24
vfex sell INFR 50 0.28
vfex portfolio
vfex history

# Record dividends
vfex dividend add INFR 2.50
vfex dividend list

# Target allocations & DCA planner
vfex target set INFR 50
vfex target set SIM 50
vfex dca 100

# Manage watchlist & price alerts
vfex watch add INFR
vfex alert add INFR above 0.30
vfex alert list
vfex alert clear

# Export report & JSON outputs
vfex export --format md
vfex export --format csv --out report.csv
vfex panel-json
vfex waybar
```

## Waybar Setup

1. Add the module from `waybar/config.jsonc` to your `~/.config/waybar/config.jsonc` (`modules-right` or `modules-center`).
2. Add the styles from `waybar/style.css` to your `~/.config/waybar/style.css`.
3. Reload Waybar.
