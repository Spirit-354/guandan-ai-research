from __future__ import annotations

from collections import Counter
from dataclasses import asdict
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Sequence

import numpy as np

import danzero_features as features
import play_step_0902 as engine


SHADOW_SCHEMA_VERSION = "website_shadow_v1"
SHADOW_SUGGESTION_SOURCE = "tempo_baseline_mirror"


def _level_to_int(level: str | int) -> int:
    text = str(level).upper()
    ranks = ("2", "3", "4", "5", "6", "7", "8", "9", "T", "J", "Q", "K", "A")
    if text in ranks:
        return ranks.index(text) + 2
    value = int(level)
    if 2 <= value <= 14:
        return value
    raise ValueError(f"invalid website level: {level}")


def _seat_from_ranking_item(item: Any, seats: Sequence[Any]) -> int | None:
    if isinstance(item, int) and 0 <= item < 4:
        return item
    text = str(item)
    if text.isdigit() and 0 <= int(text) < 4:
        return int(text)
    try:
        return list(seats).index(item)
    except ValueError:
        return None


def _history_entries(state: dict) -> list[tuple[int, list[str]]]:
    entries: list[tuple[int, list[str]]] = []
    for raw in state.get("trick_history") or []:
        if not isinstance(raw, (list, tuple)) or len(raw) < 2:
            continue
        try:
            seat = int(raw[0])
        except (TypeError, ValueError):
            continue
        if 0 <= seat < 4:
            entries.append((seat, list(raw[1] or [])))
    return entries


def validate_team_mapping(state: dict) -> dict:
    errors: list[str] = []
    seats = list(state.get("seats") or [])
    try:
        your_seat = int(state.get("your_seat"))
    except (TypeError, ValueError):
        your_seat = -1
    if len(seats) != 4:
        errors.append("seats_length_not_four")
    if not 0 <= your_seat < 4:
        errors.append("invalid_your_seat")
        return {"valid": False, "errors": errors, "teammate_seat": None}
    teammate = (your_seat + 2) % 4
    if your_seat % 2 != teammate % 2:
        errors.append("parity_team_mapping_failed")

    teams = state.get("teams")
    if isinstance(teams, dict) and seats:
        seat_team_values = [teams.get(str(seat)) for seat in range(4)]
        if all(value is not None for value in seat_team_values):
            if seat_team_values[your_seat] != seat_team_values[teammate]:
                errors.append("teammate_server_team_mismatch")
            for opponent in ((your_seat + 1) % 4, (your_seat + 3) % 4):
                if seat_team_values[opponent] == seat_team_values[your_seat]:
                    errors.append("opponent_server_team_mismatch")
        else:
            groups = [list(value) for value in teams.values() if isinstance(value, (list, tuple))]
            own_name = seats[your_seat]
            teammate_name = seats[teammate]
            own_groups = [group for group in groups if own_name in group]
            if len(own_groups) != 1:
                errors.append("own_team_group_not_unique")
            elif teammate_name not in own_groups[0]:
                errors.append("teammate_not_in_own_team_group")
    elif teams is not None:
        errors.append("unsupported_teams_shape")

    return {
        "valid": not errors,
        "errors": errors,
        "your_seat": your_seat,
        "teammate_seat": teammate,
        "opponent_seats": [(your_seat + 1) % 4, (your_seat + 3) % 4],
    }


def website_state_to_feature_game(state: dict) -> Any:
    seats = list(state.get("seats") or [0, 1, 2, 3])
    if len(seats) != 4:
        raise ValueError("website state must contain four seats")
    your_seat = int(state.get("your_seat"))
    hand_counts = list(state.get("hand_counts") or [])
    if len(hand_counts) != 4:
        raise ValueError("website state must contain four hand counts")

    played_by_seat: list[list[str]] = [[] for _ in range(4)]
    last_by_seat: list[list[str]] = [[] for _ in range(4)]
    for seat, cards in _history_entries(state):
        played_by_seat[seat].extend(cards)
        last_by_seat[seat] = cards

    players = []
    for seat in range(4):
        hand = list(state.get("your_hand") or []) if seat == your_seat else [None] * int(hand_counts[seat])
        players.append(
            SimpleNamespace(
                hand=hand,
                played_cards=played_by_seat[seat],
                last_played_cards=last_by_seat[seat],
            )
        )
    ranking = []
    for item in state.get("ranking") or []:
        seat = _seat_from_ranking_item(item, seats)
        if seat is not None and seat not in ranking:
            ranking.append(seat)
    return SimpleNamespace(
        players=players,
        ranking=ranking,
        last_play=list(state.get("last_play") or []),
        active_level=_level_to_int(state.get("level")),
    )


