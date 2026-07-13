from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import website_information_set


class WebsiteInformationSetTests(unittest.TestCase):
    def test_sample_variance(self) -> None:
        self.assertEqual(website_information_set._sample_variance([1.0]), 0.0)
        self.assertAlmostEqual(website_information_set._sample_variance([1.0, -1.0]), 2.0)

    def test_stratified_samples_prioritize_distinct_games(self) -> None:
        samples = []
        for game_id in ("a", "b", "c"):
            for turn in range(3):
                samples.append(
                    {
                        "game_id": game_id,
                        "turn_index": turn,
                        "split": "train",
                        "information_set_consistent": True,
                        "hand_counts": [20, 20, 20, 20],
                    }
                )
        selected = website_information_set._stratified_train_samples(samples, 3)
        self.assertEqual(len({sample["game_id"] for sample in selected}), 3)

    def test_pass_count_between_last_and_current_player(self) -> None:
        self.assertEqual(website_information_set._inferred_pass_count(3, 0, [27, 27, 27, 21]), 0)
        self.assertEqual(website_information_set._inferred_pass_count(1, 0, [10, 10, 10, 10]), 2)
        self.assertEqual(website_information_set._inferred_pass_count(1, 0, [10, 10, 0, 10]), 1)


if __name__ == "__main__":
    unittest.main()
