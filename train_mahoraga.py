#!/usr/bin/env python3
"""
Mahoraga Foundation Brain v3 Trainer (3-Model Deep Residual MLP Ensemble)
-------------------------------------------------------------------------
Downloads up to 15y daily OHLCV across ~310 global, EM/Africa/JSE, commodity,
bond, FX, and crypto instruments + news sentiment into ~/.cache/vfex/training_data/
(outside git), builds ~500k strictly chronological zero-lookahead multi-horizon
episodes (5d swing + 20d core), trains a 3-model Deep Residual MLP Ensemble
(16 -> 128 -> 64 -> 4 with LayerNorm + skip connections + Dropout + Grokfast EMA)
on walk-forward OOS splits, and exports a compact (~300-500 KB) JSON weights file
(mahoraga_weights.json) for zero-dependency pure-Python inference in vfex.py.
"""

from __future__ import annotations

import concurrent.futures
import json
import math
import sys
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np

CACHE_DIR = Path.home() / ".cache" / "vfex" / "training_data"
PRICES_CACHE_DIR = CACHE_DIR / "ohlcv"
NEWS_CACHE_FILE = CACHE_DIR / "news_sentiment.json"
WEIGHTS_OUT = Path(__file__).resolve().parent / "mahoraga_weights.json"

FEATURE_KEYS = [
    "bias",
    "dip",
    "rsi_oversold",
    "book",
    "news",
    "volume",
    "regime",
    "spread",
    "zse",
    "mom_5d",
    "mom_20d",
    "trend_ma",
    "vol_20d",
    "drawdown_60d",
    "macro_gold",
    "macro_vix",
]

# ~310 curated cross-asset instruments spanning the global financial world
MARKET_UNIVERSE = sorted(set([
    # Macro, Indices & Broad ETFs
    "^GSPC", "^IXIC", "^DJI", "^RUT", "^VIX", "^TNX", "^TYX", "^FVX", "DX-Y.NYB",
    "SPY", "QQQ", "IWM", "DIA", "VTI", "VEA", "VWO", "EEM", "EFA", "VGK", "EWJ",
    "AFK", "EZA", "EWZ", "INDA", "FXI", "MCHI", "EWY", "EWT", "EWW", "EWC", "EWA",
    "EWU", "EWG", "EWQ", "EWP", "EWI", "TUR", "ARGT", "KSA", "UAE", "FM",
    # Sector ETFs
    "XLK", "XLF", "XLE", "XLV", "XLI", "XLP", "XLU", "XLY", "XLB", "XLRE", "XLC",
    "SMH", "SOXX", "XBI", "KRE", "XHB", "XRT", "XOP", "OIH", "TAN", "LIT", "URA",
    # Commodities & Miners (Critical for VFEX / Zimbabwe macro)
    "GC=F", "PL=F", "PA=F", "SI=F", "HG=F", "CL=F", "BZ=F", "NG=F",
    "ZC=F", "ZW=F", "ZS=F", "KC=F", "SB=F", "CT=F",
    "GLD", "SLV", "PPLT", "GDX", "GDXJ", "SIL", "COPX", "USO", "UNG", "DBA", "DBC",
    "BHP", "RIO", "VALE", "NEM", "GOLD", "AEM", "WPM", "FNV", "KGC", "AU", "GFI",
    "HMY", "SBSW", "FCX", "SCCO", "TECK", "AA", "NUE", "STLD", "CLF", "MOS", "NTR", "CF",
    # Africa / JSE Blue-Chips
    "SBK.JO", "FSR.JO", "NED.JO", "ABG.JO", "CPI.JO", "NPN.JO", "PRX.JO",
    "MTN.JO", "VOD.JO", "SOL.JO", "SHP.JO", "WHL.JO", "BID.JO", "BVT.JO",
    "ANG.JO", "GFI.JO", "HAR.JO", "IMP.JO", "SSW.JO", "AMS.JO", "NPH.JO",
    "AGL.JO", "KIO.JO", "EXX.JO", "REM.JO", "SLM.JO", "DSY.JO", "OMU.JO",
    "BTI.JO", "CFR.JO", "APN.JO", "MRP.JO", "TFG.JO", "TBS.JO", "CLS.JO",
    # Bonds & Credit
    "TLT", "IEF", "SHY", "AGG", "BND", "LQD", "HYG", "JNK", "EMB", "TIP", "MUB",
    # FX
    "ZAR=X", "EURUSD=X", "GBPUSD=X", "JPY=X", "AUDUSD=X", "CAD=X", "CHF=X",
    "CNY=X", "BRL=X", "MXN=X", "INR=X", "TRY=X",
    # Crypto (24/7 high-volatility regime dynamics)
    "BTC-USD", "ETH-USD", "SOL-USD", "BNB-USD", "XRP-USD", "ADA-USD",
    # US Technology
    "AAPL", "MSFT", "NVDA", "GOOGL", "AMZN", "META", "TSLA", "AVGO", "ORCL", "CRM",
    "ADBE", "AMD", "INTC", "QCOM", "TXN", "AMAT", "LRCX", "KLAC", "MU", "MRVL",
    "NOW", "INTU", "PANW", "CRWD", "SNOW", "PLTR", "NFLX", "UBER", "ABNB", "SHOP",
    "IBM", "CSCO", "ACN", "HPQ", "DELL", "ADI", "NXPI", "SNPS", "CDNS", "FTNT",
    # US Financials
    "JPM", "BAC", "WFC", "C", "GS", "MS", "BLK", "SCHW", "AXP", "V", "MA", "PYPL",
    "SPGI", "MCO", "ICE", "CME", "CB", "PGR", "TRV", "MET", "PRU", "AFL", "ALL",
    "USB", "PNC", "TFC", "COF", "BX", "KKR", "APO", "COIN", "HOOD",
    # US Healthcare
    "JNJ", "UNH", "LLY", "ABBV", "MRK", "PFE", "TMO", "ABT", "DHR", "BMY", "AMGN",
    "GILD", "VRTX", "REGN", "ISRG", "MDT", "SYK", "BSX", "CI", "CVS", "ELV", "HCA",
    "ZTS", "BDX", "EW", "IDXX", "MRNA", "BIIB",
    # US Consumer Discretionary & Staples
    "WMT", "COST", "PG", "KO", "PEP", "PM", "MO", "MDLZ", "CL", "KMB", "GIS", "SYY",
    "HD", "LOW", "MCD", "SBUX", "NKE", "TJX", "BKNG", "MAR", "HLT", "CMG", "TGT",
    "DG", "DLTR", "ROST", "GM", "F", "RCL", "CCL", "DIS", "CMCSA", "TMUS", "VZ", "T",
    # US Industrials, Energy, Utilities, Real Estate
    "XOM", "CVX", "COP", "SLB", "EOG", "MPC", "PSX", "VLO", "OXY", "HAL", "KMI", "WMB",
    "CAT", "DE", "BA", "HON", "UNP", "UPS", "FDX", "RTX", "LMT", "GD", "NOC", "GE",
    "MMM", "ETN", "EMR", "ITW", "PH", "WM", "RSG", "CSX", "NSC", "DAL", "UAL", "LUV",
    "NEE", "DUK", "SO", "D", "AEP", "EXC", "SRE", "XEL", "ED", "AWK",
    "PLD", "AMT", "CCI", "EQIX", "PSA", "O", "SPG", "DLR", "VICI", "WELL",
    # Global ADRs (Europe, Asia, LatAm)
    "ASML", "NVO", "SAP", "SHEL", "TTE", "BP", "UL", "HSBC", "UBS", "SNY", "AZN", "GSK",
    "TSM", "BABA", "JD", "PDD", "BIDU", "SONY", "TM", "HDB", "IBN", "INFY",
    "MELI", "NU", "PBR", "ITUB", "BBD", "AMX", "FMX", "SQM",
]))

