"""
Test Suite for Deterministic Decimal-Safe Paper Trading Engine (paper_engine.py)
"""

from decimal import Decimal
import unittest

from paper_engine import DeterministicPaperEngine, FeeSchedule


class TestDeterministicPaperEngine(unittest.TestCase):
    def test_decimal_accounting_partial_fill_limit_cancel_and_risk_rules(self) -> None:
        eng = DeterministicPaperEngine()
        vp = eng.create_portfolio("p1", "100.00", max_position_pct="25.0", min_cash_reserve_pct="10.0")

        # 1. Stale quote rejected
        stale = eng.submit_order("p1", "a1", "v1", "VFEX", "INFR", "BUY", "MARKET", "10", {"price": "0.25", "timestamp": "2020-01-01T00:00:00+00:00"})
        self.assertEqual(stale["status"], "REJECTED")

        # 2. Unfilled LIMIT order stays PENDING, then can be CANCELLED
        pend = eng.submit_order("p1", "a1", "v1", "VFEX", "INFR", "BUY", "LIMIT", "20", {"price": "0.25", "best_ask": "0.26", "ask_volume": "100"}, limit_price="0.24")
        self.assertEqual(pend["status"], "PENDING")
        canc = eng.cancel_pending_order("p1", pend["order_id"])
        self.assertEqual(canc["status"], "CANCELLED")

        # 3. Partial fill capped by ask_volume=40 at verified best_ask=0.25 ($10.00 gross + $0.10 fee = $10.10)
        part = eng.submit_order("p1", "a1", "v1", "VFEX", "INFR", "BUY", "MARKET", "80", {"price": "0.24", "best_ask": "0.25", "ask_volume": "40"})
        self.assertEqual(part["status"], "PARTIALLY_FILLED")
        self.assertEqual(part["fill_quantity"], "40")
        self.assertEqual(part["remaining_quantity"], "40")
        self.assertEqual(vp.available_cash, Decimal("89.90"))

        # 4. Position limit (>25% = $25) blocks oversized buy
        over = eng.submit_order("p1", "a1", "v1", "VFEX", "INFR", "BUY", "MARKET", "100", {"price": "0.25", "best_ask": "0.25", "ask_volume": "200"})
        self.assertEqual(over["status"], "REJECTED")

        # 5. Dividend + Mark-to-Market
        eng.record_dividend("p1", "VFEX:INFR", "1.50")
        snap = eng.mark_to_market("p1", {"VFEX:INFR": "0.30"})
        self.assertEqual(snap["available_cash"], "91.40")
        self.assertEqual(snap["market_value"], "12.00")
        self.assertEqual(snap["total_equity"], "103.40")


if __name__ == "__main__":
    unittest.main()