def _cards_key(cards: Sequence[str]) -> tuple[tuple[str, int], ...]:
    return tuple(sorted(Counter(cards).items()))


def _cards_in_hand(cards: Sequence[str], hand: Sequence[str]) -> bool:
    required = Counter(cards)
    available = Counter(hand)
    return all(available[card] >= count for card, count in required.items())


def _play_infos(cards: Sequence[str], level: str, last_play: Sequence[str]) -> list[Any]:
    if not cards:
        return []
    if last_play:
        return list(engine.safe_follow_infos(list(cards), list(last_play), level))
    return list(engine.canonical_table_infos(list(cards), level))


def legal_candidate_metadata(state: dict) -> list[dict]:
    hand = list(state.get("your_hand") or [])
    level = str(state.get("level"))
    last_play = list(state.get("last_play") or [])
    was_lead = not last_play
    candidates: dict[tuple, dict] = {}
    if not was_lead:
        candidates[((), "pass", "", 0)] = {"cards": [], "action_type": "pass", "rank": None, "size": 0}
    for info in engine.legal_play_options(hand, level):
        cards = list(info.cards)
        legal_infos = engine.canonical_table_infos(cards, level) if was_lead else engine.safe_follow_infos(cards, last_play, level)
        for legal_info in legal_infos:
            key = (_cards_key(cards), legal_info.type, legal_info.rank, legal_info.size)
            candidates[key] = {
                "cards": cards,
                "action_type": legal_info.type,
                "rank": legal_info.rank,
                "size": legal_info.size,
            }
    return list(candidates.values())


def action_audit(state: dict, cards: Sequence[str], legal_candidates: Sequence[dict]) -> dict:
    hand = list(state.get("your_hand") or [])
    last_play = list(state.get("last_play") or [])
    level = str(state.get("level"))
    cards = list(cards or [])
    was_lead = not last_play
    in_hand = _cards_in_hand(cards, hand)
    infos = _play_infos(cards, level, last_play)
    local_legal = bool((not cards and not was_lead) or (cards and in_hand and infos))
    candidate_keys = {_cards_key(candidate.get("cards") or []) for candidate in legal_candidates}
    oracle_match = _cards_key(cards) in candidate_keys
    physical = features.encode_physical_action_54(cards)
    all_interpretations = [asdict(info) for info in engine.recognize(cards, level)] if cards else []
    canonical = infos[0] if infos else None
    wildcard = "H" + level
    return {
        "cards": cards,
        "cards_in_hand": in_hand,
        "action_not_in_hand": not in_hand,
        "local_legal": local_legal,
        "oracle_match": oracle_match,
        "action_type": canonical.type if canonical is not None else ("pass" if not cards else None),
        "logic_rank": canonical.rank if canonical is not None else None,
        "size": len(cards),
        "physical_action_54": physical.tolist(),
        "physical_action_count": int(physical.sum()),
        "physical_action_encoding_version": features.DANZERO_PHYSICAL_ACTION_ENCODING_VERSION,
        "contains_level_card": any(card not in {"B", "R"} and card[1:] == level for card in cards),
        "contains_heart_level_wildcard": wildcard in cards,
        "wildcard_interpretations": all_interpretations,
        "materialization_fail": bool(not in_hand or int(physical.sum()) != len(cards)),
    }


