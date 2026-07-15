from __future__ import annotations

import copy
from pathlib import Path
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import website_teacher_preference_corrective_dataset_v3 as corrective_v3


def vector(index: int) -> list[float]:
    result = [0.0] * 54
    result[index] = 1.0
    return result


class CorrectiveDatasetV3Tests(unittest.TestCase):
    def test_output_refusal(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            dataset = Path(directory) / "dataset.pth"
            manifest = Path(directory) / "manifest.json"
            corrective_v3.ensure_outputs_unused(dataset, manifest)
            manifest.touch()
            with self.assertRaisesRegex(RuntimeError, "already exists"):
                corrective_v3.ensure_outputs_unused(dataset, manifest)

    def test_weight_distribution_is_13_single_6_double_3_triple(self) -> None:
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
        for index in range(6):
            pairs.extend(
                {
                    "pipeline_partition": "pipeline_train",
                    "game_id": f"double-{index}",
                    "turn_index": 0,
                }
                for _ in range(2)
            )
        for game_id, turn_index in (("13957", 14), ("14022", 16), ("14038", 12)):
            pairs.extend(
                {
                    "pipeline_partition": "pipeline_train",
                    "game_id": game_id,
                    "turn_index": turn_index,
                }
                for _ in range(3)
            )
        objective = corrective_v3.apply_and_validate_weights(pairs)
        self.assertEqual(
            objective["state_pair_count_distribution"],
            {
                "one_pair_state_count": 13,
                "two_pair_state_count": 6,
                "three_pair_state_count": 3,
            },
        )
        self.assertTrue(
            all(
                abs(value - 1.0) < 1e-12
                for value in objective["partition_normalized_weight_sums"].values()
            )
        )

    def test_remaining_pair_uses_exact_action_and_provenance(self) -> None:
        teacher_action = vector(0)
        behavior_action = vector(1)
        current_top1 = vector(2)
        sample = {
            "game_id": "13957",
            "turn_index": 14,
            "state": [0.0] * 513,
            "state_dim": 513,
            "action_dim": 54,
            "teacher_action": teacher_action,
            "behavior_action": behavior_action,
            "teacher_physical_cards": ["H2"],
            "legal_actions": [teacher_action, behavior_action, current_top1],
            "legal_action_metadata": [
                {"cards": ["H2"]},
                {"cards": ["S3"]},
                {"cards": ["D4"]},
            ],
        }
        case = {
            "candidate_results": [
                {
                    "role": "teacher",
                    "action_index": 0,
                    "action_sha256": corrective_v3.v1_builder.action_sha256(
                        teacher_action
                    ),
                    "physical_cards_website": ["H2"],
                },
                {
                    "role": "residual",
                    "action_index": 2,
                    "action_sha256": corrective_v3.v1_builder.action_sha256(
                        current_top1
                    ),
                    "physical_cards_website": ["D4"],
                },
            ],
            "metrics": {"teacher_over_residual_supported": True},
        }
        pair = corrective_v3.remaining_corrective_pair(sample, 3, case)
        self.assertEqual(pair["preferred_action"], teacher_action)
        self.assertEqual(pair["rejected_action"], current_top1)
        self.assertEqual(pair["rejected_action_index"], 2)
        self.assertEqual(
            pair["preference_target"], "teacher_action_beats_current_top1"
        )
        self.assertEqual(
            pair["source_evidence_sha256"],
            corrective_v3.EXPECTED_HASHES["stage_6_14e_confirmation"],
        )

    def test_rejects_promoting_inconclusive_case(self) -> None:
        payload = corrective_v3.load_json(corrective_v3.CONFIRMATION_PATH)
        changed = copy.deepcopy(payload)
        changed["case_results"][2]["metrics"][
            "directional_classification"
        ] = "teacher_over_residual_supported"
        with self.assertRaisesRegex(RuntimeError, "case accounting mismatch"):
            corrective_v3.validate_and_select_confirmation(changed)

    def test_real_frozen_inputs_build_exact_34_pair_payload(self) -> None:
        context = corrective_v3.load_context()
        payload, manifest = corrective_v3.build_payload(context)
        self.assertEqual(payload["summary"]["total_pair_count"], 34)
        self.assertEqual(payload["summary"]["pipeline_train_pair_count"], 30)
        self.assertEqual(payload["summary"]["pipeline_development_pair_count"], 4)
        self.assertEqual(
            [corrective_v3.pair_semantic_sha256(pair) for pair in payload["pairs"][:32]],
            payload["frozen_v2_pair_semantic_sha256"],
        )
        self.assertEqual(
            manifest["new_pair_ids"],
            [
                "remaining_corrective:13957:14:teacher_vs_current_top1",
                "remaining_corrective:14038:12:teacher_vs_current_top1",
            ],
        )
        exclusions = payload["exclusions"]
        self.assertEqual(
            len(exclusions["stage_6_14e_inconclusive_pipeline_train"]), 1
        )
        self.assertEqual(
            len(exclusions["stage_6_14e_existing_inconclusive_pipeline_train"]),
            3,
        )
        self.assertEqual(
            len(exclusions["stage_6_14e_pipeline_development_identity_only"]), 3
        )
        self.assertTrue(
            all(
                int(value) == 0
                for value in payload["forbidden_operation_counts"].values()
            )
        )


if __name__ == "__main__":
    unittest.main()