NEWS_RSS_FEEDS = [
    "https://feeds.finance.yahoo.com/rss/2.0/headline?s=%5EGSPC,GC=F,EEM,AFK,EZA&region=US&lang=en-US",
    "https://feeds.marketwatch.com/marketwatch/topstories/",
    "https://feeds.marketwatch.com/marketwatch/marketpulse/",
]

POS_WORDS = {
    "rally", "surge", "gain", "gains", "beat", "beats", "record", "growth",
    "upgrade", "bullish", "profit", "profits", "dividend", "expansion",
    "strong", "outperform", "rebound", "jump", "soar", "higher", "positive",
}
NEG_WORDS = {
    "crash", "plunge", "drop", "drops", "fall", "falls", "miss", "misses",
    "loss", "losses", "downgrade", "bearish", "recession", "inflation",
    "default", "slump", "weak", "warn", "warning", "risk", "lower", "cut",
    "selloff", "crisis", "decline", "tumble", "fear", "tariff", "sanction",
}

HEADERS = {"User-Agent": "Mozilla/5.0"}


def _http_get(url: str, timeout: int = 15) -> bytes | None:
    req = urllib.request.Request(url, headers=HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read()
    except Exception:
        return None


def fetch_yahoo_ohlcv(symbol: str, range_str: str = "15y", force: bool = False) -> list[dict[str, Any]]:
    """Fetch daily OHLCV bars from Yahoo Finance public chart API with local cache."""
    PRICES_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    safe_name = symbol.replace("/", "_").replace("^", "IDX_").replace("=", "_")
    cache_file = PRICES_CACHE_DIR / f"{safe_name}.json"

    if not force and cache_file.exists():
        age_hours = (time.time() - cache_file.stat().st_mtime) / 3600.0
        if age_hours < 24.0:
            try:
                data = json.loads(cache_file.read_text(encoding="utf-8"))
                if isinstance(data, list) and len(data) > 50:
                    return data
            except Exception:
                pass

    q_sym = urllib.parse.quote(symbol, safe="")
    raw = None
    for host in ("query2.finance.yahoo.com", "query1.finance.yahoo.com"):
        url = f"https://{host}/v8/finance/chart/{q_sym}?range={range_str}&interval=1d&includeAdjustedClose=true"
        raw = _http_get(url, timeout=15)
        if raw:
            break
        time.sleep(0.25)
    if not raw:
        return []
    try:
        payload = json.loads(raw.decode("utf-8", errors="ignore"))
        result = (payload.get("chart") or {}).get("result") or []
        if not result:
            return []
        res0 = result[0]
        timestamps = res0.get("timestamp") or []
        quote = ((res0.get("indicators") or {}).get("quote") or [{}])[0]
        adj_list = ((res0.get("indicators") or {}).get("adjclose") or [{}])[0].get("adjclose") or []
        opens = quote.get("open") or []
        highs = quote.get("high") or []
        lows = quote.get("low") or []
        closes = quote.get("close") or []
        vols = quote.get("volume") or []

        bars: list[dict[str, Any]] = []
        seen_dates: set[str] = set()
        for i, ts in enumerate(timestamps):
            if ts is None or i >= len(closes):
                continue
            c = adj_list[i] if (i < len(adj_list) and adj_list[i] is not None) else closes[i]
            if c is None or c <= 0:
                continue
            dt = datetime.fromtimestamp(int(ts), tz=timezone.utc).date().isoformat()
            if dt in seen_dates:
                continue
            seen_dates.add(dt)
            o = opens[i] if (i < len(opens) and opens[i] is not None and opens[i] > 0) else c
            h = highs[i] if (i < len(highs) and highs[i] is not None and highs[i] > 0) else max(o, c)
            l = lows[i] if (i < len(lows) and lows[i] is not None and lows[i] > 0) else min(o, c)
            v = vols[i] if (i < len(vols) and vols[i] is not None and vols[i] >= 0) else 0.0
            raw_c = closes[i]
            if raw_c and raw_c > 0 and abs(c - raw_c) / raw_c > 1e-4:
                ratio = c / raw_c
                o, h, l = o * ratio, h * ratio, l * ratio
            bars.append({
                "date": dt,
                "open": round(float(o), 6),
                "high": round(float(h), 6),
                "low": round(float(l), 6),
                "close": round(float(c), 6),
                "volume": float(v),
            })
        bars.sort(key=lambda r: r["date"])
        if len(bars) > 30:
            cache_file.write_text(json.dumps(bars), encoding="utf-8")
        return bars
    except Exception:
        return []


def fetch_news_sentiment(force: bool = False) -> dict[str, float]:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    by_date: dict[str, list[float]] = {}
    if NEWS_CACHE_FILE.exists():
        try:
            existing = json.loads(NEWS_CACHE_FILE.read_text(encoding="utf-8"))
            if isinstance(existing, dict):
                for k, v in existing.items():
                    by_date.setdefault(k, []).append(float(v))
        except Exception:
            pass

    for url in NEWS_RSS_FEEDS:
        raw = _http_get(url, timeout=10)
        if not raw:
            continue
        try:
            root = ET.fromstring(raw)
            for item in root.findall(".//item"):
                title = (item.findtext("title") or "").lower()
                pub = item.findtext("pubDate") or ""
                words = set(w.strip(".,!?:;()[]{}\"'") for w in title.split())
                pos = len(words & POS_WORDS)
                neg = len(words & NEG_WORDS)
                if pos == 0 and neg == 0:
                    continue
                score = max(-1.5, min(1.5, (pos - neg) * 0.45))
                dt_str = datetime.now(timezone.utc).date().isoformat()
                if pub:
                    for fmt in ("%a, %d %b %Y %H:%M:%S %z", "%a, %d %b %Y %H:%M:%S GMT"):
                        try:
                            dt_str = datetime.strptime(pub.strip(), fmt).date().isoformat()
                            break
                        except Exception:
                            pass
                by_date.setdefault(dt_str, []).append(score)
        except Exception:
            continue

    agg = {dt: round(sum(vals) / len(vals), 4) for dt, vals in by_date.items() if vals}
    NEWS_CACHE_FILE.write_text(json.dumps(agg, indent=2), encoding="utf-8")
    return agg


def download_all_data(force: bool = False) -> tuple[dict[str, list[dict[str, Any]]], dict[str, float]]:
    print(f"[1/4] Downloading {len(MARKET_UNIVERSE)} cross-asset series (up to 15y daily, cached)...")
    series_map: dict[str, list[dict[str, Any]]] = {}

    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as ex:
        futs = {ex.submit(fetch_yahoo_ohlcv, sym, "15y", force): sym for sym in MARKET_UNIVERSE}
        for fut in concurrent.futures.as_completed(futs):
            sym = futs[fut]
            bars = fut.result()
            if len(bars) >= 60:
                series_map[sym] = bars

    vfex_count = 0
    try:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        import vfex
        store = vfex.VFEXStore()
        for sym, rows in (store.state.get("history") or {}).items():
            clean = []
            seen = set()
            for r in rows:
                dt = str(r.get("date") or "")
                c = float(r.get("close", r.get("price")) or 0.0)
                if dt and c > 0 and dt not in seen:
                    seen.add(dt)
                    clean.append({
                        "date": dt,
                        "open": float(r.get("open") or c),
                        "high": float(r.get("high") or c),
                        "low": float(r.get("low") or c),
                        "close": c,
                        "volume": float(r.get("volume") or 0.0),
                        "is_vfex_local": True,
                        "is_zse": vfex.infer_currency(sym, (store.state.get("prices") or {}).get(sym) or {}) == "ZWG",
                    })
            clean.sort(key=lambda x: x["date"])
            if len(clean) >= 10:
                series_map[f"LOCAL:{sym}"] = clean
                vfex_count += 1
    except Exception:
        pass

    news_map = fetch_news_sentiment(force=force)
    total_bars = sum(len(v) for v in series_map.values())
    print(f"  Downloaded {len(series_map)} series ({vfex_count} local VFEX/ZSE), {total_bars:,} daily bars, {len(news_map)} news days.")
    return series_map, news_map


def build_dataset(
    series_map: dict[str, list[dict[str, Any]]],
    news_map: dict[str, float],
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, list[str], dict[str, float]]:
    print("[2/4] Building 16 universal financial features & multi-horizon episodes...")

    date_rets: dict[str, list[float]] = {}
    for sym, bars in series_map.items():
        if sym.startswith("^"):
            continue
        for i in range(1, len(bars)):
            c0, c1 = bars[i - 1]["close"], bars[i]["close"]
            if c0 > 0 and c1 > 0:
                date_rets.setdefault(bars[i]["date"], []).append((c1 - c0) / c0)

    regime_by_date: dict[str, float] = {}
    for dt, rets in date_rets.items():
        if len(rets) < 5:
            continue
        adv = sum(1 for r in rets if r > 0.001)
        dec = sum(1 for r in rets if r < -0.001)
        br = (adv - dec) / len(rets)
        regime_by_date[dt] = max(-1.0, min(1.0, br * 2.5))

    gold_bars = series_map.get("GC=F") or series_map.get("GLD") or []
    gold_mom20: dict[str, float] = {}
    for i in range(20, len(gold_bars)):
        c0, c1 = gold_bars[i - 20]["close"], gold_bars[i]["close"]
        if c0 > 0:
            gold_mom20[gold_bars[i]["date"]] = max(-1.5, min(1.5, ((c1 - c0) / c0) * 10.0))

    vix_bars = series_map.get("^VIX") or []
    vix_norm: dict[str, float] = {}
    for b in vix_bars:
        vix_norm[b["date"]] = max(-1.5, min(1.5, (b["close"] - 20.0) / 15.0))

    latest_gold = gold_mom20[gold_bars[-1]["date"]] if gold_bars and gold_bars[-1]["date"] in gold_mom20 else 0.0
    latest_vix = vix_norm[vix_bars[-1]["date"]] if vix_bars and vix_bars[-1]["date"] in vix_norm else 0.0
    macro_snapshot = {"macro_gold": round(float(latest_gold), 4), "macro_vix": round(float(latest_vix), 4)}

    X_list: list[list[float]] = []
    y5_list: list[float] = []
    r5_list: list[float] = []
    y20_list: list[float] = []
    r20_list: list[float] = []
    dates_list: list[str] = []

    skip_syms = {"^VIX", "^TNX", "^TYX", "^FVX"}
    for sym, bars in series_map.items():
        if sym in skip_syms:
            continue
        n = len(bars)
        is_local = sym.startswith("LOCAL:")
        min_start = 10 if is_local else 62
        if n < min_start + 21:
            continue

        closes = np.array([b["close"] for b in bars], dtype=np.float64)
        highs = np.array([b["high"] for b in bars], dtype=np.float64)
        lows = np.array([b["low"] for b in bars], dtype=np.float64)
        vols = np.array([b["volume"] for b in bars], dtype=np.float64)
        is_zse_sym = bool(bars[0].get("is_zse", False))
        fee_pct = 4.38 if is_zse_sym else (2.08 if is_local else 0.25)

        rets = np.zeros(n, dtype=np.float64)
        rets[1:] = (closes[1:] - closes[:-1]) / np.maximum(closes[:-1], 1e-9)

        stride = 1 if is_local else 2
        for i in range(min_start, n - 20, stride):
            c = closes[i]
            if c <= 0:
                continue
            dt = bars[i]["date"]

            w30 = closes[max(0, i - 30):i]
            avg30 = float(np.mean(w30)) if len(w30) else c
            dip_pct = max(0.0, ((avg30 - c) / max(avg30, 1e-9)) * 100.0)
            f_dip = min(1.5, dip_pct / 10.0)

            r14 = rets[max(1, i - 13):i + 1]
            gains = float(np.mean(np.maximum(r14, 0.0)))
            losses = float(np.mean(np.maximum(-r14, 0.0)))
            rsi = (100.0 if gains > 0 else 50.0) if losses < 1e-9 else (100.0 - 100.0 / (1.0 + gains / losses))
            f_rsi_os = max(-1.5, min(1.5, (50.0 - rsi) / 25.0))

            hl = highs[i] - lows[i]
            f_book = max(-1.0, min(1.5, ((c - lows[i]) / hl - 0.5) * 2.0)) if hl > 1e-9 else 0.0
            f_news = float(news_map.get(dt, 0.0))

            v20 = vols[max(0, i - 20):i]
            avg_v = float(np.mean(v20)) if len(v20) else 0.0
            f_vol = min(1.5, math.log1p(vols[i] / avg_v) - 0.69) if (avg_v > 0 and vols[i] > 0) else 0.0

            f_regime = float(regime_by_date.get(dt, 0.0))
            f_spread = min(2.0, ((hl / c) * 100.0) / 12.0) if c > 0 else 0.0
            f_zse = 1.0 if is_zse_sym else 0.0

            c5 = closes[max(0, i - 5)]
            f_mom5 = max(-1.5, min(1.5, ((c - c5) / max(c5, 1e-9)) * 10.0))
            c20 = closes[max(0, i - 20)]
            f_mom20 = max(-1.5, min(1.5, ((c - c20) / max(c20, 1e-9)) * 5.0))

            ma20 = float(np.mean(closes[max(0, i - 19):i + 1]))
            ma50 = float(np.mean(closes[max(0, i - 49):i + 1]))
            f_trend = max(-1.5, min(1.5, ((ma20 - ma50) / max(ma50, 1e-9)) * 15.0))

            r20_w = rets[max(1, i - 19):i + 1]
            ann_vol = float(np.std(r20_w)) * math.sqrt(252.0) if len(r20_w) > 2 else 0.2
            f_vol20 = min(2.0, ann_vol / 0.40)

            hi60 = float(np.max(closes[max(0, i - 59):i + 1]))
            f_dd60 = min(1.5, max(0.0, (hi60 - c) / max(hi60, 1e-9)) * 5.0)

            f_gold = float(gold_mom20.get(dt, 0.0))
            f_vix = float(vix_norm.get(dt, 0.0))

            fwd5 = ((closes[i + 5] - c) / c) * 100.0 - fee_pct
            fwd20 = ((closes[i + 20] - c) / c) * 100.0 - fee_pct

            X_list.append([
                1.0, f_dip, f_rsi_os, f_book, f_news, f_vol, f_regime, f_spread, f_zse,
                f_mom5, f_mom20, f_trend, f_vol20, f_dd60, f_gold, f_vix,
            ])
            y5_list.append(1.0 if fwd5 > 0.0 else 0.0)
            r5_list.append(max(-25.0, min(25.0, fwd5)))
            y20_list.append(1.0 if fwd20 > 0.0 else 0.0)
            r20_list.append(max(-40.0, min(40.0, fwd20)))
            dates_list.append(dt)

    X = np.array(X_list, dtype=np.float32)
    y5 = np.array(y5_list, dtype=np.float32)
    r5 = np.array(r5_list, dtype=np.float32)
    y20 = np.array(y20_list, dtype=np.float32)
    r20 = np.array(r20_list, dtype=np.float32)

    order = np.argsort(np.array(dates_list))
    X, y5, r5, y20, r20 = X[order], y5[order], r5[order], y20[order], r20[order]
    dates_sorted = [dates_list[i] for i in order]
    print(f"  Built {len(X):,} chronological episodes ({dates_sorted[0]} -> {dates_sorted[-1]})")
    return X, y5, r5, y20, r20, dates_sorted, macro_snapshot


def _sigmoid(z: np.ndarray) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-np.clip(z, -15.0, 15.0)))


