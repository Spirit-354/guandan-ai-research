from __future__ import annotations

import sys
import json
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import website_shadow


def sample_state() -> dict:
    hand = [
        "S2", "H2", "D2", "C2", "S3", "H3", "D3", "C3", "S4",
        "H4", "D4", "C4", "S5", "H5", "D5", "C5", "S6", "H6",
        "D6", "C6", "S7", "H7", "D7", "C7", "ST", "B", "R",
    ]
    return {
        "seats": ["self", "opponent-a", "teammate", "opponent-b"],
        "teams": {"team0": ["self", "teammate"], "team1": ["opponent-a", "opponent-b"]},
        "level": "7",
        "your_seat": 0,
        "your_team": 0,
        "your_hand": hand,
        "hand_counts": [27, 27, 27, 26],
        "last_play": ["S9"],
        "last_player": 3,
        "ranking": [],
        "trick_history": [[3, ["S9"]], [0, []]],
    }


class WebsiteShadowTests(unittest.TestCase):
    def test_public_history_extends_growing_and_rolling_windows(self) -> None:
        tracker: list[tuple[int, list[str]]] = []
        first = {"trick_history": [[0, ["S2"]], [1, []], [2, ["H3"]]]}
        second = {"trick_history": [[0, ["S2"]], [1, []], [2, ["H3"]], [3, []]]}
        rolling = {"trick_history": [[2, ["H3"]], [3, []], [0, ["D4"]]]}
        self.assertTrue(website_shadow.extend_public_history(tracker, first)["consistent"])
        self.assertEqual(website_shadow.extend_public_history(tracker, second)["new_entry_count"], 1)
        result = website_shadow.extend_public_history(tracker, rolling)
        self.assertTrue(result["consistent"])
        self.assertEqual(result["overlap_count"], 2)
        self.assertEqual(result["history"][-1], (0, ["D4"]))

    def test_state_adapter_and_shadow_audit(self) -> None:
        state = sample_state()
        audit = website_shadow.build_shadow_audit(state, ["ST"], ["ST"])
        self.assertEqual(audit["paper_state_dim"], 513)
        self.assertEqual(audit["website_state_dim"], 487)
        self.assertTrue(audit["team_mapping"]["valid"])
        self.assertTrue(audit["submitted_action"]["cards_in_hand"])
        self.assertTrue(audit["submitted_action"]["local_legal"])
        self.assertTrue(audit["submitted_action"]["oracle_match"])
        self.assertTrue(audit["information_set_consistent"])
        self.assertFalse(audit["model_controlled_action"])
        self.assertEqual(len(audit["legal_candidates"]), audit["legal_candidate_count"])
        self.assertTrue(audit["legal_candidates"])
        self.assertTrue(
            all(len(candidate["physical_action_54"]) == 54 for candidate in audit["legal_candidates"])
        )

    def test_server_result_and_summary(self) -> None:
        audit = website_shadow.build_shadow_audit(sample_state(), ["ST"], ["ST"])
        website_shadow.mark_submit_result(audit, {"is_success": True})
        summary = website_shadow.summarize_decisions([{"website_shadow": audit}])
        self.assertTrue(summary["threshold_passed"])
        self.assertEqual(summary["model_controlled_action_count"], 0)
        self.assertEqual(summary["website_rule_disagree_count"], 0)

    def test_action_not_in_hand_is_detected(self) -> None:
        audit = website_shadow.build_shadow_audit(sample_state(), ["CA"], ["CA"])
        self.assertTrue(audit["suggested_action"]["action_not_in_hand"])
        self.assertFalse(audit["suggested_action"]["local_legal"])
        summary = website_shadow.summarize_decisions([{"website_shadow": audit}])
        self.assertFalse(summary["threshold_passed"])

    def test_finished_teammate_is_mapped_from_username(self) -> None:
        state = sample_state()
        state["ranking"] = ["teammate"]
        game = website_shadow.website_state_to_feature_game(state)
        self.assertIn(2, game.ranking)

    def test_historical_state_reconstruction(self) -> None:
        final_state = sample_state()
        final_state.update({"completed": True, "trick_history": [[3, ["S9"]], [0, []]]})
        record = {"final_state": final_state}
        decision = {
            "level": "7",
            "hand": final_state["your_hand"],
            "hand_counts": final_state["hand_counts"],
            "last_play": ["S9"],
            "last_player": 3,
            "current_turn": 0,
            "trick_index": 1,
        }
        restored = website_shadow.reconstruct_historical_state(record, decision)
        self.assertEqual(restored["trick_history"], [[3, ["S9"]]])
        self.assertEqual(restored["your_hand"], final_state["your_hand"])

    def test_historical_action_audit_skips_unreconstructable_state(self) -> None:
        final_state = sample_state()
        final_state.update({"completed": True, "trick_history": [[3, ["S9"]]] * 40})
        record = {"final_state": final_state}
        decision = {
            "level": "7",
            "hand": final_state["your_hand"],
            "hand_counts": final_state["hand_counts"],
            "last_play": ["S9"],
            "last_player": 3,
            "current_turn": 0,
            "trick_index": 40,
            "play": ["ST"],
        }
        audit = website_shadow.build_historical_action_audit(record, decision)
        self.assertFalse(audit["state_encoding_evaluated"])
        self.assertTrue(audit["suggested_action"]["local_legal"])
        self.assertTrue(audit["suggested_action"]["oracle_match"])

    def test_online_summary_requires_enough_exhaustive_games(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            for game_id in ("1", "2"):
                payload = {
                    "game_id": game_id,
                    "metric_source": "leaderboard_elo",
                    "website_shadow_summary": {
                        "shadow_decision_count": 3,
                        "oracle_exhaustive_decision_count": 3,
                        "threshold_passed": True,
                    },
                }
                Path(temp_dir, f"research_game_{game_id}.json").write_text(
                    json.dumps(payload), encoding="utf-8"
                )
            out_path = str(Path(temp_dir, "summary.json"))
            result = website_shadow.summarize_shadow_log_dir(temp_dir, out_path, minimum_games=2)
            self.assertTrue(result["online_shadow_gate_satisfied"])
            self.assertEqual(result["shadow_decision_count"], 6)
            result = website_shadow.summarize_shadow_log_dir(temp_dir, out_path, minimum_games=3)
            self.assertFalse(result["online_shadow_gate_satisfied"])


if __name__ == "__main__":
    unittest.main()
