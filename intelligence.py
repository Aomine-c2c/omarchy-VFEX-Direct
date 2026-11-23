#!/usr/bin/env python3
"""
NOTHING Investment Terminal — Multi-Agent Investment Intelligence Engine
------------------------------------------------------------------------
8 specialised analytical agents + orchestration layer for VFEX, ZSE, and C-TRADE.
Zero external runtime dependencies (Python stdlib only).

Reliability & Safety Guarantees:
- Never fabricates financial statements, market prices, or news.
- Every news analysis links to its original source URL and timestamp.
- Distinguishes verified exchange/cached data from estimates and flags data limitations.
- Allows and explicitly surfaces inter-agent disagreements.
- Trading Assistant prepares trade tickets with `requires_human_confirmation=True`
  and NEVER executes trades autonomously.
"""

from __future__ import annotations

import json
import sys
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class AgentFinding:
    agent_id: str
    agent_name: str
    status: str  # COMPLETED | WARNING | ERROR
    stance: str  # BUY | HOLD | SELL | WATCH | CAUTION | NEUTRAL
    confidence: str  # HIGH | MEDIUM | LOW
    summary: str
    evidence: list[str] = field(default_factory=list)
    citations: list[dict[str, str]] = field(default_factory=list)
    data_limitations: list[str] = field(default_factory=list)
    metrics: dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(default_factory=_utc_now)


@dataclass
class StructuredRecommendation:
    security: str
    exchange: str
    recommendation_type: str  # BUY | HOLD | SELL | WATCH (analytical opinion only)
    verified_price: float | None
    price_timestamp: str
    investment_thesis: str
    supporting_evidence: list[str]
    fundamental_analysis: str
    technical_analysis: str
    liquidity_considerations: str
    upside_scenario: str
    downside_scenario: str
    key_risks: list[str]
    expected_horizon: str
    confidence_level: str
    invalidation_conditions: list[str]
    data_limitations: list[str]
    disclaimer: str = "Analytical opinion only — not a guaranteed outcome or financial advice."


# ── Base Agent ───────────────────────────────────────────────────────────────

class BaseAgent:
    agent_id: str = "base"
    agent_name: str = "Base Agent"

    def analyze(self, ctx: dict[str, Any]) -> AgentFinding:
        raise NotImplementedError


# ── AGENT 1: PORTFOLIO ANALYST ───────────────────────────────────────────────

class PortfolioAnalystAgent(BaseAgent):
    agent_id = "portfolio_analyst"
    agent_name = "Portfolio Analyst"

    def analyze(self, ctx: dict[str, Any]) -> AgentFinding:
        snap = ctx["panel_data"]
        items = snap.get("items") or []
        total_val = float(snap.get("total_value") or 0.0)
        total_pnl = float(snap.get("total_pnl") or 0.0)
        total_pnl_pct = float(snap.get("total_pnl_pct") or 0.0)
        cash_usd = float(snap.get("wallet_cash_usd") or 0.0)
        cash_zwg = float(snap.get("wallet_cash_zwg") or 0.0)
        divs = float(snap.get("total_dividends") or 0.0)

        concentrated = [i for i in items if float(i.get("alloc_pct") or 0.0) > 25.0]
        underperf = [i for i in items if float(i.get("pnl_pct") or 0.0) < -5.0]
        evidence = [
            f"Total portfolio value: ${total_val:.2f} (Unrealised P&L: ${total_pnl:+.2f} / {total_pnl_pct:+.2f}%).",
            f"Available cash: ${cash_usd:.2f} USD | ZiG {cash_zwg:.2f} | Recorded dividends: ${divs:.2f}.",
            f"Holdings count: {len(items)} | Concentrated (>25%): {len(concentrated)} | Underperforming (<-5%): {len(underperf)}.",
        ]
        stance = "CAUTION" if (concentrated or underperf) else ("HOLD" if items else "WATCH")
        return AgentFinding(
            agent_id=self.agent_id,
            agent_name=self.agent_name,
            status="COMPLETED",
            stance=stance,
            confidence="HIGH" if items else "LOW",
            summary=f"Portfolio stands at ${total_val:.2f} across {len(items)} holding(s); {len(concentrated)} concentration flag(s) and {len(underperf)} underperformer(s).",
            evidence=evidence,
            data_limitations=["Realised P&L and historical equity curve require multi-day ledger history."] if not snap.get("equity_curve") else [],
            metrics={"total_value": total_val, "holdings_count": len(items), "concentrated": [c["symbol"] for c in concentrated]},
        )


