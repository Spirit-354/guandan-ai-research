from __future__ import annotations

import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import website_teacher_preference_corrective_dataset as corrective


def vector(index: int) -> list[float]:
    result = [0.0] * 54
    result[index] = 1.0
    return result


class CorrectiveDatasetTests(unittest.TestCase):
    def test_canonical_hash_is_key_order_independent(self) -> None:
        self.assertEqual(
            corrective.canonical_sha256({"a": 1, "b": [2]}),
            corrective.canonical_sha256({"b": [2], "a": 1}),
        )

    def test_state_balanced_weights_sum_to_one_per_state(self) -> None:
        pairs = [
            {"pipeline_partition": "pipeline_train", "game_id": "1", "turn_index": 2},
            {"pipeline_partition": "pipeline_train", "game_id": "1", "turn_index": 2},
            {"pipeline_partition": "pipeline_train", "game_id": "2", "turn_index": 3},
            {
                "pipeline_partition": "pipeline_development",
                "game_id": "3",
                "turn_index": 4,
            },
        ]
        objective = corrective.apply_state_balanced_weights(pairs)
        self.assertEqual([pair["within_state_pair_weight"] for pair in pairs], [0.5, 0.5, 1.0, 1.0])
        self.assertEqual(objective["pipeline_train_state_count"], 2)
        self.assertEqual(objective["pipeline_development_state_count"], 1)
        self.assertFalse(objective["executed"])

    def test_corrective_pair_uses_exact_teacher_and_top1_actions(self) -> None:
        teacher_action, behavior_action, top1_action = vector(0), vector(1), vector(2)
        sample = {
            "game_id": "13879",
            "turn_index": 6,
            "state": [0.0] * 513,
            "state_dim": 513,
            "action_dim": 54,
            "teacher_action": teacher_action,
            "behavior_action": behavior_action,
            "teacher_physical_cards": ["H2"],
            "legal_actions": [teacher_action, behavior_action, top1_action],
        }
        case = {
            "candidate_results": [
                {
                    "role": "teacher",
                    "action_index": 0,
                    "action_sha256": corrective.action_sha256(teacher_action),
                    "physical_cards_website": ["H2"],
                },
                {
                    "role": "top1",
                    "action_index": 2,
                    "action_sha256": corrective.action_sha256(top1_action),
                    "physical_cards_website": ["D3"],
                },
            ],
            "metrics": {"teacher_over_top1_supported": True},
        }
        result = corrective.corrective_pair(sample, 0, case)
        self.assertEqual(result["preferred_action"], teacher_action)
        self.assertEqual(result["rejected_action"], top1_action)
        self.assertEqual(result["preference_target"], "teacher_action_beats_model_top1")

    def test_select_confirmation_cases_rejects_wrong_supported_set(self) -> None:
        confirmation = {"case_results": []}
        with self.assertRaisesRegex(RuntimeError, "case set mismatch"):
            corrective.select_confirmation_cases(confirmation)

    def test_base_sample_copy_is_not_mutated_by_pair_creation(self) -> None:
        sample = {
            "game_id": "1",
            "turn_index": 2,
            "state": [0.0] * 513,
            "state_dim": 513,
            "teacher_action": vector(0),
            "behavior_action": vector(1),
            "action_dim": 54,
            "teacher_physical_cards": ["S2"],
            "behavior_physical_cards": ["H3"],
            "source_rollout_eval": "evidence.json",
            "rollout_count": 16,
            "hidden_card_sampling_method": "uniform",
            "candidate_advantage": 1.0,
            "candidate_return_variance": 0.0,
            "paired_return_variance": 0.0,
            "advantage_95_lower_bound": 1.0,
            "label_confidence": 1.0,
            "continuation_policy_advantages": {},
        }
        frozen = copy.deepcopy(sample)
        corrective.base_pair(sample, 0, "pipeline_train")
        self.assertEqual(sample, frozen)

    def test_atomic_outputs_refuse_overwrite(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            dataset = Path(directory) / "dataset.pth"
            manifest = Path(directory) / "manifest.json"
            core = {"schema_version": "test", "status": "completed"}
            written, dataset_hash = corrective.write_outputs_once(
                dataset, manifest, {"format": "test"}, core
            )
            self.assertEqual(written["dataset_sha256"], dataset_hash)
            self.assertEqual(
                json.loads(manifest.read_text(encoding="utf-8"))["dataset_sha256"],
                dataset_hash,
            )
            with self.assertRaisesRegex(RuntimeError, "already exists"):
                corrective.write_outputs_once(dataset, manifest, {}, core)
            self.assertFalse(Path(f"{dataset}.tmp").exists())
            self.assertFalse(Path(f"{manifest}.tmp").exists())


if __name__ == "__main__":
    unittest.main()
