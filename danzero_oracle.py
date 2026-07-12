from __future__ import annotations

from typing import Any

from collections import Counter
import itertools

import play_step_0902 as engine


ORACLE_VERSION = "structured_exhaustive_website_oracle_v1"
ORACLE_EXHAUSTIVE = True


def physical_key(cards: list[str]) -> tuple[tuple[str, int], ...]:
    return tuple(sorted(Counter(cards).items()))


def candidates(
    adaptive: Any,
    game: Any,
    components: dict,
    hand: list[str],
    last_play: list[str],
    was_lead: bool,
) -> list[tuple[int, list[str]]]:
    physical_candidates, _metadata = structured_exhaustive_candidates(
        adaptive,
        game,
        components,
        hand,
        last_play,
        was_lead,
    )
    return physical_candidates


def bounded_candidates(
    adaptive: Any,
    game: Any,
    components: dict,
    hand: list[str],
    last_play: list[str],
    was_lead: bool,
) -> list[tuple[int, list[str]]]:
    _oracle, physical_candidates = adaptive.offline_oracle_candidates_fast(
        game,
        components,
        hand,
        last_play,
        was_lead,
    )
    return [(int(action_id), list(cards)) for action_id, cards in physical_candidates]


def exhaustive_candidates(
    adaptive: Any,
    game: Any,
    components: dict,
    hand: list[str],
    last_play: list[str],
    was_lead: bool,
) -> tuple[list[tuple[int, list[str]]], dict]:
    level = adaptive.website_level_from_local_level(int(game.active_level))
    website_hand = adaptive.local_cards_to_website(hand)
    website_last = adaptive.local_cards_to_website(last_play)
    unique: dict[tuple[tuple[str, int], ...], tuple[int, list[str]]] = {}
    mapping_fail_count = 0
    interpretation_count = 0
    if not was_lead:
        unique[()] = (0, [])
    for option in engine.legal_play_options(website_hand, level):
        website_cards = list(option.cards)
        legal_infos = (
            engine.canonical_table_infos(website_cards, level)
            if was_lead
            else engine.safe_follow_infos(website_cards, website_last, level)
        )
        for info in legal_infos:
            interpretation_count += 1
            action_id = adaptive.website_action_id_for_info(components, website_cards, info, level)
            if action_id is None:
                mapping_fail_count += 1
                continue
            local_cards = adaptive.website_cards_to_local(website_cards)
            unique.setdefault(physical_key(local_cards), (int(action_id), local_cards))
    return list(unique.values()), {
        "oracle_version": "exhaustive_engine_oracle_audit_v1",
        "oracle_exhaustive": True,
        "interpretation_count": interpretation_count,
        "mapping_fail_count": mapping_fail_count,
    }


def _unique_card_selections(cards: list[str], count: int) -> list[tuple[str, ...]]:
    if count < 0 or count > len(cards):
        return []
    if count == 0:
        return [()]
    return sorted(set(itertools.combinations(sorted(cards), count)))


