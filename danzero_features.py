from __future__ import annotations

from collections import Counter
from typing import Any, Iterable, Sequence

import numpy as np


SUITS = ("红桃", "梅花", "黑桃", "方块")
RANKS = ("2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K", "A")
JOKERS = ("小王", "大王")
CARD_KEYS_54 = tuple(f"{suit}{rank}" for rank in RANKS for suit in SUITS) + JOKERS
CARD_INDEX_54 = {card: index for index, card in enumerate(CARD_KEYS_54)}

CANONICAL_ACTION_TYPES = (
    "pass",
    "single",
    "pair",
    "triple",
    "full_house",
    "straight",
    "plate",
    "steel",
    "bomb",
    "straight_flush",
    "quad_kings",
    "unknown",
)
ACTION_TYPE_INDEX = {name: index for index, name in enumerate(CANONICAL_ACTION_TYPES)}

DANZERO_PHYSICAL_ACTION_DIM = 54
DANZERO_ACTION_LOGIC_RANK_DIM = 18
DANZERO_ACTION_SIZE_DIM = 9
DANZERO_ACTION_FLAG_DIM = 8
DANZERO_EXTENDED_ACTION_DIM = (
    DANZERO_PHYSICAL_ACTION_DIM
    + len(CANONICAL_ACTION_TYPES)
    + DANZERO_ACTION_LOGIC_RANK_DIM
    + DANZERO_ACTION_SIZE_DIM
    + DANZERO_ACTION_FLAG_DIM
    + DANZERO_PHYSICAL_ACTION_DIM
)
DANZERO_COMPACT_STATE_DIM = 513
DANZERO_WEBSITE_COMPACT_STATE_DIM = 487
PASS_SENTINELS = {"Pass", "None", "pass", "none", ""}
DANZERO_PHYSICAL_ACTION_ENCODING_VERSION = "danzero_physical54_rank_major_hcsd_v1"
DANZERO_EXTENDED_ACTION_ENCODING_VERSION = "guandan_extended_action155_v1"
DANZERO_COMPACT_STATE_ENCODING_VERSION = "danzero_compact_state513_v1"
DANZERO_WEBSITE_STATE_ENCODING_VERSION = "guandan_website_compact_state487_v1"
DANZERO_STATE_SLICES = {
    "hand": (0, 54),
    "unknown_remaining": (54, 108),
    "last_play": (108, 162),
    "teammate_last_play": (162, 216),
    "other_hand_counts": (216, 300),
    "other_played_cards": (300, 462),
    "team_level": (462, 475),
    "opponent_level": (475, 488),
    "current_level": (488, 501),
    "wildcard_capabilities": (501, 513),
}


ASCII_SUIT_TO_LOCAL = {
    "S": "黑桃",
    "H": "红桃",
    "C": "梅花",
    "D": "方块",
}


def normalize_rank(rank: str) -> str:
    value = str(rank).upper()
    return "10" if value == "T" else value


def canonical_local_card(card: str) -> str:
    value = str(card)
    if value in CARD_INDEX_54:
        return value
    if value == "B":
        return "小王"
    if value == "R":
        return "大王"
    if len(value) >= 2 and value[0].upper() in ASCII_SUIT_TO_LOCAL:
        local = f"{ASCII_SUIT_TO_LOCAL[value[0].upper()]}{normalize_rank(value[1:])}"
        if local in CARD_INDEX_54:
            return local
    raise ValueError(f"unknown physical card: {card}")


def encode_cards_54(cards: Iterable[str], *, strict_two_decks: bool = True) -> np.ndarray:
    vector = np.zeros(DANZERO_PHYSICAL_ACTION_DIM, dtype=np.float32)
    for raw_card in cards or []:
        if str(raw_card) in PASS_SENTINELS:
            continue
        card = canonical_local_card(raw_card)
        index = CARD_INDEX_54[card]
        vector[index] += 1.0
        if strict_two_decks and vector[index] > 2.0:
            raise ValueError(f"card count exceeds two decks: {card}")
    return vector


