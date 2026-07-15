from __future__ import annotations

from collections import Counter
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import website_teacher_preference_evidence_audit as source_audit
import website_teacher_preference_residual_corrective_remaining_evidence_audit as audit


def action(cards: list[str]) -> list[float]:
    return audit.candidate_action_vector({"physical_cards_website": cards})


def stage_6_9_case(
    teacher: list[float], residual: list[float], residual_index: int
) -> dict:
    return {
        "candidate_results": [
            {
                "role": "teacher",
                "action_index": 0,
                "action_sha256": source_audit._action_sha256(teacher),
                "physical_cards_website": audit.physical_cards_website(teacher),
            },
            {
                "role": "residual",
                "action_index": residual_index,
                "action_sha256": source_audit._action_sha256(residual),
                "physical_cards_website": audit.physical_cards_website(residual),
            },
        ],
        "metrics": {
            "directional_classification": "inconclusive",
            "teacher_over_residual_failure_reasons": ["confidence"],
            "residual_over_teacher_failure_reasons": ["advantage"],
        },
    }


class RemainingEvidenceAuditTests(unittest.TestCase):
    def test_physical_action_round_trip_preserves_card_multiset(self) -> None:
        cards = ["ST", "ST", "HT", "CT"]
        vector = action(cards)
        self.assertEqual(Counter(audit.physical_cards_website(vector)), Counter(cards))
        self.assertEqual(len(vector), 54)

    def test_stage_6_9_exact_action_is_applicable(self) -> None:
        teacher = action(["H9"])
        residual = action(["D2"])
        sample = {"legal_actions": [teacher, residual], "teacher_action": teacher}
        target = {
            "top1_action_index": 1,
            "top1_action_sha256": source_audit._action_sha256(residual),
        }
        result = audit._stage_6_9_provenance(
            target, sample, stage_6_9_case(teacher, residual, 1)
        )
        self.assertTrue(result["applicable_to_current_top1"])
        self.assertTrue(result["used_as_current_direct_evidence"])

    def test_stage_6_9_physical_identity_ignores_card_list_order(self) -> None:
        teacher = action(["ST", "ST", "HT", "CT"])
        residual = action(["D2"])
        sample = {"legal_actions": [teacher, residual], "teacher_action": teacher}
        target = {
            "top1_action_index": 1,
            "top1_action_sha256": source_audit._action_sha256(residual),
        }
        case = stage_6_9_case(teacher, residual, 1)
        case["candidate_results"][0]["physical_cards_website"] = [
            "CT",
            "HT",
            "ST",
            "ST",
        ]
        result = audit._stage_6_9_provenance(target, sample, case)
        self.assertTrue(result["applicable_to_current_top1"])

    def test_stage_6_9_different_action_is_not_transferred(self) -> None:
        teacher = action(["H9"])
        old_residual = action(["D2"])
        current = action(["C3"])
        sample = {
            "legal_actions": [teacher, old_residual, current],
            "teacher_action": teacher,
        }
        target = {
            "top1_action_index": 2,
            "top1_action_sha256": source_audit._action_sha256(current),
        }
        result = audit._stage_6_9_provenance(
            target, sample, stage_6_9_case(teacher, old_residual, 1)
        )
        self.assertFalse(result["applicable_to_current_top1"])
        self.assertFalse(result["used_as_current_direct_evidence"])

    def test_aggregate_separates_missing_direct_and_inconclusive(self) -> None:
        classifications = [
            "current_top1_not_evaluated_as_source_candidate",
            "current_top1_not_evaluated_as_source_candidate",
            "source_candidates_present_without_direct_paired_comparison",
            "direct_paired_comparison_inconclusive",
            "direct_paired_comparison_inconclusive",
            "direct_paired_comparison_inconclusive",
        ]
        entries = [
            {
                "source_rollout_evidence": f"source-{index}.json",
                "evidence_classification": classification,
                "insufficiency_reasons": ["insufficient"],
                "stage_6_9_provenance": {
                    "case_present": index != 2,
                    "applicable_to_current_top1": index >= 3,
                },
            }
            for index, classification in enumerate(classifications)
        ]
        result = audit.aggregate_train_audits(entries)
        self.assertEqual(
            result["current_top1_not_evaluated_as_source_candidate_count"], 2
        )
        self.assertEqual(result["direct_paired_comparison_inconclusive_count"], 3)
        self.assertEqual(result["stage_6_9_different_action_nontransfer_count"], 2)

    def test_atomic_output_refuses_overwrite(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "audit.json"
            audit.write_output_once(path, {"status": "completed"})
            self.assertTrue(path.exists())
            with self.assertRaisesRegex(RuntimeError, "already exists"):
                audit.write_output_once(path, {})


if __name__ == "__main__":
    unittest.main()
