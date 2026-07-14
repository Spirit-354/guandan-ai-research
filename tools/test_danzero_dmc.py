from __future__ import annotations

import sys
import tempfile
import unittest
from collections import deque
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import danzero_dmc
import danzero_features
import danzero_oracle


class DanZeroDMCTests(unittest.TestCase):
    def test_network_input_contract(self) -> None:
        self.assertEqual(danzero_dmc.DANZERO_DMC_INPUT_DIM, 567)
        self.assertEqual(
            danzero_dmc.DANZERO_DMC_INPUT_DIM,
            danzero_features.DANZERO_COMPACT_STATE_DIM
            + danzero_features.DANZERO_PHYSICAL_ACTION_DIM,
        )

    def test_epsilon_schedule(self) -> None:
        self.assertAlmostEqual(danzero_dmc.epsilon_for_game(0, 0.2, 0.05, 100), 0.2)
        self.assertAlmostEqual(danzero_dmc.epsilon_for_game(50, 0.2, 0.05, 100), 0.125)
        self.assertAlmostEqual(danzero_dmc.epsilon_for_game(100, 0.2, 0.05, 100), 0.05)
        self.assertAlmostEqual(danzero_dmc.epsilon_for_game(200, 0.2, 0.05, 100), 0.05)

    def test_teacher_samples_bypass_policy_staleness(self) -> None:
        self.assertTrue(
            danzero_dmc.should_drop_stale_sample(
                {"actor_version": 1, "teacher_action": False}, 500, 100
            )
        )
        self.assertFalse(
            danzero_dmc.should_drop_stale_sample(
                {"actor_version": 1, "teacher_action": True}, 500, 100
            )
        )

    def test_resume_metadata_gate(self) -> None:
        payload = {
            "schema_version": danzero_dmc.DANZERO_DMC_SCHEMA_VERSION,
            "state_dim": 513,
            "action_dim": 54,
            "input_dim": 567,
            "state_encoding_version": danzero_features.DANZERO_COMPACT_STATE_ENCODING_VERSION,
            "action_encoding_version": danzero_features.DANZERO_PHYSICAL_ACTION_ENCODING_VERSION,
            "oracle_version": danzero_oracle.ORACLE_VERSION,
            "oracle_exhaustive": True,
            "reward_version": "terminal_team_win_loss_v1",
        }
        self.assertEqual(danzero_dmc.validate_resume_payload(payload), [])
        payload["action_dim"] = 375
        self.assertEqual(len(danzero_dmc.validate_resume_payload(payload)), 1)

    def test_legacy_and_teacher_preference_checkpoints_load(self) -> None:
        try:
            import torch
        except ImportError:
            self.skipTest("PyTorch is unavailable")

        device = torch.device("cpu")
        model = danzero_dmc.build_q_model(device)
        optimizer = torch.optim.Adam(model.parameters(), lr=1e-4)
        legacy = danzero_dmc.checkpoint_payload(
            model,
            optimizer,
            deque(),
            deque(),
            {},
            3,
            __import__("random").Random(7),
        )
        preference = {
            "schema_version": danzero_dmc.TEACHER_PREFERENCE_CHECKPOINT_SCHEMA_VERSION,
            "model_state_dict": model.state_dict(),
            "state_dim": 513,
            "action_dim": 54,
            "teacher_sha256": danzero_dmc.TEACHER_PREFERENCE_SHA256,
            "training_mode": danzero_dmc.TEACHER_PREFERENCE_TRAINING_MODE,
            "capability_claim_allowed": False,
            "checkpoint_promotion_allowed": False,
        }
        with tempfile.TemporaryDirectory() as temp_dir:
            legacy_path = Path(temp_dir, "legacy.pth")
            preference_path = Path(temp_dir, "preference.pth")
            torch.save(legacy, legacy_path)
            torch.save(preference, preference_path)
            legacy_model, legacy_payload = danzero_dmc.load_q_checkpoint(legacy_path, device)
            preference_model, preference_payload = danzero_dmc.load_q_checkpoint(
                preference_path, device
            )
        states = torch.zeros((2, 513), dtype=torch.float32)
        actions = torch.zeros((2, 54), dtype=torch.float32)
        self.assertEqual(tuple(legacy_model(states, actions).shape), (2,))
        self.assertEqual(tuple(preference_model(states, actions).shape), (2,))
        self.assertEqual(legacy_payload["learner_version"], 3)
        self.assertEqual(
            preference_payload["schema_version"],
            danzero_dmc.TEACHER_PREFERENCE_CHECKPOINT_SCHEMA_VERSION,
        )

    def test_teacher_preference_checkpoint_metadata_is_strict(self) -> None:
        try:
            import torch
        except ImportError:
            self.skipTest("PyTorch is unavailable")

        model = danzero_dmc.build_q_model(torch.device("cpu"))
        base = {
            "schema_version": danzero_dmc.TEACHER_PREFERENCE_CHECKPOINT_SCHEMA_VERSION,
            "model_state_dict": model.state_dict(),
            "state_dim": 513,
            "action_dim": 54,
            "teacher_sha256": danzero_dmc.TEACHER_PREFERENCE_SHA256,
            "training_mode": danzero_dmc.TEACHER_PREFERENCE_TRAINING_MODE,
            "capability_claim_allowed": False,
            "checkpoint_promotion_allowed": False,
        }
        invalid_values = {
            "schema_version": "wrong",
            "state_dim": 512,
            "action_dim": 53,
            "teacher_sha256": "wrong",
            "training_mode": "wrong",
            "capability_claim_allowed": True,
            "checkpoint_promotion_allowed": True,
        }
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir, "invalid.pth")
            for field, value in invalid_values.items():
                with self.subTest(field=field):
                    torch.save({**base, field: value}, path)
                    with self.assertRaisesRegex(RuntimeError, field):
                        danzero_dmc.load_q_checkpoint(path, torch.device("cpu"))

    def test_paired_arena_layout_has_ten_balanced_pairs(self) -> None:
        plans = [danzero_dmc.arena_game_plan(index, 20260714, True) for index in range(20)]
        self.assertEqual({plan["pair_index"] for plan in plans}, set(range(10)))
        for pair_index in range(10):
            pair = [plan for plan in plans if plan["pair_index"] == pair_index]
            self.assertEqual(len(pair), 2)
            self.assertEqual({plan["model_team"] for plan in pair}, {0, 1})
            self.assertEqual(len({plan["game_seed"] for plan in pair}), 1)
            self.assertEqual(len({plan["first_player_seed"] for plan in pair}), 1)
            self.assertEqual(len({plan["arena_rng_seed"] for plan in pair}), 1)

    def test_teacher_replay_is_sampled_after_regular_replay_eviction(self) -> None:
        try:
            import torch
        except ImportError:
            self.skipTest("PyTorch is unavailable")

        state = [0.0] * danzero_features.DANZERO_COMPACT_STATE_DIM
        action = [0.0] * danzero_features.DANZERO_PHYSICAL_ACTION_DIM
        negative = list(action)
        negative[0] = 1.0
        second_negative = list(action)
        second_negative[1] = 1.0
        regular = deque(
            [
                {"state": state, "action": action, "target": -1.0, "teacher_action": False},
                {"state": state, "action": action, "target": 1.0, "teacher_action": False},
            ],
            maxlen=2,
        )
        teacher = deque(
            [
                {
                    "state": state,
                    "action": action,
                    "target": 1.0,
                    "teacher_action": True,
                    "negative_actions": [negative, second_negative],
                }
            ],
            maxlen=2,
        )
        model = danzero_dmc.build_q_model(torch.device("cpu"))
        optimizer = torch.optim.Adam(model.parameters(), lr=1e-4)
        result = danzero_dmc.train_batch(
            model,
            optimizer,
            regular,
            teacher,
            2,
            torch.device("cpu"),
            __import__("random").Random(7),
            0.2,
            1.0,
            0.5,
            True,
        )
        self.assertEqual(result["teacher_sample_count"], 1)
        self.assertEqual(result["teacher_negative_count"], 2)
        self.assertEqual(result["teacher_ranked_negative_count"], 1)


if __name__ == "__main__":
    unittest.main()
