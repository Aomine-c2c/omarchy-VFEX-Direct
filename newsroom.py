#!/usr/bin/env python3
"""
NOTHING Investment Terminal — Market Intelligence & News Analysis Subsystem
---------------------------------------------------------------------------
Processes VFEX, ZSE, C-TRADE, Zimbabwean economic, regional, and international
news/announcements with:
- 12-category event classification
- Canonical deduplication (never losing confirmed official sources)
- Confirmed Announcement vs News Report vs Commentary distinction
- 7-section structured AI analysis ("Why This Matters To My Portfolio")
- Daily briefing, economic calendar, and dividend catalyst extraction
- Original source URL, headline, publisher, and timestamp always preserved.
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

NEWS_CATEGORIES = [
    "Corporate earnings",
    "Dividends",
    "Acquisitions",
    "Management changes",
    "Regulatory developments",
    "Monetary policy",
    "Fiscal policy",
    "Currency developments",
    "Inflation",
    "Market movements",
    "Corporate governance",
    "Sector developments",
]

CATEGORY_KEYWORDS: list[tuple[str, tuple[str, ...]]] = [
    ("Dividends", ("dividend", "interim div", "final div", "ex-div", "distribution", "payout")),
    ("Corporate earnings", ("earnings", "profit", "revenue", "financial results", "half year", "full year", "annual report", "interim results", "eps", "pat", "ebitda")),
    ("Acquisitions", ("acquisition", "acquire", "merger", "takeover", "cautionary", "buyout", "disposal", "stake")),
    ("Management changes", ("ceo", "cfo", "director", "resign", "appoint", "board change", "chairman", "executive")),
    ("Corporate governance", ("agm", "egm", "governance", "audit", "shareholder", "voting", "resolution")),
    ("Monetary policy", ("rbz", "reserve bank", "monetary policy", "interest rate", "bank policy rate", "central bank", "mpc")),
    ("Fiscal policy", ("budget", "tax", "cgt", "ministry of finance", "fiscal", "treasury", "tariff", "statutory instrument")),
    ("Currency developments", ("zwg", "zig", "exchange rate", "forex", "usd", "devaluation", "currency", "interbank")),
    ("Inflation", ("inflation", "cpi", "consumer price", "price index", "deflation")),
    ("Regulatory developments", ("secz", "regulatory", "compliance", "suspension", "listing", "delisting", "vfex", "zse notice")),
    ("Market movements", ("rally", "plunge", "surge", "all-share", "index", "turnover", "bull", "bear", "selloff", "gain")),
]


def _norm_fingerprint(title: str) -> str:
    clean = re.sub(r"[^a-z0-9 ]+", " ", str(title or "").lower())
    tokens = [t for t in clean.split() if len(t) > 2 and t not in ("the", "and", "for", "with", "from", "that", "this")]
    key = " ".join(tokens[:10])
    return hashlib.sha1(key.encode("utf-8")).hexdigest()[:16]


def classify_category(title: str, raw_category: str = "") -> str:
    text = f"{title} {raw_category}".lower()
    for cat, words in CATEGORY_KEYWORDS:
        if any(w in text for w in words):
            return cat
    return "Sector developments"


def detect_exchanges(title: str, source: str, symbols: list[str], zse_symbols: set[str]) -> list[str]:
    ex: list[str] = []
    text = f"{title} {source}".lower()
    if "vfex" in text or "victoria falls" in text:
        ex.append("VFEX")
    if "zse" in text or "zimbabwe stock" in text:
        ex.append("ZSE")
    if "c-trade" in text or "ctrade" in text:
        ex.append("CTRADE")
    for s in symbols:
        if s in zse_symbols and "ZSE" not in ex:
            ex.append("ZSE")
        elif s not in zse_symbols and "VFEX" not in ex:
            ex.append("VFEX")
    if not ex:
        ex.append("MACRO")
    return ex


def classify_source_type(item: dict[str, Any]) -> str:
    if item.get("official"):
        return "CONFIRMED_ANNOUNCEMENT"
    src = str(item.get("source") or "").lower()
    title = str(item.get("title") or "").lower()
    if item.get("manual"):
        return "MANUAL_UPLOAD"
    if any(w in title for w in ("opinion", "commentary", "rumour", "rumor", "editorial", "analysis:")):
        return "COMMENTARY"
    if any(w in src for w in ("vfex", "zse", "c-trade", "rbz", "official")):
        return "CONFIRMED_ANNOUNCEMENT"
    return "NEWS_REPORT"


def analyze_news_item(
    item: dict[str, Any],
    holdings_map: dict[str, dict[str, Any]],
    trading_goal: str = "hybrid",
) -> dict[str, Any]:
    """
    Produce structured 7-section AI analysis for a news item without ever replacing
    the original headline, publisher, date, or URL.
    """
    title = str(item.get("headline") or item.get("title") or "").strip()
    publisher = str(item.get("publisher") or item.get("source") or "Unknown Source")
    pub_date = str(item.get("published_at") or item.get("date") or "")
    url = str(item.get("url") or "")
    category = str(item.get("category") or classify_category(title))
    source_type = str(item.get("source_type") or classify_source_type(item))
    symbols = list(item.get("affected_securities") or item.get("symbols") or [])
    exchanges = list(item.get("affected_exchanges") or ["MACRO"])
    sentiment = str(item.get("sentiment") or "Neutral")

    linked_holdings = [s for s in symbols if s in holdings_map]
    if linked_holdings:
        parts = []
        for s in linked_holdings:
            h = holdings_map[s]
            parts.append(f"{s} ({float(h.get('alloc_pct') or 0):.1f}% of portfolio, P&L {float(h.get('pnl_pct') or 0):+.1f}%)")
        portfolio_impact = (
            f"DIRECT IMPACT on held position(s): {', '.join(parts)}. "
            f"Sentiment is {sentiment.upper()} under your {trading_goal.upper()} strategy — review position sizing and stop/target levels."
        )
    elif symbols:
        portfolio_impact = f"INDIRECT / WATCHLIST: Affects {', '.join(symbols)} (not currently held). Monitor for entry or peer read-through."
    else:
        portfolio_impact = f"MACRO / MARKET-WIDE ({', '.join(exchanges)}): No single-counter direct link; monitor FX, liquidity, and valuation multiples across your portfolio."

    why_map = {
        "Dividends": "Dividend declarations directly drive cash yield and total return, especially for USD-denominated VFEX income holdings.",
        "Corporate earnings": "Earnings trajectory drives intrinsic valuation, dividend sustainability, and institutional re-rating.",
        "Monetary policy": "RBZ policy rate and liquidity actions directly affect ZWG stability, discount rates, and ZSE/VFEX capital flows.",
        "Currency developments": "ZWG/USD exchange-rate shifts impact ZSE USD-equivalent returns and exporter vs domestic margins.",
        "Inflation": "Inflation dynamics alter real returns, consumer purchasing power, and central bank tightening risk.",
        "Acquisitions": "M&A and cautionary announcements can trigger sharp re-pricing or dilution depending on deal terms.",
        "Regulatory developments": "Exchange or SECZ rule changes affect trading costs, settlement, and market access.",
    }
    why_it_matters = why_map.get(category, f"{category} developments can shift sector sentiment, liquidity, and relative valuation on {', '.join(exchanges)}.")

    market_impact = (
        f"Potential {sentiment.lower()} impulse across {', '.join(exchanges)}"
        + (f" led by {', '.join(symbols[:3])}." if symbols else ".")
    )
    what_to_watch = (
        "Watch for official audited figures, ex-dividend / record dates, and post-announcement bid-ask volume confirmation."
        if source_type == "CONFIRMED_ANNOUNCEMENT"
        else "Await official exchange/issuer confirmation before acting; monitor volume and spread changes."
    )
    confidence = (
        "HIGH (Confirmed official exchange/issuer publication; impact estimate remains analytical.)"
        if source_type == "CONFIRMED_ANNOUNCEMENT"
        else "MEDIUM-LOW (Secondary media report or commentary; verify against primary exchange filings.)"
    )

    return {
        "original_headline": title,
        "publisher": publisher,
        "published_at": pub_date,
        "original_url": url,
        "source_type": source_type,
        "category": category,
        "what_happened": f"[{source_type.replace('_', ' ')}] {title} (Published by {publisher}).",
        "why_it_matters": why_it_matters,
        "affected_securities": symbols,
        "portfolio_impact": portfolio_impact,
        "market_impact": market_impact,
        "what_to_watch": what_to_watch,
        "confidence": confidence,
    }


def process_and_deduplicate_news(
    raw_items: list[dict[str, Any]],
    holdings: list[dict[str, Any]],
    zse_symbols: set[str],
    trading_goal: str = "hybrid",
) -> list[dict[str, Any]]:
    """
    Normalize, classify (12 categories), deduplicate (preferring CONFIRMED_ANNOUNCEMENT),
    link to portfolio holdings, and attach 7-section AI analysis.
    """
    holdings_map = {str(h.get("symbol") or "").upper(): h for h in (holdings or []) if h.get("symbol")}
    by_fp: dict[str, dict[str, Any]] = {}

    for raw in raw_items or []:
        title = str(raw.get("title") or raw.get("headline") or "").strip()
        if not title:
            continue
        fp = _norm_fingerprint(title)
        syms = [str(s).upper() for s in (raw.get("symbols") or raw.get("affected_securities") or [])]
        cat = classify_category(title, str(raw.get("category") or ""))
        src_type = classify_source_type(raw)
        exchanges = detect_exchanges(title, str(raw.get("source") or ""), syms, zse_symbols)
        linked = [s for s in syms if s in holdings_map]
        age_days = int(raw.get("age_days") if raw.get("age_days") is not None else 0)

        enriched = {
            "id": str(raw.get("id") or fp),
            "headline": title,
            "publisher": str(raw.get("source") or raw.get("publisher") or "Unknown"),
            "published_at": str(raw.get("published_at") or raw.get("date") or ""),
            "age_label": str(raw.get("age_label") or ""),
            "age_days": age_days,
            "url": str(raw.get("url") or ""),
            "affected_securities": syms,
            "affected_exchanges": exchanges,
            "category": cat,
            "source_type": src_type,
            "sentiment": str(raw.get("sentiment") or "Neutral"),
            "impact_score": int(raw.get("impact_score") or 0),
            "linked_holdings": linked,
            "affects_portfolio": len(linked) > 0,
            "is_breaking": age_days <= 1 or abs(int(raw.get("impact_score") or 0)) >= 18,
        }
        enriched["ai_analysis"] = analyze_news_item(enriched, holdings_map, trading_goal=trading_goal)

        existing = by_fp.get(fp)
        if existing is None:
            by_fp[fp] = enriched
        elif src_type == "CONFIRMED_ANNOUNCEMENT" and existing["source_type"] != "CONFIRMED_ANNOUNCEMENT":
            by_fp[fp] = enriched

    result = list(by_fp.values())
    result.sort(key=lambda x: (0 if x["affects_portfolio"] else 1, 0 if x["source_type"] == "CONFIRMED_ANNOUNCEMENT" else 1, x["age_days"]))
    return result


def build_newsroom_payload(panel_data: dict[str, Any], manual_items: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    raw = list(panel_data.get("news") or []) + list(manual_items or [])
    holdings = panel_data.get("items") or []
    zse_syms = set(panel_data.get("zse_symbols") or [])
    goal = str(panel_data.get("trading_goal") or "hybrid")

    items = process_and_deduplicate_news(raw, holdings, zse_syms, trading_goal=goal)
    breaking = [i for i in items if i["is_breaking"]]
    personalized = [i for i in items if i["affects_portfolio"]]
    confirmed = [i for i in items if i["source_type"] == "CONFIRMED_ANNOUNCEMENT"]
    dividends = [i for i in items if i["category"] == "Dividends"]
    macro = [i for i in items if i["category"] in ("Monetary policy", "Fiscal policy", "Currency developments", "Inflation")]

    briefing = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "headline_count": len(items),
        "confirmed_count": len(confirmed),
        "portfolio_linked_count": len(personalized),
        "macro_count": len(macro),
        "dividend_events_count": len(dividends),
        "summary": (
            f"Daily Briefing: {len(items)} deduplicated stories ({len(confirmed)} confirmed exchange announcements, "
            f"{len(personalized)} directly affecting your holdings, {len(dividends)} dividend event(s), {len(macro)} macro/policy item(s))."
        ),
    }

    return {
        "generated_at": briefing["generated_at"],
        "daily_briefing": briefing,
        "all_items": items,
        "breaking_feed": breaking[:10],
        "personalized_feed": personalized,
        "corporate_announcements": confirmed,
        "dividend_events": dividends,
        "economic_calendar": macro,
    }


def main() -> int:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import vfex
    store = vfex.VFEXStore()
    panel_data = vfex.format_panel_json(store)
    payload = build_newsroom_payload(panel_data)
    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
