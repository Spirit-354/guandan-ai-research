from __future__ import annotations

from collections import Counter
import hashlib
import json
from pathlib import Path
import random
from typing import Any
import statistics
import time

import numpy as np

import danzero_features as features
import website_danzero_dataset as website_data


INFORMATION_SET_SCHEMA_VERSION = "website_information_set_v1"


def _integer_counts(values: list[float], name: str) -> np.ndarray:
    array = np.asarray(values, dtype=np.float32)
    rounded = np.rint(array)
    if not np.allclose(array, rounded, atol=1e-6):
        raise ValueError(f"{name} contains fractional card counts")
    if np.any(rounded < 0) or np.any(rounded > 2):
        raise ValueError(f"{name} contains out-of-range card counts")
    return rounded.astype(np.int16)


def _cards_from_counts(counts: np.ndarray) -> list[str]:
    cards: list[str] = []
    for index, count in enumerate(counts.tolist()):
        cards.extend([features.CARD_KEYS_54[index]] * int(count))
    return cards


def decode_public_card_state(sample: dict) -> dict:
    state = list(sample.get("state") or [])
    if len(state) != features.DANZERO_COMPACT_STATE_DIM:
        raise ValueError("information-set sample state dimension is not 513")
    your_seat = int(sample.get("your_seat", 0))
    hand_counts = [int(value) for value in (sample.get("hand_counts") or [])]
    if len(hand_counts) != 4 or not 0 <= your_seat < 4:
        raise ValueError("information-set sample lacks four hand counts or valid seat")
    self_hand = _integer_counts(state[0:54], "self_hand")
    unknown_remaining = _integer_counts(state[54:108], "unknown_remaining")
    other_seats = [(your_seat + offset) % 4 for offset in (1, 2, 3)]
    played_by_seat = [np.zeros(54, dtype=np.int16) for _ in range(4)]
    for index, seat in enumerate(other_seats):
        start = 300 + index * 54
        played_by_seat[seat] = _integer_counts(state[start : start + 54], f"played_seat_{seat}")
    all_played = np.full(54, 2, dtype=np.int16) - self_hand - unknown_remaining
    self_played = all_played - sum((played_by_seat[seat] for seat in other_seats), np.zeros(54, dtype=np.int16))
    if np.any(self_played < 0) or np.any(self_played > 2):
        raise ValueError("decoded self played cards are inconsistent")
    played_by_seat[your_seat] = self_played
    if int(unknown_remaining.sum()) != sum(hand_counts) - hand_counts[your_seat]:
        raise ValueError("unknown pool size does not match opponent and teammate hand counts")
    if int(self_hand.sum()) != hand_counts[your_seat]:
        raise ValueError("encoded self hand does not match hand count")
    return {
        "your_seat": your_seat,
        "hand_counts": hand_counts,
        "self_hand_counts": self_hand,
        "unknown_remaining_counts": unknown_remaining,
        "played_by_seat_counts": played_by_seat,
        "teammate_last_counts": _integer_counts(state[162:216], "teammate_last"),
    }


def sample_determinization(sample: dict, rng: random.Random) -> dict:
    decoded = decode_public_card_state(sample)
    your_seat = decoded["your_seat"]
    hidden_pool = _cards_from_counts(decoded["unknown_remaining_counts"])
    rng.shuffle(hidden_pool)
    hands: list[list[str]] = [[] for _ in range(4)]
    hands[your_seat] = _cards_from_counts(decoded["self_hand_counts"])
    offset = 0
    for seat in range(4):
        if seat == your_seat:
            continue
        count = decoded["hand_counts"][seat]
        hands[seat] = hidden_pool[offset : offset + count]
        offset += count
    if offset != len(hidden_pool):
        raise ValueError("determinization did not consume the full hidden pool")
    return {
        **decoded,
        "hands": hands,
        "played_by_seat": [
            _cards_from_counts(counts) for counts in decoded["played_by_seat_counts"]
        ],
        "hidden_card_sampling_method": "uniform_physical_assignment_given_public_counts_v1",
    }


def _level_int(level: str) -> int:
    ranks = ("2", "3", "4", "5", "6", "7", "8", "9", "T", "J", "Q", "K", "A")
    return ranks.index(str(level).upper()) + 2


def _inferred_pass_count(last_player: int, current_player: int, hand_counts: list[int]) -> int:
    count = 0
    seat = (int(last_player) + 1) % 4
    while seat != int(current_player):
        if hand_counts[seat] > 0:
            count += 1
        seat = (seat + 1) % 4
    return count


