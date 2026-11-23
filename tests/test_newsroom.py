"""
Test Suite for Market Intelligence & News Analysis Subsystem (newsroom.py)
Verifies 12 categories, deduplication, confirmed vs commentary distinction,
7-section AI analysis, "Why This Matters To My Portfolio", and original source preservation.
"""

import unittest

from newsroom import (
    NEWS_CATEGORIES,
    build_newsroom_payload,
    classify_category,
    process_and_deduplicate_news,
)


class TestNewsroomSubsystem(unittest.TestCase):
    def test_categories_dedup_and_portfolio_impact(self) -> None:
        self.assertEqual(len(NEWS_CATEGORIES), 12)
        self.assertEqual(classify_category("RBZ raises bank policy rate in Monetary Policy Statement"), "Monetary policy")
        self.assertEqual(classify_category("Innscor declares USD interim dividend"), "Dividends")
        self.assertEqual(classify_category("ZWG exchange rate weakens against USD"), "Currency developments")

        raw = [
            {
                "id": "1",
                "title": "Innscor Africa declares interim dividend of $0.01",
                "source": "Local Blog Commentary",
                "url": "https://blog.example/infr",
                "official": False,
                "symbols": ["INFR"],
                "sentiment": "Bullish",
                "age_days": 0,
            },
            # Duplicate story from official exchange source -> should win deduplication
            {
                "id": "2",
                "title": "Innscor Africa declares interim dividend of $0.01",
                "source": "VFEX Announcements",
                "url": "https://vfex.exchange/announcements/infr-div",
                "official": True,
                "symbols": ["INFR"],
                "sentiment": "Bullish",
                "age_days": 0,
            },
            {
                "id": "3",
                "title": "RBZ Monetary Policy Committee holds interest rates steady",
                "source": "RBZ Official",
                "url": "https://rbz.co.zw/mpc",
                "official": True,
                "symbols": [],
                "sentiment": "Neutral",
                "age_days": 1,
            },
        ]
        holdings = [{"symbol": "INFR", "alloc_pct": 35.0, "pnl_pct": 4.2}]
        items = process_and_deduplicate_news(raw, holdings, zse_symbols={"DLTA"}, trading_goal="hybrid")

        # Deduplicated 3 -> 2, and official source won over blog
        self.assertEqual(len(items), 2)
        infr_item = next(i for i in items if "INFR" in i["affected_securities"])
        self.assertEqual(infr_item["source_type"], "CONFIRMED_ANNOUNCEMENT")
        self.assertEqual(infr_item["url"], "https://vfex.exchange/announcements/infr-div")
        self.assertTrue(infr_item["affects_portfolio"])

        # All 7 AI analysis sections present + original source preserved
        ai = infr_item["ai_analysis"]
        for key in (
            "original_headline", "publisher", "original_url",
            "what_happened", "why_it_matters", "affected_securities",
            "portfolio_impact", "market_impact", "what_to_watch", "confidence",
        ):
            self.assertIn(key, ai)
        self.assertIn("DIRECT IMPACT", ai["portfolio_impact"])

    def test_build_newsroom_payload_briefing(self) -> None:
        payload = build_newsroom_payload({
            "news": [
                {"title": "ZSE inflation report released", "source": "ZimStat", "url": "https://zimstat.co.zw", "official": True, "symbols": [], "age_days": 0}
            ],
            "items": [],
            "zse_symbols": ["DLTA"],
            "trading_goal": "long",
        })
        self.assertIn("daily_briefing", payload)
        self.assertEqual(payload["daily_briefing"]["headline_count"], 1)
        self.assertEqual(len(payload["economic_calendar"]), 1)


if __name__ == "__main__":
    unittest.main()
