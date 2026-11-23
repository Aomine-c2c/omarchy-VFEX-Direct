"""
Test Suite for the 8-Agent Investment Intelligence Engine (intelligence.py)
Verifies routing, all 8 agents, disagreement detection, 16-field recommendation
schema, source citations, no-fabrication rules, and human-confirmation safety.
"""

import tempfile
import unittest
from pathlib import Path

from intelligence import IntelligenceOrchestrator


SAMPLE_PANEL_DATA = {
    "total_value": 100.0,
    "total_pnl": -8.0,
    "total_pnl_pct": -8.0,
    "wallet_cash_usd": 50.0,
    "wallet_cash_zwg": 200.0,
    "total_dividends": 2.5,
    "trading_goal": "hybrid",
    "market_status": "Open",
    "last_updated": "2026-11-23T09:00:00Z",
    "breadth": {"advancers": 8, "decliners": 4, "total": 12},
    "items": [
        {"symbol": "INFR", "currency": "USD", "shares": 100, "alloc_pct": 40.0, "pnl_pct": -8.0},
    ],
    "screener": [
        {
            "symbol": "INFR",
            "company_name": "Innscor Africa",
            "currency": "USD",
            "price": 0.24,
            "change_pct": -4.5,
            "liquidity_score": 62.0,
            "spread_pct": 6.5,
            "wide_spread": True,
            "rsi14": 34.0,
            "z_score": -1.8,
            "bid_volume": 500,
            "ask_volume": 200,
            "optimal_limit": 0.238,
            "signal_action": "BUY",
            "signal_score": 68,
            "signal_horizon": "SWING",
            "reasons": ["Oversold RSI", "Dip below 30d avg"],
        }
    ],
    "signals": [
        {
            "symbol": "INFR",
            "action": "BUY",
            "score": 68,
            "reasons": ["Oversold RSI", "Dip below 30d avg"],
        }
    ],
    "news": [
        {
            "title": "Innscor Africa declares interim dividend",
            "source": "VFEX Announcements",
            "url": "https://vfex.exchange/announcements/infr-div",
            "official": True,
            "symbols": ["INFR"],
            "tracked": True,
            "sentiment": "Bullish",
            "published_at": "2026-11-22T10:00:00Z",
        }
    ],
    "targets": {},
    "idle_cash_plan": {"total_deployable_usd": 50.0, "total_deployable_zwg": 200.0},
}


class TestIntelligenceEngine(unittest.TestCase):
    def test_full_desk_8_agents_disagreement_and_recommendation(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            orch = IntelligenceOrchestrator(reports_path=Path(td) / "reports.json")
            report = orch.run_analysis("Full desk analysis on INFR", SAMPLE_PANEL_DATA, symbol="INFR", persist=True)

            # All 8 agents ran
            self.assertEqual(len(report["agents_run"]), 8)
            self.assertEqual(len(report["findings"]), 8)

            # Disagreement detected: MarketResearcher/News/Opportunity say BUY while RiskAnalyst says CAUTION (wide spread + >25% concentration)
            self.assertGreaterEqual(len(report["disagreements"]), 1)

            # News citations contain original URL & timestamp
            news_f = next(f for f in report["findings"] if f["agent_id"] == "news_intelligence")
            self.assertGreaterEqual(len(news_f["citations"]), 1)
            self.assertTrue(news_f["citations"][0]["url"].startswith("https://"))

            # Fundamental Analyst explicitly reports data limitations (no fabricated financials)
            fund_f = next(f for f in report["findings"] if f["agent_id"] == "fundamental_analyst")
            self.assertGreaterEqual(len(fund_f["data_limitations"]), 1)

            # Trading Assistant NEVER executes autonomously
            tr_f = next(f for f in report["findings"] if f["agent_id"] == "trading_assistant")
            self.assertTrue(tr_f["metrics"]["requires_human_confirmation"])
            self.assertFalse(tr_f["metrics"]["executed"])
            self.assertIn("trade_ticket", tr_f["metrics"])

            # Structured Recommendation contains all required fields
            self.assertEqual(len(report["recommendations"]), 1)
            rec = report["recommendations"][0]
            for req_key in (
                "security", "exchange", "recommendation_type", "verified_price",
                "price_timestamp", "investment_thesis", "supporting_evidence",
                "fundamental_analysis", "technical_analysis", "liquidity_considerations",
                "upside_scenario", "downside_scenario", "key_risks",
                "expected_horizon", "confidence_level", "invalidation_conditions",
                "data_limitations",
            ):
                self.assertIn(req_key, rec)

            # Real activity events logged
            event_names = [e["event"] for e in report["events"]]
            self.assertIn("STARTED", event_names)
            self.assertIn("DISAGREEMENT_DETECTED", event_names)
            self.assertIn("REPORT_READY", event_names)


if __name__ == "__main__":
    unittest.main()