def restore_game(sample: dict, components: dict, rng: random.Random) -> Any:
    determinization = sample_determinization(sample, rng)
    game = components["GuandanGame"](
        active_level=_level_int(str(sample.get("level"))),
        verbose=False,
        print_history=False,
    )
    for seat, player in enumerate(game.players):
        player.hand = game.sort_cards(list(determinization["hands"][seat]))
        player.played_cards = list(determinization["played_by_seat"][seat])
        player.last_played_cards = []
    your_seat = int(determinization["your_seat"])
    teammate = (your_seat + 2) % 4
    game.players[teammate].last_played_cards = _cards_from_counts(
        determinization["teammate_last_counts"]
    )
    last_play = [
        features.canonical_local_card(card)
        for card in (sample.get("last_play_before_action") or [])
    ]
    current_player = int(sample.get("current_turn", your_seat))
    if current_player != your_seat:
        raise ValueError("website decision sample is not the acting player's turn")
    game.current_player = current_player
    game.last_play = last_play or None
    game.last_player = int(sample.get("last_player")) if last_play else -1
    game.pass_count = (
        _inferred_pass_count(game.last_player, current_player, determinization["hand_counts"])
        if last_play
        else 0
    )
    game.ranking = []
    game.is_free_turn = not bool(last_play)
    game.jiefeng = False
    game.is_game_over = False
    game.winning_team = 0
    game.recent_actions = [["None"], ["None"], ["None"], ["None"]]
    game.history = []
    return game


def _candidate_metadata(sample: dict) -> list[dict]:
    return [
        {
            "cards": list(item.get("cards") or []),
            "action_type": item.get("action_type"),
        }
        for item in sample.get("legal_action_metadata") or []
    ]


def run_sanity(args: Any, components: dict) -> dict:
    samples, dataset_summary = website_data.load_dataset(Path(args.website_information_set_sanity))
    if dataset_summary.get("partition_role") != "train_development":
        raise RuntimeError("information-set sanity requires the frozen train_dev partition")
    if any(sample.get("split") == "locked_test" for sample in samples):
        raise RuntimeError("information-set sanity refuses locked-test samples")
    prefilter = [
        sample
        for sample in samples
        if sample.get("split") == "train" and all(int(value) > 0 for value in sample.get("hand_counts") or [])
    ]
    eligible = [sample for sample in prefilter if sample.get("information_set_consistent")][
        : int(args.information_set_sanity_samples)
    ]
    counters = Counter()
    max_state_error = 0.0
    failure_samples: list[dict] = []
    for sample_index, sample in enumerate(eligible):
        for determinization_index in range(int(args.information_set_determinizations)):
            rng = random.Random(20260713 + sample_index * 1009 + determinization_index)
            try:
                game = restore_game(sample, components, rng)
                integrity_cards: list[str] = []
                for player in game.players:
                    integrity_cards.extend(player.hand)
                    integrity_cards.extend(player.played_cards)
                counts = Counter(integrity_cards)
                if len(integrity_cards) != 108 or any(count != 2 for count in counts.values()):
                    raise ValueError("restored game does not preserve the two-deck 108-card invariant")
                encoded = features.encode_compact_state_513(
                    game,
                    int(sample.get("your_seat", 0)),
                    legal_candidates=_candidate_metadata(sample),
                )
                expected = np.asarray(sample["state"], dtype=np.float32)
                error = float(np.max(np.abs(encoded - expected)))
                max_state_error = max(max_state_error, error)
                if error > 1e-6:
                    raise ValueError(f"re-encoded state differs by {error}")
                counters["successful_determinizations"] += 1
            except Exception as exc:
                counters["failed_determinizations"] += 1
                if len(failure_samples) < 20:
                    failure_samples.append(
                        {
                            "game_id": sample.get("game_id"),
                            "turn_index": sample.get("turn_index"),
                            "determinization_index": determinization_index,
                            "error": f"{type(exc).__name__}: {exc}",
                        }
                    )
    result = {
        "schema_version": INFORMATION_SET_SCHEMA_VERSION,
        "dataset_path": str(args.website_information_set_sanity),
        "dataset_split_status": dataset_summary.get("split_status"),
        "locked_test_loaded": False,
        "evaluated_samples": len(eligible),
        "prefilter_train_samples": len(prefilter),
        "excluded_inconsistent_information_set_samples": sum(
            not bool(sample.get("information_set_consistent")) for sample in prefilter
        ),
        "determinizations_per_sample": int(args.information_set_determinizations),
        "successful_determinizations": counters["successful_determinizations"],
        "failed_determinizations": counters["failed_determinizations"],
        "max_state_reencode_error": max_state_error,
        "hidden_card_sampling_method": "uniform_physical_assignment_given_public_counts_v1",
        "future_information_used": False,
        "opponent_or_teammate_true_hands_used": False,
        "failure_samples": failure_samples,
        "threshold_passed": bool(eligible and counters["failed_determinizations"] == 0),
    }
    Path(args.information_set_sanity_out).write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if not result["threshold_passed"]:
        raise RuntimeError("website information-set sanity gate failed")
    return result


