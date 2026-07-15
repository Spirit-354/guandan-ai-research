from __future__ import annotations

from collections import Counter
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import website_teacher_preference_remaining_corrective_diagnosis as diagnosis


class RemainingCorrectiveDiagnosisTests(unittest.TestCase):
    def test_output_guard_refuses_existing_path(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "diagnosis.json"
            diagnosis.ensure_unused_output(path)
            path.touch()
            with self.assertRaisesRegex(RuntimeError, "already exists"):
                diagnosis.ensure_unused_output(path)

    def test_stage_6_16_metric_replay_has_frozen_accounting(self) -> None:
        metrics = {
            "pipeline_train": {
                "aggregate": {},
                "base_pairs": {},
                "stage_6_4_corrective_pairs": {},
                "stage_6_9_residual_pairs": {},
                "stage_6_14e_remaining_pairs": {},
            },
            "pipeline_development": {"aggregate": {}},
        }
        with mock.patch.object(
            diagnosis.training, "evaluate_model", return_value=metrics
        ):
            result = diagnosis.reproduce_stage_6_16_metrics(
                object(), [], {"final_metrics": metrics}
            )
        accounting = result["evaluation_accounting"]
        self.assertEqual(accounting["pair_metric_section_count"], 6)
        self.assertEqual(accounting["pair_evaluation_count"], 64)
        self.assertEqual(accounting["action_value_evaluation_count"], 128)
        self.assertEqual(accounting["model_forward_batch_count"], 12)
        self.assertFalse(accounting["included_in_full_legal_set_score_count"])

    def test_forbidden_operation_contract_is_zero_and_complete(self) -> None:
        forbidden = diagnosis.forbidden_operation_counts()
        self.assertEqual(len(forbidden), 17)
        self.assertTrue(all(value == 0 for value in forbidden.values()))
        self.assertIn("training_runs", forbidden)
        self.assertIn("arena_games", forbidden)
        self.assertIn("complete_website_dataset_loads", forbidden)

    def test_real_context_reproduces_24_hashes_and_6_4_2_mappings(self) -> None:
        context = diagnosis.validate_context()
        self.assertEqual(len(context["frozen_hashes"]), 24)
        self.assertEqual(len(context["samples"]), 22)
        self.assertEqual(len(context["pairs"]), 34)
        self.assertEqual(
            Counter(
                item["pair_source"]
                for item in context["corrective_mappings"].values()
            ),
            Counter(
                {
                    "stage_6_4_train_confirmation": 6,
                    "stage_6_9_residual_train_confirmation": 4,
                    "stage_6_14e_remaining_train_confirmation": 2,
                }
            ),
        )
        self.assertEqual(len(context["partitions"]["pipeline_train"]), 18)
        self.assertEqual(len(context["partitions"]["pipeline_development"]), 4)

    def test_training_report_rejects_changed_pair_use_accounting(self) -> None:
        report = diagnosis.load_json(diagnosis.TRAINING_REPORT_PATH)
        changed = dict(report)
        changed["training_accounting"] = dict(report["training_accounting"])
        changed["training_accounting"]["train_pair_epoch_use_count"] = 599
        with self.assertRaisesRegex(RuntimeError, "report validation mismatch"):
            diagnosis.validate_training_report(
                changed, diagnosis.training.verify_frozen_hashes()
            )


if __name__ == "__main__":
    unittest.main()
