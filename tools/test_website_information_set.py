from __future__ import annotations

import sys
import unittest
from pathlib import Path
import itertools
import random


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import website_information_set
import play_research_adaptive


class WebsiteInformationSetTests(unittest.TestCase):
    def test_unique_card_combinations_match_position_combinations(self) -> None:
        hand = sorted(["S3", "S3", "H4", "H4", "D5", "C6"])
        for size in range(1, len(hand) + 1):
            expected = list(dict.fromkeys(itertools.combinations(hand, size)))
            actual = list(play_research_adaptive.offline_unique_card_combinations(hand, size))
            self.assertEqual(expected, actual)

    def test_sample_variance(self) -> None:
        self.assertEqual(website_information_set._sample_variance([1.0]), 0.0)
        self.assertAlmostEqual(website_information_set._sample_variance([1.0, -1.0]), 2.0)

    def test_determinization_seed_is_case_stable(self) -> None:
        sample = {"game_id": "g1", "turn_index": 7}
        self.assertEqual(
            website_information_set._stable_determinization_seed(sample, 3),
            website_information_set._stable_determinization_seed(dict(sample), 3),
        )
        self.assertNotEqual(
            website_information_set._stable_determinization_seed(sample, 3),
            website_information_set._stable_determinization_seed(sample, 4),
        )

    def test_baseline_cache_key_includes_public_history_and_ranking(self) -> None:
        class Game:
            current_player = 0

        class Adaptive:
            def __init__(self) -> None:
                self.state = {
                    "level": "7",
                    "your_hand": ["S3"],
                    "trick_history": [],
                    "ranking": [],
                }

            def offline_arena_state_for_player(self, game, player_id):
                del game, player_id
                return dict(self.state)

        adaptive = Adaptive()
        first = website_information_set._baseline_visible_state_key(Game(), adaptive)
        adaptive.state["trick_history"] = [[1, ["S4"]]]
        second = website_information_set._baseline_visible_state_key(Game(), adaptive)
        adaptive.state["ranking"] = [2]
        third = website_information_set._baseline_visible_state_key(Game(), adaptive)
        self.assertNotEqual(first, second)
        self.assertNotEqual(second, third)

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

    def test_observable_risk_prefers_endgame_pass_with_beat(self) -> None:
        base = {
            "hand_counts": [10, 5, 10, 9],
            "your_seat": 0,
            "was_follow": True,
            "chosen_cards": [],
            "legal_action_metadata": [{"cards": []}, {"cards": ["S9"]}],
            "scenario": "endgame_danger_high",
            "legal_action_count": 2,
        }
        quiet = {**base, "hand_counts": [20, 20, 20, 20], "chosen_cards": ["S9"], "scenario": "all_unknown"}
        self.assertGreater(
            website_information_set._observable_risk_score(base),
            website_information_set._observable_risk_score(quiet),
        )

    def test_teacher_variance_gate_applies_to_candidate_return(self) -> None:
        self.assertTrue(
            website_information_set._strong_teacher_label(
                case_complete=True,
                paired_count=16,
                requested_count=16,
                advantage=0.5,
                candidate_return_variance=0.0,
                lower_bound=0.1,
                robust_across_profiles=True,
                min_advantage=0.15,
                max_return_variance=0.5,
            )
        )
        self.assertFalse(
            website_information_set._strong_teacher_label(
                case_complete=False,
                paired_count=16,
                requested_count=16,
                advantage=0.5,
                candidate_return_variance=0.2,
                lower_bound=0.2,
                robust_across_profiles=True,
                min_advantage=0.15,
                max_return_variance=0.5,
            )
        )

    def test_fast_exact_remaining_groups_matches_original(self) -> None:
        engine = play_research_adaptive.engine
        deck = [
            f"{suit}{rank}"
            for suit in "SHDC"
            for rank in "23456789TJQKA"
            for _ in range(2)
        ] + ["B", "B", "R", "R"]
        rng = random.Random(20260713)
        hands = [
            [],
            ["S3"],
            ["S3", "H3"],
            ["S3", "H3", "D3", "S4", "H4"],
            ["S2", "H3", "D4", "C5", "S6"],
        ]
        for size in range(3, 9):
            hands.extend(rng.sample(deck, size) for _ in range(3))
        for level in ("2", "7", "Q"):
            for hand in hands:
                hand_key = tuple(engine.sort_cards(list(hand), level))
                self.assertEqual(
                    engine.exact_remaining_groups(hand_key, level),
                    play_research_adaptive.offline_exact_remaining_groups_fast(hand_key, level),
                )
        self.assertFalse(
            website_information_set._strong_teacher_label(
                case_complete=True,
                paired_count=16,
                requested_count=16,
                advantage=0.5,
                candidate_return_variance=0.75,
                lower_bound=0.1,
                robust_across_profiles=True,
                min_advantage=0.15,
                max_return_variance=0.5,
            )
        )
    def test_pass_count_between_last_and_current_player(self) -> None:
        self.assertEqual(website_information_set._inferred_pass_count(3, 0, [27, 27, 27, 21]), 0)
        self.assertEqual(website_information_set._inferred_pass_count(1, 0, [10, 10, 10, 10]), 2)
        self.assertEqual(website_information_set._inferred_pass_count(1, 0, [10, 10, 0, 10]), 1)


if __name__ == "__main__":
    unittest.main()