def _candidate_key(cards: list[str]) -> tuple[tuple[str, int], ...]:
    return tuple(sorted(Counter(cards).items()))


def _rollout_candidates(sample: dict, game: Any, components: dict, adaptive: Any, limit: int) -> list[dict]:
    behavior_key = _candidate_key(list(sample.get("chosen_cards") or []))
    candidates: list[dict] = []
    seen: set[tuple[tuple[str, int], ...]] = set()
    for metadata in sample.get("legal_action_metadata") or []:
        website_cards = list(metadata.get("cards") or [])
        key = _candidate_key(website_cards)
        if key in seen:
            continue
        local_cards = adaptive.website_cards_to_local(website_cards)
        info = adaptive.offline_make_action_info_from_cards(
            game,
            components,
            local_cards,
            random.Random(0),
            policy="information_set_candidate",
            audit_masks=False,
        )
        if info.get("illegal") or info.get("materialization_fail") or info.get("hand_card_mismatch"):
            continue
        seen.add(key)
        candidates.append(
            {
                "action_id": int(info.get("action_id") or 0),
                "physical_cards": list(info.get("chosen_cards") or []),
                "physical_cards_website": website_cards,
                "action_type": str(info.get("action_type") or metadata.get("action_type") or "unknown"),
                "is_bomb": bool(info.get("is_bomb")),
                "is_behavior_action": key == behavior_key,
            }
        )
    candidates.sort(
        key=lambda item: (
            not item["is_behavior_action"],
            item["is_bomb"],
            len(item["physical_cards"]),
            int(item["action_id"]),
        )
    )
    behavior = [item for item in candidates if item["is_behavior_action"]]
    others = [item for item in candidates if not item["is_behavior_action"]]
    selected: list[dict] = []

    def select(item: dict | None) -> None:
        if item is not None and item not in selected and len(selected) < int(limit):
            selected.append(item)

    select(behavior[0] if behavior else None)
    if others:
        select(others[0])
    non_pass = [item for item in others if item["physical_cards"]]
    if non_pass:
        select(max(non_pass, key=lambda item: len(item["physical_cards"])))
    bombs = [item for item in others if item["is_bomb"]]
    if bombs:
        select(min(bombs, key=lambda item: (len(item["physical_cards"]), item["action_id"])))
    for item in others:
        if len(selected) >= int(limit):
            break
        select(item)
    return selected[: int(limit)]


def _observable_risk_score(sample: dict) -> float:
    hand_counts = [int(value) for value in (sample.get("hand_counts") or [27, 27, 27, 27])]
    your_seat = int(sample.get("your_seat", 0))
    opponents = [(your_seat + 1) % 4, (your_seat + 3) % 4]
    opponent_min = min(hand_counts[seat] for seat in opponents)
    behavior_is_pass = not bool(sample.get("chosen_cards") or [])
    non_pass_available = any(bool(item.get("cards")) for item in sample.get("legal_action_metadata") or [])
    score = 0.0
    score += max(0, 8 - opponent_min) * 2.0
    score += 8.0 if sample.get("was_follow") and behavior_is_pass and non_pass_available else 0.0
    score += 4.0 if "endgame" in str(sample.get("scenario") or "").lower() else 0.0
    score += 2.0 if int(sample.get("legal_action_count") or 0) > 1 else 0.0
    score += 1.0 if sample.get("bomb_candidate_available") else 0.0
    return score


