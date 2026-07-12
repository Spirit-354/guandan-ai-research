from __future__ import annotations

import sys
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
        "hand_counts": [27, 26, 26, 26],
        "last_play": ["S9"],
        "last_player": 3,
        "ranking": [],
        "trick_history": [[3, ["S9"]], [0, []]],
    }


class WebsiteShadowTests(unittest.TestCase):
    def test_state_adapter_and_shadow_audit(self) -> None:
        state = sample_state()
        audit = website_shadow.build_shadow_audit(state, ["ST"], ["ST"])
        self.assertEqual(audit["paper_state_dim"], 513)
        self.assertEqual(audit["website_state_dim"], 487)
        self.assertTrue(audit["team_mapping"]["valid"])
        self.assertTrue(audit["submitted_action"]["cards_in_hand"])
        self.assertTrue(audit["submitted_action"]["local_legal"])
        self.assertTrue(audit["submitted_action"]["oracle_match"])
        self.assertFalse(audit["model_controlled_action"])

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


if __name__ == "__main__":
    unittest.main()
