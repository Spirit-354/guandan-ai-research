from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import website_teacher_preference_unpaired_confirmation as confirmation


class FakeAdaptive:
    pass


class WebsiteTeacherPreferenceUnpairedConfirmationTests(unittest.TestCase):
    def test_schedule_is_fixed_and_shares_eight_determinizations(self) -> None:
        schedule = confirmation.rollout_schedule()
        self.assertEqual(len(schedule), 16)
        self.assertEqual(
            [item["continuation_profile"] for item in schedule].count("greedy_bot"),
            8,
        )
        self.assertEqual(
            [item["continuation_profile"] for item in schedule].count(
                "tempo_baseline"
            ),
            8,
        )
        self.assertEqual(
            [item["determinization_index"] for item in schedule],
            [value for value in range(8) for _ in range(2)],
        )

    def test_directional_metrics_support_teacher(self) -> None:
        metrics = confirmation.directional_metrics([1.0] * 16, [-1.0] * 16)
        self.assertEqual(metrics["directional_classification"], "teacher_over_top1_supported")
        self.assertEqual(metrics["teacher_minus_top1_advantage"], 2.0)
        self.assertEqual(metrics["paired_return_variance"], 0.0)
        self.assertEqual(metrics["teacher_over_top1_failure_reasons"], [])

    def test_directional_metrics_support_top1_symmetrically(self) -> None:
        metrics = confirmation.directional_metrics([-1.0] * 16, [1.0] * 16)
        self.assertEqual(metrics["directional_classification"], "top1_over_teacher_supported")
        self.assertEqual(metrics["top1_over_teacher_failure_reasons"], [])
        self.assertIn(
            "mean_advantage_below_frozen_threshold",
            metrics["teacher_over_top1_failure_reasons"],
        )

    def test_gate_is_conservative_for_missing_profile_evidence(self) -> None:
        reasons = confirmation.gate_failure_reasons(
            paired_count=16,
            advantage=0.5,
            candidate_variance=0.0,
            lower_bound=0.1,
            profile_advantages={"greedy_bot": 0.5, "tempo_baseline": None},
        )
        self.assertEqual(
            reasons, ["continuation_profile_advantage_below_frozen_threshold"]
        )

    def test_execute_case_uses_exact_two_candidates_and_288_contract(self) -> None:
        restore_calls = []
        simulate_calls = []

        def restore(sample, components, rng):
            game = {"key": sample["game_id"], "call": len(restore_calls)}
            restore_calls.append(game)
            return game

        def simulate(
            base_game,
            candidate,
            components,
            adaptive,
            seed,
            max_steps,
            profile,
            profile_config,
            deadline,
            baseline_cache,
            baseline_stats,
        ):
            simulate_calls.append((base_game, candidate["role"], seed, profile))
            return (1.0 if candidate["role"] == "teacher" else -1.0), None

        target = {
            "game_id": "1",
            "turn_index": 2,
            "source_sample": {"game_id": "1", "turn_index": 2},
            "legal_action_count": 2,
            "legal_action_order_sha256": "abc",
        }
        candidates = [{"role": "teacher"}, {"role": "top1"}]
        result = confirmation.execute_case(
            target,
            candidates,
            {},
            FakeAdaptive(),
            {},
            {},
            {},
            restore_fn=restore,
            simulate_fn=simulate,
        )
        self.assertEqual(len(restore_calls), 16)
        self.assertEqual(len(simulate_calls), 32)
        for index in range(0, 32, 2):
            self.assertIs(simulate_calls[index][0], simulate_calls[index + 1][0])
            self.assertEqual(simulate_calls[index][2], simulate_calls[index + 1][2])
            self.assertEqual(simulate_calls[index][3], simulate_calls[index + 1][3])
        self.assertEqual(result["metrics"]["paired_count"], 16)

    def test_execute_case_rejects_any_third_or_reordered_candidate(self) -> None:
        target = {
            "game_id": "1",
            "turn_index": 2,
            "source_sample": {},
            "legal_action_count": 2,
            "legal_action_order_sha256": "abc",
        }
        with self.assertRaisesRegex(RuntimeError, "exactly teacher/top1"):
            confirmation.execute_case(
                target,
                [{"role": "top1"}, {"role": "teacher"}],
                {},
                FakeAdaptive(),
                {},
                {},
                {},
            )

    def test_atomic_output_refuses_overwrite_and_cleans_failed_temp(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "result.json"
            confirmation.write_json_once(output, {"ok": True})
            self.assertEqual(json.loads(output.read_text(encoding="utf-8")), {"ok": True})
            with self.assertRaisesRegex(RuntimeError, "already exists"):
                confirmation.write_json_once(output, {"ok": False})
            self.assertFalse((Path(directory) / "result.json.tmp").exists())


if __name__ == "__main__":
    unittest.main()
