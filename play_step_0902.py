import argparse
import itertools
import json
import os
import socket
import time
from collections import Counter
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


BASE_URL = "http://183.175.14.145:8003"
USER = os.environ.get("GUANDAN_USER") or os.environ.get("GD_USER") or ""
PASSWORD = os.environ.get("GUANDAN_PASSWORD") or os.environ.get("GD_PASSWORD") or ""
DEFAULT_POLL_SECONDS = 6
DEFAULT_BETWEEN_GAMES_SECONDS = 8
DEFAULT_HTTP_TIMEOUT_SECONDS = 30
DEFAULT_HTTP_RETRIES = 3
DEFAULT_ABANDON_SLEEP_SECONDS = 30
MAX_ABANDON_RETRY_SLEEP_SECONDS = 130

HTTP_TIMEOUT_SECONDS = DEFAULT_HTTP_TIMEOUT_SECONDS
HTTP_RETRIES = DEFAULT_HTTP_RETRIES
STRATEGY_MODE = "tempo"
ABANDONED_GAME_IDS: set[str] = set()
ABANDONED_GAME_RETRY_SECONDS: dict[str, float] = {}

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
OPPONENT_IMMINENT_OUT_LIMIT = 1
OPPONENT_CONTROL_OUT_LIMIT = 1
CARD_TRACKER_BOMB_REMAINING_LIMIT = 4


@dataclass(frozen=True)
class PlayInfo:
    type: str
    rank: str
    cards: tuple[str, ...]
    size: int


def remaining_group_weight() -> int:
    return 34 if STRATEGY_MODE == "winrate" else REMAINING_GROUP_WEIGHT


def follow_gain_threshold() -> float:
    return 0.35 if STRATEGY_MODE == "winrate" else 0.40


def should_help_ally_shape(hand: list[str], level: str) -> bool:
    if len(hand) <= 8:
        return False
    threshold = 2.5 if STRATEGY_MODE == "winrate" else 3.5
    return estimate_remaining_groups(hand, level) > threshold


def str_to_num(value: str) -> int:
    num = 0
    for byte in value.encode("ascii"):
        num = num * 256 + byte
    return num


def encrypted_password_hex() -> str:
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


def team_min_count(state: dict) -> int:
    counts = [len(state.get("your_hand") or [])]
    ally_count = teammate_count(state)
    if ally_count is not None:
        counts.append(ally_count)
    return min(counts)


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
    if ally_count >= len(hand) or ally_count >= opponent_min or ally_count > 6:
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
    return ally_count is not None and ally_count <= 6 and ally_count < opponent_min and ally_count < len(hand)