def build_shadow_audit(
    state: dict,
    submitted_action: Sequence[str],
    suggested_action: Sequence[str] | None = None,
    *,
    suggestion_source: str = SHADOW_SUGGESTION_SOURCE,
    enumerate_all_candidates: bool = True,
) -> dict:
    suggested = list(submitted_action if suggested_action is None else suggested_action)
    team_mapping = validate_team_mapping(state)
    if enumerate_all_candidates:
        candidates = legal_candidate_metadata(state)
        oracle_validation_mode = "exhaustive_engine_options"
    else:
        candidates = []
        if state.get("last_play") and (not submitted_action or not suggested):
            candidates.append({"cards": [], "action_type": "pass", "rank": None, "size": 0})
        for cards in (list(submitted_action), suggested):
            for info in _play_infos(cards, str(state.get("level")), list(state.get("last_play") or [])):
                candidates.append(
                    {"cards": cards, "action_type": info.type, "rank": info.rank, "size": info.size}
                )
        if not state.get("last_play") and not candidates:
            candidates = []
        oracle_validation_mode = "chosen_action_only"
    game = website_state_to_feature_game(state)
    your_seat = int(state.get("your_seat"))
    paper_state = features.encode_compact_state_513(game, your_seat, legal_candidates=candidates)
    website_state = features.encode_website_compact_state_487(game, your_seat, legal_candidates=candidates)
    submitted = action_audit(state, list(submitted_action), candidates)
    suggestion = action_audit(state, suggested, candidates)
    same_action = _cards_key(submitted_action) == _cards_key(suggested)
    return {
        "schema_version": SHADOW_SCHEMA_VERSION,
        "shadow_enabled": True,
        "submission_policy": "tempo_baseline",
        "suggestion_source": suggestion_source,
        "model_controlled_action": False,
        "model_controlled_action_count": 0,
        "was_lead": not bool(state.get("last_play") or []),
        "was_follow": bool(state.get("last_play") or []),
        "level": state.get("level"),
        "your_seat": your_seat,
        "your_team": state.get("your_team"),
        "team_mapping": team_mapping,
        "team_mapping_error": not team_mapping["valid"],
        "legal_candidate_count": len(candidates),
        "oracle_validation_mode": oracle_validation_mode,
        "oracle_exhaustive": enumerate_all_candidates,
        "paper_state_513": paper_state.tolist(),
        "website_state_487": website_state.tolist(),
        "paper_state_dim": int(paper_state.shape[0]),
        "website_state_dim": int(website_state.shape[0]),
        "paper_state_encoding_version": features.DANZERO_COMPACT_STATE_ENCODING_VERSION,
        "website_state_encoding_version": features.DANZERO_WEBSITE_STATE_ENCODING_VERSION,
        "state_non_finite": bool(not np.isfinite(paper_state).all() or not np.isfinite(website_state).all()),
        "state_encoding_evaluated": True,
        "submitted_action": submitted,
        "suggested_action": suggestion,
        "suggestion_matches_submission": same_action,
        "suggestion_website_legality_observed": False,
        "submitted_action_server_success": None,
        "submitted_action_acceptance_inferred": False,
    }


def mark_submit_result(audit: dict | None, result: dict) -> None:
    if not audit:
        return
    accepted = bool(result.get("is_success"))
    audit["submitted_action_server_success"] = accepted
    if audit.get("suggestion_matches_submission"):
        audit["suggestion_website_legality_observed"] = True
        audit["suggested_action"]["website_legal"] = accepted


def mark_submit_acceptance_inferred(audit: dict | None) -> None:
    if not audit:
        return
    audit["submitted_action_acceptance_inferred"] = True
    if audit.get("suggestion_matches_submission"):
        audit["suggested_action"]["website_legality_inferred"] = True


