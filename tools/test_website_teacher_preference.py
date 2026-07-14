from __future__ import annotations

import hashlib
import sys
import tempfile
import unittest
from pathlib import Path

import torch


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import danzero_dmc
import website_teacher_preference as preference


def sample(game_id: str, *, identical: bool = False) -> dict:
    teacher = [0.0] * preference.ACTION_DIM
    behavior = [0.0] * preference.ACTION_DIM
    teacher[0] = 1.0
    behavior[0 if identical else 1] = 1.0
    return {
        "schema_version": preference.TEACHER_SCHEMA_VERSION,
        "game_id": game_id,
        "turn_index": 1,
        "split": "train",
        "state": [0.0] * preference.STATE_DIM,
        "state_dim": preference.STATE_DIM,
        "teacher_action": teacher,
        "behavior_action": behavior,
        "action_dim": preference.ACTION_DIM,
        "legal_actions": [teacher, behavior],
        "source_dataset_partition": "train_development",
        "locked_test_used": False,
        "preference_target": "teacher_action_beats_behavior_action",
    }


def write_dataset(path: Path, samples: list[dict]) -> str:
    payload = {
        "format": preference.TEACHER_SCHEMA_VERSION,
        "summary": {
            "schema_version": preference.TEACHER_SCHEMA_VERSION,
            "accepted_teacher_label_count": 22,
            "independent_teacher_games": 22,
            "training_gate_passed": True,
            "locked_test_loaded": False,
            "capability_claim_allowed": False,
            "threshold_passed": True,
            "source_base_partition_role": "train_development",
            "state_dim": preference.STATE_DIM,
            "action_dim": preference.ACTION_DIM,
        },
        "samples": samples,
    }
    torch.save(payload, path)
    return hashlib.sha256(path.read_bytes()).hexdigest()


class WebsiteTeacherPreferenceTests(unittest.TestCase):
    def test_teacher_validation_and_deterministic_game_split(self) -> None:
        samples = [sample(str(index)) for index in range(22)]
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir, "teacher.pth")
            digest = write_dataset(path, samples)
            loaded, _summary, actual = preference.load_teacher_dataset(
                path, expected_sha256=digest
            )
        train_ids, development_ids = preference.split_game_ids(loaded)
        expected = sorted(
            {str(index) for index in range(22)},
            key=lambda game_id: (
                hashlib.sha256(
                    f"{preference.SPLIT_NAMESPACE}{game_id}".encode("utf-8")
                ).hexdigest(),
                game_id,
            ),
        )
        self.assertEqual(development_ids, expected[:4])
        self.assertEqual(train_ids, expected[4:])
        self.assertFalse(set(train_ids) & set(development_ids))

    def test_teacher_validation_rejects_identical_preference_pair(self) -> None:
        samples = [sample(str(index), identical=index == 0) for index in range(22)]
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir, "teacher.pth")
            digest = write_dataset(path, samples)
            with self.assertRaisesRegex(RuntimeError, "identical teacher and behavior"):
                preference.load_teacher_dataset(path, expected_sha256=digest)

    def test_pairwise_loss_rewards_teacher_above_behavior(self) -> None:
        worse = preference.pairwise_ranking_loss(
            torch.tensor([0.0]), torch.tensor([1.0])
        )
        better = preference.pairwise_ranking_loss(
            torch.tensor([1.0]), torch.tensor([0.0])
        )
        self.assertLess(float(better.item()), float(worse.item()))

    def test_existing_model_dimensions_and_checkpoint_reload(self) -> None:
        torch.manual_seed(preference.SEED)
        model = danzero_dmc.build_q_model(torch.device("cpu"))
        states = torch.zeros((2, preference.STATE_DIM), dtype=torch.float32)
        actions = torch.zeros((2, preference.ACTION_DIM), dtype=torch.float32)
        before = model(states, actions).detach()
        self.assertEqual(tuple(before.shape), (2,))
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir, "checkpoint.pth")
            preference._save_checkpoint(path, model, "test-hash")
            with self.assertRaisesRegex(RuntimeError, "teacher_sha256 mismatch"):
                preference.load_checkpoint(path)
            reloaded, payload = preference.load_checkpoint(
                path, expected_teacher_sha256="test-hash"
            )
            after = reloaded(states, actions).detach()
        self.assertEqual(payload["state_dim"], preference.STATE_DIM)
        self.assertEqual(payload["action_dim"], preference.ACTION_DIM)
        self.assertFalse(payload["capability_claim_allowed"])
        self.assertFalse(payload["checkpoint_promotion_allowed"])
        torch.testing.assert_close(before, after, rtol=0.0, atol=0.0)


if __name__ == "__main__":
    unittest.main()
