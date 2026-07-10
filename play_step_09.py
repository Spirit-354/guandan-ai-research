import argparse
import itertools
import json
import os
import socket
import sys
import time
from collections import Counter
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


BASE_URL = "http://183.175.14.145:8003"
USER = os.environ.get("GD_USER") or os.environ.get("USER") or ""
PASSWORD = os.environ.get("GD_PASSWORD") or os.environ.get("PASSWORD") or ""
DEFAULT_POLL_SECONDS = 6
DEFAULT_BETWEEN_GAMES_SECONDS = 8
DEFAULT_HTTP_TIMEOUT_SECONDS = 30
DEFAULT_HTTP_RETRIES = 3
DEFAULT_REWARD_TEAM_FIRST = 1.0
DEFAULT_PENALTY_OPPONENT_FIRST = 2.0
DEFAULT_ALLY_RELIABILITY = 0.65
SELF_CARRY_ALLY_RELIABILITY = 0.35
ABANDON_EXIT_CODE = 42
OPPONENT_IMMINENT_OUT_LIMIT = 2
OPPONENT_CONTROL_OUT_LIMIT = 4

HTTP_TIMEOUT_SECONDS = DEFAULT_HTTP_TIMEOUT_SECONDS
HTTP_RETRIES = DEFAULT_HTTP_RETRIES
STRATEGY_MODE = "tempo"
REWARD_TEAM_FIRST = float(os.environ.get("REWARD_TEAM_FIRST", DEFAULT_REWARD_TEAM_FIRST))
PENALTY_OPPONENT_FIRST = float(os.environ.get("PENALTY_OPPONENT_FIRST", DEFAULT_PENALTY_OPPONENT_FIRST))
RISK_RATIO = PENALTY_OPPONENT_FIRST / max(REWARD_TEAM_FIRST, 0.001)
ALLY_RELIABILITY_EXPLICIT = "ALLY_RELIABILITY" in os.environ
ALLY_RELIABILITY = min(1.0, max(0.0, float(os.environ.get("ALLY_RELIABILITY", DEFAULT_ALLY_RELIABILITY))))

TRANSIENT_ERRORS = (TimeoutError, socket.timeout, URLError)

RSA_E = 65537
RSA_N = int(
    "135261828916791946705313569652794581721330948863485438876915508683244111694485850733278569559191167660149469895899348939039437830613284874764820878002628686548956779897196112828969255650312573935871059275664474562666268163936821302832645284397530568872432109324825205567091066297960733513602409443790146687029"
)

RANKS = list("23456789TJQKA")
SUITS = list("SHDC")
BOMB_TYPES = {"bomb", "straight_flush", "quad_kings"}
NON_BOMB_TYPES = {
    "single",
    "pair",
    "triple",
    "full_house",
    "straight",
    "plate",
    "steel",
}
LEAD_TYPE_SCORE = {
    "steel": 150,
    "plate": 140,
    "full_house": 125,
    "straight": 115,
    "triple": 62,
    "pair": 38,
    "single": 5,
}
PLAN_TYPE_BONUS = {
    "steel": 22,
    "plate": 20,
    "full_house": 18,
    "straight": 14,
    "triple": 7,
    "pair": 5,
    "single": 0,
}
REMAINING_GROUP_WEIGHT = 28
LEAD_BLOCK_BONUS = 18
PROACTIVE_BOMB_HAND_LIMIT = 7
FOLLOW_GAIN_THRESHOLD = 0.45
EXACT_GROUP_HAND_LIMIT = 12


@dataclass(frozen=True)
class PlayInfo:
    type: str
    rank: str
    cards: tuple[str, ...]
    size: int


def remaining_group_weight() -> int:
    return REMAINING_GROUP_WEIGHT


def follow_gain_threshold() -> float:
    return 0.40


def effective_ally_reliability(state: dict | None = None) -> float:
    base = ALLY_RELIABILITY
    if STRATEGY_MODE == "selfcarry" and not ALLY_RELIABILITY_EXPLICIT:
        base = SELF_CARRY_ALLY_RELIABILITY
    if STRATEGY_MODE != "selfcarry":
        base = max(0.5, base)
        if state is not None and ally_obstruction_streak(state) >= 2:
            base = min(base, 0.5)
    return min(1.0, max(0.0, base))


def should_help_ally_shape(hand: list[str], level: str, state: dict | None = None) -> bool:
    reliability = effective_ally_reliability(state)
    if reliability < 0.5:
        return False
    if len(hand) <= 8:
        return False
    threshold = 3.5
    threshold += (1.0 - reliability) * 2.0
    return estimate_remaining_groups(hand, level) > threshold


def configure_credentials(user: str | None, password: str | None) -> None:
    global USER, PASSWORD
    if user is not None:
        USER = user
    if password is not None:
        PASSWORD = password


def configure_scoring(reward_team_first: float | None, penalty_opponent_first: float | None) -> None:
    global REWARD_TEAM_FIRST, PENALTY_OPPONENT_FIRST, RISK_RATIO
    if reward_team_first is not None:
        REWARD_TEAM_FIRST = max(reward_team_first, 0.001)
    if penalty_opponent_first is not None:
        PENALTY_OPPONENT_FIRST = max(penalty_opponent_first, 0.001)
    RISK_RATIO = PENALTY_OPPONENT_FIRST / max(REWARD_TEAM_FIRST, 0.001)


def configure_ally_reliability(value: float | None) -> None:
    global ALLY_RELIABILITY, ALLY_RELIABILITY_EXPLICIT
    if value is not None:
        ALLY_RELIABILITY = min(1.0, max(0.0, value))
        ALLY_RELIABILITY_EXPLICIT = True


def require_credentials() -> None:
    if not USER or not PASSWORD:
        raise RuntimeError(
            "missing credentials: set GD_USER/GD_PASSWORD or USER/PASSWORD, "
            "or pass --user and --password"
        )


def str_to_num(value: str) -> int:
    num = 0
    for byte in value.encode("ascii"):
        num = num * 256 + byte
    return num


def encrypted_password_hex() -> str:
    require_credentials()
    return format(pow(str_to_num(PASSWORD), RSA_E, RSA_N), "x")


def get_json(path: str, params: dict | None = None) -> dict:
    query = "" if not params else "?" + urlencode(params)
    request = Request(BASE_URL + path + query, headers={"User-Agent": "python-game-client/1.0"})
    last_error: Exception | None = None
    for attempt in range(1, HTTP_RETRIES + 1):
        try:
            with urlopen(request, timeout=HTTP_TIMEOUT_SECONDS) as response:
                text = response.read().decode(response.headers.get_content_charset() or "utf-8")
            return json.loads(text)
        except HTTPError:
            raise
        except TRANSIENT_ERRORS as exc:
            last_error = exc
            if attempt >= HTTP_RETRIES:
                break
            sleep_seconds = min(2 * attempt, 8)
            print(f"http_retry attempt={attempt}/{HTTP_RETRIES} path={path} error={type(exc).__name__}")
            time.sleep(sleep_seconds)
    raise TimeoutError(f"request timed out after {HTTP_RETRIES} attempts: {path}") from last_error


def auth_params() -> dict:
    return {"user": USER, "password": encrypted_password_hex()}


def game_rank_order(level: str) -> list[str]:
    return [rank for rank in RANKS if rank != level] + [level, "B", "R"]


def game_rank_index(level: str) -> dict[str, int]:
    return {rank: i for i, rank in enumerate(game_rank_order(level))}


def natural_rank_index() -> dict[str, int]:
    return {rank: i for i, rank in enumerate(RANKS)}


def sort_cards(cards: list[str] | tuple[str, ...], level: str) -> list[str]:
    ranks = game_rank_index(level)
    suits = {"S": 0, "H": 1, "D": 2, "C": 3}

    def key(card: str) -> tuple[int, int]:
        if card == "B":
            return (ranks["B"], 0)
        if card == "R":
            return (ranks["R"], 0)
        return (ranks[card[1]], suits[card[0]])

    return sorted(cards, key=key)


@lru_cache(maxsize=None)
def sequence_windows(length: int) -> tuple[tuple[str, ...], ...]:
    windows: list[list[str]] = []
    low_ace = ["A"] + RANKS[:-1]
    if length <= len(low_ace):
        for start in range(len(low_ace) - length + 1):
            seq = low_ace[start : start + length]
            if seq[0] == "A":
                windows.append(seq)
    for start in range(len(RANKS) - length + 1):
        windows.append(RANKS[start : start + length])

    seen = set()
    unique = []
    for seq in windows:
        key = tuple(seq)
        if key not in seen:
            seen.add(key)
            unique.append(seq)
    return tuple(tuple(seq) for seq in unique)


def add_info(infos: list[PlayInfo], play_type: str, rank: str, cards: tuple[str, ...]) -> None:
    info = PlayInfo(play_type, rank, cards, len(cards))
    if info not in infos:
        infos.append(info)


def split_cards(cards: tuple[str, ...], level: str):
    wild_card = "H" + level
    wild_count = sum(1 for card in cards if card == wild_card)
    normal_cards = [card for card in cards if card != wild_card]
    rank_counts = Counter()
    joker_counts = Counter()
    suited = []

    for card in normal_cards:
        if card in ("B", "R"):
            joker_counts[card] += 1
        else:
            suited.append((card[0], card[1]))
            rank_counts[card[1]] += 1

    return wild_count, rank_counts, joker_counts, suited


