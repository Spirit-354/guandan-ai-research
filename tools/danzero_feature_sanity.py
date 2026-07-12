from __future__ import annotations

import argparse
import json
import random
import sys
import time
from collections import Counter
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import danzero_features as features
import play_research_adaptive as adaptive


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate DanZero physical action and compact state features.")
    parser.add_argument("--games", type=int, default=100)
    parser.add_argument("--seed", type=int, default=20260712)
    parser.add_argument("--out", default="danzero_feature_sanity.json")
    parser.add_argument("--report-every", type=int, default=10)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    components = adaptive.offline_load_guandan_components()
    GuandanGame = components["GuandanGame"]
    rng = random.Random(int(args.seed))
    started = time.monotonic()
    result = {
        "requested_games": int(args.games),
        "completed_games": 0,
        "attempted_games": 0,
        "total_decisions": 0,
        "total_oracle_candidates": 0,
        "physical_action_dim": features.DANZERO_PHYSICAL_ACTION_DIM,
        "extended_action_dim": features.DANZERO_EXTENDED_ACTION_DIM,
        "compact_state_dim": features.DANZERO_COMPACT_STATE_DIM,
        "website_compact_state_dim": features.DANZERO_WEBSITE_COMPACT_STATE_DIM,
        "legacy_state_dim": adaptive.OFFLINE_STATE_DIM,
        "initial_hand_count_errors": 0,
        "initial_deck_count_errors": 0,
        "compact_state_dim_errors": 0,
        "website_compact_state_dim_errors": 0,
        "legacy_state_dim_errors": 0,
        "action_feature_dim_errors": 0,
        "action_card_count_errors": 0,
        "non_finite_feature_count": 0,
        "illegal_action_count": 0,
        "fallback_count": 0,
        "materialization_fail_count": 0,
        "hand_card_mismatch_count": 0,
        "fatal_no_lead_action_count": 0,
        "first_player_distribution": {"0": 0, "1": 0, "2": 0, "3": 0},
        "action_type_distribution": {},
        "failure_samples": [],
        "threshold_passed": False,
    }
    action_types: Counter[str] = Counter()
    max_attempts = max(int(args.games) * 2, int(args.games) + 5)
    while result["completed_games"] < int(args.games) and result["attempted_games"] < max_attempts:
        game_index = int(result["attempted_games"])
        random.seed(int(args.seed) + game_index)
        game = GuandanGame(verbose=False, print_history=False)
        first_player = adaptive.offline_set_random_first_player(game, rng)
        result["first_player_distribution"][str(first_player)] += 1
        result["attempted_games"] += 1
        initial_cards = [card for player in game.players for card in player.hand]
        result["initial_hand_count_errors"] += int(any(len(player.hand) != 27 for player in game.players))
        initial_vector = features.encode_cards_54(initial_cards)
        result["initial_deck_count_errors"] += int(
            len(initial_cards) != 108 or initial_vector.shape != (54,) or not np.all(initial_vector == 2.0)
        )
        steps = 0
        while not game.is_game_over and steps < adaptive.OFFLINE_MAX_GAME_STEPS:
            adaptive.offline_prepare_turn(game)
            if game.current_player in game.ranking:
                steps += 1
                continue
            player_id = int(game.current_player)
            hand = list(game.players[player_id].hand)
            last_play = list(game.last_play or [])
            was_lead = bool(game.is_free_turn or not last_play)
            _oracle, candidates = adaptive.offline_oracle_candidates_fast(
                game,
                components,
                hand,
                last_play,
                was_lead,
            )
            if not candidates:
                if was_lead:
                    result["fatal_no_lead_action_count"] += 1
                    if len(result["failure_samples"]) < 20:
                        result["failure_samples"].append(
                            {"game_index": game_index, "step": steps, "reason": "no_lead_candidate"}
                        )
                    break
                candidates = [(0, [])]
            candidate_metadata = [
                {
                    "cards": list(cards),
                    "action_type": adaptive.dmc_sample_action_type(components, int(action_id)),
                }
                for action_id, cards in candidates
            ]
            compact = features.encode_compact_state_513(
                game,
                player_id,
                legal_candidates=candidate_metadata,
            )
            website_compact = features.encode_website_compact_state_487(
                game,
                player_id,
                legal_candidates=candidate_metadata,
            )
            legacy = game._get_obs()
            result["compact_state_dim_errors"] += int(compact.shape != (features.DANZERO_COMPACT_STATE_DIM,))
            result["website_compact_state_dim_errors"] += int(
                website_compact.shape != (features.DANZERO_WEBSITE_COMPACT_STATE_DIM,)
            )
            result["legacy_state_dim_errors"] += int(len(legacy) != adaptive.OFFLINE_STATE_DIM)
            result["non_finite_feature_count"] += int(
                not np.isfinite(compact).all() or not np.isfinite(website_compact).all()
            )

            for action_id, cards in candidates:
                action = components["action_by_id"].get(int(action_id), {})
                physical = features.encode_physical_action_54(list(cards))
                extended = features.encode_extended_action(
                    list(cards),
                    action_type=action.get("type") if action_id else "pass",
                    logic_rank=int(action.get("logic_point") or 0),
                    active_level=int(game.active_level),
                    was_lead=was_lead,
                )
                result["action_feature_dim_errors"] += int(
                    physical.shape != (features.DANZERO_PHYSICAL_ACTION_DIM,)
                    or extended.shape != (features.DANZERO_EXTENDED_ACTION_DIM,)
                )
                result["action_card_count_errors"] += int(float(physical.sum()) != float(len(cards)))
                result["non_finite_feature_count"] += int(
                    not np.isfinite(physical).all() or not np.isfinite(extended).all()
                )
            selected_action_id, selected_cards = rng.choice(candidates)
            action_types[adaptive.dmc_sample_action_type(components, int(selected_action_id))] += 1
            action_info = adaptive.offline_make_action_info_from_cards(
                game,
                components,
                list(selected_cards),
                rng,
                policy="danzero_feature_sanity",
                sampled_action_id=int(selected_action_id),
                audit_masks=False,
            )
            record = adaptive.offline_apply_action(game, action_info)
            result["illegal_action_count"] += int(bool(record.get("illegal")))
            result["fallback_count"] += int(bool(record.get("fallback")))
            result["materialization_fail_count"] += int(bool(record.get("materialization_fail")))
            result["hand_card_mismatch_count"] += int(bool(record.get("hand_card_mismatch")))
            result["total_decisions"] += 1
            result["total_oracle_candidates"] += len(candidates)
            steps += 1
        if game.is_game_over:
            result["completed_games"] += 1
        if int(args.report_every) > 0 and result["completed_games"] % int(args.report_every) == 0:
            print(
                f"feature_sanity_progress completed={result['completed_games']}/{args.games} "
                f"attempted={result['attempted_games']} decisions={result['total_decisions']}",
                flush=True,
            )
    result["action_type_distribution"] = dict(action_types)
    result["elapsed_seconds"] = time.monotonic() - started
    failure_counters = (
        "initial_hand_count_errors",
        "initial_deck_count_errors",
        "compact_state_dim_errors",
        "website_compact_state_dim_errors",
        "legacy_state_dim_errors",
        "action_feature_dim_errors",
        "action_card_count_errors",
        "non_finite_feature_count",
        "illegal_action_count",
        "fallback_count",
        "materialization_fail_count",
        "hand_card_mismatch_count",
        "fatal_no_lead_action_count",
    )
    result["threshold_passed"] = bool(
        result["completed_games"] >= int(args.games)
        and all(int(result[name]) == 0 for name in failure_counters)
    )
    Path(args.out).write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if not result["threshold_passed"]:
        raise RuntimeError("DanZero feature sanity threshold failed")


if __name__ == "__main__":
    main()