# ── AGENT 2: MARKET RESEARCHER ───────────────────────────────────────────────

class MarketResearcherAgent(BaseAgent):
    agent_id = "market_researcher"
    agent_name = "Market Researcher"

    def analyze(self, ctx: dict[str, Any]) -> AgentFinding:
        snap = ctx["panel_data"]
        screener = snap.get("screener") or []
        breadth = snap.get("breadth") or {}
        target = ctx.get("symbol")

        unusual = [
            r for r in screener
            if abs(float(r.get("z_score") or 0.0)) >= 1.5 or abs(float(r.get("change_pct") or 0.0)) >= 4.0
        ]
        liquid = [r for r in screener if float(r.get("liquidity_score") or 0.0) >= 50.0]
        evidence = [
            f"Market breadth: {breadth.get('advancers', 0)} advancers / {breadth.get('decliners', 0)} decliners across {len(screener)} counters.",
            f"Unusual movers detected: {len(unusual)} | Liquid counters (score >= 50): {len(liquid)}.",
        ]
        stance = "NEUTRAL"
        if target:
            row = next((r for r in screener if r.get("symbol") == target), None)
            if row:
                chg = float(row.get("change_pct") or 0.0)
                liq = float(row.get("liquidity_score") or 0.0)
                evidence.append(f"{target}: last {row.get('price')} ({chg:+.2f}%), liquidity {liq:.0f}/100, spread {row.get('spread_pct', 0):.2f}%.")
                stance = "BUY" if (chg <= -2.0 and liq >= 40) else ("WATCH" if liq < 30 else "HOLD")

        return AgentFinding(
            agent_id=self.agent_id,
            agent_name=self.agent_name,
            status="COMPLETED",
            stance=stance,
            confidence="MEDIUM" if screener else "LOW",
            summary=f"Monitored {len(screener)} VFEX/ZSE counters; {len(unusual)} unusual activity flag(s) and {len(liquid)} liquid counters.",
            evidence=evidence,
            data_limitations=["Intraday tick-by-tick order flow is not exposed by VFEX/ZSE public feeds; using daily price sheets and top-of-book depth."],
            metrics={"counters_scanned": len(screener), "unusual_count": len(unusual)},
        )


# ── AGENT 3: FUNDAMENTAL ANALYST ─────────────────────────────────────────────

class FundamentalAnalystAgent(BaseAgent):
    agent_id = "fundamental_analyst"
    agent_name = "Fundamental Analyst"

    def analyze(self, ctx: dict[str, Any]) -> AgentFinding:
        snap = ctx["panel_data"]
        target = ctx.get("symbol")
        news = snap.get("news") or []
        official_docs = [n for n in news if n.get("official") and (not target or target in (n.get("symbols") or []))]

        citations = [
            {"title": str(n.get("title", "")), "source": str(n.get("source", "")), "url": str(n.get("url", "")), "timestamp": str(n.get("published_at") or n.get("date") or "")}
            for n in official_docs[:5]
        ]
        evidence = [f"Found {len(official_docs)} official exchange/issuer filing(s) for fundamental review."]
        for c in citations[:3]:
            evidence.append(f"Filing ({c['timestamp'][:10]}): {c['title']} [{c['source']}]")

        limitations = [
            "Audited financial statement line items (revenue, net income, EBITDA, debt/equity, free cash flow) are not structured in the VFEX/ZSE JSON feeds.",
            "Valuation multiples (P/E, P/B, EV/EBITDA) are intentionally withheld rather than fabricated.",
        ]
        return AgentFinding(
            agent_id=self.agent_id,
            agent_name=self.agent_name,
            status="COMPLETED",
            stance="WATCH",
            confidence="LOW",
            summary=f"Reviewed {len(official_docs)} official issuer filing(s); full quantitative fundamental valuation is gated pending structured financial statements.",
            evidence=evidence,
            citations=citations,
            data_limitations=limitations,
            metrics={"official_filings_count": len(official_docs)},
        )