def structured_exhaustive_candidates(
    adaptive: Any,
    game: Any,
    components: dict,
    hand: list[str],
    last_play: list[str],
    was_lead: bool,
) -> tuple[list[tuple[int, list[str]]], dict]:
    level = adaptive.website_level_from_local_level(int(game.active_level))
    website_hand = adaptive.local_cards_to_website(hand)
    website_last = adaptive.local_cards_to_website(last_play)
    wild_card = "H" + level
    wild_count = website_hand.count(wild_card)
    wilds = [wild_card] * wild_count
    by_rank: dict[str, list[str]] = {rank: [] for rank in engine.RANKS}
    jokers = Counter(card for card in website_hand if card in {"B", "R"})
    for card in website_hand:
        if card in {"B", "R", wild_card}:
            continue
        by_rank[card[1:]].append(card)

    raw: set[tuple[str, ...]] = set()

    def add_raw(cards: tuple[str, ...] | list[str]) -> None:
        raw.add(tuple(engine.sort_cards(list(cards), level)))

    for card in set(website_hand):
        add_raw([card])

    for size in (2, 3):
        for rank in engine.RANKS:
            for used_wilds in range(wild_count + 1):
                normal_count = size - used_wilds
                for selected in _unique_card_selections(by_rank[rank], normal_count):
                    add_raw(selected + tuple(wilds[:used_wilds]))
        for joker in ("B", "R"):
            if jokers[joker] >= size:
                add_raw([joker] * size)

    for triple_rank in engine.RANKS:
        for pair_rank in engine.RANKS:
            if pair_rank == triple_rank:
                continue
            for triple_count in range(0, 4):
                for pair_count in range(0, 3):
                    used_wilds = (3 - triple_count) + (2 - pair_count)
                    if used_wilds > wild_count:
                        continue
                    for triple_cards in _unique_card_selections(by_rank[triple_rank], triple_count):
                        for pair_cards in _unique_card_selections(by_rank[pair_rank], pair_count):
                            add_raw(triple_cards + pair_cards + tuple(wilds[:used_wilds]))

    for sequence in engine.sequence_windows(5):
        for missing_count in range(wild_count + 1):
            for missing in itertools.combinations(sequence, missing_count):
                present = [rank for rank in sequence if rank not in set(missing)]
                choices = [[card for card in by_rank[rank]] for rank in present]
                if all(choices):
                    for selected in itertools.product(*choices):
                        add_raw(tuple(selected) + tuple(wilds[:missing_count]))
        for suit in engine.SUITS:
            for missing_count in range(wild_count + 1):
                for missing in itertools.combinations(sequence, missing_count):
                    present = [rank for rank in sequence if rank not in set(missing)]
                    choices = [[card for card in by_rank[rank] if card.startswith(suit)] for rank in present]
                    if all(choices):
                        for selected in itertools.product(*choices):
                            add_raw(tuple(selected) + tuple(wilds[:missing_count]))

    for sequence, target_count in (
        *((sequence, 2) for sequence in engine.sequence_windows(3)),
        *((sequence, 3) for sequence in engine.sequence_windows(2)),
    ):
        count_ranges = [range(0, target_count + 1) for _ in sequence]
        for counts in itertools.product(*count_ranges):
            used_wilds = sum(target_count - count for count in counts)
            if used_wilds > wild_count:
                continue
            selections = [
                _unique_card_selections(by_rank[rank], count)
                for rank, count in zip(sequence, counts)
            ]
            if all(selections):
                for selected_groups in itertools.product(*selections):
                    cards = tuple(card for group in selected_groups for card in group)
                    add_raw(cards + tuple(wilds[:used_wilds]))

    for rank in engine.RANKS:
        for normal_count in range(len(by_rank[rank]) + 1):
            for used_wilds in range(wild_count + 1):
                if normal_count + used_wilds < 4:
                    continue
                for selected in _unique_card_selections(by_rank[rank], normal_count):
                    add_raw(selected + tuple(wilds[:used_wilds]))
    if jokers["B"] >= 2 and jokers["R"] >= 2:
        add_raw(["B", "B", "R", "R"])

    unique: dict[tuple[tuple[str, int], ...], tuple[int, list[str]]] = {}
    mapping_fail_count = 0
    interpretation_count = 0
    if not was_lead:
        unique[()] = (0, [])
    for website_cards_tuple in raw:
        website_cards = list(website_cards_tuple)
        legal_infos = (
            engine.canonical_table_infos(website_cards, level)
            if was_lead
            else engine.safe_follow_infos(website_cards, website_last, level)
        )
        for info in legal_infos:
            interpretation_count += 1
            action_id = adaptive.website_action_id_for_info(components, website_cards, info, level)
            if action_id is None:
                mapping_fail_count += 1
                continue
            local_cards = adaptive.website_cards_to_local(website_cards)
            unique.setdefault(physical_key(local_cards), (int(action_id), local_cards))
    return list(unique.values()), {
        "oracle_version": "structured_exhaustive_website_oracle_v1",
        "oracle_exhaustive": True,
        "raw_candidate_count": len(raw),
        "interpretation_count": interpretation_count,
        "mapping_fail_count": mapping_fail_count,
    }
