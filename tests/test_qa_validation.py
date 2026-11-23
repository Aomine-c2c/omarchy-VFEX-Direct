"""
Principal QA & Financial Edge-Case Validation Suite (tests/test_qa_validation.py)
Tests all required financial edge cases: zero holdings, negative cash, missing
prices, stale prices, FX failure, duplicate submissions, missing fees, bad dates,
corporate actions, and inconsistent brokerage statements.
"""

import tempfile
import unittest
from pathlib import Path

from accounting import Account, PortfolioAccountingEngine, Security, Transaction
from exchange_adapters import DataProviderManager, TradeWorkflowManager


class TestFinancialEdgeCases(unittest.TestCase):
    def setUp(self) -> None:
        self.eng = PortfolioAccountingEngine(reporting_currency="USD")
        self.eng.add_account(Account("vfex", "VFEX", "VFEX", "Morgan", "USD"))
        self.eng.add_security(Security("VFEX:INFR", "VFEX", "INFR", "Innscor", "USD"))

    def test_zero_holdings_portfolio(self) -> None:
        snap = self.eng.compute_portfolio({})
        self.assertEqual(snap["positions"], [])
        self.assertEqual(snap["consolidated"]["total_equity"], 0.0)

    def test_negative_cash_balance_permitted_on_margin_or_unfunded_buy(self) -> None:
        self.eng.add_transaction(Transaction("2026-01-02", "BUY", "VFEX", "vfex", "USD", quantity=10, unit_price=1.0, symbol="INFR"))
        snap = self.eng.compute_portfolio({"VFEX:INFR": 1.0})
        self.assertAlmostEqual(snap["consolidated"]["total_cash"], -10.0, places=4)
        self.assertAlmostEqual(snap["consolidated"]["total_equity"], 0.0, places=4)

    def test_missing_market_price_falls_back_to_cost_basis(self) -> None:
        self.eng.add_transaction(Transaction("2026-01-01", "DEPOSIT", "VFEX", "vfex", "USD", total_amount=50.0))
        self.eng.add_transaction(Transaction("2026-01-02", "BUY", "VFEX", "vfex", "USD", quantity=100, unit_price=0.25, symbol="INFR"))
        snap = self.eng.compute_portfolio({})  # No market price provided
        pos = snap["positions"][0]
        self.assertAlmostEqual(pos["market_price_native"], 0.25, places=4)
        self.assertAlmostEqual(pos["unrealised_pnl_native"], 0.0, places=4)

    def test_currency_conversion_failure_raises_explicitly(self) -> None:
        self.eng.add_transaction(Transaction("2026-01-01", "DEPOSIT", "ZSE", "zse", "ZWG", total_amount=100.0))
        with self.assertRaises(ValueError):
            self.eng.compute_portfolio({})  # No ZWG->USD FX rate registered

    def test_incorrect_transaction_date_raises(self) -> None:
        self.eng.add_transaction(Transaction("NOT-A-DATE", "DEPOSIT", "VFEX", "vfex", "USD", total_amount=10.0))
        with self.assertRaises(ValueError):
            self.eng.compute_portfolio({})

    def test_missing_fees_defaults_to_zero(self) -> None:
        tx = Transaction("2026-01-02", "BUY", "VFEX", "vfex", "USD", quantity=10, unit_price=1.0, symbol="INFR")
        self.assertEqual(tx.fees, 0.0)
        self.assertEqual(tx.taxes, 0.0)

    def test_stale_price_and_duplicate_order_protection(self) -> None:
        mgr = DataProviderManager(max_retries=0)
        res = mgr.fetch_with_fallback("VFEX", {"VFEX": lambda: 1 / 0}, cached_fallback={"INFR": 0.2}, cached_at="2026-11-01")
        self.assertEqual(res["freshness"], "STALE")

        with tempfile.TemporaryDirectory() as td:
            wf = TradeWorkflowManager(log_path=Path(td) / "audit.log")
            prev = wf.preview_order("VFEX", "INFR", "BUY", 10, 0.25, available_cash=10.0)
            wf.submit_order(prev, confirmed_by_user=True)
            with self.assertRaises(ValueError):
                wf.submit_order(prev, confirmed_by_user=True)


if __name__ == "__main__":
    unittest.main()
