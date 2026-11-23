"""
Worked Test Suite for Multi-Market Investment Accounting Engine (accounting.py)
Covers all 10 required worked scenarios across VFEX, ZSE, and C-TRADE.
"""

from datetime import date
import unittest

from accounting import (
    Account,
    DividendRecord,
    PortfolioAccountingEngine,
    Security,
    Transaction,
    make_security_id,
)


class TestPortfolioAccountingEngine(unittest.TestCase):
    def setUp(self) -> None:
        self.eng = PortfolioAccountingEngine(reporting_currency="USD")
        self.eng.add_account(Account("vfex_main", "VFEX Direct", "VFEX", "Morgan & Co", "USD"))
        self.eng.add_account(Account("zse_ctrade", "C-TRADE ZSE", "ZSE", "C-TRADE", "ZWG"))
        self.eng.add_security(Security("VFEX:INFR", "VFEX", "INFR", "Innscor Africa", "USD", sector="Consumer"))
        self.eng.add_security(Security("ZSE:INFR", "ZSE", "INFR", "Hypothetical ZSE Counter", "ZWG", sector="Industrial"))
        self.eng.add_security(Security("ZSE:DLTA", "ZSE", "DLTA", "Delta Corp", "ZWG", sector="Beverages"))

    def test_01_and_02_buy_and_buy_more_at_different_price(self) -> None:
        """Buying shares and buying more at a different price with capitalized fees."""
        self.eng.add_transaction(Transaction("2026-01-01", "DEPOSIT", "VFEX", "vfex_main", "USD", total_amount=100.0))
        # Buy 100 INFR @ $0.20 + $0.25 fee -> cost $20.25 ($0.2025/sh)
        self.eng.add_transaction(Transaction("2026-01-02", "BUY", "VFEX", "vfex_main", "USD", quantity=100, unit_price=0.20, fees=0.25, symbol="INFR"))
        # Buy 100 more INFR @ $0.30 + $0.35 fee -> cost $30.35 ($0.3035/sh)
        self.eng.add_transaction(Transaction("2026-01-10", "BUY", "VFEX", "vfex_main", "USD", quantity=100, unit_price=0.30, fees=0.35, symbol="INFR"))

        snap = self.eng.compute_portfolio({"VFEX:INFR": 0.30}, as_of_date="2026-01-15")
        pos = snap["positions"][0]
        self.assertEqual(pos["quantity"], 200.0)
        self.assertAlmostEqual(pos["cost_basis_native"], 50.60, places=4)
        self.assertAlmostEqual(pos["avg_cost_native"], 0.2530, places=4)
        self.assertAlmostEqual(pos["market_value_native"], 60.00, places=4)
        self.assertAlmostEqual(pos["unrealised_pnl_native"], 9.40, places=4)
        self.assertAlmostEqual(snap["consolidated"]["total_cash"], 49.40, places=4)
        self.assertAlmostEqual(snap["consolidated"]["fees_paid"], 0.60, places=4)

    def test_03_and_04_partial_and_full_sales_fifo(self) -> None:
        """Partial sale consumes earliest FIFO lot; full sale closes position completely."""
        self.eng.add_transaction(Transaction("2026-01-01", "DEPOSIT", "VFEX", "vfex_main", "USD", total_amount=100.0))
        self.eng.add_transaction(Transaction("2026-01-02", "BUY", "VFEX", "vfex_main", "USD", quantity=100, unit_price=0.20, fees=0.0, symbol="INFR"))
        self.eng.add_transaction(Transaction("2026-01-05", "BUY", "VFEX", "vfex_main", "USD", quantity=100, unit_price=0.30, fees=0.0, symbol="INFR"))
        # Partial sale: sell 120 @ $0.40, fee $0.50 -> net proceeds $47.50
        # FIFO cost: 100 * 0.20 + 20 * 0.30 = $26.00 -> realised = $21.50
        self.eng.add_transaction(Transaction("2026-01-15", "SELL", "VFEX", "vfex_main", "USD", quantity=120, unit_price=0.40, fees=0.50, symbol="INFR"))

        snap1 = self.eng.compute_portfolio({"VFEX:INFR": 0.40}, as_of_date="2026-01-16")
        self.assertEqual(len(snap1["positions"]), 1)
        self.assertEqual(snap1["positions"][0]["quantity"], 80.0)
        self.assertAlmostEqual(snap1["positions"][0]["avg_cost_native"], 0.30, places=4)
        self.assertAlmostEqual(snap1["consolidated"]["realised_price_pnl"], 21.50, places=4)

        # Full sale: sell remaining 80 @ $0.35, fee $0.20 -> net $27.80, cost $24.00 -> +$3.80
        self.eng.add_transaction(Transaction("2026-01-20", "SELL", "VFEX", "vfex_main", "USD", quantity=80, unit_price=0.35, fees=0.20, symbol="INFR"))
        snap2 = self.eng.compute_portfolio({"VFEX:INFR": 0.35}, as_of_date="2026-01-21")
        self.assertEqual(len(snap2["positions"]), 0)
        self.assertAlmostEqual(snap2["consolidated"]["realised_price_pnl"], 25.30, places=4)

    def test_05_dividends_declared_expected_received(self) -> None:
        """Distinguish declared, expected, and received dividends + withholding tax."""
        self.eng.add_dividend(DividendRecord("VFEX:INFR", "VFEX", "INFR", "USD", "2026-02-01", "2026-02-10", "2026-02-12", "2026-02-20", gross_amount=10.0, withholding_tax=1.0, status="RECEIVED"))
        self.eng.add_dividend(DividendRecord("VFEX:INFR", "VFEX", "INFR", "USD", "2026-03-01", "2026-03-10", "2026-03-12", "2026-03-20", gross_amount=5.0, withholding_tax=0.5, status="EXPECTED"))
        self.eng.add_dividend(DividendRecord("VFEX:INFR", "VFEX", "INFR", "USD", "2026-04-01", "2026-04-10", "2026-04-12", "2026-04-20", gross_amount=4.0, withholding_tax=0.0, status="DECLARED"))
        # Record the received cash dividend in ledger
        self.eng.add_transaction(Transaction("2026-02-20", "DIVIDEND", "VFEX", "vfex_main", "USD", total_amount=10.0, taxes=1.0, symbol="INFR"))

        dsum = self.eng.dividend_summary()
        self.assertAlmostEqual(dsum["received_reporting"], 9.0, places=4)
        self.assertAlmostEqual(dsum["expected_reporting"], 4.5, places=4)
        self.assertAlmostEqual(dsum["declared_reporting"], 4.0, places=4)

        snap = self.eng.compute_portfolio({}, as_of_date="2026-02-25")
        self.assertAlmostEqual(snap["consolidated"]["dividend_income"], 9.0, places=4)
        self.assertAlmostEqual(snap["consolidated"]["total_cash"], 9.0, places=4)

    def test_06_and_07_deposits_withdrawals_and_fees_not_investment_gain(self) -> None:
        """Deposits & withdrawals change cash/net_deposits without creating fake investment return."""
        self.eng.add_transaction(Transaction("2026-01-01", "DEPOSIT", "VFEX", "vfex_main", "USD", total_amount=500.0))
        self.eng.add_transaction(Transaction("2026-01-10", "WITHDRAWAL", "VFEX", "vfex_main", "USD", total_amount=150.0, fees=2.0))
        snap = self.eng.compute_portfolio({}, as_of_date="2026-01-15")
        self.assertAlmostEqual(snap["consolidated"]["net_deposits"], 350.0, places=4)
        self.assertAlmostEqual(snap["consolidated"]["total_cash"], 348.0, places=4)
        self.assertAlmostEqual(snap["consolidated"]["total_return"], 0.0, places=4)
        self.assertAlmostEqual(snap["consolidated"]["fees_paid"], 2.0, places=4)

    def test_08_multi_currency_and_unique_security_ids(self) -> None:
        """Never conflate same symbol across VFEX (USD) & ZSE (ZWG); separate Price Return from FX Return."""
        # 1 ZWG = 0.04 USD (25 ZWG/USD) on Jan 1; depreciates to 0.02 USD (50 ZWG/USD) on Feb 1
        self.eng.add_fx_rate("2026-01-01", "ZWG", "USD", 0.04)
        self.eng.add_fx_rate("2026-02-01", "ZWG", "USD", 0.02)

        self.eng.add_transaction(Transaction("2026-01-01", "DEPOSIT", "VFEX", "vfex_main", "USD", total_amount=50.0))
        self.eng.add_transaction(Transaction("2026-01-01", "BUY", "VFEX", "vfex_main", "USD", quantity=100, unit_price=0.25, symbol="INFR"))

        self.eng.add_transaction(Transaction("2026-01-01", "DEPOSIT", "ZSE", "zse_ctrade", "ZWG", total_amount=1000.0))
        # Buy 100 ZSE:INFR @ 10 ZWG = 1000 ZWG (worth $40 USD at acquisition)
        self.eng.add_transaction(Transaction("2026-01-01", "BUY", "ZSE", "zse_ctrade", "ZWG", quantity=100, unit_price=10.0, symbol="INFR"))

        # On Feb 1: ZSE:INFR rises +50% in ZWG (10 -> 15 ZWG, worth 1500 ZWG * 0.02 = $30 USD)
        # Native price gain = +500 ZWG -> at 0.02 = +$10 USD price return
        # FX loss on original 1000 ZWG cost = 1000 * (0.02 - 0.04) = -$20 USD FX return
        # Total USD unrealised on ZSE:INFR = $30 - $40 = -$10 (+$10 price - $20 FX)
        snap = self.eng.compute_portfolio({"VFEX:INFR": 0.25, "ZSE:INFR": 15.0}, as_of_date="2026-02-01")
        self.assertEqual(len(snap["positions"]), 2)
        sec_ids = {p["security_id"] for p in snap["positions"]}
        self.assertEqual(sec_ids, {"VFEX:INFR", "ZSE:INFR"})
        zse_pos = next(p for p in snap["positions"] if p["security_id"] == "ZSE:INFR")
        self.assertAlmostEqual(zse_pos["unrealised_pnl_native"], 500.0, places=4)
        self.assertAlmostEqual(zse_pos["unrealised_price_reporting"], 10.0, places=4)
        self.assertAlmostEqual(zse_pos["unrealised_fx_reporting"], -20.0, places=4)
        self.assertIn("USD", snap["by_currency"])
        self.assertIn("ZWG", snap["by_currency"])

    def test_09_and_10_corporate_actions_reconciliation_and_immutability(self) -> None:
        """Stock split, rights issue, reconciliation mismatch detection, and RECONCILED immutability guard."""
        self.eng.add_transaction(Transaction("2026-01-01", "DEPOSIT", "VFEX", "vfex_main", "USD", total_amount=200.0))
        t_buy = self.eng.add_transaction(Transaction("2026-01-02", "BUY", "VFEX", "vfex_main", "USD", quantity=100, unit_price=1.00, symbol="INFR"))
        self.eng.mark_reconciled(t_buy.transaction_id)

        # Immutability guard: cannot silently edit RECONCILED transaction
        with self.assertRaises(ValueError):
            self.eng.update_transaction(t_buy.transaction_id, quantity=999)

        # 2-for-1 stock split -> 200 shares @ $0.50 cost basis
        self.eng.add_transaction(Transaction("2026-01-15", "SPLIT", "VFEX", "vfex_main", "USD", quantity=2.0, symbol="INFR"))
        # Rights issue: 50 new shares @ $0.40
        self.eng.add_transaction(Transaction("2026-01-20", "RIGHTS_ISSUE", "VFEX", "vfex_main", "USD", quantity=50, unit_price=0.40, symbol="INFR"))

        snap = self.eng.compute_portfolio({"VFEX:INFR": 0.60}, as_of_date="2026-01-25")
        pos = snap["positions"][0]
        self.assertEqual(pos["quantity"], 250.0)
        self.assertAlmostEqual(pos["cost_basis_native"], 120.0, places=4)
        self.assertAlmostEqual(pos["market_value_native"], 150.0, places=4)

        # Reconciliation: external statement says 260 shares & $80 cash (internal is 250 shares & $80 cash)
        recon = self.eng.reconcile_against_statement(
            external_holdings={("vfex_main", "VFEX:INFR"): 260.0},
            external_cash={("vfex_main", "USD"): 80.0},
            market_prices={"VFEX:INFR": 0.60},
        )
        self.assertFalse(recon["reconciled"])
        self.assertEqual(recon["discrepancy_count"], 1)
        self.assertEqual(recon["discrepancies"][0]["kind"], "QUANTITY_MISMATCH")
        self.assertAlmostEqual(recon["discrepancies"][0]["delta"], 10.0, places=4)

        # Insights & concentration risk (>25%)
        insights = self.eng.generate_insights({"VFEX:INFR": 0.60}, concentration_limit_pct=25.0)
        self.assertEqual(len(insights["concentration_risks"]), 1)
        self.assertEqual(insights["concentration_risks"][0]["security_id"], "VFEX:INFR")

    def test_twr_and_xirr(self) -> None:
        """Verify Time-Weighted Return (TWR) and Money-Weighted Return (XIRR)."""
        twr = PortfolioAccountingEngine.compute_twr([
            {"start_value": 100.0, "end_value": 110.0, "net_cashflow": 0.0},   # +10%
            {"start_value": 110.0, "end_value": 231.0, "net_cashflow": 100.0}, # +19.09%? wait: (231-100-110)/110 = +19.09%
        ])
        self.assertIsNotNone(twr)
        self.assertGreater(twr, 20.0)

        xirr = PortfolioAccountingEngine.compute_xirr([
            (date(2025, 1, 1), -100.0),
            (date(2026, 1, 1), 115.0),
        ])
        self.assertAlmostEqual(xirr, 15.0, places=1)


if __name__ == "__main__":
    unittest.main()