def summarize_decisions(decisions: Sequence[dict]) -> dict:
    audits = [decision.get("website_shadow") for decision in decisions if decision.get("website_shadow")]
    result = {
        "schema_version": SHADOW_SCHEMA_VERSION,
        "shadow_decision_count": len(audits),
        "model_controlled_action_count": 0,
        "state_encoding_error_count": 0,
        "state_encoding_not_evaluated_count": 0,
        "team_mapping_error_count": 0,
        "action_not_in_hand_count": 0,
        "local_legality_error_count": 0,
        "oracle_disagree_count": 0,
        "oracle_exhaustive_decision_count": 0,
        "materialization_fail_count": 0,
        "website_rule_disagree_count": 0,
        "website_acceptance_inferred_count": 0,
        "suggestion_diff_count": 0,
        "level_wildcard_error_count": 0,
        "threshold_passed": False,
    }
    for audit in audits:
        submitted = audit["submitted_action"]
        suggested = audit["suggested_action"]
        state_evaluated = bool(audit.get("state_encoding_evaluated", True))
        result["state_encoding_not_evaluated_count"] += int(not state_evaluated)
        result["state_encoding_error_count"] += int(
            state_evaluated
            and (
                audit.get("paper_state_dim") != features.DANZERO_COMPACT_STATE_DIM
                or audit.get("website_state_dim") != features.DANZERO_WEBSITE_COMPACT_STATE_DIM
                or bool(audit.get("state_non_finite"))
            )
        )
        result["team_mapping_error_count"] += int(bool(audit.get("team_mapping_error")))
        result["action_not_in_hand_count"] += int(bool(suggested.get("action_not_in_hand")))
        result["local_legality_error_count"] += int(not bool(suggested.get("local_legal")))
        result["oracle_disagree_count"] += int(not bool(suggested.get("oracle_match")))
        result["oracle_exhaustive_decision_count"] += int(bool(audit.get("oracle_exhaustive")))
        result["materialization_fail_count"] += int(bool(suggested.get("materialization_fail")))
        result["website_rule_disagree_count"] += int(
            submitted.get("local_legal") and audit.get("submitted_action_server_success") is False
        )
        result["website_acceptance_inferred_count"] += int(bool(audit.get("submitted_action_acceptance_inferred")))
        result["suggestion_diff_count"] += int(not bool(audit.get("suggestion_matches_submission")))
        result["level_wildcard_error_count"] += int(
            suggested.get("contains_heart_level_wildcard")
            and suggested.get("physical_action_count") != suggested.get("size")
        )
    error_fields = (
        "state_encoding_error_count",
        "team_mapping_error_count",
        "action_not_in_hand_count",
        "local_legality_error_count",
        "oracle_disagree_count",
        "materialization_fail_count",
        "website_rule_disagree_count",
        "level_wildcard_error_count",
    )
    result["threshold_passed"] = bool(audits and all(result[name] == 0 for name in error_fields))
    return result


def reconstruct_historical_state(record: dict, decision: dict) -> dict:
    final_state = record.get("final_state") or {}
    seats = list(final_state.get("seats") or [])
    hand_counts = list(decision.get("hand_counts") or [])
    if len(seats) != 4 or len(hand_counts) != 4:
        raise ValueError("historical record lacks four seats or hand counts")
    trick_index = int(decision.get("trick_index") or 0)
    full_history = list(final_state.get("trick_history") or [])
    ranking = [seats[index] for index, count in enumerate(hand_counts) if int(count) <= 0]
    return {
        "seats": seats,
        "teams": final_state.get("teams"),
        "level": decision.get("level") or final_state.get("level"),
        "your_seat": final_state.get("your_seat"),
        "your_team": final_state.get("your_team"),
        "your_hand": list(decision.get("hand") or []),
        "hand_counts": hand_counts,
        "last_play": list(decision.get("last_play") or []),
        "last_player": decision.get("last_player"),
        "current_turn": decision.get("current_turn"),
        "ranking": ranking,
        "trick_history": full_history[:trick_index],
        "is_your_turn": True,
        "completed": False,
    }


def build_historical_action_audit(record: dict, decision: dict) -> dict:
    state = reconstruct_historical_state(record, decision)
    action = list(decision.get("play") or [])
    candidates = []
    if state.get("last_play") and not action:
        candidates.append({"cards": [], "action_type": "pass", "rank": None, "size": 0})
    for info in _play_infos(action, str(state.get("level")), list(state.get("last_play") or [])):
        candidates.append({"cards": action, "action_type": info.type, "rank": info.rank, "size": info.size})
    action_result = action_audit(state, action, candidates)
    team_mapping = validate_team_mapping(state)
    return {
        "schema_version": SHADOW_SCHEMA_VERSION,
        "shadow_enabled": True,
        "submission_policy": "tempo_baseline",
        "suggestion_source": SHADOW_SUGGESTION_SOURCE,
        "model_controlled_action": False,
        "model_controlled_action_count": 0,
        "was_lead": not bool(state.get("last_play") or []),
        "was_follow": bool(state.get("last_play") or []),
        "level": state.get("level"),
        "your_seat": state.get("your_seat"),
        "your_team": state.get("your_team"),
        "team_mapping": team_mapping,
        "team_mapping_error": not team_mapping["valid"],
        "legal_candidate_count": len(candidates),
        "oracle_validation_mode": "chosen_action_only",
        "oracle_exhaustive": False,
        "paper_state_dim": None,
        "website_state_dim": None,
        "state_non_finite": False,
        "state_encoding_evaluated": False,
        "state_encoding_skip_reason": "historical_trick_history_is_capped_at_40",
        "submitted_action": action_result,
        "suggested_action": dict(action_result),
        "suggestion_matches_submission": True,
        "suggestion_website_legality_observed": False,
        "submitted_action_server_success": None,
        "submitted_action_acceptance_inferred": False,
    }