def _bce(p: np.ndarray, y: np.ndarray) -> float:
    pc = np.clip(p, 1e-7, 1.0 - 1e-7)
    return float(-np.mean(y * np.log(pc) + (1.0 - y) * np.log(1.0 - pc)))


def fit_linear_baseline(X_tr: np.ndarray, y_tr: np.ndarray, l2: float = 0.05, steps: int = 200) -> np.ndarray:
    w = np.zeros(X_tr.shape[1], dtype=np.float64)
    n = float(len(X_tr))
    for _ in range(steps):
        p = _sigmoid(X_tr @ w)
        grad = (X_tr.T @ (p - y_tr)) / n + l2 * w
        grad[0] -= l2 * w[0]
        w -= 0.25 * grad
    return w.astype(np.float32)


def _layernorm_fwd(x: np.ndarray, eps: float = 1e-5) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    mean = np.mean(x, axis=1, keepdims=True)
    var = np.var(x, axis=1, keepdims=True)
    inv_std = 1.0 / np.sqrt(var + eps)
    return (x - mean) * inv_std, mean, inv_std


def _layernorm_bwd(dy: np.ndarray, x_hat: np.ndarray, inv_std: np.ndarray) -> np.ndarray:
    d = float(x_hat.shape[1])
    sum_dy = np.sum(dy, axis=1, keepdims=True)
    sum_dy_xhat = np.sum(dy * x_hat, axis=1, keepdims=True)
    return (inv_std / d) * (d * dy - sum_dy - x_hat * sum_dy_xhat)