def should_spend_bomb(state: dict) -> bool:
    last_player = state.get("last_player")
    if last_player is None or relation_to_last(state) != "opponent":
        return False

    return last_player_count(state) <= 4 or race_pressure(state) or min_opponent_count(state) <= 2


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

    if ally_count == 1 and opponent_min > 1:
        helper = choose_lowest_type(hand, level, "single")
        if helper is not None:
            return helper

    if opponent_min <= 6:
        safe_options = [info for info in options if info.size != opponent_min]
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
    if ally_count is not None and ally_count < opponent_min and should_help_ally_shape(hand, level):
        helper_types: list[str] = []
        if ally_count == 3:
            helper_types = ["triple"]
        elif ally_count == 5:
            helper_types = ["full_house", "straight"]
        elif ally_count == 6:
            helper_types = ["steel", "plate"]
        for helper_type in helper_types:
            helper = choose_lowest_type(hand, level, helper_type)
            if helper is not None:
                return helper

    current_groups = estimate_remaining_groups(hand, level)
    self_is_team_sprinter = ally_count is None or len(hand) <= ally_count
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
        # Keep the special heart-level card available for flexible follow plays.
        wild_penalty = card_cost(info.cards, level)[0] * (24 if lead_control_mode else 45)
        level_penalty = level_card_count(info.cards, level) * (10 if lead_control_mode else 22)
        king_penalty = card_cost(info.cards, level)[1] * (8 if lead_control_mode else 26)
        split_penalty = structure_cost(info.cards, hand, level) * 2.4
        plan_bonus = PLAN_TYPE_BONUS.get(info.type, 0)
        endgame_control_bonus = 0.0
        if len(hand) <= 10 and remaining_groups <= 2:
            endgame_control_bonus = rank * 3.0 + info.size * 4.0
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

    all_out = choose_all_out_if_possible(hand, last_play, level)
    if all_out is not None:
        return all_out

    if not last_play:
        return choose_lead_play(state)

    relation = relation_to_last(state)
    if relation == "teammate":
        ally_count = teammate_count(state)
        opponent_min = min_opponent_count(state)
        if ally_count is not None and ally_count <= opponent_min and ally_count <= 4:
            return []
        if opponent_min <= 2:
            protective = choose_non_bomb_follow(hand, last_play, level, prefer_strong=True)
            if protective is not None and not follow_is_too_expensive(state, protective):
                return protective
        return []

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
        bomb = choose_best_bomb_follow(hand, last_play, level)
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
    if your_team is None:
        return None
    try:
        team_finished = any(hand_counts[seat] <= 0 for seat in range(4) if seat_team(state, seat) == your_team)
        opponent_finished = [
            seat for seat in range(4)
            if seat_team(state, seat) != your_team and hand_counts[seat] <= 0
        ]
    except (TypeError, ValueError):
        return None
    if opponent_finished and not team_finished:
        return opponent_finished[0]
    return None


def team_has_finished(state: dict, team: int) -> bool:
    hand_counts = state.get("hand_counts") or []
    if len(hand_counts) < 4:
        return False
    try:
        return any(hand_counts[seat] <= 0 for seat in range(4) if seat_team(state, seat) == team)
    except (TypeError, ValueError):
        return False


def tracker_card_rank(card: str) -> str:
    return card if card in ("B", "R") else card[-1]


def full_deck_counter() -> Counter:
    deck = Counter()
    for suit in SUITS:
        for rank in RANKS:
            deck[suit + rank] = 2
    deck["B"] = 2
    deck["R"] = 2
    return deck


def trick_played_counter(state: dict) -> Counter:
    played = Counter()
    for item in state.get("trick_history") or []:
        try:
            _, cards = item
        except (TypeError, ValueError):
            continue
        played.update(cards or [])
    return played


def unseen_counter(state: dict) -> Counter:
    unseen = full_deck_counter()
    unseen.subtract(trick_played_counter(state))
    unseen.subtract(Counter(state.get("your_hand") or []))
    return +unseen


def card_tracker_snapshot(state: dict) -> dict:
    level = state.get("level")
    unseen = unseen_counter(state)
    unseen_by_rank = Counter(tracker_card_rank(card) for card, count in unseen.items() for _ in range(count))
    possible_bomb_ranks = sorted(
        rank for rank in RANKS
        if unseen_by_rank.get(rank, 0) >= CARD_TRACKER_BOMB_REMAINING_LIMIT
    )
    high_single_cards = []
    if level:
        order = game_rank_index(level)
        for card, count in unseen.items():
            rank = tracker_card_rank(card)
            if rank in ("B", "R") or order.get(rank, -1) >= order.get("A", 0):
                high_single_cards.extend([card] * count)
    return {
        "unseen_total": sum(unseen.values()),
        "unseen_kings": unseen.get("B", 0) + unseen.get("R", 0),
        "unseen_big_jokers": unseen.get("R", 0),
        "unseen_small_jokers": unseen.get("B", 0),
        "unseen_wildcards": unseen.get("H" + level, 0) if level else 0,
        "possible_bomb_ranks": possible_bomb_ranks,
        "high_single_count": len(high_single_cards),
    }


