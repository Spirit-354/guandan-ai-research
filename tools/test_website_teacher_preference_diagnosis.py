from __future__ import annotations

import math
import sys
import unittest
from pathlib import Path

import torch


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import website_teacher_preference as preference
import website_teacher_preference_diagnosis as diagnosis


def sample(game_id: str, actions: list[list[float]], teacher: int, behavior: int) -> dict:
    return {
        "game_id": game_id,
        "turn_index": 1,
        "state": [0.0] * preference.STATE_DIM,
        "teacher_action": actions[teacher],
        "behavior_action": actions[behavior],
        "legal_actions": actions,
    }


def action(value: float) -> list[float]:
    result = [0.0] * preference.ACTION_DIM
    result[0] = value
    return result


class ActionValueModel(torch.nn.Module):
    def forward(self, states: torch.Tensor, actions: torch.Tensor) -> torch.Tensor:
        del states
        return actions[:, 0]


class NonfiniteModel(ActionValueModel):
    def forward(self, states: torch.Tensor, actions: torch.Tensor) -> torch.Tensor:
        values = super().forward(states, actions)
        return torch.where(actions[:, 0] == 9.0, torch.inf, values)


class WebsiteTeacherPreferenceDiagnosisTests(unittest.TestCase):
    def test_first_max_rank_ties_and_other_source(self) -> None:
        first = action(2.0)
        teacher = action(2.0)
        first[1] = 1.0
        teacher[1] = 2.0
        actions = [first, action(1.0), teacher, action(0.0)]
        item = sample("1", actions, teacher=2, behavior=1)
        state = diagnosis.diagnose_state(
            item, "pipeline_train", [2.0, 1.0, 2.0, 0.0]
        )
        self.assertEqual(state["top1_index"], 0)
        self.assertEqual(state["top1_source"], "other")
        self.assertEqual(state["teacher_rank"], 1)
        self.assertEqual(state["actions_tied_with_teacher_count"], 2)
        self.assertFalse(state["unpaired_action_strictly_outranks_teacher"])

    def test_exhaustive_scoring_preserves_recorded_duplicates(self) -> None:
        samples = [
            sample("1", [action(3.0), action(1.0), action(2.0), action(2.0)], 0, 1),
            sample("2", [action(0.0), action(4.0), action(1.0)], 1, 2),
        ]
        values, accounting = diagnosis.score_partition(ActionValueModel(), samples)
        self.assertEqual(values, [[3.0, 1.0, 2.0, 2.0], [0.0, 4.0, 1.0]])
        self.assertEqual(accounting["recorded_legal_action_count"], 7)
        self.assertEqual(accounting["legal_action_score_count"], 7)
        self.assertEqual(accounting["source_duplicate_action_vector_count"], 1)
        self.assertEqual(accounting["duplicate_action_scoring_count"], 0)

    def test_nonfinite_q_is_rejected(self) -> None:
        item = sample("1", [action(1.0), action(0.0), action(9.0)], 0, 1)
        with self.assertRaisesRegex(RuntimeError, "nonfinite"):
            diagnosis.score_partition(NonfiniteModel(), [item])

    def test_partition_mapping_rejects_unknown_and_overlap(self) -> None:
        samples = [sample("1", [action(1.0), action(0.0)], 0, 1)]
        with self.assertRaisesRegex(RuntimeError, "overlap"):
            diagnosis.map_partitions(
                samples,
                {
                    "pipeline_train_game_ids": ["1"],
                    "pipeline_development_game_ids": ["1"],
                },
            )
        with self.assertRaisesRegex(RuntimeError, "unknown or missing"):
            diagnosis.map_partitions(
                samples,
                {
                    "pipeline_train_game_ids": ["2"],
                    "pipeline_development_game_ids": [],
                },
            )

    def test_aggregate_arithmetic(self) -> None:
        states = [
            {
                "legal_action_count": 3,
                "teacher_rank": 1,
                "teacher_q": 3.0,
                "behavior_q": 1.0,
                "top1_source": "teacher",
                "top1_is_pass": False,
                "unpaired_action_strictly_outranks_teacher": False,
                "unpaired_actions_strictly_above_teacher_count": 0,
            },
            {
                "legal_action_count": 5,
                "teacher_rank": 3,
                "teacher_q": 0.0,
                "behavior_q": 1.0,
                "top1_source": "other",
                "top1_is_pass": True,
                "unpaired_action_strictly_outranks_teacher": True,
                "unpaired_actions_strictly_above_teacher_count": 2,
            },
        ]
        aggregate = diagnosis.aggregate_states(states)
        self.assertEqual(aggregate["legal_action_count"], 8)
        self.assertEqual(aggregate["teacher_over_behavior_rate"], 0.5)
        self.assertEqual(aggregate["other_action_top1_rate"], 0.5)
        self.assertEqual(aggregate["pass_top1_rate"], 0.5)
        self.assertEqual(aggregate["mean_teacher_rank"], 2.0)
        self.assertEqual(aggregate["median_teacher_rank"], 2.0)
        self.assertEqual(
            aggregate["unpaired_action_strictly_outranks_teacher_state_count"], 1
        )

    def test_pairwise_metrics_reuse_scored_values(self) -> None:
        samples = [
            sample("1", [action(2.0), action(1.0)], 0, 1),
            sample("2", [action(0.0), action(3.0)], 1, 0),
        ]
        values, _accounting = diagnosis.score_partition(ActionValueModel(), samples)
        states = [
            diagnosis.diagnose_state(item, "pipeline_train", item_values)
            for item, item_values in zip(samples, values)
        ]
        actual = diagnosis.pairwise_metrics(samples, states)
        frozen = preference.evaluate_preferences(ActionValueModel(), samples)
        self.assertEqual(
            actual,
            {key: frozen[key] for key in actual},
        )
        self.assertTrue(math.isfinite(actual["pairwise_loss"]))


if __name__ == "__main__":
    unittest.main()
