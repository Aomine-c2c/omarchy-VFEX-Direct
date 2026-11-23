"""
Test Suite for Complete Investment Planning Engine (planner.py)
Verifies goals, contribution presets ($5-$100), Bull/Base/Bear scenarios,
allocation & concentration, non-destructive what-if simulator, rebalancing, and calendar.
"""

import unittest

from planner import (
    analyze_allocation,
    build_planner_payload,
    compute_rebalancing,
    compute_required_monthly,
    run_scenarios,
    simulate_contributions,
    simulate_what_if,
)


SAMPLE_PANEL = {
    "total_value": 100.0,
    "wallet_cash_usd": 20.0,
    "items": [{"symbol": "INFR", "currency": "USD", "value": 100.0}],
    "targets": {"INFR": 50.0, "SIM": 50.0},
    "screener": [
        {"symbol": "INFR", "currency": "USD", "liquidity_score": 60, "wide_spread": False},
        {"symbol": "SIM", "currency": "USD", "liquidity_score": 25, "wide_spread": True, "spread_pct": 8.0},
    ],
    "news": [{"date": "2026-11-22", "title": "INFR declares dividend", "official": True}],
}


class TestPlannerEngine(unittest.TestCase):
    def test_required_monthly_and_contributions(self) -> None:
        req = compute_required_monthly(100.0, 1000.0, years=5.0, annual_cagr_pct=10.0)
        self.assertGreater(req, 5.0)
        sim = simulate_contributions(100.0, 20.0, 50.0, "monthly", years=5, annual_cagr_pct=10.0)
        self.assertGreater(sim["projected_end_value"], 3000.0)
        self.assertIn("HYPOTHETICAL", sim["hypothetical_disclaimer"])

    def test_scenarios_ordering(self) -> None:
        sc = run_scenarios(100.0, 20.0, 50.0, years=5)
        self.assertGreater(sc["bull"]["projected_end_value"], sc["base"]["projected_end_value"])
        self.assertGreater(sc["base"]["projected_end_value"], sc["bear"]["projected_end_value"])

    def test_what_if_is_non_destructive(self) -> None:
        res = simulate_what_if(SAMPLE_PANEL, {"type": "price_shock", "symbol": "INFR", "shock_pct": -10.0})
        self.assertAlmostEqual(res["after_invested_usd"], 90.0, places=2)
        # Original panel untouched
        self.assertEqual(SAMPLE_PANEL["items"][0]["value"], 100.0)

    def test_allocation_rebalancing_and_payload(self) -> None:
        alloc = analyze_allocation(SAMPLE_PANEL, concentration_limit_pct=25.0)
        self.assertEqual(len(alloc["concentration_flags"]), 1)
        reb = compute_rebalancing(SAMPLE_PANEL)
        self.assertEqual(len(reb["adjustments"]), 2)
        sim_adj = next(a for a in reb["adjustments"] if a["symbol"] == "SIM")
        self.assertEqual(sim_adj["action"], "BUY")
        self.assertGreaterEqual(len(sim_adj["risks"]), 1)

        payload = build_planner_payload(SAMPLE_PANEL)
        self.assertIn("$5", payload["contribution_presets_5y"])
        self.assertIn("$100", payload["contribution_presets_5y"])
        self.assertGreaterEqual(len(payload["calendar"]), 2)


if __name__ == "__main__":
    unittest.main()