def recognize(cards: list[str] | tuple[str, ...], level: str) -> list[PlayInfo]:
    cards_tuple = tuple(sort_cards(cards, level))
    return list(_recognize_cached(cards_tuple, level))


@lru_cache(maxsize=250_000)
def _recognize_cached(cards_tuple: tuple[str, ...], level: str) -> tuple[PlayInfo, ...]:
    n = len(cards_tuple)
    wild, rank_counts, joker_counts, suited = split_cards(cards_tuple, level)
    infos: list[PlayInfo] = []

    if n == 0:
        return tuple(infos)

    if n == 1:
        card = cards_tuple[0]
        if wild == 1:
            for rank in RANKS:
                add_info(infos, "single", rank, cards_tuple)
        else:
            add_info(infos, "single", card if card in ("B", "R") else card[1], cards_tuple)

    for size, play_type in ((2, "pair"), (3, "triple")):
        if n != size:
            continue
        if joker_counts:
            for joker, count in joker_counts.items():
                if count == size and len(joker_counts) == 1 and not rank_counts and wild == 0:
                    add_info(infos, play_type, joker, cards_tuple)
            continue
        for rank in RANKS:
            count = rank_counts.get(rank, 0)
            if count + wild == size and count <= size and all(r == rank for r in rank_counts):
                add_info(infos, play_type, rank, cards_tuple)

    if n == 5:
        for triple_rank in RANKS:
            triple_count = rank_counts.get(triple_rank, 0)
            if triple_count > 3:
                continue
            if joker_counts:
                continue
            for pair_rank in RANKS:
                if pair_rank == triple_rank:
                    continue
                pair_count = rank_counts.get(pair_rank, 0)
                if pair_count > 2:
                    continue

                outside_ok = all(rank in (triple_rank, pair_rank) for rank in rank_counts)
                if not outside_ok:
                    continue

                needed = max(0, 3 - triple_count)
                needed += max(0, 2 - pair_count)
                if needed == wild:
                    add_info(infos, "full_house", triple_rank, cards_tuple)

    if n == 5 and not joker_counts:
        rank_counter = Counter(rank for _, rank in suited)
        for seq in sequence_windows(5):
            if all(rank in seq for rank in rank_counter) and all(count <= 1 for count in rank_counter.values()):
                missing = sum(1 for rank in seq if rank_counter.get(rank, 0) == 0)
                if missing == wild:
                    add_info(infos, "straight", seq[-1], cards_tuple)

        suit_counter = Counter(suit for suit, _ in suited)
        if len(suit_counter) <= 1:
            for seq in sequence_windows(5):
                if all(rank in seq for rank in rank_counter) and all(count <= 1 for count in rank_counter.values()):
                    missing = sum(1 for rank in seq if rank_counter.get(rank, 0) == 0)
                    if missing == wild:
                        add_info(infos, "straight_flush", seq[-1], cards_tuple)

    if n == 6 and not joker_counts:
        for seq in sequence_windows(3):
            if not all(rank in seq for rank in rank_counts):
                continue
            needed = 0
            ok = True
            for rank in seq:
                count = rank_counts.get(rank, 0)
                if count > 2:
                    ok = False
                needed += max(0, 2 - count)
            if ok and needed == wild:
                add_info(infos, "plate", seq[-1], cards_tuple)

        for seq in sequence_windows(2):
            if not all(rank in seq for rank in rank_counts):
                continue
            needed = 0
            ok = True
            for rank in seq:
                count = rank_counts.get(rank, 0)
                if count > 3:
                    ok = False
                needed += max(0, 3 - count)
            if ok and needed == wild:
                add_info(infos, "steel", seq[-1], cards_tuple)

    if n >= 4 and not joker_counts:
        for rank in RANKS:
            count = rank_counts.get(rank, 0)
            if count + wild == n and all(r == rank for r in rank_counts):
                add_info(infos, "bomb", rank, cards_tuple)

    if (
        n == 4
        and wild == 0
        and not rank_counts
        and joker_counts.get("B", 0) == 2
        and joker_counts.get("R", 0) == 2
    ):
        add_info(infos, "quad_kings", "R", cards_tuple)

    return tuple(infos)


def is_bomb(info: PlayInfo) -> bool:
    return info.type in BOMB_TYPES


def rank_value(info: PlayInfo, level: str) -> int:
    if info.type in {"straight", "plate", "steel", "straight_flush"}:
        return natural_rank_index()[info.rank]
    return game_rank_index(level)[info.rank]


def bomb_key(info: PlayInfo, level: str) -> tuple[float, int]:
    if info.type == "quad_kings":
        return (100.0, 0)
    if info.type == "straight_flush":
        return (6.5, rank_value(info, level))
    if info.type == "bomb":
        return (float(info.size), rank_value(info, level))
    raise ValueError(f"not a bomb: {info}")


def info_beats(ours: PlayInfo, theirs: PlayInfo, level: str) -> bool:
    ours_bomb = is_bomb(ours)
    theirs_bomb = is_bomb(theirs)
    if ours_bomb and not theirs_bomb:
        return True
    if not ours_bomb and theirs_bomb:
        return False
    if ours_bomb and theirs_bomb:
        return bomb_key(ours, level) > bomb_key(theirs, level)
    if ours.type != theirs.type or ours.size != theirs.size:
        return False
    return rank_value(ours, level) > rank_value(theirs, level)


def canonical_table_infos(cards: list[str], level: str) -> list[PlayInfo]:
    infos = recognize(cards, level)
    bomb_infos = [info for info in infos if is_bomb(info)]
    if bomb_infos:
        return [max(bomb_infos, key=lambda info: bomb_key(info, level))]

    best: dict[tuple[str, int], PlayInfo] = {}
    for info in infos:
        key = (info.type, info.size)
        current = best.get(key)
        if current is None or rank_value(info, level) > rank_value(current, level):
            best[key] = info
    return list(best.values())


def safe_follow_infos(cards: list[str] | tuple[str, ...], last_play: list[str], level: str) -> list[PlayInfo]:
    last_infos = canonical_table_infos(last_play, level)
    our_canonical = canonical_table_infos(list(cards), level)
    if any(is_bomb(info) for info in our_canonical):
        return [
            ours
            for ours in our_canonical
            if is_bomb(ours) and any(info_beats(ours, theirs, level) for theirs in last_infos)
        ]

    our_infos = [info for info in recognize(cards, level) if not is_bomb(info)]
    our_types = {info.type for info in our_infos}
    # The server appears to use one canonical interpretation for wildcard hands.
    # Ambiguous follow hands such as plate/steel can be rejected even when one
    # interpretation beats the table, so only submit unambiguous non-bombs.
    if len(our_types) != 1:
        return []

    last_non_bombs = [info for info in last_infos if not is_bomb(info)]
    target_types = {(info.type, info.size) for info in last_non_bombs}
    return [
        ours
        for ours in our_infos
        if (ours.type, ours.size) in target_types
        and any(info_beats(ours, theirs, level) for theirs in last_non_bombs)
    ]


def play_beats(cards: list[str], last_play: list[str], level: str) -> bool:
    if not last_play:
        return bool(recognize(cards, level))
    return bool(safe_follow_infos(cards, last_play, level))


def server_treats_as_bomb(cards: list[str] | tuple[str, ...], level: str) -> bool:
    return any(is_bomb(info) for info in canonical_table_infos(list(cards), level))


def relation_to_last(state: dict) -> str | None:
    last_player = state.get("last_player")
    if last_player is None:
        return None
    try:
        return "teammate" if state["teams"][str(last_player)] == state["your_team"] else "opponent"
    except (KeyError, TypeError):
        return "teammate" if int(last_player) % 2 == int(state["your_seat"]) % 2 else "opponent"


def choose_all_out_if_possible(hand: list[str], last_play: list[str], level: str) -> list[str] | None:
    if not recognize(hand, level):
        return None
    if not last_play or play_beats(hand, last_play, level):
        return sort_cards(hand, level)
    return None


def remove_cards(hand: list[str], cards: list[str] | tuple[str, ...]) -> list[str]:
    remaining = Counter(hand)
    for card in cards:
        remaining[card] -= 1
        if remaining[card] < 0:
            raise ValueError(f"card {card} is not in hand {hand}")

    result = []
    for card in hand:
        if remaining[card] > 0:
            result.append(card)
            remaining[card] -= 1
    return result


def card_cost(cards: list[str] | tuple[str, ...], level: str) -> tuple[int, int, int, list[str]]:
    wild_card = "H" + level
    ranks = game_rank_index(level)
    wild_count = sum(1 for card in cards if card == wild_card)
    king_count = sum(1 for card in cards if card in ("B", "R"))
    rank_sum = 0
    for card in cards:
        if card in ("B", "R"):
            rank_sum += ranks[card]
        else:
            rank_sum += ranks[card[1]]
    return (wild_count, king_count, rank_sum, sort_cards(list(cards), level))


def level_card_count(cards: list[str] | tuple[str, ...], level: str) -> int:
    return sum(1 for card in cards if card not in ("B", "R") and card[1] == level)


def normal_rank_counts(cards: list[str] | tuple[str, ...], level: str) -> Counter:
    wild_card = "H" + level
    counts = Counter()
    for card in cards:
        if card not in ("B", "R") and card != wild_card:
            counts[card[1]] += 1
    return counts


