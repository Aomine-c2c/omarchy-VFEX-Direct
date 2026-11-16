import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from vfex import VFEXStore, build_parser, fetch_vfex_prices, format_panel_json, format_waybar, get_last_updated_label, get_market_status


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

        # Persistent triggered/active alert formatting & removal
        self.store.add_alert("INFR", "below", 0.20)
        self.store.set_price("INFR", 0.25, date="2026-11-13")
        self.store.state["last_fetch_date"] = datetime.now(timezone.utc).date().isoformat()
        panel = format_panel_json(self.store)
        self.assertEqual(len(panel["triggered_alerts"]), 1)
        self.assertEqual(len(panel["active_alerts"]), 1)
        self.assertIn("SIM above $0.3500", panel["alerts"][0])

        self.assertEqual(self.store.clear_triggered_alerts(), 1)
        self.assertEqual(len(self.store.state["alerts"]), 1)
        self.store.remove_alert(0)
        self.assertEqual(self.store.state["alerts"], [])

    def test_waybar_output(self) -> None:
        self.store.buy("PHL", 50, 0.20)
        self.store.set_price("PHL", 0.25)
        wb = format_waybar(self.store)
        self.assertIn("VFEX $12.50", wb["text"])
        self.assertEqual(wb["class"], "profit")
        self.assertIn("PHL", wb["tooltip"])

    def test_buy_recommendations_and_csv_import(self) -> None:
        csv_path = Path(self.tmp.name) / "prices.csv"
        csv_path.write_text("symbol,price\nINSC,0.50\nSIM,0.30\n", encoding="utf-8")
        count = self.store.import_csv(csv_path)
        self.assertEqual(count, 2)
        self.store.state["history"]["INSC"] = [
            {"date": "2026-11-11", "price": 0.60},
            {"date": "2026-11-12", "price": 0.60},
            {"date": "2026-11-13", "price": 0.50},
        ]
        self.store.set_price("INSC", 0.50)
        recs = self.store.buy_recommendations()
        self.assertEqual(len(recs), 1)
        self.assertEqual(recs[0]["symbol"], "INSC")

    def test_lots_targets_and_dca_planner(self) -> None:
        self.store.buy("INFR", 100, 0.25, date="2026-11-10")
        self.store.buy("INFR", 100, 0.25, date="2026-11-12")
        self.store.set_price("INFR", 0.25, date="2026-11-13")
        self.store.set_price("SIM", 0.50)

        # INFR is currently $50 (100%), SIM is $0 (0%). Target 50/50 -> $50 DCA goes 100% to SIM.
        self.store.set_target("INFR", 50.0)
        self.store.set_target("SIM", 50.0)

        summary = self.store.portfolio_summary()
        infr = summary["items"][0]
        self.assertEqual(len(infr["lots"]), 2)
        self.assertEqual(infr["lots"][0]["date"], "2026-11-10")
        self.assertAlmostEqual(infr["cost"], 50.0)
        self.assertIsNotNone(infr["days_held"])
        self.assertGreaterEqual(infr["days_held"], 0)
        self.assertEqual(infr["alloc_pct"], 100.0)
        self.assertEqual(infr["target_pct"], 50.0)

        plan = self.store.plan_dca(50.0)
        self.assertEqual(plan["mode"], "targets")
        by_sym = {r["symbol"]: r for r in plan["plan"]}
        self.assertAlmostEqual(by_sym["INFR"]["alloc_usd"], 0.0)
        self.assertAlmostEqual(by_sym["SIM"]["alloc_usd"], 50.0)
        self.assertAlmostEqual(by_sym["SIM"]["shares"], 100.0)

        # Remove targets -> equal-weight fallback across portfolio + watchlist
        self.store.set_target("INFR", 0.0)
        self.store.set_target("SIM", 0.0)
        self.assertEqual(self.store.get_targets(), {})
        eq_plan = self.store.plan_dca(100.0)
        self.assertEqual(eq_plan["mode"], "equal")
        self.assertTrue(len(eq_plan["plan"]) >= 1)

        self.store.state["last_fetch"] = datetime.now(timezone.utc).isoformat()
        panel = format_panel_json(self.store)
        self.assertIn("targets", panel)

        parser = build_parser()
        args = parser.parse_args(["dca", "100", "--json"])
        self.assertEqual(args.budget, 100.0)
        self.assertTrue(args.json)

    def test_fifo_sell_realized_pnl_and_trades(self) -> None:
        self.store.buy("ECO", 100, 0.20, date="2026-11-01")
        self.store.buy("ECO", 100, 0.40, date="2026-11-05")
        # Sell 150 @ $0.50 -> FIFO consumes 100 @ $0.20 ($20) + 50 @ $0.40 ($20) = $40 cost; proceeds = $75 -> +$35 realized
        realized = self.store.sell("ECO", 150, price=0.50, date="2026-11-13")
        self.assertAlmostEqual(realized, 35.0)
        summary = self.store.portfolio_summary()
        self.assertAlmostEqual(summary["realized_pnl"], 35.0)
        self.assertEqual(len(summary["items"]), 1)
        eco = summary["items"][0]
        self.assertAlmostEqual(eco["shares"], 50.0)
        self.assertAlmostEqual(eco["avg_cost"], 0.40)
        self.assertEqual(len(eco["lots"]), 1)
        self.assertEqual(len(self.store.state["trades"]), 3)
        self.assertEqual(self.store.state["trades"][-1]["action"], "SELL")

    def test_daily_change_pct(self) -> None:
        self.store.state["watchlist"] = ["INFR"]
        self.store.state["history"]["INFR"] = [
            {"date": "2026-11-12", "price": 0.20},
            {"date": "2026-11-13", "price": 0.25},
        ]
        self.store.set_price("INFR", 0.25, date="2026-11-13")
        self.assertAlmostEqual(self.store.get_daily_change("INFR"), 25.0)
        wb = format_waybar(self.store)
        self.assertIn("+25.0%", wb["text"])
        self.assertIn("+25.0%", wb["tooltip"])

    def test_dividends_and_total_return(self) -> None:
        self.store.buy("INFR", 100, 0.20, date="2026-11-10")
        self.store.set_price("INFR", 0.25, date="2026-11-13")
        self.store.add_dividend("INFR", 2.50, date="2026-11-13")
        summary = self.store.portfolio_summary()
        self.assertAlmostEqual(summary["total_pnl"], 5.0)
        self.assertAlmostEqual(summary["total_dividends"], 2.50)
        self.assertAlmostEqual(summary["total_return"], 7.50)
        self.assertAlmostEqual(summary["items"][0]["dividends"], 2.50)

    def test_market_status_and_timestamp(self) -> None:
        # 10:30 CAT (08:30 UTC) on Friday 2026-11-13 -> Open
        self.assertEqual(get_market_status(datetime(2026, 11, 13, 8, 30, tzinfo=timezone.utc)), "Open")
        # 14:00 CAT (12:00 UTC) on Friday -> Closed
        self.assertEqual(get_market_status(datetime(2026, 11, 13, 12, 0, tzinfo=timezone.utc)), "Closed")
        # Saturday -> Closed
        self.assertEqual(get_market_status(datetime(2026, 11, 14, 8, 30, tzinfo=timezone.utc)), "Closed")
        self.store.set_price("INFR", 0.25, date="2026-11-13")
        self.assertTrue(len(get_last_updated_label(self.store)) > 0)

    def test_fetch_ttl_and_error(self) -> None:
        self.store.state["last_fetch_at"] = datetime.now(timezone.utc).isoformat()
        cached = fetch_vfex_prices(self.store, force=False, ttl_seconds=900)
        self.assertTrue(cached["ok"])
        self.assertTrue(cached["cached"])

        err = fetch_vfex_prices(self.store, url="http://127.0.0.1:1/bad", force=True)
        self.assertFalse(err["ok"])
        self.assertIn("Could not reach VFEX", err["message"])

    def test_export_md_and_csv(self) -> None:
        self.store.buy("INFR", 100, 0.20, date="2026-11-10")
        self.store.set_price("INFR", 0.25, date="2026-11-13")
        self.store.add_dividend("INFR", 1.50, date="2026-11-13")
        md = self.store.export_report("md")
        self.assertIn("# VFEX Portfolio Report", md)
        self.assertIn("| INFR |", md)
        self.assertIn("+$1.50", md)

        csv_out = self.store.export_report("csv")
        self.assertIn("record_type,date,symbol,shares,price,value_or_amount,pnl", csv_out)
        self.assertIn("HOLDING,,INFR,100,0.2500,25.00,5.00", csv_out)
        self.assertIn("DIVIDEND,2026-11-13,INFR,,,1.50,", csv_out)

    def test_ohlc_candles_and_api_change_pct(self) -> None:
        self.store.state["watchlist"] = ["AXIA"]
        self.store.set_price("AXIA", 0.1793, source="vfex-direct", open_price=0.1802, change_pct=-0.4994, date="2026-11-13")
        # Intraday high update on same date
        self.store.set_price("AXIA", 0.1850, source="vfex-direct", open_price=0.1802, change_pct=2.66, date="2026-11-13")
        candles = self.store.get_candles("AXIA")
        self.assertEqual(len(candles), 1)
        self.assertAlmostEqual(candles[0]["open"], 0.1802)
        self.assertAlmostEqual(candles[0]["high"], 0.1850)
        self.assertAlmostEqual(candles[0]["low"], 0.1793)
        self.assertAlmostEqual(candles[0]["close"], 0.1850)
        self.assertAlmostEqual(self.store.get_daily_change("AXIA"), 2.66)

        self.store.state["last_fetch_at"] = datetime.now(timezone.utc).isoformat()
        panel = format_panel_json(self.store)
        self.assertEqual(len(panel["watchlist"][0]["candles"]), 1)

    def test_cli_date_flags_and_validation(self) -> None:
        parser = build_parser()
        buy_args = parser.parse_args(["buy", "INFR", "100", "0.24", "--date", "2026-10-01"])
        self.assertEqual(buy_args.date, "2026-10-01")
        sell_args = parser.parse_args(["sell", "INFR", "25", "0.26", "--date", "2026-10-15"])
        self.assertEqual(sell_args.date, "2026-10-15")
        div_args = parser.parse_args(["dividend", "add", "INFR", "1.5", "--date", "2026-11-01"])
        self.assertEqual(div_args.date, "2026-11-01")

        self.store.buy("INFR", 100, 0.24, date="2026-10-01")
        self.store.sell("INFR", 25, 0.26, date="2026-10-15")
        self.store.add_dividend("INFR", 1.5, date="2026-11-01")
        # Slash / dot / DD/MM/YYYY formats and chronological backfill sorting
        self.store.buy("INFR", 38, 0.2235, date="2026/10/09")
        self.assertEqual(VFEXStore._normalize_date("2026/10/09"), "2026-10-09")
        self.assertEqual(VFEXStore._normalize_date("09/10/2026"), "2026-10-09")
        self.assertEqual(VFEXStore._normalize_date("2026.10.09"), "2026-10-09")
        self.assertEqual(self.store.state["trades"][0]["date"], "2026-10-01")
        self.assertEqual(self.store.state["trades"][1]["date"], "2026-10-09")
        self.assertEqual(self.store.state["portfolio"]["INFR"]["lots"][0]["date"], "2026-10-01")
        self.assertEqual(self.store.state["portfolio"]["INFR"]["lots"][1]["date"], "2026-10-09")
        self.assertEqual(self.store.state["trades"][2]["date"], "2026-10-15")
        self.assertEqual(self.store.state["dividends"][0]["date"], "2026-11-01")

        with self.assertRaises(ValueError):
            VFEXStore._normalize_date("not-a-date")

    def test_ctrade_depth_and_zwg_currency_separation(self) -> None:
        from vfex import _ingest_ctrade_rows
        vfex_rows = [{
            "Ticker": "INFR.VX",
            "Current_price": ".2494",
            "PrevPrice": ".2477",
            "PrevPer": "0.6863",
            "Best_bid": ".2200",
            "Best_Ask": ".2480",
            "Bid_Volume": "2665",
            "Ask_Volume": "37195",
            "FullCompanyName": "Econet InfraCo",
        }]
        zse_rows = [{
            "Ticker": "AFDS.ZW",
            "Current_price": "19.2826",
            "PrevPrice": "19.2826",
            "PrevPer": "0.0",
            "Best_bid": "19.3000",
            "Best_Ask": "19.0000",
            "Bid_Volume": "40",
            "Ask_Volume": "1",
            "FullCompanyName": "African Distillers Limited",
        }]
        _ingest_ctrade_rows(self.store, vfex_rows, "USD", True, "2026-11-16", set())
        _ingest_ctrade_rows(self.store, zse_rows, "ZWG", False, "2026-11-16", set())

        self.store.buy("INFR", 10, 0.20, date="2026-11-10")
        self.store.buy("AFDS.ZW", 2, 18.00, date="2026-11-12")
        self.store.state["watchlist"] = ["INFR", "AFDS.ZW"]
        self.store.state["last_fetch_at"] = datetime.now(timezone.utc).isoformat()

        summary = self.store.portfolio_summary()
        # USD totals exclude ZWG holdings
        self.assertAlmostEqual(summary["total_cost"], 2.00)
        self.assertAlmostEqual(summary["total_value"], 2.494)
        self.assertTrue(summary["has_zwg"])
        self.assertAlmostEqual(summary["zwg_cost"], 36.00)
        self.assertAlmostEqual(summary["zwg_value"], 38.5652, places=2)

        panel = format_panel_json(self.store)
        wl = {w["symbol"]: w for w in panel["watchlist"]}
        self.assertEqual(wl["INFR"]["currency"], "USD")
        self.assertAlmostEqual(wl["INFR"]["best_bid"], 0.2200)
        self.assertAlmostEqual(wl["INFR"]["best_ask"], 0.2480)
        self.assertEqual(wl["INFR"]["bid_volume"], 2665)
        self.assertEqual(wl["INFR"]["ask_volume"], 37195)
        self.assertAlmostEqual(wl["INFR"]["spread"], 0.0280)
        self.assertEqual(wl["AFDS.ZW"]["currency"], "ZWG")
        self.assertIn("AFDS.ZW", panel["zse_symbols"])


if __name__ == "__main__":
    unittest.main()
