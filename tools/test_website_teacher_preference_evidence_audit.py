from __future__ import annotations

import hashlib
import struct
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import website_teacher_preference as preference
import website_teacher_preference_evidence_audit as audit


def action(first: float, second: float = 0.0) -> list[float]:
    result = [0.0] * preference.ACTION_DIM
    result[0] = first
    result[1] = second
    return result


def action_order_sha256(actions: list[list[float]]) -> str:
    digest = hashlib.sha256()
    for item in actions:
        digest.update(struct.pack(f"<{len(item)}f", *item))
    return digest.hexdigest()


class WebsiteTeacherPreferenceEvidenceAuditTests(unittest.TestCase):
    def test_reproduce_target_uses_first_max_and_exact_action_order(self) -> None:
        actions = [action(2.0, 1.0), action(1.0), action(2.0, 2.0)]
        sample = {
            "game_id": "1",
            "turn_index": 2,
            "legal_actions": actions,
            "teacher_action": actions[1],
            "behavior_action": actions[0],
        }
        state = {
            "legal_action_q_values": [0.0, -1.0, 2.0],
            "legal_action_order_sha256": action_order_sha256(actions),
            "top1_index": 2,
            "teacher_action_index": 1,
            "behavior_action_index": 0,
            "pipeline_partition": "pipeline_train",
        }
        result = audit.reproduce_target(state, sample, "pipeline_train")
        self.assertEqual(result["top1_action_index"], 2)
        self.assertEqual(result["top1_action"], actions[2])
        self.assertGreater(result["top1_minus_teacher_q"], 0.0)

    def test_reproduce_target_rejects_changed_action_order(self) -> None:
        actions = [action(0.0), action(1.0), action(2.0)]
        sample = {
            "game_id": "1",
            "turn_index": 2,
            "legal_actions": actions,
            "teacher_action": actions[1],
            "behavior_action": actions[0],
        }
        state = {
            "legal_action_q_values": [0.0, 1.0, 2.0],
            "legal_action_order_sha256": action_order_sha256(list(reversed(actions))),
            "top1_index": 2,
            "teacher_action_index": 1,
            "behavior_action_index": 0,
            "pipeline_partition": "pipeline_train",
        }
        with self.assertRaisesRegex(RuntimeError, "order hash"):
            audit.reproduce_target(state, sample, "pipeline_train")

    def test_direct_evidence_path_restriction(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            path = root / "evidence.json"
            path.write_text("{}", encoding="utf-8")
            self.assertEqual(
                audit.resolve_direct_evidence_path("evidence.json", root),
                path.resolve(),
            )
            with self.assertRaisesRegex(RuntimeError, "direct filename"):
                audit.resolve_direct_evidence_path("sub/evidence.json", root)
            with self.assertRaisesRegex(RuntimeError, "direct filename"):
                audit.resolve_direct_evidence_path("../evidence.json", root)

    def test_evidence_classification_is_conservative(self) -> None:
        self.assertEqual(
            audit.classify_evidence(
                mapping_ambiguous=False,
                dual_continuation_qualified=True,
                greedy_only_recorded=False,
                present_in_source_legal_actions=True,
            ),
            "dual_continuation_confirmed",
        )
        self.assertEqual(
            audit.classify_evidence(
                mapping_ambiguous=False,
                dual_continuation_qualified=False,
                greedy_only_recorded=False,
                present_in_source_legal_actions=True,
            ),
            "present_without_qualifying_comparison",
        )
        self.assertEqual(
            audit.classify_evidence(
                mapping_ambiguous=True,
                dual_continuation_qualified=True,
                greedy_only_recorded=False,
                present_in_source_legal_actions=True,
            ),
            "ambiguous_mapping",
        )

    def test_aggregate_arithmetic(self) -> None:
        audits = [
            {
                "evidence_class": "dual_continuation_confirmed",
                "source_rollout_evidence": "a.json",
                "teacher_vs_top1_ordering_supported": False,
            },
            {
                "evidence_class": "present_without_qualifying_comparison",
                "source_rollout_evidence": "b.json",
                "teacher_vs_top1_ordering_supported": False,
            },
            {
                "evidence_class": "present_without_qualifying_comparison",
                "source_rollout_evidence": "b.json",
                "teacher_vs_top1_ordering_supported": False,
            },
        ]
        result = audit.aggregate_audits(audits)
        self.assertEqual(result["target_state_count"], 3)
        self.assertEqual(result["referenced_evidence_file_count"], 2)
        self.assertEqual(result["dual_continuation_confirmed_count"], 1)
        self.assertEqual(
            result["present_without_qualifying_comparison_count"], 2
        )
        self.assertEqual(result["future_counterfactual_manifest_case_count"], 3)


if __name__ == "__main__":
    unittest.main()
