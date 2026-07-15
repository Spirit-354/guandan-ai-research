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

import website_teacher_preference_stage6_final_disposition as disposition


class Stage6FinalDispositionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.result = disposition.build_result()

    def test_frozen_inputs_and_curated_reads_are_exact(self) -> None:
        self.assertEqual(self.result["frozen_inputs"]["entry_count"], 32)
        self.assertEqual(len(self.result["frozen_inputs"]["sha256"]), 32)
        accounting = self.result["curated_json_read_accounting"]
        self.assertEqual(accounting["parsed_json_file_count"], 5)
        self.assertEqual(accounting["non_json_semantic_load_count"], 0)

    def test_stage_6_reproductions_are_exact(self) -> None:
        arena = self.result["stage_6_1_arena_reproduction"]
        self.assertEqual(
            (arena["completed_games"], arena["model_wins"], arena["baseline_wins"]),
            (20, 0, 20),
        )
        static = self.result["stage_6_17_static_reproduction"]
        self.assertEqual(
            (
                static["state_count"],
                static["recorded_legal_action_count"],
                static["overall_teacher_top1"],
                static["overall_other_top1"],
            ),
            (22, 934, 16, 6),
        )
        final = self.result["stage_6_19_confirmation_reproduction"]
        self.assertEqual(
            (
                final["requested_rollout_count"],
                final["completed_rollout_count"],
                final["inconclusive_count"],
                final["supported_comparison_count"],
            ),
            (64, 64, 2, 0),
        )

    def test_all_final_train_residuals_are_exact_and_inconclusive(self) -> None:
        self.assertEqual(
            [
                (
                    item["game_id"],
                    item["turn_index"],
                    item["current_top1_action_index"],
                    item["current_top1_action_sha256"],
                )
                for item in self.result["final_train_residuals"]
            ],
            disposition.EXPECTED_RESIDUALS,
        )
        self.assertTrue(
            all(
                item["directional_classification"] == "inconclusive"
                and item["strong_ordering_label_allowed"] is False
                and item["rerun_allowed"] is False
                for item in self.result["final_train_residuals"]
            )
        )

    def test_development_is_held_out_and_forbidden_counts_are_zero(self) -> None:
        self.assertEqual(
            [
                (item["game_id"], item["turn_index"])
                for item in self.result["pipeline_development_heldout"]
            ],
            disposition.EXPECTED_DEVELOPMENT,
        )
        self.assertTrue(
            all(
                item["source_exposure_count"] == 0
                and item["execution_count"] == 0
                and item["design_use_count"] == 0
                for item in self.result["pipeline_development_heldout"]
            )
        )
        self.assertEqual(sum(self.result["forbidden_operation_counts"].values()), 0)

    def test_final_disposition_is_negative_and_blocks_stage_7(self) -> None:
        self.assertEqual(
            self.result["final_disposition"],
            {
                "stage_6_status": "completed_rejected",
                "offline_gate_passed": False,
                "eligible_offline_candidate_count": 0,
                "stage_7_authorized": False,
                "website_control_authorized": False,
                "capability_claim_allowed": False,
                "automatic_next_stage_available": False,
            },
        )

    def test_changed_arena_or_confirmation_evidence_is_rejected(self) -> None:
        arena = json.loads(disposition.STAGE_6_1_PATH.read_text(encoding="utf-8"))
        arena["model_wins"] = 1
        with self.assertRaisesRegex(RuntimeError, "Stage 6.1 Arena rejection mismatch"):
            disposition.validate_stage_6_1(arena)

        confirmation = json.loads(
            disposition.STAGE_6_19_PATH.read_text(encoding="utf-8")
        )
        confirmation["completed_rollouts"] = 63
        with self.assertRaisesRegex(RuntimeError, "Stage 6.19 final confirmation mismatch"):
            disposition.validate_stage_6_19(confirmation)

    def test_atomic_output_refuses_overwrite(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "disposition.json"
            disposition.write_output_once(path, {"status": "completed"})
            self.assertTrue(path.exists())
            with self.assertRaisesRegex(RuntimeError, "already exists"):
                disposition.write_output_once(path, copy.deepcopy(self.result))


if __name__ == "__main__":
    unittest.main()