def _stratified_train_samples(
    samples: list[dict],
    limit: int,
    *,
    risk_priority: bool = False,
    case_keys: set[tuple[str, str]] | None = None,
) -> list[dict]:
    eligible = [
        sample
        for sample in samples
        if sample.get("split") == "train"
        and sample.get("information_set_consistent")
        and all(int(value) > 0 for value in sample.get("hand_counts") or [])
    ]
    if case_keys:
        return [
            sample
            for sample in eligible
            if (str(sample.get("game_id")), str(sample.get("turn_index"))) in case_keys
        ][: int(limit)]
    by_game: dict[str, list[dict]] = {}
    for sample in eligible:
        by_game.setdefault(str(sample.get("game_id")), []).append(sample)
    rng = random.Random(20260713)
    for game_samples in by_game.values():
        if risk_priority:
            game_samples.sort(key=lambda sample: (-_observable_risk_score(sample), int(sample.get("turn_index") or 0)))
        else:
            rng.shuffle(game_samples)
    game_ids = sorted(by_game)
    if risk_priority:
        game_ids.sort(key=lambda game_id: -max(_observable_risk_score(sample) for sample in by_game[game_id]))
    else:
        rng.shuffle(game_ids)
    selected: list[dict] = []
    depth = 0
    while len(selected) < int(limit):
        added = False
        for game_id in game_ids:
            game_samples = by_game[game_id]
            if depth < len(game_samples):
                selected.append(game_samples[depth])
                added = True
                if len(selected) >= int(limit):
                    break
        if not added:
            break
        depth += 1
    return selected


def _baseline_visible_state_key(game: Any, adaptive: Any) -> str:
    player_id = int(game.current_player)
    state = adaptive.offline_arena_state_for_player(game, player_id)
    return _baseline_visible_state_key_from_state(state)


