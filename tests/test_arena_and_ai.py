"""
Test Suite for BYOK AI Providers, Realistic Simulated Execution & Account Isolation
"""

import tempfile
import unittest
from pathlib import Path

from ai_providers import AIProviderManager
from exchange_adapters import SecretStore
from paper_arena import PaperTradingArena


class TestAIProvidersAndPaperArena(unittest.TestCase):
    def test_byok_key_isolation_budget_and_fallback_audit(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            sec = SecretStore(fallback_path=Path(td) / ".sec.json")
            sec._has_secret_tool = False
            mgr = AIProviderManager(config_path=Path(td) / "ai.json", secret_store=sec)

            reg = mgr.register_api_key("openai", "sk-test-1234567890")
            self.assertTrue(reg["key_configured"])
            # Key is NEVER exposed in status_summary
            summary_str = str(mgr.status_summary())
            self.assertNotIn("sk-test-1234567890", summary_str)

            # Fallback from failing ollama -> openai records exact provenance
            res = mgr.invoke_with_fallback(
                "portfolio_analyst",
                executors={
                    "ollama": lambda m: (_ for _ in ()).throw(RuntimeError("offline")),
                    "openai": lambda m: ("OK analysis", 500, 200),
                },
            )
            self.assertEqual(res["provider"], "openai")
            self.assertTrue(res["fallback_used"])
            self.assertEqual(len(mgr.state["task_audit"]), 1)
            self.assertEqual(mgr.state["task_audit"][0]["provider"], "openai")

    def test_paper_arena_decision_journal_liquidity_partial_fill_and_isolation(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            arena = PaperTradingArena(state_path=Path(td) / "arena.json")
            self.assertTrue(arena.ISOLATED_SIMULATION_ONLY)

            # Blocked without pre-trade Decision Journal entry
            with self.assertRaises(PermissionError):
                arena.execute_simulated_order(
                    "value_v1", "nonexistent", "INFR", "VFEX", "BUY", 100, "MARKET", None,
                    {"price": 0.24, "best_ask": 0.25, "ask_volume": 40},
                )

            # Record mandatory immutable decision journal entry
            did = arena.record_decision("value_v1", {
                "intent": "BUY 100 INFR",
                "thesis": "Trading below 30d avg",
                "evidence": ["RSI=32"],
                "price": 0.24,
                "data_timestamp": "2026-11-23T09:00:00Z",
                "expected_outcome": "+8% in 20d",
                "risk_factors": ["Spread 4%"],
                "invalidation_conditions": ["Drop below 0.20"],
                "intended_horizon": "20d",
            })

            # Partial fill at best_ask (0.25, NOT last price 0.24) capped by ask_volume=40
            tx = arena.execute_simulated_order(
                "value_v1", did, "INFR", "VFEX", "BUY", 100, "MARKET", None,
                {"price": 0.24, "best_ask": 0.25, "ask_volume": 40},
            )
            self.assertEqual(tx["status"], "PARTIALLY_FILLED")
            self.assertEqual(tx["quantity"], 40.0)
            self.assertAlmostEqual(tx["execution_price"], 0.25, places=4)
            self.assertGreater(tx["fees"], 0.0)

            rankings = arena.compute_rankings({"INFR": 0.26})
            self.assertEqual(len(rankings), 5)


if __name__ == "__main__":
    unittest.main()
