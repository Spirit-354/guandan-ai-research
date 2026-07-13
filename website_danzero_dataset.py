from __future__ import annotations

from collections import Counter
from collections import deque
import copy
import hashlib
import json
import math
from pathlib import Path
import random
from datetime import datetime, timezone
from typing import Any, Iterable

import numpy as np


DATASET_FORMAT = "website_danzero_action_value_v1"
STATE_DIM = 513
ACTION_DIM = 54


def _cards_key(cards: Iterable[str]) -> tuple[tuple[str, int], ...]:
    return tuple(sorted(Counter(cards).items()))


def _is_finite_vector(values: Any, expected_dim: int) -> bool:
    return (
        isinstance(values, list)
        and len(values) == expected_dim
        and all(isinstance(value, (int, float)) and math.isfinite(float(value)) for value in values)
    )


def _team_equal(left: Any, right: Any) -> bool:
    return left is not None and right is not None and str(left) == str(right)


def _elo_band(elo: Any) -> str | None:
    try:
        value = int(float(elo))
    except (TypeError, ValueError):
        return None
    floor = (value // 100) * 100
    return f"{floor}-{floor + 99}"


def _iter_log_paths(raw_dirs: str) -> list[Path]:
    paths: list[Path] = []
    for raw in (item.strip() for item in raw_dirs.split(",")):
        if not raw:
            continue
        path = Path(raw)
        if path.is_file():
            paths.append(path)
        elif path.is_dir():
            paths.extend(sorted(path.glob("research_game_*.json")))
    return sorted(set(paths), key=lambda item: str(item))


def _first_player(final_state: dict) -> int | None:
    for item in final_state.get("trick_history") or []:
        if not isinstance(item, (list, tuple)) or len(item) < 2 or not item[1]:
            continue
        try:
            seat = int(item[0])
        except (TypeError, ValueError):
            continue
        if 0 <= seat < 4:
            return seat
    return None


def _state_fingerprint(state: list[float]) -> str:
    packed = json.dumps(state, separators=(",", ":"), ensure_ascii=True).encode("ascii")
    return hashlib.sha256(packed).hexdigest()


def _assign_provisional_splits(samples: list[dict]) -> dict[str, str]:
    sessions: dict[str, str] = {}
    session_games: dict[str, set[str]] = {}
    for sample in samples:
        session = str(sample.get("source_session") or "unknown")
        completed_at = str(sample.get("completed_at") or "")
        session_games.setdefault(session, set()).add(str(sample.get("game_id")))
        current = sessions.get(session)
        if current is None or completed_at < current:
            sessions[session] = completed_at
    ordered = sorted(sessions, key=lambda name: (sessions[name], name))
    if len(ordered) < 3:
        return {name: "train" for name in ordered}
    assignments = {name: "train" for name in ordered}
    target_games = max(1, math.ceil(len({sample.get("game_id") for sample in samples}) * 0.15))
    assigned_locked = 0
    assigned_development = 0
    for name in reversed(ordered):
        if assigned_locked < target_games:
            assignments[name] = "locked_test"
            assigned_locked += len(session_games[name])
        elif assigned_development < target_games:
            assignments[name] = "development"
            assigned_development += len(session_games[name])
    return assignments


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _freeze_dataset(
    paths: list[Path],
    samples: list[dict],
    summary: dict,
    manifest_path: Path,
    data_card_path: Path,
) -> None:
    if not summary.get("coverage_gate_passed"):
        raise RuntimeError("website dataset coverage gate must pass before split freeze")
    split_game_ids = {
        split: sorted(
            {str(sample.get("game_id")) for sample in samples if sample.get("split") == split}
        )
        for split in ("train", "development", "locked_test")
    }
    if any(not game_ids for game_ids in split_game_ids.values()):
        raise RuntimeError("train, development, and locked_test must all contain complete games")
    overlap = (
        set(split_game_ids["train"]) & set(split_game_ids["development"])
        | set(split_game_ids["train"]) & set(split_game_ids["locked_test"])
        | set(split_game_ids["development"]) & set(split_game_ids["locked_test"])
    )
    if overlap:
        raise RuntimeError(f"game split overlap detected: {sorted(overlap)}")
    immutable = {
        "schema_version": "website_dataset_split_manifest_v1",
        "dataset_format": DATASET_FORMAT,
        "split_policy": "temporal_collection_sessions_target_70_15_15",
        "split_grouping": summary.get("split_grouping"),
        "session_split_assignments": summary.get("session_split_assignments"),
        "split_game_ids": split_game_ids,
        "source_files": [
            {"path": str(path), "sha256": _file_sha256(path), "size_bytes": path.stat().st_size}
            for path in paths
        ],
        "state_dim": STATE_DIM,
        "action_dim": ACTION_DIM,
        "metric_source": "leaderboard_elo",
        "behavior_value_scope": "Q(s,a_behavior)_only",
        "locked_test_policy": "never_train_tune_select_or_design",
    }
    content_hash = hashlib.sha256(
        json.dumps(immutable, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    manifest = {
        **immutable,
        "content_hash": content_hash,
        "frozen_at_utc": datetime.now(timezone.utc).isoformat(),
    }
    if manifest_path.exists():
        existing = json.loads(manifest_path.read_text(encoding="utf-8"))
        if existing.get("content_hash") != content_hash:
            raise RuntimeError("existing split manifest differs; frozen splits cannot be rewritten")
        manifest = existing
    else:
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    for sample in samples:
        sample["split_status"] = "frozen"
        sample["split_manifest_content_hash"] = content_hash
    summary["split_status"] = "frozen"
    summary["split_manifest_path"] = str(manifest_path)
    summary["split_manifest_content_hash"] = content_hash
    summary["data_card_path"] = str(data_card_path)
    summary["capability_evidence_eligible"] = False
    data_card = {
        "schema_version": "website_dataset_card_v1",
        "manifest_path": str(manifest_path),
        "manifest_content_hash": content_hash,
        "summary": summary,
        "capability_limit": (
            "Behavior logs supervise Q(s,a_behavior) only; unexecuted candidates have no factual return label."
        ),
        "hidden_information_policy": "decision_time_information_set_only",
        "locked_test_access": "prohibited_for_training_tuning_checkpoint_selection_and_rule_design",
        "formal_website_control_data_reuse": "prohibited_until_declared_study_concludes",
    }
    data_card_path.parent.mkdir(parents=True, exist_ok=True)
    data_card_path.write_text(json.dumps(data_card, ensure_ascii=False, indent=2), encoding="utf-8")


def _coverage_summary(samples: list[dict]) -> dict:
    game_ids = {str(sample.get("game_id")) for sample in samples}
    state_fingerprints = [str(sample.get("state_fingerprint")) for sample in samples]
    duplicate_count = len(state_fingerprints) - len(set(state_fingerprints))
    split_games: dict[str, set[str]] = {"train": set(), "development": set(), "locked_test": set()}
    split_decisions = Counter()
    first_players = Counter()
    levels = Counter()
    elo_bands = Counter()
    tables = Counter()
    seats = Counter()
    for sample in samples:
        split = str(sample.get("split") or "unassigned")
        split_decisions[split] += 1
        if split in split_games:
            split_games[split].add(str(sample.get("game_id")))
        first_players[str(sample.get("first_player"))] += 1
        levels[str(sample.get("level"))] += 1
        elo_bands[str(sample.get("elo_band_100"))] += 1
        tables[str(sample.get("robot_table_signature"))] += 1
        seats[str(sample.get("your_seat"))] += 1
    outcome_counts = Counter(str(sample.get("outcome")) for sample in samples)
    coverage = {
        "independent_games": len(game_ids),
        "decisions": len(samples),
        "candidate_actions": sum(int(sample.get("legal_action_count") or 0) for sample in samples),
        "win_decisions": outcome_counts.get("win", 0),
        "loss_decisions": outcome_counts.get("loss", 0),
        "seat_coverage": dict(seats),
        "first_player_coverage": dict(first_players),
        "level_card_coverage_count": sum(bool(sample.get("level_card_available")) for sample in samples),
        "wildcard_coverage_count": sum(bool(sample.get("heart_level_wildcard_available")) for sample in samples),
        "lead_count": sum(bool(sample.get("was_lead")) for sample in samples),
        "follow_count": sum(bool(sample.get("was_follow")) for sample in samples),
        "endgame_count": sum(bool(sample.get("is_endgame")) for sample in samples),
        "bomb_state_count": sum(bool(sample.get("bomb_candidate_available")) for sample in samples),
        "level_distribution": dict(levels),
        "elo_band_coverage": dict(elo_bands),
        "robot_table_coverage": dict(tables),
        "source_session_count": len({sample.get("source_session") for sample in samples}),
        "duplicate_state_count": duplicate_count,
        "duplicate_state_rate": duplicate_count / len(samples) if samples else 0.0,
        "information_set_consistent_count": sum(
            bool(sample.get("information_set_consistent")) for sample in samples
        ),
        "information_set_inconsistent_count": sum(
            not bool(sample.get("information_set_consistent")) for sample in samples
        ),
        "information_set_consistent_rate": (
            sum(bool(sample.get("information_set_consistent")) for sample in samples) / len(samples)
            if samples
            else 0.0
        ),
        "split_game_counts": {name: len(ids) for name, ids in split_games.items()},
        "split_decision_counts": dict(split_decisions),
    }
    coverage["coverage_gate_passed"] = bool(
        coverage["independent_games"] >= 50
        and outcome_counts.get("win", 0) > 0
        and outcome_counts.get("loss", 0) > 0
        and len([key for key in first_players if key != "None"]) == 4
        and coverage["wildcard_coverage_count"] > 0
        and coverage["lead_count"] > 0
        and coverage["follow_count"] > 0
        and coverage["endgame_count"] > 0
        and coverage["bomb_state_count"] > 0
        and len(elo_bands) >= 2
        and all(coverage["split_game_counts"].get(name, 0) > 0 for name in split_games)
    )
    coverage["information_set_rollout_gate_passed"] = bool(
        coverage["coverage_gate_passed"]
        and coverage["information_set_consistent_rate"] >= 0.90
        and coverage["information_set_consistent_count"] >= 500
    )
    return coverage


def _record_rejection(record: dict, shadow_summary: dict) -> str | None:
    final_state = record.get("final_state") or {}
    bot_evidence = final_state.get("_bot_table_evidence") or {}
    if not record.get("game_counted"):
        return "game_not_counted"
    if not final_state.get("completed"):
        return "game_not_completed"
    if record.get("metric_source") != "leaderboard_elo":
        return "metric_not_leaderboard_elo"
    if not bot_evidence.get("bot_table_verified"):
        return "bot_table_not_verified"
    if not shadow_summary.get("threshold_passed"):
        return "shadow_integrity_failed"
    if int(shadow_summary.get("model_controlled_action_count") or 0):
        return "model_controlled_submission_present"
    return None


def _decision_sample(record: dict, decision: dict) -> tuple[dict | None, str | None]:
    shadow = decision.get("website_shadow") or {}
    submitted = shadow.get("submitted_action") or {}
    state = shadow.get("paper_state_513")
    action = submitted.get("physical_action_54")
    candidates = shadow.get("legal_candidates") or []
    if not shadow:
        return None, "missing_shadow_audit"
    if not shadow.get("oracle_exhaustive"):
        return None, "oracle_not_exhaustive"
    if not _is_finite_vector(state, STATE_DIM):
        return None, "invalid_state_vector"
    if not _is_finite_vector(action, ACTION_DIM):
        return None, "invalid_action_vector"
    if not candidates:
        return None, "empty_legal_candidates"

    candidate_vectors: list[list[float]] = []
    candidate_metadata: list[dict] = []
    chosen_key = _cards_key(submitted.get("cards") or [])
    chosen_found = False
    for candidate in candidates:
        vector = candidate.get("physical_action_54")
        if not _is_finite_vector(vector, ACTION_DIM):
            return None, "invalid_candidate_vector"
        cards = list(candidate.get("cards") or [])
        candidate_vectors.append([float(value) for value in vector])
        candidate_metadata.append(
            {
                "cards": cards,
                "action_type": candidate.get("action_type"),
                "rank": candidate.get("rank"),
                "size": int(candidate.get("size") or 0),
            }
        )
        if _cards_key(cards) == chosen_key:
            chosen_found = True
    if not chosen_found:
        return None, "chosen_action_not_in_candidates"
    if not submitted.get("cards_in_hand") or not submitted.get("local_legal"):
        return None, "chosen_action_not_locally_legal"
    if not submitted.get("oracle_match") or submitted.get("materialization_fail"):
        return None, "chosen_action_oracle_or_materialization_error"
    if not (
        shadow.get("submitted_action_server_success") is True
        or shadow.get("submitted_action_acceptance_inferred") is True
    ):
        return None, "submission_not_confirmed"

    final_state = record.get("final_state") or {}
    your_team = final_state.get("your_team", shadow.get("your_team"))
    winner_team = final_state.get("winner_team")
    won = _team_equal(your_team, winner_team)
    return {
        "game_id": str(record.get("game_id")),
        "profile": record.get("profile"),
        "scenario": decision.get("scenario") or record.get("scenario"),
        "turn_index": decision.get("turn_index") or decision.get("turn"),
        "level": shadow.get("level") or decision.get("level"),
        "was_lead": bool(shadow.get("was_lead")),
        "was_follow": bool(shadow.get("was_follow")),
        "hand_before": list(decision.get("hand") or []),
        "hand_counts": [int(value) for value in (decision.get("hand_counts") or [])],
        "last_play_before_action": list(decision.get("last_play") or []),
        "last_player": decision.get("last_player"),
        "current_turn": decision.get("current_turn"),
        "trick_index": decision.get("trick_index"),
        "state": [float(value) for value in state],
        "state_dim": STATE_DIM,
        "chosen_action": [float(value) for value in action],
        "action_dim": ACTION_DIM,
        "chosen_cards": list(submitted.get("cards") or []),
        "chosen_action_type": submitted.get("action_type"),
        "chosen_action_rank": submitted.get("logic_rank"),
        "legal_actions": candidate_vectors,
        "legal_action_metadata": candidate_metadata,
        "legal_action_count": len(candidate_vectors),
        "team_reward": 1.0 if won else -1.0,
        "outcome": "win" if won else "loss",
        "value_target_scope": "terminal_team_reward_for_chosen_action_only",
        "elo_before": record.get("elo_before"),
        "elo_after": record.get("elo_after"),
        "elo_delta": record.get("elo_delta"),
        "elo_band_100": _elo_band(record.get("elo_before")),
        "metric_source": "leaderboard_elo",
        "bot_table_verified": True,
        "state_encoding_version": shadow.get("paper_state_encoding_version"),
        "action_encoding_version": shadow.get("legal_candidate_action_encoding_version"),
        "source_schema_version": shadow.get("schema_version"),
    }, None


def write_dataset(path: Path, samples: list[dict], summary: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    suffix = path.suffix.lower()
    if suffix == ".jsonl":
        with path.open("w", encoding="utf-8") as handle:
            for sample in samples:
                handle.write(json.dumps(sample, ensure_ascii=False, separators=(",", ":")) + "\n")
        path.with_suffix(path.suffix + ".summary.json").write_text(
            json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        return
    if suffix not in {".pt", ".pth"}:
        raise RuntimeError("website DanZero dataset path must end with .jsonl, .pt, or .pth")
    try:
        import torch
    except ImportError as exc:
        raise RuntimeError("PyTorch is required to write .pt/.pth datasets") from exc
    torch.save({"format": DATASET_FORMAT, "summary": summary, "samples": samples}, path)


def _partition_path(path: Path, role: str) -> Path:
    return path.with_name(f"{path.stem}.{role}{path.suffix}")


def _write_frozen_partitions(path: Path, samples: list[dict], summary: dict) -> dict:
    train_dev_all = [sample for sample in samples if sample.get("split") in {"train", "development"}]
    locked_all = [sample for sample in samples if sample.get("split") == "locked_test"]
    train_dev = [sample for sample in train_dev_all if sample.get("information_set_consistent")]
    locked = [sample for sample in locked_all if sample.get("information_set_consistent")]
    if not train_dev or not locked:
        raise RuntimeError("frozen dataset requires physical train_dev and locked_test partitions")
    train_dev_path = _partition_path(path, "train_dev")
    locked_path = _partition_path(path, "locked_test")
    train_dev_summary = copy.deepcopy(summary)
    train_dev_summary.update(
        {
            "partition_role": "train_development",
            "contains_locked_test_samples": False,
            "sample_count": len(train_dev),
            "excluded_locked_test_sample_count": len(locked_all),
            "excluded_locked_test_game_count": len(
                {str(sample.get("game_id")) for sample in locked_all}
            ),
            "excluded_inconsistent_train_dev_sample_count": len(train_dev_all) - len(train_dev),
            "all_samples_information_set_consistent": True,
        }
    )
    locked_summary = copy.deepcopy(summary)
    locked_summary.update(
        {
            "partition_role": "locked_test",
            "contains_training_samples": False,
            "sample_count": len(locked),
            "excluded_inconsistent_locked_test_sample_count": len(locked_all) - len(locked),
            "all_samples_information_set_consistent": True,
        }
    )
    write_dataset(train_dev_path, train_dev, train_dev_summary)
    write_dataset(locked_path, locked, locked_summary)
    return {
        "train_dev_path": str(train_dev_path),
        "locked_test_path": str(locked_path),
        "train_dev_sample_count": len(train_dev),
        "locked_test_sample_count": len(locked),
        "excluded_inconsistent_train_dev_sample_count": len(train_dev_all) - len(train_dev),
        "excluded_inconsistent_locked_test_sample_count": len(locked_all) - len(locked),
    }


def build_dataset(
    raw_dirs: str,
    output_path: str,
    *,
    freeze_splits: bool = False,
    split_manifest_path: str = "website_dataset_split_manifest.json",
    data_card_path: str = "website_dataset_card.json",
) -> dict:
    paths = _iter_log_paths(raw_dirs)
    samples: list[dict] = []
    reject_reasons: Counter[str] = Counter()
    accepted_games = 0
    accepted_wins = 0
    seen_decisions: set[tuple[str, Any]] = set()
    candidate_counts: list[int] = []

    for path in paths:
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            reject_reasons["unreadable_log"] += 1
            continue
        shadow_summary = record.get("website_shadow_summary") or {}
        rejection = _record_rejection(record, shadow_summary)
        if rejection:
            reject_reasons[rejection] += 1
            continue
        game_samples: list[dict] = []
        game_failed = False
        final_state = record.get("final_state") or {}
        bot_evidence = final_state.get("_bot_table_evidence") or {}
        source_session = path.parent.name
        first_player = _first_player(final_state)
        table_signature = "|".join(str(item) for item in (bot_evidence.get("observed_seats") or []))
        for decision in record.get("decisions") or []:
            sample, reason = _decision_sample(record, decision)
            if reason:
                reject_reasons[f"decision:{reason}"] += 1
                game_failed = True
                break
            hand = list(decision.get("hand") or [])
            level = str(sample.get("level"))
            candidate_types = {
                str(item.get("action_type") or "") for item in sample.get("legal_action_metadata") or []
            }
            sample.update(
                {
                    "completed_at": record.get("completed_at"),
                    "source_session": source_session,
                    "source_time_block": str(record.get("completed_at") or "")[:10],
                    "robot_table_signature": table_signature,
                    "your_seat": final_state.get("your_seat"),
                    "first_player": first_player,
                    "level_card_available": any(
                        card not in {"B", "R"} and str(card)[1:] == level for card in hand
                    ),
                    "heart_level_wildcard_available": f"H{level}" in hand,
                    "is_endgame": "endgame" in str(sample.get("scenario") or "").lower()
                    or min(list(decision.get("hand_counts") or [27])) <= 6,
                    "bomb_candidate_available": any(
                        action_type in {"bomb", "straight_flush", "quad_kings"}
                        or action_type.endswith("_bomb")
                        for action_type in candidate_types
                    ),
                    "state_fingerprint": _state_fingerprint(sample["state"]),
                    "information_set_unknown_count": int(round(sum(sample["state"][54:108]))),
                    "information_set_expected_unknown_count": (
                        sum(int(value) for value in (decision.get("hand_counts") or []))
                        - int((decision.get("hand_counts") or [0])[int(final_state.get("your_seat", 0))])
                    ),
                    "public_history_source": (decision.get("website_shadow") or {}).get(
                        "public_history_source", "legacy_server_snapshot"
                    ),
                    "public_history_consistent": bool(
                        (decision.get("website_shadow") or {}).get("public_history_consistent", True)
                    ),
                }
            )
            sample["information_set_consistent"] = bool(
                sample["information_set_unknown_count"]
                == sample["information_set_expected_unknown_count"]
                and sample["public_history_consistent"]
            )
            key = (sample["game_id"], sample["turn_index"])
            if key in seen_decisions:
                reject_reasons["duplicate_decision"] += 1
                continue
            game_samples.append(sample)
        if game_failed or not game_samples:
            reject_reasons["game_has_no_accepted_decisions"] += 1
            continue
        for sample in game_samples:
            seen_decisions.add((sample["game_id"], sample["turn_index"]))
            candidate_counts.append(sample["legal_action_count"])
        samples.extend(game_samples)
        accepted_games += 1
        accepted_wins += int(game_samples[0]["outcome"] == "win")

    split_assignments = _assign_provisional_splits(samples)
    for sample in samples:
        sample["split"] = split_assignments.get(str(sample.get("source_session")), "unassigned")
        sample["split_status"] = "provisional"
    coverage = _coverage_summary(samples)

    summary = {
        "format": DATASET_FORMAT,
        "source_log_paths": raw_dirs,
        "output_path": str(output_path),
        "files_scanned": len(paths),
        "accepted_games": accepted_games,
        "rejected_files_or_games": len(paths) - accepted_games,
        "accepted_decisions": len(samples),
        "wins": accepted_wins,
        "losses": accepted_games - accepted_wins,
        "legal_candidate_total": sum(candidate_counts),
        "average_legal_candidate_count": (
            sum(candidate_counts) / len(candidate_counts) if candidate_counts else 0.0
        ),
        "max_legal_candidate_count": max(candidate_counts, default=0),
        "reject_reason_counts": dict(sorted(reject_reasons.items())),
        "state_dim": STATE_DIM,
        "action_dim": ACTION_DIM,
        "metric_source": "leaderboard_elo",
        "bot_tables_only": True,
        "model_controlled_action_count": 0,
        "split_status": "provisional",
        "split_grouping": "complete_game+source_session+time_block+robot_table_signature",
        "session_split_assignments": split_assignments,
        "coverage": coverage,
        "coverage_gate_passed": coverage["coverage_gate_passed"],
        "capability_evidence_eligible": False,
        "behavior_value_scope": "Q(s,a_behavior)_only",
        "threshold_passed": bool(paths and accepted_games and samples),
    }
    if freeze_splits:
        _freeze_dataset(
            paths,
            samples,
            summary,
            Path(split_manifest_path),
            Path(data_card_path),
        )
        summary["partition_role"] = "complete_bundle"
        summary["contains_locked_test_samples"] = True
        summary["physical_partitions"] = _write_frozen_partitions(
            Path(output_path), samples, summary
        )
    write_dataset(Path(output_path), samples, summary)
    return summary


def load_dataset(path: Path) -> tuple[list[dict], dict]:
    suffix = path.suffix.lower()
    if suffix == ".jsonl":
        samples = [
            json.loads(line)
            for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        summary_path = path.with_suffix(path.suffix + ".summary.json")
        summary = json.loads(summary_path.read_text(encoding="utf-8")) if summary_path.exists() else {}
        return samples, summary
    if suffix not in {".pt", ".pth"}:
        raise RuntimeError("website DanZero dataset path must end with .jsonl, .pt, or .pth")
    try:
        import torch
    except ImportError as exc:
        raise RuntimeError("PyTorch is required to read .pt/.pth datasets") from exc
    try:
        payload = torch.load(path, map_location="cpu", weights_only=False)
    except TypeError:
        payload = torch.load(path, map_location="cpu")
    if payload.get("format") != DATASET_FORMAT:
        raise RuntimeError(f"unexpected website dataset format: {payload.get('format')!r}")
    return list(payload.get("samples") or []), dict(payload.get("summary") or {})


def _resolve_device(requested: str) -> tuple[Any, dict]:
    try:
        import torch
    except ImportError as exc:
        raise RuntimeError("website DanZero training requires PyTorch") from exc
    cuda_available = bool(torch.cuda.is_available())
    fallback = requested == "cuda" and not cuda_available
    actual = "cuda" if requested == "cuda" and cuda_available else "cpu"
    return torch.device(actual), {
        "backend": "torch",
        "requested_device": requested,
        "actual_device": actual,
        "device_fallback": fallback,
        "torch_available": True,
        "cuda_available": cuda_available,
    }


def _split_game_ids(samples: list[dict], validation_split: float, seed: int) -> tuple[set[str], set[str]]:
    game_ids = sorted({str(sample.get("game_id")) for sample in samples})
    if len(game_ids) < 2:
        raise RuntimeError("at least two games are required for a game-level train/validation split")
    rng = random.Random(seed)
    rng.shuffle(game_ids)
    validation_count = max(1, min(len(game_ids) - 1, round(len(game_ids) * validation_split)))
    validation_ids = set(game_ids[:validation_count])
    return set(game_ids[validation_count:]), validation_ids


def _evaluate(model: Any, samples: list[dict], device: Any, batch_size: int) -> dict:
    import torch
    import torch.nn.functional as functional

    if not samples:
        return {"loss": None, "sign_accuracy": None}
    losses: list[float] = []
    correct = 0
    model.eval()
    with torch.no_grad():
        for start in range(0, len(samples), batch_size):
            batch = samples[start : start + batch_size]
            states = torch.tensor(np.asarray([item["state"] for item in batch], dtype=np.float32), device=device)
            actions = torch.tensor(
                np.asarray([item["chosen_action"] for item in batch], dtype=np.float32), device=device
            )
            targets = torch.tensor(
                [float(item["team_reward"]) for item in batch], dtype=torch.float32, device=device
            )
            predictions = model(states, actions)
            losses.extend(functional.mse_loss(predictions, targets, reduction="none").cpu().tolist())
            correct += int(((predictions >= 0) == (targets >= 0)).sum().item())
    return {"loss": sum(losses) / len(losses), "sign_accuracy": correct / len(samples)}


def train_action_value(args: Any) -> dict:
    import torch
    import torch.nn.functional as functional

    import danzero_dmc

    dataset_path = Path(args.train_website_danzero_action_value)
    samples, dataset_summary = load_dataset(dataset_path)
    invalid_count = sum(
        not _is_finite_vector(sample.get("state"), STATE_DIM)
        or not _is_finite_vector(sample.get("chosen_action"), ACTION_DIM)
        or float(sample.get("team_reward", 0.0)) not in {-1.0, 1.0}
        or sample.get("metric_source") != "leaderboard_elo"
        or not sample.get("bot_table_verified")
        or not sample.get("information_set_consistent")
        for sample in samples
    )
    if invalid_count:
        raise RuntimeError(f"website DanZero dataset contains {invalid_count} invalid samples")
    if any(sample.get("split") not in {"train", "development", "locked_test"} for sample in samples):
        raise RuntimeError("website dataset must contain explicit train/development/locked_test splits")
    formal_frozen = (
        dataset_summary.get("split_status") == "frozen"
        and dataset_summary.get("partition_role") == "train_development"
        and dataset_summary.get("contains_locked_test_samples") is False
    )
    if not formal_frozen and not args.website_danzero_allow_provisional_smoke:
        raise RuntimeError(
            "formal training requires the frozen train_dev partition without locked-test samples; "
            "use --website-danzero-allow-provisional-smoke only for plumbing"
        )
    train_samples = [sample for sample in samples if sample.get("split") == "train"]
    validation_samples = [sample for sample in samples if sample.get("split") == "development"]
    locked_samples = [sample for sample in samples if sample.get("split") == "locked_test"]
    train_ids = {str(sample.get("game_id")) for sample in train_samples}
    validation_ids = {str(sample.get("game_id")) for sample in validation_samples}
    locked_ids = {str(sample.get("game_id")) for sample in locked_samples}
    if not train_samples or not validation_samples:
        raise RuntimeError("website training dataset requires non-empty train and development splits")
    if formal_frozen and locked_samples:
        raise RuntimeError("locked-test samples were physically loaded by the formal training path")
    if not formal_frozen and not locked_samples:
        raise RuntimeError("provisional smoke bundle is missing its diagnostic locked-test split")
    device, device_info = _resolve_device(args.device)
    if args.website_danzero_init:
        model, init_payload = danzero_dmc.load_q_checkpoint(Path(args.website_danzero_init), device)
        initialized_from = str(args.website_danzero_init)
        init_learner_version = int(init_payload.get("learner_version") or 0)
    else:
        model = danzero_dmc.build_q_model(device)
        initialized_from = None
        init_learner_version = 0
    optimizer = torch.optim.Adam(model.parameters(), lr=float(args.website_danzero_learning_rate))
    rng = random.Random(20260713)
    out_dir = Path(args.website_danzero_out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    best_path = out_dir / "website_danzero_q_best.pth"
    latest_path = out_dir / "website_danzero_q_latest.pth"
    best_loss = float("inf")
    best_epoch = 0
    history: list[dict] = []
    batch_size = int(args.website_danzero_batch_size)

    for epoch in range(1, int(args.website_danzero_epochs) + 1):
        rng.shuffle(train_samples)
        model.train()
        train_losses: list[float] = []
        for start in range(0, len(train_samples), batch_size):
            batch = train_samples[start : start + batch_size]
            states = torch.tensor(
                np.asarray([item["state"] for item in batch], dtype=np.float32), device=device
            )
            actions = torch.tensor(
                np.asarray([item["chosen_action"] for item in batch], dtype=np.float32), device=device
            )
            targets = torch.tensor(
                [float(item["team_reward"]) for item in batch], dtype=torch.float32, device=device
            )
            predictions = model(states, actions)
            loss = functional.mse_loss(predictions, targets)
            optimizer.zero_grad()
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 10.0)
            optimizer.step()
            train_losses.append(float(loss.item()))
        train_metrics = _evaluate(model, train_samples, device, batch_size)
        validation_metrics = _evaluate(model, validation_samples, device, batch_size)
        epoch_result = {
            "epoch": epoch,
            "batch_loss": sum(train_losses) / len(train_losses),
            "train_loss": train_metrics["loss"],
            "train_sign_accuracy": train_metrics["sign_accuracy"],
            "validation_loss": validation_metrics["loss"],
            "validation_sign_accuracy": validation_metrics["sign_accuracy"],
        }
        history.append(epoch_result)
        if float(validation_metrics["loss"]) < best_loss:
            best_loss = float(validation_metrics["loss"])
            best_epoch = epoch
            stats = {
                "training_mode": "website_terminal_action_value_pretrain",
                "source_dataset": str(dataset_path),
                "epoch": epoch,
                "validation_loss": best_loss,
            }
            danzero_dmc.save_training_checkpoint(
                best_path,
                model,
                optimizer,
                deque(),
                deque(),
                stats,
                init_learner_version + epoch,
                rng,
            )

    final_stats = {
        "training_mode": "website_terminal_action_value_pretrain",
        "source_dataset": str(dataset_path),
        "epoch": int(args.website_danzero_epochs),
        "validation_loss": history[-1]["validation_loss"],
    }
    danzero_dmc.save_training_checkpoint(
        latest_path,
        model,
        optimizer,
        deque(),
        deque(),
        final_stats,
        init_learner_version + int(args.website_danzero_epochs),
        rng,
    )
    result = {
        **device_info,
        "dataset_format": DATASET_FORMAT,
        "dataset_path": str(dataset_path),
        "dataset_summary_passed": bool(dataset_summary.get("threshold_passed")),
        "sample_count": len(samples),
        "game_count": len(train_ids) + len(validation_ids),
        "train_game_count": len(train_ids),
        "validation_game_count": len(validation_ids),
        "locked_test_game_count": int(
            dataset_summary.get("excluded_locked_test_game_count") or len(locked_ids)
        ),
        "train_sample_count": len(train_samples),
        "validation_sample_count": len(validation_samples),
        "locked_test_sample_count": int(
            dataset_summary.get("excluded_locked_test_sample_count") or len(locked_samples)
        ),
        "locked_test_loaded_sample_count": len(locked_samples),
        "locked_test_physically_loaded": bool(locked_samples),
        "locked_test_used_for_training": False,
        "locked_test_used_for_checkpoint_selection": False,
        "invalid_sample_count": invalid_count,
        "initialized_from": initialized_from,
        "epochs": int(args.website_danzero_epochs),
        "batch_size": batch_size,
        "learning_rate": float(args.website_danzero_learning_rate),
        "history": history,
        "best_epoch": best_epoch,
        "best_validation_loss": best_loss,
        "best_checkpoint": str(best_path),
        "latest_checkpoint": str(latest_path),
        "behavior_value_scope": "Q(s,a_behavior)_only",
        "candidate_ranking_claim_allowed": False,
        "capability_claim_allowed": False,
        "split_status": dataset_summary.get("split_status"),
        "threshold_passed": bool(best_path.exists() and latest_path.exists() and invalid_count == 0),
    }
    log_path = Path(args.website_danzero_log_out)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return result
