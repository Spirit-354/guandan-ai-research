from __future__ import annotations

import copy
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import website_teacher_preference_corrective_diagnosis as diagnosis


def action(value: float, marker: float = 0.0) -> list[float]:
    result = [0.0] * 54
    result[0] = value
    result[1] = marker
    return result


def sample(actions: list[list[float]]) -> dict:
    return {
        "game_id": "1",
        "turn_index": 2,
        "state": [0.0] * 513,
        "legal_actions": actions,
        "teacher_action": actions[0],
        "behavior_action": actions[1],
    }


def pair(
    pair_id: str,
    preferred: list[float],
    rejected: list[float],
    source: str,
    weight: float,
) -> dict:
    return {
        "pair_id": pair_id,
        "game_id": "1",
        "turn_index": 2,
        "pipeline_partition": "pipeline_train",
        "pair_source": source,
        "state": [0.0] * 513,
        "preferred_action": preferred,
        "rejected_action": rejected,
        "within_state_pair_weight": weight,
    }


class CorrectiveDiagnosisTests(unittest.TestCase):
    def test_confirmed_index_preserves_duplicate_recorded_action(self) -> None:
        teacher = action(3.0)
        behavior = action(0.0)
        rejected = action(2.0)
        item = sample([teacher, behavior, rejected, copy.deepcopy(rejected)])
        corrective = pair(
            "corrective:1:2:teacher_vs_top1",
            teacher,
            rejected,
            "stage_6_4_train_confirmation",
            0.5,
        )
        mappings = {
            ("1", 2): {
                "pair_id": corrective["pair_id"],
                "preferred_index": 0,
                "rejected_index": 3,
            }
        }
        self.assertEqual(
            diagnosis.pair_action_indices(corrective, item, mappings), (0, 3)
        )

    def test_old_comparison_preserves_first_max_tie_semantics(self) -> None:
        current = {
            "game_id": "1",
            "turn_index": 2,
            "pipeline_partition": "pipeline_train",
            "legal_action_count": 3,
            "legal_action_order_sha256": "a" * 64,
            "teacher_action_index": 1,
            "behavior_action_index": 2,
            "teacher_rank": 1,
            "top1_index": 0,
            "actions_strictly_above_teacher_count": 0,
        }
        old = dict(current)
        old.update({"teacher_rank": 2, "top1_index": 2, "top1_source": "behavior"})
        result = diagnosis.add_old_comparison(current, old)
        comparison = result["old_checkpoint_comparison"]
        self.assertEqual(comparison["new_minus_old_teacher_rank"], -1)
        self.assertFalse(comparison["old_top1_index_remains_new_top1"])

    def test_corrective_summary_uses_recorded_indices_and_ranks(self) -> None:
        state = {
            "game_id": "1",
            "turn_index": 2,
            "pipeline_partition": "pipeline_train",
            "legal_action_q_values": [2.0, 3.0, 1.0],
            "top1_index": 1,
            "top1_source": "other",
        }
        mappings = {
            ("1", 2): {
                "pair_id": "corrective:1:2",
                "preferred_index": 0,
                "rejected_index": 2,
            }
        }
        result = diagnosis.corrective_pair_diagnostics([state], mappings)[0]
        self.assertEqual(result["preferred_rank"], 2)
        self.assertEqual(result["rejected_rank"], 3)
        self.assertTrue(result["teacher_outranks_frozen_rejected_top1"])
        self.assertFalse(result["teacher_is_first_max_full_set_top1"])

    def test_action_order_digest_changes_with_recorded_state_order(self) -> None:
        first = {"game_id": "1", "turn_index": 1, "legal_action_order_sha256": "00" * 32}
        second = {"game_id": "2", "turn_index": 1, "legal_action_order_sha256": "11" * 32}
        self.assertNotEqual(
            diagnosis.action_order_digest([first, second]),
            diagnosis.action_order_digest([second, first]),
        )
        self.assertEqual(len(diagnosis.action_order_digest([first, second])), 64)

    def test_atomic_output_refuses_overwrite(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "diagnosis.json"
            diagnosis.write_output_once(path, {"status": "completed"})
            self.assertTrue(path.exists())
            self.assertFalse(path.with_name(f"{path.name}.tmp").exists())
            with self.assertRaisesRegex(RuntimeError, "already exists"):
                diagnosis.write_output_once(path, {})


if __name__ == "__main__":
    unittest.main()
