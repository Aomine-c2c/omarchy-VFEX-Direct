"""
Test Suite for Exchange Adapters, Provider Health & Safe Trade Lifecycle (exchange_adapters.py)
"""

import tempfile
import unittest
from pathlib import Path

from exchange_adapters import (
    CTradeAdapter,
    DataProviderManager,
    SecretStore,
    TradeWorkflowManager,
    VFEXDirectAdapter,
    ZSEDirectAdapter,
)


class TestExchangeAdaptersAndSafety(unittest.TestCase):
    def test_honest_capability_matrix(self) -> None:
        vfex = VFEXDirectAdapter().capabilities
        ctrade = CTradeAdapter().capabilities
        zse = ZSEDirectAdapter().capabilities

        self.assertTrue(ctrade.order_book)
        self.assertFalse(vfex.order_book)
        self.assertFalse(zse.order_book)
        # None of the 3 falsely claim automated order execution
        self.assertFalse(vfex.order_submission)
        self.assertFalse(ctrade.order_submission)
        self.assertFalse(zse.order_submission)

    def test_provider_fallback_never_labels_stale_as_live(self) -> None:
        mgr = DataProviderManager(max_retries=1)
        res = mgr.fetch_with_fallback(
            "VFEX",
            fetchers={"VFEX": lambda: (_ for _ in ()).throw(RuntimeError("timeout")), "CTRADE": lambda: (_ for _ in ()).throw(RuntimeError("503"))},
            cached_fallback={"INFR": 0.24},
            cached_at="2026-11-22T12:00:00Z",
        )
        self.assertTrue(res["ok"])
        self.assertEqual(res["freshness"], "STALE")
        self.assertEqual(res["provider"], "LOCAL_CACHE")
        self.assertEqual(mgr.health["VFEX"].status, "DEGRADED")

    def test_trade_safety_confirmation_idempotency_and_handoff(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            wf = TradeWorkflowManager(log_path=Path(td) / "audit.log")
            prev = wf.preview_order("VFEX", "INFR", "BUY", 100, 0.24, available_cash=50.0)
            self.assertTrue(prev["valid"])

            # Must refuse autonomous submission without explicit user confirmation
            with self.assertRaises(PermissionError):
                wf.submit_order(prev, confirmed_by_user=False)

            # Confirmed submission produces PORTAL_HANDOFF (never falsely EXECUTED)
            rec = wf.submit_order(prev, confirmed_by_user=True)
            self.assertEqual(rec["status"], "PORTAL_HANDOFF")
            self.assertFalse(rec["executed"])
            self.assertIn("vfexdirect.co.zw", rec["portal_url"])

            # Duplicate submission with same idempotency key is blocked
            with self.assertRaises(ValueError):
                wf.submit_order(prev, confirmed_by_user=True)

            # Audit log written
            self.assertTrue((Path(td) / "audit.log").exists())

    def test_atomic_secret_store_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            sec = SecretStore(fallback_path=Path(td) / ".secrets.json")
            sec._has_secret_tool = False
            mode = sec.set_secret("vfex_direct", "user@example.com", "s3cr3t")
            self.assertEqual(mode, "atomic-0600")
            st_mode = (Path(td) / ".secrets.json").stat().st_mode & 0o777
            self.assertEqual(st_mode, 0o600)


if __name__ == "__main__":
    unittest.main()