# ── AGENT 4: NEWS INTELLIGENCE ANALYST ───────────────────────────────────────

class NewsIntelligenceAgent(BaseAgent):
    agent_id = "news_intelligence"
    agent_name = "News Intelligence Analyst"

    def analyze(self, ctx: dict[str, Any]) -> AgentFinding:
        snap = ctx["panel_data"]
        news = snap.get("news") or []
        target = ctx.get("symbol")
        relevant = [n for n in news if (target in (n.get("symbols") or []))] if target else [n for n in news if n.get("tracked") or n.get("official")]
        if not relevant:
            relevant = news[:5]

        bullish = sum(1 for n in relevant if n.get("sentiment") == "Bullish")
        caution = sum(1 for n in relevant if n.get("sentiment") == "Caution")
        citations = [
            {
                "title": str(n.get("title", "")),
                "source": str(n.get("source", "")),
                "url": str(n.get("url", "")),
                "timestamp": str(n.get("published_at") or n.get("date") or ""),
            }
            for n in relevant[:6]
        ]
        evidence = [f"Analysed {len(relevant)} relevant item(s): {bullish} Bullish, {caution} Caution."]
        for c in citations[:4]:
            evidence.append(f"[{c['source']} | {c['timestamp'][:10]}] {c['title']} -> {c['url']}")

        stance = "BUY" if bullish > caution else ("CAUTION" if caution > bullish else "NEUTRAL")
        return AgentFinding(
            agent_id=self.agent_id,
            agent_name=self.agent_name,
            status="COMPLETED",
            stance=stance,
            confidence="MEDIUM" if citations else "LOW",
            summary=f"News flow: {bullish} bullish vs {caution} cautionary catalyst(s) across {len(relevant)} cited source(s).",
            evidence=evidence,
            citations=citations,
            data_limitations=["Sentiment classification is heuristic keyword-based; verify primary PDF announcements via cited URLs."],
            metrics={"bullish": bullish, "caution": caution, "total_cited": len(citations)},
        )


# ── AGENT 5: RISK ANALYST ────────────────────────────────────────────────────

class RiskAnalystAgent(BaseAgent):
    agent_id = "risk_analyst"
    agent_name = "Risk Analyst"

    def analyze(self, ctx: dict[str, Any]) -> AgentFinding:
        snap = ctx["panel_data"]
        target = ctx.get("symbol")
        screener = snap.get("screener") or []
        items = snap.get("items") or []
        risks: list[str] = []

        if any(float(i.get("alloc_pct") or 0.0) > 25.0 for i in items):
            risks.append("Single-stock concentration exceeds 25% portfolio cap.")
        if float(snap.get("zwg_value") or 0.0) > 0 or float(snap.get("wallet_cash_zwg") or 0.0) > 0:
            risks.append("ZWG currency depreciation and ZSE statutory CGT/fee drag (~4.38% round-trip) apply to ZSE exposure.")

        stance = "HOLD"
        if target:
            row = next((r for r in screener if r.get("symbol") == target), None)
            if row:
                spread = float(row.get("spread_pct") or 0.0)
                liq = float(row.get("liquidity_score") or 0.0)
                if row.get("wide_spread") or spread >= 5.0:
                    risks.append(f"{target} has wide bid-ask spread ({spread:.2f}%), creating immediate entry slippage.")
                    stance = "CAUTION"
                if liq < 35.0:
                    risks.append(f"{target} has low liquidity score ({liq:.0f}/100); exit execution may be slow.")
                    stance = "CAUTION"
        elif risks:
            stance = "CAUTION"

        return AgentFinding(
            agent_id=self.agent_id,
            agent_name=self.agent_name,
            status="COMPLETED",
            stance=stance,
            confidence="HIGH",
            summary=f"Identified {len(risks)} active risk factor(s) challenging aggressive positioning." if risks else "No severe liquidity or concentration risks detected.",
            evidence=risks or ["Portfolio concentration and spread metrics are within normal thresholds."],
            data_limitations=["Historical drawdown covariance across VFEX/ZSE is limited by short local OHLC history depth."],
            metrics={"risk_count": len(risks)},
        )


