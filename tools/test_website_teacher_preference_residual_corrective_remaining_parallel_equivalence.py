from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import website_information_set as information_set
import website_teacher_preference_residual_corrective_remaining_parallel_equivalence as parallel


class ParallelEquivalenceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.target, self.candidates = parallel.synthetic_target_and_candidates()
        self.tasks = parallel.build_determinization_tasks(
            self.target,
            self.candidates,
            parallel.SYNTHETIC_DEADLINE,
        )

    def test_task_manifest_reconstructs_exact_frozen_schedule(self) -> None:
        self.assertEqual(len(self.tasks), 8)
        self.assertEqual(
            [task["determinization_index"] for task in self.tasks], list(range(8))
        )
        self.assertEqual(
            sum(len(task["schedule_items"]) for task in self.tasks), 16
        )
        self.assertEqual(
            sum(len(parallel.expected_call_contracts(task)) for task in self.tasks),
            32,
        )
        for index, task in enumerate(self.tasks):
            self.assertEqual(
                [item["rollout_index"] for item in task["schedule_items"]],
                [2 * index, 2 * index + 1],
            )
            self.assertEqual(
                [item["continuation_profile"] for item in task["schedule_items"]],
                ["greedy_bot", "tempo_baseline"],
            )
            self.assertEqual(task["case_deadline_monotonic"], 987654.0)
            self.assertEqual(task["max_rollout_steps"], 300)

    def test_spawned_process_results_equal_sequential_results(self) -> None:
        sequential = parallel.run_tasks_sequential(
            self.tasks, parallel.synthetic_determinization_worker
        )
        isolated = parallel.run_tasks_process_isolated(
            self.tasks, parallel.synthetic_determinization_worker
        )
        sequential_calls = parallel.normalized_call_payload(
            parallel.validate_and_order_results(self.tasks, sequential)
        )
        isolated_calls = parallel.normalized_call_payload(
            parallel.validate_and_order_results(self.tasks, isolated)
        )
        self.assertEqual(sequential_calls, isolated_calls)
        self.assertEqual(len(isolated_calls), 32)

    def test_timeout_failure_results_and_aggregate_match(self) -> None:
        tasks = parallel.build_determinization_tasks(
            self.target,
            self.candidates,
            parallel.SYNTHETIC_DEADLINE,
            synthetic_failure_mode=True,
        )
        sequential = parallel.normalized_call_payload(
            parallel.validate_and_order_results(
                tasks,
                parallel.run_tasks_sequential(
                    tasks, parallel.synthetic_determinization_worker
                ),
            )
        )
        isolated = parallel.normalized_call_payload(
            parallel.validate_and_order_results(
                tasks,
                parallel.run_tasks_process_isolated(
                    tasks, parallel.synthetic_determinization_worker
                ),
            )
        )
        self.assertEqual(sequential, isolated)
        self.assertEqual(sum(item["failure"] is not None for item in isolated), 2)
        sequential_raw = parallel.build_raw_case_result(
            self.target,
            self.candidates,
            sequential,
            case_seconds=0.0,
            case_timed_out=True,
        )
        isolated_raw = parallel.build_raw_case_result(
            self.target,
            self.candidates,
            isolated,
            case_seconds=0.0,
            case_timed_out=True,
        )
        self.assertEqual(sequential_raw, isolated_raw)
        self.assertEqual(
            [item["failure_count"] for item in isolated_raw["candidate_results"]],
            [1, 1],
        )

    def test_parent_rejects_missing_duplicate_seed_and_deadline_changes(self) -> None:
        results = parallel.run_tasks_sequential(
            self.tasks, parallel.synthetic_determinization_worker
        )
        with self.assertRaisesRegex(RuntimeError, "task count mismatch"):
            parallel.validate_and_order_results(self.tasks, results[:-1])
        with self.assertRaisesRegex(RuntimeError, "missing or duplicated"):
            parallel.validate_and_order_results(
                self.tasks, results[:-1] + [results[0]]
            )
        seed_changed = json.loads(json.dumps(results))
        seed_changed[0]["items"][0]["determinization_seed"] += 1
        with self.assertRaisesRegex(RuntimeError, "seed mismatch"):
            parallel.validate_and_order_results(self.tasks, seed_changed)
        deadline_changed = json.loads(json.dumps(results))
        deadline_changed[0]["items"][0]["case_deadline_monotonic"] += 1.0
        with self.assertRaisesRegex(RuntimeError, "case_deadline_monotonic mismatch"):
            parallel.validate_and_order_results(self.tasks, deadline_changed)

    def test_equivalence_builder_never_calls_real_simulation(self) -> None:
        with mock.patch.object(
            information_set,
            "_simulate_candidate",
            side_effect=AssertionError("real simulation must remain unused"),
        ):
            result = parallel.build_equivalence_result()
        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["integrity"]["real_rollout_count"], 0)
        self.assertEqual(sum(result["forbidden_operation_counts"].values()), 0)
        self.assertTrue(
            result["formal_execution_gate"]["parallel_equivalence_passed"]
        )

    def test_output_refusal(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "equivalence.json"
            output.write_text("{}", encoding="utf-8")
            with self.assertRaisesRegex(RuntimeError, "already exists"):
                parallel.ensure_unused_output(output)


if __name__ == "__main__":
    unittest.main()