def level_rank_text(active_level: int | str) -> str:
    if isinstance(active_level, str):
        rank = normalize_rank(active_level)
        if rank in RANKS:
            return rank
    value = int(active_level)
    if 2 <= value <= 14:
        return RANKS[value - 2]
    raise ValueError(f"invalid active level: {active_level}")


def heart_level_card(active_level: int | str) -> str:
    return f"红桃{level_rank_text(active_level)}"


def canonical_action_type(action_type: str | None) -> str:
    value = str(action_type or "unknown")
    aliases = {
        "None": "pass",
        "none": "pass",
        "pass": "pass",
        "three_with_pair": "full_house",
        "pair_chain": "plate",
        "gangban": "steel",
        "flush_rocket": "straight_flush",
        "joker_bomb": "quad_kings",
    }
    if value in aliases:
        return aliases[value]
    if value.endswith("_bomb") and value != "joker_bomb":
        return "bomb"
    return value if value in ACTION_TYPE_INDEX else "unknown"


def encode_physical_action_54(cards: Sequence[str]) -> np.ndarray:
    return encode_cards_54(cards)


def encode_extended_action(
    cards: Sequence[str],
    *,
    action_type: str | None,
    logic_rank: int,
    active_level: int | str,
    was_lead: bool,
    wildcard_substitution_cards: Sequence[str] | None = None,
) -> np.ndarray:
    physical_cards = [card for card in cards or [] if str(card) not in PASS_SENTINELS]
    physical = encode_physical_action_54(physical_cards)
    action_type_vector = np.zeros(len(CANONICAL_ACTION_TYPES), dtype=np.float32)
    canonical_type = canonical_action_type(action_type)
    action_type_vector[ACTION_TYPE_INDEX[canonical_type]] = 1.0

    logic_rank_vector = np.zeros(DANZERO_ACTION_LOGIC_RANK_DIM, dtype=np.float32)
    logic_rank_vector[max(0, min(DANZERO_ACTION_LOGIC_RANK_DIM - 1, int(logic_rank)))] = 1.0

    size_vector = np.zeros(DANZERO_ACTION_SIZE_DIM, dtype=np.float32)
    size_vector[max(0, min(DANZERO_ACTION_SIZE_DIM - 1, len(physical_cards)))] = 1.0

    normalized_cards = [canonical_local_card(card) for card in physical_cards]
    level_rank = level_rank_text(active_level)
    wildcard = heart_level_card(active_level)
    substitution = encode_cards_54(wildcard_substitution_cards or [], strict_two_decks=False)
    flags = np.asarray(
        [
            1.0 if not physical_cards else 0.0,
            1.0 if canonical_type in {"bomb", "straight_flush", "quad_kings"} else 0.0,
            1.0 if any(card in JOKERS for card in normalized_cards) else 0.0,
            1.0 if any(card not in JOKERS and card.endswith(level_rank) for card in normalized_cards) else 0.0,
            1.0 if wildcard in normalized_cards else 0.0,
            1.0 if wildcard_substitution_cards else 0.0,
            1.0 if was_lead else 0.0,
            0.0 if was_lead else 1.0,
        ],
        dtype=np.float32,
    )
    encoded = np.concatenate(
        [physical, action_type_vector, logic_rank_vector, size_vector, flags, substitution]
    ).astype(np.float32, copy=False)
    if encoded.shape != (DANZERO_EXTENDED_ACTION_DIM,):
        raise RuntimeError(f"extended action dim mismatch: {encoded.shape}")
    return encoded


def _one_hot(index: int, size: int) -> np.ndarray:
    vector = np.zeros(size, dtype=np.float32)
    if 0 <= int(index) < size:
        vector[int(index)] = 1.0
    return vector


def _candidate_cards_and_type(candidate: Any) -> tuple[list[str], str]:
    if isinstance(candidate, dict):
        return list(candidate.get("cards") or candidate.get("physical_cards") or []), canonical_action_type(
            candidate.get("action_type") or candidate.get("type")
        )
    if isinstance(candidate, tuple) and len(candidate) >= 2:
        return list(candidate[1] or []), "unknown"
    return [], "unknown"


