from __future__ import annotations

import copy
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import website_teacher_preference_remaining_corrective_evidence_audit as audit


class RemainingCorrectiveEvidenceAuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.context = audit.validate_context()
        cls.result = audit.compute_result(cls.context)

    def test_frozen_context_reproduces_exact_targets_without_model(self) -> None:
        self.assertEqual(len(self.context["frozen_hashes"]), 28)
        self.assertEqual(
            [
                (
                    item["game_id"],
                    item["turn_index"],
                    item["top1_action_index"],
                )
                for item in self.context["train_targets"]
            ],
            audit.EXPECTED_TRAIN_TARGETS,
        )
        self.assertEqual(
            [
                (
                    item["game_id"],
                    item["turn_index"],
                    item["top1_action_index"],
                )
                for item in self.context["development_targets"]
            ],
            audit.EXPECTED_DEVELOPMENT_TARGETS,
        )

    def test_final_train_classifications_are_exact(self) -> None:
        self.assertEqual(
            [
                item["evidence_classification"]
                for item in self.result["pipeline_train_target_audits"]
            ],
            [
                "direct_paired_comparison_inconclusive",
                "source_candidates_present_without_direct_paired_comparison",
                "source_candidates_present_without_direct_paired_comparison",
            ],
        )
        self.assertEqual(
            self.result["train_evidence_aggregates"],
            {
                "target_count": 3,
                "source_file_count": 2,
                "current_top1_absent_from_source_legal_actions_count": 0,
                "current_top1_not_evaluated_as_source_candidate_count": 0,
                "source_candidates_present_without_direct_paired_comparison_count": 2,
                "direct_paired_comparison_inconclusive_count": 1,
                "teacher_over_current_top1_supported_count": 0,
                "current_top1_over_teacher_supported_count": 0,
                "stage_6_9_exact_action_evidence_count": 1,
                "stage_6_9_different_action_nontransfer_count": 1,
                "insufficient_evidence_count": 3,
                "ambiguous_mapping_count": 0,
            },
        )

    def test_prior_different_action_evidence_is_not_transferred(self) -> None:
        item = self.result["pipeline_train_target_audits"][2]
        self.assertEqual((item["game_id"], item["turn_index"]), ("14025", 20))
        self.assertFalse(
            item["stage_6_4_provenance"]["applicable_to_current_top1"]
        )
        self.assertFalse(
            item["stage_6_9_provenance"]["applicable_to_current_top1"]
        )
        self.assertFalse(
            item["stage_6_13_provenance"]["action_identity_matches_current_top1"]
        )

    def test_future_manifest_is_train_only_and_not_executed(self) -> None:
        manifest = self.result["future_counterfactual_manifest"]
        self.assertEqual(len(manifest), 3)
        self.assertEqual(sum(item["new_confirmation_needed"] for item in manifest), 2)
        self.assertTrue(
            all(item["pipeline_partition"] == "pipeline_train" for item in manifest)
        )
        self.assertTrue(
            all(not item["execution_allowed_in_this_stage"] for item in manifest)
        )
        self.assertFalse(self.result["future_counterfactual_manifest_executed"])

    def test_development_and_forbidden_operation_accounting_is_zero(self) -> None:
        self.assertEqual(
            set(self.result["development_isolation"].values()), {0, 3}
        )
        self.assertEqual(
            sum(self.result["forbidden_operation_counts"].values()), 0
        )

    def test_stage_6_17_accounting_mutation_is_rejected(self) -> None:
        payload = copy.deepcopy(self.context["stage_6_17_payload"])
        payload["scoring_accounting"]["recorded_legal_action_count"] += 1
        with self.assertRaisesRegex(RuntimeError, "contract mismatch"):
            audit.validate_stage_6_17(payload)

    def test_direct_source_hash_drift_is_rejected(self) -> None:
        context = {
            **self.context,
            "stage_6_13_source_hashes": {
                **self.context["stage_6_13_source_hashes"]
            },
        }
        source_name = self.result["source_evidence_files"][0]["path"]
        context["stage_6_13_source_hashes"][source_name] = "0" * 64
        with self.assertRaisesRegex(RuntimeError, "not frozen"):
            audit.compute_result(context)

    def test_atomic_output_refuses_overwrite(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "audit.json"
            audit.write_output_once(path, {"status": "completed"})
            self.assertTrue(path.exists())
            with self.assertRaisesRegex(RuntimeError, "already exists"):
                audit.write_output_once(path, {})


if __name__ == "__main__":
    unittest.main()
