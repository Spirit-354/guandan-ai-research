from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import website_danzero_dataset
import website_shadow
from test_website_shadow import sample_state


class WebsiteDanZeroDatasetTests(unittest.TestCase):
    def test_extension_splits_preserve_frozen_games_and_locked_set(self) -> None:
        base_manifest = {
            "session_split_assignments": {
                "old-train": "train",
                "old-dev": "development",
                "old-locked": "locked_test",
            },
            "split_game_ids": {
                "train": ["g-train"],
                "development": ["g-dev"],
                "locked_test": ["g-locked"],
            },
        }
        samples = [
            {"source_session": "old-train", "game_id": "g-train"},
            {"source_session": "old-dev", "game_id": "g-dev"},
            {"source_session": "old-locked", "game_id": "g-locked"},
            {"source_session": "new-train", "game_id": "g-new-train"},
            {"source_session": "new-dev", "game_id": "g-new-dev"},
        ]
        assignments = website_danzero_dataset._assign_extension_splits(
            samples,
            base_manifest,
            {"new-train": "train", "new-dev": "development"},
        )
        self.assertEqual(assignments["old-locked"], "locked_test")
        self.assertEqual(assignments["new-train"], "train")
        self.assertEqual(assignments["new-dev"], "development")
        with self.assertRaisesRegex(RuntimeError, "explicit train/development assignment"):
            website_danzero_dataset._assign_extension_splits(
                samples,
                base_manifest,
                {"new-train": "train"},
            )
        with self.assertRaisesRegex(RuntimeError, "cannot be remapped"):
            website_danzero_dataset._assign_extension_splits(
                samples,
                base_manifest,
                {"old-locked": "train", "new-train": "train", "new-dev": "development"},
            )

    def test_extension_split_file_forbids_new_locked_test(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir, "splits.json")
            path.write_text(
                json.dumps({"session_split_assignments": {"new-session": "locked_test"}}),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(RuntimeError, "locked_test is frozen"):
                website_danzero_dataset._load_extension_session_assignments(path)

    def test_rollout_gate_uses_consistent_train_dev_partition(self) -> None:
        samples = []
        for index in range(500):
            samples.append(
                {
                    "game_id": str(index // 10),
                    "state_fingerprint": f"state-{index}",
                    "split": "development" if index >= 400 else "train",
                    "first_player": index % 4,
                    "level": "7",
                    "elo_band_100": "2000-2099" if index % 2 else "1900-1999",
                    "robot_table_signature": "bot-table",
                    "your_seat": 0,
                    "outcome": "win" if index % 2 else "loss",
                    "legal_action_count": 2,
                    "level_card_available": True,
                    "heart_level_wildcard_available": index == 0,
                    "was_lead": index % 5 == 0,
                    "was_follow": index % 5 != 0,
                    "is_endgame": index % 3 == 0,
                    "bomb_candidate_available": index % 7 == 0,
                    "source_session": "dev" if index >= 400 else "train",
                    "information_set_consistent": True,
                }
            )
        samples.append(
            {
                **samples[0],
                "game_id": "locked-game",
                "state_fingerprint": "locked-state",
                "split": "locked_test",
                "source_session": "locked",
            }
        )
        samples.append({**samples[0], "state_fingerprint": "legacy-bad", "information_set_consistent": False})
        coverage = website_danzero_dataset._coverage_summary(samples)
        self.assertEqual(coverage["consistent_train_dev_decisions"], 500)
        self.assertLess(coverage["information_set_consistent_rate"], 1.0)
        self.assertTrue(coverage["information_set_rollout_gate_passed"])

    def test_game_level_split_has_no_overlap(self) -> None:
        samples = [{"game_id": str(index)} for index in range(10)]
        train_ids, validation_ids = website_danzero_dataset._split_game_ids(samples, 0.2, 7)
        self.assertFalse(train_ids & validation_ids)
        self.assertEqual(len(train_ids), 8)
        self.assertEqual(len(validation_ids), 2)

    def test_session_split_targets_multiple_recent_sessions(self) -> None:
        samples = []
        for session in range(10):
            for game in range(5):
                samples.append(
                    {
                        "source_session": f"session-{session}",
                        "completed_at": f"2026-07-{session + 1:02d}",
                        "game_id": f"{session}-{game}",
                    }
                )
        assignments = website_danzero_dataset._assign_provisional_splits(samples)
        self.assertEqual(sum(value == "locked_test" for value in assignments.values()), 2)
        self.assertEqual(sum(value == "development" for value in assignments.values()), 2)
        self.assertEqual(sum(value == "train" for value in assignments.values()), 6)

    def test_partition_paths_do_not_replace_source_suffix(self) -> None:
        source = Path("dataset.pth")
        self.assertEqual(
            website_danzero_dataset._partition_path(source, "train_dev").name,
            "dataset.train_dev.pth",
        )

    def test_completed_verified_shadow_log_is_exported(self) -> None:
        state = sample_state()
        audit = website_shadow.build_shadow_audit(state, ["ST"], ["ST"])
        website_shadow.mark_submit_result(audit, {"is_success": True})
        decision = {
            "turn": 1,
            "scenario": "all_unknown",
            "level": "7",
            "website_shadow": audit,
        }
        final_state = dict(state)
        final_state.update(
            {
                "completed": True,
                "winner_team": 0,
                "_bot_table_evidence": {"bot_table_verified": True},
            }
        )
        record = {
            "game_id": "test-1",
            "profile": "tempo_baseline",
            "game_counted": True,
            "metric_source": "leaderboard_elo",
            "elo_before": 2201,
            "elo_after": 2214,
            "elo_delta": 13,
            "website_shadow_summary": website_shadow.summarize_decisions([decision]),
            "decisions": [decision],
            "final_state": final_state,
        }
        with tempfile.TemporaryDirectory() as temp_dir:
            log_path = Path(temp_dir, "research_game_test.json")
            out_path = Path(temp_dir, "dataset.jsonl")
            log_path.write_text(json.dumps(record), encoding="utf-8")
            summary = website_danzero_dataset.build_dataset(temp_dir, str(out_path))
            sample = json.loads(out_path.read_text(encoding="utf-8").strip())
        self.assertTrue(summary["threshold_passed"])
        self.assertEqual(summary["accepted_games"], 1)
        self.assertEqual(summary["accepted_decisions"], 1)
        self.assertEqual(sample["state_dim"], 513)
        self.assertEqual(sample["action_dim"], 54)
        self.assertEqual(len(sample["legal_actions"]), sample["legal_action_count"])
        self.assertEqual(sample["team_reward"], 1.0)
        self.assertEqual(sample["elo_band_100"], "2200-2299")
        self.assertEqual(sample["split"], "train")
        self.assertFalse(summary["coverage_gate_passed"])
        self.assertEqual(summary["behavior_value_scope"], "Q(s,a_behavior)_only")

    def test_unverified_bot_table_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            record = {
                "game_id": "test-2",
                "game_counted": True,
                "metric_source": "leaderboard_elo",
                "website_shadow_summary": {"threshold_passed": True},
                "final_state": {"completed": True, "_bot_table_evidence": {}},
            }
            Path(temp_dir, "research_game_test.json").write_text(
                json.dumps(record), encoding="utf-8"
            )
            out_path = Path(temp_dir, "dataset.jsonl")
            summary = website_danzero_dataset.build_dataset(temp_dir, str(out_path))
        self.assertFalse(summary["threshold_passed"])
        self.assertEqual(summary["accepted_games"], 0)
        self.assertEqual(summary["reject_reason_counts"]["bot_table_not_verified"], 1)


if __name__ == "__main__":
    unittest.main()