def replay_historical_logs(profile: str, out_path: str, max_games: int = 0) -> dict:
    log_paths = sorted(
        Path(".").glob("logs*/research_game_*.json"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    records: list[tuple[Path, dict]] = []
    seen_games: set[str] = set()
    for path in log_paths:
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if str(record.get("profile")) != str(profile):
            continue
        if not bool((record.get("final_state") or {}).get("completed")):
            continue
        game_id = str(record.get("game_id"))
        if game_id in seen_games:
            continue
        seen_games.add(game_id)
        records.append((path, record))
        if int(max_games) > 0 and len(records) >= int(max_games):
            break

    aggregate_fields = (
        "state_encoding_error_count",
        "team_mapping_error_count",
        "action_not_in_hand_count",
        "local_legality_error_count",
        "oracle_disagree_count",
        "materialization_fail_count",
        "website_rule_disagree_count",
        "website_acceptance_inferred_count",
        "suggestion_diff_count",
        "level_wildcard_error_count",
    )
    result = {
        "schema_version": SHADOW_SCHEMA_VERSION,
        "mode": "historical_replay",
        "profile": profile,
        "evaluated_games": 0,
        "evaluated_decisions": 0,
        "reconstruction_error_count": 0,
        "oracle_validation_mode": "chosen_action_only",
        "oracle_exhaustive_decision_count": 0,
        "state_encoding_not_evaluated_count": 0,
        "history_capped_game_count": 0,
        "model_controlled_action_count": 0,
        **{name: 0 for name in aggregate_fields},
        "concrete_errors": [],
        "threshold_passed": False,
        "online_shadow_gate_satisfied": False,
    }
    for path, record in records:
        game_had_decision = False
        if len((record.get("final_state") or {}).get("trick_history") or []) >= 40:
            result["history_capped_game_count"] += 1
        for decision in record.get("decisions") or []:
            try:
                audit = build_historical_action_audit(record, decision)
                mark_submit_result(audit, decision.get("result") or {})
                one = summarize_decisions([{"website_shadow": audit}])
            except Exception as exc:
                result["reconstruction_error_count"] += 1
                if len(result["concrete_errors"]) < 50:
                    result["concrete_errors"].append(
                        {
                            "game_id": record.get("game_id"),
                            "turn": decision.get("turn"),
                            "source_log": str(path),
                            "reason": type(exc).__name__,
                            "message": str(exc),
                        }
                    )
                continue
            game_had_decision = True
            result["evaluated_decisions"] += 1
            result["state_encoding_not_evaluated_count"] += int(
                one.get("state_encoding_not_evaluated_count") or 0
            )
            for name in aggregate_fields:
                result[name] += int(one.get(name) or 0)
            if not one["threshold_passed"] and len(result["concrete_errors"]) < 50:
                result["concrete_errors"].append(
                    {
                        "game_id": record.get("game_id"),
                        "turn": decision.get("turn"),
                        "source_log": str(path),
                        "summary": one,
                        "submitted_action": {
                            key: value
                            for key, value in (audit.get("submitted_action") or {}).items()
                            if key not in {"physical_action_54", "wildcard_interpretations"}
                        },
                    }
                )
        result["evaluated_games"] += int(game_had_decision)

    replay_errors = (
        "reconstruction_error_count",
        "state_encoding_error_count",
        "team_mapping_error_count",
        "action_not_in_hand_count",
        "local_legality_error_count",
        "materialization_fail_count",
        "website_rule_disagree_count",
        "level_wildcard_error_count",
    )
    result["threshold_passed"] = bool(
        result["evaluated_games"] > 0
        and result["evaluated_decisions"] > 0
        and all(int(result[name]) == 0 for name in replay_errors)
    )
    Path(out_path).write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return result
