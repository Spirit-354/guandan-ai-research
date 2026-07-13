from __future__ import annotations

import itertools
import json
import random
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import website_information_set
import play_research_adaptive


class WebsiteInformationSetTests(unittest.TestCase):
    def test_teacher_builder_appends_to_validated_frozen_base(self) -> None:
        import torch

        behavior_action = [0.0] * 54
        teacher_action = [0.0] * 54
        teacher_action[3] = 1.0

        def source_sample(game_id: str) -> dict:
            return {
                "game_id": game_id,
                "turn_index": 2,
                "split": "train",
                "information_set_consistent": True,
                "state": [0.0] * 513,
                "hand_before": ["S3", "H3"],
                "chosen_cards": [],
                "chosen_action": behavior_action,
                "legal_actions": [behavior_action, teacher_action],
                "legal_action_metadata": [
                    {"cards": [], "action_type": "None"},
                    {"cards": ["S3"], "action_type": "single"},
                ],
            }

        def strong_label(game_id: str) -> dict:
            return {
                "game_id": game_id,
                "turn_index": 2,
                "state": [0.0] * 513,
                "teacher_action": {
                    "physical_cards_website": ["S3"],
                    "action_type": "single",
                },
                "behavior_action": {
                    "physical_cards_website": [],
                    "action_type": "None",
                    "mean_return": -0.5,
                },
                "rollout_count": 16,
                "hidden_card_sampling_method": "uniform_physical_assignment_given_public_counts_v1",
                "mean_return": 0.5,
                "return_variance": 0.0,
                "candidate_return_variance": 0.0,
                "paired_return_variance": 0.0,
                "candidate_advantage": 1.0,
                "advantage_95_lower_bound": 0.2,
                "label_confidence": 0.6,
                "continuation_policy_advantages": {
                    "greedy_bot": {"paired_count": 8, "mean_advantage": 1.0},
                    "tempo_baseline": {"paired_count": 8, "mean_advantage": 1.0},
                },
                "robust_across_continuation_profiles": True,
                "strong_teacher_label": True,
            }

        old_source = source_sample("old-game")
        new_source = source_sample("new-game")
        old_teacher, reason = website_information_set._teacher_sample_from_label(
            old_source,
            strong_label("old-game"),
            "old-rollout.json",
        )
        self.assertIsNone(reason)
        with tempfile.TemporaryDirectory() as temp_dir:
            temp = Path(temp_dir)
            source_path = temp / "source.pth"
            frozen_base_path = temp / "teacher-v1.pth"
            rollout_path = temp / "new-rollout.json"
            output_path = temp / "teacher-v2.pth"
            torch.save(
                {
                    "format": website_information_set.website_data.DATASET_FORMAT,
                    "summary": {
                        "partition_role": "train_development",
                        "contains_locked_test_samples": False,
                    },
                    "samples": [old_source, new_source],
                },
                source_path,
            )
            torch.save(
                {
                    "format": website_information_set.TEACHER_DATASET_SCHEMA_VERSION,
                    "summary": {
                        "accepted_teacher_label_count": 1,
                        "independent_teacher_games": 1,
                        "state_dim": 513,
                        "action_dim": 54,
                        "locked_test_loaded": False,
                        "threshold_passed": True,
                    },
                    "samples": [old_teacher],
                },
                frozen_base_path,
            )
            rollout_path.write_text(
                json.dumps(
                    {
                        "dataset_partition_role": "train_development",
                        "locked_test_loaded": False,
                        "all_cases_completed": True,
                        "threshold_passed": True,
                        "determinization_seed_scheme": "sha256_game_id_turn_index_determinization_index_v1",
                        "common_determinizations_across_continuation_profiles": True,
                        "future_information_used": False,
                        "opponent_or_teammate_true_hands_used": False,
                        "continuation_profiles": ["greedy_bot", "tempo_baseline"],
                        "strong_teacher_labels": [strong_label("new-game")],
                    }
                ),
                encoding="utf-8",
            )
            summary = website_information_set.build_teacher_dataset(
                SimpleNamespace(
                    website_information_set_teacher_base_dataset=str(source_path),
                    website_information_set_teacher_frozen_base=str(frozen_base_path),
                    build_website_information_set_teacher_dataset=str(rollout_path),
                    website_information_set_teacher_out=str(output_path),
                )
            )
            rebuilt = torch.load(output_path, map_location="cpu", weights_only=False)
        self.assertEqual(rebuilt["samples"][0], old_teacher)
        self.assertEqual(summary["frozen_teacher_base_label_count"], 1)
        self.assertEqual(summary["accepted_new_teacher_label_count"], 1)
        self.assertEqual(summary["accepted_teacher_label_count"], 2)
        self.assertEqual(summary["independent_teacher_games"], 2)
        self.assertEqual(summary["reject_reason_counts"], {})

    def test_legacy_rollout_completion_requires_exact_counts(self) -> None:
        payload = {
            "candidate_count": 4,
            "requested_rollouts_per_action": 16,
            "completed_rollouts": 64,
            "total_rollouts": 64,
            "integrity_failures": [],
            "threshold_passed": True,
        }
        self.assertTrue(website_information_set._rollout_payload_is_complete(payload))
        self.assertFalse(
            website_information_set._rollout_payload_is_complete(
                {**payload, "completed_rollouts": 63}
            )
        )

    def test_teacher_sample_maps_physical_cards_to_54_dim_action(self) -> None:
        behavior_action = [0.0] * 54
        teacher_action = [0.0] * 54
        teacher_action[3] = 1.0
        source = {
            "game_id": "g1",
            "turn_index": 2,
            "split": "train",
            "information_set_consistent": True,
            "state": [0.0] * 513,
            "hand_before": ["S3", "H3"],
            "chosen_cards": [],
            "chosen_action": behavior_action,
            "legal_actions": [behavior_action, teacher_action],
            "legal_action_metadata": [
                {"cards": [], "action_type": "None"},
                {"cards": ["S3"], "action_type": "single"},
            ],
        }
        label = {
            "game_id": "g1",
            "turn_index": 2,
            "state": [0.0] * 513,
            "teacher_action": {
                "physical_cards_website": ["S3"],
                "action_type": "single",
            },
            "behavior_action": {
                "physical_cards_website": [],
                "action_type": "None",
                "mean_return": -0.5,
            },
            "rollout_count": 16,
            "mean_return": 0.5,
            "candidate_advantage": 1.0,
            "advantage_95_lower_bound": 0.2,
        }
        sample, reason = website_information_set._teacher_sample_from_label(
            source, label, "rollout.json"
        )
        self.assertIsNone(reason)
        self.assertEqual(sample["teacher_action"], teacher_action)
        self.assertEqual(sample["behavior_action"], behavior_action)
        self.assertFalse(sample["locked_test_used"])

    def test_arena_finish_setup_shortcut_restores_engine_functions(self) -> None:
        engine = play_research_adaptive.engine
        original_follow = engine.choose_bomb_to_set_up_finish
        original_lead = engine.choose_lead_bomb_to_set_up_finish
        hand = [
            f"{suit}{rank}"
            for suit in "SHDC"
            for rank in "23456789TJQKA"
        ][:21]
        restore = play_research_adaptive.offline_install_arena_baseline_optimizations()
        try:
            self.assertIsNone(engine.choose_bomb_to_set_up_finish(hand, ["S3"], "7"))
            self.assertIsNone(engine.choose_lead_bomb_to_set_up_finish(hand, "7"))
        finally:
            restore()
        self.assertIs(engine.choose_bomb_to_set_up_finish, original_follow)
        self.assertIs(engine.choose_lead_bomb_to_set_up_finish, original_lead)

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
        self.assertFalse(
            website_information_set._strong_teacher_label(
                case_complete=True,
                paired_count=2,
                requested_count=2,
                advantage=1.0,
                candidate_return_variance=0.0,
                lower_bound=1.0,
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