def wildcard_capability_flags(
    hand: Sequence[str],
    active_level: int | str,
    legal_candidates: Sequence[Any] | None,
    last_play: Sequence[str] | None,
) -> np.ndarray:
    wildcard = heart_level_card(active_level)
    wildcard_count = Counter(canonical_local_card(card) for card in hand or [])[wildcard]
    flags = np.zeros(12, dtype=np.float32)
    flags[min(2, int(wildcard_count))] = 1.0
    flags[3] = 1.0 if wildcard_count else 0.0
    normalized_last_play = [
        canonical_local_card(card)
        for card in last_play or []
        if str(card) not in PASS_SENTINELS
    ]
    flags[4] = 1.0 if wildcard in normalized_last_play else 0.0
    type_slots = {
        "bomb": 5,
        "straight_flush": 6,
        "straight": 7,
        "full_house": 8,
        "plate": 9,
        "steel": 10,
    }
    for candidate in legal_candidates or []:
        cards, action_type = _candidate_cards_and_type(candidate)
        normalized = [canonical_local_card(card) for card in cards]
        if wildcard not in normalized:
            continue
        slot = type_slots.get(action_type, 11)
        flags[slot] = 1.0
    return flags


def encode_compact_state_513(
    game: Any,
    player_id: int,
    *,
    legal_candidates: Sequence[Any] | None = None,
    team_level: int | str | None = None,
    opponent_level: int | str | None = None,
) -> np.ndarray:
    player_id = int(player_id)
    if not 0 <= player_id < 4:
        raise ValueError(f"invalid player id: {player_id}")
    players = game.players
    self_hand = list(players[player_id].hand)
    played_by_player = [list(player.played_cards) for player in players]
    all_played = [card for cards in played_by_player for card in cards]
    remaining = np.full(DANZERO_PHYSICAL_ACTION_DIM, 2.0, dtype=np.float32)
    remaining -= encode_cards_54(self_hand)
    remaining -= encode_cards_54(all_played)
    if np.any(remaining < 0.0):
        raise ValueError("remaining-card encoding became negative")

    teammate = (player_id + 2) % 4
    other_players = [(player_id + offset) % 4 for offset in (1, 2, 3)]
    teammate_last = (
        np.full(DANZERO_PHYSICAL_ACTION_DIM, -1.0, dtype=np.float32)
        if teammate in game.ranking
        else encode_cards_54(list(players[teammate].last_played_cards or []))
    )
    sections: list[np.ndarray] = [
        encode_cards_54(self_hand),
        remaining,
        encode_cards_54(list(game.last_play or [])),
        teammate_last,
    ]
    for other in other_players:
        sections.append(_one_hot(min(27, len(players[other].hand)), 28))
    for other in other_players:
        sections.append(encode_cards_54(played_by_player[other]))

    level_value = int(game.active_level)
    team_level_value = int(team_level) if team_level is not None else level_value
    opponent_level_value = int(opponent_level) if opponent_level is not None else level_value
    sections.append(_one_hot(team_level_value - 2, 13))
    sections.append(_one_hot(opponent_level_value - 2, 13))
    sections.append(_one_hot(level_value - 2, 13))
    sections.append(
        wildcard_capability_flags(
            self_hand,
            level_value,
            legal_candidates,
            list(game.last_play or []),
        )
    )

    encoded = np.concatenate(sections).astype(np.float32, copy=False)
    if encoded.shape != (DANZERO_COMPACT_STATE_DIM,):
        raise RuntimeError(f"compact state dim mismatch: {encoded.shape}")
    if not np.isfinite(encoded).all():
        raise ValueError("compact state contains non-finite values")
    return encoded


def encode_website_compact_state_487(
    game: Any,
    player_id: int,
    *,
    legal_candidates: Sequence[Any] | None = None,
) -> np.ndarray:
    paper_state = encode_compact_state_513(
        game,
        player_id,
        legal_candidates=legal_candidates,
    )
    encoded = np.concatenate([paper_state[:462], paper_state[488:]]).astype(np.float32, copy=False)
    if encoded.shape != (DANZERO_WEBSITE_COMPACT_STATE_DIM,):
        raise RuntimeError(f"website compact state dim mismatch: {encoded.shape}")
    return encoded