def opponent_escape_risk(state: dict, seat: int, count: int) -> float:
    tracker = card_tracker_snapshot(state)
    relation = relation_to_last(state)
    risk = 0.0
    if count <= 1:
        risk += 70.0
    elif count == 2:
        risk += 45.0
    elif count <= 4:
        risk += 25.0

    if relation == "opponent" and str(state.get("last_player")) == str(seat) and (state.get("last_play") or []):
        risk += 20.0
    if tracker["unseen_kings"] == 0:
        risk += 8.0
    if tracker["high_single_count"] <= 2:
        risk += 6.0
    if len(tracker["possible_bomb_ranks"]) >= 3:
        risk += 6.0
    if tracker["unseen_wildcards"] > 0:
        risk += 4.0
    return risk


def opponent_imminent_first_out_seat(state: dict) -> int | None:
    if state.get("ranking") or opponent_first_out_seat(state) is not None:
        return None

    hand_counts = state.get("hand_counts") or []
    if len(hand_counts) < 4:
        return None
    your_team = your_team_id(state)
    if your_team is None or team_has_finished(state, your_team):
        return None

    candidates: list[tuple[int, int]] = []
    for seat in opponent_seats(state):
        try:
            count = int(hand_counts[seat])
        except (IndexError, TypeError, ValueError):
            continue
        if count <= 0:
            continue
        if count <= OPPONENT_IMMINENT_OUT_LIMIT:
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
        if 0 < count <= OPPONENT_CONTROL_OUT_LIMIT and opponent_escape_risk(state, seat, count) >= 58.0:
            return seat
    return None


def decision_snapshot(turn_count: int, state: dict, coord: list[str]) -> dict:
    hand = state.get("your_hand") or []
    level = state.get("level")
    remaining = remove_cards(hand, coord) if coord else hand
    return {
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
        "card_tracker": card_tracker_snapshot(state),
        "play": coord,
    }


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


def disconnect_wait(game_id: str, sleep_seconds: float, reason: str) -> None:
    wait_seconds = max(0.0, sleep_seconds)
    print(f"disconnect_wait game_id={game_id} seconds={wait_seconds:g} reason={reason}")
    time.sleep(wait_seconds)


def abandoned_retry_wait(game_id: str, base_sleep_seconds: float) -> float:
    key = str(game_id)
    previous = ABANDONED_GAME_RETRY_SECONDS.get(key, base_sleep_seconds)
    wait_seconds = min(
        MAX_ABANDON_RETRY_SLEEP_SECONDS,
        max(base_sleep_seconds, previous * 2, 30.0),
    )
    ABANDONED_GAME_RETRY_SECONDS[key] = wait_seconds
    return wait_seconds


