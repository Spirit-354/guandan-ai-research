from __future__ import annotations

import copy
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import website_danzero_dataset as website_data
import website_teacher_preference as preference
import website_teacher_preference_corrective_residual_confirmation as confirmation
import website_teacher_preference_unpaired_confirmation as frozen_confirmation


class CorrectiveResidualConfirmationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.audit = confirmation.load_json(confirmation.AUDIT_PATH)
        cls.diagnosis = confirmation.load_json(confirmation.DIAGNOSIS_PATH)
        cls.split = confirmation.load_json(confirmation.SPLIT_PATH)
        cls.teacher_samples, _summary, _hash = preference.load_teacher_dataset(
            confirmation.TEACHER_PATH
        )
        cls.source_samples, cls.source_summary = website_data.load_dataset(
            confirmation.SOURCE_DATASET_PATH
        )

    def test_schedule_and_total_are_frozen(self) -> None:
        schedule = frozen_confirmation.rollout_schedule()
        self.assertEqual(len(schedule), 16)
        self.assertEqual(
            [item["continuation_profile"] for item in schedule].count("greedy_bot"),
            8,
        )
        self.assertEqual(
            [item["continuation_profile"] for item in schedule].count("tempo_baseline"),
            8,
        )
        self.assertEqual(confirmation.EXPECTED_TOTAL_ROLLOUTS, 256)

    def test_reproduces_exact_eight_train_and_three_identity_only_cases(self) -> None:
        targets, heldout = confirmation.reproduce_targets(
            self.audit,
            self.diagnosis,
            self.split,
            self.teacher_samples,
            self.source_samples,
            self.source_summary,
        )
        self.assertEqual(len(targets), 8)
        self.assertTrue(
            all(item["source_sample"]["split"] == "train" for item in targets)
        )
        self.assertEqual(len(heldout), 3)
        self.assertEqual(
            {(item["game_id"], item["turn_index"]) for item in heldout},
            {("13992", 16), ("14074", 9), ("13871", 9)},
        )
        self.assertTrue(
            all(
                item["source_sample_mapping_count"] == 0
                and item["case_execution_count"] == 0
                and item["rollout_count"] == 0
                and "source_sample" not in item
                for item in heldout
            )
        )

    def test_rejects_changed_manifest_action_hash(self) -> None:
        changed = copy.deepcopy(self.audit)
        changed["future_counterfactual_manifest"][0]["top1_action_sha256"] = "0" * 64
        with self.assertRaisesRegex(RuntimeError, "state/action identity mismatch"):
            confirmation.reproduce_targets(
                changed,
                self.diagnosis,
                self.split,
                self.teacher_samples,
                self.source_samples,
                self.source_summary,
            )

    def test_normalized_metrics_record_both_directions(self) -> None:
        teacher = confirmation.normalize_metrics(
            frozen_confirmation.directional_metrics([1.0] * 16, [-1.0] * 16)
        )
        self.assertEqual(
            teacher["directional_classification"],
            "teacher_over_residual_supported",
        )
        self.assertEqual(teacher["teacher_minus_residual_advantage"], 2.0)
        self.assertEqual(teacher["residual_minus_teacher_advantage"], -2.0)
        self.assertLess(teacher["residual_minus_teacher_95_lower_bound"], 0.0)

        residual = confirmation.normalize_metrics(
            frozen_confirmation.directional_metrics([-1.0] * 16, [1.0] * 16)
        )
        self.assertEqual(
            residual["directional_classification"],
            "residual_over_teacher_supported",
        )
        self.assertEqual(residual["residual_minus_teacher_advantage"], 2.0)
        self.assertGreater(residual["residual_minus_teacher_95_lower_bound"], 0.0)

    def test_case_normalization_uses_residual_names(self) -> None:
        raw_metrics = frozen_confirmation.directional_metrics([1.0] * 16, [-1.0] * 16)
        raw = {
            "game_id": "1",
            "turn_index": 2,
            "pipeline_partition": "pipeline_train",
            "legal_action_count": 2,
            "legal_action_order_sha256": "abc",
            "case_seconds": 1.0,
            "case_timed_out": False,
            "candidate_results": [{"role": "teacher"}, {"role": "top1"}],
            "paired_rollouts": [
                {
                    **item,
                    "determinization_seed": item["determinization_index"],
                    "teacher_return": 1.0,
                    "top1_return": -1.0,
                    "teacher_minus_top1_return": 2.0,
                }
                for item in frozen_confirmation.rollout_schedule()
            ],
            "metrics": raw_metrics,
        }
        normalized = confirmation.normalize_case_result(raw)
        self.assertEqual(
            [item["role"] for item in normalized["candidate_results"]],
            ["teacher", "residual"],
        )
        self.assertIn("residual_return", normalized["paired_rollouts"][0])
        self.assertNotIn("top1_return", normalized["paired_rollouts"][0])

    def test_output_refusal(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "result.json"
            output.write_text("{}", encoding="utf-8")
            with self.assertRaisesRegex(RuntimeError, "already exists"):
                confirmation.ensure_unused_output(output)


if __name__ == "__main__":
    unittest.main()
