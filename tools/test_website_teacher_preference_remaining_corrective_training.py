from __future__ import annotations

from collections import Counter
from pathlib import Path
import sys
import tempfile
import unittest

import torch


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import website_teacher_preference_remaining_corrective_training as training


class RemainingCorrectiveTrainingTests(unittest.TestCase):
    def test_fixed_recipe_exactly_matches_stage_6_11(self) -> None:
        self.assertEqual(training.fixed_recipe(), training.recipe_authority.fixed_recipe())
        self.assertEqual(training.fixed_recipe()["seed"], 20260714)
        self.assertEqual(training.fixed_recipe()["epochs"], 20)
        self.assertEqual(training.fixed_recipe()["states_per_batch"], 6)
        self.assertEqual(training.fixed_recipe()["learning_rate"], 0.001)
        self.assertIsNone(training.fixed_recipe()["initial_checkpoint"])

    def test_output_guard_refuses_existing_path(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            checkpoint = Path(directory) / "checkpoint.pth"
            report = Path(directory) / "report.json"
            training.ensure_unused_outputs(checkpoint, report)
            checkpoint.touch()
            with self.assertRaisesRegex(RuntimeError, "already exists"):
                training.ensure_unused_outputs(checkpoint, report)

    def test_checkpoint_metadata_is_fixed_and_unpromoted(self) -> None:
        model = torch.nn.Linear(2, 1)
        hashes = {"dataset": "abc"}
        payload = training.checkpoint_payload(model, hashes)
        self.assertEqual(payload["schema_version"], training.CHECKPOINT_SCHEMA_VERSION)
        self.assertEqual(payload["pipeline_train_state_count"], 18)
        self.assertEqual(payload["pipeline_train_pair_count"], 30)
        self.assertEqual(payload["pipeline_development_training_use_count"], 0)
        self.assertEqual(payload["fine_tuning_run_count"], 0)
        self.assertIs(payload["checkpoint_promotion_allowed"], False)
        self.assertIs(payload["capability_claim_allowed"], False)

    def test_real_v3_loader_reproduces_counts_weights_and_isolation(self) -> None:
        pairs, hashes, dataset = training.validate_inputs()
        groups = training.frozen_training.build_state_groups(pairs)
        train_groups = [
            group for group in groups if group["pipeline_partition"] == "pipeline_train"
        ]
        development_groups = [
            group
            for group in groups
            if group["pipeline_partition"] == "pipeline_development"
        ]
        self.assertEqual(len(pairs), 34)
        self.assertEqual(len(train_groups), 18)
        self.assertEqual(len(development_groups), 4)
        self.assertEqual(sum(len(group["pairs"]) for group in train_groups), 30)
        self.assertEqual(sum(len(group["pairs"]) for group in development_groups), 4)
        self.assertEqual(
            Counter(len(group["pairs"]) for group in groups),
            Counter({1: 13, 2: 6, 3: 3}),
        )
        self.assertTrue(
            all(
                abs(
                    sum(
                        float(pair["within_state_pair_weight"])
                        for pair in group["pairs"]
                    )
                    - 1.0
                )
                < 1e-12
                for group in groups
            )
        )
        self.assertEqual(
            dataset["summary"]["stage_6_14e_remaining_corrective_pair_count"],
            2,
        )
        self.assertEqual(hashes["corrective_dataset_v3"], training.EXPECTED_HASHES["corrective_dataset_v3"])
        self.assertEqual(len(hashes), 19)

    def test_metrics_report_all_frozen_pair_sources(self) -> None:
        pairs, _hashes, _dataset = training.validate_inputs()
        training.frozen_training.set_deterministic()
        model = training.danzero_dmc.build_q_model(torch.device("cpu"))
        metrics = training.evaluate_model(model, pairs)
        self.assertEqual(metrics["pipeline_train"]["aggregate"]["pair_count"], 30)
        self.assertEqual(metrics["pipeline_train"]["base_pairs"]["pair_count"], 18)
        self.assertEqual(
            metrics["pipeline_train"]["stage_6_4_corrective_pairs"]["pair_count"],
            6,
        )
        self.assertEqual(
            metrics["pipeline_train"]["stage_6_9_residual_pairs"]["pair_count"],
            4,
        )
        self.assertEqual(
            metrics["pipeline_train"]["stage_6_14e_remaining_pairs"]["pair_count"],
            2,
        )
        self.assertEqual(
            metrics["pipeline_development"]["aggregate"]["pair_count"], 4
        )


if __name__ == "__main__":
    unittest.main()
