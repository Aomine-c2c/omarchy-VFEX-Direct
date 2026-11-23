"""
Test Suite for Omarchy Desktop Notifications & TUI (desktop_notify.py, vfex_tui.py)
"""

import tempfile
import unittest
from pathlib import Path

from desktop_notify import DesktopNotifier
from vfex_tui import render_tab_lines


class TestDesktopAndTUI(unittest.TestCase):
    def test_quiet_hours_and_deduplication(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            n = DesktopNotifier(dedup_path=Path(td) / "dedup.json", quiet_start_hour=22, quiet_end_hour=7)
            # Non-critical suppressed during quiet hours (23:00)
            r1 = n.send("price_change", "INFR +5%", "Moved up", now_hour=23, dry_run=True)
            self.assertFalse(r1["sent"])
            self.assertEqual(r1["reason"], "quiet_hours")

            # Critical alert still passes during quiet hours
            r2 = n.send("threshold_breach", "Stop Hit", "INFR hit stop", now_hour=23, dry_run=True)
            self.assertTrue(r2["sent"])

            # Duplicate critical alert within TTL is suppressed
            r3 = n.send("threshold_breach", "Stop Hit", "INFR hit stop", now_hour=23, dry_run=True)
            self.assertFalse(r3["sent"])
            self.assertEqual(r3["reason"], "duplicate")

    def test_tui_tab_rendering(self) -> None:
        sample = {"total_value": 50.0, "total_pnl": 5.0, "total_pnl_pct": 11.1, "wallet_cash_usd": 10.0, "wallet_cash_zwg": 0.0, "items": [], "screener": [], "watchlist": [], "news": [], "paper_agent": {}}
        for tab in (1, 2, 3, 4, 5, 6):
            lines = render_tab_lines(tab, sample)
            self.assertIsInstance(lines, list)


if __name__ == "__main__":
    unittest.main()
