#!/usr/bin/env python3
"""
NOTHING Investment Terminal — 9-Agent Research & Paper Trading Framework
------------------------------------------------------------------------
9 specialised agents with explicit permissions, risk limits, immutable decision
journal, independent Risk Management validation, engine-only virtual execution,
and versioned out-of-sample learning (never claiming success from unrealised
gains alone; never accessing real brokerage execution).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from paper_engine import DeterministicPaperEngine


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class AgentPermissions:
    read_market_data: bool = True
    read_paper_portfolio: bool = True
    read_live_portfolio: bool = False
    can_propose_paper_trades: bool = False
    can_veto_paper_trades: bool = False
    can_execute_real_trades: bool = False  # ALWAYS False for paper/research agents


@dataclass
class AgentProfile:
    agent_id: str
    name: str
    assigned_model: str
    responsibilities: list[str]
    instructions: str
    permissions: AgentPermissions
    risk_limits: dict[str, Any] = field(default_factory=dict)
    decision_history: list[dict[str, Any]] = field(default_factory=list)
    performance_records: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class ProposedPaperTrade:
    security: str
    exchange: str
    side: str  # BUY | SELL
    quantity: str
    limit_price: str | None
    investment_thesis: str
    supporting_evidence: list[str]
    expected_horizon: str
    risk_factors: list[str]
    invalidation_conditions: list[str]
    confidence_score: float  # 0.0 .. 1.0
    strategy_version: str
    agent_id: str = "paper_trading_agent"
    proposal_id: str = field(default_factory=lambda: uuid.uuid4().hex[:10])
    proposed_at: str = field(default_factory=_utc_now)


def build_nine_agents() -> dict[str, AgentProfile]:
    specs = [
        ("fundamental_analyst", "FUNDAMENTAL ANALYST", "claude-3-5-sonnet-latest", ["Financial statements", "Valuation", "Quality"], AgentPermissions()),
        ("technical_analyst", "TECHNICAL ANALYST", "gemini-2.5-flash", ["Price trends", "RSI/Z-Score", "Support/Resistance"], AgentPermissions()),
        ("news_intelligence_agent", "NEWS INTELLIGENCE AGENT", "gemini-2.5-flash", ["Exchange announcements", "Macro/RBZ", "Deduplication"], AgentPermissions()),
        ("portfolio_manager", "PORTFOLIO MANAGER", "gpt-4o-mini", ["Allocation", "Rebalancing", "Cash deployment"], AgentPermissions(read_live_portfolio=True)),
        ("risk_management_agent", "RISK MANAGEMENT AGENT", "claude-3-5-sonnet-latest", ["Independent trade validation", "Drawdown & liquidity guard"], AgentPermissions(can_veto_paper_trades=True), {"max_confidence_floor": 0.45, "max_spread_pct": 8.0}),
        ("dividend_analyst", "DIVIDEND ANALYST", "gpt-4o-mini", ["Dividend yield", "Payout sustainability", "Ex-div calendar"], AgentPermissions()),
        ("market_scanner", "MARKET SCANNER", "llama3.1:8b", ["VFEX/ZSE/C-TRADE screening", "Unusual activity"], AgentPermissions()),
        ("paper_trading_agent", "PAPER TRADING AGENT", "gemini-2.5-flash", ["Propose virtual trades", "Maintain decision journal"], AgentPermissions(can_propose_paper_trades=True)),
        ("chief_investment_strategist", "CHIEF INVESTMENT STRATEGIST", "claude-3-5-sonnet-latest", ["Synthesize 8 specialists", "Approve strategy versions"], AgentPermissions(read_live_portfolio=True)),
    ]
    out: dict[str, AgentProfile] = {}
    for row in specs:
        aid, name, model, resp, perms = row[:5]
        rlim = row[5] if len(row) > 5 else {}
        out[aid] = AgentProfile(
            agent_id=aid,
            name=name,
            assigned_model=model,
            responsibilities=resp,
            instructions=f"Act as {name} for VFEX, ZSE, and C-TRADE. Never fabricate data or execute real trades.",
            permissions=perms,
            risk_limits=rlim,
        )
    return out


class MultiAgentResearchFramework:
    """Coordinates all 9 agents, independent Risk validation, and Paper Engine execution."""

    def __init__(self, paper_engine: DeterministicPaperEngine | None = None) -> None:
        self.agents = build_nine_agents()
        self.engine = paper_engine or DeterministicPaperEngine()
        self.immutable_journal: list[dict[str, Any]] = []
        self.strategy_versions: list[dict[str, Any]] = [{"version": "v1.0", "status": "ACTIVE", "created_at": _utc_now()}]

    def validate_trade_with_risk_agent(self, proposal: ProposedPaperTrade, quote: dict[str, Any]) -> tuple[bool, list[str]]:
        """Independent Risk Management Agent validation."""
        risk_agent = self.agents["risk_management_agent"]
        reasons: list[str] = []
        if proposal.confidence_score < float(risk_agent.risk_limits.get("max_confidence_floor", 0.45)):
            reasons.append(f"Confidence {proposal.confidence_score:.2f} below risk floor.")
        spread = float(quote.get("spread_pct") or 0.0)
        if spread > float(risk_agent.risk_limits.get("max_spread_pct", 8.0)):
            reasons.append(f"Spread {spread:.2f}% exceeds max allowed risk limit.")
        if not proposal.invalidation_conditions:
            reasons.append("Missing invalidation conditions.")
        approved = len(reasons) == 0
        risk_agent.decision_history.append({
            "timestamp": _utc_now(),
            "proposal_id": proposal.proposal_id,
            "approved": approved,
            "reasons": reasons,
        })
        return approved, reasons

    def submit_proposed_paper_trade(
        self,
        portfolio_id: str,
        proposal: ProposedPaperTrade,
        quote: dict[str, Any],
        order_type: str = "LIMIT",
    ) -> dict[str, Any]:
        # Enforce strict permission check: paper agent can NEVER access real trading
        pa = self.agents["paper_trading_agent"]
        if pa.permissions.can_execute_real_trades:
            raise PermissionError("Paper trading agent must never have real trading permissions.")

        # 1. Record immutable pre-trade journal entry
        journal_entry = {
            "journal_id": uuid.uuid4().hex[:10],
            "immutable": True,
            "recorded_at": _utc_now(),
            "proposal": asdict(proposal),
        }
        self.immutable_journal.append(journal_entry)
        pa.decision_history.append(journal_entry)

        # 2. Independent Risk Management Agent validation
        approved, veto_reasons = self.validate_trade_with_risk_agent(proposal, quote)
        if not approved:
            return {"status": "VETOED_BY_RISK", "reasons": veto_reasons, "proposal_id": proposal.proposal_id}

        # 3. Paper Trading Engine alone controls virtual execution
        return self.engine.submit_order(
            portfolio_id=portfolio_id,
            agent_id=proposal.agent_id,
            strategy_version=proposal.strategy_version,
            exchange=proposal.exchange,
            security=proposal.security,
            side=proposal.side,
            order_type=order_type,
            quantity=proposal.quantity,
            quote=quote,
            limit_price=proposal.limit_price,
        )

    @staticmethod
    def evaluate_strategy_success(realised_pnl: Decimal, unrealised_pnl: Decimal, closed_trades: int) -> dict[str, Any]:
        """Never allow agents to claim success based on unrealised gains alone."""
        if closed_trades < 1:
            return {
                "success_verified": False,
                "reason": "Cannot claim strategy success from unrealised gains alone; at least 1 closed realised trade is required.",
                "realised_pnl": str(realised_pnl),
                "unrealised_pnl": str(unrealised_pnl),
            }
        return {
            "success_verified": realised_pnl > Decimal("0"),
            "reason": "Evaluated on realised closed-trade performance.",
            "realised_pnl": str(realised_pnl),
            "unrealised_pnl": str(unrealised_pnl),
        }

    def propose_strategy_version(self, new_version: str, rationale: str) -> dict[str, Any]:
        entry = {"version": new_version, "status": "PROPOSED_FOR_OOS_VALIDATION", "rationale": rationale, "created_at": _utc_now()}
        self.strategy_versions.append(entry)
        return entry
