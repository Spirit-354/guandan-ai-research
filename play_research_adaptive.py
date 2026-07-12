import argparse
import copy
import html
import itertools
import json
import os
import random
import re
import socket
import sys
import time
from collections import Counter
from dataclasses import asdict, dataclass
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import play_step_0902 as engine
import website_shadow as live_shadow


PROFILE_PATH = Path("strategy_profiles.json")
BOT_MEMORY_PATH = Path("bot_memory.json")
RESULTS_PATH = Path("research_results.json")
DEFAULT_LOG_DIR = "logs_research"
DEFAULT_LEADERBOARD_URL = "http://183.175.14.145:8003/rank/"
DEFAULT_LIVE_PROFILE = "tempo_baseline"
CANDIDATE_PROFILES: set[str] = set()
OBSERVATION_ONLY_PROFILES: set[str] = set()
CONFIGURED_PAUSED_PROFILES = {
    "tempo_plate_delay_guard",
    "tempo_shape_guard",
    "tempo_shape_guard_v2",
    "tempo_endgame_guard",
    "bait_high_card",
    "bait_high_card_v2",
    "weak_ally_safe",
    "tempo_high_elo_safe",
    "defense_heavy",
    "anti_strong_opponent",
    "balanced",
    "endgame_defense",
    "bomb_conservative",
}
LEADERBOARD_AFTER_WAIT_MIN_SECONDS = 2.0
LEADERBOARD_AFTER_WAIT_MAX_SECONDS = 5.0
BIG_ELO_LOSS_THRESHOLD = -10.0
GLOBAL_PROFILE_MIN_GAMES = 30
SCENARIO_PROFILE_MIN_GAMES = 20
ELO_BUCKETS = (
    (None, 1799, "<1800"),
    (1800, 1999, "1800-1999"),
    (2000, 2199, "2000-2199"),
    (2200, 2399, "2200-2399"),
    (2400, None, "2400+"),
)
OBSERVATION_COUNTER_KEYS = (
    "lead_probe_count",
    "possible_overblock_count",
    "high_card_response_count",
    "joker_response_count",
    "level_card_response_count",
    "bomb_response_to_non_bomb_count",
)
BAIT_COUNTER_KEYS = (
    "bait_attempt_count",
    "bait_candidate_count",
    "bait_selected_count",
    "bait_response_observed_count",
    "bait_overblocked_count",
    "bait_success_count",
    "bait_failure_count",
    "bait_candidate_overblocked_count",
    "selected_without_candidate_count",
)
SHAPE_GUARD_COUNTER_KEYS = (
    "shape_guard_triggered",
    "shape_guard_follow_declined_expensive_block",
    "shape_guard_follow_allowed_expensive_block",
    "shape_guard_safe_lead_chosen",
    "shape_guard_baseline_kept_no_safe_alt",
    "shape_guard_preserved_pair_triple_straight",
    "shape_guard_preserved_2_joker_level",
    "shape_guard_preserved_potential_block",
    "shape_guard_prevented_left_self_without_block_shape",
    "shape_guard_candidate_count",
    "shape_guard_selected_count",
)
SHAPE_GUARD_V2_COUNTER_KEYS = (
    "shape_guard_v2_blockless_lead_replaced",
    "shape_guard_v2_blockless_lead_kept_no_safe_alt",
    "shape_guard_v2_safe_alt_used_when_opponent_le3",
)
SHAPE_GUARD_V2_REASON_KEYS = (
    "shape_guard_v2_safe_alt_rejected_reason_counts",
)
PLATE_DELAY_GUARD_COUNTER_KEYS = (
    "plate_delay_guard_triggered",
    "plate_delay_guard_selected",
    "plate_delay_guard_no_safe_single",
    "plate_delay_guard_candidate_count",
)
PLATE_DELAY_GUARD_REASON_KEYS = (
    "plate_delay_guard_original_plate_rank_counts",
    "plate_delay_guard_selected_single_rank_counts",
)
RATING_VALUE_FIELDS = {"elo", "rating", "leaderboard_score", "rank_score"}
RATING_DELTA_FIELDS = {"elo_delta", "rating_delta", "leaderboard_delta"}
CANDIDATE_DELTA_FIELDS = {"score_delta", "points_delta"}
SENSITIVE_FIELD_PARTS = {"password", "token", "cookie", "secret", "authorization"}
SUBMIT_TRANSIENT_ERRORS = (TimeoutError, socket.timeout, URLError)
MAX_SUBMIT_DESYNC_COUNT = 4
OFFLINE_GUANDAN_DIR = Path(__file__).resolve().parent.parent / "github_guandan" / "guandan-main"
OFFLINE_STATE_DIM = 3049
OFFLINE_ACTION_DIM = 375
OFFLINE_MAX_GAME_STEPS = 1200
DMC_ACTION_TYPES = (
    "None",
    "single",
    "pair",
    "triple",
    "three_with_pair",
    "straight",
    "pair_chain",
    "gangban",
    "flush_rocket",
    "4_bomb",
    "5_bomb",
    "6_bomb",
    "7_bomb",
    "8_bomb",
    "joker_bomb",
)
DMC_ACTION_FEATURE_BASE_DIM = 16
DMC_ACTION_FEATURE_DIM = DMC_ACTION_FEATURE_BASE_DIM + len(DMC_ACTION_TYPES)
DMC_SELFPLAY_CANDIDATE_SNAPSHOT_LIMIT = 12


@dataclass
class PlayerModel:
    overall_skill: float = 0.5
    endgame_skill: float = 0.5
    aggression: float = 0.5
    bomb_style: float = 0.5
    cooperation: float = 0.5
    riskiness: float = 0.5
    teammate_disruption: float = 0.5
    overblock_rate: float = 0.5
    high_card_spend_early_rate: float = 0.5
    bomb_spend_early_rate: float = 0.5
    control_preservation_score: float = 0.5
    games_seen: int = 0


def clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def adjust_model(model: PlayerModel, field: str, delta: float) -> None:
    setattr(model, field, clamp(float(getattr(model, field)) + delta))


def load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return default


def save_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def require_env(require_password: bool = True) -> None:
    user = os.environ.get("GUANDAN_USER")
    password = os.environ.get("GUANDAN_PASSWORD")
    if not user or (require_password and not password):
        raise RuntimeError(
            "missing credentials: set GUANDAN_USER"
            + (" and GUANDAN_PASSWORD" if require_password else "")
            + ". GUANDAN_BASE_URL is optional."
        )
    engine.USER = user
    if password:
        engine.PASSWORD = password
    engine.BASE_URL = os.environ.get("GUANDAN_BASE_URL", engine.BASE_URL)


def auth_params() -> dict:
    return engine.auth_params()


class RecoverableGameError(RuntimeError):
    def __init__(
        self,
        game_id: str,
        game_error_type: str,
        message: str,
        payload: dict | None = None,
    ) -> None:
        super().__init__(message)
        self.game_id = game_id
        self.game_error_type = game_error_type
        self.payload = payload or {}


class SubmitDesyncError(RecoverableGameError):
    def __init__(self, game_id: str, message: str, payload: dict | None = None) -> None:
        super().__init__(game_id, "submit_desync", message, payload)


class NotYourTurnAfterTimeoutError(RecoverableGameError):
    def __init__(self, game_id: str, message: str, payload: dict | None = None) -> None:
        super().__init__(game_id, "not_your_turn_after_timeout", message, payload)


class GameDisappearedError(RecoverableGameError):
    def __init__(self, game_id: str, message: str, payload: dict | None = None) -> None:
        super().__init__(game_id, "game_disappeared", message, payload)


class TransientGameUnavailableError(RecoverableGameError):
    def __init__(self, game_id: str, message: str, payload: dict | None = None) -> None:
        super().__init__(game_id, "transient_game_unavailable", message, payload)


def get_json_once(path: str, params: dict | None = None, timeout: float | None = None) -> dict:
    query = "" if not params else "?" + urlencode(params)
    request = Request(engine.BASE_URL + path + query, headers={"User-Agent": "play-research-adaptive/1.0"})
    with urlopen(request, timeout=timeout or engine.HTTP_TIMEOUT_SECONDS) as response:
        text = response.read().decode(response.headers.get_content_charset() or "utf-8")
    return json.loads(text)


def join_game_full() -> tuple[str, dict]:
    data = engine.get_json("/join_game", auth_params())
    if not data.get("is_success"):
        raise RuntimeError(f"join_game failed: {data}")
    return str(data["game_id"]), data


def check_game(game_id: str) -> dict:
    params = {"user": engine.USER, "password": engine.encrypted_password_hex()}
    return engine.get_json(f"/check_game/{game_id}/", params)


def play_game(game_id: str, coord: list[str]) -> dict:
    params = auth_params()
    params["coord"] = json.dumps(coord, separators=(",", ":"))
    return get_json_once(f"/play_game/{game_id}/", params, timeout=engine.HTTP_TIMEOUT_SECONDS)


def is_sensitive_path(path: str) -> bool:
    lowered = path.lower()
    return any(part in lowered for part in SENSITIVE_FIELD_PARTS)


def extract_rating_fields(payload: dict) -> dict:
    """
    Recursively scan server JSON for candidate leaderboard/Elo/rating fields.
    Sensitive fields such as password, token, and cookie are skipped.
    """
    found = {"confirmed": {}, "confirmed_deltas": {}, "candidates": {}}

    def walk(value: Any, path: str) -> None:
        if is_sensitive_path(path):
            return
        if isinstance(value, dict):
            for key, child in value.items():
                child_path = f"{path}.{key}" if path else str(key)
                lowered_key = str(key).lower()
                if isinstance(child, (int, float)) and not isinstance(child, bool):
                    item = {"field": key, "value": child, "source_path": child_path}
                    if lowered_key in RATING_VALUE_FIELDS:
                        found["confirmed"][child_path] = item
                    elif lowered_key in RATING_DELTA_FIELDS:
                        found["confirmed_deltas"][child_path] = item
                    elif lowered_key in CANDIDATE_DELTA_FIELDS or any(
                        token in lowered_key for token in ("elo", "rating", "leaderboard", "rank")
                    ):
                        found["candidates"][child_path] = item
                walk(child, child_path)
        elif isinstance(value, list):
            for index, child in enumerate(value):
                walk(child, f"{path}[{index}]")

    if isinstance(payload, dict):
        walk(payload, "")
    return found


def merge_rating_fields(*items: dict) -> dict:
    merged = {"confirmed": {}, "confirmed_deltas": {}, "candidates": {}}
    for item in items:
        if not item:
            continue
        for key in merged:
            merged[key].update(item.get(key, {}))
    return merged


def resolve_elo_delta(before_fields: dict, after_fields: dict, final_state: dict) -> dict:
    """
    Compute Elo delta only from explicit Elo/rating/leaderboard fields.
    final_state["scores"] is proxy data only and is never treated as Elo.
    """
    proxy_points = final_state.get("scores") if isinstance(final_state, dict) else None
    base = {
        "elo_available": False,
        "elo_unavailable": True,
        "elo_source_field": None,
        "elo_before": None,
        "elo_after": None,
        "elo_delta": None,
        "total_elo_delta": None,
        "average_elo_delta_per_game": None,
        "max_elo_gain": None,
        "max_elo_loss": None,
        "big_elo_loss_count": None,
        "proxy_points": proxy_points,
        "proxy_metric_source": "final_state.scores" if proxy_points is not None else None,
        "candidate_rating_fields_before": before_fields.get("candidates", {}),
        "candidate_rating_fields_after": after_fields.get("candidates", {}),
    }

    for path, item in after_fields.get("confirmed_deltas", {}).items():
        if path.split(".")[-1].lower() in RATING_DELTA_FIELDS:
            delta = float(item["value"])
            base.update(
                {
                    "elo_available": True,
                    "elo_unavailable": False,
                    "elo_source_field": path,
                    "elo_delta": delta,
                    "total_elo_delta": delta,
                    "average_elo_delta_per_game": delta,
                    "max_elo_gain": max(delta, 0.0),
                    "max_elo_loss": min(delta, 0.0),
                    "big_elo_loss_count": 1 if delta <= -10 else 0,
                }
            )
            return base

    before_confirmed = before_fields.get("confirmed", {})
    after_confirmed = after_fields.get("confirmed", {})
    for path, before_item in before_confirmed.items():
        if path not in after_confirmed:
            continue
        before_value = float(before_item["value"])
        after_value = float(after_confirmed[path]["value"])
        delta = after_value - before_value
        base.update(
            {
                "elo_available": True,
                "elo_unavailable": False,
                "elo_source_field": path,
                "elo_before": before_value,
                "elo_after": after_value,
                "elo_delta": delta,
                "total_elo_delta": delta,
                "average_elo_delta_per_game": delta,
                "max_elo_gain": max(delta, 0.0),
                "max_elo_loss": min(delta, 0.0),
                "big_elo_loss_count": 1 if delta <= -10 else 0,
            }
        )
        return base

    return base


def stable_player_id(name: Any) -> str | None:
    if not isinstance(name, str) or not name:
        return None
    lowered = name.lower()
    if lowered.startswith("player") or name.startswith("\u73a9\u5bb6"):
        return None
    return name


def load_bot_memory() -> dict:
    data = load_json(BOT_MEMORY_PATH, {"version": 1, "players": {}})
    data.setdefault("version", 1)
    data.setdefault("players", {})
    return data


def save_bot_memory(memory: dict) -> None:
    save_json(BOT_MEMORY_PATH, memory)


def models_for_state(state: dict, memory: dict, session_models: dict[int, PlayerModel]) -> dict[int, PlayerModel]:
    models: dict[int, PlayerModel] = {}
    seats = state.get("seats") or []
    for seat in range(4):
        model = None
        try:
            stable_id = stable_player_id(seats[seat])
        except (IndexError, TypeError):
            stable_id = None
        if stable_id and stable_id in memory.get("players", {}):
            model = PlayerModel(**memory["players"][stable_id])
        if model is None:
            model = session_models.setdefault(seat, PlayerModel())
        models[seat] = model
    return models


def persist_stable_models(state: dict, memory: dict, models: dict[int, PlayerModel]) -> None:
    seats = state.get("seats") or []
    for seat, model in models.items():
        try:
            stable_id = stable_player_id(seats[seat])
        except (IndexError, TypeError):
            stable_id = None
        if stable_id:
            memory.setdefault("players", {})[stable_id] = asdict(model)


def teammate_seat(state: dict) -> int:
    return (int(state["your_seat"]) + 2) % 4


def opponent_seats(state: dict) -> list[int]:
    return engine.opponent_seats(state)


def opponent_hand_counts(state: dict) -> list[int]:
    counts = state.get("hand_counts") or []
    result: list[int] = []
    for seat in opponent_seats(state):
        try:
            count = int(counts[seat])
        except (IndexError, TypeError, ValueError):
            continue
        result.append(count)
    return result


def scenario_tags(state: dict, models: dict[int, PlayerModel]) -> list[str]:
    tags: list[str] = []
    ally = models.get(teammate_seat(state))
    opponents = [models.get(seat) for seat in opponent_seats(state)]
    known_games = sum(model.games_seen for model in models.values())
    if known_games == 0:
        tags.append("all_unknown")
    if ally:
        if ally.overall_skill <= 0.40:
            tags.append("ally_weak")
        if ally.overall_skill >= 0.65:
            tags.append("ally_strong")
        if ally.teammate_disruption >= 0.60 or ally.cooperation <= 0.40:
            tags.append("ally_disruptive")
    strong_opponents = [model for model in opponents if model and model.overall_skill >= 0.65]
    if len(strong_opponents) == 1:
        tags.append("one_strong_opponent")
    if len(strong_opponents) >= 2:
        tags.append("two_strong_opponents")
    if opponents and sum(model.aggression for model in opponents if model) / max(1, len(opponents)) >= 0.62:
        tags.append("opponents_aggressive")
    if opponents and sum(model.bomb_style for model in opponents if model) / max(1, len(opponents)) <= 0.40:
        tags.append("opponents_conservative")
    if opponents and sum(model.endgame_skill for model in opponents if model) / max(1, len(opponents)) >= 0.62:
        tags.append("opponents_endgame_strong")
    if ally and ally.overall_skill <= 0.40 and strong_opponents:
        tags.append("weak_ally_vs_strong_opponents")
    if ally and ally.overall_skill >= 0.65 and not strong_opponents:
        tags.append("strong_ally_vs_weak_opponents")
    if engine.min_opponent_count(state) <= 2 or (
        strong_opponents and engine.min_opponent_count(state) <= 6
    ):
        tags.append("high_elo_loss_risk")
    if engine.min_opponent_count(state) <= 4:
        tags.append("endgame_danger_high")
    return tags or ["all_unknown"]


def scenario_key(tags: list[str]) -> str:
    return "+".join(sorted(set(tags)))


def profile_stats(results: dict, scenario: str, profile: str) -> dict | None:
    return results.get("scenario_profiles", {}).get(scenario, {}).get(profile)


def profile_score_from_stats(stats: dict | None) -> float | None:
    if not stats or stats.get("games", 0) <= 0:
        return None
    if (
        stats.get("elo_available")
        and stats.get("metric_source") == "leaderboard_elo"
        and stats.get("average_elo_delta_per_game") is not None
    ):
        return float(stats["average_elo_delta_per_game"])
    return None


def best_historical_profile(
    results: dict,
    scenario: str,
    profile_names: list[str],
    min_games: int,
) -> str | None:
    best_name = None
    best_score = None
    for name in profile_names:
        stats = profile_stats(results, scenario, name)
        if not stats or stats.get("games", 0) < min_games:
            continue
        score = profile_score_from_stats(stats)
        if score is None:
            continue
        if best_score is None or score > best_score:
            best_name = name
            best_score = score
    return best_name


def choose_profile_for_state(
    state: dict,
    player_models: dict[int, PlayerModel],
    research_results: dict,
    profiles: dict,
    exploration_rate: float = 0.15,
    min_games: int = 20,
    allowed_profiles: list[str] | None = None,
) -> tuple[str, list[str]]:
    names = allowed_profiles or [DEFAULT_LIVE_PROFILE]
    tags = scenario_tags(state, player_models)
    scenario = scenario_key(tags)

    if random.random() < exploration_rate:
        return random.choice(names), tags

    historical = best_historical_profile(research_results, scenario, names, min_games)
    if historical:
        return historical, tags

    ally = player_models.get(teammate_seat(state))
    opponents = [player_models.get(seat) for seat in opponent_seats(state)]
    strong_opponents = [model for model in opponents if model and model.overall_skill >= 0.65]
    opponent_min = engine.min_opponent_count(state)
    own_groups = engine.estimate_remaining_groups(state.get("your_hand") or [], state.get("level"))
    ally_count = engine.teammate_count(state)

    if opponent_min <= 2 and "endgame_defense" in names:
        return "endgame_defense", tags
    if len(strong_opponents) >= 2 and "defense_heavy" in names:
        return "defense_heavy", tags
    if len(strong_opponents) == 1 and opponent_min <= 6 and "anti_strong_opponent" in names:
        return "anti_strong_opponent", tags
    if ally and (ally.teammate_disruption >= 0.60 or ally.cooperation <= 0.40) and "weak_ally_safe" in names:
        return "weak_ally_safe", tags
    if ally and ally.overall_skill >= 0.65 and ally_count is not None and ally_count <= 3 and "ally_support" in names:
        return "ally_support", tags
    if own_groups <= 2.5 and "self_sprint" in names:
        return "self_sprint", tags
    if "balanced" in names and "all_unknown" in tags:
        return "balanced", tags
    return "tempo_baseline" if "tempo_baseline" in names else names[0]


def apply_profile(profile_name: str, profile: dict) -> None:
    engine.STRATEGY_MODE = profile.get("engine_mode", "tempo")
    engine.REMAINING_GROUP_WEIGHT = int(profile.get("remaining_group_weight", engine.REMAINING_GROUP_WEIGHT))
    if profile_name == "bomb_aggressive":
        engine.PROACTIVE_BOMB_HAND_LIMIT = 9
    elif profile_name == "bomb_conservative":
        engine.PROACTIVE_BOMB_HAND_LIMIT = 5
    else:
        engine.PROACTIVE_BOMB_HAND_LIMIT = 7


def primary_play_info(cards: list[str], level: str) -> Any:
    infos = engine.recognize(cards, level) if cards else []
    return infos[0] if infos else None


def card_rank(card: str) -> str:
    if card in {"B", "R"}:
        return card
    return card[1]


def high_control_ranks(level: str) -> set[str]:
    return {"A", "2", level, "B", "R"}


def recent_average_for_profile(results: dict, profile: str, window: int) -> float | None:
    records = [
        record for record in official_game_records(results)
        if record.get("profile") == profile and record.get("elo_delta") is not None
    ]
    if not records:
        return None
    recent = records[-window:]
    return sum(float(record.get("elo_delta") or 0.0) for record in recent) / len(recent)


def research_context(results: dict, leaderboard_before: dict | None) -> dict:
    elo_before = None
    if leaderboard_before:
        elo_before = leaderboard_before.get("current_user_elo_numeric")
    recent20_avg = recent_average_for_profile(results, DEFAULT_LIVE_PROFILE, 20)
    high_elo_risk = bool(
        (elo_before is not None and float(elo_before) >= 2200)
        or (recent20_avg is not None and recent20_avg < 0)
    )
    return {
        "elo_before": elo_before,
        "recent20_average_elo_delta_per_game": recent20_avg,
        "high_elo_risk": high_elo_risk,
    }


def is_high_elo_safe_active(state: dict) -> bool:
    context = state.get("_research_context") or {}
    return bool(
        context.get("high_elo_risk")
        or engine.min_opponent_count(state) <= 6
    )


def choose_high_elo_safe_play(state: dict, profile: dict) -> list[str]:
    baseline = engine.choose_play(state)
    if not is_high_elo_safe_active(state):
        return baseline
    hand = state.get("your_hand") or []
    level = state.get("level")
    last_play = state.get("last_play") or []
    opponent_min = engine.min_opponent_count(state)
    if baseline and len(baseline) == len(hand):
        return baseline

    if last_play and engine.relation_to_last(state) == "opponent" and opponent_min <= 6:
        candidates = legal_candidate_actions(state)
        non_pass = [cards for cards in candidates if cards]
        if non_pass:
            ranked = [
                (
                    score_action(state, cards, profile)
                    + (80.0 if opponent_min <= 4 else 35.0)
                    - (25.0 if engine.server_treats_as_bomb(cards, level) and opponent_min > 4 else 0.0),
                    -len(cards),
                    engine.sort_cards(cards, level),
                    cards,
                )
                for cards in non_pass
            ]
            return max(ranked, key=lambda item: (item[0], item[1], item[2]))[3]

    if not last_play and baseline:
        features = action_features(state, baseline)
        if features["bad_lead_size_risk"] or features["giving_control_to_strong_opponent_risk"]:
            candidates = [
                cards for cards in legal_candidate_actions(state)
                if cards
                and not action_features(state, cards)["bad_lead_size_risk"]
                and not action_features(state, cards)["giving_control_to_strong_opponent_risk"]
                and engine.estimate_remaining_groups(engine.remove_cards(hand, cards), level)
                <= engine.estimate_remaining_groups(hand, level) + 0.01
            ]
            if candidates:
                ranked = [
                    (
                        score_action(state, cards, profile),
                        -len(cards),
                        engine.sort_cards(cards, level),
                        cards,
                    )
                    for cards in candidates
                ]
                return max(ranked, key=lambda item: (item[0], item[1], item[2]))[3]
    return baseline


def is_tempo_endgame_guard_active(state: dict) -> bool:
    context = state.get("_research_context") or {}
    tags = set(state.get("_scenario_tags") or [])
    elo_before = context.get("elo_before")
    try:
        high_elo = elo_before is not None and float(elo_before) >= 2200.0
    except (TypeError, ValueError):
        high_elo = False
    return bool(
        high_elo
        or "high_elo_loss_risk" in tags
        or "endgame_danger_high" in tags
        or any(count <= 8 for count in opponent_hand_counts(state))
    )


def cheap_guard_block_options(state: dict) -> tuple[list[dict], list[dict]]:
    hand = state.get("your_hand") or []
    level = state.get("level")
    last_play = state.get("last_play") or []
    if not hand or not last_play or not level:
        return [], []
    groups_before = engine.estimate_remaining_groups(hand, level)
    options = legal_block_options(hand, last_play, level)
    cheap = [
        option for option in options
        if not option.get("is_bomb")
        and float(option.get("structure_cost") or 0.0) <= 0.0
        and option.get("groups_after") is not None
        and float(option["groups_after"]) <= groups_before + 0.01
    ]
    return cheap, options


def choose_tempo_endgame_guard_follow(state: dict, baseline: list[str]) -> list[str]:
    last_play = state.get("last_play") or []
    if not last_play or engine.relation_to_last(state) != "opponent":
        return baseline
    opponent_min = engine.min_opponent_count(state)
    if opponent_min > 6:
        return baseline
    cheap, options = cheap_guard_block_options(state)
    if cheap:
        return list(cheap[0]["cards"])
    try:
        last_player_count = engine.last_player_count(state)
    except Exception:
        last_player_count = 99
    if not baseline and options and opponent_min <= 3 and last_player_count <= 3:
        return list(options[0]["cards"])
    return baseline


def guard_lead_penalty(state: dict, cards: list[str]) -> float:
    if not cards:
        return 0.0
    hand = state.get("your_hand") or []
    level = state.get("level")
    opponent_counts = opponent_hand_counts(state)
    opponent_min = min(opponent_counts) if opponent_counts else 99
    size = len(cards)
    features = action_features(state, cards)
    penalty = 0.0
    exact_matches = [count for count in opponent_counts if count > 0 and count == size]
    if exact_matches:
        penalty += 180.0
        if any(count <= 8 for count in exact_matches):
            penalty += 420.0
    if opponent_min <= 8 and features["giving_control_to_strong_opponent_risk"]:
        penalty += 360.0
    if opponent_min <= 6 and size == 1:
        penalty += 260.0
    if engine.server_treats_as_bomb(cards, level) and len(cards) < len(hand):
        penalty += 80.0
    try:
        if engine.structure_cost(cards, hand, level) > 0:
            penalty += 260.0
    except Exception:
        penalty += 120.0
    try:
        groups_before = engine.estimate_remaining_groups(hand, level)
        groups_after = engine.estimate_remaining_groups(engine.remove_cards(hand, cards), level)
        if groups_after > groups_before + 0.01:
            penalty += 260.0 + (groups_after - groups_before) * 60.0
        else:
            penalty -= (groups_before - groups_after) * 80.0
    except Exception:
        penalty += 120.0
    return penalty


def choose_tempo_endgame_guard_lead(state: dict, baseline: list[str], profile: dict) -> list[str]:
    if not baseline or state.get("last_play"):
        return baseline
    hand = state.get("your_hand") or []
    level = state.get("level")
    if len(baseline) == len(hand):
        return baseline
    baseline_penalty = guard_lead_penalty(state, baseline)
    if baseline_penalty <= 0.0:
        return baseline

    candidates = [cards for cards in legal_candidate_actions(state) if cards]
    if not candidates:
        return baseline
    groups_before = engine.estimate_remaining_groups(hand, level)
    safe_candidates = []
    fallback_candidates = []
    for cards in candidates:
        if len(cards) == len(hand):
            return cards
        penalty = guard_lead_penalty(state, cards)
        try:
            remaining = engine.remove_cards(hand, cards)
            groups_after = engine.estimate_remaining_groups(remaining, level)
            structure_cost = engine.structure_cost(cards, hand, level)
        except Exception:
            groups_after = 999.0
            structure_cost = 999
        row = (penalty, groups_after, structure_cost, cards)
        fallback_candidates.append(row)
        if penalty <= 0.0 and structure_cost <= 0 and groups_after <= groups_before + 0.01:
            safe_candidates.append(row)

    pool = safe_candidates or fallback_candidates
    if not pool:
        return baseline
    if safe_candidates:
        return max(
            safe_candidates,
            key=lambda item: (
                score_action(state, item[3], profile),
                groups_before - item[1],
                -len(item[3]),
                engine.sort_cards(item[3], level),
            ),
        )[3]
    best_penalty, best_groups_after, _best_structure_cost, best_cards = min(
        pool,
        key=lambda item: (
            item[0],
            item[1],
            len(item[3]),
            engine.sort_cards(item[3], level),
        ),
    )
    if best_penalty < baseline_penalty:
        return best_cards
    return baseline


def choose_tempo_endgame_guard_play(state: dict, profile: dict) -> list[str]:
    baseline = engine.choose_play(state)
    if not is_tempo_endgame_guard_active(state):
        return baseline
    if state.get("last_play"):
        return choose_tempo_endgame_guard_follow(state, baseline)
    return choose_tempo_endgame_guard_lead(state, baseline, profile)


def is_tempo_shape_guard_active(state: dict) -> bool:
    tags = set(state.get("_scenario_tags") or [])
    return bool(
        "high_elo_loss_risk" in tags
        or "endgame_danger_high" in tags
        or any(count <= 8 for count in opponent_hand_counts(state))
        or len(state.get("your_hand") or []) <= 15
    )


def straight_protected_cards(hand: list[str], level: str) -> set[str]:
    rank_to_cards: dict[str, list[str]] = {rank: [] for rank in engine.RANKS}
    for card in hand:
        if card in {"B", "R"} or card == "H" + level:
            continue
        rank_to_cards[card_rank(card)].append(card)
    protected: set[str] = set()
    for seq in engine.sequence_windows(5):
        if all(rank_to_cards.get(rank) for rank in seq):
            for rank in seq:
                protected.update(rank_to_cards[rank])
    return protected


def potential_block_shape_score(hand: list[str], level: str) -> int:
    score = 0
    counts = rank_count_by_rank([card for card in hand if card not in {"B", "R"}])
    for rank, count in counts.items():
        if rank in {"2", level, "A"}:
            score += count
        if count >= 2:
            score += 1
        if count >= 3:
            score += 1
        if count >= 4:
            score += 2
    score += sum(2 for card in hand if card in {"B", "R"})
    return score


def shape_guard_action_risks(state: dict, cards: list[str]) -> dict:
    hand = state.get("your_hand") or []
    level = state.get("level")
    last_play = state.get("last_play") or []
    opponent_counts = opponent_hand_counts(state)
    remaining = engine.remove_cards(hand, cards) if cards else list(hand)
    groups_before = engine.estimate_remaining_groups(hand, level)
    groups_after = engine.estimate_remaining_groups(remaining, level)
    structure_cost = engine.structure_cost(cards, hand, level) if cards else 0
    protected_straight = straight_protected_cards(hand, level)
    breaks_straight = any(card in protected_straight for card in cards)
    before_block_score = potential_block_shape_score(hand, level)
    after_block_score = potential_block_shape_score(remaining, level)
    consumed_control = action_consumes_control_card(cards, level)
    broke_shape = bool(structure_cost > 0 or breaks_straight)
    consumed_potential = bool(after_block_score < before_block_score and (consumed_control or broke_shape))
    left_without_shape = bool(before_block_score > 0 and after_block_score <= 0)
    features = action_features(state, cards)
    exact_length = bool(not last_play and len(cards) in {count for count in opponent_counts if count > 0})
    gave_control = bool(features["giving_control_to_strong_opponent_risk"])
    return {
        "broke_pair_or_triple_or_straight": broke_shape,
        "consumed_2_or_joker_or_level_card": consumed_control,
        "consumed_potential_block_card": consumed_potential,
        "left_self_without_block_shape": left_without_shape,
        "did_increase_groups": groups_after > groups_before + 0.01,
        "did_reduce_groups": groups_after < groups_before - 0.01,
        "opened_exact_length_to_opponent": exact_length,
        "gave_strong_opponent_control": gave_control,
        "groups_before": groups_before,
        "groups_after": groups_after,
        "structure_cost": structure_cost,
        "remaining_count_after": len(remaining),
        "potential_block_score_before": before_block_score,
        "potential_block_score_after": after_block_score,
    }


def shape_guard_is_expensive(risks: dict) -> bool:
    return bool(
        risks["broke_pair_or_triple_or_straight"]
        or risks["consumed_2_or_joker_or_level_card"]
        or risks["consumed_potential_block_card"]
        or risks["left_self_without_block_shape"]
        or risks["did_increase_groups"]
    )


def shape_guard_safe_action(state: dict, cards: list[str], require_lead_safe: bool = False) -> bool:
    risks = shape_guard_action_risks(state, cards)
    if shape_guard_is_expensive(risks):
        return False
    if require_lead_safe and (
        risks["opened_exact_length_to_opponent"]
        or risks["gave_strong_opponent_control"]
    ):
        return False
    return risks["groups_after"] <= risks["groups_before"] + 0.01


def shape_guard_base_meta(triggered: bool) -> dict:
    return {
        "shape_guard_triggered": bool(triggered),
        "shape_guard_follow_declined_expensive_block": False,
        "shape_guard_follow_allowed_expensive_block": False,
        "shape_guard_safe_lead_chosen": False,
        "shape_guard_baseline_kept_no_safe_alt": False,
        "shape_guard_preserved_pair_triple_straight": False,
        "shape_guard_preserved_2_joker_level": False,
        "shape_guard_preserved_potential_block": False,
        "shape_guard_prevented_left_self_without_block_shape": False,
        "shape_guard_candidate_count": 0,
        "shape_guard_selected_count": 0,
    }


def mark_shape_preservation(meta: dict, baseline_risks: dict) -> None:
    if baseline_risks.get("broke_pair_or_triple_or_straight"):
        meta["shape_guard_preserved_pair_triple_straight"] = True
    if baseline_risks.get("consumed_2_or_joker_or_level_card"):
        meta["shape_guard_preserved_2_joker_level"] = True
    if baseline_risks.get("consumed_potential_block_card"):
        meta["shape_guard_preserved_potential_block"] = True
    if baseline_risks.get("left_self_without_block_shape"):
        meta["shape_guard_prevented_left_self_without_block_shape"] = True


def choose_tempo_shape_guard_follow(state: dict, baseline: list[str], meta: dict) -> list[str]:
    last_play = state.get("last_play") or []
    if not last_play or engine.relation_to_last(state) != "opponent":
        return baseline
    opponent_min = engine.min_opponent_count(state)
    if not baseline:
        return baseline
    baseline_risks = shape_guard_action_risks(state, baseline)
    baseline_expensive = shape_guard_is_expensive(baseline_risks)
    if not baseline_expensive:
        return baseline

    candidates = [cards for cards in legal_candidate_actions(state) if cards]
    safe_candidates = [cards for cards in candidates if shape_guard_safe_action(state, cards)]
    meta["shape_guard_candidate_count"] = len(safe_candidates)
    if safe_candidates:
        chosen = min(
            safe_candidates,
            key=lambda cards: (
                shape_guard_action_risks(state, cards)["groups_after"],
                engine.structure_cost(cards, state.get("your_hand") or [], state.get("level")),
                len(cards),
                engine.sort_cards(cards, state.get("level")),
            ),
        )
        meta["shape_guard_selected_count"] = 1
        mark_shape_preservation(meta, baseline_risks)
        return chosen

    remaining_after = len(state.get("your_hand") or []) - len(baseline)
    groups_after = baseline_risks["groups_after"]
    must_block = opponent_min <= 3 or engine.last_player_count(state) <= 3
    helps_finish = remaining_after == 0 or groups_after <= 1.5
    if must_block or helps_finish:
        meta["shape_guard_follow_allowed_expensive_block"] = True
        return baseline
    meta["shape_guard_follow_declined_expensive_block"] = True
    mark_shape_preservation(meta, baseline_risks)
    return []


def choose_tempo_shape_guard_lead(state: dict, baseline: list[str], meta: dict) -> list[str]:
    if not baseline or state.get("last_play"):
        return baseline
    hand = state.get("your_hand") or []
    level = state.get("level")
    if len(baseline) == len(hand):
        return baseline
    if engine.teammate_count(state) is not None and engine.teammate_count(state) <= 2:
        return baseline
    baseline_risks = shape_guard_action_risks(state, baseline)
    baseline_info = primary_play_info(baseline, level)
    baseline_close_finish = bool(
        baseline_risks["remaining_count_after"] <= 4
        or baseline_risks["groups_after"] <= 1.5
    )
    baseline_bad = bool(
        shape_guard_is_expensive(baseline_risks)
        or baseline_risks["opened_exact_length_to_opponent"]
        or baseline_risks["gave_strong_opponent_control"]
    )
    if not baseline_bad or baseline_close_finish:
        return baseline

    candidates = [cards for cards in legal_candidate_actions(state) if cards and len(cards) < len(hand)]
    safe_candidates = [
        cards for cards in candidates
        if shape_guard_safe_action(state, cards, require_lead_safe=True)
    ]
    meta["shape_guard_candidate_count"] = len(safe_candidates)
    if not safe_candidates:
        meta["shape_guard_baseline_kept_no_safe_alt"] = True
        return baseline

    if baseline_info and baseline_info.type in {"triple", "straight", "plate", "steel", "full_house"}:
        safe_singles = [
            cards for cards in safe_candidates
            if len(cards) == 1 and primary_play_info(cards, level) and primary_play_info(cards, level).type == "single"
        ]
        if safe_singles:
            safe_candidates = safe_singles

    chosen = max(
        safe_candidates,
        key=lambda cards: (
            shape_guard_action_risks(state, cards)["did_reduce_groups"],
            -shape_guard_action_risks(state, cards)["groups_after"],
            -len(cards),
            engine.sort_cards(cards, level),
        ),
    )
    meta["shape_guard_safe_lead_chosen"] = True
    meta["shape_guard_selected_count"] = 1
    mark_shape_preservation(meta, baseline_risks)
    return chosen


def choose_tempo_shape_guard_play(state: dict, profile: dict) -> list[str]:
    baseline = engine.choose_play(state)
    triggered = is_tempo_shape_guard_active(state)
    meta = shape_guard_base_meta(triggered)
    state["_shape_guard_meta"] = meta
    if not triggered:
        return baseline
    if state.get("last_play"):
        return choose_tempo_shape_guard_follow(state, baseline, meta)
    return choose_tempo_shape_guard_lead(state, baseline, meta)


def shape_guard_v2_base_meta() -> dict:
    return {
        "shape_guard_v2_blockless_lead_replaced": False,
        "shape_guard_v2_blockless_lead_kept_no_safe_alt": False,
        "shape_guard_v2_safe_alt_used_when_opponent_le3": False,
        "shape_guard_v2_safe_alt_rejected_reason_counts": {},
    }


def shape_guard_v2_rejection_reasons(state: dict, cards: list[str], original_risks: dict) -> list[str]:
    risks = shape_guard_action_risks(state, cards)
    reasons = []
    if risks["opened_exact_length_to_opponent"]:
        reasons.append("opened_exact_length_to_opponent")
    if risks["gave_strong_opponent_control"]:
        reasons.append("gave_strong_opponent_control")
    if risks["consumed_2_or_joker_or_level_card"]:
        reasons.append("consumed_2_or_joker_or_level_card")
    if risks["consumed_potential_block_card"]:
        reasons.append("consumed_potential_block_card")
    if risks["broke_pair_or_triple_or_straight"]:
        reasons.append("broke_pair_or_triple_or_straight")
    if risks["left_self_without_block_shape"]:
        reasons.append("left_self_without_block_shape")
    if risks["groups_after"] > float(original_risks["groups_after"]) + 1.0:
        reasons.append("remaining_groups_after_gt_original_plus_1")
    if risks["groups_after"] > risks["groups_before"] + 0.01:
        reasons.append("remaining_groups_increased")
    return reasons


def choose_tempo_shape_guard_v2_lead(
    state: dict,
    shape_choice: list[str],
    baseline: list[str],
    meta: dict,
    v2_meta: dict,
) -> list[str]:
    if state.get("last_play") or not shape_choice:
        return shape_choice
    hand = state.get("your_hand") or []
    if len(hand) < 10:
        return shape_choice
    opponent_counts = opponent_hand_counts(state)
    if not opponent_counts or min(opponent_counts) > 3:
        return shape_choice
    if engine.teammate_count(state) is not None and engine.teammate_count(state) <= 2:
        return shape_choice

    baseline_risks = shape_guard_action_risks(state, baseline) if baseline else {}
    original_risks = shape_guard_action_risks(state, shape_choice)
    if not (
        original_risks["left_self_without_block_shape"]
        or baseline_risks.get("left_self_without_block_shape")
    ):
        return shape_choice

    candidates = [cards for cards in legal_candidate_actions(state) if cards and len(cards) < len(hand)]
    safe_candidates = []
    rejected = Counter()
    for cards in candidates:
        if cards == shape_choice:
            continue
        reasons = shape_guard_v2_rejection_reasons(state, cards, original_risks)
        if reasons:
            rejected.update(reasons)
            continue
        safe_candidates.append(cards)

    v2_meta["shape_guard_v2_safe_alt_rejected_reason_counts"] = dict(rejected)
    if not safe_candidates:
        v2_meta["shape_guard_v2_blockless_lead_kept_no_safe_alt"] = True
        return shape_choice

    chosen = min(
        safe_candidates,
        key=lambda cards: (
            shape_guard_action_risks(state, cards)["groups_after"],
            -len(cards),
            engine.sort_cards(cards, state.get("level")),
        ),
    )
    v2_meta["shape_guard_v2_blockless_lead_replaced"] = True
    v2_meta["shape_guard_v2_safe_alt_used_when_opponent_le3"] = True
    meta["shape_guard_selected_count"] = 1
    meta["shape_guard_candidate_count"] = max(int(meta.get("shape_guard_candidate_count") or 0), len(safe_candidates))
    mark_shape_preservation(meta, original_risks)
    return chosen


def choose_tempo_shape_guard_v2_play(state: dict, profile: dict) -> list[str]:
    baseline = engine.choose_play(state)
    triggered = is_tempo_shape_guard_active(state)
    meta = shape_guard_base_meta(triggered)
    v2_meta = shape_guard_v2_base_meta()
    state["_shape_guard_meta"] = meta
    state["_shape_guard_v2_meta"] = v2_meta
    if not triggered:
        return baseline
    if state.get("last_play"):
        return choose_tempo_shape_guard_follow(state, baseline, meta)
    shape_choice = choose_tempo_shape_guard_lead(state, baseline, meta)
    return choose_tempo_shape_guard_v2_lead(state, shape_choice, baseline, meta, v2_meta)


def plate_delay_guard_base_meta() -> dict:
    return {
        "plate_delay_guard_triggered": False,
        "plate_delay_guard_selected": False,
        "plate_delay_guard_no_safe_single": False,
        "plate_delay_guard_candidate_count": 0,
        "plate_delay_guard_original_plate_rank_counts": {},
        "plate_delay_guard_selected_single_rank_counts": {},
    }


def plate_delay_has_required_scenario(state: dict) -> bool:
    tags = set(state.get("_scenario_tags") or [])
    return "endgame_danger_high" in tags and "high_elo_loss_risk" in tags


def live_plate_delay_baseline_risks(state: dict, baseline: list[str]) -> dict:
    risks = shape_guard_action_risks(state, baseline)
    consumed = bool(risks.get("consumed_potential_block_card"))
    risks["consumed_potential_block_card"] = consumed
    risks["left_self_without_block_shape"] = bool(risks.get("left_self_without_block_shape") or consumed)
    return risks


def low_single_delay_candidates(state: dict, baseline_groups_after: float | None) -> list[tuple[dict, list[str]]]:
    hand = state.get("your_hand") or []
    level = state.get("level")
    candidates: list[tuple[dict, list[str]]] = []
    for card in engine.sort_cards(hand, level):
        if not is_low_single_card(card, level):
            continue
        cards = [card]
        info = play_info_for_cards(cards, [], level)
        if not info or info.type != "single":
            continue
        risks = shape_guard_action_risks(state, cards)
        if risks["opened_exact_length_to_opponent"]:
            continue
        if risks["gave_strong_opponent_control"]:
            continue
        if risks["consumed_2_or_joker_or_level_card"]:
            continue
        if risks["consumed_potential_block_card"]:
            continue
        if risks["broke_pair_or_triple_or_straight"]:
            continue
        if baseline_groups_after is not None and risks["groups_after"] > baseline_groups_after + 1.0:
            continue
        candidates.append((risks, cards))
    candidates.sort(
        key=lambda item: (
            item[0]["groups_after"],
            engine.rank_value(play_info_for_cards(item[1], [], level), level),
            item[1],
        )
    )
    return candidates


def choose_tempo_plate_delay_guard_play(state: dict, profile: dict) -> list[str]:
    baseline = engine.choose_play(state)
    meta = plate_delay_guard_base_meta()
    state["_plate_delay_guard_meta"] = meta
    hand = state.get("your_hand") or []
    level = state.get("level")
    last_play = state.get("last_play") or []
    if last_play or not baseline or not plate_delay_has_required_scenario(state):
        return baseline
    info = play_info_for_cards(baseline, [], level)
    if not info or info.type != "plate" or len(baseline) != 6:
        return baseline
    self_count = len(hand)
    if self_count < 9 or self_count > 15:
        return baseline
    opponent_counts = opponent_hand_counts(state)
    if not opponent_counts or min(opponent_counts) > 7:
        return baseline
    risks = live_plate_delay_baseline_risks(state, baseline)
    if not risks["consumed_potential_block_card"] or not risks["left_self_without_block_shape"]:
        return baseline

    meta["plate_delay_guard_triggered"] = True
    meta["plate_delay_guard_original_plate_rank_counts"] = {str(info.rank): 1}
    candidates = low_single_delay_candidates(state, risks.get("groups_after"))
    meta["plate_delay_guard_candidate_count"] = len(candidates)
    if not candidates:
        meta["plate_delay_guard_no_safe_single"] = True
        return baseline
    selected = candidates[0][1]
    selected_info = play_info_for_cards(selected, [], level)
    meta["plate_delay_guard_selected"] = True
    if selected_info:
        meta["plate_delay_guard_selected_single_rank_counts"] = {str(selected_info.rank): 1}
    return selected


def rank_count_by_rank(cards: list[str]) -> Counter:
    counts = Counter()
    for card in cards:
        counts[card_rank(card)] += 1
    return counts


def is_bait_candidate_card(card: str, hand: list[str], level: str) -> bool:
    rank = card_rank(card)
    if card in {"B", "R"} or rank == level or card == "H" + level:
        return False
    if rank not in {"J", "Q", "K", "A"}:
        return False
    if rank_count_by_rank(hand)[rank] != 1:
        return False
    before = engine.estimate_remaining_groups(hand, level)
    after = engine.estimate_remaining_groups(engine.remove_cards(hand, [card]), level)
    return after <= before + 0.01


def choose_bait_high_card_play(state: dict) -> list[str] | None:
    hand = state.get("your_hand") or []
    level = state.get("level")
    if state.get("last_play") or len(hand) <= 10:
        return None
    if engine.min_opponent_count(state) <= 6:
        return None
    if (state.get("_research_context") or {}).get("high_elo_risk"):
        return None
    opponent_counts = opponent_hand_counts(state)
    if any(count <= 6 for count in opponent_counts):
        return None
    candidates = [card for card in hand if is_bait_candidate_card(card, hand, level)]
    if not candidates:
        return None
    rank_preference = {"J": 0, "Q": 1, "K": 2, "A": 3}
    candidates.sort(key=lambda card: (rank_preference.get(card_rank(card), 99), engine.sort_cards([card], level)))
    return [candidates[0]]


def bait_high_card_v2_candidate_cards(state: dict) -> tuple[list[str], list[str]]:
    hand = state.get("your_hand") or []
    level = state.get("level")
    reasons: list[str] = []
    scenario_tags_value = set(state.get("_scenario_tags") or [])
    opponent_counts = opponent_hand_counts(state)
    teammate_count_value = engine.teammate_count(state)

    if state.get("_post_bait_lockdown"):
        reasons.append("post_bait_lockdown")
    if state.get("last_play"):
        reasons.append("not_free_lead")
    if "high_elo_loss_risk" in scenario_tags_value:
        reasons.append("high_elo_loss_risk")
    if "endgame_danger_high" in scenario_tags_value:
        reasons.append("endgame_danger_high")
    if any(count <= 8 for count in opponent_counts):
        reasons.append("opponent_count_le_8")
    if len(hand) <= 14:
        reasons.append("self_count_le_14")
    if teammate_count_value <= 6:
        reasons.append("teammate_count_le_6")

    raw_candidates = [card for card in hand if is_bait_candidate_card(card, hand, level)]
    if not raw_candidates:
        reasons.append("no_lonely_jqka")

    safe_candidates: list[str] = []
    for card in raw_candidates:
        features = action_features(state, [card])
        if features["groups_after"] > engine.estimate_remaining_groups(hand, level) + 0.01:
            continue
        if features["bad_lead_size_risk"]:
            continue
        if features["giving_control_to_strong_opponent_risk"]:
            continue
        if len([card]) in {count for count in opponent_counts if count > 0}:
            continue
        safe_candidates.append(card)
    if raw_candidates and not safe_candidates:
        reasons.append("no_safe_bait_candidate")

    if reasons:
        return [], reasons
    rank_preference = {"J": 0, "Q": 1, "K": 2, "A": 3}
    safe_candidates.sort(key=lambda card: (rank_preference.get(card_rank(card), 99), engine.sort_cards([card], level)))
    return safe_candidates, []


def choose_bait_high_card_v2_play(state: dict) -> list[str] | None:
    if state.get("_post_bait_lockdown"):
        return None
    candidates, _ = bait_high_card_v2_candidate_cards(state)
    if not candidates:
        return None
    return [candidates[0]]


def choose_post_bait_lockdown_play(state: dict, profile: dict) -> list[str]:
    baseline = engine.choose_play(state)
    hand = state.get("your_hand") or []
    level = state.get("level")
    last_play = state.get("last_play") or []
    opponent_min = engine.min_opponent_count(state)

    if last_play:
        if engine.relation_to_last(state) == "opponent" and opponent_min <= 6 and not baseline:
            blockers = [cards for cards in legal_candidate_actions(state) if cards]
            if blockers:
                return max(
                    blockers,
                    key=lambda cards: (
                        score_action(state, cards, profile),
                        -len(cards),
                        engine.sort_cards(cards, level),
                    ),
                )
        return baseline

    features = action_features(state, baseline)
    unsafe_baseline = bool(
        features["bad_lead_size_risk"]
        or features["giving_control_to_strong_opponent_risk"]
        or (baseline and len(baseline) in {count for count in opponent_hand_counts(state) if count > 0})
        or (opponent_min <= 8 and len(baseline) == 1)
    )
    if not unsafe_baseline:
        return baseline

    groups_before = engine.estimate_remaining_groups(hand, level)
    safe_candidates = []
    for cards in legal_candidate_actions(state):
        if not cards:
            continue
        candidate_features = action_features(state, cards)
        if candidate_features["bad_lead_size_risk"] or candidate_features["giving_control_to_strong_opponent_risk"]:
            continue
        if len(cards) in {count for count in opponent_hand_counts(state) if count > 0}:
            continue
        if opponent_min <= 8 and len(cards) == 1:
            continue
        if candidate_features["groups_after"] > groups_before + 0.01:
            continue
        safe_candidates.append(cards)
    if not safe_candidates:
        return baseline
    return max(
        safe_candidates,
        key=lambda cards: (
            score_action(state, cards, profile)
            - action_features(state, cards)["bad_lead_size_risk"] * 80
            - action_features(state, cards)["giving_control_to_strong_opponent_risk"] * 80,
            -len(cards),
            engine.sort_cards(cards, level),
        ),
    )


def action_features(state: dict, cards: list[str]) -> dict:
    hand = state.get("your_hand") or []
    level = state.get("level")
    last_play = state.get("last_play") or []
    remaining = engine.remove_cards(hand, cards) if cards else hand
    groups_before = engine.estimate_remaining_groups(hand, level)
    groups_after = engine.estimate_remaining_groups(remaining, level)
    relation = engine.relation_to_last(state)
    opponent_counts = opponent_hand_counts(state)
    size = len(cards)
    is_bomb = bool(cards) and engine.server_treats_as_bomb(cards, level)
    return {
        "remaining_group_reduction": groups_before - groups_after,
        "self_first_out_gain": 100.0 if cards and not remaining else 0.0,
        "ally_first_out_gain": 20.0 if relation == "teammate" and not cards else 0.0,
        "opponent_block_score": 35.0 if relation == "opponent" and last_play and cards else 0.0,
        "opponent_first_out_risk": 30.0 if not cards and engine.min_opponent_count(state) <= 2 else 0.0,
        "endgame_defense_score": max(0.0, 8.0 - engine.min_opponent_count(state)) * 6.0,
        "control_gain_score": 8.0 if cards else 0.0,
        "bad_lead_size_risk": 1.0 if not last_play and size in {c for c in opponent_counts if 0 < c <= 6} else 0.0,
        "teammate_override_risk": 1.0 if relation == "teammate" and cards else 0.0,
        "useless_bomb_risk": 1.0 if is_bomb and engine.min_opponent_count(state) > 4 and groups_after > 2.0 else 0.0,
        "giving_control_to_strong_opponent_risk": 1.0 if not last_play and size <= engine.min_opponent_count(state) <= 4 else 0.0,
        "is_bomb": is_bomb,
        "groups_after": groups_after,
    }


def score_action(state: dict, cards: list[str], profile: dict) -> float:
    features = action_features(state, cards)
    ally_reliability = profile.get("ally_reliability_base", 0.65)
    return (
        features["self_first_out_gain"] * profile.get("self_sprint_weight", 1.0)
        + features["ally_first_out_gain"] * ally_reliability * profile.get("teammate_help_weight", 1.0)
        + features["opponent_block_score"] * profile.get("opponent_block_weight", 1.0)
        - features["opponent_first_out_risk"] * profile.get("opponent_risk_weight", 1.0)
        + features["endgame_defense_score"] * profile.get("endgame_defense_weight", 1.0)
        + features["control_gain_score"]
        + features["remaining_group_reduction"] * profile.get("remaining_group_weight", 28)
        - features["bad_lead_size_risk"] * profile.get("bad_lead_size_penalty", 18.0)
        - features["teammate_override_risk"] * profile.get("teammate_override_penalty", 28.0)
        - features["useless_bomb_risk"] * profile.get("useless_bomb_penalty", 35.0)
        - features["giving_control_to_strong_opponent_risk"]
        * profile.get("giving_control_to_strong_opponent_penalty", 24.0)
    )


def decision_mode_for(profile_name: str, tags: list[str]) -> str:
    if "high_elo_loss_risk" in tags or profile_name in {"defense_heavy", "anti_strong_opponent", "endgame_defense"}:
        return "defense"
    if profile_name == "ally_support":
        return "ally_support"
    if profile_name == "self_sprint":
        return "self_carry"
    return "balanced"


def legal_candidate_actions(state: dict) -> list[list[str]]:
    hand = state.get("your_hand") or []
    level = state.get("level")
    last_play = state.get("last_play") or []
    options: list[list[str]] = []
    seen = set()

    all_out = engine.choose_all_out_if_possible(hand, last_play, level)
    if all_out is not None:
        return [all_out]

    if last_play:
        options.append([])
    for info in engine.legal_play_options(hand, level):
        cards = list(info.cards)
        key = tuple(sorted(cards))
        if key in seen:
            continue
        if last_play and not engine.play_beats(cards, last_play, level):
            continue
        seen.add(key)
        options.append(cards)
    return options or [[]]


def choose_profiled_play(state: dict, profile_name: str, profile: dict) -> list[str]:
    apply_profile(profile_name, profile)
    if profile_name == "tempo_baseline":
        return engine.choose_play(state)
    if profile_name == "tempo_high_elo_safe":
        return choose_high_elo_safe_play(state, profile)
    if profile_name == "tempo_endgame_guard":
        return choose_tempo_endgame_guard_play(state, profile)
    if profile_name == "tempo_shape_guard":
        return choose_tempo_shape_guard_play(state, profile)
    if profile_name == "tempo_shape_guard_v2":
        return choose_tempo_shape_guard_v2_play(state, profile)
    if profile_name == "tempo_plate_delay_guard":
        return choose_tempo_plate_delay_guard_play(state, profile)
    if profile_name == "bait_high_card":
        bait = choose_bait_high_card_play(state)
        if bait is not None:
            return bait
        return engine.choose_play(state)
    if profile_name == "bait_high_card_v2":
        bait = choose_bait_high_card_v2_play(state)
        if bait is not None:
            return bait
        if state.get("_post_bait_lockdown"):
            return choose_post_bait_lockdown_play(state, profile)
        return engine.choose_play(state)

    candidates = legal_candidate_actions(state)
    if len(candidates) == 1:
        return candidates[0]
    ranked = [
        (score_action(state, cards, profile), -len(cards), engine.sort_cards(cards, state["level"]), cards)
        for cards in candidates
    ]
    return max(ranked, key=lambda item: (item[0], item[1], item[2]))[3]


def bait_metadata(state: dict, profile_name: str, coord: list[str]) -> dict:
    if profile_name not in {"bait_high_card", "bait_high_card_v2"} or not coord:
        return {}
    level = state.get("level")
    info = primary_play_info(coord, level)
    if not info or info.type not in {"single", "pair"}:
        return {}
    if state.get("last_play"):
        return {}
    before = engine.estimate_remaining_groups(state.get("your_hand") or [], level)
    after = engine.estimate_remaining_groups(engine.remove_cards(state.get("your_hand") or [], coord), level)
    rank = info.rank
    if profile_name == "bait_high_card_v2" and info.type != "single":
        return {}
    if info.type == "single" and rank not in {"J", "Q", "K", "A"}:
        return {}
    return {
        "bait_play": coord,
        "bait_play_type": info.type,
        "bait_rank": rank,
        "bait_groups_before": before,
        "bait_groups_after": after,
        "bait_structure_worse": after > before + 0.01,
        "bait_attempted": True,
        "bait_selected": True,
        "bait_candidate_found": True,
    }


def bait_candidate_scan(state: dict, profile_name: str = "bait_high_card") -> tuple[bool, list[str]]:
    if profile_name == "bait_high_card_v2":
        candidates, reasons = bait_high_card_v2_candidate_cards(state)
        return bool(candidates), reasons
    hand = state.get("your_hand") or []
    level = state.get("level")
    reasons: list[str] = []
    if state.get("last_play"):
        reasons.append("not_free_lead")
    if len(hand) <= 10:
        reasons.append("hand_le_10")
    if engine.min_opponent_count(state) <= 6:
        reasons.append("opponent_min_le_6")
    if (state.get("_research_context") or {}).get("high_elo_risk"):
        reasons.append("high_elo_risk")
    opponent_counts = opponent_hand_counts(state)
    if any(count <= 6 for count in opponent_counts):
        reasons.append("opponent_count_le_6")
    if not any(is_bait_candidate_card(card, hand, level) for card in hand):
        reasons.append("no_lonely_mid_high_single")
    return not reasons, reasons


def bait_attempt_observation_metadata(state: dict, profile_name: str, coord: list[str], decision: dict) -> dict:
    metadata: dict[str, Any] = {}
    if decision.get("lead_probe_event", {}).get("is_candidate_bait"):
        metadata["bait_candidate_found"] = True
    if profile_name not in {"bait_high_card", "bait_high_card_v2"}:
        return metadata
    candidate_found, reasons = bait_candidate_scan(state, profile_name)
    metadata["bait_candidate_found"] = bool(metadata.get("bait_candidate_found") or candidate_found)
    if not decision.get("bait_selected"):
        metadata["bait_attempted"] = False
        metadata["bait_selected"] = False
        metadata["bait_not_attempted_reasons"] = reasons or ["candidate_not_selected"]
    if not candidate_found:
        metadata["bait_no_candidate_reasons"] = reasons
    return metadata


def rank_gap(low_rank: str | None, high_rank: str | None, level: str) -> int | None:
    order = engine.game_rank_index(level)
    if low_rank not in order or high_rank not in order:
        return None
    return order[high_rank] - order[low_rank]


def is_level_card_play(cards: list[str], response_info: Any, level: str) -> bool:
    if any(card not in {"B", "R"} and card_rank(card) == level for card in cards):
        return True
    return bool(response_info and response_info.rank == level)


def is_joker_play(cards: list[str], response_info: Any) -> bool:
    if any(card in {"B", "R"} for card in cards):
        return True
    return bool(response_info and response_info.rank in {"B", "R"})


def bait_candidate_result(state: dict, coord: list[str], info: Any) -> tuple[bool, str | None]:
    reasons: list[str] = []
    hand = state.get("your_hand") or []
    level = state.get("level")
    opponent_counts = opponent_hand_counts(state)
    before = engine.estimate_remaining_groups(hand, level)
    after = engine.estimate_remaining_groups(engine.remove_cards(hand, coord), level)
    early_or_midgame = len(hand) > 10 and bool(opponent_counts) and min(opponent_counts) > 6

    if state.get("last_play"):
        reasons.append("not_lead")
    if not early_or_midgame:
        reasons.append("not_early_or_midgame")
    if (state.get("_research_context") or {}).get("high_elo_risk"):
        reasons.append("high_elo_risk")
    if engine.server_treats_as_bomb(coord, level):
        reasons.append("bomb_play")
    if after > before + 0.01:
        reasons.append("structure_cost")

    rank = info.rank if info else None
    if info and info.type == "single":
        card = coord[0]
        if card in {"B", "R"}:
            reasons.append("joker")
        if rank == level or card == "H" + level:
            reasons.append("level_or_wild")
        if rank not in {"J", "Q", "K", "A"}:
            reasons.append("rank_not_mid_high_single")
        if rank_count_by_rank(hand)[rank] != 1:
            reasons.append("not_lonely_single")
    elif info and info.type == "pair":
        if rank == level:
            reasons.append("level_pair")
        if rank not in {"T", "J", "Q", "K", "A"}:
            reasons.append("rank_not_mid_high_pair")
        if rank_count_by_rank(hand)[rank] != 2:
            reasons.append("not_exact_pair")
    else:
        reasons.append("unsupported_type")

    return not reasons, ";".join(reasons) if reasons else None


def lead_probe_metadata(
    state: dict,
    game_id: str,
    turn_index: int,
    profile_name: str,
    scenario: str,
    coord: list[str],
) -> dict:
    if state.get("last_play") or not coord:
        return {}
    level = state.get("level")
    info = primary_play_info(coord, level)
    if not info or info.type not in {"single", "pair"}:
        return {}
    hand = state.get("your_hand") or []
    opponent_counts = opponent_hand_counts(state)
    remaining = engine.remove_cards(hand, coord)
    early_or_midgame = len(hand) > 10 and bool(opponent_counts) and min(opponent_counts) > 6
    is_candidate, reason = bait_candidate_result(state, coord, info)
    event = {
        "game_id": str(game_id),
        "turn_index": turn_index,
        "profile": profile_name,
        "scenario": scenario,
        "my_play": list(coord),
        "my_play_type": info.type,
        "my_play_rank": info.rank,
        "my_remaining_count": len(remaining),
        "opponent_remaining_counts": opponent_counts,
        "is_early_or_midgame": early_or_midgame,
        "is_candidate_bait": is_candidate,
        "bait_candidate_found": is_candidate,
        "reason_if_not_candidate_bait": reason,
        "history_start_index": len(state.get("trick_history") or []),
        "opponent_responses": [],
    }
    return {
        "lead_probe_event": event,
        "lead_probe": True,
        "lead_probe_is_candidate_bait": is_candidate,
        "bait_candidate_found": is_candidate,
        "lead_probe_reason_if_not_candidate_bait": reason,
    }


def is_high_card_response(response_cards: list[str], response_info: Any, level: str) -> bool:
    if any(card_rank(card) in high_control_ranks(level) for card in response_cards):
        return True
    if response_info and response_info.rank in high_control_ranks(level):
        return True
    return False


def is_obvious_overblock(bait_decision: dict, response_cards: list[str], level: str) -> bool:
    response_info = primary_play_info(response_cards, level)
    if not response_info:
        return False
    if engine.server_treats_as_bomb(response_cards, level):
        return True
    bait_type = bait_decision.get("bait_play_type")
    bait_rank = bait_decision.get("bait_rank")
    response_rank = response_info.rank
    if bait_type == "single" and response_info.type == "single":
        if bait_rank in {"J", "Q", "K"} and response_rank in high_control_ranks(level):
            return True
        if bait_rank == "A" and response_rank in {"2", level, "B", "R"}:
            return True
    if bait_type == "pair" and response_info.type == "pair":
        rank_index = engine.game_rank_index(level)
        return rank_index.get(response_rank, 0) - rank_index.get(str(bait_rank), 0) >= 3
    return False


def response_event_from_cards(
    state: dict,
    probe_decision: dict,
    responder_seat: int,
    response_cards: list[str],
    responder_remaining: int | None,
) -> dict | None:
    level = state.get("level")
    probe = probe_decision.get("lead_probe_event") or {}
    my_play = probe.get("my_play") or []
    if not my_play or not response_cards:
        return None
    response_info = primary_play_info(response_cards, level)
    response_is_bomb = bool(engine.server_treats_as_bomb(response_cards, level))
    try:
        response_beats = bool(engine.play_beats(response_cards, my_play, level))
    except Exception:
        response_beats = False
    event = {
        "responder_seat": responder_seat,
        "response_play": list(response_cards),
        "response_type": response_info.type if response_info else None,
        "response_rank": response_info.rank if response_info else None,
        "response_is_high_card": is_high_card_response(response_cards, response_info, level),
        "response_is_level_card": is_level_card_play(response_cards, response_info, level),
        "response_is_joker": is_joker_play(response_cards, response_info),
        "response_is_bomb": response_is_bomb,
        "response_beats_my_play": response_beats,
        "response_rank_gap": rank_gap(probe.get("my_play_rank"), response_info.rank if response_info else None, level),
        "responder_remaining_count_after": responder_remaining,
    }
    reason = possible_overblock_reason(state, probe, event)
    if reason:
        event["possible_overblock_event"] = True
        event["possible_overblock_reason"] = reason
    else:
        event["possible_overblock_event"] = False
    return event


def possible_overblock_reason(state: dict, probe: dict, response_event: dict) -> str | None:
    if not response_event.get("response_beats_my_play"):
        return None
    level = state.get("level")
    my_type = probe.get("my_play_type")
    my_rank = probe.get("my_play_rank")
    response_type = response_event.get("response_type")
    response_rank = response_event.get("response_rank")
    my_is_bomb = bool(engine.server_treats_as_bomb(probe.get("my_play") or [], level))

    if not my_is_bomb and response_event.get("response_is_bomb"):
        return "bomb_response_to_non_bomb"
    if my_type == "single" and response_type == "single":
        if my_rank in {"J", "Q", "K"} and (
            response_rank in high_control_ranks(level)
            or response_event.get("response_is_joker")
            or response_event.get("response_is_level_card")
        ):
            return "single_jqk_beaten_by_control"
        if my_rank == "A" and (
            response_rank in {"2", level, "B", "R"}
            or response_event.get("response_is_joker")
            or response_event.get("response_is_level_card")
        ):
            return "single_a_beaten_by_control"
    if my_type == "pair" and response_type == "pair":
        gap = response_event.get("response_rank_gap")
        if my_rank in {"T", "J", "Q", "K", "A"} and gap is not None and gap >= 2:
            return "mid_high_pair_beaten_by_two_plus_ranks"
    if probe.get("is_candidate_bait") and response_event.get("response_is_high_card"):
        return "candidate_bait_beaten_by_control"
    return None


def append_probe_response(
    state: dict,
    probe_decision: dict,
    responder_seat: int,
    response_cards: list[str],
    responder_remaining: int | None,
) -> None:
    probe = probe_decision.get("lead_probe_event")
    if not probe:
        return
    event = response_event_from_cards(state, probe_decision, responder_seat, response_cards, responder_remaining)
    if not event:
        return
    key = json.dumps(
        [
        event["responder_seat"],
        event["response_play"],
        event.get("response_type"),
        event.get("response_rank"),
        ],
        ensure_ascii=False,
    )
    seen = set(str(item) for item in probe.setdefault("_response_seen_keys", []))
    if key in seen:
        return
    probe.setdefault("opponent_responses", []).append(event)
    probe["_response_seen_keys"] = sorted(seen | {key})
    if event.get("possible_overblock_event"):
        probe_decision["possible_overblock_event"] = True
        probe_decision.setdefault("possible_overblock_events", []).append(event)


def observe_lead_probe_responses(state: dict, decisions: list[dict]) -> None:
    if not decisions:
        return
    active_decisions = [
        decision for decision in decisions
        if decision.get("lead_probe_event") and not decision.get("lead_probe_closed")
    ]
    if not active_decisions:
        return

    hand_counts = state.get("hand_counts") or []
    opponent_set = set(opponent_seats(state))
    history = state.get("trick_history") or []
    your_seat = state.get("your_seat")
    try:
        your_seat = int(your_seat)
    except (TypeError, ValueError):
        your_seat = None

    for decision in active_decisions:
        probe = decision.get("lead_probe_event") or {}
        my_play = probe.get("my_play") or []
        start_index = int(probe.get("history_start_index") or 0)
        seen_own_play = False
        pass_run = 0
        if history and your_seat is not None:
            for entry in history[start_index:]:
                if not isinstance(entry, (list, tuple)) or len(entry) < 2:
                    continue
                try:
                    seat = int(entry[0])
                except (TypeError, ValueError):
                    continue
                cards = list(entry[1] or [])
                if not seen_own_play:
                    if seat == your_seat and cards == my_play:
                        seen_own_play = True
                    continue
                if not cards:
                    pass_run += 1
                    if pass_run >= 3:
                        decision["lead_probe_closed"] = True
                        break
                    continue
                if pass_run >= 3:
                    decision["lead_probe_closed"] = True
                    break
                pass_run = 0
                if seat not in opponent_set:
                    continue
                responder_remaining = None
                append_probe_response(state, decision, seat, cards, responder_remaining)

        last_player = state.get("last_player")
        response_cards = state.get("last_play") or []
        if last_player is not None and response_cards and response_cards != my_play:
            try:
                responder_seat = int(last_player)
            except (TypeError, ValueError):
                responder_seat = None
            if responder_seat in opponent_set:
                try:
                    responder_remaining = int(hand_counts[responder_seat])
                except (IndexError, TypeError, ValueError):
                    responder_remaining = None
                append_probe_response(state, decision, responder_seat, response_cards, responder_remaining)


def update_model_for_overblock(
    state: dict,
    models: dict[int, PlayerModel],
    opponent_seat: int,
    response_cards: list[str],
) -> None:
    model = models.get(opponent_seat)
    if not model:
        return
    level = state.get("level")
    adjust_model(model, "overblock_rate", 0.04)
    if len(state.get("your_hand") or []) > 10 and engine.min_opponent_count(state) > 6:
        if is_high_card_response(response_cards, primary_play_info(response_cards, level), level):
            adjust_model(model, "high_card_spend_early_rate", 0.04)
            adjust_model(model, "control_preservation_score", -0.03)
        if engine.server_treats_as_bomb(response_cards, level):
            adjust_model(model, "bomb_spend_early_rate", 0.04)
            adjust_model(model, "control_preservation_score", -0.04)


def observe_opponent_overblock(state: dict, decisions: list[dict], models: dict[int, PlayerModel]) -> None:
    if not decisions:
        return
    bait_decision = None
    for decision in reversed(decisions):
        if decision.get("bait_play") and not decision.get("bait_overblock_checked"):
            bait_decision = decision
            break
    if not bait_decision:
        return
    last_player = state.get("last_player")
    response_cards = state.get("last_play") or []
    if last_player is None or not response_cards:
        return
    try:
        opponent_seat = int(last_player)
    except (TypeError, ValueError):
        return
    if opponent_seat not in opponent_seats(state):
        return
    if response_cards == bait_decision.get("bait_play"):
        return
    level = state.get("level")
    response_info = primary_play_info(response_cards, level)
    bait_decision["bait_overblock_checked"] = True
    if not is_obvious_overblock(bait_decision, response_cards, level):
        bait_decision["opponent_overblock_event"] = False
        return
    hand_counts = state.get("hand_counts") or []
    try:
        opponent_remaining = int(hand_counts[opponent_seat])
    except (IndexError, TypeError, ValueError):
        opponent_remaining = None
    event = {
        "opponent_overblock_event": True,
        "bait_play": bait_decision.get("bait_play"),
        "bait_play_type": bait_decision.get("bait_play_type"),
        "bait_rank": bait_decision.get("bait_rank"),
        "opponent_response": response_cards,
        "opponent_response_rank": response_info.rank if response_info else None,
        "opponent_response_type": response_info.type if response_info else None,
        "opponent_seat": opponent_seat,
        "opponent_remaining_count": opponent_remaining,
        "was_high_card_spent": is_high_card_response(response_cards, response_info, level),
        "was_bomb_spent": bool(engine.server_treats_as_bomb(response_cards, level)),
        "later_opponent_lost_control": False,
    }
    bait_decision.update(event)
    bait_decision["opponent_overblock_event_details"] = event
    update_model_for_overblock(state, models, opponent_seat, response_cards)


def update_models_from_state(state: dict, models: dict[int, PlayerModel]) -> None:
    hand_counts = state.get("hand_counts") or []
    last_player = state.get("last_player")
    last_play = state.get("last_play") or []
    if last_player is None or not last_play:
        return
    try:
        seat = int(last_player)
        remaining = int(hand_counts[seat])
    except (IndexError, TypeError, ValueError):
        return
    model = models.get(seat)
    if not model:
        return
    if engine.server_treats_as_bomb(last_play, state["level"]):
        adjust_model(model, "bomb_style", 0.03)
        if remaining > 8:
            adjust_model(model, "riskiness", 0.02)
        if engine.min_opponent_count(state) <= 3:
            adjust_model(model, "overall_skill", 0.02)
            adjust_model(model, "endgame_skill", 0.02)
        if remaining > 10:
            adjust_model(model, "aggression", 0.02)
    if remaining <= 4:
        adjust_model(model, "endgame_skill", 0.01)
    if remaining <= 3 and not engine.server_treats_as_bomb(last_play, state["level"]):
        adjust_model(model, "aggression", 0.01)
    relation = engine.relation_to_last(state)
    if relation == "teammate" and remaining <= 3:
        adjust_model(model, "cooperation", 0.01)
    if relation == "opponent" and remaining <= 3:
        adjust_model(model, "overall_skill", 0.01)
        adjust_model(model, "endgame_skill", 0.01)


def mark_game_seen(models: dict[int, PlayerModel]) -> None:
    for model in models.values():
        model.games_seen += 1


def failure_reasons(final_state: dict, decisions: list[dict]) -> Counter:
    reasons = Counter()
    if final_state.get("winner_team") != final_state.get("your_team"):
        if any(d.get("min_opponent_count", 99) <= 2 and not d.get("play") for d in decisions):
            reasons["missed_block"] += 1
        if any(len(d.get("play") or []) in {c for c in d.get("hand_counts") or [] if 0 < c <= 6} for d in decisions):
            reasons["bad_lead_size"] += 1
            reasons["opened_exact_length_to_opponent"] += 1
        if any(d.get("last_relation") == "teammate" and d.get("play") for d in decisions):
            reasons["bad_teammate_override"] += 1
        if any(d.get("min_opponent_count", 99) <= 2 and d.get("last_relation") == "opponent" and not d.get("play") for d in decisions):
            reasons["bad_endgame_pass"] += 1
        if any(d.get("scenario_tags") and "ally_disruptive" in d.get("scenario_tags") for d in decisions):
            reasons["trusted_disruptive_ally"] += 1
        if any(d.get("scenario_tags") and "one_strong_opponent" in d.get("scenario_tags") for d in decisions):
            reasons["underestimated_strong_opponent"] += 1
    if any(d.get("play_is_bomb") and d.get("hand_count", 99) > 10 for d in decisions):
        reasons["useless_bomb"] += 1
    if any(d.get("play_is_bomb") and d.get("min_opponent_count", 99) <= 2 for d in decisions[-2:]):
        reasons["late_bomb"] += 1
    if any(d.get("decision_mode") == "self_carry" for d in decisions):
        reasons["over_selfcarry"] += 1
    if any(d.get("decision_mode") == "ally_support" for d in decisions):
        reasons["over_support"] += 1
    if any(d.get("bad_lead_size_risk") for d in decisions):
        reasons["gave_strong_opponent_control"] += 1
    return reasons


def empty_stats() -> dict:
    return {
        "elo_available": False,
        "elo_unavailable": True,
        "elo_source_field": None,
        "elo_before": None,
        "elo_after": None,
        "elo_delta": None,
        "total_elo_delta": None,
        "average_elo_delta_per_game": None,
        "max_elo_gain": None,
        "max_elo_loss": None,
        "big_elo_loss_count": None,
        "proxy_points": 0,
        "average_proxy_points_per_game": 0.0,
        "proxy_metric_source": "final_state.scores",
        "games": 0,
        "wins": 0,
        "losses": 0,
        "win_rate": 0.0,
        "team_first_out_rate": None,
        "opponent_first_out_rate": None,
        "missed_block_count": 0,
        "bad_lead_size_count": 0,
        "bad_teammate_override_count": 0,
        "useless_bomb_count": 0,
        "late_bomb_count": 0,
        "gave_strong_opponent_control_count": 0,
        "average_decision_time_ms": 0.0,
        "metric_source": "proxy_not_elo",
        "failure_reason_counts": {},
        "big_elo_loss_failure_counts": {},
        **{key: 0 for key in SHAPE_GUARD_COUNTER_KEYS},
        **{key: 0 for key in SHAPE_GUARD_V2_COUNTER_KEYS},
        **{key: {} for key in SHAPE_GUARD_V2_REASON_KEYS},
        **{key: 0 for key in PLATE_DELAY_GUARD_COUNTER_KEYS},
        **{key: {} for key in PLATE_DELAY_GUARD_REASON_KEYS},
    }


def shape_guard_counts_from_decisions(decisions: list[dict]) -> dict:
    counts = {key: 0 for key in SHAPE_GUARD_COUNTER_KEYS}
    for decision in decisions:
        for key in SHAPE_GUARD_COUNTER_KEYS:
            value = decision.get(key)
            if isinstance(value, bool):
                counts[key] += 1 if value else 0
            elif isinstance(value, (int, float)):
                counts[key] += int(value)
    return counts


def shape_guard_counts_from_record(record: dict) -> dict:
    return {key: int(record.get(key) or 0) for key in SHAPE_GUARD_COUNTER_KEYS}


def shape_guard_v2_counts_from_decisions(decisions: list[dict]) -> dict:
    counts = {key: 0 for key in SHAPE_GUARD_V2_COUNTER_KEYS}
    reason_counts = Counter()
    for decision in decisions:
        for key in SHAPE_GUARD_V2_COUNTER_KEYS:
            value = decision.get(key)
            if isinstance(value, bool):
                counts[key] += 1 if value else 0
            elif isinstance(value, (int, float)):
                counts[key] += int(value)
        merge_reason_counts(reason_counts, decision.get("shape_guard_v2_safe_alt_rejected_reason_counts"))
    counts["shape_guard_v2_safe_alt_rejected_reason_counts"] = dict(reason_counts)
    return counts


def shape_guard_v2_counts_from_record(record: dict) -> dict:
    counts = {key: int(record.get(key) or 0) for key in SHAPE_GUARD_V2_COUNTER_KEYS}
    counts["shape_guard_v2_safe_alt_rejected_reason_counts"] = record.get(
        "shape_guard_v2_safe_alt_rejected_reason_counts"
    ) or {}
    return counts


def merge_shape_guard_v2_counts(target: dict, counts: dict) -> None:
    for key in SHAPE_GUARD_V2_COUNTER_KEYS:
        target[key] = int(target.get(key) or 0) + int(counts.get(key) or 0)
    reason_counts = Counter(target.get("shape_guard_v2_safe_alt_rejected_reason_counts") or {})
    merge_reason_counts(reason_counts, counts.get("shape_guard_v2_safe_alt_rejected_reason_counts"))
    target["shape_guard_v2_safe_alt_rejected_reason_counts"] = dict(reason_counts)


def plate_delay_guard_counts_from_decisions(decisions: list[dict]) -> dict:
    counts = {key: 0 for key in PLATE_DELAY_GUARD_COUNTER_KEYS}
    original_ranks = Counter()
    selected_ranks = Counter()
    for decision in decisions:
        for key in PLATE_DELAY_GUARD_COUNTER_KEYS:
            value = decision.get(key)
            if isinstance(value, bool):
                counts[key] += 1 if value else 0
            elif isinstance(value, (int, float)):
                counts[key] += int(value)
        merge_reason_counts(original_ranks, decision.get("plate_delay_guard_original_plate_rank_counts"))
        merge_reason_counts(selected_ranks, decision.get("plate_delay_guard_selected_single_rank_counts"))
    counts["plate_delay_guard_original_plate_rank_counts"] = dict(original_ranks)
    counts["plate_delay_guard_selected_single_rank_counts"] = dict(selected_ranks)
    return counts


def plate_delay_guard_counts_from_record(record: dict) -> dict:
    counts = {key: int(record.get(key) or 0) for key in PLATE_DELAY_GUARD_COUNTER_KEYS}
    counts["plate_delay_guard_original_plate_rank_counts"] = record.get(
        "plate_delay_guard_original_plate_rank_counts"
    ) or {}
    counts["plate_delay_guard_selected_single_rank_counts"] = record.get(
        "plate_delay_guard_selected_single_rank_counts"
    ) or {}
    return counts


def merge_plate_delay_guard_counts(target: dict, counts: dict) -> None:
    for key in PLATE_DELAY_GUARD_COUNTER_KEYS:
        target[key] = int(target.get(key) or 0) + int(counts.get(key) or 0)
    original_ranks = Counter(target.get("plate_delay_guard_original_plate_rank_counts") or {})
    selected_ranks = Counter(target.get("plate_delay_guard_selected_single_rank_counts") or {})
    merge_reason_counts(original_ranks, counts.get("plate_delay_guard_original_plate_rank_counts"))
    merge_reason_counts(selected_ranks, counts.get("plate_delay_guard_selected_single_rank_counts"))
    target["plate_delay_guard_original_plate_rank_counts"] = dict(original_ranks)
    target["plate_delay_guard_selected_single_rank_counts"] = dict(selected_ranks)


def update_research_results(
    results: dict,
    game_id: str,
    scenario: str,
    profile: str,
    final_state: dict,
    elo_result: dict,
    decisions: list[dict],
) -> None:
    results.setdefault("version", 1)
    if elo_result.get("metric_source") != "leaderboard_elo":
        update_proxy_research_results(results, scenario, profile, final_state, decisions)
        save_json(RESULTS_PATH, results)
        return

    results.setdefault("scenario_profiles", {})
    results.setdefault("global_profile_stats", {})
    scenario_bucket = results["scenario_profiles"].setdefault(scenario, {})
    stats = scenario_bucket.setdefault(profile, empty_stats())
    global_stats = results["global_profile_stats"].setdefault(profile, empty_stats())

    for target in (stats, global_stats):
        if target.get("metric_source") != "leaderboard_elo" and not target.get("elo_available"):
            target.clear()
            target.update(empty_stats())
        target["games"] += 1
        won = final_state.get("winner_team") == final_state.get("your_team")
        target["wins"] += 1 if won else 0
        target["losses"] += 0 if won else 1
        target["win_rate"] = target["wins"] / max(1, target["games"])
        target["team_first_out_rate"] = target["win_rate"]
        target["opponent_first_out_rate"] = target["losses"] / max(1, target["games"])
        scores = final_state.get("scores") or {}
        try:
            proxy = int(scores.get(str(final_state.get("your_team")), 0))
        except (AttributeError, TypeError, ValueError):
            proxy = 0
        target["proxy_points"] = target.get("proxy_points", 0) + proxy
        target["average_proxy_points_per_game"] = target["proxy_points"] / max(1, target["games"])
        target["proxy_metric_source"] = "final_state.scores"
        if elo_result.get("elo_available") and elo_result.get("metric_source") == "leaderboard_elo":
            delta = float(elo_result["elo_delta"])
            target["elo_available"] = True
            target["elo_unavailable"] = False
            target["metric_source"] = "leaderboard_elo"
            target["elo_source_field"] = elo_result.get("elo_source_field")
            target["elo_before"] = elo_result.get("elo_before")
            target["elo_after"] = elo_result.get("elo_after")
            target["elo_delta"] = delta
            target["total_elo_delta"] = (target.get("total_elo_delta") or 0.0) + delta
            target["average_elo_delta_per_game"] = target["total_elo_delta"] / max(1, target["games"])
            previous_gain = target.get("max_elo_gain")
            previous_loss = target.get("max_elo_loss")
            target["max_elo_gain"] = max(0.0 if previous_gain is None else previous_gain, delta)
            target["max_elo_loss"] = min(0.0 if previous_loss is None else previous_loss, delta)
            target["big_elo_loss_count"] = (
                target.get("big_elo_loss_count") or 0
            ) + (1 if delta <= BIG_ELO_LOSS_THRESHOLD else 0)
        else:
            target["elo_available"] = False
            target["elo_unavailable"] = True
            target["metric_source"] = "proxy_not_elo"
        reasons = failure_reasons(final_state, decisions)
        target.setdefault("failure_reason_counts", {})
        target.setdefault("big_elo_loss_failure_counts", {})
        for reason, count in reasons.items():
            target["failure_reason_counts"][reason] = target["failure_reason_counts"].get(reason, 0) + count
            if (
                elo_result.get("metric_source") == "leaderboard_elo"
                and elo_result.get("elo_delta") is not None
                and float(elo_result["elo_delta"]) <= BIG_ELO_LOSS_THRESHOLD
            ):
                target["big_elo_loss_failure_counts"][reason] = (
                    target["big_elo_loss_failure_counts"].get(reason, 0) + count
                )
        for reason in (
            "missed_block",
            "bad_lead_size",
            "bad_teammate_override",
            "useless_bomb",
            "late_bomb",
            "gave_strong_opponent_control",
        ):
            key = f"{reason}_count"
            target[key] = target.get(key, 0) + reasons.get(reason, 0)
        shape_counts = shape_guard_counts_from_decisions(decisions)
        for key, count in shape_counts.items():
            target[key] = int(target.get(key) or 0) + int(count)
        merge_shape_guard_v2_counts(target, shape_guard_v2_counts_from_decisions(decisions))
        merge_plate_delay_guard_counts(target, plate_delay_guard_counts_from_decisions(decisions))
        decision_times = [d.get("decision_time_ms") for d in decisions if d.get("decision_time_ms") is not None]
        if decision_times:
            previous_total = target["average_decision_time_ms"] * (target["games"] - 1)
            target["average_decision_time_ms"] = (previous_total + sum(decision_times) / len(decision_times)) / target["games"]

    results["updated_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    append_game_record(results, game_id, scenario, profile, final_state, elo_result, decisions)
    update_rankings(results)
    save_json(RESULTS_PATH, results)


def update_proxy_research_results(
    results: dict,
    scenario: str,
    profile: str,
    final_state: dict,
    decisions: list[dict],
) -> None:
    results.setdefault("version", 1)
    results.setdefault("proxy_scenario_profiles", {})
    results.setdefault("proxy_global_profile_stats", {})
    scenario_bucket = results["proxy_scenario_profiles"].setdefault(scenario, {})
    stats = scenario_bucket.setdefault(
        profile,
        {
            "metric_source": "proxy_not_elo",
            "proxy_metric_source": "final_state.scores",
            "games": 0,
            "wins": 0,
            "losses": 0,
            "win_rate": 0.0,
            "proxy_points": 0,
            "average_proxy_points_per_game": 0.0,
            "failure_reason_counts": {},
            **{key: 0 for key in SHAPE_GUARD_COUNTER_KEYS},
            **{key: 0 for key in SHAPE_GUARD_V2_COUNTER_KEYS},
            **{key: {} for key in SHAPE_GUARD_V2_REASON_KEYS},
            **{key: 0 for key in PLATE_DELAY_GUARD_COUNTER_KEYS},
            **{key: {} for key in PLATE_DELAY_GUARD_REASON_KEYS},
        },
    )
    global_stats = results["proxy_global_profile_stats"].setdefault(
        profile,
        {
            "metric_source": "proxy_not_elo",
            "proxy_metric_source": "final_state.scores",
            "games": 0,
            "wins": 0,
            "losses": 0,
            "win_rate": 0.0,
            "proxy_points": 0,
            "average_proxy_points_per_game": 0.0,
            "failure_reason_counts": {},
            **{key: 0 for key in SHAPE_GUARD_COUNTER_KEYS},
            **{key: 0 for key in SHAPE_GUARD_V2_COUNTER_KEYS},
            **{key: {} for key in SHAPE_GUARD_V2_REASON_KEYS},
            **{key: 0 for key in PLATE_DELAY_GUARD_COUNTER_KEYS},
            **{key: {} for key in PLATE_DELAY_GUARD_REASON_KEYS},
        },
    )

    for target in (stats, global_stats):
        target["games"] += 1
        won = final_state.get("winner_team") == final_state.get("your_team")
        target["wins"] += 1 if won else 0
        target["losses"] += 0 if won else 1
        target["win_rate"] = target["wins"] / max(1, target["games"])
        scores = final_state.get("scores") or {}
        try:
            proxy = int(scores.get(str(final_state.get("your_team")), 0))
        except (AttributeError, TypeError, ValueError):
            proxy = 0
        target["proxy_points"] += proxy
        target["average_proxy_points_per_game"] = target["proxy_points"] / max(1, target["games"])
        target.setdefault("failure_reason_counts", {})
        for reason, count in failure_reasons(final_state, decisions).items():
            target["failure_reason_counts"][reason] = target["failure_reason_counts"].get(reason, 0) + count
        for key, count in shape_guard_counts_from_decisions(decisions).items():
            target[key] = int(target.get(key) or 0) + int(count)
        merge_shape_guard_v2_counts(target, shape_guard_v2_counts_from_decisions(decisions))
        merge_plate_delay_guard_counts(target, plate_delay_guard_counts_from_decisions(decisions))

    results["updated_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    update_rankings(results)


def build_game_record(
    game_id: str,
    scenario: str,
    profile: str,
    final_state: dict,
    elo_result: dict,
    decisions: list[dict],
    completed_at: str | None = None,
) -> dict:
    failure_counts = failure_reasons(final_state, decisions)
    outcome = "win" if final_state.get("winner_team") == final_state.get("your_team") else "loss"
    bait_summary = summarize_bait_and_overblock(decisions, failure_counts, elo_result)
    shape_summary = shape_guard_counts_from_decisions(decisions)
    shape_v2_summary = shape_guard_v2_counts_from_decisions(decisions)
    plate_delay_summary = plate_delay_guard_counts_from_decisions(decisions)
    return {
        "game_id": str(game_id),
        "completed_at": completed_at or time.strftime("%Y-%m-%d %H:%M:%S"),
        "profile": profile,
        "scenario": scenario,
        "outcome": outcome,
        "elo_before": elo_result.get("elo_before"),
        "elo_after": elo_result.get("elo_after"),
        "elo_delta": elo_result.get("elo_delta"),
        "elo_bucket": elo_bucket_for_value(elo_result.get("elo_before")),
        "metric_source": "leaderboard_elo",
        "failure_tags": sorted(failure_counts),
        "failure_reason_counts": dict(failure_counts),
        **bait_summary,
        **shape_summary,
        **shape_v2_summary,
        **plate_delay_summary,
        "game_counted": True,
    }


def summarize_bait_and_overblock(decisions: list[dict], failure_counts: Counter, elo_result: dict) -> dict:
    overblock_events = [
        decision for decision in decisions
        if decision.get("opponent_overblock_event") is True
    ]
    lead_probe_events = [
        decision.get("lead_probe_event") for decision in decisions
        if isinstance(decision.get("lead_probe_event"), dict)
    ]
    lead_probe_responses = [
        response
        for event in lead_probe_events
        for response in event.get("opponent_responses", [])
        if isinstance(response, dict)
    ]
    possible_overblock_events = [
        response for response in lead_probe_responses
        if response.get("possible_overblock_event") is True
    ]
    bait_candidate_events = [
        event for event in lead_probe_events
        if event.get("is_candidate_bait") is True
    ]
    bait_candidate_overblocked = [
        event for event in bait_candidate_events
        if any(response.get("possible_overblock_event") is True for response in event.get("opponent_responses", []))
    ]
    bait_candidate_decisions = [
        decision for decision in decisions
        if decision.get("bait_candidate_found") is True
        or (decision.get("lead_probe_event") or {}).get("is_candidate_bait") is True
    ]
    bait_selected_decisions = [
        decision for decision in decisions
        if decision.get("bait_selected") is True or decision.get("bait_play")
    ]
    selected_without_candidate_decisions = [
        decision for decision in bait_selected_decisions
        if not (
            decision.get("bait_candidate_found") is True
            or (decision.get("lead_probe_event") or {}).get("is_candidate_bait") is True
        )
    ]
    bait_attempt_decisions = [
        decision for decision in decisions
        if decision.get("bait_attempted") is True or decision in bait_selected_decisions
    ]
    bait_response_observed_decisions = []
    bait_overblocked_decisions = []
    for decision in bait_selected_decisions:
        responses = (decision.get("lead_probe_event") or {}).get("opponent_responses", [])
        response_observed = bool(responses or decision.get("opponent_response"))
        overblocked = bool(
            decision.get("opponent_overblock_event") is True
            or decision.get("possible_overblock_event") is True
            or any(response.get("possible_overblock_event") is True for response in responses if isinstance(response, dict))
        )
        if response_observed:
            bait_response_observed_decisions.append(decision)
        if overblocked:
            bait_overblocked_decisions.append(decision)
    bait_no_candidate_reasons = Counter()
    bait_not_attempted_reasons = Counter()
    for decision in decisions:
        for reason in decision.get("bait_no_candidate_reasons") or []:
            bait_no_candidate_reasons[str(reason)] += 1
        for reason in decision.get("bait_not_attempted_reasons") or []:
            bait_not_attempted_reasons[str(reason)] += 1
        probe = decision.get("lead_probe_event") or {}
        if probe and not probe.get("is_candidate_bait") and probe.get("reason_if_not_candidate_bait"):
            for reason in str(probe["reason_if_not_candidate_bait"]).split(";"):
                if reason:
                    bait_no_candidate_reasons[reason] += 1
    high_card_spent = sum(1 for event in overblock_events if event.get("was_high_card_spent"))
    bomb_spent = sum(1 for event in overblock_events if event.get("was_bomb_spent"))
    bait_candidate_count = len(bait_candidate_decisions)
    bait_success = [
        decision for decision in bait_selected_decisions
        if decision in bait_overblocked_decisions and not decision.get("bait_structure_worse")
    ]
    bait_failure = [
        decision for decision in bait_selected_decisions
        if decision.get("bait_structure_worse")
        or (decision in bait_response_observed_decisions and decision not in bait_overblocked_decisions)
    ]
    if bait_candidate_count == 0:
        bait_success = []
        bait_failure = []
    return {
        "opponent_overblock_count": len(overblock_events),
        "high_card_spent_early_count": high_card_spent,
        "bomb_spent_early_count": bomb_spent,
        "bait_high_card_success_count": len(bait_success),
        "bait_high_card_failure_count": len(bait_failure),
        "lead_probe_count": len(lead_probe_events),
        "possible_overblock_count": len(possible_overblock_events),
        "high_card_response_count": sum(1 for response in lead_probe_responses if response.get("response_is_high_card")),
        "joker_response_count": sum(1 for response in lead_probe_responses if response.get("response_is_joker")),
        "level_card_response_count": sum(1 for response in lead_probe_responses if response.get("response_is_level_card")),
        "bomb_response_to_non_bomb_count": sum(1 for response in lead_probe_responses if response.get("response_is_bomb")),
        "bait_attempt_count": len(bait_attempt_decisions),
        "bait_candidate_count": bait_candidate_count,
        "bait_selected_count": len(bait_selected_decisions),
        "bait_response_observed_count": len(bait_response_observed_decisions),
        "bait_overblocked_count": len(bait_overblocked_decisions),
        "bait_success_count": len(bait_success),
        "bait_failure_count": len(bait_failure),
        "bait_candidate_overblocked_count": len(bait_candidate_overblocked),
        "selected_without_candidate_count": len(selected_without_candidate_decisions),
        "bait_candidate_inconsistent": bool(selected_without_candidate_decisions),
        "bait_no_candidate_reason_counts": dict(bait_no_candidate_reasons),
        "bait_not_attempted_reason_counts": dict(bait_not_attempted_reasons),
    }


def append_game_record(
    results: dict,
    game_id: str,
    scenario: str,
    profile: str,
    final_state: dict,
    elo_result: dict,
    decisions: list[dict],
) -> None:
    if elo_result.get("metric_source") != "leaderboard_elo" or elo_result.get("elo_delta") is None:
        return
    results.setdefault("game_records", [])
    game_id_text = str(game_id)
    if any(str(record.get("game_id")) == game_id_text for record in results["game_records"]):
        return
    results["game_records"].append(
        build_game_record(game_id_text, scenario, profile, final_state, elo_result, decisions)
    )


def update_rankings(results: dict) -> None:
    profiles = results.get("global_profile_stats", {})
    elo_candidates = {
        name: stats for name, stats in profiles.items()
        if (
            stats.get("elo_available")
            and stats.get("metric_source") == "leaderboard_elo"
            and stats.get("average_elo_delta_per_game") is not None
            and stats.get("games", 0) >= GLOBAL_PROFILE_MIN_GAMES
        )
    }
    observed_elo_candidates = {
        name: stats for name, stats in profiles.items()
        if (
            stats.get("elo_available")
            and stats.get("metric_source") == "leaderboard_elo"
            and stats.get("average_elo_delta_per_game") is not None
        )
    }
    if elo_candidates:
        best = max(elo_candidates, key=lambda name: elo_candidates[name]["average_elo_delta_per_game"])
        results["rankings"] = {
            "using_proxy_metric": False,
            "metric_source": "leaderboard_elo",
            "proxy_metric_source": None,
            "elo_best_profile": best,
            "observed_elo_best_profile_not_conclusive": None,
            "proxy_best_profile": None,
        }
        return
    observed_best = None
    if observed_elo_candidates:
        observed_best = max(
            observed_elo_candidates,
            key=lambda name: observed_elo_candidates[name]["average_elo_delta_per_game"],
        )
    results["rankings"] = {
        "using_proxy_metric": False,
        "metric_source": "leaderboard_elo",
        "proxy_metric_source": None,
        "elo_best_profile": None,
        "observed_elo_best_profile_not_conclusive": observed_best,
        "proxy_best_profile": None,
        "reason": "insufficient leaderboard_elo samples" if observed_best else "no leaderboard_elo games yet",
    }


def ranking_report(results: dict) -> dict:
    global_stats = results.get("global_profile_stats", {})
    scenario_stats = results.get("scenario_profiles", {})
    rankings = dict(results.get("rankings", {}))
    scenario_best = {}
    for scenario, profiles in scenario_stats.items():
        candidates = {
            name: profile_score_from_stats(stats)
            for name, stats in profiles.items()
            if stats.get("games", 0) > 0 and profile_score_from_stats(stats) is not None
        }
        if candidates:
            scenario_best[scenario] = max(candidates, key=candidates.get)
    big_loss_candidates = {
        name: stats.get("big_elo_loss_count")
        for name, stats in global_stats.items()
        if stats.get("elo_available") and stats.get("big_elo_loss_count") is not None
    }
    failure_counts = Counter()
    for stats in global_stats.values():
        failure_counts.update(stats.get("failure_reason_counts") or {})
    rankings.update(
        {
            "scenario_best_profiles": scenario_best,
            "least_big_elo_loss_profile": min(big_loss_candidates, key=big_loss_candidates.get)
            if big_loss_candidates
            else None,
            "top_failure_reasons": failure_counts.most_common(8),
        }
    )
    return rankings


def elo_stats_candidates(stats_by_profile: dict, min_games: int = 0) -> dict:
    return {
        name: stats
        for name, stats in stats_by_profile.items()
        if (
            stats.get("games", 0) >= min_games
            and stats.get("metric_source") == "leaderboard_elo"
            and stats.get("average_elo_delta_per_game") is not None
        )
    }


def best_elo_profile(stats_by_profile: dict, min_games: int = 0) -> str | None:
    candidates = elo_stats_candidates(stats_by_profile, min_games)
    if not candidates:
        return None
    return max(candidates, key=lambda name: candidates[name]["average_elo_delta_per_game"])


def completed_at_from_log_path(path: Path) -> str:
    match = re.search(r"_(\d{8}_\d{6})\.json$", path.name)
    if match:
        try:
            parsed = time.strptime(match.group(1), "%Y%m%d_%H%M%S")
            return time.strftime("%Y-%m-%d %H:%M:%S", parsed)
        except ValueError:
            pass
    return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(path.stat().st_mtime))


def record_from_log_payload(path: Path, payload: dict) -> dict | None:
    if payload.get("game_error_type") or payload.get("game_counted") is False:
        return None
    if payload.get("metric_source") != "leaderboard_elo" or payload.get("elo_delta") is None:
        return None
    game_id = payload.get("game_id")
    profile = payload.get("profile")
    scenario = payload.get("scenario")
    if not game_id or not profile or not scenario:
        return None
    outcome = payload.get("outcome")
    if outcome not in {"win", "loss"}:
        final_state = payload.get("final_state") or {}
        outcome = "win" if final_state.get("winner_team") == final_state.get("your_team") else "loss"
    failure_counts = Counter(payload.get("failure_reason_counts") or {})
    decisions = payload.get("decisions") or []
    computed_bait = summarize_bait_and_overblock(
        decisions,
        failure_counts,
        {"elo_delta": payload.get("elo_delta")},
    )
    computed_shape = shape_guard_counts_from_decisions(decisions)
    computed_shape_v2 = shape_guard_v2_counts_from_decisions(decisions)
    computed_plate_delay = plate_delay_guard_counts_from_decisions(decisions)
    return {
        "game_id": str(game_id),
        "completed_at": payload.get("completed_at") or completed_at_from_log_path(path),
        "profile": profile,
        "scenario": scenario,
        "outcome": outcome,
        "elo_before": payload.get("elo_before"),
        "elo_after": payload.get("elo_after"),
        "elo_delta": payload.get("elo_delta"),
        "elo_bucket": payload.get("elo_bucket") or elo_bucket_for_value(payload.get("elo_before")),
        "metric_source": "leaderboard_elo",
        "failure_tags": payload.get("failure_tags") or [],
        "failure_reason_counts": payload.get("failure_reason_counts") or {},
        "opponent_overblock_count": int(payload.get("opponent_overblock_count") or computed_bait["opponent_overblock_count"]),
        "high_card_spent_early_count": int(payload.get("high_card_spent_early_count") or computed_bait["high_card_spent_early_count"]),
        "bomb_spent_early_count": int(payload.get("bomb_spent_early_count") or computed_bait["bomb_spent_early_count"]),
        "bait_high_card_success_count": int(computed_bait["bait_high_card_success_count"]),
        "bait_high_card_failure_count": int(computed_bait["bait_high_card_failure_count"]),
        "lead_probe_count": int(payload.get("lead_probe_count") or computed_bait["lead_probe_count"]),
        "possible_overblock_count": int(payload.get("possible_overblock_count") or computed_bait["possible_overblock_count"]),
        "high_card_response_count": int(payload.get("high_card_response_count") or computed_bait["high_card_response_count"]),
        "joker_response_count": int(payload.get("joker_response_count") or computed_bait["joker_response_count"]),
        "level_card_response_count": int(payload.get("level_card_response_count") or computed_bait["level_card_response_count"]),
        "bomb_response_to_non_bomb_count": int(
            payload.get("bomb_response_to_non_bomb_count") or computed_bait["bomb_response_to_non_bomb_count"]
        ),
        "bait_candidate_count": int(payload.get("bait_candidate_count") or computed_bait["bait_candidate_count"]),
        "bait_candidate_overblocked_count": int(
            payload.get("bait_candidate_overblocked_count") or computed_bait["bait_candidate_overblocked_count"]
        ),
        "bait_attempt_count": int(payload.get("bait_attempt_count") or computed_bait["bait_attempt_count"]),
        "bait_selected_count": int(payload.get("bait_selected_count") or computed_bait["bait_selected_count"]),
        "bait_response_observed_count": int(
            payload.get("bait_response_observed_count") or computed_bait["bait_response_observed_count"]
        ),
        "bait_overblocked_count": int(payload.get("bait_overblocked_count") or computed_bait["bait_overblocked_count"]),
        "bait_success_count": int(computed_bait["bait_success_count"]),
        "bait_failure_count": int(computed_bait["bait_failure_count"]),
        "selected_without_candidate_count": int(
            payload.get("selected_without_candidate_count") or computed_bait["selected_without_candidate_count"]
        ),
        "bait_candidate_inconsistent": bool(
            payload.get("bait_candidate_inconsistent") or computed_bait["bait_candidate_inconsistent"]
        ),
        "bait_no_candidate_reason_counts": payload.get("bait_no_candidate_reason_counts")
        or computed_bait["bait_no_candidate_reason_counts"],
        "bait_not_attempted_reason_counts": payload.get("bait_not_attempted_reason_counts")
        or computed_bait["bait_not_attempted_reason_counts"],
        **{key: int(payload.get(key) or computed_shape[key]) for key in SHAPE_GUARD_COUNTER_KEYS},
        **{key: int(payload.get(key) or computed_shape_v2[key]) for key in SHAPE_GUARD_V2_COUNTER_KEYS},
        "shape_guard_v2_safe_alt_rejected_reason_counts": payload.get(
            "shape_guard_v2_safe_alt_rejected_reason_counts"
        )
        or computed_shape_v2["shape_guard_v2_safe_alt_rejected_reason_counts"],
        **{key: int(payload.get(key) or computed_plate_delay[key]) for key in PLATE_DELAY_GUARD_COUNTER_KEYS},
        "plate_delay_guard_original_plate_rank_counts": payload.get(
            "plate_delay_guard_original_plate_rank_counts"
        )
        or computed_plate_delay["plate_delay_guard_original_plate_rank_counts"],
        "plate_delay_guard_selected_single_rank_counts": payload.get(
            "plate_delay_guard_selected_single_rank_counts"
        )
        or computed_plate_delay["plate_delay_guard_selected_single_rank_counts"],
        "game_counted": True,
    }


def backfill_game_records_from_logs(results: dict) -> int:
    results.setdefault("game_records", [])
    known = {str(record.get("game_id")) for record in results["game_records"] if record.get("game_id") is not None}
    added = 0
    for path in Path(".").glob("logs*/research_game_*.json"):
        try:
            payload = load_json(path, {})
            record = record_from_log_payload(path, payload)
        except Exception:
            continue
        if not record:
            continue
        key = str(record.get("game_id"))
        if key in known:
            continue
        results["game_records"].append(record)
        known.add(key)
        added += 1
    return added


def official_game_records(results: dict) -> list[dict]:
    records = []
    for record in results.get("game_records") or []:
        if (
            record.get("game_counted") is True
            and record.get("metric_source") == "leaderboard_elo"
            and record.get("elo_delta") is not None
            and record.get("profile")
        ):
            records.append(record)
    return sorted(records, key=lambda item: str(item.get("completed_at") or ""))


def numeric_value(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def elo_bucket_for_value(value: Any) -> str:
    elo = numeric_value(value)
    if elo is None:
        return "unknown"
    for low, high, label in ELO_BUCKETS:
        if (low is None or elo >= low) and (high is None or elo <= high):
            return label
    return "unknown"


def elo_bucket_for_record(record: dict) -> str:
    return str(record.get("elo_bucket") or elo_bucket_for_value(record.get("elo_before")))


def score_pressure_level(break_even_win_rate: float | None) -> str | None:
    if break_even_win_rate is None:
        return None
    if break_even_win_rate < 0.55:
        return "low"
    if break_even_win_rate <= 0.65:
        return "medium"
    if break_even_win_rate <= 0.70:
        return "high"
    return "extreme"


def elo_economy_stats(records: list[dict]) -> dict:
    counted = []
    for record in records:
        delta = numeric_value(record.get("elo_delta"))
        if delta is None:
            continue
        counted.append((record, delta))

    games = len(counted)
    wins = sum(1 for record, _ in counted if record.get("outcome") == "win")
    losses = sum(1 for record, _ in counted if record.get("outcome") == "loss")
    total_delta = sum(delta for _, delta in counted)
    gains = [delta for _, delta in counted if delta > 0]
    costs = [-delta for _, delta in counted if delta < 0]
    avg_gain = sum(gains) / len(gains) if gains else None
    avg_cost = sum(costs) / len(costs) if costs else None
    actual_win_rate = wins / games if games else None
    break_even = None
    required_plus_1 = None
    margin = None
    if avg_gain is not None and avg_cost is not None and avg_gain + avg_cost > 0:
        break_even = avg_cost / (avg_gain + avg_cost)
        required_plus_1 = (avg_cost + 1.0) / (avg_gain + avg_cost)
        if actual_win_rate is not None:
            margin = actual_win_rate - break_even

    return {
        "elo_economy_games": games,
        "elo_economy_wins": wins,
        "elo_economy_losses": losses,
        "actual_win_rate": actual_win_rate,
        "total_elo_delta": total_delta,
        "average_elo_delta_per_game": total_delta / games if games else None,
        "positive_elo_games": len(gains),
        "negative_elo_games": len(costs),
        "avg_win_elo_gain": avg_gain,
        "avg_loss_elo_cost": avg_cost,
        "break_even_win_rate": break_even,
        "current_win_rate_margin": margin,
        "required_win_rate_for_plus_1": required_plus_1,
        "high_elo_unsustainable": bool(actual_win_rate is not None and actual_win_rate > 0.5 and total_delta < 0),
        "score_pressure_level": score_pressure_level(break_even),
        "not_suitable_for_long_run": bool(break_even is not None and actual_win_rate is not None and break_even > actual_win_rate),
    }


def bait_counts_from_record(record: dict) -> dict:
    counts = {
        "bait_attempt_count": int(record.get("bait_attempt_count") or 0),
        "bait_candidate_count": int(record.get("bait_candidate_count") or 0),
        "bait_selected_count": int(record.get("bait_selected_count") or 0),
        "bait_response_observed_count": int(record.get("bait_response_observed_count") or 0),
        "bait_overblocked_count": int(record.get("bait_overblocked_count") or 0),
        "bait_success_count": int(record.get("bait_success_count") or record.get("bait_high_card_success_count") or 0),
        "bait_failure_count": int(record.get("bait_failure_count") or record.get("bait_high_card_failure_count") or 0),
        "bait_candidate_overblocked_count": int(record.get("bait_candidate_overblocked_count") or 0),
        "selected_without_candidate_count": int(record.get("selected_without_candidate_count") or 0),
    }
    if counts["selected_without_candidate_count"] == 0 and counts["bait_selected_count"] > counts["bait_candidate_count"]:
        counts["selected_without_candidate_count"] = counts["bait_selected_count"] - counts["bait_candidate_count"]
    if counts["bait_candidate_count"] == 0 or counts["bait_attempt_count"] == 0:
        counts["bait_success_count"] = 0
        counts["bait_failure_count"] = 0
        counts["bait_candidate_overblocked_count"] = 0
    counts["bait_candidate_inconsistent"] = bool(counts["selected_without_candidate_count"])
    counts["bait_high_card_success_count"] = counts["bait_success_count"]
    counts["bait_high_card_failure_count"] = counts["bait_failure_count"]
    return counts


def merge_reason_counts(target: Counter, value: Any) -> None:
    if isinstance(value, dict):
        for reason, count in value.items():
            try:
                target[str(reason)] += int(count)
            except (TypeError, ValueError):
                target[str(reason)] += 1
    elif isinstance(value, list):
        target.update(str(item) for item in value)


def recent_stats_for_profile(profile: str, stats: dict, records: list[dict], window: int) -> dict:
    profile_records = [record for record in records if record.get("profile") == profile]
    recent = profile_records[-window:] if window > 0 else []
    deltas = [float(record.get("elo_delta") or 0.0) for record in recent]
    wins = sum(1 for record in recent if record.get("outcome") == "win")
    losses = sum(1 for record in recent if record.get("outcome") == "loss")
    failure_counts = Counter()
    for record in recent:
        if isinstance(record.get("failure_reason_counts"), dict) and record["failure_reason_counts"]:
            failure_counts.update(record["failure_reason_counts"])
        else:
            failure_counts.update(record.get("failure_tags") or [])
    recent_games = len(recent)
    recent_avg = sum(deltas) / recent_games if recent_games else None
    cumulative_avg = stats.get("average_elo_delta_per_game")
    recent_regression = bool(
        cumulative_avg is not None
        and float(cumulative_avg) > 0
        and recent_avg is not None
        and recent_avg < 0
    )
    recent_performance_drop = bool(
        cumulative_avg is not None
        and recent_avg is not None
        and recent_avg <= float(cumulative_avg) - 2.0
    )
    bait_counts = Counter()
    bait_no_candidate_reasons = Counter()
    bait_not_attempted_reasons = Counter()
    for record in recent:
        bait_counts.update(bait_counts_from_record(record))
        merge_reason_counts(bait_no_candidate_reasons, record.get("bait_no_candidate_reason_counts"))
        merge_reason_counts(bait_not_attempted_reasons, record.get("bait_not_attempted_reason_counts"))
    shape_counts = Counter()
    shape_v2_counts = Counter()
    shape_v2_reasons = Counter()
    plate_delay_counts = Counter()
    plate_delay_original_ranks = Counter()
    plate_delay_selected_ranks = Counter()
    for record in recent:
        shape_counts.update(shape_guard_counts_from_record(record))
        shape_v2 = shape_guard_v2_counts_from_record(record)
        for key in SHAPE_GUARD_V2_COUNTER_KEYS:
            shape_v2_counts[key] += int(shape_v2.get(key) or 0)
        merge_reason_counts(shape_v2_reasons, shape_v2.get("shape_guard_v2_safe_alt_rejected_reason_counts"))
        plate_delay = plate_delay_guard_counts_from_record(record)
        for key in PLATE_DELAY_GUARD_COUNTER_KEYS:
            plate_delay_counts[key] += int(plate_delay.get(key) or 0)
        merge_reason_counts(
            plate_delay_original_ranks,
            plate_delay.get("plate_delay_guard_original_plate_rank_counts"),
        )
        merge_reason_counts(
            plate_delay_selected_ranks,
            plate_delay.get("plate_delay_guard_selected_single_rank_counts"),
        )
    recent_overblocks = sum(int(record.get("opponent_overblock_count") or 0) for record in recent)
    recent_lead_probes = sum(int(record.get("lead_probe_count") or 0) for record in recent)
    recent_possible_overblocks = sum(int(record.get("possible_overblock_count") or 0) for record in recent)
    result = {
        "recent_games": recent_games,
        "recent_wins": wins,
        "recent_losses": losses,
        "recent_win_rate": wins / recent_games if recent_games else None,
        "recent_total_elo_delta": sum(deltas) if recent_games else 0.0,
        "recent_average_elo_delta_per_game": recent_avg,
        "recent_max_elo_gain": max(deltas) if deltas else None,
        "recent_max_elo_loss": min(deltas) if deltas else None,
        "recent_big_elo_loss_count": sum(1 for delta in deltas if delta <= BIG_ELO_LOSS_THRESHOLD),
        "recent_failure_reason_counts": dict(failure_counts),
        "recent_opponent_overblock_count": recent_overblocks,
        "recent_opponent_overblock_rate": recent_overblocks / recent_games if recent_games else None,
        "recent_high_card_spent_early_count": sum(int(record.get("high_card_spent_early_count") or 0) for record in recent),
        "recent_bomb_spent_early_count": sum(int(record.get("bomb_spent_early_count") or 0) for record in recent),
        "recent_bait_high_card_success_count": bait_counts["bait_high_card_success_count"],
        "recent_bait_high_card_failure_count": bait_counts["bait_high_card_failure_count"],
        "recent_lead_probe_count": recent_lead_probes,
        "recent_possible_overblock_count": recent_possible_overblocks,
        "recent_possible_overblock_rate": recent_possible_overblocks / recent_lead_probes if recent_lead_probes else None,
        "recent_high_card_response_count": sum(int(record.get("high_card_response_count") or 0) for record in recent),
        "recent_joker_response_count": sum(int(record.get("joker_response_count") or 0) for record in recent),
        "recent_level_card_response_count": sum(int(record.get("level_card_response_count") or 0) for record in recent),
        "recent_bomb_response_to_non_bomb_count": sum(
            int(record.get("bomb_response_to_non_bomb_count") or 0) for record in recent
        ),
        "recent_bait_attempt_count": bait_counts["bait_attempt_count"],
        "recent_bait_candidate_count": bait_counts["bait_candidate_count"],
        "recent_bait_selected_count": bait_counts["bait_selected_count"],
        "recent_bait_response_observed_count": bait_counts["bait_response_observed_count"],
        "recent_bait_overblocked_count": bait_counts["bait_overblocked_count"],
        "recent_bait_success_count": bait_counts["bait_success_count"],
        "recent_bait_failure_count": bait_counts["bait_failure_count"],
        "recent_bait_candidate_overblocked_count": bait_counts["bait_candidate_overblocked_count"],
        "recent_selected_without_candidate_count": bait_counts["selected_without_candidate_count"],
        "recent_bait_candidate_inconsistent": bool(bait_counts["selected_without_candidate_count"]),
        "recent_bait_no_candidate_reason_counts": dict(bait_no_candidate_reasons),
        "recent_bait_not_attempted_reason_counts": dict(bait_not_attempted_reasons),
        **{f"recent_{key}": shape_counts[key] for key in SHAPE_GUARD_COUNTER_KEYS},
        **{f"recent_{key}": shape_v2_counts[key] for key in SHAPE_GUARD_V2_COUNTER_KEYS},
        "recent_shape_guard_v2_safe_alt_rejected_reason_counts": dict(shape_v2_reasons),
        **{f"recent_{key}": plate_delay_counts[key] for key in PLATE_DELAY_GUARD_COUNTER_KEYS},
        "recent_plate_delay_guard_original_plate_rank_counts": dict(plate_delay_original_ranks),
        "recent_plate_delay_guard_selected_single_rank_counts": dict(plate_delay_selected_ranks),
        "recent_regression": recent_regression,
        "recent_performance_drop": recent_performance_drop,
    }
    result.update(elo_economy_stats(recent))
    return result


def recent_window_summary(results: dict, window: int, profiles: dict | None = None) -> dict:
    records = official_game_records(results)
    summary = {}
    profile_names = sorted(set(results.get("global_profile_stats") or {}) | set(profiles or {}))
    for profile in profile_names:
        stats = (results.get("global_profile_stats") or {}).get(profile) or empty_stats()
        summary[profile] = recent_stats_for_profile(profile, stats, records, window)
    return {
        "recent_window": window,
        "record_source": "game_records",
        "records_available": len(records),
        "profiles": summary,
    }


def elo_bucket_labels() -> list[str]:
    return [label for _, _, label in ELO_BUCKETS] + ["unknown"]


def elo_economy_summary(results: dict, recent_window: int) -> dict:
    records = official_game_records(results)
    profiles = sorted({str(record.get("profile")) for record in records if record.get("profile")})
    by_profile = {
        profile: elo_economy_stats([record for record in records if record.get("profile") == profile])
        for profile in profiles
    }

    by_elo_bucket = {}
    for bucket in elo_bucket_labels():
        bucket_records = [record for record in records if elo_bucket_for_record(record) == bucket]
        if bucket_records:
            by_elo_bucket[bucket] = elo_economy_stats(bucket_records)

    by_profile_elo_bucket = {}
    for profile in profiles:
        profile_records = [record for record in records if record.get("profile") == profile]
        buckets = {}
        for bucket in elo_bucket_labels():
            bucket_records = [record for record in profile_records if elo_bucket_for_record(record) == bucket]
            if bucket_records:
                buckets[bucket] = elo_economy_stats(bucket_records)
        by_profile_elo_bucket[profile] = buckets

    recent_by_profile = {}
    recent_records_all = []
    for profile in profiles:
        profile_records = [record for record in records if record.get("profile") == profile]
        recent = profile_records[-recent_window:] if recent_window > 0 else []
        recent_records_all.extend(recent)
        recent_by_profile[profile] = elo_economy_stats(recent)
    recent_by_elo_bucket = {}
    for bucket in elo_bucket_labels():
        bucket_records = [record for record in recent_records_all if elo_bucket_for_record(record) == bucket]
        if bucket_records:
            recent_by_elo_bucket[bucket] = elo_economy_stats(bucket_records)
    recent_by_profile_elo_bucket = {}
    for profile in profiles:
        profile_records = [record for record in records if record.get("profile") == profile]
        recent = profile_records[-recent_window:] if recent_window > 0 else []
        buckets = {}
        for bucket in elo_bucket_labels():
            bucket_records = [record for record in recent if elo_bucket_for_record(record) == bucket]
            if bucket_records:
                buckets[bucket] = elo_economy_stats(bucket_records)
        recent_by_profile_elo_bucket[profile] = buckets

    return {
        "metric_source": "leaderboard_elo",
        "record_source": "game_records",
        "proxy_scores_note": "final_state.scores is proxy only and is not used for Elo economy.",
        "long_run_warning_note": (
            "If break_even_win_rate is higher than actual_win_rate/current win rate, "
            "that profile is not suitable for continued long runs at this Elo band."
        ),
        "elo_bucket_source": "elo_before",
        "elo_buckets": [label for _, _, label in ELO_BUCKETS],
        "global": elo_economy_stats(records),
        "by_profile": by_profile,
        "recent_window": {
            "window": recent_window,
            "by_profile": recent_by_profile,
            "by_elo_bucket": recent_by_elo_bucket,
            "by_profile_elo_bucket": recent_by_profile_elo_bucket,
        },
        "by_elo_bucket": by_elo_bucket,
        "by_profile_elo_bucket": by_profile_elo_bucket,
        "profiles_not_suitable_for_long_run": [
            profile for profile, stats in by_profile.items()
            if stats.get("not_suitable_for_long_run")
        ],
        "recent_profiles_not_suitable_for_long_run": [
            profile for profile, stats in recent_by_profile.items()
            if stats.get("not_suitable_for_long_run")
        ],
        "high_elo_unsustainable_profiles": [
            profile for profile, stats in recent_by_profile.items()
            if stats.get("high_elo_unsustainable")
        ],
    }


def enriched_global_profile_stats(results: dict, profiles: dict | None = None) -> dict:
    records = official_game_records(results)
    global_stats = results.get("global_profile_stats") or {}
    profile_names = sorted(
        set(global_stats)
        | set(profiles or {})
        | {str(record.get("profile")) for record in records if record.get("profile")}
    )
    enriched = {}
    for profile in profile_names:
        profile_records = [record for record in records if record.get("profile") == profile]
        item = dict(global_stats.get(profile) or empty_stats())
        item.update(elo_economy_stats(profile_records))
        enriched[profile] = item
    return enriched


def elo_bucket_profile_stats(results: dict) -> dict:
    records = official_game_records(results)
    profile_names = sorted({str(record.get("profile")) for record in records if record.get("profile")})
    buckets: dict[str, dict] = {}
    for bucket in elo_bucket_labels():
        bucket_records = [record for record in records if elo_bucket_for_record(record) == bucket]
        if not bucket_records:
            continue
        buckets[bucket] = {}
        for profile in profile_names:
            profile_records = [record for record in bucket_records if record.get("profile") == profile]
            if profile_records:
                buckets[bucket][profile] = elo_economy_stats(profile_records)
    return buckets


def total_elo_delta(records: list[dict]) -> float:
    return sum(float(record.get("elo_delta") or 0.0) for record in records)


def profile_window_comparison(results: dict) -> dict:
    records = official_game_records(results)
    profiles = sorted({str(record.get("profile")) for record in records if record.get("profile")})
    comparison = {}
    for profile in profiles:
        profile_records = [record for record in records if record.get("profile") == profile]
        comparison[profile] = {
            "games": len(profile_records),
            "first10_total_elo_delta": total_elo_delta(profile_records[:10]),
            "last10_total_elo_delta": total_elo_delta(profile_records[-10:]),
            "last20_total_elo_delta": total_elo_delta(profile_records[-20:]),
            "last25_total_elo_delta": total_elo_delta(profile_records[-25:]),
        }
    return comparison


def profile_status_summary(results: dict, profiles: dict) -> dict:
    global_stats = results.get("global_profile_stats", {})
    tempo_avg = (global_stats.get(DEFAULT_LIVE_PROFILE) or {}).get("average_elo_delta_per_game")
    paused: dict[str, list[str]] = {}
    candidate: dict[str, list[str]] = {}
    observation_only: dict[str, list[str]] = {}
    active = {DEFAULT_LIVE_PROFILE: ["active_default"]}

    for profile in sorted(set(profiles) | set(global_stats) | OBSERVATION_ONLY_PROFILES):
        if profile == DEFAULT_LIVE_PROFILE:
            continue
        if profile in OBSERVATION_ONLY_PROFILES:
            observation_only[profile] = ["observation_only"]
            continue
        stats = global_stats.get(profile) or {}
        games = int(stats.get("games", 0))
        avg = stats.get("average_elo_delta_per_game")
        reasons: list[str] = []
        if profile in CONFIGURED_PAUSED_PROFILES:
            reasons.append("configured_paused")
        if games >= 10 and avg is not None and float(avg) < 0:
            reasons.append("paused_negative")
        if (
            games >= 20
            and avg is not None
            and tempo_avg is not None
            and float(avg) <= float(tempo_avg) - 2.0
        ):
            reasons.append("paused_underperforming")
        if reasons:
            paused[profile] = reasons
        elif profile in CANDIDATE_PROFILES:
            candidate[profile] = ["candidate_observation"]

    for profile in sorted(CANDIDATE_PROFILES):
        if profile not in paused and profile in profiles:
            candidate.setdefault(profile, ["candidate_observation"])

    return {
        "default_live_profile": DEFAULT_LIVE_PROFILE,
        "active_default": DEFAULT_LIVE_PROFILE,
        "active": active,
        "candidate": candidate,
        "observation_only": observation_only,
        "paused": paused,
        "paused_profiles_excluded_from_default_research": sorted(paused),
    }


def overblock_summary(results: dict) -> dict:
    records = official_game_records(results)
    by_profile: dict[str, dict] = {}
    total = Counter()
    for record in records:
        profile = record.get("profile")
        if not profile:
            continue
        bucket = by_profile.setdefault(
            profile,
            {
                "games": 0,
                "opponent_overblock_count": 0,
                "high_card_spent_early_count": 0,
                "bomb_spent_early_count": 0,
                "bait_high_card_success_count": 0,
                "bait_high_card_failure_count": 0,
                "lead_probe_count": 0,
                "possible_overblock_count": 0,
                "high_card_response_count": 0,
                "joker_response_count": 0,
                "level_card_response_count": 0,
                "bomb_response_to_non_bomb_count": 0,
                "bait_attempt_count": 0,
                "bait_candidate_count": 0,
                "bait_selected_count": 0,
                "bait_response_observed_count": 0,
                "bait_overblocked_count": 0,
                "bait_success_count": 0,
                "bait_failure_count": 0,
                "bait_candidate_overblocked_count": 0,
                "selected_without_candidate_count": 0,
                "bait_candidate_inconsistent": False,
                "bait_no_candidate_reason_counts": {},
                "bait_not_attempted_reason_counts": {},
            },
        )
        bucket["games"] += 1
        for key in (
            "opponent_overblock_count",
            "high_card_spent_early_count",
            "bomb_spent_early_count",
            "bait_high_card_success_count",
            "bait_high_card_failure_count",
            *OBSERVATION_COUNTER_KEYS,
        ):
            value = int(record.get(key) or 0)
            bucket[key] += value
            total[key] += value
        bait_counts = bait_counts_from_record(record)
        for key in BAIT_COUNTER_KEYS:
            value = int(bait_counts.get(key) or 0)
            bucket[key] += value
            total[key] += value
        bucket["bait_high_card_success_count"] = bucket["bait_success_count"]
        bucket["bait_high_card_failure_count"] = bucket["bait_failure_count"]
        bucket["bait_candidate_inconsistent"] = bool(bucket["selected_without_candidate_count"])
        total["bait_high_card_success_count"] = total["bait_success_count"]
        total["bait_high_card_failure_count"] = total["bait_failure_count"]
        total["bait_candidate_inconsistent"] = bool(total["selected_without_candidate_count"])
        bucket_no_candidate = Counter(bucket.get("bait_no_candidate_reason_counts") or {})
        bucket_not_attempted = Counter(bucket.get("bait_not_attempted_reason_counts") or {})
        merge_reason_counts(bucket_no_candidate, record.get("bait_no_candidate_reason_counts"))
        merge_reason_counts(bucket_not_attempted, record.get("bait_not_attempted_reason_counts"))
        bucket["bait_no_candidate_reason_counts"] = dict(bucket_no_candidate)
        bucket["bait_not_attempted_reason_counts"] = dict(bucket_not_attempted)
        merge_reason_counts(total.setdefault("bait_no_candidate_reason_counts", Counter()), record.get("bait_no_candidate_reason_counts"))
        merge_reason_counts(total.setdefault("bait_not_attempted_reason_counts", Counter()), record.get("bait_not_attempted_reason_counts"))
    for bucket in by_profile.values():
        games = max(1, int(bucket["games"]))
        bucket["opponent_overblock_rate"] = bucket["opponent_overblock_count"] / games
        bucket["possible_overblock_rate"] = (
            bucket["possible_overblock_count"] / bucket["lead_probe_count"]
            if bucket["lead_probe_count"]
            else None
        )
    total_games = len(records)
    return {
        "games": total_games,
        "opponent_overblock_count": total["opponent_overblock_count"],
        "opponent_overblock_rate": total["opponent_overblock_count"] / total_games if total_games else None,
        "high_card_spent_early_count": total["high_card_spent_early_count"],
        "bomb_spent_early_count": total["bomb_spent_early_count"],
        "bait_high_card_success_count": total["bait_high_card_success_count"],
        "bait_high_card_failure_count": total["bait_high_card_failure_count"],
        "lead_probe_count": total["lead_probe_count"],
        "possible_overblock_count": total["possible_overblock_count"],
        "possible_overblock_rate": (
            total["possible_overblock_count"] / total["lead_probe_count"]
            if total["lead_probe_count"]
            else None
        ),
        "high_card_response_count": total["high_card_response_count"],
        "joker_response_count": total["joker_response_count"],
        "level_card_response_count": total["level_card_response_count"],
        "bomb_response_to_non_bomb_count": total["bomb_response_to_non_bomb_count"],
        "bait_attempt_count": total["bait_attempt_count"],
        "bait_candidate_count": total["bait_candidate_count"],
        "bait_selected_count": total["bait_selected_count"],
        "bait_response_observed_count": total["bait_response_observed_count"],
        "bait_overblocked_count": total["bait_overblocked_count"],
        "bait_success_count": total["bait_success_count"],
        "bait_failure_count": total["bait_failure_count"],
        "bait_candidate_overblocked_count": total["bait_candidate_overblocked_count"],
        "selected_without_candidate_count": total["selected_without_candidate_count"],
        "bait_candidate_inconsistent": bool(total["selected_without_candidate_count"]),
        "bait_no_candidate_reason_counts": dict(total.get("bait_no_candidate_reason_counts") or {}),
        "bait_not_attempted_reason_counts": dict(total.get("bait_not_attempted_reason_counts") or {}),
        "by_profile": by_profile,
    }


def build_research_summary(results: dict, profiles: dict, recent_window: int = 10) -> dict:
    global_stats = results.get("global_profile_stats", {})
    scenario_stats = results.get("scenario_profiles", {})
    observed_global_best = best_elo_profile(global_stats, 1)
    conclusive_global_best = best_elo_profile(global_stats, GLOBAL_PROFILE_MIN_GAMES)
    scenario_best: dict[str, dict] = {}
    insufficient_samples: list[dict] = []

    for scenario, profile_stats_map in scenario_stats.items():
        observed = best_elo_profile(profile_stats_map, 1)
        conclusive = best_elo_profile(profile_stats_map, SCENARIO_PROFILE_MIN_GAMES)
        scenario_best[scenario] = {
            "elo_best_profile": conclusive,
            "observed_best_profile_not_conclusive": observed if conclusive is None else None,
            "sample_status": "ok" if conclusive else "insufficient_samples",
        }
        for profile, stats in profile_stats_map.items():
            games = int(stats.get("games", 0))
            if games < SCENARIO_PROFILE_MIN_GAMES:
                insufficient_samples.append(
                    {
                        "scenario": scenario,
                        "profile": profile,
                        "games": games,
                        "needed": SCENARIO_PROFILE_MIN_GAMES,
                    }
                )

    big_loss_failure_counts = Counter()
    failure_counts = Counter()
    for stats in global_stats.values():
        big_loss_failure_counts.update(stats.get("big_elo_loss_failure_counts") or {})
        failure_counts.update(stats.get("failure_reason_counts") or {})

    suggestion_profiles = {DEFAULT_LIVE_PROFILE} | CANDIDATE_PROFILES
    profile_names = [
        name for name in (list(profiles.keys()) if profiles else sorted(global_stats))
        if name in suggestion_profiles
    ]
    suggested_next_profiles: list[dict] = []
    for profile in profile_names:
        games = int(global_stats.get(profile, {}).get("games", 0))
        if games < GLOBAL_PROFILE_MIN_GAMES:
            suggested_next_profiles.append(
                {
                    "profile": profile,
                    "reason": "global_profile_under_30_games",
                    "games": games,
                    "needed": GLOBAL_PROFILE_MIN_GAMES,
                }
            )
    for item in insufficient_samples:
        if item["profile"] not in suggestion_profiles:
            continue
        suggested_next_profiles.append(
            {
                "profile": item["profile"],
                "scenario": item["scenario"],
                "reason": "scenario_profile_under_20_games",
                "games": item["games"],
                "needed": item["needed"],
            }
        )
        if len(suggested_next_profiles) >= 30:
            break

    overblock = overblock_summary(results)
    economy = elo_economy_summary(results, recent_window)
    enriched_stats = enriched_global_profile_stats(results, profiles)
    bucket_profile_stats = elo_bucket_profile_stats(results)
    window_comparison = profile_window_comparison(results)
    observed_best_stats = enriched_stats.get(observed_global_best, {}) if observed_global_best else {}
    conclusive_best_stats = enriched_stats.get(conclusive_global_best, {}) if conclusive_global_best else {}
    return {
        "metric_source": "leaderboard_elo",
        "using_proxy_metric": False,
        "elo_economy_warning": economy["long_run_warning_note"],
        "global_profile_stats": enriched_stats,
        "elo_bucket_profile_stats": bucket_profile_stats,
        "profile_elo_bucket_stats": economy["by_profile_elo_bucket"],
        "profile_window_comparison": window_comparison,
        "bait_high_card_window_comparison": window_comparison.get("bait_high_card", {}),
        "global_elo_best_profile": conclusive_global_best,
        "global_elo_best_profile_stats": conclusive_best_stats,
        "global_elo_best_observed_profile_not_conclusive": observed_global_best if conclusive_global_best is None else None,
        "global_elo_best_observed_profile_stats": observed_best_stats if conclusive_global_best is None else {},
        "global_sample_status": "ok" if conclusive_global_best else "insufficient_samples",
        "scenario_elo_best_profiles": scenario_best,
        "big_elo_loss_top_failure_reasons": big_loss_failure_counts.most_common(10),
        "top_failure_reasons_all_games": failure_counts.most_common(10),
        "profile_status": profile_status_summary(results, profiles),
        "opponent_overblock_count": overblock["opponent_overblock_count"],
        "opponent_overblock_rate": overblock["opponent_overblock_rate"],
        "high_card_spent_early_count": overblock["high_card_spent_early_count"],
        "bomb_spent_early_count": overblock["bomb_spent_early_count"],
        "bait_high_card_success_count": overblock["bait_high_card_success_count"],
        "bait_high_card_failure_count": overblock["bait_high_card_failure_count"],
        "lead_probe_count": overblock["lead_probe_count"],
        "possible_overblock_count": overblock["possible_overblock_count"],
        "possible_overblock_rate": overblock["possible_overblock_rate"],
        "high_card_response_count": overblock["high_card_response_count"],
        "joker_response_count": overblock["joker_response_count"],
        "level_card_response_count": overblock["level_card_response_count"],
        "bomb_response_to_non_bomb_count": overblock["bomb_response_to_non_bomb_count"],
        "bait_attempt_count": overblock["bait_attempt_count"],
        "bait_candidate_count": overblock["bait_candidate_count"],
        "bait_selected_count": overblock["bait_selected_count"],
        "bait_response_observed_count": overblock["bait_response_observed_count"],
        "bait_overblocked_count": overblock["bait_overblocked_count"],
        "bait_success_count": overblock["bait_success_count"],
        "bait_failure_count": overblock["bait_failure_count"],
        "bait_candidate_overblocked_count": overblock["bait_candidate_overblocked_count"],
        "selected_without_candidate_count": overblock["selected_without_candidate_count"],
        "bait_candidate_inconsistent": overblock["bait_candidate_inconsistent"],
        "bait_no_candidate_reason_counts": overblock["bait_no_candidate_reason_counts"],
        "bait_not_attempted_reason_counts": overblock["bait_not_attempted_reason_counts"],
        "overblock_summary": overblock,
        "elo_economy_summary": economy,
        "recent_window_summary": recent_window_summary(results, recent_window, profiles),
        "insufficient_samples": insufficient_samples,
        "suggested_next_profiles": suggested_next_profiles[:30],
        "sample_rules": {
            "global_profile_min_games": GLOBAL_PROFILE_MIN_GAMES,
            "scenario_profile_min_games": SCENARIO_PROFILE_MIN_GAMES,
            "note": "Do not draw conclusions from 1-5 games.",
        },
    }


def research_log_index() -> dict[tuple[str, str], dict]:
    index: dict[tuple[str, str], dict] = {}
    for log_path in Path(".").glob("logs*/research_game_*.json"):
        try:
            payload = load_json(log_path, {})
        except Exception:
            continue
        if not isinstance(payload, dict):
            continue
        game_id = payload.get("game_id")
        profile = payload.get("profile")
        if not game_id or not profile:
            continue
        key = (str(game_id), str(profile))
        previous = index.get(key)
        if previous is None or str(payload.get("completed_at") or "") >= str(previous.get("completed_at") or ""):
            payload["_log_path"] = str(log_path)
            index[key] = payload
    return index


def compact_decision(decision: dict | None) -> dict | None:
    if not decision:
        return None
    return {
        "turn": decision.get("turn"),
        "play": decision.get("play") or [],
        "last_play": decision.get("last_play") or [],
        "last_player": decision.get("last_player"),
        "last_relation": decision.get("last_relation"),
        "hand_count": decision.get("hand_count"),
        "hand_counts": decision.get("hand_counts"),
        "min_opponent_count": decision.get("min_opponent_count"),
        "teammate_count": decision.get("teammate_count"),
    }


def decision_failure_labels(decision: dict) -> list[str]:
    labels: list[str] = []
    play = decision.get("play") or []
    hand_counts = decision.get("hand_counts") or []
    play_len = len(play)
    if decision.get("min_opponent_count", 99) <= 2 and not play:
        labels.extend(["missed_block", "bad_endgame_pass"])
    if play_len and play_len in {int(count) for count in hand_counts if isinstance(count, int) and 0 < count <= 6}:
        labels.extend(["bad_lead_size", "opened_exact_length_to_opponent"])
    if decision.get("last_relation") == "teammate" and play:
        labels.append("bad_teammate_override")
    if decision.get("play_is_bomb") and decision.get("hand_count", 99) > 10:
        labels.append("useless_bomb")
    if decision.get("bad_lead_size_risk") or decision.get("giving_control_to_strong_opponent_risk"):
        labels.append("gave_strong_opponent_control")
    return labels


def first_major_failure_decision(decisions: list[dict], failure_tags: list[str]) -> dict | None:
    failure_set = set(failure_tags)
    for decision in decisions:
        labels = decision_failure_labels(decision)
        if labels and (not failure_set or failure_set.intersection(labels)):
            return decision
    return None


def last_lead_decision(decisions: list[dict]) -> dict | None:
    for decision in reversed(decisions):
        if decision.get("play") and not (decision.get("last_play") or []):
            return decision
    return None


def last_control_loss_decision(decisions: list[dict]) -> dict | None:
    for decision in reversed(decisions):
        labels = set(decision_failure_labels(decision))
        if labels.intersection({"gave_strong_opponent_control", "bad_lead_size", "opened_exact_length_to_opponent"}):
            return decision
    return None


def counts_at_decision(final_state: dict, decision: dict | None) -> tuple[list[int] | None, int | None, int | None]:
    if not decision:
        return None, None, None
    hand_counts = decision.get("hand_counts") or []
    try:
        opponents = opponent_seats(final_state)
    except Exception:
        opponents = []
    opponent_counts = []
    for seat in opponents:
        try:
            opponent_counts.append(int(hand_counts[seat]))
        except (IndexError, TypeError, ValueError):
            pass
    try:
        ally = teammate_seat(final_state)
        teammate_count_value = int(hand_counts[ally])
    except (KeyError, IndexError, TypeError, ValueError):
        teammate_count_value = decision.get("teammate_count")
    self_count = decision.get("hand_count")
    try:
        self_count = int(self_count)
    except (TypeError, ValueError):
        self_count = None
    return opponent_counts or None, teammate_count_value, self_count


def bait_loss_attribution(decisions: list[dict], failure_tags: list[str]) -> dict:
    bait_summary = summarize_bait_and_overblock(decisions, Counter(failure_tags), {"elo_delta": None})
    bait_decisions = [decision for decision in decisions if decision.get("bait_play") or decision.get("bait_selected")]
    bait_caused_bad_lead_size = any(
        "bad_lead_size" in decision_failure_labels(decision)
        or "opened_exact_length_to_opponent" in decision_failure_labels(decision)
        for decision in bait_decisions
    )
    bait_caused_opened_exact = any(
        "opened_exact_length_to_opponent" in decision_failure_labels(decision)
        for decision in bait_decisions
    )
    bait_caused_control_loss = any(
        decision.get("opponent_overblock_event")
        or decision.get("possible_overblock_event")
        or "gave_strong_opponent_control" in decision_failure_labels(decision)
        for decision in bait_decisions
    )
    bait_attempted = bool(bait_summary.get("bait_attempt_count"))
    related = bool(
        bait_attempted
        and (
            bait_summary.get("bait_failure_count")
            or bait_caused_control_loss
            or bait_caused_bad_lead_size
        )
    )
    return {
        "bait_attempt_count": bait_summary.get("bait_attempt_count", 0),
        "bait_selected_count": bait_summary.get("bait_selected_count", 0),
        "bait_candidate_count": bait_summary.get("bait_candidate_count", 0),
        "bait_success_count": bait_summary.get("bait_success_count", 0),
        "bait_failure_count": bait_summary.get("bait_failure_count", 0),
        "bait_no_candidate_reason_counts": bait_summary.get("bait_no_candidate_reason_counts", {}),
        "bait_not_attempted_reason_counts": bait_summary.get("bait_not_attempted_reason_counts", {}),
        "bait_failure_related_to_loss": related,
        "bait_caused_control_loss": bool(bait_caused_control_loss),
        "bait_caused_bad_lead_size": bool(bait_caused_bad_lead_size),
        "bait_caused_opened_exact_length_to_opponent": bool(bait_caused_opened_exact),
        "bait_was_neutral_but_lost_later": bool(bait_attempted and not related),
    }


def loss_drilldown_summary(results: dict, profile: str, recent_loss_window: int) -> dict:
    records = official_game_records(results)
    profile_records = [record for record in records if record.get("profile") == profile]
    recent_records = profile_records[-recent_loss_window:] if recent_loss_window > 0 else []
    recent_losses = [record for record in recent_records if record.get("outcome") == "loss"]
    logs = research_log_index()
    items = []
    for record in recent_losses:
        game_id = str(record.get("game_id"))
        payload = logs.get((game_id, profile), {})
        decisions = payload.get("decisions") or []
        final_state = payload.get("final_state") or {}
        failure_tags = record.get("failure_tags") or payload.get("failure_tags") or []
        failure_decision = first_major_failure_decision(decisions, failure_tags)
        opponent_counts, teammate_count_value, self_count = counts_at_decision(final_state, failure_decision)
        if decisions:
            bait_summary = summarize_bait_and_overblock(decisions, Counter(failure_tags), {"elo_delta": record.get("elo_delta")})
            bait_counts = {
                "bait_attempt_count": int(bait_summary.get("bait_attempt_count") or 0),
                "bait_success_count": int(bait_summary.get("bait_success_count") or 0),
                "bait_failure_count": int(bait_summary.get("bait_failure_count") or 0),
            }
        else:
            bait_counts = bait_counts_from_record(record)
        item = {
            "game_id": game_id,
            "completed_at": record.get("completed_at"),
            "elo_before": record.get("elo_before"),
            "elo_after": record.get("elo_after"),
            "elo_delta": record.get("elo_delta"),
            "scenario": record.get("scenario"),
            "failure_tags": failure_tags,
            "first_major_failure_turn": failure_decision.get("turn") if failure_decision else None,
            "last_lead_before_loss": compact_decision(last_lead_decision(decisions)),
            "last_play_before_opponent_control": compact_decision(last_control_loss_decision(decisions)),
            "opponent_remaining_counts_at_failure": opponent_counts,
            "teammate_remaining_count_at_failure": teammate_count_value,
            "self_remaining_count_at_failure": self_count,
            "whether_gave_control": bool(
                "gave_strong_opponent_control" in failure_tags
                or any("gave_strong_opponent_control" in decision_failure_labels(decision) for decision in decisions)
            ),
            "whether_bad_endgame_pass": "bad_endgame_pass" in failure_tags,
            "whether_opened_exact_length_to_opponent": "opened_exact_length_to_opponent" in failure_tags,
            "whether_useless_bomb": "useless_bomb" in failure_tags,
            "whether_bait_attempted": bool(bait_counts.get("bait_attempt_count")),
            "whether_bait_success": bool(bait_counts.get("bait_success_count")),
            "whether_bait_failure": bool(bait_counts.get("bait_failure_count")),
            "log_available": bool(payload),
            "log_path": payload.get("_log_path"),
        }
        if profile == "bait_high_card":
            item.update(bait_loss_attribution(decisions, failure_tags))
        items.append(item)
    return {
        "profile": profile,
        "recent_loss_window": recent_loss_window,
        "recent_games_considered": len(recent_records),
        "losses_found": len(items),
        "record_source": "game_records",
        "detail_source": "logs*/research_game_*.json",
        "losses": items,
    }


def relevant_endgame_audit_decision(decisions: list[dict], failure_tags: list[str]) -> dict | None:
    for decision in decisions:
        if (
            decision.get("last_relation") == "opponent"
            and (decision.get("last_play") or [])
            and int(decision.get("min_opponent_count") or 99) <= 6
            and not (decision.get("play") or [])
        ):
            return decision
    failure_set = set(failure_tags)
    for decision in decisions:
        labels = set(decision_failure_labels(decision))
        if labels.intersection({"missed_block", "bad_endgame_pass"}) and (
            not failure_set or failure_set.intersection(labels)
        ):
            return decision
    return first_major_failure_decision(decisions, failure_tags) or last_control_loss_decision(decisions)


def play_info_for_cards(cards: list[str], last_play: list[str], level: str) -> Any:
    infos = engine.safe_follow_infos(cards, last_play, level) if last_play else engine.canonical_table_infos(cards, level)
    if not infos:
        return None
    return max(
        infos,
        key=lambda info: (
            1 if engine.is_bomb(info) else 0,
            engine.bomb_key(info, level) if engine.is_bomb(info) else (0.0, engine.rank_value(info, level)),
        ),
    )


def play_summary(cards: list[str] | tuple[str, ...] | None, level: str, last_play: list[str] | None = None, hand: list[str] | None = None) -> dict | None:
    if not cards:
        return None
    card_list = list(cards)
    info = play_info_for_cards(card_list, last_play or [], level)
    groups_after = None
    structure_cost = None
    if hand is not None:
        try:
            remaining = engine.remove_cards(hand, card_list)
            groups_after = engine.estimate_remaining_groups(remaining, level)
            structure_cost = engine.structure_cost(card_list, hand, level)
        except Exception:
            pass
    return {
        "cards": engine.sort_cards(card_list, level),
        "type": info.type if info else None,
        "rank": info.rank if info else None,
        "size": len(card_list),
        "is_bomb": bool(info and engine.is_bomb(info)),
        "structure_cost": structure_cost,
        "groups_after": groups_after,
    }


def block_option_sort_key(option: dict) -> tuple:
    return (
        1 if option.get("is_bomb") else 0,
        option.get("structure_cost") if option.get("structure_cost") is not None else 999,
        option.get("groups_after") if option.get("groups_after") is not None else 999.0,
        option.get("rank_value") if option.get("rank_value") is not None else 999,
        option.get("size") or 99,
        option.get("cards") or [],
    )


def block_option_strength_key(option: dict) -> tuple:
    return (
        option.get("bomb_tier") or 0.0,
        option.get("rank_value") if option.get("rank_value") is not None else -1,
        option.get("size") or 0,
    )


def audit_bomb_candidate_cards(hand: list[str], level: str) -> list[list[str]]:
    wild_card = "H" + level
    wilds = [card for card in hand if card == wild_card]
    candidates: dict[tuple[str, ...], list[str]] = {}
    by_rank: dict[str, list[str]] = {rank: [] for rank in engine.RANKS}
    by_suit: dict[str, list[str]] = {suit: [] for suit in "SHDC"}
    jokers = Counter(card for card in hand if card in {"B", "R"})

    for card in hand:
        if card in {"B", "R"} or card == wild_card:
            continue
        by_rank[card[1]].append(card)
        by_suit[card[0]].append(card)

    for rank, cards_of_rank in by_rank.items():
        pool = cards_of_rank + wilds
        for size in range(4, len(pool) + 1):
            for combo in itertools.combinations(pool, size):
                sorted_cards = tuple(engine.sort_cards(list(combo), level))
                if any(info.type == "bomb" for info in engine.recognize(sorted_cards, level)):
                    candidates[sorted_cards] = list(sorted_cards)

    for suit, suited_cards in by_suit.items():
        pool = suited_cards + wilds
        if len(pool) < 5:
            continue
        for combo in itertools.combinations(pool, 5):
            sorted_cards = tuple(engine.sort_cards(list(combo), level))
            if any(info.type == "straight_flush" for info in engine.recognize(sorted_cards, level)):
                candidates[sorted_cards] = list(sorted_cards)

    if jokers.get("B", 0) >= 2 and jokers.get("R", 0) >= 2:
        cards = ["B", "B", "R", "R"]
        candidates[tuple(cards)] = cards

    return list(candidates.values())


def audit_follow_candidate_cards(hand: list[str], last_play: list[str], level: str) -> list[list[str]]:
    candidates: dict[tuple[str, ...], list[str]] = {}
    last_infos = engine.canonical_table_infos(last_play, level)
    last_is_bomb = any(engine.is_bomb(info) for info in last_infos)
    if not last_is_bomb and len(last_play) <= 6:
        for combo in itertools.combinations(hand, len(last_play)):
            sorted_cards = tuple(engine.sort_cards(list(combo), level))
            candidates[sorted_cards] = list(sorted_cards)
    for cards in audit_bomb_candidate_cards(hand, level):
        candidates[tuple(cards)] = cards
    return list(candidates.values())


def legal_block_options(hand: list[str], last_play: list[str], level: str) -> list[dict]:
    if not hand or not last_play or not level:
        return []
    seen = set()
    options = []
    for cards in audit_follow_candidate_cards(hand, last_play, level):
        key = tuple(cards)
        if key in seen:
            continue
        try:
            follow_infos = engine.safe_follow_infos(cards, last_play, level)
        except Exception:
            follow_infos = []
        if not follow_infos:
            continue
        best_info = max(
            follow_infos,
            key=lambda item: (
                1 if engine.is_bomb(item) else 0,
                engine.bomb_key(item, level) if engine.is_bomb(item) else (0.0, engine.rank_value(item, level)),
            ),
        )
        try:
            remaining = engine.remove_cards(hand, cards)
            groups_after = engine.estimate_remaining_groups(remaining, level)
            structure_cost = engine.structure_cost(cards, hand, level)
        except Exception:
            groups_after = None
            structure_cost = None
        is_bomb = engine.is_bomb(best_info)
        options.append(
            {
                "cards": engine.sort_cards(cards, level),
                "type": best_info.type,
                "rank": best_info.rank,
                "size": len(cards),
                "is_bomb": bool(is_bomb),
                "structure_cost": structure_cost,
                "groups_after": groups_after,
                "rank_value": engine.rank_value(best_info, level),
                "bomb_tier": engine.bomb_key(best_info, level)[0] if is_bomb else 0.0,
            }
        )
        seen.add(key)
    return sorted(options, key=block_option_sort_key)


OFFLINE_BLOCK_OPTIONS_CACHE: dict[tuple[tuple[str, ...], tuple[str, ...], str], list[dict]] = {}


def cached_legal_block_options(hand: list[str], last_play: list[str], level: str) -> list[dict]:
    if not hand or not last_play or not level:
        return []
    key = (
        tuple(engine.sort_cards(list(hand), level)),
        tuple(engine.sort_cards(list(last_play), level)),
        level,
    )
    if key not in OFFLINE_BLOCK_OPTIONS_CACHE:
        OFFLINE_BLOCK_OPTIONS_CACHE[key] = legal_block_options(list(key[0]), list(key[1]), level)
    return OFFLINE_BLOCK_OPTIONS_CACHE[key]


def option_is_expensive(option: dict, groups_before: float | None) -> bool:
    if option.get("is_bomb"):
        return True
    if option.get("structure_cost") is not None and float(option["structure_cost"]) >= 45.0:
        return True
    if (
        groups_before is not None
        and option.get("groups_after") is not None
        and float(option["groups_after"]) > float(groups_before) + 0.01
    ):
        return True
    return False


def endgame_block_reason(decision: dict, options: list[dict]) -> str | None:
    if not (decision.get("last_play") or []):
        return None
    if decision.get("play") or []:
        return None
    if not options:
        return "no_legal_block"
    groups_before = decision.get("groups_before")
    try:
        groups_before = float(groups_before)
    except (TypeError, ValueError):
        groups_before = None
    if all(option_is_expensive(option, groups_before) for option in options):
        return "block_available_but_expensive"
    return "cheap_block_missed"


def opened_exact_length_targets(decision: dict, final_state: dict) -> list[int]:
    play = decision.get("play") or []
    if not play or (decision.get("last_play") or []):
        return []
    hand_counts = decision.get("hand_counts") or []
    targets = []
    for seat in opponent_seats(final_state):
        try:
            if int(hand_counts[seat]) == len(play):
                targets.append(int(seat))
        except (IndexError, TypeError, ValueError):
            continue
    return targets


def first_opened_exact_length_decision(decisions: list[dict], final_state: dict) -> tuple[dict | None, list[int]]:
    for decision in decisions:
        targets = opened_exact_length_targets(decision, final_state)
        if targets:
            return decision, targets
    return None, []


def game_gave_control(decisions: list[dict], failure_tags: list[str]) -> bool:
    if "gave_strong_opponent_control" in failure_tags:
        return True
    return any("gave_strong_opponent_control" in decision_failure_labels(decision) for decision in decisions)


def recommended_safe_action(options: list[dict], decision: dict) -> dict | None:
    if not options:
        return None
    groups_before = decision.get("groups_before")
    try:
        groups_before = float(groups_before)
    except (TypeError, ValueError):
        groups_before = None
    cheap = [option for option in options if not option_is_expensive(option, groups_before)]
    return (cheap or options)[0]


def endgame_audit_item(record: dict, payload: dict, profile: str) -> dict:
    game_id = str(record.get("game_id"))
    decisions = payload.get("decisions") or []
    final_state = payload.get("final_state") or {}
    failure_tags = record.get("failure_tags") or payload.get("failure_tags") or []
    decision = relevant_endgame_audit_decision(decisions, failure_tags)
    opponent_counts, teammate_count_value, self_count = counts_at_decision(final_state, decision)
    _exact_decision, exact_targets = first_opened_exact_length_decision(decisions, final_state)
    if decision:
        level = decision.get("level")
        hand = decision.get("hand") or []
        last_play = decision.get("last_play") or []
        chosen = decision.get("play") or []
        options = legal_block_options(hand, last_play, level)
        smallest = options[0] if options else None
        strongest = max(options, key=block_option_strength_key) if options else None
        reason = endgame_block_reason(decision, options)
        should_have_blocked = bool(
            decision.get("last_relation") == "opponent"
            and int(decision.get("min_opponent_count") or 99) <= 6
            and last_play
            and not chosen
            and options
        )
        chosen_info = play_info_for_cards(chosen, last_play, level) if chosen else None
        try:
            chosen_beats = bool(chosen and last_play and engine.play_beats(chosen, last_play, level))
        except Exception:
            chosen_beats = False
        last_info = play_info_for_cards(last_play, [], level) if last_play else None
        safe_action = recommended_safe_action(options, decision)
    else:
        level = None
        last_play = []
        chosen = []
        options = []
        smallest = None
        strongest = None
        reason = "no_decision_log"
        should_have_blocked = False
        chosen_info = None
        chosen_beats = False
        last_info = None
        safe_action = None

    return {
        "game_id": game_id,
        "completed_at": record.get("completed_at"),
        "elo_before": record.get("elo_before"),
        "elo_after": record.get("elo_after"),
        "elo_delta": record.get("elo_delta"),
        "scenario": record.get("scenario"),
        "failure_tags": failure_tags,
        "opponent_remaining_counts_at_failure": opponent_counts,
        "teammate_remaining_count_at_failure": teammate_count_value,
        "self_remaining_count_at_failure": self_count,
        "last_play": last_play,
        "last_play_type": last_info.type if last_info else None,
        "last_play_size": len(last_play),
        "current_turn_player": decision.get("current_turn") if decision else None,
        "was_my_turn": bool(decision),
        "did_i_pass": bool(decision and not (decision.get("play") or [])),
        "legal_block_options_count": len(options),
        "legal_block_options_summary": options[:8],
        "smallest_legal_block": smallest,
        "strongest_legal_block": strongest,
        "chosen_action": chosen,
        "chosen_action_type": chosen_info.type if chosen_info else None,
        "chosen_action_size": len(chosen),
        "chosen_action_beats_last_play": chosen_beats,
        "should_have_blocked": should_have_blocked,
        "block_missed_reason": reason,
        "opened_exact_length_to_which_opponent": exact_targets,
        "opponent_remaining_equals_lead_size": bool(exact_targets),
        "opened_exact_length_to_opponent": bool(exact_targets),
        "gave_strong_opponent_control": game_gave_control(decisions, failure_tags),
        "recommended_safe_action": safe_action,
        "log_available": bool(payload),
        "log_path": payload.get("_log_path"),
    }


def endgame_audit_summary(results: dict, profile: str, recent_loss_window: int) -> dict:
    records = official_game_records(results)
    profile_losses = [record for record in records if record.get("profile") == profile and record.get("outcome") == "loss"]
    recent_losses = profile_losses[-recent_loss_window:] if recent_loss_window > 0 else profile_losses
    logs = research_log_index()
    items = []
    for record in recent_losses:
        game_id = str(record.get("game_id"))
        payload = logs.get((game_id, profile), {})
        items.append(endgame_audit_item(record, payload, profile))

    recommended_counts = Counter()
    for item in items:
        action = item.get("recommended_safe_action")
        if action:
            key = f"{action.get('type')}:{action.get('rank')}:{action.get('size')}:{','.join(action.get('cards') or [])}"
            recommended_counts[key] += 1

    return {
        "profile": profile,
        "recent_loss_window": recent_loss_window,
        "record_source": "game_records",
        "detail_source": "logs*/research_game_*.json",
        "audited_losses": len(items),
        "missed_block_true_count": sum(1 for item in items if item.get("should_have_blocked")),
        "missed_block_no_legal_block_count": sum(
            1 for item in items if item.get("block_missed_reason") == "no_legal_block"
        ),
        "cheap_block_missed_count": sum(
            1 for item in items if item.get("block_missed_reason") == "cheap_block_missed"
        ),
        "block_available_but_expensive_count": sum(
            1 for item in items if item.get("block_missed_reason") == "block_available_but_expensive"
        ),
        "bad_endgame_pass_true_count": sum(1 for item in items if item.get("did_i_pass") and item.get("should_have_blocked")),
        "opened_exact_length_true_count": sum(1 for item in items if item.get("opened_exact_length_to_opponent")),
        "gave_control_true_count": sum(1 for item in items if item.get("gave_strong_opponent_control")),
        "top_recommended_safe_actions": recommended_counts.most_common(10),
        "losses": items,
    }


def decision_after_hand(decision: dict) -> list[str]:
    hand = decision.get("hand") or []
    play = decision.get("play") or []
    if not play:
        return list(hand)
    try:
        return engine.remove_cards(hand, play)
    except Exception:
        return list(hand)


def decision_opponent_counts(final_state: dict, decision: dict) -> list[int]:
    hand_counts = decision.get("hand_counts") or []
    counts = []
    for seat in opponent_seats(final_state):
        try:
            counts.append(int(hand_counts[seat]))
        except (IndexError, TypeError, ValueError):
            continue
    return counts


def action_rank_type(cards: list[str], last_play: list[str], level: str) -> tuple[str | None, str | None]:
    if not cards:
        return None, None
    info = play_info_for_cards(cards, last_play, level)
    return (info.type if info else None, info.rank if info else None)


def action_consumes_control_card(cards: list[str], level: str) -> bool:
    for card in cards:
        if card in {"B", "R"}:
            return True
        if card_rank(card) in {"2", level}:
            return True
    return False


def safe_alternative_actions(decision: dict, final_state: dict) -> list[dict]:
    hand = decision.get("hand") or []
    level = decision.get("level")
    last_play = decision.get("last_play") or []
    if not hand or not level:
        return []
    groups_before = decision.get("groups_before")
    try:
        groups_before = float(groups_before)
    except (TypeError, ValueError):
        groups_before = engine.estimate_remaining_groups(hand, level)
    opponent_counts = decision_opponent_counts(final_state, decision)
    opponent_min = min(opponent_counts) if opponent_counts else 99
    alternatives = []
    seen = set()
    for info in engine.legal_play_options(hand, level):
        cards = list(info.cards)
        key = tuple(cards)
        if key in seen:
            continue
        seen.add(key)
        if last_play and not engine.play_beats(cards, last_play, level):
            continue
        if not last_play and not cards:
            continue
        if engine.server_treats_as_bomb(cards, level) and len(cards) < len(hand):
            continue
        if len(cards) in {count for count in opponent_counts if count > 0}:
            continue
        if not last_play and len(cards) <= opponent_min <= 4:
            continue
        try:
            groups_after = engine.estimate_remaining_groups(engine.remove_cards(hand, cards), level)
            structure_cost = engine.structure_cost(cards, hand, level)
        except Exception:
            continue
        if structure_cost > 0 or groups_after > groups_before + 0.01:
            continue
        summary = play_summary(cards, level, last_play, hand)
        if not summary:
            continue
        summary["groups_after"] = groups_after
        summary["structure_cost"] = structure_cost
        alternatives.append(summary)
    return sorted(
        alternatives,
        key=lambda item: (
            item.get("groups_after") if item.get("groups_after") is not None else 999.0,
            item.get("structure_cost") if item.get("structure_cost") is not None else 999,
            item.get("size") or 99,
            item.get("cards") or [],
        ),
    )


def consumed_potential_block(decision: dict, final_decision: dict | None) -> bool:
    if not final_decision or not (decision.get("play") or []):
        return False
    final_last_play = final_decision.get("last_play") or []
    level = decision.get("level")
    if not final_last_play or not level:
        return False
    before_hand = decision.get("hand") or []
    after_hand = decision_after_hand(decision)
    if not before_hand:
        return False
    before_options = cached_legal_block_options(before_hand, final_last_play, level)
    if not before_options:
        return False
    after_options = cached_legal_block_options(after_hand, final_last_play, level)
    return not after_options


def left_without_block_shape(decision: dict, final_decision: dict | None) -> bool:
    if not final_decision:
        return False
    final_last_play = final_decision.get("last_play") or []
    level = decision.get("level")
    if not final_last_play or not level:
        return False
    after_hand = decision_after_hand(decision)
    return not cached_legal_block_options(after_hand, final_last_play, level)


def preloss_decision_summary(decision: dict, final_state: dict, final_decision: dict | None) -> dict:
    hand = decision.get("hand") or []
    play = decision.get("play") or []
    level = decision.get("level")
    last_play = decision.get("last_play") or []
    opponent_counts = decision_opponent_counts(final_state, decision)
    teammate_count_value = decision.get("teammate_count")
    groups_before = decision.get("groups_before")
    groups_after = decision.get("groups_after")
    try:
        groups_before_number = float(groups_before)
    except (TypeError, ValueError):
        groups_before_number = None
    try:
        groups_after_number = float(groups_after)
    except (TypeError, ValueError):
        groups_after_number = None
    action_type, action_rank = action_rank_type(play, last_play, level) if level else (None, None)
    try:
        chosen_beats = bool(play and last_play and engine.play_beats(play, last_play, level))
    except Exception:
        chosen_beats = False
    exact_targets = opened_exact_length_targets(decision, final_state)
    alternatives = safe_alternative_actions(decision, final_state)
    structure_cost = 0
    if play and level:
        try:
            structure_cost = engine.structure_cost(play, hand, level)
        except Exception:
            structure_cost = 0
    broke_structure = bool(
        structure_cost > 0
        or (
            groups_before_number is not None
            and groups_after_number is not None
            and groups_after_number > groups_before_number + 0.01
        )
    )
    return {
        "turn_index": decision.get("turn"),
        "my_remaining_before": decision.get("hand_count"),
        "my_remaining_after": (int(decision.get("hand_count") or len(hand)) - len(play)) if play else decision.get("hand_count"),
        "teammate_remaining": teammate_count_value,
        "opponent_remaining_counts": opponent_counts,
        "was_lead": not bool(last_play),
        "last_play_before_action": last_play,
        "chosen_action": play,
        "chosen_action_type": action_type,
        "chosen_action_size": len(play),
        "chosen_action_rank": action_rank,
        "chosen_action_beats_last_play": chosen_beats,
        "remaining_groups_before": groups_before,
        "remaining_groups_after": groups_after,
        "did_reduce_groups": bool(
            groups_before_number is not None
            and groups_after_number is not None
            and groups_after_number < groups_before_number - 0.01
        ),
        "did_increase_groups": bool(
            groups_before_number is not None
            and groups_after_number is not None
            and groups_after_number > groups_before_number + 0.01
        ),
        "gave_control_after_action": bool("gave_strong_opponent_control" in decision_failure_labels(decision)),
        "opened_exact_length_to_opponent": bool(exact_targets),
        "left_self_without_block_shape": left_without_block_shape(decision, final_decision),
        "consumed_potential_block_card": consumed_potential_block(decision, final_decision),
        "consumed_2_or_joker_or_level_card": bool(level and action_consumes_control_card(play, level)),
        "broke_pair_or_triple_or_straight": broke_structure,
        "alternative_safe_actions_count": len(alternatives),
        "best_alternative_safe_action": alternatives[0] if alternatives else None,
        **{key: int(decision.get(key) or 0) for key in SHAPE_GUARD_COUNTER_KEYS},
        **{key: int(decision.get(key) or 0) for key in SHAPE_GUARD_V2_COUNTER_KEYS},
        "shape_guard_v2_safe_alt_rejected_reason_counts": decision.get(
            "shape_guard_v2_safe_alt_rejected_reason_counts"
        )
        or {},
    }


def preloss_risk_labels(item: dict) -> list[str]:
    labels = []
    if item.get("gave_control_after_action"):
        labels.append("gave_control_after_action")
    if item.get("opened_exact_length_to_opponent"):
        labels.append("opened_exact_length_to_opponent")
    if item.get("left_self_without_block_shape"):
        labels.append("left_self_without_block_shape")
    if item.get("consumed_potential_block_card"):
        labels.append("consumed_potential_block_card")
    if item.get("consumed_2_or_joker_or_level_card"):
        labels.append("consumed_2_or_joker_or_level_card")
    if item.get("broke_pair_or_triple_or_straight"):
        labels.append("broke_pair_or_triple_or_straight")
    if item.get("did_increase_groups"):
        labels.append("did_increase_groups")
    return labels


def preloss_trace_item(record: dict, payload: dict, profile: str, preloss_turns: int) -> dict:
    decisions = payload.get("decisions") or []
    final_state = payload.get("final_state") or {}
    failure_tags = record.get("failure_tags") or payload.get("failure_tags") or []
    audit = endgame_audit_item(record, payload, profile)
    final_decision = relevant_endgame_audit_decision(decisions, failure_tags)
    final_turn = final_decision.get("turn") if final_decision else None
    if final_turn is not None:
        preloss_decisions = [
            decision for decision in decisions
            if decision.get("turn") is not None and int(decision.get("turn")) < int(final_turn)
        ]
    else:
        preloss_decisions = decisions
    if preloss_turns > 0:
        preloss_decisions = preloss_decisions[-preloss_turns:]
    summaries = [preloss_decision_summary(decision, final_state, final_decision) for decision in preloss_decisions]
    return {
        "game_id": str(record.get("game_id")),
        "elo_delta": record.get("elo_delta"),
        "scenario": record.get("scenario"),
        "final_failure_tags": failure_tags,
        "final_block_missed_reason": audit.get("block_missed_reason"),
        "final_legal_block_options_count": audit.get("legal_block_options_count"),
        "preloss_my_decisions": summaries,
    }


def preloss_trace_summary(results: dict, profile: str, recent_loss_window: int, preloss_turns: int) -> dict:
    records = official_game_records(results)
    profile_losses = [record for record in records if record.get("profile") == profile and record.get("outcome") == "loss"]
    recent_losses = profile_losses[-recent_loss_window:] if recent_loss_window > 0 else profile_losses
    logs = research_log_index()
    items = []
    risk_counts = Counter()
    shape_counts = Counter()
    shape_v2_counts = Counter()
    shape_v2_reasons = Counter()
    for record in recent_losses:
        game_id = str(record.get("game_id"))
        payload = logs.get((game_id, profile), {})
        item = preloss_trace_item(record, payload, profile, preloss_turns)
        items.append(item)
        shape_counts.update(shape_guard_counts_from_record(record))
        shape_v2 = shape_guard_v2_counts_from_record(record)
        for key in SHAPE_GUARD_V2_COUNTER_KEYS:
            shape_v2_counts[key] += int(shape_v2.get(key) or 0)
        merge_reason_counts(shape_v2_reasons, shape_v2.get("shape_guard_v2_safe_alt_rejected_reason_counts"))
        seen_labels = set()
        for decision in item.get("preloss_my_decisions") or []:
            for label in preloss_risk_labels(decision):
                risk_counts[label] += 1
                seen_labels.add(label)
        for label in sorted(seen_labels):
            risk_counts[f"loss_with_{label}"] += 1

    return {
        "profile": profile,
        "recent_loss_window": recent_loss_window,
        "preloss_turns": preloss_turns,
        "record_source": "game_records",
        "detail_source": "logs*/research_game_*.json",
        "traced_losses": len(items),
        "no_legal_block_losses": sum(1 for item in items if item.get("final_block_missed_reason") == "no_legal_block"),
        "gave_control_before_loss_count": sum(
            1 for item in items
            if any(decision.get("gave_control_after_action") for decision in item.get("preloss_my_decisions") or [])
        ),
        "consumed_block_card_before_loss_count": sum(
            1 for item in items
            if any(decision.get("consumed_potential_block_card") for decision in item.get("preloss_my_decisions") or [])
        ),
        "broke_structure_before_loss_count": sum(
            1 for item in items
            if any(decision.get("broke_pair_or_triple_or_straight") for decision in item.get("preloss_my_decisions") or [])
        ),
        "opened_exact_length_before_loss_count": sum(
            1 for item in items
            if any(decision.get("opened_exact_length_to_opponent") for decision in item.get("preloss_my_decisions") or [])
        ),
        **{key: shape_counts[key] for key in SHAPE_GUARD_COUNTER_KEYS},
        **{key: shape_v2_counts[key] for key in SHAPE_GUARD_V2_COUNTER_KEYS},
        "shape_guard_v2_safe_alt_rejected_reason_counts": dict(shape_v2_reasons),
        "top_pre_loss_risk_patterns": risk_counts.most_common(12),
        "losses": items,
    }


OFFLINE_RISK_PATTERNS = (
    "gave_strong_opponent_control",
    "opened_exact_length_to_opponent",
    "left_self_without_block_shape",
    "consumed_potential_block_card",
    "consumed_2_or_joker_or_level_card",
    "broke_pair_or_triple_or_straight",
    "did_increase_groups",
    "used_bomb",
    "used_joker",
    "bad_lead_size",
    "missed_block",
)


def used_level_card(cards: list[str], level: str | None) -> bool:
    if not level:
        return False
    return any(card not in {"B", "R"} and card_rank(card) == level for card in cards)


def risk_patterns_for_decision_row(row: dict) -> list[str]:
    patterns = []
    for key in (
        "gave_strong_opponent_control",
        "opened_exact_length_to_opponent",
        "left_self_without_block_shape",
        "consumed_potential_block_card",
        "consumed_2_or_joker_or_level_card",
        "broke_pair_or_triple_or_straight",
        "did_increase_groups",
        "used_bomb",
        "used_joker",
    ):
        if row.get(key):
            patterns.append(key)
    action_size = int(row.get("chosen_action_size") or 0)
    opponent_counts = row.get("opponent_remaining_counts") or []
    if action_size and action_size in {int(count) for count in opponent_counts if 0 < int(count) <= 6}:
        patterns.append("bad_lead_size")
    if row.get("was_follow") and not row.get("chosen_action") and opponent_counts and min(opponent_counts) <= 6:
        patterns.append("missed_block")
    return sorted(set(patterns))


def offline_shape_flags(decision: dict) -> tuple[bool, bool]:
    level = decision.get("level")
    if not level:
        return False, False
    before_hand = decision.get("hand") or []
    after_hand = decision_after_hand(decision)
    before_score = potential_block_shape_score(before_hand, level)
    after_score = potential_block_shape_score(after_hand, level)
    left_without = bool(before_score > 0 and after_score <= 0)
    consumed_potential = bool((decision.get("play") or []) and after_score < before_score)
    return left_without, consumed_potential


def decision_dataset_row(record: dict, payload: dict, decision: dict, final_decision: dict | None) -> dict:
    final_state = payload.get("final_state") or {}
    hand = decision.get("hand") or []
    play = decision.get("play") or []
    level = decision.get("level")
    last_play = decision.get("last_play") or []
    action_type, action_rank = action_rank_type(play, last_play, level) if level else (None, None)
    groups_before = decision.get("groups_before")
    groups_after = decision.get("groups_after")
    try:
        groups_before_number = float(groups_before)
    except (TypeError, ValueError):
        groups_before_number = None
    try:
        groups_after_number = float(groups_after)
    except (TypeError, ValueError):
        groups_after_number = None
    try:
        chosen_beats = bool(play and last_play and engine.play_beats(play, last_play, level))
    except Exception:
        chosen_beats = False
    structure_cost = 0
    if play and level:
        try:
            structure_cost = engine.structure_cost(play, hand, level)
        except Exception:
            structure_cost = 0
    broke_structure = bool(
        structure_cost > 0
        or (
            groups_before_number is not None
            and groups_after_number is not None
            and groups_after_number > groups_before_number + 0.01
        )
    )
    left_without_shape, consumed_potential = offline_shape_flags(decision)
    row = {
        "game_id": str(record.get("game_id")),
        "profile": record.get("profile"),
        "outcome": record.get("outcome"),
        "elo_delta": record.get("elo_delta"),
        "scenario": record.get("scenario"),
        "turn_index": decision.get("turn"),
        "was_lead": not bool(last_play),
        "was_follow": bool(last_play),
        "hand_before": hand,
        "chosen_action": play,
        "chosen_action_type": action_type,
        "chosen_action_size": len(play),
        "chosen_action_rank": action_rank,
        "chosen_action_beats_last_play": chosen_beats,
        "last_play_before_action": last_play,
        "my_remaining_before": decision.get("hand_count"),
        "my_remaining_after": (int(decision.get("hand_count") or len(hand)) - len(play)) if play else decision.get("hand_count"),
        "teammate_remaining": decision.get("teammate_count"),
        "opponent_remaining_counts": decision_opponent_counts(final_state, decision),
        "remaining_groups_before": groups_before,
        "remaining_groups_after": groups_after,
        "did_reduce_groups": bool(
            groups_before_number is not None
            and groups_after_number is not None
            and groups_after_number < groups_before_number - 0.01
        ),
        "did_increase_groups": bool(
            groups_before_number is not None
            and groups_after_number is not None
            and groups_after_number > groups_before_number + 0.01
        ),
        "opened_exact_length_to_opponent": bool(opened_exact_length_targets(decision, final_state)),
        "gave_strong_opponent_control": bool("gave_strong_opponent_control" in decision_failure_labels(decision)),
        "left_self_without_block_shape": left_without_shape,
        "consumed_potential_block_card": consumed_potential,
        "consumed_2_or_joker_or_level_card": bool(level and action_consumes_control_card(play, level)),
        "broke_pair_or_triple_or_straight": broke_structure,
        "used_bomb": bool(play and level and engine.server_treats_as_bomb(play, level)),
        "used_joker": any(card in {"B", "R"} for card in play),
        "used_level_card": used_level_card(play, level),
        "failure_tags_of_game": record.get("failure_tags") or payload.get("failure_tags") or [],
    }
    row["risk_patterns"] = risk_patterns_for_decision_row(row)
    return row


def decision_rows_for_record(record: dict, payload: dict) -> list[dict]:
    decisions = payload.get("decisions") or []
    failure_tags = record.get("failure_tags") or payload.get("failure_tags") or []
    final_decision = relevant_endgame_audit_decision(decisions, failure_tags)
    return [decision_dataset_row(record, payload, decision, final_decision) for decision in decisions]


def decision_dataset_summary(results: dict, profile: str, decision_window: int) -> dict:
    records = [record for record in official_game_records(results) if record.get("profile") == profile]
    logs = research_log_index()
    rows = []
    missing_logs = 0
    for record in records:
        payload = logs.get((str(record.get("game_id")), profile), {})
        if not payload:
            missing_logs += 1
            continue
        rows.extend(decision_rows_for_record(record, payload))
    return {
        "profile": profile,
        "decision_window": decision_window,
        "record_source": "game_records",
        "detail_source": "logs*/research_game_*.json",
        "games": len(records),
        "missing_log_games": missing_logs,
        "decision_count": len(rows),
        "decisions": rows,
    }


def decision_shadow_state(record: dict, payload: dict, decision: dict) -> dict:
    hand_counts = list(decision.get("hand_counts") or [])
    try:
        your_seat = int(decision.get("current_turn"))
    except (TypeError, ValueError):
        your_seat = 0
    scenario = str(record.get("scenario") or decision.get("scenario") or "")
    return {
        "level": decision.get("level"),
        "your_hand": list(decision.get("hand") or []),
        "last_play": list(decision.get("last_play") or []),
        "last_player": decision.get("last_player"),
        "current_turn": your_seat,
        "your_seat": your_seat,
        "your_team": your_seat % 2,
        "teams": {str(seat): seat % 2 for seat in range(4)},
        "hand_counts": hand_counts,
        "seats": (payload.get("final_state") or {}).get("seats") or [],
        "_scenario_tags": [tag for tag in scenario.split("+") if tag],
        "_research_context": {
            "high_elo_risk": "high_elo_loss_risk" in scenario,
            "elo_before": record.get("elo_before"),
        },
    }


def action_summary_for_dataset(cards: list[str], decision: dict) -> dict:
    level = decision.get("level")
    last_play = decision.get("last_play") or []
    if not cards:
        return {"cards": [], "type": "pass", "rank": None, "size": 0}
    summary = play_summary(cards, level, last_play, decision.get("hand") or []) if level else None
    return summary or {"cards": list(cards), "type": None, "rank": None, "size": len(cards)}


def fast_action_summary_for_dataset(cards: list[str], decision: dict) -> dict:
    level = decision.get("level")
    last_play = decision.get("last_play") or []
    if not cards:
        return {"cards": [], "type": "pass", "rank": None, "size": 0}
    info = play_info_for_cards(cards, last_play, level) if level else None
    sorted_cards = engine.sort_cards(cards, level) if level else list(cards)
    return {
        "cards": sorted_cards,
        "type": info.type if info else None,
        "rank": info.rank if info else None,
        "size": len(cards),
    }


def bounded_legal_actions_for_dataset(decision: dict, payload: dict, limit: int = 80) -> tuple[list[dict], bool]:
    hand = decision.get("hand") or []
    level = decision.get("level")
    last_play = decision.get("last_play") or []
    chosen = decision.get("play") or []
    if not hand or not level:
        return [], False
    actions: list[dict] = []
    seen = set()

    def add(cards: list[str]) -> None:
        key = normalized_action_key(cards, level)
        if key in seen:
            return
        seen.add(key)
        actions.append(fast_action_summary_for_dataset(list(key), decision))

    if last_play:
        add([])
        if len(hand) <= 10:
            for option in cached_legal_block_options(hand, last_play, level)[:limit]:
                add(option.get("cards") or [])
        if chosen:
            add(chosen)
        return actions[:limit], len(actions) > limit

    for cards in casebook_lead_candidate_cards(hand, level):
        add(cards)
        if len(actions) >= limit:
            break
    if chosen:
        add(chosen)
    return actions[:limit], len(actions) > limit


def export_decision_dataset(profile: str, out_path: str) -> dict:
    results = load_json(RESULTS_PATH, {})
    records = [record for record in official_game_records(results) if record.get("profile") == profile]
    logs = research_log_index()
    path = Path(out_path)
    path.parent.mkdir(parents=True, exist_ok=True) if path.parent != Path(".") else None
    rows_written = 0
    missing_logs = 0
    with path.open("w", encoding="utf-8") as fh:
        for record in records:
            payload = logs.get((str(record.get("game_id")), profile), {})
            if not payload:
                missing_logs += 1
                continue
            decisions = payload.get("decisions") or []
            failure_tags = record.get("failure_tags") or payload.get("failure_tags") or []
            final_decision = relevant_endgame_audit_decision(decisions, failure_tags)
            for decision in decisions:
                row = decision_dataset_row(record, payload, decision, final_decision)
                legal_actions, legal_limited = bounded_legal_actions_for_dataset(decision, payload)
                row.update(
                    {
                        "elo_before": record.get("elo_before"),
                        "elo_after": record.get("elo_after"),
                        "level": decision.get("level"),
                        "legal_actions": legal_actions,
                        "legal_action_count": len(legal_actions),
                        "legal_actions_limited": legal_limited,
                        "is_loss_game": record.get("outcome") == "loss",
                        "is_big_elo_loss": bool(float(record.get("elo_delta") or 0.0) <= BIG_ELO_LOSS_THRESHOLD),
                        "metric_source": record.get("metric_source"),
                    }
                )
                fh.write(json.dumps(row, ensure_ascii=False) + "\n")
                rows_written += 1
    result = {
        "profile": profile,
        "dataset_out": str(path),
        "metric_source": "leaderboard_elo",
        "games": len(records),
        "missing_log_games": missing_logs,
        "decision_rows_written": rows_written,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return result


def clone_shadow_state(state: dict) -> dict:
    cloned = dict(state)
    for key in ("your_hand", "last_play", "hand_counts", "_scenario_tags"):
        if isinstance(cloned.get(key), list):
            cloned[key] = list(cloned[key])
    if isinstance(cloned.get("teams"), dict):
        cloned["teams"] = dict(cloned["teams"])
    if isinstance(cloned.get("_research_context"), dict):
        cloned["_research_context"] = dict(cloned["_research_context"])
    return cloned


def shadow_policy_may_change(record: dict, payload: dict, decision: dict, policy: str) -> bool:
    state = decision_shadow_state(record, payload, decision)
    original = decision.get("play") or []
    last_play = decision.get("last_play") or []
    if policy == "tempo_plate_delay_guard":
        return True
    if policy == "tempo_shape_guard":
        if not is_tempo_shape_guard_active(state):
            return False
        if last_play:
            return bool(original and engine.relation_to_last(state) == "opponent")
        return bool(original)
    if policy == "tempo_shape_guard_v2":
        if not is_tempo_shape_guard_active(state):
            return False
        return bool(original)
    if policy == "tempo_endgame_guard":
        if not is_tempo_endgame_guard_active(state):
            return False
        if last_play:
            return bool(engine.relation_to_last(state) == "opponent" and engine.min_opponent_count(state) <= 6)
        features = action_features(state, original) if original else {}
        return bool(
            original
            and (
                features.get("bad_lead_size_risk")
                or features.get("giving_control_to_strong_opponent_risk")
                or (engine.min_opponent_count(state) <= 6 and len(original) == 1)
            )
        )
    return True


def offline_shadow_safe_alternative(record: dict, payload: dict, decision: dict) -> list[str] | None:
    final_state = payload.get("final_state") or {}
    hand = decision.get("hand") or []
    level = decision.get("level")
    last_play = decision.get("last_play") or []
    if not hand or not level:
        return None
    original_groups_after = float_or_none(decision.get("groups_after"))
    counts = rank_count_by_rank(hand)
    candidates = []
    for card in engine.sort_cards(hand, level):
        if not is_low_single_card(card, level):
            continue
        if card not in {"B", "R"} and counts[card_rank(card)] > 1:
            continue
        cards = [card]
        if last_play:
            try:
                if not engine.play_beats(cards, last_play, level):
                    continue
            except Exception:
                continue
        if simulated_opened_exact_length(decision, final_state, cards):
            continue
        if simulated_gave_control(decision, final_state, cards):
            continue
        if simulated_consumes_potential_block_card(decision, cards):
            continue
        try:
            groups_after = engine.estimate_remaining_groups(engine.remove_cards(hand, cards), level)
            structure_cost = engine.structure_cost(cards, hand, level)
        except Exception:
            continue
        if structure_cost > 0:
            continue
        if original_groups_after is not None and groups_after > original_groups_after + 1.0:
            continue
        candidates.append((groups_after, engine.rank_value(play_info_for_cards(cards, last_play, level), level), cards))
    if not candidates:
        return None
    return min(candidates, key=lambda item: (item[0], item[1], item[2]))[2]


def offline_shadow_action_for_known_policy(
    record: dict,
    payload: dict,
    decision: dict,
    policy: str,
    final_decision: dict | None,
) -> list[str] | None:
    original = list(decision.get("play") or [])
    if policy == "tempo_plate_delay_guard":
        hit = late_plate_only_delay_sim(record, payload, decision, final_decision)
        return list((hit or {}).get("simulated_action", {}).get("cards") or original)
    if policy == "tempo_shape_guard":
        state = decision_shadow_state(record, payload, decision)
        if not is_tempo_shape_guard_active(state):
            return original
        row = decision_dataset_row(record, payload, decision, final_decision)
        risky = bool(
            row.get("left_self_without_block_shape")
            or row.get("consumed_potential_block_card")
            or row.get("consumed_2_or_joker_or_level_card")
            or row.get("broke_pair_or_triple_or_straight")
            or row.get("did_increase_groups")
        )
        if not risky:
            return original
        alt = offline_shadow_safe_alternative(record, payload, decision)
        return alt if alt is not None else original
    if policy == "tempo_endgame_guard":
        state = decision_shadow_state(record, payload, decision)
        if not is_tempo_endgame_guard_active(state):
            return original
        labels = set(decision_failure_labels(decision))
        follow_block = bool(
            decision.get("last_play")
            and engine.relation_to_last(state) == "opponent"
            and engine.min_opponent_count(state) <= 6
            and not original
        )
        risky_lead = bool(not decision.get("last_play") and labels.intersection({"bad_lead_size", "gave_strong_opponent_control"}))
        if not follow_block and not risky_lead:
            return original
        alt = offline_shadow_safe_alternative(record, payload, decision)
        return alt if alt is not None else original
    return None


def shadow_action_for_policy(
    record: dict,
    payload: dict,
    decision: dict,
    policy: str,
    profiles: dict,
    final_decision: dict | None,
) -> list[str] | None:
    profile = profiles.get(policy)
    if not profile:
        return None
    offline_known = offline_shadow_action_for_known_policy(record, payload, decision, policy, final_decision)
    if offline_known is not None:
        return offline_known
    original = list(decision.get("play") or [])
    if not shadow_policy_may_change(record, payload, decision, policy):
        return original
    state = decision_shadow_state(record, payload, decision)
    return choose_profiled_play(clone_shadow_state(state), policy, profile)


def shadow_context_key(record: dict, decision: dict, payload: dict) -> str:
    final_state = payload.get("final_state") or {}
    counts = decision_opponent_counts(final_state, decision)
    opponent_min = min(counts) if counts else None
    phase = "lead" if not (decision.get("last_play") or []) else "follow"
    return f"{record.get('scenario')}|{phase}|opp_min={opponent_min}"


def shadow_action_type_key(original: dict, shadow: dict) -> str:
    return f"{original.get('type')}:{original.get('size')}->{shadow.get('type')}:{shadow.get('size')}"


def shadow_eval(profile: str, policies_text: str, out_path: str) -> dict:
    results = load_json(RESULTS_PATH, {})
    profiles = load_json(PROFILE_PATH, {})
    records = [record for record in official_game_records(results) if record.get("profile") == profile]
    logs = research_log_index()
    policies = [name.strip() for name in policies_text.split(",") if name.strip()]
    stats = {
        policy: {
            "changed": 0,
            "loss_hits": 0,
            "win_hits": 0,
            "changed_non_endgame": 0,
            "changed_unrelated_phase": 0,
            "lead_changes": 0,
            "follow_changes": 0,
            "errors": 0,
            "contexts": Counter(),
            "action_types": Counter(),
        }
        for policy in policies
    }
    concrete_changes = []
    total_decisions = 0
    missing_logs = 0

    for record in records:
        payload = logs.get((str(record.get("game_id")), profile), {})
        if not payload:
            missing_logs += 1
            continue
        decisions = payload.get("decisions") or []
        failure_tags = record.get("failure_tags") or payload.get("failure_tags") or []
        final_decision = relevant_endgame_audit_decision(decisions, failure_tags)
        for decision in decisions:
            total_decisions += 1
            original_cards = list(decision.get("play") or [])
            original_key = normalized_action_key(original_cards, decision.get("level"))
            original_summary = fast_action_summary_for_dataset(original_cards, decision)
            for policy in policies:
                if policy not in profiles:
                    stats[policy]["errors"] += 1
                    continue
                try:
                    shadow_cards = shadow_action_for_policy(record, payload, decision, policy, profiles, final_decision)
                except Exception:
                    stats[policy]["errors"] += 1
                    continue
                if shadow_cards is None:
                    stats[policy]["errors"] += 1
                    continue
                shadow_key = normalized_action_key(shadow_cards, decision.get("level"))
                if shadow_key == original_key:
                    continue
                shadow_summary = fast_action_summary_for_dataset(list(shadow_key), decision)
                item = {
                    "policy": policy,
                    "game_id": str(record.get("game_id")),
                    "turn_index": decision.get("turn"),
                    "scenario": record.get("scenario"),
                    "outcome": record.get("outcome"),
                    "elo_delta": record.get("elo_delta"),
                    "metric_source": record.get("metric_source"),
                    "was_lead": not bool(decision.get("last_play") or []),
                    "was_follow": bool(decision.get("last_play") or []),
                    "original_action": original_summary,
                    "shadow_action": shadow_summary,
                    "opponent_remaining_counts": decision_opponent_counts(payload.get("final_state") or {}, decision),
                }
                concrete_changes.append(item)
                bucket = stats[policy]
                bucket["changed"] += 1
                if record.get("outcome") == "loss":
                    bucket["loss_hits"] += 1
                elif record.get("outcome") == "win":
                    bucket["win_hits"] += 1
                if "endgame_danger_high" not in str(record.get("scenario") or ""):
                    bucket["changed_non_endgame"] += 1
                if item["was_lead"]:
                    bucket["lead_changes"] += 1
                elif item["was_follow"]:
                    bucket["follow_changes"] += 1
                else:
                    bucket["changed_unrelated_phase"] += 1
                bucket["contexts"][shadow_context_key(record, decision, payload)] += 1
                bucket["action_types"][shadow_action_type_key(original_summary, shadow_summary)] += 1

    changed_by_policy = {policy: stats[policy]["changed"] for policy in policies}
    loss_by_policy = {policy: stats[policy]["loss_hits"] for policy in policies}
    win_by_policy = {policy: stats[policy]["win_hits"] for policy in policies}
    result = {
        "profile": profile,
        "policies": policies,
        "metric_source": "leaderboard_elo",
        "uses_leaderboard_elo": True,
        "evaluated_games": len(records),
        "missing_log_games": missing_logs,
        "total_decisions": total_decisions,
        "changed_decisions_by_policy": changed_by_policy,
        "changed_decision_rate_by_policy": {
            policy: changed_by_policy[policy] / total_decisions if total_decisions else 0.0
            for policy in policies
        },
        "hit_loss_count_by_policy": loss_by_policy,
        "hit_win_count_by_policy": win_by_policy,
        "false_positive_rate_by_policy": {
            policy: win_by_policy[policy] / changed_by_policy[policy] if changed_by_policy[policy] else 0.0
            for policy in policies
        },
        "changed_non_endgame_count_by_policy": {
            policy: stats[policy]["changed_non_endgame"] for policy in policies
        },
        "changed_unrelated_phase_count_by_policy": {
            policy: stats[policy]["changed_unrelated_phase"] for policy in policies
        },
        "changed_lead_count_by_policy": {policy: stats[policy]["lead_changes"] for policy in policies},
        "changed_follow_count_by_policy": {policy: stats[policy]["follow_changes"] for policy in policies},
        "shadow_error_count_by_policy": {policy: stats[policy]["errors"] for policy in policies},
        "top_changed_contexts": {
            policy: stats[policy]["contexts"].most_common(12) for policy in policies
        },
        "top_changed_action_types": {
            policy: stats[policy]["action_types"].most_common(12) for policy in policies
        },
        "concrete_changed_decisions": concrete_changes,
    }
    save_json(Path(out_path), result)
    print(json.dumps({"shadow_out": out_path, **{k: result[k] for k in ("profile", "policies", "total_decisions", "changed_decisions_by_policy")}}, ensure_ascii=False, indent=2))
    return result


def candidate_gate(shadow_result_path: str) -> dict:
    data = load_json(Path(shadow_result_path), {})
    policies = data.get("policies") or sorted((data.get("changed_decisions_by_policy") or {}).keys())
    gates = []
    passing = []
    for policy in policies:
        changed_rate = float((data.get("changed_decision_rate_by_policy") or {}).get(policy) or 0.0)
        loss_hits = int((data.get("hit_loss_count_by_policy") or {}).get(policy) or 0)
        win_hits = int((data.get("hit_win_count_by_policy") or {}).get(policy) or 0)
        fp_rate = float((data.get("false_positive_rate_by_policy") or {}).get(policy) or 0.0)
        non_endgame = int((data.get("changed_non_endgame_count_by_policy") or {}).get(policy) or 0)
        unrelated_phase = int((data.get("changed_unrelated_phase_count_by_policy") or {}).get(policy) or 0)
        reasons = []
        if data.get("metric_source") != "leaderboard_elo" or not data.get("uses_leaderboard_elo"):
            reasons.append("requires_leaderboard_elo")
        if changed_rate > 0.02:
            reasons.append("changed_decision_rate_gt_0.02")
        if loss_hits <= win_hits:
            reasons.append("hit_loss_count_not_greater_than_hit_win_count")
        if fp_rate > 0.35:
            reasons.append("false_positive_rate_gt_0.35")
        if non_endgame > 0:
            reasons.append("changes_non_endgame_games")
        if unrelated_phase > 0:
            reasons.append("changes_unrelated_phase")
        pass_gate = not reasons
        if pass_gate:
            passing.append(policy)
        gates.append(
            {
                "candidate_name": policy,
                "pass_gate": pass_gate,
                "reasons": reasons or ["pass"],
                "changed_decision_rate": changed_rate,
                "hit_loss_count": loss_hits,
                "hit_win_count": win_hits,
                "false_positive_rate": fp_rate,
                "changed_non_endgame_count": non_endgame,
                "changed_unrelated_phase_count": unrelated_phase,
                "recommended_live_test_games": 5 if pass_gate else 0,
                "stop_loss": {"recent_games": 5, "max_elo_delta": -20},
                "stop_after_losses": 3,
            }
        )
    result = {
        "shadow_result_path": shadow_result_path,
        "candidate_name": passing[0] if passing else None,
        "pass_gate": bool(passing),
        "reasons": ["at_least_one_candidate_passed"] if passing else ["no_candidate_passed"],
        "recommended_live_test_games": 5 if passing else 0,
        "stop_loss": {"recent_games": 5, "max_elo_delta": -20},
        "stop_after_losses": 3,
        "policy_gates": gates,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return result


def decision_window_rows_for_record(record: dict, payload: dict, window: int) -> list[dict]:
    decisions = payload.get("decisions") or []
    failure_tags = record.get("failure_tags") or payload.get("failure_tags") or []
    final_decision = relevant_endgame_audit_decision(decisions, failure_tags)
    selected = decisions
    if record.get("outcome") == "loss" and final_decision and final_decision.get("turn") is not None:
        selected = [
            decision for decision in decisions
            if decision.get("turn") is not None and int(decision.get("turn")) < int(final_decision.get("turn"))
        ]
    if window > 0:
        selected = selected[-window:]
    return [decision_dataset_row(record, payload, decision, final_decision) for decision in selected]


def profile_pattern_game_stats(results: dict, profile: str, decision_window: int) -> dict:
    records = [record for record in official_game_records(results) if record.get("profile") == profile]
    logs = research_log_index()
    pattern_games: dict[str, dict] = {}
    loss_rows = []
    win_rows = []
    for record in records:
        payload = logs.get((str(record.get("game_id")), profile), {})
        if not payload:
            continue
        rows = decision_window_rows_for_record(record, payload, decision_window)
        if record.get("outcome") == "loss":
            loss_rows.extend(rows)
        else:
            win_rows.extend(rows)
        game_patterns = sorted({pattern for row in rows for pattern in row.get("risk_patterns") or []})
        for pattern in game_patterns:
            bucket = pattern_games.setdefault(pattern, {"games": 0, "losses": 0, "wins": 0, "elo_delta_total": 0.0})
            bucket["games"] += 1
            bucket["losses"] += 1 if record.get("outcome") == "loss" else 0
            bucket["wins"] += 1 if record.get("outcome") == "win" else 0
            bucket["elo_delta_total"] += float(record.get("elo_delta") or 0.0)
    for bucket in pattern_games.values():
        games = max(1, int(bucket["games"]))
        bucket["loss_rate"] = bucket["losses"] / games
        bucket["average_elo_delta"] = bucket["elo_delta_total"] / games
    return {
        "records": records,
        "loss_rows": loss_rows,
        "win_rows": win_rows,
        "pattern_games": pattern_games,
    }


def risk_attribution_summary(results: dict, profile: str, decision_window: int) -> dict:
    stats = profile_pattern_game_stats(results, profile, decision_window)
    loss_rows = stats["loss_rows"]
    win_rows = stats["win_rows"]
    pattern_counts = Counter(pattern for row in loss_rows for pattern in row.get("risk_patterns") or [])
    lead_patterns = Counter(
        pattern for row in loss_rows if row.get("was_lead") for pattern in row.get("risk_patterns") or []
    )
    follow_patterns = Counter(
        pattern for row in loss_rows if row.get("was_follow") for pattern in row.get("risk_patterns") or []
    )
    safe_win_patterns = Counter(pattern for row in win_rows for pattern in row.get("risk_patterns") or [])
    pattern_stats = stats["pattern_games"]
    loss_rate = {pattern: bucket["loss_rate"] for pattern, bucket in sorted(pattern_stats.items())}
    avg_delta = {pattern: bucket["average_elo_delta"] for pattern, bucket in sorted(pattern_stats.items())}
    top_loss = sorted(
        pattern_stats.items(),
        key=lambda item: (
            item[1]["loss_rate"],
            item[1]["losses"],
            -item[1]["average_elo_delta"],
        ),
        reverse=True,
    )
    return {
        "profile": profile,
        "decision_window": decision_window,
        "analyzed_losses": sum(1 for record in stats["records"] if record.get("outcome") == "loss"),
        "analyzed_decisions": len(loss_rows),
        "risk_pattern_counts": dict(pattern_counts),
        "risk_pattern_loss_rate": loss_rate,
        "risk_pattern_avg_elo_delta": avg_delta,
        "top_loss_correlated_patterns": [
            {"pattern": pattern, **bucket} for pattern, bucket in top_loss[:12]
        ],
        "top_safe_patterns_in_wins": safe_win_patterns.most_common(12),
        "lead_risk_patterns": lead_patterns.most_common(12),
        "follow_risk_patterns": follow_patterns.most_common(12),
    }


def profile_total_elo(records: list[dict]) -> float:
    return sum(float(record.get("elo_delta") or 0.0) for record in records)


def profile_risk_rates(results: dict, profile: str, decision_window: int) -> dict:
    stats = profile_pattern_game_stats(results, profile, decision_window)
    return {
        pattern: bucket["loss_rate"]
        for pattern, bucket in stats["pattern_games"].items()
    }


def compare_profiles_summary(results: dict, profile_a: str, profile_b: str, recent_window: int, decision_window: int) -> dict:
    records = official_game_records(results)
    a_records = [record for record in records if record.get("profile") == profile_a]
    b_records = [record for record in records if record.get("profile") == profile_b]
    a_rates = profile_risk_rates(results, profile_a, decision_window)
    b_rates = profile_risk_rates(results, profile_b, decision_window)
    patterns = sorted(set(a_rates) | set(b_rates) | set(OFFLINE_RISK_PATTERNS))
    deltas = {
        pattern: {
            "profile_a_loss_rate": a_rates.get(pattern, 0.0),
            "profile_b_loss_rate": b_rates.get(pattern, 0.0),
            "profile_b_minus_a": b_rates.get(pattern, 0.0) - a_rates.get(pattern, 0.0),
        }
        for pattern in patterns
    }
    reduced = []
    introduced = []
    for pattern, item in deltas.items():
        delta = item["profile_b_minus_a"]
        if abs(delta) < 1e-9:
            continue
        reduced.append(
            {
                "pattern": pattern,
                "reduced_by": profile_b if delta < 0 else profile_a,
                "profile_b_minus_a": delta,
            }
        )
        if item["profile_a_loss_rate"] == 0.0 and item["profile_b_loss_rate"] > 0.0:
            introduced.append({"pattern": pattern, "introduced_by": profile_b, **item})
        elif item["profile_b_loss_rate"] == 0.0 and item["profile_a_loss_rate"] > 0.0:
            introduced.append({"pattern": pattern, "introduced_by": profile_a, **item})
    reduced.sort(key=lambda item: abs(item["profile_b_minus_a"]), reverse=True)
    introduced.sort(key=lambda item: abs(item["profile_b_minus_a"]), reverse=True)
    return {
        "profile_a": profile_a,
        "profile_b": profile_b,
        "decision_window": decision_window,
        "recent_window": recent_window,
        "profile_a_games": len(a_records),
        "profile_b_games": len(b_records),
        "profile_a_total_elo_delta": profile_total_elo(a_records),
        "profile_b_total_elo_delta": profile_total_elo(b_records),
        "profile_a_recent_elo_delta": profile_total_elo(a_records[-recent_window:]) if recent_window > 0 else 0.0,
        "profile_b_recent_elo_delta": profile_total_elo(b_records[-recent_window:]) if recent_window > 0 else 0.0,
        "risk_pattern_delta": deltas,
        "which_profile_reduced_which_risk": reduced,
        "which_profile_introduced_new_risk": introduced,
    }


def normalized_action_key(cards: list[str] | tuple[str, ...] | None, level: str | None) -> tuple[str, ...]:
    if not cards:
        return ()
    if not level:
        return tuple(cards)
    try:
        return tuple(engine.sort_cards(list(cards), level))
    except Exception:
        return tuple(cards)


CASEBOOK_ALT_EVAL_LIMIT = 24


def casebook_lead_candidate_cards(hand: list[str], level: str) -> list[list[str]]:
    seen = set()
    candidates = []

    def add(cards: list[str] | tuple[str, ...]) -> None:
        if not action_counter_in_hand(list(cards), hand):
            return
        key = normalized_action_key(cards, level)
        if key and key not in seen:
            seen.add(key)
            candidates.append(list(key))

    for card in hand:
        add([card])

    by_rank: dict[str, list[str]] = {rank: [] for rank in engine.RANKS}
    wild_card = "H" + level
    wilds = [card for card in hand if card == wild_card]
    for card in hand:
        if card in {"B", "R"}:
            continue
        if card != wild_card:
            by_rank[card_rank(card)].append(card)

    def select_rank_cards(rank: str, count: int) -> list[str] | None:
        cards = engine.sort_cards(by_rank.get(rank, []), level)
        if len(cards) >= count:
            return cards[:count]
        need_wild = count - len(cards)
        if need_wild <= len(wilds):
            return cards + wilds[:need_wild]
        return None

    pairs = []
    triples = []
    for rank, cards in by_rank.items():
        sorted_cards = engine.sort_cards(cards, level)
        for size in range(2, min(8, len(sorted_cards) + len(wilds)) + 1):
            selected = select_rank_cards(rank, size)
            if selected:
                add(selected)
                if size == 2:
                    pairs.append(selected)
                elif size == 3:
                    triples.append(selected)

    for triple in triples:
        triple_rank = card_rank(triple[0])
        for pair in pairs:
            if card_rank(pair[0]) != triple_rank:
                add(triple + pair)

    for seq in engine.sequence_windows(5):
        selected = []
        used_wilds = 0
        for rank in seq:
            card = select_rank_cards(rank, 1)
            if not card:
                selected = []
                break
            if card[0] == wild_card:
                if used_wilds >= len(wilds):
                    selected = []
                    break
                selected.append(wilds[used_wilds])
                used_wilds += 1
            else:
                selected.extend(card)
        if len(selected) == 5:
            add(selected)

    for suit in engine.SUITS:
        for seq in engine.sequence_windows(5):
            selected = []
            used_wilds = 0
            for rank in seq:
                suited = [card for card in by_rank.get(rank, []) if card.startswith(suit)]
                if suited:
                    selected.append(engine.sort_cards(suited, level)[0])
                    continue
                if used_wilds < len(wilds):
                    selected.append(wilds[used_wilds])
                    used_wilds += 1
                    continue
                selected = []
                break
            if len(selected) == 5:
                add(selected)

    for seq_len, need_each in ((3, 2), (2, 3)):
        for seq in engine.sequence_windows(seq_len):
            selected = []
            used_wilds = 0
            ok = True
            for rank in seq:
                cards = engine.sort_cards(by_rank.get(rank, []), level)
                take = cards[:need_each]
                need_wild = need_each - len(take)
                if need_wild > len(wilds) - used_wilds:
                    ok = False
                    break
                selected.extend(take)
                selected.extend(wilds[used_wilds : used_wilds + need_wild])
                used_wilds += need_wild
            if ok and len(selected) == seq_len * need_each:
                add(selected)

    kings = [card for card in hand if card in {"B", "R"}]
    if kings.count("B") >= 2 and kings.count("R") >= 2:
        add(["B", "B", "R", "R"])

    return candidates


def casebook_alternative_scan(decision: dict, final_state: dict) -> tuple[int, list[dict], bool]:
    hand = decision.get("hand") or []
    level = decision.get("level")
    last_play = decision.get("last_play") or []
    chosen_key = normalized_action_key(decision.get("play") or [], level)
    if not hand or not level:
        return 0, [], False
    groups_before = decision.get("groups_before")
    try:
        groups_before = float(groups_before)
    except (TypeError, ValueError):
        groups_before = engine.estimate_remaining_groups(hand, level)
    opponent_counts = decision_opponent_counts(final_state, decision)
    opponent_min = min(opponent_counts) if opponent_counts else 99

    seen = set()
    legal_count = 0
    candidates = []
    search_limited = not bool(last_play)
    if last_play:
        if len(hand) > 12 and len(last_play) >= 5:
            return 0, [], True
        block_options = cached_legal_block_options(hand, last_play, level)
        for option in block_options:
            cards = option.get("cards") or []
            key = normalized_action_key(cards, level)
            if key in seen or key == chosen_key:
                continue
            seen.add(key)
            legal_count += 1
            if option.get("is_bomb") and len(cards) < len(hand):
                continue
            if option.get("structure_cost") is not None and float(option["structure_cost"]) > 0:
                continue
            if (
                option.get("groups_after") is not None
                and float(option["groups_after"]) > groups_before + 0.01
            ):
                continue
            candidates.append(option)
        alternatives = sorted(
            candidates,
            key=lambda item: (
                item.get("groups_after") if item.get("groups_after") is not None else 999.0,
                item.get("structure_cost") if item.get("structure_cost") is not None else 999,
                item.get("size") or 99,
                item.get("cards") or [],
            ),
        )
        return legal_count, alternatives, search_limited

    for cards in casebook_lead_candidate_cards(hand, level):
        key = normalized_action_key(cards, level)
        if key in seen or key == chosen_key:
            continue
        seen.add(key)
        info = play_info_for_cards(list(key), [], level)
        if not info:
            continue
        legal_count += 1
        if engine.is_bomb(info) and len(key) < len(hand):
            continue
        if len(key) in {count for count in opponent_counts if count > 0}:
            continue
        if len(key) <= opponent_min <= 4:
            continue
        candidates.append((info, list(key)))

    candidates.sort(
        key=lambda item: (
            action_consumes_control_card(item[1], level),
            len(item[1]),
            engine.rank_value(item[0], level),
            item[1],
        )
    )
    search_limited = search_limited or len(candidates) > CASEBOOK_ALT_EVAL_LIMIT
    alternatives = []
    for info, cards in candidates[:CASEBOOK_ALT_EVAL_LIMIT]:
        try:
            remaining = engine.remove_cards(hand, cards)
            groups_after = engine.estimate_remaining_groups(remaining, level)
            structure_cost = engine.structure_cost(cards, hand, level)
        except Exception:
            continue
        if structure_cost > 0 or groups_after > groups_before + 0.01:
            continue
        alternatives.append(
            {
                "cards": engine.sort_cards(cards, level),
                "type": info.type,
                "rank": info.rank,
                "size": len(cards),
                "is_bomb": bool(engine.is_bomb(info)),
                "structure_cost": structure_cost,
                "groups_after": groups_after,
            }
        )
    alternatives.sort(
        key=lambda item: (
            item.get("groups_after") if item.get("groups_after") is not None else 999.0,
            item.get("structure_cost") if item.get("structure_cost") is not None else 999,
            item.get("size") or 99,
            item.get("cards") or [],
        ),
    )
    return legal_count, alternatives, search_limited


def alternative_preserves_final_block_shape(
    decision: dict,
    final_decision: dict | None,
    alternative_cards: list[str] | tuple[str, ...] | None,
) -> bool:
    if not final_decision or not alternative_cards:
        return False
    final_last_play = final_decision.get("last_play") or []
    level = decision.get("level")
    hand = decision.get("hand") or []
    if not final_last_play or not level or not hand:
        return False
    try:
        after_hand = engine.remove_cards(hand, list(alternative_cards))
    except Exception:
        return False
    return bool(cached_legal_block_options(after_hand, final_last_play, level))


def casebook_risk_reasons(item: dict) -> list[str]:
    reasons = []
    for key in (
        "opened_exact_length_to_opponent",
        "gave_strong_opponent_control",
        "left_self_without_block_shape",
        "consumed_potential_block_card",
        "consumed_2_or_joker_or_level_card",
        "broke_pair_or_triple_or_straight",
        "did_increase_groups",
        "used_bomb",
        "used_joker",
        "used_level_card",
    ):
        if item.get(key):
            reasons.append(key)
    action_size = int(item.get("chosen_action_size") or 0)
    opponent_counts = item.get("opponent_remaining_counts") or []
    if action_size and action_size in {int(count) for count in opponent_counts if 0 < int(count) <= 6}:
        reasons.append("bad_lead_size")
    if item.get("was_follow") and not item.get("chosen_action") and opponent_counts and min(opponent_counts) <= 6:
        reasons.append("missed_block")
    return sorted(set(reasons))


def best_safe_alternative_reason(item: dict, best_alternative: dict | None, preserves_final_block: bool) -> str:
    if not best_alternative:
        return "no_safe_alternative"
    if preserves_final_block:
        return "preserves_final_block_shape"
    reasons = []
    if item.get("opened_exact_length_to_opponent"):
        reasons.append("avoids_opened_exact_length")
    if item.get("gave_strong_opponent_control"):
        reasons.append("avoids_giving_control")
    if item.get("consumed_potential_block_card"):
        reasons.append("preserves_potential_block")
    if item.get("consumed_2_or_joker_or_level_card"):
        reasons.append("preserves_control_card")
    if item.get("broke_pair_or_triple_or_straight"):
        reasons.append("preserves_structure")
    if item.get("did_increase_groups"):
        reasons.append("does_not_increase_groups")
    return ",".join(reasons) if reasons else "lower_risk_safe_action"


def concrete_action_key(item: dict) -> str:
    cards = ",".join(item.get("chosen_action") or [])
    return f"{item.get('chosen_action_type')}:{item.get('chosen_action_rank')}:{item.get('chosen_action_size')}:{cards}"


def action_shape_key(item: dict) -> str:
    mode = "lead" if item.get("was_lead") else "follow"
    return f"{mode}:{item.get('chosen_action_type')}:{item.get('chosen_action_rank')}:size={item.get('chosen_action_size')}"


def action_context_key(item: dict) -> str:
    opponent_counts = item.get("opponent_remaining_counts") or []
    opponent_min = min(opponent_counts) if opponent_counts else None
    mode = "lead" if item.get("was_lead") else "follow"
    risks = "+".join(item.get("why_chosen_action_risky") or ["none"])
    return f"{item.get('scenario')}|{mode}|opp_min={opponent_min}|{risks}"


def alternative_action_key(option: dict | None) -> str | None:
    if not option:
        return None
    cards = ",".join(option.get("cards") or [])
    return f"{option.get('type')}:{option.get('rank')}:{option.get('size')}:{cards}"


def casebook_decision_detail(
    record: dict,
    payload: dict,
    decision: dict,
    final_decision: dict | None,
    final_audit: dict,
) -> dict:
    final_state = payload.get("final_state") or {}
    hand = decision.get("hand") or []
    play = decision.get("play") or []
    level = decision.get("level")
    last_play = decision.get("last_play") or []
    opponent_counts = decision_opponent_counts(final_state, decision)
    groups_before = decision.get("groups_before")
    groups_after = decision.get("groups_after")
    try:
        groups_before_number = float(groups_before)
    except (TypeError, ValueError):
        groups_before_number = None
    try:
        groups_after_number = float(groups_after)
    except (TypeError, ValueError):
        groups_after_number = None
    action_type, action_rank = action_rank_type(play, last_play, level) if level else (None, None)
    structure_cost = 0
    if play and level:
        try:
            structure_cost = engine.structure_cost(play, hand, level)
        except Exception:
            structure_cost = 0
    broke_structure = bool(
        structure_cost > 0
        or (
            groups_before_number is not None
            and groups_after_number is not None
            and groups_after_number > groups_before_number + 0.01
        )
    )
    legal_count, safe_alts, alt_search_limited = casebook_alternative_scan(decision, final_state)
    best_alt = safe_alts[0] if safe_alts else None
    exact_targets = opened_exact_length_targets(decision, final_state)
    left_without_shape, consumed_potential = offline_shape_flags(decision)
    block_avoidance_evaluated = bool(
        final_audit.get("block_missed_reason") == "no_legal_block"
        and final_decision
        and int(decision.get("hand_count") or len(hand)) <= 16
    )
    could_preserve_final_block = bool(
        block_avoidance_evaluated
        and any(alternative_preserves_final_block_shape(decision, final_decision, option.get("cards")) for option in safe_alts)
    )
    item = {
        "turn_index": decision.get("turn"),
        "was_lead": not bool(last_play),
        "was_follow": bool(last_play),
        "scenario": record.get("scenario"),
        "hand_before": hand,
        "last_play_before_action": last_play,
        "chosen_action": play,
        "chosen_action_type": action_type,
        "chosen_action_size": len(play),
        "chosen_action_rank": action_rank,
        "my_remaining_before": decision.get("hand_count"),
        "my_remaining_after": (int(decision.get("hand_count") or len(hand)) - len(play)) if play else decision.get("hand_count"),
        "teammate_remaining": decision.get("teammate_count"),
        "opponent_remaining_counts": opponent_counts,
        "remaining_groups_before": groups_before,
        "remaining_groups_after": groups_after,
        "did_reduce_groups": bool(
            groups_before_number is not None
            and groups_after_number is not None
            and groups_after_number < groups_before_number - 0.01
        ),
        "did_increase_groups": bool(
            groups_before_number is not None
            and groups_after_number is not None
            and groups_after_number > groups_before_number + 0.01
        ),
        "opened_exact_length_to_opponent": bool(exact_targets),
        "gave_strong_opponent_control": bool("gave_strong_opponent_control" in decision_failure_labels(decision)),
        "left_self_without_block_shape": left_without_shape,
        "consumed_potential_block_card": consumed_potential,
        "consumed_2_or_joker_or_level_card": bool(level and action_consumes_control_card(play, level)),
        "broke_pair_or_triple_or_straight": broke_structure,
        "used_bomb": bool(play and level and engine.server_treats_as_bomb(play, level)),
        "used_joker": any(card in {"B", "R"} for card in play),
        "used_level_card": used_level_card(play, level),
        "legal_alternative_count": legal_count,
        "safe_alternative_count": len(safe_alts),
        "best_safe_alternative": best_alt,
        "could_have_avoided_final_no_legal_block": could_preserve_final_block,
        "could_have_avoided_final_no_legal_block_evaluated": block_avoidance_evaluated,
        "alternative_search_limited": alt_search_limited,
    }
    item["why_chosen_action_risky"] = casebook_risk_reasons(item)
    item["best_safe_alternative_reason"] = best_safe_alternative_reason(
        item,
        best_alt,
        could_preserve_final_block,
    )
    return item


def loss_casebook_summary(results: dict, profile: str, case_window: int, max_cases: int) -> dict:
    records = official_game_records(results)
    losses = [record for record in records if record.get("profile") == profile and record.get("outcome") == "loss"]
    selected_losses = losses[-max_cases:] if max_cases > 0 else losses
    logs = research_log_index()
    cases = []
    bad_actions = Counter()
    bad_shapes = Counter()
    bad_contexts = Counter()
    bad_alternatives = Counter()

    for record in selected_losses:
        game_id = str(record.get("game_id"))
        payload = logs.get((game_id, profile), {})
        decisions = payload.get("decisions") or []
        failure_tags = record.get("failure_tags") or payload.get("failure_tags") or []
        final_audit = endgame_audit_item(record, payload, profile)
        final_decision = relevant_endgame_audit_decision(decisions, failure_tags)
        final_turn = final_decision.get("turn") if final_decision else None
        if final_turn is not None:
            preloss_decisions = [
                decision for decision in decisions
                if decision.get("turn") is not None and int(decision.get("turn")) < int(final_turn)
            ]
        else:
            preloss_decisions = decisions
        if case_window > 0:
            preloss_decisions = preloss_decisions[-case_window:]
        details = [
            casebook_decision_detail(record, payload, decision, final_decision, final_audit)
            for decision in preloss_decisions
        ]
        for detail in details:
            if not detail.get("why_chosen_action_risky"):
                continue
            bad_actions[concrete_action_key(detail)] += 1
            bad_shapes[action_shape_key(detail)] += 1
            bad_contexts[action_context_key(detail)] += 1
            alt_key = alternative_action_key(detail.get("best_safe_alternative"))
            if alt_key:
                bad_alternatives[alt_key] += 1
        cases.append(
            {
                "game_id": game_id,
                "elo_before": record.get("elo_before"),
                "elo_after": record.get("elo_after"),
                "elo_delta": record.get("elo_delta"),
                "final_failure_tags": failure_tags,
                "final_block_missed_reason": final_audit.get("block_missed_reason"),
                "final_legal_block_options_count": final_audit.get("legal_block_options_count"),
                "opponent_remaining_counts_at_failure": final_audit.get("opponent_remaining_counts_at_failure"),
                "teammate_remaining_count_at_failure": final_audit.get("teammate_remaining_count_at_failure"),
                "self_remaining_count_at_failure": final_audit.get("self_remaining_count_at_failure"),
                "preloss_my_decisions": details,
                "log_available": bool(payload),
                "log_path": payload.get("_log_path"),
            }
        )

    return {
        "profile": profile,
        "case_window": case_window,
        "max_cases": max_cases,
        "record_source": "game_records",
        "detail_source": "logs*/research_game_*.json",
        "available_losses": len(losses),
        "analyzed_cases": len(cases),
        "top_concrete_bad_actions": bad_actions.most_common(20),
        "repeated_bad_action_shapes": bad_shapes.most_common(20),
        "repeated_bad_contexts": bad_contexts.most_common(20),
        "repeated_bad_alternatives": bad_alternatives.most_common(20),
        "cases": cases,
    }


def scenario_has_casebook_guard_risk(scenario: Any) -> bool:
    text = str(scenario or "")
    return "high_elo_loss_risk" in text or "endgame_danger_high" in text


def scenario_has_narrow_plate_risk(scenario: Any) -> bool:
    text = str(scenario or "")
    return "high_elo_loss_risk" in text and "endgame_danger_high" in text


def float_or_none(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def simulated_opened_exact_length(decision: dict, final_state: dict, cards: list[str]) -> bool:
    if not cards:
        return False
    hand_counts = decision.get("hand_counts") or []
    for seat in opponent_seats(final_state):
        try:
            if int(hand_counts[seat]) == len(cards):
                return True
        except (IndexError, TypeError, ValueError):
            continue
    return False


def simulated_gave_control(decision: dict, final_state: dict, cards: list[str]) -> bool:
    opponent_counts = decision_opponent_counts(final_state, decision)
    opponent_min = min(opponent_counts) if opponent_counts else 99
    return bool(cards and len(cards) <= opponent_min <= 4)


def simulated_consumes_potential_block_card(decision: dict, cards: list[str]) -> bool:
    level = decision.get("level")
    hand = decision.get("hand") or []
    if not level or not hand or not cards:
        return False
    try:
        before_score = potential_block_shape_score(hand, level)
        after_score = potential_block_shape_score(engine.remove_cards(hand, cards), level)
    except Exception:
        return False
    return bool(after_score < before_score)


def cheap_follow_block_sim(record: dict, payload: dict, decision: dict) -> dict | None:
    final_state = payload.get("final_state") or {}
    scenario = record.get("scenario")
    hand = decision.get("hand") or []
    level = decision.get("level")
    last_play = decision.get("last_play") or []
    original = decision.get("play") or []
    opponent_counts = decision_opponent_counts(final_state, decision)
    if not last_play or original:
        return None
    if not scenario_has_casebook_guard_risk(scenario):
        return None
    if not opponent_counts or min(opponent_counts) > 6:
        return None
    if not hand or not level:
        return None
    if len(hand) > 12 and len(last_play) >= 5:
        return None

    groups_before = float_or_none(decision.get("groups_before"))
    if groups_before is None:
        groups_before = engine.estimate_remaining_groups(hand, level)
    for option in cached_legal_block_options(hand, last_play, level):
        cards = option.get("cards") or []
        if option.get("is_bomb"):
            continue
        if action_consumes_control_card(cards, level):
            continue
        if option.get("structure_cost") is not None and float(option["structure_cost"]) > 0:
            continue
        groups_after = float_or_none(option.get("groups_after"))
        if groups_after is not None and groups_after > groups_before + 0.01:
            continue
        return {
            "rule": "cheap_follow_block_sim",
            "simulated_action": option,
            "reason": "cheap_non_bomb_block_available_in_high_risk_follow",
        }
    return None


def safe_single_delay_alternative(record: dict, payload: dict, decision: dict) -> dict | None:
    final_state = payload.get("final_state") or {}
    hand = decision.get("hand") or []
    level = decision.get("level")
    play = decision.get("play") or []
    last_play = decision.get("last_play") or []
    if not hand or not level or last_play or not play:
        return None
    if int(decision.get("hand_count") or len(hand)) > 15:
        return None
    opponent_counts = decision_opponent_counts(final_state, decision)
    if not opponent_counts or min(opponent_counts) > 7:
        return None
    action_type, _rank = action_rank_type(play, [], level)
    if len(play) < 5 or action_type not in {"plate", "straight", "straight_flush", "full_house"}:
        return None
    left_without_shape, consumed_potential = offline_shape_flags(decision)
    if not (left_without_shape or consumed_potential):
        return None

    original_groups_after = float_or_none(decision.get("groups_after"))
    if original_groups_after is None:
        try:
            original_groups_after = engine.estimate_remaining_groups(engine.remove_cards(hand, play), level)
        except Exception:
            original_groups_after = None
    candidates = []
    for card in engine.sort_cards(hand, level):
        cards = [card]
        info = play_info_for_cards(cards, [], level)
        if not info or info.type != "single":
            continue
        if simulated_opened_exact_length(decision, final_state, cards):
            continue
        if simulated_gave_control(decision, final_state, cards):
            continue
        if action_consumes_control_card(cards, level):
            continue
        if simulated_consumes_potential_block_card(decision, cards):
            continue
        try:
            groups_after = engine.estimate_remaining_groups(engine.remove_cards(hand, cards), level)
            structure_cost = engine.structure_cost(cards, hand, level)
        except Exception:
            continue
        if structure_cost > 0:
            continue
        if original_groups_after is not None and groups_after > original_groups_after + 1.0:
            continue
        candidates.append(
            {
                "cards": cards,
                "type": info.type,
                "rank": info.rank,
                "size": 1,
                "is_bomb": False,
                "structure_cost": structure_cost,
                "groups_after": groups_after,
            }
        )
    if not candidates:
        return None
    candidates.sort(
        key=lambda item: (
            item.get("groups_after") if item.get("groups_after") is not None else 999.0,
            engine.rank_value(play_info_for_cards(item["cards"], [], level), level),
            item.get("cards") or [],
        )
    )
    return {
        "rule": "late_big_plate_delay_sim",
        "simulated_action": candidates[0],
        "reason": "safe_single_delay_preserves_block_shape",
    }


def is_low_single_card(card: str, level: str) -> bool:
    if card in {"B", "R"}:
        return False
    rank = card_rank(card)
    if rank in {"2", level}:
        return False
    return engine.RANKS.index(rank) <= engine.RANKS.index("T")


def late_plate_only_delay_sim(
    record: dict,
    payload: dict,
    decision: dict,
    final_decision: dict | None = None,
) -> dict | None:
    final_state = payload.get("final_state") or {}
    scenario = record.get("scenario")
    hand = decision.get("hand") or []
    level = decision.get("level")
    play = decision.get("play") or []
    last_play = decision.get("last_play") or []
    if not hand or not level or last_play or not play:
        return None
    if not scenario_has_narrow_plate_risk(scenario):
        return None
    action_type, _rank = action_rank_type(play, [], level)
    if action_type != "plate" or len(play) != 6:
        return None
    self_remaining = int(decision.get("hand_count") or len(hand))
    if self_remaining < 9 or self_remaining > 15:
        return None
    opponent_counts = decision_opponent_counts(final_state, decision)
    if not opponent_counts or min(opponent_counts) > 7:
        return None
    offline_left_without_shape, offline_consumed_potential = offline_shape_flags(decision)
    left_without_shape = bool(
        offline_left_without_shape
        or (left_without_block_shape(decision, final_decision) if final_decision else False)
    )
    consumed_potential = bool(
        offline_consumed_potential
        or (consumed_potential_block(decision, final_decision) if final_decision else False)
    )
    if not consumed_potential or not (left_without_shape or offline_consumed_potential):
        return None

    original_groups_after = float_or_none(decision.get("groups_after"))
    if original_groups_after is None:
        try:
            original_groups_after = engine.estimate_remaining_groups(engine.remove_cards(hand, play), level)
        except Exception:
            original_groups_after = None

    candidates = []
    for card in engine.sort_cards(hand, level):
        if not is_low_single_card(card, level):
            continue
        cards = [card]
        info = play_info_for_cards(cards, [], level)
        if not info or info.type != "single":
            continue
        if simulated_opened_exact_length(decision, final_state, cards):
            continue
        if simulated_gave_control(decision, final_state, cards):
            continue
        if action_consumes_control_card(cards, level):
            continue
        if simulated_consumes_potential_block_card(decision, cards):
            continue
        try:
            groups_after = engine.estimate_remaining_groups(engine.remove_cards(hand, cards), level)
            structure_cost = engine.structure_cost(cards, hand, level)
        except Exception:
            continue
        if structure_cost > 0:
            continue
        if original_groups_after is not None and groups_after > original_groups_after + 1.0:
            continue
        candidates.append(
            {
                "cards": cards,
                "type": info.type,
                "rank": info.rank,
                "size": 1,
                "is_bomb": False,
                "structure_cost": structure_cost,
                "groups_after": groups_after,
            }
        )
    if not candidates:
        return None
    candidates.sort(
        key=lambda item: (
            item.get("groups_after") if item.get("groups_after") is not None else 999.0,
            engine.rank_value(play_info_for_cards(item["cards"], [], level), level),
            item.get("cards") or [],
        )
    )
    return {
        "rule": "late_plate_only_delay_sim",
        "simulated_action": candidates[0],
        "reason": "narrow_plate_size6_delay_preserves_block_shape",
    }


def casebook_guard_simulation_decisions(record: dict, payload: dict, case_window: int) -> tuple[list[dict], dict | None]:
    decisions = payload.get("decisions") or []
    failure_tags = record.get("failure_tags") or payload.get("failure_tags") or []
    final_decision = relevant_endgame_audit_decision(decisions, failure_tags)
    if record.get("outcome") == "loss" and final_decision and final_decision.get("turn") is not None:
        selected = [
            decision for decision in decisions
            if decision.get("turn") is not None and int(decision.get("turn")) < int(final_decision.get("turn"))
        ]
    else:
        selected = decisions
    if case_window > 0:
        selected = selected[-case_window:]
    return selected, final_decision


def simulated_original_action(decision: dict) -> dict:
    level = decision.get("level")
    play = decision.get("play") or []
    last_play = decision.get("last_play") or []
    summary = play_summary(play, level, last_play, decision.get("hand") or []) if play and level else None
    return summary or {
        "cards": play,
        "type": None,
        "rank": None,
        "size": len(play),
    }


def casebook_guard_changed_decision(record: dict, payload: dict, decision: dict, rule_hit: dict) -> dict:
    outcome = record.get("outcome")
    final_state = payload.get("final_state") or {}
    return {
        "game_id": str(record.get("game_id")),
        "turn_index": decision.get("turn"),
        "rule": rule_hit.get("rule"),
        "original_action": simulated_original_action(decision),
        "simulated_action": rule_hit.get("simulated_action"),
        "reason": rule_hit.get("reason"),
        "outcome": outcome,
        "elo_delta": record.get("elo_delta"),
        "whether_loss_case": outcome == "loss",
        "whether_win_case": outcome == "win",
        "scenario": record.get("scenario"),
        "opponent_remaining_counts": decision_opponent_counts(final_state, decision),
        "my_remaining_before": decision.get("hand_count"),
    }


def simulate_casebook_guard_summary(results: dict, profile: str, case_window: int) -> dict:
    records = [record for record in official_game_records(results) if record.get("profile") == profile]
    logs = research_log_index()
    changed = []
    evaluated_decisions = 0
    missing_logs = 0
    rule_counts = Counter()
    target_cases = {(6973, 11), (6973, 12)}
    target_checks: dict[tuple[int, int], dict] = {
        target: {"game_id": str(target[0]), "turn_index": target[1], "seen": False, "hit": False}
        for target in target_cases
    }

    for record in records:
        payload = logs.get((str(record.get("game_id")), profile), {})
        if not payload:
            missing_logs += 1
            continue
        decisions, final_decision = casebook_guard_simulation_decisions(record, payload, case_window)
        for decision in decisions:
            evaluated_decisions += 1
            try:
                target = (int(record.get("game_id")), int(decision.get("turn")))
            except (TypeError, ValueError):
                target = None
            if target in target_checks:
                target_checks[target]["seen"] = True

            hit = cheap_follow_block_sim(record, payload, decision)
            if hit is None:
                hit = safe_single_delay_alternative(record, payload, decision)
            if hit is None:
                continue
            rule_counts[hit["rule"]] += 1
            item = casebook_guard_changed_decision(record, payload, decision, hit)
            changed.append(item)
            if target in target_checks:
                target_checks[target]["hit"] = True
                target_checks[target]["simulated_action"] = hit.get("simulated_action")
                target_checks[target]["rule"] = hit.get("rule")

    hit_loss_game_ids = sorted({item["game_id"] for item in changed if item.get("whether_loss_case")})
    hit_win_game_ids = sorted({item["game_id"] for item in changed if item.get("whether_win_case")})
    hit_targets = [
        item for item in changed
        if (str(item.get("game_id")), int(item.get("turn_index") or -1)) in {("6973", 11), ("6973", 12)}
    ]
    simulated_hits = len(changed)
    hits_on_wins = sum(1 for item in changed if item.get("whether_win_case"))
    false_positive_rate = hits_on_wins / simulated_hits if simulated_hits else 0.0
    return {
        "profile": profile,
        "case_window": case_window,
        "record_source": "game_records",
        "detail_source": "logs*/research_game_*.json",
        "simulation_only": True,
        "evaluated_games": len(records),
        "missing_log_games": missing_logs,
        "evaluated_decision_count": evaluated_decisions,
        "simulated_rule_hits": simulated_hits,
        "hits_on_losses": sum(1 for item in changed if item.get("whether_loss_case")),
        "hits_on_wins": hits_on_wins,
        "hit_loss_game_ids": hit_loss_game_ids,
        "hit_win_game_ids": hit_win_game_ids,
        "hit_target_cases": hit_targets,
        "target_case_checks": list(target_checks.values()),
        "false_positive_risk_estimate": {
            "hit_on_win_rate": false_positive_rate,
            "hit_on_win_count": hits_on_wins,
            "note": "Offline estimate: proportion of simulated changes that would have occurred in games already won.",
        },
        "changed_decision_count": simulated_hits,
        "changed_decision_rate": simulated_hits / evaluated_decisions if evaluated_decisions else 0.0,
        "rule_a_hits": rule_counts.get("cheap_follow_block_sim", 0),
        "rule_b_hits": rule_counts.get("late_big_plate_delay_sim", 0),
        "concrete_changed_decisions": changed,
    }


def simulate_narrow_plate_guard_summary(results: dict, profile: str, case_window: int) -> dict:
    records = [record for record in official_game_records(results) if record.get("profile") == profile]
    logs = research_log_index()
    changed = []
    evaluated_decisions = 0
    missing_logs = 0
    target_cases = {(6973, 11), (6973, 12)}
    target_checks: dict[tuple[int, int], dict] = {
        target: {"game_id": str(target[0]), "turn_index": target[1], "seen": False, "hit": False}
        for target in target_cases
    }

    for record in records:
        payload = logs.get((str(record.get("game_id")), profile), {})
        if not payload:
            missing_logs += 1
            continue
        decisions, final_decision = casebook_guard_simulation_decisions(record, payload, case_window)
        for decision in decisions:
            evaluated_decisions += 1
            try:
                target = (int(record.get("game_id")), int(decision.get("turn")))
            except (TypeError, ValueError):
                target = None
            if target in target_checks:
                target_checks[target]["seen"] = True

            hit = late_plate_only_delay_sim(record, payload, decision, final_decision)
            if hit is None:
                continue
            item = casebook_guard_changed_decision(record, payload, decision, hit)
            changed.append(item)
            if target in target_checks:
                target_checks[target]["hit"] = True
                target_checks[target]["simulated_action"] = hit.get("simulated_action")
                target_checks[target]["rule"] = hit.get("rule")

    hits_on_wins = sum(1 for item in changed if item.get("whether_win_case"))
    hits_on_losses = sum(1 for item in changed if item.get("whether_loss_case"))
    hit_loss_game_ids = sorted({item["game_id"] for item in changed if item.get("whether_loss_case")})
    hit_win_game_ids = sorted({item["game_id"] for item in changed if item.get("whether_win_case")})
    total_hits = len(changed)
    return {
        "profile": profile,
        "case_window": case_window,
        "record_source": "game_records",
        "detail_source": "logs*/research_game_*.json",
        "simulation_only": True,
        "evaluated_games": len(records),
        "missing_log_games": missing_logs,
        "evaluated_decision_count": evaluated_decisions,
        "narrow_rule_hits": total_hits,
        "narrow_hits_on_losses": hits_on_losses,
        "narrow_hits_on_wins": hits_on_wins,
        "narrow_hit_loss_game_ids": hit_loss_game_ids,
        "narrow_hit_win_game_ids": hit_win_game_ids,
        "narrow_false_positive_risk_estimate": {
            "hit_on_win_rate": hits_on_wins / total_hits if total_hits else 0.0,
            "hit_on_win_count": hits_on_wins,
            "note": "Offline estimate: proportion of narrow simulated changes that would have occurred in games already won.",
        },
        "narrow_changed_decision_count": total_hits,
        "narrow_changed_decision_rate": total_hits / evaluated_decisions if evaluated_decisions else 0.0,
        "narrow_target_case_checks": list(target_checks.values()),
        "narrow_concrete_changed_decisions": changed,
    }


def run_summary(
    path: str,
    recent_window: int,
    loss_drilldown: str | None = None,
    recent_loss_window: int = 20,
    endgame_audit: str | None = None,
    preloss_trace: str | None = None,
    preloss_turns: int = 5,
    decision_dataset: str | None = None,
    decision_window: int = 5,
    risk_attribution: str | None = None,
    compare_profiles: list[str] | None = None,
    loss_casebook: str | None = None,
    case_window: int = 5,
    max_cases: int = 10,
    simulate_casebook_guard: str | None = None,
    simulate_narrow_plate_guard: str | None = None,
) -> None:
    results = load_json(Path(path), {})
    results.setdefault("game_records", [])
    backfilled = backfill_game_records_from_logs(results)
    if backfilled:
        save_json(Path(path), results)
    profiles = load_json(PROFILE_PATH, {})
    summary = build_research_summary(results, profiles, recent_window)
    if loss_drilldown:
        summary["loss_drilldown"] = loss_drilldown_summary(results, loss_drilldown, recent_loss_window)
    if endgame_audit:
        summary["endgame_audit"] = endgame_audit_summary(results, endgame_audit, recent_loss_window)
    if preloss_trace:
        summary["preloss_trace"] = preloss_trace_summary(
            results,
            preloss_trace,
            recent_loss_window,
            preloss_turns,
        )
    if decision_dataset:
        summary["decision_dataset"] = decision_dataset_summary(results, decision_dataset, decision_window)
    if risk_attribution:
        summary["risk_attribution"] = risk_attribution_summary(results, risk_attribution, decision_window)
    if compare_profiles:
        summary["compare_profiles"] = compare_profiles_summary(
            results,
            compare_profiles[0],
            compare_profiles[1],
            recent_window,
            decision_window,
        )
    if loss_casebook:
        summary["loss_casebook"] = loss_casebook_summary(results, loss_casebook, case_window, max_cases)
    if simulate_casebook_guard:
        summary["casebook_guard_simulation"] = simulate_casebook_guard_summary(
            results,
            simulate_casebook_guard,
            case_window,
        )
    if simulate_narrow_plate_guard:
        summary["narrow_plate_guard_simulation"] = simulate_narrow_plate_guard_summary(
            results,
            simulate_narrow_plate_guard,
            case_window,
        )
    summary["game_records_backfilled_from_logs"] = backfilled
    print(json.dumps(summary, ensure_ascii=False, indent=2))


def is_game_does_not_exist(payload: Any) -> bool:
    if not isinstance(payload, dict):
        return False
    return str(payload.get("error", "")).lower() == "game does not exist"


def save_error_log(
    log_dir: str | None,
    game_id: str,
    profile: str,
    scenario: str,
    game_error_type: str,
    details: dict,
) -> None:
    if not log_dir:
        return
    target = Path(log_dir)
    target.mkdir(parents=True, exist_ok=True)
    path = target / f"research_game_{game_id}_{profile}_{game_error_type}_{time.strftime('%Y%m%d_%H%M%S')}.json"
    payload = {
        "game_id": game_id,
        "profile": profile,
        "scenario": scenario,
        "game_error_type": game_error_type,
        "game_counted": False,
        "research_stats_updated": False,
        **details,
    }
    save_json(path, payload)
    print(f"saved_error_log={path}")


def confirm_submit_state(game_id: str, decision: dict, flag: str) -> tuple[str, dict]:
    wait_seconds = random.uniform(1.0, 2.0)
    decision[f"{flag}_check_wait_seconds"] = wait_seconds
    time.sleep(wait_seconds)
    try:
        state = check_game(game_id)
    except SUBMIT_TRANSIENT_ERRORS as exc:
        state = {
            "is_success": False,
            "error": type(exc).__name__,
            "message": str(exc),
        }
    decision[f"{flag}_check_state"] = {
        "is_success": state.get("is_success"),
        "error": state.get("error"),
        "completed": bool(state.get("completed")),
        "is_your_turn": bool(state.get("is_your_turn")),
        "current_turn": state.get("current_turn"),
        "last_play": state.get("last_play") or [],
        "last_player": state.get("last_player"),
        "hand_counts": state.get("hand_counts"),
    }
    if not state.get("is_success", True):
        if is_game_does_not_exist(state):
            return "game_disappeared", state
        return "transient_game_unavailable", state
    if state.get("completed"):
        return "completed", state
    if not state.get("is_your_turn"):
        decision[f"{flag}_assumed_accepted"] = True
        return "accepted", state
    decision[f"{flag}_still_your_turn"] = True
    return "retry_current_state", state


def raise_recoverable_checked_state(
    status: str,
    checked_state: dict,
    args: argparse.Namespace,
    game_id: str,
    profile: str,
    scenario: str,
    turn: int,
    coord: list[str] | None,
    leaderboard_before: dict | None,
    decisions: list[dict],
    reason: str,
) -> None:
    game_error_type = "game_disappeared" if status == "game_disappeared" else "transient_game_unavailable"
    leaderboard_after = None
    if requires_leaderboard_elo(args):
        try:
            leaderboard_after = read_current_leaderboard_elo(args.leaderboard_url, engine.USER, args.timeout)
        except Exception as exc:
            leaderboard_after = {
                "leaderboard_available": False,
                "error": type(exc).__name__,
                "message": str(exc),
            }
    details = {
        "turn": turn,
        "coord": coord,
        "check_game_response": checked_state,
        "leaderboard_before": leaderboard_before,
        "leaderboard_after": leaderboard_after,
        "decisions": decisions,
        "reason": reason,
        "error_log_saved": True,
    }
    save_error_log(args.log_dir, game_id, profile, scenario, game_error_type, details)
    if game_error_type == "game_disappeared":
        raise GameDisappearedError(game_id, reason, details)
    raise TransientGameUnavailableError(game_id, reason, details)


def run_game(
    profiles: dict,
    results: dict,
    memory: dict,
    session_models: dict[int, PlayerModel],
    args: argparse.Namespace,
    fixed_profile: str | None = None,
    allowed_profiles: list[str] | None = None,
) -> dict:
    leaderboard_before = None
    if requires_leaderboard_elo(args):
        leaderboard_before = require_current_leaderboard_elo(args.leaderboard_url, args.timeout)
        print(
            "leaderboard_before "
            f"rank={leaderboard_before.get('current_user_rank')} "
            f"elo={leaderboard_before.get('current_user_elo_numeric')}"
        )
    else:
        print("metric_mode=proxy leaderboard_required=false")
    current_research_context = research_context(results, leaderboard_before)
    game_id, join_data = join_game_full()
    print(f"joined game_id={game_id}")
    before_fields = extract_rating_fields(join_data)
    decisions: list[dict] = []
    scenario = "all_unknown"
    selected_profile = fixed_profile or "tempo_baseline"
    final_state = {}
    rating_after = {}
    turn_count = 0
    submit_desync_count = 0

    while True:
        try:
            state = check_game(game_id)
        except SUBMIT_TRANSIENT_ERRORS as exc:
            details = {
                "turn": turn_count,
                "coord": None,
                "error": type(exc).__name__,
                "message": str(exc),
                "leaderboard_before": leaderboard_before,
                "decisions": decisions,
                "error_log_saved": True,
            }
            save_error_log(
                args.log_dir,
                game_id,
                selected_profile,
                scenario,
                "transient_game_unavailable",
                details,
            )
            raise TransientGameUnavailableError(
                game_id,
                f"check_game transient error: game_id={game_id} error={type(exc).__name__}",
                details,
            ) from exc
        if not state.get("is_success", True):
            if is_game_does_not_exist(state):
                details = {
                    "turn": turn_count,
                    "coord": None,
                    "check_game_response": state,
                    "leaderboard_before": leaderboard_before,
                    "error_log_saved": True,
                }
                save_error_log(
                    args.log_dir,
                    game_id,
                    selected_profile,
                    scenario,
                    "game_disappeared",
                    details,
                )
                raise GameDisappearedError(
                    game_id,
                    f"check_game says game does not exist: game_id={game_id}",
                    details,
                )
            raise RuntimeError(f"check_game failed: {state}")
        state["_research_context"] = current_research_context
        before_fields = merge_rating_fields(before_fields, extract_rating_fields(state))

        if state.get("completed"):
            observe_lead_probe_responses(state, decisions)
            final_state = state
            rating_after = extract_rating_fields(state)
            print("completed")
            break

        models = models_for_state(state, memory, session_models)
        observe_lead_probe_responses(state, decisions)
        observe_opponent_overblock(state, decisions, models)
        update_models_from_state(state, models)
        if state.get("is_your_turn"):
            turn_count += 1
            if fixed_profile:
                selected_profile = fixed_profile
                tags = scenario_tags(state, models)
            else:
                selected_profile, tags = choose_profile_for_state(
                    state,
                    models,
                    results,
                    profiles,
                    args.exploration_rate,
                    args.min_games_per_scenario_profile,
                    allowed_profiles,
                )
            scenario = scenario_key(tags)
            profile = profiles[selected_profile]
            state["_scenario_tags"] = tags
            state["_post_bait_lockdown"] = bool(any(decision.get("bait_selected") for decision in decisions))
            start = time.perf_counter()
            coord = choose_profiled_play(state, selected_profile, profile)
            decision_time_ms = (time.perf_counter() - start) * 1000.0
            features = action_features(state, coord)
            decision = engine.decision_snapshot(turn_count, state, coord)
            decision.update(
                {
                    "research_profile": selected_profile,
                    "scenario": scenario,
                    "scenario_tags": tags,
                    "research_context": current_research_context,
                    "decision_mode": decision_mode_for(selected_profile, tags),
                    "post_bait_lockdown": bool(state.get("_post_bait_lockdown")),
                    "decision_time_ms": decision_time_ms,
                    "play_is_bomb": features["is_bomb"],
                    "bad_lead_size_risk": features["bad_lead_size_risk"],
                    "giving_control_to_strong_opponent_risk": features["giving_control_to_strong_opponent_risk"],
                    "groups_after_research_score": features["groups_after"],
                }
            )
            decision.update(bait_metadata(state, selected_profile, coord))
            if selected_profile in {"tempo_shape_guard", "tempo_shape_guard_v2"}:
                decision.update(state.get("_shape_guard_meta") or shape_guard_base_meta(False))
            if selected_profile == "tempo_shape_guard_v2":
                decision.update(state.get("_shape_guard_v2_meta") or shape_guard_v2_base_meta())
            if selected_profile == "tempo_plate_delay_guard":
                decision.update(state.get("_plate_delay_guard_meta") or plate_delay_guard_base_meta())
            decision.update(lead_probe_metadata(state, game_id, turn_count, selected_profile, scenario, coord))
            decision.update(bait_attempt_observation_metadata(state, selected_profile, coord, decision))
            if args.website_shadow:
                decision["website_shadow"] = live_shadow.build_shadow_audit(
                    state,
                    coord,
                    coord,
                    suggestion_source=live_shadow.SHADOW_SUGGESTION_SOURCE,
                )
            decisions.append(decision)
            print(
                f"turn={turn_count} profile={selected_profile} scenario={scenario} "
                f"level={state['level']} hand={len(state['your_hand'])} "
                f"last={state.get('last_play') or []} play={coord}"
            )
            try:
                result = play_game(game_id, coord)
            except SUBMIT_TRANSIENT_ERRORS as exc:
                decision["submit_timeout_error"] = type(exc).__name__
                print(f"submit_timeout game_id={game_id} error={type(exc).__name__}")
                status, checked_state = confirm_submit_state(game_id, decision, "submit_timeout")
                if status == "completed":
                    live_shadow.mark_submit_acceptance_inferred(decision.get("website_shadow"))
                    final_state = checked_state
                    rating_after = extract_rating_fields(checked_state)
                    print("completed_after_submit_timeout")
                    break
                if status == "accepted":
                    decision["submit_timeout_assumed_accepted"] = True
                    live_shadow.mark_submit_acceptance_inferred(decision.get("website_shadow"))
                    submit_desync_count = 0
                    continue
                if status in {"game_disappeared", "transient_game_unavailable"}:
                    raise_recoverable_checked_state(
                        status,
                        checked_state,
                        args,
                        game_id,
                        selected_profile,
                        scenario,
                        turn_count,
                        coord,
                        leaderboard_before,
                        decisions,
                        f"submit timeout check returned {status}: game_id={game_id}",
                    )
                submit_desync_count += 1
                if submit_desync_count >= MAX_SUBMIT_DESYNC_COUNT:
                    raise SubmitDesyncError(
                        game_id,
                        f"submit timeout desync repeated {submit_desync_count} times for game_id={game_id}",
                    ) from exc
                continue
            decision["result"] = result
            live_shadow.mark_submit_result(decision.get("website_shadow"), result)
            rating_after = merge_rating_fields(rating_after, extract_rating_fields(result))
            print(json.dumps(result, ensure_ascii=False))
            if not result.get("is_success"):
                error_text = str(result.get("error", ""))
                if error_text.lower() == "game does not exist":
                    decision["game_does_not_exist_after_submit"] = True
                    check_response = None
                    leaderboard_after = None
                    try:
                        check_response = check_game(game_id)
                    except Exception as exc:
                        check_response = {"is_success": False, "error": type(exc).__name__, "message": str(exc)}
                    if isinstance(check_response, dict) and check_response.get("completed"):
                        final_state = check_response
                        rating_after = extract_rating_fields(check_response)
                        print("completed_after_game_does_not_exist")
                        break
                    if requires_leaderboard_elo(args):
                        try:
                            leaderboard_after = read_current_leaderboard_elo(
                                args.leaderboard_url,
                                engine.USER,
                                args.timeout,
                            )
                        except Exception as exc:
                            leaderboard_after = {
                                "leaderboard_available": False,
                                "error": type(exc).__name__,
                                "message": str(exc),
                            }
                    details = {
                        "turn": turn_count,
                        "coord": coord,
                        "play_game_response": result,
                        "check_game_response": check_response,
                        "leaderboard_before": leaderboard_before,
                        "leaderboard_after": leaderboard_after,
                        "decisions": decisions,
                        "error_log_saved": True,
                    }
                    save_error_log(
                        args.log_dir,
                        game_id,
                        selected_profile,
                        scenario,
                        "game_disappeared",
                        details,
                    )
                    raise GameDisappearedError(
                        game_id,
                        f"play_game says game does not exist: game_id={game_id}",
                        details,
                    )
                if error_text.lower() == "not your turn":
                    decision["not_your_turn_after_submit"] = True
                    status, checked_state = confirm_submit_state(game_id, decision, "not_your_turn_after_submit")
                    if status == "completed":
                        live_shadow.mark_submit_acceptance_inferred(decision.get("website_shadow"))
                        final_state = checked_state
                        rating_after = extract_rating_fields(checked_state)
                        print("completed_after_not_your_turn")
                        break
                    if status == "accepted":
                        live_shadow.mark_submit_acceptance_inferred(decision.get("website_shadow"))
                        submit_desync_count = 0
                        continue
                    if status in {"game_disappeared", "transient_game_unavailable"}:
                        raise_recoverable_checked_state(
                            status,
                            checked_state,
                            args,
                            game_id,
                            selected_profile,
                            scenario,
                            turn_count,
                            coord,
                            leaderboard_before,
                            decisions,
                            f"not-your-turn check returned {status}: game_id={game_id}",
                        )
                    submit_desync_count += 1
                    if submit_desync_count >= MAX_SUBMIT_DESYNC_COUNT:
                        raise NotYourTurnAfterTimeoutError(
                            game_id,
                            f"not-your-turn desync repeated {submit_desync_count} times for game_id={game_id}",
                            {
                                "turn": turn_count,
                                "coord": coord,
                                "decisions": decisions,
                            },
                        )
                    continue
                try:
                    fallback_state = check_game(game_id)
                except SUBMIT_TRANSIENT_ERRORS as exc:
                    fallback_state = {
                        "is_success": False,
                        "error": type(exc).__name__,
                        "message": str(exc),
                    }
                decision["fallback_precheck_state"] = {
                    "is_success": fallback_state.get("is_success"),
                    "error": fallback_state.get("error"),
                    "completed": bool(fallback_state.get("completed")),
                    "is_your_turn": bool(fallback_state.get("is_your_turn")),
                    "current_turn": fallback_state.get("current_turn"),
                }
                if not fallback_state.get("is_success", True):
                    status = "game_disappeared" if is_game_does_not_exist(fallback_state) else "transient_game_unavailable"
                    raise_recoverable_checked_state(
                        status,
                        fallback_state,
                        args,
                        game_id,
                        selected_profile,
                        scenario,
                        turn_count,
                        coord,
                        leaderboard_before,
                        decisions,
                        f"fallback precheck returned {status}: game_id={game_id}",
                    )
                if fallback_state.get("completed"):
                    final_state = fallback_state
                    rating_after = extract_rating_fields(fallback_state)
                    print("completed_before_fallback_pass")
                    break
                if coord and (state.get("last_play") or []) and fallback_state.get("is_your_turn"):
                    try:
                        fallback = play_game(game_id, [])
                    except SUBMIT_TRANSIENT_ERRORS as exc:
                        decision["fallback_pass_timeout_error"] = type(exc).__name__
                        status, checked_state = confirm_submit_state(game_id, decision, "fallback_pass_timeout")
                        if status == "completed":
                            final_state = checked_state
                            rating_after = extract_rating_fields(checked_state)
                            print("completed_after_fallback_timeout")
                            break
                        if status == "accepted":
                            submit_desync_count = 0
                            continue
                        if status in {"game_disappeared", "transient_game_unavailable"}:
                            raise_recoverable_checked_state(
                                status,
                                checked_state,
                                args,
                                game_id,
                                selected_profile,
                                scenario,
                                turn_count,
                                [],
                                leaderboard_before,
                                decisions,
                                f"fallback pass timeout check returned {status}: game_id={game_id}",
                            )
                    else:
                        decision["fallback_pass"] = fallback
                        print(f"fallback_pass={json.dumps(fallback, ensure_ascii=False)}")
                        if fallback.get("is_success"):
                            submit_desync_count = 0
                            time.sleep(1)
                            continue
                raise RuntimeError(f"play_game failed for {coord}: {result}")
            submit_desync_count = 0
            time.sleep(1)
        else:
            print(
                f"waiting current_turn={state.get('current_turn')} "
                f"hand_counts={state.get('hand_counts')} left_time={state.get('left_time')}"
            )
            time.sleep(args.poll)

    observe_lead_probe_responses(final_state, decisions)
    models = models_for_state(final_state, memory, session_models)
    mark_game_seen(models)
    persist_stable_models(final_state, memory, models)
    save_bot_memory(memory)
    rating_after = merge_rating_fields(rating_after, extract_rating_fields(final_state))
    if requires_leaderboard_elo(args):
        wait_seconds = random.uniform(LEADERBOARD_AFTER_WAIT_MIN_SECONDS, LEADERBOARD_AFTER_WAIT_MAX_SECONDS)
        print(f"leaderboard_after_wait seconds={wait_seconds:.2f}")
        time.sleep(wait_seconds)
        leaderboard_after = require_current_leaderboard_elo(args.leaderboard_url, args.timeout)
        print(
            "leaderboard_after "
            f"rank={leaderboard_after.get('current_user_rank')} "
            f"elo={leaderboard_after.get('current_user_elo_numeric')}"
        )
        elo_result = resolve_leaderboard_elo_delta(leaderboard_before or {}, leaderboard_after, final_state)
    else:
        elo_result = resolve_proxy_metric(final_state)
    update_research_results(results, game_id, scenario, selected_profile, final_state, elo_result, decisions)
    save_game_log(args.log_dir, game_id, scenario, selected_profile, final_state, decisions, before_fields, rating_after, elo_result)
    final_state["_metric_result"] = elo_result
    final_state["_leaderboard_elo_result"] = elo_result if elo_result.get("metric_source") == "leaderboard_elo" else None
    return final_state


def save_game_log(
    log_dir: str | None,
    game_id: str,
    scenario: str,
    profile: str,
    final_state: dict,
    decisions: list[dict],
    before_fields: dict,
    after_fields: dict,
    elo_result: dict,
) -> None:
    if not log_dir:
        return
    target = Path(log_dir)
    target.mkdir(parents=True, exist_ok=True)
    outcome = "win" if final_state.get("winner_team") == final_state.get("your_team") else "loss"
    path = target / f"research_game_{game_id}_{profile}_{outcome}_{time.strftime('%Y%m%d_%H%M%S')}.json"
    failure_counts = failure_reasons(final_state, decisions)
    bait_summary = summarize_bait_and_overblock(decisions, failure_counts, elo_result)
    website_shadow_summary = live_shadow.summarize_decisions(decisions)
    payload = {
        "game_id": game_id,
        "scenario": scenario,
        "profile": profile,
        "outcome": outcome,
        "completed_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "game_counted": True,
        "elo_before": elo_result.get("elo_before"),
        "elo_after": elo_result.get("elo_after"),
        "elo_delta": elo_result.get("elo_delta"),
        "metric_source": elo_result.get("metric_source"),
        "proxy_scores": final_state.get("scores"),
        "failure_tags": sorted(failure_counts),
        "failure_reason_counts": dict(failure_counts),
        **bait_summary,
        "rating_fields_before": before_fields.get("confirmed", {}),
        "candidate_rating_fields_before": before_fields.get("candidates", {}),
        "rating_fields_after": after_fields.get("confirmed", {}),
        "candidate_rating_fields_after": after_fields.get("candidates", {}),
        "elo_result": elo_result,
        "detected_elo_before": elo_result.get("elo_before"),
        "detected_elo_after": elo_result.get("elo_after"),
        "detected_elo_delta": elo_result.get("elo_delta"),
        "elo_source_field": elo_result.get("elo_source_field"),
        "elo_available": elo_result.get("elo_available"),
        "elo_unavailable": elo_result.get("elo_unavailable"),
        "proxy_points": elo_result.get("proxy_points"),
        "proxy_metric_source": elo_result.get("proxy_metric_source"),
        **(
            {"website_shadow_summary": website_shadow_summary}
            if website_shadow_summary.get("shadow_decision_count")
            else {}
        ),
        "decisions": decisions,
        "final_state": final_state,
    }
    save_json(path, payload)
    print(f"saved_research_log={path}")


def normalize_html_text(value: str) -> str:
    value = html.unescape(value or "")
    return re.sub(r"\s+", " ", value).strip()


class SimpleTableParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.tables: list[list[list[str]]] = []
        self._table_stack = 0
        self._current_table: list[list[str]] | None = None
        self._current_row: list[str] | None = None
        self._current_cell: list[str] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        if tag == "table":
            self._table_stack += 1
            if self._table_stack == 1:
                self._current_table = []
        elif tag == "tr" and self._current_table is not None:
            self._current_row = []
        elif tag in {"th", "td"} and self._current_row is not None:
            self._current_cell = []

    def handle_data(self, data: str) -> None:
        if self._current_cell is not None:
            self._current_cell.append(data)

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag in {"th", "td"} and self._current_row is not None and self._current_cell is not None:
            self._current_row.append(normalize_html_text("".join(self._current_cell)))
            self._current_cell = None
        elif tag == "tr" and self._current_table is not None and self._current_row is not None:
            if any(cell for cell in self._current_row):
                self._current_table.append(self._current_row)
            self._current_row = None
        elif tag == "table" and self._table_stack > 0:
            self._table_stack -= 1
            if self._table_stack == 0 and self._current_table is not None:
                self.tables.append(self._current_table)
                self._current_table = None


def canonical_header(value: str) -> str | None:
    text = normalize_html_text(value).lower()
    if text in {"#", "排名", "rank"}:
        return "#"
    if text in {"用户", "用户名", "user", "username", "name"}:
        return "用户"
    if text in {"elo", "评分", "elo评分", "elo score"}:
        return "Elo"
    return None


def parse_leaderboard_number(value: str | None) -> int | float | None:
    if value is None:
        return None
    match = re.search(r"-?\d+(?:\.\d+)?", str(value).replace(",", ""))
    if not match:
        return None
    number = float(match.group(0))
    return int(number) if number.is_integer() else number


def find_leaderboard_row(tables: list[list[list[str]]], username: str) -> dict:
    result = {
        "table_found": bool(tables),
        "required_columns_found": False,
        "current_user_found": False,
        "rank": None,
        "elo": None,
        "matched_username": None,
        "table_index": None,
        "header_row_index": None,
    }
    normalized_user = normalize_html_text(username)
    for table_index, table in enumerate(tables):
        for row_index, row in enumerate(table):
            header_map: dict[str, int] = {}
            for index, cell in enumerate(row):
                header = canonical_header(cell)
                if header and header not in header_map:
                    header_map[header] = index
            if not {"#", "用户", "Elo"}.issubset(header_map):
                continue
            result.update(
                {
                    "required_columns_found": True,
                    "table_index": table_index,
                    "header_row_index": row_index,
                }
            )
            for data_row in table[row_index + 1:]:
                max_index = max(header_map.values())
                if len(data_row) <= max_index:
                    continue
                row_user = normalize_html_text(data_row[header_map["用户"]])
                if row_user != normalized_user:
                    continue
                result.update(
                    {
                        "current_user_found": True,
                        "rank": normalize_html_text(data_row[header_map["#"]]),
                        "elo": normalize_html_text(data_row[header_map["Elo"]]),
                        "matched_username": row_user,
                    }
                )
                return result
    return result


def fetch_leaderboard_html(url: str, timeout: float) -> tuple[bool, int | None, str, str | None]:
    request = Request(url, headers={"User-Agent": "play-research-adaptive/1.0"})
    try:
        with urlopen(request, timeout=timeout) as response:
            raw = response.read()
            charset = response.headers.get_content_charset() or "utf-8"
            return True, int(response.status), raw.decode(charset, errors="replace"), None
    except HTTPError as exc:
        try:
            raw = exc.read()
            charset = exc.headers.get_content_charset() or "utf-8"
            body = raw.decode(charset, errors="replace")
        except Exception:
            body = ""
        return False, int(exc.code), body, str(exc)
    except URLError as exc:
        return False, None, "", str(exc.reason)
    except OSError as exc:
        return False, None, "", str(exc)


def read_current_leaderboard_elo(url: str, username: str, timeout: float) -> dict:
    ok, status_code, body, error = fetch_leaderboard_html(url, timeout)
    parser = SimpleTableParser()
    if body:
        parser.feed(body)
    row_result = find_leaderboard_row(parser.tables, username)
    elo_numeric = parse_leaderboard_number(row_result["elo"])
    available = bool(
        ok
        and status_code is not None
        and 200 <= status_code < 300
        and row_result["table_found"]
        and row_result["required_columns_found"]
        and row_result["current_user_found"]
        and elo_numeric is not None
    )
    reasons: list[str] = []
    if not ok:
        reasons.append(f"leaderboard_request_failed: {error}")
    if not row_result["table_found"]:
        reasons.append("no_html_table_found")
    if row_result["table_found"] and not row_result["required_columns_found"]:
        reasons.append("required_columns_not_found: expected # / 用户 / Elo")
    if row_result["required_columns_found"] and not row_result["current_user_found"]:
        reasons.extend(
            [
                "current_user_not_found_in_visible_rows",
                "possible_account_not_ranked_yet",
                "possible_username_display_differs",
                "possible_pagination_or_top_rows_only",
            ]
        )
    return {
        "leaderboard_url": url,
        "leaderboard_request_success": ok,
        "http_status_code": status_code,
        "table_found": row_result["table_found"],
        "required_columns_found": row_result["required_columns_found"],
        "required_columns": ["#", "用户", "Elo"],
        "current_username": username,
        "current_user_found": row_result["current_user_found"],
        "current_user_rank": row_result["rank"],
        "current_user_rank_numeric": parse_leaderboard_number(row_result["rank"]),
        "current_user_elo": row_result["elo"],
        "current_user_elo_numeric": elo_numeric,
        "leaderboard_available": available,
        "metric_source": "leaderboard_elo" if available else None,
        "elo_available": available,
        "elo_unavailable": not available,
        "reasons": reasons,
    }


def require_current_leaderboard_elo(url: str, timeout: float) -> dict:
    snapshot = read_current_leaderboard_elo(url, engine.USER, timeout)
    if not snapshot.get("elo_available"):
        raise RuntimeError(
            "leaderboard Elo unavailable; stop research instead of using proxy. "
            f"details={json.dumps(snapshot, ensure_ascii=False)}"
        )
    return snapshot


def resolve_leaderboard_elo_delta(before_snapshot: dict, after_snapshot: dict, final_state: dict) -> dict:
    before = before_snapshot.get("current_user_elo_numeric")
    after = after_snapshot.get("current_user_elo_numeric")
    if before is None or after is None:
        return {
            "elo_available": False,
            "elo_unavailable": True,
            "elo_source_field": None,
            "metric_source": None,
            "elo_before": None,
            "elo_after": None,
            "elo_delta": None,
            "proxy_scores": final_state.get("scores") if isinstance(final_state, dict) else None,
            "proxy_metric_source": "final_state.scores",
            "leaderboard_before": before_snapshot,
            "leaderboard_after": after_snapshot,
        }
    delta = float(after) - float(before)
    return {
        "elo_available": True,
        "elo_unavailable": False,
        "elo_source_field": "leaderboard_elo",
        "metric_source": "leaderboard_elo",
        "elo_before": before,
        "elo_after": after,
        "elo_delta": delta,
        "total_elo_delta": delta,
        "average_elo_delta_per_game": delta,
        "max_elo_gain": max(delta, 0.0),
        "max_elo_loss": min(delta, 0.0),
        "big_elo_loss_count": 1 if delta <= BIG_ELO_LOSS_THRESHOLD else 0,
        "proxy_scores": final_state.get("scores") if isinstance(final_state, dict) else None,
        "proxy_metric_source": "final_state.scores",
        "leaderboard_before": before_snapshot,
        "leaderboard_after": after_snapshot,
    }


def resolve_proxy_metric(final_state: dict) -> dict:
    return {
        "elo_available": False,
        "elo_unavailable": True,
        "elo_source_field": None,
        "metric_source": "proxy_not_elo",
        "elo_before": None,
        "elo_after": None,
        "elo_delta": None,
        "total_elo_delta": None,
        "average_elo_delta_per_game": None,
        "max_elo_gain": None,
        "max_elo_loss": None,
        "big_elo_loss_count": None,
        "proxy_scores": final_state.get("scores") if isinstance(final_state, dict) else None,
        "proxy_metric_source": "final_state.scores",
    }


def requires_leaderboard_elo(args: argparse.Namespace) -> bool:
    return bool(args.require_elo or args.metric == "elo")


def save_leaderboard_probe_log(args: argparse.Namespace, result: dict) -> None:
    if not args.log_dir:
        return
    target = Path(args.log_dir)
    target.mkdir(parents=True, exist_ok=True)
    path = target / f"leaderboard_probe_{time.strftime('%Y%m%d_%H%M%S')}.json"
    save_json(path, result)
    print(f"saved_leaderboard_probe_log={path}")


def run_leaderboard_probe(args: argparse.Namespace, results: dict) -> None:
    result = read_current_leaderboard_elo(args.probe_leaderboard, engine.USER, args.timeout)
    results["last_leaderboard_probe"] = result
    if result.get("elo_available"):
        results["leaderboard_available"] = True
        results["metric_source"] = "leaderboard_elo"
    save_json(RESULTS_PATH, results)
    save_leaderboard_probe_log(args, result)
    print("leaderboard_probe=" + json.dumps(result, ensure_ascii=False, indent=2))


def print_rating_probe(game_index: int, before_fields: dict, after_fields: dict, elo_result: dict) -> None:
    print(f"probe_game={game_index}")
    print("rating_fields_before=" + json.dumps(before_fields.get("confirmed", {}), ensure_ascii=False))
    print("candidate_rating_fields_before=" + json.dumps(before_fields.get("candidates", {}), ensure_ascii=False))
    print("rating_fields_after=" + json.dumps(after_fields.get("confirmed", {}), ensure_ascii=False))
    print("candidate_rating_fields_after=" + json.dumps(after_fields.get("candidates", {}), ensure_ascii=False))
    print("elo_result=" + json.dumps(elo_result, ensure_ascii=False))
    if not elo_result.get("elo_available"):
        print(
            'elo_unavailable=true reason="No confirmed Elo/rating/leaderboard field found. '
            'final_state.scores is treated as proxy only."'
        )


def run_probe(args: argparse.Namespace, profiles: dict, results: dict, memory: dict) -> None:
    session_models: dict[int, PlayerModel] = {}
    any_elo_available = False
    last_reason = "Probe complete. See logs for candidate fields."
    for index in range(1, args.games + 1):
        final_state = run_game(
            profiles,
            results,
            memory,
            session_models,
            args,
            fixed_profile="tempo_baseline",
            allowed_profiles=["tempo_baseline"],
        )
        log_files = sorted(Path(args.log_dir or DEFAULT_LOG_DIR).glob("research_game_*.json"))
        if log_files:
            latest = load_json(log_files[-1], {})
            print_rating_probe(
                index,
                {"confirmed": latest.get("rating_fields_before", {}), "candidates": latest.get("candidate_rating_fields_before", {})},
                {"confirmed": latest.get("rating_fields_after", {}), "candidates": latest.get("candidate_rating_fields_after", {})},
                latest.get("elo_result", {}),
            )
            any_elo_available = any_elo_available or bool(latest.get("elo_result", {}).get("elo_available"))
            if not latest.get("elo_result", {}).get("elo_available"):
                last_reason = (
                    "No confirmed Elo/rating/leaderboard field found. "
                    "final_state.scores is treated as proxy only."
                )
    results["last_probe"] = {
        "elo_available": any_elo_available,
        "elo_unavailable": not any_elo_available,
        "reason": "Confirmed Elo/rating field found." if any_elo_available else last_reason,
    }
    save_json(RESULTS_PATH, results)


def loop_summary(stats: dict, args: argparse.Namespace) -> str:
    games = max(1, stats["games"])
    if args.metric == "proxy" and not args.require_elo:
        return (
            f"research_summary games={stats['games']} wins={stats['wins']} "
            f"proxy_points={stats['proxy_points']} "
            f"average_proxy_points_per_game={stats['proxy_points'] / games:.3f} "
            f"metric_source=proxy_not_elo proxy_metric_source=final_state.scores"
        )
    return (
        f"research_summary games={stats['games']} wins={stats['wins']} "
        f"total_elo_delta={stats['total_elo_delta']:.3f} "
        f"average_elo_delta_per_game={stats['total_elo_delta'] / games:.3f} "
        f"last_elo_delta={stats['last_elo_delta']:.3f} "
        f"metric_source=leaderboard_elo"
    )


def run_loop(args: argparse.Namespace) -> None:
    profiles = load_json(PROFILE_PATH, {})
    results = load_json(RESULTS_PATH, {"version": 1, "scenario_profiles": {}, "global_profile_stats": {}})
    memory = load_bot_memory()
    session_models: dict[int, PlayerModel] = {}
    alternate = [name.strip() for name in (args.alternate_profiles or "").split(",") if name.strip()]
    if args.profile:
        allowed = [args.profile]
    elif alternate:
        allowed = alternate
    else:
        allowed = None
    fixed_profile = args.profile if args.profile else None
    stats = {
        "games": 0,
        "wins": 0,
        "total_elo_delta": 0.0,
        "last_elo_delta": 0.0,
        "proxy_points": 0,
        "submit_desync_errors": 0,
        "recoverable_game_errors": 0,
    }

    for game_index in range(args.games if args.games else 1_000_000):
        try:
            final_state = run_game(profiles, results, memory, session_models, args, fixed_profile, allowed)
        except RecoverableGameError as exc:
            stats["recoverable_game_errors"] += 1
            if exc.game_error_type == "submit_desync":
                stats["submit_desync_errors"] += 1
            if not exc.payload.get("error_log_saved"):
                save_error_log(
                    args.log_dir,
                    exc.game_id,
                    fixed_profile or "unknown_profile",
                    "unknown_scenario",
                    exc.game_error_type,
                    {
                        "message": str(exc),
                        "payload": exc.payload,
                    },
                )
            print(
                f"game_error_type={exc.game_error_type} game_id={exc.game_id} "
                f"game_counted=false research_stats_updated=false message={exc}"
            )
            if not args.loop:
                break
            time.sleep(args.error_delay)
            continue
        stats["games"] += 1
        stats["wins"] += 1 if final_state.get("winner_team") == final_state.get("your_team") else 0
        metric_result = final_state.get("_metric_result") or {}
        if metric_result.get("metric_source") == "leaderboard_elo":
            delta = float(metric_result.get("elo_delta") or 0.0)
            stats["last_elo_delta"] = delta
            stats["total_elo_delta"] += delta
        else:
            scores = final_state.get("scores") or {}
            try:
                stats["proxy_points"] += int(scores.get(str(final_state.get("your_team")), 0))
            except (AttributeError, TypeError, ValueError):
                pass
        print(loop_summary(stats, args))
        if (game_index + 1) % args.report_every == 0:
            print(json.dumps(ranking_report(load_json(RESULTS_PATH, {})), ensure_ascii=False, indent=2))
        if not args.loop:
            break
        time.sleep(args.delay)


def offline_load_guandan_components() -> dict:
    if not OFFLINE_GUANDAN_DIR.exists():
        raise RuntimeError(f"offline guandan project not found: {OFFLINE_GUANDAN_DIR}")
    guandan_path = str(OFFLINE_GUANDAN_DIR)
    if guandan_path not in sys.path:
        sys.path.insert(0, guandan_path)
    from get_actions import enumerate_colorful_actions  # type: ignore
    from guandan_env import GuandanGame  # type: ignore

    actions_path = OFFLINE_GUANDAN_DIR / "doudizhu_actions.json"
    actions = json.loads(actions_path.read_text(encoding="utf-8"))
    if len(actions) != OFFLINE_ACTION_DIM:
        raise RuntimeError(f"expected {OFFLINE_ACTION_DIM} actions, got {len(actions)}")
    action_by_id = {int(action["id"]): action for action in actions}
    return {
        "GuandanGame": GuandanGame,
        "enumerate_colorful_actions": enumerate_colorful_actions,
        "actions": actions,
        "action_by_id": action_by_id,
    }


def offline_resolve_device(requested_device: str) -> dict:
    requested = (requested_device or "cpu").lower()
    if requested not in {"cpu", "cuda"}:
        raise RuntimeError(f"unsupported --device value: {requested_device}")
    try:
        import torch
    except ModuleNotFoundError:
        return {
            "backend": "numpy",
            "requested_device": requested,
            "actual_device": "cpu",
            "device_fallback": requested == "cuda",
            "torch_available": False,
            "cuda_available": False,
            "torch": None,
            "device": None,
        }
    cuda_available = bool(torch.cuda.is_available())
    actual_device = "cuda" if requested == "cuda" and cuda_available else "cpu"
    return {
        "backend": "torch",
        "requested_device": requested,
        "actual_device": actual_device,
        "device_fallback": requested == "cuda" and actual_device == "cpu",
        "torch_available": True,
        "cuda_available": cuda_available,
        "torch": torch,
        "device": torch.device(actual_device),
    }


def offline_team_id(player_id: int) -> int:
    return 0 if player_id in (0, 2) else 1


def offline_teammate(player_id: int) -> int:
    return {0: 2, 2: 0, 1: 3, 3: 1}[player_id]


def offline_local_player_mapping() -> dict:
    return {
        "0": "player1/self/A_team",
        "1": "player2/opponent/B_team",
        "2": "player3/teammate/A_team",
        "3": "player4/opponent/B_team",
    }


def offline_team_mapping() -> dict:
    return {"A_team": [0, 2], "B_team": [1, 3]}


def offline_set_random_first_player(game: Any, rng: random.Random) -> int:
    first_player = int(rng.randrange(4))
    game.current_player = first_player
    return first_player


def offline_card_counter(cards: list[str]) -> Counter:
    return Counter(cards or [])


def offline_cards_in_hand(cards: list[str], hand: list[str]) -> bool:
    needed = offline_card_counter(cards)
    available = offline_card_counter(hand)
    return all(available[card] >= count for card, count in needed.items())


def offline_missing_cards(cards: list[str], hand: list[str]) -> list[str]:
    needed = offline_card_counter(cards)
    available = offline_card_counter(hand)
    missing: list[str] = []
    for card, count in needed.items():
        deficit = count - available.get(card, 0)
        if deficit > 0:
            missing.extend([card] * deficit)
    return missing


def offline_prepare_turn(game: Any) -> None:
    skipped = 0
    while game.current_player in game.ranking and skipped < 4:
        game.recent_actions[game.current_player] = []
        game.players[game.current_player].last_played_cards = []
        game.current_player = (game.current_player + 1) % 4
        skipped += 1
    active_players = 4 - len(game.ranking)
    if active_players <= 0 or game.current_player in game.ranking:
        return
    if game.pass_count >= active_players - 1:
        if game.jiefeng and game.ranking:
            teammate = offline_teammate(game.ranking[-1])
            if teammate not in game.ranking:
                game.current_player = teammate
        game.last_play = None
        game.pass_count = 0
        game.is_free_turn = True
        game.jiefeng = False


def offline_action_is_bomb(action: dict | None) -> bool:
    if not action:
        return False
    action_type = str(action.get("type") or "")
    return "bomb" in action_type or action_type == "flush_rocket"


def offline_action_rank_label(action: dict | None) -> str | None:
    if not action:
        return None
    value = action.get("logic_point")
    return None if value is None else str(value)


def offline_map_action(game: Any, actions: list[dict], cards: list[str]) -> dict | None:
    if not cards:
        return {"type": "None", "points": [], "logic_point": 0, "id": 0}
    return game.map_cards_to_action(cards, actions, game.active_level)


def offline_action_is_legal(
    game: Any,
    actions: list[dict],
    cards: list[str],
    hand_before: list[str],
    last_play_before: list[str] | None,
    was_lead: bool,
) -> tuple[bool, str | None]:
    if not cards:
        if was_lead:
            return False, "pass_on_lead"
        return True, None
    if not offline_cards_in_hand(cards, hand_before):
        return False, "cards_not_in_hand"
    del actions
    level = website_level_from_local_level(game.active_level)
    website_cards = local_cards_to_website(cards)
    if was_lead or not last_play_before:
        if not engine.recognize(website_cards, level):
            return False, "unmapped_action"
        return True, None
    website_last = local_cards_to_website(list(last_play_before))
    if not engine.play_beats(website_cards, website_last, level):
        return False, "cannot_beat_last_play"
    return True, None


def offline_rank_text(active_level: int) -> str:
    ranks = ["2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K", "A"]
    if 2 <= int(active_level) <= 14:
        return ranks[int(active_level) - 2]
    return str(active_level)


def offline_is_level_card(card: str, active_level: int) -> bool:
    rank = offline_rank_text(active_level)
    return card.endswith(rank)


def offline_is_joker(card: str) -> bool:
    return "王" in card


def offline_action_uses_level_or_joker(cards: list[str], active_level: int) -> bool:
    return any(offline_is_joker(card) or offline_is_level_card(card, active_level) for card in cards)


def offline_heart_level_mix_issue(cards: list[str], active_level: int) -> bool:
    level_cards = [card for card in cards if offline_is_level_card(card, active_level)]
    if len(level_cards) < 2:
        return False
    has_heart = any(card.startswith("红桃") for card in level_cards)
    has_non_heart = any(not card.startswith("红桃") for card in level_cards)
    return has_heart and has_non_heart


def offline_action_cards_for_id(
    game: Any,
    components: dict,
    action_id: int,
    hand_before: list[str],
    last_play_before: list[str] | None,
    was_lead: bool,
    rng: random.Random,
) -> tuple[list[str] | None, str | None]:
    actions = components["actions"]
    action_by_id = components["action_by_id"]
    enumerate_colorful_actions = components["enumerate_colorful_actions"]
    if action_id == 0:
        cards: list[str] = []
        ok, reason = offline_action_is_legal(game, actions, cards, hand_before, last_play_before, was_lead)
        return (cards, None) if ok else (None, reason)
    action = action_by_id.get(int(action_id))
    if not action:
        return None, "action_id_not_found"
    combos = enumerate_colorful_actions(action, hand_before, game.active_level)
    rng.shuffle(combos)
    for combo in combos:
        cards = list(combo)
        ok, reason = offline_action_is_legal(game, actions, cards, hand_before, last_play_before, was_lead)
        if ok:
            return cards, None
    return None, "no_legal_combo_for_action_id"


def website_level_from_local_level(active_level: int) -> str:
    ranks = ["2", "3", "4", "5", "6", "7", "8", "9", "T", "J", "Q", "K", "A"]
    if 2 <= int(active_level) <= 14:
        return ranks[int(active_level) - 2]
    return str(active_level)


def rank_to_action_point(rank: str, level: str, sequence: bool = False) -> int:
    if rank == "B":
        return 16
    if rank == "R":
        return 17
    if not sequence and rank == level:
        return 15
    face = {"T": 10, "J": 11, "Q": 12, "K": 13, "A": 14}
    if rank in face:
        return face[rank]
    return int(rank)


def sequence_logic_point(cards: list[str] | tuple[str, ...], info: Any, sequence_len: int) -> int:
    ranks = {card_rank(card) for card in cards if card not in {"B", "R"}}
    if "A" in ranks and info.rank in {"3", "5"}:
        return 1
    high = rank_to_action_point(info.rank, level="A", sequence=True)
    return high - sequence_len + 1


def full_house_pair_rank(cards: list[str] | tuple[str, ...], triple_rank: str, level: str) -> str:
    wild = "H" + level
    counts = Counter(card_rank(card) for card in cards if card not in {"B", "R"} and card != wild)
    for rank, count in counts.items():
        if rank != triple_rank and count > 0:
            return rank
    for rank in engine.RANKS:
        if rank != triple_rank:
            return rank
    return "2"


def website_action_id_for_info(components: dict, cards: list[str] | tuple[str, ...], info: Any, level: str) -> int | None:
    action_type = info.type
    logic_point: int
    target_type: str
    points: list[int] | None = None
    if action_type == "single":
        target_type = "single"
        logic_point = rank_to_action_point(info.rank, level)
    elif action_type == "pair":
        target_type = "pair"
        logic_point = rank_to_action_point(info.rank, level)
    elif action_type == "triple":
        target_type = "triple"
        logic_point = rank_to_action_point(info.rank, level)
    elif action_type == "full_house":
        target_type = "three_with_pair"
        logic_point = rank_to_action_point(info.rank, level)
        pair_rank = full_house_pair_rank(cards, info.rank, level)
        triple_point = rank_to_action_point(info.rank, level)
        pair_point = rank_to_action_point(pair_rank, level)
        points = [triple_point, triple_point, triple_point, pair_point, pair_point]
    elif action_type == "straight":
        target_type = "straight"
        logic_point = sequence_logic_point(cards, info, 5)
    elif action_type == "straight_flush":
        target_type = "flush_rocket"
        logic_point = sequence_logic_point(cards, info, 5)
    elif action_type == "plate":
        target_type = "pair_chain"
        logic_point = sequence_logic_point(cards, info, 3)
    elif action_type == "steel":
        target_type = "gangban"
        logic_point = sequence_logic_point(cards, info, 2)
    elif action_type == "bomb":
        target_type = f"{info.size}_bomb"
        logic_point = rank_to_action_point(info.rank, level)
    elif action_type == "quad_kings":
        target_type = "joker_bomb"
        logic_point = 1
    else:
        return None
    for action in components["actions"]:
        if action.get("type") != target_type:
            continue
        if int(action.get("logic_point", -999)) != int(logic_point):
            continue
        if points is not None and sorted(action.get("points") or []) != sorted(points):
            continue
        return int(action["id"])
    return None


def website_compatible_verified_options(
    components: dict,
    local_hand: list[str],
    local_last_play: list[str] | None,
    was_lead: bool,
    max_combos_per_action: int,
) -> dict[int, list[list[str]]]:
    level = website_level_from_local_level(components.get("_active_level", 2))
    website_hand = local_cards_to_website(local_hand)
    website_last = local_cards_to_website(list(local_last_play or []))
    options: dict[int, list[list[str]]] = {}
    if not was_lead:
        options[0] = [[]]
    candidate_cards: list[list[str]] = []
    if was_lead:
        candidate_cards = casebook_lead_candidate_cards(website_hand, level)
    else:
        seen_follow: set[tuple[str, ...]] = set()
        if len(website_last) <= 3:
            for combo in itertools.combinations(website_hand, len(website_last)):
                key = website_action_set_key(combo, level)
                if key in seen_follow:
                    continue
                seen_follow.add(key)
                candidate_cards.append(list(key))
                if len(candidate_cards) >= 160:
                    break
        for cards in casebook_lead_candidate_cards(website_hand, level):
            key = website_action_set_key(cards, level)
            if key not in seen_follow:
                seen_follow.add(key)
                candidate_cards.append(list(key))
    for cards in candidate_cards:
        if not cards:
            continue
        if was_lead:
            infos = engine.recognize(cards, level)
        else:
            if not engine.play_beats(cards, website_last, level):
                continue
            infos = engine.safe_follow_infos(cards, website_last, level)
        for info in infos:
            action_id = website_action_id_for_info(components, cards, info, level)
            if action_id is None:
                continue
            bucket = options.setdefault(action_id, [])
            if len(bucket) < max_combos_per_action:
                local_cards = website_cards_to_local(cards)
                if offline_cards_in_hand(local_cards, local_hand) and local_cards not in bucket:
                    bucket.append(local_cards)
    return {action_id: combos for action_id, combos in options.items() if combos}


def offline_oracle_legal_mask(
    game: Any,
    components: dict,
    player_id: int,
    hand: list[str],
    last_play: list[str] | None,
    level: int,
    max_combos_per_action: int = 8,
) -> dict:
    del player_id
    was_lead = bool(game.is_free_turn or not last_play)
    components["_active_level"] = level
    options = website_compatible_verified_options(
        components,
        hand,
        last_play,
        was_lead,
        max_combos_per_action,
    )
    mask = [0.0 for _ in components["actions"]]
    for action_id, combos in options.items():
        if combos and 0 <= int(action_id) < len(mask):
            mask[int(action_id)] = 1.0
    if not was_lead and not any(mask):
        options = {0: [[]]}
        mask[0] = 1.0
    return {
        "mask": mask,
        "options": options,
        "ids": sorted(int(action_id) for action_id, combos in options.items() if combos),
        "legal_action_count": sum(1 for value in mask if value > 0),
        "source": "website_oracle",
    }


def offline_verified_legal_options(
    game: Any,
    components: dict,
    hand_before: list[str],
    last_play_before: list[str] | None,
    was_lead: bool,
    raw_mask: Any,
    max_combos_per_action: int = 8,
    oracle_options: dict[int, list[list[str]]] | None = None,
) -> dict:
    actions = components["actions"]
    raw_values = [float(value) for value in raw_mask]
    raw_ids = [idx for idx, value in enumerate(raw_values) if value > 0 and 0 <= idx < len(actions)]
    verified_mask = [0.0 for _ in raw_values]
    components["_active_level"] = game.active_level
    verified_options = (
        oracle_options
        if oracle_options is not None
        else website_compatible_verified_options(
            components,
            hand_before,
            last_play_before,
            was_lead,
            max_combos_per_action,
        )
    )
    verified_options = {
        int(action_id): [list(combo) for combo in combos if offline_cards_in_hand(list(combo), hand_before)]
        for action_id, combos in verified_options.items()
    }
    verified_options = {action_id: combos for action_id, combos in verified_options.items() if combos}
    disagree_ids: list[int] = []
    disagree_samples: list[dict] = []
    for action_id, combos in verified_options.items():
        if 0 <= int(action_id) < len(verified_mask) and combos:
            verified_mask[action_id] = 1.0
    verified_id_set = {int(action_id) for action_id in verified_options if 0 <= int(action_id) < len(raw_values)}
    for action_id in raw_ids:
        if action_id in verified_id_set:
            continue
        disagree_ids.append(action_id)
        if len(disagree_samples) < 20:
            action = components["action_by_id"].get(int(action_id), {})
            verified_combo_count = len(verified_options.get(int(action_id), []) or [])
            disagree_samples.append(
                {
                    "action_id": action_id,
                    "action_type": action.get("type"),
                    "is_flush_rocket": action.get("type") == "flush_rocket",
                    "level": game.active_level,
                    "was_lead": was_lead,
                    "last_play": list(last_play_before or []),
                    "raw_mask_allowed": True,
                    "raw_combo_count": 0,
                    "verified_combo_count": verified_combo_count,
                    "local_option_count": verified_combo_count,
                    "oracle_option_count": sum(len(combos or []) for combos in verified_options.values()),
                    "reason": "raw_mask_set_but_no_verified_combo",
                }
            )
    verified_ids = sorted(verified_options)
    return {
        "raw_mask": raw_values,
        "verified_mask": verified_mask,
        "raw_ids": raw_ids,
        "verified_ids": verified_ids,
        "verified_options": verified_options,
        "disagree_ids": disagree_ids,
        "disagree_samples": disagree_samples,
    }


def offline_legal_candidates(
    game: Any,
    components: dict,
    hand_before: list[str],
    last_play_before: list[str] | None,
    was_lead: bool,
    max_combos_per_action: int = 8,
) -> list[tuple[int, list[str]]]:
    oracle = offline_oracle_legal_mask(
        game,
        components,
        int(game.current_player),
        hand_before,
        last_play_before,
        game.active_level,
        max_combos_per_action=max_combos_per_action,
    )
    verified = offline_verified_legal_options(
        game,
        components,
        hand_before,
        last_play_before,
        was_lead,
        oracle["mask"],
        max_combos_per_action=max_combos_per_action,
        oracle_options=oracle["options"],
    )
    candidates: list[tuple[int, list[str]]] = []
    for action_id, combos in verified["verified_options"].items():
        for cards in combos:
            candidates.append((int(action_id), list(cards)))
    return candidates


def offline_oracle_candidates_fast(
    game: Any,
    components: dict,
    hand_before: list[str],
    last_play_before: list[str] | None,
    was_lead: bool,
) -> tuple[dict, list[tuple[int, list[str]]]]:
    oracle = offline_oracle_legal_mask(
        game,
        components,
        int(game.current_player),
        hand_before,
        last_play_before,
        game.active_level,
    )
    candidates: list[tuple[int, list[str]]] = []
    for action_id, combos in (oracle.get("options") or {}).items():
        for cards in combos or []:
            cards_list = list(cards)
            if offline_cards_in_hand(cards_list, hand_before):
                candidates.append((int(action_id), cards_list))
    if not candidates and not was_lead:
        candidates.append((0, []))
        oracle["mask"][0] = 1.0
        oracle["ids"] = sorted(set(list(oracle.get("ids") or []) + [0]))
        oracle["options"] = {**dict(oracle.get("options") or {}), 0: [[]]}
    return oracle, candidates


def offline_select_action_fast(
    game: Any,
    components: dict,
    actor: Any,
    device: Any,
    rng: random.Random,
) -> dict:
    import numpy as np

    player_id = int(game.current_player)
    player = game.players[player_id]
    hand_before = list(player.hand)
    last_play_before = list(game.last_play or [])
    was_lead = bool(game.is_free_turn or not last_play_before)
    state = game._get_obs()
    oracle, candidates = offline_oracle_candidates_fast(game, components, hand_before, last_play_before, was_lead)
    legal_mask = list(oracle["mask"])
    valid_ids = sorted({int(action_id) for action_id, _cards in candidates})
    if not valid_ids:
        return {
            "state": state,
            "legal_mask": legal_mask,
            "raw_legal_mask": legal_mask,
            "old_legal_mask": [0.0 for _ in legal_mask],
            "legal_mask_source": "website_oracle",
            "old_mask_disagree_count": 0,
            "old_mask_disagree_denominator": 0,
            "old_mask_disagree_rate": 0.0,
            "raw_legal_action_count": 0,
            "verified_legal_action_count": 0,
            "mask_combo_disagree_count": 0,
            "mask_combo_disagree_action_ids": [],
            "mask_combo_disagree_samples": [],
            "legal_action_count": 0,
            "mask_issue": "empty_verified_legal_mask",
            "sampled_action_id": None,
            "action_id": 0,
            "chosen_cards": [],
            "physical_cards": [],
            "logical_cards": None,
            "chosen_cards_website": [],
            "hand_subset_checked": True,
            "missing_cards": [],
            "materialization_fail": False,
            "materialization_fail_reason": None,
            "illegal": True,
            "fallback": False,
            "fatal_no_verified_legal": True,
            "illegal_reason": "lead_has_no_verified_legal_action",
            "action_type": "None",
            "action_rank": "0",
            "is_bomb": False,
            "player_id": player_id,
            "team_id": offline_team_id(player_id),
            "was_lead": was_lead,
            "was_follow": not was_lead,
            "hand_before": hand_before,
            "last_play": last_play_before,
        }
    import torch

    with torch.no_grad():
        state_tensor = torch.tensor(np.asarray(state), dtype=torch.float32, device=device).unsqueeze(0)
        mask_tensor = torch.tensor(np.asarray(legal_mask, dtype=np.float32), dtype=torch.float32, device=device).unsqueeze(0)
        probs = actor(state_tensor, mask_tensor).squeeze(0)
        if not torch.isfinite(probs).all() or float(probs.sum().item()) <= 0:
            sampled_action_id = int(rng.choice(valid_ids))
        else:
            sampled_action_id = int(torch.multinomial(probs, 1).item())
    options = {
        int(action_id): [list(cards) for cards in combos or [] if offline_cards_in_hand(list(cards), hand_before)]
        for action_id, combos in (oracle.get("options") or {}).items()
    }
    physical_options = options.get(int(sampled_action_id), [])
    materialization_fail = False
    materialization_fail_reason = None
    fallback = False
    illegal = False
    illegal_reason = None
    action_id = int(sampled_action_id)
    if len(legal_mask) != OFFLINE_ACTION_DIM:
        physical_options = []
        illegal = True
        illegal_reason = "legal_mask_dim_mismatch"
    elif not 0 <= action_id < OFFLINE_ACTION_DIM:
        physical_options = []
        illegal = True
        illegal_reason = "action_id_out_of_range"
    elif float(legal_mask[action_id]) <= 0:
        physical_options = []
        illegal = True
        illegal_reason = "action_id_not_in_legal_mask"
    if physical_options:
        chosen_cards = list(rng.choice(physical_options))
    else:
        chosen_cards = []
        materialization_fail = True
        materialization_fail_reason = illegal_reason or "no_physical_cards_for_action_id"
        illegal = True
        fallback = True
        if candidates:
            action_id, chosen_cards = rng.choice(candidates)
            chosen_cards = list(chosen_cards)
    missing_cards = offline_missing_cards(chosen_cards, hand_before)
    if missing_cards:
        materialization_fail = True
        materialization_fail_reason = materialization_fail_reason or "chosen_cards_not_in_hand"
        illegal = True
    elif not materialization_fail:
        illegal = False
        illegal_reason = None
    action_struct = components["action_by_id"].get(int(action_id))
    if action_id == 0:
        action_struct = {"type": "None", "points": [], "logic_point": 0, "id": 0}
    return {
        "state": state,
        "legal_mask": legal_mask,
        "raw_legal_mask": legal_mask,
        "old_legal_mask": [0.0 for _ in legal_mask],
        "legal_mask_source": "website_oracle",
        "old_mask_disagree_count": 0,
        "old_mask_disagree_denominator": 0,
        "old_mask_disagree_rate": 0.0,
        "raw_legal_action_count": len(valid_ids),
        "verified_legal_action_count": len(valid_ids),
        "mask_combo_disagree_count": 0,
        "mask_combo_disagree_action_ids": [],
        "mask_combo_disagree_samples": [],
        "legal_action_count": len(valid_ids),
        "mask_issue": None,
        "sampled_action_id": sampled_action_id,
        "action_id": int(action_id),
        "chosen_cards": chosen_cards,
        "physical_cards": chosen_cards,
        "logical_cards": None,
        "chosen_cards_website": local_cards_to_website(chosen_cards) if chosen_cards else [],
        "hand_subset_checked": True,
        "missing_cards": missing_cards,
        "materialization_fail": bool(materialization_fail),
        "materialization_fail_reason": materialization_fail_reason,
        "illegal": bool(illegal),
        "fallback": bool(fallback),
        "fatal_no_verified_legal": False,
        "illegal_reason": illegal_reason,
        "action_type": str((action_struct or {}).get("type") or "unknown"),
        "action_rank": offline_action_rank_label(action_struct),
        "is_bomb": offline_action_is_bomb(action_struct),
        "player_id": player_id,
        "team_id": offline_team_id(player_id),
        "was_lead": was_lead,
        "was_follow": not was_lead,
        "hand_before": hand_before,
        "last_play": last_play_before,
    }


def offline_select_action(
    game: Any,
    components: dict,
    actor: Any = None,
    device: Any = None,
    rng: random.Random | None = None,
) -> dict:
    rng = rng or random.Random()
    actions = components["actions"]
    player_id = int(game.current_player)
    player = game.players[player_id]
    hand_before = list(player.hand)
    last_play_before = list(game.last_play or [])
    was_lead = bool(game.is_free_turn or not last_play_before)
    state = game._get_obs()
    last_action_arg = [] if was_lead else last_play_before
    old_legal_mask = game.get_valid_action_mask(hand_before, actions, game.active_level, last_action_arg)
    oracle = offline_oracle_legal_mask(
        game,
        components,
        player_id,
        hand_before,
        last_play_before,
        game.active_level,
    )
    raw_legal_mask = oracle["mask"]
    verified = offline_verified_legal_options(
        game,
        components,
        hand_before,
        last_play_before,
        was_lead,
        raw_legal_mask,
        oracle_options=oracle["options"],
    )
    old_ids = {idx for idx, value in enumerate(old_legal_mask) if float(value) > 0 and 0 <= idx < len(actions)}
    oracle_ids = set(oracle["ids"])
    old_mask_disagree_ids = sorted(old_ids.symmetric_difference(oracle_ids))
    old_mask_disagree_denominator = len(old_ids.union(oracle_ids))
    legal_mask = verified["verified_mask"]
    valid_ids = list(verified["verified_ids"])
    mask_issue = None
    if not valid_ids:
        mask_issue = "empty_verified_legal_mask"
        if not was_lead and len(legal_mask) > 0:
            valid_ids = [0]
            legal_mask[0] = 1.0
            verified["verified_options"] = {0: [[]]}
        else:
            return {
                "state": state,
                "legal_mask": legal_mask,
                "raw_legal_mask": raw_legal_mask.tolist() if hasattr(raw_legal_mask, "tolist") else list(raw_legal_mask),
                "old_legal_mask": old_legal_mask.tolist() if hasattr(old_legal_mask, "tolist") else list(old_legal_mask),
                "legal_mask_source": "website_oracle",
                "old_mask_disagree_count": len(old_mask_disagree_ids),
                "old_mask_disagree_denominator": old_mask_disagree_denominator,
                "old_mask_disagree_rate": len(old_mask_disagree_ids) / max(1, old_mask_disagree_denominator),
                "raw_legal_action_count": len(verified["raw_ids"]),
                "verified_legal_action_count": 0,
                "mask_combo_disagree_count": len(verified["disagree_ids"]),
                "mask_combo_disagree_action_ids": list(verified["disagree_ids"]),
                "mask_combo_disagree_samples": list(verified["disagree_samples"]),
                "legal_action_count": 0,
                "mask_issue": mask_issue,
                "sampled_action_id": None,
                "action_id": 0,
                "chosen_cards": [],
                "illegal": True,
                "fallback": False,
                "fatal_no_verified_legal": True,
                "illegal_reason": "lead_has_no_verified_legal_action",
                "action_type": "None",
                "action_rank": "0",
                "is_bomb": False,
                "player_id": player_id,
                "team_id": offline_team_id(player_id),
                "was_lead": was_lead,
                "was_follow": not was_lead,
                "hand_before": hand_before,
                "last_play": last_play_before,
            }
    sampled_action_id = None
    if actor is not None and valid_ids:
        import numpy as np

        if hasattr(actor, "predict_probs"):
            probs_arr = np.asarray(actor.predict_probs(state, legal_mask), dtype=np.float64)
            probs_arr = probs_arr / max(1e-12, float(probs_arr.sum()))
            sampled_action_id = int(rng.choices(range(len(probs_arr)), weights=probs_arr, k=1)[0])
        else:
            import torch

            with torch.no_grad():
                state_tensor = torch.tensor(np.asarray(state), dtype=torch.float32, device=device).unsqueeze(0)
                mask_tensor = torch.tensor(legal_mask, dtype=torch.float32, device=device).unsqueeze(0)
                probs = actor(state_tensor, mask_tensor).squeeze(0)
                if torch.isfinite(probs).all() and float(probs.sum().item()) > 0:
                    sampled_action_id = int(torch.multinomial(probs, 1).item())
    if sampled_action_id is None:
        sampled_action_id = int(rng.choice(valid_ids)) if valid_ids else 0
    verified_options = verified["verified_options"]
    materialization_fail = False
    materialization_fail_reason = None
    if (
        len(legal_mask) == OFFLINE_ACTION_DIM
        and 0 <= int(sampled_action_id) < OFFLINE_ACTION_DIM
        and float(legal_mask[int(sampled_action_id)]) > 0
        and sampled_action_id in verified_options
        and verified_options[sampled_action_id]
    ):
        physical_options = [
            list(cards) for cards in verified_options[sampled_action_id] if offline_cards_in_hand(list(cards), hand_before)
        ]
        if physical_options:
            chosen_cards = list(rng.choice(physical_options))
            illegal_reason = None
        else:
            chosen_cards = None
            illegal_reason = "no_physical_cards_for_action_id"
            materialization_fail = True
            materialization_fail_reason = illegal_reason
    else:
        chosen_cards = None
        if len(legal_mask) != OFFLINE_ACTION_DIM:
            illegal_reason = "legal_mask_dim_mismatch"
        elif not 0 <= int(sampled_action_id) < OFFLINE_ACTION_DIM:
            illegal_reason = "action_id_out_of_range"
        elif float(legal_mask[int(sampled_action_id)]) <= 0:
            illegal_reason = "action_id_not_in_legal_mask"
        else:
            illegal_reason = "no_verified_option_for_action_id"
        materialization_fail = True
        materialization_fail_reason = illegal_reason
    illegal = chosen_cards is None
    fallback = False
    action_id = sampled_action_id
    if illegal:
        fallback = True
        candidates = offline_legal_candidates(game, components, hand_before, last_play_before, was_lead)
        if candidates:
            action_id, chosen_cards = rng.choice(candidates)
            illegal_reason = materialization_fail_reason
        elif not was_lead:
            action_id, chosen_cards = (0, [])
            illegal_reason = illegal_reason or "fallback_pass"
        else:
            action_id, chosen_cards = (0, [])
            illegal_reason = illegal_reason or "no_fallback_candidate"
    chosen_cards = list(chosen_cards or [])
    hand_subset_checked = True
    missing_cards = offline_missing_cards(chosen_cards, hand_before)
    if missing_cards:
        materialization_fail = True
        materialization_fail_reason = materialization_fail_reason or "chosen_cards_not_in_hand"
        fallback = True
        candidates = offline_legal_candidates(game, components, hand_before, last_play_before, was_lead)
        if candidates:
            action_id, chosen_cards = rng.choice(candidates)
            chosen_cards = list(chosen_cards)
            missing_cards = offline_missing_cards(chosen_cards, hand_before)
            illegal_reason = materialization_fail_reason
        elif not was_lead:
            action_id, chosen_cards = (0, [])
            missing_cards = []
            illegal_reason = materialization_fail_reason
        else:
            action_id, chosen_cards = (0, [])
            illegal_reason = materialization_fail_reason
    if not missing_cards:
        illegal = False
        illegal_reason = None
    action_struct = components["action_by_id"].get(int(action_id))
    if action_id == 0:
        action_struct = {"type": "None", "points": [], "logic_point": 0, "id": 0}
    return {
        "state": state,
        "legal_mask": legal_mask.tolist() if hasattr(legal_mask, "tolist") else list(legal_mask),
        "raw_legal_mask": raw_legal_mask.tolist() if hasattr(raw_legal_mask, "tolist") else list(raw_legal_mask),
        "old_legal_mask": old_legal_mask.tolist() if hasattr(old_legal_mask, "tolist") else list(old_legal_mask),
        "legal_mask_source": "website_oracle",
        "old_mask_disagree_count": len(old_mask_disagree_ids),
        "old_mask_disagree_denominator": old_mask_disagree_denominator,
        "old_mask_disagree_rate": len(old_mask_disagree_ids) / max(1, old_mask_disagree_denominator),
        "raw_legal_action_count": len(verified["raw_ids"]),
        "verified_legal_action_count": len(valid_ids),
        "mask_combo_disagree_count": len(verified["disagree_ids"]),
        "mask_combo_disagree_action_ids": list(verified["disagree_ids"]),
        "mask_combo_disagree_samples": list(verified["disagree_samples"]),
        "legal_action_count": len(valid_ids),
        "mask_issue": mask_issue,
        "sampled_action_id": sampled_action_id,
        "action_id": int(action_id),
        "chosen_cards": chosen_cards,
        "physical_cards": chosen_cards,
        "logical_cards": None,
        "chosen_cards_website": local_cards_to_website(chosen_cards) if chosen_cards else [],
        "hand_subset_checked": hand_subset_checked,
        "missing_cards": missing_cards,
        "materialization_fail": bool(materialization_fail),
        "materialization_fail_reason": materialization_fail_reason,
        "illegal": bool(illegal),
        "fallback": bool(fallback),
        "fatal_no_verified_legal": False,
        "illegal_reason": illegal_reason,
        "action_type": str((action_struct or {}).get("type") or "unknown"),
        "action_rank": offline_action_rank_label(action_struct),
        "is_bomb": offline_action_is_bomb(action_struct),
        "player_id": player_id,
        "team_id": offline_team_id(player_id),
        "was_lead": was_lead,
        "was_follow": not was_lead,
        "hand_before": hand_before,
        "last_play": last_play_before,
    }


def offline_apply_action(game: Any, action_info: dict) -> dict:
    player_id = int(game.current_player)
    player = game.players[player_id]
    hand_before = list(player.hand)
    chosen_cards = list(action_info.get("chosen_cards") or [])
    missing_cards = offline_missing_cards(chosen_cards, hand_before)
    hand_card_mismatch = bool(missing_cards)
    if hand_card_mismatch:
        action_info["hand_card_mismatch"] = True
        action_info["missing_cards"] = missing_cards
        action_info["materialization_fail"] = True
        action_info["materialization_fail_reason"] = action_info.get("materialization_fail_reason") or "apply_missing_cards"
        chosen_cards = []
        action_info["chosen_cards"] = []
        action_info["physical_cards"] = []
        action_info["chosen_cards_website"] = []
    else:
        action_info["hand_card_mismatch"] = False
        action_info.setdefault("missing_cards", [])
    if chosen_cards:
        game.last_play = chosen_cards
        game.last_player = player_id
        for card in chosen_cards:
            player.played_cards.append(card)
            player.hand.remove(card)
        game.recent_actions[player_id] = list(chosen_cards)
        game.jiefeng = False
        if not player.hand and player_id not in game.ranking:
            game.ranking.append(player_id)
            if len(game.ranking) <= 2:
                game.jiefeng = True
        game.pass_count = 0
        if not player.hand:
            game.pass_count -= 1
        if game.is_free_turn:
            game.is_free_turn = False
    else:
        game.pass_count += 1
        game.recent_actions[player_id] = ["Pass"]
    player.last_played_cards = list(game.recent_actions[player_id])
    game.current_player = (player_id + 1) % 4
    if game.current_player == 0:
        game.history.append([list(game.recent_actions[i]) for i in range(4)])
        game.recent_actions = [["None"], ["None"], ["None"], ["None"]]
    game.check_game_over()
    hand_after = list(player.hand)
    record = {
        **action_info,
        "player_id": player_id,
        "team_id": offline_team_id(player_id),
        "hand_before": hand_before,
        "hand_after": hand_after,
        "hand_card_mismatch": hand_card_mismatch,
        "missing_cards": missing_cards,
        "my_remaining_before": len(hand_before),
        "my_remaining_after": len(hand_after),
        "reward": 0.0,
    }
    return record


def offline_deck_integrity(game: Any) -> dict:
    all_cards: list[str] = []
    for player in game.players:
        all_cards.extend(player.hand)
        all_cards.extend(player.played_cards)
    counts = Counter(all_cards)
    over_count = {card: count for card, count in counts.items() if count > 2}
    return {
        "total_cards_seen": len(all_cards),
        "unique_card_names": len(counts),
        "over_duplicate_cards": over_count,
        "total_is_108": len(all_cards) == 108,
        "no_card_count_over_2": not over_count,
    }


def run_offline_env_sanity_check(args: argparse.Namespace) -> None:
    import numpy as np

    device_info = offline_resolve_device(args.device)
    components = offline_load_guandan_components()
    GuandanGame = components["GuandanGame"]
    rng = random.Random(20260703)
    summary = {
        "backend": device_info["backend"],
        "requested_device": device_info["requested_device"],
        "actual_device": device_info["actual_device"],
        "device_fallback": device_info["device_fallback"],
        "torch_available": device_info["torch_available"],
        "cuda_available": device_info["cuda_available"],
        "legal_mask_source": "website_oracle",
        "sanity_games": args.sanity_games,
        "completed_games": 0,
        "raw_legal_action_count": 0,
        "verified_legal_action_count": 0,
        "mask_combo_disagree_count": 0,
        "mask_combo_disagree_action_ids": [],
        "mask_combo_disagree_samples": [],
        "old_mask_disagree_count": 0,
        "old_mask_disagree_denominator": 0,
        "old_mask_disagree_rate": 0.0,
        "initial_27_each_player_failures": 0,
        "total_cards_108_failures": 0,
        "duplicate_or_lost_card_failures": 0,
        "empty_legal_mask_count": 0,
        "action_id_out_of_range_count": 0,
        "chosen_cards_not_in_hand_count": 0,
        "follow_cannot_beat_count": 0,
        "obs_dim_3049_failures": 0,
        "nan_count": 0,
        "illegal_action_count": 0,
        "fallback_count": 0,
        "heart_level_action_filter_known_issue": True,
        "fix_heart_level_action_filter_enabled": bool(args.fix_heart_level_action_filter),
        "heart_level_mixed_action_count": 0,
        "concrete_issue_samples": [],
        "game_summaries": [],
    }
    disagree_action_ids: set[int] = set()
    for game_index in range(int(args.sanity_games)):
        game = GuandanGame(verbose=False, print_history=False)
        initial_counts = [len(player.hand) for player in game.players]
        if initial_counts != [27, 27, 27, 27]:
            summary["initial_27_each_player_failures"] += 1
        integrity = offline_deck_integrity(game)
        if not integrity["total_is_108"]:
            summary["total_cards_108_failures"] += 1
        if not integrity["no_card_count_over_2"]:
            summary["duplicate_or_lost_card_failures"] += 1
        steps = 0
        while not game.is_game_over and steps < OFFLINE_MAX_GAME_STEPS:
            offline_prepare_turn(game)
            if game.current_player in game.ranking:
                steps += 1
                continue
            state = game._get_obs()
            if len(state) != OFFLINE_STATE_DIM:
                summary["obs_dim_3049_failures"] += 1
            if not np.isfinite(state).all():
                summary["nan_count"] += 1
            action_info = offline_select_action(game, components, actor=None, rng=rng)
            summary["raw_legal_action_count"] += int(action_info.get("raw_legal_action_count") or 0)
            summary["verified_legal_action_count"] += int(action_info.get("verified_legal_action_count") or 0)
            summary["mask_combo_disagree_count"] += int(action_info.get("mask_combo_disagree_count") or 0)
            summary["old_mask_disagree_count"] += int(action_info.get("old_mask_disagree_count") or 0)
            summary["old_mask_disagree_denominator"] += int(action_info.get("old_mask_disagree_denominator") or 0)
            disagree_action_ids.update(int(action_id) for action_id in action_info.get("mask_combo_disagree_action_ids") or [])
            for sample in action_info.get("mask_combo_disagree_samples") or []:
                if len(summary["mask_combo_disagree_samples"]) < 20:
                    summary["mask_combo_disagree_samples"].append(sample)
            if action_info.get("fatal_no_verified_legal"):
                if len(summary["concrete_issue_samples"]) < 10:
                    summary["concrete_issue_samples"].append(
                        {
                            "game_index": game_index,
                            "step": steps,
                            "issue": action_info.get("illegal_reason"),
                            "player_id": action_info["player_id"],
                            "raw_legal_action_count": action_info.get("raw_legal_action_count"),
                            "verified_legal_action_count": action_info.get("verified_legal_action_count"),
                        }
                    )
                summary["mask_combo_disagree_action_ids"] = sorted(disagree_action_ids)
                save_json(Path(args.sanity_out), summary)
                raise RuntimeError("lead turn has no verified legal action; see sanity output")
            if action_info.get("mask_issue") in {"empty_legal_mask", "empty_verified_legal_mask"}:
                summary["empty_legal_mask_count"] += 1
            if not 0 <= int(action_info["action_id"]) < OFFLINE_ACTION_DIM:
                summary["action_id_out_of_range_count"] += 1
            if action_info["illegal"]:
                summary["illegal_action_count"] += 1
            if action_info["fallback"]:
                summary["fallback_count"] += 1
            if action_info["chosen_cards"] and not offline_cards_in_hand(action_info["chosen_cards"], action_info["hand_before"]):
                summary["chosen_cards_not_in_hand_count"] += 1
            ok, reason = offline_action_is_legal(
                game,
                components["actions"],
                action_info["chosen_cards"],
                action_info["hand_before"],
                action_info["last_play"],
                action_info["was_lead"],
            )
            if not ok and reason == "cannot_beat_last_play":
                summary["follow_cannot_beat_count"] += 1
            if offline_heart_level_mix_issue(action_info["chosen_cards"], game.active_level):
                summary["heart_level_mixed_action_count"] += 1
                if len(summary["concrete_issue_samples"]) < 10:
                    summary["concrete_issue_samples"].append(
                        {
                            "game_index": game_index,
                            "step": steps,
                            "issue": "heart_and_non_heart_level_cards_share_logic_point_15",
                            "level": game.active_level,
                            "chosen_cards": action_info["chosen_cards"],
                            "action_id": action_info["action_id"],
                        }
                    )
            if (not ok or action_info["illegal"] or action_info["fallback"]) and len(summary["concrete_issue_samples"]) < 10:
                summary["concrete_issue_samples"].append(
                    {
                        "game_index": game_index,
                        "step": steps,
                        "issue": reason or action_info.get("illegal_reason") or "fallback",
                        "player_id": action_info["player_id"],
                        "action_id": action_info["action_id"],
                        "chosen_cards": action_info["chosen_cards"],
                        "last_play": action_info["last_play"],
                    }
                )
            offline_apply_action(game, action_info)
            steps += 1
        if game.is_game_over:
            summary["completed_games"] += 1
        final_integrity = offline_deck_integrity(game)
        if not final_integrity["total_is_108"] or not final_integrity["no_card_count_over_2"]:
            summary["duplicate_or_lost_card_failures"] += 1
        summary["game_summaries"].append(
            {
                "game_index": game_index,
                "completed": bool(game.is_game_over),
                "steps": steps,
                "ranking": list(game.ranking),
                "winning_team": int(game.winning_team),
                "integrity": final_integrity,
            }
        )
    summary["passed"] = (
        summary["completed_games"] == int(args.sanity_games)
        and summary["initial_27_each_player_failures"] == 0
        and summary["total_cards_108_failures"] == 0
        and summary["duplicate_or_lost_card_failures"] == 0
        and summary["empty_legal_mask_count"] == 0
        and summary["action_id_out_of_range_count"] == 0
        and summary["chosen_cards_not_in_hand_count"] == 0
        and summary["follow_cannot_beat_count"] == 0
        and summary["obs_dim_3049_failures"] == 0
        and summary["nan_count"] == 0
    )
    summary["mask_combo_disagree_action_ids"] = sorted(disagree_action_ids)
    summary["old_mask_disagree_rate"] = summary["old_mask_disagree_count"] / max(
        1,
        summary["old_mask_disagree_denominator"],
    )
    save_json(Path(args.sanity_out), summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    if not summary["passed"]:
        raise RuntimeError(f"offline env sanity check failed; see {args.sanity_out}")


class OfflineNumpyActor:
    def __init__(self, action_dim: int, seed: int = 20260703) -> None:
        import numpy as np

        rng = np.random.default_rng(seed)
        self.weights = rng.normal(0.0, 0.01, size=(OFFLINE_STATE_DIM, action_dim)).astype("float32")
        self.bias = np.zeros(action_dim, dtype="float32")

    def predict_probs(self, state: Any, mask: Any) -> Any:
        import numpy as np

        state_arr = np.asarray(state, dtype=np.float32)
        mask_arr = np.asarray(mask, dtype=np.float32)
        logits = state_arr @ self.weights + self.bias
        logits = np.where(mask_arr > 0, logits, -1e9)
        logits = logits - np.max(logits)
        exp_logits = np.exp(logits)
        denom = float(np.sum(exp_logits))
        if not np.isfinite(denom) or denom <= 0:
            probs = mask_arr / max(1.0, float(np.sum(mask_arr)))
            return probs.astype("float32")
        return (exp_logits / denom).astype("float32")

    def save(self, path: Path) -> None:
        import numpy as np

        np.savez_compressed(path, weights=self.weights, bias=self.bias)


class OfflineNumpyCritic:
    def __init__(self, seed: int = 20260704) -> None:
        import numpy as np

        rng = np.random.default_rng(seed)
        self.weights = rng.normal(0.0, 0.01, size=(OFFLINE_STATE_DIM,)).astype("float32")
        self.bias = np.float32(0.0)

    def values(self, states: Any) -> Any:
        import numpy as np

        states_arr = np.asarray(states, dtype=np.float32)
        return states_arr @ self.weights + self.bias

    def save(self, path: Path) -> None:
        import numpy as np

        np.savez_compressed(path, weights=self.weights, bias=self.bias)


def offline_build_models(action_dim: int, device: Any) -> tuple[Any, Any, Any, Any]:
    import torch
    import torch.nn as nn
    import torch.nn.functional as F
    import torch.optim as optim

    class OfflineActorNet(nn.Module):
        def __init__(self, state_dim: int = OFFLINE_STATE_DIM, hidden_dim: int = 512) -> None:
            super().__init__()
            self.net = nn.Sequential(
                nn.Linear(state_dim, hidden_dim),
                nn.ReLU(),
                nn.Linear(hidden_dim, hidden_dim),
                nn.ReLU(),
                nn.Linear(hidden_dim, action_dim),
            )

        def forward(self, x: Any, mask: Any = None) -> Any:
            logits = self.net(x)
            if mask is not None:
                logits = logits + (mask - 1) * 1e9
            return F.softmax(logits, dim=-1)

    class OfflineCriticNet(nn.Module):
        def __init__(self, state_dim: int = OFFLINE_STATE_DIM, hidden_dim: int = 256) -> None:
            super().__init__()
            self.net = nn.Sequential(
                nn.Linear(state_dim, hidden_dim),
                nn.ReLU(),
                nn.Linear(hidden_dim, hidden_dim),
                nn.ReLU(),
                nn.Linear(hidden_dim, 1),
            )

        def forward(self, x: Any) -> Any:
            return self.net(x)

    actor = OfflineActorNet().to(device)
    critic = OfflineCriticNet().to(device)
    actor_optimizer = optim.Adam(actor.parameters(), lr=1e-4)
    critic_optimizer = optim.Adam(critic.parameters(), lr=1e-4)
    return actor, critic, actor_optimizer, critic_optimizer


def offline_train_on_memory(batch: list[dict], actor: Any, critic: Any, actor_optimizer: Any, critic_optimizer: Any, device: Any) -> tuple[float, float]:
    import numpy as np

    if not batch:
        return 0.0, 0.0
    if hasattr(actor, "predict_probs"):
        states = np.asarray([item["state"] for item in batch], dtype=np.float32)
        masks = np.asarray([item["legal_mask"] for item in batch], dtype=np.float32)
        actions = np.asarray([int(item["action_id"]) for item in batch], dtype=np.int64)
        rewards = np.asarray([float(item["reward"]) for item in batch], dtype=np.float32)
        values = critic.values(states).astype(np.float32)
        advantages = rewards - values
        critic_loss = float(np.mean(np.square(advantages)))
        critic_lr = 1e-4
        critic.weights += critic_lr * (states.T @ advantages) / max(1, len(batch))
        critic.bias = np.float32(critic.bias + critic_lr * float(np.mean(advantages)))
        grad_logits = np.zeros((len(batch), actor.weights.shape[1]), dtype=np.float32)
        actor_loss_terms = []
        for idx, (state, mask, action_id, advantage) in enumerate(zip(states, masks, actions, advantages)):
            probs = actor.predict_probs(state, mask)
            actor_loss_terms.append(float(-np.log(max(1e-8, float(probs[action_id]))) * float(advantage)))
            grad_logits[idx] = probs
            grad_logits[idx, action_id] -= 1.0
            grad_logits[idx] *= float(advantage)
            grad_logits[idx] *= mask
        actor_lr = 1e-4
        actor.weights -= actor_lr * (states.T @ grad_logits) / max(1, len(batch))
        actor.bias -= actor_lr * np.mean(grad_logits, axis=0)
        return float(np.mean(actor_loss_terms)), critic_loss

    import torch
    import torch.nn.functional as F

    states = torch.tensor(np.asarray([item["state"] for item in batch]), dtype=torch.float32, device=device)
    masks = torch.tensor(np.asarray([item["legal_mask"] for item in batch]), dtype=torch.float32, device=device)
    actions = torch.tensor([int(item["action_id"]) for item in batch], dtype=torch.long, device=device)
    rewards = torch.tensor([float(item["reward"]) for item in batch], dtype=torch.float32, device=device)
    values = critic(states).squeeze(-1)
    critic_loss = F.mse_loss(values, rewards)
    probs = actor(states, masks)
    log_probs = torch.log(probs.clamp_min(1e-8))
    chosen_log_probs = log_probs[torch.arange(len(batch), device=device), actions]
    advantages = rewards - values.detach()
    actor_loss = -(chosen_log_probs * advantages).mean()
    actor_optimizer.zero_grad()
    actor_loss.backward()
    actor_optimizer.step()
    critic_optimizer.zero_grad()
    critic_loss.backward()
    critic_optimizer.step()
    return float(actor_loss.item()), float(critic_loss.item())


def offline_oracle_sample_action_info(
    game: Any,
    components: dict,
    rng: random.Random,
    policy: str,
) -> dict:
    player_id = int(game.current_player)
    hand_before = list(game.players[player_id].hand)
    last_play_before = list(game.last_play or [])
    was_lead = bool(game.is_free_turn or not last_play_before)
    _oracle, candidates = offline_oracle_candidates_fast(game, components, hand_before, last_play_before, was_lead)
    if not candidates:
        return offline_make_action_info_from_cards(
            game,
            components,
            [] if not was_lead else [],
            rng,
            policy=policy,
            fallback=not was_lead,
            fallback_reason="no_oracle_candidate",
        )
    action_id, cards = rng.choice(candidates)
    return offline_make_action_info_from_cards(
        game,
        components,
        list(cards),
        rng,
        policy=policy,
        sampled_action_id=action_id,
    )


def offline_greedy_action_info(game: Any, components: dict, rng: random.Random) -> dict:
    player_id = int(game.current_player)
    hand_before = list(game.players[player_id].hand)
    last_play_before = list(game.last_play or [])
    was_lead = bool(game.is_free_turn or not last_play_before)
    _oracle, candidates = offline_oracle_candidates_fast(game, components, hand_before, last_play_before, was_lead)
    if not candidates:
        return offline_oracle_sample_action_info(game, components, rng, policy="greedy_bot")
    scored: list[tuple[float, int, list[str]]] = []
    for action_id, cards in candidates:
        action = components["action_by_id"].get(int(action_id), {})
        is_pass = not bool(cards)
        score = float(len(cards) * 100)
        if offline_action_is_bomb(action):
            score += 15.0
        if not was_lead and is_pass:
            score -= 1000.0
        if was_lead and is_pass:
            score -= 10000.0
        score += float(action.get("logic_point") or 0) / 100.0
        scored.append((score, int(action_id), list(cards)))
    best_score = max(score for score, _action_id, _cards in scored)
    best = [(action_id, cards) for score, action_id, cards in scored if score == best_score]
    action_id, cards = rng.choice(best)
    return offline_make_action_info_from_cards(
        game,
        components,
        list(cards),
        rng,
        policy="greedy_bot",
        sampled_action_id=action_id,
    )


def offline_opponent_pool_profile(rng: random.Random) -> str:
    return str(rng.choices(["random_bot", "greedy_bot", "tempo_baseline"], weights=[20, 30, 50], k=1)[0])


def offline_opponent_action_info(
    game: Any,
    components: dict,
    opponent_profile: str,
    profile_config: dict,
    rng: random.Random,
) -> dict:
    if opponent_profile == "random_bot":
        return offline_oracle_sample_action_info(game, components, rng, policy="random_bot")
    if opponent_profile == "greedy_bot":
        return offline_greedy_action_info(game, components, rng)
    return offline_baseline_action_info(game, components, "tempo_baseline", profile_config, rng)


def offline_ppo_log_prob_value(
    actor: Any,
    critic: Any,
    state: Any,
    legal_mask: list[float],
    action_id: int,
    device: Any,
) -> tuple[float, float]:
    import numpy as np
    import torch

    if len(legal_mask) != OFFLINE_ACTION_DIM:
        raise RuntimeError(f"legal_mask dim mismatch: {len(legal_mask)}")
    if not 0 <= int(action_id) < OFFLINE_ACTION_DIM:
        raise RuntimeError(f"action_id out of range: {action_id}")
    if float(legal_mask[int(action_id)]) <= 0:
        raise RuntimeError(f"action_id not in legal_mask: {action_id}")
    with torch.no_grad():
        states = torch.tensor(np.asarray(state, dtype=np.float32), dtype=torch.float32, device=device).unsqueeze(0)
        masks = torch.tensor(np.asarray(legal_mask, dtype=np.float32), dtype=torch.float32, device=device).unsqueeze(0)
        logits = actor.net(states)
        if logits.shape[-1] != OFFLINE_ACTION_DIM:
            raise RuntimeError(f"actor output dim mismatch: {logits.shape[-1]}")
        masked_logits = logits.masked_fill(masks <= 0, -1e9)
        dist = torch.distributions.Categorical(logits=masked_logits)
        action_tensor = torch.tensor([int(action_id)], dtype=torch.long, device=device)
        log_prob = float(dist.log_prob(action_tensor).item())
        value = float(critic(states).squeeze(-1).item())
    return log_prob, value


def offline_ppo_assign_advantages(
    player_memory: dict[int, list[dict]],
    final_reward: float,
    gamma: float,
    gae_lambda: float,
) -> list[dict]:
    transitions: list[dict] = []
    for items in player_memory.values():
        next_value = 0.0
        next_advantage = 0.0
        for item in reversed(items):
            reward = float(final_reward) + float(item.get("step_reward", 0.0))
            value = float(item["value"])
            delta = reward + gamma * next_value - value
            advantage = delta + gamma * gae_lambda * next_advantage
            item["reward"] = reward
            item["advantage"] = advantage
            item["return"] = advantage + value
            next_value = value
            next_advantage = advantage
        transitions.extend(items)
    return transitions


def offline_ppo_update(
    actor: Any,
    critic: Any,
    optimizer: Any,
    transitions: list[dict],
    args: argparse.Namespace,
    device: Any,
    init_actor: Any = None,
) -> dict:
    import numpy as np
    import torch
    import torch.nn.functional as F

    if not transitions:
        return {
            "policy_loss": 0.0,
            "value_loss": 0.0,
            "entropy": 0.0,
            "approx_kl": 0.0,
            "clip_fraction": 0.0,
            "init_policy_kl": 0.0,
            "early_stop_kl_triggered": False,
        }
    states = torch.tensor(
        np.asarray([item["state"] for item in transitions], dtype=np.float32),
        dtype=torch.float32,
        device=device,
    )
    masks = torch.tensor(
        np.asarray([item["legal_mask"] for item in transitions], dtype=np.float32),
        dtype=torch.float32,
        device=device,
    )
    actions = torch.tensor([int(item["action_id"]) for item in transitions], dtype=torch.long, device=device)
    old_log_probs = torch.tensor([float(item["old_log_prob"]) for item in transitions], dtype=torch.float32, device=device)
    returns = torch.tensor([float(item["return"]) for item in transitions], dtype=torch.float32, device=device)
    advantages = torch.tensor([float(item["advantage"]) for item in transitions], dtype=torch.float32, device=device)
    if len(transitions) > 1:
        advantages = (advantages - advantages.mean()) / advantages.std(unbiased=False).clamp_min(1e-8)
    indices = list(range(len(transitions)))
    rng = random.Random(20260705 + len(transitions))
    metrics = {
        "policy_loss": [],
        "value_loss": [],
        "entropy": [],
        "approx_kl": [],
        "clip_fraction": [],
        "init_policy_kl": [],
    }
    early_stop_kl_triggered = False
    for _epoch in range(int(args.ppo_update_epochs)):
        rng.shuffle(indices)
        for start in range(0, len(indices), int(args.ppo_batch_size)):
            batch = indices[start : start + int(args.ppo_batch_size)]
            batch_tensor = torch.tensor(batch, dtype=torch.long, device=device)
            batch_states = states.index_select(0, batch_tensor)
            batch_masks = masks.index_select(0, batch_tensor)
            batch_actions = actions.index_select(0, batch_tensor)
            batch_old_log_probs = old_log_probs.index_select(0, batch_tensor)
            batch_returns = returns.index_select(0, batch_tensor)
            batch_advantages = advantages.index_select(0, batch_tensor)
            logits = actor.net(batch_states)
            if logits.shape[-1] != OFFLINE_ACTION_DIM:
                raise RuntimeError(f"actor output dim mismatch: {logits.shape[-1]}")
            masked_logits = logits.masked_fill(batch_masks <= 0, -1e9)
            dist = torch.distributions.Categorical(logits=masked_logits)
            new_log_probs = dist.log_prob(batch_actions)
            entropy = dist.entropy().mean()
            ratio = torch.exp(new_log_probs - batch_old_log_probs)
            unclipped = ratio * batch_advantages
            clipped = torch.clamp(ratio, 1.0 - float(args.ppo_clip), 1.0 + float(args.ppo_clip)) * batch_advantages
            policy_loss = -torch.min(unclipped, clipped).mean()
            values = critic(batch_states).squeeze(-1)
            value_loss = F.mse_loss(values, batch_returns)
            init_policy_kl = torch.tensor(0.0, dtype=torch.float32, device=device)
            if bool(getattr(args, "ppo_safe_mode", False)) and init_actor is not None:
                with torch.no_grad():
                    init_logits = init_actor.net(batch_states)
                    if init_logits.shape[-1] != OFFLINE_ACTION_DIM:
                        raise RuntimeError(f"init actor output dim mismatch: {init_logits.shape[-1]}")
                    init_masked_logits = init_logits.masked_fill(batch_masks <= 0, -1e9)
                    init_log_probs = torch.log_softmax(init_masked_logits, dim=-1)
                current_log_probs = torch.log_softmax(masked_logits, dim=-1)
                current_probs = torch.softmax(masked_logits, dim=-1)
                init_policy_kl = (
                    current_probs * (current_log_probs - init_log_probs)
                ).masked_fill(batch_masks <= 0, 0.0).sum(dim=-1).mean()
            loss = (
                policy_loss
                + float(args.ppo_value_coef) * value_loss
                - float(args.ppo_entropy_coef) * entropy
                + float(getattr(args, "ppo_kl_to_init_coef", 0.0)) * init_policy_kl
            )
            optimizer.zero_grad()
            loss.backward()
            optimizer.step()
            with torch.no_grad():
                log_ratio = new_log_probs - batch_old_log_probs
                approx_kl = ((torch.exp(log_ratio) - 1.0) - log_ratio).mean()
                clip_fraction = ((ratio - 1.0).abs() > float(args.ppo_clip)).float().mean()
            metrics["policy_loss"].append(float(policy_loss.item()))
            metrics["value_loss"].append(float(value_loss.item()))
            metrics["entropy"].append(float(entropy.item()))
            metrics["approx_kl"].append(float(approx_kl.item()))
            metrics["clip_fraction"].append(float(clip_fraction.item()))
            metrics["init_policy_kl"].append(float(init_policy_kl.item()))
            if (
                bool(getattr(args, "ppo_early_stop_kl", False))
                and float(approx_kl.item()) > float(getattr(args, "ppo_target_kl", 0.0))
            ):
                early_stop_kl_triggered = True
                break
        if early_stop_kl_triggered:
            break
    result = {key: sum(values) / max(1, len(values)) for key, values in metrics.items()}
    result["early_stop_kl_triggered"] = bool(early_stop_kl_triggered)
    return result


def offline_ppo_arena_probe(
    actor: Any,
    components: dict,
    profile_config: dict,
    device: Any,
    games: int,
    rng: random.Random,
) -> dict:
    GuandanGame = components["GuandanGame"]
    result = {
        "games": int(games),
        "completed_games": 0,
        "team0_wins": 0,
        "team1_wins": 0,
        "team0_win_rate": 0.0,
        "avg_game_length": 0.0,
        "illegal_action_count": 0,
        "fallback_count": 0,
        "materialization_fail_count": 0,
        "hand_card_mismatch_count": 0,
    }
    total_steps = 0
    for _game_index in range(int(games)):
        game = GuandanGame(verbose=False, print_history=False)
        offline_set_random_first_player(game, rng)
        steps = 0
        while not game.is_game_over and steps < OFFLINE_MAX_GAME_STEPS:
            offline_prepare_turn(game)
            if game.current_player in game.ranking:
                steps += 1
                continue
            if int(game.current_player) in (0, 2):
                action_info = offline_select_action_fast(game, components, actor=actor, device=device, rng=rng)
            else:
                action_info = offline_baseline_action_info(
                    game,
                    components,
                    "tempo_baseline",
                    profile_config,
                    rng,
                )
            record = offline_apply_action(game, action_info)
            if record.get("illegal"):
                result["illegal_action_count"] += 1
            if record.get("fallback"):
                result["fallback_count"] += 1
            if record.get("materialization_fail"):
                result["materialization_fail_count"] += 1
            if record.get("hand_card_mismatch"):
                result["hand_card_mismatch_count"] += 1
            steps += 1
            total_steps += 1
        if game.is_game_over:
            result["completed_games"] += 1
            winner_team = offline_winner_team_id(game)
            if winner_team == 0:
                result["team0_wins"] += 1
            elif winner_team == 1:
                result["team1_wins"] += 1
    completed = max(1, int(result["completed_games"]))
    result["team0_win_rate"] = result["team0_wins"] / completed
    result["avg_game_length"] = total_steps / max(1, int(games))
    return result


def run_ppo_curriculum_train(args: argparse.Namespace) -> None:
    components = offline_load_guandan_components()
    GuandanGame = components["GuandanGame"]
    device_info = offline_resolve_device(args.device)
    torch = device_info["torch"]
    if torch is None:
        raise RuntimeError("torch backend is required for PPO curriculum training")
    device = device_info["device"]
    actor, critic, _actor_optimizer, _critic_optimizer = offline_build_models(len(components["actions"]), device)
    if args.init_actor:
        try:
            state_dict = torch.load(Path(args.init_actor), map_location=device, weights_only=True)
        except TypeError:
            state_dict = torch.load(Path(args.init_actor), map_location=device)
        actor.load_state_dict(state_dict)
    init_actor = None
    if bool(args.ppo_safe_mode) or bool(args.ppo_keep_best_by_arena):
        init_actor, _init_critic, _init_actor_optimizer, _init_critic_optimizer = offline_build_models(
            len(components["actions"]),
            device,
        )
        init_actor.load_state_dict(actor.state_dict())
        init_actor.eval()
        for param in init_actor.parameters():
            param.requires_grad_(False)
    optimizer = torch.optim.Adam(list(actor.parameters()) + list(critic.parameters()), lr=float(args.ppo_lr))
    profiles = load_json(PROFILE_PATH, {})
    profile_config = profiles.get("tempo_baseline", {"engine_mode": "tempo"})
    rng = random.Random(20260706)
    out_dir = Path(args.ppo_out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    restore_baseline = offline_install_arena_baseline_optimizations()
    stats = {
        "backend": device_info["backend"],
        "requested_device": device_info["requested_device"],
        "actual_device": device_info["actual_device"],
        "device_fallback": device_info["device_fallback"],
        "torch_available": device_info["torch_available"],
        "cuda_available": device_info["cuda_available"],
        "legal_mask_source": "website_oracle",
        "local_player_mapping": offline_local_player_mapping(),
        "team_mapping": offline_team_mapping(),
        "first_player_policy": "random_each_game",
        "first_player_distribution": {"0": 0, "1": 0, "2": 0, "3": 0},
        "model_team": [0, 2],
        "opponent_team": [1, 3],
        "opponent_pool": {"random_bot": 0.20, "greedy_bot": 0.30, "tempo_baseline": 0.50},
        "opponent_profile_distribution": {"random_bot": 0, "greedy_bot": 0, "tempo_baseline": 0},
        "ppo_episodes": int(args.ppo_episodes),
        "ppo_rollout_games": 10,
        "ppo_safe_mode": bool(args.ppo_safe_mode),
        "ppo_kl_to_init_coef": float(args.ppo_kl_to_init_coef),
        "ppo_target_kl": float(args.ppo_target_kl),
        "ppo_early_stop_kl": bool(args.ppo_early_stop_kl),
        "ppo_reward_shaping": bool(args.ppo_reward_shaping),
        "ppo_hand_delta_reward": float(args.ppo_hand_delta_reward),
        "ppo_win_reward": float(args.ppo_win_reward),
        "ppo_loss_reward": float(args.ppo_loss_reward),
        "ppo_eval_every": int(args.ppo_eval_every),
        "ppo_eval_games": int(args.ppo_eval_games),
        "ppo_keep_best_by_arena": bool(args.ppo_keep_best_by_arena),
        "completed_games": 0,
        "team0_wins": 0,
        "team1_wins": 0,
        "team0_win_rate": 0.0,
        "team1_win_rate": 0.0,
        "avg_game_length": 0.0,
        "pass_rate": 0.0,
        "bomb_usage_rate": 0.0,
        "illegal_action_count": 0,
        "fallback_count": 0,
        "materialization_fail_count": 0,
        "hand_card_mismatch_count": 0,
        "policy_loss": 0.0,
        "value_loss": 0.0,
        "entropy": 0.0,
        "approx_kl": 0.0,
        "clip_fraction": 0.0,
        "init_policy_kl": 0.0,
        "ppo_early_stop_kl_count": 0,
        "saved_checkpoints": [],
        "best_arena_checkpoint": None,
        "best_arena_win_rate": None,
        "init_arena_probe": None,
        "arena_probe_history": [],
        "no_improvement": False,
        "arena_no_improvement_count": 0,
        "threshold_passed": False,
        "concrete_failure_samples": [],
        "action_type_distribution": {},
    }
    total_steps = 0
    total_passes = 0
    total_bombs = 0
    total_game_length = 0
    action_type_counts: Counter = Counter()
    ppo_metric_history: list[dict] = []
    ppo_buffer: list[dict] = []
    ppo_rollout_games = 10
    best_arena_win_rate = -1.0
    init_arena_win_rate = None
    try:
        if bool(args.ppo_keep_best_by_arena) and init_actor is not None and int(args.ppo_eval_games) > 0:
            init_probe = offline_ppo_arena_probe(
                init_actor,
                components,
                profile_config,
                device,
                int(args.ppo_eval_games),
                rng,
            )
            stats["init_arena_probe"] = init_probe
            init_arena_win_rate = float(init_probe.get("team0_win_rate") or 0.0)
        for episode in range(1, int(args.ppo_episodes) + 1):
            game = GuandanGame(verbose=False, print_history=False)
            first_player = offline_set_random_first_player(game, rng)
            stats["first_player_distribution"][str(first_player)] += 1
            opponent_profile = offline_opponent_pool_profile(rng)
            stats["opponent_profile_distribution"][opponent_profile] += 1
            model_memory: dict[int, list[dict]] = {0: [], 2: []}
            last_shape_opponent_total = len(game.players[1].hand) + len(game.players[3].hand)
            episode_steps = 0
            while not game.is_game_over and episode_steps < OFFLINE_MAX_GAME_STEPS:
                offline_prepare_turn(game)
                if game.current_player in game.ranking:
                    episode_steps += 1
                    continue
                current_player = int(game.current_player)
                hand_counts_before = [len(player.hand) for player in game.players]
                if current_player in (0, 2):
                    action_info = offline_select_action_fast(game, components, actor=actor, device=device, rng=rng)
                    if len(action_info.get("legal_mask") or []) != OFFLINE_ACTION_DIM:
                        stats["illegal_action_count"] += 1
                    if action_info.get("fatal_no_verified_legal"):
                        stats["illegal_action_count"] += 1
                    if not action_info.get("fallback") and not action_info.get("illegal"):
                        try:
                            old_log_prob, value = offline_ppo_log_prob_value(
                                actor,
                                critic,
                                action_info["state"],
                                list(action_info["legal_mask"]),
                                int(action_info["action_id"]),
                                device,
                            )
                            action_info["old_log_prob"] = old_log_prob
                            action_info["value"] = value
                        except RuntimeError as exc:
                            stats["illegal_action_count"] += 1
                            action_info["illegal"] = True
                            action_info["illegal_reason"] = str(exc)
                    action_info["policy"] = "ppo_actor"
                else:
                    action_info = offline_opponent_action_info(game, components, opponent_profile, profile_config, rng)
                record = offline_apply_action(game, action_info)
                hand_counts_after = [len(player.hand) for player in game.players]
                total_steps += 1
                episode_steps += 1
                action_type_counts[record["action_type"]] += 1
                if not record["chosen_cards"]:
                    total_passes += 1
                if record["is_bomb"]:
                    total_bombs += 1
                if record.get("illegal"):
                    stats["illegal_action_count"] += 1
                if record.get("fallback"):
                    stats["fallback_count"] += 1
                if record.get("materialization_fail"):
                    stats["materialization_fail_count"] += 1
                if record.get("hand_card_mismatch"):
                    stats["hand_card_mismatch_count"] += 1
                if (
                    record.get("illegal")
                    or record.get("fallback")
                    or record.get("materialization_fail")
                    or record.get("hand_card_mismatch")
                ) and len(stats["concrete_failure_samples"]) < 20:
                    stats["concrete_failure_samples"].append(
                        {
                            "episode": episode,
                            "step": episode_steps,
                            "player_id": record.get("player_id"),
                            "policy": record.get("policy"),
                            "action_id": record.get("action_id"),
                            "chosen_cards": record.get("chosen_cards"),
                            "illegal_reason": record.get("illegal_reason"),
                            "materialization_fail_reason": record.get("materialization_fail_reason"),
                            "missing_cards": record.get("missing_cards"),
                        }
                    )
                if current_player in (0, 2) and not (
                    record.get("illegal")
                    or record.get("fallback")
                    or record.get("materialization_fail")
                    or record.get("hand_card_mismatch")
                ):
                    step_reward = 0.0
                    if bool(args.ppo_reward_shaping):
                        own_delta = (hand_counts_before[0] + hand_counts_before[2]) - (
                            hand_counts_after[0] + hand_counts_after[2]
                        )
                        opponent_delta = max(0, last_shape_opponent_total - (hand_counts_before[1] + hand_counts_before[3]))
                        step_reward = float(args.ppo_hand_delta_reward) * float(own_delta - opponent_delta)
                        record["own_hand_delta"] = int(own_delta)
                        record["opponent_hand_delta_since_last_model_action"] = int(opponent_delta)
                    last_shape_opponent_total = hand_counts_after[1] + hand_counts_after[3]
                    record["step_reward"] = float(step_reward)
                    record["old_log_prob"] = float(action_info.get("old_log_prob", 0.0))
                    record["value"] = float(action_info.get("value", 0.0))
                    model_memory[current_player].append(record)
            total_game_length += episode_steps
            if game.is_game_over:
                stats["completed_games"] += 1
                winner_team = offline_winner_team_id(game)
                if winner_team == 0:
                    stats["team0_wins"] += 1
                elif winner_team == 1:
                    stats["team1_wins"] += 1
                final_reward = float(args.ppo_win_reward) if winner_team == 0 else float(args.ppo_loss_reward)
                transitions = offline_ppo_assign_advantages(
                    model_memory,
                    final_reward,
                    float(args.ppo_gamma),
                    float(args.ppo_lambda),
                )
                ppo_buffer.extend(transitions)
            if ppo_buffer and (episode % ppo_rollout_games == 0 or episode == int(args.ppo_episodes)):
                metrics = offline_ppo_update(actor, critic, optimizer, ppo_buffer, args, device, init_actor=init_actor)
                ppo_metric_history.append(metrics)
                if metrics.get("early_stop_kl_triggered"):
                    stats["ppo_early_stop_kl_count"] += 1
                ppo_buffer = []
            if int(args.ppo_save_every) > 0 and episode % int(args.ppo_save_every) == 0:
                actor_path = out_dir / f"ppo_actor_ep{episode}.pth"
                critic_path = out_dir / f"ppo_critic_ep{episode}.pth"
                torch.save(actor.state_dict(), actor_path)
                torch.save(critic.state_dict(), critic_path)
                stats["saved_checkpoints"].append(
                    {"episode": episode, "actor": str(actor_path), "critic": str(critic_path)}
                )
            if int(args.ppo_eval_every) > 0 and episode % int(args.ppo_eval_every) == 0 and int(args.ppo_eval_games) > 0:
                probe = offline_ppo_arena_probe(
                    actor,
                    components,
                    profile_config,
                    device,
                    int(args.ppo_eval_games),
                    rng,
                )
                probe["episode"] = episode
                stats["arena_probe_history"].append(probe)
                probe_win_rate = float(probe.get("team0_win_rate") or 0.0)
                if init_arena_win_rate is not None and probe_win_rate <= init_arena_win_rate:
                    stats["arena_no_improvement_count"] += 1
                if bool(args.ppo_keep_best_by_arena) and probe_win_rate > best_arena_win_rate:
                    best_arena_win_rate = probe_win_rate
                    best_actor_path = out_dir / "ppo_actor_best_arena.pth"
                    torch.save(actor.state_dict(), best_actor_path)
                    stats["best_arena_checkpoint"] = str(best_actor_path)
                    stats["best_arena_win_rate"] = best_arena_win_rate
            if episode % max(1, int(args.report_every)) == 0:
                save_json(Path(args.ppo_log_out), stats)
    finally:
        restore_baseline()
    completed = max(1, int(stats["completed_games"]))
    stats["team0_win_rate"] = stats["team0_wins"] / completed
    stats["team1_win_rate"] = stats["team1_wins"] / completed
    stats["avg_game_length"] = total_game_length / max(1, int(args.ppo_episodes))
    stats["pass_rate"] = total_passes / max(1, total_steps)
    stats["bomb_usage_rate"] = total_bombs / max(1, total_steps)
    stats["action_type_distribution"] = dict(action_type_counts)
    if ppo_metric_history:
        recent = ppo_metric_history[-20:]
        for key in ("policy_loss", "value_loss", "entropy", "approx_kl", "clip_fraction", "init_policy_kl"):
            stats[key] = sum(float(item.get(key, 0.0)) for item in recent) / max(1, len(recent))
    if init_arena_win_rate is not None and stats["arena_probe_history"]:
        stats["no_improvement"] = bool(
            all(float(probe.get("team0_win_rate") or 0.0) <= init_arena_win_rate for probe in stats["arena_probe_history"])
        )
    stats["threshold_passed"] = bool(
        stats["completed_games"] == int(args.ppo_episodes)
        and stats["illegal_action_count"] == 0
        and stats["fallback_count"] == 0
        and stats["hand_card_mismatch_count"] == 0
        and stats["materialization_fail_count"] == 0
        and stats["saved_checkpoints"]
    )
    save_json(Path(args.ppo_log_out), stats)
    save_json(out_dir / "ppo_training_state.json", stats)
    print(json.dumps(stats, ensure_ascii=False, indent=2))
    if not stats["threshold_passed"]:
        raise RuntimeError("PPO curriculum smoke threshold failed")


def run_shared_selfplay_train(args: argparse.Namespace) -> None:
    components = offline_load_guandan_components()
    GuandanGame = components["GuandanGame"]
    device_info = offline_resolve_device(args.device)
    torch = device_info["torch"]
    if torch is not None:
        device = device_info["device"]
        actor, critic, actor_optimizer, critic_optimizer = offline_build_models(len(components["actions"]), device)
    else:
        device = None
        actor = OfflineNumpyActor(len(components["actions"]))
        critic = OfflineNumpyCritic()
        actor_optimizer = None
        critic_optimizer = None
    rng = random.Random(20260703)
    model_dir = Path(args.model_out_dir)
    model_dir.mkdir(parents=True, exist_ok=True)
    stats = {
        "backend": device_info["backend"],
        "requested_device": device_info["requested_device"],
        "actual_device": device_info["actual_device"],
        "device_fallback": device_info["device_fallback"],
        "torch_available": device_info["torch_available"],
        "cuda_available": device_info["cuda_available"],
        "legal_mask_source": "website_oracle",
        "local_player_mapping": offline_local_player_mapping(),
        "team_mapping": offline_team_mapping(),
        "first_player_policy": "random_each_game",
        "first_player_distribution": {"0": 0, "1": 0, "2": 0, "3": 0},
        "episodes": int(args.episodes),
        "completed_games": 0,
        "team0_wins": 0,
        "team1_wins": 0,
        "team0_win_rate": 0.0,
        "team1_win_rate": 0.0,
        "average_game_length": 0.0,
        "raw_legal_action_count": 0,
        "verified_legal_action_count": 0,
        "average_raw_legal_action_count": 0.0,
        "average_verified_legal_action_count": 0.0,
        "mask_combo_disagree_count": 0,
        "mask_combo_disagree_action_ids": [],
        "mask_combo_disagree_samples": [],
        "old_mask_disagree_count": 0,
        "old_mask_disagree_denominator": 0,
        "old_mask_disagree_rate": 0.0,
        "illegal_action_count": 0,
        "fallback_count": 0,
        "hand_card_mismatch_count": 0,
        "materialization_fail_count": 0,
        "top_materialization_fail_reasons": [],
        "illegal_action_rate": 0.0,
        "fallback_rate": 0.0,
        "pass_rate": 0.0,
        "bomb_usage_rate": 0.0,
        "action_type_distribution": {},
        "average_final_reward": 0.0,
        "actor_loss_recent": None,
        "critic_loss_recent": None,
        "saved_checkpoints": [],
        "concrete_illegal_samples": [],
        "threshold_passed": True,
        "episodes_summary": [],
    }
    total_steps = 0
    total_passes = 0
    total_bombs = 0
    total_game_length = 0
    final_rewards: list[float] = []
    actor_losses: list[float] = []
    critic_losses: list[float] = []
    action_type_counts: Counter = Counter()
    disagree_action_ids: set[int] = set()
    for episode in range(1, int(args.episodes) + 1):
        game = GuandanGame(verbose=False, print_history=False)
        first_player = offline_set_random_first_player(game, rng)
        stats["first_player_distribution"][str(first_player)] += 1
        memory: dict[int, list[dict]] = {0: [], 1: [], 2: [], 3: []}
        episode_steps = 0
        while not game.is_game_over and episode_steps < OFFLINE_MAX_GAME_STEPS:
            offline_prepare_turn(game)
            if game.current_player in game.ranking:
                episode_steps += 1
                continue
            action_info = offline_select_action(game, components, actor=actor, device=device, rng=rng)
            stats["raw_legal_action_count"] += int(action_info.get("raw_legal_action_count") or 0)
            stats["verified_legal_action_count"] += int(action_info.get("verified_legal_action_count") or 0)
            stats["mask_combo_disagree_count"] += int(action_info.get("mask_combo_disagree_count") or 0)
            stats["old_mask_disagree_count"] += int(action_info.get("old_mask_disagree_count") or 0)
            stats["old_mask_disagree_denominator"] += int(action_info.get("old_mask_disagree_denominator") or 0)
            disagree_action_ids.update(int(action_id) for action_id in action_info.get("mask_combo_disagree_action_ids") or [])
            for sample in action_info.get("mask_combo_disagree_samples") or []:
                if len(stats["mask_combo_disagree_samples"]) < 20:
                    stats["mask_combo_disagree_samples"].append(
                        {
                            "episode": episode,
                            "step": episode_steps,
                            "player_id": action_info["player_id"],
                            **sample,
                        }
                    )
            if action_info.get("fatal_no_verified_legal"):
                stats["concrete_illegal_samples"].append(
                    {
                        "episode": episode,
                        "step": episode_steps,
                        "player_id": action_info["player_id"],
                        "illegal_reason": action_info.get("illegal_reason"),
                        "raw_legal_action_count": action_info.get("raw_legal_action_count"),
                        "verified_legal_action_count": action_info.get("verified_legal_action_count"),
                    }
                )
                save_json(Path(args.selfplay_log_out), stats)
                raise RuntimeError("lead turn has no verified legal action; see self-play log")
            record = offline_apply_action(game, action_info)
            memory[int(record["player_id"])].append(record)
            total_steps += 1
            episode_steps += 1
            action_type_counts[record["action_type"]] += 1
            if not record["chosen_cards"]:
                total_passes += 1
            if record["is_bomb"]:
                total_bombs += 1
            if record["illegal"]:
                stats["illegal_action_count"] += 1
                if len(stats["concrete_illegal_samples"]) < 20:
                    stats["concrete_illegal_samples"].append(
                        {
                            "episode": episode,
                            "step": episode_steps,
                            "player_id": record["player_id"],
                            "sampled_action_id": record["sampled_action_id"],
                            "fallback_action_id": record["action_id"],
                            "illegal_reason": record["illegal_reason"],
                            "chosen_cards": record["chosen_cards"],
                            "last_play": record["last_play"],
                        }
                    )
            if record["fallback"]:
                stats["fallback_count"] += 1
        total_game_length += episode_steps
        if game.is_game_over:
            stats["completed_games"] += 1
            winner_team = 0 if int(game.winning_team) == 1 else 1
            if winner_team == 0:
                stats["team0_wins"] += 1
            else:
                stats["team1_wins"] += 1
            final_reward = float(game.upgrade_amount or 1)
            final_rewards.append(final_reward)
            merged_memory: list[dict] = []
            for player_id, player_memory in memory.items():
                signed_reward = final_reward if offline_team_id(player_id) == winner_team else -final_reward
                for item in player_memory:
                    item["reward"] = signed_reward
                    merged_memory.append(item)
            actor_loss, critic_loss = offline_train_on_memory(
                merged_memory,
                actor,
                critic,
                actor_optimizer,
                critic_optimizer,
                device,
            )
            actor_losses.append(actor_loss)
            critic_losses.append(critic_loss)
        stats["episodes_summary"].append(
            {
                "episode": episode,
                "completed": bool(game.is_game_over),
                "first_player": first_player,
                "steps": episode_steps,
                "ranking": list(game.ranking),
                "winning_team_id": 0 if int(game.winning_team) == 1 else 1 if int(game.winning_team) == 2 else None,
            }
        )
        if args.save_every and episode % int(args.save_every) == 0:
            suffix = "pth" if device_info["backend"] == "torch" else "npz"
            actor_path = model_dir / f"actor_ep{episode}.{suffix}"
            critic_path = model_dir / f"critic_ep{episode}.{suffix}"
            if device_info["backend"] == "torch":
                torch.save(actor.state_dict(), actor_path)
                torch.save(critic.state_dict(), critic_path)
            else:
                actor.save(actor_path)
                critic.save(critic_path)
            stats["saved_checkpoints"].append({"episode": episode, "actor": str(actor_path), "critic": str(critic_path)})
        if args.eval_every and episode % int(args.eval_every) == 0:
            save_json(Path(args.selfplay_log_out), stats)
    completed = max(1, int(stats["completed_games"]))
    stats["team0_win_rate"] = stats["team0_wins"] / completed
    stats["team1_win_rate"] = stats["team1_wins"] / completed
    stats["average_game_length"] = total_game_length / max(1, int(args.episodes))
    stats["average_raw_legal_action_count"] = stats["raw_legal_action_count"] / max(1, total_steps)
    stats["average_verified_legal_action_count"] = stats["verified_legal_action_count"] / max(1, total_steps)
    stats["mask_combo_disagree_action_ids"] = sorted(disagree_action_ids)
    stats["old_mask_disagree_rate"] = stats["old_mask_disagree_count"] / max(
        1,
        stats["old_mask_disagree_denominator"],
    )
    stats["illegal_action_rate"] = stats["illegal_action_count"] / max(1, total_steps)
    stats["fallback_rate"] = stats["fallback_count"] / max(1, total_steps)
    stats["pass_rate"] = total_passes / max(1, total_steps)
    stats["bomb_usage_rate"] = total_bombs / max(1, total_steps)
    stats["action_type_distribution"] = dict(action_type_counts)
    stats["average_final_reward"] = sum(final_rewards) / max(1, len(final_rewards))
    stats["actor_loss_recent"] = sum(actor_losses[-10:]) / max(1, len(actor_losses[-10:])) if actor_losses else None
    stats["critic_loss_recent"] = sum(critic_losses[-10:]) / max(1, len(critic_losses[-10:])) if critic_losses else None
    stats["threshold_passed"] = (
        stats["illegal_action_rate"] <= float(args.max_illegal_rate)
        and stats["fallback_rate"] <= float(args.max_fallback_rate)
    )
    save_json(Path(args.selfplay_log_out), stats)
    print(json.dumps(stats, ensure_ascii=False, indent=2))
    if not stats["threshold_passed"]:
        raise RuntimeError(
            "shared self-play threshold failed: "
            f"illegal_rate={stats['illegal_action_rate']:.4f}, fallback_rate={stats['fallback_rate']:.4f}"
        )


def offline_load_actor_checkpoint(path: Path, components: dict, device_info: dict) -> Any:
    torch = device_info.get("torch")
    if torch is None:
        raise RuntimeError("offline arena actor checkpoints require torch backend")
    actor, _critic, _actor_optimizer, _critic_optimizer = offline_build_models(
        len(components["actions"]),
        device_info["device"],
    )
    try:
        state_dict = torch.load(path, map_location=device_info["device"], weights_only=True)
    except TypeError:
        state_dict = torch.load(path, map_location=device_info["device"])
    actor.load_state_dict(state_dict)
    actor.eval()
    return actor


def offline_winner_team_id(game: Any) -> int | None:
    try:
        winning_team = int(game.winning_team)
    except (TypeError, ValueError):
        return None
    if winning_team == 1:
        return 0
    if winning_team == 2:
        return 1
    return None


def offline_arena_state_for_player(game: Any, player_id: int) -> dict:
    was_lead = bool(game.is_free_turn or not (game.last_play or []))
    hand_counts = [len(player.hand) for player in game.players]
    state = {
        "level": website_level_from_local_level(game.active_level),
        "your_hand": local_cards_to_website(list(game.players[player_id].hand)),
        "last_play": [] if was_lead else local_cards_to_website(list(game.last_play or [])),
        "last_player": None if was_lead else game.last_player,
        "current_turn": player_id,
        "your_seat": player_id,
        "your_team": offline_team_id(player_id),
        "is_your_turn": True,
        "completed": False,
        "seats": [f"arena_{seat}" for seat in range(4)],
        "teams": {str(seat): offline_team_id(seat) for seat in range(4)},
        "hand_counts": hand_counts,
        "ranking": list(game.ranking),
        "trick_history": list(game.history),
        "left_time": None,
    }
    models = {seat: PlayerModel() for seat in range(4)}
    tags = scenario_tags(state, models)
    state["_scenario_tags"] = tags
    return state


def offline_action_id_for_cards(
    game: Any,
    components: dict,
    cards: list[str],
    last_play_before: list[str] | None,
    was_lead: bool,
) -> int | None:
    if not cards:
        return 0
    level = website_level_from_local_level(game.active_level)
    website_cards = local_cards_to_website(cards)
    website_last = local_cards_to_website(list(last_play_before or []))
    infos = engine.recognize(website_cards, level) if was_lead else engine.safe_follow_infos(
        website_cards,
        website_last,
        level,
    )
    for info in infos:
        action_id = website_action_id_for_info(components, website_cards, info, level)
        if action_id is not None:
            return int(action_id)
    action = offline_map_action(game, components["actions"], cards)
    if action and action.get("id") is not None:
        return int(action["id"])
    return None


def offline_make_action_info_from_cards(
    game: Any,
    components: dict,
    cards: list[str],
    rng: random.Random,
    policy: str,
    fallback: bool = False,
    fallback_reason: str | None = None,
    sampled_action_id: int | None = None,
    audit_masks: bool = True,
) -> dict:
    del rng
    player_id = int(game.current_player)
    player = game.players[player_id]
    hand_before = list(player.hand)
    last_play_before = list(game.last_play or [])
    was_lead = bool(game.is_free_turn or not last_play_before)
    state = game._get_obs()
    if audit_masks:
        last_action_arg = [] if was_lead else last_play_before
        old_legal_mask = game.get_valid_action_mask(
            hand_before,
            components["actions"],
            game.active_level,
            last_action_arg,
        )
        oracle = offline_oracle_legal_mask(
            game,
            components,
            player_id,
            hand_before,
            last_play_before,
            game.active_level,
        )
        verified = offline_verified_legal_options(
            game,
            components,
            hand_before,
            last_play_before,
            was_lead,
            oracle["mask"],
            oracle_options=oracle["options"],
        )
        old_ids = {
            idx
            for idx, value in enumerate(old_legal_mask)
            if float(value) > 0 and 0 <= idx < len(components["actions"])
        }
        oracle_ids = set(oracle["ids"])
        old_mask_disagree_ids = sorted(old_ids.symmetric_difference(oracle_ids))
        old_mask_disagree_denominator = len(old_ids.union(oracle_ids))
        legal_mask = verified["verified_mask"]
        raw_legal_mask = list(oracle["mask"])
        old_legal_mask_value = old_legal_mask.tolist() if hasattr(old_legal_mask, "tolist") else list(old_legal_mask)
        raw_count = len(verified["raw_ids"])
        verified_count = len(verified["verified_ids"])
        mask_disagree_count = len(verified["disagree_ids"])
        mask_disagree_ids = list(verified["disagree_ids"])
        mask_disagree_samples = list(verified["disagree_samples"])
    else:
        legal_mask = [0.0 for _ in components["actions"]]
        raw_legal_mask = [0.0 for _ in components["actions"]]
        old_legal_mask_value = [0.0 for _ in components["actions"]]
        old_mask_disagree_ids = []
        old_mask_disagree_denominator = 0
        raw_count = 0
        verified_count = 0
        mask_disagree_count = 0
        mask_disagree_ids = []
        mask_disagree_samples = []
    chosen_cards = list(cards or [])
    hand_subset_checked = True
    missing_cards = offline_missing_cards(chosen_cards, hand_before)
    ok, illegal_reason = offline_action_is_legal(
        game,
        components["actions"],
        chosen_cards,
        hand_before,
        last_play_before,
        was_lead,
    )
    if missing_cards:
        ok = False
        illegal_reason = "chosen_cards_not_in_hand"
    action_id = offline_action_id_for_cards(game, components, chosen_cards, last_play_before, was_lead) if ok else None
    if ok and action_id is None:
        ok = False
        illegal_reason = "action_id_mapping_failed"
    if not ok:
        action_id = 0
        chosen_cards = []
    action_struct = components["action_by_id"].get(int(action_id))
    if action_id == 0:
        action_struct = {"type": "None", "points": [], "logic_point": 0, "id": 0}
    return {
        "state": state,
        "legal_mask": legal_mask.tolist() if hasattr(legal_mask, "tolist") else list(legal_mask),
        "raw_legal_mask": raw_legal_mask,
        "old_legal_mask": old_legal_mask_value,
        "legal_mask_source": "website_oracle",
        "old_mask_disagree_count": len(old_mask_disagree_ids),
        "old_mask_disagree_denominator": old_mask_disagree_denominator,
        "old_mask_disagree_rate": len(old_mask_disagree_ids) / max(1, old_mask_disagree_denominator),
        "raw_legal_action_count": raw_count,
        "verified_legal_action_count": verified_count,
        "mask_combo_disagree_count": mask_disagree_count,
        "mask_combo_disagree_action_ids": mask_disagree_ids,
        "mask_combo_disagree_samples": mask_disagree_samples,
        "legal_action_count": verified_count,
        "mask_issue": None,
        "sampled_action_id": sampled_action_id if sampled_action_id is not None else action_id,
        "action_id": int(action_id),
        "chosen_cards": chosen_cards,
        "physical_cards": chosen_cards,
        "logical_cards": None,
        "chosen_cards_website": local_cards_to_website(chosen_cards) if chosen_cards else [],
        "hand_subset_checked": hand_subset_checked,
        "missing_cards": missing_cards,
        "materialization_fail": bool(missing_cards),
        "materialization_fail_reason": "chosen_cards_not_in_hand" if missing_cards else None,
        "illegal": not ok,
        "fallback": bool(fallback),
        "fallback_reason": fallback_reason,
        "fatal_no_verified_legal": False,
        "illegal_reason": illegal_reason,
        "action_type": str((action_struct or {}).get("type") or "unknown"),
        "action_rank": offline_action_rank_label(action_struct),
        "is_bomb": offline_action_is_bomb(action_struct),
        "player_id": player_id,
        "team_id": offline_team_id(player_id),
        "was_lead": was_lead,
        "was_follow": not was_lead,
        "hand_before": hand_before,
        "last_play": last_play_before,
        "policy": policy,
    }


def offline_first_oracle_action_info(
    game: Any,
    components: dict,
    rng: random.Random,
    policy: str,
    fallback_reason: str,
) -> dict:
    player_id = int(game.current_player)
    hand_before = list(game.players[player_id].hand)
    last_play_before = list(game.last_play or [])
    was_lead = bool(game.is_free_turn or not last_play_before)
    candidates = offline_legal_candidates(game, components, hand_before, last_play_before, was_lead)
    if not candidates:
        cards: list[str] = [] if not was_lead else []
        return offline_make_action_info_from_cards(
            game,
            components,
            cards,
            rng,
            policy=policy,
            fallback=True,
            fallback_reason=fallback_reason,
        )
    action_id, cards = rng.choice(candidates)
    return offline_make_action_info_from_cards(
        game,
        components,
        list(cards),
        rng,
        policy=policy,
        fallback=True,
        fallback_reason=fallback_reason,
        sampled_action_id=action_id,
    )


def offline_baseline_action_info(
    game: Any,
    components: dict,
    baseline_profile: str,
    profile_config: dict,
    rng: random.Random,
    fallback: bool = False,
    fallback_reason: str | None = None,
) -> dict:
    player_id = int(game.current_player)
    state = offline_arena_state_for_player(game, player_id)
    coord = choose_profiled_play(state, baseline_profile, profile_config)
    local_cards = website_cards_to_local(list(coord or []))
    info = offline_make_action_info_from_cards(
        game,
        components,
        local_cards,
        rng,
        policy="tempo_baseline",
        fallback=fallback,
        fallback_reason=fallback_reason,
        audit_masks=False,
    )
    if info.get("illegal"):
        return offline_first_oracle_action_info(
            game,
            components,
            rng,
            policy="tempo_baseline",
            fallback_reason=str(info.get("illegal_reason") or "baseline_action_invalid"),
        )
    return info


def offline_arena_model_action_info(
    game: Any,
    components: dict,
    actor: Any,
    device: Any,
    baseline_profile: str,
    profile_config: dict,
    rng: random.Random,
) -> dict:
    model_info = offline_select_action(game, components, actor=actor, device=device, rng=rng)
    model_failed = bool(
        model_info.get("fatal_no_verified_legal")
        or model_info.get("illegal")
        or model_info.get("fallback")
        or model_info.get("materialization_fail")
        or model_info.get("hand_card_mismatch")
        or (model_info.get("was_lead") and not model_info.get("chosen_cards"))
    )
    if not model_failed:
        model_info["policy"] = "model"
        return model_info
    baseline_info = offline_baseline_action_info(
        game,
        components,
        baseline_profile,
        profile_config,
        rng,
        fallback=True,
        fallback_reason=str(model_info.get("illegal_reason") or model_info.get("mask_issue") or "model_action_failed"),
    )
    baseline_info["model_failure_sample"] = {
        "sampled_action_id": model_info.get("sampled_action_id"),
        "illegal_reason": model_info.get("illegal_reason"),
        "materialization_fail": model_info.get("materialization_fail"),
        "materialization_fail_reason": model_info.get("materialization_fail_reason"),
        "missing_cards": model_info.get("missing_cards"),
        "mask_issue": model_info.get("mask_issue"),
        "chosen_cards": model_info.get("chosen_cards"),
        "was_lead": model_info.get("was_lead"),
        "last_play": model_info.get("last_play"),
    }
    return baseline_info


def offline_guard_empty_counts() -> dict:
    return {
        "guard_trigger_count": 0,
        "guard_pass_override_count": 0,
        "guard_bomb_override_count": 0,
        "guard_teammate_support_count": 0,
        "guard_opponent_block_count": 0,
        "guard_illegal_count": 0,
    }


def offline_rule_assisted_guard_action(
    game: Any,
    components: dict,
    action_info: dict,
    args: argparse.Namespace,
    rng: random.Random,
) -> tuple[dict, dict]:
    counts = offline_guard_empty_counts()
    if not bool(getattr(args, "rule_assisted_guard", False)):
        return action_info, counts
    if action_info.get("illegal") or action_info.get("fatal_no_verified_legal"):
        return action_info, counts
    player_id = int(game.current_player)
    hand_before = list(game.players[player_id].hand)
    last_play_before = list(game.last_play or [])
    was_lead = bool(game.is_free_turn or not last_play_before)
    hand_counts = [len(player.hand) for player in game.players]
    teammate = offline_teammate(player_id)
    opponents = [seat for seat in range(4) if offline_team_id(seat) != offline_team_id(player_id)]
    opponent_min = min(hand_counts[seat] for seat in opponents)
    teammate_remaining = hand_counts[teammate]
    _oracle, candidates = offline_oracle_candidates_fast(game, components, hand_before, last_play_before, was_lead)
    selected: tuple[int, list[str]] | None = None
    reason: str | None = None
    original_pass = not bool(action_info.get("chosen_cards"))
    if (
        not was_lead
        and game.last_player == teammate
        and teammate_remaining <= int(args.guard_critical_hand_threshold)
        and action_info.get("chosen_cards")
    ):
        selected = (0, [])
        reason = "avoid_overriding_teammate"
        counts["guard_teammate_support_count"] += 1
    elif not was_lead and original_pass:
        non_pass_candidates = [(action_id, cards) for action_id, cards in candidates if cards]
        if non_pass_candidates and opponent_min <= int(args.guard_opponent_hand_threshold):
            allow_bomb = bool(args.guard_allow_minimal_bomb and opponent_min <= int(args.guard_critical_hand_threshold))
            selected = corrective_smallest_candidate(components, candidates, allow_bomb=allow_bomb)
            if selected is None and opponent_min <= int(args.guard_critical_hand_threshold):
                selected = corrective_smallest_candidate(components, candidates, allow_bomb=True)
            if selected is not None:
                reason = "opponent_block"
                counts["guard_pass_override_count"] += 1
                counts["guard_opponent_block_count"] += 1
    elif was_lead and teammate_remaining <= int(args.guard_critical_hand_threshold):
        support_candidates = [
            (action_id, cards)
            for action_id, cards in candidates
            if cards
            and len(cards) == teammate_remaining
            and not offline_action_is_bomb(components["action_by_id"].get(int(action_id)))
        ]
        if support_candidates:
            selected = min(support_candidates, key=lambda item: corrective_action_sort_key(components, item[0], item[1]))
            if list(action_info.get("chosen_cards") or []) != list(selected[1]):
                reason = "teammate_support"
                counts["guard_teammate_support_count"] += 1
    if selected is None:
        return action_info, counts
    selected_action_id, selected_cards = selected
    guard_info = offline_make_action_info_from_cards(
        game,
        components,
        list(selected_cards),
        rng,
        policy="rule_assisted_guard",
        sampled_action_id=int(selected_action_id),
        audit_masks=False,
    )
    counts["guard_trigger_count"] += 1
    if offline_action_is_bomb(components["action_by_id"].get(int(selected_action_id))):
        counts["guard_bomb_override_count"] += 1
    if guard_info.get("illegal") or guard_info.get("materialization_fail") or guard_info.get("hand_card_mismatch"):
        counts["guard_illegal_count"] += 1
        return action_info, counts
    guard_info["guard_applied"] = True
    guard_info["guard_reason"] = reason
    guard_info["guard_original_action_id"] = action_info.get("action_id")
    guard_info["guard_original_cards"] = list(action_info.get("chosen_cards") or [])
    return guard_info, counts


def offline_arena_profile_seats(game_index: int, arena_games: int, swap_seats: bool) -> tuple[set[int], set[int]]:
    if swap_seats and game_index >= arena_games // 2:
        return {1, 3}, {0, 2}
    return {0, 2}, {1, 3}


def offline_arena_empty_result(checkpoint: str) -> dict:
    return {
        "checkpoint": checkpoint,
        "local_player_mapping": offline_local_player_mapping(),
        "team_mapping": offline_team_mapping(),
        "first_player_policy": "random_each_game",
        "first_player_distribution": {"0": 0, "1": 0, "2": 0, "3": 0},
        "completed_games": 0,
        "attempted_games": 0,
        "model_team_wins": 0,
        "baseline_team_wins": 0,
        "model_team_win_rate": 0.0,
        "baseline_team_win_rate": 0.0,
        "avg_game_length": 0.0,
        "illegal_action_count": 0,
        "fallback_count": 0,
        "hand_card_mismatch_count": 0,
        "materialization_fail_count": 0,
        "top_materialization_fail_reasons": [],
        "illegal_action_rate": 0.0,
        "fallback_rate": 0.0,
        "pass_rate": 0.0,
        "bomb_usage_rate": 0.0,
        "action_type_distribution": {},
        "raw_legal_action_count": 0,
        "verified_legal_action_count": 0,
        "mask_combo_disagree_count": 0,
        "old_mask_disagree_count": 0,
        **offline_guard_empty_counts(),
        "concrete_failure_samples": [],
        "concrete_materialization_failure_samples": [],
        "allowed_for_shadow_eval": False,
        "allowed_for_website_dry_run": False,
    }


def offline_install_arena_baseline_optimizations() -> Any:
    original_choose_all_out = engine.choose_all_out_if_possible
    original_choose_non_bomb_follow = engine.choose_non_bomb_follow

    def arena_choose_all_out_if_possible(hand: list[str], last_play: list[str], level: str) -> list[str] | None:
        if len(hand) > 10:
            return None
        return original_choose_all_out(hand, last_play, level)

    def arena_choose_non_bomb_follow(
        hand: list[str],
        last_play: list[str],
        level: str,
        prefer_strong: bool = False,
    ) -> list[str] | None:
        canonical_infos = engine.canonical_table_infos(last_play, level)
        if any(engine.is_bomb(info) for info in canonical_infos):
            return None
        last_infos = [info for info in canonical_infos if not engine.is_bomb(info)]
        if not last_infos:
            return None
        target_types = {(info.type, info.size) for info in last_infos}
        target_size = len(last_play)
        if target_size <= 3:
            return original_choose_non_bomb_follow(hand, last_play, level, prefer_strong=prefer_strong)
        options = []
        for candidate in engine.legal_play_options(hand, level):
            if candidate.size != target_size:
                continue
            if engine.is_bomb(candidate) or engine.server_treats_as_bomb(candidate.cards, level):
                continue
            infos = [
                info
                for info in engine.safe_follow_infos(list(candidate.cards), last_play, level)
                if not engine.is_bomb(info) and (info.type, info.size) in target_types
            ]
            if not infos:
                continue
            options.append((engine.candidate_key(candidate.cards, infos[0], hand, level), candidate.cards))
        if not options:
            return None
        if prefer_strong:
            return engine.sort_cards(
                list(
                    max(
                        options,
                        key=lambda item: (
                            item[0][4],
                            -item[0][0],
                            -item[0][1],
                            -item[0][2],
                            -item[0][3],
                            item[1],
                        ),
                    )[1]
                ),
                level,
            )
        return engine.sort_cards(list(min(options, key=lambda item: item[0])[1]), level)

    engine.choose_all_out_if_possible = arena_choose_all_out_if_possible
    engine.choose_non_bomb_follow = arena_choose_non_bomb_follow

    def restore() -> None:
        engine.choose_all_out_if_possible = original_choose_all_out
        engine.choose_non_bomb_follow = original_choose_non_bomb_follow

    return restore


def offline_arena_action_type(cards: list[str], last_play: list[str], level: str) -> str:
    if not cards:
        return "None"
    infos = engine.safe_follow_infos(cards, last_play, level) if last_play else engine.recognize(cards, level)
    return infos[0].type if infos else "unknown"


def offline_baseline_equivalence_check(components: dict, profile_config: dict, sample_count: int = 200) -> dict:
    GuandanGame = components["GuandanGame"]
    rng = random.Random(20260704)
    states: list[dict] = []
    game_index = 0
    while len(states) < sample_count and game_index < sample_count * 2:
        random.seed(20260704 + game_index)
        game = GuandanGame(verbose=False, print_history=False)
        offline_set_random_first_player(game, rng)
        steps = 0
        while not game.is_game_over and steps < OFFLINE_MAX_GAME_STEPS and len(states) < sample_count:
            offline_prepare_turn(game)
            if game.current_player in game.ranking:
                steps += 1
                continue
            states.append(offline_arena_state_for_player(game, int(game.current_player)))
            action_info = offline_first_oracle_action_info(
                game,
                components,
                rng,
                policy="equivalence_sampler",
                fallback_reason="equivalence_sampling",
            )
            offline_apply_action(game, action_info)
            steps += 1
        game_index += 1

    original_actions: list[dict] = []
    for state in states:
        state_copy = json.loads(json.dumps(state, ensure_ascii=False))
        coord = choose_profiled_play(state_copy, "tempo_baseline", profile_config)
        original_actions.append(
            {
                "chosen_cards": engine.sort_cards(list(coord or []), state["level"]),
                "action_type": offline_arena_action_type(list(coord or []), list(state.get("last_play") or []), state["level"]),
                "is_pass": not bool(coord),
            }
        )

    restore = offline_install_arena_baseline_optimizations()
    optimized_actions: list[dict] = []
    try:
        for state in states:
            state_copy = json.loads(json.dumps(state, ensure_ascii=False))
            coord = choose_profiled_play(state_copy, "tempo_baseline", profile_config)
            optimized_actions.append(
                {
                    "chosen_cards": engine.sort_cards(list(coord or []), state["level"]),
                    "action_type": offline_arena_action_type(
                        list(coord or []),
                        list(state.get("last_play") or []),
                        state["level"],
                    ),
                    "is_pass": not bool(coord),
                }
            )
    finally:
        restore()

    mismatches: list[dict] = []
    for index, (state, original, optimized) in enumerate(zip(states, original_actions, optimized_actions)):
        if original == optimized:
            continue
        if len(mismatches) < 20:
            mismatches.append(
                {
                    "sample_index": index,
                    "level": state.get("level"),
                    "your_seat": state.get("your_seat"),
                    "hand_count": len(state.get("your_hand") or []),
                    "hand": state.get("your_hand"),
                    "last_play": state.get("last_play"),
                    "last_player": state.get("last_player"),
                    "hand_counts": state.get("hand_counts"),
                    "original": original,
                    "optimized": optimized,
                }
            )
    return {
        "baseline_equivalence_checked": True,
        "baseline_equivalence_samples": len(states),
        "baseline_equivalence_mismatch_count": sum(
            1 for original, optimized in zip(original_actions, optimized_actions) if original != optimized
        ),
        "baseline_equivalence_mismatches": mismatches,
    }


def run_offline_arena_eval(args: argparse.Namespace) -> None:
    if args.baseline_profile != "tempo_baseline":
        raise RuntimeError("offline arena currently only supports --baseline-profile tempo_baseline")
    if not args.candidate_actors:
        raise RuntimeError("--candidate-actors is required with --offline-arena-eval")
    components = offline_load_guandan_components()
    GuandanGame = components["GuandanGame"]
    device_info = offline_resolve_device(args.device)
    actor_paths = [Path(item.strip()) for item in args.candidate_actors.split(",") if item.strip()]
    missing = [str(path) for path in actor_paths if not path.exists()]
    if missing:
        raise RuntimeError(f"candidate actor checkpoint(s) not found: {', '.join(missing)}")
    profiles = load_json(PROFILE_PATH, {})
    profile_config = profiles.get("tempo_baseline", {"engine_mode": "tempo"})
    rng = random.Random(20260704)
    equivalence = offline_baseline_equivalence_check(components, profile_config, sample_count=200)
    top = {
        "backend": device_info["backend"],
        "requested_device": device_info["requested_device"],
        "actual_device": device_info["actual_device"],
        "device_fallback": device_info["device_fallback"],
        "torch_available": device_info["torch_available"],
        "cuda_available": device_info["cuda_available"],
        "legal_mask_source": "website_oracle",
        "local_player_mapping": offline_local_player_mapping(),
        "team_mapping": offline_team_mapping(),
        "first_player_policy": "random_each_game",
        "first_player_distribution": {"0": 0, "1": 0, "2": 0, "3": 0},
        "evaluated_checkpoints": len(actor_paths),
        "games_per_checkpoint": int(args.arena_games),
        "baseline_profile": args.baseline_profile,
        "seat_swap_enabled": bool(args.swap_seats),
        "rule_assisted_guard": bool(args.rule_assisted_guard),
        "guard_opponent_hand_threshold": int(args.guard_opponent_hand_threshold),
        "guard_critical_hand_threshold": int(args.guard_critical_hand_threshold),
        "guard_allow_minimal_bomb": bool(args.guard_allow_minimal_bomb),
        "checkpoint_results": [],
        "model_team_win_rate": 0.0,
        "baseline_team_win_rate": 0.0,
        "avg_game_length": 0.0,
        "illegal_action_count": 0,
        "fallback_count": 0,
        "hand_card_mismatch_count": 0,
        "materialization_fail_count": 0,
        "top_materialization_fail_reasons": [],
        "illegal_action_rate": 0.0,
        "fallback_rate": 0.0,
        "pass_rate": 0.0,
        "bomb_usage_rate": 0.0,
        "action_type_distribution": {},
        "best_checkpoint_by_win_rate": None,
        "allowed_for_shadow_eval": False,
        "allowed_for_website_dry_run": False,
        "concrete_failure_samples": [],
        "concrete_materialization_failure_samples": [],
        **offline_guard_empty_counts(),
        **equivalence,
    }
    if (
        int(equivalence["baseline_equivalence_samples"]) < 200
        or int(equivalence["baseline_equivalence_mismatch_count"]) != 0
    ):
        save_json(Path(args.arena_out), top)
        print(json.dumps(top, ensure_ascii=False, indent=2))
        raise RuntimeError("baseline equivalence check failed; arena eval blocked")
    restore_baseline = offline_install_arena_baseline_optimizations()
    aggregate_steps = 0
    aggregate_passes = 0
    aggregate_bombs = 0
    aggregate_game_length = 0
    aggregate_action_types: Counter = Counter()
    aggregate_materialization_reasons: Counter = Counter()
    aggregate_model_wins = 0
    aggregate_baseline_wins = 0
    for checkpoint_index, actor_path in enumerate(actor_paths):
        actor = offline_load_actor_checkpoint(actor_path, components, device_info)
        result = offline_arena_empty_result(str(actor_path))
        result_action_types: Counter = Counter()
        materialization_reasons: Counter = Counter()
        total_steps = 0
        total_passes = 0
        total_bombs = 0
        total_game_length = 0
        completed_index = 0
        max_attempts = max(int(args.arena_games) * 3, int(args.arena_games) + 10)
        while result["completed_games"] < int(args.arena_games) and result["attempted_games"] < max_attempts:
            game_seed = 20260704 + completed_index
            random.seed(game_seed)
            game = GuandanGame(verbose=False, print_history=False)
            first_player = offline_set_random_first_player(game, rng)
            result["first_player_distribution"][str(first_player)] += 1
            top["first_player_distribution"][str(first_player)] += 1
            model_seats, baseline_seats = offline_arena_profile_seats(
                completed_index,
                int(args.arena_games),
                bool(args.swap_seats),
            )
            model_team = offline_team_id(next(iter(model_seats)))
            steps = 0
            result["attempted_games"] += 1
            while not game.is_game_over and steps < OFFLINE_MAX_GAME_STEPS:
                offline_prepare_turn(game)
                if game.current_player in game.ranking:
                    steps += 1
                    continue
                if int(game.current_player) in model_seats:
                    action_info = offline_arena_model_action_info(
                        game,
                        components,
                        actor,
                        device_info["device"],
                        args.baseline_profile,
                        profile_config,
                        rng,
                    )
                    guard_counts = offline_guard_empty_counts()
                    if bool(args.rule_assisted_guard):
                        action_info, guard_counts = offline_rule_assisted_guard_action(
                            game,
                            components,
                            action_info,
                            args,
                            rng,
                        )
                        for key, value in guard_counts.items():
                            result[key] += int(value)
                elif int(game.current_player) in baseline_seats:
                    action_info = offline_baseline_action_info(
                        game,
                        components,
                        args.baseline_profile,
                        profile_config,
                        rng,
                    )
                else:
                    action_info = offline_first_oracle_action_info(
                        game,
                        components,
                        rng,
                        policy="unknown",
                        fallback_reason="seat_not_assigned",
                    )
                result["raw_legal_action_count"] += int(action_info.get("raw_legal_action_count") or 0)
                result["verified_legal_action_count"] += int(action_info.get("verified_legal_action_count") or 0)
                result["mask_combo_disagree_count"] += int(action_info.get("mask_combo_disagree_count") or 0)
                result["old_mask_disagree_count"] += int(action_info.get("old_mask_disagree_count") or 0)
                if action_info.get("illegal"):
                    result["illegal_action_count"] += 1
                if action_info.get("hand_card_mismatch"):
                    result["hand_card_mismatch_count"] += 1
                if action_info.get("materialization_fail"):
                    result["materialization_fail_count"] += 1
                    reason = str(action_info.get("materialization_fail_reason") or "unknown")
                    materialization_reasons[reason] += 1
                    if len(result["concrete_materialization_failure_samples"]) < 20:
                        result["concrete_materialization_failure_samples"].append(
                            {
                                "checkpoint": str(actor_path),
                                "game_index": completed_index,
                                "step": steps,
                                "current_player": int(game.current_player),
                                "first_player": first_player,
                                "action_id": action_info.get("action_id"),
                                "sampled_action_id": action_info.get("sampled_action_id"),
                                "action_type": action_info.get("action_type"),
                                "hand_before": action_info.get("hand_before"),
                                "chosen_cards": action_info.get("chosen_cards"),
                                "physical_cards": action_info.get("physical_cards"),
                                "missing_cards": action_info.get("missing_cards"),
                                "last_play": action_info.get("last_play"),
                                "reason": reason,
                                "model_failure_sample": action_info.get("model_failure_sample"),
                            }
                        )
                if action_info.get("fallback"):
                    result["fallback_count"] += 1
                    if len(result["concrete_failure_samples"]) < 20:
                        result["concrete_failure_samples"].append(
                            {
                                "checkpoint": str(actor_path),
                                "game_index": completed_index,
                                "step": steps,
                                "player_id": action_info.get("player_id"),
                                "fallback_reason": action_info.get("fallback_reason"),
                                "model_failure_sample": action_info.get("model_failure_sample"),
                                "chosen_cards": action_info.get("chosen_cards"),
                            }
                        )
                pre_apply_hand_mismatch = bool(action_info.get("hand_card_mismatch"))
                pre_apply_materialization_fail = bool(action_info.get("materialization_fail"))
                record = offline_apply_action(game, action_info)
                if record.get("hand_card_mismatch") and not pre_apply_hand_mismatch:
                    result["hand_card_mismatch_count"] += 1
                if record.get("materialization_fail") and not pre_apply_materialization_fail:
                    result["materialization_fail_count"] += 1
                    reason = str(record.get("materialization_fail_reason") or "unknown")
                    materialization_reasons[reason] += 1
                    if len(result["concrete_materialization_failure_samples"]) < 20:
                        result["concrete_materialization_failure_samples"].append(
                            {
                                "checkpoint": str(actor_path),
                                "game_index": completed_index,
                                "step": steps,
                                "current_player": int(record.get("player_id")),
                                "first_player": first_player,
                                "action_id": record.get("action_id"),
                                "sampled_action_id": record.get("sampled_action_id"),
                                "action_type": record.get("action_type"),
                                "hand_before": record.get("hand_before"),
                                "chosen_cards": record.get("chosen_cards"),
                                "physical_cards": record.get("physical_cards"),
                                "missing_cards": record.get("missing_cards"),
                                "last_play": record.get("last_play"),
                                "reason": reason,
                            }
                        )
                total_steps += 1
                steps += 1
                result_action_types[record["action_type"]] += 1
                if not record["chosen_cards"]:
                    total_passes += 1
                if record["is_bomb"]:
                    total_bombs += 1
            if not game.is_game_over:
                if len(result["concrete_failure_samples"]) < 20:
                    result["concrete_failure_samples"].append(
                        {
                            "checkpoint": str(actor_path),
                            "game_index": completed_index,
                            "failure": "max_steps_reached",
                            "steps": steps,
                            "ranking": list(game.ranking),
                        }
                    )
                continue
            result["completed_games"] += 1
            completed_index += 1
            total_game_length += steps
            winner_team = offline_winner_team_id(game)
            if winner_team == model_team:
                result["model_team_wins"] += 1
            else:
                result["baseline_team_wins"] += 1
        completed = max(1, int(result["completed_games"]))
        result["model_team_win_rate"] = result["model_team_wins"] / completed
        result["baseline_team_win_rate"] = result["baseline_team_wins"] / completed
        result["avg_game_length"] = total_game_length / completed
        result["illegal_action_rate"] = result["illegal_action_count"] / max(1, total_steps)
        result["fallback_rate"] = result["fallback_count"] / max(1, total_steps)
        result["pass_rate"] = total_passes / max(1, total_steps)
        result["bomb_usage_rate"] = total_bombs / max(1, total_steps)
        result["action_type_distribution"] = dict(result_action_types)
        result["top_materialization_fail_reasons"] = materialization_reasons.most_common(20)
        result["allowed_for_shadow_eval"] = (
            result["completed_games"] >= int(args.arena_games)
            and result["illegal_action_count"] == 0
            and result["hand_card_mismatch_count"] == 0
            and result["materialization_fail_count"] == 0
            and result["fallback_rate"] <= 0.01
            and result["model_team_win_rate"] >= 0.48
        )
        result["allowed_for_website_dry_run"] = (
            result["completed_games"] >= int(args.arena_games)
            and result["illegal_action_count"] == 0
            and result["hand_card_mismatch_count"] == 0
            and result["materialization_fail_count"] == 0
            and result["fallback_rate"] <= 0.01
            and result["model_team_win_rate"] >= 0.52
        )
        top["checkpoint_results"].append(result)
        top["illegal_action_count"] += int(result["illegal_action_count"])
        top["fallback_count"] += int(result["fallback_count"])
        top["hand_card_mismatch_count"] += int(result["hand_card_mismatch_count"])
        top["materialization_fail_count"] += int(result["materialization_fail_count"])
        for key in offline_guard_empty_counts():
            top[key] += int(result.get(key) or 0)
        aggregate_steps += total_steps
        aggregate_passes += total_passes
        aggregate_bombs += total_bombs
        aggregate_game_length += total_game_length
        aggregate_action_types.update(result_action_types)
        aggregate_materialization_reasons.update(dict(result["top_materialization_fail_reasons"]))
        aggregate_model_wins += int(result["model_team_wins"])
        aggregate_baseline_wins += int(result["baseline_team_wins"])
        for sample in result["concrete_failure_samples"]:
            if len(top["concrete_failure_samples"]) < 50:
                top["concrete_failure_samples"].append(sample)
        for sample in result["concrete_materialization_failure_samples"]:
            if len(top["concrete_materialization_failure_samples"]) < 50:
                top["concrete_materialization_failure_samples"].append(sample)
        save_json(Path(args.arena_out), top)
        del actor
        if device_info["torch"] is not None and device_info["actual_device"] == "cuda":
            device_info["torch"].cuda.empty_cache()
    total_completed = max(1, sum(int(item["completed_games"]) for item in top["checkpoint_results"]))
    top["model_team_win_rate"] = aggregate_model_wins / total_completed
    top["baseline_team_win_rate"] = aggregate_baseline_wins / total_completed
    top["avg_game_length"] = aggregate_game_length / total_completed
    top["illegal_action_rate"] = top["illegal_action_count"] / max(1, aggregate_steps)
    top["fallback_rate"] = top["fallback_count"] / max(1, aggregate_steps)
    top["pass_rate"] = aggregate_passes / max(1, aggregate_steps)
    top["bomb_usage_rate"] = aggregate_bombs / max(1, aggregate_steps)
    top["action_type_distribution"] = dict(aggregate_action_types)
    top["top_materialization_fail_reasons"] = aggregate_materialization_reasons.most_common(20)
    best = max(top["checkpoint_results"], key=lambda item: item["model_team_win_rate"], default=None)
    if best:
        top["best_checkpoint_by_win_rate"] = {
            "checkpoint": best["checkpoint"],
            "model_team_win_rate": best["model_team_win_rate"],
        }
        top["allowed_for_shadow_eval"] = bool(best["allowed_for_shadow_eval"])
        top["allowed_for_website_dry_run"] = bool(best["allowed_for_website_dry_run"])
    save_json(Path(args.arena_out), top)
    restore_baseline()
    print(json.dumps(top, ensure_ascii=False, indent=2))


def arena_diagnosis_phase(hand_counts: list[int]) -> str:
    if min(hand_counts or [27]) <= 5:
        return "endgame"
    if sum(hand_counts or [108]) <= 54:
        return "midgame"
    return "early"


def arena_diagnosis_rate_dict(counter: Counter, denominator: Counter) -> dict:
    phases = sorted(set(counter) | set(denominator) | {"early", "midgame", "endgame"})
    return {phase: counter[phase] / max(1, denominator[phase]) for phase in phases}


def arena_diagnosis_action_distribution(decisions: list[dict], team_id: int) -> dict:
    counts: Counter = Counter()
    for decision in decisions[-10:]:
        if int(decision.get("team", -1)) == team_id:
            counts[str(decision.get("action_type") or "unknown")] += 1
    return dict(counts)


def corrective_casebook_tags(value: str | None) -> set[str]:
    if not value:
        return set()
    return {item.strip() for item in value.split(",") if item.strip()}


def corrective_cards_to_local(cards: list[str]) -> list[str]:
    if not cards:
        return []
    if all(isinstance(card, str) and (card in {"B", "R"} or re.fullmatch(r"[SHDC][2-9TJQKA]", card)) for card in cards):
        return website_cards_to_local(cards)
    return list(cards)


def corrective_case_to_game(case: dict, components: dict) -> Any:
    GuandanGame = components["GuandanGame"]
    game = GuandanGame(verbose=False, print_history=False)
    player_id = int(case.get("current_player", 0))
    hand_counts = list(case.get("remaining_hand_sizes") or [27, 27, 27, 27])
    hand_counts = (hand_counts + [27, 27, 27, 27])[:4]
    hand_before = list(case.get("hand_before") or [])
    game.current_player = player_id
    game.active_level = website_level_to_local_level(str(case.get("level") or "2"))
    for seat, player in enumerate(game.players):
        if seat == player_id:
            player.hand = list(hand_before)
        else:
            player.hand = ["小王"] * max(0, int(hand_counts[seat]))
        player.played_cards = []
        player.last_played_cards = []
    last_play = list(case.get("last_play") or [])
    game.last_play = list(last_play) if last_play else None
    game.last_player = case.get("last_player")
    game.is_free_turn = not bool(last_play)
    game.pass_count = 0
    game.jiefeng = False
    game.recent_actions = [["None"], ["None"], ["None"], ["None"]]
    game.history = []
    game.ranking = []
    game.is_game_over = False
    return game


def corrective_action_sort_key(components: dict, action_id: int, cards: list[str]) -> tuple:
    action = components["action_by_id"].get(int(action_id), {})
    is_bomb = offline_action_is_bomb(action)
    return (
        1 if is_bomb else 0,
        len(cards),
        int(action.get("logic_point") or 0),
        str(action.get("type") or ""),
        tuple(cards),
    )


def corrective_smallest_candidate(
    components: dict,
    candidates: list[tuple[int, list[str]]],
    allow_bomb: bool,
) -> tuple[int, list[str]] | None:
    usable: list[tuple[int, list[str]]] = []
    for action_id, cards in candidates:
        if not cards:
            continue
        action = components["action_by_id"].get(int(action_id), {})
        if offline_action_is_bomb(action) and not allow_bomb:
            continue
        usable.append((int(action_id), list(cards)))
    if not usable and allow_bomb:
        usable = [(int(action_id), list(cards)) for action_id, cards in candidates if cards]
    if not usable:
        return None
    return min(usable, key=lambda item: corrective_action_sort_key(components, item[0], item[1]))


def corrective_sample_from_case(case: dict, components: dict, source_casebook: str, include_tags: set[str]) -> tuple[dict | None, str | None]:
    tags = set(case.get("reason_tags") or [])
    if include_tags and not (tags & include_tags):
        return None, "reason_tag_not_selected"
    game = corrective_case_to_game(case, components)
    player_id = int(game.current_player)
    hand_before = list(game.players[player_id].hand)
    last_play_before = list(game.last_play or [])
    was_lead = bool(game.is_free_turn or not last_play_before)
    oracle, candidates = offline_oracle_candidates_fast(game, components, hand_before, last_play_before, was_lead)
    legal_mask = list(oracle["mask"])
    if len(legal_mask) != OFFLINE_ACTION_DIM:
        return None, "legal_mask_dim_mismatch"
    label_cards = corrective_cards_to_local(list(case.get("baseline_action_if_same_state") or []))
    label_action_id: int | None = None
    if label_cards:
        ok, _reason = offline_action_is_legal(
            game,
            components["actions"],
            label_cards,
            hand_before,
            last_play_before,
            was_lead,
        )
        if ok:
            mapped = offline_action_id_for_cards(game, components, label_cards, last_play_before, was_lead)
            if mapped is not None and 0 <= int(mapped) < OFFLINE_ACTION_DIM and float(legal_mask[int(mapped)]) > 0:
                label_action_id = int(mapped)
    if label_action_id is None and not label_cards and case.get("can_beat") and not case.get("model_physical_cards"):
        allow_bomb = bool({"missed_opponent_block", "missed_bomb_block"} & tags)
        selected = corrective_smallest_candidate(components, candidates, allow_bomb=allow_bomb)
        if selected is not None:
            label_action_id, label_cards = selected
    if label_action_id is None or not label_cards:
        return None, "no_legal_corrective_label"
    if not offline_cards_in_hand(label_cards, hand_before):
        return None, "label_cards_not_in_hand"
    if not 0 <= int(label_action_id) < OFFLINE_ACTION_DIM or float(legal_mask[int(label_action_id)]) <= 0:
        return None, "label_action_not_in_mask"
    obs = game._get_obs()
    obs_list = obs.tolist() if hasattr(obs, "tolist") else list(obs)
    if len(obs_list) != OFFLINE_STATE_DIM:
        return None, "obs_dim_mismatch"
    action_struct = components["action_by_id"].get(int(label_action_id))
    sample = {
        "obs": obs_list,
        "legal_mask": legal_mask,
        "teacher_action_id": int(label_action_id),
        "teacher_chosen_cards": list(label_cards),
        "teacher_chosen_cards_website": local_cards_to_website(list(label_cards)),
        "action_type": str((action_struct or {}).get("type") or "unknown"),
        "current_player": player_id,
        "hand_size_by_player": [len(player.hand) for player in game.players],
        "last_play": last_play_before,
        "last_play_website": local_cards_to_website(last_play_before),
        "active_level": int(game.active_level),
        "level": website_level_from_local_level(game.active_level),
        "was_lead": was_lead,
        "was_follow": not was_lead,
        "is_corrective": True,
        "corrective_action_id": int(label_action_id),
        "corrective_physical_cards": list(label_cards),
        "original_model_action_id": case.get("model_action_id"),
        "original_model_physical_cards": list(case.get("model_physical_cards") or []),
        "reason_tags": sorted(tags),
        "weight": 1.0,
        "source_casebook": source_casebook,
        "source_game_id": case.get("game_id"),
        "source_turn": case.get("turn"),
    }
    return sample, None


def arena_diagnosis_baseline_for_case(case: dict, profile_config: dict, baseline_profile: str) -> tuple[list[str], str]:
    level = str(case.get("level") or "2")
    hand = local_cards_to_website(list(case.get("hand_before") or []))
    last_play = local_cards_to_website(list(case.get("last_play") or []))
    player_id = int(case.get("current_player", 0))
    hand_counts = list(case.get("remaining_hand_sizes") or [27, 27, 27, 27])
    state = {
        "level": level,
        "your_hand": hand,
        "last_play": last_play,
        "last_player": case.get("last_player"),
        "current_turn": player_id,
        "your_seat": player_id,
        "your_team": offline_team_id(player_id),
        "is_your_turn": True,
        "completed": False,
        "seats": [f"diagnosis_{seat}" for seat in range(4)],
        "teams": {str(seat): offline_team_id(seat) for seat in range(4)},
        "hand_counts": hand_counts,
        "ranking": [],
        "trick_history": [],
        "left_time": None,
    }
    coord = choose_profiled_play(state, baseline_profile, profile_config)
    cards = list(coord or [])
    return cards, offline_arena_action_type(cards, last_play, level)


def arena_diagnosis_decision_case(
    game_id: int,
    turn: int,
    game: Any,
    components: dict,
    model_info: dict,
    baseline_info: dict,
    candidates: list[tuple[int, list[str]]],
) -> dict:
    player_id = int(model_info.get("player_id"))
    hand_counts = [len(player.hand) for player in game.players]
    teammate = offline_teammate(player_id)
    opponent_counts = [hand_counts[player] for player in (1, 3)]
    teammate_remaining = hand_counts[teammate]
    opponent_min = min(opponent_counts)
    was_follow = bool(model_info.get("was_follow"))
    was_lead = bool(model_info.get("was_lead"))
    non_pass_candidates = [(action_id, cards) for action_id, cards in candidates if cards]
    can_beat = bool(was_follow and non_pass_candidates)
    bomb_candidates = [
        (action_id, cards)
        for action_id, cards in candidates
        if offline_action_is_bomb(components["action_by_id"].get(int(action_id)))
    ]
    model_cards = list(model_info.get("chosen_cards") or [])
    model_type = str(model_info.get("action_type") or "unknown")
    model_is_pass = not bool(model_cards)
    model_is_bomb = bool(model_info.get("is_bomb"))
    model_rank = model_info.get("action_rank")
    try:
        rank_value = int(model_rank) if model_rank is not None else 0
    except (TypeError, ValueError):
        rank_value = 0
    weak_lead = bool(was_lead and model_cards and len(model_cards) <= 2 and rank_value <= 11 and opponent_min <= 8)
    wasted_bomb = bool(model_is_bomb and opponent_min > 6 and len(model_info.get("hand_before") or []) - len(model_cards) > 5)
    missed_bomb_block = bool(was_follow and opponent_min <= 3 and bomb_candidates and not model_is_bomb)
    bad_endgame = bool(opponent_min <= 5 and ((model_is_pass and can_beat) or weak_lead or wasted_bomb))
    missed_teammate_support = bool(
        teammate_remaining <= 3
        and (model_is_pass or (was_lead and len(model_cards) not in (teammate_remaining, 1)))
    )
    missed_opponent_block = bool(opponent_min <= 3 and ((model_is_pass and can_beat) or missed_bomb_block))
    over_passive_follow = bool(was_follow and model_is_pass and can_beat and opponent_min <= 8)
    over_aggressive_split = bool(
        model_type in {"straight", "three_with_pair", "pair_chain", "gangban", "flush_rocket"}
        and opponent_min <= 6
        and len(model_info.get("hand_before") or []) > 8
    )
    reason_tags: list[str] = []
    if model_is_pass and can_beat:
        reason_tags.append("pass_when_can_beat")
    if missed_bomb_block:
        reason_tags.append("missed_bomb_block")
    if wasted_bomb:
        reason_tags.append("wasted_bomb")
    if weak_lead:
        reason_tags.append("weak_lead")
    if bad_endgame:
        reason_tags.append("bad_endgame")
    if missed_teammate_support:
        reason_tags.append("missed_teammate_support")
    if missed_opponent_block:
        reason_tags.append("missed_opponent_block")
    if over_passive_follow:
        reason_tags.append("over_passive_follow")
    if over_aggressive_split:
        reason_tags.append("over_aggressive_split")
    return {
        "game_id": game_id,
        "turn": turn,
        "current_player": player_id,
        "team": offline_team_id(player_id),
        "level": website_level_from_local_level(game.active_level),
        "hand_before": list(model_info.get("hand_before") or []),
        "last_play": list(model_info.get("last_play") or []),
        "last_player": game.last_player,
        "legal_options_count": len(candidates),
        "model_action_id": model_info.get("action_id"),
        "model_physical_cards": model_cards,
        "model_action_type": model_type,
        "baseline_action_if_same_state": list(baseline_info.get("chosen_cards") or []),
        "baseline_action_type_if_same_state": str(baseline_info.get("action_type") or "unknown"),
        "can_beat": can_beat,
        "reason_tags": reason_tags,
        "remaining_hand_sizes": hand_counts,
        "winner_team": None,
        "_diagnosis": {
            "phase": arena_diagnosis_phase(hand_counts),
            "bomb_available": bool(bomb_candidates),
            "model_is_bomb": model_is_bomb,
            "model_is_pass": model_is_pass,
            "opponent_min_remaining": opponent_min,
            "teammate_remaining": teammate_remaining,
            "was_follow": was_follow,
            "was_lead": was_lead,
        },
    }


def run_arena_loss_diagnosis(args: argparse.Namespace) -> None:
    if args.diagnosis_baseline_profile != "tempo_baseline":
        raise RuntimeError("arena loss diagnosis currently only supports --diagnosis-baseline-profile tempo_baseline")
    actor_path = Path(args.diagnosis_candidate_actor)
    if not actor_path.exists():
        raise RuntimeError(f"diagnosis candidate actor not found: {actor_path}")
    components = offline_load_guandan_components()
    GuandanGame = components["GuandanGame"]
    device_info = offline_resolve_device(args.device)
    actor = offline_load_actor_checkpoint(actor_path, components, device_info)
    profiles = load_json(PROFILE_PATH, {})
    profile_config = profiles.get("tempo_baseline", {"engine_mode": "tempo"})
    rng = random.Random(20260706)
    restore_baseline = offline_install_arena_baseline_optimizations()
    result = {
        "backend": device_info["backend"],
        "requested_device": device_info["requested_device"],
        "actual_device": device_info["actual_device"],
        "device_fallback": device_info["device_fallback"],
        "legal_mask_source": "website_oracle",
        "candidate_actor": str(actor_path),
        "baseline_profile": args.diagnosis_baseline_profile,
        "diagnosis_games": int(args.diagnosis_games),
        "completed_games": 0,
        "model_team_wins": 0,
        "baseline_team_wins": 0,
        "model_team_win_rate": 0.0,
        "loss_games": 0,
        "pass_when_can_beat_count": 0,
        "pass_when_can_beat_rate": 0.0,
        "bomb_available_but_not_used_count": 0,
        "bomb_used_count": 0,
        "bomb_waste_suspect_count": 0,
        "lead_low_value_combo_count": 0,
        "endgame_bad_decision_count": 0,
        "teammate_about_to_win_support_miss_count": 0,
        "opponent_about_to_win_block_miss_count": 0,
        "hand_size_le_5_decision_count": 0,
        "hand_size_le_3_decision_count": 0,
        "model_last_10_turns_action_distribution": {},
        "baseline_last_10_turns_action_distribution": {},
        "model_pass_rate_by_phase": {},
        "model_bomb_usage_by_phase": {},
        "baseline_bomb_usage_by_phase": {},
        "reason_tag_counts": {},
        "illegal_action_count": 0,
        "fallback_count": 0,
        "hand_card_mismatch_count": 0,
        "materialization_fail_count": 0,
        "mask_combo_disagree_count": 0,
        "casebook_path": args.diagnosis_save_casebook,
    }
    casebook = {
        "candidate_actor": str(actor_path),
        "baseline_profile": args.diagnosis_baseline_profile,
        "games": int(args.diagnosis_games),
        "loss_games": [],
        "failure_cases": [],
    }
    model_phase_seen: Counter = Counter()
    model_phase_pass: Counter = Counter()
    model_phase_bomb: Counter = Counter()
    baseline_phase_seen: Counter = Counter()
    baseline_phase_bomb: Counter = Counter()
    model_last10_dist: Counter = Counter()
    baseline_last10_dist: Counter = Counter()
    reason_counts: Counter = Counter()
    follow_can_beat_seen = 0
    try:
        for game_index in range(1, int(args.diagnosis_games) + 1):
            game = GuandanGame(verbose=False, print_history=False)
            offline_set_random_first_player(game, rng)
            turn = 0
            game_decisions: list[dict] = []
            game_model_cases: list[dict] = []
            while not game.is_game_over and turn < OFFLINE_MAX_GAME_STEPS:
                offline_prepare_turn(game)
                if game.current_player in game.ranking:
                    turn += 1
                    continue
                player_id = int(game.current_player)
                hand_before = list(game.players[player_id].hand)
                last_play_before = list(game.last_play or [])
                was_lead = bool(game.is_free_turn or not last_play_before)
                hand_counts_before = [len(player.hand) for player in game.players]
                phase = arena_diagnosis_phase(hand_counts_before)
                if player_id in (0, 2):
                    _oracle, candidates = offline_oracle_candidates_fast(
                        game,
                        components,
                        hand_before,
                        last_play_before,
                        was_lead,
                    )
                    action_info = offline_select_action_fast(
                        game,
                        components,
                        actor=actor,
                        device=device_info["device"],
                        rng=rng,
                    )
                    case = arena_diagnosis_decision_case(
                        game_index,
                        turn,
                        game,
                        components,
                        action_info,
                        {"chosen_cards": [], "action_type": "not_evaluated"},
                        candidates,
                    )
                    game_model_cases.append(case)
                else:
                    action_info = offline_baseline_action_info(
                        game,
                        components,
                        args.diagnosis_baseline_profile,
                        profile_config,
                        rng,
                    )
                record = offline_apply_action(game, action_info)
                if record.get("illegal"):
                    result["illegal_action_count"] += 1
                if record.get("fallback"):
                    result["fallback_count"] += 1
                if record.get("materialization_fail"):
                    result["materialization_fail_count"] += 1
                if record.get("hand_card_mismatch"):
                    result["hand_card_mismatch_count"] += 1
                result["mask_combo_disagree_count"] += int(record.get("mask_combo_disagree_count") or 0)
                game_decisions.append(
                    {
                        "turn": turn,
                        "player": player_id,
                        "team": offline_team_id(player_id),
                        "action_type": str(record.get("action_type") or "unknown"),
                        "is_bomb": bool(record.get("is_bomb")),
                        "is_pass": not bool(record.get("chosen_cards")),
                        "phase": phase,
                    }
                )
                turn += 1
            if not game.is_game_over:
                continue
            result["completed_games"] += 1
            winner_team = offline_winner_team_id(game)
            if winner_team == 0:
                result["model_team_wins"] += 1
                continue
            result["baseline_team_wins"] += 1
            result["loss_games"] += 1
            for case in game_model_cases:
                case["winner_team"] = winner_team
                diag = case.pop("_diagnosis", {})
                phase = str(diag.get("phase") or "unknown")
                model_phase_seen[phase] += 1
                if diag.get("model_is_pass"):
                    model_phase_pass[phase] += 1
                if diag.get("model_is_bomb"):
                    model_phase_bomb[phase] += 1
                    result["bomb_used_count"] += 1
                if diag.get("was_follow") and case.get("can_beat"):
                    follow_can_beat_seen += 1
                if diag.get("bomb_available") and not diag.get("model_is_bomb"):
                    result["bomb_available_but_not_used_count"] += 1
                if len(case.get("hand_before") or []) <= 5:
                    result["hand_size_le_5_decision_count"] += 1
                if len(case.get("hand_before") or []) <= 3:
                    result["hand_size_le_3_decision_count"] += 1
                tags = list(case.get("reason_tags") or [])
                reason_counts.update(tags)
                if "pass_when_can_beat" in tags:
                    result["pass_when_can_beat_count"] += 1
                if "wasted_bomb" in tags:
                    result["bomb_waste_suspect_count"] += 1
                if "weak_lead" in tags:
                    result["lead_low_value_combo_count"] += 1
                if "bad_endgame" in tags:
                    result["endgame_bad_decision_count"] += 1
                if "missed_teammate_support" in tags:
                    result["teammate_about_to_win_support_miss_count"] += 1
                if "missed_opponent_block" in tags:
                    result["opponent_about_to_win_block_miss_count"] += 1
                if tags:
                    baseline_cards, baseline_type = arena_diagnosis_baseline_for_case(
                        case,
                        profile_config,
                        args.diagnosis_baseline_profile,
                    )
                    case["baseline_action_if_same_state"] = baseline_cards
                    case["baseline_action_type_if_same_state"] = baseline_type
                    casebook["failure_cases"].append(case)
            for decision in game_decisions:
                phase = str(decision.get("phase") or "unknown")
                if int(decision.get("team", -1)) == 1:
                    baseline_phase_seen[phase] += 1
                    if decision.get("is_bomb"):
                        baseline_phase_bomb[phase] += 1
            model_last10_dist.update(arena_diagnosis_action_distribution(game_decisions, 0))
            baseline_last10_dist.update(arena_diagnosis_action_distribution(game_decisions, 1))
            casebook["loss_games"].append(
                {
                    "game_id": game_index,
                    "winner_team": winner_team,
                    "ranking": list(game.ranking),
                    "last_10_decisions": game_decisions[-10:],
                    "failure_case_count": sum(1 for case in game_model_cases if case.get("reason_tags")),
                }
            )
    finally:
        restore_baseline()
    completed = max(1, int(result["completed_games"]))
    result["model_team_win_rate"] = result["model_team_wins"] / completed
    result["pass_when_can_beat_rate"] = result["pass_when_can_beat_count"] / max(1, follow_can_beat_seen)
    result["model_last_10_turns_action_distribution"] = dict(model_last10_dist)
    result["baseline_last_10_turns_action_distribution"] = dict(baseline_last10_dist)
    result["model_pass_rate_by_phase"] = arena_diagnosis_rate_dict(model_phase_pass, model_phase_seen)
    result["model_bomb_usage_by_phase"] = arena_diagnosis_rate_dict(model_phase_bomb, model_phase_seen)
    result["baseline_bomb_usage_by_phase"] = arena_diagnosis_rate_dict(baseline_phase_bomb, baseline_phase_seen)
    result["reason_tag_counts"] = dict(reason_counts)
    result["failure_case_count"] = len(casebook["failure_cases"])
    save_json(Path(args.diagnosis_out), result)
    save_json(Path(args.diagnosis_save_casebook), casebook)
    print(json.dumps(result, ensure_ascii=False, indent=2))


def imitation_dataset_format(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix == ".jsonl":
        return "jsonl"
    if suffix in {".pt", ".pth"}:
        return "torch"
    raise RuntimeError("imitation dataset path must end with .jsonl, .pt, or .pth")


def imitation_sample_from_teacher_action(
    game: Any,
    components: dict,
    teacher_profile: str,
    profile_config: dict,
    first_player: int,
) -> tuple[dict | None, dict, dict]:
    player_id = int(game.current_player)
    hand_before = list(game.players[player_id].hand)
    last_play_before = list(game.last_play or [])
    was_lead = bool(game.is_free_turn or not last_play_before)
    obs = game._get_obs()
    oracle = offline_oracle_legal_mask(
        game,
        components,
        player_id,
        hand_before,
        last_play_before,
        game.active_level,
    )
    legal_mask = list(oracle["mask"])
    state = offline_arena_state_for_player(game, player_id)
    coord = choose_profiled_play(state, teacher_profile, profile_config)
    teacher_cards = website_cards_to_local(list(coord or []))
    ok, illegal_reason = offline_action_is_legal(
        game,
        components["actions"],
        teacher_cards,
        hand_before,
        last_play_before,
        was_lead,
    )
    action_id = offline_action_id_for_cards(game, components, teacher_cards, last_play_before, was_lead) if ok else None
    mapping_failed = ok and action_id is None
    action_in_range = action_id is not None and 0 <= int(action_id) < OFFLINE_ACTION_DIM
    action_in_mask = bool(action_in_range and float(legal_mask[int(action_id)]) > 0)
    action_struct = components["action_by_id"].get(int(action_id)) if action_in_range else None
    if action_id == 0:
        action_struct = {"type": "None", "points": [], "logic_point": 0, "id": 0}
    failure = {
        "player_id": player_id,
        "first_player": first_player,
        "level": website_level_from_local_level(game.active_level),
        "hand_size_by_player": [len(player.hand) for player in game.players],
        "last_play": last_play_before,
        "last_play_website": local_cards_to_website(last_play_before),
        "teacher_chosen_cards": teacher_cards,
        "teacher_chosen_cards_website": list(coord or []),
        "teacher_action_id": action_id,
        "illegal_reason": illegal_reason,
        "mapping_failed": mapping_failed,
        "action_in_mask": action_in_mask,
    }
    if not ok or mapping_failed or not action_in_mask:
        return None, failure, {
            "chosen_cards": teacher_cards,
            "illegal": not ok,
            "mapping_failed": mapping_failed,
            "action_in_mask": action_in_mask,
        }
    sample = {
        "obs": obs.tolist() if hasattr(obs, "tolist") else list(obs),
        "legal_mask": legal_mask,
        "teacher_action_id": int(action_id),
        "teacher_chosen_cards": teacher_cards,
        "teacher_chosen_cards_website": list(coord or []),
        "action_type": str((action_struct or {}).get("type") or "unknown"),
        "current_player": player_id,
        "first_player": first_player,
        "hand_size_by_player": [len(player.hand) for player in game.players],
        "last_play": last_play_before,
        "last_play_website": local_cards_to_website(last_play_before),
        "active_level": int(game.active_level),
        "level": website_level_from_local_level(game.active_level),
        "was_lead": was_lead,
        "was_follow": not was_lead,
    }
    return sample, failure, {
        "chosen_cards": teacher_cards,
        "illegal": False,
        "mapping_failed": False,
        "action_in_mask": True,
    }


def write_imitation_dataset(path: Path, dataset_format: str, samples: list[dict], summary: dict) -> None:
    if dataset_format == "jsonl":
        with path.open("w", encoding="utf-8") as handle:
            for sample in samples:
                handle.write(json.dumps(sample, ensure_ascii=False, separators=(",", ":")) + "\n")
        save_json(Path(str(path) + ".summary.json"), summary)
        return
    torch = offline_resolve_device("cpu")["torch"]
    if torch is None:
        raise RuntimeError("torch is required to write .pt/.pth imitation datasets")
    torch.save({"format": "imitation_dataset_v1", "summary": summary, "samples": samples}, path)


def imitation_dataset_worker(worker_id: int, target_count: int, teacher_profile: str, profile_config: dict) -> dict:
    components = offline_load_guandan_components()
    GuandanGame = components["GuandanGame"]
    restore_baseline = offline_install_arena_baseline_optimizations()
    rng = random.Random(20260705 + worker_id * 100_000)
    samples: list[dict] = []
    first_player_distribution = {"0": 0, "1": 0, "2": 0, "3": 0}
    action_type_counts: Counter = Counter()
    failures: list[dict] = []
    mapping_fail_count = 0
    illegal_count = 0
    attempted = 0
    completed_games = 0
    try:
        game_index = 0
        while len(samples) < target_count:
            random.seed(20260705 + worker_id * 1_000_000 + game_index)
            game = GuandanGame(verbose=False, print_history=False)
            first_player = offline_set_random_first_player(game, rng)
            first_player_distribution[str(first_player)] += 1
            steps = 0
            while not game.is_game_over and steps < OFFLINE_MAX_GAME_STEPS and len(samples) < target_count:
                offline_prepare_turn(game)
                if game.current_player in game.ranking:
                    steps += 1
                    continue
                sample, failure, apply_meta = imitation_sample_from_teacher_action(
                    game,
                    components,
                    teacher_profile,
                    profile_config,
                    first_player,
                )
                attempted += 1
                if sample is None:
                    if apply_meta.get("mapping_failed"):
                        mapping_fail_count += 1
                    if apply_meta.get("illegal") or not apply_meta.get("action_in_mask"):
                        illegal_count += 1
                    if len(failures) < 20:
                        failure["worker_id"] = worker_id
                        failures.append(failure)
                    action_info = offline_first_oracle_action_info(
                        game,
                        components,
                        rng,
                        policy="teacher_fallback",
                        fallback_reason="teacher_action_invalid",
                    )
                else:
                    samples.append(sample)
                    action_type_counts[sample["action_type"]] += 1
                    action_info = offline_make_action_info_from_cards(
                        game,
                        components,
                        list(sample["teacher_chosen_cards"]),
                        rng,
                        policy="teacher",
                        sampled_action_id=int(sample["teacher_action_id"]),
                        audit_masks=False,
                    )
                offline_apply_action(game, action_info)
                steps += 1
            if game.is_game_over:
                completed_games += 1
            game_index += 1
    finally:
        restore_baseline()
    return {
        "worker_id": worker_id,
        "samples": samples,
        "attempted_teacher_decisions": attempted,
        "completed_games": completed_games,
        "first_player_distribution": first_player_distribution,
        "teacher_mapping_fail_count": mapping_fail_count,
        "teacher_illegal_count": illegal_count,
        "action_type_distribution": dict(action_type_counts),
        "concrete_teacher_failure_samples": failures,
    }


def imitation_worker_targets(total: int, worker_count: int) -> list[int]:
    base = total // worker_count
    remainder = total % worker_count
    return [base + (1 if idx < remainder else 0) for idx in range(worker_count)]


def run_generate_imitation_dataset(args: argparse.Namespace) -> None:
    if args.teacher_profile != "tempo_baseline":
        raise RuntimeError("only --teacher-profile tempo_baseline is supported for imitation dataset generation")
    components = offline_load_guandan_components()
    GuandanGame = components["GuandanGame"]
    device_info = offline_resolve_device(args.device)
    dataset_path = Path(args.imitation_dataset_out)
    dataset_format = imitation_dataset_format(dataset_path)
    profiles = load_json(PROFILE_PATH, {})
    profile_config = profiles.get("tempo_baseline", {"engine_mode": "tempo"})
    equivalence = offline_baseline_equivalence_check(components, profile_config, sample_count=200)
    summary = {
        "backend": device_info["backend"],
        "requested_device": device_info["requested_device"],
        "actual_device": device_info["actual_device"],
        "device_fallback": device_info["device_fallback"],
        "torch_available": device_info["torch_available"],
        "cuda_available": device_info["cuda_available"],
        "dataset_format": dataset_format,
        "legal_mask_source": "website_oracle",
        "local_player_mapping": offline_local_player_mapping(),
        "team_mapping": offline_team_mapping(),
        "first_player_policy": "random_each_game",
        "first_player_distribution": {"0": 0, "1": 0, "2": 0, "3": 0},
        "teacher_profile": args.teacher_profile,
        "target_teacher_decisions": int(args.target_teacher_decisions),
        "collected_teacher_decisions": 0,
        "completed_games": 0,
        "teacher_mapping_fail_count": 0,
        "teacher_mapping_fail_rate": 0.0,
        "teacher_illegal_count": 0,
        "teacher_illegal_rate": 0.0,
        "action_type_distribution": {},
        "concrete_teacher_failure_samples": [],
        "threshold_passed": False,
        **equivalence,
    }
    if (
        int(equivalence["baseline_equivalence_samples"]) < 200
        or int(equivalence["baseline_equivalence_mismatch_count"]) != 0
    ):
        save_json(Path(str(dataset_path) + ".summary.json"), summary)
        raise RuntimeError("baseline equivalence check failed; imitation dataset generation blocked")

    samples: list[dict] = []
    action_type_counts: Counter = Counter()
    attempted_teacher_decisions = 0
    import concurrent.futures

    worker_count = min(max(1, os.cpu_count() or 1), 8, max(1, int(args.target_teacher_decisions) // 500))
    targets = imitation_worker_targets(int(args.target_teacher_decisions), worker_count)
    with concurrent.futures.ProcessPoolExecutor(max_workers=worker_count) as executor:
        futures = [
            executor.submit(imitation_dataset_worker, worker_id, target, args.teacher_profile, profile_config)
            for worker_id, target in enumerate(targets)
            if target > 0
        ]
        for future in concurrent.futures.as_completed(futures):
            result = future.result()
            samples.extend(result["samples"])
            attempted_teacher_decisions += int(result["attempted_teacher_decisions"])
            summary["completed_games"] += int(result["completed_games"])
            summary["teacher_mapping_fail_count"] += int(result["teacher_mapping_fail_count"])
            summary["teacher_illegal_count"] += int(result["teacher_illegal_count"])
            for key, value in result["first_player_distribution"].items():
                summary["first_player_distribution"][str(key)] += int(value)
            action_type_counts.update(result["action_type_distribution"])
            for failure in result["concrete_teacher_failure_samples"]:
                if len(summary["concrete_teacher_failure_samples"]) < 20:
                    summary["concrete_teacher_failure_samples"].append(failure)
    summary["collected_teacher_decisions"] = len(samples)
    summary["teacher_mapping_fail_rate"] = summary["teacher_mapping_fail_count"] / max(1, attempted_teacher_decisions)
    summary["teacher_illegal_rate"] = summary["teacher_illegal_count"] / max(1, attempted_teacher_decisions)
    summary["action_type_distribution"] = dict(action_type_counts)
    summary["threshold_passed"] = (
        summary["collected_teacher_decisions"] >= int(args.target_teacher_decisions)
        and summary["teacher_mapping_fail_rate"] <= float(args.max_teacher_mapping_fail_rate)
        and summary["teacher_illegal_rate"] <= float(args.max_illegal_rate)
    )
    write_imitation_dataset(dataset_path, dataset_format, samples, summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    if not summary["threshold_passed"]:
        raise RuntimeError("imitation dataset thresholds failed")


def run_build_corrective_dataset(args: argparse.Namespace) -> None:
    components = offline_load_guandan_components()
    base_path = Path(args.base_imitation_dataset)
    base_samples, base_summary, _base_format = load_imitation_dataset(base_path)
    include_tags = corrective_casebook_tags(args.include_reason_tags)
    casebook_paths = [Path(item.strip()) for item in str(args.corrective_casebooks or "").split(",") if item.strip()]
    if not casebook_paths:
        raise RuntimeError("--corrective-casebooks is required with --build-corrective-dataset")
    missing = [str(path) for path in casebook_paths if not path.exists()]
    if missing:
        raise RuntimeError(f"corrective casebook(s) not found: {', '.join(missing)}")
    corrective_unique: list[dict] = []
    reject_reasons: Counter = Counter()
    reason_counts: Counter = Counter()
    processed_cases = 0
    for path in casebook_paths:
        payload = load_json(path, {})
        for case in payload.get("failure_cases") or []:
            processed_cases += 1
            sample, reject_reason = corrective_sample_from_case(case, components, str(path), include_tags)
            if sample is None:
                reject_reasons[str(reject_reason or "unknown")] += 1
                continue
            corrective_unique.append(sample)
            reason_counts.update(sample.get("reason_tags") or [])
    oversample_factor = max(1, int(args.casebook_oversample_factor))
    corrective_samples: list[dict] = []
    for sample in corrective_unique:
        for _copy_index in range(oversample_factor):
            copied = dict(sample)
            copied["weight"] = float(sample.get("weight", 1.0))
            corrective_samples.append(copied)
    merged_samples = list(base_samples) + corrective_samples
    summary = {
        "format": "corrective_dataset_v1",
        "base_dataset": str(base_path),
        "base_sample_count": len(base_samples),
        "base_summary": {
            "legal_mask_source": base_summary.get("legal_mask_source"),
            "sample_count": base_summary.get("sample_count") or len(base_samples),
        },
        "casebooks": [str(path) for path in casebook_paths],
        "processed_failure_cases": processed_cases,
        "corrective_unique_count": len(corrective_unique),
        "casebook_oversample_factor": oversample_factor,
        "corrective_sample_count": len(corrective_samples),
        "merged_sample_count": len(merged_samples),
        "include_reason_tags": sorted(include_tags),
        "reason_tag_counts": dict(reason_counts),
        "reject_reasons": dict(reject_reasons),
        "legal_mask_source": "website_oracle",
        "action_dim_checked": True,
        "legal_mask_dim_checked": True,
        "threshold_passed": bool(corrective_unique),
    }
    out_path = Path(args.corrective_dataset_out)
    write_imitation_dataset(out_path, imitation_dataset_format(out_path), merged_samples, summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    if not summary["threshold_passed"]:
        raise RuntimeError("no valid corrective samples were built")


def load_imitation_dataset(path: Path) -> tuple[list[dict], dict, str]:
    dataset_format = imitation_dataset_format(path)
    if dataset_format == "jsonl":
        samples = []
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if line:
                    samples.append(json.loads(line))
        summary = load_json(Path(str(path) + ".summary.json"), {})
        return samples, summary, dataset_format
    torch = offline_resolve_device("cpu")["torch"]
    if torch is None:
        raise RuntimeError("torch is required to read .pt/.pth imitation datasets")
    try:
        payload = torch.load(path, map_location="cpu", weights_only=False)
    except TypeError:
        payload = torch.load(path, map_location="cpu")
    return list(payload.get("samples") or []), dict(payload.get("summary") or {}), dataset_format


def dmc_dataset_format(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix == ".jsonl":
        return "jsonl"
    if suffix in {".pt", ".pth"}:
        return "torch"
    raise RuntimeError("DMC dataset path must end with .jsonl, .pt, or .pth")


def write_dmc_dataset(path: Path, dataset_format: str, samples: list[dict], summary: dict) -> None:
    if dataset_format == "jsonl":
        with path.open("w", encoding="utf-8") as handle:
            for sample in samples:
                handle.write(json.dumps(sample, ensure_ascii=False, separators=(",", ":")) + "\n")
        save_json(Path(str(path) + ".summary.json"), summary)
        return
    torch = offline_resolve_device("cpu")["torch"]
    if torch is None:
        raise RuntimeError("torch is required to write .pt/.pth DMC datasets")
    torch.save({"format": "dmc_action_value_dataset_v1", "summary": summary, "samples": samples}, path)


def load_dmc_dataset(path: Path) -> tuple[list[dict], dict, str]:
    dataset_format = dmc_dataset_format(path)
    if dataset_format == "jsonl":
        samples = []
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if line:
                    samples.append(json.loads(line))
        return samples, load_json(Path(str(path) + ".summary.json"), {}), dataset_format
    torch = offline_resolve_device("cpu")["torch"]
    if torch is None:
        raise RuntimeError("torch is required to read .pt/.pth DMC datasets")
    try:
        payload = torch.load(path, map_location="cpu", weights_only=False)
    except TypeError:
        payload = torch.load(path, map_location="cpu")
    return list(payload.get("samples") or []), dict(payload.get("summary") or {}), dataset_format


def dmc_card_is_joker(card: str) -> bool:
    return card in {"灏忕帇", "澶х帇", "小王", "大王"} or "王" in str(card)


def dmc_cards_use_joker(cards: list[str]) -> bool:
    return any(dmc_card_is_joker(card) for card in cards)


def dmc_cards_use_level(cards: list[str], active_level: int) -> bool:
    rank = offline_rank_text(active_level)
    return any((not dmc_card_is_joker(card)) and str(card).endswith(rank) for card in cards)


def dmc_action_features(
    components: dict,
    action_id: int,
    cards: list[str],
    current_player: int,
    hand_sizes: list[int],
    was_lead: bool,
    active_level: int,
) -> list[float]:
    action = components["action_by_id"].get(int(action_id), {})
    if int(action_id) == 0:
        action = {"type": "None", "logic_point": 0, "id": 0}
    action_type = str(action.get("type") or "unknown")
    hand_sizes = (list(hand_sizes or []) + [27, 27, 27, 27])[:4]
    current_player = int(current_player)
    teammate = offline_teammate(current_player)
    opponents = [seat for seat in range(4) if offline_team_id(seat) != offline_team_id(current_player)]
    opponent_counts = [int(hand_sizes[seat]) for seat in opponents]
    current_hand = max(1, int(hand_sizes[current_player]))
    size = len(cards or [])
    logic_point = float(action.get("logic_point") or 0.0)
    is_bomb = offline_action_is_bomb(action)
    uses_joker = dmc_cards_use_joker(cards)
    uses_level = dmc_cards_use_level(cards, active_level)
    key_combo = action_type in {"straight", "three_with_pair", "pair_chain", "gangban", "flush_rocket"}
    base = [
        float(action_id) / max(1.0, float(OFFLINE_ACTION_DIM - 1)),
        float(size) / 8.0,
        logic_point / 17.0,
        1.0 if size == 0 else 0.0,
        1.0 if is_bomb else 0.0,
        1.0 if was_lead else 0.0,
        0.0 if was_lead else 1.0,
        1.0 if uses_joker else 0.0,
        1.0 if uses_level else 0.0,
        float(active_level) / 14.0,
        float(hand_sizes[current_player]) / 27.0,
        float(hand_sizes[teammate]) / 27.0,
        float(min(opponent_counts or [27])) / 27.0,
        float(sum(opponent_counts)) / 54.0,
        float(size) / float(current_hand),
        1.0 if key_combo else 0.0,
    ]
    if len(base) != DMC_ACTION_FEATURE_BASE_DIM:
        raise RuntimeError(f"DMC base feature dim mismatch: {len(base)}")
    one_hot = [1.0 if action_type == name else 0.0 for name in DMC_ACTION_TYPES]
    features = base + one_hot
    if len(features) != DMC_ACTION_FEATURE_DIM:
        raise RuntimeError(f"DMC action feature dim mismatch: {len(features)}")
    return features


def dmc_sample_action_type(components: dict, action_id: int) -> str:
    if int(action_id) == 0:
        return "None"
    return str((components["action_by_id"].get(int(action_id)) or {}).get("type") or "unknown")


def dmc_source_action_item(
    sample: dict,
    components: dict,
    action_id: int,
    cards: list[str],
    target: float,
    weight: float,
    source_label: str,
) -> tuple[dict | None, str | None]:
    obs = list(sample.get("obs") or [])
    legal_mask = list(sample.get("legal_mask") or [])
    if len(obs) != OFFLINE_STATE_DIM:
        return None, "obs_dim_mismatch"
    if len(legal_mask) != OFFLINE_ACTION_DIM:
        return None, "legal_mask_dim_mismatch"
    if not 0 <= int(action_id) < OFFLINE_ACTION_DIM:
        return None, "action_id_out_of_range"
    if float(legal_mask[int(action_id)]) <= 0:
        return None, "action_id_not_in_mask"
    hand_before = list(sample.get("hand_before") or [])
    if hand_before and not offline_cards_in_hand(list(cards or []), hand_before):
        return None, "cards_not_in_hand"
    current_player = int(sample.get("current_player", 0))
    active_level = int(sample.get("active_level") or website_level_to_local_level(str(sample.get("level") or "2")))
    hand_sizes = list(sample.get("hand_size_by_player") or [27, 27, 27, 27])
    was_lead = bool(sample.get("was_lead"))
    action_features = dmc_action_features(
        components,
        int(action_id),
        list(cards or []),
        current_player,
        hand_sizes,
        was_lead,
        active_level,
    )
    return {
        "obs": obs,
        "action_id": int(action_id),
        "action_features": action_features,
        "target": float(max(-1.0, min(1.0, target))),
        "weight": float(max(0.0, weight)),
        "physical_cards": list(cards or []),
        "action_type": dmc_sample_action_type(components, int(action_id)),
        "current_player": current_player,
        "hand_size_by_player": hand_sizes,
        "active_level": active_level,
        "level": website_level_from_local_level(active_level),
        "was_lead": was_lead,
        "was_follow": not was_lead,
        "source_label": source_label,
        "source_game_id": sample.get("source_game_id"),
        "source_turn": sample.get("source_turn"),
        "reason_tags": list(sample.get("reason_tags") or []),
    }, None


def run_build_dmc_action_value_dataset(args: argparse.Namespace) -> None:
    components = offline_load_guandan_components()
    source_path = Path(args.dmc_source_dataset)
    samples, source_summary, _source_format = load_imitation_dataset(source_path)
    items: list[dict] = []
    reject_reasons: Counter = Counter()
    source_counts: Counter = Counter()
    action_type_counts: Counter = Counter()
    max_samples = int(args.dmc_max_samples or 0)
    rollout_seen = 0
    for sample in samples:
        if max_samples and rollout_seen >= max_samples:
            break
        if not sample.get("is_rollout_teacher"):
            continue
        rollout_seen += 1
        teacher_id = sample.get("rollout_teacher_action_id", sample.get("teacher_action_id"))
        teacher_cards = list(sample.get("rollout_teacher_physical_cards") or sample.get("teacher_chosen_cards") or [])
        target = sample.get("estimated_action_win_rate")
        if target is None:
            target = 1.0
        item, reason = dmc_source_action_item(
            sample,
            components,
            int(teacher_id),
            teacher_cards,
            float(target),
            float(sample.get("weight", args.dmc_rollout_label_weight)),
            "rollout_teacher",
        )
        if item is None:
            reject_reasons[str(reason or "unknown")] += 1
        else:
            items.append(item)
            source_counts[item["source_label"]] += 1
            action_type_counts[item["action_type"]] += 1
        original_id = sample.get("original_model_action_id")
        original_target = sample.get("model_action_win_rate")
        if original_id is not None and original_target is not None:
            original_cards = list(sample.get("original_model_physical_cards") or [])
            item, reason = dmc_source_action_item(
                sample,
                components,
                int(original_id),
                original_cards,
                float(original_target),
                1.0,
                "original_model_action",
            )
            if item is None:
                reject_reasons[f"original_{reason or 'unknown'}"] += 1
            else:
                items.append(item)
                source_counts[item["source_label"]] += 1
                action_type_counts[item["action_type"]] += 1
    summary = {
        "format": "dmc_action_value_dataset_v1",
        "method_reference": "DanZero-style state-action value learning",
        "source_dataset": str(source_path),
        "source_summary": {
            "format": source_summary.get("format"),
            "legal_mask_source": source_summary.get("legal_mask_source"),
            "rollout_teacher_sample_count": source_summary.get("rollout_teacher_sample_count"),
        },
        "source_rollout_samples_seen": rollout_seen,
        "dmc_sample_count": len(items),
        "source_label_counts": dict(source_counts),
        "action_type_distribution": dict(action_type_counts),
        "reject_reasons": dict(reject_reasons),
        "state_dim": OFFLINE_STATE_DIM,
        "action_feature_dim": DMC_ACTION_FEATURE_DIM,
        "legal_mask_source": "website_oracle",
        "threshold_passed": bool(items),
    }
    out_path = Path(args.dmc_dataset_out)
    write_dmc_dataset(out_path, dmc_dataset_format(out_path), items, summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    if not summary["threshold_passed"]:
        raise RuntimeError("no valid DMC action-value samples were built")


def dmc_candidate_snapshots(
    components: dict,
    candidates: list[tuple[int, list[str]]],
    current_player: int,
    hand_sizes: list[int],
    was_lead: bool,
    active_level: int,
    selected_action_id: int | None,
    selected_cards: list[str] | None,
    limit: int,
) -> list[dict]:
    snapshots: list[dict] = []
    seen: set[tuple[int, tuple[str, ...]]] = set()
    selected_key = (
        int(selected_action_id),
        tuple(selected_cards or []),
    ) if selected_action_id is not None else None
    ordered = list(candidates)
    if selected_key is not None:
        ordered.sort(key=lambda item: 0 if (int(item[0]), tuple(item[1])) == selected_key else 1)
    for action_id, cards in ordered:
        key = (int(action_id), tuple(cards))
        if key in seen:
            continue
        seen.add(key)
        snapshots.append(
            {
                "action_id": int(action_id),
                "physical_cards": list(cards),
                "action_type": dmc_sample_action_type(components, int(action_id)),
                "action_features": dmc_action_features(
                    components,
                    int(action_id),
                    list(cards),
                    current_player,
                    hand_sizes,
                    was_lead,
                    active_level,
                ),
                "is_selected": bool(selected_key is not None and key == selected_key),
            }
        )
        if len(snapshots) >= int(limit):
            break
    return snapshots


def dmc_selfplay_policy_name(rng: random.Random) -> str:
    return str(rng.choices(["tempo_baseline", "greedy_bot", "random_bot"], weights=[50, 30, 20], k=1)[0])


def dmc_selfplay_action_info(
    game: Any,
    components: dict,
    profile_config: dict,
    rng: random.Random,
    policy: str,
) -> dict:
    if policy == "tempo_baseline":
        return offline_baseline_action_info(game, components, "tempo_baseline", profile_config, rng)
    if policy == "greedy_bot":
        return offline_greedy_action_info(game, components, rng)
    return offline_oracle_sample_action_info(game, components, rng, policy="random_bot")


def dmc_selfplay_decision_sample(
    game: Any,
    components: dict,
    action_info: dict,
    candidates: list[tuple[int, list[str]]],
    legal_mask: list[float],
    candidate_snapshot_limit: int,
) -> tuple[dict | None, str | None]:
    player_id = int(action_info.get("player_id", game.current_player))
    action_id = int(action_info.get("action_id", -1))
    cards = list(action_info.get("chosen_cards") or [])
    if len(legal_mask) != OFFLINE_ACTION_DIM:
        return None, "legal_mask_dim_mismatch"
    if not 0 <= action_id < OFFLINE_ACTION_DIM:
        return None, "action_id_out_of_range"
    if float(legal_mask[action_id]) <= 0:
        return None, "action_id_not_in_mask"
    if action_info.get("illegal"):
        return None, str(action_info.get("illegal_reason") or "illegal_action")
    if action_info.get("fallback"):
        return None, "fallback_action"
    if action_info.get("materialization_fail"):
        return None, str(action_info.get("materialization_fail_reason") or "materialization_fail")
    if action_info.get("hand_card_mismatch"):
        return None, "hand_card_mismatch"
    hand_before = list(action_info.get("hand_before") or [])
    if not offline_cards_in_hand(cards, hand_before):
        return None, "cards_not_in_hand"
    obs = action_info.get("state")
    obs_list = obs.tolist() if hasattr(obs, "tolist") else list(obs or [])
    if len(obs_list) != OFFLINE_STATE_DIM:
        return None, "obs_dim_mismatch"
    hand_sizes = [len(player.hand) for player in game.players]
    was_lead = bool(action_info.get("was_lead"))
    active_level = int(game.active_level)
    teammate = offline_teammate(player_id)
    opponent_counts = [hand_sizes[seat] for seat in range(4) if offline_team_id(seat) != offline_team_id(player_id)]
    opponent_min = min(opponent_counts or [27])
    action_type = dmc_sample_action_type(components, action_id)
    is_pass = not bool(cards)
    is_bomb = offline_action_is_bomb(components["action_by_id"].get(int(action_id)))
    is_key_combo = action_type in {"straight", "three_with_pair", "pair_chain", "gangban", "flush_rocket"}
    can_beat_available = bool((not was_lead) and any(candidate_cards for _candidate_id, candidate_cards in candidates))
    candidate_actions = dmc_candidate_snapshots(
        components,
        candidates,
        player_id,
        hand_sizes,
        was_lead,
        active_level,
        action_id,
        cards,
        candidate_snapshot_limit,
    )
    return {
        "obs": obs_list,
        "action_id": action_id,
        "action_features": dmc_action_features(
            components,
            action_id,
            cards,
            player_id,
            hand_sizes,
            was_lead,
            active_level,
        ),
        "target": 0.0,
        "weight": 1.0,
        "physical_cards": cards,
        "action_type": action_type,
        "current_player": player_id,
        "team_id": offline_team_id(player_id),
        "hand_size_by_player": hand_sizes,
        "active_level": active_level,
        "level": website_level_from_local_level(active_level),
        "was_lead": was_lead,
        "was_follow": not was_lead,
        "is_pass": is_pass,
        "is_non_pass": not is_pass,
        "can_beat_available": can_beat_available,
        "opponent_min_hand_count": opponent_min,
        "teammate_hand_count": hand_sizes[teammate],
        "is_endgame": bool(opponent_min <= 5 or min(hand_sizes or [27]) <= 5),
        "is_bomb": is_bomb,
        "is_key_combo": is_key_combo,
        "source_label": "dmc_selfplay_actual_action",
        "selfplay_policy": str(action_info.get("policy") or "unknown"),
        "candidate_actions": candidate_actions,
        "candidate_action_count": len(candidates),
    }, None


def dmc_selfplay_dataset_worker(
    worker_id: int,
    target_samples: int,
    profile_config: dict,
    candidate_snapshot_limit: int,
    max_pass_ratio: float,
) -> dict:
    components = offline_load_guandan_components()
    GuandanGame = components["GuandanGame"]
    restore_baseline = offline_install_arena_baseline_optimizations()
    rng = random.Random(20260708 + worker_id * 1_000_000)
    samples: list[dict] = []
    reject_reasons: Counter = Counter()
    action_type_counts: Counter = Counter()
    policy_counts: Counter = Counter()
    first_player_distribution = {"0": 0, "1": 0, "2": 0, "3": 0}
    completed_games = 0
    attempted_games = 0
    illegal_action_count = 0
    fallback_count = 0
    materialization_fail_count = 0
    hand_card_mismatch_count = 0
    concrete_failure_samples: list[dict] = []
    accepted_pass_count = 0
    pass_quota = int(max(0.0, min(1.0, float(max_pass_ratio))) * int(target_samples))
    try:
        game_index = 0
        while len(samples) < int(target_samples):
            random.seed(20260708 + worker_id * 10_000_000 + game_index)
            game = GuandanGame(verbose=False, print_history=False)
            first_player = offline_set_random_first_player(game, rng)
            first_player_distribution[str(first_player)] += 1
            attempted_games += 1
            game_samples: list[dict] = []
            steps = 0
            while not game.is_game_over and steps < OFFLINE_MAX_GAME_STEPS:
                offline_prepare_turn(game)
                if game.current_player in game.ranking:
                    steps += 1
                    continue
                player_id = int(game.current_player)
                hand_before = list(game.players[player_id].hand)
                last_play_before = list(game.last_play or [])
                was_lead = bool(game.is_free_turn or not last_play_before)
                oracle, candidates = offline_oracle_candidates_fast(
                    game,
                    components,
                    hand_before,
                    last_play_before,
                    was_lead,
                )
                policy = dmc_selfplay_policy_name(rng)
                policy_counts[policy] += 1
                action_info = dmc_selfplay_action_info(game, components, profile_config, rng, policy)
                sample, reject_reason = dmc_selfplay_decision_sample(
                    game,
                    components,
                    action_info,
                    candidates,
                    list(oracle["mask"]),
                    int(candidate_snapshot_limit),
                )
                if sample is None:
                    reject_reasons[str(reject_reason or "unknown")] += 1
                elif sample.get("is_pass") and accepted_pass_count >= pass_quota:
                    reject_reasons["pass_ratio_filtered"] += 1
                else:
                    game_samples.append(sample)
                    if sample.get("is_pass"):
                        accepted_pass_count += 1
                record = offline_apply_action(game, action_info)
                if record.get("illegal"):
                    illegal_action_count += 1
                if record.get("fallback"):
                    fallback_count += 1
                if record.get("materialization_fail"):
                    materialization_fail_count += 1
                if record.get("hand_card_mismatch"):
                    hand_card_mismatch_count += 1
                if (
                    record.get("illegal")
                    or record.get("fallback")
                    or record.get("materialization_fail")
                    or record.get("hand_card_mismatch")
                ) and len(concrete_failure_samples) < 20:
                    concrete_failure_samples.append(
                        {
                            "worker_id": worker_id,
                            "game_index": game_index,
                            "step": steps,
                            "player_id": record.get("player_id"),
                            "policy": policy,
                            "action_id": record.get("action_id"),
                            "chosen_cards": record.get("chosen_cards"),
                            "illegal_reason": record.get("illegal_reason"),
                            "materialization_fail_reason": record.get("materialization_fail_reason"),
                            "missing_cards": record.get("missing_cards"),
                        }
                    )
                steps += 1
            if game.is_game_over:
                completed_games += 1
                winner_team = offline_winner_team_id(game)
                for sample in game_samples:
                    reward = 1.0 if int(sample["team_id"]) == winner_team else -1.0
                    sample["target"] = reward
                    sample["winner_team"] = winner_team
                    sample["source_game_id"] = f"worker{worker_id}_game{game_index}"
                    samples.append(sample)
                    action_type_counts[sample["action_type"]] += 1
                    if len(samples) >= int(target_samples):
                        break
            game_index += 1
    finally:
        restore_baseline()
    return {
        "worker_id": worker_id,
        "samples": samples[: int(target_samples)],
        "completed_games": completed_games,
        "attempted_games": attempted_games,
        "first_player_distribution": first_player_distribution,
        "policy_distribution": dict(policy_counts),
        "action_type_distribution": dict(action_type_counts),
        "reject_reasons": dict(reject_reasons),
        "illegal_action_count": illegal_action_count,
        "fallback_count": fallback_count,
        "materialization_fail_count": materialization_fail_count,
        "hand_card_mismatch_count": hand_card_mismatch_count,
        "concrete_failure_samples": concrete_failure_samples,
    }


def run_generate_dmc_selfplay_dataset(args: argparse.Namespace) -> None:
    device_info = offline_resolve_device(args.device)
    profiles = load_json(PROFILE_PATH, {})
    profile_config = profiles.get("tempo_baseline", {"engine_mode": "tempo"})
    target_samples = int(args.dmc_target_samples)
    worker_count = int(args.dmc_selfplay_workers or 0)
    if worker_count <= 0:
        worker_count = min(max(1, os.cpu_count() or 1), 6, max(1, target_samples // 1000))
    worker_targets = imitation_worker_targets(target_samples, worker_count)
    samples: list[dict] = []
    summary = {
        "format": "dmc_action_value_dataset_v1",
        "method_reference": "DanZero-style self-play Monte-Carlo state-action value learning",
        "backend": device_info["backend"],
        "requested_device": device_info["requested_device"],
        "actual_device": device_info["actual_device"],
        "device_fallback": device_info["device_fallback"],
        "legal_mask_source": "website_oracle",
        "local_player_mapping": offline_local_player_mapping(),
        "team_mapping": offline_team_mapping(),
        "first_player_policy": "random_each_game",
        "target_samples": target_samples,
        "dmc_sample_count": 0,
        "completed_games": 0,
        "attempted_games": 0,
        "worker_count": worker_count,
        "candidate_snapshot_limit": int(args.dmc_candidate_snapshot_limit),
        "max_pass_ratio": float(args.dmc_max_pass_ratio),
        "first_player_distribution": {"0": 0, "1": 0, "2": 0, "3": 0},
        "policy_distribution": {},
        "action_type_distribution": {},
        "pass_sample_count": 0,
        "non_pass_sample_count": 0,
        "pass_ratio": 0.0,
        "reject_reasons": {},
        "illegal_action_count": 0,
        "fallback_count": 0,
        "materialization_fail_count": 0,
        "hand_card_mismatch_count": 0,
        "state_dim": OFFLINE_STATE_DIM,
        "action_feature_dim": DMC_ACTION_FEATURE_DIM,
        "concrete_failure_samples": [],
        "threshold_passed": False,
    }
    import concurrent.futures

    policy_counts: Counter = Counter()
    action_type_counts: Counter = Counter()
    reject_reasons: Counter = Counter()
    with concurrent.futures.ProcessPoolExecutor(max_workers=worker_count) as executor:
        futures = [
            executor.submit(
                dmc_selfplay_dataset_worker,
                worker_id,
                target,
                profile_config,
                int(args.dmc_candidate_snapshot_limit),
                float(args.dmc_max_pass_ratio),
            )
            for worker_id, target in enumerate(worker_targets)
            if target > 0
        ]
        for future in concurrent.futures.as_completed(futures):
            result = future.result()
            samples.extend(result["samples"])
            summary["completed_games"] += int(result["completed_games"])
            summary["attempted_games"] += int(result["attempted_games"])
            summary["illegal_action_count"] += int(result["illegal_action_count"])
            summary["fallback_count"] += int(result["fallback_count"])
            summary["materialization_fail_count"] += int(result["materialization_fail_count"])
            summary["hand_card_mismatch_count"] += int(result["hand_card_mismatch_count"])
            for key, value in result["first_player_distribution"].items():
                summary["first_player_distribution"][str(key)] += int(value)
            policy_counts.update(result["policy_distribution"])
            action_type_counts.update(result["action_type_distribution"])
            reject_reasons.update(result["reject_reasons"])
            for sample in result["concrete_failure_samples"]:
                if len(summary["concrete_failure_samples"]) < 20:
                    summary["concrete_failure_samples"].append(sample)
    samples = samples[:target_samples]
    summary["dmc_sample_count"] = len(samples)
    summary["pass_sample_count"] = sum(1 for sample in samples if sample.get("is_pass"))
    summary["non_pass_sample_count"] = sum(1 for sample in samples if sample.get("is_non_pass"))
    summary["pass_ratio"] = summary["pass_sample_count"] / max(1, len(samples))
    summary["policy_distribution"] = dict(policy_counts)
    summary["action_type_distribution"] = dict(action_type_counts)
    summary["reject_reasons"] = dict(reject_reasons)
    summary["threshold_passed"] = bool(
        len(samples) >= target_samples
        and summary["pass_ratio"] <= float(args.dmc_max_pass_ratio) + 1e-9
        and summary["illegal_action_count"] == 0
        and summary["fallback_count"] == 0
        and summary["materialization_fail_count"] == 0
        and summary["hand_card_mismatch_count"] == 0
    )
    out_path = Path(args.dmc_dataset_out)
    write_dmc_dataset(out_path, dmc_dataset_format(out_path), samples, summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    if not summary["threshold_passed"]:
        raise RuntimeError("DMC self-play dataset threshold failed")


def offline_build_dmc_value_model(device: Any) -> Any:
    import torch
    import torch.nn as nn

    class DMCActionValueNet(nn.Module):
        def __init__(self) -> None:
            super().__init__()
            self.net = nn.Sequential(
                nn.Linear(OFFLINE_STATE_DIM + DMC_ACTION_FEATURE_DIM, 512),
                nn.ReLU(),
                nn.Linear(512, 256),
                nn.ReLU(),
                nn.Linear(256, 1),
            )

        def forward(self, states: Any, action_features: Any) -> Any:
            return self.net(torch.cat([states, action_features], dim=-1)).squeeze(-1)

    return DMCActionValueNet().to(device)


def offline_load_dmc_value_model(path: Path, device_info: dict) -> Any:
    torch = device_info.get("torch")
    if torch is None:
        raise RuntimeError("DMC action-value models require torch backend")
    model = offline_build_dmc_value_model(device_info["device"])
    try:
        payload = torch.load(path, map_location=device_info["device"], weights_only=False)
    except TypeError:
        payload = torch.load(path, map_location=device_info["device"])
    state_dict = payload.get("model_state_dict") if isinstance(payload, dict) and "model_state_dict" in payload else payload
    model.load_state_dict(state_dict)
    model.eval()
    return model


def dmc_split_indices(count: int, validation_split: float, rng: random.Random) -> tuple[list[int], list[int]]:
    indices = list(range(count))
    rng.shuffle(indices)
    val_count = max(1, int(round(count * float(validation_split)))) if count > 1 else 0
    return indices[val_count:], indices[:val_count]


def dmc_training_weight(sample: dict, args: argparse.Namespace) -> float:
    weight = float(sample.get("weight", 1.0))
    if not bool(getattr(args, "dmc_balanced_training", False)):
        return weight
    if sample.get("is_pass") or str(sample.get("action_type") or "") == "None":
        weight *= float(args.dmc_pass_weight)
    else:
        weight *= float(args.dmc_non_pass_weight)
    if sample.get("was_follow"):
        weight *= float(args.dmc_follow_weight)
    if sample.get("is_endgame"):
        weight *= float(args.dmc_endgame_weight)
    if sample.get("is_bomb"):
        weight *= float(args.dmc_bomb_weight)
    return float(max(0.0, weight))


def dmc_dataset_tag_summary(samples: list[dict]) -> dict:
    total = len(samples)
    return {
        "pass_sample_count": sum(1 for sample in samples if sample.get("is_pass") or sample.get("action_type") == "None"),
        "non_pass_sample_count": sum(1 for sample in samples if sample.get("is_non_pass") or sample.get("action_type") != "None"),
        "follow_sample_count": sum(1 for sample in samples if sample.get("was_follow")),
        "lead_sample_count": sum(1 for sample in samples if sample.get("was_lead")),
        "endgame_sample_count": sum(1 for sample in samples if sample.get("is_endgame")),
        "bomb_sample_count": sum(1 for sample in samples if sample.get("is_bomb")),
        "key_combo_sample_count": sum(1 for sample in samples if sample.get("is_key_combo")),
        "pass_ratio": sum(1 for sample in samples if sample.get("is_pass") or sample.get("action_type") == "None") / max(1, total),
    }


def dmc_batch_metrics(model: Any, samples: list[dict], indices: list[int], batch_size: int, device: Any) -> dict:
    import numpy as np
    import torch
    import torch.nn.functional as F

    if not indices:
        return {"mse": 0.0, "mae": 0.0}
    losses: list[float] = []
    maes: list[float] = []
    with torch.no_grad():
        for start in range(0, len(indices), batch_size):
            batch_indices = indices[start : start + batch_size]
            states = torch.tensor(
                np.asarray([samples[idx]["obs"] for idx in batch_indices], dtype=np.float32),
                dtype=torch.float32,
                device=device,
            )
            action_features = torch.tensor(
                np.asarray([samples[idx]["action_features"] for idx in batch_indices], dtype=np.float32),
                dtype=torch.float32,
                device=device,
            )
            targets = torch.tensor(
                [float(samples[idx]["target"]) for idx in batch_indices],
                dtype=torch.float32,
                device=device,
            )
            pred = model(states, action_features)
            losses.append(float(F.mse_loss(pred, targets).item()))
            maes.append(float(torch.mean(torch.abs(pred - targets)).item()))
    return {
        "mse": sum(losses) / max(1, len(losses)),
        "mae": sum(maes) / max(1, len(maes)),
    }


def run_train_dmc_action_value(args: argparse.Namespace) -> None:
    device_info = offline_resolve_device(args.device)
    torch = device_info["torch"]
    if torch is None:
        raise RuntimeError("torch backend is required for DMC action-value training")
    samples, dataset_summary, dataset_format = load_dmc_dataset(Path(args.dmc_dataset))
    invalid = 0
    for sample in samples:
        if (
            len(sample.get("obs") or []) != OFFLINE_STATE_DIM
            or len(sample.get("action_features") or []) != DMC_ACTION_FEATURE_DIM
            or not 0 <= int(sample.get("action_id", -1)) < OFFLINE_ACTION_DIM
        ):
            invalid += 1
    if invalid:
        raise RuntimeError(f"invalid DMC samples: {invalid}")
    rng = random.Random(20260707)
    train_indices, val_indices = dmc_split_indices(len(samples), float(args.validation_split), rng)
    device = device_info["device"]
    model = offline_build_dmc_value_model(device)
    optimizer = torch.optim.Adam(model.parameters(), lr=float(args.learning_rate))
    out_dir = Path(args.dmc_out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    log = {
        "backend": device_info["backend"],
        "requested_device": device_info["requested_device"],
        "actual_device": device_info["actual_device"],
        "device_fallback": device_info["device_fallback"],
        "dataset_path": str(args.dmc_dataset),
        "dataset_format": dataset_format,
        "dataset_summary": dataset_summary,
        "sample_count": len(samples),
        "train_sample_count": len(train_indices),
        "val_sample_count": len(val_indices),
        "state_dim": OFFLINE_STATE_DIM,
        "action_feature_dim": DMC_ACTION_FEATURE_DIM,
        "dmc_epochs": int(args.dmc_epochs),
        "batch_size": int(args.batch_size),
        "learning_rate": float(args.learning_rate),
        "dmc_balanced_training": bool(args.dmc_balanced_training),
        "dmc_non_pass_weight": float(args.dmc_non_pass_weight),
        "dmc_follow_weight": float(args.dmc_follow_weight),
        "dmc_endgame_weight": float(args.dmc_endgame_weight),
        "dmc_bomb_weight": float(args.dmc_bomb_weight),
        "dmc_pass_weight": float(args.dmc_pass_weight),
        "dataset_tag_summary": dmc_dataset_tag_summary(samples),
        "train_mse_by_epoch": [],
        "val_mse_by_epoch": [],
        "train_mae_by_epoch": [],
        "val_mae_by_epoch": [],
        "best_epoch": None,
        "best_val_mse": None,
        "saved_checkpoints": [],
        "threshold_passed": False,
    }
    best_val = float("inf")
    best_path = out_dir / "dmc_action_value_best.pth"
    import numpy as np
    import torch.nn.functional as F

    for epoch in range(1, int(args.dmc_epochs) + 1):
        rng.shuffle(train_indices)
        model.train()
        for start in range(0, len(train_indices), int(args.batch_size)):
            batch_indices = train_indices[start : start + int(args.batch_size)]
            states = torch.tensor(
                np.asarray([samples[idx]["obs"] for idx in batch_indices], dtype=np.float32),
                dtype=torch.float32,
                device=device,
            )
            action_features = torch.tensor(
                np.asarray([samples[idx]["action_features"] for idx in batch_indices], dtype=np.float32),
                dtype=torch.float32,
                device=device,
            )
            targets = torch.tensor(
                [float(samples[idx]["target"]) for idx in batch_indices],
                dtype=torch.float32,
                device=device,
            )
            weights = torch.tensor(
                [dmc_training_weight(samples[idx], args) for idx in batch_indices],
                dtype=torch.float32,
                device=device,
            )
            pred = model(states, action_features)
            loss = (F.mse_loss(pred, targets, reduction="none") * weights).sum() / weights.sum().clamp_min(1e-8)
            optimizer.zero_grad()
            loss.backward()
            optimizer.step()
        model.eval()
        train_metrics = dmc_batch_metrics(model, samples, train_indices, int(args.batch_size), device)
        val_metrics = dmc_batch_metrics(model, samples, val_indices, int(args.batch_size), device)
        log["train_mse_by_epoch"].append(train_metrics["mse"])
        log["val_mse_by_epoch"].append(val_metrics["mse"])
        log["train_mae_by_epoch"].append(train_metrics["mae"])
        log["val_mae_by_epoch"].append(val_metrics["mae"])
        if val_metrics["mse"] < best_val:
            best_val = float(val_metrics["mse"])
            log["best_epoch"] = epoch
            log["best_val_mse"] = best_val
            torch.save(
                {
                    "model_state_dict": model.state_dict(),
                    "state_dim": OFFLINE_STATE_DIM,
                    "action_feature_dim": DMC_ACTION_FEATURE_DIM,
                    "method": "dmc_action_value",
                },
                best_path,
            )
        if int(args.dmc_save_every) > 0 and epoch % int(args.dmc_save_every) == 0:
            path = out_dir / f"dmc_action_value_epoch{epoch}.pth"
            torch.save(
                {
                    "model_state_dict": model.state_dict(),
                    "state_dim": OFFLINE_STATE_DIM,
                    "action_feature_dim": DMC_ACTION_FEATURE_DIM,
                    "method": "dmc_action_value",
                },
                path,
            )
            log["saved_checkpoints"].append(str(path))
    log["best_checkpoint"] = str(best_path) if best_path.exists() else None
    log["threshold_passed"] = bool(best_path.exists() and samples)
    save_json(out_dir / "dmc_action_value_training_state.json", log)
    save_json(Path(args.dmc_log_out), log)
    print(json.dumps(log, ensure_ascii=False, indent=2))
    if not log["threshold_passed"]:
        raise RuntimeError("DMC action-value training threshold failed")


def offline_dmc_action_info(
    game: Any,
    components: dict,
    model: Any,
    device: Any,
    rng: random.Random,
) -> dict:
    import numpy as np
    import torch

    player_id = int(game.current_player)
    hand_before = list(game.players[player_id].hand)
    last_play_before = list(game.last_play or [])
    was_lead = bool(game.is_free_turn or not last_play_before)
    state = game._get_obs()
    _oracle, candidates = offline_oracle_candidates_fast(game, components, hand_before, last_play_before, was_lead)
    if not candidates:
        return offline_first_oracle_action_info(
            game,
            components,
            rng,
            policy="dmc_action_value",
            fallback_reason="dmc_no_oracle_candidate",
        )
    hand_sizes = [len(player.hand) for player in game.players]
    states = []
    action_features = []
    for action_id, cards in candidates:
        states.append(state)
        action_features.append(
            dmc_action_features(
                components,
                int(action_id),
                list(cards),
                player_id,
                hand_sizes,
                was_lead,
                int(game.active_level),
            )
        )
    with torch.no_grad():
        state_tensor = torch.tensor(np.asarray(states, dtype=np.float32), dtype=torch.float32, device=device)
        action_tensor = torch.tensor(
            np.asarray(action_features, dtype=np.float32),
            dtype=torch.float32,
            device=device,
        )
        values = model(state_tensor, action_tensor).detach().cpu().numpy().tolist()
    best_value = max(float(value) for value in values)
    best_indices = [idx for idx, value in enumerate(values) if float(value) == best_value]
    selected_index = int(rng.choice(best_indices))
    selected_action_id, selected_cards = candidates[selected_index]
    info = offline_make_action_info_from_cards(
        game,
        components,
        list(selected_cards),
        rng,
        policy="dmc_action_value",
        sampled_action_id=int(selected_action_id),
        audit_masks=False,
    )
    info["dmc_q_value"] = best_value
    info["dmc_candidate_count"] = len(candidates)
    return info


def offline_dmc_score_action(
    game: Any,
    components: dict,
    model: Any,
    device: Any,
    state: Any,
    action_id: int,
    cards: list[str],
) -> float:
    import numpy as np
    import torch

    player_id = int(game.current_player)
    hand_sizes = [len(player.hand) for player in game.players]
    was_lead = bool(game.is_free_turn or not (game.last_play or []))
    features = dmc_action_features(
        components,
        int(action_id),
        list(cards),
        player_id,
        hand_sizes,
        was_lead,
        int(game.active_level),
    )
    with torch.no_grad():
        state_tensor = torch.tensor(
            np.asarray([state], dtype=np.float32),
            dtype=torch.float32,
            device=device,
        )
        action_tensor = torch.tensor(
            np.asarray([features], dtype=np.float32),
            dtype=torch.float32,
            device=device,
        )
        return float(model(state_tensor, action_tensor).item())


def offline_dmc_best_candidate(
    game: Any,
    components: dict,
    model: Any,
    device: Any,
) -> dict | None:
    import numpy as np
    import torch

    player_id = int(game.current_player)
    hand_before = list(game.players[player_id].hand)
    last_play_before = list(game.last_play or [])
    was_lead = bool(game.is_free_turn or not last_play_before)
    state = game._get_obs()
    _oracle, candidates = offline_oracle_candidates_fast(game, components, hand_before, last_play_before, was_lead)
    if not candidates:
        return None
    hand_sizes = [len(player.hand) for player in game.players]
    states = []
    action_features = []
    for action_id, cards in candidates:
        states.append(state)
        action_features.append(
            dmc_action_features(
                components,
                int(action_id),
                list(cards),
                player_id,
                hand_sizes,
                was_lead,
                int(game.active_level),
            )
        )
    with torch.no_grad():
        state_tensor = torch.tensor(np.asarray(states, dtype=np.float32), dtype=torch.float32, device=device)
        action_tensor = torch.tensor(np.asarray(action_features, dtype=np.float32), dtype=torch.float32, device=device)
        values = model(state_tensor, action_tensor).detach().cpu().numpy().tolist()
    best_value = max(float(value) for value in values)
    best_index = next(idx for idx, value in enumerate(values) if float(value) == best_value)
    action_id, cards = candidates[best_index]
    return {
        "state": state,
        "action_id": int(action_id),
        "cards": list(cards),
        "q_value": best_value,
        "candidate_count": len(candidates),
    }


def offline_hybrid_is_endgame(game: Any, player_id: int) -> bool:
    hand_sizes = [len(player.hand) for player in game.players]
    opponent_counts = [hand_sizes[seat] for seat in range(4) if offline_team_id(seat) != offline_team_id(player_id)]
    return bool(min(hand_sizes or [27]) <= 5 or min(opponent_counts or [27]) <= 5)


def offline_hybrid_opponent_min(game: Any, player_id: int) -> int:
    hand_sizes = [len(player.hand) for player in game.players]
    opponent_counts = [hand_sizes[seat] for seat in range(4) if offline_team_id(seat) != offline_team_id(player_id)]
    return int(min(opponent_counts or [27]))


def offline_hybrid_teammate_min(game: Any, player_id: int) -> int:
    teammate = offline_teammate(player_id)
    if teammate in game.ranking:
        return 0
    return int(len(game.players[teammate].hand))


def offline_hybrid_transition(baseline_cards: list[str], dmc_cards: list[str]) -> str:
    baseline_is_pass = not bool(baseline_cards)
    dmc_is_pass = not bool(dmc_cards)
    if baseline_is_pass and dmc_is_pass:
        return "pass_to_pass"
    if baseline_is_pass:
        return "pass_to_non_pass"
    if dmc_is_pass:
        return "non_pass_to_pass"
    return "non_pass_to_non_pass"


def offline_hybrid_is_control_preservation_action(action_type: str, cards: list[str]) -> bool:
    if "bomb" in str(action_type):
        return True
    return any(card in {"大王", "小王"} for card in cards)


def offline_hybrid_override_safety(
    args: argparse.Namespace,
    components: dict,
    baseline_cards: list[str],
    best_cards: list[str],
    best_action_id: int,
    q_margin: float,
    was_follow: bool,
    is_endgame: bool,
    opponent_min: int,
    hybrid_stats: dict,
) -> tuple[bool, str, str]:
    baseline_is_pass = not bool(baseline_cards)
    best_is_pass = not bool(best_cards)
    best_is_bomb = offline_action_is_bomb(components["action_by_id"].get(int(best_action_id)))
    if bool(args.hybrid_forbid_pass_over_non_pass) and (not baseline_is_pass) and best_is_pass:
        hybrid_stats["hybrid_pass_over_non_pass_block_count"] += 1
        hybrid_stats["hybrid_unsafe_override_block_count"] += 1
        return False, "pass_over_non_pass_blocked", "pass_over_non_pass"
    if baseline_is_pass and not best_is_pass:
        if not was_follow:
            hybrid_stats["hybrid_unsafe_override_block_count"] += 1
            return False, "pass_to_non_pass_not_follow", "pass_to_non_pass"
        threshold = int(args.hybrid_block_only_when_opponent_le)
        if threshold > 0 and opponent_min > threshold and not is_endgame:
            hybrid_stats["hybrid_unsafe_override_block_count"] += 1
            return False, "pass_to_non_pass_opponent_not_dangerous", "pass_to_non_pass"
        if best_is_bomb and int(args.hybrid_avoid_bomb_unless_opponent_le) > 0 and opponent_min > int(args.hybrid_avoid_bomb_unless_opponent_le):
            hybrid_stats["hybrid_bomb_override_block_count"] += 1
            hybrid_stats["hybrid_unsafe_override_block_count"] += 1
            return False, "bomb_override_blocked", "pass_to_non_pass"
        return True, "pass_to_non_pass_override", "pass_to_non_pass"
    if (not baseline_is_pass) and (not best_is_pass):
        if q_margin < float(args.hybrid_non_pass_margin):
            hybrid_stats["hybrid_unsafe_override_block_count"] += 1
            return False, "non_pass_margin_below_threshold", "non_pass_to_non_pass"
        if best_is_bomb and int(args.hybrid_avoid_bomb_unless_opponent_le) > 0 and opponent_min > int(args.hybrid_avoid_bomb_unless_opponent_le):
            hybrid_stats["hybrid_bomb_override_block_count"] += 1
            hybrid_stats["hybrid_unsafe_override_block_count"] += 1
            return False, "bomb_override_blocked", "non_pass_to_non_pass"
        return True, "non_pass_to_non_pass_override", "non_pass_to_non_pass"
    return True, "pass_to_pass_or_safe", offline_hybrid_transition(baseline_cards, best_cards)


def offline_hybrid_override_whitelist(
    args: argparse.Namespace,
    components: dict,
    baseline_cards: list[str],
    baseline_action_type: str,
    best_cards: list[str],
    best_action_id: int,
    q_margin: float,
    was_follow: bool,
    opponent_min: int,
    hybrid_stats: dict,
) -> tuple[bool, str, str]:
    transition = offline_hybrid_transition(baseline_cards, best_cards)
    reason_counts = hybrid_stats["hybrid_whitelist_reason_counts"]
    best_is_bomb = offline_action_is_bomb(components["action_by_id"].get(int(best_action_id)))
    if not was_follow:
        reason_counts["not_follow"] += 1
        hybrid_stats["hybrid_whitelist_block_count"] += 1
        hybrid_stats["hybrid_unsafe_override_block_count"] += 1
        return False, "whitelist_not_follow", transition
    if not best_cards:
        if (
            transition == "non_pass_to_pass"
            and offline_hybrid_is_control_preservation_action(baseline_action_type, baseline_cards)
            and q_margin >= float(args.hybrid_control_pass_margin)
        ):
            reason_counts["preserve_control_pass_allowed"] += 1
            return True, "whitelist_preserve_control_pass", transition
        reason_counts["dmc_pass"] += 1
        hybrid_stats["hybrid_whitelist_block_count"] += 1
        hybrid_stats["hybrid_unsafe_override_block_count"] += 1
        return False, "whitelist_dmc_pass_blocked", transition
    if best_is_bomb:
        hybrid_stats["hybrid_bomb_override_block_count"] += 1
    reason_counts["dmc_non_pass_not_whitelisted"] += 1
    hybrid_stats["hybrid_whitelist_block_count"] += 1
    hybrid_stats["hybrid_unsafe_override_block_count"] += 1
    return False, "whitelist_dmc_non_pass_blocked", transition


def offline_dmc_hybrid_action_info(
    game: Any,
    components: dict,
    model: Any,
    device: Any,
    args: argparse.Namespace,
    profile_config: dict,
    rng: random.Random,
    hybrid_stats: dict,
    game_index: int | None = None,
    step: int | None = None,
) -> dict:
    player_id = int(game.current_player)
    baseline_info = offline_baseline_action_info(
        game,
        components,
        "tempo_baseline",
        profile_config,
        rng,
    )
    hybrid_stats["hybrid_decision_count"] += 1
    best = offline_dmc_best_candidate(game, components, model, device)
    if best is None:
        hybrid_stats["hybrid_no_candidate_count"] += 1
        baseline_info["hybrid_used"] = False
        baseline_info["hybrid_reason"] = "no_dmc_candidate"
        return baseline_info
    baseline_action_id = int(baseline_info.get("action_id", 0))
    baseline_cards = list(baseline_info.get("chosen_cards") or [])
    baseline_q = offline_dmc_score_action(
        game,
        components,
        model,
        device,
        best["state"],
        baseline_action_id,
        baseline_cards,
    )
    best_q = float(best["q_value"])
    q_margin = best_q - baseline_q
    hybrid_stats["hybrid_q_margin_sum"] += q_margin
    hybrid_stats["hybrid_baseline_q_sum"] += baseline_q
    hybrid_stats["hybrid_best_q_sum"] += best_q
    was_follow = bool(baseline_info.get("was_follow"))
    is_endgame = offline_hybrid_is_endgame(game, player_id)
    opponent_min = offline_hybrid_opponent_min(game, player_id)
    teammate_min = offline_hybrid_teammate_min(game, player_id)
    phase_allowed = True
    if bool(args.hybrid_only_follow) or bool(args.hybrid_only_endgame):
        phase_allowed = bool((args.hybrid_only_follow and was_follow) or (args.hybrid_only_endgame and is_endgame))
    same_action = baseline_action_id == int(best["action_id"]) and tuple(baseline_cards) == tuple(best["cards"])
    projected_override_rate = (int(hybrid_stats["hybrid_override_count"]) + 1) / max(
        1,
        int(hybrid_stats["hybrid_decision_count"]),
    )
    safety_allowed = True
    safety_reason = "not_checked"
    safety_category = offline_hybrid_transition(baseline_cards, list(best["cards"]))
    if not same_action and phase_allowed and q_margin >= float(args.hybrid_q_margin):
        if bool(args.simulate_hybrid_override_whitelist):
            safety_allowed, safety_reason, safety_category = offline_hybrid_override_whitelist(
                args,
                components,
                baseline_cards,
                str(baseline_info.get("action_type") or "unknown"),
                list(best["cards"]),
                int(best["action_id"]),
                q_margin,
                was_follow,
                opponent_min,
                hybrid_stats,
            )
        else:
            safety_allowed, safety_reason, safety_category = offline_hybrid_override_safety(
                args,
                components,
                baseline_cards,
                list(best["cards"]),
                int(best["action_id"]),
                q_margin,
                was_follow,
                is_endgame,
                opponent_min,
                hybrid_stats,
            )
    can_override = (
        not same_action
        and phase_allowed
        and q_margin >= float(args.hybrid_q_margin)
        and safety_allowed
        and projected_override_rate <= float(args.hybrid_max_override_rate)
    )
    if not phase_allowed:
        hybrid_stats["hybrid_phase_block_count"] += 1
        reason = "phase_blocked"
    elif same_action:
        hybrid_stats["hybrid_same_action_count"] += 1
        reason = "same_action"
    elif q_margin < float(args.hybrid_q_margin):
        hybrid_stats["hybrid_margin_block_count"] += 1
        reason = "q_margin_below_threshold"
    elif not safety_allowed:
        reason = safety_reason
    elif projected_override_rate > float(args.hybrid_max_override_rate):
        hybrid_stats["hybrid_rate_block_count"] += 1
        reason = "override_rate_limit"
    else:
        reason = "override"
    if not can_override:
        baseline_info.update(
            {
                "hybrid_used": False,
                "hybrid_reason": reason,
                "hybrid_baseline_q": baseline_q,
                "hybrid_best_q": best_q,
                "hybrid_q_margin": q_margin,
                "hybrid_best_action_id": int(best["action_id"]),
                "hybrid_best_cards": list(best["cards"]),
                "hybrid_candidate_count": int(best["candidate_count"]),
                "hybrid_is_endgame": is_endgame,
                "hybrid_opponent_min": opponent_min,
                "hybrid_teammate_min": teammate_min,
                "hybrid_safety_reason": safety_reason,
                "hybrid_safety_category": safety_category,
            }
        )
        return baseline_info
    hybrid_info = offline_make_action_info_from_cards(
        game,
        components,
        list(best["cards"]),
        rng,
        policy="dmc_hybrid",
        sampled_action_id=int(best["action_id"]),
        audit_masks=False,
    )
    if hybrid_info.get("illegal") or hybrid_info.get("materialization_fail") or hybrid_info.get("hand_card_mismatch"):
        hybrid_stats["hybrid_illegal_override_count"] += 1
        baseline_info["hybrid_used"] = False
        baseline_info["hybrid_reason"] = "override_action_invalid"
        return baseline_info
    hybrid_stats["hybrid_override_count"] += 1
    if safety_category == "pass_to_non_pass":
        hybrid_stats["hybrid_pass_to_non_pass_override_count"] += 1
    elif safety_category == "non_pass_to_non_pass":
        hybrid_stats["hybrid_non_pass_to_non_pass_override_count"] += 1
    hybrid_stats["hybrid_override_action_types"][str(hybrid_info.get("action_type") or "unknown")] += 1
    override_record = {
        "game_index": game_index,
        "step": step,
        "player_id": player_id,
        "was_follow": was_follow,
        "is_endgame": is_endgame,
        "opponent_min": opponent_min,
        "teammate_min": teammate_min,
        "baseline_action": baseline_cards,
        "dmc_action": list(best["cards"]),
        "baseline_action_type": str(baseline_info.get("action_type") or "unknown"),
        "dmc_action_type": str(hybrid_info.get("action_type") or "unknown"),
        "baseline_q": baseline_q,
        "dmc_q": best_q,
        "q_margin": q_margin,
        "transition": safety_category,
        "is_bomb_override": bool(hybrid_info.get("is_bomb")),
        "game_outcome": None,
        "winner_team": None,
        "model_team": None,
    }
    hybrid_stats["hybrid_override_records"].append(override_record)
    if len(hybrid_stats["hybrid_override_samples"]) < 20:
        hybrid_stats["hybrid_override_samples"].append(
            {
                "game_index": game_index,
                "step": step,
                "player_id": player_id,
                "was_follow": was_follow,
                "is_endgame": is_endgame,
                "opponent_min": opponent_min,
                "teammate_min": teammate_min,
                "baseline_action_id": baseline_action_id,
                "baseline_cards": baseline_cards,
                "baseline_action_type": str(baseline_info.get("action_type") or "unknown"),
                "baseline_q": baseline_q,
                "best_action_id": int(best["action_id"]),
                "best_cards": list(best["cards"]),
                "best_action_type": str(hybrid_info.get("action_type") or "unknown"),
                "best_q": best_q,
                "q_margin": q_margin,
                "candidate_count": int(best["candidate_count"]),
                "safety_reason": safety_reason,
                "safety_category": safety_category,
            }
        )
    hybrid_info.update(
        {
            "hybrid_used": True,
            "hybrid_reason": "override",
            "hybrid_baseline_q": baseline_q,
            "hybrid_best_q": best_q,
            "hybrid_q_margin": q_margin,
            "hybrid_baseline_action_id": baseline_action_id,
            "hybrid_baseline_cards": baseline_cards,
            "hybrid_candidate_count": int(best["candidate_count"]),
            "hybrid_is_endgame": is_endgame,
            "hybrid_opponent_min": opponent_min,
            "hybrid_teammate_min": teammate_min,
            "hybrid_safety_reason": safety_reason,
            "hybrid_safety_category": safety_category,
        }
    )
    return hybrid_info


def offline_dmc_hybrid_stats_template() -> dict:
    return {
        "hybrid_decision_count": 0,
        "hybrid_override_count": 0,
        "hybrid_override_rate": 0.0,
        "hybrid_q_margin_avg": 0.0,
        "hybrid_baseline_q_avg": 0.0,
        "hybrid_best_q_avg": 0.0,
        "hybrid_q_margin_sum": 0.0,
        "hybrid_baseline_q_sum": 0.0,
        "hybrid_best_q_sum": 0.0,
        "hybrid_no_candidate_count": 0,
        "hybrid_phase_block_count": 0,
        "hybrid_same_action_count": 0,
        "hybrid_margin_block_count": 0,
        "hybrid_rate_block_count": 0,
        "hybrid_illegal_override_count": 0,
        "hybrid_pass_over_non_pass_block_count": 0,
        "hybrid_pass_to_non_pass_override_count": 0,
        "hybrid_non_pass_to_non_pass_override_count": 0,
        "hybrid_bomb_override_block_count": 0,
        "hybrid_unsafe_override_block_count": 0,
        "hybrid_whitelist_block_count": 0,
        "hybrid_whitelist_reason_counts": Counter(),
        "hybrid_override_action_types": Counter(),
        "hybrid_override_samples": [],
        "hybrid_override_records": [],
    }


def offline_hybrid_override_group_summary(records: list[dict], predicate: Any) -> dict:
    selected = [record for record in records if predicate(record)]
    win_count = sum(1 for record in selected if record.get("game_outcome") == "win")
    margin_values = [float(record.get("q_margin") or 0.0) for record in selected]
    return {
        "count": len(selected),
        "win_count": win_count,
        "loss_count": len(selected) - win_count,
        "win_rate": win_count / max(1, len(selected)),
        "avg_q_margin": sum(margin_values) / max(1, len(margin_values)),
    }


def offline_hybrid_override_audit_summary(records: list[dict]) -> dict:
    transition_counts: dict[str, dict] = {}
    action_type_counts: dict[str, dict] = {}
    for transition in sorted({str(record.get("transition") or "unknown") for record in records}):
        transition_counts[transition] = offline_hybrid_override_group_summary(
            records,
            lambda item, value=transition: str(item.get("transition") or "unknown") == value,
        )
    for action_type in sorted({str(record.get("dmc_action_type") or "unknown") for record in records}):
        action_type_counts[action_type] = offline_hybrid_override_group_summary(
            records,
            lambda item, value=action_type: str(item.get("dmc_action_type") or "unknown") == value,
        )
    return {
        "override_record_count": len(records),
        "win_side_override_count": sum(1 for record in records if record.get("game_outcome") == "win"),
        "loss_side_override_count": sum(1 for record in records if record.get("game_outcome") == "loss"),
        "transition_summary": transition_counts,
        "dmc_action_type_summary": action_type_counts,
        "pass_to_non_pass_summary": offline_hybrid_override_group_summary(
            records,
            lambda item: item.get("transition") == "pass_to_non_pass",
        ),
        "non_pass_to_pass_summary": offline_hybrid_override_group_summary(
            records,
            lambda item: item.get("transition") == "non_pass_to_pass",
        ),
        "bomb_override_summary": offline_hybrid_override_group_summary(
            records,
            lambda item: bool(item.get("is_bomb_override")),
        ),
        "three_with_pair_override_summary": offline_hybrid_override_group_summary(
            records,
            lambda item: item.get("dmc_action_type") == "three_with_pair",
        ),
    }


def offline_paired_oracle_action_id(
    game: Any,
    components: dict,
    action_id: int,
    cards: list[str],
) -> tuple[int | None, str]:
    hand = list(game.players[int(game.current_player)].hand)
    last_play = list(game.last_play or [])
    was_lead = bool(game.is_free_turn or not last_play)
    _oracle, candidates = offline_oracle_candidates_fast(game, components, hand, last_play, was_lead)
    target = rollout_action_key(int(action_id), list(cards))
    for candidate_id, candidate_cards in candidates:
        if rollout_action_key(candidate_id, candidate_cards) == target:
            return int(candidate_id), "oracle_exact"
    target_cards = tuple(sorted(cards))
    for candidate_id, candidate_cards in candidates:
        if tuple(sorted(candidate_cards)) == target_cards:
            return int(candidate_id), "oracle_physical_cards"
    ok, _reason = offline_action_is_legal(
        game,
        components["actions"],
        list(cards),
        hand,
        last_play,
        was_lead,
    )
    if ok and offline_cards_in_hand(cards, hand):
        mapped_action_id = offline_action_id_for_cards(game, components, cards, last_play, was_lead)
        if mapped_action_id is not None:
            return int(mapped_action_id), "website_rule_fallback"
    return None, "not_legal"


def offline_paired_rollout_branch(
    base_game: Any,
    components: dict,
    profile_config: dict,
    action_id: int,
    cards: list[str],
    team_id: int,
    continuation_profile: str,
    simulation_seed: int,
    depth_turns: int,
) -> dict:
    rng = random.Random(simulation_seed)
    game = copy.deepcopy(base_game)
    result = {
        "terminal": False,
        "winner_team": None,
        "team_win_value": 0.0,
        "team_rank": 4.0,
        "steps": 0,
        "illegal_action_count": 0,
        "fallback_count": 0,
        "materialization_fail_count": 0,
        "hand_card_mismatch_count": 0,
        "oracle_candidate_validation_fail_count": 0,
        "oracle_option_fallback_count": 0,
        "failure": None,
    }
    resolved_action_id, resolution_source = offline_paired_oracle_action_id(
        game,
        components,
        action_id,
        cards,
    )
    result["requested_action_id"] = int(action_id)
    result["resolved_action_id"] = resolved_action_id
    result["action_id_resolution_source"] = resolution_source
    result["oracle_option_fallback_count"] = int(resolution_source == "website_rule_fallback")
    if resolved_action_id is None:
        result["oracle_candidate_validation_fail_count"] = 1
        result["failure"] = "initial_action_not_in_oracle_options"
        return result
    action_info = offline_make_action_info_from_cards(
        game,
        components,
        list(cards),
        rng,
        policy="paired_counterfactual",
        sampled_action_id=int(resolved_action_id),
        audit_masks=False,
    )
    record = offline_apply_action(game, action_info)

    def observe(action_record: dict) -> bool:
        result["illegal_action_count"] += int(bool(action_record.get("illegal")))
        result["fallback_count"] += int(bool(action_record.get("fallback")))
        result["materialization_fail_count"] += int(bool(action_record.get("materialization_fail")))
        result["hand_card_mismatch_count"] += int(bool(action_record.get("hand_card_mismatch")))
        return not bool(
            action_record.get("illegal")
            or action_record.get("materialization_fail")
            or action_record.get("hand_card_mismatch")
        )

    if not observe(record):
        result["failure"] = "initial_action_apply_failed"
        return result
    result["steps"] = 1
    max_steps = int(depth_turns) if int(depth_turns) > 0 else OFFLINE_MAX_GAME_STEPS
    while not game.is_game_over and int(result["steps"]) < max_steps:
        offline_prepare_turn(game)
        if game.current_player in game.ranking:
            result["steps"] += 1
            continue
        if continuation_profile == "greedy_bot":
            next_action = rollout_greedy_action_info(game, components, rng, policy="paired_greedy_bot")
        else:
            next_action = offline_baseline_action_info(
                game,
                components,
                "tempo_baseline",
                profile_config,
                rng,
            )
        next_record = offline_apply_action(game, next_action)
        result["steps"] += 1
        if not observe(next_record):
            result["failure"] = "continuation_action_apply_failed"
            return result
    result["terminal"] = bool(game.is_game_over)
    result["winner_team"] = offline_winner_team_id(game) if game.is_game_over else None
    result["team_win_value"] = (
        1.0 if result["winner_team"] == team_id else 0.0
    ) if game.is_game_over else rollout_estimated_team_win(game, team_id)
    result["team_rank"] = rollout_estimated_team_rank(game, team_id)
    if not game.is_game_over:
        result["failure"] = "depth_limit_reached"
    return result


def offline_paired_state_evaluation(
    base_game: Any,
    components: dict,
    profile_config: dict,
    baseline_action: dict,
    override_action: dict,
    team_id: int,
    state_index: int,
    args: argparse.Namespace,
) -> dict:
    simulations: list[dict] = []
    deltas: list[float] = []
    rank_deltas: list[float] = []
    for simulation_index in range(max(1, int(args.paired_rollouts_per_state))):
        simulation_seed = int(args.paired_seed) + state_index * 100_000 + simulation_index
        baseline_result = offline_paired_rollout_branch(
            base_game,
            components,
            profile_config,
            int(baseline_action["action_id"]),
            list(baseline_action["cards"]),
            team_id,
            str(args.paired_continuation_profile),
            simulation_seed,
            int(args.paired_depth_turns),
        )
        override_result = offline_paired_rollout_branch(
            base_game,
            components,
            profile_config,
            int(override_action["action_id"]),
            list(override_action["cards"]),
            team_id,
            str(args.paired_continuation_profile),
            simulation_seed,
            int(args.paired_depth_turns),
        )
        delta = float(override_result["team_win_value"]) - float(baseline_result["team_win_value"])
        rank_delta = float(baseline_result["team_rank"]) - float(override_result["team_rank"])
        deltas.append(delta)
        rank_deltas.append(rank_delta)
        simulations.append(
            {
                "simulation_index": simulation_index,
                "simulation_seed": simulation_seed,
                "baseline": baseline_result,
                "override": override_result,
                "win_value_delta": delta,
                "rank_improvement": rank_delta,
            }
        )
    baseline_values = [float(item["baseline"]["team_win_value"]) for item in simulations]
    override_values = [float(item["override"]["team_win_value"]) for item in simulations]
    return {
        "simulation_count": len(simulations),
        "baseline_win_rate": sum(baseline_values) / max(1, len(baseline_values)),
        "override_win_rate": sum(override_values) / max(1, len(override_values)),
        "causal_win_rate_delta": sum(deltas) / max(1, len(deltas)),
        "average_rank_improvement": sum(rank_deltas) / max(1, len(rank_deltas)),
        "improved_pair_count": sum(1 for value in deltas if value > 0),
        "harmed_pair_count": sum(1 for value in deltas if value < 0),
        "neutral_pair_count": sum(1 for value in deltas if value == 0),
        "terminal_pair_count": sum(
            1 for item in simulations if item["baseline"]["terminal"] and item["override"]["terminal"]
        ),
        "simulations": simulations,
    }


def offline_paired_delta_interval(deltas: list[float]) -> tuple[float, float, float]:
    if not deltas:
        return 0.0, 0.0, 0.0
    mean = sum(deltas) / len(deltas)
    if len(deltas) == 1:
        return mean, mean, mean
    variance = sum((value - mean) ** 2 for value in deltas) / (len(deltas) - 1)
    half_width = 1.96 * (variance / len(deltas)) ** 0.5
    return mean, mean - half_width, mean + half_width


def offline_dmc_ranked_candidates(
    game: Any,
    components: dict,
    model: Any,
    device: Any,
) -> tuple[Any, list[dict]]:
    import numpy as np
    import torch

    player_id = int(game.current_player)
    hand = list(game.players[player_id].hand)
    last_play = list(game.last_play or [])
    was_lead = bool(game.is_free_turn or not last_play)
    state = game._get_obs()
    _oracle, candidates = offline_oracle_candidates_fast(game, components, hand, last_play, was_lead)
    if not candidates:
        return state, []
    hand_sizes = [len(player.hand) for player in game.players]
    features = [
        dmc_action_features(
            components,
            int(action_id),
            list(cards),
            player_id,
            hand_sizes,
            was_lead,
            int(game.active_level),
        )
        for action_id, cards in candidates
    ]
    with torch.no_grad():
        states = torch.tensor(
            np.asarray([state] * len(candidates), dtype=np.float32),
            dtype=torch.float32,
            device=device,
        )
        action_features = torch.tensor(
            np.asarray(features, dtype=np.float32),
            dtype=torch.float32,
            device=device,
        )
        q_values = model(states, action_features).detach().cpu().numpy().tolist()
    ranked = [
        {
            "action_id": int(action_id),
            "cards": list(cards),
            "action_type": dmc_sample_action_type(components, int(action_id)),
            "q_value": float(q_value),
            "is_bomb": bool(offline_action_is_bomb(components["action_by_id"].get(int(action_id)))),
        }
        for (action_id, cards), q_value in zip(candidates, q_values)
    ]
    ranked.sort(key=lambda item: item["q_value"], reverse=True)
    return state, ranked


def offline_dmc_calibration_bucket(q_margin: float) -> str:
    if q_margin < 0.10:
        return "lt_0.10"
    if q_margin < 0.25:
        return "0.10_to_0.25"
    if q_margin < 0.50:
        return "0.25_to_0.50"
    return "ge_0.50"


def offline_dmc_calibration_candidate_set(
    components: dict,
    ranked: list[dict],
    baseline_action_id: int,
    baseline_cards: list[str],
    top_k: int,
) -> list[dict]:
    selected: list[dict] = []
    seen: set[tuple] = set()

    def add(item: dict, source: str) -> None:
        key = rollout_action_key(int(item["action_id"]), list(item["cards"]))
        if key in seen:
            for existing in selected:
                if rollout_action_key(int(existing["action_id"]), list(existing["cards"])) == key:
                    existing["sources"] = sorted(set(existing["sources"] + [source]))
                    return
        seen.add(key)
        selected.append({**item, "sources": [source]})

    by_key = {
        rollout_action_key(int(item["action_id"]), list(item["cards"])): item
        for item in ranked
    }
    baseline_key = rollout_action_key(int(baseline_action_id), list(baseline_cards))
    baseline_item = by_key.get(baseline_key)
    if baseline_item is None:
        baseline_item = {
            "action_id": int(baseline_action_id),
            "cards": list(baseline_cards),
            "action_type": dmc_sample_action_type(components, int(baseline_action_id)),
            "q_value": None,
            "is_bomb": bool(offline_action_is_bomb(components["action_by_id"].get(int(baseline_action_id)))),
        }
    add(baseline_item, "tempo_baseline")
    for item in ranked[: max(1, int(top_k))]:
        add(item, "dmc_top_k")
    pass_item = next((item for item in ranked if not item["cards"]), None)
    if pass_item is not None:
        add(pass_item, "pass")
    non_pass = [item for item in ranked if item["cards"] and not item["is_bomb"]]
    if non_pass:
        smallest = min(
            non_pass,
            key=lambda item: corrective_action_sort_key(
                components,
                int(item["action_id"]),
                list(item["cards"]),
            ),
        )
        add(smallest, "smallest_non_bomb")
    bombs = [item for item in ranked if item["is_bomb"]]
    if bombs:
        smallest_bomb = min(
            bombs,
            key=lambda item: corrective_action_sort_key(
                components,
                int(item["action_id"]),
                list(item["cards"]),
            ),
        )
        add(smallest_bomb, "smallest_bomb")
    return selected


def offline_dmc_calibration_rollouts(
    base_game: Any,
    components: dict,
    profile_config: dict,
    candidates: list[dict],
    team_id: int,
    state_index: int,
    args: argparse.Namespace,
) -> list[dict]:
    evaluated: list[dict] = []
    rollout_count = max(1, int(args.dmc_calibration_rollouts_per_action))
    player_id = int(base_game.current_player)
    hand_sizes = [len(player.hand) for player in base_game.players]
    was_lead = bool(base_game.is_free_turn or not (base_game.last_play or []))
    for candidate in candidates:
        branch_results: list[dict] = []
        for rollout_index in range(rollout_count):
            seed = int(args.dmc_calibration_seed) + state_index * 100_000 + rollout_index
            branch_results.append(
                offline_paired_rollout_branch(
                    base_game,
                    components,
                    profile_config,
                    int(candidate["action_id"]),
                    list(candidate["cards"]),
                    team_id,
                    str(args.dmc_calibration_continuation_profile),
                    seed,
                    int(args.dmc_calibration_depth_turns),
                )
            )
        win_rate = sum(float(item["team_win_value"]) for item in branch_results) / len(branch_results)
        average_team_rank = sum(float(item["team_rank"]) for item in branch_results) / len(branch_results)
        team_value = win_rate * 2.0 - 1.0
        q_value = candidate.get("q_value")
        evaluated.append(
            {
                **candidate,
                "action_features": dmc_action_features(
                    components,
                    int(candidate["action_id"]),
                    list(candidate["cards"]),
                    player_id,
                    hand_sizes,
                    was_lead,
                    int(base_game.active_level),
                ),
                "rollout_win_rate": win_rate,
                "rollout_average_team_rank": average_team_rank,
                "rollout_team_value": team_value,
                "q_error": None if q_value is None else float(q_value) - team_value,
                "absolute_q_error": None if q_value is None else abs(float(q_value) - team_value),
                "terminal_rollout_count": sum(1 for item in branch_results if item["terminal"]),
                "rollouts": branch_results,
            }
        )
    return evaluated


def offline_dmc_calibration_context_summary(states: list[dict], predicate: Any) -> dict:
    subset = [state for state in states if predicate(state)]
    if not subset:
        return {
            "state_count": 0,
            "dmc_better_count": 0,
            "baseline_better_count": 0,
            "equal_count": 0,
            "average_realized_delta": 0.0,
            "overconfident_wrong_count": 0,
        }
    deltas = [float(state["realized_dmc_minus_baseline"]) for state in subset]
    return {
        "state_count": len(subset),
        "dmc_better_count": sum(1 for value in deltas if value > 0),
        "baseline_better_count": sum(1 for value in deltas if value < 0),
        "equal_count": sum(1 for value in deltas if value == 0),
        "average_realized_delta": sum(deltas) / len(deltas),
        "overconfident_wrong_count": sum(1 for state in subset if state["overconfident_wrong"]),
    }


def run_offline_dmc_q_calibration_audit(args: argparse.Namespace) -> None:
    if args.baseline_profile != "tempo_baseline":
        raise RuntimeError("DMC Q calibration currently only supports --baseline-profile tempo_baseline")
    components = offline_load_guandan_components()
    GuandanGame = components["GuandanGame"]
    device_info = offline_resolve_device(args.device)
    model_path = Path(args.dmc_model)
    if not model_path.exists():
        raise RuntimeError(f"DMC model not found: {model_path}")
    model = offline_load_dmc_value_model(model_path, device_info)
    profiles = load_json(PROFILE_PATH, {})
    profile_config = profiles.get("tempo_baseline", {"engine_mode": "tempo"})
    equivalence = offline_baseline_equivalence_check(
        components,
        profile_config,
        sample_count=max(200, int(args.dmc_calibration_equivalence_samples)),
    )
    out_path = Path(args.dmc_calibration_out)
    result = {
        "status": "running",
        "backend": device_info["backend"],
        "requested_device": device_info["requested_device"],
        "actual_device": device_info["actual_device"],
        "legal_mask_source": "website_oracle",
        "dmc_model": str(model_path),
        "baseline_profile": args.baseline_profile,
        "target_states": int(args.dmc_calibration_states),
        "top_k_actions": int(args.dmc_calibration_top_k),
        "rollouts_per_action": int(args.dmc_calibration_rollouts_per_action),
        "depth_turns": int(args.dmc_calibration_depth_turns),
        "continuation_profile": str(args.dmc_calibration_continuation_profile),
        "minimum_q_margin": float(args.dmc_calibration_min_q_margin),
        "calibration_seed": int(args.dmc_calibration_seed),
        "first_player_policy": "random_each_game",
        "first_player_distribution": {"0": 0, "1": 0, "2": 0, "3": 0},
        "scanned_games": 0,
        "scanned_decisions": 0,
        "evaluated_states": 0,
        "evaluated_actions": 0,
        "states": [],
        "scanner_illegal_action_count": 0,
        "scanner_fallback_count": 0,
        "scanner_materialization_fail_count": 0,
        "scanner_hand_card_mismatch_count": 0,
        **equivalence,
    }
    if (
        int(equivalence["baseline_equivalence_samples"]) < 200
        or int(equivalence["baseline_equivalence_mismatch_count"]) != 0
    ):
        save_json(out_path, result)
        raise RuntimeError("baseline equivalence check failed; DMC Q calibration blocked")

    target_states = max(1, int(args.dmc_calibration_states))
    rng = random.Random(int(args.dmc_calibration_seed))
    restore_baseline = offline_install_arena_baseline_optimizations()
    started = time.monotonic()
    try:
        for game_index in range(max(1, int(args.dmc_calibration_max_games))):
            if len(result["states"]) >= target_states:
                break
            random.seed(int(args.dmc_calibration_seed) + game_index)
            game = GuandanGame(verbose=False, print_history=False)
            first_player = offline_set_random_first_player(game, rng)
            result["first_player_distribution"][str(first_player)] += 1
            steps = 0
            while not game.is_game_over and steps < OFFLINE_MAX_GAME_STEPS:
                offline_prepare_turn(game)
                if game.current_player in game.ranking:
                    steps += 1
                    continue
                result["scanned_decisions"] += 1
                baseline_info = offline_baseline_action_info(
                    game,
                    components,
                    "tempo_baseline",
                    profile_config,
                    rng,
                )
                state, ranked = offline_dmc_ranked_candidates(
                    game,
                    components,
                    model,
                    device_info["device"],
                )
                baseline_cards = list(baseline_info.get("chosen_cards") or [])
                baseline_action_id = int(baseline_info.get("action_id", 0))
                if ranked:
                    baseline_q = offline_dmc_score_action(
                        game,
                        components,
                        model,
                        device_info["device"],
                        state,
                        baseline_action_id,
                        baseline_cards,
                    )
                    best = ranked[0]
                    same_action = rollout_action_key(baseline_action_id, baseline_cards) == rollout_action_key(
                        int(best["action_id"]),
                        list(best["cards"]),
                    )
                    q_margin = float(best["q_value"]) - float(baseline_q)
                    if not same_action and q_margin >= float(args.dmc_calibration_min_q_margin):
                        base_game = copy.deepcopy(game)
                        candidates = offline_dmc_calibration_candidate_set(
                            components,
                            ranked,
                            baseline_action_id,
                            baseline_cards,
                            int(args.dmc_calibration_top_k),
                        )
                        for candidate in candidates:
                            if candidate.get("q_value") is None:
                                candidate["q_value"] = offline_dmc_score_action(
                                    game,
                                    components,
                                    model,
                                    device_info["device"],
                                    state,
                                    int(candidate["action_id"]),
                                    list(candidate["cards"]),
                                )
                        evaluated = offline_dmc_calibration_rollouts(
                            base_game,
                            components,
                            profile_config,
                            candidates,
                            offline_team_id(int(game.current_player)),
                            len(result["states"]),
                            args,
                        )
                        baseline_eval = next(item for item in evaluated if "tempo_baseline" in item["sources"])
                        dmc_eval = next(item for item in evaluated if "dmc_top_k" in item["sources"])
                        rollout_best = max(
                            evaluated,
                            key=lambda item: (
                                float(item["rollout_win_rate"]),
                                -float(item["rollout_average_team_rank"]),
                                float(item["q_value"]),
                            ),
                        )
                        pairwise_comparable = 0
                        pairwise_agree = 0
                        for left_index, left in enumerate(evaluated):
                            for right in evaluated[left_index + 1 :]:
                                q_delta = float(left["q_value"]) - float(right["q_value"])
                                rollout_delta = float(left["rollout_win_rate"]) - float(right["rollout_win_rate"])
                                if rollout_delta == 0.0:
                                    rollout_delta = float(right["rollout_average_team_rank"]) - float(
                                        left["rollout_average_team_rank"]
                                    )
                                if q_delta == 0.0 or rollout_delta == 0.0:
                                    continue
                                pairwise_comparable += 1
                                pairwise_agree += int((q_delta > 0.0) == (rollout_delta > 0.0))
                        realized_delta = float(dmc_eval["rollout_win_rate"]) - float(
                            baseline_eval["rollout_win_rate"]
                        )
                        realized_rank_improvement = float(baseline_eval["rollout_average_team_rank"]) - float(
                            dmc_eval["rollout_average_team_rank"]
                        )
                        state_result = {
                            "state_index": len(result["states"]),
                            "obs": state.tolist() if hasattr(state, "tolist") else list(state),
                            "game_index": game_index,
                            "step": steps,
                            "first_player": first_player,
                            "player_id": int(game.current_player),
                            "team_id": offline_team_id(int(game.current_player)),
                            "level": website_level_from_local_level(game.active_level),
                            "was_follow": bool(baseline_info.get("was_follow")),
                            "is_endgame": offline_hybrid_is_endgame(game, int(game.current_player)),
                            "opponent_min": offline_hybrid_opponent_min(game, int(game.current_player)),
                            "teammate_min": offline_hybrid_teammate_min(game, int(game.current_player)),
                            "hand_sizes": [len(player.hand) for player in game.players],
                            "hand_before": local_cards_to_website(list(game.players[int(game.current_player)].hand)),
                            "last_play": local_cards_to_website(list(game.last_play or [])),
                            "baseline_action_id": baseline_action_id,
                            "baseline_action": local_cards_to_website(baseline_cards),
                            "baseline_action_type": str(baseline_info.get("action_type") or "unknown"),
                            "baseline_q": float(baseline_q),
                            "dmc_action_id": int(best["action_id"]),
                            "dmc_action": local_cards_to_website(list(best["cards"])),
                            "dmc_action_type": str(best["action_type"]),
                            "dmc_q": float(best["q_value"]),
                            "q_margin": q_margin,
                            "q_margin_bucket": offline_dmc_calibration_bucket(q_margin),
                            "baseline_rollout_win_rate": float(baseline_eval["rollout_win_rate"]),
                            "dmc_rollout_win_rate": float(dmc_eval["rollout_win_rate"]),
                            "realized_dmc_minus_baseline": realized_delta,
                            "baseline_rollout_average_team_rank": float(
                                baseline_eval["rollout_average_team_rank"]
                            ),
                            "dmc_rollout_average_team_rank": float(dmc_eval["rollout_average_team_rank"]),
                            "realized_dmc_rank_improvement": realized_rank_improvement,
                            "rollout_best_action_id": int(rollout_best["action_id"]),
                            "rollout_best_action": local_cards_to_website(list(rollout_best["cards"])),
                            "rollout_best_action_type": str(rollout_best["action_type"]),
                            "q_top1_matches_rollout_best": rollout_action_key(
                                int(best["action_id"]), list(best["cards"])
                            ) == rollout_action_key(int(rollout_best["action_id"]), list(rollout_best["cards"])),
                            "q_top1_rollout_regret": float(rollout_best["rollout_win_rate"])
                            - float(dmc_eval["rollout_win_rate"]),
                            "q_top1_rollout_rank_regret": float(dmc_eval["rollout_average_team_rank"])
                            - float(rollout_best["rollout_average_team_rank"]),
                            "pairwise_comparable_count": pairwise_comparable,
                            "pairwise_q_order_agree_count": pairwise_agree,
                            "pairwise_q_order_agreement_rate": pairwise_agree / max(1, pairwise_comparable),
                            "overconfident_wrong": bool(
                                q_margin >= 0.25
                                and (realized_delta < 0.0 or (realized_delta == 0.0 and realized_rank_improvement < 0.0))
                            ),
                            "actions": evaluated,
                        }
                        result["states"].append(state_result)
                        result["evaluated_states"] = len(result["states"])
                        result["evaluated_actions"] += len(evaluated)
                        result["elapsed_seconds"] = time.monotonic() - started
                        save_json(out_path, result)
                        print(
                            "dmc_calibration_hit "
                            f"state={len(result['states'])}/{target_states} game={game_index} step={steps} "
                            f"q_margin={q_margin:.3f} realized_delta={realized_delta:.3f}",
                            flush=True,
                        )
                        if len(result["states"]) >= target_states:
                            break
                record = offline_apply_action(game, baseline_info)
                result["scanner_illegal_action_count"] += int(bool(record.get("illegal")))
                result["scanner_fallback_count"] += int(bool(record.get("fallback")))
                result["scanner_materialization_fail_count"] += int(bool(record.get("materialization_fail")))
                result["scanner_hand_card_mismatch_count"] += int(bool(record.get("hand_card_mismatch")))
                steps += 1
            result["scanned_games"] += 1
    finally:
        restore_baseline()

    states = result["states"]
    actions = [action for state in states for action in state.get("actions") or []]
    q_actions = [action for action in actions if action.get("q_value") is not None]
    squared_errors = [float(action["q_error"]) ** 2 for action in q_actions]
    absolute_errors = [float(action["absolute_q_error"]) for action in q_actions]
    brier_errors = [
        ((max(-1.0, min(1.0, float(action["q_value"]))) + 1.0) / 2.0 - float(action["rollout_win_rate"])) ** 2
        for action in q_actions
    ]
    bucket_summary: dict[str, dict] = {}
    for bucket in ("lt_0.10", "0.10_to_0.25", "0.25_to_0.50", "ge_0.50"):
        bucket_states = [state for state in states if state["q_margin_bucket"] == bucket]
        bucket_summary[bucket] = offline_dmc_calibration_context_summary(bucket_states, lambda _state: True)
    contexts = {
        "follow": offline_dmc_calibration_context_summary(states, lambda state: state["was_follow"]),
        "lead": offline_dmc_calibration_context_summary(states, lambda state: not state["was_follow"]),
        "endgame": offline_dmc_calibration_context_summary(states, lambda state: state["is_endgame"]),
        "dmc_pass": offline_dmc_calibration_context_summary(states, lambda state: not state["dmc_action"]),
        "dmc_bomb": offline_dmc_calibration_context_summary(
            states,
            lambda state: "bomb" in str(state["dmc_action_type"]),
        ),
    }
    branch_counter_names = (
        "illegal_action_count",
        "fallback_count",
        "materialization_fail_count",
        "hand_card_mismatch_count",
        "oracle_candidate_validation_fail_count",
    )
    for name in branch_counter_names:
        result[f"rollout_{name}"] = sum(
            int(rollout.get(name) or 0)
            for action in actions
            for rollout in action.get("rollouts") or []
        )
    result["rollout_oracle_option_fallback_count"] = sum(
        int(rollout.get("oracle_option_fallback_count") or 0)
        for action in actions
        for rollout in action.get("rollouts") or []
    )
    pairwise_comparable = sum(int(state["pairwise_comparable_count"]) for state in states)
    pairwise_agree = sum(int(state["pairwise_q_order_agree_count"]) for state in states)
    result.update(
        {
            "status": "completed",
            "elapsed_seconds": time.monotonic() - started,
            "q_value_mse": sum(squared_errors) / max(1, len(squared_errors)),
            "q_value_mae": sum(absolute_errors) / max(1, len(absolute_errors)),
            "q_probability_brier_score": sum(brier_errors) / max(1, len(brier_errors)),
            "q_top1_matches_rollout_best_count": sum(1 for state in states if state["q_top1_matches_rollout_best"]),
            "q_top1_matches_rollout_best_rate": sum(1 for state in states if state["q_top1_matches_rollout_best"])
            / max(1, len(states)),
            "average_q_top1_rollout_regret": sum(float(state["q_top1_rollout_regret"]) for state in states)
            / max(1, len(states)),
            "average_q_top1_rollout_rank_regret": sum(
                float(state["q_top1_rollout_rank_regret"]) for state in states
            )
            / max(1, len(states)),
            "pairwise_comparable_count": pairwise_comparable,
            "pairwise_q_order_agree_count": pairwise_agree,
            "pairwise_q_order_agreement_rate": pairwise_agree / max(1, pairwise_comparable),
            "dmc_outperforms_baseline_count": sum(
                1 for state in states if state["realized_dmc_minus_baseline"] > 0
            ),
            "baseline_outperforms_dmc_count": sum(
                1 for state in states if state["realized_dmc_minus_baseline"] < 0
            ),
            "equal_outcome_count": sum(1 for state in states if state["realized_dmc_minus_baseline"] == 0),
            "average_realized_dmc_minus_baseline": sum(
                float(state["realized_dmc_minus_baseline"]) for state in states
            )
            / max(1, len(states)),
            "average_realized_dmc_rank_improvement": sum(
                float(state["realized_dmc_rank_improvement"]) for state in states
            )
            / max(1, len(states)),
            "overconfident_wrong_count": sum(1 for state in states if state["overconfident_wrong"]),
            "q_margin_bucket_summary": bucket_summary,
            "context_summary": contexts,
        }
    )
    correctness_passed = bool(
        len(states) >= target_states
        and result["scanner_illegal_action_count"] == 0
        and result["scanner_fallback_count"] == 0
        and result["scanner_materialization_fail_count"] == 0
        and result["scanner_hand_card_mismatch_count"] == 0
        and all(result[f"rollout_{name}"] == 0 for name in branch_counter_names)
    )
    result["threshold_passed"] = correctness_passed
    result["q_calibration_acceptable"] = bool(
        correctness_passed
        and len(states) >= 30
        and result["q_top1_matches_rollout_best_rate"] >= 0.60
        and result["average_realized_dmc_minus_baseline"] > 0.0
        and result["overconfident_wrong_count"] == 0
    )
    result["recommendation"] = (
        "build_pairwise_action_value_dataset"
        if correctness_passed and not result["q_calibration_acceptable"]
        else "q_calibration_supports_larger_hybrid_validation"
        if result["q_calibration_acceptable"]
        else "fix_calibration_audit_before_policy_work"
    )
    save_json(out_path, result)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if not correctness_passed:
        raise RuntimeError("DMC Q calibration audit correctness threshold failed")


def dmc_pairwise_preference(
    left: dict,
    right: dict,
    min_win_delta: float,
    min_rank_delta: float,
) -> tuple[dict, dict, float, float] | None:
    win_delta = float(left.get("rollout_win_rate") or 0.0) - float(right.get("rollout_win_rate") or 0.0)
    if abs(win_delta) > float(min_win_delta):
        return (left, right, win_delta, 0.0) if win_delta > 0.0 else (right, left, -win_delta, 0.0)
    if win_delta != 0.0:
        return None
    rank_delta = float(right.get("rollout_average_team_rank") or 4.0) - float(
        left.get("rollout_average_team_rank") or 4.0
    )
    if abs(rank_delta) < float(min_rank_delta):
        return None
    return (left, right, 0.0, rank_delta) if rank_delta > 0.0 else (right, left, 0.0, -rank_delta)


def dmc_pairwise_sample_valid(sample: dict) -> tuple[bool, str | None]:
    if len(sample.get("obs") or []) != OFFLINE_STATE_DIM:
        return False, "obs_dim_mismatch"
    if len(sample.get("preferred_action_features") or []) != DMC_ACTION_FEATURE_DIM:
        return False, "preferred_action_feature_dim_mismatch"
    if len(sample.get("rejected_action_features") or []) != DMC_ACTION_FEATURE_DIM:
        return False, "rejected_action_feature_dim_mismatch"
    preferred_id = int(sample.get("preferred_action_id", -1))
    rejected_id = int(sample.get("rejected_action_id", -1))
    if not 0 <= preferred_id < OFFLINE_ACTION_DIM:
        return False, "preferred_action_id_out_of_range"
    if not 0 <= rejected_id < OFFLINE_ACTION_DIM:
        return False, "rejected_action_id_out_of_range"
    if preferred_id == rejected_id and tuple(sorted(sample.get("preferred_cards") or [])) == tuple(
        sorted(sample.get("rejected_cards") or [])
    ):
        return False, "identical_action_pair"
    return True, None


def run_build_dmc_pairwise_dataset(args: argparse.Namespace) -> None:
    source_paths = [Path(item.strip()) for item in str(args.dmc_calibration_source or "").split(",") if item.strip()]
    if not source_paths:
        raise RuntimeError("--dmc-calibration-source is required with --build-dmc-pairwise-dataset")
    samples: list[dict] = []
    reject_reasons: Counter = Counter()
    source_counts: Counter = Counter()
    action_type_pairs: Counter = Counter()
    state_count = 0
    raw_pair_count = 0
    for source_path in source_paths:
        source = load_json(source_path, {})
        if not source_path.exists():
            reject_reasons["source_not_found"] += 1
            continue
        if source.get("legal_mask_source") != "website_oracle":
            reject_reasons["not_website_oracle"] += 1
            continue
        for state in source.get("states") or []:
            state_count += 1
            obs = list(state.get("obs") or [])
            actions = list(state.get("actions") or [])
            state_samples: list[dict] = []
            for left_index, left in enumerate(actions):
                for right in actions[left_index + 1 :]:
                    raw_pair_count += 1
                    preference = dmc_pairwise_preference(
                        left,
                        right,
                        float(args.dmc_pairwise_min_win_delta),
                        float(args.dmc_pairwise_min_rank_delta),
                    )
                    if preference is None:
                        reject_reasons["no_material_rollout_difference"] += 1
                        continue
                    preferred, rejected, win_delta, rank_improvement = preference
                    sample = {
                        "obs": obs,
                        "preferred_action_id": int(preferred.get("action_id", -1)),
                        "preferred_action_features": list(preferred.get("action_features") or []),
                        "preferred_cards": list(preferred.get("cards") or []),
                        "preferred_action_type": str(preferred.get("action_type") or "unknown"),
                        "preferred_sources": list(preferred.get("sources") or []),
                        "preferred_rollout_win_rate": float(preferred.get("rollout_win_rate") or 0.0),
                        "preferred_rollout_average_team_rank": float(
                            preferred.get("rollout_average_team_rank") or 4.0
                        ),
                        "rejected_action_id": int(rejected.get("action_id", -1)),
                        "rejected_action_features": list(rejected.get("action_features") or []),
                        "rejected_cards": list(rejected.get("cards") or []),
                        "rejected_action_type": str(rejected.get("action_type") or "unknown"),
                        "rejected_sources": list(rejected.get("sources") or []),
                        "rejected_rollout_win_rate": float(rejected.get("rollout_win_rate") or 0.0),
                        "rejected_rollout_average_team_rank": float(
                            rejected.get("rollout_average_team_rank") or 4.0
                        ),
                        "rollout_win_delta": float(win_delta),
                        "rollout_rank_improvement": float(rank_improvement),
                        "weight": float(max(1.0, 1.0 + win_delta * 2.0 + rank_improvement / 2.0)),
                        "state_group": f"{source_path}:{state.get('game_index')}:{state.get('step')}",
                        "source_path": str(source_path),
                        "game_index": state.get("game_index"),
                        "step": state.get("step"),
                        "player_id": state.get("player_id"),
                        "was_follow": bool(state.get("was_follow")),
                        "is_endgame": bool(state.get("is_endgame")),
                        "opponent_min": state.get("opponent_min"),
                        "teammate_min": state.get("teammate_min"),
                        "metric_source": "paired_offline_rollout",
                    }
                    valid, reason = dmc_pairwise_sample_valid(sample)
                    if not valid:
                        reject_reasons[str(reason or "invalid_pair")] += 1
                        continue
                    state_samples.append(sample)
            state_samples.sort(
                key=lambda sample: (
                    float(sample["rollout_win_delta"]),
                    float(sample["rollout_rank_improvement"]),
                    float(sample["weight"]),
                ),
                reverse=True,
            )
            limit = max(1, int(args.dmc_pairwise_max_pairs_per_state))
            for sample in state_samples[:limit]:
                samples.append(sample)
                source_counts[str(source_path)] += 1
                action_type_pairs[
                    f"{sample['preferred_action_type']}>{sample['rejected_action_type']}"
                ] += 1
            if len(state_samples) > limit:
                reject_reasons["per_state_limit"] += len(state_samples) - limit
    summary = {
        "format": "dmc_pairwise_action_value_dataset_v1",
        "source_paths": [str(path) for path in source_paths],
        "source_file_count": len(source_paths),
        "source_state_count": state_count,
        "raw_pair_count": raw_pair_count,
        "pairwise_sample_count": len(samples),
        "unique_state_group_count": len({sample["state_group"] for sample in samples}),
        "source_sample_counts": dict(source_counts),
        "action_type_pair_distribution": dict(action_type_pairs),
        "reject_reasons": dict(reject_reasons),
        "state_dim": OFFLINE_STATE_DIM,
        "action_feature_dim": DMC_ACTION_FEATURE_DIM,
        "metric_source": "paired_offline_rollout",
        "legal_mask_source": "website_oracle",
        "threshold_passed": bool(samples),
    }
    out_path = Path(args.dmc_pairwise_dataset_out)
    write_dmc_dataset(out_path, dmc_dataset_format(out_path), samples, summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    if not summary["threshold_passed"]:
        raise RuntimeError("no valid DMC pairwise samples were built")


def dmc_pairwise_split_indices(samples: list[dict], validation_split: float, rng: random.Random) -> tuple[list[int], list[int]]:
    groups: dict[str, list[int]] = {}
    for index, sample in enumerate(samples):
        groups.setdefault(str(sample.get("state_group") or index), []).append(index)
    group_names = list(groups)
    rng.shuffle(group_names)
    val_group_count = max(1, int(round(len(group_names) * float(validation_split)))) if len(group_names) > 1 else 0
    val_groups = set(group_names[:val_group_count])
    train_indices = [index for name, indices in groups.items() if name not in val_groups for index in indices]
    val_indices = [index for name, indices in groups.items() if name in val_groups for index in indices]
    return train_indices, val_indices


def dmc_pairwise_metrics(model: Any, samples: list[dict], indices: list[int], batch_size: int, device: Any) -> dict:
    import numpy as np
    import torch
    import torch.nn.functional as F

    if not indices:
        return {"pairwise_loss": 0.0, "pairwise_accuracy": 0.0, "average_q_margin": 0.0}
    loss_sum = 0.0
    correct = 0
    margin_sum = 0.0
    sample_count = 0
    with torch.no_grad():
        for start in range(0, len(indices), batch_size):
            batch_indices = indices[start : start + batch_size]
            states = torch.tensor(
                np.asarray([samples[index]["obs"] for index in batch_indices], dtype=np.float32),
                dtype=torch.float32,
                device=device,
            )
            preferred = torch.tensor(
                np.asarray([samples[index]["preferred_action_features"] for index in batch_indices], dtype=np.float32),
                dtype=torch.float32,
                device=device,
            )
            rejected = torch.tensor(
                np.asarray([samples[index]["rejected_action_features"] for index in batch_indices], dtype=np.float32),
                dtype=torch.float32,
                device=device,
            )
            margins = model(states, preferred) - model(states, rejected)
            loss_sum += float(F.softplus(-margins).sum().item())
            correct += int((margins > 0.0).sum().item())
            margin_sum += float(margins.sum().item())
            sample_count += len(batch_indices)
    return {
        "pairwise_loss": loss_sum / max(1, sample_count),
        "pairwise_accuracy": correct / max(1, sample_count),
        "average_q_margin": margin_sum / max(1, sample_count),
    }


def run_train_dmc_pairwise(args: argparse.Namespace) -> None:
    device_info = offline_resolve_device(args.device)
    torch = device_info.get("torch")
    if torch is None:
        raise RuntimeError("torch backend is required for DMC pairwise training")
    samples, dataset_summary, dataset_format = load_dmc_dataset(Path(args.dmc_pairwise_dataset))
    invalid_reasons: Counter = Counter()
    for sample in samples:
        valid, reason = dmc_pairwise_sample_valid(sample)
        if not valid:
            invalid_reasons[str(reason or "invalid_pair")] += 1
    if invalid_reasons:
        raise RuntimeError(f"invalid DMC pairwise samples: {dict(invalid_reasons)}")
    model_path = Path(args.init_dmc_model)
    if not model_path.exists():
        raise RuntimeError(f"initial DMC model not found: {model_path}")
    model = offline_load_dmc_value_model(model_path, device_info)
    reference = offline_load_dmc_value_model(model_path, device_info)
    for parameter in reference.parameters():
        parameter.requires_grad_(False)
    rng = random.Random(int(args.dmc_pairwise_seed))
    train_indices, val_indices = dmc_pairwise_split_indices(samples, float(args.validation_split), rng)
    if not train_indices or not val_indices:
        raise RuntimeError("DMC pairwise dataset needs at least two state groups for train/validation split")
    optimizer = torch.optim.Adam(model.parameters(), lr=float(args.dmc_pairwise_lr))
    out_dir = Path(args.dmc_pairwise_out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    best_path = out_dir / "dmc_pairwise_best.pth"
    log = {
        "backend": device_info["backend"],
        "requested_device": device_info["requested_device"],
        "actual_device": device_info["actual_device"],
        "dataset_path": str(args.dmc_pairwise_dataset),
        "dataset_format": dataset_format,
        "dataset_summary": dataset_summary,
        "init_dmc_model": str(model_path),
        "sample_count": len(samples),
        "train_sample_count": len(train_indices),
        "val_sample_count": len(val_indices),
        "train_state_group_count": len({samples[index]["state_group"] for index in train_indices}),
        "val_state_group_count": len({samples[index]["state_group"] for index in val_indices}),
        "epochs": int(args.dmc_pairwise_epochs),
        "batch_size": int(args.batch_size),
        "learning_rate": float(args.dmc_pairwise_lr),
        "ranking_margin": float(args.dmc_pairwise_margin),
        "anchor_weight": float(args.dmc_pairwise_anchor_weight),
        "train_pairwise_loss_by_epoch": [],
        "val_pairwise_loss_by_epoch": [],
        "train_pairwise_accuracy_by_epoch": [],
        "val_pairwise_accuracy_by_epoch": [],
        "val_average_q_margin_by_epoch": [],
        "best_epoch": None,
        "best_val_pairwise_accuracy": None,
        "best_val_pairwise_loss": None,
        "saved_checkpoints": [],
        "threshold_passed": False,
    }
    import numpy as np
    import torch.nn.functional as F

    best_key = (-1.0, float("inf"))
    for epoch in range(1, int(args.dmc_pairwise_epochs) + 1):
        rng.shuffle(train_indices)
        model.train()
        for start in range(0, len(train_indices), int(args.batch_size)):
            batch_indices = train_indices[start : start + int(args.batch_size)]
            states = torch.tensor(
                np.asarray([samples[index]["obs"] for index in batch_indices], dtype=np.float32),
                dtype=torch.float32,
                device=device_info["device"],
            )
            preferred = torch.tensor(
                np.asarray([samples[index]["preferred_action_features"] for index in batch_indices], dtype=np.float32),
                dtype=torch.float32,
                device=device_info["device"],
            )
            rejected = torch.tensor(
                np.asarray([samples[index]["rejected_action_features"] for index in batch_indices], dtype=np.float32),
                dtype=torch.float32,
                device=device_info["device"],
            )
            weights = torch.tensor(
                [float(samples[index].get("weight", 1.0)) for index in batch_indices],
                dtype=torch.float32,
                device=device_info["device"],
            )
            preferred_q = model(states, preferred)
            rejected_q = model(states, rejected)
            ranking_loss = (
                F.softplus(-(preferred_q - rejected_q - float(args.dmc_pairwise_margin))) * weights
            ).sum() / weights.sum().clamp_min(1e-8)
            with torch.no_grad():
                reference_preferred = reference(states, preferred)
                reference_rejected = reference(states, rejected)
            anchor_loss = F.mse_loss(preferred_q, reference_preferred) + F.mse_loss(
                rejected_q,
                reference_rejected,
            )
            loss = ranking_loss + float(args.dmc_pairwise_anchor_weight) * anchor_loss
            optimizer.zero_grad()
            loss.backward()
            optimizer.step()
        model.eval()
        train_metrics = dmc_pairwise_metrics(
            model, samples, train_indices, int(args.batch_size), device_info["device"]
        )
        val_metrics = dmc_pairwise_metrics(model, samples, val_indices, int(args.batch_size), device_info["device"])
        log["train_pairwise_loss_by_epoch"].append(train_metrics["pairwise_loss"])
        log["val_pairwise_loss_by_epoch"].append(val_metrics["pairwise_loss"])
        log["train_pairwise_accuracy_by_epoch"].append(train_metrics["pairwise_accuracy"])
        log["val_pairwise_accuracy_by_epoch"].append(val_metrics["pairwise_accuracy"])
        log["val_average_q_margin_by_epoch"].append(val_metrics["average_q_margin"])
        key = (float(val_metrics["pairwise_accuracy"]), -float(val_metrics["pairwise_loss"]))
        if key > best_key:
            best_key = key
            log["best_epoch"] = epoch
            log["best_val_pairwise_accuracy"] = val_metrics["pairwise_accuracy"]
            log["best_val_pairwise_loss"] = val_metrics["pairwise_loss"]
            torch.save(
                {
                    "model_state_dict": model.state_dict(),
                    "state_dim": OFFLINE_STATE_DIM,
                    "action_feature_dim": DMC_ACTION_FEATURE_DIM,
                    "method": "dmc_pairwise_action_value",
                    "init_model": str(model_path),
                },
                best_path,
            )
        if int(args.dmc_pairwise_save_every) > 0 and epoch % int(args.dmc_pairwise_save_every) == 0:
            checkpoint = out_dir / f"dmc_pairwise_epoch{epoch}.pth"
            torch.save(
                {
                    "model_state_dict": model.state_dict(),
                    "state_dim": OFFLINE_STATE_DIM,
                    "action_feature_dim": DMC_ACTION_FEATURE_DIM,
                    "method": "dmc_pairwise_action_value",
                    "init_model": str(model_path),
                },
                checkpoint,
            )
            log["saved_checkpoints"].append(str(checkpoint))
    log["best_checkpoint"] = str(best_path) if best_path.exists() else None
    log["threshold_passed"] = bool(best_path.exists() and log["best_val_pairwise_accuracy"] is not None)
    save_json(out_dir / "dmc_pairwise_training_state.json", log)
    save_json(Path(args.dmc_pairwise_log_out), log)
    print(json.dumps(log, ensure_ascii=False, indent=2))
    if not log["threshold_passed"]:
        raise RuntimeError("DMC pairwise training threshold failed")


def run_offline_hybrid_paired_audit(args: argparse.Namespace) -> None:
    source_path = Path(args.paired_audit_source) if args.paired_audit_source else None
    source = load_json(source_path, {}) if source_path else {}
    if source_path and not source_path.exists():
        raise RuntimeError(f"paired audit source not found: {source_path}")
    model_value = args.dmc_model or source.get("dmc_model")
    if not model_value:
        raise RuntimeError("--dmc-model is required unless --paired-audit-source contains dmc_model")
    model_path = Path(str(model_value))
    if not model_path.exists():
        raise RuntimeError(f"DMC model not found: {model_path}")
    baseline_profile = str(source.get("baseline_profile") or args.baseline_profile)
    if baseline_profile != "tempo_baseline":
        raise RuntimeError("paired hybrid audit only supports tempo_baseline")

    paired_args = copy.copy(args)
    for field in (
        "hybrid_q_margin",
        "hybrid_max_override_rate",
        "hybrid_only_follow",
        "hybrid_only_endgame",
        "hybrid_forbid_pass_over_non_pass",
        "hybrid_block_only_when_opponent_le",
        "hybrid_non_pass_margin",
        "hybrid_avoid_bomb_unless_opponent_le",
        "hybrid_control_pass_margin",
    ):
        if source.get(field) is not None:
            setattr(paired_args, field, source[field])
    paired_args.simulate_hybrid_override_whitelist = True
    paired_args.baseline_profile = baseline_profile
    paired_args.swap_seats = bool(source.get("seat_swap_enabled")) if source else bool(args.swap_seats)

    components = offline_load_guandan_components()
    GuandanGame = components["GuandanGame"]
    device_info = offline_resolve_device(args.device)
    model = offline_load_dmc_value_model(model_path, device_info)
    profiles = load_json(PROFILE_PATH, {})
    profile_config = profiles.get("tempo_baseline", {"engine_mode": "tempo"})
    equivalence_samples = max(1, int(args.paired_equivalence_samples))
    equivalence = offline_baseline_equivalence_check(
        components,
        profile_config,
        sample_count=equivalence_samples,
    )
    if int(equivalence["baseline_equivalence_mismatch_count"]) != 0:
        raise RuntimeError("baseline equivalence check failed; paired audit blocked")

    requested_target_states = max(1, int(args.paired_target_states))
    max_games = max(1, int(args.paired_max_games))
    source_reference_games = max(1, int(source.get("arena_games") or max_games))
    source_override_records = list(source.get("hybrid_override_records") or [])
    source_override_keys = {
        (int(record.get("game_index")), int(record.get("step")))
        for record in source_override_records
        if record.get("game_index") is not None and record.get("step") is not None
    }
    source_game_indices = sorted({game_index for game_index, _step in source_override_keys})
    source_overrides_only = bool(args.paired_source_overrides_only and source_game_indices)
    if source_overrides_only:
        planned_game_indices = source_game_indices[:max_games]
        target_states = min(requested_target_states, len(source_override_keys))
        paired_args.hybrid_max_override_rate = 1.0
    else:
        planned_game_indices = list(range(max_games))
        target_states = requested_target_states
    first_player_rng = random.Random(int(args.paired_seed))
    first_player_by_game = {
        game_index: int(first_player_rng.randrange(4))
        for game_index in range(max(planned_game_indices or [0]) + 1)
    }
    hybrid_stats = offline_dmc_hybrid_stats_template()
    cases: list[dict] = []
    result = {
        "status": "running",
        "backend": device_info["backend"],
        "requested_device": device_info["requested_device"],
        "actual_device": device_info["actual_device"],
        "device_fallback": device_info["device_fallback"],
        "legal_mask_source": "website_oracle",
        "paired_audit_source": str(source_path) if source_path else None,
        "dmc_model": str(model_path),
        "baseline_profile": baseline_profile,
        "paired_requested_target_states": requested_target_states,
        "paired_target_states": target_states,
        "paired_min_states_for_gate": max(1, int(args.paired_min_states_for_gate)),
        "paired_max_games": max_games,
        "paired_source_overrides_only": source_overrides_only,
        "source_override_record_count": len(source_override_keys),
        "source_rate_limit_bypassed": source_overrides_only,
        "planned_game_count": len(planned_game_indices),
        "planned_game_indices": planned_game_indices,
        "paired_rollouts_per_state": max(1, int(args.paired_rollouts_per_state)),
        "paired_depth_turns": int(args.paired_depth_turns),
        "paired_continuation_profile": str(args.paired_continuation_profile),
        "paired_seed": int(args.paired_seed),
        "paired_equivalence_samples_requested": equivalence_samples,
        "hybrid_control_pass_margin": float(paired_args.hybrid_control_pass_margin),
        "seat_swap_enabled": bool(paired_args.swap_seats),
        "scanned_games": 0,
        "completed_scanner_games": 0,
        "collected_override_states": 0,
        "matched_source_override_count": 0,
        "source_expected_not_triggered_count": 0,
        "source_unrecorded_candidate_block_count": 0,
        "scanner_illegal_action_count": 0,
        "scanner_fallback_count": 0,
        "scanner_materialization_fail_count": 0,
        "scanner_hand_card_mismatch_count": 0,
        "cases": cases,
        **equivalence,
    }
    out_path = Path(args.paired_audit_out)
    restore_baseline = offline_install_arena_baseline_optimizations()
    started = time.monotonic()
    try:
        for scan_index, game_index in enumerate(planned_game_indices, start=1):
            if len(cases) >= target_states:
                break
            random.seed(int(args.paired_seed) + game_index)
            game = GuandanGame(verbose=False, print_history=False)
            first_player = int(first_player_by_game[game_index])
            game.current_player = first_player
            rng = random.Random(int(args.paired_seed) + game_index * 1_000_003 + 17)
            model_seats, baseline_seats = offline_arena_profile_seats(
                game_index,
                source_reference_games,
                bool(paired_args.swap_seats),
            )
            model_team = offline_team_id(next(iter(model_seats)))
            result["scanned_games"] += 1
            steps = 0
            stop_after_case = False
            while not game.is_game_over and steps < OFFLINE_MAX_GAME_STEPS:
                offline_prepare_turn(game)
                if game.current_player in game.ranking:
                    steps += 1
                    continue
                if int(game.current_player) in model_seats:
                    base_game = copy.deepcopy(game)
                    action_info = offline_dmc_hybrid_action_info(
                        game,
                        components,
                        model,
                        device_info["device"],
                        paired_args,
                        profile_config,
                        rng,
                        hybrid_stats,
                        game_index=game_index,
                        step=steps,
                    )
                    source_key = (game_index, steps)
                    is_source_target = source_key in source_override_keys
                    if source_overrides_only and is_source_target and not action_info.get("hybrid_used"):
                        result["source_expected_not_triggered_count"] += 1
                    should_evaluate = bool(
                        action_info.get("hybrid_used")
                        and (not source_overrides_only or is_source_target)
                    )
                    if should_evaluate:
                        baseline_cards = list(action_info.get("hybrid_baseline_cards") or [])
                        baseline_action_id = int(action_info.get("hybrid_baseline_action_id") or 0)
                        override_cards = list(action_info.get("chosen_cards") or [])
                        override_action_id = int(action_info.get("action_id") or 0)
                        evaluation = offline_paired_state_evaluation(
                            base_game,
                            components,
                            profile_config,
                            {"action_id": baseline_action_id, "cards": baseline_cards},
                            {"action_id": override_action_id, "cards": override_cards},
                            model_team,
                            len(cases),
                            args,
                        )
                        case = {
                            "state_index": len(cases),
                            "game_index": game_index,
                            "step": steps,
                            "first_player": first_player,
                            "player_id": int(game.current_player),
                            "model_team": model_team,
                            "level": website_level_from_local_level(game.active_level),
                            "hand_sizes": [len(player.hand) for player in game.players],
                            "hand_before": local_cards_to_website(list(game.players[int(game.current_player)].hand)),
                            "last_play": local_cards_to_website(list(game.last_play or [])),
                            "last_player": game.last_player,
                            "baseline_action_id": baseline_action_id,
                            "baseline_action": local_cards_to_website(baseline_cards),
                            "baseline_action_type": str(
                                (components["action_by_id"].get(baseline_action_id) or {}).get("type") or "unknown"
                            ),
                            "override_action_id": override_action_id,
                            "override_action": local_cards_to_website(override_cards),
                            "override_action_type": str(action_info.get("action_type") or "unknown"),
                            "baseline_q": float(action_info.get("hybrid_baseline_q") or 0.0),
                            "override_q": float(action_info.get("hybrid_best_q") or 0.0),
                            "q_margin": float(action_info.get("hybrid_q_margin") or 0.0),
                            "matched_source_override": (game_index, steps) in source_override_keys,
                            **evaluation,
                        }
                        cases.append(case)
                        result["collected_override_states"] = len(cases)
                        result["matched_source_override_count"] += int(case["matched_source_override"])
                        result["elapsed_seconds"] = time.monotonic() - started
                        save_json(out_path, result)
                        print(
                            "paired_audit_hit "
                            f"state={len(cases)}/{target_states} game={game_index} step={steps} "
                            f"delta={evaluation['causal_win_rate_delta']:.3f}",
                            flush=True,
                        )
                        stop_after_case = len(cases) >= target_states
                    elif source_overrides_only and action_info.get("hybrid_used"):
                        result["source_unrecorded_candidate_block_count"] += 1
                        baseline_cards = list(action_info.get("hybrid_baseline_cards") or [])
                        baseline_action_id = int(action_info.get("hybrid_baseline_action_id") or 0)
                        action_info = offline_make_action_info_from_cards(
                            game,
                            components,
                            baseline_cards,
                            rng,
                            policy="paired_source_baseline",
                            sampled_action_id=baseline_action_id,
                            audit_masks=False,
                        )
                elif int(game.current_player) in baseline_seats:
                    action_info = offline_baseline_action_info(
                        game,
                        components,
                        baseline_profile,
                        profile_config,
                        rng,
                    )
                else:
                    action_info = offline_first_oracle_action_info(
                        game,
                        components,
                        rng,
                        policy="paired_scanner_unknown",
                        fallback_reason="seat_not_assigned",
                    )
                if stop_after_case:
                    break
                record = offline_apply_action(game, action_info)
                result["scanner_illegal_action_count"] += int(bool(record.get("illegal")))
                result["scanner_fallback_count"] += int(bool(record.get("fallback")))
                result["scanner_materialization_fail_count"] += int(bool(record.get("materialization_fail")))
                result["scanner_hand_card_mismatch_count"] += int(bool(record.get("hand_card_mismatch")))
                steps += 1
            if game.is_game_over:
                result["completed_scanner_games"] += 1
            if scan_index % 10 == 0:
                print(
                    f"paired_audit_progress games={scan_index}/{len(planned_game_indices)} "
                    f"states={len(cases)}/{target_states}",
                    flush=True,
                )
    finally:
        restore_baseline()

    paired_deltas = [
        float(simulation["win_value_delta"])
        for case in cases
        for simulation in case.get("simulations") or []
    ]
    baseline_values = [
        float(simulation["baseline"]["team_win_value"])
        for case in cases
        for simulation in case.get("simulations") or []
    ]
    override_values = [
        float(simulation["override"]["team_win_value"])
        for case in cases
        for simulation in case.get("simulations") or []
    ]
    branch_counter_names = (
        "illegal_action_count",
        "fallback_count",
        "materialization_fail_count",
        "hand_card_mismatch_count",
        "oracle_candidate_validation_fail_count",
    )
    for counter_name in branch_counter_names:
        result[f"paired_{counter_name}"] = sum(
            int(simulation[branch].get(counter_name) or 0)
            for case in cases
            for simulation in case.get("simulations") or []
            for branch in ("baseline", "override")
        )
    result["paired_oracle_option_fallback_count"] = sum(
        int(simulation[branch].get("oracle_option_fallback_count") or 0)
        for case in cases
        for simulation in case.get("simulations") or []
        for branch in ("baseline", "override")
    )
    delta_mean, delta_low, delta_high = offline_paired_delta_interval(paired_deltas)
    result.update(
        {
            "status": "completed",
            "elapsed_seconds": time.monotonic() - started,
            "paired_simulation_count": len(paired_deltas),
            "baseline_win_rate": sum(baseline_values) / max(1, len(baseline_values)),
            "override_win_rate": sum(override_values) / max(1, len(override_values)),
            "causal_win_rate_delta": delta_mean,
            "causal_win_rate_delta_ci95_low": delta_low,
            "causal_win_rate_delta_ci95_high": delta_high,
            "improved_pair_count": sum(1 for value in paired_deltas if value > 0),
            "harmed_pair_count": sum(1 for value in paired_deltas if value < 0),
            "neutral_pair_count": sum(1 for value in paired_deltas if value == 0),
            "exact_terminal_pair_count": sum(
                1
                for case in cases
                for simulation in case.get("simulations") or []
                if simulation["baseline"]["terminal"] and simulation["override"]["terminal"]
            ),
        }
    )
    correctness_passed = bool(
        len(cases) >= target_states
        and (not source_overrides_only or result["matched_source_override_count"] >= target_states)
        and result["source_expected_not_triggered_count"] == 0
        and result["scanner_illegal_action_count"] == 0
        and result["scanner_fallback_count"] == 0
        and result["scanner_materialization_fail_count"] == 0
        and result["scanner_hand_card_mismatch_count"] == 0
        and all(result[f"paired_{name}"] == 0 for name in branch_counter_names)
    )
    result["threshold_passed"] = correctness_passed
    result["policy_gate_passed"] = bool(
        correctness_passed
        and len(cases) >= max(1, int(args.paired_min_states_for_gate))
        and delta_mean >= float(args.paired_min_win_delta)
        and delta_low > 0.0
        and result["exact_terminal_pair_count"] == len(paired_deltas)
    )
    result["recommendation"] = (
        "control_pass_override_worth_larger_validation"
        if result["policy_gate_passed"]
        else "do_not_promote_control_pass_override"
    )
    save_json(out_path, result)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if not correctness_passed:
        raise RuntimeError("paired hybrid audit correctness threshold failed")


def run_offline_dmc_hybrid_arena_eval(args: argparse.Namespace) -> None:
    if args.baseline_profile != "tempo_baseline":
        raise RuntimeError("DMC hybrid arena currently only supports --baseline-profile tempo_baseline")
    components = offline_load_guandan_components()
    GuandanGame = components["GuandanGame"]
    device_info = offline_resolve_device(args.device)
    model_path = Path(args.dmc_model)
    if not model_path.exists():
        raise RuntimeError(f"DMC model not found: {model_path}")
    model = offline_load_dmc_value_model(model_path, device_info)
    profiles = load_json(PROFILE_PATH, {})
    profile_config = profiles.get("tempo_baseline", {"engine_mode": "tempo"})
    equivalence = offline_baseline_equivalence_check(components, profile_config, sample_count=200)
    hybrid_stats = offline_dmc_hybrid_stats_template()
    result = {
        "backend": device_info["backend"],
        "requested_device": device_info["requested_device"],
        "actual_device": device_info["actual_device"],
        "device_fallback": device_info["device_fallback"],
        "legal_mask_source": "website_oracle",
        "dmc_model": str(model_path),
        "baseline_profile": args.baseline_profile,
        "arena_games": int(args.arena_games),
        "seat_swap_enabled": bool(args.swap_seats),
        "hybrid_q_margin": float(args.hybrid_q_margin),
        "hybrid_max_override_rate": float(args.hybrid_max_override_rate),
        "hybrid_only_follow": bool(args.hybrid_only_follow),
        "hybrid_only_endgame": bool(args.hybrid_only_endgame),
        "hybrid_forbid_pass_over_non_pass": bool(args.hybrid_forbid_pass_over_non_pass),
        "hybrid_block_only_when_opponent_le": int(args.hybrid_block_only_when_opponent_le),
        "hybrid_non_pass_margin": float(args.hybrid_non_pass_margin),
        "hybrid_avoid_bomb_unless_opponent_le": int(args.hybrid_avoid_bomb_unless_opponent_le),
        "hybrid_control_pass_margin": float(args.hybrid_control_pass_margin),
        "simulate_hybrid_override_whitelist": bool(args.simulate_hybrid_override_whitelist),
        "local_player_mapping": offline_local_player_mapping(),
        "team_mapping": offline_team_mapping(),
        "first_player_policy": "random_each_game",
        "first_player_distribution": {"0": 0, "1": 0, "2": 0, "3": 0},
        "completed_games": 0,
        "attempted_games": 0,
        "model_team_wins": 0,
        "baseline_team_wins": 0,
        "model_team_win_rate": 0.0,
        "baseline_team_win_rate": 0.0,
        "avg_game_length": 0.0,
        "illegal_action_count": 0,
        "fallback_count": 0,
        "materialization_fail_count": 0,
        "hand_card_mismatch_count": 0,
        "pass_rate": 0.0,
        "bomb_usage_rate": 0.0,
        "action_type_distribution": {},
        "allowed_for_shadow_eval": False,
        "allowed_for_website_dry_run": False,
        "concrete_failure_samples": [],
        **equivalence,
    }
    if (
        int(equivalence["baseline_equivalence_samples"]) < 200
        or int(equivalence["baseline_equivalence_mismatch_count"]) != 0
    ):
        save_json(Path(args.arena_out), result)
        raise RuntimeError("baseline equivalence check failed; DMC hybrid arena eval blocked")
    rng = random.Random(20260708)
    restore_baseline = offline_install_arena_baseline_optimizations()
    total_steps = 0
    total_passes = 0
    total_bombs = 0
    total_length = 0
    action_types: Counter = Counter()
    completed_index = 0
    try:
        max_attempts = max(int(args.arena_games) * 3, int(args.arena_games) + 10)
        while result["completed_games"] < int(args.arena_games) and result["attempted_games"] < max_attempts:
            game_index = completed_index
            game_seed = 20260708 + game_index
            random.seed(game_seed)
            game = GuandanGame(verbose=False, print_history=False)
            first_player = offline_set_random_first_player(game, rng)
            result["first_player_distribution"][str(first_player)] += 1
            model_seats, baseline_seats = offline_arena_profile_seats(
                completed_index,
                int(args.arena_games),
                bool(args.swap_seats),
            )
            model_team = offline_team_id(next(iter(model_seats)))
            steps = 0
            result["attempted_games"] += 1
            while not game.is_game_over and steps < OFFLINE_MAX_GAME_STEPS:
                offline_prepare_turn(game)
                if game.current_player in game.ranking:
                    steps += 1
                    continue
                if int(game.current_player) in model_seats:
                    action_info = offline_dmc_hybrid_action_info(
                        game,
                        components,
                        model,
                        device_info["device"],
                        args,
                        profile_config,
                        rng,
                        hybrid_stats,
                        game_index=game_index,
                        step=steps,
                    )
                elif int(game.current_player) in baseline_seats:
                    action_info = offline_baseline_action_info(
                        game,
                        components,
                        args.baseline_profile,
                        profile_config,
                        rng,
                    )
                else:
                    action_info = offline_first_oracle_action_info(
                        game,
                        components,
                        rng,
                        policy="unknown",
                        fallback_reason="seat_not_assigned",
                    )
                record = offline_apply_action(game, action_info)
                if record.get("illegal"):
                    result["illegal_action_count"] += 1
                if record.get("fallback"):
                    result["fallback_count"] += 1
                if record.get("materialization_fail"):
                    result["materialization_fail_count"] += 1
                if record.get("hand_card_mismatch"):
                    result["hand_card_mismatch_count"] += 1
                if (
                    record.get("illegal")
                    or record.get("fallback")
                    or record.get("materialization_fail")
                    or record.get("hand_card_mismatch")
                ) and len(result["concrete_failure_samples"]) < 20:
                    result["concrete_failure_samples"].append(
                        {
                            "game_index": completed_index,
                            "step": steps,
                            "player_id": record.get("player_id"),
                            "policy": record.get("policy"),
                            "action_id": record.get("action_id"),
                            "chosen_cards": record.get("chosen_cards"),
                            "illegal_reason": record.get("illegal_reason"),
                            "materialization_fail_reason": record.get("materialization_fail_reason"),
                        }
                    )
                total_steps += 1
                steps += 1
                action_types[str(record.get("action_type") or "unknown")] += 1
                if not record.get("chosen_cards"):
                    total_passes += 1
                if record.get("is_bomb"):
                    total_bombs += 1
            if not game.is_game_over:
                continue
            result["completed_games"] += 1
            total_length += steps
            winner_team = offline_winner_team_id(game)
            game_outcome = "win" if winner_team == model_team else "loss"
            for override_record in hybrid_stats["hybrid_override_records"]:
                if override_record.get("game_index") == game_index and override_record.get("game_outcome") is None:
                    override_record["game_outcome"] = game_outcome
                    override_record["winner_team"] = winner_team
                    override_record["model_team"] = model_team
            if winner_team == model_team:
                result["model_team_wins"] += 1
            else:
                result["baseline_team_wins"] += 1
            completed_index += 1
    finally:
        restore_baseline()
    completed = max(1, int(result["completed_games"]))
    result["model_team_win_rate"] = result["model_team_wins"] / completed
    result["baseline_team_win_rate"] = result["baseline_team_wins"] / completed
    result["avg_game_length"] = total_length / completed
    result["pass_rate"] = total_passes / max(1, total_steps)
    result["bomb_usage_rate"] = total_bombs / max(1, total_steps)
    result["action_type_distribution"] = dict(action_types)
    decision_count = max(1, int(hybrid_stats["hybrid_decision_count"]))
    hybrid_stats["hybrid_override_rate"] = int(hybrid_stats["hybrid_override_count"]) / decision_count
    hybrid_stats["hybrid_q_margin_avg"] = float(hybrid_stats["hybrid_q_margin_sum"]) / decision_count
    hybrid_stats["hybrid_baseline_q_avg"] = float(hybrid_stats["hybrid_baseline_q_sum"]) / decision_count
    hybrid_stats["hybrid_best_q_avg"] = float(hybrid_stats["hybrid_best_q_sum"]) / decision_count
    serializable_hybrid_stats = dict(hybrid_stats)
    serializable_hybrid_stats["hybrid_override_action_types"] = dict(hybrid_stats["hybrid_override_action_types"])
    serializable_hybrid_stats["hybrid_whitelist_reason_counts"] = dict(hybrid_stats["hybrid_whitelist_reason_counts"])
    serializable_hybrid_stats["hybrid_override_audit"] = offline_hybrid_override_audit_summary(
        list(hybrid_stats["hybrid_override_records"])
    )
    result.update(serializable_hybrid_stats)
    result["allowed_for_shadow_eval"] = bool(
        result["completed_games"] >= int(args.arena_games)
        and result["illegal_action_count"] == 0
        and result["fallback_count"] == 0
        and result["materialization_fail_count"] == 0
        and result["hand_card_mismatch_count"] == 0
        and result["hybrid_override_rate"] <= float(args.hybrid_max_override_rate) + 1e-9
        and result["model_team_win_rate"] >= 0.48
    )
    result["allowed_for_website_dry_run"] = bool(
        result["completed_games"] >= int(args.arena_games)
        and result["illegal_action_count"] == 0
        and result["fallback_count"] == 0
        and result["materialization_fail_count"] == 0
        and result["hand_card_mismatch_count"] == 0
        and result["hybrid_override_rate"] <= float(args.hybrid_max_override_rate) + 1e-9
        and result["model_team_win_rate"] >= 0.52
    )
    save_json(Path(args.arena_out), result)
    print(json.dumps(result, ensure_ascii=False, indent=2))


def run_offline_dmc_arena_eval(args: argparse.Namespace) -> None:
    if args.baseline_profile != "tempo_baseline":
        raise RuntimeError("DMC arena currently only supports --baseline-profile tempo_baseline")
    components = offline_load_guandan_components()
    GuandanGame = components["GuandanGame"]
    device_info = offline_resolve_device(args.device)
    model_path = Path(args.dmc_model)
    if not model_path.exists():
        raise RuntimeError(f"DMC model not found: {model_path}")
    model = offline_load_dmc_value_model(model_path, device_info)
    profiles = load_json(PROFILE_PATH, {})
    profile_config = profiles.get("tempo_baseline", {"engine_mode": "tempo"})
    equivalence = offline_baseline_equivalence_check(components, profile_config, sample_count=200)
    result = {
        "backend": device_info["backend"],
        "requested_device": device_info["requested_device"],
        "actual_device": device_info["actual_device"],
        "device_fallback": device_info["device_fallback"],
        "legal_mask_source": "website_oracle",
        "dmc_model": str(model_path),
        "baseline_profile": args.baseline_profile,
        "arena_games": int(args.arena_games),
        "seat_swap_enabled": bool(args.swap_seats),
        "local_player_mapping": offline_local_player_mapping(),
        "team_mapping": offline_team_mapping(),
        "first_player_policy": "random_each_game",
        "first_player_distribution": {"0": 0, "1": 0, "2": 0, "3": 0},
        "completed_games": 0,
        "attempted_games": 0,
        "model_team_wins": 0,
        "baseline_team_wins": 0,
        "model_team_win_rate": 0.0,
        "baseline_team_win_rate": 0.0,
        "avg_game_length": 0.0,
        "illegal_action_count": 0,
        "fallback_count": 0,
        "materialization_fail_count": 0,
        "hand_card_mismatch_count": 0,
        "pass_rate": 0.0,
        "bomb_usage_rate": 0.0,
        "action_type_distribution": {},
        "allowed_for_shadow_eval": False,
        "allowed_for_website_dry_run": False,
        "concrete_failure_samples": [],
        **equivalence,
    }
    if (
        int(equivalence["baseline_equivalence_samples"]) < 200
        or int(equivalence["baseline_equivalence_mismatch_count"]) != 0
    ):
        save_json(Path(args.arena_out), result)
        raise RuntimeError("baseline equivalence check failed; DMC arena eval blocked")
    rng = random.Random(20260707)
    restore_baseline = offline_install_arena_baseline_optimizations()
    total_steps = 0
    total_passes = 0
    total_bombs = 0
    total_length = 0
    action_types: Counter = Counter()
    completed_index = 0
    try:
        max_attempts = max(int(args.arena_games) * 3, int(args.arena_games) + 10)
        while result["completed_games"] < int(args.arena_games) and result["attempted_games"] < max_attempts:
            game_seed = 20260707 + completed_index
            random.seed(game_seed)
            game = GuandanGame(verbose=False, print_history=False)
            first_player = offline_set_random_first_player(game, rng)
            result["first_player_distribution"][str(first_player)] += 1
            model_seats, baseline_seats = offline_arena_profile_seats(
                completed_index,
                int(args.arena_games),
                bool(args.swap_seats),
            )
            model_team = offline_team_id(next(iter(model_seats)))
            steps = 0
            result["attempted_games"] += 1
            while not game.is_game_over and steps < OFFLINE_MAX_GAME_STEPS:
                offline_prepare_turn(game)
                if game.current_player in game.ranking:
                    steps += 1
                    continue
                if int(game.current_player) in model_seats:
                    action_info = offline_dmc_action_info(game, components, model, device_info["device"], rng)
                elif int(game.current_player) in baseline_seats:
                    action_info = offline_baseline_action_info(
                        game,
                        components,
                        args.baseline_profile,
                        profile_config,
                        rng,
                    )
                else:
                    action_info = offline_first_oracle_action_info(
                        game,
                        components,
                        rng,
                        policy="unknown",
                        fallback_reason="seat_not_assigned",
                    )
                record = offline_apply_action(game, action_info)
                if record.get("illegal"):
                    result["illegal_action_count"] += 1
                if record.get("fallback"):
                    result["fallback_count"] += 1
                if record.get("materialization_fail"):
                    result["materialization_fail_count"] += 1
                if record.get("hand_card_mismatch"):
                    result["hand_card_mismatch_count"] += 1
                if (
                    record.get("illegal")
                    or record.get("fallback")
                    or record.get("materialization_fail")
                    or record.get("hand_card_mismatch")
                ) and len(result["concrete_failure_samples"]) < 20:
                    result["concrete_failure_samples"].append(
                        {
                            "game_index": completed_index,
                            "step": steps,
                            "player_id": record.get("player_id"),
                            "policy": record.get("policy"),
                            "action_id": record.get("action_id"),
                            "chosen_cards": record.get("chosen_cards"),
                            "illegal_reason": record.get("illegal_reason"),
                            "materialization_fail_reason": record.get("materialization_fail_reason"),
                        }
                    )
                total_steps += 1
                steps += 1
                action_types[str(record.get("action_type") or "unknown")] += 1
                if not record.get("chosen_cards"):
                    total_passes += 1
                if record.get("is_bomb"):
                    total_bombs += 1
            if not game.is_game_over:
                continue
            result["completed_games"] += 1
            completed_index += 1
            total_length += steps
            winner_team = offline_winner_team_id(game)
            if winner_team == model_team:
                result["model_team_wins"] += 1
            else:
                result["baseline_team_wins"] += 1
    finally:
        restore_baseline()
    completed = max(1, int(result["completed_games"]))
    result["model_team_win_rate"] = result["model_team_wins"] / completed
    result["baseline_team_win_rate"] = result["baseline_team_wins"] / completed
    result["avg_game_length"] = total_length / completed
    result["pass_rate"] = total_passes / max(1, total_steps)
    result["bomb_usage_rate"] = total_bombs / max(1, total_steps)
    result["action_type_distribution"] = dict(action_types)
    result["allowed_for_shadow_eval"] = bool(
        result["completed_games"] >= int(args.arena_games)
        and result["illegal_action_count"] == 0
        and result["fallback_count"] == 0
        and result["materialization_fail_count"] == 0
        and result["hand_card_mismatch_count"] == 0
        and result["model_team_win_rate"] >= 0.48
    )
    result["allowed_for_website_dry_run"] = bool(
        result["completed_games"] >= int(args.arena_games)
        and result["illegal_action_count"] == 0
        and result["fallback_count"] == 0
        and result["materialization_fail_count"] == 0
        and result["hand_card_mismatch_count"] == 0
        and result["model_team_win_rate"] >= 0.52
    )
    save_json(Path(args.arena_out), result)
    print(json.dumps(result, ensure_ascii=False, indent=2))


def validate_imitation_samples(samples: list[dict]) -> dict:
    invalid = 0
    in_mask = 0
    for sample in samples:
        mask = sample.get("legal_mask") or []
        action_id = int(sample.get("teacher_action_id", -1))
        valid = (
            len(sample.get("obs") or []) == OFFLINE_STATE_DIM
            and len(mask) == OFFLINE_ACTION_DIM
            and 0 <= action_id < OFFLINE_ACTION_DIM
            and float(mask[action_id]) > 0
        )
        if valid:
            in_mask += 1
        else:
            invalid += 1
    return {
        "sample_count": len(samples),
        "invalid_sample_count": invalid,
        "action_dim_checked": True,
        "legal_mask_dim_checked": invalid == 0,
        "teacher_action_in_mask_rate": in_mask / max(1, len(samples)),
    }


IMITATION_PASS_TYPES = {"", "None", "none", "pass", "PASS", "null"}
IMITATION_KEY_ACTION_TYPES = {"straight", "three_with_pair", "pair_chain", "gangban", "flush_rocket"}


def imitation_action_type(sample: dict) -> str:
    action_type = sample.get("action_type")
    return str(action_type) if action_type is not None else "None"


def imitation_is_pass_sample(sample: dict) -> bool:
    action_type = imitation_action_type(sample)
    cards = sample.get("teacher_chosen_cards")
    website_cards = sample.get("teacher_chosen_cards_website")
    return action_type in IMITATION_PASS_TYPES or (not cards and not website_cards)


def imitation_is_bomb_or_key_sample(sample: dict) -> bool:
    action_type = imitation_action_type(sample)
    return "bomb" in action_type or action_type in IMITATION_KEY_ACTION_TYPES


def imitation_sample_weight(sample: dict, args: argparse.Namespace) -> float:
    if not getattr(args, "balanced_imitation", False):
        return 1.0
    weight = 1.0
    if not imitation_is_pass_sample(sample):
        weight *= float(args.non_pass_weight)
    if sample.get("was_lead"):
        weight *= float(args.lead_weight)
    if imitation_is_bomb_or_key_sample(sample):
        weight *= float(args.bomb_weight)
    return float(weight)


def imitation_pass_sample_ratio(samples: list[dict], indices: list[int]) -> float:
    if not indices:
        return 0.0
    pass_count = sum(1 for idx in indices if imitation_is_pass_sample(samples[idx]))
    return pass_count / max(1, len(indices))


def imitation_epoch_indices(samples: list[dict], train_indices: list[int], args: argparse.Namespace, rng: random.Random) -> list[int]:
    selected = list(train_indices)
    use_sampler = bool(getattr(args, "balanced_imitation", False) or getattr(args, "action_type_balanced_sampler", False))
    max_pass_ratio = float(getattr(args, "max_pass_sample_ratio", 1.0))
    if use_sampler and 0.0 <= max_pass_ratio < 1.0:
        pass_indices = [idx for idx in train_indices if imitation_is_pass_sample(samples[idx])]
        non_pass_indices = [idx for idx in train_indices if not imitation_is_pass_sample(samples[idx])]
        if non_pass_indices:
            max_pass_count = int((max_pass_ratio / max(1e-9, 1.0 - max_pass_ratio)) * len(non_pass_indices))
            if len(pass_indices) > max_pass_count:
                pass_indices = rng.sample(pass_indices, max_pass_count)
            selected = non_pass_indices + pass_indices
    rng.shuffle(selected)
    return selected


def imitation_batch_metrics(actor: Any, samples: list[dict], indices: list[int], batch_size: int, device: Any) -> dict:
    import numpy as np
    import torch
    import torch.nn.functional as F

    if not indices:
        return {
            "loss": 0.0,
            "accuracy": 0.0,
            "overall_accuracy": 0.0,
            "pass_accuracy": 0.0,
            "non_pass_accuracy": 0.0,
            "lead_accuracy": 0.0,
            "follow_accuracy": 0.0,
            "action_type_macro_accuracy": 0.0,
            "action_type_accuracy_by_type": {},
            "pass_sample_ratio": 0.0,
        }
    total_loss = 0.0
    total_correct = 0
    total_seen = 0
    group_seen = Counter()
    group_correct = Counter()
    type_seen = Counter()
    type_correct = Counter()
    actor.eval()
    with torch.no_grad():
        for start in range(0, len(indices), batch_size):
            batch_indices = indices[start : start + batch_size]
            states = torch.tensor(
                np.asarray([samples[idx]["obs"] for idx in batch_indices], dtype=np.float32),
                dtype=torch.float32,
                device=device,
            )
            masks = torch.tensor(
                np.asarray([samples[idx]["legal_mask"] for idx in batch_indices], dtype=np.float32),
                dtype=torch.float32,
                device=device,
            )
            labels = torch.tensor(
                [int(samples[idx]["teacher_action_id"]) for idx in batch_indices],
                dtype=torch.long,
                device=device,
            )
            logits = actor.net(states)
            masked_logits = logits.masked_fill(masks <= 0, -1e9)
            loss = F.cross_entropy(masked_logits, labels, reduction="sum")
            predictions = masked_logits.argmax(dim=-1).detach().cpu().tolist()
            label_values = labels.detach().cpu().tolist()
            total_loss += float(loss.item())
            total_correct += int(sum(1 for pred, label in zip(predictions, label_values) if pred == label))
            total_seen += len(batch_indices)
            for idx, pred, label in zip(batch_indices, predictions, label_values):
                sample = samples[idx]
                correct = int(pred == label)
                is_pass = imitation_is_pass_sample(sample)
                pass_group = "pass" if is_pass else "non_pass"
                group_seen[pass_group] += 1
                group_correct[pass_group] += correct
                if sample.get("was_lead"):
                    group_seen["lead"] += 1
                    group_correct["lead"] += correct
                if sample.get("was_follow"):
                    group_seen["follow"] += 1
                    group_correct["follow"] += correct
                action_type = imitation_action_type(sample)
                type_seen[action_type] += 1
                type_correct[action_type] += correct
    actor.train()
    type_accuracy = {
        action_type: {
            "accuracy": type_correct[action_type] / max(1, count),
            "correct": int(type_correct[action_type]),
            "total": int(count),
        }
        for action_type, count in sorted(type_seen.items())
    }
    macro_values = [entry["accuracy"] for entry in type_accuracy.values()]
    return {
        "loss": total_loss / max(1, total_seen),
        "accuracy": total_correct / max(1, total_seen),
        "overall_accuracy": total_correct / max(1, total_seen),
        "pass_accuracy": group_correct["pass"] / max(1, group_seen["pass"]),
        "non_pass_accuracy": group_correct["non_pass"] / max(1, group_seen["non_pass"]),
        "lead_accuracy": group_correct["lead"] / max(1, group_seen["lead"]),
        "follow_accuracy": group_correct["follow"] / max(1, group_seen["follow"]),
        "action_type_macro_accuracy": sum(macro_values) / max(1, len(macro_values)),
        "action_type_accuracy_by_type": type_accuracy,
        "pass_sample_ratio": imitation_pass_sample_ratio(samples, indices),
    }


def run_train_from_imitation_dataset(args: argparse.Namespace) -> None:
    import numpy as np
    import torch
    import torch.nn.functional as F

    device_info = offline_resolve_device(args.device)
    if device_info["torch"] is None:
        raise RuntimeError("torch backend is required for imitation training")
    device = device_info["device"]
    dataset_path = Path(args.train_from_imitation_dataset)
    samples, dataset_summary, dataset_format = load_imitation_dataset(dataset_path)
    validation = validate_imitation_samples(samples)
    if validation["invalid_sample_count"]:
        raise RuntimeError(f"invalid imitation samples: {validation['invalid_sample_count']}")
    components = offline_load_guandan_components()
    actor, _critic, _actor_optimizer, _critic_optimizer = offline_build_models(len(components["actions"]), device)
    if args.init_actor:
        try:
            state_dict = torch.load(Path(args.init_actor), map_location=device, weights_only=True)
        except TypeError:
            state_dict = torch.load(Path(args.init_actor), map_location=device)
        actor.load_state_dict(state_dict)
    optimizer = torch.optim.Adam(actor.parameters(), lr=float(args.learning_rate))
    rng = random.Random(20260705)
    indices = list(range(len(samples)))
    rng.shuffle(indices)
    val_count = int(round(len(indices) * float(args.validation_split)))
    val_count = min(max(val_count, 1 if len(indices) > 1 else 0), max(0, len(indices) - 1))
    val_indices = indices[:val_count]
    train_indices = indices[val_count:]
    out_dir = Path(args.imitation_out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    log = {
        "backend": device_info["backend"],
        "requested_device": device_info["requested_device"],
        "actual_device": device_info["actual_device"],
        "device_fallback": device_info["device_fallback"],
        "torch_available": device_info["torch_available"],
        "cuda_available": device_info["cuda_available"],
        "dataset_path": str(dataset_path),
        "dataset_format": dataset_format,
        "sample_count": len(samples),
        "train_sample_count": len(train_indices),
        "val_sample_count": len(val_indices),
        "imitation_epochs": int(args.imitation_epochs),
        "batch_size": int(args.batch_size),
        "learning_rate": float(args.learning_rate),
        "balanced_imitation": bool(args.balanced_imitation),
        "non_pass_weight": float(args.non_pass_weight),
        "lead_weight": float(args.lead_weight),
        "bomb_weight": float(args.bomb_weight),
        "action_type_balanced_sampler": bool(args.action_type_balanced_sampler),
        "max_pass_sample_ratio": float(args.max_pass_sample_ratio),
        "report_detailed_imitation_metrics": bool(args.report_detailed_imitation_metrics),
        "validation_split": float(args.validation_split),
        "early_stop_patience": int(args.early_stop_patience),
        "min_delta": float(args.min_delta),
        "legal_mask_source": dataset_summary.get("legal_mask_source", "website_oracle"),
        "train_loss_by_epoch": [],
        "val_loss_by_epoch": [],
        "weighted_loss_by_epoch": [],
        "unweighted_loss_by_epoch": [],
        "train_accuracy_by_epoch": [],
        "val_accuracy_by_epoch": [],
        "pass_train_accuracy_by_epoch": [],
        "pass_val_accuracy_by_epoch": [],
        "non_pass_train_accuracy_by_epoch": [],
        "non_pass_val_accuracy_by_epoch": [],
        "lead_train_accuracy_by_epoch": [],
        "lead_val_accuracy_by_epoch": [],
        "follow_train_accuracy_by_epoch": [],
        "follow_val_accuracy_by_epoch": [],
        "train_action_type_macro_accuracy_by_epoch": [],
        "val_action_type_macro_accuracy_by_epoch": [],
        "pass_sample_ratio_train_by_epoch": [],
        "pass_sample_ratio_val_by_epoch": [],
        "supervised_loss_by_epoch": [],
        "supervised_loss_recent": None,
        "train_accuracy": None,
        "val_accuracy": None,
        "overall_train_accuracy": None,
        "overall_val_accuracy": None,
        "pass_train_accuracy": None,
        "pass_val_accuracy": None,
        "non_pass_train_accuracy": None,
        "non_pass_val_accuracy": None,
        "lead_train_accuracy": None,
        "lead_val_accuracy": None,
        "follow_train_accuracy": None,
        "follow_val_accuracy": None,
        "action_type_macro_accuracy": None,
        "train_action_type_macro_accuracy": None,
        "val_action_type_macro_accuracy": None,
        "action_type_accuracy_by_type": {},
        "train_action_type_accuracy_by_type": {},
        "val_action_type_accuracy_by_type": {},
        "pass_sample_ratio_train": imitation_pass_sample_ratio(samples, train_indices),
        "pass_sample_ratio_val": imitation_pass_sample_ratio(samples, val_indices),
        "best_epoch": None,
        "best_val_accuracy": 0.0,
        "early_stopped": False,
        "accuracy_too_high": False,
        "train_val_accuracy_gap": None,
        "action_dim_checked": validation["action_dim_checked"],
        "legal_mask_dim_checked": validation["legal_mask_dim_checked"],
        "teacher_action_in_mask_rate": validation["teacher_action_in_mask_rate"],
        "saved_checkpoints": [],
        "threshold_passed": False,
    }
    best_val_loss = float("inf")
    best_val_accuracy = -1.0
    stale_epochs = 0
    best_checkpoint_name = "imitation_actor_balanced_best.pth" if args.balanced_imitation else "imitation_actor_best.pth"
    epoch_checkpoint_prefix = "imitation_actor_balanced_epoch" if args.balanced_imitation else "imitation_actor_epoch"
    best_checkpoint_path = out_dir / best_checkpoint_name
    for epoch in range(1, int(args.imitation_epochs) + 1):
        actor.train()
        epoch_train_indices = imitation_epoch_indices(samples, train_indices, args, rng)
        weighted_loss_numer = 0.0
        weighted_loss_denom = 0.0
        unweighted_loss_sum = 0.0
        total_correct = 0
        total_seen = 0
        for start in range(0, len(epoch_train_indices), int(args.batch_size)):
            batch_indices = epoch_train_indices[start : start + int(args.batch_size)]
            states = torch.tensor(
                np.asarray([samples[idx]["obs"] for idx in batch_indices], dtype=np.float32),
                dtype=torch.float32,
                device=device,
            )
            masks = torch.tensor(
                np.asarray([samples[idx]["legal_mask"] for idx in batch_indices], dtype=np.float32),
                dtype=torch.float32,
                device=device,
            )
            labels = torch.tensor(
                [int(samples[idx]["teacher_action_id"]) for idx in batch_indices],
                dtype=torch.long,
                device=device,
            )
            logits = actor.net(states)
            if logits.shape[-1] != OFFLINE_ACTION_DIM:
                raise RuntimeError(f"actor output dim mismatch: {logits.shape[-1]}")
            masked_logits = logits.masked_fill(masks <= 0, -1e9)
            loss_items = F.cross_entropy(masked_logits, labels, reduction="none")
            if args.balanced_imitation:
                weights = torch.tensor(
                    [imitation_sample_weight(samples[idx], args) for idx in batch_indices],
                    dtype=torch.float32,
                    device=device,
                )
            else:
                weights = torch.ones(len(batch_indices), dtype=torch.float32, device=device)
            loss = (loss_items * weights).sum() / weights.sum().clamp_min(1e-8)
            optimizer.zero_grad()
            loss.backward()
            optimizer.step()
            weighted_loss_numer += float((loss_items.detach() * weights.detach()).sum().item())
            weighted_loss_denom += float(weights.detach().sum().item())
            unweighted_loss_sum += float(loss_items.detach().sum().item())
            total_correct += int((masked_logits.argmax(dim=-1) == labels).sum().item())
            total_seen += len(batch_indices)
        train_weighted_loss = weighted_loss_numer / max(1e-8, weighted_loss_denom)
        train_unweighted_loss = unweighted_loss_sum / max(1, total_seen)
        train_accuracy = total_correct / max(1, total_seen)
        train_metrics = imitation_batch_metrics(actor, samples, epoch_train_indices, int(args.batch_size), device)
        val_metrics = imitation_batch_metrics(actor, samples, val_indices, int(args.batch_size), device)
        val_loss = float(val_metrics["loss"])
        val_accuracy = float(val_metrics["accuracy"])
        train_accuracy = float(train_metrics["accuracy"])
        log["train_loss_by_epoch"].append(train_weighted_loss)
        log["val_loss_by_epoch"].append(val_loss)
        log["weighted_loss_by_epoch"].append(train_weighted_loss)
        log["unweighted_loss_by_epoch"].append(train_unweighted_loss)
        log["train_accuracy_by_epoch"].append(train_accuracy)
        log["val_accuracy_by_epoch"].append(val_accuracy)
        log["pass_train_accuracy_by_epoch"].append(train_metrics["pass_accuracy"])
        log["pass_val_accuracy_by_epoch"].append(val_metrics["pass_accuracy"])
        log["non_pass_train_accuracy_by_epoch"].append(train_metrics["non_pass_accuracy"])
        log["non_pass_val_accuracy_by_epoch"].append(val_metrics["non_pass_accuracy"])
        log["lead_train_accuracy_by_epoch"].append(train_metrics["lead_accuracy"])
        log["lead_val_accuracy_by_epoch"].append(val_metrics["lead_accuracy"])
        log["follow_train_accuracy_by_epoch"].append(train_metrics["follow_accuracy"])
        log["follow_val_accuracy_by_epoch"].append(val_metrics["follow_accuracy"])
        log["train_action_type_macro_accuracy_by_epoch"].append(train_metrics["action_type_macro_accuracy"])
        log["val_action_type_macro_accuracy_by_epoch"].append(val_metrics["action_type_macro_accuracy"])
        log["pass_sample_ratio_train_by_epoch"].append(train_metrics["pass_sample_ratio"])
        log["pass_sample_ratio_val_by_epoch"].append(val_metrics["pass_sample_ratio"])
        log["supervised_loss_by_epoch"].append(train_weighted_loss)
        improved_loss = val_loss < best_val_loss - float(args.min_delta)
        improved_accuracy = val_accuracy > best_val_accuracy + float(args.min_delta)
        if improved_loss or improved_accuracy:
            best_val_loss = min(best_val_loss, val_loss)
            best_val_accuracy = max(best_val_accuracy, val_accuracy)
            log["best_epoch"] = epoch
            log["best_val_accuracy"] = best_val_accuracy
            torch.save(actor.state_dict(), best_checkpoint_path)
            stale_epochs = 0
        else:
            stale_epochs += 1
        if args.save_every_epoch and epoch % int(args.save_every_epoch) == 0:
            checkpoint = out_dir / f"{epoch_checkpoint_prefix}{epoch}.pth"
            torch.save(actor.state_dict(), checkpoint)
            log["saved_checkpoints"].append(str(checkpoint))
        if int(args.early_stop_patience) > 0 and stale_epochs >= int(args.early_stop_patience):
            log["early_stopped"] = True
            break
    log["supervised_loss_recent"] = (
        sum(log["train_loss_by_epoch"][-3:]) / max(1, len(log["train_loss_by_epoch"][-3:]))
        if log["train_loss_by_epoch"]
        else None
    )
    log["train_accuracy"] = log["train_accuracy_by_epoch"][-1] if log["train_accuracy_by_epoch"] else None
    log["val_accuracy"] = log["val_accuracy_by_epoch"][-1] if log["val_accuracy_by_epoch"] else None
    log["overall_train_accuracy"] = log["train_accuracy"]
    log["overall_val_accuracy"] = log["val_accuracy"]
    log["pass_train_accuracy"] = log["pass_train_accuracy_by_epoch"][-1] if log["pass_train_accuracy_by_epoch"] else None
    log["pass_val_accuracy"] = log["pass_val_accuracy_by_epoch"][-1] if log["pass_val_accuracy_by_epoch"] else None
    log["non_pass_train_accuracy"] = log["non_pass_train_accuracy_by_epoch"][-1] if log["non_pass_train_accuracy_by_epoch"] else None
    log["non_pass_val_accuracy"] = log["non_pass_val_accuracy_by_epoch"][-1] if log["non_pass_val_accuracy_by_epoch"] else None
    log["lead_train_accuracy"] = log["lead_train_accuracy_by_epoch"][-1] if log["lead_train_accuracy_by_epoch"] else None
    log["lead_val_accuracy"] = log["lead_val_accuracy_by_epoch"][-1] if log["lead_val_accuracy_by_epoch"] else None
    log["follow_train_accuracy"] = log["follow_train_accuracy_by_epoch"][-1] if log["follow_train_accuracy_by_epoch"] else None
    log["follow_val_accuracy"] = log["follow_val_accuracy_by_epoch"][-1] if log["follow_val_accuracy_by_epoch"] else None
    log["train_action_type_macro_accuracy"] = (
        log["train_action_type_macro_accuracy_by_epoch"][-1] if log["train_action_type_macro_accuracy_by_epoch"] else None
    )
    log["val_action_type_macro_accuracy"] = (
        log["val_action_type_macro_accuracy_by_epoch"][-1] if log["val_action_type_macro_accuracy_by_epoch"] else None
    )
    log["action_type_macro_accuracy"] = log["val_action_type_macro_accuracy"]
    log["train_action_type_accuracy_by_type"] = train_metrics["action_type_accuracy_by_type"] if "train_metrics" in locals() else {}
    log["val_action_type_accuracy_by_type"] = val_metrics["action_type_accuracy_by_type"] if "val_metrics" in locals() else {}
    log["action_type_accuracy_by_type"] = log["val_action_type_accuracy_by_type"]
    log["pass_sample_ratio_train"] = (
        log["pass_sample_ratio_train_by_epoch"][-1] if log["pass_sample_ratio_train_by_epoch"] else log["pass_sample_ratio_train"]
    )
    log["pass_sample_ratio_val"] = (
        log["pass_sample_ratio_val_by_epoch"][-1] if log["pass_sample_ratio_val_by_epoch"] else log["pass_sample_ratio_val"]
    )
    if log["train_accuracy"] is not None and log["val_accuracy"] is not None:
        log["train_val_accuracy_gap"] = float(log["train_accuracy"]) - float(log["val_accuracy"])
        log["accuracy_too_high"] = bool(float(log["train_accuracy"]) >= 0.98 and log["train_val_accuracy_gap"] >= 0.10)
    log["threshold_passed"] = bool(log["saved_checkpoints"] and best_checkpoint_path.exists())
    save_json(out_dir / "imitation_training_state.json", log)
    save_json(Path(args.imitation_log_out), log)
    print(json.dumps(log, ensure_ascii=False, indent=2))
    if not log["threshold_passed"]:
        raise RuntimeError("imitation training threshold failed")


def corrective_label_id(sample: dict) -> int:
    if sample.get("is_corrective") and sample.get("corrective_action_id") is not None:
        return int(sample["corrective_action_id"])
    return int(sample.get("teacher_action_id", -1))


def corrective_sample_loss_weight(sample: dict, args: argparse.Namespace) -> float:
    if sample.get("is_corrective"):
        return float(args.casebook_loss_weight) * float(sample.get("weight", 1.0))
    return 1.0


def corrective_batch_metrics(actor: Any, samples: list[dict], indices: list[int], batch_size: int, device: Any) -> dict:
    import numpy as np
    import torch
    import torch.nn.functional as F

    tag_names = [
        "pass_when_can_beat",
        "bad_endgame",
        "missed_opponent_block",
        "missed_teammate_support",
    ]
    if not indices:
        return {
            "loss": 0.0,
            "overall_accuracy": 0.0,
            "corrective_accuracy": 0.0,
            "action_type_macro_accuracy": 0.0,
            "action_type_accuracy_by_type": {},
            **{f"{tag}_accuracy": 0.0 for tag in tag_names},
        }
    total_loss = 0.0
    total_seen = 0
    total_correct = 0
    corrective_seen = 0
    corrective_correct = 0
    tag_seen = Counter()
    tag_correct = Counter()
    type_seen = Counter()
    type_correct = Counter()
    actor.eval()
    with torch.no_grad():
        for start in range(0, len(indices), batch_size):
            batch_indices = indices[start : start + batch_size]
            states = torch.tensor(
                np.asarray([samples[idx]["obs"] for idx in batch_indices], dtype=np.float32),
                dtype=torch.float32,
                device=device,
            )
            masks = torch.tensor(
                np.asarray([samples[idx]["legal_mask"] for idx in batch_indices], dtype=np.float32),
                dtype=torch.float32,
                device=device,
            )
            labels = torch.tensor([corrective_label_id(samples[idx]) for idx in batch_indices], dtype=torch.long, device=device)
            logits = actor.net(states)
            masked_logits = logits.masked_fill(masks <= 0, -1e9)
            loss = F.cross_entropy(masked_logits, labels, reduction="sum")
            predictions = masked_logits.argmax(dim=-1).detach().cpu().tolist()
            label_values = labels.detach().cpu().tolist()
            total_loss += float(loss.item())
            total_seen += len(batch_indices)
            for idx, pred, label in zip(batch_indices, predictions, label_values):
                sample = samples[idx]
                correct = int(pred == label)
                total_correct += correct
                action_type = imitation_action_type(sample)
                type_seen[action_type] += 1
                type_correct[action_type] += correct
                if sample.get("is_corrective"):
                    corrective_seen += 1
                    corrective_correct += correct
                    for tag in sample.get("reason_tags") or []:
                        tag_seen[str(tag)] += 1
                        tag_correct[str(tag)] += correct
    actor.train()
    type_accuracy = {
        action_type: {
            "accuracy": type_correct[action_type] / max(1, count),
            "correct": int(type_correct[action_type]),
            "total": int(count),
        }
        for action_type, count in sorted(type_seen.items())
    }
    macro_values = [item["accuracy"] for item in type_accuracy.values()]
    result = {
        "loss": total_loss / max(1, total_seen),
        "overall_accuracy": total_correct / max(1, total_seen),
        "corrective_accuracy": corrective_correct / max(1, corrective_seen),
        "action_type_macro_accuracy": sum(macro_values) / max(1, len(macro_values)),
        "action_type_accuracy_by_type": type_accuracy,
    }
    for tag in tag_names:
        result[f"{tag}_accuracy"] = tag_correct[tag] / max(1, tag_seen[tag])
    return result


def run_train_corrective_bc(args: argparse.Namespace) -> None:
    import numpy as np
    import torch
    import torch.nn.functional as F

    device_info = offline_resolve_device(args.device)
    if device_info["torch"] is None:
        raise RuntimeError("torch backend is required for corrective BC training")
    device = device_info["device"]
    dataset_path = Path(args.corrective_dataset)
    samples, dataset_summary, dataset_format = load_imitation_dataset(dataset_path)
    invalid = 0
    for sample in samples:
        label = corrective_label_id(sample)
        mask = sample.get("legal_mask") or []
        if (
            len(sample.get("obs") or []) != OFFLINE_STATE_DIM
            or len(mask) != OFFLINE_ACTION_DIM
            or not 0 <= label < OFFLINE_ACTION_DIM
            or float(mask[label]) <= 0
        ):
            invalid += 1
    if invalid:
        raise RuntimeError(f"invalid corrective BC samples: {invalid}")
    components = offline_load_guandan_components()
    actor, _critic, _actor_optimizer, _critic_optimizer = offline_build_models(len(components["actions"]), device)
    if args.init_actor:
        try:
            state_dict = torch.load(Path(args.init_actor), map_location=device, weights_only=True)
        except TypeError:
            state_dict = torch.load(Path(args.init_actor), map_location=device)
        actor.load_state_dict(state_dict)
    optimizer = torch.optim.Adam(actor.parameters(), lr=float(args.learning_rate))
    rng = random.Random(20260706)
    indices = list(range(len(samples)))
    rng.shuffle(indices)
    val_count = int(round(len(indices) * float(args.validation_split)))
    val_count = min(max(val_count, 1 if len(indices) > 1 else 0), max(0, len(indices) - 1))
    val_indices = indices[:val_count]
    train_indices = indices[val_count:]
    out_dir = Path(args.corrective_out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    log = {
        "backend": device_info["backend"],
        "requested_device": device_info["requested_device"],
        "actual_device": device_info["actual_device"],
        "device_fallback": device_info["device_fallback"],
        "dataset_path": str(dataset_path),
        "dataset_format": dataset_format,
        "dataset_summary": dataset_summary,
        "sample_count": len(samples),
        "corrective_sample_count": sum(1 for sample in samples if sample.get("is_corrective")),
        "train_sample_count": len(train_indices),
        "val_sample_count": len(val_indices),
        "corrective_epochs": int(args.corrective_epochs),
        "batch_size": int(args.batch_size),
        "learning_rate": float(args.learning_rate),
        "casebook_loss_weight": float(args.casebook_loss_weight),
        "validation_split": float(args.validation_split),
        "early_stop_patience": int(args.early_stop_patience),
        "train_loss_by_epoch": [],
        "val_loss_by_epoch": [],
        "overall_val_accuracy_by_epoch": [],
        "corrective_val_accuracy_by_epoch": [],
        "best_epoch": None,
        "best_val_accuracy": 0.0,
        "early_stopped": False,
        "saved_checkpoints": [],
        "threshold_passed": False,
    }
    best_val_loss = float("inf")
    best_val_accuracy = -1.0
    stale_epochs = 0
    best_path = out_dir / "corrective_actor_best.pth"
    for epoch in range(1, int(args.corrective_epochs) + 1):
        actor.train()
        rng.shuffle(train_indices)
        total_loss_num = 0.0
        total_loss_den = 0.0
        for start in range(0, len(train_indices), int(args.batch_size)):
            batch_indices = train_indices[start : start + int(args.batch_size)]
            states = torch.tensor(
                np.asarray([samples[idx]["obs"] for idx in batch_indices], dtype=np.float32),
                dtype=torch.float32,
                device=device,
            )
            masks = torch.tensor(
                np.asarray([samples[idx]["legal_mask"] for idx in batch_indices], dtype=np.float32),
                dtype=torch.float32,
                device=device,
            )
            labels = torch.tensor([corrective_label_id(samples[idx]) for idx in batch_indices], dtype=torch.long, device=device)
            weights = torch.tensor(
                [corrective_sample_loss_weight(samples[idx], args) for idx in batch_indices],
                dtype=torch.float32,
                device=device,
            )
            logits = actor.net(states)
            if logits.shape[-1] != OFFLINE_ACTION_DIM:
                raise RuntimeError(f"actor output dim mismatch: {logits.shape[-1]}")
            masked_logits = logits.masked_fill(masks <= 0, -1e9)
            loss_items = F.cross_entropy(masked_logits, labels, reduction="none")
            loss = (loss_items * weights).sum() / weights.sum().clamp_min(1e-8)
            optimizer.zero_grad()
            loss.backward()
            optimizer.step()
            total_loss_num += float((loss_items.detach() * weights.detach()).sum().item())
            total_loss_den += float(weights.detach().sum().item())
        train_loss = total_loss_num / max(1e-8, total_loss_den)
        val_metrics = corrective_batch_metrics(actor, samples, val_indices, int(args.batch_size), device)
        val_loss = float(val_metrics["loss"])
        val_accuracy = float(val_metrics["overall_accuracy"])
        log["train_loss_by_epoch"].append(train_loss)
        log["val_loss_by_epoch"].append(val_loss)
        log["overall_val_accuracy_by_epoch"].append(val_accuracy)
        log["corrective_val_accuracy_by_epoch"].append(val_metrics["corrective_accuracy"])
        improved = val_loss < best_val_loss or val_accuracy > best_val_accuracy
        if improved:
            best_val_loss = min(best_val_loss, val_loss)
            best_val_accuracy = max(best_val_accuracy, val_accuracy)
            log["best_epoch"] = epoch
            log["best_val_accuracy"] = best_val_accuracy
            torch.save(actor.state_dict(), best_path)
            stale_epochs = 0
        else:
            stale_epochs += 1
        checkpoint = out_dir / f"corrective_actor_epoch{epoch}.pth"
        torch.save(actor.state_dict(), checkpoint)
        log["saved_checkpoints"].append(str(checkpoint))
        if int(args.early_stop_patience) > 0 and stale_epochs >= int(args.early_stop_patience):
            log["early_stopped"] = True
            break
    final_metrics = corrective_batch_metrics(actor, samples, val_indices, int(args.batch_size), device)
    log.update(
        {
            "overall_val_accuracy": final_metrics["overall_accuracy"],
            "corrective_val_accuracy": final_metrics["corrective_accuracy"],
            "pass_when_can_beat_accuracy": final_metrics["pass_when_can_beat_accuracy"],
            "bad_endgame_accuracy": final_metrics["bad_endgame_accuracy"],
            "missed_opponent_block_accuracy": final_metrics["missed_opponent_block_accuracy"],
            "missed_teammate_support_accuracy": final_metrics["missed_teammate_support_accuracy"],
            "action_type_macro_accuracy": final_metrics["action_type_macro_accuracy"],
            "action_type_accuracy_by_type": final_metrics["action_type_accuracy_by_type"],
            "threshold_passed": bool(best_path.exists() and log["saved_checkpoints"]),
        }
    )
    save_json(out_dir / "corrective_training_state.json", log)
    save_json(Path(args.corrective_log_out), log)
    print(json.dumps(log, ensure_ascii=False, indent=2))
    if not log["threshold_passed"]:
        raise RuntimeError("corrective BC training threshold failed")


def rollout_full_deck() -> list[str]:
    cards = [f"{suit}{rank}" for suit in "SHDC" for rank in "23456789TJQKA"] + ["B", "R"]
    return website_cards_to_local(cards) * 2


def rollout_deal_unknown_hands(case: dict, components: dict, rng: random.Random) -> Any:
    GuandanGame = components["GuandanGame"]
    game = GuandanGame(verbose=False, print_history=False)
    player_id = int(case.get("current_player", 0))
    hand_counts = list(case.get("remaining_hand_sizes") or [27, 27, 27, 27])
    hand_counts = (hand_counts + [27, 27, 27, 27])[:4]
    hand_before = corrective_cards_to_local(list(case.get("hand_before") or []))
    last_play = corrective_cards_to_local(list(case.get("last_play") or []))
    game.current_player = player_id
    game.active_level = website_level_to_local_level(str(case.get("level") or "2"))
    deck = rollout_full_deck()
    known_cards = list(hand_before) + list(last_play)
    missing_known = offline_missing_cards(known_cards, deck)
    if missing_known:
        raise RuntimeError(f"casebook state contains impossible cards: {missing_known[:8]}")
    remaining_deck = list(deck)
    for card in known_cards:
        remaining_deck.remove(card)
    rng.shuffle(remaining_deck)
    for seat, player in enumerate(game.players):
        if seat == player_id:
            player.hand = list(hand_before)
        else:
            need = max(0, int(hand_counts[seat]))
            player.hand = remaining_deck[:need]
            del remaining_deck[:need]
        player.played_cards = []
        player.last_played_cards = []
    last_player = case.get("last_player")
    if last_play and last_player is not None:
        try:
            game.players[int(last_player)].played_cards = list(last_play)
        except (TypeError, ValueError, IndexError):
            pass
    game.last_play = list(last_play) if last_play else None
    game.last_player = last_player
    game.is_free_turn = not bool(last_play)
    game.pass_count = 0
    game.jiefeng = False
    game.recent_actions = [["None"], ["None"], ["None"], ["None"]]
    game.history = []
    game.ranking = []
    game.is_game_over = False
    return game


def rollout_action_key(action_id: int, cards: list[str]) -> tuple:
    return int(action_id), tuple(sorted(cards))


def rollout_state_key(game: Any) -> tuple:
    player_id = int(game.current_player)
    return (
        int(game.active_level),
        player_id,
        bool(game.is_free_turn),
        game.last_player,
        tuple(game.last_play or []),
        tuple(sorted(game.players[player_id].hand)),
        tuple(len(player.hand) for player in game.players),
    )


def rollout_cached_oracle_candidates(
    game: Any,
    components: dict,
    legal_cache: dict | None,
) -> tuple[dict, list[tuple[int, list[str]]]]:
    player_id = int(game.current_player)
    hand_before = list(game.players[player_id].hand)
    last_play_before = list(game.last_play or [])
    was_lead = bool(game.is_free_turn or not last_play_before)
    key = rollout_state_key(game)
    if legal_cache is not None and key in legal_cache:
        cached_oracle, cached_candidates = legal_cache[key]
        return copy.deepcopy(cached_oracle), [(int(action_id), list(cards)) for action_id, cards in cached_candidates]
    oracle, candidates = offline_oracle_candidates_fast(game, components, hand_before, last_play_before, was_lead)
    if legal_cache is not None:
        legal_cache[key] = (copy.deepcopy(oracle), [(int(action_id), list(cards)) for action_id, cards in candidates])
    return oracle, candidates


def rollout_cached_baseline_action(
    game: Any,
    components: dict,
    baseline_profile: str,
    profile_config: dict,
    rng: random.Random,
    baseline_cache: dict | None,
) -> dict:
    key = rollout_state_key(game)
    if baseline_cache is not None and key in baseline_cache:
        return offline_make_action_info_from_cards(
            game,
            components,
            list(baseline_cache[key]),
            rng,
            policy="tempo_baseline_cached",
            audit_masks=False,
        )
    info = offline_baseline_action_info(game, components, baseline_profile, profile_config, rng)
    if baseline_cache is not None and not info.get("illegal"):
        baseline_cache[key] = list(info.get("chosen_cards") or [])
    return info


def rollout_candidate_from_cards(
    game: Any,
    components: dict,
    cards: list[str],
    source: str,
    rng: random.Random,
) -> dict | None:
    info = offline_make_action_info_from_cards(
        game,
        components,
        list(cards),
        rng,
        policy=f"rollout_candidate_{source}",
        audit_masks=False,
    )
    if info.get("illegal") or info.get("materialization_fail") or info.get("hand_card_mismatch"):
        return None
    return {
        "action_id": int(info.get("action_id")),
        "physical_cards": list(info.get("chosen_cards") or []),
        "action_type": str(info.get("action_type") or "unknown"),
        "is_bomb": bool(info.get("is_bomb")),
        "source": source,
    }


def rollout_actor_topk_candidates(
    game: Any,
    components: dict,
    actor: Any,
    device: Any,
    top_k: int,
) -> list[tuple[int, list[str]]]:
    import numpy as np
    import torch

    player_id = int(game.current_player)
    hand_before = list(game.players[player_id].hand)
    last_play_before = list(game.last_play or [])
    was_lead = bool(game.is_free_turn or not last_play_before)
    oracle, candidates = offline_oracle_candidates_fast(game, components, hand_before, last_play_before, was_lead)
    option_by_action: dict[int, list[list[str]]] = {}
    for action_id, cards in candidates:
        option_by_action.setdefault(int(action_id), []).append(list(cards))
    valid_ids = sorted(option_by_action)
    if not valid_ids:
        return []
    with torch.no_grad():
        state = game._get_obs()
        state_tensor = torch.tensor(np.asarray(state), dtype=torch.float32, device=device).unsqueeze(0)
        mask_tensor = torch.tensor(np.asarray(oracle["mask"], dtype=np.float32), dtype=torch.float32, device=device).unsqueeze(0)
        probs = actor(state_tensor, mask_tensor).squeeze(0).detach().cpu().tolist()
    ranked_ids = sorted(valid_ids, key=lambda action_id: float(probs[action_id]), reverse=True)[: max(1, int(top_k))]
    result: list[tuple[int, list[str]]] = []
    for action_id in ranked_ids:
        combos = option_by_action.get(action_id) or []
        if not combos:
            continue
        action = components["action_by_id"].get(int(action_id), {})
        cards = min(combos, key=lambda combo: corrective_action_sort_key(components, int(action_id), list(combo)))
        result.append((int(action_id), list(cards)))
    return result


def rollout_min_bomb_candidate(
    components: dict,
    candidates: list[tuple[int, list[str]]],
) -> tuple[int, list[str]] | None:
    bombs = [
        (int(action_id), list(cards))
        for action_id, cards in candidates
        if cards and offline_action_is_bomb(components["action_by_id"].get(int(action_id)))
    ]
    if not bombs:
        return None
    return min(bombs, key=lambda item: corrective_action_sort_key(components, item[0], item[1]))


def rollout_collect_candidates(
    game: Any,
    components: dict,
    actor: Any,
    device: Any,
    baseline_profile: str,
    profile_config: dict,
    rng: random.Random,
    top_k: int,
    baseline_cache: dict | None = None,
    legal_cache: dict | None = None,
) -> tuple[list[dict], dict]:
    player_id = int(game.current_player)
    hand_before = list(game.players[player_id].hand)
    last_play_before = list(game.last_play or [])
    was_lead = bool(game.is_free_turn or not last_play_before)
    oracle, legal_candidates = rollout_cached_oracle_candidates(game, components, legal_cache)
    candidate_map: dict[tuple, dict] = {}

    def add_candidate(action_id: int, cards: list[str], source: str) -> None:
        if not 0 <= int(action_id) < OFFLINE_ACTION_DIM:
            return
        if float(oracle["mask"][int(action_id)]) <= 0:
            return
        if not offline_cards_in_hand(list(cards), hand_before):
            return
        info = rollout_candidate_from_cards(game, components, list(cards), source, rng)
        if info is None:
            return
        key = rollout_action_key(int(info["action_id"]), list(info["physical_cards"]))
        if key in candidate_map:
            candidate_map[key]["sources"] = sorted(set(candidate_map[key].get("sources", []) + [source]))
        else:
            info["sources"] = [source]
            candidate_map[key] = info

    for action_id, cards in rollout_actor_topk_candidates(game, components, actor, device, top_k):
        add_candidate(action_id, cards, "model_topk")

    baseline_info = rollout_cached_baseline_action(
        game,
        components,
        baseline_profile,
        profile_config,
        rng,
        baseline_cache,
    )
    add_candidate(int(baseline_info.get("action_id") or 0), list(baseline_info.get("chosen_cards") or []), "baseline")

    model_info = offline_select_action_fast(game, components, actor=actor, device=device, rng=rng)
    if not model_info.get("illegal"):
        add_candidate(int(model_info.get("action_id") or 0), list(model_info.get("chosen_cards") or []), "model_sample")

    if not was_lead:
        add_candidate(0, [], "pass")
        min_beat = corrective_smallest_candidate(components, legal_candidates, allow_bomb=False)
        if min_beat is not None:
            add_candidate(min_beat[0], min_beat[1], "min_beat")
        min_bomb = rollout_min_bomb_candidate(components, legal_candidates)
        if min_bomb is not None:
            add_candidate(min_bomb[0], min_bomb[1], "min_bomb")
    else:
        sorted_leads = sorted(
            [(int(action_id), list(cards)) for action_id, cards in legal_candidates if cards],
            key=lambda item: (
                offline_action_is_bomb(components["action_by_id"].get(int(item[0]))),
                len(item[1]) > 2,
                len(item[1]),
                corrective_action_sort_key(components, item[0], item[1]),
            ),
        )
        for action_id, cards in sorted_leads[: max(2, int(top_k))]:
            add_candidate(action_id, cards, "safe_lead_pool")

    candidates = list(candidate_map.values())
    return candidates, {
        "oracle_legal_action_count": int(sum(1 for value in oracle["mask"] if float(value) > 0)),
        "legal_candidate_count": len(legal_candidates),
        "was_lead": was_lead,
        "hand_before": hand_before,
        "last_play": last_play_before,
    }


def rollout_estimated_team_rank(game: Any, team_id: int) -> float:
    ranks: dict[int, int] = {player: index + 1 for index, player in enumerate(game.ranking)}
    remaining = [seat for seat in range(4) if seat not in ranks]
    remaining_sorted = sorted(remaining, key=lambda seat: len(game.players[seat].hand))
    next_rank = len(ranks) + 1
    for offset, seat in enumerate(remaining_sorted):
        ranks[seat] = next_rank + offset
    team_players = [seat for seat in range(4) if offline_team_id(seat) == team_id]
    return sum(float(ranks.get(seat, 4)) for seat in team_players) / 2.0


def rollout_estimated_team_win(game: Any, team_id: int) -> float:
    winner = offline_winner_team_id(game) if game.is_game_over else None
    if winner is not None:
        return 1.0 if winner == team_id else 0.0
    own = sum(len(game.players[seat].hand) for seat in range(4) if offline_team_id(seat) == team_id)
    opp = sum(len(game.players[seat].hand) for seat in range(4) if offline_team_id(seat) != team_id)
    if own < opp:
        return 1.0
    if own > opp:
        return 0.0
    return 0.5


def rollout_greedy_action_info(
    game: Any,
    components: dict,
    rng: random.Random,
    policy: str = "greedy_bot",
) -> dict:
    player_id = int(game.current_player)
    hand_before = list(game.players[player_id].hand)
    last_play_before = list(game.last_play or [])
    was_lead = bool(game.is_free_turn or not last_play_before)
    _oracle, candidates = offline_oracle_candidates_fast(game, components, hand_before, last_play_before, was_lead)
    if not candidates:
        return offline_make_action_info_from_cards(game, components, [], rng, policy=policy, audit_masks=False)
    if was_lead:
        non_bombs = [
            (int(action_id), list(cards))
            for action_id, cards in candidates
            if cards and not offline_action_is_bomb(components["action_by_id"].get(int(action_id)))
        ]
        pool = non_bombs or [(int(action_id), list(cards)) for action_id, cards in candidates if cards]
        if not pool:
            selected = (0, [])
        else:
            selected = max(
                pool,
                key=lambda item: (
                    len(item[1]),
                    -int(components["action_by_id"].get(int(item[0]), {}).get("logic_point") or 0),
                    -int(item[0]),
                ),
            )
    else:
        non_pass = [(int(action_id), list(cards)) for action_id, cards in candidates if cards]
        non_bombs = [
            (action_id, cards)
            for action_id, cards in non_pass
            if not offline_action_is_bomb(components["action_by_id"].get(int(action_id)))
        ]
        pool = non_bombs or non_pass
        selected = min(pool, key=lambda item: corrective_action_sort_key(components, item[0], item[1])) if pool else (0, [])
    return offline_make_action_info_from_cards(
        game,
        components,
        list(selected[1]),
        rng,
        policy=policy,
        sampled_action_id=int(selected[0]),
        audit_masks=False,
    )


def rollout_candidate_breaks_group(cards: list[str], hand: list[str]) -> bool:
    if not cards:
        return False
    hand_counts = Counter(card_rank(card) for card in local_cards_to_website(hand) if card not in {"B", "R"})
    used_counts = Counter(card_rank(card) for card in local_cards_to_website(cards) if card not in {"B", "R"})
    for rank, used in used_counts.items():
        available = hand_counts.get(rank, 0)
        if available >= 2 and 0 < used < available:
            return True
    return False


def rollout_candidate_touches_straight(cards: list[str], hand: list[str], level: str) -> bool:
    if not cards:
        return False
    rank_order = list(engine.RANKS)
    hand_ranks = {card_rank(card) for card in local_cards_to_website(hand) if card not in {"B", "R"}}
    used_ranks = {card_rank(card) for card in local_cards_to_website(cards) if card not in {"B", "R"}}
    if not used_ranks:
        return False
    sequences = []
    for start in range(0, len(rank_order) - 4):
        seq = set(rank_order[start : start + 5])
        if seq <= hand_ranks:
            sequences.append(seq)
    return any(seq & used_ranks for seq in sequences)


def rollout_heuristic_score(
    game: Any,
    components: dict,
    candidate: dict,
    case: dict,
) -> tuple[float, list[str]]:
    player_id = int(game.current_player)
    team_id = offline_team_id(player_id)
    teammate = offline_teammate(player_id)
    opponents = [seat for seat in range(4) if offline_team_id(seat) != team_id]
    hand_counts = [len(player.hand) for player in game.players]
    opponent_min = min(hand_counts[seat] for seat in opponents)
    teammate_remaining = hand_counts[teammate]
    my_before = hand_counts[player_id]
    cards = list(candidate.get("physical_cards") or [])
    action = components["action_by_id"].get(int(candidate.get("action_id") or 0), {})
    action_type = str(candidate.get("action_type") or action.get("type") or "unknown")
    is_bomb = bool(candidate.get("is_bomb") or offline_action_is_bomb(action))
    was_lead = bool(game.is_free_turn or not (game.last_play or []))
    last_player = game.last_player
    last_team = offline_team_id(int(last_player)) if last_player is not None else None
    tags = set(case.get("reason_tags") or [])
    score = 0.0
    reasons: list[str] = []
    hand_delta = len(cards)
    score += hand_delta * 1.2
    if my_before <= 5 and hand_delta:
        score += hand_delta * 0.8
        reasons.append("self_endgame_reduce_cards")
    if hand_delta >= my_before and hand_delta:
        score += 12.0
        reasons.append("self_go_out")
    if not was_lead:
        if not cards:
            if last_team == team_id:
                score += 1.5
                reasons.append("pass_to_teammate")
            elif opponent_min <= 3:
                score -= 10.0
                reasons.append("critical_opponent_pass_penalty")
            elif opponent_min <= 5:
                score -= 6.0
                reasons.append("opponent_endgame_pass_penalty")
            elif "pass_when_can_beat" in tags:
                score -= 2.5
                reasons.append("pass_when_can_beat_penalty")
        else:
            if last_team != team_id:
                if opponent_min <= 3:
                    score += 8.0
                    reasons.append("critical_opponent_block")
                elif opponent_min <= 5:
                    score += 4.0
                    reasons.append("opponent_block")
            else:
                score -= 4.0
                reasons.append("overrides_teammate_penalty")
    else:
        if teammate_remaining <= 3 and hand_delta == teammate_remaining:
            score += 4.0
            reasons.append("teammate_support_size")
        if opponent_min <= 5 and hand_delta == opponent_min:
            score -= 6.0
            reasons.append("opens_exact_opponent_length")
        if opponent_min <= 3 and action_type == "single":
            score -= 2.5
            reasons.append("single_lead_vs_critical_opponent")
    if is_bomb:
        if opponent_min <= 3:
            score += 3.0
            reasons.append("bomb_for_critical_block")
        else:
            score -= 5.0
            reasons.append("noncritical_bomb_penalty")
    level = website_level_from_local_level(game.active_level)
    if offline_action_uses_level_or_joker(cards, game.active_level) and opponent_min > 3:
        score -= 1.5
        reasons.append("spends_control_card")
    if rollout_candidate_breaks_group(cards, list(game.players[player_id].hand)):
        score -= 2.0
        reasons.append("breaks_pair_or_group")
    if action_type not in {"straight", "pair_chain", "gangban", "flush_rocket"} and rollout_candidate_touches_straight(
        cards,
        list(game.players[player_id].hand),
        level,
    ):
        score -= 1.5
        reasons.append("touches_straight_shape")
    if "bad_endgame" in tags and opponent_min <= 5 and cards:
        score += 1.0
        reasons.append("bad_endgame_active_action")
    if "missed_teammate_support" in tags and teammate_remaining <= 3 and was_lead:
        score += 1.0 if hand_delta in {1, teammate_remaining} else -1.0
        reasons.append("teammate_support_tag")
    return score, reasons


def rollout_policy_action_info(
    game: Any,
    components: dict,
    actor: Any,
    device: Any,
    baseline_profile: str,
    profile_config: dict,
    rng: random.Random,
    team_profile: str,
) -> dict:
    if team_profile == "actor":
        return offline_arena_model_action_info(game, components, actor, device, baseline_profile, profile_config, rng)
    if team_profile in {"greedy_bot", "fast_baseline"}:
        return rollout_greedy_action_info(game, components, rng, policy=team_profile)
    return offline_baseline_action_info(game, components, baseline_profile, profile_config, rng)


def rollout_simulate_candidate(
    case: dict,
    components: dict,
    actor: Any,
    device: Any,
    profile_config: dict,
    args: argparse.Namespace,
    candidate: dict,
    simulation_seed: int,
) -> tuple[float, float, dict | None]:
    rng = random.Random(simulation_seed)
    try:
        game = rollout_deal_unknown_hands(case, components, rng)
    except RuntimeError as exc:
        return 0.0, 4.0, {"reason": str(exc)}
    player_id = int(game.current_player)
    team_id = offline_team_id(player_id)
    action_info = offline_make_action_info_from_cards(
        game,
        components,
        list(candidate.get("physical_cards") or []),
        rng,
        policy="rollout_counterfactual",
        sampled_action_id=int(candidate.get("action_id") or 0),
        audit_masks=False,
    )
    if action_info.get("illegal") or action_info.get("materialization_fail") or action_info.get("hand_card_mismatch"):
        return 0.0, 4.0, {"reason": "candidate_apply_invalid", "candidate": candidate}
    record = offline_apply_action(game, action_info)
    if record.get("hand_card_mismatch") or record.get("materialization_fail"):
        return 0.0, 4.0, {"reason": "candidate_apply_failed", "candidate": candidate}
    steps = 0
    while not game.is_game_over and steps < int(args.rollout_depth_turns):
        offline_prepare_turn(game)
        if game.current_player in game.ranking:
            steps += 1
            continue
        current_team = offline_team_id(int(game.current_player))
        if current_team == team_id:
            policy = str(
                (args.rollout_fast_teammate_profile if bool(getattr(args, "rollout_fast_mode", False)) else None)
                or args.rollout_teammate_profile
                or "tempo_baseline"
            )
        else:
            policy = str(
                (args.rollout_fast_opponent_profile if bool(getattr(args, "rollout_fast_mode", False)) else None)
                or args.rollout_opponent_profile
                or "tempo_baseline"
            )
        action = rollout_policy_action_info(
            game,
            components,
            actor,
            device,
            str(args.rollout_baseline_profile),
            profile_config,
            rng,
            policy,
        )
        record = offline_apply_action(game, action)
        if record.get("hand_card_mismatch") or record.get("materialization_fail"):
            return 0.0, 4.0, {"reason": "rollout_action_failed", "record": record}
        steps += 1
    return rollout_estimated_team_win(game, team_id), rollout_estimated_team_rank(game, team_id), None


def rollout_candidate_summary(
    case: dict,
    components: dict,
    actor: Any,
    device: Any,
    profile_config: dict,
    args: argparse.Namespace,
    candidate: dict,
    case_index: int,
    candidate_index: int,
) -> dict:
    wins: list[float] = []
    ranks: list[float] = []
    failures: list[dict] = []
    for sim_index in range(int(args.rollout_simulations_per_action)):
        win, rank, failure = rollout_simulate_candidate(
            case,
            components,
            actor,
            device,
            profile_config,
            args,
            candidate,
            20260707 + case_index * 100_000 + candidate_index * 1_000 + sim_index,
        )
        wins.append(float(win))
        ranks.append(float(rank))
        if failure and len(failures) < 3:
            failures.append(failure)
    return {
        "action_id": int(candidate.get("action_id")),
        "physical_cards": list(candidate.get("physical_cards") or []),
        "physical_cards_website": local_cards_to_website(list(candidate.get("physical_cards") or [])),
        "action_type": str(candidate.get("action_type") or "unknown"),
        "is_bomb": bool(candidate.get("is_bomb")),
        "hand_delta": len(candidate.get("physical_cards") or []),
        "sources": list(candidate.get("sources") or [candidate.get("source") or "unknown"]),
        "estimated_team_win_rate": sum(wins) / max(1, len(wins)),
        "avg_final_rank": sum(ranks) / max(1, len(ranks)),
        "simulation_count": len(wins),
        "failures": failures,
    }


def rollout_simulate_candidate_from_game(
    base_game: Any,
    components: dict,
    actor: Any,
    device: Any,
    profile_config: dict,
    args: argparse.Namespace,
    candidate: dict,
    simulation_seed: int,
) -> tuple[float, float, dict | None]:
    rng = random.Random(simulation_seed)
    game = copy.deepcopy(base_game)
    player_id = int(game.current_player)
    team_id = offline_team_id(player_id)
    action_info = offline_make_action_info_from_cards(
        game,
        components,
        list(candidate.get("physical_cards") or []),
        rng,
        policy="rollout_counterfactual",
        sampled_action_id=int(candidate.get("action_id") or 0),
        audit_masks=False,
    )
    if action_info.get("illegal") or action_info.get("materialization_fail") or action_info.get("hand_card_mismatch"):
        return 0.0, 4.0, {"reason": "candidate_apply_invalid", "candidate": candidate}
    record = offline_apply_action(game, action_info)
    if record.get("hand_card_mismatch") or record.get("materialization_fail"):
        return 0.0, 4.0, {"reason": "candidate_apply_failed", "candidate": candidate}
    steps = 0
    while not game.is_game_over and steps < int(args.rollout_depth_turns):
        offline_prepare_turn(game)
        if game.current_player in game.ranking:
            steps += 1
            continue
        current_team = offline_team_id(int(game.current_player))
        if current_team == team_id:
            policy = str(
                (args.rollout_fast_teammate_profile if bool(getattr(args, "rollout_fast_mode", False)) else None)
                or args.rollout_teammate_profile
                or "tempo_baseline"
            )
        else:
            policy = str(
                (args.rollout_fast_opponent_profile if bool(getattr(args, "rollout_fast_mode", False)) else None)
                or args.rollout_opponent_profile
                or "tempo_baseline"
            )
        action = rollout_policy_action_info(
            game,
            components,
            actor,
            device,
            str(args.rollout_baseline_profile),
            profile_config,
            rng,
            policy,
        )
        record = offline_apply_action(game, action)
        if record.get("hand_card_mismatch") or record.get("materialization_fail"):
            return 0.0, 4.0, {"reason": "rollout_action_failed", "record": record}
        steps += 1
    return rollout_estimated_team_win(game, team_id), rollout_estimated_team_rank(game, team_id), None


def rollout_evaluate_candidate_summaries(
    case: dict,
    components: dict,
    actor: Any,
    device: Any,
    profile_config: dict,
    args: argparse.Namespace,
    candidates: list[dict],
    case_index: int,
) -> list[dict]:
    wins: list[list[float]] = [[] for _candidate in candidates]
    ranks: list[list[float]] = [[] for _candidate in candidates]
    failures: list[list[dict]] = [[] for _candidate in candidates]
    for sim_index in range(int(args.rollout_simulations_per_action)):
        seed = 20260707 + case_index * 100_000 + sim_index
        rng = random.Random(seed)
        try:
            base_game = rollout_deal_unknown_hands(case, components, rng)
        except RuntimeError as exc:
            for candidate_index in range(len(candidates)):
                wins[candidate_index].append(0.0)
                ranks[candidate_index].append(4.0)
                if len(failures[candidate_index]) < 3:
                    failures[candidate_index].append({"reason": str(exc)})
            continue
        for candidate_index, candidate in enumerate(candidates):
            win, rank, failure = rollout_simulate_candidate_from_game(
                base_game,
                components,
                actor,
                device,
                profile_config,
                args,
                candidate,
                seed + candidate_index * 1000,
            )
            wins[candidate_index].append(float(win))
            ranks[candidate_index].append(float(rank))
            if failure and len(failures[candidate_index]) < 3:
                failures[candidate_index].append(failure)
    summaries: list[dict] = []
    for candidate, candidate_wins, candidate_ranks, candidate_failures in zip(candidates, wins, ranks, failures):
        summaries.append(
            {
                "action_id": int(candidate.get("action_id")),
                "physical_cards": list(candidate.get("physical_cards") or []),
                "physical_cards_website": local_cards_to_website(list(candidate.get("physical_cards") or [])),
                "action_type": str(candidate.get("action_type") or "unknown"),
                "is_bomb": bool(candidate.get("is_bomb")),
                "hand_delta": len(candidate.get("physical_cards") or []),
                "sources": list(candidate.get("sources") or [candidate.get("source") or "unknown"]),
                "estimated_team_win_rate": sum(candidate_wins) / max(1, len(candidate_wins)),
                "avg_final_rank": sum(candidate_ranks) / max(1, len(candidate_ranks)),
                "simulation_count": len(candidate_wins),
                "failures": candidate_failures,
            }
        )
    return summaries


def rollout_select_fast_candidates(
    game: Any,
    components: dict,
    candidates: list[dict],
    case: dict,
    args: argparse.Namespace,
) -> tuple[list[dict], list[dict], dict | None]:
    scored: list[dict] = []
    for candidate in candidates:
        score, reasons = rollout_heuristic_score(game, components, candidate, case)
        item = {
            **candidate,
            "heuristic_score": float(score),
            "heuristic_reasons": reasons,
            "heuristic_score_record": {
                "action_id": int(candidate.get("action_id")),
                "physical_cards": list(candidate.get("physical_cards") or []),
                "physical_cards_website": local_cards_to_website(list(candidate.get("physical_cards") or [])),
                "action_type": str(candidate.get("action_type") or "unknown"),
                "sources": list(candidate.get("sources") or []),
                "heuristic_score": float(score),
                "heuristic_reasons": reasons,
            },
        }
        scored.append(item)
    scored.sort(key=lambda item: float(item["heuristic_score"]), reverse=True)
    coarse_top_m = max(1, int(args.rollout_coarse_top_m or len(scored)))
    final_top_m = max(1, int(args.rollout_final_top_m or coarse_top_m))
    coarse_pool = scored[:coarse_top_m]
    selected: list[dict] = []
    selected_keys: set[tuple] = set()

    def add(item: dict) -> None:
        key = rollout_action_key(int(item.get("action_id")), list(item.get("physical_cards") or []))
        if key not in selected_keys:
            selected_keys.add(key)
            selected.append(item)

    for item in coarse_pool[:final_top_m]:
        add(item)
    for source in ("model_sample", "baseline", "min_beat"):
        for item in scored:
            if source in (item.get("sources") or []):
                add(item)
                break
    exact_limit = int(getattr(args, "rollout_exact_verify_top_m", 0) or 0)
    if exact_limit > 0:
        selected = selected[:exact_limit]
    heuristic_best = scored[0]["heuristic_score_record"] if scored else None
    return selected, [item["heuristic_score_record"] for item in scored], heuristic_best


def rollout_action_rate_by_source(action_summaries: list[dict], source: str) -> float | None:
    values = [float(item["estimated_team_win_rate"]) for item in action_summaries if source in (item.get("sources") or [])]
    if not values:
        return None
    return max(values)


def run_casebook_rollout_eval(args: argparse.Namespace) -> None:
    if args.rollout_baseline_profile != "tempo_baseline":
        raise RuntimeError("casebook rollout currently only supports --rollout-baseline-profile tempo_baseline")
    casebook_path = Path(args.rollout_casebook)
    actor_path = Path(args.rollout_actor)
    if not casebook_path.exists():
        raise RuntimeError(f"rollout casebook not found: {casebook_path}")
    if not actor_path.exists():
        raise RuntimeError(f"rollout actor not found: {actor_path}")
    components = offline_load_guandan_components()
    device_info = offline_resolve_device(args.rollout_device or args.device)
    actor = offline_load_actor_checkpoint(actor_path, components, device_info)
    profiles = load_json(PROFILE_PATH, {})
    profile_config = profiles.get("tempo_baseline", {"engine_mode": "tempo"})
    rng = random.Random(20260707)
    payload = load_json(casebook_path, {})
    only_tags = corrective_casebook_tags(getattr(args, "rollout_only_reason_tags", "") or "")
    raw_failure_cases = list(payload.get("failure_cases") or [])
    if only_tags:
        raw_failure_cases = [
            case for case in raw_failure_cases if only_tags & {str(tag) for tag in case.get("reason_tags") or []}
        ]
    failure_cases = raw_failure_cases[: max(0, int(args.rollout_max_cases))]
    baseline_cache: dict | None = {} if bool(getattr(args, "rollout_cache_baseline_actions", False)) else None
    legal_cache: dict | None = {} if bool(getattr(args, "rollout_cache_legal_options", False)) else None
    restore_baseline = offline_install_arena_baseline_optimizations()
    result = {
        "backend": device_info["backend"],
        "requested_device": device_info["requested_device"],
        "actual_device": device_info["actual_device"],
        "device_fallback": device_info["device_fallback"],
        "legal_mask_source": "website_oracle",
        "rollout_casebook": str(casebook_path),
        "rollout_actor": str(actor_path),
        "rollout_baseline_profile": args.rollout_baseline_profile,
        "rollout_opponent_profile": args.rollout_opponent_profile,
        "rollout_teammate_profile": args.rollout_teammate_profile,
        "rollout_fast_mode": bool(getattr(args, "rollout_fast_mode", False)),
        "fast_mode": bool(getattr(args, "rollout_fast_mode", False)),
        "rollout_coarse_eval": bool(getattr(args, "rollout_coarse_eval", False)),
        "rollout_use_heuristic_value": bool(getattr(args, "rollout_use_heuristic_value", False)),
        "rollout_fast_opponent_profile": getattr(args, "rollout_fast_opponent_profile", "greedy_bot"),
        "rollout_fast_teammate_profile": getattr(args, "rollout_fast_teammate_profile", "greedy_bot"),
        "rollout_coarse_top_m": int(getattr(args, "rollout_coarse_top_m", 3) or 3),
        "rollout_final_top_m": int(getattr(args, "rollout_final_top_m", 2) or 2),
        "rollout_exact_verify_top_m": int(getattr(args, "rollout_exact_verify_top_m", 0) or 0),
        "rollout_max_seconds_per_case": float(getattr(args, "rollout_max_seconds_per_case", 0.0) or 0.0),
        "rollout_only_reason_tags": sorted(only_tags),
        "rollout_cache_baseline_actions": bool(getattr(args, "rollout_cache_baseline_actions", False)),
        "rollout_cache_legal_options": bool(getattr(args, "rollout_cache_legal_options", False)),
        "rollout_max_cases": int(args.rollout_max_cases),
        "rollout_top_k_actions": int(args.rollout_top_k_actions),
        "rollout_simulations_per_action": int(args.rollout_simulations_per_action),
        "rollout_depth_turns": int(args.rollout_depth_turns),
        "rollout_case_count": len(failure_cases),
        "evaluated_case_count": 0,
        "skipped_case_count": 0,
        "timeout_case_count": 0,
        "skipped_due_to_timeout_count": 0,
        "skip_reasons": {},
        "avg_candidate_count": 0.0,
        "avg_seconds_per_case": 0.0,
        "coarse_candidate_count": 0,
        "exact_verified_candidate_count": 0,
        "rollout_teacher_label_count": 0,
        "model_action_avg_win_rate": None,
        "baseline_action_avg_win_rate": None,
        "min_beat_action_avg_win_rate": None,
        "rollout_best_action_avg_win_rate": None,
        "reason_tag_breakdown": {},
        "hand_card_mismatch_count": 0,
        "materialization_fail_count": 0,
        "concrete_rollout_examples": [],
        "cases": [],
    }
    skip_reasons: Counter = Counter()
    reason_tags: Counter = Counter()
    candidate_counts: list[int] = []
    model_rates: list[float] = []
    baseline_rates: list[float] = []
    min_beat_rates: list[float] = []
    best_rates: list[float] = []
    case_seconds: list[float] = []
    try:
        for case_index, case in enumerate(failure_cases):
            case_start = time.monotonic()
            try:
                base_game = rollout_deal_unknown_hands(case, components, rng)
            except RuntimeError as exc:
                skip_reasons[str(exc)] += 1
                result["skipped_case_count"] += 1
                continue
            player_id = int(base_game.current_player)
            hand_before = list(base_game.players[player_id].hand)
            was_lead = bool(base_game.is_free_turn or not (base_game.last_play or []))
            oracle = offline_oracle_legal_mask(
                base_game,
                components,
                player_id,
                hand_before,
                list(base_game.last_play or []),
                base_game.active_level,
            )
            candidates, meta = rollout_collect_candidates(
                base_game,
                components,
                actor,
                device_info["device"],
                args.rollout_baseline_profile,
                profile_config,
                rng,
                int(args.rollout_top_k_actions),
                baseline_cache=baseline_cache,
                legal_cache=legal_cache,
            )
            if not candidates:
                skip_reasons["no_candidate_actions"] += 1
                result["skipped_case_count"] += 1
                continue
            heuristic_scores: list[dict] = []
            heuristic_best_action: dict | None = None
            exact_candidates = candidates
            if bool(getattr(args, "rollout_fast_mode", False)) or bool(getattr(args, "rollout_coarse_eval", False)):
                exact_candidates, heuristic_scores, heuristic_best_action = rollout_select_fast_candidates(
                    base_game,
                    components,
                    candidates,
                    case,
                    args,
                )
                result["coarse_candidate_count"] += len(candidates)
                result["exact_verified_candidate_count"] += len(exact_candidates)
            else:
                result["coarse_candidate_count"] += len(candidates)
                result["exact_verified_candidate_count"] += len(candidates)
            if (
                float(getattr(args, "rollout_max_seconds_per_case", 0.0) or 0.0) > 0
                and time.monotonic() - case_start > float(args.rollout_max_seconds_per_case)
            ):
                skip_reasons["case_timeout_before_exact"] += 1
                result["timeout_case_count"] += 1
                result["skipped_due_to_timeout_count"] += 1
                result["skipped_case_count"] += 1
                continue
            action_summaries = rollout_evaluate_candidate_summaries(
                case,
                components,
                actor,
                device_info["device"],
                profile_config,
                args,
                exact_candidates,
                case_index,
            )
            if (
                float(getattr(args, "rollout_max_seconds_per_case", 0.0) or 0.0) > 0
                and time.monotonic() - case_start > float(args.rollout_max_seconds_per_case)
            ):
                result["timeout_case_count"] += 1
            action_summaries = sorted(
                action_summaries,
                key=lambda item: (float(item["estimated_team_win_rate"]), -float(item["avg_final_rank"])),
                reverse=True,
            )
            best_action = action_summaries[0]
            model_rate = rollout_action_rate_by_source(action_summaries, "model_sample")
            baseline_rate = rollout_action_rate_by_source(action_summaries, "baseline")
            min_beat_rate = rollout_action_rate_by_source(action_summaries, "min_beat")
            if model_rate is not None:
                model_rates.append(model_rate)
            if baseline_rate is not None:
                baseline_rates.append(baseline_rate)
            if min_beat_rate is not None:
                min_beat_rates.append(min_beat_rate)
            best_rates.append(float(best_action["estimated_team_win_rate"]))
            improvement_ref = max(value for value in [model_rate, baseline_rate] if value is not None) if (
                model_rate is not None or baseline_rate is not None
            ) else 0.0
            has_teacher = float(best_action["estimated_team_win_rate"]) - float(improvement_ref) >= 0.15
            if has_teacher:
                result["rollout_teacher_label_count"] += 1
            tags = [str(tag) for tag in case.get("reason_tags") or []]
            reason_tags.update(tags)
            case_result = {
                "case_index": case_index,
                "source_game_id": case.get("game_id"),
                "source_turn": case.get("turn"),
                "reason_tags": tags,
                "level": case.get("level"),
                "current_player": case.get("current_player"),
                "was_lead": was_lead,
                "hand_before": hand_before,
                "last_play": list(base_game.last_play or []),
                "remaining_hand_sizes": list(case.get("remaining_hand_sizes") or []),
                "obs": (base_game._get_obs().tolist() if hasattr(base_game._get_obs(), "tolist") else list(base_game._get_obs())),
                "legal_mask": list(oracle["mask"]),
                "model_action_id": case.get("model_action_id"),
                "model_physical_cards": corrective_cards_to_local(list(case.get("model_physical_cards") or [])),
                "baseline_action_if_same_state": corrective_cards_to_local(list(case.get("baseline_action_if_same_state") or [])),
                "candidate_count": len(candidates),
                "coarse_candidate_count": len(candidates),
                "exact_verified_candidate_count": len(exact_candidates),
                "heuristic_best_action": heuristic_best_action,
                "heuristic_score_by_action": heuristic_scores,
                "action_evaluations": action_summaries,
                "best_rollout_action": best_action,
                "exact_best_action": best_action,
                "best_rollout_action_win_rate": float(best_action["estimated_team_win_rate"]),
                "model_action_win_rate": model_rate,
                "baseline_action_win_rate": baseline_rate,
                "min_beat_action_win_rate": min_beat_rate,
                "rollout_teacher_label": best_action if has_teacher else None,
            }
            result["cases"].append(case_result)
            candidate_counts.append(len(candidates))
            case_seconds.append(time.monotonic() - case_start)
            result["evaluated_case_count"] += 1
            if len(result["concrete_rollout_examples"]) < 20:
                result["concrete_rollout_examples"].append(
                    {
                        "case_index": case_index,
                        "reason_tags": tags,
                        "model_action_win_rate": model_rate,
                        "baseline_action_win_rate": baseline_rate,
                        "best_rollout_action": best_action,
                        "has_teacher_label": has_teacher,
                    }
                )
            result["skip_reasons"] = dict(skip_reasons)
            result["reason_tag_breakdown"] = dict(reason_tags)
            result["avg_candidate_count"] = sum(candidate_counts) / max(1, len(candidate_counts))
            result["avg_seconds_per_case"] = sum(case_seconds) / max(1, len(case_seconds))
            result["model_action_avg_win_rate"] = sum(model_rates) / max(1, len(model_rates)) if model_rates else None
            result["baseline_action_avg_win_rate"] = sum(baseline_rates) / max(1, len(baseline_rates)) if baseline_rates else None
            result["min_beat_action_avg_win_rate"] = sum(min_beat_rates) / max(1, len(min_beat_rates)) if min_beat_rates else None
            result["rollout_best_action_avg_win_rate"] = sum(best_rates) / max(1, len(best_rates)) if best_rates else None
            result["baseline_action_cache_size"] = len(baseline_cache or {})
            result["legal_options_cache_size"] = len(legal_cache or {})
            save_json(Path(args.rollout_out), result)
    finally:
        restore_baseline()
    result["skip_reasons"] = dict(skip_reasons)
    result["reason_tag_breakdown"] = dict(reason_tags)
    result["avg_candidate_count"] = sum(candidate_counts) / max(1, len(candidate_counts))
    result["avg_seconds_per_case"] = sum(case_seconds) / max(1, len(case_seconds))
    result["model_action_avg_win_rate"] = sum(model_rates) / max(1, len(model_rates)) if model_rates else None
    result["baseline_action_avg_win_rate"] = sum(baseline_rates) / max(1, len(baseline_rates)) if baseline_rates else None
    result["min_beat_action_avg_win_rate"] = sum(min_beat_rates) / max(1, len(min_beat_rates)) if min_beat_rates else None
    result["rollout_best_action_avg_win_rate"] = sum(best_rates) / max(1, len(best_rates)) if best_rates else None
    result["baseline_action_cache_size"] = len(baseline_cache or {})
    result["legal_options_cache_size"] = len(legal_cache or {})
    save_json(Path(args.rollout_out), result)
    print(json.dumps(result, ensure_ascii=False, indent=2))


def rollout_teacher_sample_from_case(case: dict, label_weight: float, min_improvement: float) -> tuple[dict | None, str | None]:
    label = case.get("rollout_teacher_label")
    if not label:
        return None, "no_rollout_teacher_label"
    best_rate = float(case.get("best_rollout_action_win_rate") or 0.0)
    model_rate = case.get("model_action_win_rate")
    model_rate_value = float(model_rate) if model_rate is not None else 0.0
    if best_rate - model_rate_value < float(min_improvement):
        return None, "insufficient_model_improvement"
    action_id = int(label.get("action_id"))
    legal_mask = list(case.get("legal_mask") or [])
    obs = list(case.get("obs") or [])
    physical_cards = list(label.get("physical_cards") or [])
    hand_before = list(case.get("hand_before") or [])
    if len(obs) != OFFLINE_STATE_DIM:
        return None, "obs_dim_mismatch"
    if len(legal_mask) != OFFLINE_ACTION_DIM:
        return None, "legal_mask_dim_mismatch"
    if not 0 <= action_id < OFFLINE_ACTION_DIM or float(legal_mask[action_id]) <= 0:
        return None, "label_not_in_mask"
    if not offline_cards_in_hand(physical_cards, hand_before):
        return None, "label_cards_not_in_hand"
    sample = {
        "obs": obs,
        "legal_mask": legal_mask,
        "teacher_action_id": action_id,
        "teacher_chosen_cards": physical_cards,
        "teacher_chosen_cards_website": local_cards_to_website(physical_cards),
        "action_type": str(label.get("action_type") or "unknown"),
        "current_player": case.get("current_player"),
        "hand_size_by_player": case.get("remaining_hand_sizes") or [],
        "hand_before": list(hand_before),
        "last_play": list(case.get("last_play") or []),
        "active_level": website_level_to_local_level(str(case.get("level") or "2")),
        "level": case.get("level"),
        "was_lead": bool(case.get("was_lead")),
        "was_follow": not bool(case.get("was_lead")),
        "is_rollout_teacher": True,
        "rollout_teacher_action_id": action_id,
        "rollout_teacher_physical_cards": physical_cards,
        "original_model_action_id": case.get("model_action_id"),
        "original_model_physical_cards": list(case.get("model_physical_cards") or []),
        "estimated_action_win_rate": best_rate,
        "model_action_win_rate": model_rate,
        "baseline_action_win_rate": case.get("baseline_action_win_rate"),
        "reason_tags": list(case.get("reason_tags") or []),
        "weight": float(label_weight),
        "source_game_id": case.get("source_game_id"),
        "source_turn": case.get("source_turn"),
    }
    return sample, None


def rollout_teacher_dedup_key(sample: dict) -> tuple:
    obs = sample.get("obs") or []
    return (
        tuple(float(value) for value in obs),
        int(sample.get("rollout_teacher_action_id") or sample.get("teacher_action_id")),
        tuple(sample.get("rollout_teacher_physical_cards") or sample.get("teacher_chosen_cards") or []),
    )


def rollout_teacher_sample_valid(sample: dict) -> tuple[bool, str | None]:
    action_id = int(sample.get("rollout_teacher_action_id") or sample.get("teacher_action_id", -1))
    mask = sample.get("legal_mask") or []
    cards = list(sample.get("rollout_teacher_physical_cards") or sample.get("teacher_chosen_cards") or [])
    hand = list(sample.get("hand_before") or [])
    if len(mask) != OFFLINE_ACTION_DIM:
        return False, "legal_mask_dim_mismatch"
    if not 0 <= action_id < OFFLINE_ACTION_DIM:
        return False, "action_id_out_of_range"
    if float(mask[action_id]) <= 0:
        return False, "action_id_not_in_legal_mask"
    if hand and not offline_cards_in_hand(cards, hand):
        return False, "physical_cards_not_in_hand"
    return True, None


def run_build_rollout_teacher_dataset(args: argparse.Namespace) -> None:
    rollout_paths = [Path(item.strip()) for item in str(args.rollout_eval or "").split(",") if item.strip()]
    base_path = Path(args.base_imitation_dataset)
    if not rollout_paths:
        raise RuntimeError("--rollout-eval is required")
    missing_rollouts = [str(path) for path in rollout_paths if not path.exists()]
    if missing_rollouts:
        raise RuntimeError(f"rollout eval file(s) not found: {', '.join(missing_rollouts)}")
    if not base_path.exists():
        raise RuntimeError(f"base imitation dataset not found: {base_path}")
    base_samples, base_summary, _base_format = load_imitation_dataset(base_path)
    rollout_samples: list[dict] = []
    reject_reasons: Counter = Counter()
    reason_counts: Counter = Counter()
    label_count_by_source: Counter = Counter()
    action_type_counts: Counter = Counter()
    seen_keys: set[tuple] = set()
    raw_rollout_label_count = 0
    illegal_label_count = 0
    for rollout_path in rollout_paths:
        rollout_payload = load_json(rollout_path, {})
        for case in rollout_payload.get("cases") or []:
            if not case.get("rollout_teacher_label"):
                continue
            raw_rollout_label_count += 1
            sample, reason = rollout_teacher_sample_from_case(
                case,
                float(args.rollout_label_weight),
                float(args.rollout_min_improvement),
            )
            if sample is None:
                reject_reasons[str(reason or "unknown")] += 1
                if reason in {"label_not_in_mask", "label_cards_not_in_hand", "legal_mask_dim_mismatch"}:
                    illegal_label_count += 1
                continue
            sample["source_rollout_eval"] = str(rollout_path)
            ok, invalid_reason = rollout_teacher_sample_valid(sample)
            if not ok:
                illegal_label_count += 1
                reject_reasons[str(invalid_reason or "invalid_label")] += 1
                continue
            key = rollout_teacher_dedup_key(sample)
            if key in seen_keys:
                reject_reasons["duplicate_rollout_label"] += 1
                continue
            seen_keys.add(key)
            rollout_samples.append(sample)
            label_count_by_source[str(rollout_path)] += 1
            reason_counts.update(sample.get("reason_tags") or [])
            action_type_counts[str(sample.get("action_type") or "unknown")] += 1
    merged = list(base_samples) + rollout_samples
    summary = {
        "format": "rollout_teacher_dataset_v1",
        "base_dataset": str(base_path),
        "base_sample_count": len(base_samples),
        "base_summary": {
            "legal_mask_source": base_summary.get("legal_mask_source"),
            "sample_count": base_summary.get("sample_count") or len(base_samples),
        },
        "rollout_eval": ",".join(str(path) for path in rollout_paths),
        "rollout_eval_files": [str(path) for path in rollout_paths],
        "rollout_eval_file_count": len(rollout_paths),
        "rollout_label_weight": float(args.rollout_label_weight),
        "rollout_min_improvement": float(args.rollout_min_improvement),
        "raw_rollout_label_count": raw_rollout_label_count,
        "unique_rollout_label_count": len(rollout_samples),
        "rollout_teacher_sample_count": len(rollout_samples),
        "merged_sample_count": len(merged),
        "label_count_by_source": dict(label_count_by_source),
        "reason_tag_breakdown": dict(reason_counts),
        "reason_tag_counts": dict(reason_counts),
        "action_type_distribution": dict(action_type_counts),
        "reject_reasons": dict(reject_reasons),
        "illegal_label_count": illegal_label_count,
        "legal_mask_source": "website_oracle",
        "action_dim_checked": True,
        "legal_mask_dim_checked": True,
        "threshold_passed": bool(rollout_samples and illegal_label_count == 0),
    }
    out_path = Path(args.rollout_dataset_out)
    write_imitation_dataset(out_path, imitation_dataset_format(out_path), merged, summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    if not summary["threshold_passed"]:
        raise RuntimeError("no rollout teacher samples were built")


def rollout_distill_label_id(sample: dict) -> int:
    if sample.get("is_rollout_teacher") and sample.get("rollout_teacher_action_id") is not None:
        return int(sample["rollout_teacher_action_id"])
    return int(sample.get("teacher_action_id", -1))


def rollout_distill_sample_weight(sample: dict, args: argparse.Namespace) -> float:
    if sample.get("is_rollout_teacher"):
        return float(args.rollout_label_weight) * float(sample.get("weight", 1.0))
    return 1.0


def rollout_distill_batch_metrics(actor: Any, samples: list[dict], indices: list[int], batch_size: int, device: Any) -> dict:
    import numpy as np
    import torch
    import torch.nn.functional as F

    tag_names = ["pass_when_can_beat", "bad_endgame", "missed_opponent_block"]
    if not indices:
        return {
            "loss": 0.0,
            "overall_accuracy": 0.0,
            "rollout_teacher_accuracy": 0.0,
            "action_type_macro_accuracy": 0.0,
            "reason_tag_accuracy": {},
            **{f"{tag}_accuracy": 0.0 for tag in tag_names},
        }
    total_loss = 0.0
    total_seen = 0
    total_correct = 0
    rollout_seen = 0
    rollout_correct = 0
    tag_seen = Counter()
    tag_correct = Counter()
    type_seen = Counter()
    type_correct = Counter()
    actor.eval()
    with torch.no_grad():
        for start in range(0, len(indices), batch_size):
            batch_indices = indices[start : start + batch_size]
            states = torch.tensor(
                np.asarray([samples[idx]["obs"] for idx in batch_indices], dtype=np.float32),
                dtype=torch.float32,
                device=device,
            )
            masks = torch.tensor(
                np.asarray([samples[idx]["legal_mask"] for idx in batch_indices], dtype=np.float32),
                dtype=torch.float32,
                device=device,
            )
            labels = torch.tensor([rollout_distill_label_id(samples[idx]) for idx in batch_indices], dtype=torch.long, device=device)
            logits = actor.net(states)
            masked_logits = logits.masked_fill(masks <= 0, -1e9)
            loss = F.cross_entropy(masked_logits, labels, reduction="sum")
            predictions = masked_logits.argmax(dim=-1).detach().cpu().tolist()
            label_values = labels.detach().cpu().tolist()
            total_loss += float(loss.item())
            total_seen += len(batch_indices)
            for idx, pred, label_value in zip(batch_indices, predictions, label_values):
                sample = samples[idx]
                correct = int(pred == label_value)
                total_correct += correct
                action_type = imitation_action_type(sample)
                type_seen[action_type] += 1
                type_correct[action_type] += correct
                if sample.get("is_rollout_teacher"):
                    rollout_seen += 1
                    rollout_correct += correct
                    for tag in sample.get("reason_tags") or []:
                        tag_seen[str(tag)] += 1
                        tag_correct[str(tag)] += correct
    actor.train()
    type_accuracy = {
        action_type: {
            "accuracy": type_correct[action_type] / max(1, count),
            "correct": int(type_correct[action_type]),
            "total": int(count),
        }
        for action_type, count in sorted(type_seen.items())
    }
    tag_accuracy = {
        tag: {
            "accuracy": tag_correct[tag] / max(1, count),
            "correct": int(tag_correct[tag]),
            "total": int(count),
        }
        for tag, count in sorted(tag_seen.items())
    }
    macro_values = [entry["accuracy"] for entry in type_accuracy.values()]
    result = {
        "loss": total_loss / max(1, total_seen),
        "overall_accuracy": total_correct / max(1, total_seen),
        "rollout_teacher_accuracy": rollout_correct / max(1, rollout_seen),
        "reason_tag_accuracy": tag_accuracy,
        "action_type_macro_accuracy": sum(macro_values) / max(1, len(macro_values)),
    }
    for tag in tag_names:
        result[f"{tag}_accuracy"] = tag_correct[tag] / max(1, tag_seen[tag])
    return result


def run_train_rollout_distill(args: argparse.Namespace) -> None:
    import numpy as np
    import torch
    import torch.nn.functional as F

    device_info = offline_resolve_device(args.device)
    if device_info["torch"] is None:
        raise RuntimeError("torch backend is required for rollout distillation")
    dataset_path = Path(args.rollout_dataset)
    if not dataset_path.exists():
        raise RuntimeError(f"rollout dataset not found: {dataset_path}")
    samples, dataset_summary, dataset_format = load_imitation_dataset(dataset_path)
    invalid = 0
    for sample in samples:
        label = rollout_distill_label_id(sample)
        mask = sample.get("legal_mask") or []
        if (
            len(sample.get("obs") or []) != OFFLINE_STATE_DIM
            or len(mask) != OFFLINE_ACTION_DIM
            or not 0 <= label < OFFLINE_ACTION_DIM
            or float(mask[label]) <= 0
        ):
            invalid += 1
    if invalid:
        raise RuntimeError(f"invalid rollout distill samples: {invalid}")
    device = device_info["device"]
    components = offline_load_guandan_components()
    actor, _critic, _actor_optimizer, _critic_optimizer = offline_build_models(len(components["actions"]), device)
    if args.init_actor:
        try:
            state_dict = torch.load(Path(args.init_actor), map_location=device, weights_only=True)
        except TypeError:
            state_dict = torch.load(Path(args.init_actor), map_location=device)
        actor.load_state_dict(state_dict)
    optimizer = torch.optim.Adam(actor.parameters(), lr=float(args.learning_rate))
    rng = random.Random(20260707)
    indices = list(range(len(samples)))
    rng.shuffle(indices)
    val_count = int(round(len(indices) * float(args.validation_split)))
    val_count = min(max(val_count, 1 if len(indices) > 1 else 0), max(0, len(indices) - 1))
    val_indices = indices[:val_count]
    train_indices = indices[val_count:]
    out_dir = Path(args.rollout_distill_out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    log = {
        "backend": device_info["backend"],
        "requested_device": device_info["requested_device"],
        "actual_device": device_info["actual_device"],
        "device_fallback": device_info["device_fallback"],
        "dataset_path": str(dataset_path),
        "dataset_format": dataset_format,
        "dataset_summary": dataset_summary,
        "sample_count": len(samples),
        "rollout_teacher_sample_count": sum(1 for sample in samples if sample.get("is_rollout_teacher")),
        "train_sample_count": len(train_indices),
        "val_sample_count": len(val_indices),
        "rollout_distill_epochs": int(args.rollout_distill_epochs),
        "batch_size": int(args.batch_size),
        "learning_rate": float(args.learning_rate),
        "rollout_label_weight": float(args.rollout_label_weight),
        "validation_split": float(args.validation_split),
        "early_stop_patience": int(args.early_stop_patience),
        "train_loss_by_epoch": [],
        "val_loss_by_epoch": [],
        "overall_val_accuracy_by_epoch": [],
        "rollout_teacher_val_accuracy_by_epoch": [],
        "best_epoch": None,
        "best_val_accuracy": 0.0,
        "early_stopped": False,
        "saved_checkpoints": [],
        "threshold_passed": False,
    }
    best_val_loss = float("inf")
    best_val_accuracy = -1.0
    stale_epochs = 0
    best_path = out_dir / "rollout_distill_actor_best.pth"
    for epoch in range(1, int(args.rollout_distill_epochs) + 1):
        actor.train()
        rng.shuffle(train_indices)
        loss_num = 0.0
        loss_den = 0.0
        for start in range(0, len(train_indices), int(args.batch_size)):
            batch_indices = train_indices[start : start + int(args.batch_size)]
            states = torch.tensor(
                np.asarray([samples[idx]["obs"] for idx in batch_indices], dtype=np.float32),
                dtype=torch.float32,
                device=device,
            )
            masks = torch.tensor(
                np.asarray([samples[idx]["legal_mask"] for idx in batch_indices], dtype=np.float32),
                dtype=torch.float32,
                device=device,
            )
            labels = torch.tensor([rollout_distill_label_id(samples[idx]) for idx in batch_indices], dtype=torch.long, device=device)
            weights = torch.tensor(
                [rollout_distill_sample_weight(samples[idx], args) for idx in batch_indices],
                dtype=torch.float32,
                device=device,
            )
            logits = actor.net(states)
            if logits.shape[-1] != OFFLINE_ACTION_DIM:
                raise RuntimeError(f"actor output dim mismatch: {logits.shape[-1]}")
            masked_logits = logits.masked_fill(masks <= 0, -1e9)
            loss_items = F.cross_entropy(masked_logits, labels, reduction="none")
            loss = (loss_items * weights).sum() / weights.sum().clamp_min(1e-8)
            optimizer.zero_grad()
            loss.backward()
            optimizer.step()
            loss_num += float((loss_items.detach() * weights.detach()).sum().item())
            loss_den += float(weights.detach().sum().item())
        train_loss = loss_num / max(1e-8, loss_den)
        val_metrics = rollout_distill_batch_metrics(actor, samples, val_indices, int(args.batch_size), device)
        val_loss = float(val_metrics["loss"])
        val_accuracy = float(val_metrics["overall_accuracy"])
        log["train_loss_by_epoch"].append(train_loss)
        log["val_loss_by_epoch"].append(val_loss)
        log["overall_val_accuracy_by_epoch"].append(val_accuracy)
        log["rollout_teacher_val_accuracy_by_epoch"].append(val_metrics["rollout_teacher_accuracy"])
        improved = val_loss < best_val_loss or val_accuracy > best_val_accuracy
        if improved:
            best_val_loss = min(best_val_loss, val_loss)
            best_val_accuracy = max(best_val_accuracy, val_accuracy)
            log["best_epoch"] = epoch
            log["best_val_accuracy"] = best_val_accuracy
            torch.save(actor.state_dict(), best_path)
            stale_epochs = 0
        else:
            stale_epochs += 1
        checkpoint = out_dir / f"rollout_distill_actor_epoch{epoch}.pth"
        torch.save(actor.state_dict(), checkpoint)
        log["saved_checkpoints"].append(str(checkpoint))
        if int(args.early_stop_patience) > 0 and stale_epochs >= int(args.early_stop_patience):
            log["early_stopped"] = True
            break
    final_metrics = rollout_distill_batch_metrics(actor, samples, val_indices, int(args.batch_size), device)
    log.update(
        {
            "overall_val_accuracy": final_metrics["overall_accuracy"],
            "rollout_teacher_accuracy": final_metrics["rollout_teacher_accuracy"],
            "reason_tag_accuracy": final_metrics["reason_tag_accuracy"],
            "pass_when_can_beat_accuracy": final_metrics["pass_when_can_beat_accuracy"],
            "bad_endgame_accuracy": final_metrics["bad_endgame_accuracy"],
            "missed_opponent_block_accuracy": final_metrics["missed_opponent_block_accuracy"],
            "action_type_macro_accuracy": final_metrics["action_type_macro_accuracy"],
            "threshold_passed": bool(best_path.exists() and log["saved_checkpoints"]),
        }
    )
    save_json(out_dir / "rollout_distill_training_state.json", log)
    save_json(Path(args.rollout_distill_log_out), log)
    print(json.dumps(log, ensure_ascii=False, indent=2))
    if not log["threshold_passed"]:
        raise RuntimeError("rollout distillation threshold failed")


def rollout_focused_split_indices(indices: list[int], validation_split: float, rng: random.Random) -> tuple[list[int], list[int]]:
    shuffled = list(indices)
    rng.shuffle(shuffled)
    if len(shuffled) <= 1:
        return shuffled, []
    val_count = int(round(len(shuffled) * float(validation_split)))
    val_count = min(max(val_count, 1), len(shuffled) - 1)
    return shuffled[val_count:], shuffled[:val_count]


def rollout_focused_epoch_batches(
    base_indices: list[int],
    rollout_indices: list[int],
    args: argparse.Namespace,
    rng: random.Random,
    epoch: int,
) -> list[list[int]]:
    batch_size = max(1, int(args.batch_size))
    if not rollout_indices:
        raise RuntimeError("focused rollout distill requires rollout teacher samples")
    if epoch <= int(args.rollout_only_warmup_epochs):
        total_rollout = max(batch_size, len(rollout_indices) * max(1, int(args.rollout_oversample_factor)))
        selected = [rng.choice(rollout_indices) for _ in range(total_rollout)]
        rng.shuffle(selected)
        return [selected[start : start + batch_size] for start in range(0, len(selected), batch_size)]

    ratio = min(0.95, max(0.05, float(args.rollout_sample_ratio)))
    rollout_per_batch = min(batch_size - 1, max(1, int(round(batch_size * ratio)))) if base_indices else batch_size
    base_per_batch = max(0, batch_size - rollout_per_batch)
    base_epoch_count = int(round(len(base_indices) * max(0.0, float(args.base_sample_ratio))))
    if base_indices and base_epoch_count <= 0:
        base_epoch_count = base_per_batch
    n_batches = max(
        1,
        (base_epoch_count + max(1, base_per_batch) - 1) // max(1, base_per_batch) if base_per_batch else 1,
    )
    base_pool = list(base_indices)
    rng.shuffle(base_pool)
    batches: list[list[int]] = []
    base_cursor = 0
    for _batch_index in range(n_batches):
        batch: list[int] = [rng.choice(rollout_indices) for _ in range(rollout_per_batch)]
        if base_per_batch and base_indices:
            if base_cursor + base_per_batch > len(base_pool):
                rng.shuffle(base_pool)
                base_cursor = 0
            batch.extend(base_pool[base_cursor : base_cursor + base_per_batch])
            base_cursor += base_per_batch
        rng.shuffle(batch)
        batches.append(batch)
    return batches


def rollout_focused_sample_weight(sample: dict, args: argparse.Namespace) -> float:
    if sample.get("is_rollout_teacher"):
        return float(args.rollout_loss_weight) * float(sample.get("weight", 1.0))
    return float(args.preserve_base_loss_weight)


def rollout_focused_metrics(actor: Any, samples: list[dict], indices: list[int], batch_size: int, device: Any) -> dict:
    import numpy as np
    import torch
    import torch.nn.functional as F

    tag_names = ["pass_when_can_beat", "bad_endgame", "missed_opponent_block", "missed_bomb_block"]
    if not indices:
        return {
            "loss": 0.0,
            "overall_accuracy": 0.0,
            "base_accuracy": 0.0,
            "rollout_teacher_accuracy": 0.0,
            "action_type_macro_accuracy": 0.0,
            "reason_tag_accuracy": {},
            **{f"{tag}_accuracy": 0.0 for tag in tag_names},
        }
    total_loss = 0.0
    total_seen = 0
    total_correct = 0
    base_seen = 0
    base_correct = 0
    rollout_seen = 0
    rollout_correct = 0
    tag_seen = Counter()
    tag_correct = Counter()
    type_seen = Counter()
    type_correct = Counter()
    actor.eval()
    with torch.no_grad():
        for start in range(0, len(indices), batch_size):
            batch_indices = indices[start : start + batch_size]
            states = torch.tensor(
                np.asarray([samples[idx]["obs"] for idx in batch_indices], dtype=np.float32),
                dtype=torch.float32,
                device=device,
            )
            masks = torch.tensor(
                np.asarray([samples[idx]["legal_mask"] for idx in batch_indices], dtype=np.float32),
                dtype=torch.float32,
                device=device,
            )
            labels = torch.tensor([rollout_distill_label_id(samples[idx]) for idx in batch_indices], dtype=torch.long, device=device)
            logits = actor.net(states)
            masked_logits = logits.masked_fill(masks <= 0, -1e9)
            loss = F.cross_entropy(masked_logits, labels, reduction="sum")
            predictions = masked_logits.argmax(dim=-1).detach().cpu().tolist()
            label_values = labels.detach().cpu().tolist()
            total_loss += float(loss.item())
            total_seen += len(batch_indices)
            for idx, pred, label_value in zip(batch_indices, predictions, label_values):
                sample = samples[idx]
                correct = int(pred == label_value)
                total_correct += correct
                action_type = imitation_action_type(sample)
                type_seen[action_type] += 1
                type_correct[action_type] += correct
                if sample.get("is_rollout_teacher"):
                    rollout_seen += 1
                    rollout_correct += correct
                    for tag in sample.get("reason_tags") or []:
                        tag_seen[str(tag)] += 1
                        tag_correct[str(tag)] += correct
                else:
                    base_seen += 1
                    base_correct += correct
    actor.train()
    type_accuracy = {
        action_type: {
            "accuracy": type_correct[action_type] / max(1, count),
            "correct": int(type_correct[action_type]),
            "total": int(count),
        }
        for action_type, count in sorted(type_seen.items())
    }
    tag_accuracy = {
        tag: {
            "accuracy": tag_correct[tag] / max(1, count),
            "correct": int(tag_correct[tag]),
            "total": int(count),
        }
        for tag, count in sorted(tag_seen.items())
    }
    macro_values = [entry["accuracy"] for entry in type_accuracy.values()]
    result = {
        "loss": total_loss / max(1, total_seen),
        "overall_accuracy": total_correct / max(1, total_seen),
        "base_accuracy": base_correct / max(1, base_seen),
        "rollout_teacher_accuracy": rollout_correct / max(1, rollout_seen),
        "reason_tag_accuracy": tag_accuracy,
        "action_type_macro_accuracy": sum(macro_values) / max(1, len(macro_values)),
        "action_type_accuracy_by_type": type_accuracy,
    }
    for tag in tag_names:
        result[f"{tag}_accuracy"] = tag_correct[tag] / max(1, tag_seen[tag])
    return result


def run_train_rollout_distill_focused(args: argparse.Namespace) -> None:
    import numpy as np
    import torch
    import torch.nn.functional as F

    device_info = offline_resolve_device(args.device)
    if device_info["torch"] is None:
        raise RuntimeError("torch backend is required for focused rollout distillation")
    dataset_path = Path(args.rollout_dataset)
    if not dataset_path.exists():
        raise RuntimeError(f"rollout dataset not found: {dataset_path}")
    samples, dataset_summary, dataset_format = load_imitation_dataset(dataset_path)
    invalid = 0
    for sample in samples:
        label = rollout_distill_label_id(sample)
        mask = sample.get("legal_mask") or []
        if (
            len(sample.get("obs") or []) != OFFLINE_STATE_DIM
            or len(mask) != OFFLINE_ACTION_DIM
            or not 0 <= label < OFFLINE_ACTION_DIM
            or float(mask[label]) <= 0
        ):
            invalid += 1
    if invalid:
        raise RuntimeError(f"invalid focused rollout distill samples: {invalid}")
    rollout_indices = [idx for idx, sample in enumerate(samples) if sample.get("is_rollout_teacher")]
    base_indices = [idx for idx, sample in enumerate(samples) if not sample.get("is_rollout_teacher")]
    if not rollout_indices:
        raise RuntimeError("focused rollout distill dataset has no rollout teacher samples")
    rng = random.Random(20260707)
    base_train, base_val = rollout_focused_split_indices(base_indices, float(args.validation_split), rng)
    rollout_train, rollout_val = rollout_focused_split_indices(rollout_indices, float(args.validation_split), rng)
    if not rollout_val and rollout_train:
        rollout_val = [rollout_train.pop()]
    if not base_val and base_train:
        base_val = [base_train.pop()]
    train_eval_indices = base_train + rollout_train
    val_indices = base_val + rollout_val
    device = device_info["device"]
    components = offline_load_guandan_components()
    actor, _critic, _actor_optimizer, _critic_optimizer = offline_build_models(len(components["actions"]), device)
    if args.init_actor:
        try:
            state_dict = torch.load(Path(args.init_actor), map_location=device, weights_only=True)
        except TypeError:
            state_dict = torch.load(Path(args.init_actor), map_location=device)
        actor.load_state_dict(state_dict)
    optimizer = torch.optim.Adam(actor.parameters(), lr=float(args.learning_rate))
    out_dir = Path(args.rollout_distill_out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    best_rollout_path = out_dir / "rollout_focused_actor_best_rollout.pth"
    best_mixed_path = out_dir / "rollout_focused_actor_best_mixed.pth"
    log = {
        "backend": device_info["backend"],
        "requested_device": device_info["requested_device"],
        "actual_device": device_info["actual_device"],
        "device_fallback": device_info["device_fallback"],
        "dataset_path": str(dataset_path),
        "dataset_format": dataset_format,
        "dataset_summary": dataset_summary,
        "sample_count": len(samples),
        "base_sample_count": len(base_indices),
        "rollout_teacher_sample_count": len(rollout_indices),
        "base_train_sample_count": len(base_train),
        "base_val_sample_count": len(base_val),
        "rollout_train_sample_count": len(rollout_train),
        "rollout_val_sample_count": len(rollout_val),
        "rollout_distill_epochs": int(args.rollout_distill_epochs),
        "batch_size": int(args.batch_size),
        "learning_rate": float(args.learning_rate),
        "rollout_sample_ratio": float(args.rollout_sample_ratio),
        "rollout_oversample_factor": int(args.rollout_oversample_factor),
        "base_sample_ratio": float(args.base_sample_ratio),
        "rollout_only_warmup_epochs": int(args.rollout_only_warmup_epochs),
        "rollout_loss_weight": float(args.rollout_loss_weight),
        "preserve_base_loss_weight": float(args.preserve_base_loss_weight),
        "best_by_rollout_metric": bool(args.best_by_rollout_metric),
        "min_base_val_accuracy": float(args.min_base_val_accuracy),
        "train_loss_by_epoch": [],
        "rollout_teacher_train_accuracy_by_epoch": [],
        "rollout_teacher_val_accuracy_by_epoch": [],
        "base_train_accuracy_by_epoch": [],
        "base_val_accuracy_by_epoch": [],
        "best_rollout_epoch": None,
        "best_mixed_epoch": None,
        "best_rollout_val_accuracy": 0.0,
        "best_mixed_score": -1.0,
        "best_rollout_base_threshold_met": False,
        "early_stopped": False,
        "saved_checkpoints": [],
        "threshold_passed": False,
    }
    best_rollout_metric = -1.0
    best_rollout_any_state: dict | None = None
    best_rollout_any_epoch: int | None = None
    best_mixed_score = -1.0
    stale_epochs = 0
    for epoch in range(1, int(args.rollout_distill_epochs) + 1):
        actor.train()
        batches = rollout_focused_epoch_batches(base_train, rollout_train, args, rng, epoch)
        loss_num = 0.0
        loss_den = 0.0
        for batch_indices in batches:
            states = torch.tensor(
                np.asarray([samples[idx]["obs"] for idx in batch_indices], dtype=np.float32),
                dtype=torch.float32,
                device=device,
            )
            masks = torch.tensor(
                np.asarray([samples[idx]["legal_mask"] for idx in batch_indices], dtype=np.float32),
                dtype=torch.float32,
                device=device,
            )
            labels = torch.tensor([rollout_distill_label_id(samples[idx]) for idx in batch_indices], dtype=torch.long, device=device)
            weights = torch.tensor(
                [rollout_focused_sample_weight(samples[idx], args) for idx in batch_indices],
                dtype=torch.float32,
                device=device,
            )
            logits = actor.net(states)
            if logits.shape[-1] != OFFLINE_ACTION_DIM:
                raise RuntimeError(f"actor output dim mismatch: {logits.shape[-1]}")
            masked_logits = logits.masked_fill(masks <= 0, -1e9)
            loss_items = F.cross_entropy(masked_logits, labels, reduction="none")
            loss = (loss_items * weights).sum() / weights.sum().clamp_min(1e-8)
            optimizer.zero_grad()
            loss.backward()
            optimizer.step()
            loss_num += float((loss_items.detach() * weights.detach()).sum().item())
            loss_den += float(weights.detach().sum().item())
        train_loss = loss_num / max(1e-8, loss_den)
        train_metrics = rollout_focused_metrics(actor, samples, train_eval_indices, int(args.batch_size), device)
        val_metrics = rollout_focused_metrics(actor, samples, val_indices, int(args.batch_size), device)
        rollout_val = float(val_metrics["rollout_teacher_accuracy"])
        base_val = float(val_metrics["base_accuracy"])
        mixed_score = rollout_val + 0.25 * base_val
        log["train_loss_by_epoch"].append(train_loss)
        log["rollout_teacher_train_accuracy_by_epoch"].append(train_metrics["rollout_teacher_accuracy"])
        log["rollout_teacher_val_accuracy_by_epoch"].append(rollout_val)
        log["base_train_accuracy_by_epoch"].append(train_metrics["base_accuracy"])
        log["base_val_accuracy_by_epoch"].append(base_val)
        improved = False
        state_cpu = {key: value.detach().cpu().clone() for key, value in actor.state_dict().items()}
        if rollout_val > best_rollout_metric:
            best_rollout_metric = rollout_val
            best_rollout_any_state = state_cpu
            best_rollout_any_epoch = epoch
            improved = True
            if base_val >= float(args.min_base_val_accuracy):
                torch.save(actor.state_dict(), best_rollout_path)
                log["best_rollout_epoch"] = epoch
                log["best_rollout_val_accuracy"] = rollout_val
                log["best_rollout_base_threshold_met"] = True
        if mixed_score > best_mixed_score:
            best_mixed_score = mixed_score
            torch.save(actor.state_dict(), best_mixed_path)
            log["best_mixed_epoch"] = epoch
            log["best_mixed_score"] = mixed_score
            improved = True
        checkpoint = out_dir / f"rollout_focused_actor_epoch{epoch}.pth"
        torch.save(actor.state_dict(), checkpoint)
        log["saved_checkpoints"].append(str(checkpoint))
        if improved:
            stale_epochs = 0
        else:
            stale_epochs += 1
        if int(args.early_stop_patience) > 0 and stale_epochs >= int(args.early_stop_patience):
            log["early_stopped"] = True
            break
    if not best_rollout_path.exists() and best_rollout_any_state is not None:
        torch.save(best_rollout_any_state, best_rollout_path)
        log["best_rollout_epoch"] = best_rollout_any_epoch
        log["best_rollout_val_accuracy"] = best_rollout_metric
        log["best_rollout_base_threshold_met"] = False
    train_metrics = rollout_focused_metrics(actor, samples, train_eval_indices, int(args.batch_size), device)
    val_metrics = rollout_focused_metrics(actor, samples, val_indices, int(args.batch_size), device)
    log.update(
        {
            "rollout_teacher_train_accuracy": train_metrics["rollout_teacher_accuracy"] if args.eval_rollout_train_accuracy else None,
            "rollout_teacher_val_accuracy": val_metrics["rollout_teacher_accuracy"] if args.eval_rollout_val_accuracy else None,
            "base_train_accuracy": train_metrics["base_accuracy"],
            "base_val_accuracy": val_metrics["base_accuracy"],
            "pass_when_can_beat_accuracy": val_metrics["pass_when_can_beat_accuracy"],
            "bad_endgame_accuracy": val_metrics["bad_endgame_accuracy"],
            "missed_opponent_block_accuracy": val_metrics["missed_opponent_block_accuracy"],
            "missed_bomb_block_accuracy": val_metrics["missed_bomb_block_accuracy"],
            "action_type_macro_accuracy": val_metrics["action_type_macro_accuracy"],
            "reason_tag_accuracy": val_metrics["reason_tag_accuracy"],
            "action_type_accuracy_by_type": val_metrics["action_type_accuracy_by_type"],
            "best_rollout_checkpoint": str(best_rollout_path) if best_rollout_path.exists() else None,
            "best_mixed_checkpoint": str(best_mixed_path) if best_mixed_path.exists() else None,
            "threshold_passed": bool(best_rollout_path.exists() and best_mixed_path.exists() and log["saved_checkpoints"]),
        }
    )
    save_json(out_dir / "rollout_focused_training_state.json", log)
    save_json(Path(args.rollout_distill_log_out), log)
    print(json.dumps(log, ensure_ascii=False, indent=2))
    if not log["threshold_passed"]:
        raise RuntimeError("focused rollout distillation threshold failed")


def website_level_to_local_level(level: str) -> int:
    mapping = {"T": 10, "J": 11, "Q": 12, "K": 13, "A": 14}
    if level in mapping:
        return mapping[level]
    return int(level)


def website_card_to_local_card(card: str) -> str:
    if card == "B":
        return "小王"
    if card == "R":
        return "大王"
    suit_map = {"S": "黑桃", "H": "红桃", "D": "方块", "C": "梅花"}
    rank = "10" if card[1] == "T" else card[1]
    return suit_map[card[0]] + rank


def local_card_to_website_card(card: str) -> str:
    if card == "小王":
        return "B"
    if card == "大王":
        return "R"
    suit_map = {"黑桃": "S", "红桃": "H", "方块": "D", "梅花": "C"}
    for suit_text, suit_code in suit_map.items():
        if card.startswith(suit_text):
            rank = card[len(suit_text):]
            return suit_code + ("T" if rank == "10" else rank)
    raise ValueError(f"unknown local card: {card}")


def website_cards_to_local(cards: list[str]) -> list[str]:
    return [website_card_to_local_card(card) for card in cards]


def local_cards_to_website(cards: list[str]) -> list[str]:
    return [local_card_to_website_card(card) for card in cards]


def website_action_set_key(cards: list[str] | tuple[str, ...], level: str) -> tuple[str, ...]:
    return normalized_action_key(list(cards), level)


def action_counter_in_hand(cards: list[str], hand: list[str]) -> bool:
    needed = Counter(cards)
    available = Counter(hand)
    return all(available[card] >= count for card, count in needed.items())


def website_rule_legal_action_set(
    hand: list[str],
    last_play: list[str],
    level: str,
    chosen: list[str] | None = None,
) -> set[tuple[str, ...]]:
    actions: set[tuple[str, ...]] = set()
    chosen = chosen or []
    if last_play:
        actions.add(())
        if chosen and engine.play_beats(chosen, last_play, level):
            actions.add(website_action_set_key(chosen, level))
        return actions
    for cards in casebook_lead_candidate_cards(hand, level):
        if engine.recognize(cards, level):
            actions.add(website_action_set_key(cards, level))
    if chosen and engine.recognize(chosen, level):
        actions.add(website_action_set_key(chosen, level))
    return actions


def local_rule_legal_action_set(
    components: dict,
    hand: list[str],
    last_play: list[str],
    level: str,
    candidate_actions: set[tuple[str, ...]] | None = None,
) -> tuple[set[tuple[str, ...]], dict]:
    if candidate_actions is not None:
        actions = set()
        for cards in candidate_actions:
            if local_rule_action_is_legal(components, hand, last_play, list(cards), level):
                actions.add(website_action_set_key(list(cards), level))
        return actions, {"disagree_ids": [], "bounded_candidate_count": len(candidate_actions)}
    GuandanGame = components["GuandanGame"]
    local_level = website_level_to_local_level(level)
    was_lead = not bool(last_play)
    game = GuandanGame(active_level=local_level, verbose=False, print_history=False)
    game.is_free_turn = was_lead
    local_hand = website_cards_to_local(hand)
    local_last = website_cards_to_local(last_play)
    raw_mask = game.get_valid_action_mask(
        local_hand,
        components["actions"],
        local_level,
        [] if was_lead else local_last,
    )
    verified = offline_verified_legal_options(
        game,
        components,
        local_hand,
        local_last,
        was_lead,
        raw_mask,
        max_combos_per_action=100000,
    )
    actions: set[tuple[str, ...]] = set()
    for combos in verified["verified_options"].values():
        for combo in combos:
            website_cards = local_cards_to_website(list(combo))
            actions.add(website_action_set_key(website_cards, level))
    return actions, verified


def local_rule_action_is_legal(components: dict, hand: list[str], last_play: list[str], chosen: list[str], level: str) -> bool:
    if not chosen:
        return bool(last_play)
    if not action_counter_in_hand(chosen, hand):
        return False
    if not last_play:
        return bool(engine.recognize(chosen, level))
    return bool(engine.play_beats(chosen, last_play, level))


def local_rule_play_beats(components: dict, cards: list[str], last_play: list[str], level: str) -> bool:
    if not cards:
        return False
    return local_rule_action_is_legal(components, cards, last_play, cards, level)


def action_uses_heart_level(cards: list[str], level: str) -> bool:
    return any(card == "H" + level for card in cards)


def action_uses_level(cards: list[str], level: str) -> bool:
    return any(card not in {"B", "R"} and card[1] == level for card in cards)


def website_rule_fixture_issues(components: dict) -> tuple[Counter, list[dict]]:
    checks = [
        {
            "name": "five_bomb_beats_four_bomb",
            "category": "bomb_order_issue",
            "level": "A",
            "ours": ["S3", "H3", "D3", "C3", "S3"],
            "theirs": ["S2", "H2", "D2", "C2"],
        },
        {
            "name": "straight_flush_beats_six_bomb",
            "category": "straight_flush_issue",
            "level": "A",
            "ours": ["S3", "S4", "S5", "S6", "S7"],
            "theirs": ["S2", "H2", "D2", "C2", "S2", "H2"],
        },
        {
            "name": "seven_bomb_beats_straight_flush",
            "category": "straight_flush_issue",
            "level": "A",
            "ours": ["S4", "H4", "D4", "C4", "S4", "H4", "D4"],
            "theirs": ["S3", "S4", "S5", "S6", "S7"],
        },
        {
            "name": "quad_kings_beats_eight_bomb",
            "category": "bomb_order_issue",
            "level": "A",
            "ours": ["B", "B", "R", "R"],
            "theirs": ["S3", "H3", "D3", "C3", "S3", "H3", "D3", "C3"],
        },
        {
            "name": "quad_kings_is_max",
            "category": "bomb_order_issue",
            "level": "A",
            "ours": ["B", "B", "R", "R"],
            "theirs": ["S2", "H2", "D2", "C2", "S2", "H2", "D2", "C2"],
        },
    ]
    issue_counts: Counter = Counter()
    issues: list[dict] = []
    for check in checks:
        website_result = engine.play_beats(check["ours"], check["theirs"], check["level"])
        local_result = local_rule_play_beats(components, check["ours"], check["theirs"], check["level"])
        if bool(website_result) != bool(local_result):
            issue_counts[check["category"]] += 1
            issues.append({**check, "website_result": website_result, "local_result": local_result})
    return issue_counts, issues


def run_website_rule_consistency(profile: str, out_path: str) -> dict:
    results = load_json(RESULTS_PATH, {})
    backfill_game_records_from_logs(results)
    records = [record for record in official_game_records(results) if record.get("profile") == profile]
    logs = research_log_index()
    components = offline_load_guandan_components()
    website_legal_cache: dict[tuple, set[tuple[str, ...]]] = {}
    local_legal_cache: dict[tuple, tuple[set[tuple[str, ...]], dict]] = {}
    disagreement_types: Counter = Counter()
    concrete: list[dict] = []
    evaluated_games = 0
    evaluated_decisions = 0
    chosen_valid = 0
    chosen_invalid = 0
    action_not_in_hand = 0
    can_beat_agree = 0
    can_beat_disagree = 0
    legal_agree = 0
    legal_disagree = 0
    heart_level_issue = 0
    wild_card_issue = 0
    pass_rule_issue = 0
    missing_logs = 0

    fixture_issue_counts, fixture_issues = website_rule_fixture_issues(components)
    bomb_order_issue = int(fixture_issue_counts.get("bomb_order_issue", 0))
    straight_flush_issue = int(fixture_issue_counts.get("straight_flush_issue", 0))
    if fixture_issues:
        concrete.extend({"type": "fixture_rule_disagreement", **issue} for issue in fixture_issues)
    invalid_reasons: Counter = Counter()
    can_beat_reasons: Counter = Counter()
    heart_examples: list[dict] = []
    wild_examples: list[dict] = []

    for record in records:
        payload = logs.get((str(record.get("game_id")), profile), {})
        if not payload:
            missing_logs += 1
            continue
        evaluated_games += 1
        for decision in payload.get("decisions") or []:
            hand = list(decision.get("hand") or [])
            chosen = list(decision.get("play") or [])
            last_play = list(decision.get("last_play") or [])
            level = str(decision.get("level") or "")
            if not hand or not level:
                continue
            evaluated_decisions += 1
            was_follow = bool(last_play)
            was_lead = not was_follow
            chosen_key = website_action_set_key(chosen, level)
            if chosen and not action_counter_in_hand(chosen, hand):
                action_not_in_hand += 1
                disagreement_types["chosen_action_not_in_hand"] += 1
                invalid_reasons["action_not_in_hand"] += 1
            if not chosen and was_lead:
                pass_rule_issue += 1
                disagreement_types["pass_on_lead"] += 1
                invalid_reasons["pass_on_lead"] += 1
            cache_key = (
                tuple(engine.sort_cards(hand, level)),
                tuple(engine.sort_cards(last_play, level)),
                tuple(engine.sort_cards(chosen, level)),
                level,
            )
            if cache_key not in website_legal_cache:
                website_legal_cache[cache_key] = website_rule_legal_action_set(hand, last_play, level, chosen)
            if cache_key not in local_legal_cache:
                local_legal_cache[cache_key] = local_rule_legal_action_set(
                    components,
                    hand,
                    last_play,
                    level,
                    candidate_actions=website_legal_cache[cache_key],
                )
            website_actions = website_legal_cache[cache_key]
            local_actions, local_meta = local_legal_cache[cache_key]
            local_chosen_valid = chosen_key in local_actions
            if local_chosen_valid:
                chosen_valid += 1
            else:
                chosen_invalid += 1
                disagreement_types["chosen_action_not_local_legal"] += 1
                if not chosen and was_follow:
                    invalid_reasons["follow_pass_not_local_legal"] += 1
                elif not action_counter_in_hand(chosen, hand):
                    invalid_reasons["action_not_in_hand"] += 1
                elif was_follow and not engine.play_beats(chosen, last_play, level):
                    invalid_reasons["chosen_does_not_beat_last_play"] += 1
                elif not was_follow and not engine.recognize(chosen, level):
                    invalid_reasons["chosen_not_recognized_on_lead"] += 1
                else:
                    invalid_reasons["local_rule_mapping_mismatch"] += 1
            if was_follow:
                website_beats = bool(chosen and engine.play_beats(chosen, last_play, level))
                local_beats = bool(chosen and local_rule_action_is_legal(components, hand, last_play, chosen, level))
                if website_beats == local_beats:
                    can_beat_agree += 1
                else:
                    can_beat_disagree += 1
                    disagreement_types["can_beat_disagree"] += 1
                    if website_beats and not local_beats:
                        can_beat_reasons["website_true_local_false"] += 1
                    elif local_beats and not website_beats:
                        can_beat_reasons["local_true_website_false"] += 1
                    else:
                        can_beat_reasons["unknown"] += 1
            if website_actions == local_actions:
                legal_agree += 1
            else:
                legal_disagree += 1
                disagreement_types["legal_action_set_disagree"] += 1
            if action_uses_heart_level(hand + chosen + last_play, level) and (website_actions != local_actions or not local_chosen_valid):
                heart_level_issue += 1
                wild_card_issue += 1
                disagreement_types["heart_level_wildcard_disagree"] += 1
                if len(heart_examples) < 10:
                    heart_examples.append(
                        {
                            "game_id": str(record.get("game_id")),
                            "turn": decision.get("turn"),
                            "level": level,
                            "hand_before": hand,
                            "last_play": last_play,
                            "chosen_action": chosen,
                        }
                    )
            elif action_uses_level(hand + chosen + last_play, level) and (website_actions != local_actions or not local_chosen_valid):
                wild_card_issue += 1
                disagreement_types["level_card_logic_disagree"] += 1
                if len(wild_examples) < 10:
                    wild_examples.append(
                        {
                            "game_id": str(record.get("game_id")),
                            "turn": decision.get("turn"),
                            "level": level,
                            "hand_before": hand,
                            "last_play": last_play,
                            "chosen_action": chosen,
                        }
                    )
            if (website_actions != local_actions or not local_chosen_valid or action_counter_in_hand(chosen, hand) is False) and len(concrete) < 80:
                website_only = sorted(website_actions - local_actions)[:10]
                local_only = sorted(local_actions - website_actions)[:10]
                concrete.append(
                    {
                        "type": "decision_rule_disagreement",
                        "game_id": str(record.get("game_id")),
                        "turn": decision.get("turn"),
                        "level": level,
                        "was_lead": was_lead,
                        "was_follow": was_follow,
                        "hand_before": hand,
                        "last_play_before_action": last_play,
                        "chosen_action": chosen,
                        "chosen_action_in_hand": action_counter_in_hand(chosen, hand),
                        "chosen_action_local_legal": local_chosen_valid,
                        "website_legal_action_count": len(website_actions),
                        "local_legal_action_count": len(local_actions),
                        "website_only_sample": [list(item) for item in website_only],
                        "local_only_sample": [list(item) for item in local_only],
                        "local_mask_combo_disagree_action_ids": local_meta.get("disagree_ids"),
                    }
                )

    disagreement_rate = legal_disagree / evaluated_decisions if evaluated_decisions else 0.0
    rule_compatible = bool(
        chosen_invalid == 0
        and action_not_in_hand == 0
        and bomb_order_issue == 0
        and straight_flush_issue == 0
        and can_beat_disagree <= max(1, int(evaluated_decisions * 0.001))
        and disagreement_rate <= 0.01
        and heart_level_issue == 0
        and wild_card_issue == 0
    )
    result = {
        "profile": profile,
        "record_source": "game_records",
        "detail_source": "logs*/research_game_*.json",
        "legal_action_comparison_scope": "bounded audit: lead uses casebook lead candidates; follow uses pass plus actual chosen_action when website-legal; chosen_action and can_beat checks are exact",
        "missing_log_games": missing_logs,
        "evaluated_games": evaluated_games,
        "evaluated_decisions": evaluated_decisions,
        "chosen_action_valid_count": chosen_valid,
        "chosen_action_invalid_count": chosen_invalid,
        "action_not_in_hand_count": action_not_in_hand,
        "can_beat_agree_count": can_beat_agree,
        "can_beat_disagree_count": can_beat_disagree,
        "legal_action_agree_count": legal_agree,
        "legal_action_disagree_count": legal_disagree,
        "disagreement_rate": disagreement_rate,
        "heart_level_issue_count": heart_level_issue,
        "wild_card_issue_count": wild_card_issue,
        "bomb_order_issue_count": bomb_order_issue,
        "straight_flush_issue_count": straight_flush_issue,
        "pass_rule_issue_count": pass_rule_issue,
        "top_disagreement_types": disagreement_types.most_common(20),
        "top_invalid_reasons": invalid_reasons.most_common(20),
        "top_can_beat_disagree_reasons": can_beat_reasons.most_common(20),
        "top_heart_level_disagree_examples": heart_examples,
        "top_wild_card_disagree_examples": wild_examples,
        "first_50_concrete_disagreements": concrete[:50],
        "concrete_disagreements": concrete,
        "rule_compatible": rule_compatible,
        "allowed_for_selfplay": rule_compatible,
        "allowed_for_website_direct_use": False,
        "website_direct_use_reason": "local model A rules must match website rules before direct use" if not rule_compatible else "rule compatible by offline audit",
    }
    result["allowed_for_website_direct_use"] = bool(rule_compatible)
    save_json(Path(out_path), result)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Research adaptive Guandan client.")
    parser.add_argument("--strategy", choices=("research", "tempo"), default="tempo")
    parser.add_argument("--profile", help="Run one fixed profile from strategy_profiles.json.")
    parser.add_argument("--alternate-profiles", help="Comma-separated profile list to alternate/explore.")
    parser.add_argument("--exploration-rate", type=float, default=0.15)
    parser.add_argument("--min-games-per-scenario-profile", type=int, default=20)
    parser.add_argument("--metric", choices=("elo", "proxy"), default="elo")
    parser.add_argument("--require-elo", action="store_true")
    parser.add_argument("--loop", action="store_true")
    parser.add_argument("--games", type=int, default=1)
    parser.add_argument("--poll", type=float, default=6)
    parser.add_argument("--delay", type=float, default=8)
    parser.add_argument("--error-delay", type=float, default=8)
    parser.add_argument("--timeout", type=float, default=30)
    parser.add_argument("--retries", type=int, default=3)
    parser.add_argument("--log-dir", default=DEFAULT_LOG_DIR)
    parser.add_argument("--probe-rating-fields", action="store_true")
    parser.add_argument("--probe-leaderboard", help="Probe an HTML leaderboard page for the current user's Elo.")
    parser.add_argument("--leaderboard-url", default=DEFAULT_LEADERBOARD_URL)
    parser.add_argument(
        "--website-shadow",
        action="store_true",
        help="Audit website state/actions while frozen tempo_baseline remains the only submitting policy.",
    )
    parser.add_argument("--website-shadow-replay", help="Replay historical website logs for a profile without networking.")
    parser.add_argument("--shadow-replay-out", default="website_shadow_replay.json")
    parser.add_argument("--shadow-replay-max-games", type=int, default=0)
    parser.add_argument("--website-shadow-summary", help="Summarize completed online Shadow logs in a directory.")
    parser.add_argument("--shadow-summary-out", default="website_shadow_summary.json")
    parser.add_argument("--shadow-minimum-games", type=int, default=20)
    parser.add_argument("--summary", help="Print an Elo research summary from research_results.json.")
    parser.add_argument("--recent-window", type=int, default=10)
    parser.add_argument("--loss-drilldown", help="Profile name for recent loss drilldown in summary mode.")
    parser.add_argument("--endgame-audit", help="Profile name for recent loss endgame block audit in summary mode.")
    parser.add_argument("--preloss-trace", help="Profile name for recent loss preloss trace in summary mode.")
    parser.add_argument("--preloss-turns", type=int, default=5)
    parser.add_argument("--decision-dataset", help="Profile name for offline decision dataset export in summary mode.")
    parser.add_argument("--decision-window", type=int, default=5)
    parser.add_argument("--risk-attribution", help="Profile name for offline risk attribution in summary mode.")
    parser.add_argument("--compare-profiles", nargs=2, metavar=("PROFILE_A", "PROFILE_B"))
    parser.add_argument("--loss-casebook", help="Profile name for recent loss casebook in summary mode.")
    parser.add_argument("--case-window", type=int, default=5)
    parser.add_argument("--max-cases", type=int, default=10)
    parser.add_argument("--simulate-casebook-guard", help="Profile name for offline casebook guard simulation in summary mode.")
    parser.add_argument("--simulate-narrow-plate-guard", help="Profile name for offline narrow plate guard simulation in summary mode.")
    parser.add_argument("--export-decision-dataset", help="Profile name for JSONL decision dataset export.")
    parser.add_argument("--dataset-out", help="Output path for --export-decision-dataset.")
    parser.add_argument("--shadow-eval", help="Baseline profile name for offline shadow policy evaluation.")
    parser.add_argument("--shadow-policies", help="Comma-separated policy names for --shadow-eval.")
    parser.add_argument("--shadow-out", help="Output path for --shadow-eval.")
    parser.add_argument("--candidate-gate", help="Run candidate gate on a shadow eval JSON file.")
    parser.add_argument("--website-rule-consistency", help="Profile name for offline website/local rule consistency audit.")
    parser.add_argument("--consistency-out", help="Output path for --website-rule-consistency.")
    parser.add_argument("--offline-arena-eval", action="store_true")
    parser.add_argument("--candidate-actors", help="Comma-separated actor checkpoint paths for --offline-arena-eval.")
    parser.add_argument("--baseline-profile", default="tempo_baseline")
    parser.add_argument("--arena-games", type=int, default=200)
    parser.add_argument("--arena-out", default="arena_eval_modelA_vs_baseline.json")
    parser.add_argument("--swap-seats", action="store_true")
    parser.add_argument("--rule-assisted-guard", action="store_true")
    parser.add_argument("--guard-opponent-hand-threshold", type=int, default=5)
    parser.add_argument("--guard-critical-hand-threshold", type=int, default=3)
    parser.add_argument("--guard-allow-minimal-bomb", action="store_true")
    parser.add_argument("--arena-loss-diagnosis", action="store_true")
    parser.add_argument("--diagnosis-candidate-actor")
    parser.add_argument("--diagnosis-baseline-profile", default="tempo_baseline")
    parser.add_argument("--diagnosis-games", type=int, default=20)
    parser.add_argument("--diagnosis-out", default="arena_loss_diagnosis.json")
    parser.add_argument("--diagnosis-save-casebook", default="arena_loss_casebook.json")
    parser.add_argument("--offline-env-sanity-check", action="store_true")
    parser.add_argument("--sanity-games", type=int, default=20)
    parser.add_argument("--sanity-out", default="offline_env_sanity.json")
    parser.add_argument("--fix-heart-level-action-filter", action="store_true")
    parser.add_argument("--shared-selfplay-train", action="store_true")
    parser.add_argument("--device", choices=("cpu", "cuda"), default="cpu")
    parser.add_argument("--episodes", type=int, default=10)
    parser.add_argument("--model-out-dir", default="models_shared_selfplay_test")
    parser.add_argument("--selfplay-log-out", default="shared_selfplay_test.json")
    parser.add_argument("--save-every", type=int, default=10)
    parser.add_argument("--eval-every", type=int, default=10)
    parser.add_argument("--max-illegal-rate", type=float, default=0.05)
    parser.add_argument("--max-fallback-rate", type=float, default=0.10)
    parser.add_argument("--ppo-curriculum-train", action="store_true")
    parser.add_argument("--ppo-out-dir", default="models_ppo_smoke")
    parser.add_argument("--ppo-log-out", default="ppo_smoke.json")
    parser.add_argument("--ppo-episodes", type=int, default=200)
    parser.add_argument("--ppo-save-every", type=int, default=100)
    parser.add_argument("--ppo-lr", type=float, default=0.00003)
    parser.add_argument("--ppo-gamma", type=float, default=0.99)
    parser.add_argument("--ppo-lambda", type=float, default=0.95)
    parser.add_argument("--ppo-clip", type=float, default=0.1)
    parser.add_argument("--ppo-entropy-coef", type=float, default=0.003)
    parser.add_argument("--ppo-value-coef", type=float, default=0.5)
    parser.add_argument("--ppo-batch-size", type=int, default=512)
    parser.add_argument("--ppo-update-epochs", type=int, default=4)
    parser.add_argument("--ppo-safe-mode", action="store_true")
    parser.add_argument("--ppo-kl-to-init-coef", type=float, default=0.0)
    parser.add_argument("--ppo-target-kl", type=float, default=0.01)
    parser.add_argument("--ppo-early-stop-kl", action="store_true")
    parser.add_argument("--ppo-reward-shaping", action="store_true")
    parser.add_argument("--ppo-hand-delta-reward", type=float, default=0.005)
    parser.add_argument("--ppo-win-reward", type=float, default=1.0)
    parser.add_argument("--ppo-loss-reward", type=float, default=-1.0)
    parser.add_argument("--ppo-eval-every", type=int, default=0)
    parser.add_argument("--ppo-eval-games", type=int, default=5)
    parser.add_argument("--ppo-keep-best-by-arena", action="store_true")
    parser.add_argument("--generate-imitation-dataset", action="store_true")
    parser.add_argument("--teacher-profile", default="tempo_baseline")
    parser.add_argument("--target-teacher-decisions", type=int, default=5000)
    parser.add_argument("--imitation-dataset-out", default="imitation_dataset_baseline_smoke.jsonl")
    parser.add_argument("--max-teacher-mapping-fail-rate", type=float, default=0.01)
    parser.add_argument("--build-corrective-dataset", action="store_true")
    parser.add_argument("--corrective-casebooks")
    parser.add_argument("--base-imitation-dataset")
    parser.add_argument("--corrective-dataset-out", default="corrective_dataset_casebook_50k.pth")
    parser.add_argument("--casebook-oversample-factor", type=int, default=8)
    parser.add_argument("--include-reason-tags", default="")
    parser.add_argument("--train-corrective-bc", action="store_true")
    parser.add_argument("--corrective-dataset")
    parser.add_argument("--corrective-out-dir", default="models_corrective_casebook")
    parser.add_argument("--corrective-log-out", default="corrective_train.json")
    parser.add_argument("--corrective-epochs", type=int, default=10)
    parser.add_argument("--casebook-loss-weight", type=float, default=3.0)
    parser.add_argument("--casebook-rollout-eval", action="store_true")
    parser.add_argument("--rollout-casebook")
    parser.add_argument("--rollout-actor")
    parser.add_argument("--rollout-baseline-profile", default="tempo_baseline")
    parser.add_argument("--rollout-out", default="rollout_eval_casebook.json")
    parser.add_argument("--rollout-max-cases", type=int, default=100)
    parser.add_argument("--rollout-top-k-actions", type=int, default=6)
    parser.add_argument("--rollout-simulations-per-action", type=int, default=8)
    parser.add_argument("--rollout-depth-turns", type=int, default=30)
    parser.add_argument("--rollout-opponent-profile", default="tempo_baseline")
    parser.add_argument("--rollout-teammate-profile", default="tempo_baseline")
    parser.add_argument("--rollout-device", choices=("cpu", "cuda"))
    parser.add_argument("--rollout-fast-mode", action="store_true")
    parser.add_argument("--rollout-coarse-eval", action="store_true")
    parser.add_argument("--rollout-coarse-top-m", type=int, default=3)
    parser.add_argument("--rollout-final-top-m", type=int, default=2)
    parser.add_argument("--rollout-use-heuristic-value", action="store_true")
    parser.add_argument("--rollout-fast-opponent-profile", default="greedy_bot")
    parser.add_argument("--rollout-fast-teammate-profile", default="greedy_bot")
    parser.add_argument("--rollout-exact-verify-top-m", type=int, default=0)
    parser.add_argument("--rollout-max-seconds-per-case", type=float, default=0.0)
    parser.add_argument("--rollout-only-reason-tags", default="")
    parser.add_argument("--rollout-cache-baseline-actions", action="store_true")
    parser.add_argument("--rollout-cache-legal-options", action="store_true")
    parser.add_argument("--build-rollout-teacher-dataset", action="store_true")
    parser.add_argument("--rollout-eval")
    parser.add_argument("--rollout-dataset-out", default="rollout_teacher_dataset.pth")
    parser.add_argument("--rollout-label-weight", type=float, default=3.0)
    parser.add_argument("--rollout-min-improvement", type=float, default=0.15)
    parser.add_argument("--train-rollout-distill", action="store_true")
    parser.add_argument("--train-rollout-distill-focused", action="store_true")
    parser.add_argument("--rollout-dataset")
    parser.add_argument("--rollout-distill-out-dir", default="models_rollout_distill")
    parser.add_argument("--rollout-distill-log-out", default="rollout_distill_train.json")
    parser.add_argument("--rollout-distill-epochs", type=int, default=10)
    parser.add_argument("--rollout-sample-ratio", type=float, default=0.5)
    parser.add_argument("--rollout-oversample-factor", type=int, default=200)
    parser.add_argument("--base-sample-ratio", type=float, default=1.0)
    parser.add_argument("--rollout-only-warmup-epochs", type=int, default=4)
    parser.add_argument("--rollout-loss-weight", type=float, default=20.0)
    parser.add_argument("--preserve-base-loss-weight", type=float, default=1.0)
    parser.add_argument("--best-by-rollout-metric", action="store_true")
    parser.add_argument("--min-base-val-accuracy", type=float, default=0.82)
    parser.add_argument("--eval-rollout-train-accuracy", action="store_true")
    parser.add_argument("--eval-rollout-val-accuracy", action="store_true")
    parser.add_argument("--save-best-rollout-checkpoint", action="store_true")
    parser.add_argument("--build-dmc-action-value-dataset", action="store_true")
    parser.add_argument("--generate-dmc-selfplay-dataset", action="store_true")
    parser.add_argument("--dmc-source-dataset")
    parser.add_argument("--dmc-dataset-out", default="dmc_action_value_dataset.pth")
    parser.add_argument("--dmc-max-samples", type=int, default=0)
    parser.add_argument("--dmc-rollout-label-weight", type=float, default=8.0)
    parser.add_argument("--dmc-target-samples", type=int, default=10000)
    parser.add_argument("--dmc-selfplay-workers", type=int, default=0)
    parser.add_argument("--dmc-candidate-snapshot-limit", type=int, default=DMC_SELFPLAY_CANDIDATE_SNAPSHOT_LIMIT)
    parser.add_argument("--dmc-max-pass-ratio", type=float, default=1.0)
    parser.add_argument("--train-dmc-action-value", action="store_true")
    parser.add_argument("--build-dmc-pairwise-dataset", action="store_true")
    parser.add_argument("--train-dmc-pairwise", action="store_true")
    parser.add_argument("--dmc-dataset")
    parser.add_argument("--dmc-out-dir", default="models_dmc_action_value")
    parser.add_argument("--dmc-log-out", default="dmc_action_value_train.json")
    parser.add_argument("--dmc-epochs", type=int, default=10)
    parser.add_argument("--dmc-save-every", type=int, default=1)
    parser.add_argument("--dmc-balanced-training", action="store_true")
    parser.add_argument("--dmc-non-pass-weight", type=float, default=2.0)
    parser.add_argument("--dmc-follow-weight", type=float, default=1.5)
    parser.add_argument("--dmc-endgame-weight", type=float, default=2.0)
    parser.add_argument("--dmc-bomb-weight", type=float, default=2.0)
    parser.add_argument("--dmc-pass-weight", type=float, default=0.5)
    parser.add_argument("--danzero-dmc-train", action="store_true")
    parser.add_argument("--danzero-games", type=int, default=1000)
    parser.add_argument("--danzero-actors", type=int, default=4)
    parser.add_argument("--danzero-out-dir", default="models_danzero_dmc")
    parser.add_argument("--danzero-log-out", default="danzero_dmc_training.json")
    parser.add_argument("--danzero-save-every", type=int, default=200)
    parser.add_argument("--danzero-learning-rate", type=float, default=0.0001)
    parser.add_argument("--danzero-batch-size", type=int, default=512)
    parser.add_argument("--danzero-updates-per-game", type=int, default=1)
    parser.add_argument("--danzero-replay-capacity", type=int, default=100000)
    parser.add_argument("--danzero-sync-every-updates", type=int, default=20)
    parser.add_argument("--danzero-max-version-lag", type=int, default=200)
    parser.add_argument("--danzero-epsilon-start", type=float, default=0.20)
    parser.add_argument("--danzero-epsilon-end", type=float, default=0.05)
    parser.add_argument("--danzero-epsilon-decay-games", type=int, default=100000)
    parser.add_argument("--danzero-max-steps", type=int, default=OFFLINE_MAX_GAME_STEPS)
    parser.add_argument("--danzero-seed", type=int, default=20260712)
    parser.add_argument("--danzero-resume")
    parser.add_argument("--dmc-calibration-source")
    parser.add_argument("--dmc-pairwise-dataset-out", default="dmc_pairwise_dataset.pth")
    parser.add_argument("--dmc-pairwise-min-win-delta", type=float, default=0.0)
    parser.add_argument("--dmc-pairwise-min-rank-delta", type=float, default=0.25)
    parser.add_argument("--dmc-pairwise-max-pairs-per-state", type=int, default=20)
    parser.add_argument("--dmc-pairwise-dataset")
    parser.add_argument("--init-dmc-model")
    parser.add_argument("--dmc-pairwise-out-dir", default="models_dmc_pairwise")
    parser.add_argument("--dmc-pairwise-log-out", default="dmc_pairwise_train.json")
    parser.add_argument("--dmc-pairwise-epochs", type=int, default=10)
    parser.add_argument("--dmc-pairwise-lr", type=float, default=0.00001)
    parser.add_argument("--dmc-pairwise-margin", type=float, default=0.10)
    parser.add_argument("--dmc-pairwise-anchor-weight", type=float, default=0.25)
    parser.add_argument("--dmc-pairwise-save-every", type=int, default=1)
    parser.add_argument("--dmc-pairwise-seed", type=int, default=20260711)
    parser.add_argument("--offline-dmc-arena-eval", action="store_true")
    parser.add_argument("--offline-dmc-hybrid-arena-eval", action="store_true")
    parser.add_argument("--offline-hybrid-paired-audit", action="store_true")
    parser.add_argument("--offline-dmc-q-calibration-audit", action="store_true")
    parser.add_argument("--dmc-model")
    parser.add_argument("--hybrid-q-margin", type=float, default=0.25)
    parser.add_argument("--hybrid-max-override-rate", type=float, default=0.05)
    parser.add_argument("--hybrid-only-follow", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--hybrid-only-endgame", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--hybrid-forbid-pass-over-non-pass", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--hybrid-block-only-when-opponent-le", type=int, default=6)
    parser.add_argument("--hybrid-non-pass-margin", type=float, default=0.35)
    parser.add_argument("--hybrid-avoid-bomb-unless-opponent-le", type=int, default=3)
    parser.add_argument("--hybrid-control-pass-margin", type=float, default=0.30)
    parser.add_argument("--simulate-hybrid-override-whitelist", action="store_true")
    parser.add_argument("--paired-audit-source")
    parser.add_argument("--paired-audit-out", default="paired_hybrid_audit.json")
    parser.add_argument("--paired-target-states", type=int, default=30)
    parser.add_argument("--paired-min-states-for-gate", type=int, default=30)
    parser.add_argument("--paired-max-games", type=int, default=1000)
    parser.add_argument("--paired-source-overrides-only", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--paired-rollouts-per-state", type=int, default=1)
    parser.add_argument("--paired-depth-turns", type=int, default=0)
    parser.add_argument("--paired-continuation-profile", choices=("tempo_baseline", "greedy_bot"), default="tempo_baseline")
    parser.add_argument("--paired-min-win-delta", type=float, default=0.05)
    parser.add_argument("--paired-seed", type=int, default=20260708)
    parser.add_argument("--paired-equivalence-samples", type=int, default=200)
    parser.add_argument("--dmc-calibration-out", default="dmc_q_calibration_audit.json")
    parser.add_argument("--dmc-calibration-states", type=int, default=30)
    parser.add_argument("--dmc-calibration-max-games", type=int, default=100)
    parser.add_argument("--dmc-calibration-top-k", type=int, default=3)
    parser.add_argument("--dmc-calibration-rollouts-per-action", type=int, default=1)
    parser.add_argument("--dmc-calibration-depth-turns", type=int, default=1200)
    parser.add_argument(
        "--dmc-calibration-continuation-profile",
        choices=("tempo_baseline", "greedy_bot"),
        default="greedy_bot",
    )
    parser.add_argument("--dmc-calibration-min-q-margin", type=float, default=0.0)
    parser.add_argument("--dmc-calibration-seed", type=int, default=20260711)
    parser.add_argument("--dmc-calibration-equivalence-samples", type=int, default=200)
    parser.add_argument("--train-from-imitation-dataset")
    parser.add_argument("--imitation-out-dir", default="models_imitation_baseline_smoke")
    parser.add_argument("--imitation-log-out", default="imitation_train_smoke.json")
    parser.add_argument("--init-actor")
    parser.add_argument("--imitation-epochs", type=int, default=3)
    parser.add_argument("--batch-size", type=int, default=256)
    parser.add_argument("--learning-rate", type=float, default=0.0003)
    parser.add_argument("--save-every-epoch", type=int, default=1)
    parser.add_argument("--validation-split", type=float, default=0.1)
    parser.add_argument("--early-stop-patience", type=int, default=0)
    parser.add_argument("--min-delta", type=float, default=0.0)
    parser.add_argument("--balanced-imitation", action="store_true")
    parser.add_argument("--non-pass-weight", type=float, default=2.0)
    parser.add_argument("--lead-weight", type=float, default=1.5)
    parser.add_argument("--bomb-weight", type=float, default=2.0)
    parser.add_argument("--action-type-balanced-sampler", action="store_true")
    parser.add_argument("--max-pass-sample-ratio", type=float, default=0.40)
    parser.add_argument("--report-detailed-imitation-metrics", action="store_true")
    parser.add_argument("--recent-loss-window", type=int, default=20)
    parser.add_argument("--report-every", type=int, default=10)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.website_shadow_replay:
        result = live_shadow.replay_historical_logs(
            args.website_shadow_replay,
            args.shadow_replay_out,
            args.shadow_replay_max_games,
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return
    if args.website_shadow_summary:
        result = live_shadow.summarize_shadow_log_dir(
            args.website_shadow_summary,
            args.shadow_summary_out,
            args.shadow_minimum_games,
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return
    if args.offline_env_sanity_check:
        run_offline_env_sanity_check(args)
        return
    if args.shared_selfplay_train:
        run_shared_selfplay_train(args)
        return
    if args.ppo_curriculum_train:
        run_ppo_curriculum_train(args)
        return
    if args.generate_imitation_dataset:
        run_generate_imitation_dataset(args)
        return
    if args.build_corrective_dataset:
        if not args.corrective_casebooks or not args.base_imitation_dataset:
            raise RuntimeError("--corrective-casebooks and --base-imitation-dataset are required")
        run_build_corrective_dataset(args)
        return
    if args.train_corrective_bc:
        if not args.corrective_dataset or not args.init_actor:
            raise RuntimeError("--corrective-dataset and --init-actor are required with --train-corrective-bc")
        run_train_corrective_bc(args)
        return
    if args.casebook_rollout_eval:
        if not args.rollout_casebook or not args.rollout_actor:
            raise RuntimeError("--rollout-casebook and --rollout-actor are required with --casebook-rollout-eval")
        run_casebook_rollout_eval(args)
        return
    if args.build_rollout_teacher_dataset:
        if not args.rollout_eval or not args.base_imitation_dataset:
            raise RuntimeError("--rollout-eval and --base-imitation-dataset are required")
        run_build_rollout_teacher_dataset(args)
        return
    if args.train_rollout_distill:
        if not args.rollout_dataset or not args.init_actor:
            raise RuntimeError("--rollout-dataset and --init-actor are required with --train-rollout-distill")
        run_train_rollout_distill(args)
        return
    if args.train_rollout_distill_focused:
        if not args.rollout_dataset or not args.init_actor:
            raise RuntimeError("--rollout-dataset and --init-actor are required with --train-rollout-distill-focused")
        run_train_rollout_distill_focused(args)
        return
    if args.build_dmc_action_value_dataset:
        if not args.dmc_source_dataset:
            raise RuntimeError("--dmc-source-dataset is required with --build-dmc-action-value-dataset")
        run_build_dmc_action_value_dataset(args)
        return
    if args.generate_dmc_selfplay_dataset:
        run_generate_dmc_selfplay_dataset(args)
        return
    if args.danzero_dmc_train:
        import danzero_dmc

        danzero_dmc.run_distributed_dmc(args)
        return
    if args.train_dmc_action_value:
        if not args.dmc_dataset:
            raise RuntimeError("--dmc-dataset is required with --train-dmc-action-value")
        run_train_dmc_action_value(args)
        return
    if args.build_dmc_pairwise_dataset:
        if not args.dmc_calibration_source:
            raise RuntimeError("--dmc-calibration-source is required with --build-dmc-pairwise-dataset")
        run_build_dmc_pairwise_dataset(args)
        return
    if args.train_dmc_pairwise:
        if not args.dmc_pairwise_dataset or not args.init_dmc_model:
            raise RuntimeError("--dmc-pairwise-dataset and --init-dmc-model are required with --train-dmc-pairwise")
        run_train_dmc_pairwise(args)
        return
    if args.offline_dmc_arena_eval:
        if not args.dmc_model:
            raise RuntimeError("--dmc-model is required with --offline-dmc-arena-eval")
        run_offline_dmc_arena_eval(args)
        return
    if args.offline_dmc_hybrid_arena_eval:
        if not args.dmc_model:
            raise RuntimeError("--dmc-model is required with --offline-dmc-hybrid-arena-eval")
        run_offline_dmc_hybrid_arena_eval(args)
        return
    if args.offline_hybrid_paired_audit:
        run_offline_hybrid_paired_audit(args)
        return
    if args.offline_dmc_q_calibration_audit:
        if not args.dmc_model:
            raise RuntimeError("--dmc-model is required with --offline-dmc-q-calibration-audit")
        run_offline_dmc_q_calibration_audit(args)
        return
    if args.train_from_imitation_dataset:
        run_train_from_imitation_dataset(args)
        return
    if args.export_decision_dataset:
        if not args.dataset_out:
            raise RuntimeError("--dataset-out is required with --export-decision-dataset")
        export_decision_dataset(args.export_decision_dataset, args.dataset_out)
        return
    if args.shadow_eval:
        if not args.shadow_policies or not args.shadow_out:
            raise RuntimeError("--shadow-policies and --shadow-out are required with --shadow-eval")
        shadow_eval(args.shadow_eval, args.shadow_policies, args.shadow_out)
        return
    if args.candidate_gate:
        candidate_gate(args.candidate_gate)
        return
    if args.website_rule_consistency:
        if not args.consistency_out:
            raise RuntimeError("--consistency-out is required with --website-rule-consistency")
        run_website_rule_consistency(args.website_rule_consistency, args.consistency_out)
        return
    if args.offline_arena_eval:
        run_offline_arena_eval(args)
        return
    if args.arena_loss_diagnosis:
        if not args.diagnosis_candidate_actor:
            raise RuntimeError("--diagnosis-candidate-actor is required with --arena-loss-diagnosis")
        run_arena_loss_diagnosis(args)
        return
    if args.summary:
        run_summary(
            args.summary,
            args.recent_window,
            args.loss_drilldown,
            args.recent_loss_window,
            args.endgame_audit,
            args.preloss_trace,
            args.preloss_turns,
            args.decision_dataset,
            args.decision_window,
            args.risk_attribution,
            args.compare_profiles,
            args.loss_casebook,
            args.case_window,
            args.max_cases,
            args.simulate_casebook_guard,
            args.simulate_narrow_plate_guard,
        )
        return
    if args.probe_leaderboard:
        require_env(require_password=False)
        results = load_json(RESULTS_PATH, {"version": 1, "scenario_profiles": {}, "global_profile_stats": {}})
        run_leaderboard_probe(args, results)
        return
    require_env()
    if args.website_shadow:
        if args.profile not in {None, "tempo_baseline"} or args.alternate_profiles:
            raise RuntimeError("--website-shadow only permits the frozen tempo_baseline submission policy")
        args.strategy = "tempo"
        args.profile = "tempo_baseline"
        print(
            "website_shadow=true submission_policy=tempo_baseline "
            "suggestion_source=tempo_baseline_mirror model_controlled_actions=0"
        )
    if args.metric == "elo":
        args.require_elo = True
    engine.HTTP_TIMEOUT_SECONDS = args.timeout
    engine.HTTP_RETRIES = max(1, args.retries)
    profiles = load_json(PROFILE_PATH, {})
    if not profiles:
        raise RuntimeError("strategy_profiles.json is missing or empty")
    requested_profiles = []
    if args.profile:
        requested_profiles.append(args.profile)
    requested_profiles.extend(name.strip() for name in (args.alternate_profiles or "").split(",") if name.strip())
    missing_profiles = [name for name in requested_profiles if name not in profiles]
    if missing_profiles:
        raise RuntimeError(f"unknown strategy profile(s): {', '.join(missing_profiles)}")
    results = load_json(RESULTS_PATH, {"version": 1, "scenario_profiles": {}, "global_profile_stats": {}})
    memory = load_bot_memory()
    if args.probe_rating_fields:
        run_probe(args, profiles, results, memory)
        return
    if not args.profile and not args.alternate_profiles:
        args.profile = DEFAULT_LIVE_PROFILE
    run_loop(args)


if __name__ == "__main__":
    main()