def _baseline_visible_state_key_from_state(state: dict) -> str:
    return json.dumps(state, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _cached_baseline_action_info(
    game: Any,
    components: dict,
    adaptive: Any,
    profile_config: dict,
    rng: random.Random,
    cache: dict[str, list[str]] | None,
    stats: dict[str, Any],
) -> dict:
    state = adaptive.offline_arena_state_for_player(game, int(game.current_player))
    key = _baseline_visible_state_key_from_state(state) if cache is not None else None
    started = time.monotonic()
    if key is not None and key in cache:
        stats["hits"] = stats.get("hits", 0.0) + 1.0
        info = adaptive.offline_make_action_info_from_cards(
            game,
            components,
            list(cache[key]),
            rng,
            policy="information_set_tempo_cached",
            audit_masks=False,
        )
        stats["hit_seconds"] = stats.get("hit_seconds", 0.0) + (time.monotonic() - started)
        return info
    info = adaptive.offline_baseline_action_info(
        game,
        components,
        "tempo_baseline",
        profile_config,
        rng,
    )
    elapsed = time.monotonic() - started
    stats["misses"] = stats.get("misses", 0.0) + 1.0
    stats["miss_seconds"] = stats.get("miss_seconds", 0.0) + elapsed
    stats["max_miss_seconds"] = max(stats.get("max_miss_seconds", 0.0), elapsed)
    slow_samples = stats.setdefault("slow_samples", [])
    slow_samples.append(
        {
            "seconds": elapsed,
            "current_player": int(game.current_player),
            "hand_count": len(state.get("your_hand") or []),
            "last_play_size": len(state.get("last_play") or []),
            "hand_counts": list(state.get("hand_counts") or []),
            "ranking": list(state.get("ranking") or []),
            "trick_history_count": len(state.get("trick_history") or []),
            "state": state,
        }
    )
    slow_samples.sort(key=lambda item: float(item["seconds"]), reverse=True)
    del slow_samples[5:]
    if key is not None and not info.get("illegal"):
        cache[key] = list(info.get("chosen_cards") or [])
    return info


def _simulate_candidate(
    base_game: Any,
    candidate: dict,
    components: dict,
    adaptive: Any,
    seed: int,
    max_steps: int,
    continuation_profile: str,
    profile_config: dict,
    deadline_monotonic: float | None = None,
    baseline_cache: dict[str, list[str]] | None = None,
    baseline_stats: dict[str, Any] | None = None,
) -> tuple[float | None, dict | None]:
    import copy

    rng = random.Random(seed)
    game = copy.deepcopy(base_game)
    acting_player = int(game.current_player)
    team_id = adaptive.offline_team_id(acting_player)
    action = adaptive.offline_make_action_info_from_cards(
        game,
        components,
        list(candidate.get("physical_cards") or []),
        rng,
        policy="information_set_counterfactual",
        sampled_action_id=int(candidate.get("action_id") or 0),
        audit_masks=False,
    )
    if action.get("illegal") or action.get("materialization_fail") or action.get("hand_card_mismatch"):
        return None, {"reason": "candidate_apply_invalid"}
    record = adaptive.offline_apply_action(game, action)
    if record.get("materialization_fail") or record.get("hand_card_mismatch"):
        return None, {"reason": "candidate_apply_failed"}
    steps = 0
    while not game.is_game_over and steps < int(max_steps):
        if deadline_monotonic is not None and time.monotonic() >= deadline_monotonic:
            return None, {"reason": "case_time_budget_exhausted", "steps": steps}
        adaptive.offline_prepare_turn(game)
        if game.current_player in game.ranking:
            steps += 1
            continue
        if continuation_profile == "tempo_baseline":
            next_action = _cached_baseline_action_info(
                game,
                components,
                adaptive,
                profile_config,
                rng,
                baseline_cache,
                baseline_stats if baseline_stats is not None else {},
            )
        elif continuation_profile == "random_bot":
            next_action = adaptive.offline_oracle_sample_action_info(
                game, components, rng, policy="information_set_random_bot"
            )
        else:
            next_action = adaptive.rollout_greedy_action_info(
                game, components, rng, policy="information_set_greedy_bot"
            )
        record = adaptive.offline_apply_action(game, next_action)
        if record.get("materialization_fail") or record.get("hand_card_mismatch"):
            return None, {"reason": "continuation_action_failed", "step": steps}
        steps += 1
    if not game.is_game_over:
        return None, {"reason": "rollout_depth_exhausted", "steps": steps}
    winner_team = adaptive.offline_winner_team_id(game)
    if winner_team is None:
        return None, {"reason": "winner_team_unavailable"}
    return (1.0 if int(winner_team) == int(team_id) else -1.0), None


def _sample_variance(values: list[float]) -> float:
    return float(statistics.variance(values)) if len(values) >= 2 else 0.0


def _stable_determinization_seed(sample: dict, determinization_index: int) -> int:
    case_key = f"{sample.get('game_id')}:{sample.get('turn_index')}:{int(determinization_index)}"
    digest = hashlib.sha256(case_key.encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big")


def _strong_teacher_label(
    *,
    case_complete: bool,
    paired_count: int,
    requested_count: int,
    advantage: float,
    candidate_return_variance: float,
    lower_bound: float,
    robust_across_profiles: bool,
    min_advantage: float,
    max_return_variance: float,
) -> bool:
    return bool(
        case_complete
        and paired_count == requested_count
        and advantage >= min_advantage
        and candidate_return_variance <= max_return_variance
        and lower_bound > 0.0
        and robust_across_profiles
    )


def run_baseline_cache_equivalence(args: Any, components: dict, adaptive: Any) -> dict:
    import copy

    sample_target = max(200, int(args.information_set_cache_equivalence_samples))
    profile_config = adaptive.load_json(adaptive.PROFILE_PATH, {}).get(
        "tempo_baseline", {"engine_mode": "tempo"}
    )
    rng = random.Random(20260713)
    samples = 0
    game_index = 0
    unique_keys: set[str] = set()
    mismatches: list[dict] = []
    mismatch_count = 0
    cache_stats: dict[str, float] = {}
    GuandanGame = components["GuandanGame"]
    while samples < sample_target and game_index < sample_target * 2:
        random.seed(20260713 + game_index)
        game = GuandanGame(verbose=False, print_history=False)
        adaptive.offline_set_random_first_player(game, rng)
        steps = 0
        while not game.is_game_over and steps < adaptive.OFFLINE_MAX_GAME_STEPS and samples < sample_target:
            adaptive.offline_prepare_turn(game)
            if game.current_player in game.ranking:
                steps += 1
                continue
            snapshot = copy.deepcopy(game)
            direct = adaptive.offline_baseline_action_info(
                snapshot,
                components,
                "tempo_baseline",
                profile_config,
                rng,
            )
            key = _baseline_visible_state_key(snapshot, adaptive)
            unique_keys.add(key)
            cache = {key: list(direct.get("chosen_cards") or [])}
            cached = _cached_baseline_action_info(
                snapshot,
                components,
                adaptive,
                profile_config,
                rng,
                cache,
                cache_stats,
            )
            direct_cards = tuple(sorted(direct.get("chosen_cards") or []))
            cached_cards = tuple(sorted(cached.get("chosen_cards") or []))
            if (
                direct_cards != cached_cards
                or str(direct.get("action_type")) != str(cached.get("action_type"))
                or bool(direct_cards) != bool(cached_cards)
                or bool(cached.get("illegal"))
            ):
                mismatch_count += 1
                if len(mismatches) < 20:
                    mismatches.append(
                        {
                            "sample_index": samples,
                            "player_id": int(snapshot.current_player),
                            "direct_cards": list(direct_cards),
                            "cached_cards": list(cached_cards),
                            "direct_action_type": direct.get("action_type"),
                            "cached_action_type": cached.get("action_type"),
                            "cached_illegal": bool(cached.get("illegal")),
                        }
                    )
            samples += 1
            advance = adaptive.offline_first_oracle_action_info(
                game,
                components,
                rng,
                policy="information_set_cache_equivalence_sampler",
                fallback_reason="information_set_cache_equivalence_sampler",
            )
            adaptive.offline_apply_action(game, advance)
            steps += 1
        game_index += 1
    result = {
        "schema_version": "website_information_set_baseline_cache_equivalence_v1",
        "baseline_equivalence_checked": True,
        "baseline_equivalence_samples": samples,
        "baseline_equivalence_unique_state_keys": len(unique_keys),
        "baseline_equivalence_mismatch_count": mismatch_count,
        "baseline_equivalence_mismatches": mismatches,
        "cache_key_source": "complete_offline_arena_state_for_player_json_v1",
        "cache_hit_count": int(cache_stats.get("hits", 0.0)),
        "threshold_passed": bool(samples >= sample_target and mismatch_count == 0),
    }
    Path(args.information_set_cache_equivalence_out).write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if not result["threshold_passed"]:
        raise RuntimeError("information-set baseline cache equivalence failed")
    return result


def run_rollout_eval(args: Any, components: dict, adaptive: Any) -> dict:
    samples, dataset_summary = website_data.load_dataset(Path(args.website_information_set_rollout_eval))
    if dataset_summary.get("partition_role") != "train_development":
        raise RuntimeError("information-set rollout requires the frozen train_dev partition")
    if any(sample.get("split") == "locked_test" for sample in samples):
        raise RuntimeError("information-set rollout refuses locked-test samples")
    case_keys = {
        tuple(item.split(":", 1))
        for item in str(args.information_set_case_keys or "").split(",")
        if ":" in item
    }
    eligible = _stratified_train_samples(
        samples,
        int(args.information_set_rollout_samples),
        risk_priority=bool(args.information_set_risk_priority),
        case_keys=case_keys or None,
    )
    case_results: list[dict] = []
    strong_labels: list[dict] = []
    integrity_failures: list[dict] = []
    continuation_profiles = [
        item.strip()
        for item in str(args.information_set_continuation_profiles).split(",")
        if item.strip()
    ]
    allowed_profiles = {"greedy_bot", "tempo_baseline", "random_bot"}
    if not continuation_profiles or any(item not in allowed_profiles for item in continuation_profiles):
        raise RuntimeError("information-set continuation profiles must be greedy_bot, tempo_baseline, or random_bot")
    profile_config = adaptive.load_json(adaptive.PROFILE_PATH, {}).get(
        "tempo_baseline", {"engine_mode": "tempo"}
    )
    profile_rollout_counts = Counter()
    baseline_cache: dict[str, list[str]] | None = (
        {} if bool(args.information_set_cache_baseline_actions) else None
    )
    baseline_stats: dict[str, Any] = {}
    total_rollouts = 0
    completed_rollouts = 0
    timeout_case_count = 0
    for sample in eligible:
        case_started = time.monotonic()
        case_timed_out = False
        case_deadline = (
            case_started + float(args.information_set_max_seconds_per_case)
            if float(args.information_set_max_seconds_per_case) > 0.0
            else None
        )
        base_rng = random.Random(_stable_determinization_seed(sample, -1))
        candidate_game = restore_game(sample, components, base_rng)
        candidates = _rollout_candidates(
            sample,
            candidate_game,
            components,
            adaptive,
            int(args.information_set_rollout_candidates),
        )
        returns: list[list[float]] = [[] for _ in candidates]
        paired_returns: list[list[float | None]] = [[] for _ in candidates]
        failures: list[list[dict]] = [[] for _ in candidates]
        for rollout_index in range(int(args.information_set_rollouts_per_action)):
            if (
                float(args.information_set_max_seconds_per_case) > 0.0
                and time.monotonic() - case_started >= float(args.information_set_max_seconds_per_case)
            ):
                case_timed_out = True
                break
            continuation_profile = continuation_profiles[rollout_index % len(continuation_profiles)]
            determinization_index = rollout_index // len(continuation_profiles)
            determinization_seed = _stable_determinization_seed(sample, determinization_index)
            profile_rollout_counts[continuation_profile] += len(candidates)
            base_game = restore_game(sample, components, random.Random(determinization_seed))
            for candidate_index, candidate in enumerate(candidates):
                total_rollouts += 1
                if case_deadline is not None and time.monotonic() >= case_deadline:
                    value, failure = None, {"reason": "case_time_budget_exhausted", "steps": 0}
                else:
                    value, failure = _simulate_candidate(
                        base_game,
                        candidate,
                        components,
                        adaptive,
                        determinization_seed,
                        int(args.information_set_rollout_max_steps),
                        continuation_profile,
                        profile_config,
                        case_deadline,
                        baseline_cache,
                        baseline_stats,
                    )
                paired_returns[candidate_index].append(value)
                if value is not None:
                    returns[candidate_index].append(float(value))
                    completed_rollouts += 1
                elif failure and len(failures[candidate_index]) < 5:
                    failures[candidate_index].append(failure)
                if failure and failure.get("reason") == "case_time_budget_exhausted":
                    case_timed_out = True
        if case_timed_out:
            timeout_case_count += 1
        candidate_results: list[dict] = []
        for candidate, values in zip(candidates, returns):
            candidate_results.append(
                {
                    **candidate,
                    "rollout_count": len(values),
                    "mean_return": sum(values) / len(values) if values else None,
                    "return_variance": _sample_variance(values),
                    "completion_rate": len(values) / int(args.information_set_rollouts_per_action),
                }
            )
        valid_indices = [
            index for index, result in enumerate(candidate_results) if result["mean_return"] is not None
        ]
        behavior_index = next(
            (index for index, result in enumerate(candidate_results) if result["is_behavior_action"]), None
        )
        best_index = max(valid_indices, key=lambda index: candidate_results[index]["mean_return"]) if valid_indices else None
        label = None
        if behavior_index is not None and best_index is not None and best_index != behavior_index:
            paired_differences = [
                float(best) - float(behavior)
                for best, behavior in zip(paired_returns[best_index], paired_returns[behavior_index])
                if best is not None and behavior is not None
            ]
            advantage = sum(paired_differences) / len(paired_differences) if paired_differences else 0.0
            variance = _sample_variance(paired_differences)
            standard_error = (variance / len(paired_differences)) ** 0.5 if paired_differences else float("inf")
            lower_bound = advantage - 1.96 * standard_error
            confidence = max(0.0, min(1.0, 0.5 + lower_bound / 2.0))
            policy_advantages: dict[str, dict] = {}
            for profile in continuation_profiles:
                paired_length = min(
                    len(paired_returns[best_index]),
                    len(paired_returns[behavior_index]),
                )
                differences = [
                    float(paired_returns[best_index][rollout_index])
                    - float(paired_returns[behavior_index][rollout_index])
                    for rollout_index in range(paired_length)
                    if continuation_profiles[rollout_index % len(continuation_profiles)] == profile
                    and paired_returns[best_index][rollout_index] is not None
                    and paired_returns[behavior_index][rollout_index] is not None
                ]
                policy_advantages[profile] = {
                    "paired_count": len(differences),
                    "mean_advantage": sum(differences) / len(differences) if differences else None,
                    "variance": _sample_variance(differences),
                }
            robust_across_profiles = all(
                metrics["mean_advantage"] is not None
                and float(metrics["mean_advantage"]) >= float(args.information_set_min_advantage)
                for metrics in policy_advantages.values()
            )
            candidate_return_variance = float(candidate_results[best_index]["return_variance"])
            strong = _strong_teacher_label(
                case_complete=not case_timed_out,
                paired_count=len(paired_differences),
                requested_count=int(args.information_set_rollouts_per_action),
                advantage=advantage,
                candidate_return_variance=candidate_return_variance,
                lower_bound=lower_bound,
                robust_across_profiles=robust_across_profiles,
                min_advantage=float(args.information_set_min_advantage),
                max_return_variance=float(args.information_set_max_variance),
            )
            label = {
                "best_candidate_index": best_index,
                "behavior_candidate_index": behavior_index,
                "candidate_advantage": advantage,
                "paired_return_variance": variance,
                "candidate_return_variance": candidate_return_variance,
                "advantage_95_lower_bound": lower_bound,
                "label_confidence": confidence,
                "continuation_policy_advantages": policy_advantages,
                "robust_across_continuation_profiles": robust_across_profiles,
                "strong_teacher_label": strong,
            }
            if strong:
                strong_labels.append(
                    {
                        "game_id": sample.get("game_id"),
                        "turn_index": sample.get("turn_index"),
                        "state": sample.get("state"),
                        "legal_actions": sample.get("legal_actions"),
                        "teacher_action": candidate_results[best_index],
                        "behavior_action": candidate_results[behavior_index],
                        "rollout_count": len(paired_differences),
                        "hidden_card_sampling_method": "uniform_physical_assignment_given_public_counts_v1",
                        "mean_return": candidate_results[best_index]["mean_return"],
                        "return_variance": candidate_results[best_index]["return_variance"],
                        **label,
                    }
                )
        case_results.append(
            {
                "game_id": sample.get("game_id"),
                "turn_index": sample.get("turn_index"),
                "scenario": sample.get("scenario"),
                "observable_risk_score": _observable_risk_score(sample),
                "case_seconds": time.monotonic() - case_started,
                "case_timed_out": case_timed_out,
                "candidate_results": candidate_results,
                "teacher_label": label,
                "candidate_failures": failures,
            }
        )
    requested_total_rollouts = sum(
        len(case["candidate_results"]) * int(args.information_set_rollouts_per_action)
        for case in case_results
    )
    all_cases_completed = bool(
        case_results
        and timeout_case_count == 0
        and completed_rollouts == requested_total_rollouts
    )
    result = {
        "schema_version": "website_information_set_rollout_v1",
        "dataset_path": str(args.website_information_set_rollout_eval),
        "dataset_partition_role": dataset_summary.get("partition_role"),
        "locked_test_loaded": False,
        "evaluated_cases": len(case_results),
        "candidate_count": sum(len(case["candidate_results"]) for case in case_results),
        "requested_rollouts_per_action": int(args.information_set_rollouts_per_action),
        "requested_total_rollouts": requested_total_rollouts,
        "total_rollouts": total_rollouts,
        "completed_rollouts": completed_rollouts,
        "rollout_completion_rate": (
            completed_rollouts / requested_total_rollouts if requested_total_rollouts else 0.0
        ),
        "timeout_case_count": timeout_case_count,
        "all_cases_completed": all_cases_completed,
        "hidden_card_sampling_method": "uniform_physical_assignment_given_public_counts_v1",
        "determinization_seed_scheme": "sha256_game_id_turn_index_determinization_index_v1",
        "common_determinizations_across_continuation_profiles": True,
        "continuation_policy": "information_set_profile_ensemble_v1",
        "continuation_profiles": continuation_profiles,
        "continuation_profile_rollout_counts": dict(profile_rollout_counts),
        "baseline_action_cache_enabled": baseline_cache is not None,
        "baseline_action_cache_size": len(baseline_cache or {}),
        "baseline_action_cache_hit_count": int(baseline_stats.get("hits", 0.0)),
        "baseline_action_cache_miss_count": int(baseline_stats.get("misses", 0.0)),
        "baseline_action_cache_hit_rate": (
            baseline_stats.get("hits", 0.0)
            / (baseline_stats.get("hits", 0.0) + baseline_stats.get("misses", 0.0))
            if baseline_stats.get("hits", 0.0) + baseline_stats.get("misses", 0.0)
            else 0.0
        ),
        "baseline_action_cache_hit_seconds": baseline_stats.get("hit_seconds", 0.0),
        "baseline_action_cache_miss_seconds": baseline_stats.get("miss_seconds", 0.0),
        "baseline_action_max_miss_seconds": baseline_stats.get("max_miss_seconds", 0.0),
        "baseline_action_slow_samples": list(baseline_stats.get("slow_samples", [])),
        "risk_priority": bool(args.information_set_risk_priority),
        "requested_case_keys": sorted(":".join(item) for item in case_keys),
        "future_information_used": False,
        "opponent_or_teammate_true_hands_used": False,
        "strong_teacher_label_count": len(strong_labels),
        "strong_teacher_labels": strong_labels,
        "case_results": case_results,
        "integrity_failures": integrity_failures,
        "threshold_passed": bool(all_cases_completed and not integrity_failures),
        "capability_claim_allowed": False,
    }
    Path(args.information_set_rollout_out).write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(
        json.dumps(
            {
                key: value
                for key, value in result.items()
                if key not in {"case_results", "strong_teacher_labels", "baseline_action_slow_samples"}
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    if not case_results or integrity_failures:
        raise RuntimeError("information-set rollout feasibility gate failed")
    return result
