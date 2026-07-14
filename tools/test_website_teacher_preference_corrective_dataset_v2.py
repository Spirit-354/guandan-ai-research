from __future__ import annotations

import copy
from pathlib import Path
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import website_teacher_preference_corrective_dataset_v2 as corrective_v2


def vector(index: int) -> list[float]:
    result = [0.0] * 54
    result[index] = 1.0
    return result


class CorrectiveDatasetV2Tests(unittest.TestCase):
    def test_output_refusal(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            dataset = Path(directory) / "dataset.pth"
            manifest = Path(directory) / "manifest.json"
            corrective_v2.ensure_outputs_unused(dataset, manifest)
            dataset.touch()
            with self.assertRaisesRegex(RuntimeError, "already exists"):
                corrective_v2.ensure_outputs_unused(dataset, manifest)

    def test_pair_semantic_hash_ignores_only_weight_fields(self) -> None:
        pair = {
            "pair_id": "pair",
            "preferred_action": vector(0),
            "within_state_pair_weight": 1.0,
            "partition_normalized_pair_weight": 0.5,
            "state_objective_weight": 1.0,
        }
        changed_weights = copy.deepcopy(pair)
        changed_weights["within_state_pair_weight"] = 0.25
        changed_weights["partition_normalized_pair_weight"] = 0.125
        self.assertEqual(
            corrective_v2.pair_semantic_sha256(pair),
            corrective_v2.pair_semantic_sha256(changed_weights),
        )
        changed_identity = copy.deepcopy(pair)
        changed_identity["pair_id"] = "different"
        self.assertNotEqual(
            corrective_v2.pair_semantic_sha256(pair),
            corrective_v2.pair_semantic_sha256(changed_identity),
        )

    def test_weight_distribution_has_eight_double_and_one_triple_state(self) -> None:
        pairs = []
        for index in range(13):
            pairs.append(
                {
                    "pipeline_partition": (
                        "pipeline_development" if index < 4 else "pipeline_train"
                    ),
                    "game_id": f"single-{index}",
                    "turn_index": 0,
                }
            )
        for index in range(8):
            pairs.extend(
                {
                    "pipeline_partition": "pipeline_train",
                    "game_id": f"double-{index}",
                    "turn_index": 0,
                }
                for _ in range(2)
            )
        pairs.extend(
            {
                "pipeline_partition": "pipeline_train",
                "game_id": "14022",
                "turn_index": 16,
            }
            for _ in range(3)
        )
        objective = corrective_v2.apply_and_validate_weights(pairs)
        triple = [pair for pair in pairs if pair["game_id"] == "14022"]
        self.assertEqual(
            [pair["within_state_pair_weight"] for pair in triple],
            [1.0 / 3.0] * 3,
        )
        self.assertEqual(
            objective["state_pair_count_distribution"],
            {
                "one_pair_state_count": 13,
                "two_pair_state_count": 8,
                "three_pair_state_count": 1,
            },
        )

    def test_residual_pair_uses_exact_recorded_actions_and_provenance(self) -> None:
        teacher_action = vector(0)
        behavior_action = vector(1)
        residual_action = vector(2)
        sample = {
            "game_id": "14044",
            "turn_index": 9,
            "state": [0.0] * 513,
            "state_dim": 513,
            "action_dim": 54,
            "teacher_action": teacher_action,
            "behavior_action": behavior_action,
            "teacher_physical_cards": ["H2"],
            "legal_actions": [teacher_action, behavior_action, residual_action],
        }
        case = {
            "candidate_results": [
                {
                    "role": "teacher",
                    "action_index": 0,
                    "action_sha256": corrective_v2.v1_builder.action_sha256(
                        teacher_action
                    ),
                    "physical_cards_website": ["H2"],
                },
                {
                    "role": "residual",
                    "action_index": 2,
                    "action_sha256": corrective_v2.v1_builder.action_sha256(
                        residual_action
                    ),
                    "physical_cards_website": ["D3"],
                },
            ],
            "metrics": {"teacher_over_residual_supported": True},
        }
        pair = corrective_v2.residual_corrective_pair(sample, 3, case)
        self.assertEqual(pair["preferred_action"], teacher_action)
        self.assertEqual(pair["rejected_action"], residual_action)
        self.assertEqual(
            pair["preference_target"], "teacher_action_beats_residual_top1"
        )
        self.assertEqual(
            pair["source_evidence_sha256"],
            corrective_v2.EXPECTED_HASHES["stage_6_9_confirmation"],
        )

    def test_real_frozen_inputs_build_exact_32_pair_payload(self) -> None:
        context = corrective_v2.load_context()
        payload, manifest = corrective_v2.build_payload(context)
        self.assertEqual(payload["summary"]["total_pair_count"], 32)
        self.assertEqual(payload["summary"]["pipeline_train_pair_count"], 28)
        self.assertEqual(payload["summary"]["pipeline_development_pair_count"], 4)
        self.assertEqual(
            [
                corrective_v2.pair_semantic_sha256(pair)
                for pair in payload["pairs"][:28]
            ],
            payload["frozen_v1_pair_semantic_sha256"],
        )
        self.assertEqual(
            manifest["new_pair_ids"],
            [
                "residual_corrective:14044:9:teacher_vs_residual_top1",
                "residual_corrective:14038:12:teacher_vs_residual_top1",
                "residual_corrective:14000:5:teacher_vs_residual_top1",
                "residual_corrective:14022:16:teacher_vs_residual_top1",
            ],
        )
        self.assertEqual(
            len(payload["exclusions"]["stage_6_9_inconclusive_pipeline_train"]),
            4,
        )
        heldout = payload["exclusions"]["stage_6_9_pipeline_development_identity_only"]
        self.assertEqual(len(heldout), 3)
        self.assertTrue(
            all(item["action_inspected_in_this_stage"] is False for item in heldout)
        )
        self.assertTrue(
            all(
                int(value) == 0
                for value in payload["forbidden_operation_counts"].values()
            )
        )


if __name__ == "__main__":
    unittest.main()