# ── AGENT 6: OPPORTUNITY SCANNER ─────────────────────────────────────────────

class OpportunityScannerAgent(BaseAgent):
    agent_id = "opportunity_scanner"
    agent_name = "Opportunity Scanner"

    def analyze(self, ctx: dict[str, Any]) -> AgentFinding:
        snap = ctx["panel_data"]
        signals = (snap.get("signals") or []) + (snap.get("market_top_signals") or [])
        seen: set[str] = set()
        ranked: list[dict[str, Any]] = []
        for s in signals:
            sym = str(s.get("symbol") or "")
            if sym and sym not in seen:
                seen.add(sym)
                ranked.append(s)
        ranked.sort(key=lambda x: -float(x.get("score") or x.get("signal_score") or 0.0))

        evidence = [
            f"#{idx+1} {r.get('symbol')}: {r.get('action') or r.get('signal_action')} (score {r.get('score') or r.get('signal_score')}) — {', '.join((r.get('reasons') or [])[:2])}"
            for idx, r in enumerate(ranked[:5])
        ]
        top_action = str(ranked[0].get("action") or ranked[0].get("signal_action") or "WATCH") if ranked else "WATCH"
        return AgentFinding(
            agent_id=self.agent_id,
            agent_name=self.agent_name,
            status="COMPLETED",
            stance=top_action if top_action in ("BUY", "SELL", "HOLD", "WATCH") else "WATCH",
            confidence="MEDIUM" if ranked else "LOW",
            summary=f"Ranked {len(ranked)} transparent quant opportunity candidate(s) across VFEX & ZSE.",
            evidence=evidence or ["No counters currently meet minimum quantitative opportunity score."],
            metrics={"top_opportunities": [r.get("symbol") for r in ranked[:5]]},
        )


# ── AGENT 7: INVESTMENT STRATEGIST ───────────────────────────────────────────

class InvestmentStrategistAgent(BaseAgent):
    agent_id = "investment_strategist"
    agent_name = "Investment Strategist"

    def analyze(self, ctx: dict[str, Any]) -> AgentFinding:
        snap = ctx["panel_data"]
        goal = str(snap.get("trading_goal") or "hybrid").upper()
        targets = snap.get("targets") or {}
        idle = snap.get("idle_cash_plan") or {}
        dep_usd = float(idle.get("total_deployable_usd") or 0.0)
        dep_zwg = float(idle.get("total_deployable_zwg") or 0.0)

        evidence = [
            f"Active investment goal: {goal}.",
            f"Defined allocation targets: {len(targets)} symbol(s).",
            f"Deployable idle cash: ${dep_usd:.2f} USD | ZiG {dep_zwg:.2f}.",
        ]
        if not targets:
            evidence.append("Recommendation: define target allocation percentages in Planner (Screen 7) to unlock automated rebalancing.")
        return AgentFinding(
            agent_id=self.agent_id,
            agent_name=self.agent_name,
            status="COMPLETED",
            stance="HOLD",
            confidence="MEDIUM",
            summary=f"Strategy aligned to {goal} horizon with ${dep_usd:.2f} USD and ZiG {dep_zwg:.2f} deployable cash.",
            evidence=evidence,
            metrics={"goal": goal, "target_count": len(targets), "deployable_usd": dep_usd},
        )


# ── AGENT 8: TRADING ASSISTANT (NEVER EXECUTES AUTONOMOUSLY) ─────────────────

