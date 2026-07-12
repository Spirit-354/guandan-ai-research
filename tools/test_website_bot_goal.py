from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import play_research_adaptive as research


class WebsiteBotGoalTests(unittest.TestCase):
    def test_wilson_target_requires_confident_seventy_percent(self) -> None:
        records = []
        for index in range(500):
            records.append(
                {
                    "game_counted": True,
                    "metric_source": "leaderboard_elo",
                    "profile": "tempo_baseline",
                    "completed_at": f"2026-07-13 {index:04d}",
                    "outcome": "win" if index < 375 else "loss",
                    "elo_before": 2250,
                    "elo_after": 2251,
                    "elo_delta": 1 if index < 375 else -1,
                    "opponent_signature": "bot-a|bot-b",
                    "bot_table_verified": True,
                }
            )
        summary = research.website_bot_goal_summary({"game_records": records})
        self.assertEqual(summary["target_high_elo_segment"]["games"], 500)
        self.assertGreater(summary["target_high_elo_segment"]["wilson_95_lower"], 0.70)
        self.assertTrue(summary["statistical_target_passed"])
        self.assertFalse(summary["final_goal_passed"])

    def test_elo_band_uses_observed_hundred_point_ranges(self) -> None:
        self.assertEqual(research.elo_band_for_value(2199), "2100-2199")
        self.assertEqual(research.elo_band_for_value(2200), "2200-2299")
        self.assertEqual(research.elo_band_for_value(None), "unknown")

    def test_bot_only_table_signature(self) -> None:
        verified = research.website_bot_table_evidence(
            {"seats": ["\u73a9\u5bb61", "\u73a9\u5bb62", "\u73a9\u5bb63", "\u73a9\u5bb64"], "your_seat": 0}
        )
        rejected = research.website_bot_table_evidence(
            {"seats": ["\u73a9\u5bb61", "Alice", "\u73a9\u5bb63", "Bob"], "your_seat": 0}
        )
        self.assertTrue(verified["bot_table_verified"])
        self.assertFalse(rejected["bot_table_verified"])


if __name__ == "__main__":
    unittest.main()
