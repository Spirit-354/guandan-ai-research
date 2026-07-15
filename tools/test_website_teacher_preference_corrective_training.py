from __future__ import annotations

import copy
from pathlib import Path
import sys
import tempfile
import unittest

import torch


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import website_teacher_preference_corrective_training as training


class SumModel(torch.nn.Module):
    def forward(self, states: torch.Tensor, actions: torch.Tensor) -> torch.Tensor:
        return states[:, 0] + actions[:, 0]


def pair(
    pair_id: str,
    game_id: str,
    turn_index: int,
    preferred: float,
    rejected: float,
    weight: float,
    partition: str = "pipeline_train",
    source: str = "frozen_teacher_v6",
) -> dict:
    preferred_action = [0.0] * 54
    rejected_action = [0.0] * 54
    preferred_action[0] = preferred
    rejected_action[0] = rejected
    return {
        "pair_id": pair_id,
        "game_id": game_id,
        "turn_index": turn_index,
        "pipeline_partition": partition,
        "pair_source": source,
        "state": [0.0] * 513,
        "preferred_action": preferred_action,
        "rejected_action": rejected_action,
        "within_state_pair_weight": weight,
    }


class CorrectiveTrainingTests(unittest.TestCase):
    def test_grouped_loss_uses_frozen_pair_weights_then_equal_states(self) -> None:
        pairs = [
            pair("a", "1", 1, 2.0, 0.0, 0.25),
            pair("b", "1", 1, 1.0, 0.0, 0.75),
            pair("c", "2", 1, 0.0, 1.0, 1.0),
        ]
        groups = training.build_state_groups(pairs)
        actual = training.state_balanced_batch_loss(SumModel(), groups)
        expected_state_1 = 0.25 * torch.nn.functional.softplus(torch.tensor(-2.0))
        expected_state_1 += 0.75 * torch.nn.functional.softplus(torch.tensor(-1.0))
        expected_state_2 = torch.nn.functional.softplus(torch.tensor(1.0))
        self.assertAlmostEqual(actual.item(), ((expected_state_1 + expected_state_2) / 2).item())

    def test_groups_preserve_train_development_isolation(self) -> None:
        pairs = [
            pair("train", "1", 1, 1.0, 0.0, 1.0),
            pair("development", "2", 1, 1.0, 0.0, 1.0, "pipeline_development"),
        ]
        groups = training.build_state_groups(pairs)
        self.assertEqual([group["pipeline_partition"] for group in groups], [
            "pipeline_train",
            "pipeline_development",
        ])
        self.assertNotEqual(groups[0]["key"], groups[1]["key"])

    def test_fixed_recipe_matches_stage_contract(self) -> None:
        self.assertEqual(training.fixed_recipe(), {
            "device": "cpu",
            "seed": 20260714,
            "epochs": 20,
            "states_per_batch": 6,
            "learning_rate": 0.001,
            "initial_checkpoint": None,
            "model_architecture": "danzero_dmc.build_q_model",
            "state_dim": 513,
            "action_dim": 54,
            "objective": (
                "mean_states(sum_pairs(within_state_pair_weight*"
                "softplus(Q_rejected-Q_preferred)))"
            ),
        })

    def test_pair_metrics_and_digest_are_deterministic(self) -> None:
        pairs = [
            pair("a", "1", 1, 2.0, 0.0, 1.0),
            pair("b", "2", 1, 0.0, 1.0, 1.0),
        ]
        first = training.evaluate_partition(SumModel(), pairs)
        second = training.evaluate_partition(SumModel(), copy.deepcopy(pairs))
        self.assertEqual(first, second)
        self.assertEqual(first["pair_ranking_accuracy"], 0.5)
        self.assertEqual(first["nonfinite_value_count"], 0)

    def test_checkpoint_metadata_is_frozen_and_unpromoted(self) -> None:
        model = torch.nn.Linear(2, 1)
        hashes = {"input": "abc"}
        payload = training.checkpoint_payload(model, hashes)
        self.assertEqual(payload["schema_version"], training.CHECKPOINT_SCHEMA_VERSION)
        self.assertEqual(payload["frozen_input_hashes"], hashes)
        self.assertEqual(payload["pipeline_development_training_use_count"], 0)
        self.assertIs(payload["checkpoint_promotion_allowed"], False)
        self.assertIs(payload["capability_claim_allowed"], False)

    def test_checkpoint_write_is_atomic_and_refuses_overwrite(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "checkpoint.pth"
            training.save_checkpoint_once(path, {"value": 1})
            self.assertTrue(path.exists())
            self.assertFalse(path.with_name(f"{path.name}.tmp").exists())
            with self.assertRaisesRegex(RuntimeError, "already exists"):
                training.save_checkpoint_once(path, {"value": 2})

    def test_output_guard_refuses_existing_report(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            original_checkpoint = training.CHECKPOINT_PATH
            original_report = training.REPORT_PATH
            try:
                training.CHECKPOINT_PATH = Path(directory) / "checkpoint.pth"
                training.REPORT_PATH = Path(directory) / "report.json"
                training.REPORT_PATH.write_text("{}", encoding="utf-8")
                with self.assertRaisesRegex(RuntimeError, "already exists"):
                    training.ensure_unused_outputs()
            finally:
                training.CHECKPOINT_PATH = original_checkpoint
                training.REPORT_PATH = original_report


if __name__ == "__main__":
    unittest.main()