def structure_cost(cards: list[str] | tuple[str, ...], hand: list[str], level: str) -> int:
    before = normal_rank_counts(hand, level)
    used = normal_rank_counts(cards, level)
    wild_card = "H" + level
    cost = 0

    for rank, used_count in used.items():
        before_count = before[rank]
        left = before_count - used_count
        if before_count >= 4 and left:
            cost += 35
        elif before_count >= 3 and left in (1, 2):
            cost += 24
        elif before_count == 2 and left == 1:
            cost += 28

    cost += sum(1 for card in cards if card == wild_card) * 70
    cost += level_card_count(cards, level) * 18
    cost += sum(1 for card in cards if card in ("B", "R")) * 36
    return cost


def estimate_remaining_groups(hand: list[str], level: str) -> float:
    if len(hand) <= EXACT_GROUP_HAND_LIMIT:
        return float(exact_remaining_groups(tuple(sort_cards(hand, level)), level))

    counts = normal_rank_counts(hand, level)
    wild_card = "H" + level
    wilds = sum(1 for card in hand if card == wild_card)
    jokers = sum(1 for card in hand if card in ("B", "R"))
    groups = 0

    # Treat large same-rank groups as one future bomb and avoid breaking them in the estimate.
    for rank in RANKS:
        if counts[rank] >= 4:
            groups += 1
            counts[rank] = 0

    for seq_len, need_each in ((2, 3), (3, 2), (5, 1)):
        changed = True
        while changed:
            changed = False
            best_seq = None
            for seq in sequence_windows(seq_len):
                if all(counts[rank] >= need_each for rank in seq):
                    best_seq = seq
                    break
            if best_seq:
                for rank in best_seq:
                    counts[rank] -= need_each
                groups += 1
                changed = True

    triples = []
    pairs = []
    singles = 0
    for rank in RANKS:
        while counts[rank] >= 3:
            triples.append(rank)
            counts[rank] -= 3
        while counts[rank] >= 2:
            pairs.append(rank)
            counts[rank] -= 2
        singles += counts[rank]

    full_house_count = min(len(triples), len(pairs))
    groups += full_house_count
    triples = triples[full_house_count:]
    pairs = pairs[full_house_count:]
    groups += len(triples) + len(pairs) + singles

    # Wildcards and kings are strong residual cards; count them as partial groups so preserving them is rewarded.
    groups += jokers * 0.65 + wilds * 0.45
    return groups


@lru_cache(maxsize=100_000)
def exact_remaining_groups(hand_key: tuple[str, ...], level: str) -> int:
    hand = list(hand_key)
    if not hand:
        return 0
    if recognize(hand, level):
        return 1

    fallback = len(hand)
    if len(hand) > EXACT_GROUP_HAND_LIMIT:
        return fallback

    unique_plays = {info.cards for info in legal_play_options(hand, level)}
    best = fallback
    for cards in sorted(unique_plays, key=lambda item: (-len(item), card_cost(item, level))):
        if len(cards) >= len(hand):
            continue
        remaining = tuple(sort_cards(remove_cards(hand, cards), level))
        best = min(best, 1 + exact_remaining_groups(remaining, level))
        if best <= 2:
            break
    return best


def teammate_seat(state: dict) -> int:
    return (int(state["your_seat"]) + 2) % 4


def teammate_count(state: dict) -> int | None:
    counts = state.get("hand_counts") or []
    try:
        return counts[teammate_seat(state)]
    except (IndexError, TypeError):
        return None


def ally_obstruction_streak(state: dict) -> int:
    history = state.get("trick_history") or []
    try:
        your_seat = int(state["your_seat"])
        ally_seat = teammate_seat(state)
    except (KeyError, TypeError, ValueError):
        return 0

    streak = 0
    for index in range(len(history) - 1, 0, -1):
        try:
            current_seat, current_cards = history[index]
            previous_seat, previous_cards = history[index - 1]
        except (TypeError, ValueError):
            continue
        if (
            int(current_seat) == ally_seat
            and current_cards
            and int(previous_seat) == your_seat
            and previous_cards
        ):
            streak += 1
            continue
        if streak:
            break
    return streak


def team_min_count(state: dict) -> int:
    counts = [len(state.get("your_hand") or [])]
    ally_count = teammate_count(state)
    if ally_count is not None:
        counts.append(ally_count)
    return min(counts)


def best_group_reduction_potential(hand: list[str], level: str) -> float:
    if not hand or len(hand) > 14:
        return 0.0
    current = estimate_remaining_groups(hand, level)
    best = 0.0
    for info in legal_non_bomb_options(hand, level):
        remaining = remove_cards(hand, info.cards)
        best = max(best, current - estimate_remaining_groups(remaining, level))
    return best


def hand_has_bomb(hand: list[str], level: str) -> bool:
    return bool(legal_bomb_options(hand, level))


def bomb_near_finish_potential(hand: list[str], level: str) -> bool:
    if not hand:
        return False
    for bomb in legal_bomb_options(hand, level):
        remaining = remove_cards(hand, bomb.cards)
        if len(remaining) <= 6 or estimate_remaining_groups(remaining, level) <= 2.0:
            return True
    return False


def self_sprint_score(state: dict) -> float:
    hand = state.get("your_hand") or []
    level = state.get("level")
    if not level:
        return 0.0
    if not hand:
        return 100.0

    groups = estimate_remaining_groups(hand, level)
    score = max(0.0, 72.0 - len(hand) * 1.8 - groups * 12.0)
    if recognize(hand, level):
        score = max(score, 96.0)
    elif groups <= 2.0:
        score += 30.0
    elif groups <= 2.5:
        score += 20.0
    elif groups <= 3.0:
        score += 10.0

    if not (state.get("last_play") or []):
        score += 14.0
    elif relation_to_last(state) == "opponent":
        score -= 4.0

    if hand_has_bomb(hand, level):
        score += 8.0
        if bomb_near_finish_potential(hand, level):
            score += 14.0
    score += sum(1 for card in hand if card == "R") * 5.0
    score += sum(1 for card in hand if card == "B") * 3.5
    score += sum(1 for card in hand if card == "H" + level) * 5.0
    score += min(12.0, best_group_reduction_potential(hand, level) * 5.0)
    return min(110.0, score)


def raw_ally_sprint_score(state: dict) -> float:
    ally_count = teammate_count(state)
    if ally_count is None:
        return 0.0
    if ally_count <= 0:
        return 100.0
    if ally_count == 1:
        score = 88.0
    elif ally_count == 2:
        score = 76.0
    elif ally_count == 3:
        score = 60.0
    elif ally_count == 4:
        score = 46.0
    elif ally_count <= 6:
        score = 32.0
    else:
        score = max(0.0, 28.0 - (ally_count - 6) * 1.5)

    relation = relation_to_last(state)
    if relation == "teammate":
        score += 10.0
    elif not (state.get("last_play") or []):
        score += 4.0
    return min(100.0, score)


def ally_sprint_score(state: dict) -> float:
    return raw_ally_sprint_score(state) * effective_ally_reliability(state)


def self_carry_mode(state: dict) -> bool:
    hand = state.get("your_hand") or []
    level = state.get("level")
    if not level:
        return False

    groups = estimate_remaining_groups(hand, level)
    if STRATEGY_MODE == "tempo":
        return False
    if STRATEGY_MODE == "balanced":
        return groups <= 2.5 or len(hand) <= 5 or bomb_near_finish_potential(hand, level)

    if groups <= 2.5:
        return True
    if len(hand) <= 6:
        return True
    if bomb_near_finish_potential(hand, level):
        return True
    return effective_ally_reliability(state) < 0.5 and self_sprint_score(state) >= ally_sprint_score(state)


def opponent_hand_counts(state: dict) -> list[int]:
    hand_counts = state.get("hand_counts") or []
    counts = []
    for seat in opponent_seats(state):
        try:
            counts.append(hand_counts[seat])
        except (IndexError, TypeError):
            pass
    return counts


def opponent_may_go_out_next(state: dict) -> bool:
    opponent_min = min_opponent_count(state)
    if opponent_min <= 0:
        return True
    if opponent_min <= 2:
        return True

    last_play = state.get("last_play") or []
    relation = relation_to_last(state)
    if relation == "opponent" and last_player_count(state) <= 6:
        return True
    if last_play and len(last_play) == opponent_min and opponent_min <= 6:
        return True
    if not last_play and opponent_min <= 6:
        return True
    return False


def opponent_head_threat_score(state: dict) -> float:
    opponent_min = min_opponent_count(state)
    if opponent_min <= 0:
        base = 100.0
    elif opponent_min == 1:
        base = 78.0
    elif opponent_min == 2:
        base = 62.0
    elif opponent_min == 3:
        base = 44.0
    elif opponent_min == 4:
        base = 34.0
    elif opponent_min <= 6:
        base = 24.0
    else:
        base = max(0.0, 18.0 - opponent_min)

    last_play = state.get("last_play") or []
    relation = relation_to_last(state)
    if relation == "opponent":
        base += 10.0
        if last_player_count(state) <= 6:
            base += 8.0
    if last_play and relation == "opponent":
        base += 7.0
    if opponent_may_go_out_next(state):
        base += 12.0
    if last_play and len(last_play) in {count for count in opponent_hand_counts(state) if 0 < count <= 6}:
        base += 6.0

    return base * max(0.5, min(RISK_RATIO, 4.0))


