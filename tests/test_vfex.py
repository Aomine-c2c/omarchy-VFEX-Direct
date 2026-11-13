import tempfile
import unittest
from pathlib import Path

from vfex import VFEXStore, format_waybar


class TestVFEXStore(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.store = VFEXStore(config_dir=Path(self.tmp.name))

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_buy_sell_and_pnl(self) -> None:
        self.store.buy("INSC", 100, 0.40)
        self.store.buy("INSC", 100, 0.60)
        self.store.set_price("INSC", 0.55)

        summary = self.store.portfolio_summary()
        self.assertEqual(len(summary["items"]), 1)
        item = summary["items"][0]
        self.assertAlmostEqual(item["avg_cost"], 0.50)
        self.assertAlmostEqual(item["value"], 110.0)
        self.assertAlmostEqual(item["pnl"], 10.0)

        self.store.sell("INSC", 200)
        self.assertEqual(self.store.portfolio_summary()["items"], [])

    def test_alerts(self) -> None:
        self.store.add_alert("SIM", "above", 0.35)
        self.store.set_price("SIM", 0.36)
        hits = self.store.check_alerts(notify=False)
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0]["symbol"], "SIM")
        # Already triggered, should not fire again
        self.assertEqual(self.store.check_alerts(notify=False), [])

    def test_waybar_output(self) -> None:
        self.store.buy("PHL", 50, 0.20)
        self.store.set_price("PHL", 0.25)
        wb = format_waybar(self.store)
        self.assertIn("VFEX $12.50", wb["text"])
        self.assertEqual(wb["class"], "profit")
        self.assertIn("PHL", wb["tooltip"])


if __name__ == "__main__":
    unittest.main()
