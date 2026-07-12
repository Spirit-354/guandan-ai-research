from __future__ import annotations

import argparse
import json
import random
import sys
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import danzero_oracle
import play_research_adaptive as adaptive


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compare bounded and exhaustive DanZero physical oracles.")
    parser.add_argument("--states", type=int, default=3)
    parser.add_argument("--seed", type=int, default=20260712)
    parser.add_argument("--out", default="danzero_oracle_audit.json")
    parser.add_argument("--new-game-every", type=int, default=0)
    parser.add_argument("--cycle-levels", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    components = adaptive.offline_load_guandan_components()
    GuandanGame = components["GuandanGame"]
    rng = random.Random(int(args.seed))
    random.seed(int(args.seed))
    game = GuandanGame(active_level=2 if args.cycle_levels else None, verbose=False, print_history=False)
    adaptive.offline_set_random_first_player(game, rng)
    result = {
        "requested_states": int(args.states),
        "evaluated_states": 0,
        "bounded_oracle_version": danzero_oracle.ORACLE_VERSION,
        "exhaustive_oracle_version": "exhaustive_engine_oracle_audit_v1",
        "bounded_candidate_count": 0,
        "exhaustive_candidate_count": 0,
        "structured_candidate_count": 0,
        "bounded_missing_count": 0,
        "bounded_extra_count": 0,
        "mapping_fail_count": 0,
        "structured_mapping_fail_count": 0,
        "average_bounded_recall": 0.0,
        "average_structured_recall": 0.0,
        "bounded_seconds": 0.0,
        "exhaustive_seconds": 0.0,
        "structured_seconds": 0.0,
        "states": [],
        "level_distribution": {},
        "threshold_passed": False,
    }
    recalls: list[float] = []
    structured_recalls: list[float] = []
    level_distribution: dict[str, int] = {}
    while result["evaluated_states"] < int(args.states):
        if game.is_game_over or (
            int(args.new_game_every) > 0
            and result["evaluated_states"] > 0
            and result["evaluated_states"] % int(args.new_game_every) == 0
        ):
            random.seed(int(args.seed) + result["evaluated_states"] * 1009)
            active_level = 2 + (result["evaluated_states"] % 13) if args.cycle_levels else None
            game = GuandanGame(active_level=active_level, verbose=False, print_history=False)
            adaptive.offline_set_random_first_player(game, rng)
        adaptive.offline_prepare_turn(game)
        if game.current_player in game.ranking:
            continue
        player_id = int(game.current_player)
        level_distribution[str(game.active_level)] = level_distribution.get(str(game.active_level), 0) + 1
        hand = list(game.players[player_id].hand)
        last_play = list(game.last_play or [])
        was_lead = bool(game.is_free_turn or not last_play)
        started = time.perf_counter()
        bounded = danzero_oracle.bounded_candidates(adaptive, game, components, hand, last_play, was_lead)
        bounded_seconds = time.perf_counter() - started
        started = time.perf_counter()
        exhaustive, meta = danzero_oracle.exhaustive_candidates(
            adaptive, game, components, hand, last_play, was_lead
        )
        exhaustive_seconds = time.perf_counter() - started
        started = time.perf_counter()
        structured, structured_meta = danzero_oracle.structured_exhaustive_candidates(
            adaptive, game, components, hand, last_play, was_lead
        )
        structured_seconds = time.perf_counter() - started
        bounded_keys = {danzero_oracle.physical_key(cards) for _action_id, cards in bounded}
        exhaustive_keys = {danzero_oracle.physical_key(cards) for _action_id, cards in exhaustive}
        structured_keys = {danzero_oracle.physical_key(cards) for _action_id, cards in structured}
        missing = exhaustive_keys - bounded_keys
        extra = bounded_keys - exhaustive_keys
        recall = len(bounded_keys & exhaustive_keys) / max(1, len(exhaustive_keys))
        structured_recall = len(structured_keys & exhaustive_keys) / max(1, len(exhaustive_keys))
        recalls.append(recall)
        structured_recalls.append(structured_recall)
        result["bounded_candidate_count"] += len(bounded_keys)
        result["exhaustive_candidate_count"] += len(exhaustive_keys)
        result["structured_candidate_count"] += len(structured_keys)
        result["bounded_missing_count"] += len(missing)
        result["bounded_extra_count"] += len(extra)
        result["mapping_fail_count"] += int(meta["mapping_fail_count"])
        result["structured_mapping_fail_count"] += int(structured_meta["mapping_fail_count"])
        result["bounded_seconds"] += bounded_seconds
        result["exhaustive_seconds"] += exhaustive_seconds
        result["structured_seconds"] += structured_seconds
        result["states"].append(
            {
                "state_index": result["evaluated_states"],
                "player_id": player_id,
                "level": int(game.active_level),
                "hand_count": len(hand),
                "last_play": last_play,
                "was_lead": was_lead,
                "bounded_candidate_count": len(bounded_keys),
                "exhaustive_candidate_count": len(exhaustive_keys),
                "structured_candidate_count": len(structured_keys),
                "bounded_missing_count": len(missing),
                "bounded_extra_count": len(extra),
                "bounded_recall": recall,
                "structured_recall": structured_recall,
                "structured_missing_count": len(exhaustive_keys - structured_keys),
                "structured_extra_count": len(structured_keys - exhaustive_keys),
                "bounded_seconds": bounded_seconds,
                "exhaustive_seconds": exhaustive_seconds,
                "structured_seconds": structured_seconds,
                "mapping_fail_count": meta["mapping_fail_count"],
                "structured_mapping_fail_count": structured_meta["mapping_fail_count"],
                "missing_examples": [list(key) for key in list(sorted(missing))[:20]],
                "extra_examples": [list(key) for key in list(sorted(extra))[:20]],
                "structured_missing_examples": [
                    list(key) for key in list(sorted(exhaustive_keys - structured_keys))[:20]
                ],
                "structured_extra_examples": [
                    list(key) for key in list(sorted(structured_keys - exhaustive_keys))[:20]
                ],
            }
        )
        result["evaluated_states"] += 1
        selected_action_id, selected_cards = rng.choice(bounded)
        action_info = adaptive.offline_make_action_info_from_cards(
            game,
            components,
            selected_cards,
            rng,
            policy="danzero_oracle_audit",
            sampled_action_id=selected_action_id,
            audit_masks=False,
        )
        adaptive.offline_apply_action(game, action_info)
    result["average_bounded_recall"] = sum(recalls) / max(1, len(recalls))
    result["average_structured_recall"] = sum(structured_recalls) / max(1, len(structured_recalls))
    result["level_distribution"] = level_distribution
    result["threshold_passed"] = bool(
        result["evaluated_states"] == int(args.states)
        and result["mapping_fail_count"] == 0
        and result["structured_mapping_fail_count"] == 0
        and result["bounded_extra_count"] == 0
        and result["structured_candidate_count"] == result["exhaustive_candidate_count"]
        and result["average_structured_recall"] == 1.0
    )
    Path(args.out).write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if not result["threshold_passed"]:
        raise RuntimeError("DanZero oracle audit found mapping failures or invalid bounded candidates")


if __name__ == "__main__":
    main()