def train_deep_res_mlp(
    X_tr: np.ndarray, y5_tr: np.ndarray, r5_tr: np.ndarray, y20_tr: np.ndarray, r20_tr: np.ndarray,
    X_val: np.ndarray, y5_val: np.ndarray, r5_val: np.ndarray, y20_val: np.ndarray, r20_val: np.ndarray,
    w_lin5: np.ndarray, w_lin20: np.ndarray,
    h1: int = 128, h2: int = 64, weight_decay: float = 0.03, dropout: float = 0.25,
    lr: float = 0.002, epochs: int = 25, batch_size: int = 1024, seed: int = 42,
) -> dict[str, Any]:
    """Train 2-hidden-layer Deep Residual MLP (16 -> h1 -> h2 -> 4) with LayerNorm + skip + Grokfast EMA."""
    rng = np.random.default_rng(seed)
    in_dim = X_tr.shape[1]
    out_dim = 4

    W1 = (rng.standard_normal((h1, in_dim)) * math.sqrt(1.0 / in_dim)).astype(np.float32)
    b1 = np.zeros(h1, dtype=np.float32)
    W2 = (rng.standard_normal((h2, h1)) * math.sqrt(1.0 / h1)).astype(np.float32)
    b2 = np.zeros(h2, dtype=np.float32)
    # Residual projection from input -> h2
    Wskip = (rng.standard_normal((h2, in_dim)) * math.sqrt(0.25 / in_dim)).astype(np.float32)
    W3 = (rng.standard_normal((out_dim, h2)) * math.sqrt(0.5 / h2)).astype(np.float32)
    b3 = np.zeros(out_dim, dtype=np.float32)

    params = [W1, b1, W2, b2, Wskip, W3, b3]
    wds = [weight_decay, 0.0, weight_decay, 0.0, weight_decay, weight_decay, 0.0]
    ms = [np.zeros_like(p) for p in params]
    vs = [np.zeros_like(p) for p in params]
    emas = [np.zeros_like(p) for p in params]

    base5_tr = np.clip(X_tr @ w_lin5, -5.0, 5.0)
    base20_tr = np.clip(X_tr @ w_lin20, -5.0, 5.0)
    base5_val = np.clip(X_val @ w_lin5, -5.0, 5.0)
    base20_val = np.clip(X_val @ w_lin20, -5.0, 5.0)

    def _fwd(X: np.ndarray, b5: np.ndarray, b20: np.ndarray, train: bool = False):
        z1 = X @ W1.T + b1
        z1_n, _, inv1 = _layernorm_fwd(z1)
        a1 = np.tanh(np.clip(z1_n, -6.0, 6.0))
        if train and dropout > 0.0:
            m1 = (rng.random(a1.shape) >= dropout).astype(np.float32) / (1.0 - dropout)
            a1_d = a1 * m1
        else:
            m1, a1_d = None, a1

        z2 = a1_d @ W2.T + b2 + X @ Wskip.T
        z2_n, _, inv2 = _layernorm_fwd(z2)
        a2 = np.tanh(np.clip(z2_n, -6.0, 6.0))
        if train and dropout > 0.0:
            m2 = (rng.random(a2.shape) >= dropout).astype(np.float32) / (1.0 - dropout)
            a2_d = a2 * m2
        else:
            m2, a2_d = None, a2

        out = a2_d @ W3.T + b3
        res5 = np.clip(out[:, 0], -4.0, 4.0)
        ret5 = out[:, 1] * 10.0
        res20 = np.clip(out[:, 2], -4.0, 4.0)
        ret20 = out[:, 3] * 15.0
        p5 = _sigmoid(b5 + 0.5 * res5)
        p20 = _sigmoid(b20 + 0.5 * res20)
        return p5, ret5, p20, ret20, (z1_n, inv1, a1, m1, a1_d, z2_n, inv2, a2, m2, a2_d)

    best_val_loss = 1e9
    best_weights = None
    best_epoch = 0
    step_t = 0
    n_tr = len(X_tr)

    for ep in range(1, epochs + 1):
        ep_lr = lr * 0.5 * (1.0 + math.cos(math.pi * (ep - 1) / max(1, epochs)))
        perm = rng.permutation(n_tr)
        for start in range(0, n_tr, batch_size):
            idx = perm[start:start + batch_size]
            xb = X_tr[idx]
            y5b, r5b = y5_tr[idx], r5_tr[idx]
            y20b, r20b = y20_tr[idx], r20_tr[idx]
            b5b, b20b = base5_tr[idx], base20_tr[idx]
            bs = float(len(idx))

            p5, ret5, p20, ret20, cache = _fwd(xb, b5b, b20b, train=True)
            z1_n, inv1, a1, m1, a1_d, z2_n, inv2, a2, m2, a2_d = cache

            d_out = np.zeros((len(idx), out_dim), dtype=np.float32)
            d_out[:, 0] = 0.5 * (p5 - y5b) / bs
            d_out[:, 1] = 0.04 * ((ret5 - r5b) / 10.0) / bs
            d_out[:, 2] = 0.5 * (p20 - y20b) / bs
            d_out[:, 3] = 0.04 * ((ret20 - r20b) / 15.0) / bs

            gW3 = d_out.T @ a2_d
            gb3 = np.sum(d_out, axis=0)

            da2 = d_out @ W3
            if m2 is not None:
                da2 = da2 * m2
            dz2_n = da2 * (1.0 - a2 * a2)
            dz2 = _layernorm_bwd(dz2_n, z2_n, inv2)

            gW2 = dz2.T @ a1_d
            gb2 = np.sum(dz2, axis=0)
            gWskip = dz2.T @ xb

            da1 = dz2 @ W2
            if m1 is not None:
                da1 = da1 * m1
            dz1_n = da1 * (1.0 - a1 * a1)
            dz1 = _layernorm_bwd(dz1_n, z1_n, inv1)

            gW1 = dz1.T @ xb
            gb1 = np.sum(dz1, axis=0)

            grads = [gW1, gb1, gW2, gb2, gWskip, gW3, gb3]
            step_t += 1
            b1_c = 1.0 - (0.9 ** step_t)
            b2_c = 1.0 - (0.999 ** step_t)

            for p, g, m, v, ema, wd in zip(params, grads, ms, vs, emas, wds):
                ema[:] = 0.85 * ema + 0.15 * g
                g_eff = g + 0.6 * ema
                m[:] = 0.9 * m + 0.1 * g_eff
                v[:] = 0.999 * v + 0.001 * (g_eff * g_eff)
                if wd > 0.0:
                    p *= (1.0 - ep_lr * wd)
                p -= ep_lr * (m / b1_c) / (np.sqrt(v / b2_c) + 1e-8)

        p5_v, _, p20_v, _, _ = _fwd(X_val, base5_val, base20_val, train=False)
        val_loss = 0.5 * (_bce(p5_v, y5_val) + _bce(p20_v, y20_val))
        if val_loss < best_val_loss:
            best_val_loss = val_loss
            best_epoch = ep
            best_weights = [p.copy() for p in params]

    for p, bw in zip(params, best_weights):
        p[:] = bw

    p5_tr, _, p20_tr, _, _ = _fwd(X_tr, base5_tr, base20_tr, train=False)
    p5_v, ret5_v, p20_v, ret20_v, _ = _fwd(X_val, base5_val, base20_val, train=False)
    tr_acc = 0.5 * (float(np.mean((p5_tr >= 0.5) == (y5_tr >= 0.5))) + float(np.mean((p20_tr >= 0.5) == (y20_tr >= 0.5)))) * 100.0
    val_acc = 0.5 * (float(np.mean((p5_v >= 0.5) == (y5_val >= 0.5))) + float(np.mean((p20_v >= 0.5) == (y20_val >= 0.5)))) * 100.0

    return {
        "W1": best_weights[0], "b1": best_weights[1],
        "W2": best_weights[2], "b2": best_weights[3],
        "Wskip": best_weights[4],
        "W3": best_weights[5], "b3": best_weights[6],
        "h1": h1, "h2": h2,
        "best_epoch": best_epoch, "epochs_run": epochs,
        "train_acc_pct": round(tr_acc, 2),
        "val_acc_pct": round(val_acc, 2),
        "val_loss": round(best_val_loss, 5),
        "gap_pct": round(abs(tr_acc - val_acc), 2),
        "p5_val": p5_v, "p20_val": p20_v,
    }