class TradingAssistantAgent(BaseAgent):
    agent_id = "trading_assistant"
    agent_name = "Trading Assistant"

    def analyze(self, ctx: dict[str, Any]) -> AgentFinding:
        snap = ctx["panel_data"]
        target = ctx.get("symbol")
        qty = float(ctx.get("quantity") or 100.0)
        side = str(ctx.get("side") or "BUY").upper()
        screener = snap.get("screener") or []
        row = next((r for r in screener if r.get("symbol") == target), None) if target else None

        cash_usd = float(snap.get("wallet_cash_usd") or 0.0)
        cash_zwg = float(snap.get("wallet_cash_zwg") or 0.0)

        if not row or not row.get("price"):
            return AgentFinding(
                agent_id=self.agent_id,
                agent_name=self.agent_name,
                status="COMPLETED",
                stance="WATCH",
                confidence="LOW",
                summary="No verified counter price selected for trade ticket preparation.",
                evidence=[f"Available balances: ${cash_usd:.2f} USD | ZiG {cash_zwg:.2f}."],
                metrics={"requires_human_confirmation": True, "executed": False},
            )

        px = float(row["price"])
        cur = str(row.get("currency") or "USD")
        gross = qty * px
        fee_rate = 0.0218 if cur == "ZWG" else 0.0104
        est_fees = round(gross * fee_rate, 2)
        net_total = round(gross + est_fees, 2) if side == "BUY" else round(max(0.0, gross - est_fees), 2)
        avail = cash_zwg if cur == "ZWG" else cash_usd
        sufficient = (side == "SELL") or (avail >= net_total)

        ticket = {
            "security": target,
            "exchange": "ZSE" if cur == "ZWG" else "VFEX",
            "side": side,
            "quantity": qty,
            "limit_price": round(float(row.get("optimal_limit") or px), 4),
            "currency": cur,
            "estimated_gross": round(gross, 2),
            "estimated_fees": est_fees,
            "estimated_net": net_total,
            "available_balance": round(avail, 2),
            "balance_sufficient": sufficient,
            "requires_human_confirmation": True,
            "executed": False,
        }
        evidence = [
            f"Prepared {side} ticket: {qty:.0f} {target} @ {ticket['limit_price']} {cur} (Est. fees {est_fees} {cur}, Net {net_total} {cur}).",
            f"Balance check: {'SUFFICIENT' if sufficient else 'INSUFFICIENT'} (Available: {avail:.2f} {cur}).",
            "SAFETY: Ticket prepared for human review only — NEVER executed without explicit confirmation.",
        ]
        return AgentFinding(
            agent_id=self.agent_id,
            agent_name=self.agent_name,
            status="COMPLETED",
            stance="CAUTION" if not sufficient else side,
            confidence="HIGH",
            summary=f"Trade ticket ready for human confirmation: {side} {qty:.0f} {target} (Est. net {net_total} {cur}).",
            evidence=evidence,
            metrics={"trade_ticket": ticket, "requires_human_confirmation": True, "executed": False},
        )


# ── ORCHESTRATION LAYER ──────────────────────────────────────────────────────

