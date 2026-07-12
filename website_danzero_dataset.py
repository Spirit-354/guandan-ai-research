from __future__ import annotations

from collections import Counter
import json
import math
from pathlib import Path
from typing import Any, Iterable


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


def build_dataset(raw_dirs: str, output_path: str) -> dict:
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
        for decision in record.get("decisions") or []:
            sample, reason = _decision_sample(record, decision)
            if reason:
                reject_reasons[f"decision:{reason}"] += 1
                game_failed = True
                break
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
        "threshold_passed": bool(paths and accepted_games and samples),
    }
    write_dataset(Path(output_path), samples, summary)
    return summary
