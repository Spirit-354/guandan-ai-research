from __future__ import annotations

import sys
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

    def test_teacher_replay_is_sampled_after_regular_replay_eviction(self) -> None:
        try:
            import torch
        except ImportError:
            self.skipTest("PyTorch is unavailable")

        state = [0.0] * danzero_features.DANZERO_COMPACT_STATE_DIM
        action = [0.0] * danzero_features.DANZERO_PHYSICAL_ACTION_DIM
        negative = list(action)
        negative[0] = 1.0
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
                    "negative_actions": [negative],
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
        )
        self.assertEqual(result["teacher_sample_count"], 1)
        self.assertEqual(result["teacher_negative_count"], 1)


if __name__ == "__main__":
    unittest.main()