def run_game(
    game_id: str | None = None,
    poll_seconds: float = DEFAULT_POLL_SECONDS,
    log_dir: str | None = None,
    log_losses_only: bool = False,
    abandon_sleep_seconds: float = DEFAULT_ABANDON_SLEEP_SECONDS,
) -> dict:
    if game_id is None:
        while True:
            game_id = join_game()
            if str(game_id) not in ABANDONED_GAME_IDS:
                break
            wait_seconds = abandoned_retry_wait(str(game_id), abandon_sleep_seconds)
            print(
                f"rejoined_abandoned_game game_id={game_id}; "
                f"disconnecting_again seconds={wait_seconds:g}"
            )
            disconnect_wait(str(game_id), wait_seconds, "rejoined_abandoned_game")
            game_id = None
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

        abandoned_seat = opponent_first_out_seat(state) if not state.get("completed") else None
        imminent_seat = (
            opponent_imminent_first_out_seat(state)
            if abandoned_seat is None and not state.get("completed")
            else None
        )
        if abandoned_seat is not None:
            state = dict(state)
            state["abandoned_after_opponent_first_out"] = True
            state["abandoned_first_out_seat"] = abandoned_seat
            state["winner_team"] = seat_team(state, abandoned_seat)
            state["card_tracker"] = card_tracker_snapshot(state)
            ABANDONED_GAME_IDS.add(str(game_id))
            ABANDONED_GAME_RETRY_SECONDS[str(game_id)] = max(0.0, abandon_sleep_seconds)
            print(
                f"abandon_game game_id={game_id} opponent_first_out_seat={abandoned_seat} "
                f"winner_team={state['winner_team']} your_team={state.get('your_team')}"
            )
            save_game_log(game_id, state, decisions, log_dir, log_losses_only)
            return state

        if imminent_seat is not None:
            state = dict(state)
            state["abandoned_before_opponent_first_out"] = True
            state["abandoned_imminent_out_seat"] = imminent_seat
            state["anticipated_winner_team"] = seat_team(state, imminent_seat)
            try:
                imminent_count = int((state.get("hand_counts") or [])[imminent_seat])
            except (IndexError, TypeError, ValueError):
                imminent_count = 99
            state["opponent_escape_risk"] = opponent_escape_risk(state, imminent_seat, imminent_count)
            state["card_tracker"] = card_tracker_snapshot(state)
            ABANDONED_GAME_IDS.add(str(game_id))
            ABANDONED_GAME_RETRY_SECONDS[str(game_id)] = max(0.0, abandon_sleep_seconds)
            print(
                f"abandon_game game_id={game_id} opponent_imminent_first_out_seat={imminent_seat} "
                f"anticipated_winner_team={state['anticipated_winner_team']} your_team={state.get('your_team')}"
            )
            save_game_log(game_id, state, decisions, log_dir, log_losses_only)
            return state

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
        "--abandon-sleep",
        type=float,
        default=DEFAULT_ABANDON_SLEEP_SECONDS,
        help="Seconds to disconnect after abandoning a risky table before trying to join again.",
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
        choices=("winrate", "tempo"),
        default="tempo",
        help="Strategy profile: tempo is the current stable profile; winrate is an experimental teammate-assist profile.",
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
    if not USER or not PASSWORD:
        raise RuntimeError(
            "missing credentials: set GUANDAN_USER and GUANDAN_PASSWORD"
        )
    HTTP_TIMEOUT_SECONDS = args.timeout
    HTTP_RETRIES = max(1, args.retries)
    STRATEGY_MODE = args.strategy

    if args.game_id:
        run_game(args.game_id, args.poll, args.log_dir, args.log_losses_only, args.abandon_sleep)
        return

    target_games = args.games if args.loop else 1
    played = 0
    wins = 0
    points = 0
    abandons = 0

    try:
        while target_games == 0 or played < target_games:
            try:
                final_state = run_game(
                    poll_seconds=args.poll,
                    log_dir=args.log_dir,
                    log_losses_only=args.log_losses_only,
                    abandon_sleep_seconds=args.abandon_sleep,
                )
            except Exception as exc:
                if not args.loop:
                    raise
                print(f"game_error {type(exc).__name__}: {exc}")
                time.sleep(max(args.error_delay, args.delay))
                continue

            played += 1
            your_team = final_state.get("your_team")
            winner_team = final_state.get("winner_team")
            abandoned_this_game = (
                final_state.get("abandoned_after_opponent_first_out")
                or final_state.get("abandoned_before_opponent_first_out")
            )
            if abandoned_this_game:
                abandons += 1
            if winner_team == your_team:
                wins += 1
            try:
                scores = final_state.get("scores") or {}
                points += int(scores.get(str(your_team), 0))
            except (TypeError, ValueError):
                pass
            print(
                f"loop_summary played={played} wins={wins} points={points} abandons={abandons} "
                f"last_winner={winner_team} your_team={your_team}"
            )

            if not args.loop or (target_games and played >= target_games):
                break
            if abandoned_this_game:
                disconnect_wait(str(final_state.get("game_id")), args.abandon_sleep, "abandoned_table")
            else:
                time.sleep(args.delay)
    except KeyboardInterrupt:
        print(f"stopped by user played={played} wins={wins}")


if __name__ == "__main__":
    main()
