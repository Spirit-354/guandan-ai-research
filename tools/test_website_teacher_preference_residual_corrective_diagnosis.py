from __future__ import annotations

from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import website_teacher_preference_residual_corrective_diagnosis as diagnosis


def action(value: float, marker: float = 0.0) -> list[float]:
    result = [0.0] * 54
    result[0] = value
    result[1] = marker
    return result


class ResidualCorrectiveDiagnosisTests(unittest.TestCase):
    def test_enrich_state_records_hashes_and_every_strictly_higher_action(self) -> None:
        actions = [action(1.0), action(0.0), action(2.0), action(3.0)]
        sample = {"legal_actions": actions}
        state = {
            "teacher_action_index": 0,
            "behavior_action_index": 1,
            "teacher_q": 1.0,
            "legal_action_q_values": [1.0, 0.5, 1.5, 1.5],
            "actions_strictly_above_teacher_count": 2,
        }
        result = diagnosis.enrich_state(sample, state)
        self.assertEqual(
            [item["action_index"] for item in result["actions_strictly_above_teacher"]],
            [2, 3],
        )
        self.assertEqual(len(result["teacher_action_sha256"]), 64)
        self.assertEqual(len(result["behavior_action_sha256"]), 64)

    def test_corrective_diagnostic_preserves_source_indices_and_first_max(self) -> None:
        state = {
            "game_id": "1",
            "turn_index": 2,
            "pipeline_partition": "pipeline_train",
            "legal_action_q_values": [2.0, 3.0, 1.0],
            "top1_index": 1,
            "top1_source": "other",
        }
        mappings = {
            "residual:1:2": {
                "pair_id": "residual:1:2",
                "game_id": "1",
                "turn_index": 2,
                "pair_source": "stage_6_9_residual_train_confirmation",
                "preference_target": "teacher_action_beats_residual_top1",
                "preferred_action_sha256": "a" * 64,
                "rejected_action_sha256": "b" * 64,
                "preferred_physical_cards_website": ["H2"],
                "rejected_physical_cards_website": ["S2"],
                "preferred_index": 0,
                "rejected_index": 2,
            }
        }
        result = diagnosis.corrective_pair_diagnostics([state], mappings)[0]
        self.assertEqual(result["preferred_rank"], 2)
        self.assertEqual(result["rejected_rank"], 3)
        self.assertEqual(result["teacher_minus_rejected_margin"], 1.0)
        self.assertTrue(result["teacher_outranks_frozen_rejected_action"])
        self.assertFalse(result["teacher_is_first_max_full_set_top1"])

    def test_stage_6_11_metric_replay_has_frozen_accounting(self) -> None:
        metrics = {"pipeline_train": {}, "pipeline_development": {}}
        with mock.patch.object(
            diagnosis.residual_training, "evaluate_model", return_value=metrics
        ):
            result = diagnosis.reproduce_stage_6_11_metrics(
                object(), [], {"final_metrics": metrics}
            )
        accounting = result["evaluation_accounting"]
        self.assertEqual(accounting["pair_evaluation_count"], 60)
        self.assertEqual(accounting["action_value_evaluation_count"], 120)
        self.assertFalse(accounting["included_in_full_legal_set_score_count"])

    def test_action_order_digest_changes_with_state_order(self) -> None:
        first = {"game_id": "1", "turn_index": 1, "legal_action_order_sha256": "00" * 32}
        second = {"game_id": "2", "turn_index": 1, "legal_action_order_sha256": "11" * 32}
        self.assertNotEqual(
            diagnosis.action_order_digest([first, second]),
            diagnosis.action_order_digest([second, first]),
        )

    def test_atomic_output_refuses_overwrite(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "diagnosis.json"
            diagnosis.write_output_once(path, {"status": "completed"})
            self.assertTrue(path.exists())
            with self.assertRaisesRegex(RuntimeError, "already exists"):
                diagnosis.write_output_once(path, {})


if __name__ == "__main__":
    unittest.main()