def _eval_member(m: dict[str, Any], X: np.ndarray, w_lin5: np.ndarray, w_lin20: np.ndarray):
    z1 = X @ m["W1"].T + m["b1"]
    z1_n, _, _ = _layernorm_fwd(z1)
    a1 = np.tanh(np.clip(z1_n, -6.0, 6.0))
    z2 = a1 @ m["W2"].T + m["b2"] + X @ m["Wskip"].T
    z2_n, _, _ = _layernorm_fwd(z2)
    a2 = np.tanh(np.clip(z2_n, -6.0, 6.0))
    out = a2 @ m["W3"].T + m["b3"]
    p5 = _sigmoid(np.clip(X @ w_lin5, -5.0, 5.0) + 0.5 * np.clip(out[:, 0], -4.0, 4.0))
    p20 = _sigmoid(np.clip(X @ w_lin20, -5.0, 5.0) + 0.5 * np.clip(out[:, 2], -4.0, 4.0))
    return p5, out[:, 1] * 10.0, p20, out[:, 3] * 15.0


def run_training_loop(force_download: bool = False) -> dict[str, Any]:
    series_map, news_map = download_all_data(force=force_download)
    X, y5, r5, y20, r20, dates, macro_snapshot = build_dataset(series_map, news_map)

    n = len(X)
    i_tr = int(n * 0.70)
    i_val = int(n * 0.85)

    X_tr, y5_tr, r5_tr, y20_tr, r20_tr = X[:i_tr], y5[:i_tr], r5[:i_tr], y20[:i_tr], r20[:i_tr]
    X_val, y5_val, r5_val, y20_val, r20_val = X[i_tr:i_val], y5[i_tr:i_val], r5[i_tr:i_val], y20[i_tr:i_val], r20[i_tr:i_val]
    X_te, y5_te, r5_te, y20_te, r20_te = X[i_val:], y5[i_val:], r5[i_val:], y20[i_val:], r20[i_val:]

    print(f"  Walk-forward splits: Train={len(X_tr):,} ({dates[0]}..{dates[i_tr-1]}) | Val={len(X_val):,} ({dates[i_tr]}..{dates[i_val-1]}) | Test={len(X_te):,} ({dates[i_val]}..{dates[-1]})")

    w_lin5 = fit_linear_baseline(X_tr, y5_tr, l2=0.05)
    w_lin20 = fit_linear_baseline(X_tr, y20_tr, l2=0.05)
    lin_val_loss = 0.5 * (_bce(_sigmoid(X_val @ w_lin5), y5_val) + _bce(_sigmoid(X_val @ w_lin20), y20_val))
    lin_val_acc = 0.5 * (
        float(np.mean((_sigmoid(X_val @ w_lin5) >= 0.5) == (y5_val >= 0.5))) +
        float(np.mean((_sigmoid(X_val @ w_lin20) >= 0.5) == (y20_val >= 0.5)))
    ) * 100.0
    print(f"[3/4] Linear Baseline OOS Val: loss={lin_val_loss:.5f}, acc={lin_val_acc:.2f}%")

    # Train 3 diverse Deep Residual MLP Ensemble members
    ensemble_cfgs = [
        {"h1": 128, "h2": 64, "weight_decay": 0.03, "dropout": 0.25, "lr": 0.0020, "epochs": 24, "seed": 101},
        {"h1": 128, "h2": 64, "weight_decay": 0.04, "dropout": 0.30, "lr": 0.0018, "epochs": 26, "seed": 202},
        {"h1": 96,  "h2": 48, "weight_decay": 0.025, "dropout": 0.20, "lr": 0.0022, "epochs": 24, "seed": 303},
    ]

    members = []
    for idx, cfg in enumerate(ensemble_cfgs, 1):
        print(f"  Training Ensemble Member {idx}/3 (16 -> {cfg['h1']} -> {cfg['h2']} -> 4, wd={cfg['weight_decay']}, drop={cfg['dropout']})...")
        m = train_deep_res_mlp(
            X_tr, y5_tr, r5_tr, y20_tr, r20_tr,
            X_val, y5_val, r5_val, y20_val, r20_val,
            w_lin5, w_lin20, **cfg,
        )
        print(f"    -> Member {idx}: Val loss={m['val_loss']:.5f} | Train={m['train_acc_pct']:.2f}% Val={m['val_acc_pct']:.2f}% Gap={m['gap_pct']:.2f}% (best ep {m['best_epoch']})")
        members.append(m)

    # Ensemble Validation & Unseen Test evaluation
    p5_val_ens = np.mean([m["p5_val"] for m in members], axis=0)
    p20_val_ens = np.mean([m["p20_val"] for m in members], axis=0)
    ens_val_loss = 0.5 * (_bce(p5_val_ens, y5_val) + _bce(p20_val_ens, y20_val))
    ens_val_acc = 0.5 * (
        float(np.mean((p5_val_ens >= 0.5) == (y5_val >= 0.5))) +
        float(np.mean((p20_val_ens >= 0.5) == (y20_val >= 0.5)))
    ) * 100.0
    avg_tr_acc = float(np.mean([m["train_acc_pct"] for m in members]))
    ens_gap = abs(avg_tr_acc - ens_val_acc)
    hi_val = p20_val_ens >= 0.55
    oos_hi_ret = float(np.mean(r20_val[hi_val])) if np.any(hi_val) else float(np.mean(r20_val))

    p5_te_list, p20_te_list = [], []
    for m in members:
        p5_t, _, p20_t, _ = _eval_member(m, X_te, w_lin5, w_lin20)
        p5_te_list.append(p5_t)
        p20_te_list.append(p20_t)
    p5_te_ens = np.mean(p5_te_list, axis=0)
    p20_te_ens = np.mean(p20_te_list, axis=0)
    te_loss = 0.5 * (_bce(p5_te_ens, y5_te) + _bce(p20_te_ens, y20_te))
    lin_te_loss = 0.5 * (_bce(_sigmoid(X_te @ w_lin5), y5_te) + _bce(_sigmoid(X_te @ w_lin20), y20_te))
    te_acc = 0.5 * (
        float(np.mean((p5_te_ens >= 0.5) == (y5_te >= 0.5))) +
        float(np.mean((p20_te_ens >= 0.5) == (y20_te >= 0.5)))
    ) * 100.0
    hi_te = p20_te_ens >= 0.55
    te_hi_ret = float(np.mean(r20_te[hi_te])) if np.any(hi_te) else float(np.mean(r20_te))

    passed = (ens_val_loss < lin_val_loss) and (ens_gap < 5.0) and (oos_hi_ret > 0.0)
    print(f"[4/4] Ensemble OOS Val: loss={ens_val_loss:.5f} (vs lin {lin_val_loss:.5f}) | acc={ens_val_acc:.2f}% | Gap={ens_gap:.2f}% | HiConf 20d Ret={oos_hi_ret:+.2f}% | Gate={'PASS' if passed else 'GATED'}")
    print(f"      Unseen Test ({dates[i_val]}..{dates[-1]}): loss={te_loss:.5f} (vs lin {lin_te_loss:.5f}) | acc={te_acc:.2f}% | HiConf 20d Ret={te_hi_ret:+.2f}%")

    def _round_mat(mat: np.ndarray) -> list[list[float]]:
        return [[round(float(v), 4) for v in row] for row in mat]

    def _round_vec(vec: np.ndarray) -> list[float]:
        return [round(float(v), 4) for v in vec]

    payload = {
        "version": 3,
        "trained_at": datetime.now(timezone.utc).isoformat(),
        "feature_order": FEATURE_KEYS,
        "residual_alpha": 0.5,
        "enabled": bool(passed),
        "status": "Grokked (Foundation v3 Ensemble)" if passed else "Calibrating",
        "macro_snapshot": macro_snapshot,
        "linear_5d": _round_vec(w_lin5),
        "linear_20d": _round_vec(w_lin20),
        "models": [
            {
                "h1": int(m["h1"]), "h2": int(m["h2"]),
                "W1": _round_mat(m["W1"]), "b1": _round_vec(m["b1"]),
                "W2": _round_mat(m["W2"]), "b2": _round_vec(m["b2"]),
                "Wskip": _round_mat(m["Wskip"]),
                "W3": _round_mat(m["W3"]), "b3": _round_vec(m["b3"]),
            }
            for m in members
        ],
        "metrics": {
            "episodes_total": int(n),
            "train_count": int(len(X_tr)),
            "val_count": int(len(X_val)),
            "test_count": int(len(X_te)),
            "series_count": int(len(series_map)),
            "ensemble_size": len(members),
            "date_range": f"{dates[0]}..{dates[-1]}",
            "train_acc_pct": round(avg_tr_acc, 2),
            "val_acc_pct": round(ens_val_acc, 2),
            "test_acc_pct": round(te_acc, 2),
            "linear_val_loss": round(lin_val_loss, 5),
            "grok_val_loss": round(ens_val_loss, 5),
            "linear_val_acc_pct": round(lin_val_acc, 2),
            "val_gain_pct": round(ens_val_acc - lin_val_acc, 2),
            "generalization_gap_pct": round(ens_gap, 2),
            "oos_hi_ret_20d_pct": round(oos_hi_ret, 3),
            "test_hi_ret_20d_pct": round(te_hi_ret, 3),
            "last_trained": datetime.now(timezone.utc).date().isoformat(),
        },
    }
    WEIGHTS_OUT.write_text(json.dumps(payload, separators=(",", ":")), encoding="utf-8")
    size_kb = WEIGHTS_OUT.stat().st_size / 1024.0
    print(f"Exported {WEIGHTS_OUT.name} ({size_kb:.1f} KB) | Status: {payload['status']}")
    return payload


if __name__ == "__main__":
    force = "--force" in sys.argv
    run_training_loop(force_download=force)
