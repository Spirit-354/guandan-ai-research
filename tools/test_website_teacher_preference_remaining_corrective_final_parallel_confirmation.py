from __future__ import annotations

import copy
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import website_information_set as information_set
import website_teacher_preference_corrective_residual_confirmation as stage_6_9
import website_teacher_preference_remaining_corrective_final_parallel_confirmation as confirmation
import website_teacher_preference_unpaired_confirmation as frozen_confirmation


def completed_case(target: dict) -> dict:
    teacher_returns = [1.0] * 16
    top1_returns = [0.0] * 16
    paired = []
    for item in frozen_confirmation.rollout_schedule():
        paired.append(
            {
                **item,
                "determinization_seed": information_set._stable_determinization_seed(
                    target["source_sample"], item["determinization_index"]
                ),
                "teacher_return": 1.0,
                "residual_return": 0.0,
                "teacher_minus_residual_return": 1.0,
            }
        )
    candidates = []
    for role, index, action_hash, cards, values in (
        (
            "teacher",
            target["teacher_action_index"],
            target["teacher_action_sha256"],
            target["teacher_physical_identity"]["cards_website"],
            teacher_returns,
        ),
        (
            "residual",
            target["top1_action_index"],
            target["top1_action_sha256"],
            target["top1_physical_identity"]["cards_website"],
            top1_returns,
        ),
    ):
        candidates.append(
            {
                "role": role,
                "action_index": index,
                "action_sha256": action_hash,
                "physical_cards_website": cards,
                "requested_rollout_count": 16,
                "completed_rollout_count": 16,
                "completion_rate": 1.0,
                "mean_return": sum(values) / len(values),
                "return_variance": frozen_confirmation.sample_variance(values),
                "failure_count": 0,
                "failures": [],
            }
        )
    return {
        "game_id": target["game_id"],
        "turn_index": target["turn_index"],
        "pipeline_partition": "pipeline_train",
        "legal_action_count": target["legal_action_count"],
        "legal_action_order_sha256": target["legal_action_order_sha256"],
        "case_seconds": 0.1,
        "case_timed_out": False,
        "candidate_results": candidates,
        "paired_rollouts": paired,
        "metrics": stage_6_9.normalize_metrics(
            frozen_confirmation.directional_metrics(
                teacher_returns, top1_returns
            )
        ),
    }


class FinalParallelConfirmationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.context = confirmation.load_context()
        cls.cases = [completed_case(target) for target in cls.context["targets"]]

    def test_frozen_context_has_exact_execution_and_exclusion_counts(self) -> None:
        self.assertEqual(len(self.context["frozen_hashes"]), 30)
        self.assertEqual(
            [
                (
                    item["game_id"],
                    item["turn_index"],
                    item["top1_action_index"],
                    item["top1_action_sha256"],
                )
                for item in self.context["targets"]
            ],
            confirmation.EXPECTED_EXECUTED,
        )
        self.assertEqual(len(self.context["excluded"]), 1)
        self.assertEqual(len(self.context["heldout"]), 3)
        self.assertEqual(len(self.context["other"]), 16)

    def test_parallel_metadata_is_exactly_two_cases(self) -> None:
        metadata = confirmation.expected_parallel_execution_metadata()
        self.assertEqual(metadata["total_worker_task_count"], 16)
        self.assertEqual(metadata["total_schedule_item_count"], 32)
        self.assertEqual(metadata["total_candidate_call_count"], 64)
        self.assertEqual(metadata["sequential_fallback_count"], 0)
        self.assertEqual(metadata["retry_count"], 0)

    def test_complete_result_accepts_exact_64_rollouts(self) -> None:
        result = confirmation.build_result(self.context, self.cases)
        self.assertEqual(result["completed_rollouts"], 64)
        self.assertEqual(
            result["continuation_profile_rollout_counts"],
            {"greedy_bot": 32, "tempo_baseline": 32},
        )
        self.assertEqual(
            result["directional_classification_counts"],
            {
                "teacher_over_residual_supported": 2,
                "residual_over_teacher_supported": 0,
                "inconclusive": 0,
            },
        )
        self.assertEqual(sum(result["forbidden_operation_counts"].values()), 0)

    def test_partial_or_timed_out_case_is_rejected(self) -> None:
        cases = copy.deepcopy(self.cases)
        cases[0]["case_timed_out"] = True
        with self.assertRaisesRegex(RuntimeError, "mismatch|partial or failed"):
            confirmation.build_result(self.context, cases)

    def test_excluded_cases_have_zero_use(self) -> None:
        isolated = (
            self.context["excluded"]
            + self.context["heldout"]
            + self.context["other"]
        )
        self.assertTrue(
            all(
                item["source_sample_mapping_count"] == 0
                and item["case_execution_count"] == 0
                and item["rollout_count"] == 0
                and item[
                    "threshold_objective_or_confirmation_design_use_count"
                ]
                == 0
                for item in isolated
            )
        )

    def test_atomic_output_refuses_overwrite(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "confirmation.json"
            confirmation.write_output_once(path, {"status": "completed"})
            self.assertTrue(path.exists())
            with self.assertRaisesRegex(RuntimeError, "already exists"):
                confirmation.write_output_once(path, {})


if __name__ == "__main__":
    unittest.main()
