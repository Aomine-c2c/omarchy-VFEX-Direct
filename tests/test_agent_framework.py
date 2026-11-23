"""
Test Suite for 9-Agent Investment Research & Paper Trading Framework (agent_framework.py)
"""

from decimal import Decimal
import unittest

from agent_framework import MultiAgentResearchFramework, ProposedPaperTrade


class TestNineAgentFramework(unittest.TestCase):
    def test_nine_agents_risk_veto_execution_and_no_unrealised_success(self) -> None:
        fw = MultiAgentResearchFramework()
        self.assertEqual(len(fw.agents), 9)
        for a in fw.agents.values():
            self.assertFalse(a.permissions.can_execute_real_trades)

        fw.engine.create_portfolio("sim1", "100.00")

        # Low-confidence trade vetoed by independent Risk Management Agent
        bad_prop = ProposedPaperTrade(
            security="INFR", exchange="VFEX", side="BUY", quantity="20", limit_price="0.25",
            investment_thesis="Test", supporting_evidence=["RSI=40"], expected_horizon="10d",
            risk_factors=["Wide spread"], invalidation_conditions=["<0.20"],
            confidence_score=0.20, strategy_version="v1.0",
        )
        vetoed = fw.submit_proposed_paper_trade("sim1", bad_prop, {"price": "0.25", "best_ask": "0.25", "spread_pct": 2.0})
        self.assertEqual(vetoed["status"], "VETOED_BY_RISK")

        # Valid trade approved by Risk Agent -> executed by DeterministicPaperEngine
        good_prop = ProposedPaperTrade(
            security="INFR", exchange="VFEX", side="BUY", quantity="20", limit_price="0.25",
            investment_thesis="Oversold dip", supporting_evidence=["RSI=31"], expected_horizon="15d",
            risk_factors=["Liquidity"], invalidation_conditions=["<0.21"],
            confidence_score=0.72, strategy_version="v1.0",
        )
        filled = fw.submit_proposed_paper_trade("sim1", good_prop, {"price": "0.24", "best_ask": "0.25", "ask_volume": "100", "spread_pct": 2.0})
        self.assertEqual(filled["status"], "FILLED")
        self.assertEqual(len(fw.immutable_journal), 2)

        # Cannot claim success from unrealised gains alone (0 closed trades)
        ev = fw.evaluate_strategy_success(Decimal("0.00"), Decimal("15.00"), closed_trades=0)
        self.assertFalse(ev["success_verified"])


if __name__ == "__main__":
    unittest.main()
