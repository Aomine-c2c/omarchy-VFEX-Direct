"""
Test Suite for Isolated Browser-Based Account Connector (browser_connector.py)
Verifies per-platform adapters, isolated 0700 profiles, read-only enforcement,
deduplication, manual CSV statement fallback, and immediate disconnect/wipe.
"""

import tempfile
import unittest
from pathlib import Path

from browser_connector import BrowserConnectorService


class TestBrowserConnector(unittest.TestCase):
    def test_profile_isolation_dedup_csv_fallback_and_disconnect(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            svc = BrowserConnectorService(base_dir=Path(td) / "bc")
            self.assertTrue(svc.READ_ONLY_ONLY)

            # Prepare isolated user-controlled login profile (0700)
            sess = svc.launch_user_login_session("VFEX", "acct_1")
            self.assertTrue(sess["read_only"])
            prof = Path(sess["profile_dir"])
            self.assertTrue(prof.exists())
            self.assertEqual(prof.stat().st_mode & 0o777, 0o700)

            # Manual CSV statement fallback + duplicate prevention
            csv_data = "id,date,type,symbol,shares,price,amount,currency\nTX1,2026-11-20,BUY,INFR,50,0.24,12.0,USD\nTX1,2026-11-20,BUY,INFR,50,0.24,12.0,USD\n"
            res = svc.import_manual_csv_statement("VFEX", "acct_1", csv_data)
            self.assertEqual(res["added"], 1)
            self.assertEqual(res["duplicates_skipped"], 1)

            # Immediate disconnect wipes profile
            disc = svc.disconnect("VFEX", "acct_1")
            self.assertTrue(disc["disconnected"])
            self.assertFalse(prof.exists())


if __name__ == "__main__":
    unittest.main()
