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
import website_teacher_preference_residual_corrective_remaining_confirmation as confirmation
import website_teacher_preference_unpaired_confirmation as frozen_confirmation


class RemainingTop1ConfirmationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.audit = confirmation.load_json(confirmation.AUDIT_PATH)
        cls.split = confirmation.load_json(confirmation.SPLIT_PATH)
        cls.teacher_samples, _summary, _hash = preference.load_teacher_dataset(
            confirmation.TEACHER_PATH
        )
        cls.source_samples, cls.source_summary = website_data.load_dataset(
            confirmation.SOURCE_DATASET_PATH
        )

    def reproduce(self, audit: dict | None = None):
        return confirmation.reproduce_targets(
            audit or self.audit,
            self.split,
            self.teacher_samples,
            self.source_samples,
            self.source_summary,
        )

    def test_schedule_gates_and_total_are_frozen(self) -> None:
        schedule = frozen_confirmation.rollout_schedule()
        self.assertEqual(len(schedule), 16)
        self.assertEqual(
            [item["continuation_profile"] for item in schedule].count("greedy_bot"),
            8,
        )
        self.assertEqual(
            [item["continuation_profile"] for item in schedule].count(
                "tempo_baseline"
            ),
            8,
        )
        self.assertEqual(confirmation.EXPECTED_TOTAL_ROLLOUTS, 96)
        self.assertEqual(frozen_confirmation.MIN_ADVANTAGE, 0.15)
        self.assertEqual(frozen_confirmation.MAX_RETURN_VARIANCE, 0.50)

    def test_selects_only_three_new_cases_and_isolates_six(self) -> None:
        targets, excluded, heldout = self.reproduce()
        self.assertEqual(
            [
                (item["game_id"], item["turn_index"], item["top1_action_index"])
                for item in targets
            ],
            confirmation.EXPECTED_EXECUTED,
        )
        self.assertTrue(
            all(
                item["source_sample"]["split"] == "train"
                and item["source_sample"]["information_set_consistent"] is True
                for item in targets
            )
        )
        self.assertEqual(
            [
                (item["game_id"], item["turn_index"], item["top1_action_index"])
                for item in excluded
            ],
            confirmation.EXPECTED_EXCLUDED,
        )
        self.assertEqual(
            [(item["game_id"], item["turn_index"]) for item in heldout],
            confirmation.EXPECTED_DEVELOPMENT,
        )
        for item in excluded + heldout:
            self.assertEqual(item["source_sample_mapping_count"], 0)
            self.assertEqual(item["case_execution_count"], 0)
            self.assertEqual(item["rollout_count"], 0)
            self.assertIs(item["used_for_confirmation_or_design"], False)
            self.assertNotIn("source_sample", item)

    def test_rejects_changed_permitted_action_hash(self) -> None:
        changed = copy.deepcopy(self.audit)
        changed["future_counterfactual_manifest"][0]["top1_action_sha256"] = "0" * 64
        with self.assertRaisesRegex(RuntimeError, "state/action identity mismatch"):
            self.reproduce(changed)

    def test_rejects_promoting_existing_inconclusive_case(self) -> None:
        changed = copy.deepcopy(self.audit)
        item = next(
            entry
            for entry in changed["future_counterfactual_manifest"]
            if str(entry["game_id"]) == "14077" and int(entry["turn_index"]) == 10
        )
        item["new_confirmation_needed"] = True
        with self.assertRaisesRegex(RuntimeError, "excluded train target identity mismatch"):
            self.reproduce(changed)

    def test_stage_6_9_directional_gates_are_reused(self) -> None:
        teacher = frozen_confirmation.directional_metrics([1.0] * 16, [-1.0] * 16)
        normalized = confirmation.stage_6_9_impl.normalize_metrics(teacher)
        self.assertEqual(
            normalized["directional_classification"],
            "teacher_over_residual_supported",
        )
        inconclusive = frozen_confirmation.directional_metrics(
            [0.0] * 16, [0.0] * 16
        )
        self.assertEqual(inconclusive["directional_classification"], "inconclusive")

    def test_output_refusal(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "result.json"
            output.write_text("{}", encoding="utf-8")
            with self.assertRaisesRegex(RuntimeError, "already exists"):
                confirmation.ensure_unused_output(output)


if __name__ == "__main__":
    unittest.main()
