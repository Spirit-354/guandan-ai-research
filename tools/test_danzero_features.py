from __future__ import annotations

import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import danzero_features as features


def player(hand, played=None, last=None):
    return SimpleNamespace(
        hand=list(hand),
        played_cards=list(played or []),
        last_played_cards=list(last or []),
    )


class DanZeroFeatureTests(unittest.TestCase):
    def test_encoding_contract_is_versioned_and_contiguous(self) -> None:
        self.assertTrue(features.DANZERO_PHYSICAL_ACTION_ENCODING_VERSION)
        self.assertTrue(features.DANZERO_COMPACT_STATE_ENCODING_VERSION)
        cursor = 0
        for start, end in features.DANZERO_STATE_SLICES.values():
            self.assertEqual(start, cursor)
            self.assertGreater(end, start)
            cursor = end
        self.assertEqual(cursor, features.DANZERO_COMPACT_STATE_DIM)

    def test_paper_card_order_and_ascii_equivalence(self) -> None:
        self.assertEqual(
            features.CARD_KEYS_54[:8],
            ("红桃2", "梅花2", "黑桃2", "方块2", "红桃3", "梅花3", "黑桃3", "方块3"),
        )
        self.assertEqual(features.CARD_KEYS_54[-2:], ("小王", "大王"))
        local = features.encode_cards_54(["红桃10", "梅花A", "黑桃2", "方块K", "小王", "大王"])
        website = features.encode_cards_54(["HT", "CA", "S2", "DK", "B", "R"])
        np.testing.assert_array_equal(local, website)

    def test_duplicate_counts_and_two_deck_guard(self) -> None:
        vector = features.encode_cards_54(["H7", "H7", "SA"])
        self.assertEqual(vector[features.CARD_INDEX_54["红桃7"]], 2.0)
        self.assertEqual(vector[features.CARD_INDEX_54["黑桃A"]], 1.0)
        with self.assertRaises(ValueError):
            features.encode_cards_54(["H7", "H7", "H7"])

    def test_pass_is_zero_physical_action(self) -> None:
        np.testing.assert_array_equal(features.encode_physical_action_54(["Pass"]), np.zeros(54))
        extended = features.encode_extended_action(
            ["Pass"],
            action_type="pass",
            logic_rank=0,
            active_level=7,
            was_lead=False,
        )
        self.assertEqual(extended.shape, (features.DANZERO_EXTENDED_ACTION_DIM,))
        self.assertEqual(float(extended[:54].sum()), 0.0)
        size_offset = 54 + len(features.CANONICAL_ACTION_TYPES) + features.DANZERO_ACTION_LOGIC_RANK_DIM
        self.assertEqual(extended[size_offset], 1.0)

    def test_wildcard_stays_in_physical_heart_level_slot(self) -> None:
        physical = features.encode_physical_action_54(["H7", "S6", "D8", "C9", "HT"])
        self.assertEqual(physical[features.CARD_INDEX_54["红桃7"]], 1.0)
        self.assertEqual(physical[features.CARD_INDEX_54["红桃5"]], 0.0)
        extended = features.encode_extended_action(
            ["H7", "S6", "D8", "C9", "HT"],
            action_type="straight",
            logic_rank=10,
            active_level=7,
            was_lead=True,
            wildcard_substitution_cards=["H7"],
        )
        self.assertEqual(extended.shape, (features.DANZERO_EXTENDED_ACTION_DIM,))

    def test_compact_state_layout_and_relative_seats(self) -> None:
        game = SimpleNamespace(
            players=[
                player(["H2"], ["S3"], ["S3"]),
                player(["C4", "C4"], ["D5"], ["D5"]),
                player(["S6", "S7", "S8"], [], ["Pass"]),
                player(["D9", "DT", "DJ", "DQ"], ["HK"], ["HK"]),
            ],
            ranking=[],
            last_play=["D5"],
            active_level=7,
        )
        state = features.encode_compact_state_513(game, 0, legal_candidates=[])
        website = features.encode_website_compact_state_487(game, 0, legal_candidates=[])
        self.assertEqual(state.shape, (513,))
        self.assertEqual(website.shape, (487,))
        np.testing.assert_array_equal(state[:54], features.encode_cards_54(["H2"]))
        np.testing.assert_array_equal(state[108:162], features.encode_cards_54(["D5"]))
        np.testing.assert_array_equal(state[162:216], np.zeros(54))
        self.assertEqual(int(np.argmax(state[216:244])), 2)
        self.assertEqual(int(np.argmax(state[244:272])), 3)
        self.assertEqual(int(np.argmax(state[272:300])), 4)
        np.testing.assert_array_equal(state[300:354], features.encode_cards_54(["D5"]))
        np.testing.assert_array_equal(state[354:408], features.encode_cards_54([]))
        np.testing.assert_array_equal(state[408:462], features.encode_cards_54(["HK"]))
        self.assertEqual(int(np.argmax(state[462:475])), 5)
        self.assertEqual(int(np.argmax(state[475:488])), 5)
        self.assertEqual(int(np.argmax(state[488:501])), 5)

    def test_finished_teammate_uses_negative_one_sentinel(self) -> None:
        game = SimpleNamespace(
            players=[player(["H2"]), player(["C3"]), player([]), player(["D4"])],
            ranking=[2],
            last_play=[],
            active_level=2,
        )
        state = features.encode_compact_state_513(game, 0)
        np.testing.assert_array_equal(state[162:216], np.full(54, -1.0))


if __name__ == "__main__":
    unittest.main()
