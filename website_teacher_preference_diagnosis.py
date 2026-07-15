from __future__ import annotations

import hashlib
import json
import math
import statistics
import struct
from pathlib import Path
from typing import Any

import numpy as np

import website_teacher_preference as preference


SCHEMA_VERSION = "website_teacher_preference_failure_diagnosis_v1"
CHECKPOINT_PATH = Path(
    "models_website_teacher_preference_v1/website_teacher_preference_final.pth"
)
TEACHER_PATH = Path("website_information_set_teacher_dataset_v6.pth")
SPLIT_PATH = Path("website_teacher_preference_split_v1.json")
TRAINING_REPORT_PATH = Path("website_teacher_preference_training_v1.json")
ARENA_PATH = Path("website_teacher_preference_arena_smoke20_v1.json")
OUTPUT_PATH = Path("website_teacher_preference_failure_diagnosis_v1.json")

EXPECTED_HASHES = {
    "checkpoint": "c54801a9db05100c2fe5a9bf610a64fc7c94dc2cd947dfaab115ff827bd90919",
    "teacher_dataset": preference.EXPECTED_TEACHER_SHA256,
    "split_manifest": "5a15e514dc9bc51d77d300837151d9f1a49250f42885cc7940725bcbe4d35107",
    "training_report": "896192b1d0b4de2caabe20ac17d6a20766fc7f89d6e82a981d834b777932ddd3",
    "arena_evidence": "aa45da9de202194102fe8d11e612ad3eb4b51177fd910b9a7948836afd2a1fe6",
}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_json(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError(f"{path} must contain a JSON object")
    return payload


def _verify_hash(path: Path, expected: str) -> str:
    actual = _sha256(path)
    if actual != expected:
        raise RuntimeError(
            f"{path} SHA-256 mismatch: expected {expected}, got {actual}"
        )
    return actual


def validate_frozen_inputs(
    samples: list[dict], split: dict, report: dict, arena: dict
) -> dict[str, str]:
    actual_hashes = {
        "checkpoint": _verify_hash(CHECKPOINT_PATH, EXPECTED_HASHES["checkpoint"]),
        "teacher_dataset": _verify_hash(
            TEACHER_PATH, EXPECTED_HASHES["teacher_dataset"]
        ),
        "split_manifest": _verify_hash(SPLIT_PATH, EXPECTED_HASHES["split_manifest"]),
        "training_report": _verify_hash(
            TRAINING_REPORT_PATH, EXPECTED_HASHES["training_report"]
        ),
        "arena_evidence": _verify_hash(ARENA_PATH, EXPECTED_HASHES["arena_evidence"]),
    }
    train_ids, development_ids = preference.split_game_ids(samples)
    required_split = {
        "schema_version": preference.SPLIT_SCHEMA_VERSION,
        "teacher_sha256": EXPECTED_HASHES["teacher_dataset"],
        "pipeline_train_game_ids": train_ids,
        "pipeline_development_game_ids": development_ids,
        "pipeline_train_game_count": 18,
        "pipeline_development_game_count": 4,
        "total_game_count": 22,
        "overlap_game_ids": [],
        "dropped_game_ids": [],
        "locked_test_loaded": False,
        "capability_claim_allowed": False,
        "threshold_passed": True,
    }
    for key, expected in required_split.items():
        if split.get(key) != expected:
            raise RuntimeError(f"frozen split {key} mismatch")
    required_report = {
        "schema_version": preference.SCHEMA_VERSION,
        "teacher_sha256": EXPECTED_HASHES["teacher_dataset"],
        "teacher_label_count": 22,
        "preference_pair_count": 22,
        "pipeline_train_game_count": 18,
        "pipeline_development_game_count": 4,
        "split_overlap_game_count": 0,
        "checkpoint_sha256": EXPECTED_HASHES["checkpoint"],
        "checkpoint_reload_verified": True,
        "locked_test_loaded": False,
        "complete_bundle_loaded": False,
        "hyperparameter_search_count": 0,
        "checkpoint_selection_count": 0,
        "arena_evaluation_count": 0,
        "website_shadow_count": 0,
        "website_game_count": 0,
        "model_controlled_website_action_count": 0,
        "capability_claim_allowed": False,
        "checkpoint_promotion_allowed": False,
        "threshold_passed": True,
    }
    for key, expected in required_report.items():
        if report.get(key) != expected:
            raise RuntimeError(f"frozen training report {key} mismatch")
    if set((report.get("final_metrics") or {})) != {
        "pipeline_train",
        "pipeline_development",
    }:
        raise RuntimeError("frozen training report final metrics mismatch")
    required_arena = {
        "checkpoint_sha256": EXPECTED_HASHES["checkpoint"],
        "requested_games": 20,
        "completed_games": 20,
        "model_wins": 0,
        "baseline_wins": 20,
        "model_team_win_rate": 0.0,
        "threshold_passed": True,
        "early_screen_continuation_allowed": False,
        "allowed_for_stage4_continuation": False,
        "illegal_action_count": 0,
        "fallback_count": 0,
        "materialization_fail_count": 0,
        "hand_card_mismatch_count": 0,
        "fatal_no_candidate_count": 0,
        "training_run_count": 0,
        "hyperparameter_search_count": 0,
        "checkpoint_selection_count": 0,
        "locked_test_load_count": 0,
        "website_dataset_load_count": 0,
        "website_shadow_count": 0,
        "website_game_count": 0,
        "model_controlled_website_action_count": 0,
        "checkpoint_promotion_allowed": False,
        "capability_claim_allowed": False,
        "status": "completed",
    }
    for key, expected in required_arena.items():
        if arena.get(key) != expected:
            raise RuntimeError(f"frozen Arena evidence {key} mismatch")
    baseline = arena.get("baseline_evidence") or {}
    if (
        baseline.get("baseline_equivalence_samples") != 500
        or baseline.get("baseline_equivalence_mismatch_count") != 0
    ):
        raise RuntimeError("frozen Arena baseline equivalence mismatch")
    return actual_hashes


def map_partitions(samples: list[dict], split: dict) -> dict[str, list[dict]]:
    train_ids = [str(value) for value in split["pipeline_train_game_ids"]]
    development_ids = [
        str(value) for value in split["pipeline_development_game_ids"]
    ]
    if set(train_ids) & set(development_ids):
        raise RuntimeError("pipeline partitions overlap")
    sample_ids = [str(sample["game_id"]) for sample in samples]
    if len(sample_ids) != len(set(sample_ids)):
        raise RuntimeError("teacher state game IDs are not unique")
    if set(sample_ids) != set(train_ids) | set(development_ids):
        raise RuntimeError("pipeline partition has unknown or missing teacher games")
    return {
        "pipeline_train": preference._ordered_samples(samples, train_ids),
        "pipeline_development": preference._ordered_samples(
            samples, development_ids
        ),
    }


def _score_batch(model: Any, samples: list[dict], actions: list[list[float]]) -> list[float]:
    import torch

    if not samples:
        return []
    states = torch.tensor(
        np.asarray([sample["state"] for sample in samples], dtype=np.float32)
    )
    action_tensor = torch.tensor(np.asarray(actions, dtype=np.float32))
    with torch.no_grad():
        values = model(states, action_tensor)
    if tuple(values.shape) != (len(samples),):
        raise RuntimeError("Q model returned an invalid shape")
    if not bool(torch.isfinite(values).all().item()):
        raise RuntimeError("Q model returned a nonfinite value")
    return [float(value) for value in values.tolist()]


def score_partition(model: Any, samples: list[dict]) -> tuple[list[list[float]], dict]:
    q_values: list[list[float | None]] = [
        [None] * len(sample["legal_actions"]) for sample in samples
    ]
    teacher_indices: list[int] = []
    behavior_indices: list[int] = []
    duplicate_vector_count = 0
    for sample in samples:
        actions = sample["legal_actions"]
        teacher_matches = [
            index for index, action in enumerate(actions) if action == sample["teacher_action"]
        ]
        behavior_matches = [
            index for index, action in enumerate(actions) if action == sample["behavior_action"]
        ]
        if len(teacher_matches) != 1 or len(behavior_matches) != 1:
            raise RuntimeError("preference action must occur exactly once in legal actions")
        teacher_indices.append(teacher_matches[0])
        behavior_indices.append(behavior_matches[0])
        duplicate_vector_count += len(actions) - len({tuple(action) for action in actions})

    teacher_scores = _score_batch(
        model, samples, [sample["teacher_action"] for sample in samples]
    )
    behavior_scores = _score_batch(
        model, samples, [sample["behavior_action"] for sample in samples]
    )
    for state_index, value in enumerate(teacher_scores):
        q_values[state_index][teacher_indices[state_index]] = value
    for state_index, value in enumerate(behavior_scores):
        q_values[state_index][behavior_indices[state_index]] = value

    other_samples: list[dict] = []
    other_actions: list[list[float]] = []
    other_positions: list[tuple[int, int]] = []
    for state_index, sample in enumerate(samples):
        excluded = {teacher_indices[state_index], behavior_indices[state_index]}
        for action_index, action in enumerate(sample["legal_actions"]):
            if action_index not in excluded:
                other_samples.append(sample)
                other_actions.append(action)
                other_positions.append((state_index, action_index))
    other_scores = _score_batch(model, other_samples, other_actions)
    for position, value in zip(other_positions, other_scores):
        state_index, action_index = position
        q_values[state_index][action_index] = value

    if any(value is None for values in q_values for value in values):
        raise RuntimeError("not every recorded legal action was scored")
    scored = [[float(value) for value in values] for values in q_values]
    legal_action_count = sum(len(sample["legal_actions"]) for sample in samples)
    if sum(len(values) for values in scored) != legal_action_count:
        raise RuntimeError("legal action score accounting mismatch")
    return scored, {
        "state_count": len(samples),
        "recorded_legal_action_count": legal_action_count,
        "legal_action_score_count": legal_action_count,
        "dropped_action_count": 0,
        "duplicate_action_scoring_count": 0,
        "reconstructed_action_count": 0,
        "source_duplicate_action_vector_count": duplicate_vector_count,
        "model_forward_batch_count": 3 if other_samples else 2,
    }


def _action_order_sha256(actions: list[list[float]]) -> str:
    digest = hashlib.sha256()
    for action in actions:
        digest.update(struct.pack(f"<{len(action)}f", *[float(value) for value in action]))
    return digest.hexdigest()


def diagnose_state(sample: dict, partition: str, q_values: list[float]) -> dict:
    import torch

    actions = sample["legal_actions"]
    if len(q_values) != len(actions) or not all(math.isfinite(value) for value in q_values):
        raise RuntimeError("state Q values do not cover every finite legal action")
    teacher_index = actions.index(sample["teacher_action"])
    behavior_index = actions.index(sample["behavior_action"])
    teacher_q = q_values[teacher_index]
    behavior_q = q_values[behavior_index]
    top1_index = int(torch.argmax(torch.tensor(q_values, dtype=torch.float32)).item())
    if top1_index == teacher_index:
        top1_source = "teacher"
    elif top1_index == behavior_index:
        top1_source = "behavior"
    else:
        top1_source = "other"
    unpaired_above = sum(
        index not in {teacher_index, behavior_index} and value > teacher_q
        for index, value in enumerate(q_values)
    )
    return {
        "game_id": str(sample["game_id"]),
        "turn_index": int(sample["turn_index"]),
        "pipeline_partition": partition,
        "legal_action_count": len(actions),
        "legal_action_order_sha256": _action_order_sha256(actions),
        "legal_action_q_values": q_values,
        "teacher_action_index": teacher_index,
        "teacher_rank": 1 + sum(value > teacher_q for value in q_values),
        "teacher_q": teacher_q,
        "behavior_action_index": behavior_index,
        "behavior_rank": 1 + sum(value > behavior_q for value in q_values),
        "behavior_q": behavior_q,
        "teacher_minus_behavior_margin": teacher_q - behavior_q,
        "top1_index": top1_index,
        "top1_q": q_values[top1_index],
        "top1_source": top1_source,
        "top1_is_pass": all(float(value) == 0.0 for value in actions[top1_index]),
        "actions_strictly_above_teacher_count": sum(
            value > teacher_q for value in q_values
        ),
        "actions_tied_with_teacher_count": sum(
            value == teacher_q for value in q_values
        ),
        "unpaired_actions_strictly_above_teacher_count": unpaired_above,
        "unpaired_action_strictly_outranks_teacher": bool(unpaired_above),
    }


def aggregate_states(states: list[dict]) -> dict:
    count = len(states)
    if not count:
        raise RuntimeError("cannot aggregate an empty partition")
    teacher_ranks = [int(state["teacher_rank"]) for state in states]
    teacher_over_behavior_count = sum(
        float(state["teacher_q"]) > float(state["behavior_q"]) for state in states
    )
    teacher_top1_count = sum(state["top1_source"] == "teacher" for state in states)
    behavior_top1_count = sum(state["top1_source"] == "behavior" for state in states)
    other_top1_count = sum(state["top1_source"] == "other" for state in states)
    pass_top1_count = sum(bool(state["top1_is_pass"]) for state in states)
    unpaired_state_count = sum(
        bool(state["unpaired_action_strictly_outranks_teacher"]) for state in states
    )
    return {
        "state_count": count,
        "legal_action_count": sum(int(state["legal_action_count"]) for state in states),
        "teacher_over_behavior_count": teacher_over_behavior_count,
        "teacher_over_behavior_rate": teacher_over_behavior_count / count,
        "teacher_top1_count": teacher_top1_count,
        "teacher_top1_rate": teacher_top1_count / count,
        "behavior_top1_count": behavior_top1_count,
        "behavior_top1_rate": behavior_top1_count / count,
        "other_action_top1_count": other_top1_count,
        "other_action_top1_rate": other_top1_count / count,
        "pass_top1_count": pass_top1_count,
        "pass_top1_rate": pass_top1_count / count,
        "mean_teacher_rank": sum(teacher_ranks) / count,
        "median_teacher_rank": float(statistics.median(teacher_ranks)),
        "unpaired_action_strictly_outranks_teacher_state_count": unpaired_state_count,
        "unpaired_action_strictly_outranks_teacher_state_rate": unpaired_state_count / count,
        "unpaired_actions_strictly_above_teacher_count": sum(
            int(state["unpaired_actions_strictly_above_teacher_count"])
            for state in states
        ),
    }


def pairwise_metrics(samples: list[dict], states: list[dict]) -> dict:
    import torch

    by_key = {
        (state["game_id"], int(state["turn_index"])): state for state in states
    }
    ordered_states = [
        by_key[(str(sample["game_id"]), int(sample["turn_index"]))]
        for sample in samples
    ]
    teacher_values = torch.tensor(
        [state["teacher_q"] for state in ordered_states], dtype=torch.float32
    )
    behavior_values = torch.tensor(
        [state["behavior_q"] for state in ordered_states], dtype=torch.float32
    )
    margins = teacher_values - behavior_values
    digest = hashlib.sha256()
    for sample, teacher_value, behavior_value in zip(
        samples, teacher_values.tolist(), behavior_values.tolist()
    ):
        digest.update(f"{sample['game_id']}:{sample['turn_index']}\n".encode("utf-8"))
        digest.update(struct.pack("<ff", teacher_value, behavior_value))
    return {
        "sample_count": len(samples),
        "pairwise_loss": float(
            preference.pairwise_ranking_loss(teacher_values, behavior_values).item()
        ),
        "ranking_accuracy": float((margins > 0.0).float().mean().item()),
        "mean_teacher_minus_behavior_margin": float(margins.mean().item()),
        "prediction_sha256": digest.hexdigest(),
    }


def reproduce_pairwise_metrics(
    partitions: dict[str, list[dict]],
    states_by_partition: dict[str, list[dict]],
    report: dict,
) -> dict:
    reproduction: dict[str, dict] = {}
    for partition in ("pipeline_train", "pipeline_development"):
        actual = pairwise_metrics(partitions[partition], states_by_partition[partition])
        frozen = report["final_metrics"][partition]
        expected = {key: frozen[key] for key in actual}
        exact_match = actual == expected
        reproduction[partition] = {
            "actual": actual,
            "frozen": expected,
            "exact_match": exact_match,
        }
        if not exact_match:
            raise RuntimeError(f"{partition} frozen pairwise metrics did not reproduce")
    return reproduction


def run(output_path: Path = OUTPUT_PATH) -> dict:
    if output_path.exists():
        raise RuntimeError(f"diagnostic output already exists: {output_path}")
    samples, _teacher_summary, teacher_sha256 = preference.load_teacher_dataset(
        TEACHER_PATH
    )
    split = _load_json(SPLIT_PATH)
    report = _load_json(TRAINING_REPORT_PATH)
    arena = _load_json(ARENA_PATH)
    actual_hashes = validate_frozen_inputs(samples, split, report, arena)
    if teacher_sha256 != actual_hashes["teacher_dataset"]:
        raise RuntimeError("loaded teacher SHA-256 mismatch")
    partitions = map_partitions(samples, split)
    model, checkpoint = preference.load_checkpoint(CHECKPOINT_PATH)

    states_by_partition: dict[str, list[dict]] = {}
    accounting_by_partition: dict[str, dict] = {}
    for partition, partition_samples in partitions.items():
        q_values, accounting = score_partition(model, partition_samples)
        states_by_partition[partition] = [
            diagnose_state(sample, partition, values)
            for sample, values in zip(partition_samples, q_values)
        ]
        accounting_by_partition[partition] = accounting
    all_states = (
        states_by_partition["pipeline_train"]
        + states_by_partition["pipeline_development"]
    )
    pairwise_reproduction = reproduce_pairwise_metrics(
        partitions, states_by_partition, report
    )
    total_actions = sum(state["legal_action_count"] for state in all_states)
    source_duplicate_vectors = sum(
        item["source_duplicate_action_vector_count"]
        for item in accounting_by_partition.values()
    )
    result = {
        "schema_version": SCHEMA_VERSION,
        "frozen_inputs": {
            "checkpoint": str(CHECKPOINT_PATH),
            "teacher_dataset": str(TEACHER_PATH),
            "split_manifest": str(SPLIT_PATH),
            "training_report": str(TRAINING_REPORT_PATH),
            "arena_evidence": str(ARENA_PATH),
            "sha256": actual_hashes,
        },
        "checkpoint_schema_version": checkpoint["schema_version"],
        "checkpoint_screen_status": "rejected_from_100_200_game_screen",
        "arena_conclusion": {
            "requested_games": 20,
            "completed_games": 20,
            "model_wins": 0,
            "baseline_wins": 20,
            "integrity_gate_passed": True,
            "early_screen_continuation_allowed": False,
            "safety_error_count": 0,
        },
        "partition_mapping": {
            "pipeline_train_game_count": len(partitions["pipeline_train"]),
            "pipeline_development_game_count": len(
                partitions["pipeline_development"]
            ),
            "overlap_game_count": 0,
            "unknown_game_count": 0,
        },
        "scoring_accounting": {
            "unique_teacher_state_count": len(all_states),
            "recorded_legal_action_count": total_actions,
            "legal_action_score_count": total_actions,
            "dropped_state_count": 0,
            "duplicate_state_count": 0,
            "dimension_invalid_action_count": 0,
            "nonfinite_q_count": 0,
            "illegal_recorded_action_count": 0,
            "dropped_action_count": 0,
            "duplicate_action_scoring_count": 0,
            "reconstructed_action_count": 0,
            "source_duplicate_action_vector_count": source_duplicate_vectors,
            "by_partition": accounting_by_partition,
        },
        "pairwise_reproduction": pairwise_reproduction,
        "state_diagnostics": all_states,
        "aggregates": {
            "pipeline_train": aggregate_states(
                states_by_partition["pipeline_train"]
            ),
            "pipeline_development": aggregate_states(
                states_by_partition["pipeline_development"]
            ),
            "overall": aggregate_states(all_states),
        },
        "interpretation_scope": {
            "objective_coverage_pattern_may_be_identified": True,
            "causal_claim_allowed": False,
            "capability_claim_allowed": False,
            "corrective_model_result_claimed": False,
            "checkpoint_promotion_allowed": False,
        },
        "forbidden_operation_counts": {
            "training_runs": 0,
            "hyperparameter_searches": 0,
            "checkpoint_selections": 0,
            "checkpoint_modifications": 0,
            "website_dataset_loads": 0,
            "locked_test_loads": 0,
            "arena_games": 0,
            "website_shadow_games": 0,
            "website_games": 0,
            "model_controlled_website_actions": 0,
            "checkpoint_promotions": 0,
            "capability_claims": 0,
        },
        "status": "completed",
    }
    output_path.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return result


if __name__ == "__main__":
    run()
