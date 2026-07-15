from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import website_teacher_preference_residual_corrective_remaining_parallel_confirmation as formal


class RemainingTop1ParallelConfirmationTests(unittest.TestCase):
    def test_frozen_parallel_authority_and_preflight(self) -> None:
        hashes = formal.verify_frozen_inputs()
        self.assertEqual(len(hashes), 10)
        with mock.patch.object(formal.confirmation, "ensure_unused_output"):
            result = formal.preflight()
        self.assertEqual(result["pipeline_train_case_count"], 3)
        self.assertEqual(result["excluded_inconclusive_train_case_count"], 3)
        self.assertEqual(result["pipeline_development_heldout_count"], 3)
        self.assertEqual(result["worker_task_count"], 24)
        self.assertEqual(result["schedule_item_count"], 48)
        self.assertEqual(result["requested_total_rollouts"], 96)
        self.assertEqual(result["sequential_fallback_count"], 0)
        self.assertEqual(result["retry_count"], 0)

    def test_rejects_changed_parallel_authority(self) -> None:
        payload = formal.load_json(formal.PARALLEL_ARTIFACT_PATH)
        changed = copy.deepcopy(payload)
        changed["formal_execution_gate"]["sequential_retry_allowed"] = True
        with self.assertRaisesRegex(RuntimeError, "parallel authority mismatch"):
            formal.verify_parallel_authority(changed)

    def test_parallel_metadata_is_exact_and_fail_closed(self) -> None:
        result = {"parallel_execution": formal.expected_parallel_execution_metadata()}
        formal.validate_parallel_execution_metadata(result)
        changed = copy.deepcopy(result)
        changed["parallel_execution"]["retry_count"] = 1
        with self.assertRaisesRegex(RuntimeError, "metadata mismatch"):
            formal.validate_parallel_execution_metadata(changed)

    @staticmethod
    def fake_raw(target: dict, candidates: list[dict]) -> dict:
        teacher_returns = [1.0] * 16
        top1_returns = [-1.0] * 16
        candidate_results = []
        for candidate, values in zip(candidates, (teacher_returns, top1_returns)):
            candidate_results.append(
                {
                    **candidate,
                    "requested_rollout_count": 16,
                    "completed_rollout_count": 16,
                    "completion_rate": 1.0,
                    "mean_return": sum(values) / len(values),
                    "return_variance": 0.0,
                    "failure_count": 0,
                    "failures": [],
                }
            )
        paired = []
        for item in formal.frozen_confirmation.rollout_schedule():
            seed = formal.information_set._stable_determinization_seed(
                target["source_sample"], item["determinization_index"]
            )
            paired.append(
                {
                    **item,
                    "determinization_seed": seed,
                    "teacher_return": 1.0,
                    "top1_return": -1.0,
                    "teacher_minus_top1_return": 2.0,
                }
            )
        return {
            "game_id": target["game_id"],
            "turn_index": target["turn_index"],
            "pipeline_partition": "pipeline_train",
            "legal_action_count": target["legal_action_count"],
            "legal_action_order_sha256": target["legal_action_order_sha256"],
            "case_seconds": 1.0,
            "case_timed_out": False,
            "candidate_results": candidate_results,
            "paired_rollouts": paired,
            "metrics": formal.frozen_confirmation.directional_metrics(
                teacher_returns, top1_returns
            ),
        }

    def test_run_uses_three_parallel_cases_without_real_rollout(self) -> None:
        calls = []
        written = []

        def fake_materialize(target, _components, _adaptive):
            return [
                {
                    "role": "teacher",
                    "action_index": target["teacher_action_index"],
                    "action_sha256": target["teacher_action_sha256"],
                    "physical_cards_website": target["teacher_physical_identity"][
                        "cards_website"
                    ],
                },
                {
                    "role": "top1",
                    "action_index": target["top1_action_index"],
                    "action_sha256": target["top1_action_sha256"],
                    "physical_cards_website": target["top1_physical_identity"][
                        "cards_website"
                    ],
                },
            ]

        def fake_execute(target, candidates):
            calls.append((target["game_id"], target["turn_index"]))
            return self.fake_raw(target, candidates)

        with mock.patch.object(formal.confirmation, "ensure_unused_output"), mock.patch.object(formal, "materialize_candidates", fake_materialize), mock.patch.object(
            formal.parallel, "execute_parallel_case", fake_execute
        ), mock.patch.object(
            formal.frozen_confirmation,
            "write_json_once",
            lambda _path, result: written.append(result),
        ):
            result = formal.run({}, object())

        self.assertEqual(calls, [("13957", 14), ("14038", 12), ("13872", 4)])
        self.assertEqual(result["completed_rollouts"], 96)
        self.assertEqual(result["continuation_profile_rollout_counts"], {"greedy_bot": 48, "tempo_baseline": 48})
        self.assertEqual(result["timeout_case_count"], 0)
        self.assertEqual(result["candidate_failure_count"], 0)
        self.assertEqual(len(written), 1)
        formal.validate_parallel_execution_metadata(written[0])
        for item in result["excluded_inconclusive_train"] + result[
            "pipeline_development_heldout"
        ]:
            self.assertEqual(item["source_sample_mapping_count"], 0)
            self.assertEqual(item["case_execution_count"], 0)
            self.assertEqual(item["rollout_count"], 0)


if __name__ == "__main__":
    unittest.main()