class IntelligenceOrchestrator:
    """
    Routes investment questions to relevant specialised agents, collects real
    activity events, detects inter-agent disagreements, and produces a
    consolidated structured report with full evidence and citations.
    """

    def __init__(self, reports_path: Path | None = None) -> None:
        self.agents: dict[str, BaseAgent] = {
            a.agent_id: a
            for a in (
                PortfolioAnalystAgent(),
                MarketResearcherAgent(),
                FundamentalAnalystAgent(),
                NewsIntelligenceAgent(),
                RiskAnalystAgent(),
                OpportunityScannerAgent(),
                InvestmentStrategistAgent(),
                TradingAssistantAgent(),
            )
        }
        self.reports_path = reports_path or (Path.home() / ".config" / "vfex" / "intelligence_reports.json")

    def select_agents(self, question: str, symbol: str | None = None) -> list[str]:
        q = question.lower()
        if any(w in q for w in ("full", "all", "desk", "report", "comprehensive")):
            return list(self.agents.keys())
        chosen: list[str] = []
        if any(w in q for w in ("portfolio", "holding", "allocation", "diversif", "dividend")):
            chosen.extend(["portfolio_analyst", "risk_analyst", "investment_strategist"])
        if any(w in q for w in ("news", "announcement", "catalyst", "macro", "economic")):
            chosen.append("news_intelligence")
        if any(w in q for w in ("fundamental", "valuation", "earnings", "revenue", "debt")):
            chosen.append("fundamental_analyst")
        if any(w in q for w in ("scan", "opportunit", "undervalued", "unusual", "screen")):
            chosen.extend(["opportunity_scanner", "market_researcher"])
        if any(w in q for w in ("buy", "sell", "trade", "order", "ticket", "size")) or symbol:
            chosen.extend(["market_researcher", "fundamental_analyst", "news_intelligence", "risk_analyst", "trading_assistant"])
        if not chosen:
            return list(self.agents.keys())
        # Preserve order, deduplicate
        return list(dict.fromkeys(chosen))

    def run_analysis(
        self,
        question: str,
        panel_data: dict[str, Any],
        symbol: str | None = None,
        quantity: float = 100.0,
        side: str = "BUY",
        persist: bool = True,
    ) -> dict[str, Any]:
        events: list[dict[str, str]] = []
        events.append({"timestamp": _utc_now(), "event": "STARTED", "detail": f"Received query: {question}"})

        # Detect symbol in question if not explicitly provided
        if not symbol:
            known_syms = {str(r.get("symbol", "")).upper() for r in (panel_data.get("screener") or [])}
            for tok in question.replace("?", "").replace(",", "").split():
                if tok.upper() in known_syms:
                    symbol = tok.upper()
                    break

        selected_ids = self.select_agents(question, symbol=symbol)
        events.append({"timestamp": _utc_now(), "event": "ROUTED", "detail": f"Selected {len(selected_ids)} agent(s): {', '.join(selected_ids)}"})

        ctx = {
            "question": question,
            "symbol": symbol,
            "quantity": quantity,
            "side": side,
            "panel_data": panel_data,
        }

        findings: list[AgentFinding] = []
        for aid in selected_ids:
            agent = self.agents[aid]
            try:
                f = agent.analyze(ctx)
                findings.append(f)
                events.append({"timestamp": _utc_now(), "event": "AGENT_COMPLETED", "detail": f"{agent.agent_name} -> {f.stance} ({f.confidence})"})
            except Exception as exc:
                findings.append(AgentFinding(aid, agent.agent_name, "ERROR", "NEUTRAL", "LOW", f"Agent error: {exc}"))
                events.append({"timestamp": _utc_now(), "event": "AGENT_ERROR", "detail": f"{agent.agent_name}: {exc}"})

        # Detect explicit inter-agent disagreements
        disagreements: list[dict[str, Any]] = []
        bullish_agents = [f for f in findings if f.stance == "BUY"]
        cautious_agents = [f for f in findings if f.stance in ("CAUTION", "SELL")]
        if bullish_agents and cautious_agents:
            disagreements.append({
                "topic": f"Stance conflict on {symbol or 'portfolio'}",
                "bullish_side": [{"agent": f.agent_name, "summary": f.summary} for f in bullish_agents],
                "cautious_side": [{"agent": f.agent_name, "summary": f.summary} for f in cautious_agents],
            })
            events.append({"timestamp": _utc_now(), "event": "DISAGREEMENT_DETECTED", "detail": f"{len(bullish_agents)} BUY vs {len(cautious_agents)} CAUTION/SELL"})

        # Build structured 16-field recommendation if a security is in scope
        recommendations: list[dict[str, Any]] = []
        rec_sym = symbol or ((panel_data.get("top_signal") or {}).get("symbol"))
        if rec_sym:
            row = next((r for r in (panel_data.get("screener") or []) if r.get("symbol") == rec_sym), None)
            if row:
                rec_type = "WATCH"
                if bullish_agents and not cautious_agents:
                    rec_type = "BUY"
                elif cautious_agents and not bullish_agents:
                    rec_type = "HOLD" if any(i.get("symbol") == rec_sym for i in (panel_data.get("items") or [])) else "WATCH"
                rec = StructuredRecommendation(
                    security=rec_sym,
                    exchange="ZSE" if row.get("currency") == "ZWG" else "VFEX",
                    recommendation_type=rec_type,
                    verified_price=float(row["price"]) if row.get("price") is not None else None,
                    price_timestamp=str(panel_data.get("last_updated") or _utc_now()),
                    investment_thesis=f"Multi-agent synthesis on {rec_sym} based on verified price {row.get('price')} ({row.get('currency')}), liquidity {row.get('liquidity_score', 0)}/100, and {len(findings)} agent reviews.",
                    supporting_evidence=[ev for f in findings for ev in f.evidence[:2]][:8],
                    fundamental_analysis=next((f.summary for f in findings if f.agent_id == "fundamental_analyst"), "Structured financial statements not yet ingested."),
                    technical_analysis=f"RSI14={row.get('rsi14', '--')}, Z-Score={row.get('z_score', '--')}, 1D Chg={row.get('change_pct', 0)}%.",
                    liquidity_considerations=f"Spread {row.get('spread_pct', 0):.2f}%, Bid Vol {row.get('bid_volume', 0)}, Ask Vol {row.get('ask_volume', 0)}, Liquidity {row.get('liquidity_score', 0)}/100.",
                    upside_scenario="Mean reversion toward 30d average / positive catalyst confirmation with improving order-book depth.",
                    downside_scenario="Continued illiquidity, spread widening, or adverse issuer/macro shock.",
                    key_risks=[ev for f in findings if f.agent_id == "risk_analyst" for ev in f.evidence] or ["Market liquidity and concentration risk."],
                    expected_horizon=str(row.get("signal_horizon") or "SWING (5-20d)"),
                    confidence_level="LOW" if disagreements else ("MEDIUM" if row.get("price") else "LOW"),
                    invalidation_conditions=["Verified price breaks below hard stop (-8%)", "Adverse official exchange cautionary announcement", "Spread widens above 8%"],
                    data_limitations=list(dict.fromkeys([lim for f in findings for lim in f.data_limitations])),
                )
                recommendations.append(asdict(rec))

        events.append({"timestamp": _utc_now(), "event": "REPORT_READY", "detail": f"Consolidated report ready with {len(recommendations)} recommendation(s)."})

        report = {
            "report_id": uuid.uuid4().hex[:10],
            "timestamp": _utc_now(),
            "question": question,
            "symbol": symbol,
            "agents_run": selected_ids,
            "findings": [asdict(f) for f in findings],
            "disagreements": disagreements,
            "recommendations": recommendations,
            "events": events,
            "data_snapshot_used": {
                "market_status": panel_data.get("market_status"),
                "last_updated": panel_data.get("last_updated"),
                "screener_count": len(panel_data.get("screener") or []),
                "news_count": len(panel_data.get("news") or []),
            },
        }

        if persist:
            self._save_report(report)
        return report

    def _save_report(self, report: dict[str, Any]) -> None:
        try:
            self.reports_path.parent.mkdir(parents=True, exist_ok=True)
            existing: list[dict[str, Any]] = []
            if self.reports_path.exists():
                parsed = json.loads(self.reports_path.read_text(encoding="utf-8"))
                if isinstance(parsed, list):
                    existing = parsed
            existing.append(report)
            self.reports_path.write_text(json.dumps(existing[-25:], indent=2), encoding="utf-8")
        except Exception:
            pass


def main(argv: list[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    question = " ".join(args).strip() or "Full desk analysis"
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import vfex
    store = vfex.VFEXStore()
    panel_data = vfex.format_panel_json(store)
    orch = IntelligenceOrchestrator()
    report = orch.run_analysis(question, panel_data, persist=True)
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
