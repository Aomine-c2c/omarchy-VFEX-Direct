# omarchy-VFEX-Direct

A lightweight **Victoria Falls Stock Exchange (VFEX)** portfolio tracker, price alert tool, and **Waybar** status bar plugin for Omarchy.

## Features

- **Portfolio Tracking (USD):** Record `buy` / `sell` trades, average cost basis, and live P&L.
- **Watchlist & Quotes:** Track VFEX symbols (`INSC`, `SIM`, `PHL`, `CALD`, `SCIL`, etc.).
- **Price Alerts:** Desktop notifications via `notify-send` when a stock crosses your target price.
- **Waybar Integration:** JSON status bar output with profit/loss styling and hover tooltip.

## Installation

```bash
./install.sh
```

This symlinks `vfex.py` to `~/.local/bin/vfex`.

## CLI Usage

```bash
# List known VFEX symbols
vfex symbols

# Update a stock price (USD)
vfex price INSC 0.45

# Record a purchase & view portfolio
vfex buy INSC 100 0.42
vfex portfolio

# Manage watchlist
vfex watch add CALD
vfex watch list

# Set a price alert
vfex alert add INSC above 0.50
vfex alert check

# Output Waybar JSON
vfex waybar
```

## Waybar Setup

1. Add the module from `waybar/config.jsonc` to your `~/.config/waybar/config.jsonc` (`modules-right` or `modules-center`).
2. Add the styles from `waybar/style.css` to your `~/.config/waybar/style.css`.
3. Reload Waybar.