def team_first_actor(state: dict) -> str:
    return "teammate" if ally_sprint_score(state) > self_sprint_score(state) + 10.0 else "self"


def team_first_chance_score(state: dict) -> float:
    return max(self_sprint_score(state), ally_sprint_score(state))


def candidate_key(
    cards: tuple[str, ...], info: PlayInfo, hand: list[str], level: str
) -> tuple[float, int, int, int, int, tuple[int, int, int, list[str]]]:
    remaining = remove_cards(hand, cards)
    wilds, kings, _, _ = card_cost(cards, level)
    return (
        estimate_remaining_groups(remaining, level),
        structure_cost(cards, hand, level),
        wilds,
        kings,
        rank_value(info, level),
        card_cost(cards, level),
    )


def legal_play_options(hand: list[str], level: str) -> list[PlayInfo]:
    hand_key = tuple(sort_cards(hand, level))
    return list(_legal_play_options_cached(hand_key, level))


@lru_cache(maxsize=4096)
def _legal_play_options_cached(hand_key: tuple[str, ...], level: str) -> tuple[PlayInfo, ...]:
    hand = list(hand_key)
    options: dict[tuple[tuple[str, ...], str, str], PlayInfo] = {}
    brute_sizes = [1, 2, 3, 4, 5, 6]
    for size in brute_sizes:
        if size > len(hand):
            continue
        for combo in itertools.combinations(hand, size):
            cards = tuple(sort_cards(combo, level))
            for info in recognize(cards, level):
                key = (cards, info.type, info.rank)
                options[key] = PlayInfo(info.type, info.rank, cards, len(cards))

    wild_card = "H" + level
    wilds = [card for card in hand if card == wild_card]
    by_rank: dict[str, list[str]] = {rank: [] for rank in RANKS}
    for card in hand:
        if card not in ("B", "R") and card != wild_card:
            by_rank[card[1]].append(card)

    for rank, cards_of_rank in by_rank.items():
        cards_of_rank = sort_cards(cards_of_rank, level)
        max_size = len(cards_of_rank) + len(wilds)
        for size in range(7, max_size + 1):
            need_wild = max(0, size - len(cards_of_rank))
            if need_wild > len(wilds):
                continue
            selected = cards_of_rank[: size - need_wild] + wilds[:need_wild]
            cards = tuple(sort_cards(selected, level))
            key = (cards, "bomb", rank)
            options[key] = PlayInfo("bomb", rank, cards, len(cards))

    return tuple(options.values())


def legal_non_bomb_options(hand: list[str], level: str) -> list[PlayInfo]:
    return [
        info
        for info in legal_play_options(hand, level)
        if not is_bomb(info) and not server_treats_as_bomb(info.cards, level)
    ]


def legal_bomb_options(hand: list[str], level: str) -> list[PlayInfo]:
    bombs = []
    for info in legal_play_options(hand, level):
        canonical_bombs = [table_info for table_info in canonical_table_infos(list(info.cards), level) if is_bomb(table_info)]
        bombs.extend(canonical_bombs)
    unique: dict[tuple[tuple[str, ...], str, str], PlayInfo] = {}
    for info in bombs:
        unique[(info.cards, info.type, info.rank)] = info
    return list(unique.values())


