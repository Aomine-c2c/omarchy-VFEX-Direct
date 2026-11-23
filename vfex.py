#!/usr/bin/env python3
"""omarchy-VFEX-Direct: Victoria Falls Stock Exchange (VFEX) CLI & Waybar tracker."""

from __future__ import annotations

import argparse
import concurrent.futures
import contextlib
import csv
from email.utils import parsedate_to_datetime
import fcntl
import hashlib
import html as html_lib
import http.cookiejar
import io
import json
import os
import re
import stat
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

DEFAULT_CONFIG_DIR = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "vfex-direct"

VFEX_DIRECT_API_BASE = "https://d3u8q0mxu6epjj.cloudfront.net/api/v1"
ZSE_DIRECT_API_BASE = "https://d17zh5y0djjrt1.cloudfront.net/api/v1"
VFEX_DIRECT_URL = f"{VFEX_DIRECT_API_BASE}/voms/price-sheets/active"
ZSE_DIRECT_URL = f"{ZSE_DIRECT_API_BASE}/voms/price-sheets/active"
CTRADE_BASE_URL = "https://ctradenew.ctrade.co.zw"
CTRADE_VFEX_URL = f"{CTRADE_BASE_URL}/api/web-proxy/online.ctrade_php/marketwatchvx.php"
CTRADE_ZSE_URL = f"{CTRADE_BASE_URL}/api/mobile-proxy/marketwatchzsenew"
CTRADE_ETF_URL = f"{CTRADE_BASE_URL}/api/mobile-proxy/etfMarketWatch"
CTRADE_INDICES_URL = f"{CTRADE_BASE_URL}/api/mobile-proxy/marketwatchindices"
CTRADE_FINSEC_URL = f"{CTRADE_BASE_URL}/api/web-proxy/online.ctrade_php/marketwatchbidoffer.php"
CTRADE_UNIT_TRUSTS_URL = f"{CTRADE_BASE_URL}/api/trading-proxy/data/unit_trusts-v2"
CTRADE_NOTICES_URL = f"{CTRADE_BASE_URL}/api/notices"

EXCHANGE_DOCS_API_BASE = "https://ds88jcmqc11je.cloudfront.net/api"
VFEX_ANNOUNCEMENTS_URL = f"{EXCHANGE_DOCS_API_BASE}/docs?exchange=VFEX&category=announcements"
ZSE_ANNOUNCEMENTS_URL = f"{EXCHANGE_DOCS_API_BASE}/docs?exchange=ZSE&category=announcements"
VFEX_ISSUER_DOCS_URL = f"{EXCHANGE_DOCS_API_BASE}/issuer-documents?exchange=VFEX"
ZSE_ISSUER_DOCS_URL = f"{EXCHANGE_DOCS_API_BASE}/issuer-documents?exchange=ZSE"
VFEX_DTR_URL = f"{EXCHANGE_DOCS_API_BASE}/fetch/dtr?exchange=VFEX"
ZSE_DTR_URL = f"{EXCHANGE_DOCS_API_BASE}/fetch/dtr?exchange=ZSE"
GOOGLE_NEWS_RSS_URL = "https://news.google.com/rss/search?q={q}&hl=en-ZW&gl=ZW&ceid=ZW:en"
NEWS_CACHE_TTL_SECONDS = 900
NEWS_MAX_AGE_DAYS = 14
INTEL_CACHE_TTL_SECONDS = 300

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


