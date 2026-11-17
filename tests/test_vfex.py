import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from vfex import (
    VFEXStore,
    _build_symbol_alias_index,
    _extract_title_news_date,
    _match_news_symbols,
    _news_age_weight,
    _parse_dtr_exchange_payload,
    _parse_exchange_docs_json,
    _parse_google_news_rss,
    build_parser,
    calculate_trade_charges,
    classify_news_headline,
    compute_smart_limit,
    compute_symbol_technicals,
    compute_xirr,
    fetch_exchange_intelligence,
    fetch_vfex_news,
    fetch_vfex_prices,
    format_panel_json,
    format_waybar,
    get_last_updated_label,
    get_market_countdown,
    get_market_status,
    normalize_goal,
    parse_contract_note_text,
    extract_contract_note_file,
)


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

    def test_trade_signals_settings_cli_and_ctrade_storage(self) -> None:
        from vfex import _ingest_ctrade_rows
        self.store.state["history"]["SCIL"] = [
            {"date": "2026-11-10", "price": 0.40},
            {"date": "2026-11-11", "price": 0.40},
        ]
        _ingest_ctrade_rows(self.store, [{
            "Ticker": "SCIL.VX",
            "Current_price": "0.36",
            "PrevPrice": "0.40",
            "PrevPer": "-10.0",
            "Best_bid": "0.3550",
            "Best_Ask": "0.3600",
            "Bid_Volume": "1000",
            "Ask_Volume": "100",
        }], "USD", True, "2026-11-16", set())
        _ingest_ctrade_rows(self.store, [{
            "Ticker": "ARIS.ZW",
            "Current_price": "0.10",
            "PrevPrice": "0.12",
            "PrevPer": "-16.6",
            "Best_bid": "0.095",
            "Best_Ask": "0.100",
            "Bid_Volume": "500",
            "Ask_Volume": "50",
        }], "ZWG", False, "2026-11-16", set())

        self.store.state["watchlist"] = ["INSC", "SIM", "PHL", "SCIL", "ARIS.ZW"]
        self.store.buy("INFR", 100, 0.20, date="2026-11-01")
        self.store.set_price("INFR", 0.25, date="2026-11-16")

        # Also stage an untracked counter with a steep dip -> excluded by tracked_only=True
        self.store.set_price("UNTR", 0.10, change_pct=-8.0, date="2026-11-16", best_bid=0.095, best_ask=0.100, bid_volume=500, ask_volume=20)
        self.assertNotIn("UNTR", {s["symbol"] for s in self.store.trade_signals(discount_pct=3.0, include_zse=True)})
        self.assertIn("UNTR", {s["symbol"] for s in self.store.trade_signals(discount_pct=3.0, include_zse=True, tracked_only=False)})

        vfex_only = self.store.trade_signals(discount_pct=3.0, include_zse=False)
        syms_vfex = {s["symbol"] for s in vfex_only}
        self.assertIn("SCIL", syms_vfex)
        self.assertIn("INFR", syms_vfex)  # +25% gain triggers SELL profit-take signal
        self.assertNotIn("ARIS.ZW", syms_vfex)

        all_sigs = self.store.trade_signals(discount_pct=3.0, include_zse=True)
        self.assertIn("ARIS.ZW", {s["symbol"] for s in all_sigs})

        # Deduplicated daily notifications
        sent1 = self.store.notify_trade_signals(all_sigs)
        sent2 = self.store.notify_trade_signals(all_sigs)
        self.assertTrue(len(sent1) >= 1)
        self.assertEqual(sent2, [])

        # C-TRADE local credential helper stores 0600 and masks email
        self.store._save_ctrade_creds({"email": "trader@example.com", "password": "secret"})
        mode = self.store.ctrade_file.stat().st_mode & 0o777
        self.assertEqual(mode, 0o600)
        st = self.store.ctrade_status()
        self.assertTrue(st["connected"])
        self.assertEqual(st["email_masked"], "tr***@example.com")
        self.assertNotIn("secret", json.dumps(st))
        self.store.ctrade_logout()
        self.assertFalse(self.store.ctrade_status()["connected"])

        parser = build_parser()
        pargs = parser.parse_args(["panel-json", "--market", "vfex", "--discount", "5", "--notify-signals"])
        self.assertEqual(pargs.market, "vfex")
        self.assertEqual(pargs.discount, 5.0)
        self.assertTrue(pargs.notify_signals)

    def test_multi_portal_accounts_mfa_and_wallet_reconciliation(self) -> None:
        # Manual lot + synced VFEX-D & ZSE-D holdings + wallet cash reconcile cleanly
        self.store.buy("INFR", 10, 0.20, date="2026-10-09")
        self.store.set_price("INFR", 0.25, date="2026-11-16")
        self.store.set_price("AXIA", 0.18, date="2026-11-16")
        self.store.set_price("AFDS.ZW", 20.0, currency="ZWG", date="2026-11-16")

        self.store._save_accounts({
            "vfex_direct": {"email": "user@example.com", "password": "pw", "mfa_pending": True, "mfa_token": "tok123", "access_token": ""},
            "zse_direct": {"email": "zse@example.com", "password": "pw", "access_token": "jwt-zse", "mfa_pending": False},
        })
        self.assertEqual(self.store.accounts_file.stat().st_mode & 0o777, 0o600)

        with self.assertRaises(ValueError):
            self.store.portal_verify_mfa("vfex_direct", "abc")  # must be 6 digits

        self.store.state["synced_accounts"] = {
            "vfex_direct": {
                "holdings": [{"symbol": "AXIA", "shares": 100, "avg_cost": 0.15, "currency": "USD"}],
                "cash_usd": 12.50,
                "cash_zwg": 0.0,
                "last_sync": "2026-11-16T10:00:00+00:00",
            },
            "zse_direct": {
                "holdings": [{"symbol": "AFDS.ZW", "shares": 5, "avg_cost": 18.0, "currency": "ZWG"}],
                "cash_usd": 0.0,
                "cash_zwg": 240.0,
                "last_sync": "2026-11-16T10:00:00+00:00",
            },
        }
        self.store.state["last_fetch_at"] = datetime.now(timezone.utc).isoformat()

        summary = self.store.portfolio_summary()
        self.assertEqual(len(summary["items"]), 3)
        by_tag = {(i["symbol"], i["source_tag"]): i for i in summary["items"]}
        self.assertIn(("INFR", "Manual"), by_tag)
        self.assertIn(("AXIA", "VFEX-D"), by_tag)
        self.assertIn(("AFDS.ZW", "ZSE-D"), by_tag)
        self.assertAlmostEqual(summary["wallet_cash_usd"], 12.50)
        self.assertAlmostEqual(summary["wallet_cash_zwg"], 240.0)
        # USD total = INFR ($2.50) + AXIA ($18.00) = $20.50 (excluding AFDS.ZW ZWG)
        self.assertAlmostEqual(summary["total_value"], 20.50)
        self.assertAlmostEqual(summary["zwg_value"], 100.0)

        panel = format_panel_json(self.store)
        self.assertTrue(panel["accounts"]["vfex_direct"]["mfa_pending"])
        self.assertTrue(panel["accounts"]["zse_direct"]["connected"])
        self.assertEqual(panel["connected_count"], 1)
        self.assertAlmostEqual(panel["wallet_cash_usd"], 12.50)
        self.assertAlmostEqual(panel["wallet_cash_zwg"], 240.0)

        self.store.portal_logout("vfex_direct")
        self.assertFalse(self.store.accounts_status()["vfex_direct"]["mfa_pending"])

        parser = build_parser()
        a1 = parser.parse_args(["account", "verify-mfa", "--provider", "vfex_direct", "--code", "123456"])
        self.assertEqual(a1.provider, "vfex_direct")
        self.assertEqual(a1.code, "123456")

    def test_quant_backtest_trailing_stop_fees_and_trade_delete(self) -> None:
        # XIRR: invest $1000 365 days ago, worth $1210 today (~21% annualized)
        now = datetime.now(timezone.utc)
        xirr = compute_xirr([(now - timedelta(days=365), -1000.0), (now, 1210.0)])
        self.assertIsNotNone(xirr)
        self.assertAlmostEqual(xirr, 21.0, delta=0.5)

        # Symbol technicals: steady rise -> RSI-14, MA-20, Z-score populated
        hist = [{"date": f"2026-10-{d:02d}", "price": 0.10 + d * 0.002} for d in range(1, 25)]
        tech = compute_symbol_technicals(hist, 0.16)
        self.assertIsNotNone(tech["ma20"])
        self.assertIsNotNone(tech["rsi14"])
        self.assertIsNotNone(tech["z_score"])
        self.assertGreater(tech["rsi14"], 60.0)

        # Smart limit & wide spread detection
        sl = compute_smart_limit(0.25, 0.22, 0.26, 2700, 8400, action="BUY")
        self.assertGreater(sl["spread_pct"], 5.0)
        self.assertTrue(sl["wide_spread"])
        self.assertIsNotNone(sl["optimal_limit"])

        # Portfolio fees, breakeven, trailing stops, notes, and trade delete
        self.store.buy("INFR", 100, 0.20, date="2026-06-01")
        self.store.buy("INFR", 100, 0.24, date="2026-09-01")
        self.store.set_price("INFR", 0.30)

        raw_sum = self.store.portfolio_summary()
        fee_sum = self.store.portfolio_summary(vfex_fee_pct=2.0)
        self.assertAlmostEqual(raw_sum["total_pnl"], 16.0, places=2)
        self.assertLess(fee_sum["net_total_pnl"], raw_sum["total_pnl"])
        self.assertGreater(fee_sum["items"][0]["breakeven_price"], fee_sum["items"][0]["avg_cost"])

        # Trailing stop: set 10% stop at peak $0.30 -> trigger threshold $0.27
        stop = self.store.add_trailing_stop("INFR", 10.0)
        self.assertEqual(stop["symbol"], "INFR")
        self.assertEqual(self.store.check_trailing_stops(notify=False), [])
        self.store.set_price("INFR", 0.26)
        trig = self.store.check_trailing_stops(notify=False)
        self.assertEqual(len(trig), 1)
        self.assertEqual(trig[0]["symbol"], "INFR")

        # Notes & delete_trade FIFO rebuild
        self.store.set_note("INFR", "Hold long term")
        self.assertEqual(self.store.get_notes().get("INFR"), "Hold long term")
        self.store.delete_trade(1)  # remove the 0.24 buy lot
        rebuilt = self.store.portfolio_summary()
        self.assertAlmostEqual(rebuilt["items"][0]["shares"], 100.0)
        self.assertAlmostEqual(rebuilt["items"][0]["avg_cost"], 0.20)

        # Signal history recording + deduplication + backtest summary
        fake_sigs = [
            {"symbol": "AXIA", "action": "BUY", "score": 45, "price": 0.16, "currency": "USD", "exchange": "VFEX", "reasons": ["Oversold"]},
        ]
        added1 = self.store.record_signal_history(fake_sigs, min_score=35)
        added2 = self.store.record_signal_history(fake_sigs, min_score=35)
        self.assertEqual(added1, 1)
        self.assertEqual(added2, 0)  # deduped same-day
        self.store.set_price("AXIA", 0.20)
        bt = self.store.signal_backtest_summary()
        self.assertGreaterEqual(bt["total_logged"], 1)
        self.assertAlmostEqual(bt["win_rate_pct"], 100.0)
        self.assertGreater(bt["avg_return_pct"], 20.0)

        # Screener, breadth, equity curve, and panel-json payload keys
        scr = self.store.market_screener()
        br = self.store.market_breadth()
        eq = self.store.portfolio_equity_curve()
        self.assertIsInstance(scr, list)
        self.assertIn("advancers", br)
        self.assertGreaterEqual(len(eq), 1)

        panel = format_panel_json(self.store, vfex_fee_pct=1.5, max_stock_pct=25.0, profit_take_pct=15.0)
        for key in ("screener", "breadth", "signal_backtest", "equity_curve", "trailing_stops", "notes", "trades", "fee_config", "market_countdown"):
            self.assertIn(key, panel)
        self.assertTrue(len(get_market_countdown()) > 0)
        if panel["screener"]:
            for sk in ("candles", "history", "ma20_series", "recommended_shares"):
                self.assertIn(sk, panel["screener"][0])
        if panel["items"]:
            for hk in ("history", "candles", "optimal_limit", "liquidity_score", "strategy_tag"):
                self.assertIn(hk, panel["items"][0])

    def test_trading_goals_and_per_holding_strategy_tags(self) -> None:
        self.assertEqual(normalize_goal("Long-Term Compounder"), "long")
        self.assertEqual(normalize_goal("Short-Term Swing"), "short")
        self.assertEqual(normalize_goal("Hybrid (Both)"), "hybrid")

        # Hold INFR with +25% unrealized gain + watched SCIL swing candidate
        self.store.state["watchlist"].append("SCIL")
        self.store.buy("INFR", 100, 0.20, date="2026-10-01")
        self.store.set_price("INFR", 0.25, date="2026-11-16", best_bid=0.245, best_ask=0.255, bid_volume=500, ask_volume=200)
        self.store.state["history"]["SCIL"] = [
            {"date": "2026-10-10", "price": 0.40},
            {"date": "2026-10-11", "price": 0.40},
        ]
        self.store.set_price("SCIL", 0.35, change_pct=-5.0, date="2026-11-16", best_bid=0.345, best_ask=0.352, bid_volume=800, ask_volume=100)

        # Short-term mode triggers fast swing SELL on INFR (+25%) and SWING BUY on SCIL
        short_sigs = self.store.trade_signals(trading_goal="short")
        self.assertTrue(any(s["symbol"] == "INFR" and s["action"] == "SELL" and s["horizon"] == "SWING" for s in short_sigs))
        self.assertTrue(any(s["symbol"] == "SCIL" and s["action"] == "BUY" and s["horizon"] == "SWING" for s in short_sigs))

        # Long-term mode protects +25% hold from small SELL chatter and tags BUYs as CORE
        long_sigs = self.store.trade_signals(trading_goal="long")
        self.assertFalse(any(s["symbol"] == "INFR" and s["action"] == "SELL" for s in long_sigs))
        self.assertTrue(any(s["symbol"] == "SCIL" and s["action"] == "BUY" and s["horizon"] == "CORE" for s in long_sigs))

        # Hybrid mode: pinning INFR as CORE protects it from 15-25% SELL take-profit alerts
        self.store.set_strategy_tag("INFR", "core")
        hyb_sum = self.store.portfolio_summary(trading_goal="hybrid")
        self.assertEqual(hyb_sum["core_count"], 1)
        self.assertGreater(hyb_sum["core_value"], 0)
        hyb_sigs = self.store.trade_signals(trading_goal="hybrid")
        self.assertFalse(any(s["symbol"] == "INFR" and s["action"] == "SELL" for s in hyb_sigs))

        # Goal override persists and resets via 'auto'
        self.store.set_trading_goal("long")
        panel_long = format_panel_json(self.store, trading_goal="short", enable_news=False)
        self.assertEqual(panel_long["trading_goal"], "long")
        self.assertTrue(panel_long["trading_goal_override"])
        self.store.set_trading_goal("auto")
        panel_short = format_panel_json(self.store, trading_goal="short", enable_news=False)
        self.assertEqual(panel_short["trading_goal"], "short")
        self.assertFalse(panel_short["trading_goal_override"])

        # Track record splits CORE vs SWING win rates cleanly
        self.store.state["signal_history"] = []
        self.store.record_signal_history([
            {"symbol": "AXIA", "action": "BUY", "horizon": "SWING", "score": 50, "price": 0.10, "currency": "USD"},
            {"symbol": "SCIL", "action": "BUY", "horizon": "CORE", "score": 50, "price": 0.30, "currency": "USD"},
        ], min_score=35)
        self.store.set_price("AXIA", 0.12)
        bt = self.store.signal_backtest_summary()
        self.assertGreaterEqual(bt["core_count"], 1)
        self.assertGreaterEqual(bt["swing_count"], 1)
        self.assertAlmostEqual(bt["swing_win_rate_pct"], 100.0)

        # CLI parser coverage for goal, tag, buy --tag, and --all-market
        parser = build_parser()
        ag = parser.parse_args(["goal", "long"])
        at = parser.parse_args(["tag", "set", "INFR", "core"])
        ab = parser.parse_args(["buy", "INFR", "10", "0.25", "--tag", "core"])
        ap = parser.parse_args(["panel-json", "--all-market"])
        ar = parser.parse_args(["recommend", "--all-market"])
        self.assertEqual(ag.mode, "long")
        self.assertEqual(at.horizon, "core")
        self.assertEqual(ab.tag, "core")
        self.assertTrue(ap.all_market)
        self.assertTrue(ar.all_market)

    def test_tracked_only_signals_and_recommendations_scope(self) -> None:
        # Clear default watchlist to just SIM, then add dips to SIM (tracked) and BIND (untracked)
        self.store.state["watchlist"] = ["SIM"]
        self.store.state["history"]["SIM"] = [{"date": "2026-11-10", "price": 0.40}, {"date": "2026-11-11", "price": 0.40}]
        self.store.state["history"]["BIND"] = [{"date": "2026-11-10", "price": 0.40}, {"date": "2026-11-11", "price": 0.40}]
        self.store.set_price("SIM", 0.34, change_pct=-5.0, date="2026-11-16", best_bid=0.335, best_ask=0.342, bid_volume=600, ask_volume=50)
        self.store.set_price("BIND", 0.30, change_pct=-10.0, date="2026-11-16", best_bid=0.295, best_ask=0.300, bid_volume=2000, ask_volume=10)
        self.store.state["last_fetch_at"] = datetime.now(timezone.utc).isoformat()

        # Default recommendations & signals only return tracked SIM, not untracked BIND
        self.assertEqual([r["symbol"] for r in self.store.buy_recommendations()], ["SIM"])
        self.assertEqual({s["symbol"] for s in self.store.trade_signals()}, {"SIM"})
        # All-market mode & Screener still include untracked BIND
        self.assertIn("BIND", {r["symbol"] for r in self.store.buy_recommendations(tracked_only=False)})
        self.assertIn("BIND", {r["symbol"] for r in self.store.market_screener()})

        panel = format_panel_json(self.store, enable_news=False)
        self.assertTrue(panel["tracked_only"])
        self.assertEqual(panel["tracked_count"], 1)
        self.assertEqual({s["symbol"] for s in panel["signals"]}, {"SIM"})
        self.assertTrue(any(m["symbol"] == "BIND" for m in panel["market_top_signals"]))

        # Overriding with tracked_only=False re-includes untracked BIND in main signals
        panel_all = format_panel_json(self.store, tracked_only=False, enable_news=False)
        self.assertFalse(panel_all["tracked_only"])
        self.assertIn("BIND", {s["symbol"] for s in panel_all["signals"]})

    def test_news_catalyst_matching_classification_and_signal_impact(self) -> None:
        self.store.state["watchlist"] = ["SIM", "INFR"]
        self.store.buy("PHL", 100, 0.20)
        self.store.set_price("SIM", 0.35, date="2026-11-16", company_name="Simbisa Brands Limited")
        self.store.set_price("INFR", 0.25, date="2026-11-16", company_name="Econet InfraCo")
        self.store.set_price("PHL", 0.21, date="2026-11-16", company_name="Padenga Holdings Limited")
        self.store.set_price("FCA", 0.16, date="2026-11-16", company_name="First Capital Bank Limited")
        self.store.set_price("DLTA.ZW", 7.50, date="2026-11-16", company_name="Delta Corporation Limited")
        self.store.set_price("INV", 0.05, date="2026-11-16", company_name="Invictus Energy Limited")
        self.store.state["last_fetch_at"] = datetime.now(timezone.utc).isoformat()

        # Strict company/context matching avoids foreign false positives on short tickers
        alias_idx = _build_symbol_alias_index(self.store)
        stored_syms = set(self.store.state["prices"].keys()) | {"SIM", "INFR", "PHL"}
        self.assertEqual(_match_news_symbols("UK FCA fines London broker £2m", alias_idx, stored_syms), [])
        self.assertEqual(_match_news_symbols("Threats to the Okavango Delta - National Geographic", alias_idx, stored_syms), [])
        self.assertEqual(_match_news_symbols("Phone SIM card registration delays in Europe", alias_idx, stored_syms), [])
        self.assertIn("SIM", _match_news_symbols("Chicken Inn owner Simbisa takes full ownership of Kenyan delivery business", alias_idx, stored_syms))
        self.assertIn("DLTA.ZW", _match_news_symbols("Delta Corporation declares interim dividend on ZSE", alias_idx, stored_syms))

        # Event classification & sentiment rules
        div_cls = classify_news_headline("Simbisa declares interim dividend on VFEX", official=False)
        self.assertEqual(div_cls["category"], "Dividend")
        self.assertEqual(div_cls["sentiment"], "Bullish")
        self.assertGreaterEqual(div_cls["impact_score"], 15)

        vic_cls = classify_news_headline("Victoria Falls Stock Exchange hosts AGM notice", official=True)
        self.assertNotEqual(vic_cls["sentiment"], "Caution")

        caut_cls = classify_news_headline("PHL.vx Cautionary Statement - Operations Delay", official=True)
        self.assertEqual(caut_cls["category"], "Cautionary")
        self.assertEqual(caut_cls["sentiment"], "Caution")
        self.assertLessEqual(caut_cls["impact_score"], -15)

        # Mock feed ingestion + 15m TTL cache check
        now_dt = datetime.now(timezone.utc)
        pub_rss = now_dt.strftime("%a, %d %b %Y %H:%M:%S GMT")
        rss_xml = f"""<?xml version="1.0" encoding="UTF-8"?>
        <rss><channel>
          <item>
            <title>Simbisa Brands acquires full ownership of regional expansion unit - Techzim</title>
            <link>https://example.com/simbisa</link>
            <pubDate>{pub_rss}</pubDate>
            <source>Techzim</source>
          </item>
          <item>
            <title>UK FCA warns crypto platforms - Reuters</title>
            <link>https://example.com/fca</link>
            <pubDate>{pub_rss}</pubDate>
            <source>Reuters</source>
          </item>
        </channel></rss>"""
        vfex_docs = json.dumps([
            {
                "id": 901,
                "doc_name": "PHL.vx Cautionary Statement on Export Operations",
                "exchange": "VFEX",
                "category": "announcements",
                "created_at": now_dt.isoformat(),
                "download_url": "http://ds88jcmqc11je.cloudfront.net/websites/phl_caut.pdf",
                "issuer": None,
            },
            {
                "id": 902,
                "doc_name": "INV.vx Notice to Shareholders - Mobilisation Commenced and Rig-Up Underway",
                "exchange": "VFEX",
                "category": "announcements",
                "created_at": now_dt.isoformat(),
                "download_url": "https://example.com/inv.pdf",
                "issuer": None,
            },
        ])
        calls: list[str] = []

        def fake_fetcher(url: str) -> str:
            calls.append(url)
            if "exchange=VFEX" in url and "docs?" in url:
                return vfex_docs
            if "news.google.com" in url:
                return rss_xml
            return "[]"

        res1 = fetch_vfex_news(self.store, force=True, fetcher=fake_fetcher)
        self.assertTrue(res1["ok"])
        self.assertFalse(res1["cached"])
        self.assertGreater(len(calls), 0)
        titles = [it["title"] for it in res1["items"]]
        self.assertTrue(any("Simbisa Brands acquires full ownership" in t for t in titles))
        self.assertFalse(any("UK FCA" in t for t in titles))
        phl_item = next(it for it in res1["items"] if "PHL.vx Cautionary" in it["title"])
        self.assertTrue(phl_item["official"])
        self.assertTrue(phl_item["tracked"])
        self.assertTrue(phl_item["url"].startswith("https://"))

        # Second call inside TTL window hits cache cleanly with zero HTTP calls
        prev_calls = len(calls)
        res2 = fetch_vfex_news(self.store, force=False, fetcher=fake_fetcher)
        self.assertTrue(res2["cached"])
        self.assertEqual(len(calls), prev_calls)

        # Bullish news creates/boosts BUY signal for tracked SIM; Caution news flags owned PHL for SELL review
        sigs = self.store.trade_signals(trading_goal="hybrid", tracked_only=True, news_items=res1["items"])
        sim_buy = next((s for s in sigs if s["symbol"] == "SIM" and s["action"] == "BUY"), None)
        self.assertIsNotNone(sim_buy)
        self.assertTrue(any("News+" in r for r in sim_buy["reasons"]))
        self.assertEqual(sim_buy["news_catalyst"]["category"], "Expansion")

        phl_sell = next((s for s in sigs if s["symbol"] == "PHL" and s["action"] == "SELL"), None)
        self.assertIsNotNone(phl_sell)
        self.assertEqual(phl_sell["news_catalyst"]["sentiment"], "Caution")

        # Panel JSON carries structured news, top catalysts, and inline watchlist catalyst metadata
        panel = format_panel_json(self.store, enable_news=True)
        self.assertTrue(panel["news_enabled"])
        self.assertGreaterEqual(panel["news_summary"]["tracked"], 2)
        self.assertGreaterEqual(len(panel["news_top"]), 1)
        sim_wl = next(w for w in panel["watchlist"] if w["symbol"] == "SIM")
        self.assertEqual(sim_wl["news_catalyst"]["sentiment"], "Bullish")

        # Notification dedup fires once per tracked material headline
        sent_calls: list[tuple[str, str]] = []
        import vfex as vfex_mod
        orig_notify = vfex_mod.send_notification
        try:
            vfex_mod.send_notification = lambda title, body: sent_calls.append((title, body))
            first = self.store.notify_news_catalysts(res1["items"])
            second = self.store.notify_news_catalysts(res1["items"])
            self.assertGreaterEqual(len(first), 2)
            self.assertEqual(len(second), 0)
        finally:
            vfex_mod.send_notification = orig_notify

        # CLI parser flags for news and --no-news
        parser = build_parser()
        an = parser.parse_args(["news", "--fetch", "--tracked", "--json", "--summary"])
        apn = parser.parse_args(["panel-json", "--no-news"])
        self.assertTrue(an.fetch and an.tracked and an.json and an.summary)
        self.assertTrue(apn.no_news)

    def test_paper_agent_contract_notes_holds_and_self_learning(self) -> None:
        # 1. Exact Morgan & Co contract note verification: 38 INFR @ $0.2235 -> $8.4930 gross + $0.10 charges
        vfex_buy = calculate_trade_charges("USD", "BUY", 38, 0.2235)
        self.assertAlmostEqual(vfex_buy["gross"], 8.493, places=3)
        self.assertAlmostEqual(vfex_buy["brokerage"], 0.05)
        self.assertAlmostEqual(vfex_buy["vat"], 0.01)
        self.assertAlmostEqual(vfex_buy["platform_levy"], 0.01)
        self.assertAlmostEqual(vfex_buy["secz_levy"], 0.01)
        self.assertAlmostEqual(vfex_buy["stamp_duty"], 0.02)
        self.assertAlmostEqual(vfex_buy["cgt"], 0.0)
        self.assertAlmostEqual(vfex_buy["total_charges"], 0.10)

        vfex_sell = calculate_trade_charges("USD", "SELL", 38, 0.25)
        self.assertAlmostEqual(vfex_sell["stamp_duty"], 0.0)
        self.assertAlmostEqual(vfex_sell["cgt"], 0.0)

        # ZSE contract note includes CGT on SELL and 0% CGT on BUY
        zse_buy = calculate_trade_charges("ZWG", "BUY", 100, 5.0)
        zse_sell = calculate_trade_charges("ZWG", "SELL", 100, 5.5)
        self.assertGreater(zse_buy["stamp_duty"], 0.0)
        self.assertEqual(zse_buy["cgt"], 0.0)
        self.assertGreater(zse_sell["cgt"], 0.0)

        # 2. Isolated $100 wallet (real portfolio remains untouched)
        self.store.reset_paper_agent(starting_usd=100.0, zwg_rate=26.5)
        summary0 = self.store.paper_agent_summary()
        self.assertAlmostEqual(summary0["cash_usd"], 80.0)
        self.assertAlmostEqual(summary0["cash_zwg"], 530.0)
        self.assertEqual(self.store.portfolio_summary()["items"], [])

        # 3. Simulate causal multi-day walk with 1 losing wide-spread trade + 1 winning SWING dip trade
        self.store.state["history"]["SIM"] = [
            {"date": "2026-10-20", "price": 0.355},
            {"date": "2026-10-22", "price": 0.355},
        ]
        # AXIA wide-spread (-6% dip, 12% spread) triggers entry on 2026-11-01 then drops -12% on 2026-11-03 (hard stop)
        self.store.state["history"]["AXIA"] = [
            {"date": "2026-10-20", "price": 0.20},
            {"date": "2026-10-25", "price": 0.20},
        ]
        day1_prices = {
            "SIM": {"price": 0.34, "currency": "USD", "change_pct": -5.0, "best_bid": 0.335, "best_ask": 0.342, "bid_volume": 800, "ask_volume": 50},
            "AXIA": {"price": 0.18, "currency": "USD", "change_pct": -6.0, "best_bid": 0.170, "best_ask": 0.195, "bid_volume": 400, "ask_volume": 100},
        }
        r1 = self.store.run_paper_agent_step(as_of_date="2026-11-01", allow_off_hours=True, prices_override=day1_prices)
        self.assertEqual(len(r1["executed"]), 2)
        self.assertEqual(set(self.store.state["paper_agent"]["positions"].keys()), {"SIM", "AXIA"})

        # Day 2 (1 day hold): SIM up +6% -> must HOLD because < 3d min SWING hold (anti-churn!)
        day2_prices = {
            "SIM": {"price": 0.37, "currency": "USD", "change_pct": 6.0, "best_bid": 0.368, "best_ask": 0.372, "bid_volume": 500, "ask_volume": 100},
            "AXIA": {"price": 0.182, "currency": "USD", "change_pct": 1.0, "best_bid": 0.180, "best_ask": 0.185, "bid_volume": 400, "ask_volume": 100},
        }
        r2 = self.store.run_paper_agent_step(as_of_date="2026-11-02", allow_off_hours=True, prices_override=day2_prices)
        self.assertIn("SIM", self.store.state["paper_agent"]["positions"])

        # Day 5 (4d hold): SIM stays +12% (takes profit) & AXIA dumps -12% (hard stop + MISTAKE learning!)
        day5_prices = {
            "SIM": {"price": 0.40, "currency": "USD", "change_pct": 5.0, "best_bid": 0.398, "best_ask": 0.402, "bid_volume": 500, "ask_volume": 100},
            "AXIA": {"price": 0.145, "currency": "USD", "change_pct": -12.0, "best_bid": 0.144, "best_ask": 0.150, "bid_volume": 100, "ask_volume": 800},
        }
        self.store.run_paper_agent_step(as_of_date="2026-11-05", allow_off_hours=True, prices_override=day5_prices)

        summary = self.store.paper_agent_summary()
        self.assertEqual(summary["total_closed"], 2)
        self.assertEqual(summary["wins"], 1)
        self.assertEqual(summary["losses"], 1)
        self.assertGreater(summary["total_fees_usd"], 0.5)
        self.assertGreaterEqual(len(summary["lessons"]), 2)
        # Wide spread mistake increased wide_spread_penalty and placed AXIA on cooldown
        self.assertGreater(summary["weights"]["wide_spread_penalty"], 1.0)
        self.assertIn("AXIA", {c["symbol"] for c in summary["cooldowns"]})

        # Ensure AXIA cooldown blocks re-entry even if it dips on 2026-11-06
        cands = self.store._agent_score_candidates(
            self.store.get_paper_agent_state(),
            day1_prices,
            self.store.state["history"],
            {},
            "2026-11-06",
        )
        self.assertNotIn("AXIA", {c["symbol"] for c in cands})

        # Pause/Resume & Replay + Panel JSON integration + CLI parser checks
        self.assertFalse(self.store.toggle_paper_agent(False))
        self.assertTrue(self.store.toggle_paper_agent(True))
        self.store.state["last_fetch_at"] = datetime.now(timezone.utc).isoformat()
        panel = format_panel_json(self.store, enable_news=False, enable_agent=True)
        self.assertIn("paper_agent", panel)
        self.assertGreater(len(panel["paper_agent"]["trades"]), 0)

        p = build_parser()
        a_rep = p.parse_args(["agent", "replay", "--days", "30", "--capital", "100"])
        a_pn = p.parse_args(["panel-json", "--no-agent", "--agent-zwg-rate", "27.0"])
        self.assertEqual(a_rep.action, "replay")
        self.assertTrue(a_pn.no_agent)
        self.assertAlmostEqual(a_pn.agent_zwg_rate, 27.0)

    def test_exchange_intelligence_dtr_and_circuit_breaker_signals(self) -> None:
        self.store.state["watchlist"] = ["FCA", "PHL", "SIM"]
        self.store.set_price("FCA", 0.16, currency="USD", company_name="First Capital Bank Limited", upper_limit=0.19, lower_limit=0.145)
        # Preserve VOMS circuit limits even when subsequent C-TRADE quote updates lack those fields
        self.store.set_price("FCA", 0.15, source="c-trade-vfex", change_pct=-4.0, best_bid=0.149, best_ask=0.152, bid_volume=1000, ask_volume=100)
        entry_fca = self.store.get_price_entry("FCA")
        self.assertAlmostEqual(entry_fca["upper_limit"], 0.19)
        self.assertAlmostEqual(entry_fca["lower_limit"], 0.145)
        band_pos = self.store._band_position_pct(0.15, entry_fca)
        self.assertIsNotNone(band_pos)
        self.assertLessEqual(band_pos, 20.0)

        self.store.set_price("PHL", 1.85, currency="USD", company_name="Padenga Holdings Limited", change_pct=8.0, best_bid=1.80, best_ask=1.86, bid_volume=600, ask_volume=100, upper_limit=1.87, lower_limit=1.40)

        vfex_dtr_mock = json.dumps({
            "data": [{
                "statsDate": [2026, 11, 16],
                "content": json.dumps({
                    "indices": {"index": "VFEX ALLSHARE", "closingPrice": 267.48, "changePercentage": -0.17},
                    "volumeAndTurnover": {
                        "totalMarketVolumeShares": 1597525.0,
                        "totalMarketTurnover": 848195.24,
                        "foreignPurchases": {"value": 12000.0},
                        "foreignSales": {"value": 29808.28},
                        "totalNumberOfTrades": 168,
                    },
                    "topFiveCounters": {
                        "volumesTraded": [
                            {"counter": "FIRST CAPITAL BANK LIMITED", "volumes": 1153162.0, "valueTraded": 184510.54},
                        ]
                    },
                    "topTenMarketCap": [
                        {"counter": "PHL.VX", "value": 1208601785.0, "percentage": 13.36},
                        {"counter": "FCA.VX", "value": 450000000.0, "percentage": 5.20},
                    ],
                }),
            }]
        })
        calls: list[str] = []

        def fake_dtr_fetch(url: str) -> str:
            calls.append(url)
            if "exchange=VFEX" in url:
                return vfex_dtr_mock
            return json.dumps({"data": []})

        intel1 = fetch_exchange_intelligence(self.store, force=True, fetcher=fake_dtr_fetch)
        self.assertEqual(intel1["vfex"]["index_name"], "VFEX ALLSHARE")
        self.assertAlmostEqual(intel1["vfex"]["foreign_net"], -17808.28)
        self.assertIn("FCA", intel1["counters"])
        self.assertIn("PHL", intel1["blue_chips"])
        self.assertEqual(intel1["blue_chips"]["PHL"]["rank"], 1)

        # 5m cache prevents repeat HTTP fetch
        n_before = len(calls)
        fetch_exchange_intelligence(self.store, force=False, fetcher=fake_dtr_fetch)
        self.assertEqual(len(calls), n_before)

        # Signals include DTR Vol, Blue-Chip Cap, Near floor, and round-trip fee metadata
        sigs = self.store.trade_signals(trading_goal="hybrid", tracked_only=True, news_items=[])
        fca_sig = next(s for s in sigs if s["symbol"] == "FCA" and s["action"] == "BUY")
        self.assertAlmostEqual(fca_sig["dtr_turnover"], 184510.54)
        self.assertEqual(fca_sig["blue_chip_rank"], 2)
        self.assertAlmostEqual(fca_sig["est_round_trip_fee_pct"], 2.08)
        self.assertTrue(any("DTR" in r for r in fca_sig["reasons"]))
        self.assertTrue(any("Near floor" in r for r in fca_sig["reasons"]))

        # Format panel JSON exposes market_intel and CLI intel parser works
        self.store.state["last_fetch_at"] = datetime.now(timezone.utc).isoformat()
        panel = format_panel_json(self.store, enable_news=False, enable_agent=False)
        self.assertEqual(panel["market_intel"]["vfex"]["num_trades"], 168)

        ai = build_parser().parse_args(["intel", "--fetch", "--json"])
        self.assertTrue(ai.fetch and ai.json)

    def test_audit_polish_signal_floor_statutory_fees_and_news_dedup(self) -> None:
        # 1. DTR volume alone with heavy ask depth & zero dip must NOT trigger noisy sub-25 signal
        self.store.state["watchlist"] = ["INFR"]
        self.store.set_price("INFR", 0.25, change_pct=0.0, best_bid=0.22, best_ask=0.26, bid_volume=100, ask_volume=5000)
        self.store.state["market_intel"] = {
            "fetched_at": datetime.now(timezone.utc).isoformat(),
            "vfex": {"index_name": "VFEX ALLSHARE", "index_value": 267.48, "index_chg_pct": -0.17, "turnover": 100000, "num_trades": 50, "foreign_net": 0},
            "zse": {},
            "counters": {"INFR": {"volumes": 40000, "value_traded": 10000.0}},
            "blue_chips": {},
        }
        sigs = self.store.trade_signals(tracked_only=True, news_items=[])
        self.assertEqual(sigs, [])

        # 2. Statutory default computes exact Morgan & Co net P&L on 38 INFR @ $0.2235 -> $0.2494
        self.store.buy("INFR", 38, 0.2235)
        self.store.set_price("INFR", 0.2494)
        stat_sum = self.store.portfolio_summary(vfex_fee_pct="statutory", zse_fee_pct="statutory")
        gross_sum = self.store.portfolio_summary(vfex_fee_pct=0.0, zse_fee_pct=0.0)
        self.assertLess(stat_sum["net_total_pnl"], gross_sum["total_pnl"])
        self.assertGreater(stat_sum["items"][0]["breakeven_price"], 0.2235)

        # 3. Overview news_top deduplicates same-ticker duplicates (e.g. Abridged + Full prospectus)
        self.store.state["last_fetch_at"] = datetime.now(timezone.utc).isoformat()
        self.store.state["news_cache"] = {
            "fetched_at": datetime.now(timezone.utc).isoformat(),
            "items": [
                {"id": "1", "title": "ABL.vx Abridged Prospectus", "symbols": ["ABL"], "tracked": False, "official": True, "sentiment": "Bullish", "category": "Listing", "published_at": "2026-11-16T10:00:00+00:00", "date": "2026-11-16"},
                {"id": "2", "title": "ABL.vx Full Prospectus", "symbols": ["ABL"], "tracked": False, "official": True, "sentiment": "Bullish", "category": "Listing", "published_at": "2026-11-16T09:00:00+00:00", "date": "2026-11-16"},
                {"id": "3", "title": "AAU.vx Prospectus", "symbols": ["AAU"], "tracked": False, "official": True, "sentiment": "Bullish", "category": "Listing", "published_at": "2026-11-15T09:00:00+00:00", "date": "2026-11-15"},
                {"id": "4", "title": "INV.vx Rig-Up Underway", "symbols": ["INV"], "tracked": False, "official": True, "sentiment": "Bullish", "category": "Expansion", "published_at": "2026-11-14T09:00:00+00:00", "date": "2026-11-14"},
            ],
        }
        panel = format_panel_json(self.store, enable_agent=False)
        top_syms = [tuple(n.get("symbols") or []) for n in panel["news_top"]]
        self.assertEqual(len(top_syms), 3)
        self.assertEqual(len(set(top_syms)), 3)
        self.assertTrue(panel["fee_config"]["vfex_statutory"])

    def test_morgan_co_contract_note_parser_pdf_and_duplicate_guard(self) -> None:
        sample_buy_note = """\
We confirm we have traded the following securities
ECONET INFRACO                                                     38 ORDINARY SHARES
These shares were on the Zimbabwe Stock Exchange at a price of      $0.22350 dollars per share
Description of Security               Number Of Shares      Price (USD)          Consideration (USD$)
ECONET INFRACO                             38                $0.2235                     $8.4930
Less Charges          Commission @ 0.6%                      $0.05
            0.59 % Brokerage fees                                                              0.05
            0.00 % Capital gains with holding Tax                                              0.00
            0.00 % Investor Protection Levy                                                    0.00
                   Basic Charge                                                                0.00
            0.12 % Platform Levy                                                               0.01
            0.12 % SECZ Levy                                                                   0.01
            0.00 % Settlement Levy                                                             0.00
            0.24 % Stamp Duty                                                                  0.02
              15% VAT on Brokerage                                                             0.01
                                      Total Charges                                           $0.10
                      Total Net Consideration USD                                             $8.60
We anticipate these securities will be delivered in good order against payment on:         13/10/2026
For and on behalf of MORGAN & CO
"""
        self.store.set_price("INFR", 0.2235)
        parsed = parse_contract_note_text(sample_buy_note, store=self.store)
        self.assertTrue(parsed["ok"])
        self.assertEqual(parsed["broker"], "Morgan & Co")
        self.assertEqual(parsed["side"], "BUY")
        self.assertEqual(parsed["symbol"], "INFR")
        self.assertTrue(parsed["symbol_matched"])
        self.assertEqual(parsed["shares"], 38.0)
        self.assertAlmostEqual(parsed["price"], 0.2235, places=4)
        self.assertAlmostEqual(parsed["gross"], 8.4930, places=4)
        self.assertAlmostEqual(parsed["total_charges"], 0.10, places=2)
        self.assertAlmostEqual(parsed["net_settlement"], 8.60, places=2)
        self.assertEqual(parsed["date"], "2026-10-13")
        note = parsed["contract_note"]
        self.assertAlmostEqual(note["brokerage"], 0.05, places=2)
        self.assertAlmostEqual(note["stamp_duty"], 0.02, places=2)
        self.assertAlmostEqual(note["vat"], 0.01, places=2)
        self.assertAlmostEqual(note["platform_levy"], 0.01, places=2)
        self.assertAlmostEqual(note["secz_levy"], 0.01, places=2)

        # Dry-run preview does not record trade
        preview = self.store.import_contract_note(sample_buy_note, tag="core", dry_run=True, is_text=True)
        self.assertFalse(preview["duplicate"])
        self.assertEqual(len(self.store.state["trades"]), 0)

        # Commit import attaches itemized charges & records position
        res = self.store.import_contract_note(sample_buy_note, tag="core", dry_run=False, is_text=True)
        self.assertTrue(res["imported"])
        self.assertEqual(len(self.store.state["trades"]), 1)
        trade = self.store.state["trades"][0]
        self.assertEqual(trade["symbol"], "INFR")
        self.assertEqual(self.store.state["strategy_tags"].get("INFR"), "core")
        self.assertAlmostEqual(trade["contract_note"]["total_charges"], 0.10, places=2)

        # Duplicate guard blocks repeat import unless allow_duplicate=True
        dup_preview = self.store.import_contract_note(sample_buy_note, dry_run=True, is_text=True)
        self.assertTrue(dup_preview["duplicate"])
        with self.assertRaises(ValueError):
            self.store.import_contract_note(sample_buy_note, dry_run=False, is_text=True)

        # Text file extraction via extract_contract_note_file + SELL note detection (CGT > 0, Net < Gross)
        note_path = Path(self.tmp.name) / "morgan_sell.txt"
        sell_text = """\
We confirm we have SOLD the following securities
ECONET INFRACO 10 ORDINARY SHARES at $0.3000 per share
Consideration (USD$) $3.0000
0.59 % Brokerage fees 0.02
2.00 % Capital gains with holding Tax 0.06
Total Charges $0.10
Total Net Consideration USD $2.90
payment on: 20/10/2026
For and on behalf of MORGAN & CO
"""
        note_path.write_text(sell_text, encoding="utf-8")
        extracted = extract_contract_note_file(note_path, store=self.store)
        self.assertEqual(extracted["side"], "SELL")
        self.assertEqual(extracted["date"], "2026-10-20")
        sell_res = self.store.import_contract_note(str(note_path), tag="swing", is_text=False)
        self.assertTrue(sell_res["imported"])
        self.assertEqual(self.store.state["portfolio"]["INFR"]["shares"], 28.0)

        # CLI parser verification
        parser = build_parser()
        args = parser.parse_args(["import-note", "--preview", "--json", "--tag", "core", "--text", "sample"])
        self.assertEqual(args.command, "import-note")
        self.assertTrue(args.preview)
        self.assertTrue(args.json)
        self.assertEqual(args.tag, "core")

    def test_news_14d_cutoff_title_date_decay_and_recency_buckets(self) -> None:
        # 1. Embedded title dates parsed cleanly
        dt_oct = _extract_title_news_date("ABL.vx Abridged Prospectus - 14 Oct 2026")
        self.assertIsNotNone(dt_oct)
        self.assertEqual((dt_oct.year, dt_oct.month, dt_oct.day), (2026, 10, 14))
        dt_nov = _extract_title_news_date("AAU.vx Prospectus - 09 Nov 2026")
        self.assertIsNotNone(dt_nov)
        self.assertEqual((dt_nov.year, dt_nov.month, dt_nov.day), (2026, 11, 9))

        # 2. Age decay schedule: 0-3d 100%, 4-7d 70%, 8-14d 40%, >14d 0%
        self.assertAlmostEqual(_news_age_weight(1), 1.0)
        self.assertAlmostEqual(_news_age_weight(5), 0.70)
        self.assertAlmostEqual(_news_age_weight(10), 0.40)
        self.assertAlmostEqual(_news_age_weight(15), 0.0)

        # 3. fetch_vfex_news uses when:14d and drops >14d items & back-uploaded older docs
        now_dt = datetime.now(timezone.utc)
        fresh_rss = (now_dt - timedelta(days=1)).strftime("%a, %d %b %Y %H:%M:%S GMT")
        stale_rss = (now_dt - timedelta(days=20)).strftime("%a, %d %b %Y %H:%M:%S GMT")
        backdated_str = (now_dt - timedelta(days=30)).strftime("%d %b %Y")
        rss_xml = f"""<?xml version="1.0" encoding="UTF-8"?>
        <rss><channel>
          <item>
            <title>Simbisa Revenue Rises 24% on Zimbabwe Growth - The Zimbabwe Mail</title>
            <link>https://example.com/sim-fresh</link>
            <pubDate>{fresh_rss}</pubDate>
            <source>The Zimbabwe Mail</source>
          </item>
          <item>
            <title>Old October Zimbabwe Stock Exchange Update - Herald</title>
            <link>https://example.com/zse-stale</link>
            <pubDate>{stale_rss}</pubDate>
            <source>Herald</source>
          </item>
        </channel></rss>"""
        vfex_docs = json.dumps([
            {
                "id": 911,
                "doc_name": f"ABL.vx Abridged Prospectus - {backdated_str}",
                "exchange": "VFEX",
                "category": "issuer",
                "created_at": now_dt.isoformat(),
                "download_url": "https://example.com/abl-old.pdf",
                "issuer": None,
            },
            {
                "id": 912,
                "doc_name": "INV.vx Notice to Shareholders - Exploration Update",
                "exchange": "VFEX",
                "category": "announcements",
                "created_at": (now_dt - timedelta(days=10)).isoformat(),
                "download_url": "https://example.com/inv-10d.pdf",
                "issuer": None,
            },
        ])
        seen_urls: list[str] = []

        def fake_fetcher(url: str) -> str:
            seen_urls.append(url)
            if "exchange=VFEX" in url:
                return vfex_docs
            if "news.google.com" in url:
                return rss_xml
            return "[]"

        res = fetch_vfex_news(self.store, force=True, fetcher=fake_fetcher)
        self.assertTrue(any("when%3A14d" in u or "when:14d" in u for u in seen_urls))
        titles = [it["title"] for it in res["items"]]
        self.assertTrue(any("Simbisa Revenue Rises" in t for t in titles))
        self.assertTrue(any("INV.vx Notice to Shareholders" in t for t in titles))
        self.assertFalse(any("Old October" in t for t in titles))
        self.assertFalse(any("ABL.vx Abridged Prospectus" in t for t in titles))

        # 4. _news_by_symbol applies recency decay and prefers 1d over 10d for same symbol
        cat_input = [
            {
                "id": "old10",
                "title": "Simbisa old expansion note",
                "symbols": ["SIM"],
                "category": "Expansion",
                "sentiment": "Bullish",
                "impact_score": 20,
                "age_days": 10,
                "date": (now_dt - timedelta(days=10)).date().isoformat(),
                "age_label": "10d ago",
            },
            {
                "id": "fresh1",
                "title": "Simbisa fresh dividend growth",
                "symbols": ["SIM"],
                "category": "Earnings",
                "sentiment": "Bullish",
                "impact_score": 16,
                "age_days": 1,
                "date": (now_dt - timedelta(days=1)).date().isoformat(),
                "age_label": "Yesterday",
            },
            {
                "id": "expired",
                "title": "Innscor stale October rumor",
                "symbols": ["INN"],
                "category": "Earnings",
                "sentiment": "Bullish",
                "impact_score": 20,
                "age_days": 20,
                "date": (now_dt - timedelta(days=20)).date().isoformat(),
                "age_label": "20d ago",
            },
        ]
        by_sym = self.store._news_by_symbol(cat_input)
        self.assertEqual(by_sym["SIM"]["id"], "fresh1")
        self.assertEqual(by_sym["SIM"]["impact_score"], 16)
        self.assertNotIn("INN", by_sym)

        # 5. Overview news_top puts <=3d non-official material news ahead of 10d official notice
        self.store.state["last_fetch_at"] = now_dt.isoformat()
        panel = format_panel_json(self.store, enable_news=True)
        top_titles = [n["title"] for n in panel["news_top"]]
        self.assertGreaterEqual(len(top_titles), 2)
        self.assertIn("Simbisa Revenue Rises", top_titles[0])

    def test_agent_sizing_min_floor_uncapped_and_voms_holdings_sync(self) -> None:
        # 1. Dust protection: leftover < $15 USD eqv must be skipped
        agent = self.store.reset_paper_agent(starting_usd=100.0, zwg_rate=26.5)
        agent["cash_zwg"] = 100.0  # ~$3.77 USD eqv -> below $15 floor
        res_dust = self.store._execute_paper_buy(
            agent,
            {"symbol": "WILD.ZW", "currency": "ZWG", "horizon": "SWING", "score": 45, "price": 0.10, "reasons": ["Test"]},
            "2026-11-16",
        )
        self.assertIsNone(res_dust)

        # 2. High-conviction sizing removes $25 ceiling on larger equity & allocates 35% vs 18%
        agent_big = self.store.reset_paper_agent(starting_usd=400.0, zwg_rate=26.5)
        rec_hi = self.store._execute_paper_buy(
            agent_big,
            {"symbol": "SIM", "currency": "USD", "horizon": "CORE", "score": 60, "price": 0.50, "reasons": ["Strong"]},
            "2026-11-16",
        )
        self.assertIsNotNone(rec_hi)
        hi_gross = float(rec_hi["shares"]) * float(rec_hi["price"])
        self.assertGreater(hi_gross, 120.0)  # ~35% of $400 = $140, uncapped above $25

        rec_lo = self.store._execute_paper_buy(
            agent_big,
            {"symbol": "INSC", "currency": "USD", "horizon": "SWING", "score": 25, "price": 0.40, "reasons": ["Mild"]},
            "2026-11-16",
        )
        self.assertIsNotNone(rec_lo)
        lo_gross = float(rec_lo["shares"]) * float(rec_lo["price"])
        self.assertLess(lo_gross, hi_gross * 0.65)  # 18% tier clearly smaller than 35% tier

        # 3. VFEX Direct /holdings bucket extraction ('equity' + string 'volume' + '.VX' strip)
        orig_req = self.store._voms_request

        def fake_voms_ok(url: str, method: str = "GET", body=None, token: str | None = None):
            if url.endswith("/holdings"):
                return {
                    "status": "SUCCESS",
                    "data": {
                        "summary": {"totalValue": 9.41},
                        "equity": [{
                            "symbol": "INFR.VX",
                            "exchange": "VFEX",
                            "volume": "38",
                            "openingPrice": 0.2474,
                            "closingPrice": 0.2477,
                        }],
                        "reit": [],
                    },
                }
            raise ValueError("HTTP 500: INTERNAL_ERROR")

        self.store._voms_request = fake_voms_ok  # type: ignore[method-assign]
        try:
            synced = self.store._voms_sync_with_token("vfex_direct", "tok")
            self.assertEqual(synced["holdings_synced"], 1)
            ac_h = self.store.state["synced_accounts"]["vfex_direct"]["holdings"]
            self.assertEqual(ac_h[0]["symbol"], "INFR")
            self.assertEqual(ac_h[0]["shares"], 38.0)
            self.assertAlmostEqual(ac_h[0]["avg_cost"], 0.2474, places=4)

            # 4. If all holdings endpoints fail, raise instead of reporting 0 holdings
            def fake_voms_err(url: str, method: str = "GET", body=None, token: str | None = None):
                raise ValueError("HTTP 500: INTERNAL_ERROR")

            self.store._voms_request = fake_voms_err  # type: ignore[method-assign]
            with self.assertRaises(ValueError):
                self.store._voms_sync_with_token("vfex_direct", "tok")
        finally:
            self.store._voms_request = orig_req  # type: ignore[method-assign]

    def test_deduped_history_rsi_floor_and_same_symbol_sync_reconciliation(self) -> None:
        # 1. Out-of-order / duplicate snapshot dates collapse cleanly and tiny flat ticks don't hallucinate RSI=100
        self.store.set_price("INFR", 0.2474, date="2026-11-13")
        self.store.set_price("INFR", 0.2477, date="2026-11-16")
        self.store.set_price("INFR", 0.2477, date="2026-11-17")
        self.store.set_price("INFR", 0.2477, date="2026-11-16")
        self.store.set_price("INFR", 0.2477, date="2026-11-17")
        candles = self.store.get_candles("INFR")
        self.assertEqual([c["date"] for c in candles], ["2026-11-13", "2026-11-16", "2026-11-17"])
        tech = compute_symbol_technicals(self.store.state["history"]["INFR"], 0.2477)
        self.assertIsNone(tech["rsi14"])

        # 2. Matching (symbol, shares) between Manual ledger and synced VFEX Direct deduplicates without doubling value
        self.store.buy("INFR", 38, 0.2235, date="2026-10-09")
        self.store.state["synced_accounts"] = {
            "vfex_direct": {
                "holdings": [{"symbol": "INFR", "shares": 38.0, "avg_cost": 0.2474, "currency": "USD"}],
                "cash_usd": 0.0,
                "cash_zwg": 0.0,
                "last_sync": "2026-11-17T05:00:00+00:00",
            }
        }
        summary = self.store.portfolio_summary()
        self.assertEqual(len(summary["items"]), 1)
        self.assertEqual(summary["items"][0]["synced_source"], "VFEX-D")
        self.assertAlmostEqual(summary["total_value"], round(38 * 0.2477, 2), places=2)

    def test_mahoraga_brain_playbooks_immunities_shadows_and_train(self) -> None:
        agent = self.store.reset_paper_agent(starting_usd=100.0, zwg_rate=26.5)
        # 1. Online update from wide-spread Book Imbalance loss spins Spread Trap Shield & updates weights
        w_spread_before = agent["brain"]["logistic_weights"]["spread"]
        notes = self.store._mahoraga_update(
            agent,
            feat_vec={"bias": 1.0, "dip": 0.0, "rsi_oversold": 0.0, "book": 0.8, "news": 0.0, "volume": 0.0, "spread": 1.0, "zse": 0.0},
            playbook="Book Imbalance",
            net_pnl_pct=-8.5,
            spread_pct=12.0,
            is_zse=False,
            dip_30d=0.5,
            has_dtr_vol=False,
            as_of_date="2026-11-10",
            is_shadow=False,
        )
        self.assertEqual(agent["brain"]["adaptations_spun"], 1)
        self.assertLess(agent["brain"]["logistic_weights"]["spread"], w_spread_before)
        self.assertTrue(any("Spread Trap Shield" in n for n in notes))
        self.assertTrue(agent["brain"]["immunities"]["wide_spread_trap"]["active"])
        self.assertLess(agent["brain"]["playbooks"]["Book Imbalance"]["mult"], 1.0)

        # 2. Active Spread Trap Shield blocks wide-spread (>8%) candidate & logs counterfactual shadow
        wide_prices = {
            "TRAP": {"price": 0.20, "currency": "USD", "change_pct": -5.0, "best_bid": 0.175, "best_ask": 0.205, "bid_volume": 900, "ask_volume": 100},
        }
        cands = self.store._agent_score_candidates(agent, wide_prices, {}, {}, "2026-11-10")
        self.assertEqual(cands, [])
        self.assertGreaterEqual(len(agent["shadows"]), 1)
        self.assertEqual(agent["shadows"][0]["symbol"], "TRAP")
        self.assertFalse(agent["shadows"][0]["resolved"])

        # 3. Five days later, shadow evaluates against live price & increments adaptations_spun
        later_prices = {"TRAP": {"price": 0.16, "currency": "USD"}}
        resolved = self.store._evaluate_agent_shadows(agent, later_prices, "2026-11-16")
        self.assertEqual(resolved, 1)
        self.assertTrue(agent["shadows"][0]["resolved"])
        self.assertLess(agent["shadows"][0]["shadow_net_pct"], -10.0)
        self.assertGreaterEqual(agent["brain"]["adaptations_spun"], 2)

        # 4. Warm-train on stored 30D history preserves live cash & positions untouched
        agent["cash_usd"] = 55.30
        agent["positions"]["FCA"] = {
            "symbol": "FCA", "currency": "USD", "horizon": "CORE", "shares": 148.0,
            "entry_price": 0.165, "last_price": 0.165, "peak_price": 0.165,
            "entry_cost_net": 24.70, "entry_date": "2026-11-16", "entry_score": 48,
            "playbook": "DTR Flow", "win_prob_pct": 62.0,
        }
        for d in range(1, 16):
            self.store.set_price("SIM", round(0.42 - (d % 5) * 0.015, 4), date=f"2026-11-{d:02d}", best_bid=0.35, best_ask=0.36, bid_volume=600, ask_volume=100)
        trained_sum = self.store.train_paper_agent_brain(days=15)
        self.assertAlmostEqual(trained_sum["cash_usd"], 55.30)
        self.assertEqual(len(trained_sum["positions"]), 1)
        self.assertEqual(trained_sum["positions"][0]["symbol"], "FCA")
        self.assertEqual(trained_sum["positions"][0]["playbook"], "DTR Flow")
        self.assertIn("brain", trained_sum)
        self.assertEqual(len(trained_sum["brain"]["playbooks"]), 4)
        self.assertEqual(build_parser().parse_args(["agent", "train", "--days", "30", "--json"]).action, "train")

    def test_adaptive_exit_policy_radar_and_train_live_merge(self) -> None:
        agent = self.store.reset_paper_agent(starting_usd=100.0, zwg_rate=26.5)
        self.store.state["prices"]["FML.ZW"] = {"price": 4.10, "currency": "ZWG", "best_bid": 4.05, "best_ask": 4.15}
        # Simulate FML.ZW entered as CORE and exited on Day 1 at flat 4.10 via non-official Caution news (-4.31% fee churn)
        agent["positions"]["FML.ZW"] = {
            "symbol": "FML.ZW", "currency": "ZWG", "horizon": "CORE", "shares": 122.0,
            "entry_price": 4.10, "last_price": 4.10, "peak_price": 4.10,
            "entry_cost_net": 508.02, "entry_charges_usd": 0.30, "entry_date": "2026-11-16",
            "entry_score": 42, "playbook": "DTR Flow",
            "entry_features": {"dip_30d": 0.0, "spread_pct": 2.4, "is_zse": True, "vol_pts": 15.0},
        }
        sell_rec = self.store._execute_paper_sell(agent, "FML.ZW", 4.10, "2026-11-17", "Cautionary news risk (-4.3% net)")
        self.assertIsNotNone(sell_rec)
        # Brain itself adapted Caution Shield Tier from 0 -> 1 after flat-price fee churn
        self.assertEqual(agent["brain"]["exit_policy"]["caution_exit_strictness"], 1)
        self.assertEqual(agent["brain"]["exit_policy"]["premature_exit_losses"], 1)
        self.assertEqual(agent["brain"]["playbooks"]["DTR Flow"]["losses"], 1)

        # Next day, a non-official caution headline at flat price does NOT panic-sell a fresh CORE hold;
        # while a >= 2.5% drop or official caution notice still triggers exit at Tier 1.
        agent["positions"]["FCA"] = {
            "symbol": "FCA", "currency": "USD", "horizon": "CORE", "shares": 148.0,
            "entry_price": 0.165, "last_price": 0.165, "peak_price": 0.165,
            "entry_cost_net": 24.70, "entry_charges_usd": 0.28, "entry_date": "2026-11-17",
            "entry_score": 48, "playbook": "DTR Flow",
        }
        non_official_news = [{
            "id": "n1", "title": "FCA market chatter", "symbols": ["FCA"], "official": False,
            "sentiment": "Caution", "category": "Risk", "impact_score": -16, "age_days": 0, "date": "2026-11-17",
        }]
        self.store.run_paper_agent_step(
            as_of_date="2026-11-18", allow_off_hours=True,
            prices_override={"FCA": {"price": 0.165, "currency": "USD"}},
            news_items=non_official_news, save_state=False,
        )
        self.assertIn("FCA", agent["positions"])  # Hold preserved!

        # 2. train_paper_agent_brain preserves real closed FML.ZW experience instead of wiping it
        self.store.set_price("AXIA", 0.18, date="2026-11-16", change_pct=-5.0, best_bid=0.178, best_ask=0.182, bid_volume=600, ask_volume=50)
        summary = self.store.train_paper_agent_brain(days=10)
        dtr_pb = next(pb for pb in summary["brain"]["playbooks"] if pb["name"] == "DTR Flow")
        self.assertGreaterEqual(dtr_pb["losses"], 1)
        self.assertGreaterEqual(summary["brain"]["exit_policy"]["caution_exit_strictness"], 1)

        # 3. Summary radar exposes live candidate probabilities without mutating shadows count
        sh_before = summary["brain"]["shadows_total"]
        summary2 = self.store.paper_agent_summary()
        self.assertEqual(summary2["brain"]["shadows_total"], sh_before)
        self.assertIn("radar", summary2)
        self.assertIn("shielded", summary2)

    def test_mahoraga_v2_ucb_pending_limits_partial_scale_pyramid_and_regime(self) -> None:
        from vfex import _compute_market_regime

        agent = self.store.reset_paper_agent(starting_usd=100.0, zwg_rate=26.5)
        # 1. Book-depth guard filters out thin bid depth (< $8 exitable); ask-heavy wide spread stages 2d GTD Smart Limit
        self.store.state["history"]["SIM"] = [
            {"date": "2026-11-10", "price": 0.42},
            {"date": "2026-11-12", "price": 0.41},
        ]
        step_prices = {
            "THIN.ZW": {"price": 0.06, "currency": "ZWG", "change_pct": -6.0, "best_bid": 0.06, "best_ask": 0.062, "bid_volume": 35, "ask_volume": 50000},
            "SIM": {"price": 0.35, "currency": "USD", "change_pct": -5.0, "best_bid": 0.33, "best_ask": 0.38, "bid_volume": 100, "ask_volume": 500},
        }
        blocked = []
        cands = self.store._agent_score_candidates(agent, step_prices, self.store.state["history"], {}, "2026-11-16", blocked_out=blocked, record_shadows=False)
        self.assertTrue(any(b["symbol"] == "THIN.ZW" and "Thin Bid Depth" in b["block_reason"] for b in blocked))
        sim_cand = next((c for c in cands if c["symbol"] == "SIM"), None)
        self.assertIsNotNone(sim_cand)
        self.assertTrue(sim_cand["stage_limit"])

        # Step 1 stages SIM limit instead of crossing $0.38 wide ask
        self.store.run_paper_agent_step(as_of_date="2026-11-16", allow_off_hours=True, prices_override=step_prices, save_state=False)
        self.assertEqual(len(agent["pending_orders"]), 1)
        self.assertNotIn("SIM", agent["positions"])
        lim_px = float(agent["pending_orders"][0]["limit_price"])

        # Step 2: Ask drops down into resting limit -> pending order fills automatically
        fill_prices = {"SIM": {"price": lim_px, "currency": "USD", "change_pct": 0.0, "best_bid": round(lim_px * 0.99, 4), "best_ask": lim_px, "bid_volume": 400, "ask_volume": 500}}
        self.store.run_paper_agent_step(as_of_date="2026-11-17", allow_off_hours=True, prices_override=fill_prices, save_state=False)
        self.assertEqual(len(agent["pending_orders"]), 0)
        self.assertIn("SIM", agent["positions"])

        # 2. Partial scale-out 50% at take-target leaves remaining half riding; CORE pyramid adds 1 slice on +5% winner
        agent["positions"]["SIM"]["horizon"] = "SWING"
        agent["positions"]["SIM"]["shares"] = 100.0
        agent["positions"]["SIM"]["entry_date"] = "2026-11-10"
        agent["positions"]["SIM"]["entry_price"] = 0.30
        agent["positions"]["SIM"]["entry_cost_net"] = 30.35
        # Simulate +20% jump -> scales out 50 shares, leaves 50 shares with partial_taken=True
        self.store.run_paper_agent_step(
            as_of_date="2026-11-18", allow_off_hours=True,
            prices_override={"SIM": {"price": 0.37, "currency": "USD", "best_bid": 0.368, "best_ask": 0.372, "bid_volume": 500, "ask_volume": 500}},
            save_state=False,
        )
        self.assertIn("SIM", agent["positions"])
        self.assertAlmostEqual(agent["positions"]["SIM"]["shares"], 50.0)
        self.assertTrue(agent["positions"]["SIM"]["partial_taken"])

        # Pyramid check on winning CORE holding (>= +4% + Bid > 2*Ask)
        agent["cash_usd"] = 60.0
        agent["positions"]["FCA"] = {
            "symbol": "FCA", "currency": "USD", "horizon": "CORE", "shares": 100.0,
            "entry_price": 0.16, "last_price": 0.18, "peak_price": 0.18,
            "entry_cost_net": 16.20, "entry_charges_usd": 0.18, "entry_date": "2026-11-10", "entry_score": 50,
        }
        self.store.run_paper_agent_step(
            as_of_date="2026-11-19", allow_off_hours=True,
            prices_override={"FCA": {"price": 0.185, "currency": "USD", "best_bid": 0.184, "best_ask": 0.186, "bid_volume": 1000, "ask_volume": 200}},
            save_state=False,
        )
        self.assertTrue(agent["positions"]["FCA"].get("pyramided"))
        self.assertGreater(agent["positions"]["FCA"]["shares"], 100.0)

        # 3. Market Regime Risk-Off cash floor (40%) blocks buys when cash <= 40%
        ro_prices = {f"SYM{i}": {"price": 0.20, "change_pct": -3.0} for i in range(6)}
        reg = _compute_market_regime(ro_prices, {})
        self.assertEqual(reg["label"], "Risk-Off")
        self.assertEqual(reg["cash_floor_pct"], 40.0)
        agent_ro = self.store.reset_paper_agent(starting_usd=100.0)
        agent_ro["cash_usd"] = 18.0  # + $20 ZWG = $38 total cash < $40 floor
        buy_blocked = self.store._execute_paper_buy(
            agent_ro,
            {"symbol": "SIM", "currency": "USD", "horizon": "SWING", "score": 50, "price": 0.20, "reasons": ["Test"]},
            "2026-11-19", cash_floor_pct=40.0,
        )
        self.assertIsNone(buy_blocked)


if __name__ == "__main__":
    unittest.main()