def choose_non_bomb_follow(
    hand: list[str], last_play: list[str], level: str, prefer_strong: bool = False
) -> list[str] | None:
    canonical_infos = canonical_table_infos(last_play, level)
    if any(is_bomb(info) for info in canonical_infos):
        return None
    last_infos = [info for info in canonical_infos if not is_bomb(info)]
    if not last_infos:
        return None

    target_types = {(info.type, info.size) for info in last_infos}
    target_size = len(last_play)
    options = []
    for combo in itertools.combinations(hand, target_size):
        if server_treats_as_bomb(combo, level):
            continue
        infos = safe_follow_infos(combo, last_play, level)
        infos = [info for info in infos if not is_bomb(info)]
        info_types = {info.type for info in infos}
        if len(info_types) != 1 or not info_types.issubset({play_type for play_type, _ in target_types}):
            continue
        for info in infos:
            if (info.type, info.size) not in target_types:
                continue
            options.append((candidate_key(combo, info, hand, level), combo))
            break

    if not options:
        return None
    if prefer_strong:
        return sort_cards(
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
    return sort_cards(list(min(options, key=lambda item: item[0])[1]), level)


def choose_lowest_single(hand: list[str], level: str) -> list[str]:
    return [sort_cards(hand, level)[0]]


def choose_lowest_type(hand: list[str], level: str, play_type: str) -> list[str] | None:
    options = [
        info
        for info in legal_non_bomb_options(hand, level)
        if info.type == play_type and not server_treats_as_bomb(info.cards, level)
    ]
    if not options:
        return None
    best = min(
        options,
        key=lambda info: (
            card_cost(info.cards, level)[0],
            card_cost(info.cards, level)[1],
            rank_value(info, level),
            card_cost(info.cards, level),
        ),
    )
    return list(best.cards)


def choose_teammate_setup_lead(state: dict) -> list[str] | None:
    level = state["level"]
    hand = state["your_hand"]
    ally_count = teammate_count(state)
    opponent_min = min_opponent_count(state)
    if ally_count is None:
        return None
    current_groups = estimate_remaining_groups(hand, level)

    if STRATEGY_MODE == "selfcarry":
        if self_carry_mode(state):
            return None
        if ally_count >= len(hand) or ally_count >= opponent_min or ally_count > 3:
            return None

        self_score = self_sprint_score(state)
        effective_ally_score = ally_sprint_score(state)
        if opponent_head_threat_score(state) >= defense_block_threshold():
            return None
        if effective_ally_score <= self_score + 14.0:
            return None
        if effective_ally_reliability(state) < 0.5 and ally_count > 2 and effective_ally_score < 70.0:
            return None
    else:
        if current_groups <= 2.5:
            return None
        if ally_count >= len(hand):
            return None
        risk = opponent_head_threat_score(state)
        if ally_count <= 3:
            if opponent_min < ally_count:
                return None
        elif ally_count in (5, 6):
            if current_groups <= 3.0 or risk >= defense_block_threshold() or opponent_min <= ally_count:
                return None
        else:
            return None

        if effective_ally_reliability(state) < 0.6 and ally_count > 2:
            return None

    if ally_count >= opponent_min and not (STRATEGY_MODE != "selfcarry" and ally_count <= 3 and opponent_min == ally_count):
        return None

    helper_types_by_count = {
        1: ["single"],
        2: ["pair", "single"],
        3: ["triple", "pair", "single"],
        4: ["single", "pair"],
        5: ["full_house", "straight", "single"],
        6: ["steel", "plate", "straight", "pair", "single"],
    }
    for helper_type in helper_types_by_count.get(ally_count, []):
        helper = choose_lowest_type(hand, level, helper_type)
        if helper is not None:
            return helper
    return None


def choose_best_bomb_follow(hand: list[str], last_play: list[str], level: str) -> list[str] | None:
    last_infos = canonical_table_infos(last_play, level)
    options = []
    for bomb in legal_bomb_options(hand, level):
        if any(info_beats(bomb, last_info, level) for last_info in last_infos):
            options.append((bomb_key(bomb, level), card_cost(bomb.cards, level), bomb.cards))
    if not options:
        return None
    return list(min(options, key=lambda item: item[:2])[2])


def defense_block_threshold() -> float:
    return 42.0


def forced_defense_threshold() -> float:
    return 90.0


def choose_score_swing_bomb(state: dict, risk: float | None = None, chance: float | None = None) -> list[str] | None:
    last_play = state.get("last_play") or []
    if not last_play:
        return None
    if relation_to_last(state) != "opponent":
        return None

    level = state["level"]
    hand = state["your_hand"]
    risk = opponent_head_threat_score(state) if risk is None else risk
    chance = team_first_chance_score(state) if chance is None else chance
    actor = team_first_actor(state)
    last_infos = canonical_table_infos(last_play, level)
    options = []

    for bomb in legal_bomb_options(hand, level):
        if not any(info_beats(bomb, last_info, level) for last_info in last_infos):
            continue
        remaining = remove_cards(hand, bomb.cards)
        remaining_groups = estimate_remaining_groups(remaining, level)
        if STRATEGY_MODE == "selfcarry":
            blocks_head = risk >= defense_block_threshold()
            wins_key_control = risk >= 32.0 and min_opponent_count(state) <= 6
        else:
            blocks_head = min_opponent_count(state) <= 2 or last_player_count(state) <= 4
            wins_key_control = False
        self_head_setup = remaining_groups <= 2.0 or len(remaining) <= 4
        ally_count = teammate_count(state)
        protects_teammate = (
            actor == "teammate"
            and ally_count is not None
            and ally_count <= 3
            and chance >= 34.0
            and risk >= 30.0
        )
        if not (blocks_head or protects_teammate or wins_key_control or self_head_setup):
            continue
        priority = (
            risk * 1.8
            + chance * 0.7
            + (35.0 if blocks_head else 0.0)
            + (24.0 if protects_teammate else 0.0)
            + (30.0 if self_head_setup else 0.0)
            - remaining_groups * 8.0
        )
        options.append((priority, bomb_key(bomb, level), card_cost(bomb.cards, level), bomb.cards))

    if not options:
        return None
    return list(max(options, key=lambda item: (item[0], -item[1][0], -item[2][2]))[3])


def choose_bomb_to_set_up_finish(hand: list[str], last_play: list[str], level: str) -> list[str] | None:
    last_infos = canonical_table_infos(last_play, level)
    options = []
    for bomb in legal_bomb_options(hand, level):
        if not any(info_beats(bomb, last_info, level) for last_info in last_infos):
            continue
        remaining = remove_cards(hand, bomb.cards)
        if recognize(remaining, level):
            options.append((bomb_key(bomb, level), card_cost(bomb.cards, level), bomb.cards))
    if not options:
        return None
    return list(min(options, key=lambda item: item[:2])[2])


def choose_bomb_to_reduce_endgame(hand: list[str], last_play: list[str], level: str) -> list[str] | None:
    if len(hand) > 10:
        return None
    last_infos = canonical_table_infos(last_play, level)
    options = []
    for bomb in legal_bomb_options(hand, level):
        if not any(info_beats(bomb, last_info, level) for last_info in last_infos):
            continue
        remaining = remove_cards(hand, bomb.cards)
        remaining_groups = estimate_remaining_groups(remaining, level)
        if remaining_groups <= 2.5 or len(remaining) <= 4:
            options.append((remaining_groups, bomb_key(bomb, level), card_cost(bomb.cards, level), bomb.cards))
    if not options:
        return None
    return list(min(options, key=lambda item: item[:3])[3])


def choose_lead_bomb_to_set_up_finish(hand: list[str], level: str) -> list[str] | None:
    options = []
    for bomb in legal_bomb_options(hand, level):
        remaining = remove_cards(hand, bomb.cards)
        if recognize(remaining, level):
            options.append((bomb_key(bomb, level), card_cost(bomb.cards, level), bomb.cards))
    if not options:
        return None
    return list(min(options, key=lambda item: item[:2])[2])


def opponent_seats(state: dict) -> list[int]:
    your_seat = int(state["your_seat"])
    return [seat for seat in range(4) if seat % 2 != your_seat % 2]


def min_opponent_count(state: dict) -> int:
    hand_counts = state.get("hand_counts") or []
    counts = []
    for seat in opponent_seats(state):
        try:
            counts.append(hand_counts[seat])
        except (IndexError, TypeError):
            pass
    return min(counts) if counts else 99


def last_player_count(state: dict) -> int:
    last_player = state.get("last_player")
    hand_counts = state.get("hand_counts") or []
    try:
        return hand_counts[int(last_player)]
    except (IndexError, TypeError, ValueError):
        return 99


def race_pressure(state: dict) -> bool:
    opponent_min = min_opponent_count(state)
    hand = state.get("your_hand") or []
    level = state.get("level")
    ally_count = teammate_count(state)

    if opponent_min <= 4 or len(hand) <= 4:
        return True
    if level and len(hand) <= 10 and len(hand) < opponent_min:
        if estimate_remaining_groups(hand, level) <= 2.5:
            return True
    if ally_count is None or ally_count > 6 or ally_count >= opponent_min or ally_count >= len(hand):
        return False
    if effective_ally_reliability(state) >= 0.5:
        return True
    return ally_count <= 2 and ally_sprint_score(state) > self_sprint_score(state) + 12.0


def should_spend_bomb(state: dict) -> bool:
    last_player = state.get("last_player")
    if last_player is None or relation_to_last(state) != "opponent":
        return False

    if STRATEGY_MODE != "selfcarry":
        ally_count = teammate_count(state)
        teammate_near_head = (
            team_first_actor(state) == "teammate"
            and ally_count is not None
            and ally_count <= 3
            and team_first_chance_score(state) >= 34.0
        )
        return min_opponent_count(state) <= 2 or last_player_count(state) <= 4 or teammate_near_head

    risk = opponent_head_threat_score(state)
    chance = team_first_chance_score(state)
    return (
        risk >= defense_block_threshold()
        or last_player_count(state) <= 4
        or min_opponent_count(state) <= 2
        or (chance >= 58.0 and min_opponent_count(state) <= 6)
    )


def should_press_hard(state: dict) -> bool:
    last_player = state.get("last_player")
    if last_player is None or relation_to_last(state) != "opponent":
        return False
    hand_counts = state.get("hand_counts") or []
    try:
        return hand_counts[int(last_player)] <= 3 or race_pressure(state) or min_opponent_count(state) <= 2
    except (IndexError, TypeError, ValueError):
        return race_pressure(state) or min_opponent_count(state) <= 2


def follow_is_too_expensive(state: dict, follow: list[str]) -> bool:
    if should_press_hard(state) or race_pressure(state) or min_opponent_count(state) <= 2:
        return False
    level = state["level"]
    hand = state["your_hand"]
    wilds, kings, _, _ = card_cost(follow, level)
    if kings >= 2 and len(hand) > 8:
        return True
    if wilds or kings:
        return True
    current_groups = estimate_remaining_groups(hand, level)
    remaining_groups = estimate_remaining_groups(remove_cards(hand, follow), level)
    if len(hand) <= 10 or remaining_groups <= max(2.5, current_groups - 0.8):
        return False
    return structure_cost(follow, hand, level) >= 45 and last_player_count(state) > 4


def follow_has_good_tempo(state: dict, follow: list[str]) -> bool:
    level = state["level"]
    hand = state["your_hand"]
    current_groups = estimate_remaining_groups(hand, level)
    remaining_groups = estimate_remaining_groups(remove_cards(hand, follow), level)
    wilds, kings, _, _ = card_cost(follow, level)
    if kings >= 2 and len(hand) > 8 and remaining_groups > 1.5:
        return False
    if (wilds or kings) and not should_press_hard(state) and not race_pressure(state):
        return remaining_groups <= 2.0 or (len(hand) <= 6 and current_groups - remaining_groups >= 0.8)
    if remaining_groups <= 2.5:
        return True
    if current_groups - remaining_groups >= follow_gain_threshold():
        return True
    return len(hand) <= 8


def follow_damages_race_shape(state: dict, follow: list[str]) -> bool:
    if last_player_count(state) <= 2 or min_opponent_count(state) <= 2:
        return False

    level = state["level"]
    hand = state["your_hand"]
    current_groups = estimate_remaining_groups(hand, level)
    remaining_groups = estimate_remaining_groups(remove_cards(hand, follow), level)
    if len(hand) <= 5 and remaining_groups <= 2.0:
        return False
    return remaining_groups > current_groups


def teammate_play_feeds_opponent_directly(state: dict) -> bool:
    last_play = state.get("last_play") or []
    if not last_play:
        return False
    return len(last_play) in {count for count in opponent_hand_counts(state) if 0 < count <= 6}


def teammate_override_reason(state: dict, follow: list[str]) -> str | None:
    level = state["level"]
    hand = state["your_hand"]
    remaining = remove_cards(hand, follow)
    remaining_groups = estimate_remaining_groups(remaining, level)
    if remaining and recognize(remaining, level):
        return "self_one_hand_after_override"
    if remaining_groups <= 1.5:
        return "self_remaining_groups_le_1_5"
    if min_opponent_count(state) <= 2:
        return "opponent_head_emergency"
    if teammate_play_feeds_opponent_directly(state):
        return "teammate_feed_direct_head"
    return None


def choose_lead_play(state: dict) -> list[str]:
    level = state["level"]
    hand = state["your_hand"]
    bomb_finish = choose_lead_bomb_to_set_up_finish(hand, level)
    if bomb_finish is not None and len(hand) <= PROACTIVE_BOMB_HAND_LIMIT:
        return bomb_finish

    options = legal_non_bomb_options(hand, level)
    if not options:
        return choose_lowest_single(hand, level)

    ally_count = teammate_count(state)
    opponent_min = min_opponent_count(state)
    teammate_helper = choose_teammate_setup_lead(state)
    if teammate_helper is not None:
        return teammate_helper

    if (
        STRATEGY_MODE == "selfcarry"
        and ally_count == 1
        and opponent_min > 1
        and not self_carry_mode(state)
        and ally_sprint_score(state) > self_sprint_score(state) + 16.0
        and opponent_head_threat_score(state) < defense_block_threshold()
    ):
        helper = choose_lowest_type(hand, level, "single")
        if helper is not None:
            return helper

    avoid_size_limit = max(4, min(8, int(4 + RISK_RATIO)))
    opponent_finish_sizes = {
        count for count in opponent_hand_counts(state) if 0 < count <= avoid_size_limit
    }
    if opponent_finish_sizes:
        safe_options = [info for info in options if info.size not in opponent_finish_sizes]
        if safe_options:
            options = safe_options
    if opponent_min <= 1:
        safe_options = [info for info in options if info.type != "single"]
        if safe_options:
            options = safe_options
    if opponent_min <= 2:
        safe_options = [info for info in options if info.type != "pair"]
        if safe_options:
            options = safe_options
    if (
        STRATEGY_MODE == "selfcarry"
        and ally_count is not None
        and ally_count <= 3
        and ally_count < opponent_min
        and not self_carry_mode(state)
        and ally_sprint_score(state) > self_sprint_score(state) + 16.0
        and opponent_head_threat_score(state) < defense_block_threshold()
        and should_help_ally_shape(hand, level, state)
    ):
        helper_types: list[str] = []
        if ally_count == 3:
            helper_types = ["triple"]
        for helper_type in helper_types:
            helper = choose_lowest_type(hand, level, helper_type)
            if helper is not None:
                return helper

    current_groups = estimate_remaining_groups(hand, level)
    self_is_team_sprinter = self_sprint_score(state) >= ally_sprint_score(state)
    lead_control_mode = (
        race_pressure(state)
        and self_is_team_sprinter
        and (len(hand) <= 8 or current_groups <= 3.0)
    )

    def score(info: PlayInfo) -> float:
        remaining = remove_cards(hand, list(info.cards))
        remaining_groups = estimate_remaining_groups(remaining, level)
        base = LEAD_TYPE_SCORE.get(info.type, 0)
        rank = rank_value(info, level)
        rank_penalty = 0.0 if lead_control_mode else rank * 1.4
        size_bonus = info.size * 7
        block_bonus = LEAD_BLOCK_BONUS if info.size > opponent_min else 0
        if STRATEGY_MODE == "balanced" and opponent_min <= 2 and info.size > opponent_min:
            block_bonus += LEAD_BLOCK_BONUS
        # Keep the special heart-level card available for flexible follow plays.
        wild_penalty = card_cost(info.cards, level)[0] * (24 if lead_control_mode else 45)
        level_penalty = level_card_count(info.cards, level) * (10 if lead_control_mode else 22)
        king_penalty = card_cost(info.cards, level)[1] * (8 if lead_control_mode else 26)
        split_penalty = structure_cost(info.cards, hand, level) * 2.4
        plan_bonus = PLAN_TYPE_BONUS.get(info.type, 0)
        endgame_control_bonus = 0.0
        if len(hand) <= 10 and remaining_groups <= 2:
            endgame_control_bonus = rank * 3.0 + info.size * 4.0
        if STRATEGY_MODE == "balanced" and current_groups <= 2.5 and remaining_groups < current_groups:
            endgame_control_bonus += 14.0
        if lead_control_mode:
            endgame_control_bonus += rank * 3.8
            if remaining_groups <= current_groups - 1:
                endgame_control_bonus += 18.0
        expected_remaining = max(0.0, current_groups - 1.0)
        plan_damage_penalty = max(0.0, remaining_groups - expected_remaining) * 26.0
        if remaining_groups > current_groups:
            plan_damage_penalty += (remaining_groups - current_groups) * 30.0
        return (
            base
            + size_bonus
            + block_bonus
            + plan_bonus
            + endgame_control_bonus
            - remaining_groups * remaining_group_weight()
            - plan_damage_penalty
            - rank_penalty
            - wild_penalty
            - level_penalty
            - king_penalty
            - split_penalty
        )

    ranked = []
    for info in options:
        rank_tie = card_cost(info.cards, level)[2]
        if not lead_control_mode:
            rank_tie = -rank_tie
        ranked.append((score(info), rank_tie, info.cards))

    best = max(ranked, key=lambda item: (item[0], item[1], sort_cards(item[2], level)))
    return list(best[2])


def choose_play(state: dict) -> list[str]:
    level = state["level"]
    hand = state["your_hand"]
    last_play = state.get("last_play") or []
    risk = opponent_head_threat_score(state)
    chance = team_first_chance_score(state)

    all_out = choose_all_out_if_possible(hand, last_play, level)
    if all_out is not None:
        return all_out

    if not last_play:
        return choose_lead_play(state)

    relation = relation_to_last(state)
    if relation == "teammate":
        ally_count = teammate_count(state)
        opponent_min = min_opponent_count(state)
        if STRATEGY_MODE != "selfcarry":
            teammate_follow = choose_non_bomb_follow(
                hand, last_play, level, prefer_strong=opponent_min <= 2
            )
            if teammate_follow is not None and teammate_override_reason(state, teammate_follow):
                return teammate_follow
            if opponent_min <= 2:
                bomb = choose_best_bomb_follow(hand, last_play, level)
                if bomb is not None:
                    return bomb
            return []

        self_score = self_sprint_score(state)
        ally_score = ally_sprint_score(state)
        risk_is_low = risk < defense_block_threshold()
        trust_ally = (
            ally_count is not None
            and ally_count <= 3
            and ally_count < opponent_min
            and ally_score > self_score + 16.0
            and risk_is_low
            and not self_carry_mode(state)
        )
        if trust_ally:
            return []

        teammate_follow = choose_non_bomb_follow(
            hand, last_play, level, prefer_strong=self_carry_mode(state) or opponent_min <= 6
        )
        if teammate_follow is not None:
            current_groups = estimate_remaining_groups(hand, level)
            remaining_groups = estimate_remaining_groups(remove_cards(hand, teammate_follow), level)
            improves_self = current_groups - remaining_groups >= 0.75 or remaining_groups <= 2.0
            teammate_play_feeds_opponent = len(last_play) in {
                count for count in opponent_hand_counts(state) if 0 < count <= 6
            }
            low_trust_override = effective_ally_reliability(state) < 0.5 and improves_self
            defensive_override = opponent_min <= 6 and (
                risk >= defense_block_threshold() or teammate_play_feeds_opponent
            )
            self_finish_override = self_carry_mode(state) and (improves_self or self_score >= ally_score)
            if low_trust_override or defensive_override or self_finish_override:
                return teammate_follow

        if self_carry_mode(state) and effective_ally_reliability(state) < 0.5:
            bomb = choose_bomb_to_reduce_endgame(hand, last_play, level)
            if bomb is not None:
                return bomb
        return []

    if relation == "opponent" and risk >= defense_block_threshold():
        urgent_follow = choose_non_bomb_follow(hand, last_play, level, prefer_strong=True)
        if urgent_follow is not None:
            if risk >= forced_defense_threshold() or not follow_damages_race_shape(state, urgent_follow):
                return urgent_follow
        urgent_bomb = choose_score_swing_bomb(state, risk, chance)
        if urgent_bomb is not None:
            return urgent_bomb

    follow = choose_non_bomb_follow(hand, last_play, level, prefer_strong=should_press_hard(state))
    if follow is not None:
        if follow_damages_race_shape(state, follow):
            return []
        if follow_is_too_expensive(state, follow) and not follow_has_good_tempo(state, follow):
            return []
        return follow
    setup_bomb = choose_bomb_to_set_up_finish(hand, last_play, level)
    if setup_bomb is not None:
        return setup_bomb
    endgame_bomb = choose_bomb_to_reduce_endgame(hand, last_play, level)
    if endgame_bomb is not None:
        return endgame_bomb
    if should_spend_bomb(state):
        bomb = choose_score_swing_bomb(state, risk, chance) or choose_best_bomb_follow(hand, last_play, level)
        if bomb is not None:
            return bomb
    return []


def join_game() -> str:
    data = get_json("/join_game", auth_params())
    if not data.get("is_success"):
        raise RuntimeError(f"join_game failed: {data}")
    return str(data["game_id"])


def check_game(game_id: str) -> dict:
    params = {"user": USER, "password": encrypted_password_hex()}
    return get_json(f"/check_game/{game_id}/", params)


def play_game(game_id: str, coord: list[str]) -> dict:
    params = auth_params()
    params["coord"] = json.dumps(coord, separators=(",", ":"))
    return get_json(f"/play_game/{game_id}/", params)


def seat_team(state: dict, seat: int) -> int:
    try:
        return int(state["teams"][str(seat)])
    except (KeyError, TypeError, ValueError):
        return seat % 2


def your_team_id(state: dict) -> int | None:
    try:
        return int(state["your_team"])
    except (KeyError, TypeError, ValueError):
        return None


def ranked_seat(state: dict, entry) -> int | None:
    if isinstance(entry, int):
        return entry
    if isinstance(entry, str) and entry.isdigit():
        seat = int(entry)
        if 0 <= seat < 4:
            return seat
    seats = state.get("seats") or []
    for seat, name in enumerate(seats):
        if name == entry:
            return seat
    return None


def team_has_finished(state: dict, team: int) -> bool:
    hand_counts = state.get("hand_counts") or []
    if len(hand_counts) < 4:
        return False
    try:
        return any(hand_counts[seat] <= 0 for seat in range(4) if seat_team(state, seat) == team)
    except (TypeError, ValueError):
        return False


def opponent_first_out_seat(state: dict) -> int | None:
    ranking = state.get("ranking") or []
    if ranking:
        first_seat = ranked_seat(state, ranking[0])
        if first_seat is None:
            return None
        your_team = your_team_id(state)
        return first_seat if your_team is not None and seat_team(state, first_seat) != your_team else None

    hand_counts = state.get("hand_counts") or []
    if len(hand_counts) < 4:
        return None
    your_team = your_team_id(state)
    if your_team is None or team_has_finished(state, your_team):
        return None
    for seat in opponent_seats(state):
        try:
            if hand_counts[seat] <= 0:
                return seat
        except (IndexError, TypeError):
            continue
    return None


def opponent_imminent_first_out_seat(state: dict) -> int | None:
    if state.get("ranking") or opponent_first_out_seat(state) is not None:
        return None

    hand_counts = state.get("hand_counts") or []
    if len(hand_counts) < 4:
        return None
    your_team = your_team_id(state)
    if your_team is None or team_has_finished(state, your_team):
        return None

    candidates = []
    for seat in opponent_seats(state):
        try:
            count = int(hand_counts[seat])
        except (IndexError, TypeError, ValueError):
            continue
        if 0 < count <= OPPONENT_IMMINENT_OUT_LIMIT:
            candidates.append((count, seat))
    if candidates:
        return min(candidates)[1]

    last_player = state.get("last_player")
    if last_player is not None and relation_to_last(state) == "opponent" and (state.get("last_play") or []):
        try:
            seat = int(last_player)
            count = int(hand_counts[seat])
        except (IndexError, TypeError, ValueError):
            return None
        if 0 < count <= OPPONENT_CONTROL_OUT_LIMIT:
            return seat
    return None


def abandon_state(state: dict, game_id: str, reason: str, seat: int) -> dict:
    abandoned = dict(state)
    abandoned["game_id"] = game_id
    abandoned["abandoned_reason"] = reason
    if reason == "opponent_first_out":
        abandoned["abandoned_after_opponent_first_out"] = True
        abandoned["abandoned_first_out_seat"] = seat
        abandoned["winner_team"] = seat_team(abandoned, seat)
    else:
        abandoned["abandoned_before_opponent_first_out"] = True
        abandoned["abandoned_imminent_out_seat"] = seat
        abandoned["anticipated_winner_team"] = seat_team(abandoned, seat)
    return abandoned


def handle_abandon(
    game_id: str,
    state: dict,
    decisions: list[dict],
    log_dir: str | None,
    log_losses_only: bool,
    action: str,
    exit_code: int,
) -> dict | None:
    if action == "off" or state.get("completed"):
        return None

    seat = opponent_first_out_seat(state)
    reason = "opponent_first_out"
    if seat is None:
        seat = opponent_imminent_first_out_seat(state)
        reason = "opponent_imminent_first_out"
    if seat is None:
        return None

    abandoned = abandon_state(state, game_id, reason, seat)
    if reason == "opponent_first_out":
        print(
            f"abandon_game game_id={game_id} opponent_first_out_seat={seat} "
            f"winner_team={abandoned.get('winner_team')} your_team={abandoned.get('your_team')}"
        )
    else:
        print(
            f"abandon_game game_id={game_id} opponent_imminent_first_out_seat={seat} "
            f"anticipated_winner_team={abandoned.get('anticipated_winner_team')} "
            f"your_team={abandoned.get('your_team')}"
        )
    save_game_log(game_id, abandoned, decisions, log_dir, log_losses_only)
    if action == "exit":
        print(f"abandon_exit code={exit_code}")
        sys.exit(exit_code)
    return abandoned


def play_uses_bomb(cards: list[str], level: str) -> bool:
    return bool(cards) and any(is_bomb(info) for info in canonical_table_infos(cards, level))


def bomb_usage_reason(state: dict, coord: list[str], risk: float, chance: float) -> str | None:
    if not play_uses_bomb(coord, state["level"]):
        return None
    remaining = remove_cards(state.get("your_hand") or [], coord)
    remaining_groups = estimate_remaining_groups(remaining, state["level"])
    if relation_to_last(state) == "opponent" and risk >= defense_block_threshold():
        return "block_opponent_head"
    if team_first_actor(state) == "teammate" and chance >= 34.0:
        return "protect_teammate_head"
    if remaining_groups <= 2.0 or len(remaining) <= 4:
        return "self_head_setup"
    return "key_control"


def decision_analysis(state: dict, coord: list[str]) -> dict:
    risk = opponent_head_threat_score(state)
    chance = team_first_chance_score(state)
    self_score = self_sprint_score(state)
    raw_ally_score = raw_ally_sprint_score(state)
    effective_ally_score = ally_sprint_score(state)
    relation = relation_to_last(state)
    last_play = state.get("last_play") or []
    actor = team_first_actor(state)
    blocked_opponent = bool(coord and relation == "opponent" and last_play)
    overrode_teammate = bool(coord and relation == "teammate" and last_play)
    protected_teammate = bool(
        effective_ally_score > self_score + 16.0
        and (
            (relation == "teammate" and not coord)
            or (not last_play and bool(coord))
            or blocked_opponent
        )
    )
    bomb_reason = bomb_usage_reason(state, coord, risk, chance)

    if relation == "opponent" and risk >= defense_block_threshold():
        mode = "defense"
    elif actor == "teammate" and effective_ally_score > self_score + 16.0 and not self_carry_mode(state):
        mode = "ally_support"
    elif self_carry_mode(state):
        mode = "self_carry"
    else:
        mode = "attack"

    override_reason = None
    if overrode_teammate:
        if self_carry_mode(state):
            override_reason = "self_carry"
        elif risk >= defense_block_threshold() or min_opponent_count(state) <= 6:
            override_reason = "defense_control"
        elif effective_ally_reliability(state) < 0.5:
            override_reason = "low_ally_reliability"
        else:
            override_reason = "improve_self_sprint"

    refused_help = False
    refused_reason = None
    if raw_ally_score > 0 and effective_ally_score <= self_score + 16.0:
        refused_help = True
        if effective_ally_reliability(state) < 0.5:
            refused_reason = "discounted_ally_reliability"
        elif self_carry_mode(state):
            refused_reason = "self_carry_higher_expected_score"
        elif risk >= defense_block_threshold():
            refused_reason = "opponent_head_threat"
        else:
            refused_reason = "self_sprint_not_worse"

    if not coord:
        if relation == "teammate":
            reason = "pass_to_teammate"
        elif relation == "opponent" and risk >= defense_block_threshold():
            reason = "no_safe_block_or_preserve_shape"
        else:
            reason = "pass_no_positive_expected_score"
    elif sorted(coord) == sorted(state.get("your_hand") or []):
        reason = "all_out"
    elif bomb_reason:
        reason = bomb_reason
    elif relation == "opponent":
        reason = "block_or_follow_opponent"
    elif not last_play and actor == "teammate":
        reason = "setup_teammate_first"
    elif not last_play:
        reason = "push_self_first"
    else:
        reason = "normal_play"

    return {
        "risk_ratio": RISK_RATIO,
        "ally_reliability": effective_ally_reliability(state),
        "configured_ally_reliability": ALLY_RELIABILITY,
        "self_sprint_score": self_score,
        "raw_ally_sprint_score": raw_ally_score,
        "effective_ally_sprint_score": effective_ally_score,
        "opponent_head_threat_score": risk,
        "team_first_chance_score": chance,
        "decision_mode": mode,
        "decision_reason": reason,
        "whether_blocked_opponent": blocked_opponent,
        "whether_protected_teammate": protected_teammate,
        "whether_overrode_teammate": overrode_teammate,
        "override_teammate_reason": override_reason,
        "whether_refused_to_help_ally": refused_help,
        "refused_to_help_ally_reason": refused_reason,
        "bomb_usage_reason": bomb_reason,
    }


def decision_snapshot(turn_count: int, state: dict, coord: list[str]) -> dict:
    hand = state.get("your_hand") or []
    level = state.get("level")
    remaining = remove_cards(hand, coord) if coord else hand
    snapshot = {
        "turn": turn_count,
        "strategy": STRATEGY_MODE,
        "level": level,
        "hand": hand,
        "hand_count": len(hand),
        "hand_counts": state.get("hand_counts"),
        "teammate_count": teammate_count(state),
        "team_min_count": team_min_count(state),
        "min_opponent_count": min_opponent_count(state),
        "last_player_count": last_player_count(state),
        "race_pressure": race_pressure(state),
        "last_play": state.get("last_play") or [],
        "last_player": state.get("last_player"),
        "last_relation": relation_to_last(state),
        "current_turn": state.get("current_turn"),
        "trick_index": len(state.get("trick_history") or []),
        "groups_before": estimate_remaining_groups(hand, level) if level else None,
        "groups_after": estimate_remaining_groups(remaining, level) if level else None,
        "play": coord,
    }
    snapshot.update(decision_analysis(state, coord))
    return snapshot


def save_game_log(
    game_id: str,
    final_state: dict,
    decisions: list[dict],
    log_dir: str | None,
    log_losses_only: bool,
) -> None:
    if not log_dir:
        return

    your_team = final_state.get("your_team")
    winner_team = final_state.get("winner_team")
    is_loss = winner_team != your_team
    if log_losses_only and not is_loss:
        return

    target = Path(log_dir)
    target.mkdir(parents=True, exist_ok=True)
    outcome = "loss" if is_loss else "win"
    stamp = time.strftime("%Y%m%d_%H%M%S")
    path = target / f"game_{game_id}_{outcome}_{stamp}.json"
    payload = {
        "game_id": game_id,
        "outcome": outcome,
        "strategy": STRATEGY_MODE,
        "decisions": decisions,
        "final_state": final_state,
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"saved_game_log={path}")


def run_game(
    game_id: str | None = None,
    poll_seconds: float = DEFAULT_POLL_SECONDS,
    log_dir: str | None = None,
    log_losses_only: bool = False,
    abandon_action: str = "exit",
    abandon_exit_code: int = ABANDON_EXIT_CODE,
) -> dict:
    if game_id is None:
        game_id = join_game()
        print(f"joined game_id={game_id}")
    else:
        print(f"resuming game_id={game_id}")

    turn_count = 0
    transient_failures = 0
    decisions: list[dict] = []
    while True:
        try:
            state = check_game(game_id)
            transient_failures = 0
        except TRANSIENT_ERRORS as exc:
            transient_failures += 1
            wait_seconds = min(max(poll_seconds, 5) * transient_failures, 60)
            print(
                f"transient_timeout game_id={game_id} phase=check "
                f"count={transient_failures} wait={wait_seconds}s error={type(exc).__name__}"
            )
            time.sleep(wait_seconds)
            continue

        if not state.get("is_success", True):
            raise RuntimeError(f"check_game failed: {state}")

        abandoned = handle_abandon(
            str(game_id),
            state,
            decisions,
            log_dir,
            log_losses_only,
            abandon_action,
            abandon_exit_code,
        )
        if abandoned is not None:
            return abandoned

        if state.get("completed"):
            print("completed")
            print(json.dumps(state, ensure_ascii=False, indent=2))
            save_game_log(game_id, state, decisions, log_dir, log_losses_only)
            return state

        if state.get("is_your_turn"):
            turn_count += 1
            coord = choose_play(state)
            decision = decision_snapshot(turn_count, state, coord)
            decisions.append(decision)
            print(
                f"turn={turn_count} level={state['level']} hand={len(state['your_hand'])} "
                f"last={state.get('last_play') or []} last_player={state.get('last_player')} play={coord}"
            )
            try:
                result = play_game(game_id, coord)
                transient_failures = 0
            except TRANSIENT_ERRORS as exc:
                decision["transient_error"] = type(exc).__name__
                transient_failures += 1
                wait_seconds = min(max(poll_seconds, 5) * transient_failures, 60)
                print(
                    f"transient_timeout game_id={game_id} phase=play "
                    f"count={transient_failures} wait={wait_seconds}s error={type(exc).__name__}"
                )
                time.sleep(wait_seconds)
                continue
            print(json.dumps(result, ensure_ascii=False))
            decision["result"] = result
            if not result.get("is_success"):
                if coord and (state.get("last_play") or []):
                    fallback = play_game(game_id, [])
                    decision["fallback_pass"] = fallback
                    print(f"fallback_pass={json.dumps(fallback, ensure_ascii=False)}")
                    if fallback.get("is_success"):
                        time.sleep(1)
                        continue
                raise RuntimeError(f"play_game failed for {coord}: {result}")
            time.sleep(1)
        else:
            print(
                f"waiting current_turn={state.get('current_turn')} "
                f"hand_counts={state.get('hand_counts')} left_time={state.get('left_time')}"
            )
            time.sleep(poll_seconds)


def new_loop_stats() -> dict:
    return {
        "played": 0,
        "wins": 0,
        "points": 0,
        "team_first_outs": 0,
        "opponent_first_outs": 0,
        "abandons": 0,
        "last_winner": None,
        "your_team": None,
    }


def update_loop_stats(stats: dict, final_state: dict) -> None:
    stats["played"] += 1
    your_team = final_state.get("your_team")
    winner_team = final_state.get("winner_team")
    stats["last_winner"] = winner_team
    stats["your_team"] = your_team
    if final_state.get("abandoned_after_opponent_first_out") or final_state.get("abandoned_before_opponent_first_out"):
        stats["abandons"] += 1

    if winner_team == your_team:
        stats["wins"] += 1
        stats["team_first_outs"] += 1
    else:
        stats["opponent_first_outs"] += 1
    try:
        scores = final_state.get("scores") or {}
        stats["points"] += int(scores.get(str(your_team), 0))
    except (TypeError, ValueError):
        pass


def loop_summary_text(stats: dict, prefix: str = "loop_summary") -> str:
    played = max(1, stats["played"])
    average_points = stats["points"] / played
    team_rate = stats["team_first_outs"] / played
    opponent_rate = stats["opponent_first_outs"] / played
    return (
        f"{prefix} strategy={STRATEGY_MODE} played={stats['played']} "
        f"wins={stats['wins']} points={stats['points']} abandons={stats['abandons']} "
        f"average_points_per_game={average_points:.3f} "
        f"team_first_out_rate={team_rate:.3f} "
        f"opponent_first_out_rate={opponent_rate:.3f} "
        f"last_winner={stats['last_winner']} your_team={stats['your_team']}"
    )


def run_loop(args: argparse.Namespace, target_games: int, force_loop: bool = False) -> dict:
    stats = new_loop_stats()
    keep_going = args.loop or force_loop

    try:
        while target_games == 0 or stats["played"] < target_games:
            try:
                final_state = run_game(
                    poll_seconds=args.poll,
                    log_dir=args.log_dir,
                    log_losses_only=args.log_losses_only,
                    abandon_action=args.abandon_action,
                    abandon_exit_code=args.abandon_exit_code,
                )
            except Exception as exc:
                if not keep_going:
                    raise
                print(f"game_error {type(exc).__name__}: {exc}")
                time.sleep(max(args.error_delay, args.delay))
                continue

            update_loop_stats(stats, final_state)
            print(loop_summary_text(stats))

            if not keep_going or (target_games and stats["played"] >= target_games):
                break
            time.sleep(args.delay)
    except KeyboardInterrupt:
        print(f"stopped by user played={stats['played']} wins={stats['wins']}")
    return stats


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Play Guandan games with the local bot strategy.")
    parser.add_argument("game_id", nargs="?", help="Resume an existing game instead of joining a new bot table.")
    parser.add_argument("--loop", action="store_true", help="Keep joining new bot games after each game ends.")
    parser.add_argument(
        "--games",
        type=int,
        default=1,
        help="Number of new games to play. Use 0 with --loop for no fixed limit.",
    )
    parser.add_argument(
        "--poll",
        type=float,
        default=DEFAULT_POLL_SECONDS,
        help="Seconds to wait between status checks when it is not your turn.",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=DEFAULT_BETWEEN_GAMES_SECONDS,
        help="Seconds to wait before joining the next game in loop mode.",
    )
    parser.add_argument(
        "--error-delay",
        type=float,
        default=30,
        help="Seconds to back off before retrying after an error in loop mode.",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=DEFAULT_HTTP_TIMEOUT_SECONDS,
        help="HTTP request timeout in seconds.",
    )
    parser.add_argument(
        "--retries",
        type=int,
        default=DEFAULT_HTTP_RETRIES,
        help="HTTP retries per request before treating it as transient timeout.",
    )
    parser.add_argument(
        "--strategy",
        choices=("tempo", "balanced", "selfcarry"),
        default="tempo",
        help="Strategy profile: tempo is the stable baseline; balanced is a small revision; selfcarry is the previous aggressive profile.",
    )
    parser.add_argument(
        "--ab-test",
        action="store_true",
        help="Run tempo, balanced, and selfcarry sequentially for comparison.",
    )
    parser.add_argument(
        "--ab-games",
        type=int,
        default=30,
        help="Games per strategy when --ab-test is used.",
    )
    parser.add_argument("--user", help="Login user. Defaults to GD_USER or USER environment variable.")
    parser.add_argument("--password", help="Login password. Defaults to GD_PASSWORD or PASSWORD environment variable.")
    parser.add_argument(
        "--reward-team-first",
        type=float,
        help="Expected score gain when our team gets first out. Defaults to REWARD_TEAM_FIRST env or 1.0.",
    )
    parser.add_argument(
        "--penalty-opponent-first",
        type=float,
        help="Expected score loss magnitude when opponents get first out. Defaults to PENALTY_OPPONENT_FIRST env or 2.0.",
    )
    parser.add_argument(
        "--ally-reliability",
        type=float,
        help="Trust in teammate bot from 0.0 to 1.0. Defaults to ALLY_RELIABILITY env or 0.65.",
    )
    parser.add_argument(
        "--abandon-action",
        choices=("exit", "return", "off"),
        default="exit",
        help="What to do when an opponent has or is about to get first out: exit process, return to loop, or disable.",
    )
    parser.add_argument(
        "--abandon-exit-code",
        type=int,
        default=ABANDON_EXIT_CODE,
        help="Process exit code used when --abandon-action exit triggers.",
    )
    parser.add_argument(
        "--log-dir",
        help="Optional directory for JSON game logs with hands, decisions, and final state.",
    )
    parser.add_argument(
        "--log-losses-only",
        action="store_true",
        help="When --log-dir is set, save only lost games.",
    )
    return parser.parse_args()


def main() -> None:
    global HTTP_RETRIES, HTTP_TIMEOUT_SECONDS, STRATEGY_MODE
    args = parse_args()
    STRATEGY_MODE = args.strategy
    configure_credentials(args.user, args.password)
    configure_scoring(args.reward_team_first, args.penalty_opponent_first)
    configure_ally_reliability(args.ally_reliability)
    HTTP_TIMEOUT_SECONDS = args.timeout
    HTTP_RETRIES = max(1, args.retries)

    if args.ab_test:
        if args.game_id:
            raise RuntimeError("--ab-test cannot be used with an existing game_id")
        for strategy in ("tempo", "balanced", "selfcarry"):
            STRATEGY_MODE = strategy
            print(f"ab_start strategy={strategy} games={args.ab_games}")
            stats = run_loop(args, max(1, args.ab_games), force_loop=True)
            print(loop_summary_text(stats, prefix="ab_summary"))
        return

    if args.game_id:
        run_game(
            args.game_id,
            args.poll,
            args.log_dir,
            args.log_losses_only,
            args.abandon_action,
            args.abandon_exit_code,
        )
        return

    target_games = args.games if args.loop else 1
    run_loop(args, target_games)


if __name__ == "__main__":
    main()