def _dedupe_sorted_history(hist: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Deduplicate OHLC/price history entries by date (preserving latest per date) in chronological order."""
    by_date: dict[str, dict[str, Any]] = {}
    undated: list[dict[str, Any]] = []
    for row in hist:
        if not isinstance(row, dict):
            continue
        dt = str(row.get("date") or "").strip()
        if dt:
            by_date[dt] = row
        else:
            undated.append(row)
    return [by_date[d] for d in sorted(by_date)] + undated


def compute_symbol_technicals(hist: list[dict[str, Any]], cur: float) -> dict[str, Any]:
    """Compute 20D/30D averages, rolling MA series, Z-score, and RSI-14 from candle history."""
    clean_hist = _dedupe_sorted_history(hist)
    closes = [float(h.get("close", h.get("price", 0.0))) for h in clean_hist if float(h.get("close", h.get("price", 0.0))) > 0]
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
    if len(closes) >= 6 and closes[0] > 0:
        deltas = [closes[i] - closes[i - 1] for i in range(1, len(closes))][-14:]
        total_move_pct = sum(abs(d) for d in deltas) / closes[0]
        if total_move_pct >= 0.005:
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


def normalize_goal(raw: str | None) -> str:
    """Normalize trading goal strings into 'long', 'short', or 'hybrid'."""
    s = str(raw or "").strip().lower()
    if s in ("long", "long-term", "long-term compounder", "core", "invest"):
        return "long"
    if s in ("short", "short-term", "short-term swing", "swing", "trade"):
        return "short"
    return "hybrid"


_CORP_SUFFIXES = (
    "holdings limited",
    "corporation limited",
    "investment trust",
    "investments limited",
    "resources plc",
    "limited",
    "holdings",
    "corporation",
    "group",
    "company",
    "zimbabwe",
    "plc",
    "ltd",
    "corp",
    "fund",
    "reit",
)

_AMBIGUOUS_SINGLE_WORDS = {
    "africa",
    "african",
    "art",
    "bank",
    "british",
    "capital",
    "delta",
    "eagle",
    "earth",
    "first",
    "food",
    "foods",
    "general",
    "gold",
    "green",
    "mutual",
    "national",
    "old",
    "power",
    "rainbow",
    "real",
    "seed",
    "star",
    "sun",
    "trust",
    "true",
    "united",
}

_ZIM_CONTEXT_TERMS = (
    "vfex",
    "zse",
    "victoria falls stock exchange",
    "zimbabwe stock exchange",
    "zimbabwe",
    "harare",
    "bulawayo",
    "victoria falls",
    "c-trade",
    "ctrade",
    "seczim",
    "zig",
    "zwg",
    "shareholders",
    "shareholder",
    "cautionary",
    "trading update",
    "agm",
    "dividend",
    "bourse",
)


def _clean_company_aliases(raw_name: str, base_sym: str) -> list[str]:
    """Generate distinctive company-name search phrases from a formal listing title."""
    aliases: list[str] = []
    text = re.sub(r"\([^)]*\)", " ", str(raw_name or ""))
    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        return aliases
    low = text.lower()
    no_legal = re.sub(r"\b(?:limited|ltd|plc|inc)\b\.?", " ", low)
    no_legal = re.sub(r"\s+", " ", no_legal).strip(" -.,")
    stripped = low
    for suf in _CORP_SUFFIXES:
        stripped = re.sub(rf"\b{re.escape(suf)}\b\.?", " ", stripped)
    stripped = re.sub(r"\s+", " ", stripped).strip(" -.,")
    for cand in (low, no_legal, stripped):
        if len(cand) >= 4 and cand not in _AMBIGUOUS_SINGLE_WORDS:
            if cand not in aliases:
                aliases.append(cand)
    parts = [p for p in stripped.split() if len(p) >= 5]
    if parts:
        first_word = parts[0]
        if first_word not in _AMBIGUOUS_SINGLE_WORDS and first_word not in aliases:
            aliases.append(first_word)
    if base_sym == "DLTA":
        for extra in ("delta corporation", "delta corp"):
            if extra not in aliases:
                aliases.append(extra)
    if base_sym in ("INSC", "INN"):
        for extra in ("innscor africa", "innscor"):
            if extra not in aliases:
                aliases.append(extra)
    if base_sym == "INFR":
        for extra in ("econet infraco", "infraco"):
            if extra not in aliases:
                aliases.append(extra)
    if base_sym == "EAGLE":
        aliases.append("eagle reit")
    return aliases


def _build_symbol_alias_index(store: "VFEXStore") -> dict[str, list[str]]:
    """Build mapping {stored_symbol: [aliases...]} from prices, KNOWN_VFEX_SYMBOLS, holdings, watchlist."""
    index: dict[str, list[str]] = {}
    prices = store.state.get("prices", {})
    all_syms = set(prices.keys()) | set(KNOWN_VFEX_SYMBOLS.keys()) | set(store.state.get("watchlist", [])) | set(store.state.get("portfolio", {}).keys())
    for sym in sorted(all_syms):
        base = sym.split(".")[0].upper()
        entry = prices.get(sym, {})
        comp = str(entry.get("company_name") or KNOWN_VFEX_SYMBOLS.get(sym) or KNOWN_VFEX_SYMBOLS.get(base) or "")
        index[sym] = _clean_company_aliases(comp, base)
    return index


def _match_news_symbols(
    title: str,
    alias_index: dict[str, list[str]],
    stored_symbols: set[str],
    issuer_short: str = "",
    issuer_name: str = "",
) -> list[str]:
    """Strictly match a headline against known VFEX/ZSE symbols without short-ticker false positives."""
    matched: list[str] = []
    combined = f"{title} {issuer_name}".strip()
    low = combined.lower()
    has_zim_ctx = any(term in low for term in _ZIM_CONTEXT_TERMS) or bool(re.search(r"\.[vwx]x\b|\.zw\b", low))

    explicit_tokens: list[str] = []
    if issuer_short:
        explicit_tokens.append(issuer_short.upper().strip())
    for m in re.finditer(r"\b([A-Z]{2,8})\.(VX|ZW)\b", title.upper()):
        explicit_tokens.append(f"{m.group(1)}.{m.group(2)}")

    for tok in explicit_tokens:
        base = tok.split(".")[0]
        is_zw = tok.endswith(".ZW")
        for sym in stored_symbols:
            if is_zw and sym.upper() == f"{base}.ZW":
                if sym not in matched:
                    matched.append(sym)
            elif not is_zw and sym.upper() in (base, f"{base}.VX"):
                if sym not in matched:
                    matched.append(sym)
        if not any(s.split(".")[0] == base and (s.endswith(".ZW") == is_zw) for s in matched):
            fallback = f"{base}.ZW" if is_zw else base
            if fallback not in matched:
                matched.append(fallback)

    for sym, aliases in alias_index.items():
        if sym in matched:
            continue
        for alias in aliases:
            if re.search(rf"\b{re.escape(alias)}\b", low):
                if " " in alias or has_zim_ctx or len(alias) >= 7:
                    matched.append(sym)
                    break

    if has_zim_ctx:
        title_words = set(re.findall(r"\b[A-Z]{2,6}\b", title))
        for sym in alias_index:
            base = sym.split(".")[0].upper()
            if base in title_words and sym not in matched:
                matched.append(sym)

    dedup: list[str] = []
    # Deduplicate alias pairs (INN vs INSC, CALD vs CMCL) preferring priced/tracked symbols
    priced_or_tracked = stored_symbols
    if "INN" in matched and "INSC" in matched:
        prefer = "INN" if ("INN" in priced_or_tracked and "INSC" not in priced_or_tracked) else "INSC"
        drop = "INSC" if prefer == "INN" else "INN"
        matched = [s for s in matched if s != drop]
    if "CALD" in matched and "CMCL" in matched:
        prefer = "CMCL" if ("CMCL" in priced_or_tracked and "CALD" not in priced_or_tracked) else "CALD"
        drop = "CALD" if prefer == "CMCL" else "CMCL"
        matched = [s for s in matched if s != drop]
    for s in matched:
        if s not in dedup:
            dedup.append(s)
    return dedup[:5]


def classify_news_headline(title: str, raw_category: str = "", official: bool = False) -> dict[str, Any]:
    """Classify a VFEX/ZSE headline into (category, sentiment, impact_score)."""
    t = f" {title} {raw_category} ".lower().replace("victoria falls", "vic_bourse")

    def _has(terms: tuple[str, ...]) -> int:
        return sum(1 for term in terms if re.search(rf"\b{re.escape(term)}\b", t))

    negative_strong = (
        "cautionary", "suspension", "suspended", "delist", "delisting",
        "profit warning", "default", "insolvency", "going concern", "fraud",
        "fine", "penalty", "terminated", "withdraw", "shutdown",
    )
    negative_soft = (
        "loss", "losses", "decline", "declines", "drop", "drops", "dropped",
        "slump", "slumps", "falls", "fell", "lower profit", "delay", "delayed",
        "downturn", "deficit", "weak", "warning",
    )
    positive_strong = (
        "acquires", "acquisition", "full ownership", "takeover", "share buy-back", "buyback",
        "dividend", "rig-up", "rig move", "mobilisation", "gazettal", "commission",
        "commissioned", "expansion", "record profit", "debut", "landmark", "exceeds",
        "exceeded", "surges", "jumps", "prospectus", "allotment", "completed",
    )
    positive_soft = (
        "growth", "grows", "rise", "rises", "rising", "profit", "profitable",
        "approved", "strong", "resilient", "rebound", "recovery", "launches",
        "launched", "solar", "contract", "partnership", "upgrade", "progress",
        "advances", "rallies", "leads",
    )

    if _has(("cautionary", "suspension", "suspended", "delist", "profit warning", "going concern", "fraud", "delay in publication")):
        category = "Cautionary"
    elif _has(("dividend", "interim div", "final div", "ex-div", "distribution")):
        category = "Dividend"
    elif _has(("agm results", "egm results", "agm notice", "egm notice", "director", "board", "appointment", "resignation", "notice of agm", "circular to")):
        category = "Governance"
    elif _has(("trading update", "results", "financial statements", "quarterly report", "half year", "full year", "annual report", "earnings", "revenue", "profit", "first quarter", "second quarter", "third quarter", "q1", "q2", "q3", "q4", "hy2", "fy2")):
        category = "Earnings"
    elif _has(("acquires", "acquisition", "full ownership", "share buy-back", "buyback", "rig-up", "rig move", "mobilisation", "drilling", "gazettal", "expansion", "solar", "wellpad", "commission", "contract", "agreement", "partnership")):
        category = "Expansion"
    elif _has(("prospectus", "listing", "ipo", "debut", "rights issue", "renounceable", "capital raise")):
        category = "Listing"
    else:
        category = "Market"

    neg_hits = _has(negative_strong) * 2 + _has(negative_soft)
    pos_hits = _has(positive_strong) * 2 + _has(positive_soft)

    if neg_hits > pos_hits:
        sentiment = "Caution"
        impact_score = -20 if _has(negative_strong) else -15
    elif pos_hits > neg_hits:
        sentiment = "Bullish"
        impact_score = 20 if category in ("Dividend", "Expansion", "Listing") or pos_hits >= 2 else 15
    else:
        sentiment = "Neutral"
        impact_score = 5 if official else 0

    return {
        "category": category,
        "sentiment": sentiment,
        "impact_score": impact_score,
    }


def _parse_news_timestamp(raw_ts: str | None) -> datetime | None:
    """Parse RFC-2822 RSS dates or ISO-8601 API dates into UTC datetime."""
    s = str(raw_ts or "").strip()
    if not s:
        return None
    try:
        s_iso = (s[:-1] + "+00:00") if s.endswith("Z") else s
        dt = datetime.fromisoformat(s_iso)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except ValueError:
        pass
    try:
        dt2 = parsedate_to_datetime(s)
        if dt2.tzinfo is None:
            dt2 = dt2.replace(tzinfo=timezone.utc)
        return dt2.astimezone(timezone.utc)
    except (TypeError, ValueError):
        return None


def _format_age_label(dt: datetime | None, now: datetime | None = None) -> tuple[int, str]:
    """Return (age_days, compact human label) for a UTC timestamp."""
    if dt is None:
        return 0, "Recent"
    ref = now or datetime.now(timezone.utc)
    secs = max(0.0, (ref - dt).total_seconds())
    days = int(secs // 86400)
    if secs < 3600:
        return 0, f"{max(1, int(secs // 60))}m ago"
    if secs < 86400:
        return 0, f"{int(secs // 3600)}h ago"
    if days == 1:
        return 1, "Yesterday"
    if days <= 14:
        return days, f"{days}d ago"
    return days, dt.strftime("%b %d")


_MONTH_ABBR_MAP = {
    "jan": 1, "january": 1, "feb": 2, "february": 2, "mar": 3, "march": 3,
    "apr": 4, "april": 4, "may": 5, "jun": 6, "june": 6,
    "jul": 7, "july": 7, "aug": 8, "august": 8, "sep": 9, "sept": 9, "september": 9,
    "oct": 10, "october": 10, "nov": 11, "november": 11, "dec": 12, "december": 12,
}


def _extract_title_news_date(title: str) -> datetime | None:
    """Extract an explicit full calendar date (e.g. '14 Oct 2026') embedded in an official notice title."""
    s = str(title or "")
    m_txt = re.search(r"\b(\d{1,2})\s+([A-Za-z]{3,9})\s+(20\d{2})\b", s)
    if m_txt:
        mon = _MONTH_ABBR_MAP.get(m_txt.group(2).lower())
        if mon:
            try:
                return datetime(int(m_txt.group(3)), mon, int(m_txt.group(1)), 12, 0, tzinfo=timezone.utc)
            except ValueError:
                pass
    m_iso = re.search(r"\b(20\d{2})-(\d{2})-(\d{2})\b", s)
    if m_iso:
        try:
            return datetime(int(m_iso.group(1)), int(m_iso.group(2)), int(m_iso.group(3)), 12, 0, tzinfo=timezone.utc)
        except ValueError:
            pass
    m_dmy = re.search(r"\b(\d{1,2})[./-](\d{1,2})[./-](20\d{2})\b", s)
    if m_dmy:
        try:
            return datetime(int(m_dmy.group(3)), int(m_dmy.group(2)), int(m_dmy.group(1)), 12, 0, tzinfo=timezone.utc)
        except ValueError:
            pass
    return None


def _news_age_weight(age_days: int) -> float:
    """Return recency decay multiplier over the 14-day news window."""
    if age_days <= 3:
        return 1.0
    if age_days <= 7:
        return 0.70
    if age_days <= NEWS_MAX_AGE_DAYS:
        return 0.40
    return 0.0


def _news_freshness_bucket(age_days: int) -> int:
    """Return discrete freshness tier (3: <=3d, 2: <=7d, 1: <=14d, 0: stale)."""
    if age_days <= 3:
        return 3
    if age_days <= 7:
        return 2
    if age_days <= NEWS_MAX_AGE_DAYS:
        return 1
    return 0


def _parse_google_news_rss(xml_text: str) -> list[dict[str, Any]]:
    """Parse Google News RSS XML string into raw headline records."""
    rows: list[dict[str, Any]] = []
    if not xml_text or "<item" not in xml_text:
        return rows
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return rows
    for item in root.findall(".//item"):
        raw_title = html_lib.unescape(str(item.findtext("title") or "")).strip()
        if not raw_title:
            continue
        link = str(item.findtext("link") or "").strip()
        pub_raw = str(item.findtext("pubDate") or "").strip()
        src_el = item.find("source")
        source = html_lib.unescape(str(src_el.text or "Google News")) if src_el is not None else "Google News"
        source = source.strip() or "Google News"
        if source != "Google News" and raw_title.endswith(f" - {source}"):
            raw_title = raw_title[: -(len(source) + 3)].strip()
        elif " - " in raw_title and len(raw_title.rsplit(" - ", 1)[1]) <= 36:
            maybe_src = raw_title.rsplit(" - ", 1)[1].strip()
            if maybe_src:
                source = maybe_src if source == "Google News" else source
                raw_title = raw_title.rsplit(" - ", 1)[0].strip()
        rows.append({
            "title": raw_title,
            "url": link,
            "source": source,
            "pub_raw": pub_raw,
            "raw_category": "",
            "official": False,
            "issuer_short": "",
            "issuer_name": "",
        })
    return rows


def _parse_exchange_docs_json(payload: Any, default_exchange: str = "VFEX") -> list[dict[str, Any]]:
    """Parse official VFEX/ZSE CDN announcement or issuer-document JSON lists."""
    rows_raw = payload.get("data", payload) if isinstance(payload, dict) else payload
    if not isinstance(rows_raw, list):
        return []
    out: list[dict[str, Any]] = []
    for item in rows_raw[:35]:
        if not isinstance(item, dict):
            continue
        title = str(item.get("doc_name") or item.get("title") or "").strip()
        if not title:
            continue
        exch = str(item.get("exchange") or default_exchange or "VFEX").upper()
        url = str(item.get("download_url") or item.get("proxy_download_url") or "").strip()
        if url.startswith("http://ds88jcmqc11je.cloudfront.net"):
            url = "https://" + url[len("http://"):]
        issuer = item.get("issuer") if isinstance(item.get("issuer"), dict) else {}
        out.append({
            "title": title,
            "url": url or ("https://vfex.exchange/about-us/announcements" if exch == "VFEX" else "https://www.zse.co.zw/about-us/announcements"),
            "source": f"{exch} Official",
            "pub_raw": str(item.get("updated_at") or item.get("created_at") or ""),
            "raw_category": str(item.get("category") or ""),
            "official": True,
            "issuer_short": str(issuer.get("short_name") or ""),
            "issuer_name": str(issuer.get("name") or ""),
        })
    return out


VFEX_FEE_SCHEDULE = {
    "exchange": "VFEX",
    "currency": "USD",
    "brokerage_pct": 0.59,
    "vat_on_brokerage_pct": 15.0,
    "platform_levy_pct": 0.12,
    "secz_levy_pct": 0.12,
    "buy_stamp_duty_pct": 0.24,
    "sell_stamp_duty_pct": 0.0,
    "sell_cgt_pct": 0.0,
    "round_trip_pct": 2.08,
}

ZSE_FEE_SCHEDULE = {
    "exchange": "ZSE",
    "currency": "ZWG",
    "brokerage_pct": 0.92,
    "vat_on_brokerage_pct": 15.0,
    "platform_levy_pct": 0.095,  # CSD 0.07% + IPF 0.025%
    "secz_levy_pct": 0.16,
    "buy_stamp_duty_pct": 0.25,
    "sell_stamp_duty_pct": 0.0,
    "sell_cgt_pct": 1.50,
    "round_trip_pct": 4.38,
}


def calculate_trade_charges(currency: str, side: str, shares: float, price: float) -> dict[str, Any]:
    """Compute itemized statutory & brokerage charges matching VFEX (Morgan & Co) and ZSE Direct schedules."""
    cur = "ZWG" if str(currency or "USD").upper() == "ZWG" else "USD"
    act = "SELL" if str(side or "BUY").upper() == "SELL" else "BUY"
    sched = ZSE_FEE_SCHEDULE if cur == "ZWG" else VFEX_FEE_SCHEDULE

    sh = max(0.0, float(shares or 0.0))
    px = max(0.0, float(price or 0.0))
    gross = sh * px
    if gross <= 0.0:
        return {
            "exchange": sched["exchange"],
            "currency": cur,
            "side": act,
            "shares": sh,
            "price": round(px, 4),
            "gross": 0.0,
            "brokerage_pct": sched["brokerage_pct"],
            "brokerage": 0.0,
            "vat": 0.0,
            "platform_levy": 0.0,
            "secz_levy": 0.0,
            "stamp_duty": 0.0,
            "cgt": 0.0,
            "total_charges": 0.0,
            "total_fee_pct": 0.0,
            "net_settlement": 0.0,
            "round_trip_hurdle_pct": sched["round_trip_pct"],
        }

    def _cent(rate_pct: float) -> float:
        raw = gross * (rate_pct / 100.0)
        return round(raw, 2)

    brokerage = _cent(sched["brokerage_pct"])
    if gross >= 1.0 and brokerage == 0.0:
        brokerage = 0.01
    vat = round(brokerage * (sched["vat_on_brokerage_pct"] / 100.0), 2)
    if brokerage >= 0.04 and vat == 0.0:
        vat = 0.01
    platform_levy = _cent(sched["platform_levy_pct"])
    secz_levy = _cent(sched["secz_levy_pct"])
    stamp_pct = sched["sell_stamp_duty_pct"] if act == "SELL" else sched["buy_stamp_duty_pct"]
    stamp_duty = _cent(stamp_pct)
    cgt = _cent(sched["sell_cgt_pct"]) if act == "SELL" else 0.0

    # Ensure regulatory micro-levies reflect $0.01 minimum per line once consideration >= ~$5 (as on Morgan & Co notes)
    if cur == "USD" and gross >= 5.0:
        if platform_levy == 0.0:
            platform_levy = 0.01
        if secz_levy == 0.0:
            secz_levy = 0.01
        if act == "BUY" and stamp_duty == 0.0:
            stamp_duty = 0.01

    total_charges = round(brokerage + vat + platform_levy + secz_levy + stamp_duty + cgt, 2)
    total_fee_pct = round((total_charges / gross) * 100.0, 2) if gross > 0 else 0.0
    net_settlement = round(gross + total_charges, 2) if act == "BUY" else round(max(0.0, gross - total_charges), 2)

    return {
        "exchange": sched["exchange"],
        "currency": cur,
        "side": act,
        "shares": round(sh, 4),
        "price": round(px, 4),
        "gross": round(gross, 4),
        "brokerage_pct": sched["brokerage_pct"],
        "brokerage": brokerage,
        "vat_pct": sched["vat_on_brokerage_pct"],
        "vat": vat,
        "platform_levy_pct": sched["platform_levy_pct"],
        "platform_levy": platform_levy,
        "secz_levy_pct": sched["secz_levy_pct"],
        "secz_levy": secz_levy,
        "stamp_duty_pct": stamp_pct,
        "stamp_duty": stamp_duty,
        "cgt_pct": sched["sell_cgt_pct"] if act == "SELL" else 0.0,
        "cgt": cgt,
        "total_charges": total_charges,
        "total_fee_pct": total_fee_pct,
        "net_settlement": net_settlement,
        "round_trip_hurdle_pct": sched["round_trip_pct"],
    }


def resolve_fee_mode(raw: float | str | None, currency: str = "USD") -> tuple[bool, float]:
    """Return (is_statutory, effective_single_side_pct) from settings ('statutory', 'auto', or float)."""
    cur = "ZWG" if str(currency or "USD").upper() == "ZWG" else "USD"
    sched = ZSE_FEE_SCHEDULE if cur == "ZWG" else VFEX_FEE_SCHEDULE
    if isinstance(raw, str):
        s = raw.strip().lower()
        if s in ("statutory", "auto", "morgan", "default", ""):
            return True, round(float(sched["round_trip_pct"]) / 2.0, 2)
        try:
            return False, max(0.0, float(s))
        except ValueError:
            return True, round(float(sched["round_trip_pct"]) / 2.0, 2)
    if raw is None:
        return True, round(float(sched["round_trip_pct"]) / 2.0, 2)
    return False, max(0.0, float(raw))


def parse_contract_note_text(text: str, store: "VFEXStore | None" = None) -> dict[str, Any]:
    """Parse a Morgan & Co / VFEX / ZSE PDF-extracted or pasted contract note into structured trade + fees."""
    raw = str(text or "").strip()
    if not raw:
        raise ValueError("Contract note text is empty.")

    lines = [ln.strip() for ln in raw.splitlines() if ln.strip()]
    joined = "\n".join(lines)
    low = joined.lower()

    # Currency detection (ZWG / ZiG vs USD)
    currency = "ZWG" if any(k in low for k in ("zwg", "zig", "zw$")) and "usd" not in low else "USD"

    # Shares & Security Name extraction
    shares: float | None = None
    security_name = ""
    price: float | None = None
    gross: float | None = None

    m_ord = re.search(r"([A-Za-z][A-Za-z0-9 &().,'-]{2,55}?)\s+([\d,]+(?:\.\d+)?)\s+ORDINARY\s+SHARES", joined, re.I)
    if m_ord:
        security_name = re.sub(r"\s+", " ", m_ord.group(1)).strip()
        shares = _safe_float(m_ord.group(2).replace(",", ""))

    m_px = re.search(r"(?:at\s+(?:a\s+price\s+of\s+)?|price\s*\([^)]+\)\s*:?)\s*(?:US\$|ZWG|ZiG|ZW\$|\$)?\s*([\d,]+\.\d{2,})", joined, re.I)
    if m_px:
        price = _safe_float(m_px.group(1).replace(",", ""))

    # Table line fallback: "ECONET INFRACO   38   $0.2235   $8.4930"
    for ln in lines:
        m_tbl = re.match(
            r"^([A-Za-z][A-Za-z0-9 &().,'-]{1,50}?)\s{2,}([\d,]+(?:\.\d+)?)\s+(?:US\$|ZWG|ZiG|ZW\$|\$)?([\d,]+\.\d+)\s+(?:US\$|ZWG|ZiG|ZW\$|\$)?([\d,]+\.\d+)\b",
            ln,
        )
        if m_tbl:
            cand_name = re.sub(r"\s+", " ", m_tbl.group(1)).strip()
            if not any(bad in cand_name.lower() for bad in ("description", "less charges", "brokerage", "total", "sub total")):
                security_name = security_name or cand_name
                shares = shares or _safe_float(m_tbl.group(2).replace(",", ""))
                price = price or _safe_float(m_tbl.group(3).replace(",", ""))
                gross = _safe_float(m_tbl.group(4).replace(",", ""))
                break

    if not shares or shares <= 0 or not price or price < 0:
        raise ValueError("Could not locate shares or unit price in contract note.")

    if gross is None:
        gross = round(shares * price, 4)

    # Resolve symbol from company name or explicit ticker
    alias_idx = _build_symbol_alias_index(store) if store is not None else {
        k: _clean_company_aliases(v, k) for k, v in KNOWN_VFEX_SYMBOLS.items()
    }
    stored_syms = (set(store.state.get("prices", {}).keys()) | set(KNOWN_VFEX_SYMBOLS.keys())) if store is not None else set(KNOWN_VFEX_SYMBOLS.keys())
    matched = _match_news_symbols(f"{security_name} {joined[:400]} VFEX ZSE", alias_idx, stored_syms)
    symbol = matched[0] if matched else ""
    symbol_matched = bool(symbol)
    if not symbol and security_name:
        toks = [re.sub(r"[^A-Z0-9]", "", w.upper()) for w in security_name.split() if len(w) >= 2]
        symbol = (toks[-1][:5] if toks else "UNKNOWN") or "UNKNOWN"
    if not symbol:
        raise ValueError("Could not identify stock symbol from contract note.")

    # Date extraction (prefer DD/MM/YYYY or YYYY-MM-DD, fallback today)
    trade_date = ""
    for pat, fmt in (
        (r"\b(\d{4}-\d{2}-\d{2})\b", "%Y-%m-%d"),
        (r"\b(\d{1,2}/\d{1,2}/\d{4})\b", "%d/%m/%Y"),
        (r"\b(\d{1,2}-\d{1,2}-\d{4})\b", "%d-%m-%Y"),
    ):
        for dm in re.finditer(pat, joined):
            try:
                trade_date = datetime.strptime(dm.group(1), fmt).strftime("%Y-%m-%d")
                break
            except ValueError:
                continue
        if trade_date:
            break
    if not trade_date:
        trade_date = datetime.now(timezone.utc).date().isoformat()

    # Right-column numeric matcher on itemized fee lines (ignores left-column % rate)
    def _line_amt(key_regex: str) -> float | None:
        for ln in lines:
            if re.search(key_regex, ln, re.I):
                m_end = re.search(r"(?:US\$|ZWG|ZiG|ZW\$|\$)?\s*([\d,]+\.\d+)\s*$", ln)
                if m_end:
                    val = _safe_float(m_end.group(1).replace(",", ""))
                    if val is not None:
                        return round(val, 2)
        return None

    brk = _line_amt(r"\bBrokerage\s+fees?\b")
    cgt = _line_amt(r"\bCapital\s+gains\b")
    plat = _line_amt(r"\bPlatform\s+Levy\b")
    secz = _line_amt(r"\bSECZ\s+Levy\b")
    stamp = _line_amt(r"\bStamp\s+Duty\b")
    vat = _line_amt(r"\bVAT\s+on\s+Brokerage\b|\bVAT\s+Total\b")
    tot_chg = _line_amt(r"\bTotal\s+Charges\b")
    net_cons = _line_amt(r"\bTotal\s+Net\s+Consideration\b|\bNet\s+Settlement\b")

    # Side determination: explicit Sell cues OR Net < Gross OR CGT > 0 -> SELL; Stamp > 0 or Net > Gross -> BUY
    sell_cue = bool(re.search(r"\b(we confirm we have sold|sale\s+of|sold\s+the\s+following)\b", low))
    buy_cue = bool(re.search(r"\b(we confirm we have bought|purchased|delivery against payment|delivered in good order against payment)\b", low))
    if sell_cue and not buy_cue:
        side = "SELL"
    elif net_cons is not None and abs(net_cons - gross) > 0.005:
        side = "SELL" if net_cons < gross else "BUY"
    elif (cgt or 0.0) > 0.0 and (stamp or 0.0) == 0.0:
        side = "SELL"
    else:
        side = "BUY"

    calc = calculate_trade_charges(currency, side, shares, price)
    final_charges = tot_chg if tot_chg is not None else (
        round(sum(x or 0.0 for x in (brk, vat, plat, secz, stamp, cgt)), 2)
        if any(x is not None for x in (brk, vat, plat, secz, stamp, cgt))
        else calc["total_charges"]
    )
    final_net = net_cons if net_cons is not None else (
        round(gross + final_charges, 2) if side == "BUY" else round(max(0.0, gross - final_charges), 2)
    )
    contract_note = {
        **calc,
        "brokerage": brk if brk is not None else calc["brokerage"],
        "vat": vat if vat is not None else calc["vat"],
        "platform_levy": plat if plat is not None else calc["platform_levy"],
        "secz_levy": secz if secz is not None else calc["secz_levy"],
        "stamp_duty": stamp if stamp is not None else calc["stamp_duty"],
        "cgt": cgt if cgt is not None else calc["cgt"],
        "total_charges": round(final_charges, 2),
        "total_fee_pct": round((final_charges / gross) * 100.0, 2) if gross > 0 else 0.0,
        "net_settlement": round(final_net, 2),
    }

    broker = "Morgan & Co" if "morgan" in low else ("C-TRADE" if "c-trade" in low else "Contract Note")
    note_hash = hashlib.sha1(f"{trade_date}|{side}|{symbol}|{shares:.4f}|{price:.4f}".encode("utf-8")).hexdigest()[:12]
    return {
        "ok": True,
        "broker": broker,
        "side": side,
        "symbol": symbol,
        "symbol_matched": symbol_matched,
        "security_name": security_name or symbol,
        "currency": currency,
        "shares": round(shares, 6),
        "price": round(price, 4),
        "gross": round(gross, 4),
        "total_charges": round(final_charges, 2),
        "net_settlement": round(final_net, 2),
        "date": trade_date,
        "note_hash": note_hash,
        "contract_note": contract_note,
    }


def extract_contract_note_file(path: Path, store: "VFEXStore | None" = None) -> dict[str, Any]:
    """Read a PDF (via local pdftotext) or text contract note file and parse it cleanly."""
    p = Path(path).expanduser()
    if not p.exists() or not p.is_file():
        raise ValueError(f"Contract note file not found: {p}")
    if p.suffix.lower() == ".pdf":
        try:
            proc = subprocess.run(
                ["pdftotext", "-layout", str(p), "-"],
                capture_output=True,
                text=True,
                timeout=12,
                check=False,
            )
        except OSError as exc:
            raise ValueError(f"Could not run pdftotext: {exc}") from exc
        if proc.returncode != 0:
            raise ValueError(f"pdftotext failed ({proc.returncode}): {proc.stderr.strip()}")
        raw_text = proc.stdout
    else:
        raw_text = p.read_text(encoding="utf-8", errors="replace")
    parsed = parse_contract_note_text(raw_text, store=store)
    parsed["file_name"] = p.name
    parsed["file_path"] = str(p)
    return parsed


def scan_local_pdf_notes(directory: str | Path = "~/Downloads", limit: int = 8) -> list[dict[str, str]]:
    """Return recent PDF filenames in directory for 1-click contract-note preview/import in Tab 4."""
    d = Path(directory).expanduser()
    if not d.exists() or not d.is_dir():
        return []
    pdfs = sorted(d.glob("*.pdf"), key=lambda fp: fp.stat().st_mtime, reverse=True)
    return [{"name": fp.name, "path": str(fp)} for fp in pdfs[:limit]]


def _default_paper_weights() -> dict[str, Any]:
    return {
        "dip_mult": 1.0,
        "rsi_mult": 1.0,
        "book_mult": 1.0,
        "news_mult": 1.0,
        "volume_mult": 1.0,
        "wide_spread_penalty": 1.0,
        "zse_hurdle_mult": 1.0,
        "min_entry_score": 22,
    }


PAPER_PLAYBOOKS = ("Dip Reversal", "Book Imbalance", "News Catalyst", "DTR Flow")
GROK_FEATURE_KEYS = ("bias", "dip", "rsi_oversold", "book", "news", "volume", "regime", "spread", "zse")
GROK_MIN_EPISODES = 18
GROK_HIDDEN_DIM = 6


def _default_grok_state() -> dict[str, Any]:
    """Initialize Grokking-inspired residual neural trainer and generalization gate."""
    return {
        "enabled": False,
        "status": "Accumulating History",
        "feature_order": list(GROK_FEATURE_KEYS),
        "hidden_dim": GROK_HIDDEN_DIM,
        "residual_alpha": 0.45,
        "W1": [],
        "b1": [],
        "W2": [],
        "b2": 0.0,
        "metrics": {
            "episodes_total": 0,
            "min_episodes": GROK_MIN_EPISODES,
            "train_count": 0,
            "val_count": 0,
            "epochs_run": 0,
            "best_epoch": 0,
            "train_acc_pct": 0.0,
            "val_acc_pct": 0.0,
            "linear_val_loss": 0.0,
            "grok_val_loss": 0.0,
            "linear_val_acc_pct": 0.0,
            "val_gain_pct": 0.0,
            "weight_l2_norm": 0.0,
            "initial_weight_l2_norm": 0.0,
            "generalization_gap_pct": 0.0,
            "last_trained": "",
        },
    }


def _default_exit_policy() -> dict[str, Any]:
    """Experience-adaptive exit policy bounds."""
    return {
        "caution_exit_strictness": 0,  # 0=exit immediately on <=-15 caution; 1=require official or <=-2.5% drop; 2=hold floor strict
        "swing_take_pct": 4.5,
        "zse_take_pct": 6.5,
        "hard_stop_pct": -8.0,
        "core_min_hold": 14,
        "swing_min_hold": 3,
        "premature_exit_losses": 0,
    }


def _default_mahoraga_brain() -> dict[str, Any]:
    """Initialize zero-dependency online RL / contextual model for Mahoraga adaptation."""
    return {
        "adaptations_spun": 0,
        "logistic_weights": {
            "bias": 0.15,
            "dip": 0.60,
            "rsi_oversold": 0.45,
            "book": 0.35,
            "news": 0.55,
            "volume": 0.40,
            "regime": 0.25,
            "spread": -0.55,
            "zse": -0.25,
        },
        "playbooks": {
            pb: {"wins": 0, "losses": 0, "total_net_pct": 0.0, "mult": 1.0}
            for pb in PAPER_PLAYBOOKS
        },
        "payoffs": {"avg_win_pct": 8.5, "avg_loss_pct": 5.0},
        "immunities": {},
        "exit_policy": _default_exit_policy(),
        "grok": _default_grok_state(),
    }


def _compute_market_regime(prices_map: dict[str, dict[str, Any]], intel: dict[str, Any] | None = None) -> dict[str, Any]:
    """Classify overall VFEX/ZSE session into Risk-On / Neutral / Risk-Off with dynamic cash floor."""
    adv = dec = total = 0
    for entry in (prices_map or {}).values():
        if not isinstance(entry, dict) or float(entry.get("price") or 0.0) <= 0:
            continue
        total += 1
        ch = entry.get("change_pct")
        if ch is not None:
            if float(ch) > 0.1:
                adv += 1
            elif float(ch) < -0.1:
                dec += 1
    breadth_ratio = ((adv - dec) / total) if total > 0 else 0.0
    vx_intel = (intel or {}).get("vfex") if isinstance(intel, dict) else {}
    foreign_net = float((vx_intel or {}).get("foreign_net") or 0.0)

    if breadth_ratio >= 0.12 or (breadth_ratio >= 0.0 and foreign_net >= 10000.0):
        label, score, cash_floor = "Risk-On", 1.0, 15.0
    elif breadth_ratio <= -0.12 or (breadth_ratio < 0.0 and foreign_net <= -25000.0):
        label, score, cash_floor = "Risk-Off", -1.0, 40.0
    else:
        label, score, cash_floor = "Neutral", 0.0, 25.0

    return {
        "label": label,
        "score": score,
        "cash_floor_pct": cash_floor,
        "advancers": adv,
        "decliners": dec,
        "total": total,
        "breadth_pct": round(breadth_ratio * 100.0, 1),
        "foreign_net": round(foreign_net, 2),
    }


def _classify_agent_playbook(
    dip_pts: float,
    rsi_pts: float,
    book_pts: float,
    news_pts: float,
    vol_pts: float,
) -> str:
    """Assign primary strategy archetype driving a candidate entry."""
    scores = [
        ("News Catalyst", news_pts),
        ("Dip Reversal", dip_pts + rsi_pts),
        ("DTR Flow", vol_pts),
        ("Book Imbalance", book_pts),
    ]
    scores.sort(key=lambda kv: -float(kv[1]))
    return scores[0][0]


def _mahoraga_feature_vector(feats: dict[str, Any]) -> dict[str, float]:
    """Normalize raw candidate features into bounded 16-dim universal model inputs."""
    dip = max(0.0, float(feats.get("dip_30d") or 0.0))
    rsi = feats.get("rsi14")
    rsi_os = max(-1.5, min(1.5, (50.0 - float(rsi)) / 25.0)) if rsi is not None else 0.0
    book_r = max(0.0, float(feats.get("book_ratio") or 0.0) - 1.0)
    news_imp = float(feats.get("news_impact") or 0.0)
    spread = max(0.0, float(feats.get("spread_pct") or 0.0))
    has_vol = 1.0 if float(feats.get("vol_pts") or 0.0) > 0.0 else 0.0
    regime_s = float(feats.get("regime_score") or 0.0)
    fb = _load_foundation_brain()
    macro = (fb.get("macro_snapshot") or {}) if isinstance(fb, dict) else {}
    return {
        "bias": 1.0,
        "dip": round(min(1.5, dip / 10.0), 4),
        "rsi_oversold": round(rsi_os, 4),
        "book": round(min(1.5, book_r / 3.0), 4),
        "news": round(max(-1.5, min(1.5, news_imp / 20.0)), 4),
        "volume": has_vol,
        "regime": round(max(-1.0, min(1.0, regime_s)), 2),
        "spread": round(min(2.0, spread / 12.0), 4),
        "zse": 1.0 if feats.get("is_zse") else 0.0,
        "mom_5d": round(max(-1.5, min(1.5, float(feats.get("mom_5d") or 0.0))), 4),
        "mom_20d": round(max(-1.5, min(1.5, float(feats.get("mom_20d") or 0.0))), 4),
        "trend_ma": round(max(-1.5, min(1.5, float(feats.get("trend_ma") or 0.0))), 4),
        "vol_20d": round(max(0.0, min(2.0, float(feats.get("vol_20d") or 0.0))), 4),
        "drawdown_60d": round(max(0.0, min(1.5, float(feats.get("drawdown_60d") or 0.0))), 4),
        "macro_gold": round(float(feats.get("macro_gold", macro.get("macro_gold", 0.0)) or 0.0), 4),
        "macro_vix": round(float(feats.get("macro_vix", macro.get("macro_vix", 0.0)) or 0.0), 4),
    }


def _grok_mlp_logit(grok: dict[str, Any], feat_vec: dict[str, float]) -> float:
    """Forward pass of compact 9 -> H -> 1 tanh residual network (pure Python)."""
    import math

    w1 = grok.get("W1") or []
    b1 = grok.get("b1") or []
    w2 = grok.get("W2") or []
    if not w1 or not b1 or not w2 or len(w1) != len(w2) or len(b1) != len(w2):
        return 0.0
    keys = grok.get("feature_order") or list(GROK_FEATURE_KEYS)
    x = [float(feat_vec.get(k, 0.0)) for k in keys]
    out = float(grok.get("b2") or 0.0)
    for j, row in enumerate(w1):
        if len(row) != len(x):
            return 0.0
        pre = float(b1[j]) + sum(float(row[i]) * x[i] for i in range(len(x)))
        out += float(w2[j]) * math.tanh(max(-6.0, min(6.0, pre)))
    return max(-4.0, min(4.0, out))


_FOUNDATION_BRAIN_CACHE: dict[str, Any] | None = None
_FOUNDATION_BRAIN_MTIME: float = -1.0


def _load_foundation_brain() -> dict[str, Any] | None:
    """Load compact zero-dependency pre-trained Mahoraga foundation weights if present."""
    global _FOUNDATION_BRAIN_CACHE, _FOUNDATION_BRAIN_MTIME
    wpath = Path(__file__).resolve().parent / "mahoraga_weights.json"
    try:
        if not wpath.exists():
            return None
        mt = wpath.stat().st_mtime
        if _FOUNDATION_BRAIN_CACHE is not None and mt == _FOUNDATION_BRAIN_MTIME:
            return _FOUNDATION_BRAIN_CACHE
        data = json.loads(wpath.read_text(encoding="utf-8"))
        if isinstance(data, dict) and (data.get("models") or (data.get("W1") and data.get("W2"))):
            _FOUNDATION_BRAIN_CACHE = data
            _FOUNDATION_BRAIN_MTIME = mt
            return data
    except Exception:
        pass
    return None


def _layernorm_1d(vec: list[float], eps: float = 1e-5) -> list[float]:
    import math
    n = len(vec)
    if n == 0:
        return vec
    mean = sum(vec) / n
    var = sum((v - mean) ** 2 for v in vec) / n
    inv = 1.0 / math.sqrt(var + eps)
    return [(v - mean) * inv for v in vec]


def _foundation_predict(fb: dict[str, Any], feat_vec: dict[str, float]) -> tuple[float, float, float, float] | None:
    """Pure-Python forward pass for v2 single MLP or v3 Deep Residual MLP Ensemble -> (p5, ret5, p20, ret20)."""
    import math

    lin5 = fb.get("linear_5d") or []
    lin20 = fb.get("linear_20d") or []
    keys = fb.get("feature_order") or []
    if not keys or len(lin5) != len(keys) or len(lin20) != len(keys):
        return None
    x = [float(feat_vec.get(k, 0.0)) for k in keys]
    alpha = float(fb.get("residual_alpha") or 0.5)
    b5 = max(-5.0, min(5.0, sum(float(lin5[i]) * x[i] for i in range(len(x)))))
    b20 = max(-5.0, min(5.0, sum(float(lin20[i]) * x[i] for i in range(len(x)))))

    # v3: Deep Residual MLP Ensemble (16 -> h1 -> h2 -> 4 with LayerNorm + skip)
    models = fb.get("models")
    if isinstance(models, list) and models:
        p5_s = ret5_s = p20_s = ret20_s = 0.0
        for m in models:
            w1, b1 = m["W1"], m["b1"]
            w2, b2 = m["W2"], m["b2"]
            wskip = m["Wskip"]
            w3, b3 = m["W3"], m["b3"]
            z1 = [float(b1[j]) + sum(float(w1[j][i]) * x[i] for i in range(len(x))) for j in range(len(w1))]
            a1 = [math.tanh(max(-6.0, min(6.0, v))) for v in _layernorm_1d(z1)]
            z2 = [
                float(b2[j])
                + sum(float(w2[j][i]) * a1[i] for i in range(len(a1)))
                + sum(float(wskip[j][i]) * x[i] for i in range(len(x)))
                for j in range(len(w2))
            ]
            a2 = [math.tanh(max(-6.0, min(6.0, v))) for v in _layernorm_1d(z2)]
            out = [float(b3[k]) + sum(float(w3[k][j]) * a2[j] for j in range(len(a2))) for k in range(4)]
            z5 = max(-6.0, min(6.0, b5 + alpha * max(-4.0, min(4.0, out[0]))))
            z20 = max(-6.0, min(6.0, b20 + alpha * max(-4.0, min(4.0, out[2]))))
            p5_s += 1.0 / (1.0 + math.exp(-z5))
            ret5_s += out[1] * 10.0
            p20_s += 1.0 / (1.0 + math.exp(-z20))
            ret20_s += out[3] * 15.0
        k_n = float(len(models))
        return p5_s / k_n, ret5_s / k_n, p20_s / k_n, ret20_s / k_n

    # v2 fallback: single hidden layer MLP
    w1, b1, w2, b2 = fb.get("W1") or [], fb.get("b1") or [], fb.get("W2") or [], fb.get("b2") or []
    if not w1 or not w2 or len(w2) != 4 or len(b2) != 4:
        return None
    h = [math.tanh(max(-6.0, min(6.0, float(b1[j]) + sum(float(w1[j][i]) * x[i] for i in range(len(x)))))) for j in range(len(w1))]
    out = [float(b2[k]) + sum(float(w2[k][j]) * h[j] for j in range(len(h))) for k in range(4)]
    z5 = max(-6.0, min(6.0, b5 + alpha * max(-4.0, min(4.0, out[0]))))
    z20 = max(-6.0, min(6.0, b20 + alpha * max(-4.0, min(4.0, out[2]))))
    return 1.0 / (1.0 + math.exp(-z5)), out[1] * 10.0, 1.0 / (1.0 + math.exp(-z20)), out[3] * 15.0


def _mahoraga_predict(
    brain: dict[str, Any],
    feat_vec: dict[str, float],
    playbook: str,
    is_zse: bool,
) -> dict[str, float]:
    """Predict P(Win), EWMA expected net return %, and UCB exploration edge."""
    import math

    lw = brain.get("logistic_weights") or {}
    pb_info = (brain.get("playbooks") or {}).get(playbook) or {}
    pb_mult = float(pb_info.get("mult") or 1.0)
    pb_trials = max(0, int(pb_info.get("wins") or 0) + int(pb_info.get("losses") or 0))
    payoffs = brain.get("payoffs") or {}
    avg_win = max(4.0, float(payoffs.get("avg_win_pct") or 8.5))
    avg_loss = max(2.5, float(payoffs.get("avg_loss_pct") or 5.0))

    z = sum(float(lw.get(k, 0.0)) * float(v) for k, v in feat_vec.items())
    z += (pb_mult - 1.0) * 1.15
    grok = brain.get("grok") or {}
    if grok.get("enabled") and grok.get("W1") and grok.get("W2"):
        z += float(grok.get("residual_alpha") or 0.45) * _grok_mlp_logit(grok, feat_vec)
    z = max(-6.0, min(6.0, z))
    prob = 1.0 / (1.0 + math.exp(-z))

    # Blend with pre-trained multi-market foundation brain if available and enabled
    fb = _load_foundation_brain()
    if fb and fb.get("enabled"):
        fpred = _foundation_predict(fb, feat_vec)
        if fpred is not None:
            p5, _ret5, p20, _ret20 = fpred
            fb_prob = 0.45 * p5 + 0.55 * p20
            # Blend: 65% foundation world-model + 35% local live adaptation
            prob = 0.65 * fb_prob + 0.35 * prob

    fee_drag = 4.38 if is_zse else 2.08
    exp_net = (prob * avg_win - (1.0 - prob) * avg_loss) - (fee_drag * 0.45)
    ucb_bonus = min(2.4, 2.4 / math.sqrt(pb_trials + 1.0))
    return {
        "win_prob_pct": round(prob * 100.0, 1),
        "expected_net_pct": round(exp_net, 2),
        "ucb_bonus_pct": round(ucb_bonus, 2),
        "ucb_edge_pct": round(exp_net + ucb_bonus, 2),
        "pb_mult": round(pb_mult, 2),
    }


def _build_history_episodes(
    agent: dict[str, Any],
    history_map: dict[str, list[dict[str, Any]]],
    prices_map: dict[str, dict[str, Any]],
    horizon_days: int = 4,
) -> list[dict[str, Any]]:
    """Build strictly chronological labeled episodes (zero lookahead) from OHLC history, trades, and shadows."""
    # Compute historical per-date market breadth regime strictly from cross-sectional prior closes
    date_rets: dict[str, list[float]] = {}
    clean_by_sym: dict[str, list[dict[str, Any]]] = {}
    for sym, raw_rows in (history_map or {}).items():
        clean = _dedupe_sorted_history(raw_rows)
        if not clean:
            continue
        clean_by_sym[sym] = clean
        for i in range(1, len(clean)):
            dt = str(clean[i].get("date") or "")
            c_prev = float(clean[i - 1].get("close", clean[i - 1].get("price")) or 0.0)
            c_cur = float(clean[i].get("close", clean[i].get("price")) or 0.0)
            if dt and c_prev > 0 and c_cur > 0:
                date_rets.setdefault(dt, []).append(((c_cur - c_prev) / c_prev) * 100.0)

    regime_by_date: dict[str, float] = {}
    for dt, rets in date_rets.items():
        tot = len(rets)
        adv = sum(1 for r in rets if r > 0.1)
        dec = sum(1 for r in rets if r < -0.1)
        br = ((adv - dec) / tot) if tot > 0 else 0.0
        regime_by_date[dt] = 1.0 if br >= 0.12 else (-1.0 if br <= -0.12 else 0.0)

    episodes: list[dict[str, Any]] = []
    seen_keys: set[tuple[str, str, str]] = set()
    horizons = (3, horizon_days) if horizon_days != 3 else (3, 5)

    for sym, clean in clean_by_sym.items():
        if len(clean) < 7:
            continue
        meta = prices_map.get(sym) or {}
        cur_code = infer_currency(sym, meta)
        is_zse = (cur_code == "ZWG")
        for h in horizons:
            for idx in range(3, len(clean) - h):
                row_t = clean[idx]
                row_f = clean[idx + h]
                dt = str(row_t.get("date") or "")
                px_t = float(row_t.get("close", row_t.get("price")) or 0.0)
                px_f = float(row_f.get("close", row_f.get("price")) or 0.0)
                if not dt or px_t <= 0 or px_f <= 0:
                    continue
                k = (dt, sym, f"H{h}")
                if k in seen_keys:
                    continue
                seen_keys.add(k)
                window = clean[max(0, idx - 29): idx + 1]
                tech = compute_symbol_technicals(window, px_t)
                hi = float(row_t.get("high") or px_t)
                lo = float(row_t.get("low") or px_t)
                candle_sp = ((hi - lo) / px_t * 100.0) if hi > lo and px_t > 0 else 1.5
                spread_pct = round(max(0.5, min(6.0, candle_sp)), 2)
                feat_vec = _mahoraga_feature_vector({
                    "dip_30d": max(0.0, float(tech["drop30"] or 0.0)),
                    "rsi14": tech["rsi14"],
                    "book_ratio": 1.0,
                    "news_impact": 0.0,
                    "spread_pct": spread_pct,
                    "vol_pts": 0.0,
                    "regime_score": regime_by_date.get(dt, 0.0),
                    "is_zse": is_zse,
                })
                buy_n = calculate_trade_charges(cur_code, "BUY", 100.0, px_t)
                sell_n = calculate_trade_charges(cur_code, "SELL", 100.0, px_f)
                net_pct = (
                    ((sell_n["net_settlement"] - buy_n["net_settlement"]) / buy_n["net_settlement"]) * 100.0
                    if buy_n["net_settlement"] > 0 else 0.0
                )
                episodes.append({
                    "date": dt,
                    "symbol": sym,
                    "source": f"H{h}",
                    "feat_vec": feat_vec,
                    "y": 1.0 if net_pct >= 0.5 else 0.0,
                    "net_pnl_pct": round(net_pct, 2),
                })

    for sh in (agent.get("shadows") or []):
        if not sh.get("resolved") or sh.get("shadow_net_pct") is None:
            continue
        dt = str(sh.get("date") or "")
        sym = str(sh.get("symbol") or "")
        fv = sh.get("feat_vec") or {}
        if not dt or not sym or not fv:
            continue
        k = (dt, sym, "SHADOW")
        if k in seen_keys:
            continue
        seen_keys.add(k)
        net_pct = float(sh.get("shadow_net_pct") or 0.0)
        episodes.append({
            "date": dt,
            "symbol": sym,
            "source": "SHADOW",
            "feat_vec": fv,
            "y": 1.0 if net_pct >= 0.5 else 0.0,
            "net_pnl_pct": round(net_pct, 2),
        })

    for tr in (agent.get("trades") or []):
        if tr.get("side") != "SELL":
            continue
        dt = str(tr.get("date") or "")
        sym = str(tr.get("symbol") or "")
        tfeats = tr.get("entry_features") or {}
        fv = tr.get("entry_feat_vec") or (_mahoraga_feature_vector(tfeats) if tfeats else {})
        if not dt or not sym or not fv:
            continue
        k = (dt, sym, "TRADE")
        if k in seen_keys:
            continue
        seen_keys.add(k)
        net_pct = float(tr.get("net_pnl_pct") or 0.0)
        episodes.append({
            "date": dt,
            "symbol": sym,
            "source": "TRADE",
            "feat_vec": fv,
            "y": 1.0 if net_pct >= 0.5 else 0.0,
            "net_pnl_pct": round(net_pct, 2),
        })

    episodes.sort(key=lambda e: (e["date"], e["symbol"], e["source"]))
    return episodes[-1200:]


def _train_grokking_model(
    brain: dict[str, Any],
    episodes: list[dict[str, Any]],
    today_str: str,
    epochs: int = 160,
    lr: float = 0.06,
    weight_decay: float = 0.14,
    ema_alpha: float = 0.85,
    ema_lamb: float = 1.5,
    seed: int = 42,
) -> dict[str, Any]:
    """Multi-epoch Grokfast EMA + heavy L2 weight decay over 70/30 chronological split with OOS gate."""
    import copy
    import math
    import random

    grok = brain.setdefault("grok", _default_grok_state())
    metrics = grok.setdefault("metrics", dict(_default_grok_state()["metrics"]))
    keys = list(grok.get("feature_order") or GROK_FEATURE_KEYS)
    h_dim = int(grok.get("hidden_dim") or GROK_HIDDEN_DIM)
    alpha = float(grok.get("residual_alpha") or 0.45)

    n_total = len(episodes)
    metrics["episodes_total"] = n_total
    metrics["min_episodes"] = GROK_MIN_EPISODES
    metrics["last_trained"] = today_str

    if n_total < GROK_MIN_EPISODES:
        grok["enabled"] = False
        grok["status"] = "Accumulating History"
        metrics.update({
            "train_count": 0,
            "val_count": 0,
            "epochs_run": 0,
            "best_epoch": 0,
            "train_acc_pct": 0.0,
            "val_acc_pct": 0.0,
            "linear_val_loss": 0.0,
            "grok_val_loss": 0.0,
            "linear_val_acc_pct": 0.0,
            "val_gain_pct": 0.0,
            "weight_l2_norm": 0.0,
            "initial_weight_l2_norm": 0.0,
            "generalization_gap_pct": 0.0,
        })
        return grok

    val_len = max(5, int(round(n_total * 0.30)))
    split_idx = n_total - val_len
    if split_idx < 10:
        grok["enabled"] = False
        grok["status"] = "Accumulating History"
        return grok

    train_ep = episodes[:split_idx]
    val_ep = episodes[split_idx:]
    lw = brain.get("logistic_weights") or {}

    def _prep(ep_list: list[dict[str, Any]]) -> list[tuple[list[float], float, float]]:
        out: list[tuple[list[float], float, float]] = []
        for ep in ep_list:
            fv = ep.get("feat_vec") or {}
            xv = [float(fv.get(k, 0.0)) for k in keys]
            base_z = sum(float(lw.get(k, 0.0)) * float(fv.get(k, 0.0)) for k in keys)
            out.append((xv, float(ep.get("y") or 0.0), max(-5.0, min(5.0, base_z))))
        return out

    train_data = _prep(train_ep)
    val_data = _prep(val_ep)

    def _sigmoid(z_val: float) -> float:
        zc = max(-12.0, min(12.0, z_val))
        return 1.0 / (1.0 + math.exp(-zc))

    def _bce(p: float, y: float) -> float:
        pc = max(1e-7, min(1.0 - 1e-7, p))
        return -(y * math.log(pc) + (1.0 - y) * math.log(1.0 - pc))

    # Evaluate linear baseline strictly on validation split
    lin_loss = sum(_bce(_sigmoid(bz), y) for _, y, bz in val_data) / len(val_data)
    lin_acc = sum(1 for _, y, bz in val_data if (_sigmoid(bz) >= 0.5) == (y >= 0.5)) / len(val_data)

    in_dim = len(keys)
    rng = random.Random(seed)
    w1 = [[rng.gauss(0.0, 0.35) for _ in range(in_dim)] for _ in range(h_dim)]
    b1 = [0.0 for _ in range(h_dim)]
    w2 = [rng.gauss(0.0, 0.25) for _ in range(h_dim)]
    b2 = 0.0

    def _l2_norm() -> float:
        sq = sum(v * v for row in w1 for v in row) + sum(v * v for v in w2)
        return math.sqrt(sq)

    init_norm = _l2_norm()

    # Grokfast EMA buffers + Adam moments
    ema_w1 = [[0.0] * in_dim for _ in range(h_dim)]
    ema_b1 = [0.0] * h_dim
    ema_w2 = [0.0] * h_dim
    ema_b2 = 0.0

    m_w1 = [[0.0] * in_dim for _ in range(h_dim)]
    v_w1 = [[0.0] * in_dim for _ in range(h_dim)]
    m_b1 = [0.0] * h_dim
    v_b1 = [0.0] * h_dim
    m_w2 = [0.0] * h_dim
    v_w2 = [0.0] * h_dim
    m_b2 = 0.0
    v_b2 = 0.0

    def _eval_split(data: list[tuple[list[float], float, float]], cw1: list[list[float]], cb1: list[float], cw2: list[float], cb2: float) -> tuple[float, float]:
        loss_s = 0.0
        correct = 0
        for xv, y, bz in data:
            res = cb2
            for j in range(h_dim):
                pre = cb1[j] + sum(cw1[j][i] * xv[i] for i in range(in_dim))
                res += cw2[j] * math.tanh(max(-6.0, min(6.0, pre)))
            res = max(-4.0, min(4.0, res))
            p = _sigmoid(bz + alpha * res)
            loss_s += _bce(p, y)
            if (p >= 0.5) == (y >= 0.5):
                correct += 1
        return loss_s / len(data), correct / len(data)

    best_val_loss = lin_loss
    best_val_acc = lin_acc
    best_train_acc = sum(1 for _, y, bz in train_data if (_sigmoid(bz) >= 0.5) == (y >= 0.5)) / len(train_data)
    best_epoch = 0
    best_norm = init_norm
    best_weights = (copy.deepcopy(w1), list(b1), list(w2), float(b2))

    beta1, beta2, eps = 0.9, 0.99, 1e-8
    n_tr = float(len(train_data))

    for ep_i in range(1, max(20, int(epochs)) + 1):
        gw1 = [[0.0] * in_dim for _ in range(h_dim)]
        gb1 = [0.0] * h_dim
        gw2 = [0.0] * h_dim
        gb2 = 0.0

        for xv, y, bz in train_data:
            hs = [0.0] * h_dim
            res = b2
            for j in range(h_dim):
                pre = b1[j] + sum(w1[j][i] * xv[i] for i in range(in_dim))
                h = math.tanh(max(-6.0, min(6.0, pre)))
                hs[j] = h
                res += w2[j] * h
            res_clamped = max(-4.0, min(4.0, res))
            p = _sigmoid(bz + alpha * res_clamped)
            dl_dz = (p - y) / n_tr
            dl_dres = dl_dz * alpha

            gb2 += dl_dres
            for j in range(h_dim):
                gw2[j] += dl_dres * hs[j]
                dl_dpre = dl_dres * w2[j] * (1.0 - hs[j] * hs[j])
                gb1[j] += dl_dpre
                row_g = gw1[j]
                for i in range(in_dim):
                    row_g[i] += dl_dpre * xv[i]

        b1_corr = 1.0 - (beta1 ** ep_i)
        b2_corr = 1.0 - (beta2 ** ep_i)
        wd_scale = max(0.0, 1.0 - lr * weight_decay)

        def _adam_gf_step(param: float, grad: float, ema_g: float, m_val: float, v_val: float, decay: bool = True) -> tuple[float, float, float, float]:
            new_ema = ema_alpha * ema_g + (1.0 - ema_alpha) * grad
            g_eff = grad + ema_lamb * new_ema
            new_m = beta1 * m_val + (1.0 - beta1) * g_eff
            new_v = beta2 * v_val + (1.0 - beta2) * (g_eff * g_eff)
            m_hat = new_m / b1_corr
            v_hat = new_v / b2_corr
            base_p = (param * wd_scale) if decay else param
            new_p = base_p - lr * m_hat / (math.sqrt(v_hat) + eps)
            return max(-3.0, min(3.0, new_p)), new_ema, new_m, new_v

        b2, ema_b2, m_b2, v_b2 = _adam_gf_step(b2, gb2, ema_b2, m_b2, v_b2, decay=False)
        for j in range(h_dim):
            w2[j], ema_w2[j], m_w2[j], v_w2[j] = _adam_gf_step(w2[j], gw2[j], ema_w2[j], m_w2[j], v_w2[j], decay=True)
            b1[j], ema_b1[j], m_b1[j], v_b1[j] = _adam_gf_step(b1[j], gb1[j], ema_b1[j], m_b1[j], v_b1[j], decay=False)
            for i in range(in_dim):
                w1[j][i], ema_w1[j][i], m_w1[j][i], v_w1[j][i] = _adam_gf_step(
                    w1[j][i], gw1[j][i], ema_w1[j][i], m_w1[j][i], v_w1[j][i], decay=True
                )

        if ep_i >= 5 and (ep_i % 4 == 0 or ep_i == epochs):
            tr_loss, tr_acc = _eval_split(train_data, w1, b1, w2, b2)
            va_loss, va_acc = _eval_split(val_data, w1, b1, w2, b2)
            # Prefer lower validation log-loss once accuracy matches/beats baseline
            if va_loss < best_val_loss and va_acc >= best_val_acc - 1e-9:
                best_val_loss = va_loss
                best_val_acc = va_acc
                best_train_acc = tr_acc
                best_epoch = ep_i
                best_norm = _l2_norm()
                best_weights = (copy.deepcopy(w1), list(b1), list(w2), float(b2))

    # Measure final epoch metrics if checkpoint stayed at epoch 0 so memorizing phase still shows honest numbers
    if best_epoch == 0:
        tr_loss_f, best_train_acc = _eval_split(train_data, w1, b1, w2, b2)
        best_val_loss, best_val_acc = _eval_split(val_data, w1, b1, w2, b2)
        best_norm = _l2_norm()

    improved = (best_epoch > 0) and (best_val_loss < lin_loss - 1e-3) and (best_val_acc >= lin_acc - 1e-9)
    bw1, bb1, bw2, bb2 = best_weights
    grok["W1"] = [[round(v, 5) for v in row] for row in bw1]
    grok["b1"] = [round(v, 5) for v in bb1]
    grok["W2"] = [round(v, 5) for v in bw2]
    grok["b2"] = round(bb2, 5)
    grok["enabled"] = bool(improved)
    grok["status"] = "Grokked (Active)" if improved else "Memorizing (Gated)"

    tr_pct = round(best_train_acc * 100.0, 1)
    va_pct = round(best_val_acc * 100.0, 1)
    lin_pct = round(lin_acc * 100.0, 1)
    metrics.update({
        "train_count": len(train_ep),
        "val_count": len(val_ep),
        "epochs_run": int(epochs),
        "best_epoch": int(best_epoch),
        "train_acc_pct": tr_pct,
        "val_acc_pct": va_pct,
        "linear_val_loss": round(lin_loss, 4),
        "grok_val_loss": round(best_val_loss, 4),
        "linear_val_acc_pct": lin_pct,
        "val_gain_pct": round(va_pct - lin_pct, 1),
        "weight_l2_norm": round(best_norm, 3),
        "initial_weight_l2_norm": round(init_norm, 3),
        "generalization_gap_pct": round(tr_pct - va_pct, 1),
    })
    return grok


def _default_paper_agent(starting_usd: float = 100.0, zwg_rate: float = 26.5) -> dict[str, Any]:
    start = max(10.0, float(starting_usd or 100.0))
    rate = max(1.0, float(zwg_rate or 26.5))
    usd_pool = round(start * 0.80, 2)
    zwg_pool_usd = round(start - usd_pool, 2)
    zwg_cash = round(zwg_pool_usd * rate, 2)
    today = datetime.now(timezone.utc).date().isoformat()
    return {
        "enabled": True,
        "starting_capital_usd": round(start, 2),
        "zwg_rate": round(rate, 4),
        "cash_usd": usd_pool,
        "cash_zwg": zwg_cash,
        "positions": {},
        "pending_orders": [],
        "trades": [],
        "equity_history": [
            {
                "date": today,
                "equity_usd": round(start, 2),
                "cash_usd": round(start, 2),
                "invested_usd": 0.0,
                "fees_paid_usd": 0.0,
            }
        ],
        "weights": _default_paper_weights(),
        "brain": _default_mahoraga_brain(),
        "shadows": [],
        "lessons": [],
        "cooldowns": {},
        "daily_actions": {"date": today, "buys": 0, "sells": 0},
        "last_step_date": "",
        "stats": {"wins": 0, "losses": 0, "total_closed": 0, "total_fees_usd": 0.0},
    }


class VFEXStore:
    """Manages persistent state for portfolio, watchlist, prices, and alerts."""

    def __init__(self, config_dir: Path | None = None) -> None:
        self.config_dir = config_dir or DEFAULT_CONFIG_DIR
        self.config_dir.mkdir(parents=True, exist_ok=True)
        self.state_file = self.config_dir / "state.json"
        self.backup_file = self.config_dir / "state.json.bak"
        self.lock_file = self.config_dir / ".state.lock"
        self.state: dict[str, Any] = self._load()

    @staticmethod
    def _default_state() -> dict[str, Any]:
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
            "strategy_tags": {},
            "trading_goal": "",
        }

    @contextlib.contextmanager
    def _state_lock(self, exclusive: bool = False):
        lock_fh = self.lock_file.open("a+", encoding="utf-8")
        try:
            fcntl.flock(lock_fh.fileno(), fcntl.LOCK_EX if exclusive else fcntl.LOCK_SH)
            try:
                yield
            finally:
                fcntl.flock(lock_fh.fileno(), fcntl.LOCK_UN)
        finally:
            lock_fh.close()

    def _atomic_write_text(self, target: Path, content: str, mode: int | None = None) -> None:
        fd, tmp_name = tempfile.mkstemp(prefix=f".{target.name}.", suffix=".tmp", dir=str(self.config_dir))
        tmp_path = Path(tmp_name)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                fh.write(content)
                fh.flush()
                os.fsync(fh.fileno())
            if mode is not None:
                os.chmod(tmp_path, mode)
            os.replace(tmp_path, target)
        except Exception:
            with contextlib.suppress(OSError):
                tmp_path.unlink(missing_ok=True)
            raise

    @staticmethod
    def _read_valid_state_file(path: Path) -> dict[str, Any] | None:
        if not path.exists():
            return None
        try:
            raw = path.read_text(encoding="utf-8")
            if not raw.strip():
                return None
            parsed = json.loads(raw)
            return parsed if isinstance(parsed, dict) else None
        except (OSError, json.JSONDecodeError):
            return None

    def _load(self) -> dict[str, Any]:
        with self._state_lock(exclusive=False):
            if self.state_file.exists():
                for attempt in range(3):
                    loaded = self._read_valid_state_file(self.state_file)
                    if loaded is not None:
                        return loaded
                    if attempt < 2:
                        time.sleep(0.02)
                backup_loaded = self._read_valid_state_file(self.backup_file)
                with contextlib.suppress(OSError):
                    corrupt_raw = self.state_file.read_text(encoding="utf-8", errors="replace")
                    if corrupt_raw.strip():
                        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
                        self._atomic_write_text(self.config_dir / f"state.json.corrupt.{stamp}", corrupt_raw)
                if backup_loaded is not None:
                    return backup_loaded
            return self._default_state()

    def save(self) -> None:
        payload = json.dumps(self.state, indent=2) + "\n"
        with self._state_lock(exclusive=True):
            if self.state_file.exists():
                existing = self._read_valid_state_file(self.state_file)
                if existing is not None:
                    self._atomic_write_text(self.backup_file, self.state_file.read_text(encoding="utf-8"))
            self._atomic_write_text(self.state_file, payload)

    def set_trading_goal(self, goal: str) -> str:
        """Persist a local UI trading goal override ('long', 'short', 'hybrid') or clear ('auto')."""
        s = str(goal or "").strip().lower()
        if s in ("auto", "clear", "default", ""):
            self.state["trading_goal"] = ""
            self.save()
            return "auto"
        norm = normalize_goal(s)
        self.state["trading_goal"] = norm
        self.save()
        return norm

    def get_strategy_tags(self) -> dict[str, str]:
        return dict(self.state.get("strategy_tags", {}))

    def get_strategy_tag(self, symbol: str, trading_goal: str = "hybrid") -> tuple[str, bool]:
        """Return (effective tag 'core'|'swing', is_explicitly_pinned)."""
        sym = symbol.upper()
        tags = self.state.get("strategy_tags", {})
        if sym in tags and tags[sym] in ("core", "swing"):
            return str(tags[sym]), True
        goal = normalize_goal(trading_goal)
        if goal == "long":
            return "core", False
        if goal == "short":
            return "swing", False
        # Hybrid default: targets/long holds lean core, newer positions lean swing
        if sym in self.state.get("targets", {}):
            return "core", False
        return "core" if sym in self.state.get("portfolio", {}) and len(self.state["portfolio"][sym].get("lots", [])) >= 2 else "swing", False

    def set_strategy_tag(self, symbol: str, tag: str) -> str:
        """Pin a symbol to 'core', 'swing', or 'auto' (clear pin)."""
        sym = symbol.upper()
        s = str(tag or "").strip().lower()
        tags = self.state.setdefault("strategy_tags", {})
        if s in ("auto", "clear", ""):
            tags.pop(sym, None)
            self.save()
            return "auto"
        if s not in ("core", "swing"):
            raise ValueError("Strategy tag must be 'core', 'swing', or 'auto'.")
        tags[sym] = s
        self.save()
        return s

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
        upper_limit: float | None = None,
        lower_limit: float | None = None,
        isin: str | None = None,
        security_type: str | None = None,
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
        up_v = upper_limit if upper_limit is not None else prev_entry.get("upper_limit")
        lo_v = lower_limit if lower_limit is not None else prev_entry.get("lower_limit")
        if up_v is not None and float(up_v) > 0:
            price_entry["upper_limit"] = round(float(up_v), 4)
        if lo_v is not None and float(lo_v) > 0:
            price_entry["lower_limit"] = round(float(lo_v), 4)

        self._apply_depth_fields(
            price_entry,
            best_bid=best_bid if best_bid is not None else prev_entry.get("best_bid"),
            best_ask=best_ask if best_ask is not None else prev_entry.get("best_ask"),
            bid_volume=bid_volume if bid_volume is not None else prev_entry.get("bid_volume"),
            ask_volume=ask_volume if ask_volume is not None else prev_entry.get("ask_volume"),
            currency=cur_code,
            company_name=company_name or prev_entry.get("company_name"),
            isin=isin or prev_entry.get("isin"),
            security_type=security_type or prev_entry.get("security_type"),
        )
        self.state["prices"][sym] = price_entry

        if track_history:
            open_val = float(open_price) if open_price is not None else float(price)
            history = _dedupe_sorted_history(self.state.setdefault("history", {}).setdefault(sym, []))
            existing = next((row for row in history if row.get("date") == today), None)
            if existing is not None:
                cur_open = float(open_price) if open_price is not None else float(existing.get("open", existing.get("price", price)))
                cur_high = max(float(existing.get("high", existing.get("price", price))), float(price), cur_open)
                cur_low = min(float(existing.get("low", existing.get("price", price))), float(price), cur_open)
                existing["open"] = round(cur_open, 4)
                existing["high"] = round(cur_high, 4)
                existing["low"] = round(cur_low, 4)
                existing["close"] = round(price, 4)
                existing["price"] = round(price, 4)
            else:
                history.append({
                    "date": today,
                    "open": round(open_val, 4),
                    "high": round(max(open_val, price), 4),
                    "low": round(min(open_val, price), 4),
                    "close": round(price, 4),
                    "price": round(price, 4),
                })
                history = _dedupe_sorted_history(history)
            self.state["history"][sym] = history[-180:]
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
        isin: str | None = None,
        security_type: str | None = None,
    ) -> None:
        if currency:
            entry["currency"] = currency
        if company_name:
            entry["company_name"] = str(company_name).strip()
        if isin:
            entry["isin"] = str(isin).strip().upper()
        if security_type:
            entry["security_type"] = str(security_type).strip().upper()
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
        isin: str | None = None,
        security_type: str | None = None,
    ) -> None:
        """Attach bid/ask depth metadata to an existing price entry without altering its price."""
        entry = self.state["prices"].get(symbol.upper())
        if entry:
            self._apply_depth_fields(entry, best_bid, best_ask, bid_volume, ask_volume, currency, company_name, isin, security_type)

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
        for h in _dedupe_sorted_history(self.state.get("history", {}).get(symbol.upper(), [])):
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

    def import_contract_note(
        self,
        source: dict[str, Any] | str | Path,
        tag: str | None = None,
        allow_duplicate: bool = False,
        dry_run: bool = False,
        is_text: bool = False,
    ) -> dict[str, Any]:
        """Parse & optionally commit a Morgan & Co / VFEX / ZSE PDF or text contract note."""
        if isinstance(source, dict):
            parsed = dict(source)
        elif is_text:
            parsed = parse_contract_note_text(str(source), store=self)
        else:
            parsed = extract_contract_note_file(Path(source), store=self)

        sym = str(parsed["symbol"]).upper()
        side = str(parsed["side"]).upper()
        sh = float(parsed["shares"])
        px = float(parsed["price"])
        dt = str(parsed["date"])
        nhash = str(parsed["note_hash"])

        duplicate = any(
            tr.get("note_hash") == nhash
            or (
                tr.get("date") == dt
                and str(tr.get("action", "")).upper() == side
                and str(tr.get("symbol", "")).upper() == sym
                and abs(float(tr.get("shares") or 0.0) - sh) < 1e-4
                and abs(float(tr.get("price") or 0.0) - px) < 1e-4
            )
            for tr in self.state.get("trades", [])
        )
        parsed["duplicate"] = duplicate

        if dry_run:
            return parsed

        if duplicate and not allow_duplicate:
            raise ValueError(f"Duplicate contract note already in ledger ({dt} {side} {sh:g} {sym} @ ${px:.4f}).")

        if side == "SELL":
            realized = self.sell(sym, sh, price=px, date=dt)
            parsed["realized_pnl"] = round(realized, 2)
        else:
            self.buy(sym, sh, px, date=dt)
            if sym not in self.state.get("watchlist", []):
                self.state.setdefault("watchlist", []).append(sym)
            if tag and tag in ("core", "swing", "auto"):
                self.set_strategy_tag(sym, tag)

        # Attach itemized contract_note & fingerprint onto matching latest trade
        for tr in reversed(self.state.get("trades", [])):
            if (
                tr.get("date") == dt
                and str(tr.get("action", "")).upper() == side
                and str(tr.get("symbol", "")).upper() == sym
                and abs(float(tr.get("shares") or 0.0) - sh) < 1e-4
                and abs(float(tr.get("price") or 0.0) - px) < 1e-4
            ):
                tr["note_hash"] = nhash
                tr["source"] = parsed.get("broker", "Contract Note")
                tr["contract_note"] = parsed["contract_note"]
                break
        self.save()
        parsed["imported"] = True
        parsed["message"] = (
            f"Imported {parsed.get('broker', 'Note')}: {side} {sh:g} {sym} @ "
            f"{format_money(px, parsed.get('currency', 'USD'), 4)} ({dt}, Charges {format_money(parsed['total_charges'], parsed.get('currency', 'USD'), 2)})"
        )
        return parsed

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
        fee_pct: float | str,
        provider: str | None = None,
        trading_goal: str = "hybrid",
    ) -> dict[str, Any]:
        p_entry = self.get_price_entry(sym)
        current_price = self.get_price(sym)
        if current_price is None:
            current_price = avg_cost
        cost = shares * avg_cost
        value = shares * current_price
        pnl = value - cost
        pnl_pct = (pnl / cost * 100.0) if cost > 0 else 0.0

        is_stat, eff_fee_pct = resolve_fee_mode(fee_pct, cur_code)
        f = max(0.0, eff_fee_pct) / 100.0
        if is_stat:
            buy_c = calculate_trade_charges(cur_code, "BUY", shares, avg_cost)
            sell_c = calculate_trade_charges(cur_code, "SELL", shares, current_price)
            net_cost = float(buy_c["net_settlement"])
            net_val = float(sell_c["net_settlement"])
            buy_rate = (buy_c["total_charges"] / buy_c["gross"]) if buy_c["gross"] > 0 else f
            sell_rate = (sell_c["total_charges"] / sell_c["gross"]) if sell_c["gross"] > 0 else f
            breakeven = (avg_cost * (1.0 + buy_rate) / max(0.5, 1.0 - sell_rate))
        else:
            net_cost = cost * (1.0 + f)
            net_val = value * (1.0 - f)
            breakeven = (avg_cost * (1.0 + f) / (1.0 - f)) if f < 0.5 else avg_cost
        net_pnl = net_val - net_cost
        net_pnl_pct = (net_pnl / net_cost * 100.0) if net_cost > 0 else 0.0

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
        lim = compute_smart_limit(
            current_price,
            p_entry.get("best_bid"),
            p_entry.get("best_ask"),
            p_entry.get("bid_volume"),
            p_entry.get("ask_volume"),
            "BUY",
        )

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
            "spread_pct": lim["spread_pct"],
            "wide_spread": lim["wide_spread"],
            "liquidity_score": lim["liquidity_score"],
            "optimal_limit": lim["optimal_limit"],
            "company_name": p_entry.get("company_name"),
            "history": [h.get("close", h.get("price")) for h in hist if ("close" in h or "price" in h)],
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
            "strategy_tag": self.get_strategy_tag(sym, trading_goal)[0],
            "strategy_pinned": self.get_strategy_tag(sym, trading_goal)[1],
        }
        if provider:
            item["provider"] = provider
        return item

    def portfolio_summary(
        self,
        vfex_fee_pct: float | str = 0.0,
        zse_fee_pct: float | str = 0.0,
        trading_goal: str = "hybrid",
    ) -> dict[str, Any]:
        vfex_stat, vfex_eff = resolve_fee_mode(vfex_fee_pct, "USD")
        _, zse_eff = resolve_fee_mode(zse_fee_pct, "ZWG")
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
                trading_goal=trading_goal,
            )
            items.append(item)

        wallet_cash_usd = 0.0
        wallet_cash_zwg = 0.0
        manual_by_sym = {item["symbol"]: item for item in items}
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
                # Avoid double-counting when the same position is already tracked in Manual FIFO ledger
                manual_match = manual_by_sym.get(sym)
                if manual_match is not None and abs(float(manual_match.get("shares") or 0.0) - shares) <= 1e-4:
                    manual_match["synced_source"] = tag
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
                    trading_goal=trading_goal,
                ))

        for item in items:
            c = float(item["shares"]) * float(item["avg_cost"])
            v = float(item["value"])
            if item["currency"] == "ZWG":
                zwg_cost += c
                zwg_value += v
            else:
                total_cost += c
                total_value += v
                if vfex_stat:
                    net_total_cost += float(calculate_trade_charges("USD", "BUY", float(item["shares"]), float(item["avg_cost"]))["net_settlement"])
                    net_total_value += float(calculate_trade_charges("USD", "SELL", float(item["shares"]), float(item["price"]))["net_settlement"])
                else:
                    f = max(0.0, vfex_eff) / 100.0
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
        f_usd = max(0.0, vfex_eff) / 100.0
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

        core_val = round(sum(float(i["value"]) for i in items if i["currency"] == "USD" and i.get("strategy_tag") == "core"), 2)
        swing_val = round(sum(float(i["value"]) for i in items if i["currency"] == "USD" and i.get("strategy_tag") == "swing"), 2)
        core_cnt = sum(1 for i in items if i.get("strategy_tag") == "core")
        swing_cnt = sum(1 for i in items if i.get("strategy_tag") == "swing")

        return {
            "items": items,
            "core_value": core_val,
            "swing_value": swing_val,
            "core_count": core_cnt,
            "swing_count": swing_cnt,
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

    @staticmethod
    def _max_affordable_shares(currency: str, price: float, cash_avail: float) -> tuple[int, float]:
        """Return (max_whole_shares, net_settlement_cost) strictly <= cash_avail after statutory buy fees."""
        if price <= 0 or cash_avail <= 0:
            return 0, 0.0
        one_net = float(calculate_trade_charges(currency, "BUY", 1.0, price)["net_settlement"])
        if one_net <= 0 or one_net > cash_avail + 1e-9:
            return 0, round(one_net, 2)
        hi = max(1, int(cash_avail // price) + 1)
        lo = 1
        best_q, best_cost = 1, one_net
        while lo <= hi:
            mid = (lo + hi) // 2
            c = float(calculate_trade_charges(currency, "BUY", float(mid), price)["net_settlement"])
            if c <= cash_avail + 1e-9:
                best_q, best_cost = mid, c
                lo = mid + 1
            else:
                hi = mid - 1
        return best_q, round(best_cost, 2)

    def idle_cash_deployment(
        self,
        include_zse: bool = True,
        news_items: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """Recommend fee-aware whole-share buys across unused USD & ZWG portal cash balances."""
        synced = self.state.get("synced_accounts", {})
        accounts_out: list[dict[str, Any]] = []
        tot_dep_usd = 0.0
        tot_dep_zwg = 0.0

        for prov in ("vfex_direct", "ctrade", "zse_direct"):
            adata = synced.get(prov) or {}
            status = self._provider_status(prov)
            c_usd = float(adata.get("cash_usd") or 0.0)
            c_zwg = float(adata.get("cash_zwg") or 0.0)
            h_usd = float(adata.get("held_usd") or 0.0)
            h_zwg = float(adata.get("held_zwg") or 0.0)
            dep_usd = round(max(0.0, c_usd - h_usd), 2)
            dep_zwg = round(max(0.0, c_zwg - h_zwg), 2)
            if status.get("connected") or dep_usd > 0 or dep_zwg > 0:
                accounts_out.append({
                    "provider": prov,
                    "title": PORTAL_LABELS.get(prov, prov),
                    "connected": bool(status.get("connected")),
                    "cash_usd": round(c_usd, 2),
                    "cash_zwg": round(c_zwg, 2),
                    "held_usd": round(h_usd, 2),
                    "held_zwg": round(h_zwg, 2),
                    "deployable_usd": dep_usd,
                    "deployable_zwg": dep_zwg,
                })
            tot_dep_usd += dep_usd
            tot_dep_zwg += dep_zwg

        tot_dep_usd = round(tot_dep_usd, 2)
        tot_dep_zwg = round(tot_dep_zwg, 2)

        sig_map = {
            s["symbol"]: s
            for s in self.trade_signals(
                include_zse=include_zse,
                tracked_only=False,
                news_items=news_items,
            )
        }
        # Enrich with Mahoraga + Grokking probability estimates
        agent = self.get_paper_agent_state()
        brain = self._ensure_agent_brain(agent)
        cand_rows = self._agent_score_candidates(
            agent,
            self.state.get("prices", {}),
            self.state.get("history", {}),
            self._news_by_symbol(news_items or []),
            datetime.now(timezone.utc).date().isoformat(),
            tracked_only=False,
            record_shadows=False,
        )
        cand_map = {c["symbol"]: c for c in cand_rows}

        def _picks_for_currency(cur_code: str, budget: float) -> tuple[list[dict[str, Any]], float | None, list[dict[str, Any]], float]:
            ranked: list[dict[str, Any]] = []
            cheapest_gap: float | None = None
            for sym, entry in sorted(self.state.get("prices", {}).items()):
                px_last = float(entry.get("price") or 0.0)
                if px_last <= 0:
                    continue
                if infer_currency(sym, entry) != cur_code:
                    continue
                sig = sig_map.get(sym) or {}
                act = str(sig.get("action") or "HOLD").upper()
                if act == "SELL":
                    continue
                exec_px = float(entry.get("best_ask") or 0.0) or px_last
                qty, net_cost = self._max_affordable_shares(cur_code, exec_px, budget)
                sig_score = int(sig.get("score") or 0)
                cinfo = cand_map.get(sym) or {}
                win_prob = float(cinfo.get("win_prob_pct") or 50.0)
                if qty <= 0:
                    if budget > 0:
                        one_c = net_cost or float(calculate_trade_charges(cur_code, "BUY", 1.0, exec_px)["net_settlement"])
                        gap = round(max(0.01, one_c - budget), 2)
                        if cheapest_gap is None or gap < cheapest_gap:
                            cheapest_gap = gap
                    continue
                conv_rank = (2 if act == "BUY" else 1 if sig_score >= 25 else 0, sig_score, win_prob, -exec_px)
                ranked.append({
                    "symbol": sym,
                    "currency": cur_code,
                    "action": act if act == "BUY" else "WATCH",
                    "score": sig_score,
                    "win_prob_pct": round(win_prob, 1),
                    "exec_price": round(exec_px, 4),
                    "max_shares": qty,
                    "net_cost": net_cost,
                    "leftover": round(max(0.0, budget - net_cost), 2),
                    "reasons": list(sig.get("reasons") or [entry.get("company_name") or "Lowest liquid ask"])[:2],
                    "_rank": conv_rank,
                })
            ranked.sort(key=lambda r: r["_rank"], reverse=True)
            top_picks = [{k: v for k, v in r.items() if k != "_rank"} for r in ranked[:5]]

            # Greedy diversified basket across top picks that fits strictly within remaining budget
            rem = budget
            basket: list[dict[str, Any]] = []
            for r in top_picks:
                if len(basket) >= 3 or rem <= 0:
                    break
                slice_cap = rem if len(basket) == 2 or rem < float(calculate_trade_charges(cur_code, "BUY", 1.0, r["exec_price"])["net_settlement"]) * 2 else round(rem * 0.55, 2)
                bq, bcost = self._max_affordable_shares(cur_code, r["exec_price"], slice_cap)
                if bq <= 0:
                    bq, bcost = self._max_affordable_shares(cur_code, r["exec_price"], rem)
                if bq > 0 and bcost <= rem + 1e-9:
                    rem = round(max(0.0, rem - bcost), 2)
                    basket.append({
                        "symbol": r["symbol"],
                        "currency": cur_code,
                        "shares": bq,
                        "exec_price": r["exec_price"],
                        "net_cost": bcost,
                        "score": r["score"],
                        "win_prob_pct": r["win_prob_pct"],
                    })
            return top_picks, cheapest_gap, basket, round(rem, 2)

        usd_picks, usd_gap, usd_basket, usd_rem = _picks_for_currency("USD", tot_dep_usd)
        zwg_picks, zwg_gap, zwg_basket, zwg_rem = _picks_for_currency("ZWG", tot_dep_zwg) if include_zse else ([], None, [], tot_dep_zwg)

        return {
            "accounts": accounts_out,
            "total_deployable_usd": tot_dep_usd,
            "total_deployable_zwg": tot_dep_zwg,
            "usd_picks": usd_picks,
            "zwg_picks": zwg_picks,
            "usd_basket": usd_basket,
            "zwg_basket": zwg_basket,
            "usd_leftover": usd_rem,
            "zwg_leftover": zwg_rem,
            "usd_gap_for_one": usd_gap,
            "zwg_gap_for_one": zwg_gap,
            "grok_active": bool((brain.get("grok") or {}).get("enabled")),
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

    def get_tracked_symbols(self) -> set[str]:
        """Return union of watchlist, owned holdings (manual & synced), targets, alerts, and stops."""
        tracked: set[str] = {str(s).upper() for s in self.state.get("watchlist", []) if s}
        tracked.update(str(s).upper() for s in self.state.get("portfolio", {}).keys())
        tracked.update(str(s).upper() for s in self.state.get("targets", {}).keys())
        tracked.update(str(s).upper() for s in self.state.get("trailing_stops", {}).keys())
        for a in self.state.get("alerts", []):
            if a.get("symbol"):
                tracked.add(str(a["symbol"]).upper())
        for acct in self.state.get("synced_accounts", {}).values():
            if isinstance(acct, dict):
                for h in acct.get("holdings", []):
                    if float(h.get("shares") or 0.0) > 0 and h.get("symbol"):
                        tracked.add(str(h["symbol"]).upper())
        return tracked

    def buy_recommendations(self, discount_pct: float = 5.0, tracked_only: bool = True) -> list[dict[str, Any]]:
        """Return symbols trading >= discount_pct below 30-day average or below a target alert."""
        recs: list[dict[str, Any]] = []
        history_map = self.state.get("history", {})
        tracked = self.get_tracked_symbols() if tracked_only else None
        below_targets = {
            a["symbol"]: float(a["target"])
            for a in self.state.get("alerts", [])
            if a.get("direction") == "below"
        }
        for sym, entry in sorted(self.state.get("prices", {}).items()):
            if tracked is not None and sym not in tracked:
                continue
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

    def get_cached_news(self, max_items: int = 35) -> list[dict[str, Any]]:
        """Return cached VFEX/ZSE news catalysts within NEWS_MAX_AGE_DAYS, annotated with tracked status."""
        cache = self.state.get("news_cache", {})
        raw_items = cache.get("items", []) if isinstance(cache, dict) else []
        tracked_syms = self.get_tracked_symbols()
        now = datetime.now(timezone.utc)
        out: list[dict[str, Any]] = []
        for item in raw_items[:max_items]:
            if not isinstance(item, dict):
                continue
            syms = [str(s).upper() for s in item.get("symbols", [])]
            dt = _parse_news_timestamp(item.get("published_at") or item.get("date"))
            title_dt = _extract_title_news_date(str(item.get("title") or ""))
            if title_dt is not None and (dt is None or title_dt < dt):
                dt = title_dt
            age_days, age_label = _format_age_label(dt, now=now)
            if dt is not None and age_days > NEWS_MAX_AGE_DAYS:
                continue
            out.append({
                **item,
                "symbols": syms,
                "tracked": any(s in tracked_syms for s in syms),
                "age_days": age_days,
                "age_label": age_label or item.get("age_label", "Recent"),
            })
        return out

    def notify_news_catalysts(self, news_items: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
        """Send one desktop notification per fresh material headline on Tracked counters."""
        items = news_items if news_items is not None else self.get_cached_news()
        seen_ids = [str(x) for x in self.state.get("notified_news", [])][-120:]
        seen_set = set(seen_ids)
        sent: list[dict[str, Any]] = []
        for item in items:
            if not item.get("tracked"):
                continue
            if int(item.get("age_days", 99)) > 7:
                continue
            sent_lbl = str(item.get("sentiment") or "Neutral")
            if sent_lbl == "Neutral" and int(item.get("impact_score") or 0) == 0:
                continue
            if sent_lbl not in ("Bullish", "Caution"):
                continue
            nid = str(item.get("id") or hashlib.sha1(str(item.get("title", "")).encode("utf-8")).hexdigest()[:12])
            if nid in seen_set:
                continue
            seen_set.add(nid)
            seen_ids.append(nid)
            syms_txt = ", ".join(item.get("symbols", [])[:2]) or "VFEX"
            icon = "⚠" if sent_lbl == "Caution" else "📰"
            send_notification(
                f"{icon} VFEX News [{sent_lbl}] • {syms_txt}",
                f"[{item.get('category', 'Market')}] {item.get('title', '')} ({item.get('source', '')})",
            )
            sent.append(item)
        if sent:
            self.state["notified_news"] = seen_ids[-120:]
            self.save()
        return sent

    def _news_by_symbol(self, news_items: list[dict[str, Any]] | None = None, max_age_days: int = NEWS_MAX_AGE_DAYS) -> dict[str, dict[str, Any]]:
        """Select strongest recency-weighted news catalyst per symbol."""
        items = news_items if news_items is not None else self.get_cached_news()
        best: dict[str, dict[str, Any]] = {}
        for item in items:
            age_days = max(0, int(item.get("age_days") or 0))
            if age_days > max_age_days:
                continue
            raw_imp = int(item.get("impact_score") or 0)
            weight = _news_age_weight(age_days)
            if weight <= 0.0:
                continue
            weighted_imp = int(round(raw_imp * weight))
            if raw_imp != 0 and weighted_imp == 0:
                weighted_imp = 1 if raw_imp > 0 else -1
            for sym in item.get("symbols", []):
                prev = best.get(sym)
                cand_rank = (abs(weighted_imp), -age_days)
                prev_rank = (abs(int(prev.get("impact_score") or 0)), -int(prev.get("age_days", 99))) if prev else (-1, -999)
                if prev is None or cand_rank > prev_rank:
                    best[sym] = {
                        "id": item.get("id", ""),
                        "title": item.get("title", ""),
                        "category": item.get("category", "Market"),
                        "sentiment": item.get("sentiment", "Neutral"),
                        "impact_score": weighted_imp,
                        "raw_impact_score": raw_imp,
                        "age_weight": weight,
                        "age_days": age_days,
                        "date": item.get("date", ""),
                        "age_label": item.get("age_label", ""),
                        "source": item.get("source", ""),
                        "url": item.get("url", ""),
                        "official": bool(item.get("official")),
                    }
        return best

    def get_cached_intel(self) -> dict[str, Any]:
        """Return cached exchange intelligence (VFEX/ZSE DTR turnover, foreign flow, index, market cap)."""
        raw = self.state.get("market_intel")
        if isinstance(raw, dict):
            return raw
        return {"vfex": {}, "zse": {}, "counters": {}, "blue_chips": {}}

    @staticmethod
    def _band_position_pct(cur: float, entry: dict[str, Any]) -> float | None:
        """Compute current price position inside daily circuit-breaker band (0=lower bound, 100=upper)."""
        lo = _safe_float(entry.get("lower_limit"))
        hi = _safe_float(entry.get("upper_limit"))
        if lo is None or hi is None or hi <= lo or cur <= 0:
            return None
        return round(max(0.0, min(100.0, ((cur - lo) / (hi - lo)) * 100.0)), 1)

    def trade_signals(
        self,
        discount_pct: float = 3.0,
        include_zse: bool = True,
        profit_take_pct: float = 15.0,
        max_stock_pct: float = 25.0,
        limit: int = 8,
        trading_goal: str = "hybrid",
        tracked_only: bool = True,
        news_items: list[dict[str, Any]] | None = None,
    ) -> list[dict[str, Any]]:
        """Score live VFEX/ZSE counters adaptively for Long-Term Compounder, Short-Term Swing, or Hybrid goals."""
        goal = normalize_goal(trading_goal)
        summary = self.portfolio_summary(trading_goal=goal)
        holdings = {item["symbol"]: item for item in summary["items"]}
        targets = self.get_targets()
        tracked_syms = self.get_tracked_symbols() if tracked_only else None
        history_map = self.state.get("history", {})
        div_syms = {str(d.get("symbol", "")).upper() for d in self.state.get("dividends", [])}
        news_map = self._news_by_symbol(news_items)
        intel = self.get_cached_intel()
        dtr_counters = intel.get("counters", {}) if isinstance(intel, dict) else {}
        blue_chips = intel.get("blue_chips", {}) if isinstance(intel, dict) else {}
        foreign_counters = intel.get("foreign_counters", {}) if isinstance(intel, dict) else {}
        below_targets = {
            a["symbol"]: float(a["target"])
            for a in self.state.get("alerts", [])
            if a.get("direction") == "below"
        }
        watchlist_set = set(self.state.get("watchlist", []))
        usd_equity = float(summary["total_value"]) + float(summary.get("wallet_cash_usd") or 0.0)
        zwg_equity = float(summary["zwg_value"]) + float(summary.get("wallet_cash_zwg") or 0.0)
        signals: list[dict[str, Any]] = []

        for sym, entry in sorted(self.state.get("prices", {}).items()):
            if tracked_syms is not None and sym not in tracked_syms:
                continue
            cur = float(entry.get("price") or 0.0)
            if cur <= 0:
                continue
            cur_code = infer_currency(sym, entry)
            if not include_zse and cur_code != "USD":
                continue

            hist = history_map.get(sym, [])
            tech = compute_symbol_technicals(hist, cur)
            drop30 = tech["drop30"]
            chg_pct = entry.get("change_pct")
            bid = float(entry.get("best_bid") or 0.0)
            ask = float(entry.get("best_ask") or 0.0)
            bid_vol = int(entry.get("bid_volume") or 0)
            ask_vol = int(entry.get("ask_volume") or 0)
            lim = compute_smart_limit(cur, bid, ask, bid_vol, ask_vol, "BUY")
            pinned_tag, is_pinned = self.get_strategy_tag(sym, goal)
            dtr_info = dtr_counters.get(sym)
            bc_info = blue_chips.get(sym)
            fc_info = foreign_counters.get(sym)
            band_pos = self._band_position_pct(cur, entry)
            sched = ZSE_FEE_SCHEDULE if cur_code == "ZWG" else VFEX_FEE_SCHEDULE

            # Separate Core (long-term value/DCA) vs Swing (momentum/RSI/book) components
            core_score = 0
            core_reasons: list[str] = []
            core_disc = max(discount_pct, 4.0) if goal == "long" else discount_pct
            if len(hist) >= 2 and drop30 >= core_disc:
                core_score += min(40, int(round(drop30 * 3.0)))
                core_reasons.append(f"-{drop30:.1f}% vs 30d avg")
            if sym in below_targets and cur <= below_targets[sym]:
                core_score += 35
                core_reasons.append(f"<= target {format_money(below_targets[sym], cur_code, 4)}")
            if cur_code == "USD" and sym in targets:
                cur_alloc = float(holdings[sym]["alloc_pct"]) if sym in holdings else 0.0
                if cur_alloc < float(targets[sym]) - 5.0:
                    core_score += 25
                    core_reasons.append(f"Alloc {cur_alloc:.0f}% < {float(targets[sym]):.0f}%")
            if sym in div_syms and (drop30 >= 2.0 or sym in targets):
                core_score += 10
                core_reasons.append("Dividend payer")
            if bc_info and (drop30 >= 2.0 or sym in below_targets or (chg_pct is not None and float(chg_pct) <= -1.5)):
                core_score += 10
                core_reasons.append(f"Top{bc_info['rank']} Cap ({bc_info['pct']:.0f}%)")
            if tech["ma20"] and cur < float(tech["ma20"]) * 0.97 and core_score == 0 and len(hist) >= 5:
                core_score += 15
                core_reasons.append("Below MA20 value")

            swing_score = 0
            swing_reasons: list[str] = []
            dip_floor = max(1.5, discount_pct * 0.67)
            if chg_pct is not None and float(chg_pct) <= -dip_floor:
                swing_score += min(35, int(round(abs(float(chg_pct)) * 4.0)))
                swing_reasons.append(f"{float(chg_pct):.1f}% today")
            if tech["rsi14"] is not None and tech["rsi14"] <= 35.0:
                swing_score += 20
                swing_reasons.append(f"RSI {tech['rsi14']:.0f}")
            if tech["z_score"] is not None and tech["z_score"] <= -1.5:
                swing_score += 20
                swing_reasons.append(f"Z {tech['z_score']:.1f}")
            if bid > 0 and bid_vol >= 50 and (ask_vol == 0 or bid_vol >= 2 * ask_vol):
                swing_score += 25
                if lim["spread_pct"] is not None and lim["spread_pct"] <= 5.0:
                    swing_score += 12
                swing_reasons.append(f"Bid {bid_vol} > Ask {ask_vol}")
            if dtr_info and float(dtr_info.get("value_traded") or 0.0) > 0 and (core_score > 0 or swing_score > 0):
                swing_score += 14
                vt = float(dtr_info["value_traded"])
                v_lbl = f"${vt / 1000.0:.1f}k" if cur_code == "USD" and vt >= 1000 else (f"ZiG {vt / 1000.0:.1f}k" if vt >= 1000 else f"{vt:.0f}")
                swing_reasons.append(f"DTR {v_lbl}")
            if band_pos is not None and band_pos <= 20.0 and (swing_score > 0 or core_score > 0):
                swing_score += 8
                swing_reasons.append(f"Near floor {band_pos:.0f}%")
            if fc_info:
                f_net = float(fc_info.get("net_val") or 0.0)
                f_thr = 50000.0 if cur_code == "ZWG" else 1000.0
                if f_net >= f_thr and (swing_score > 0 or core_score > 0):
                    swing_score += 10
                    swing_reasons.append(f"Foreign inflow {format_money(f_net, cur_code, 0)}")
                elif f_net <= -f_thr and swing_score > 0:
                    swing_score = max(0, swing_score - 6)
                    swing_reasons.append(f"Foreign outflow {format_money(abs(f_net), cur_code, 0)}")

            # Resolve horizon & score per Trading Goal
            buy_score = 0
            buy_reasons: list[str] = []
            horizon = "CORE"
            if goal == "long":
                buy_score = core_score + (10 if (tech["rsi14"] is not None and tech["rsi14"] <= 35.0 and core_score > 0) else 0)
                if buy_score == 0 and chg_pct is not None and float(chg_pct) <= -max(3.0, discount_pct) and (sym in watchlist_set or sym in holdings or sym in targets):
                    buy_score = 20
                    core_reasons.append(f"{float(chg_pct):.1f}% dip")
                buy_reasons = list(core_reasons)
                horizon = "CORE"
                if lim["wide_spread"] and (lim["spread_pct"] or 0.0) > 10.0 and buy_score > 0:
                    buy_score = max(1, buy_score - 5)
                    buy_reasons.append(f"Wide spread {lim['spread_pct']:.1f}%")
            elif goal == "short":
                buy_score = swing_score + (15 if (len(hist) >= 2 and drop30 >= discount_pct and swing_score > 0) else 0)
                buy_reasons = list(swing_reasons)
                if len(hist) >= 2 and drop30 >= discount_pct and swing_score > 0 and f"-{drop30:.1f}% vs 30d avg" not in buy_reasons:
                    buy_reasons.append(f"-{drop30:.1f}% vs 30d avg")
                horizon = "SWING"
                if lim["wide_spread"] or lim["liquidity_score"] < 40:
                    buy_score = max(0, buy_score - 20)
                    if buy_score > 0 and lim["wide_spread"]:
                        buy_reasons.append(f"Wide spread {lim['spread_pct']:.1f}%")
            else:
                # Hybrid: classify as CORE or SWING cleanly and score both
                if is_pinned:
                    horizon = pinned_tag.upper()
                elif core_score >= swing_score and core_score > 0:
                    horizon = "CORE"
                else:
                    horizon = "SWING"
                buy_score = core_score + swing_score
                buy_reasons = list(dict.fromkeys(core_reasons + swing_reasons))
                if lim["wide_spread"] and buy_score > 0:
                    buy_score = max(1, buy_score - 10)
                    buy_reasons.append(f"Wide spread {lim['spread_pct']:.1f}%")

            news_cat = news_map.get(sym)
            if news_cat:
                imp = int(news_cat.get("impact_score") or 0)
                n_cat = str(news_cat.get("category") or "Market")
                if imp >= 12:
                    if goal == "long":
                        boost = min(20, imp) if n_cat in ("Dividend", "Expansion", "Listing", "Earnings") else 10
                    elif goal == "short":
                        boost = min(20, imp) if n_cat in ("Earnings", "Expansion") else 12
                    else:
                        boost = min(20, imp)
                    if buy_score > 0 or (sym in watchlist_set or sym in holdings or sym in targets):
                        buy_score += boost
                        buy_reasons.insert(0, f"News+{boost}: {n_cat}")
                elif imp <= -12 and buy_score > 0:
                    pen = min(25, abs(imp))
                    buy_score = max(0, buy_score - pen)
                    if buy_score > 0:
                        buy_reasons.append(f"⚠ Caution news (-{pen})")

            if buy_score > 0 and buy_reasons:
                if sym in watchlist_set or sym in holdings:
                    buy_score += 5

            if buy_score >= 25 and buy_reasons:
                if band_pos is not None and band_pos >= 90.0:
                    buy_score = max(1, buy_score - 12)
                    buy_reasons.append(f"Near ceiling {band_pos:.0f}%")
                pool_eq = zwg_equity if cur_code == "ZWG" else usd_equity
                eff_cap_pct = min(max_stock_pct, 15.0) if horizon == "SWING" else max_stock_pct
                cap_budget = pool_eq * (eff_cap_pct / 100.0)
                rec_sh = int(cap_budget // lim["optimal_limit"]) if (cap_budget > 0 and lim["optimal_limit"] > 0) else 0
                signals.append({
                    "symbol": sym,
                    "action": "BUY",
                    "horizon": horizon,
                    "score": min(100, buy_score),
                    "currency": cur_code,
                    "price": cur,
                    "limit_price": lim["optimal_limit"],
                    "spread_pct": lim["spread_pct"],
                    "wide_spread": lim["wide_spread"],
                    "liquidity_score": lim["liquidity_score"],
                    "recommended_shares": rec_sh,
                    "rsi14": tech["rsi14"],
                    "z_score": tech["z_score"],
                    "best_bid": entry.get("best_bid"),
                    "best_ask": entry.get("best_ask"),
                    "bid_volume": entry.get("bid_volume"),
                    "ask_volume": entry.get("ask_volume"),
                    "change_pct": chg_pct,
                    "dtr_turnover": float(dtr_info["value_traded"]) if dtr_info else None,
                    "dtr_volume": float(dtr_info["volumes"]) if dtr_info else None,
                    "blue_chip_rank": int(bc_info["rank"]) if bc_info else None,
                    "foreign_net": float(fc_info["net_val"]) if fc_info else None,
                    "band_pos_pct": band_pos,
                    "est_round_trip_fee_pct": sched["round_trip_pct"],
                    "reasons": buy_reasons,
                    "news_catalyst": news_cat,
                    "headline": f"BUY [{horizon}] {sym} ({buy_reasons[0]})",
                })

            if sym in holdings:
                held = holdings[sym]
                held_horizon = "CORE" if held.get("strategy_tag") == "core" else "SWING"
                is_core_protected = (goal == "long" and not (is_pinned and pinned_tag == "swing")) or (goal == "hybrid" and held_horizon == "CORE")
                sell_score = 0
                sell_reasons: list[str] = []
                pnl_pct = float(held.get("pnl_pct") or 0.0)
                if is_core_protected:
                    # Core long-term holds suppress small profit-takes; only flag extreme valuation or major overweight trim
                    extreme_take = max(50.0, profit_take_pct * 3.0)
                    if pnl_pct >= extreme_take:
                        sell_score += 35
                        sell_reasons.append(f"+{pnl_pct:.1f}% extreme gain")
                    if held.get("target_pct") is not None and float(held.get("alloc_pct") or 0.0) > float(held["target_pct"]) + 15.0:
                        sell_score += 25
                        sell_reasons.append(f"Trim {float(held['alloc_pct']):.0f}% > {float(held['target_pct']):.0f}%")
                else:
                    eff_profit_take = min(profit_take_pct, 12.0) if goal == "short" else profit_take_pct
                    if pnl_pct >= eff_profit_take:
                        sell_score += 35
                        sell_reasons.append(f"+{pnl_pct:.1f}% swing target")
                    if tech["rsi14"] is not None and tech["rsi14"] >= 70.0:
                        sell_score += 25
                        sell_reasons.append(f"Overbought RSI {tech['rsi14']:.0f}")
                    if held.get("target_pct") is not None and float(held.get("alloc_pct") or 0.0) > float(held["target_pct"]) + 10.0:
                        sell_score += 20
                        sell_reasons.append(f"Alloc {float(held['alloc_pct']):.0f}% > {float(held['target_pct']):.0f}%")
                    if chg_pct is not None and float(chg_pct) >= 6.0 and ask > 0 and ask_vol >= 2 * max(1, bid_vol):
                        sell_score += 25
                        sell_reasons.append(f"+{float(chg_pct):.1f}% spike / heavy ask")
                    if band_pos is not None and band_pos >= 90.0 and sell_score > 0:
                        sell_score += 12
                        sell_reasons.append(f"Near upper limit {band_pos:.0f}%")

                if news_cat and int(news_cat.get("impact_score") or 0) <= -12:
                    sell_score += abs(int(news_cat.get("impact_score") or 0))
                    if sell_score < 35:
                        sell_score = 35
                    sell_reasons.insert(0, f"⚠ News {news_cat.get('category', 'Caution')}")

                if sell_score >= 25:
                    slim = compute_smart_limit(cur, bid, ask, bid_vol, ask_vol, "SELL")
                    sell_h = "CORE" if is_core_protected else "SWING"
                    signals.append({
                        "symbol": sym,
                        "action": "SELL",
                        "horizon": sell_h,
                        "score": min(100, sell_score),
                        "currency": cur_code,
                        "price": cur,
                        "limit_price": slim["optimal_limit"],
                        "spread_pct": slim["spread_pct"],
                        "wide_spread": slim["wide_spread"],
                        "liquidity_score": slim["liquidity_score"],
                        "recommended_shares": int(float(held.get("shares") or 0)) if (goal == "short" and not is_core_protected) else (int(float(held.get("shares") or 0) // 2) or int(float(held.get("shares") or 0))),
                        "rsi14": tech["rsi14"],
                        "z_score": tech["z_score"],
                        "best_bid": entry.get("best_bid"),
                        "best_ask": entry.get("best_ask"),
                        "bid_volume": entry.get("bid_volume"),
                        "ask_volume": entry.get("ask_volume"),
                        "change_pct": chg_pct,
                        "reasons": sell_reasons,
                        "news_catalyst": news_cat,
                        "headline": f"SELL [{sell_h}] {sym} ({sell_reasons[0]})",
                    })

        signals.sort(key=lambda s: (-int(s["score"]), s["symbol"]))
        return signals[:limit]

    def record_signal_history(self, signals: list[dict[str, Any]], min_score: int = 35) -> int:
        """Auto-log high-conviction signals once per day into rolling 90-day backtest track record."""
        today_dt = datetime.now(timezone.utc).date()
        today = today_dt.isoformat()
        cutoff = (today_dt - timedelta(days=90)).isoformat()
        hist = [h for h in self.state.get("signal_history", []) if str(h.get("date", "")) >= cutoff]
        existing = {(h.get("date"), h.get("action"), h.get("symbol")) for h in hist}
        added = 0
        for sig in signals:
            if int(sig.get("score", 0)) < min_score:
                continue
            key = (today, sig["action"], sig["symbol"])
            if key in existing:
                continue
            existing.add(key)
            hist.append({
                "date": today,
                "symbol": sig["symbol"],
                "action": sig["action"],
                "horizon": sig.get("horizon", "SWING"),
                "currency": sig.get("currency", "USD"),
                "entry_price": round(float(sig["price"]), 4),
                "score": int(sig["score"]),
                "headline": sig.get("headline", ""),
            })
            added += 1
        if added or len(hist) != len(self.state.get("signal_history", [])):
            self.state["signal_history"] = hist[-250:]
            self.save()
        return added

    def signal_backtest_summary(self) -> dict[str, Any]:
        """Evaluate forward win-rate and average return across recorded signals (overall + Core vs Swing)."""
        entries = self.state.get("signal_history", [])
        evaluated: list[dict[str, Any]] = []
        wins = 0
        returns: list[float] = []
        core_wins = core_tot = swing_wins = swing_tot = 0
        for row in entries:
            sym = str(row.get("symbol", "")).upper()
            ep = float(row.get("entry_price") or 0.0)
            if ep <= 0:
                continue
            cur = self.get_price(sym) or ep
            raw_ret = ((cur - ep) / ep) * 100.0
            adj_ret = -raw_ret if row.get("action") == "SELL" else raw_ret
            returns.append(adj_ret)
            is_win = adj_ret > 0
            if is_win:
                wins += 1
            hz = str(row.get("horizon") or "SWING").upper()
            if hz == "CORE":
                core_tot += 1
                if is_win:
                    core_wins += 1
            else:
                swing_tot += 1
                if is_win:
                    swing_wins += 1
            evaluated.append({
                **row,
                "horizon": hz,
                "current_price": round(cur, 4),
                "return_pct": round(adj_ret, 2),
            })
        evaluated.sort(key=lambda r: (r["date"], r["score"]), reverse=True)
        total = len(evaluated)
        best = max(evaluated, key=lambda r: r["return_pct"], default=None)
        worst = min(evaluated, key=lambda r: r["return_pct"], default=None)
        return {
            "total_logged": total,
            "wins": wins,
            "win_rate_pct": round((wins / total) * 100.0, 1) if total > 0 else 0.0,
            "core_count": core_tot,
            "core_win_rate_pct": round((core_wins / core_tot) * 100.0, 1) if core_tot > 0 else 0.0,
            "swing_count": swing_tot,
            "swing_win_rate_pct": round((swing_wins / swing_tot) * 100.0, 1) if swing_tot > 0 else 0.0,
            "avg_return_pct": round(sum(returns) / total, 2) if total > 0 else 0.0,
            "best": best,
            "worst": worst,
            "entries": evaluated[:15],
        }

    def market_screener(
        self,
        discount_pct: float = 3.0,
        profit_take_pct: float = 15.0,
        max_stock_pct: float = 25.0,
        trading_goal: str = "hybrid",
        news_items: list[dict[str, Any]] | None = None,
    ) -> list[dict[str, Any]]:
        """Build full screener table across all fetched VFEX & ZSE counters with depth, technicals, & signals."""
        news_map = self._news_by_symbol(news_items)
        sig_by_sym: dict[str, dict[str, Any]] = {}
        for s in self.trade_signals(
            discount_pct=discount_pct,
            include_zse=True,
            profit_take_pct=profit_take_pct,
            max_stock_pct=max_stock_pct,
            limit=60,
            trading_goal=trading_goal,
            tracked_only=False,
            news_items=news_items,
        ):
            if s["symbol"] not in sig_by_sym:
                sig_by_sym[s["symbol"]] = s

        rows: list[dict[str, Any]] = []
        history_map = self.state.get("history", {})
        intel = self.get_cached_intel()
        foreign_counters = intel.get("foreign_counters", {}) if isinstance(intel, dict) else {}
        for sym, entry in sorted(self.state.get("prices", {}).items()):
            cur = float(entry.get("price") or 0.0)
            if cur <= 0:
                continue
            cur_code = infer_currency(sym, entry)
            hist = history_map.get(sym, [])
            tech = compute_symbol_technicals(hist, cur)
            lim = compute_smart_limit(
                cur,
                entry.get("best_bid"),
                entry.get("best_ask"),
                entry.get("bid_volume"),
                entry.get("ask_volume"),
                "BUY",
            )
            sig = sig_by_sym.get(sym)
            fc_info = foreign_counters.get(sym)
            rows.append({
                "symbol": sym,
                "company_name": entry.get("company_name") or KNOWN_VFEX_SYMBOLS.get(sym, ""),
                "currency": cur_code,
                "isin": entry.get("isin"),
                "security_type": entry.get("security_type") or "EQUITY",
                "upper_limit": entry.get("upper_limit"),
                "lower_limit": entry.get("lower_limit"),
                "band_position_pct": self._band_position_pct(cur, entry),
                "foreign_net": float(fc_info["net_val"]) if fc_info else None,
                "price": cur,
                "change_pct": self.get_daily_change(sym),
                "best_bid": entry.get("best_bid"),
                "best_ask": entry.get("best_ask"),
                "bid_volume": entry.get("bid_volume") or 0,
                "ask_volume": entry.get("ask_volume") or 0,
                "spread_pct": lim["spread_pct"],
                "wide_spread": lim["wide_spread"],
                "liquidity_score": lim["liquidity_score"],
                "optimal_limit": lim["optimal_limit"],
                "history": [h.get("close", h.get("price")) for h in hist[-30:] if ("close" in h or "price" in h)],
                "candles": self.get_candles(sym) if len(hist) >= 2 else [],
                "rsi14": tech["rsi14"],
                "z_score": tech["z_score"],
                "ma20": tech["ma20"],
                "ma20_series": tech["ma20_series"] if len(hist) >= 2 else [],
                "signal_action": sig["action"] if sig else "",
                "signal_horizon": sig.get("horizon", "") if sig else "",
                "signal_score": sig["score"] if sig else 0,
                "recommended_shares": sig.get("recommended_shares", 0) if sig else 0,
                "reasons": sig["reasons"] if sig else [],
                "news_catalyst": (sig.get("news_catalyst") if sig else None) or news_map.get(sym),
            })
        return rows

    def market_breadth(self) -> dict[str, int]:
        """Count advancing, declining, and unchanged VFEX + ZSE counters."""
        adv = dec = unch = vfex_n = zse_n = 0
        for sym, entry in self.state.get("prices", {}).items():
            if infer_currency(sym, entry) == "ZWG":
                zse_n += 1
            else:
                vfex_n += 1
            chg = self.get_daily_change(sym)
            if chg is None or abs(chg) < 1e-6:
                unch += 1
            elif chg > 0:
                adv += 1
            else:
                dec += 1
        return {
            "advancers": adv,
            "decliners": dec,
            "unchanged": unch,
            "total": adv + dec + unch,
            "vfex_count": vfex_n,
            "zse_count": zse_n,
        }

    def portfolio_equity_curve(self, max_points: int = 30) -> list[dict[str, Any]]:
        """Reconstruct daily USD portfolio value vs invested cost curve."""
        trades = [
            tr for tr in self.state.get("trades", [])
            if infer_currency(str(tr.get("symbol", "")), self.get_price_entry(str(tr.get("symbol", "")))) == "USD"
        ]
        history_map = self.state.get("history", {})
        all_dates: set[str] = set()
        for sym in set(self.state.get("portfolio", {}).keys()) | {str(t.get("symbol", "")) for t in trades}:
            if infer_currency(sym, self.get_price_entry(sym)) == "USD":
                for h in history_map.get(sym, []):
                    if h.get("date"):
                        all_dates.add(str(h["date"]))
        for t in trades:
            if t.get("date"):
                all_dates.add(str(t["date"]))
        today_str = datetime.now(timezone.utc).date().isoformat()
        if self.state.get("portfolio"):
            all_dates.add(today_str)
        if not all_dates:
            return []

        dates = sorted(all_dates)[-max_points:]
        price_lookup: dict[str, list[tuple[str, float]]] = {}
        for sym, rows in history_map.items():
            price_lookup[sym] = sorted(
                ((str(r["date"]), float(r.get("close", r.get("price", 0.0)))) for r in rows if r.get("date")),
                key=lambda x: x[0],
            )

        curve: list[dict[str, Any]] = []
        for dt in dates:
            shares_map: dict[str, float] = {}
            avg_map: dict[str, float] = {}
            for tr in trades:
                if str(tr.get("date", "")) > dt:
                    continue
                s = str(tr["symbol"]).upper()
                sh = float(tr["shares"])
                pr = float(tr["price"])
                if tr["action"] == "BUY":
                    old_sh = shares_map.get(s, 0.0)
                    new_sh = old_sh + sh
                    avg_map[s] = ((old_sh * avg_map.get(s, 0.0)) + (sh * pr)) / new_sh if new_sh > 0 else 0.0
                    shares_map[s] = new_sh
                elif tr["action"] == "SELL":
                    rem = max(0.0, shares_map.get(s, 0.0) - sh)
                    if rem <= 1e-9:
                        shares_map.pop(s, None)
                    else:
                        shares_map[s] = rem
            cost_sum = sum(sh * avg_map.get(s, 0.0) for s, sh in shares_map.items())
            val_sum = 0.0
            for s, sh in shares_map.items():
                pts = [p for d, p in price_lookup.get(s, []) if d <= dt]
                px = pts[-1] if pts else (self.get_price(s) or avg_map.get(s, 0.0))
                val_sum += sh * px
            if cost_sum > 0 or val_sum > 0:
                curve.append({"date": dt, "cost": round(cost_sum, 2), "value": round(val_sum, 2)})
        return curve

    def notify_trade_signals(
        self,
        signals: list[dict[str, Any]],
        min_score: int = 30,
        trading_goal: str = "hybrid",
    ) -> list[dict[str, Any]]:
        """Send one desktop notification per day for each high-conviction signal matching the trading goal."""
        goal = normalize_goal(trading_goal)
        today = datetime.now(timezone.utc).date().isoformat()
        seen_today = [k for k in self.state.get("notified_signals", []) if k.startswith(today + ":")]
        seen_set = set(seen_today)
        sent: list[dict[str, Any]] = []
        for sig in signals:
            if int(sig.get("score", 0)) < min_score:
                continue
            hz = str(sig.get("horizon") or "SWING").upper()
            if goal == "long" and hz != "CORE":
                continue
            if goal == "short" and hz != "SWING":
                continue
            key = f"{today}:{sig['action']}:{sig['symbol']}"
            if key in seen_set:
                continue
            seen_set.add(key)
            seen_today.append(key)
            cur_code = sig.get("currency", "USD")
            body = f"[{hz}] {format_money(sig['price'], cur_code, 4)} — {', '.join(sig.get('reasons', []))}"
            send_notification(f"VFEX Signal: {sig['action']} {sig['symbol']}", body)
            sent.append(sig)
        if len(seen_today) != len(self.state.get("notified_signals", [])) or sent:
            self.state["notified_signals"] = seen_today
            self.save()
        return sent

    # === SELF-LEARNING LOCAL $100 PAPER-TRADING AGENT ===

    def get_paper_agent_state(self, zwg_rate: float = 26.5) -> dict[str, Any]:
        """Return persistent isolated $100 paper-agent state, initializing defaults if missing."""
        agent = self.state.get("paper_agent")
        if not isinstance(agent, dict) or "cash_usd" not in agent or "weights" not in agent:
            agent = _default_paper_agent(starting_usd=100.0, zwg_rate=zwg_rate)
            self.state["paper_agent"] = agent
            self.save()
        else:
            if zwg_rate and abs(float(agent.get("zwg_rate") or 26.5) - float(zwg_rate)) > 1e-6:
                agent["zwg_rate"] = round(float(zwg_rate), 4)
            base_w = _default_paper_weights()
            w = agent.setdefault("weights", {})
            for k, v in base_w.items():
                w.setdefault(k, v)
            agent.setdefault("positions", {})
            agent.setdefault("pending_orders", [])
            agent.setdefault("trades", [])
            agent.setdefault("equity_history", [])
            agent.setdefault("lessons", [])
            agent.setdefault("cooldowns", {})
            agent.setdefault("daily_actions", {"date": "", "buys": 0, "sells": 0})
            agent.setdefault("stats", {"wins": 0, "losses": 0, "total_closed": 0, "total_fees_usd": 0.0})
            self._ensure_agent_brain(agent)
            agent.setdefault("shadows", [])
        return agent

    @staticmethod
    def _ensure_agent_brain(agent: dict[str, Any]) -> dict[str, Any]:
        """Ensure Mahoraga brain schema exists cleanly on saved agent dicts."""
        base = _default_mahoraga_brain()
        brain = agent.setdefault("brain", base)
        brain.setdefault("adaptations_spun", 0)
        lw = brain.setdefault("logistic_weights", {})
        for k, v in base["logistic_weights"].items():
            lw.setdefault(k, v)
        pbs = brain.setdefault("playbooks", {})
        for pb in PAPER_PLAYBOOKS:
            entry = pbs.setdefault(pb, {"wins": 0, "losses": 0, "total_net_pct": 0.0, "mult": 1.0})
            entry.setdefault("wins", 0)
            entry.setdefault("losses", 0)
            entry.setdefault("total_net_pct", 0.0)
            entry.setdefault("mult", 1.0)
        po_def = base["payoffs"]
        po = brain.setdefault("payoffs", dict(po_def))
        po.setdefault("avg_win_pct", po_def["avg_win_pct"])
        po.setdefault("avg_loss_pct", po_def["avg_loss_pct"])
        brain.setdefault("immunities", {})
        ep_def = _default_exit_policy()
        ep = brain.setdefault("exit_policy", ep_def)
        for ek, ev in ep_def.items():
            ep.setdefault(ek, ev)
        gk_def = _default_grok_state()
        gk = brain.setdefault("grok", gk_def)
        for gk_k, gk_v in gk_def.items():
            if gk_k == "metrics":
                gm = gk.setdefault("metrics", dict(gk_v))
                for mk, mv in gk_v.items():
                    gm.setdefault(mk, mv)
            else:
                gk.setdefault(gk_k, gk_v)
        return brain

    @staticmethod
    def _adapt_exit_policy(
        brain: dict[str, Any],
        exit_reason: str,
        net_pnl_pct: float,
        px_chg_pct: float,
        hold_days: int,
        min_hold: int,
        is_zse: bool,
        followup_delta_pct: float | None = None,
    ) -> list[str]:
        """Evolve exit strictness, profit targets & stops from real closed exits and post-exit followups."""
        ep_def = _default_exit_policy()
        ep = brain.setdefault("exit_policy", ep_def)
        for ek, ev in ep_def.items():
            ep.setdefault(ek, ev)
        notes: list[str] = []
        rlow = str(exit_reason or "").lower()
        is_caution_exit = "cautionary news" in rlow
        is_hard_stop = "hard risk stop" in rlow
        is_take_profit = "profit target" in rlow or "rsi" in rlow

        # Direct fee-churn feedback: premature news exit at ~0% price move that lost net to fees
        if followup_delta_pct is None:
            if is_caution_exit and hold_days < min_hold and net_pnl_pct < 0.0 and px_chg_pct >= -1.5:
                ep["premature_exit_losses"] = int(ep.get("premature_exit_losses") or 0) + 1
                old_s = int(ep.get("caution_exit_strictness") or 0)
                if old_s < 2:
                    ep["caution_exit_strictness"] = old_s + 1
                    brain["adaptations_spun"] = int(brain.get("adaptations_spun") or 0) + 1
                    notes.append(f"Exit Policy: Caution Tier -> {ep['caution_exit_strictness']} (flat-price fee churn)")
            return notes

        # Counterfactual 5+ day post-exit validation
        if is_caution_exit and followup_delta_pct >= 2.0 and net_pnl_pct < 0.0:
            old_s = int(ep.get("caution_exit_strictness") or 0)
            if old_s < 2:
                ep["caution_exit_strictness"] = old_s + 1
                brain["adaptations_spun"] = int(brain.get("adaptations_spun") or 0) + 1
                notes.append(f"Exit Policy: Caution Tier -> {ep['caution_exit_strictness']} (missed +{followup_delta_pct:.1f}% recovery)")
        elif is_hard_stop and followup_delta_pct >= 5.0:
            cur_stop = float(ep.get("hard_stop_pct") or -8.0)
            if cur_stop > -10.5:
                ep["hard_stop_pct"] = round(max(-10.5, cur_stop - 0.5), 1)
                brain["adaptations_spun"] = int(brain.get("adaptations_spun") or 0) + 1
                notes.append(f"Exit Policy: Hard Stop -> {ep['hard_stop_pct']:.1f}%")
        elif is_take_profit and followup_delta_pct >= 5.0:
            key = "zse_take_pct" if is_zse else "swing_take_pct"
            cur_t = float(ep.get(key) or (6.5 if is_zse else 4.5))
            hi = 10.5 if is_zse else 8.5
            if cur_t < hi:
                ep[key] = round(min(hi, cur_t + 0.5), 1)
                brain["adaptations_spun"] = int(brain.get("adaptations_spun") or 0) + 1
                notes.append(f"Exit Policy: {key} -> +{ep[key]:.1f}%")
        return notes

    @staticmethod
    def _mahoraga_check_immunity(
        brain: dict[str, Any],
        playbook: str,
        spread_pct: float,
        is_zse: bool,
        dip_30d: float,
        has_dtr_vol: bool,
    ) -> str:
        """Return blocking immunity label if evolved adaptation shields against this trap, else ''."""
        imms = brain.get("immunities") or {}
        sp_imm = imms.get("wide_spread_trap") or {}
        if sp_imm.get("active") and spread_pct > 8.0:
            return f"Shield: Spread>{8:.0f}% Trap"
        bk_imm = imms.get("weak_book_fakeout") or {}
        if bk_imm.get("active") and playbook == "Book Imbalance" and dip_30d < 2.0 and not has_dtr_vol:
            return "Shield: Unconfirmed Book Fakeout"
        zse_imm = imms.get("zse_fee_chop") or {}
        if zse_imm.get("active") and is_zse and dip_30d < 3.5 and not has_dtr_vol:
            return "Shield: ZSE 4.4% Chop Filter"
        nw_imm = imms.get("stale_news_chase") or {}
        if nw_imm.get("active") and playbook == "News Catalyst" and dip_30d < 1.0:
            return "Shield: No-Dip News Chase"
        return ""

    def _mahoraga_update(
        self,
        agent: dict[str, Any],
        feat_vec: dict[str, float],
        playbook: str,
        net_pnl_pct: float,
        spread_pct: float,
        is_zse: bool,
        dip_30d: float,
        has_dtr_vol: bool,
        as_of_date: str,
        is_shadow: bool = False,
    ) -> list[str]:
        """Update online logistic SGD weights, playbook bandits, and Mahoraga regime immunities."""
        brain = self._ensure_agent_brain(agent)
        pred = _mahoraga_predict(brain, feat_vec, playbook, is_zse)
        p = float(pred["win_prob_pct"]) / 100.0
        y = 1.0 if net_pnl_pct >= 0.5 else 0.0
        lr = 0.12 if is_shadow else 0.28
        err = y - p

        lw = brain["logistic_weights"]
        for k, x in feat_vec.items():
            w_old = float(lw.get(k, 0.0))
            w_new = w_old + lr * (err * float(x) - 0.02 * w_old)
            lw[k] = round(max(-2.5, min(2.5, w_new)), 4)

        pb_map = brain["playbooks"]
        pb = pb_map.setdefault(playbook, {"wins": 0, "losses": 0, "total_net_pct": 0.0, "mult": 1.0})
        po = brain.setdefault("payoffs", {"avg_win_pct": 8.5, "avg_loss_pct": 5.0})
        if not is_shadow:
            if y >= 0.5:
                pb["wins"] = int(pb.get("wins") or 0) + 1
                pb["mult"] = round(min(1.60, float(pb.get("mult") or 1.0) + 0.08), 2)
                po["avg_win_pct"] = round(max(3.5, min(25.0, 0.75 * float(po.get("avg_win_pct") or 8.5) + 0.25 * max(2.0, net_pnl_pct))), 2)
            else:
                pb["losses"] = int(pb.get("losses") or 0) + 1
                pb["mult"] = round(max(0.55, float(pb.get("mult") or 1.0) - 0.10), 2)
                po["avg_loss_pct"] = round(max(2.0, min(15.0, 0.75 * float(po.get("avg_loss_pct") or 5.0) + 0.25 * max(1.0, abs(net_pnl_pct)))), 2)
            pb["total_net_pct"] = round(float(pb.get("total_net_pct") or 0.0) + net_pnl_pct, 2)
        else:
            delta_m = 0.03 if y >= 0.5 else -0.04
            pb["mult"] = round(max(0.55, min(1.60, float(pb.get("mult") or 1.0) + delta_m)), 2)

        spun_notes: list[str] = []
        imms = brain["immunities"]

        def _bump_imm(key: str, label: str, desc: str, activate_at: int = 2) -> None:
            rec = imms.setdefault(key, {"id": key, "label": label, "description": desc, "loss_count": 0, "active": False, "updated_at": as_of_date})
            rec["loss_count"] = int(rec.get("loss_count") or 0) + 1
            rec["updated_at"] = as_of_date
            if rec["loss_count"] >= activate_at or net_pnl_pct <= -5.0:
                was_active = bool(rec.get("active"))
                rec["active"] = True
                if not was_active:
                    spun_notes.append(f"Wheel Spun: {label} ACTIVE")

        if y < 0.5:
            if spread_pct > 7.5:
                _bump_imm("wide_spread_trap", "Spread Trap Shield", "Blocks >8% illiquid spread entries after repeated slippage losses.")
            if playbook == "Book Imbalance" and dip_30d < 2.0 and not has_dtr_vol:
                _bump_imm("weak_book_fakeout", "Book Fakeout Shield", "Requires dip >=2% or DTR volume before trading order-book skew.")
            if is_zse and dip_30d < 3.5 and net_pnl_pct > -7.0:
                _bump_imm("zse_fee_chop", "ZSE Fee-Chop Filter", "Blocks shallow ZWG bounces eaten by 4.38% CGT & levies.")
            if playbook == "News Catalyst" and dip_30d < 1.0:
                _bump_imm("stale_news_chase", "News Chase Shield", "Prevents chasing News spikes without an entry pullback.")
        else:
            # Successful outcome softens temporary immunity count gradually if setup succeeded cleanly
            for rec in imms.values():
                if rec.get("active") and net_pnl_pct >= 5.0 and int(rec.get("loss_count") or 0) > 1:
                    rec["loss_count"] = int(rec["loss_count"]) - 1

        brain["adaptations_spun"] = int(brain.get("adaptations_spun") or 0) + 1
        return spun_notes

    @staticmethod
    def _record_agent_shadow(
        agent: dict[str, Any],
        cand: dict[str, Any],
        as_of_date: str,
        reason: str,
    ) -> None:
        """Record a skipped or shielded setup cleanly to measure 5-10d counterfactual net outcome."""
        shadows = agent.setdefault("shadows", [])
        sym = str(cand.get("symbol") or "")
        if any(sh.get("symbol") == sym and sh.get("date") == as_of_date for sh in shadows[-15:]):
            return
        if sum(1 for sh in shadows[-10:] if sh.get("date") == as_of_date) >= 2:
            return
        shadows.append({
            "id": f"{as_of_date}-SH-{sym}-{len(shadows) + 1}",
            "date": as_of_date,
            "symbol": sym,
            "currency": cand.get("currency", "USD"),
            "entry_price": float(cand.get("price") or 0.0),
            "playbook": cand.get("playbook", "Dip Reversal"),
            "feat_vec": cand.get("feat_vec") or {},
            "spread_pct": float((cand.get("features") or {}).get("spread_pct") or 0.0),
            "is_zse": bool((cand.get("features") or {}).get("is_zse")),
            "dip_30d": float((cand.get("features") or {}).get("dip_30d") or 0.0),
            "has_dtr_vol": float((cand.get("features") or {}).get("vol_pts") or 0.0) > 0.0,
            "reason": reason,
            "resolved": False,
            "shadow_net_pct": None,
        })
        if len(shadows) > 60:
            agent["shadows"] = shadows[-60:]

    def _evaluate_agent_shadows(
        self,
        agent: dict[str, Any],
        prices_map: dict[str, dict[str, Any]],
        step_date: str,
    ) -> int:
        """Resolve >=5-day-old counterfactual shadows against live quotes & feed Mahoraga."""
        resolved_count = 0
        try:
            cur_dt = datetime.fromisoformat(step_date).date()
        except ValueError:
            return 0
        for sh in agent.get("shadows", []):
            if sh.get("resolved"):
                continue
            try:
                s_dt = datetime.fromisoformat(str(sh.get("date") or step_date)).date()
            except ValueError:
                continue
            age = (cur_dt - s_dt).days
            if age < 5:
                continue
            sym = str(sh.get("symbol") or "")
            entry_px = float(sh.get("entry_price") or 0.0)
            now_px = float((prices_map.get(sym) or {}).get("price") or 0.0)
            if entry_px <= 0 or now_px <= 0:
                if age > 20:
                    sh["resolved"] = True
                continue
            cur_code = str(sh.get("currency") or "USD")
            if sh.get("shadow_type") == "exit_followup":
                delta_pct = ((now_px - entry_px) / entry_px) * 100.0
                sh["resolved"] = True
                sh["resolved_date"] = step_date
                sh["shadow_net_pct"] = round(delta_pct, 2)
                brain = self._ensure_agent_brain(agent)
                self._adapt_exit_policy(
                    brain,
                    exit_reason=str(sh.get("reason") or ""),
                    net_pnl_pct=float(sh.get("exit_net_pct") or 0.0),
                    px_chg_pct=0.0,
                    hold_days=int(sh.get("hold_days") or 0),
                    min_hold=int(sh.get("min_hold") or 3),
                    is_zse=(cur_code == "ZWG"),
                    followup_delta_pct=delta_pct,
                )
                resolved_count += 1
                continue
            buy_n = calculate_trade_charges(cur_code, "BUY", 100.0, entry_px)
            sell_n = calculate_trade_charges(cur_code, "SELL", 100.0, now_px)
            net_pct = ((sell_n["net_settlement"] - buy_n["net_settlement"]) / buy_n["net_settlement"]) * 100.0 if buy_n["net_settlement"] > 0 else 0.0
            sh["resolved"] = True
            sh["resolved_date"] = step_date
            sh["shadow_net_pct"] = round(net_pct, 2)
            self._mahoraga_update(
                agent,
                feat_vec=sh.get("feat_vec") or {},
                playbook=str(sh.get("playbook") or "Dip Reversal"),
                net_pnl_pct=net_pct,
                spread_pct=float(sh.get("spread_pct") or 0.0),
                is_zse=bool(sh.get("is_zse")),
                dip_30d=float(sh.get("dip_30d") or 0.0),
                has_dtr_vol=bool(sh.get("has_dtr_vol")),
                as_of_date=step_date,
                is_shadow=True,
            )
            resolved_count += 1
        return resolved_count

    def reset_paper_agent(self, starting_usd: float = 100.0, zwg_rate: float = 26.5) -> dict[str, Any]:
        """Reset paper agent cleanly to starting capital & fresh baseline weights."""
        agent = _default_paper_agent(starting_usd=starting_usd, zwg_rate=zwg_rate)
        self.state["paper_agent"] = agent
        self.save()
        return agent

    def toggle_paper_agent(self, enabled: bool | None = None) -> bool:
        """Pause or resume autonomous paper agent execution."""
        agent = self.get_paper_agent_state()
        new_val = (not bool(agent.get("enabled", True))) if enabled is None else bool(enabled)
        agent["enabled"] = new_val
        self.save()
        return new_val

    def _agent_mark_to_market(self, agent: dict[str, Any], prices_map: dict[str, dict[str, Any]], as_of_date: str) -> float:
        """Update equity_history snapshot for as_of_date cleanly in unified USD."""
        rate = max(1.0, float(agent.get("zwg_rate") or 26.5))
        cash_total_usd = float(agent.get("cash_usd") or 0.0) + (float(agent.get("cash_zwg") or 0.0) / rate)
        invested_usd = 0.0
        for sym, pos in agent.get("positions", {}).items():
            entry = prices_map.get(sym, {})
            cur_px = float(entry.get("price") or pos.get("last_price") or pos.get("entry_price") or 0.0)
            if cur_px > 0:
                pos["last_price"] = cur_px
                if cur_px > float(pos.get("peak_price") or 0.0):
                    pos["peak_price"] = cur_px
            sh = float(pos.get("shares") or 0.0)
            val_native = sh * float(pos.get("last_price") or pos.get("entry_price") or 0.0)
            if str(pos.get("currency") or "USD") == "ZWG":
                invested_usd += val_native / rate
            else:
                invested_usd += val_native
        total_eq = round(cash_total_usd + invested_usd, 2)
        fees_usd = round(float(agent.get("stats", {}).get("total_fees_usd") or 0.0), 2)
        hist = agent.setdefault("equity_history", [])
        point = {
            "date": as_of_date,
            "equity_usd": total_eq,
            "cash_usd": round(cash_total_usd, 2),
            "invested_usd": round(invested_usd, 2),
            "fees_paid_usd": fees_usd,
        }
        if hist and hist[-1].get("date") == as_of_date:
            hist[-1] = point
        else:
            hist.append(point)
            if len(hist) > 120:
                agent["equity_history"] = hist[-120:]
        return total_eq

    def _agent_score_candidates(
        self,
        agent: dict[str, Any],
        prices_map: dict[str, dict[str, Any]],
        history_map: dict[str, list[dict[str, Any]]],
        news_map: dict[str, dict[str, Any]],
        as_of_date: str,
        tracked_only: bool = False,
        blocked_out: list[dict[str, Any]] | None = None,
        record_shadows: bool = True,
    ) -> list[dict[str, Any]]:
        """Score buy candidates using adaptive weights + realistic fee hurdles & cooldowns."""
        w = agent.get("weights", _default_paper_weights())
        cooldowns = agent.get("cooldowns", {})
        positions = agent.get("positions", {})
        tracked = self.get_tracked_symbols()
        intel = self.get_cached_intel()
        dtr_counters = intel.get("counters", {}) if isinstance(intel, dict) else {}
        blue_chips = intel.get("blue_chips", {}) if isinstance(intel, dict) else {}
        foreign_counters = intel.get("foreign_counters", {}) if isinstance(intel, dict) else {}
        regime = _compute_market_regime(prices_map, intel)
        zwg_rate = max(1.0, float(agent.get("zwg_rate") or 26.5))
        cands: list[dict[str, Any]] = []

        for sym, entry in sorted(prices_map.items()):
            if sym in positions:
                continue
            if tracked_only and sym not in tracked:
                continue
            cd_until = str(cooldowns.get(sym) or "")
            if cd_until and as_of_date < cd_until:
                continue
            cur = float(entry.get("price") or 0.0)
            if cur <= 0:
                continue
            cur_code = infer_currency(sym, entry)
            hist = [h for h in history_map.get(sym, []) if str(h.get("date", "")) <= as_of_date]
            tech = compute_symbol_technicals(hist, cur)
            drop30 = float(tech.get("drop30") or 0.0)
            chg_pct = entry.get("change_pct")
            bid = float(entry.get("best_bid") or 0.0)
            ask = float(entry.get("best_ask") or 0.0)
            bid_vol = int(entry.get("bid_volume") or 0)
            ask_vol = int(entry.get("ask_volume") or 0)
            lim = compute_smart_limit(cur, bid, ask, bid_vol, ask_vol, "BUY")
            spread_pct = float(lim.get("spread_pct") or 0.0)

            # Reject severe illiquidity traps where spread exceeds 25%
            if spread_pct > 25.0:
                continue

            # Book-depth capacity check: don't enter counters whose top-of-book bid can't absorb >= $8 exit
            if bid > 0 and bid_vol > 0:
                bid_depth_usd = (bid * bid_vol / zwg_rate) if cur_code == "ZWG" else (bid * bid_vol)
                if bid_depth_usd < 8.0:
                    if blocked_out is not None:
                        blocked_out.append({
                            "symbol": sym, "currency": cur_code, "playbook": "Liquidity Guard",
                            "score": 0, "win_prob_pct": 0.0, "expected_net_pct": 0.0,
                            "block_reason": f"Thin Bid Depth (${bid_depth_usd:.1f})",
                        })
                    continue

            book_ratio = round(bid_vol / max(1, ask_vol), 2) if (bid > 0 and bid_vol >= 50) else 0.0
            news_cat = news_map.get(sym)
            news_imp = int(news_cat.get("impact_score") or 0) if news_cat else 0
            if news_imp <= -12:
                # Never buy into active Cautionary / negative news
                continue

            dip_pts = min(38.0, drop30 * 3.5) * float(w.get("dip_mult", 1.0)) if (len(hist) >= 2 and drop30 >= 2.0) else 0.0
            if chg_pct is not None and float(chg_pct) <= -2.0 and dip_pts == 0.0:
                dip_pts = min(28.0, abs(float(chg_pct)) * 4.5) * float(w.get("dip_mult", 1.0))
            rsi_val = tech.get("rsi14")
            rsi_pts = 22.0 * float(w.get("rsi_mult", 1.0)) if (rsi_val is not None and float(rsi_val) <= 38.0) else 0.0
            book_pts = (25.0 if book_ratio >= 2.0 else 12.0) * float(w.get("book_mult", 1.0)) if book_ratio >= 1.4 else 0.0
            news_pts = min(28.0, float(news_imp) * 1.25) * float(w.get("news_mult", 1.0)) if news_imp >= 12 else 0.0

            dtr_info = dtr_counters.get(sym)
            bc_info = blue_chips.get(sym)
            fc_info = foreign_counters.get(sym)
            band_pos = self._band_position_pct(cur, entry)
            vol_pts = 15.0 * float(w.get("volume_mult", 1.0)) if (dtr_info and float(dtr_info.get("value_traded") or 0.0) > 0) else 0.0
            bc_pts = 8.0 if (bc_info and (dip_pts > 0 or rsi_pts > 0 or vol_pts > 0)) else 0.0
            band_adj = 8.0 if (band_pos is not None and band_pos <= 20.0) else (-12.0 if (band_pos is not None and band_pos >= 90.0) else 0.0)
            f_adj = 0.0
            if fc_info:
                f_net = float(fc_info.get("net_val") or 0.0)
                f_thr = 50000.0 if cur_code == "ZWG" else 1000.0
                if f_net >= f_thr:
                    f_adj = 8.0
                elif f_net <= -f_thr:
                    f_adj = -8.0

            spread_pen = 8.0 * float(w.get("wide_spread_penalty", 1.0)) if spread_pct > 10.0 else 0.0
            # ZSE carries ~4.38% round-trip cost incl CGT, require extra edge via zse_hurdle_mult
            zse_pen = 6.0 * float(w.get("zse_hurdle_mult", 1.0)) if cur_code == "ZWG" else 0.0

            raw_score = dip_pts + rsi_pts + book_pts + news_pts + vol_pts + bc_pts + band_adj + f_adj - spread_pen - zse_pen
            score = int(round(max(0.0, min(100.0, raw_score))))
            if score < int(w.get("min_entry_score", 22)):
                continue

            reasons: list[str] = []
            if news_pts > 0 and news_cat:
                reasons.append(f"News+{int(round(news_pts))}: {news_cat.get('category', 'Catalyst')}")
            if vol_pts > 0 and dtr_info:
                vt = float(dtr_info["value_traded"])
                v_lbl = f"${vt / 1000.0:.1f}k" if cur_code == "USD" and vt >= 1000 else (f"ZiG {vt / 1000.0:.1f}k" if vt >= 1000 else f"{vt:.0f}")
                reasons.append(f"DTR Vol {v_lbl}")
            if bc_pts > 0 and bc_info:
                reasons.append(f"Top{bc_info['rank']} Cap")
            if f_adj > 0 and fc_info:
                reasons.append(f"Foreign Inflow {format_money(float(fc_info.get('net_val') or 0.0), cur_code, 0)}")
            elif f_adj < 0 and fc_info:
                reasons.append(f"Foreign Outflow {format_money(abs(float(fc_info.get('net_val') or 0.0)), cur_code, 0)}")
            if dip_pts > 0:
                reasons.append(f"Dip -{drop30:.1f}%" if drop30 >= 2.0 else f"{float(chg_pct or 0):.1f}% today")
            if rsi_pts > 0 and rsi_val is not None:
                reasons.append(f"RSI {float(rsi_val):.0f}")
            if book_pts > 0:
                reasons.append(f"Bid {bid_vol} > Ask {ask_vol}")
            if not reasons:
                continue

            horizon = "CORE" if ((news_cat and news_cat.get("category") in ("Dividend", "Expansion", "Listing")) or drop30 >= 6.0 or bc_pts > 0) else "SWING"
            exec_px = ask if (ask > 0 and ask >= cur * 0.99 and spread_pct <= 8.0) else cur
            # Stage passive 2d GTD Smart Limit when wide spread lacks buyer swarm (ask-heavy or >14% spread)
            smart_limit_px = float(lim.get("optimal_limit") or exec_px)
            should_stage_limit = (spread_pct > 14.0 or (spread_pct > 4.0 and ask > cur * 1.03 and bid_vol < ask_vol * 2)) and smart_limit_px < exec_px * 0.99
            max_book_shares = int(max(1, ask_vol * 0.50)) if (ask > 0 and ask_vol > 0) else None
            feat_dict = {
                "dip_30d": round(drop30, 2),
                "rsi14": round(float(rsi_val), 1) if rsi_val is not None else None,
                "book_ratio": book_ratio,
                "spread_pct": round(spread_pct, 2),
                "news_impact": news_imp,
                "is_zse": cur_code == "ZWG",
                "regime_score": float(regime["score"]),
                "dip_pts": round(dip_pts, 1),
                "rsi_pts": round(rsi_pts, 1),
                "book_pts": round(book_pts, 1),
                "news_pts": round(news_pts, 1),
                "vol_pts": round(vol_pts, 1),
            }
            playbook = _classify_agent_playbook(dip_pts, rsi_pts, book_pts, news_pts, vol_pts)
            feat_vec = _mahoraga_feature_vector(feat_dict)
            brain = self._ensure_agent_brain(agent)
            pred = _mahoraga_predict(brain, feat_vec, playbook, cur_code == "ZWG")

            cand_obj = {
                "symbol": sym,
                "currency": cur_code,
                "horizon": horizon,
                "score": score,
                "price": exec_px,
                "limit_price": round(smart_limit_px, 4),
                "stage_limit": bool(should_stage_limit),
                "max_book_shares": max_book_shares,
                "playbook": playbook,
                "win_prob_pct": pred["win_prob_pct"],
                "expected_net_pct": pred["expected_net_pct"],
                "ucb_bonus_pct": pred["ucb_bonus_pct"],
                "ucb_edge_pct": pred["ucb_edge_pct"],
                "feat_vec": feat_vec,
                "reasons": reasons,
                "features": feat_dict,
            }
            imm_block = self._mahoraga_check_immunity(
                brain,
                playbook=playbook,
                spread_pct=spread_pct,
                is_zse=(cur_code == "ZWG"),
                dip_30d=drop30,
                has_dtr_vol=(vol_pts > 0.0),
            )
            if imm_block:
                if record_shadows:
                    self._record_agent_shadow(agent, cand_obj, as_of_date, imm_block)
                if blocked_out is not None:
                    blocked_out.append({**cand_obj, "block_reason": imm_block})
                continue
            if int(brain.get("adaptations_spun") or 0) >= 5 and float(pred["ucb_edge_pct"]) <= 0.0:
                edge_blk = f"Negative UCB Edge ({pred['ucb_edge_pct']:+.2f}%)"
                if record_shadows:
                    self._record_agent_shadow(agent, cand_obj, as_of_date, edge_blk)
                if blocked_out is not None:
                    blocked_out.append({**cand_obj, "block_reason": edge_blk})
                continue

            cands.append(cand_obj)

        cands.sort(key=lambda c: (-(float(c["score"]) + (float(c.get("win_prob_pct") or 50.0) - 50.0) * 0.35 + float(c.get("ucb_bonus_pct") or 0.0)), c["symbol"]))
        return cands

    def _learn_from_closed_trade(self, agent: dict[str, Any], sell_trade: dict[str, Any], as_of_date: str) -> dict[str, Any] | None:
        """Self-learning feedback: inspect net outcome after fees, adapt weights & log lesson."""
        w = agent.setdefault("weights", _default_paper_weights())
        stats = agent.setdefault("stats", {"wins": 0, "losses": 0, "total_closed": 0, "total_fees_usd": 0.0})
        sym = str(sell_trade.get("symbol") or "")
        net_pnl_usd = float(sell_trade.get("realized_net_pnl_usd") or 0.0)
        net_pnl_pct = float(sell_trade.get("net_pnl_pct") or 0.0)
        feats = sell_trade.get("entry_features") or {}
        is_win = net_pnl_usd >= 0.0 and net_pnl_pct >= 0.5
        playbook = str(sell_trade.get("playbook") or "Dip Reversal")
        feat_vec = sell_trade.get("entry_feat_vec") or _mahoraga_feature_vector(feats)
        spun_notes = self._mahoraga_update(
            agent,
            feat_vec=feat_vec,
            playbook=playbook,
            net_pnl_pct=net_pnl_pct,
            spread_pct=float(feats.get("spread_pct") or 0.0),
            is_zse=bool(feats.get("is_zse")),
            dip_30d=float(feats.get("dip_30d") or 0.0),
            has_dtr_vol=float(feats.get("vol_pts") or 0.0) > 0.0,
            as_of_date=as_of_date,
            is_shadow=False,
        )
        exit_reason = str(sell_trade.get("exit_reason") or (sell_trade.get("reasons") or [""])[0])
        spun_notes.extend(self._adapt_exit_policy(
            self._ensure_agent_brain(agent),
            exit_reason=exit_reason,
            net_pnl_pct=net_pnl_pct,
            px_chg_pct=float(sell_trade.get("price_chg_pct") or 0.0),
            hold_days=int(sell_trade.get("hold_days") or 0),
            min_hold=int(sell_trade.get("entry_min_hold") or 3),
            is_zse=bool(feats.get("is_zse")),
            followup_delta_pct=None,
        ))

        stats["total_closed"] = int(stats.get("total_closed") or 0) + 1
        if is_win:
            stats["wins"] = int(stats.get("wins") or 0) + 1
        else:
            stats["losses"] = int(stats.get("losses") or 0) + 1

        def _clamp(val: float, lo: float = 0.4, hi: float = 2.0) -> float:
            return round(max(lo, min(hi, val)), 2)

        lesson: dict[str, Any] | None = None
        if not is_win:
            adjustments: list[str] = []
            spread_v = float(feats.get("spread_pct") or 0.0)
            is_zse = bool(feats.get("is_zse"))
            rsi_v = feats.get("rsi14")
            dip_v = float(feats.get("dip_30d") or 0.0)

            if spread_v > 5.0:
                w["wide_spread_penalty"] = _clamp(float(w.get("wide_spread_penalty", 1.0)) + 0.25)
                adjustments.append(f"Spread penalty -> {w['wide_spread_penalty']}x")
            if is_zse and net_pnl_pct > -6.0:
                w["zse_hurdle_mult"] = _clamp(float(w.get("zse_hurdle_mult", 1.0)) + 0.25)
                adjustments.append(f"ZSE 4.4% fee hurdle -> {w['zse_hurdle_mult']}x")
            if dip_v < 3.0 and (rsi_v is None or float(rsi_v) > 45.0):
                w["min_entry_score"] = min(65, int(w.get("min_entry_score", 22)) + 3)
                adjustments.append(f"Min score -> {w['min_entry_score']}")
            if float(feats.get("news_pts") or 0.0) > 10.0:
                w["news_mult"] = _clamp(float(w.get("news_mult", 1.0)) - 0.12)
                adjustments.append(f"News mult -> {w['news_mult']}x")
            if float(feats.get("book_pts") or 0.0) > 10.0 and dip_v < 2.0:
                w["book_mult"] = _clamp(float(w.get("book_mult", 1.0)) - 0.12)
                adjustments.append(f"Book mult -> {w['book_mult']}x")
            if float(feats.get("vol_pts") or 0.0) > 10.0:
                w["volume_mult"] = _clamp(float(w.get("volume_mult", 1.0)) - 0.10)
                adjustments.append(f"Vol mult -> {w['volume_mult']}x")
            if not adjustments:
                w["min_entry_score"] = min(65, int(w.get("min_entry_score", 22)) + 2)
                adjustments.append(f"Min score -> {w['min_entry_score']}")

            # Place symbol on loss cooldown (14d first loss, 21d repeat loss)
            prior_losses = sum(
                1 for t in agent.get("trades", [])[-12:]
                if t.get("symbol") == sym and t.get("side") == "SELL" and float(t.get("realized_net_pnl_usd") or 0.0) < 0
            )
            cd_days = 21 if prior_losses >= 2 else 14
            try:
                cd_date = (datetime.fromisoformat(as_of_date).date() + timedelta(days=cd_days)).isoformat()
            except ValueError:
                cd_date = as_of_date
            agent.setdefault("cooldowns", {})[sym] = cd_date
            adjustments.append(f"{cd_days}d cooldown on {sym}")

            lesson = {
                "date": as_of_date,
                "type": "MISTAKE",
                "symbol": sym,
                "playbook": playbook,
                "net_pnl_usd": round(net_pnl_usd, 2),
                "net_pnl_pct": round(net_pnl_pct, 2),
                "summary": f"{sym} [{playbook}] closed {net_pnl_pct:+.1f}% net after fees (${sell_trade.get('round_trip_fees_usd', 0):.2f} charges)",
                "adjustment": " • ".join(adjustments + spun_notes),
            }
        elif net_pnl_pct >= 2.0:
            boosts: list[str] = []
            if float(feats.get("dip_pts") or 0.0) > 10.0:
                w["dip_mult"] = _clamp(float(w.get("dip_mult", 1.0)) + 0.10)
                boosts.append(f"Dip -> {w['dip_mult']}x")
            if float(feats.get("rsi_pts") or 0.0) > 10.0:
                w["rsi_mult"] = _clamp(float(w.get("rsi_mult", 1.0)) + 0.10)
                boosts.append(f"RSI -> {w['rsi_mult']}x")
            if float(feats.get("news_pts") or 0.0) > 10.0:
                w["news_mult"] = _clamp(float(w.get("news_mult", 1.0)) + 0.10)
                boosts.append(f"News -> {w['news_mult']}x")
            if float(feats.get("book_pts") or 0.0) > 10.0:
                w["book_mult"] = _clamp(float(w.get("book_mult", 1.0)) + 0.08)
                boosts.append(f"Book -> {w['book_mult']}x")
            if float(feats.get("vol_pts") or 0.0) > 10.0:
                w["volume_mult"] = _clamp(float(w.get("volume_mult", 1.0)) + 0.10)
                boosts.append(f"DTR Vol -> {w['volume_mult']}x")
            if stats.get("wins", 0) >= 2 and stats["wins"] > stats.get("losses", 0):
                w["min_entry_score"] = max(18, int(w.get("min_entry_score", 22)) - 1)
            lesson = {
                "date": as_of_date,
                "type": "WIN",
                "symbol": sym,
                "playbook": playbook,
                "net_pnl_usd": round(net_pnl_usd, 2),
                "net_pnl_pct": round(net_pnl_pct, 2),
                "summary": f"{sym} [{playbook}] +{net_pnl_pct:.1f}% net win clearing full contract charges",
                "adjustment": ("Reinforced: " + " • ".join(boosts + spun_notes)) if (boosts or spun_notes) else "Maintained balanced weights",
            }
        elif spun_notes:
            lesson = {
                "date": as_of_date,
                "type": "WIN" if is_win else "MISTAKE",
                "symbol": sym,
                "playbook": playbook,
                "net_pnl_usd": round(net_pnl_usd, 2),
                "net_pnl_pct": round(net_pnl_pct, 2),
                "summary": f"{sym} [{playbook}] {net_pnl_pct:+.1f}% net",
                "adjustment": " • ".join(spun_notes),
            }

        if lesson:
            lessons = agent.setdefault("lessons", [])
            lessons.append(lesson)
            if len(lessons) > 40:
                agent["lessons"] = lessons[-40:]
        return lesson

    def _execute_paper_buy(
        self,
        agent: dict[str, Any],
        cand: dict[str, Any],
        as_of_date: str,
        cash_floor_pct: float = 0.0,
        allow_stage: bool = True,
        pyramid_mult: float = 1.0,
    ) -> dict[str, Any] | None:
        """Execute a paper BUY (or stage 2d Smart Limit) with book-depth caps & regime cash floor."""
        cur = str(cand["currency"])
        px = float(cand["price"])
        rate = max(1.0, float(agent.get("zwg_rate") or 26.5))
        if px <= 0:
            return None

        if allow_stage and cand.get("stage_limit") and cand.get("limit_price"):
            lim_px = float(cand["limit_price"])
            pending = agent.setdefault("pending_orders", [])
            sym_k = str(cand["symbol"])
            if not any(o.get("symbol") == sym_k for o in pending):
                try:
                    exp_dt = (datetime.fromisoformat(as_of_date).date() + timedelta(days=2)).isoformat()
                except ValueError:
                    exp_dt = as_of_date
                pending.append({
                    "id": f"{as_of_date}-LIM-{sym_k}-{len(pending) + 1}",
                    "date": as_of_date,
                    "expires_at": exp_dt,
                    "symbol": sym_k,
                    "currency": cur,
                    "horizon": cand.get("horizon", "SWING"),
                    "limit_price": round(lim_px, 4),
                    "score": int(cand.get("score") or 0),
                    "playbook": cand.get("playbook", "Dip Reversal"),
                    "win_prob_pct": float(cand.get("win_prob_pct") or 55.0),
                    "expected_net_pct": float(cand.get("expected_net_pct") or 0.0),
                    "ucb_edge_pct": float(cand.get("ucb_edge_pct") or 0.0),
                    "max_book_shares": cand.get("max_book_shares"),
                    "feat_vec": cand.get("feat_vec") or {},
                    "features": cand.get("features") or {},
                    "reasons": list(cand.get("reasons") or []),
                })
                if len(pending) > 10:
                    agent["pending_orders"] = pending[-10:]
            return None

        cash_avail = float(agent.get("cash_zwg") or 0.0) if cur == "ZWG" else float(agent.get("cash_usd") or 0.0)
        cash_avail_usd = (cash_avail / rate) if cur == "ZWG" else cash_avail
        min_order_usd = 15.0
        if cash_avail_usd < min_order_usd:
            return None

        # Compute live equity & enforce Regime dynamic cash floor across total cash pools
        total_cash_usd = float(agent.get("cash_usd") or 0.0) + (float(agent.get("cash_zwg") or 0.0) / rate)
        eq_live = total_cash_usd
        for p in (agent.get("positions") or {}).values():
            pval = float(p.get("shares") or 0.0) * float(p.get("last_price") or p.get("entry_price") or 0.0)
            eq_live += (pval / rate) if str(p.get("currency") or "USD") == "ZWG" else pval
        eq_est = max(eq_live, float(agent.get("starting_capital_usd") or 100.0))

        cash_reserve_usd = eq_est * max(0.0, float(cash_floor_pct) / 100.0) if cash_floor_pct > 0 else 0.0
        deployable_total_usd = max(0.0, total_cash_usd - cash_reserve_usd)
        if cash_floor_pct > 0 and deployable_total_usd < min_order_usd:
            return None

        sig_score = int(cand.get("score") or 0)
        win_prob = float(cand.get("win_prob_pct") or 55.0)
        base_pct = 0.35 if sig_score >= 55 else (0.25 if sig_score >= 35 else 0.18)
        tier_pct = max(0.15, min(0.45, base_pct + ((win_prob - 50.0) / 100.0) * 0.15)) * max(0.3, float(pyramid_mult))
        max_pool_usd = min(cash_avail_usd * 0.97, deployable_total_usd) if cash_floor_pct > 0 else (cash_avail_usd * 0.97)
        target_usd = min(max_pool_usd, max(min_order_usd, eq_est * tier_pct))
        if target_usd < min_order_usd:
            return None
        spendable = target_usd * rate if cur == "ZWG" else target_usd
        # Reserve ~2% buffer for buy contract note fees
        shares = int(spendable // (px * 1.02))
        max_bsh = cand.get("max_book_shares")
        book_capped = False
        if max_bsh is not None and int(max_bsh) >= 1 and shares > int(max_bsh):
            shares = int(max_bsh)
            book_capped = True
        if shares < 1:
            return None

        note = calculate_trade_charges(cur, "BUY", shares, px)
        if note["net_settlement"] > cash_avail + 1e-9 or note["net_settlement"] <= 0:
            shares = max(0, shares - 1)
            if shares < 1:
                return None
            note = calculate_trade_charges(cur, "BUY", shares, px)
            if note["net_settlement"] > cash_avail + 1e-9:
                return None
        gross_usd = (float(note["gross"]) / rate) if cur == "ZWG" else float(note["gross"])
        effective_min_usd = 8.0 if (book_capped or pyramid_mult < 1.0) else min_order_usd
        if gross_usd < effective_min_usd:
            return None

        if cur == "ZWG":
            agent["cash_zwg"] = round(cash_avail - note["net_settlement"], 2)
        else:
            agent["cash_usd"] = round(cash_avail - note["net_settlement"], 2)

        charges_usd = round(note["total_charges"] / rate, 4) if cur == "ZWG" else float(note["total_charges"])
        stats = agent.setdefault("stats", {"wins": 0, "losses": 0, "total_closed": 0, "total_fees_usd": 0.0})
        stats["total_fees_usd"] = round(float(stats.get("total_fees_usd") or 0.0) + charges_usd, 4)

        sym = str(cand["symbol"])
        existing_pos = agent.setdefault("positions", {}).get(sym)
        if existing_pos is not None:
            old_sh = float(existing_pos.get("shares") or 0.0)
            old_net = float(existing_pos.get("entry_cost_net") or 0.0)
            old_chg = float(existing_pos.get("entry_charges_usd") or 0.0)
            new_sh = old_sh + float(shares)
            new_avg = ((old_sh * float(existing_pos.get("entry_price") or px)) + (shares * px)) / max(1.0, new_sh)
            existing_pos["shares"] = new_sh
            existing_pos["entry_price"] = round(new_avg, 4)
            existing_pos["entry_gross"] = round(float(existing_pos.get("entry_gross") or 0.0) + note["gross"], 4)
            existing_pos["entry_charges"] = round(float(existing_pos.get("entry_charges") or 0.0) + note["total_charges"], 2)
            existing_pos["entry_cost_net"] = round(old_net + note["net_settlement"], 2)
            existing_pos["entry_charges_usd"] = round(old_chg + charges_usd, 2)
            existing_pos["pyramided"] = True
        else:
            agent["positions"][sym] = {
                "symbol": sym,
                "currency": cur,
                "horizon": cand.get("horizon", "SWING"),
                "shares": float(shares),
                "entry_price": round(px, 4),
                "last_price": round(px, 4),
                "peak_price": round(px, 4),
                "entry_gross": note["gross"],
                "entry_charges": note["total_charges"],
                "entry_cost_net": note["net_settlement"],
                "entry_charges_usd": round(charges_usd, 2),
                "entry_date": as_of_date,
                "entry_score": int(cand.get("score") or 0),
                "playbook": cand.get("playbook", "Dip Reversal"),
                "win_prob_pct": float(cand.get("win_prob_pct") or 55.0),
                "expected_net_pct": float(cand.get("expected_net_pct") or 0.0),
                "entry_feat_vec": cand.get("feat_vec") or {},
                "entry_features": cand.get("features") or {},
                "entry_reasons": list(cand.get("reasons") or []),
            }
        trade_rec = {
            "id": f"{as_of_date}-BUY-{sym}-{len(agent.get('trades', [])) + 1}",
            "date": as_of_date,
            "side": "BUY",
            "symbol": sym,
            "currency": cur,
            "horizon": cand.get("horizon", "SWING"),
            "playbook": cand.get("playbook", "Dip Reversal"),
            "win_prob_pct": float(cand.get("win_prob_pct") or 55.0),
            "shares": float(shares),
            "price": round(px, 4),
            "score": int(cand.get("score") or 0),
            "reasons": list(cand.get("reasons") or []),
            "contract_note": note,
            "fees_usd": round(charges_usd, 2),
            "realized_net_pnl_usd": None,
            "net_pnl_pct": None,
        }
        agent.setdefault("trades", []).append(trade_rec)
        return trade_rec

    def _process_pending_orders(
        self,
        agent: dict[str, Any],
        prices_map: dict[str, dict[str, Any]],
        step_date: str,
        daily: dict[str, Any],
        cash_floor_pct: float,
    ) -> list[dict[str, Any]]:
        """Fill or expire resting 2-day GTD Smart Limit orders when market touches limit."""
        filled: list[dict[str, Any]] = []
        keep: list[dict[str, Any]] = []
        positions = agent.get("positions", {})
        for ord_obj in agent.get("pending_orders", []):
            sym = str(ord_obj.get("symbol") or "")
            if sym in positions:
                continue
            if str(ord_obj.get("expires_at") or step_date) < step_date:
                continue
            q = prices_map.get(sym, {})
            cur_px = float(q.get("price") or 0.0)
            ask_px = float(q.get("best_ask") or 0.0)
            fill_check_px = ask_px if (ask_px > 0 and ask_px <= cur_px * 1.05) else cur_px
            lim_px = float(ord_obj.get("limit_price") or 0.0)
            if fill_check_px > 0 and lim_px > 0 and fill_check_px <= lim_px * 1.005 and int(daily.get("buys") or 0) < 2 and len(positions) < 5:
                cand_fill = {**ord_obj, "price": round(min(fill_check_px, lim_px), 4), "stage_limit": False}
                rec = self._execute_paper_buy(agent, cand_fill, step_date, cash_floor_pct=cash_floor_pct, allow_stage=False)
                if rec:
                    daily["buys"] = int(daily.get("buys") or 0) + 1
                    filled.append(rec)
                    continue
            keep.append(ord_obj)
        agent["pending_orders"] = keep
        return filled

    def _execute_paper_sell(
        self,
        agent: dict[str, Any],
        sym: str,
        sell_px: float,
        as_of_date: str,
        reason: str,
        partial_pct: float = 1.0,
    ) -> dict[str, Any] | None:
        """Execute a full or partial paper SELL with itemized charges and trigger self-learning."""
        positions = agent.get("positions", {})
        pos = positions.get(sym)
        if not pos or sell_px <= 0:
            return None
        cur = str(pos.get("currency") or "USD")
        total_sh = float(pos.get("shares") or 0.0)
        is_partial = partial_pct < 0.99 and total_sh >= 4
        sh = float(int(round(total_sh * partial_pct))) if is_partial else total_sh
        if sh <= 0 or (is_partial and total_sh - sh < 1):
            is_partial = False
            sh = total_sh

        frac = sh / total_sh if total_sh > 0 else 1.0
        rate = max(1.0, float(agent.get("zwg_rate") or 26.5))
        note = calculate_trade_charges(cur, "SELL", sh, sell_px)

        if cur == "ZWG":
            agent["cash_zwg"] = round(float(agent.get("cash_zwg") or 0.0) + note["net_settlement"], 2)
        else:
            agent["cash_usd"] = round(float(agent.get("cash_usd") or 0.0) + note["net_settlement"], 2)

        full_entry_net = float(pos.get("entry_cost_net") or (total_sh * float(pos.get("entry_price") or sell_px)))
        full_entry_chg = float(pos.get("entry_charges_usd") or 0.0)
        entry_net = full_entry_net * frac
        entry_chg_slice = full_entry_chg * frac
        if is_partial:
            pos["shares"] = round(total_sh - sh, 6)
            pos["entry_cost_net"] = round(full_entry_net - entry_net, 4)
            pos["entry_charges_usd"] = round(full_entry_chg - entry_chg_slice, 4)
            pos["partial_taken"] = True
        else:
            positions.pop(sym, None)

        net_pnl_native = note["net_settlement"] - entry_net
        net_pnl_usd = (net_pnl_native / rate) if cur == "ZWG" else net_pnl_native
        net_pnl_pct = (net_pnl_native / entry_net) * 100.0 if entry_net > 0 else 0.0
        exit_fees_usd = (note["total_charges"] / rate) if cur == "ZWG" else float(note["total_charges"])
        rt_fees_usd = entry_chg_slice + exit_fees_usd

        stats = agent.setdefault("stats", {"wins": 0, "losses": 0, "total_closed": 0, "total_fees_usd": 0.0})
        stats["total_fees_usd"] = round(float(stats.get("total_fees_usd") or 0.0) + exit_fees_usd, 4)

        try:
            hold_days = max(0, (datetime.fromisoformat(as_of_date).date() - datetime.fromisoformat(str(pos.get("entry_date") or as_of_date)).date()).days)
        except ValueError:
            hold_days = 0

        entry_px = float(pos.get("entry_price") or sell_px)
        px_chg_pct = ((sell_px - entry_px) / entry_px) * 100.0 if entry_px > 0 else 0.0
        min_hold = 14 if str(pos.get("horizon") or "SWING").upper() == "CORE" else 3
        sell_rec = {
            "id": f"{as_of_date}-SELL-{sym}-{len(agent.get('trades', [])) + 1}",
            "date": as_of_date,
            "side": "SELL",
            "symbol": sym,
            "currency": cur,
            "horizon": pos.get("horizon", "SWING"),
            "playbook": pos.get("playbook", "Dip Reversal"),
            "win_prob_pct": pos.get("win_prob_pct"),
            "shares": sh,
            "price": round(sell_px, 4),
            "entry_price": round(entry_px, 4),
            "price_chg_pct": round(px_chg_pct, 2),
            "hold_days": hold_days,
            "entry_min_hold": min_hold,
            "exit_reason": reason,
            "score": int(pos.get("entry_score") or 0),
            "reasons": [reason],
            "contract_note": note,
            "fees_usd": round(exit_fees_usd, 2),
            "round_trip_fees_usd": round(rt_fees_usd, 2),
            "realized_net_pnl_usd": round(net_pnl_usd, 2),
            "net_pnl_pct": round(net_pnl_pct, 2),
            "entry_feat_vec": pos.get("entry_feat_vec") or {},
            "entry_features": pos.get("entry_features") or {},
        }
        agent.setdefault("trades", []).append(sell_rec)
        # Track 5d post-exit followup counterfactual to learn exit timing (premature caution exits, stops, takes)
        shadows = agent.setdefault("shadows", [])
        shadows.append({
            "id": f"{as_of_date}-EX-{sym}-{len(shadows) + 1}",
            "shadow_type": "exit_followup",
            "date": as_of_date,
            "symbol": sym,
            "currency": cur,
            "entry_price": round(sell_px, 4),
            "exit_net_pct": round(net_pnl_pct, 2),
            "hold_days": hold_days,
            "min_hold": min_hold,
            "reason": reason,
            "resolved": False,
            "shadow_net_pct": None,
        })
        if len(shadows) > 60:
            agent["shadows"] = shadows[-60:]
        self._learn_from_closed_trade(agent, sell_rec, as_of_date)
        return sell_rec

    def run_paper_agent_step(
        self,
        as_of_date: str | None = None,
        allow_off_hours: bool = True,
        prices_override: dict[str, dict[str, Any]] | None = None,
        history_override: dict[str, list[dict[str, Any]]] | None = None,
        news_items: list[dict[str, Any]] | None = None,
        zwg_rate: float = 26.5,
        save_state: bool = True,
    ) -> dict[str, Any]:
        """Run one local paper-trading cycle with hold-period discipline, fee hurdles & Mahoraga adaptation."""
        agent = self.get_paper_agent_state(zwg_rate=zwg_rate)
        step_date = as_of_date or datetime.now(timezone.utc).date().isoformat()
        prices_map = prices_override if prices_override is not None else self.state.get("prices", {})
        history_map = history_override if history_override is not None else self.state.get("history", {})
        news_map = self._news_by_symbol(news_items)

        if not agent.get("enabled", True) and not allow_off_hours:
            self._agent_mark_to_market(agent, prices_map, step_date)
            return {"executed": [], "skipped": "paused"}

        # Autonomous background refreshes only trade when market is Open (manual/replay bypasses this)
        if not allow_off_hours and get_market_status() != "Open":
            self._agent_mark_to_market(agent, prices_map, step_date)
            if save_state:
                self.save()
            return {"executed": [], "skipped": "market_closed"}

        # Resolve >=5d counterfactual shadow experiences before scoring today's setups
        self._evaluate_agent_shadows(agent, prices_map, step_date)

        daily = agent.setdefault("daily_actions", {"date": step_date, "buys": 0, "sells": 0})
        if daily.get("date") != step_date:
            daily = {"date": step_date, "buys": 0, "sells": 0}
            agent["daily_actions"] = daily

        executed: list[dict[str, Any]] = []

        # 1. Evaluate open positions with strict minimum-hold & net-of-fee profit protection
        for sym in list(agent.get("positions", {}).keys()):
            pos = agent["positions"][sym]
            entry = prices_map.get(sym, {})
            cur_px = float(entry.get("price") or 0.0)
            if cur_px <= 0:
                continue
            bid_px = float(entry.get("best_bid") or 0.0)
            sell_px = bid_px if (bid_px > 0 and ((cur_px - bid_px) / cur_px) <= 0.06) else cur_px
            pos["last_price"] = cur_px
            if cur_px > float(pos.get("peak_price") or 0.0):
                pos["peak_price"] = cur_px

            try:
                hold_days = (datetime.fromisoformat(step_date).date() - datetime.fromisoformat(str(pos.get("entry_date") or step_date)).date()).days
            except ValueError:
                hold_days = 0

            est_note = calculate_trade_charges(str(pos.get("currency") or "USD"), "SELL", float(pos["shares"]), sell_px)
            entry_net = float(pos.get("entry_cost_net") or 1.0)
            net_pct = ((est_note["net_settlement"] - entry_net) / entry_net) * 100.0
            peak_px = max(cur_px, float(pos.get("peak_price") or cur_px))
            drawdown_from_peak = ((peak_px - cur_px) / peak_px) * 100.0 if peak_px > 0 else 0.0

            horizon = str(pos.get("horizon") or "SWING").upper()
            is_zse = str(pos.get("currency") or "USD") == "ZWG"
            ep = self._ensure_agent_brain(agent)["exit_policy"]
            min_hold = int(ep.get("core_min_hold") or 14) if horizon == "CORE" else int(ep.get("swing_min_hold") or 3)
            take_target = (25.0 if horizon == "CORE" else float(ep.get("zse_take_pct") or 6.5 if is_zse else ep.get("swing_take_pct") or 4.5))
            hard_stop = float(ep.get("hard_stop_pct") or -8.0)
            entry_px_f = float(pos.get("entry_price") or sell_px)
            px_chg_pct = ((sell_px - entry_px_f) / entry_px_f) * 100.0 if entry_px_f > 0 else 0.0
            news_cat = news_map.get(sym)
            caution_imp = int(news_cat.get("impact_score") or 0) if news_cat else 0
            caution_official = bool(news_cat and news_cat.get("official"))
            strict = int(ep.get("caution_exit_strictness") or 0)
            if caution_imp <= -15:
                if strict == 0:
                    caution_news = True
                elif strict == 1:
                    caution_news = caution_official or px_chg_pct <= -2.5 or hold_days >= min_hold
                else:
                    caution_news = (caution_official and caution_imp <= -20) or hold_days >= min_hold
            else:
                caution_news = False

            sell_reason = ""
            sell_frac = 1.0
            if caution_news:
                sell_reason = f"Cautionary news risk ({net_pct:+.1f}% net)"
            elif net_pct <= hard_stop:
                sell_reason = f"Hard risk stop {hard_stop:.0f}% ({net_pct:+.1f}% net)"
            elif hold_days >= min_hold:
                pos_sh = float(pos.get("shares") or 0.0)
                half_usd = ((pos_sh * 0.5 * sell_px) / max(1.0, float(agent.get("zwg_rate") or 26.5))) if is_zse else (pos_sh * 0.5 * sell_px)
                if net_pct >= take_target:
                    if not pos.get("partial_taken") and pos_sh >= 4 and half_usd >= 12.0:
                        sell_reason = f"Partial scale-out 50% +{take_target:.1f}% ({net_pct:+.1f}% net)"
                        sell_frac = 0.5
                    elif pos.get("partial_taken"):
                        if drawdown_from_peak >= (9.0 if horizon == "CORE" else 5.5):
                            sell_reason = f"Trailing profit lock ({net_pct:+.1f}% net)"
                    else:
                        sell_reason = f"Take-profit +{take_target:.1f}% ({net_pct:+.1f}% net)"
                elif pos.get("partial_taken") and drawdown_from_peak >= (9.0 if horizon == "CORE" else 5.5):
                    sell_reason = f"Trailing profit lock ({net_pct:+.1f}% net)"
                elif horizon == "SWING":
                    hist = [h for h in history_map.get(sym, []) if str(h.get("date", "")) <= step_date]
                    tech = compute_symbol_technicals(hist, cur_px)
                    rsi_val = tech.get("rsi14")
                    if rsi_val is not None and float(rsi_val) >= 70.0 and net_pct >= 2.5:
                        sell_reason = f"Overbought RSI {float(rsi_val):.0f} take-profit ({net_pct:+.1f}% net)"
                    elif hold_days >= 18 and net_pct < 0.0:
                        sell_reason = f"Time stop 18d stale trade ({net_pct:+.1f}% net)"
                elif horizon == "CORE" and drawdown_from_peak >= 10.0 and peak_px >= float(pos.get("entry_price") or cur_px) * 1.12:
                    sell_reason = f"Core trailing profit lock ({net_pct:+.1f}% net)"

            if sell_reason and int(daily.get("sells") or 0) < 2:
                rec = self._execute_paper_sell(agent, sym, sell_px, step_date, sell_reason, partial_pct=sell_frac)
                if rec:
                    daily["sells"] = int(daily.get("sells") or 0) + 1
                    executed.append(rec)

        # 2. Fill or expire resting GTD Smart Limit orders & evaluate new BUY / pyramid entries
        regime = _compute_market_regime(prices_map, self.get_cached_intel())
        cash_floor_pct = float(regime.get("cash_floor_pct") or 25.0)
        for p_rec in self._process_pending_orders(agent, prices_map, step_date, daily, cash_floor_pct):
            executed.append(p_rec)

        if int(daily.get("buys") or 0) < 2 and len(agent.get("positions", {})) < 5:
            cands = self._agent_score_candidates(agent, prices_map, history_map, news_map, step_date, tracked_only=False)
            for cand in cands:
                if int(daily.get("buys") or 0) >= 2 or len(agent.get("positions", {})) >= 5:
                    break
                rec = self._execute_paper_buy(agent, cand, step_date, cash_floor_pct=cash_floor_pct, allow_stage=True)
                if rec:
                    daily["buys"] = int(daily.get("buys") or 0) + 1
                    executed.append(rec)

        # 3. Allow 1 pyramid add-on onto winning CORE positions (>= +4% net with fresh catalyst)
        if int(daily.get("buys") or 0) < 2:
            rate = max(1.0, float(agent.get("zwg_rate") or 26.5))
            for sym, pos in list(agent.get("positions", {}).items()):
                if int(daily.get("buys") or 0) >= 2:
                    break
                if str(pos.get("horizon") or "").upper() != "CORE" or pos.get("pyramided"):
                    continue
                q = prices_map.get(sym, {})
                cur_px = float(q.get("price") or 0.0)
                if cur_px <= 0:
                    continue
                cur_c = str(pos.get("currency") or "USD")
                entry_net = float(pos.get("entry_cost_net") or 1.0)
                est_sell = calculate_trade_charges(cur_c, "SELL", float(pos.get("shares") or 0.0), cur_px)
                cur_net_pct = ((est_sell["net_settlement"] - entry_net) / entry_net) * 100.0
                ncat = news_map.get(sym)
                has_cat = bool((ncat and int(ncat.get("impact_score") or 0) >= 12) or (int(q.get("bid_volume") or 0) >= 2 * max(1, int(q.get("ask_volume") or 0))))
                if cur_net_pct >= 4.0 and has_cat:
                    pyr_cand = {
                        "symbol": sym, "currency": cur_c, "horizon": "CORE", "score": max(40, int(pos.get("entry_score") or 40)),
                        "price": cur_px, "playbook": pos.get("playbook", "DTR Flow"), "win_prob_pct": float(pos.get("win_prob_pct") or 60.0),
                        "expected_net_pct": float(pos.get("expected_net_pct") or 3.0), "feat_vec": pos.get("entry_feat_vec") or {},
                        "features": pos.get("entry_features") or {}, "reasons": [f"Pyramid CORE +{cur_net_pct:.1f}% winner"],
                    }
                    rec = self._execute_paper_buy(agent, pyr_cand, step_date, cash_floor_pct=cash_floor_pct, allow_stage=False, pyramid_mult=0.5)
                    if rec:
                        daily["buys"] = int(daily.get("buys") or 0) + 1
                        executed.append(rec)

        agent["last_step_date"] = step_date
        self._agent_mark_to_market(agent, prices_map, step_date)
        if save_state:
            self.save()
        return {"executed": executed, "date": step_date}

    def _run_history_walk(
        self,
        days: int = 30,
        starting_usd: float = 100.0,
        zwg_rate: float = 26.5,
    ) -> dict[str, Any]:
        """Run chronological OHLC replay inside the active self.state['paper_agent'] slot (no disk write)."""
        agent = _default_paper_agent(starting_usd=starting_usd, zwg_rate=zwg_rate)
        self.state["paper_agent"] = agent
        history_map = self.state.get("history", {})
        all_dates = sorted({str(h.get("date") or "") for rows in history_map.values() for h in rows if h.get("date")})
        if not all_dates:
            self.run_paper_agent_step(allow_off_hours=True, zwg_rate=zwg_rate, save_state=False)
            return agent

        sim_dates = all_dates[-max(5, int(days)):]
        agent["equity_history"] = []
        prices_live = self.state.get("prices", {})
        news_items = self.get_cached_news()

        for sim_date in sim_dates:
            snap_prices: dict[str, dict[str, Any]] = {}
            is_last = (sim_date == sim_dates[-1])
            for sym, rows in history_map.items():
                upto = [r for r in rows if str(r.get("date") or "") <= sim_date]
                if not upto:
                    continue
                last_r = upto[-1]
                px = float(last_r.get("close", last_r.get("price")) or 0.0)
                if px <= 0:
                    continue
                prev_px = float(upto[-2].get("close", upto[-2].get("price")) or px) if len(upto) >= 2 else px
                chg_pct = ((px - prev_px) / prev_px * 100.0) if prev_px > 0 else 0.0
                live_meta = prices_live.get(sym, {})
                snap_prices[sym] = {
                    "price": live_meta.get("price") or px if is_last else px,
                    "currency": live_meta.get("currency") or infer_currency(sym, live_meta),
                    "change_pct": live_meta.get("change_pct") if (is_last and live_meta.get("change_pct") is not None) else round(chg_pct, 2),
                    "best_bid": live_meta.get("best_bid") if is_last else round(px * 0.992, 4),
                    "best_ask": live_meta.get("best_ask") if is_last else round(px * 1.005, 4),
                    "bid_volume": int(live_meta.get("bid_volume") or 300),
                    "ask_volume": int(live_meta.get("ask_volume") or 150),
                }
            if is_last:
                for sym, live_meta in prices_live.items():
                    if sym not in snap_prices and float(live_meta.get("price") or 0.0) > 0:
                        snap_prices[sym] = live_meta
            self.run_paper_agent_step(
                as_of_date=sim_date,
                allow_off_hours=True,
                prices_override=snap_prices,
                history_override=history_map,
                news_items=news_items if is_last else [],
                zwg_rate=zwg_rate,
                save_state=False,
            )
        return agent

    def replay_paper_agent_history(
        self,
        days: int = 30,
        starting_usd: float = 100.0,
        zwg_rate: float = 26.5,
    ) -> dict[str, Any]:
        """Reset & simulate chronological day-by-day trading over stored OHLC history with full fees & learning."""
        self._run_history_walk(days=days, starting_usd=starting_usd, zwg_rate=zwg_rate)
        self.save()
        return self.paper_agent_summary()

    def train_paper_agent_brain(self, days: int = 180, zwg_rate: float = 26.5) -> dict[str, Any]:
        """Warm-train Mahoraga brain weights, playbooks, immunities & Grokking residual on history without altering live cash/holdings."""
        import copy

        live_agent = copy.deepcopy(self.get_paper_agent_state(zwg_rate=zwg_rate))
        try:
            sim_agent = self._run_history_walk(days=days, starting_usd=100.0, zwg_rate=zwg_rate)
            # Extract soft calibration from any sandbox positions still open at walk end (handles short histories cleanly)
            prices_live = self.state.get("prices", {})
            today_str = datetime.now(timezone.utc).date().isoformat()
            for ssym, spos in list((sim_agent.get("positions") or {}).items()):
                px_now = float((prices_live.get(ssym) or {}).get("price") or spos.get("last_price") or spos.get("entry_price") or 0.0)
                sh = float(spos.get("shares") or 0.0)
                entry_net = float(spos.get("entry_cost_net") or 0.0)
                if px_now > 0 and sh > 0 and entry_net > 0:
                    cur_c = str(spos.get("currency") or "USD")
                    exit_n = calculate_trade_charges(cur_c, "SELL", sh, px_now)
                    mtm_net_pct = ((exit_n["net_settlement"] - entry_net) / entry_net) * 100.0
                    sfeats = spos.get("entry_features") or {}
                    self._mahoraga_update(
                        sim_agent,
                        feat_vec=spos.get("entry_feat_vec") or _mahoraga_feature_vector(sfeats),
                        playbook=str(spos.get("playbook") or "Dip Reversal"),
                        net_pnl_pct=mtm_net_pct,
                        spread_pct=float(sfeats.get("spread_pct") or 0.0),
                        is_zse=(cur_c == "ZWG"),
                        dip_30d=float(sfeats.get("dip_30d") or 0.0),
                        has_dtr_vol=float(sfeats.get("vol_pts") or 0.0) > 0.0,
                        as_of_date=today_str,
                        is_shadow=True,
                    )
            # Carry learned sandbox weights/shadows into live agent, then re-apply live closed SELL experience on top
            live_agent["brain"] = sim_agent.get("brain", _default_mahoraga_brain())
            self._ensure_agent_brain(live_agent)
            live_agent["weights"] = sim_agent.get("weights", _default_paper_weights())
            existing_shadows = list(live_agent.get("shadows") or [])
            seen_sh_ids = {sh.get("id") for sh in existing_shadows}
            for sim_sh in (sim_agent.get("shadows") or []):
                if sim_sh.get("id") not in seen_sh_ids:
                    existing_shadows.append(sim_sh)
            live_agent["shadows"] = existing_shadows[-60:]

            for tr in live_agent.get("trades", []):
                if tr.get("side") != "SELL":
                    continue
                tfeats = tr.get("entry_features") or {}
                tn_pct = float(tr.get("net_pnl_pct") or 0.0)
                t_reasons = tr.get("reasons") or [""]
                tr_reason = str(tr.get("exit_reason") or t_reasons[0])
                tpb = str(tr.get("playbook") or "Dip Reversal")
                if "exit_reason" not in tr and "cautionary news" in tr_reason.lower() and not tfeats:
                    tpb = "Book Imbalance"
                self._mahoraga_update(
                    live_agent,
                    feat_vec=tr.get("entry_feat_vec") or _mahoraga_feature_vector(tfeats),
                    playbook=tpb,
                    net_pnl_pct=tn_pct,
                    spread_pct=float(tfeats.get("spread_pct") or 0.0),
                    is_zse=(str(tr.get("currency") or "USD") == "ZWG"),
                    dip_30d=float(tfeats.get("dip_30d") or 0.0),
                    has_dtr_vol=float(tfeats.get("vol_pts") or 0.0) > 0.0,
                    as_of_date=str(tr.get("date") or today_str),
                    is_shadow=False,
                )
                self._adapt_exit_policy(
                    live_agent["brain"],
                    exit_reason=tr_reason,
                    net_pnl_pct=tn_pct,
                    px_chg_pct=float(tr.get("price_chg_pct") or 0.0),
                    hold_days=int(tr.get("hold_days") or 0),
                    min_hold=int(tr.get("entry_min_hold") or (14 if str(tr.get("horizon") or "SWING") == "CORE" else 3)),
                    is_zse=(str(tr.get("currency") or "USD") == "ZWG"),
                    followup_delta_pct=None,
                )
            sb = live_agent["brain"]
            episodes = _build_history_episodes(live_agent, self.state.get("history", {}), prices_live)
            grok_res = _train_grokking_model(sb, episodes, today_str=today_str)
            fb = _load_foundation_brain()
            if fb and fb.get("enabled") and not grok_res.get("enabled"):
                grok_res["enabled"] = True
                grok_res["status"] = str(fb.get("status") or "Grokked (Foundation)")
                fb_m = fb.get("metrics") or {}
                grok_res.setdefault("metrics", {}).update(fb_m)
            gm = grok_res.get("metrics") or {}
            today = today_str
            imms = [v["label"] for v in (sb.get("immunities") or {}).values() if v.get("active")]
            ep_tier = int((sb.get("exit_policy") or {}).get("caution_exit_strictness") or 0)
            grok_note = (
                f"Grokking: {grok_res.get('status')} (Val {gm.get('val_acc_pct', 0):.1f}% vs Lin {gm.get('linear_val_acc_pct', 0):.1f}%, Ep {gm.get('best_epoch', 0)}/{gm.get('epochs_run', 0)})"
                if int(gm.get("episodes_total") or 0) >= GROK_MIN_EPISODES
                else f"Grokking: {grok_res.get('status')} ({gm.get('episodes_total', 0)}/{GROK_MIN_EPISODES} episodes)"
            )
            live_agent.setdefault("lessons", []).append({
                "date": today,
                "type": "TRAIN",
                "symbol": "BRAIN",
                "playbook": "Mahoraga",
                "net_pnl_usd": 0.0,
                "net_pnl_pct": 0.0,
                "summary": f"Trained Mahoraga on {int(days)}d + live trades ({sb.get('adaptations_spun', 0)} spins) • {grok_note}",
                "adjustment": f"Caution Shield Tier {ep_tier}" + (f" • Shields: {', '.join(imms)}" if imms else ""),
            })
            if len(live_agent["lessons"]) > 40:
                live_agent["lessons"] = live_agent["lessons"][-40:]
        finally:
            self.state["paper_agent"] = live_agent
        self.save()
        return self.paper_agent_summary()

    def paper_agent_summary(self, zwg_rate: float | None = None) -> dict[str, Any]:
        """Build JSON-ready UI summary for Tab 5 Auto-Trader."""
        agent = self.get_paper_agent_state(zwg_rate=zwg_rate or 26.5)
        rate = max(1.0, float(agent.get("zwg_rate") or 26.5))
        today = datetime.now(timezone.utc).date().isoformat()
        prices_map = self.state.get("prices", {})

        pos_list: list[dict[str, Any]] = []
        invested_usd = 0.0
        for sym, pos in sorted(agent.get("positions", {}).items()):
            cur_code = str(pos.get("currency") or "USD")
            sh = float(pos.get("shares") or 0.0)
            entry_px = float(pos.get("entry_price") or 0.0)
            live_px = float(prices_map.get(sym, {}).get("price") or pos.get("last_price") or entry_px)
            val_native = sh * live_px
            est_exit = calculate_trade_charges(cur_code, "SELL", sh, live_px)
            entry_net = float(pos.get("entry_cost_net") or (sh * entry_px))
            net_pnl_native = est_exit["net_settlement"] - entry_net
            net_pnl_usd = (net_pnl_native / rate) if cur_code == "ZWG" else net_pnl_native
            net_pnl_pct = (net_pnl_native / entry_net) * 100.0 if entry_net > 0 else 0.0
            invested_usd += (val_native / rate) if cur_code == "ZWG" else val_native
            try:
                hold_days = max(0, (datetime.fromisoformat(today).date() - datetime.fromisoformat(str(pos.get("entry_date") or today)).date()).days)
            except ValueError:
                hold_days = 0
            hz = str(pos.get("horizon") or "SWING").upper()
            pos_list.append({
                "symbol": sym,
                "currency": cur_code,
                "horizon": hz,
                "shares": sh,
                "entry_price": round(entry_px, 4),
                "current_price": round(live_px, 4),
                "value_native": round(val_native, 2),
                "value_usd": round((val_native / rate) if cur_code == "ZWG" else val_native, 2),
                "net_pnl_usd": round(net_pnl_usd, 2),
                "net_pnl_pct": round(net_pnl_pct, 2),
                "hold_days": hold_days,
                "min_hold_days": 14 if hz == "CORE" else 3,
                "entry_date": pos.get("entry_date", today),
                "entry_score": int(pos.get("entry_score") or 0),
                "playbook": pos.get("playbook", "Dip Reversal"),
                "win_prob_pct": pos.get("win_prob_pct"),
                "expected_net_pct": pos.get("expected_net_pct"),
                "entry_reasons": pos.get("entry_reasons") or [],
            })

        cash_usd = float(agent.get("cash_usd") or 0.0)
        cash_zwg = float(agent.get("cash_zwg") or 0.0)
        total_cash_usd = round(cash_usd + (cash_zwg / rate), 2)
        equity_usd = round(total_cash_usd + invested_usd, 2)
        start_usd = float(agent.get("starting_capital_usd") or 100.0)
        net_pnl_usd = round(equity_usd - start_usd, 2)
        net_pnl_pct = round(((equity_usd - start_usd) / start_usd) * 100.0, 2) if start_usd > 0 else 0.0
        stats = agent.get("stats", {})
        wins = int(stats.get("wins") or 0)
        losses = int(stats.get("losses") or 0)
        total_closed = wins + losses
        win_rate = round((wins / total_closed) * 100.0, 1) if total_closed > 0 else 0.0

        active_cooldowns = [
            {"symbol": s, "until": d}
            for s, d in sorted(agent.get("cooldowns", {}).items())
            if str(d) > today
        ]
        brain = self._ensure_agent_brain(agent)
        pb_list = []
        for pb_name in PAPER_PLAYBOOKS:
            pb_data = (brain.get("playbooks") or {}).get(pb_name) or {}
            pw = int(pb_data.get("wins") or 0)
            pl = int(pb_data.get("losses") or 0)
            ptot = pw + pl
            pb_list.append({
                "name": pb_name,
                "wins": pw,
                "losses": pl,
                "win_rate_pct": round((pw / ptot) * 100.0, 0) if ptot > 0 else None,
                "avg_net_pct": round(float(pb_data.get("total_net_pct") or 0.0) / ptot, 2) if ptot > 0 else None,
                "mult": round(float(pb_data.get("mult") or 1.0), 2),
            })
        imm_list = [
            v for v in (brain.get("immunities") or {}).values()
            if isinstance(v, dict)
        ]
        imm_list.sort(key=lambda r: (0 if r.get("active") else 1, -int(r.get("loss_count") or 0)))
        shadows = agent.get("shadows") or []
        shadows_resolved = sum(1 for sh in shadows if sh.get("resolved"))
        shielded_list: list[dict[str, Any]] = []
        radar_cands = self._agent_score_candidates(
            agent,
            prices_map,
            self.state.get("history", {}),
            self._news_by_symbol(),
            today,
            tracked_only=False,
            blocked_out=shielded_list,
            record_shadows=False,
        )
        radar_top = [
            {
                "symbol": c["symbol"],
                "currency": c["currency"],
                "horizon": c["horizon"],
                "playbook": c["playbook"],
                "score": c["score"],
                "price": c["price"],
                "limit_price": c.get("limit_price"),
                "stage_limit": bool(c.get("stage_limit")),
                "win_prob_pct": c["win_prob_pct"],
                "expected_net_pct": c["expected_net_pct"],
                "ucb_edge_pct": c.get("ucb_edge_pct"),
                "reasons": c["reasons"],
            }
            for c in radar_cands[:5]
        ]
        shielded_top = [
            {
                "symbol": c["symbol"],
                "currency": c["currency"],
                "playbook": c["playbook"],
                "score": c["score"],
                "win_prob_pct": c["win_prob_pct"],
                "expected_net_pct": c["expected_net_pct"],
                "block_reason": c.get("block_reason", "Shielded"),
            }
            for c in shielded_list[:5]
        ]
        regime = _compute_market_regime(prices_map, self.get_cached_intel())

        return {
            "enabled": bool(agent.get("enabled", True)),
            "starting_capital_usd": round(start_usd, 2),
            "zwg_rate": round(rate, 2),
            "cash_usd": round(cash_usd, 2),
            "cash_zwg": round(cash_zwg, 2),
            "total_cash_usd": total_cash_usd,
            "invested_usd": round(invested_usd, 2),
            "equity_usd": equity_usd,
            "net_pnl_usd": net_pnl_usd,
            "net_pnl_pct": net_pnl_pct,
            "total_fees_usd": round(float(stats.get("total_fees_usd") or 0.0), 2),
            "wins": wins,
            "losses": losses,
            "total_closed": total_closed,
            "win_rate_pct": win_rate,
            "positions": pos_list,
            "pending_orders": list(agent.get("pending_orders") or []),
            "regime": regime,
            "trades": list(reversed(agent.get("trades", [])))[:35],
            "equity_history": agent.get("equity_history", [])[-60:],
            "weights": agent.get("weights", _default_paper_weights()),
            "brain": {
                "adaptations_spun": int(brain.get("adaptations_spun") or 0),
                "shadows_total": len(shadows),
                "shadows_resolved": shadows_resolved,
                "playbooks": pb_list,
                "payoffs": brain.get("payoffs") or {"avg_win_pct": 8.5, "avg_loss_pct": 5.0},
                "immunities": imm_list,
                "exit_policy": brain.get("exit_policy") or _default_exit_policy(),
                "logistic_weights": brain.get("logistic_weights") or {},
                "grok": {
                    "enabled": bool((brain.get("grok") or {}).get("enabled")),
                    "status": str((brain.get("grok") or {}).get("status") or "Accumulating History"),
                    "residual_alpha": float((brain.get("grok") or {}).get("residual_alpha") or 0.45),
                    "metrics": dict((brain.get("grok") or {}).get("metrics") or _default_grok_state()["metrics"]),
                },
            },
            "radar": radar_top,
            "shielded": shielded_top,
            "lessons": list(reversed(agent.get("lessons", [])))[:20],
            "cooldowns": active_cooldowns,
            "last_step_date": str(agent.get("last_step_date") or ""),
            "fee_schedules": {"vfex": VFEX_FEE_SCHEDULE, "zse": ZSE_FEE_SCHEDULE},
        }

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
            "held_usd": round(float(synced.get("held_usd") or 0.0), 2),
            "held_zwg": round(float(synced.get("held_zwg") or 0.0), 2),
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
                # VFEX/ZSE Direct /holdings groups securities into asset-class buckets
                if any(k in data for k in ("equity", "reit", "etf", "bond", "other")):
                    bucketed: list[dict[str, Any]] = []
                    for bk in ("equity", "reit", "etf", "bond", "other"):
                        bval = data.get(bk)
                        if isinstance(bval, list):
                            bucketed.extend(r for r in bval if isinstance(r, dict))
                    return bucketed
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
        holdings_ok = False
        last_err: ValueError | None = None
        for ep in ("/holdings", "/voms/holdings", "/voms/portfolios", "/voms/portfolio", "/portfolio"):
            try:
                payload = self._voms_request(f"{base}{ep}", method="GET", token=token)
                rows = self._extract_voms_rows(payload)
                for r in rows:
                    raw_sym = str(r.get("symbol") or r.get("ticker") or r.get("counter") or "").strip().upper()
                    if not raw_sym:
                        continue
                    sym = raw_sym[:-3] if (strip_vx and raw_sym.endswith(".VX")) else raw_sym
                    qty = _safe_float(r.get("volume") or r.get("quantity") or r.get("shares") or r.get("totalUnits") or r.get("units") or r.get("balance") or r.get("availableQuantity"))
                    avg = _safe_float(r.get("averagePrice") or r.get("avgCost") or r.get("averageCost") or r.get("costPrice") or r.get("openingPrice") or r.get("closingPrice") or r.get("currentPrice")) or self.get_price(sym) or 0.0
                    exch = str(r.get("exchange") or "").upper()
                    cur = str(r.get("currency") or ("ZWG" if exch == "ZSE" else cur_default)).upper()
                    if cur not in ("USD", "ZWG"):
                        cur = cur_default
                    if qty and qty > 0:
                        holdings.append({"symbol": sym, "shares": round(qty, 6), "avg_cost": round(avg, 4), "currency": cur})
                        if sym not in self.state["watchlist"]:
                            self.state["watchlist"].append(sym)
                holdings_ok = True
                break
            except ValueError as exc:
                last_err = exc
                if "HTTP 401" in str(exc):
                    raise
                continue

        if not holdings_ok and last_err is not None:
            raise last_err

        cash_usd = 0.0
        cash_zwg = 0.0
        held_usd = 0.0
        held_zwg = 0.0
        for wep in ("/wallet/balance", "/voms/wallet/balance", "/wallets/balance", "/voms/wallet", "/voms/wallets", "/wallet", "/wallets"):
            try:
                wpayload = self._voms_request(f"{base}{wep}", method="GET", token=token)
                wdata = wpayload.get("data", wpayload) if isinstance(wpayload, dict) else wpayload
                wrows = [wdata] if isinstance(wdata, dict) and any(k in wdata for k in ("balance", "availableBalance", "cashBalance", "totalValuation")) else self._extract_voms_rows(wpayload)
                for w in wrows:
                    bal = _safe_float(w.get("availableBalance") or w.get("cashBalance") or w.get("balance") or w.get("amount"))
                    if bal is None:
                        continue
                    held = _safe_float(w.get("heldFundsBalance")) or 0.0
                    wcur = str(w.get("currency") or w.get("currencyCode") or cur_default).upper()
                    if wcur in ("ZWG", "ZWL", "ZIG"):
                        cash_zwg += bal
                        held_zwg += held
                    else:
                        cash_usd += bal
                        held_usd += held
                if wrows:
                    break
            except ValueError:
                continue

        voms_txns: list[dict[str, Any]] = []
        for tx_ep in ("/transactions", "/voms/transactions"):
            try:
                txpay = self._voms_request(f"{base}{tx_ep}", method="GET", token=token)
                tdata = txpay.get("data", txpay) if isinstance(txpay, dict) else txpay
                txrows = tdata.get("transactions") if isinstance(tdata, dict) and isinstance(tdata.get("transactions"), list) else self._extract_voms_rows(txpay)
                if txrows:
                    for t in txrows[:25]:
                        if not isinstance(t, dict):
                            continue
                        slug = str(t.get("transactionTypeSlug") or t.get("type") or "TRANSACTION").replace("_", " ").upper()
                        st_txt = str(t.get("status") or "").upper()
                        amt = float(_safe_float(t.get("amount")) or 0.0)
                        gw = str(t.get("paymentGateway") or "").strip()
                        ref = str(t.get("refNumber") or t.get("transactionId") or "")
                        voms_txns.append({
                            "id": ref or str(len(voms_txns) + 1),
                            "date": str(t.get("createdAt") or t.get("date") or "")[:10],
                            "type": slug,
                            "symbol": "",
                            "shares": 0.0,
                            "price": 0.0,
                            "amount": round(amt, 2),
                            "currency": str(t.get("currency") or cur_default).upper(),
                            "description": f"{title}: {slug}" + (f" via {gw}" if gw else "") + (f" [{st_txt}]" if st_txt else ""),
                            "provider": title,
                        })
                    break
            except ValueError:
                continue

        now_iso = datetime.now(timezone.utc).isoformat()
        self.state.setdefault("synced_accounts", {})[provider] = {
            "holdings": holdings,
            "cash_usd": round(cash_usd, 2),
            "cash_zwg": round(cash_zwg, 2),
            "held_usd": round(held_usd, 2),
            "held_zwg": round(held_zwg, 2),
            "transactions": voms_txns,
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
            "held_usd": round(held_usd, 2),
            "held_zwg": round(held_zwg, 2),
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

    @staticmethod
    def _extract_ctrade_cash(payload: Any) -> float | None:
        """Extract a numeric cash balance from C-TRADE USD forex or ZWG cash payloads."""
        if isinstance(payload, (int, float)):
            return float(payload)
        if isinstance(payload, str):
            return _safe_float(payload)
        if isinstance(payload, list):
            for item in payload:
                val = VFEXStore._extract_ctrade_cash(item)
                if val is not None:
                    return val
            return None
        if isinstance(payload, dict):
            for k in (
                "actualCashBal", "ActualCashBal", "cashBal", "CashBal",
                "availableBalance", "cashBalance", "balance", "currentBalance",
                "forexBalance", "usdBalance", "amount", "Amount", "CashBalance",
            ):
                if payload.get(k) is not None:
                    val = _safe_float(payload.get(k))
                    if val is not None:
                        return val
            for k in ("data", "result", "cash"):
                if payload.get(k) is not None:
                    val = VFEXStore._extract_ctrade_cash(payload.get(k))
                    if val is not None:
                        return val
        return None

    def ctrade_login_and_sync(
        self,
        email: str | None = None,
        password: str | None = None,
        sync_portfolio: bool = True,
        base_url: str = CTRADE_BASE_URL,
    ) -> dict[str, Any]:
        """Authenticate against C-TRADE and sync multi-asset holdings, cash balances, orders & transactions."""
        saved = self._load_ctrade_creds()
        em = (email or saved.get("email") or "").strip()
        pw = password if password is not None else saved.get("password")
        if not em or not pw:
            raise ValueError("C-TRADE email and password required.")

        jar = http.cookiejar.CookieJar()
        opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))

        def _req_json(path_or_url: str, method: str = "GET", body: dict[str, Any] | None = None) -> Any:
            full_u = path_or_url if path_or_url.startswith("http") else f"{base_url}{path_or_url}"
            hdrs = {"Accept": "application/json", "User-Agent": "omarchy-VFEX-Direct/0.1"}
            raw_data = None
            if body is not None:
                hdrs["Content-Type"] = "application/json"
                raw_data = json.dumps(body).encode("utf-8")
            req = urllib.request.Request(full_u, data=raw_data, headers=hdrs, method=method)
            with opener.open(req, timeout=15) as hresp:
                return json.loads(hresp.read().decode("utf-8", "ignore"))

        try:
            auth_payload = _req_json("/api/auth/login", method="POST", body={"Email": em, "Password": pw})
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
        seen_holdings: set[tuple[str, str]] = set()
        cash_usd = 0.0
        cash_zwg = 0.0
        portal_orders: list[dict[str, Any]] = []
        portal_txns: list[dict[str, Any]] = []

        if sync_portfolio and cds:
            for endpoint, default_cur, strip_vx in (
                ("PortfolioByTypeVFEX", "USD", True),
                ("PortfolioByType", "ZWG", False),
            ):
                for asset_type in ("equity", "reits", "etf"):
                    q = urllib.parse.urlencode({"cdsNumber": cds, "type": asset_type})
                    try:
                        pdata = _req_json(f"/api/mobile-proxy/{endpoint}?{q}")
                    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, ValueError, urllib.error.HTTPError):
                        continue
                    rows = pdata if isinstance(pdata, list) else (pdata.get("data") if isinstance(pdata, dict) else [])
                    if isinstance(rows, list):
                        for r in rows:
                            if not isinstance(r, dict):
                                continue
                            raw_sym = str(r.get("counter") or r.get("symbol") or r.get("Ticker") or "").strip().upper()
                            sym = raw_sym[:-3] if (strip_vx and raw_sym.endswith(".VX")) else raw_sym
                            qty = _safe_float(r.get("total_units") or r.get("shares") or r.get("Quantity") or r.get("balance"))
                            avg = _safe_float(r.get("average_price") or r.get("avg_price") or r.get("Current_price")) or self.get_price(sym) or 0.0
                            if sym and qty and qty > 0 and (sym, default_cur) not in seen_holdings:
                                seen_holdings.add((sym, default_cur))
                                imported_holdings.append({
                                    "symbol": sym,
                                    "shares": round(qty, 6),
                                    "avg_cost": round(avg, 4),
                                    "currency": default_cur,
                                    "asset_type": asset_type.upper(),
                                })
                                if sym not in self.state["watchlist"]:
                                    self.state["watchlist"].append(sym)

            try:
                usd_bal_raw = _req_json(f"/api/web-proxy/online.ctrade_php/getCashBalanceForex.php?{urllib.parse.urlencode({'cdsNumber': cds})}")
                u_val = self._extract_ctrade_cash(usd_bal_raw)
                if u_val is not None:
                    cash_usd = round(max(0.0, u_val), 2)
            except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, ValueError, urllib.error.HTTPError):
                pass

            try:
                zwg_bal_raw = _req_json("/api/trading-proxy/account/cash", method="POST", body={"cdsNumber": cds})
                z_val = self._extract_ctrade_cash(zwg_bal_raw)
                if z_val is not None:
                    cash_zwg = round(max(0.0, z_val), 2)
            except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, ValueError, urllib.error.HTTPError):
                try:
                    mob_bal_raw = _req_json(f"/api/mobile-proxy/getCashBalance?{urllib.parse.urlencode({'cdsNumber': cds})}")
                    z_val = self._extract_ctrade_cash(mob_bal_raw)
                    if z_val is not None:
                        cash_zwg = round(max(0.0, z_val), 2)
                except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, ValueError, urllib.error.HTTPError):
                    pass

            for ord_method, ord_ep, ord_body in (
                ("POST", "/api/trading-proxy/account/orders", {"cdsNumber": cds}),
                ("GET", f"/api/mobile-proxy/orders?{urllib.parse.urlencode({'cdsNumber': cds})}", None),
                ("GET", f"/api/trading-proxy/orders?{urllib.parse.urlencode({'cdsNumber': cds})}", None),
            ):
                try:
                    opay = _req_json(ord_ep, method=ord_method, body=ord_body)
                    orows = self._extract_voms_rows(opay) if isinstance(opay, dict) else (opay if isinstance(opay, list) else [])
                    if orows:
                        for o in orows[:25]:
                            if not isinstance(o, dict):
                                continue
                            raw_s = str(o.get("symbol") or o.get("counter") or o.get("Ticker") or o.get("company") or "").strip().upper()
                            sym = raw_s[:-3] if raw_s.endswith(".VX") else raw_s
                            if not sym:
                                continue
                            cur = infer_currency(sym, {"currency": str(o.get("currency") or "").upper()})
                            portal_orders.append({
                                "id": str(o.get("id") or o.get("orderId") or o.get("order_id") or ""),
                                "symbol": sym,
                                "side": str(o.get("side") or o.get("orderType") or o.get("type") or "ORDER").upper(),
                                "shares": float(_safe_float(o.get("quantity") or o.get("shares") or o.get("volume") or o.get("units")) or 0.0),
                                "price": float(_safe_float(o.get("price") or o.get("limitPrice") or o.get("orderPrice")) or 0.0),
                                "status": str(o.get("status") or o.get("orderStatus") or "ACTIVE"),
                                "date": str(o.get("createdAt") or o.get("date") or o.get("orderDate") or "")[:10],
                                "currency": cur,
                            })
                        break
                except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, ValueError, urllib.error.HTTPError):
                    continue

            seen_tx_keys: set[str] = set()
            for tx_method, tx_ep, tx_body, def_cur in (
                ("POST", "/api/trading-proxy/cash/usdTransactions", {"cdsNumber": cds}, "USD"),
                ("POST", "/api/trading-proxy/cash/transactions", {"cdsNumber": cds}, "ZWG"),
                ("GET", f"/api/trading-proxy/transactions?{urllib.parse.urlencode({'cdsNumber': cds})}", None, "USD"),
            ):
                try:
                    tpay = _req_json(tx_ep, method=tx_method, body=tx_body)
                    trows = self._extract_voms_rows(tpay) if isinstance(tpay, dict) else (tpay if isinstance(tpay, list) else [])
                    for tx in trows[:40]:
                        if not isinstance(tx, dict):
                            continue
                        raw_s = str(tx.get("symbol") or tx.get("counter") or tx.get("Ticker") or tx.get("security") or "").strip().upper()
                        sym = raw_s[:-3] if raw_s.endswith(".VX") else raw_s
                        dt_s = str(tx.get("date") or tx.get("day") or tx.get("transactionDate") or tx.get("createdAt") or tx.get("Date") or "")[:10]
                        tx_type = str(tx.get("transType") or tx.get("type") or tx.get("transactionType") or tx.get("side") or tx.get("action") or "TRANSACTION").upper()
                        sh = float(_safe_float(tx.get("shares") or tx.get("quantity") or tx.get("units") or tx.get("volume")) or 0.0)
                        px = float(_safe_float(tx.get("price") or tx.get("unitPrice")) or 0.0)
                        amt = float(_safe_float(tx.get("amount") or tx.get("netAmount") or tx.get("total") or tx.get("value")) or (sh * px))
                        cur = str(tx.get("currency") or ("USD" if raw_s.endswith(".VX") else (infer_currency(sym) if sym else def_cur))).upper()
                        if cur not in ("USD", "ZWG"):
                            cur = def_cur
                        desc = str(tx.get("description") or tx.get("narration") or tx.get("remarks") or tx_type).strip()
                        key = f"{dt_s}|{tx_type}|{sym}|{sh:.4f}|{amt:.2f}|{cur}"
                        if key in seen_tx_keys:
                            continue
                        seen_tx_keys.add(key)
                        portal_txns.append({
                            "id": str(tx.get("id") or tx.get("reference") or key),
                            "date": dt_s,
                            "type": tx_type,
                            "symbol": sym,
                            "shares": round(sh, 6),
                            "price": round(px, 4),
                            "amount": round(amt, 2),
                            "currency": cur,
                            "description": desc,
                            "provider": "C-TRADE",
                        })
                except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, ValueError, urllib.error.HTTPError):
                    continue

        now_iso = datetime.now(timezone.utc).isoformat()
        self.state["ctrade_account"] = {
            "email": em,
            "cds_number": cds,
            "last_sync": now_iso,
            "holdings_count": len(imported_holdings),
            "cash_usd": cash_usd,
            "cash_zwg": cash_zwg,
            "orders_count": len(portal_orders),
            "transactions_count": len(portal_txns),
        }
        self.state.setdefault("synced_accounts", {})["ctrade"] = {
            "holdings": imported_holdings,
            "cash_usd": cash_usd,
            "cash_zwg": cash_zwg,
            "orders": portal_orders,
            "transactions": portal_txns,
            "last_sync": now_iso,
        }
        self.save()
        cash_msg = ""
        if cash_usd > 0 or cash_zwg > 0:
            parts = []
            if cash_usd > 0:
                parts.append(f"${cash_usd:.2f} USD")
            if cash_zwg > 0:
                parts.append(f"ZiG {cash_zwg:.2f}")
            cash_msg = f", cash {' + '.join(parts)}"
        return {
            "ok": True,
            "cds_number": cds,
            "email_masked": self._mask_email(em),
            "holdings_synced": len(imported_holdings),
            "cash_usd": cash_usd,
            "cash_zwg": cash_zwg,
            "orders_count": len(portal_orders),
            "transactions_count": len(portal_txns),
            "message": f"Connected C-TRADE ({cds or self._mask_email(em)}); synced {len(imported_holdings)} holding(s){cash_msg}.",
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


def get_market_countdown(now: datetime | None = None) -> str:
    """Return human countdown to market close or next 09:00 CAT session open."""
    dt = (now or datetime.now(timezone.utc)).astimezone(CAT_TZ)
    if dt.weekday() < 5 and 9 <= dt.hour < 13:
        close_dt = dt.replace(hour=13, minute=0, second=0, microsecond=0)
        mins = max(1, int((close_dt - dt).total_seconds() // 60))
        return f"Closes in {mins // 60}h {mins % 60:02d}m"
    if dt.weekday() < 5 and dt.hour < 9:
        open_dt = dt.replace(hour=9, minute=0, second=0, microsecond=0)
        mins = max(1, int((open_dt - dt).total_seconds() // 60))
        return f"Opens in {mins // 60}h {mins % 60:02d}m"
    next_day = dt.date() + timedelta(days=1)
    while next_day.weekday() >= 5:
        next_day += timedelta(days=1)
    return f"Opens {next_day.strftime('%a')} 09:00 CAT"


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


def _ingest_price_sheet_payload(
    store: VFEXStore,
    payload: Any,
    currency: str = "USD",
    scale_div: float = 1.0,
    strip_vx: bool = True,
    source: str = "vfex-direct",
    tracked_zse: set[str] | None = None,
) -> int:
    data = payload.get("data") if isinstance(payload, dict) else None
    if not isinstance(data, dict):
        return 0
    updated = 0
    for grp_name, group_items in data.items():
        if not isinstance(group_items, list):
            continue
        sec_type_default = str(grp_name or "EQUITY").strip().upper()
        for item in group_items:
            if not isinstance(item, dict):
                continue
            raw_sym = str(item.get("symbol") or "").strip().upper()
            sym = raw_sym[:-3] if (strip_vx and raw_sym.endswith(".VX")) else raw_sym
            raw_price = item.get("closingPrice")
            if raw_price is None:
                raw_price = item.get("openingPrice")
            if sym and raw_price is not None and float(raw_price) > 0:
                p_val = float(raw_price) / scale_div
                open_p = _safe_float(item.get("openingPrice"))
                chg_p = _safe_float(item.get("percentagePriceChange"))
                stats_d = item.get("statsDate")
                up_lim = _safe_float(item.get("upperPriceRange"))
                lo_lim = _safe_float(item.get("lowerPriceRange"))
                sec_t = str(item.get("securitySubType") or sec_type_default).strip().upper()
                isin_v = str(item.get("isin") or "").strip().upper() or None
                track_h = (currency == "USD") or (tracked_zse is not None and sym in tracked_zse)
                store.set_price(
                    sym,
                    p_val,
                    source=source,
                    open_price=(open_p / scale_div) if open_p is not None else None,
                    change_pct=chg_p,
                    date=str(stats_d) if stats_d else None,
                    currency=currency,
                    company_name=item.get("symbolName"),
                    track_history=track_h,
                    save=False,
                    upper_limit=(up_lim / scale_div) if up_lim is not None else None,
                    lower_limit=(lo_lim / scale_div) if lo_lim is not None else None,
                    isin=isin_v,
                    security_type=sec_t,
                )
                updated += 1
    return updated


def _ingest_vfex_direct_payload(store: VFEXStore, payload: Any) -> int:
    return _ingest_price_sheet_payload(store, payload, currency="USD", scale_div=1.0, strip_vx=True, source="vfex-direct")


def _ingest_zse_direct_payload(store: VFEXStore, payload: Any, tracked_zse: set[str] | None = None) -> int:
    return _ingest_price_sheet_payload(
        store, payload, currency="ZWG", scale_div=100.0, strip_vx=False, source="zse-direct", tracked_zse=tracked_zse
    )


def _ingest_ctrade_rows(
    store: VFEXStore,
    rows: Any,
    currency: str,
    strip_vx: bool,
    today: str,
    tracked_zse: set[str],
    security_type: str | None = None,
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
        isin_v = str(item.get("ISIN") or "").strip().upper() or None
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
                isin=isin_v,
                security_type=security_type,
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
                isin=isin_v,
                security_type=security_type,
            )
            updated += 1
    return updated


def _ingest_finsec_rows(store: VFEXStore, rows: Any, today: str, tracked_zse: set[str]) -> int:
    """Ingest FINSEC over-the-counter quotes & depth from C-TRADE marketwatchbidoffer feed."""
    if not isinstance(rows, list):
        return 0
    updated = 0
    for item in rows:
        if not isinstance(item, dict):
            continue
        sym = str(item.get("market_company") or "").strip().upper()
        if not sym:
            continue
        lp = _safe_float(item.get("market_lp") or item.get("market_vwap"))
        if lp is None or lp <= 0:
            continue
        op = _safe_float(item.get("market_open"))
        chg_p = _safe_float(item.get("market_per_change"))
        bid = _safe_float(item.get("market_bp"))
        ask = _safe_float(item.get("market_ap"))
        bid_vol = _safe_int(item.get("market_bbv"))
        ask_vol = _safe_int(item.get("market_va"))
        cname = str(item.get("FullCompanyName") or "").strip() or None
        sec_t = str(item.get("Category") or "FINSEC").strip().upper()
        store.set_price(
            sym,
            lp,
            source="c-trade-finsec",
            open_price=op if (op is not None and op > 0) else None,
            change_pct=chg_p,
            date=today,
            best_bid=bid,
            best_ask=ask,
            bid_volume=bid_vol,
            ask_volume=ask_vol,
            currency="ZWG",
            company_name=cname,
            track_history=(sym in tracked_zse),
            save=False,
            security_type=sec_t,
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
    zse_direct_url: str | None = ZSE_DIRECT_URL,
    ctrade_etf_url: str | None = CTRADE_ETF_URL,
    ctrade_finsec_url: str | None = CTRADE_FINSEC_URL,
) -> dict[str, Any]:
    """Fetch VFEX, ZSE Direct & C-TRADE (Equities, ETFs, REITs, FINSEC) prices, circuit breakers & depth."""
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

    if not custom_override and zse_direct_url:
        try:
            st, zse_sh = _fetch_json(zse_direct_url)
            statuses.append(st)
            updated += _ingest_zse_direct_payload(store, zse_sh, tracked_zse=tracked_zse)
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

    if not custom_override and ctrade_etf_url:
        try:
            st, ct_etf = _fetch_json(ctrade_etf_url)
            statuses.append(st)
            updated += _ingest_ctrade_rows(store, ct_etf, "ZWG", False, today, tracked_zse, security_type="ETF")
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, ValueError) as exc:
            errors.append(str(exc))

    if not custom_override and ctrade_finsec_url:
        try:
            st, ct_fin = _fetch_json(ctrade_finsec_url)
            statuses.append(st)
            updated += _ingest_finsec_rows(store, ct_fin, today, tracked_zse)
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, ValueError) as exc:
            errors.append(str(exc))

    if not statuses:
        reason = errors[0] if errors else "network error"
        return {"ok": False, "cached": True, "status": None, "message": f"Could not reach VFEX ({reason}). Using cached prices."}

    # Backfill real 30-day OHLC candles for dual-listed CMCL from Yahoo Finance when history is short
    if not custom_override and "CMCL" in store.state.get("prices", {}) and len(store.state.get("history", {}).get("CMCL", [])) < 15:
        _backfill_cmcl_yahoo_history(store)

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


def _backfill_cmcl_yahoo_history(store: VFEXStore) -> int:
    """Fetch real 1-month daily OHLC history for dual-listed CMCL (NYSE American/VFEX) from Yahoo Finance."""
    try:
        raw = _fetch_text("https://query1.finance.yahoo.com/v8/finance/chart/CMCL?range=1mo&interval=1d", timeout=5)
        payload = json.loads(raw)
        res = (payload.get("chart") or {}).get("result") or []
        if not res:
            return 0
        ts_list = res[0].get("timestamp") or []
        quote = ((res[0].get("indicators") or {}).get("quote") or [{}])[0]
        opens = quote.get("open") or []
        highs = quote.get("high") or []
        lows = quote.get("low") or []
        closes = quote.get("close") or []
        hist = list(store.state.get("history", {}).get("CMCL", []))
        added = 0
        for idx, ts in enumerate(ts_list):
            if idx >= len(closes) or closes[idx] is None or float(closes[idx]) <= 0:
                continue
            dt_str = datetime.fromtimestamp(int(ts), timezone.utc).date().isoformat()
            cl = round(float(closes[idx]), 4)
            op = round(float(opens[idx]), 4) if idx < len(opens) and opens[idx] else cl
            hi = round(float(highs[idx]), 4) if idx < len(highs) and highs[idx] else max(op, cl)
            lo = round(float(lows[idx]), 4) if idx < len(lows) and lows[idx] else min(op, cl)
            hist.append({"date": dt_str, "open": op, "high": hi, "low": lo, "close": cl, "price": cl})
            added += 1
        if added > 0:
            store.state.setdefault("history", {})["CMCL"] = _dedupe_sorted_history(hist)[-30:]
        return added
    except Exception:
        return 0


def _fetch_text(target_url: str, timeout: int = 7) -> str:
    """Fetch raw UTF-8 text from an HTTP/HTTPS endpoint."""
    req = urllib.request.Request(
        target_url,
        headers={
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36",
            "Accept": "application/json, application/rss+xml, application/xml, text/xml;q=0.9, */*;q=0.8",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", errors="replace")


def _parse_dtr_exchange_payload(
    payload: Any,
    exchange: str,
    alias_index: dict[str, list[str]],
    stored_syms: set[str],
) -> tuple[dict[str, Any], dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    """Parse official VFEX/ZSE Daily Trade Report (DTR) into regime summary, traded volumes, and blue-chips."""
    rows = payload.get("data", payload) if isinstance(payload, dict) else payload
    if not isinstance(rows, list) or not rows:
        return {}, {}, {}

    exch = exchange.upper()
    best_summary: dict[str, Any] = {}
    counters: dict[str, dict[str, Any]] = {}
    blue_chips: dict[str, dict[str, Any]] = {}

    for row in rows:
        if not isinstance(row, dict):
            continue
        raw_c = row.get("content")
        try:
            content = json.loads(raw_c) if isinstance(raw_c, str) else raw_c
        except json.JSONDecodeError:
            continue
        if not isinstance(content, dict):
            continue

        vt = content.get("volumeAndTurnover") or {}
        idx = content.get("indices") or {}
        idx_name = str(idx.get("index") or f"{exch} Index")
        f_buy = float((vt.get("foreignPurchases") or {}).get("value") or 0.0)
        f_sell = float((vt.get("foreignSales") or {}).get("value") or 0.0)
        stats_arr = row.get("statsDate")
        stats_str = (
            f"{int(stats_arr[0]):04d}-{int(stats_arr[1]):02d}-{int(stats_arr[2]):02d}"
            if isinstance(stats_arr, list) and len(stats_arr) >= 3
            else ""
        )
        mvs = content.get("moversAndShakers") or {}
        cand_sum = {
            "exchange": exch,
            "index_name": idx_name,
            "index_value": round(float(idx.get("closingPrice") or 0.0), 2),
            "index_chg_pct": round(float(idx.get("changePercentage") or 0.0), 2),
            "turnover": round(float(vt.get("totalMarketTurnover") or 0.0), 2),
            "volume_shares": round(float(vt.get("totalMarketVolumeShares") or 0.0), 0),
            "num_trades": int(vt.get("totalNumberOfTrades") or 0),
            "foreign_buy": round(f_buy, 2),
            "foreign_sell": round(f_sell, 2),
            "foreign_net": round(f_buy - f_sell, 2),
            "total_market_cap": round(float(content.get("totalMarketCapitalisation") or 0.0), 2),
            "movers": list(mvs.get("movers") or [])[:5],
            "shakers": list(mvs.get("shakers") or [])[:5],
            "stats_date": stats_str,
        }
        if not best_summary or "ALL" in idx_name.upper():
            best_summary = cand_sum

        for vrow in (content.get("topFiveCounters") or {}).get("volumesTraded") or []:
            if not isinstance(vrow, dict):
                continue
            cname = str(vrow.get("counter") or "").strip()
            if not cname:
                continue
            matched = _match_news_symbols(f"{cname} {exch}", alias_index, stored_syms)
            for sym in matched:
                if (exch == "ZSE") != sym.endswith(".ZW"):
                    continue
                counters[sym] = {
                    "volumes": round(float(vrow.get("volumes") or 0.0), 0),
                    "value_traded": round(float(vrow.get("valueTraded") or 0.0), 2),
                    "counter_name": cname,
                }

        for rank_i, mc in enumerate((content.get("topTenMarketCap") or []), start=1):
            if not isinstance(mc, dict):
                continue
            raw_c_sym = str(mc.get("counter") or "").strip().upper()
            if not raw_c_sym:
                continue
            sym = raw_c_sym[:-3] if raw_c_sym.endswith(".VX") else raw_c_sym
            if sym not in stored_syms and sym == "INN" and "INSC" in stored_syms:
                sym = "INSC"
            blue_chips[sym] = {
                "rank": rank_i,
                "pct": round(float(mc.get("percentage") or 0.0), 2),
                "market_cap": round(float(mc.get("value") or 0.0), 2),
            }

    return best_summary, counters, blue_chips


def _parse_dtr_foreign_flows(payload: Any, exchange: str, stored_syms: set[str]) -> dict[str, dict[str, Any]]:
    """Extract per-counter institutional foreign buys and sells from VFEX/ZSE Daily Trade Report."""
    rows = payload.get("data", payload) if isinstance(payload, dict) else payload
    if not isinstance(rows, list):
        return {}
    exch = exchange.upper()
    cur_code = "ZWG" if exch == "ZSE" else "USD"
    flows: dict[str, dict[str, Any]] = {}

    def _norm_sym(raw_c: str) -> str:
        s = raw_c.strip().upper()
        if not s or "NO_FOREIGN" in s:
            return ""
        s = s[:-3] if s.endswith(".VX") else s
        if s not in stored_syms and s == "INN" and "INSC" in stored_syms:
            return "INSC"
        return s

    for row in rows:
        if not isinstance(row, dict):
            continue
        raw_c = row.get("content")
        try:
            content = json.loads(raw_c) if isinstance(raw_c, str) else raw_c
        except json.JSONDecodeError:
            continue
        if not isinstance(content, dict):
            continue
        top5 = content.get("topFiveCounters") or {}
        for side_key, val_field, vol_field in (("foreignPurchases", "buy_val", "buy_vol"), ("foreignSales", "sell_val", "sell_vol")):
            for item in top5.get(side_key) or []:
                if not isinstance(item, dict):
                    continue
                sym = _norm_sym(str(item.get("counter") or ""))
                if not sym:
                    continue
                rec = flows.setdefault(sym, {"symbol": sym, "currency": cur_code, "buy_val": 0.0, "sell_val": 0.0, "buy_vol": 0.0, "sell_vol": 0.0, "net_val": 0.0})
                rec[val_field] = round(rec[val_field] + float(item.get("value") or 0.0), 2)
                rec[vol_field] = round(rec[vol_field] + float(item.get("volume") or 0.0), 0)
                rec["net_val"] = round(rec["buy_val"] - rec["sell_val"], 2)
    return flows


def fetch_exchange_intelligence(
    store: VFEXStore,
    force: bool = False,
    ttl_seconds: int = INTEL_CACHE_TTL_SECONDS,
    fetcher: Any = None,
) -> dict[str, Any]:
    """Fetch VFEX/ZSE DTR turnover, foreign flows, indices, unit trusts & top market-cap data on a 5m TTL."""
    now = datetime.now(timezone.utc)
    cached = store.state.get("market_intel")
    if not force and isinstance(cached, dict) and cached.get("fetched_at"):
        dt = _parse_news_timestamp(cached.get("fetched_at"))
        if dt is not None and (now - dt).total_seconds() < ttl_seconds:
            return cached

    text_getter = fetcher or _fetch_text
    endpoints = [
        ("vfex", VFEX_DTR_URL),
        ("zse", ZSE_DTR_URL),
        ("indices", CTRADE_INDICES_URL),
        ("unit_trusts", CTRADE_UNIT_TRUSTS_URL),
    ]
    alias_idx = _build_symbol_alias_index(store)
    stored_syms = set(store.state.get("prices", {}).keys()) | set(KNOWN_VFEX_SYMBOLS.keys()) | set(store.state.get("watchlist", [])) | set(store.state.get("portfolio", {}).keys())

    def _pull(ex_url: tuple[str, str]) -> tuple[str, str, str]:
        ex, u = ex_url
        try:
            return ex, text_getter(u), ""
        except Exception as exc:
            return ex, "", str(exc)

    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(_pull, endpoints))

    out: dict[str, Any] = {
        "fetched_at": now.isoformat(),
        "vfex": dict(cached.get("vfex", {})) if isinstance(cached, dict) else {},
        "zse": dict(cached.get("zse", {})) if isinstance(cached, dict) else {},
        "counters": {},
        "blue_chips": {},
        "foreign_counters": {},
        "indices": list(cached.get("indices", [])) if isinstance(cached, dict) else [],
        "unit_trusts": list(cached.get("unit_trusts", [])) if isinstance(cached, dict) else [],
    }
    any_ok = False
    for ex, raw_txt, err in results:
        if err or not raw_txt:
            continue
        try:
            payload = json.loads(raw_txt)
        except json.JSONDecodeError:
            continue
        if ex == "indices" and isinstance(payload, list):
            out["indices"] = [
                {
                    "name": str(r.get("Indexcode") or r.get("IndexSymbol") or "").strip(),
                    "symbol": str(r.get("IndexSymbol") or "").strip(),
                    "level": float(_safe_float(r.get("IndexLevel")) or 0.0),
                    "change": float(_safe_float(r.get("IndexChange")) or 0.0),
                    "high": float(_safe_float(r.get("High")) or 0.0),
                    "low": float(_safe_float(r.get("Low")) or 0.0),
                    "one_week": float(_safe_float(r.get("one_week")) or 0.0),
                    "one_month": float(_safe_float(r.get("one_month")) or 0.0),
                    "one_year": float(_safe_float(r.get("one_year")) or 0.0),
                    "high_52w": float(_safe_float(r.get("fifty_two_high")) or 0.0),
                }
                for r in payload
                if isinstance(r, dict) and r.get("Indexcode")
            ]
            any_ok = any_ok or bool(out["indices"])
            continue
        if ex == "unit_trusts" and isinstance(payload, list):
            out["unit_trusts"] = [
                {
                    "symbol": str(r.get("company") or "").strip(),
                    "name": str(r.get("fullName") or "").strip(),
                    "currency": str(r.get("currency") or "USD").upper(),
                    "price": float(_safe_float(r.get("initialPrice")) or 0.0),
                    "status": str(r.get("status") or ""),
                    "type": str(r.get("type") or r.get("securityType") or ""),
                }
                for r in payload
                if isinstance(r, dict) and r.get("company")
            ]
            any_ok = any_ok or bool(out["unit_trusts"])
            continue

        summary_ex, c_map, bc_map = _parse_dtr_exchange_payload(payload, ex.upper(), alias_idx, stored_syms)
        fc_map = _parse_dtr_foreign_flows(payload, ex.upper(), stored_syms)
        if summary_ex:
            out[ex] = summary_ex
            any_ok = True
        out["counters"].update(c_map)
        out["blue_chips"].update(bc_map)
        out["foreign_counters"].update(fc_map)

    if any_ok or out["counters"] or out["blue_chips"] or out["foreign_counters"] or out["indices"]:
        store.state["market_intel"] = out
        store.save()
        return out
    return cached if isinstance(cached, dict) else out


def _build_tracked_rss_query(store: VFEXStore) -> str:
    """Build a safe Google News RSS query covering user's tracked holdings/watchlist."""
    tracked = sorted(store.get_tracked_symbols())
    alias_idx = _build_symbol_alias_index(store)
    terms: list[str] = []
    for sym in tracked[:8]:
        aliases = alias_idx.get(sym, [])
        # Prefer multi-word or long unique company names so we never query ambiguous bare words
        chosen = ""
        for a in aliases:
            if len(a) >= 6:
                chosen = a
                break
        if chosen:
            terms.append(f'"{chosen}"' if " " in chosen else chosen)
    for base_term in ('"Econet InfraCo"', '"Innscor"', '"Simbisa"', '"Caledonia Mining"'):
        if base_term not in terms and len(terms) < 8:
            terms.append(base_term)
    if not terms:
        return ""
    return f"Zimbabwe ({' OR '.join(terms)}) when:{NEWS_MAX_AGE_DAYS}d"


def fetch_vfex_news(
    store: VFEXStore,
    force: bool = False,
    ttl_seconds: int = NEWS_CACHE_TTL_SECONDS,
    fetcher: Any = None,
) -> dict[str, Any]:
    """Fetch & classify VFEX/ZSE official notices + Google News ZW RSS on a 15-minute TTL cache."""
    now = datetime.now(timezone.utc)
    cache = store.state.get("news_cache", {})
    if not force and isinstance(cache, dict) and cache.get("fetched_at"):
        fetched_dt = _parse_news_timestamp(cache.get("fetched_at"))
        if fetched_dt is not None and (now - fetched_dt).total_seconds() < ttl_seconds:
            return {
                "ok": True,
                "cached": True,
                "fetched_at": cache.get("fetched_at"),
                "items": store.get_cached_news(),
                "error": str(cache.get("error") or ""),
            }

    text_getter = fetcher or _fetch_text
    rss_general = GOOGLE_NEWS_RSS_URL.format(
        q=urllib.parse.quote(f'("Victoria Falls Stock Exchange" OR "Zimbabwe Stock Exchange" OR "VFEX") Zimbabwe when:{NEWS_MAX_AGE_DAYS}d')
    )
    tracked_q = _build_tracked_rss_query(store)
    endpoints: list[tuple[str, str]] = [
        ("vfex_ann", VFEX_ANNOUNCEMENTS_URL),
        ("vfex_issuer", VFEX_ISSUER_DOCS_URL),
        ("zse_ann", ZSE_ANNOUNCEMENTS_URL),
        ("zse_issuer", ZSE_ISSUER_DOCS_URL),
        ("ctrade_notices", CTRADE_NOTICES_URL),
        ("rss_mkt", rss_general),
    ]
    if tracked_q:
        endpoints.append(("rss_tracked", GOOGLE_NEWS_RSS_URL.format(q=urllib.parse.quote(tracked_q))))

    raw_records: list[dict[str, Any]] = []
    errors: list[str] = []

    def _pull(tag_url: tuple[str, str]) -> tuple[str, str, str]:
        tag, u = tag_url
        try:
            return tag, text_getter(u), ""
        except Exception as exc:
            return tag, "", str(exc)

    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
        results = list(pool.map(_pull, endpoints))

    for tag, payload, err in results:
        if err or not payload:
            if err:
                errors.append(f"{tag}: {err}")
            continue
        if tag.startswith("rss_"):
            raw_records.extend(_parse_google_news_rss(payload))
        elif tag == "ctrade_notices":
            try:
                parsed_cn = json.loads(payload)
            except json.JSONDecodeError:
                continue
            for n in (parsed_cn.get("notices") or []) if isinstance(parsed_cn, dict) else []:
                if isinstance(n, dict) and (n.get("title") or n.get("message") or n.get("notice")):
                    raw_records.append({
                        "title": str(n.get("title") or n.get("notice") or n.get("message") or "").strip(),
                        "url": str(n.get("url") or f"{CTRADE_BASE_URL}/"),
                        "source": "C-TRADE Official",
                        "pub_raw": str(n.get("created_at") or n.get("date") or ""),
                        "official": True,
                        "raw_category": "notices",
                    })
        else:
            try:
                parsed_json = json.loads(payload)
            except json.JSONDecodeError:
                continue
            exch = "ZSE" if tag.startswith("zse") else "VFEX"
            raw_records.extend(_parse_exchange_docs_json(parsed_json, default_exchange=exch))

    if not raw_records and isinstance(cache, dict) and cache.get("items"):
        return {
            "ok": False,
            "cached": True,
            "fetched_at": cache.get("fetched_at"),
            "items": store.get_cached_news(),
            "error": errors[0] if errors else "Could not refresh news.",
        }

    alias_idx = _build_symbol_alias_index(store)
    stored_syms = set(store.state.get("prices", {}).keys()) | set(store.state.get("watchlist", [])) | set(store.state.get("portfolio", {}).keys())
    tracked_syms = store.get_tracked_symbols()

    seen_keys: set[str] = set()
    normalized_items: list[dict[str, Any]] = []
    for rec in raw_records:
        title = re.sub(r"\s+", " ", str(rec.get("title") or "")).strip()
        if not title:
            continue
        dt = _parse_news_timestamp(rec.get("pub_raw"))
        title_dt = _extract_title_news_date(title)
        if title_dt is not None and (dt is None or title_dt < dt):
            dt = title_dt
        age_days, age_label = _format_age_label(dt, now=now)
        if dt is not None and age_days > NEWS_MAX_AGE_DAYS:
            continue

        syms = _match_news_symbols(
            title,
            alias_idx,
            stored_syms,
            issuer_short=str(rec.get("issuer_short") or ""),
            issuer_name=str(rec.get("issuer_name") or ""),
        )
        # Drop unrelated RSS items that neither match a ZW company nor mention ZW/exchange context
        if not rec.get("official") and not syms:
            low_t = title.lower()
            if not any(ctx in low_t for ctx in ("vfex", "zse", "zimbabwe", "victoria falls", "harare", "bulawayo", "seczim", "c-trade", "zig", "zwg")):
                continue
        # Deduplicate across overlapping docs/issuer endpoints
        norm_key = re.sub(r"[^a-z0-9]+", "", title.lower())[:56]
        if not norm_key or norm_key in seen_keys:
            continue
        seen_keys.add(norm_key)

        cls = classify_news_headline(title, str(rec.get("raw_category") or ""), bool(rec.get("official")))
        is_tracked = any(s in tracked_syms for s in syms)
        ts_iso = dt.isoformat() if dt else now.isoformat()
        date_str = dt.date().isoformat() if dt else now.date().isoformat()
        nid = hashlib.sha1(f"{norm_key}|{date_str}".encode("utf-8")).hexdigest()[:12]
        normalized_items.append({
            "id": nid,
            "title": title,
            "url": str(rec.get("url") or ""),
            "source": str(rec.get("source") or "Market"),
            "official": bool(rec.get("official")),
            "symbols": syms,
            "tracked": is_tracked,
            "category": cls["category"],
            "sentiment": cls["sentiment"],
            "impact_score": cls["impact_score"],
            "published_at": ts_iso,
            "date": date_str,
            "age_days": age_days,
            "age_label": age_label,
        })

    # Sort descending by date/timestamp, prioritizing tracked & official on equal dates
    normalized_items.sort(
        key=lambda r: (
            r.get("published_at", ""),
            1 if r.get("tracked") else 0,
            1 if r.get("official") else 0,
            abs(int(r.get("impact_score") or 0)),
        ),
        reverse=True,
    )
    final_items = normalized_items[:35]
    fetched_at = now.isoformat()
    store.state["news_cache"] = {
        "fetched_at": fetched_at,
        "items": final_items,
        "error": errors[0] if (errors and not final_items) else "",
    }
    store.save()
    return {
        "ok": True,
        "cached": False,
        "fetched_at": fetched_at,
        "items": store.get_cached_news(),
        "error": "",
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
    vfex_fee_pct: float | str = "statutory",
    zse_fee_pct: float | str = "statutory",
    max_stock_pct: float = 25.0,
    profit_take_pct: float = 15.0,
    trading_goal: str = "hybrid",
    tracked_only: bool = True,
    enable_news: bool = True,
    enable_agent: bool = True,
    agent_zwg_rate: float = 26.5,
) -> dict[str, Any]:
    """Build structured JSON for BarWidget.qml and Panel.qml."""
    vfex_stat, vfex_fee_num = resolve_fee_mode(vfex_fee_pct, "USD")
    zse_stat, zse_fee_num = resolve_fee_mode(zse_fee_pct, "ZWG")
    fetch_res = fetch_vfex_prices(store, force=False)
    intel_res = fetch_exchange_intelligence(store, force=False)
    news_items: list[dict[str, Any]] = []
    news_error = ""
    news_fetched_at = ""
    if enable_news:
        news_res = fetch_vfex_news(store, force=False)
        news_items = news_res.get("items", [])
        news_error = str(news_res.get("error") or "")
        news_fetched_at = str(news_res.get("fetched_at") or "")
        if notify_signals:
            store.notify_news_catalysts(news_items)

    news_map = store._news_by_symbol(news_items) if enable_news else {}
    if enable_agent:
        store.run_paper_agent_step(
            allow_off_hours=False,
            news_items=news_items if enable_news else [],
            zwg_rate=agent_zwg_rate,
            save_state=True,
        )
    else:
        store.get_paper_agent_state(zwg_rate=agent_zwg_rate)
    store.check_alerts(notify=True)
    store.check_trailing_stops(notify=True)
    wb = format_waybar(store)
    effective_goal = normalize_goal(store.state.get("trading_goal") or trading_goal)
    tracked_syms = store.get_tracked_symbols()
    summary = store.portfolio_summary(
        vfex_fee_pct=vfex_fee_pct,
        zse_fee_pct=zse_fee_pct,
        trading_goal=effective_goal,
    )
    recs = {r["symbol"]: r for r in store.buy_recommendations(discount_pct=discount_pct, tracked_only=tracked_only)}
    signals = store.trade_signals(
        discount_pct=discount_pct,
        include_zse=include_zse,
        profit_take_pct=profit_take_pct,
        max_stock_pct=max_stock_pct,
        trading_goal=effective_goal,
        tracked_only=tracked_only,
        news_items=news_items if enable_news else [],
    )
    store.record_signal_history(signals, min_score=35)
    if notify_signals and get_market_status() == "Open":
        store.notify_trade_signals(signals, trading_goal=effective_goal)

    watchlist_items = []
    history_map = store.state.get("history", {})
    for sym in store.state.get("watchlist", []):
        p_entry = store.get_price_entry(sym)
        hist_rows = history_map.get(sym, [])
        hist = [h.get("close", h.get("price")) for h in hist_rows if ("close" in h or "price" in h)]
        cur_p = store.get_price(sym) or 0.0
        tech = compute_symbol_technicals(hist_rows, cur_p) if cur_p > 0 else {"ma20": None, "ma20_series": [], "rsi14": None, "z_score": None}
        lim = compute_smart_limit(
            cur_p,
            p_entry.get("best_bid"),
            p_entry.get("best_ask"),
            p_entry.get("bid_volume"),
            p_entry.get("ask_volume"),
            "BUY",
        )
        watchlist_items.append({
            "symbol": sym,
            "currency": infer_currency(sym, p_entry),
            "price": store.get_price(sym),
            "buy": sym in recs or any(s["symbol"] == sym and s["action"] == "BUY" for s in signals),
            "history": hist,
            "candles": store.get_candles(sym),
            "ma20": tech["ma20"],
            "ma20_series": tech["ma20_series"],
            "rsi14": tech["rsi14"],
            "z_score": tech["z_score"],
            "change_pct": store.get_daily_change(sym),
            "best_bid": p_entry.get("best_bid"),
            "best_ask": p_entry.get("best_ask"),
            "bid_volume": p_entry.get("bid_volume"),
            "ask_volume": p_entry.get("ask_volume"),
            "spread": p_entry.get("spread"),
            "spread_pct": lim["spread_pct"],
            "wide_spread": lim["wide_spread"],
            "liquidity_score": lim["liquidity_score"],
            "optimal_limit": lim["optimal_limit"],
            "company_name": p_entry.get("company_name"),
            "source": p_entry.get("source"),
            "news_catalyst": news_map.get(sym),
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

    indexed_trades = [
        {**t, "index": i, "currency": infer_currency(str(t.get("symbol", "")), store.get_price_entry(str(t.get("symbol", ""))))}
        for i, t in enumerate(store.state.get("trades", []))
    ]
    indexed_trades.reverse()
    recent_divs = list(reversed(store.state.get("dividends", [])))[:30]

    screener_rows = store.market_screener(
        discount_pct=discount_pct,
        profit_take_pct=profit_take_pct,
        max_stock_pct=max_stock_pct,
        trading_goal=effective_goal,
        news_items=news_items if enable_news else [],
    )
    market_top_signals = sorted(
        [r for r in screener_rows if r.get("symbol") not in tracked_syms and int(r.get("signal_score") or 0) > 0 and (include_zse or r.get("currency") == "USD")],
        key=lambda r: (-int(r.get("signal_score") or 0), str(r.get("symbol", ""))),
    )[:3]

    # Prioritize fresh headlines first (<=3d, <=7d, <=14d), then Tracked/Official/Material, max 1 per symbol
    sorted_news = sorted(
        news_items,
        key=lambda n: (
            _news_freshness_bucket(int(n.get("age_days") or 0)),
            1 if n.get("tracked") else 0,
            1 if n.get("official") else 0,
            1 if n.get("sentiment") in ("Bullish", "Caution") else 0,
            str(n.get("published_at") or ""),
        ),
        reverse=True,
    )
    overview_news: list[dict[str, Any]] = []
    seen_top_syms: set[str] = set()
    for n in sorted_news:
        syms = [str(s).upper() for s in n.get("symbols") or []]
        key_sym = syms[0] if syms else "__MARKET__"
        if key_sym in seen_top_syms:
            continue
        seen_top_syms.add(key_sym)
        overview_news.append(n)
        if len(overview_news) >= 3:
            break

    synced_map = store.state.get("synced_accounts", {})
    ct_acct = synced_map.get("ctrade") or {}
    portal_orders = list(ct_acct.get("orders") or [])[:25]
    raw_ptx: list[dict[str, Any]] = []
    for prov_k in ("ctrade", "vfex_direct", "zse_direct"):
        for tx_row in ((synced_map.get(prov_k) or {}).get("transactions") or [])[:25]:
            raw_ptx.append(tx_row)
    raw_ptx.sort(key=lambda r: str(r.get("date") or ""), reverse=True)
    raw_ptx = raw_ptx[:40]
    idle_cash_plan = store.idle_cash_deployment(
        include_zse=include_zse,
        news_items=news_items if enable_news else [],
    )
    existing_trade_keys = {
        (str(t.get("date") or ""), str(t.get("symbol") or "").upper(), round(float(t.get("shares") or 0.0), 3), str(t.get("action") or "").upper())
        for t in store.state.get("trades", [])
    }
    existing_div_keys = {
        (str(d.get("date") or ""), str(d.get("symbol") or "").upper(), round(float(d.get("amount") or 0.0), 2))
        for d in store.state.get("dividends", [])
    }
    portal_transactions: list[dict[str, Any]] = []
    for tx in raw_ptx:
        sym_k = str(tx.get("symbol") or "").upper()
        dt_k = str(tx.get("date") or "")
        sh_k = round(float(tx.get("shares") or 0.0), 3)
        amt_k = round(float(tx.get("amount") or 0.0), 2)
        t_up = str(tx.get("type") or "").upper()
        side_k = "BUY" if "BUY" in t_up else ("SELL" if "SELL" in t_up else ("DIV" if "DIV" in t_up else ""))
        dup = (
            ((dt_k, sym_k, sh_k, side_k) in existing_trade_keys) if side_k in ("BUY", "SELL")
            else (((dt_k, sym_k, amt_k) in existing_div_keys) if side_k == "DIV" else False)
        )
        portal_transactions.append({**tx, "trade_side": side_k, "already_imported": dup})

    return {
        **wb,
        "total_value": round(summary["total_value"], 2),
        "total_cost": round(summary["total_cost"], 2),
        "total_pnl": round(summary["total_pnl"], 2),
        "total_pnl_pct": round(summary["total_pnl_pct"], 2),
        "net_total_pnl": summary["net_total_pnl"],
        "net_total_pnl_pct": summary["net_total_pnl_pct"],
        "portfolio_xirr_pct": summary["portfolio_xirr_pct"],
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
        "core_value": summary["core_value"],
        "swing_value": summary["swing_value"],
        "core_count": summary["core_count"],
        "swing_count": summary["swing_count"],
        "trading_goal": effective_goal,
        "trading_goal_override": bool(store.state.get("trading_goal")),
        "tracked_only": tracked_only,
        "tracked_count": len(tracked_syms),
        "market_top_signals": market_top_signals,
        "news_enabled": enable_news,
        "news": news_items,
        "news_top": overview_news,
        "news_summary": {
            "total": len(news_items),
            "tracked": sum(1 for n in news_items if n.get("tracked")),
            "bullish": sum(1 for n in news_items if n.get("sentiment") == "Bullish"),
            "caution": sum(1 for n in news_items if n.get("sentiment") == "Caution"),
            "official": sum(1 for n in news_items if n.get("official")),
            "fetched_at": news_fetched_at,
            "error": news_error,
        },
        "strategy_tags": store.get_strategy_tags(),
        "watchlist": watchlist_items,
        "recommendations": list(recs.values()),
        "signals": signals,
        "top_signal": signals[0] if signals else None,
        "screener": screener_rows,
        "breadth": store.market_breadth(),
        "signal_backtest": store.signal_backtest_summary(),
        "equity_curve": store.portfolio_equity_curve(),
        "trailing_stops": list(store.state.get("trailing_stops", {}).values()),
        "trades": indexed_trades[:40],
        "dividends": recent_divs,
        "notes": store.get_notes(),
        "fee_config": {
            "vfex_fee_pct": round(vfex_fee_num, 2),
            "zse_fee_pct": round(zse_fee_num, 2),
            "vfex_statutory": vfex_stat,
            "zse_statutory": zse_stat,
            "max_stock_pct": round(max_stock_pct, 1),
            "profit_take_pct": round(profit_take_pct, 1),
        },
        "account": store.ctrade_status(),
        "accounts": store.accounts_status(),
        "portal_orders": portal_orders,
        "portal_transactions": portal_transactions,
        "idle_cash_plan": idle_cash_plan,
        "connected_count": sum(1 for v in store.accounts_status().values() if v.get("connected")),
        "wallet_cash_usd": summary["wallet_cash_usd"],
        "wallet_cash_zwg": summary["wallet_cash_zwg"],
        "alerts": [a["text"] for a in triggered_alerts],
        "triggered_alerts": triggered_alerts,
        "active_alerts": active_alerts,
        "targets": store.get_targets(),
        "market_status": get_market_status(),
        "market_countdown": get_market_countdown(),
        "last_updated": get_last_updated_label(store),
        "fetch_error": "" if fetch_res.get("ok") else str(fetch_res.get("message", "Fetch failed")),
        "market_intel": intel_res,
        "local_pdfs": scan_local_pdf_notes("~/Downloads", limit=8),
        "paper_agent": store.paper_agent_summary(zwg_rate=agent_zwg_rate),
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
    p_buy.add_argument("--tag", choices=["core", "swing", "auto"], default=None, help="Optional strategy horizon tag")

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
    p_panel.add_argument("--vfex-fee", type=str, default="statutory", help="VFEX fee per side pct or 'statutory'")
    p_panel.add_argument("--zse-fee", type=str, default="statutory", help="ZSE fee per side pct or 'statutory'")
    p_panel.add_argument("--max-stock-pct", type=float, default=25.0, help="Max allocation cap pct for sizing")
    p_panel.add_argument("--profit-take-pct", type=float, default=15.0, help="Profit-take signal pct")
    p_panel.add_argument("--goal", default="hybrid", help="Trading goal: long, short, or hybrid")
    p_panel.add_argument("--all-market", action="store_true", help="Include untracked market counters in signals/recommendations")
    p_panel.add_argument("--no-news", action="store_true", help="Disable live VFEX/ZSE news catalysts")
    p_panel.add_argument("--no-agent", action="store_true", help="Disable autonomous paper-agent execution")
    p_panel.add_argument("--agent-zwg-rate", type=float, default=26.5, help="ZWG per USD rate for ZSE paper wallet")

    p_agent = sub.add_parser("agent", help="Manage and run the local $100 self-learning paper-trading agent")
    p_agent.add_argument("action", choices=["status", "step", "replay", "train", "pause", "resume", "reset", "fees"])
    p_agent.add_argument("--days", type=int, default=180, help="Historical days for replay/training")
    p_agent.add_argument("--capital", type=float, default=100.0, help="Starting USD capital for reset/replay")
    p_agent.add_argument("--zwg-rate", type=float, default=26.5, help="ZWG/USD exchange rate")
    p_agent.add_argument("--json", action="store_true", help="Output structured JSON")
    p_agent.add_argument("--summary", action="store_true", help="Output concise one-line status")

    p_intel = sub.add_parser("intel", help="Show VFEX & ZSE DTR turnover, foreign institutional flow, and indices")
    p_intel.add_argument("--fetch", action="store_true", help="Bypass 5m cache and force live fetch")
    p_intel.add_argument("--json", action="store_true", help="Output structured JSON")

    p_news = sub.add_parser("news", help="Fetch and display VFEX/ZSE market & company news catalysts")
    p_news.add_argument("--fetch", action="store_true", help="Bypass 15m cache and force live fetch")
    p_news.add_argument("--tracked", action="store_true", help="Show tracked Watchlist/Holdings news only")
    p_news.add_argument("--json", action="store_true", help="Output structured JSON")
    p_news.add_argument("--summary", action="store_true", help="Output concise one-line status summary")

    p_goal = sub.add_parser("goal", help="Set or show trading goal override (long/short/hybrid/auto)")
    p_goal.add_argument("mode", nargs="?", choices=["long", "short", "hybrid", "auto", "show"], default="show")

    p_tag = sub.add_parser("tag", help="Pin a stock strategy horizon (core/swing/auto)")
    p_tag.add_argument("action", choices=["set", "clear", "list"])
    p_tag.add_argument("symbol", nargs="?")
    p_tag.add_argument("horizon", nargs="?", choices=["core", "swing", "auto"])

    p_stop = sub.add_parser("stop", help="Manage trailing stop-loss alerts (pct)")
    p_stop.add_argument("action", choices=["add", "remove", "list"])
    p_stop.add_argument("symbol", nargs="?")
    p_stop.add_argument("trail_pct", nargs="?", type=float)

    p_note = sub.add_parser("note", help="Manage per-symbol investment thesis notes")
    p_note.add_argument("action", choices=["set", "clear", "list"])
    p_note.add_argument("symbol", nargs="?")
    p_note.add_argument("text", nargs="?")

    p_trade = sub.add_parser("trade", help="Delete a mistaken trade from ledger")
    p_trade.add_argument("action", choices=["delete"])
    p_trade.add_argument("index", type=int)

    sub.add_parser("screener", help="Output full VFEX + ZSE screener table (JSON)")
    sub.add_parser("backtest", help="Show rolling 90-day signal track record")

    p_signals = sub.add_parser("signals", help="Show ranked BUY/SELL trade opportunities")
    p_signals.add_argument("--market", choices=["all", "vfex"], default="all")
    p_signals.add_argument("--discount", type=float, default=3.0)
    p_signals.add_argument("--goal", default="hybrid", help="Trading goal: long, short, or hybrid")
    p_signals.add_argument("--all-market", action="store_true", help="Scan all fetched counters beyond Watchlist/Holdings")
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
    p_rec = sub.add_parser("recommend", help="Show BUY recommendations based on 30d avg and targets")
    p_rec.add_argument("--all-market", action="store_true", help="Scan all fetched counters beyond Watchlist/Holdings")
    p_import = sub.add_parser("import", help="Import prices from a CSV file (symbol,price)")
    p_import.add_argument("file", help="Path to CSV file")

    p_imp_note = sub.add_parser("import-note", help="Parse and import a Morgan & Co / VFEX / ZSE PDF or text contract note")
    p_imp_note.add_argument("file", nargs="?", default=None, help="Path to PDF or TXT contract note")
    p_imp_note.add_argument("--text", default=None, help="Raw pasted contract note text instead of file path")
    p_imp_note.add_argument("--text-stdin", action="store_true", help="Read contract note text from stdin")
    p_imp_note.add_argument("--preview", action="store_true", help="Parse and return preview without modifying ledger")
    p_imp_note.add_argument("--tag", choices=["core", "swing", "auto"], default=None, help="Optional strategy horizon tag")
    p_imp_note.add_argument("--allow-duplicate", action="store_true", help="Import even if matching trade already exists")
    p_imp_note.add_argument("--json", action="store_true", help="Output structured JSON")
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
        try:
            fetch_exchange_intelligence(store, force=True)
        except Exception:
            pass
        try:
            fetch_vfex_news(store, force=True)
        except Exception:
            pass
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
        if getattr(args, "tag", None):
            store.set_strategy_tag(args.symbol, args.tag)
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
            vfex_fee_pct=args.vfex_fee,
            zse_fee_pct=args.zse_fee,
            max_stock_pct=args.max_stock_pct,
            profit_take_pct=args.profit_take_pct,
            trading_goal=args.goal,
            tracked_only=not getattr(args, "all_market", False),
            enable_news=not getattr(args, "no_news", False),
            enable_agent=not getattr(args, "no_agent", False),
            agent_zwg_rate=getattr(args, "agent_zwg_rate", 26.5),
        )))
    elif args.command == "agent":
        act = args.action
        rate = float(getattr(args, "zwg_rate", 26.5) or 26.5)
        cap = float(getattr(args, "capital", 100.0) or 100.0)
        if act == "fees":
            print(json.dumps({"vfex": VFEX_FEE_SCHEDULE, "zse": ZSE_FEE_SCHEDULE}, indent=2))
        elif act == "reset":
            store.reset_paper_agent(starting_usd=cap, zwg_rate=rate)
            msg = f"Reset $100 paper agent -> ${cap:.2f} USD (80% VFEX / 20% ZSE @ {rate:.1f} ZiG/$)"
            print(json.dumps(store.paper_agent_summary(rate)) if args.json else msg)
        elif act == "pause":
            store.toggle_paper_agent(False)
            print("Paused autonomous paper-trading agent.")
        elif act == "resume":
            store.toggle_paper_agent(True)
            print("Resumed autonomous paper-trading agent.")
        elif act == "step":
            res = store.run_paper_agent_step(allow_off_hours=True, news_items=store.get_cached_news(), zwg_rate=rate, save_state=True)
            summary = store.paper_agent_summary(rate)
            if args.json:
                print(json.dumps({"step": res, "agent": summary}))
            else:
                n_ex = len(res.get("executed", []))
                print(f"Agent step: {n_ex} fill(s) • Equity ${summary['equity_usd']:.2f} ({summary['net_pnl_pct']:+.2f}%)")
        elif act == "replay":
            summary = store.replay_paper_agent_history(days=int(getattr(args, "days", 30) or 30), starting_usd=cap, zwg_rate=rate)
            if args.json:
                print(json.dumps(summary))
            else:
                print(
                    f"Replayed {len(summary['equity_history'])}d: ${summary['starting_capital_usd']:.2f} -> ${summary['equity_usd']:.2f} "
                    f"({summary['net_pnl_pct']:+.2f}%) | {len(summary['trades'])} fills | Fees ${summary['total_fees_usd']:.2f} | {len(summary['lessons'])} lessons"
                )
        elif act == "train":
            summary = store.train_paper_agent_brain(days=int(getattr(args, "days", 180) or 180), zwg_rate=rate)
            if args.json:
                print(json.dumps(summary))
            else:
                br = summary.get("brain", {})
                gk = br.get("grok") or {}
                active_imm = sum(1 for im in br.get("immunities", []) if im.get("active"))
                print(
                    f"Trained Mahoraga brain: {br.get('adaptations_spun', 0)} wheel adaptation(s), "
                    f"{active_imm} active shield(s), {br.get('shadows_resolved', 0)}/{br.get('shadows_total', 0)} shadows | "
                    f"Grokking: {gk.get('status', 'Accumulating History')}"
                )
        else:
            summary = store.paper_agent_summary(rate)
            if args.json:
                print(json.dumps(summary))
            else:
                print(
                    f"Paper Agent [{'ACTIVE' if summary['enabled'] else 'PAUSED'}]: Equity ${summary['equity_usd']:.2f} "
                    f"({summary['net_pnl_pct']:+.2f}%) | Cash ${summary['cash_usd']:.2f} + ZiG {summary['cash_zwg']:.2f} | "
                    f"Open {len(summary['positions'])} | Closed {summary['total_closed']} (Win {summary['win_rate_pct']}%) | Fees ${summary['total_fees_usd']:.2f}"
                )
    elif args.command == "intel":
        intel = fetch_exchange_intelligence(store, force=bool(getattr(args, "fetch", False)))
        if getattr(args, "json", False):
            print(json.dumps(intel, indent=2))
        else:
            vx = intel.get("vfex", {})
            zs = intel.get("zse", {})
            if vx:
                print(f"VFEX: {vx.get('index_name')} {vx.get('index_value')} ({vx.get('index_chg_pct'):+.2f}%) | Turnover ${vx.get('turnover', 0):,.2f} ({vx.get('num_trades', 0)} trades) | Foreign Net ${vx.get('foreign_net', 0):+,.2f}")
            if zs:
                print(f"ZSE : {zs.get('index_name')} {zs.get('index_value')} ({zs.get('index_chg_pct'):+.2f}%) | Turnover ZiG {zs.get('turnover', 0):,.2f} ({zs.get('num_trades', 0)} trades) | Foreign Net ZiG {zs.get('foreign_net', 0):+,.2f}")
            print(f"Matched DTR active counters: {len(intel.get('counters', {}))} | Top Cap Blue-Chips: {len(intel.get('blue_chips', {}))}")
    elif args.command == "news":
        res = fetch_vfex_news(store, force=bool(getattr(args, "fetch", False)))
        items = res.get("items", [])
        if getattr(args, "tracked", False):
            items = [it for it in items if it.get("tracked")]
        if getattr(args, "json", False):
            print(json.dumps({"ok": res.get("ok"), "cached": res.get("cached"), "items": items}))
        elif getattr(args, "summary", False):
            trk_n = sum(1 for it in items if it.get("tracked"))
            print(f"Refreshed {len(items)} news catalysts ({trk_n} tracked).")
        elif not items:
            print("No VFEX/ZSE news catalysts found.")
        else:
            for it in items:
                syms_txt = ",".join(it.get("symbols") or ["MARKET"])
                trk = "*" if it.get("tracked") else " "
                print(f"{trk}[{it.get('sentiment'):<7} | {it.get('category'):<10}] {syms_txt:<14} {it.get('date')} | {it.get('title')} ({it.get('source')})")
    elif args.command == "goal":
        if args.mode == "show":
            print(store.state.get("trading_goal") or "auto")
        else:
            res = store.set_trading_goal(args.mode)
            print(f"Trading goal: {res}")
    elif args.command == "tag":
        if args.action == "list":
            print(json.dumps(store.get_strategy_tags()))
        elif args.action == "clear" and args.symbol:
            store.set_strategy_tag(args.symbol, "auto")
            print(f"Cleared strategy tag for {args.symbol.upper()}.")
        elif args.action == "set" and args.symbol and args.horizon:
            res = store.set_strategy_tag(args.symbol, args.horizon)
            print(f"Tagged {args.symbol.upper()} as {res.upper()}.")
    elif args.command == "stop":
        if args.action == "list":
            for sym, st in sorted(store.state.get("trailing_stops", {}).items()):
                print(f"{sym:<8} -{st['trail_pct']:.1f}% from peak {st['peak_price']:.4f}")
        elif args.action == "add" and args.symbol and args.trail_pct is not None:
            st = store.add_trailing_stop(args.symbol, args.trail_pct)
            print(f"Trailing stop set for {st['symbol']} (-{st['trail_pct']:.1f}% from peak {st['peak_price']:.4f})")
        elif args.action == "remove" and args.symbol:
            store.remove_trailing_stop(args.symbol)
            print(f"Removed trailing stop for {args.symbol.upper()}.")
    elif args.command == "note":
        if args.action == "list":
            print(json.dumps(store.get_notes()))
        elif args.action == "set" and args.symbol:
            store.set_note(args.symbol, args.text or "")
            print(f"Saved thesis note for {args.symbol.upper()}.")
        elif args.action == "clear" and args.symbol:
            store.set_note(args.symbol, "")
            print(f"Cleared note for {args.symbol.upper()}.")
    elif args.command == "trade":
        if args.action == "delete":
            removed = store.delete_trade(args.index)
            print(f"Removed trade #{args.index}: {removed.get('action')} {removed.get('symbol')}")
    elif args.command == "screener":
        print(json.dumps(store.market_screener()))
    elif args.command == "backtest":
        print(json.dumps(store.signal_backtest_summary(), indent=2))
    elif args.command == "signals":
        eff_goal = store.state.get("trading_goal") or args.goal
        sigs = store.trade_signals(
            discount_pct=args.discount,
            include_zse=(args.market == "all"),
            trading_goal=eff_goal,
            tracked_only=not getattr(args, "all_market", False),
        )
        if args.json:
            print(json.dumps(sigs))
        elif not sigs:
            print("No trade signals right now.")
        else:
            for s in sigs:
                print(f"[{s['score']}] {s['action']:<4} [{s.get('horizon','SWING')}] {s['symbol']:<8} {format_money(s['price'], s['currency'], 4)} ({', '.join(s['reasons'])})")
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
        recs = store.buy_recommendations(tracked_only=not getattr(args, "all_market", False))
        if not recs:
            print("No BUY signals right now.")
        else:
            for r in recs:
                print(f"BUY {r['symbol']}: ${r['price']:.4f} ({', '.join(r['reasons'])})")
    elif args.command == "import":
        count = store.import_csv(Path(args.file))
        print(f"Imported {count} price(s) from {args.file}.")
    elif args.command == "import-note":
        raw_txt = args.text
        if getattr(args, "text_stdin", False):
            raw_txt = sys.stdin.read()
        if raw_txt is not None:
            res = store.import_contract_note(
                raw_txt,
                tag=getattr(args, "tag", None),
                allow_duplicate=bool(getattr(args, "allow_duplicate", False)),
                dry_run=bool(getattr(args, "preview", False)),
                is_text=True,
            )
        elif args.file:
            res = store.import_contract_note(
                Path(args.file),
                tag=getattr(args, "tag", None),
                allow_duplicate=bool(getattr(args, "allow_duplicate", False)),
                dry_run=bool(getattr(args, "preview", False)),
                is_text=False,
            )
        else:
            raise ValueError("Provide a PDF/text file path or --text / --text-stdin.")
        if getattr(args, "json", False):
            print(json.dumps(res))
        elif getattr(args, "preview", False):
            dup_note = " [DUPLICATE IN LEDGER]" if res.get("duplicate") else ""
            print(f"Preview: {res['side']} {res['shares']:g} {res['symbol']} @ {format_money(res['price'], res['currency'], 4)} ({res['date']}) • Charges {format_money(res['total_charges'], res['currency'], 2)} • Net {format_money(res['net_settlement'], res['currency'], 2)}{dup_note}")
        else:
            print(res["message"])
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
