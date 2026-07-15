from __future__ import annotations

import copy
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import website_teacher_preference as preference
import website_teacher_preference_corrective_residual_evidence_audit as audit


class CorrectiveResidualEvidenceAuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.diagnosis = audit.load_json(audit.DIAGNOSIS_PATH)
        cls.split = audit.load_json(audit.SPLIT_PATH)
        cls.samples, _summary, _hash = preference.load_teacher_dataset(
            audit.TEACHER_PATH
        )

    def test_extracts_exact_frozen_8_3_targets_without_source_reads(self) -> None:
        targets, _sample_by_key = audit.extract_residual_targets(
            self.diagnosis, self.samples, self.split
        )
        train = [
            item for item in targets if item["pipeline_partition"] == "pipeline_train"
        ]
        development = [
            item
            for item in targets
            if item["pipeline_partition"] == "pipeline_development"
        ]
        self.assertEqual(len(targets), 11)
        self.assertEqual(len(train), 8)
        self.assertEqual(len(development), 3)
        self.assertEqual(
            {(item["game_id"], item["turn_index"]) for item in development},
            {("13992", 16), ("14074", 9), ("13871", 9)},
        )
        identity_keys = {
            "game_id",
            "turn_index",
            "pipeline_partition",
            "legal_action_count",
            "legal_action_order_sha256",
            "teacher_rank",
            "top1_action_index",
            "top1_action_sha256",
        }
        self.assertTrue(all(set(item) == identity_keys for item in development))

    def test_extract_rejects_changed_action_order(self) -> None:
        changed = copy.deepcopy(self.diagnosis)
        residual = next(
            item
            for item in changed["state_diagnostics"]
            if item["top1_source"] == "other"
        )
        residual["legal_action_order_sha256"] = "0" * 64
        with self.assertRaisesRegex(RuntimeError, "order mismatch"):
            audit.extract_residual_targets(changed, self.samples, self.split)

    def test_direct_evidence_classification_is_conservative(self) -> None:
        classification, reasons = audit.classify_direct_evidence(
            top1_candidate_count=0,
            teacher_candidate_count=1,
            required_field_status={},
            direct_pair=None,
        )
        self.assertEqual(classification, "residual_action_not_evaluated_as_candidate")
        self.assertEqual(reasons, ["residual_top1_candidate_result_missing"])

        classification, reasons = audit.classify_direct_evidence(
            top1_candidate_count=1,
            teacher_candidate_count=1,
            required_field_status={"candidate_advantage": False},
            direct_pair=None,
        )
        self.assertEqual(
            classification, "candidate_present_without_direct_paired_statistics"
        )
        self.assertEqual(reasons, ["missing_direct_field:candidate_advantage"])

    def test_complete_direct_pair_classifies_only_recorded_direction(self) -> None:
        direct_pair = {
            "paired_rollout_count": 16,
            "hidden_card_sampling_method": "uniform",
            "teacher_mean_return": 1.0,
            "teacher_return_variance": 0.0,
            "residual_top1_mean_return": 0.0,
            "residual_top1_return_variance": 0.0,
            "teacher_minus_residual_top1_advantage": 1.0,
            "teacher_minus_residual_top1_95_lower_bound": 0.5,
            "teacher_over_residual_top1_confidence": 0.75,
            "continuation_profile_advantages": {
                "greedy_bot": 1.0,
                "tempo_baseline": 1.0,
            },
            "directional_classification": ("teacher_over_residual_top1_supported"),
        }
        classification, reasons = audit.classify_direct_evidence(
            top1_candidate_count=1,
            teacher_candidate_count=1,
            required_field_status={"all_required_fields": True},
            direct_pair=direct_pair,
        )
        self.assertEqual(classification, "teacher_over_residual_top1_supported")
        self.assertEqual(reasons, [])

    def test_compute_result_queries_only_train_targets(self) -> None:
        context = audit.validate_context()
        result = audit.compute_result(context)
        self.assertEqual(len(result["pipeline_train_target_audits"]), 8)
        self.assertEqual(len(result["pipeline_development_identity_only"]), 3)
        self.assertEqual(
            result["development_isolation"]["source_evidence_target_query_count"],
            0,
        )
        self.assertEqual(result["source_evidence_file_count"], 6)
        self.assertNotIn(
            "website_information_set_rollout_cases13871_13865_confirm16.json",
            {item["path"] for item in result["source_evidence_files"]},
        )
        self.assertEqual(result["future_counterfactual_manifest_case_count"], 8)

    def test_output_refusal(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir) / "already.json"
            output.write_text("{}", encoding="utf-8")
            with self.assertRaisesRegex(RuntimeError, "already exists"):
                audit.ensure_unused_output(output)


if __name__ == "__main__":
    unittest.main()
