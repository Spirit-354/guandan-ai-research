from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import website_information_set as information_set
import website_teacher_preference_residual_corrective_remaining_timeout_recovery_audit as recovery
import website_teacher_preference_unpaired_confirmation as frozen_confirmation


class TimeoutRecoveryAuditTests(unittest.TestCase):
    def test_static_trace_derives_exact_six_missing_candidate_values(self) -> None:
        trace = recovery.trace_deadline_path()
        self.assertEqual(trace["case_deadline_seconds"], 600.0)
        self.assertEqual(trace["schedule_items_per_case"], 16)
        self.assertEqual(trace["third_case_completed_pairs"], 13)
        self.assertEqual(trace["third_case_missing_schedule_items"], 3)
        self.assertEqual(trace["third_case_missing_candidate_values"], 6)
        self.assertTrue(trace["derived_candidate_failure_count_matches_terminal"])

    def test_expired_candidate_returns_exact_deadline_failure(self) -> None:
        class Game:
            current_player = 0
            is_game_over = False

        class Adaptive:
            @staticmethod
            def offline_team_id(player: int) -> int:
                return player % 2

            @staticmethod
            def offline_make_action_info_from_cards(*args, **kwargs):
                del args, kwargs
                return {
                    "illegal": False,
                    "materialization_fail": False,
                    "hand_card_mismatch": False,
                }

            @staticmethod
            def offline_apply_action(game, action):
                del game, action
                return {}

        value, failure = information_set._simulate_candidate(
            Game(),
            {"physical_cards": [], "action_id": 0},
            {},
            Adaptive(),
            7,
            300,
            "greedy_bot",
            {},
            0.0,
            {},
            {},
        )
        self.assertIsNone(value)
        self.assertEqual(failure, {"reason": "case_time_budget_exhausted", "steps": 0})

    def test_execute_case_accounts_for_three_missing_pairs_as_six_failures(self) -> None:
        calls = 0
        seen_deadlines: list[float] = []

        def simulate(*args):
            nonlocal calls
            seen_deadlines.append(float(args[8]))
            calls += 1
            if calls > 26:
                return None, {"reason": "case_time_budget_exhausted", "steps": 0}
            return (1.0 if calls % 2 else -1.0), None

        target = {
            "game_id": "13872",
            "turn_index": 4,
            "pipeline_partition": "pipeline_train",
            "legal_action_count": 2,
            "legal_action_order_sha256": "order",
            "source_sample": {"game_id": "13872", "turn_index": 4},
        }
        candidates = [
            {"role": "teacher", "action_index": 0},
            {"role": "top1", "action_index": 1},
        ]
        with mock.patch.object(
            frozen_confirmation.time,
            "monotonic",
            side_effect=[100.0, 701.0, 701.0],
        ):
            result = frozen_confirmation.execute_case(
                target,
                candidates,
                {},
                object(),
                {},
                {},
                {},
                restore_fn=lambda *args: object(),
                simulate_fn=simulate,
            )
        self.assertEqual(calls, 32)
        self.assertEqual(set(seen_deadlines), {700.0})
        self.assertTrue(result["case_timed_out"])
        self.assertEqual(
            [item["completed_rollout_count"] for item in result["candidate_results"]],
            [13, 13],
        )
        self.assertEqual(
            [item["failure_count"] for item in result["candidate_results"]],
            [3, 3],
        )

    def test_existing_optimization_boundary_is_already_active(self) -> None:
        boundary = recovery.audit_optimization_boundary()
        self.assertTrue(boundary["offline_optimization_installer_already_active"])
        self.assertTrue(boundary["baseline_visible_state_action_cache_already_active"])
        self.assertFalse(boundary["additional_existing_sequential_optimization_toggle_found"])
        self.assertTrue(boundary["existing_process_isolation_infrastructure_found"])
        self.assertFalse(boundary["process_isolation_used_by_confirmation"])

    def test_build_result_forbids_rollout_and_partial_comparison_use(self) -> None:
        result = recovery.build_result()
        self.assertEqual(result["status"], "completed")
        self.assertFalse(result["recovery_decision"]["unchanged_sequential_retry_allowed"])
        self.assertEqual(
            result["recovery_decision"]["frozen_next_stage"],
            "stage_6_14p_process_isolated_determinization_parallel_equivalence",
        )
        self.assertFalse(result["integrity"]["new_rollout_executed"])
        self.assertFalse(result["integrity"]["partial_comparison_used"])
        self.assertEqual(sum(result["forbidden_operation_counts"].values()), 0)

    def test_output_refusal(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "audit.json"
            output.write_text("{}", encoding="utf-8")
            with self.assertRaisesRegex(RuntimeError, "already exists"):
                recovery.ensure_output_state(output)


if __name__ == "__main__":
    unittest.main()
