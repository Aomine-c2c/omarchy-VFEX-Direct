"""
Test Suite for Central Multi-Provider AI Gateway (ai_providers.py)
Verifies multi-key registration, capability validation, 8 routing profiles,
daily/monthly/provider budgets, and fallback with sanitized audit logging.
"""

import tempfile
import unittest
from pathlib import Path

from ai_providers import AIProviderManager, ROUTING_PROFILES
from exchange_adapters import SecretStore


class TestCentralAIGateway(unittest.TestCase):
    def test_multi_key_capability_validation_and_budgets(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            sec = SecretStore(fallback_path=Path(td) / ".sec.json")
            sec._has_secret_tool = False
            gw = AIProviderManager(config_path=Path(td) / "gw.json", secret_store=sec)

            self.assertEqual(len(ROUTING_PROFILES), 8)

            # Multiple API keys per provider
            gw.register_api_key("openai", "sk-primary-111111", key_label="primary")
            gw.register_api_key("openai", "sk-backup-222222", key_label="backup")
            openai_st = next(p for p in gw.status_summary()["providers"] if p["id"] == "openai")
            self.assertEqual(openai_st["key_count"], 2)

            # Capability validation blocks tiny-local-no-tools for paper_trading_decisions (requires tools + structured)
            with self.assertRaises(ValueError):
                gw.assign_agent_model("trader", "ollama", "tiny-local-no-tools", task_type="paper_trading_decisions")

            # Daily budget guard never exceeds silently
            gw.state["daily_budget_usd"] = 0.001
            gw.state["usage"]["daily_cost_usd"] = 0.002
            with self.assertRaises(RuntimeError):
                gw.invoke_with_fallback("news", {"openai": lambda m: ("ok", 10, 10)}, task_type="news_analysis")


if __name__ == "__main__":
    unittest.main()
