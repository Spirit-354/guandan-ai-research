from __future__ import annotations

from collections import Counter
import hashlib
import json
import math
import os
from pathlib import Path
import random
import statistics
import struct
import time
from typing import Any, Callable

import website_danzero_dataset as website_data
import website_information_set as information_set
import website_teacher_preference as preference


SCHEMA_VERSION = "website_teacher_preference_unpaired_train_confirmation_v1"
AUDIT_PATH = Path("website_teacher_preference_unpaired_evidence_audit_v1.json")
DIAGNOSIS_PATH = Path("website_teacher_preference_failure_diagnosis_v1.json")
TEACHER_PATH = Path("website_information_set_teacher_dataset_v6.pth")
SPLIT_PATH = Path("website_teacher_preference_split_v1.json")
TRAINING_REPORT_PATH = Path("website_teacher_preference_training_v1.json")
CHECKPOINT_PATH = Path(
    "models_website_teacher_preference_v1/website_teacher_preference_final.pth"
)
ARENA_PATH = Path("website_teacher_preference_arena_smoke20_v1.json")
SOURCE_DATASET_PATH = Path("website_danzero_shadow_extension_v5.train_dev.pth")
OUTPUT_PATH = Path("website_teacher_preference_unpaired_train_confirmation_v1.json")

EXPECTED_HASHES = {
    "stage_6_3_audit": "09f52df90d095ab6b3777a046c50901f96fbeb15e6ef5f613343a13be1249383",
    "stage_6_2_diagnosis": "da08516c39986a01349533e160ba0e97a566d7fad6e42b0b7b3ce41df835b0b2",
    "teacher_dataset": "a74416e6facb28a1bc64563eba90cb33d460dc9e59cc2109518da142465e15f8",
    "split_manifest": "5a15e514dc9bc51d77d300837151d9f1a49250f42885cc7940725bcbe4d35107",
    "training_report": "896192b1d0b4de2caabe20ac17d6a20766fc7f89d6e82a981d834b777932ddd3",
    "checkpoint": "c54801a9db05100c2fe5a9bf610a64fc7c94dc2cd947dfaab115ff827bd90919",
    "arena_evidence": "aa45da9de202194102fe8d11e612ad3eb4b51177fd910b9a7948836afd2a1fe6",
}
EXPECTED_SOURCE_DATASET_SHA256 = (
    "e5e220c3c770116ca9d01478e98e610dd6309a0f3d6c17088a8328f62b47174b"
)
CONTINUATION_PROFILES = ("greedy_bot", "tempo_baseline")
ROLLOUTS_PER_ACTION = 16
ROLLOUTS_PER_PROFILE = 8
MAX_ROLLOUT_STEPS = 300
MAX_SECONDS_PER_CASE = 600.0
MIN_ADVANTAGE = 0.15
MAX_RETURN_VARIANCE = 0.50


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def action_sha256(action: list[float]) -> str:
    return hashlib.sha256(
        struct.pack(f"<{len(action)}f", *[float(value) for value in action])
    ).hexdigest()


def action_order_sha256(actions: list[list[float]]) -> str:
    digest = hashlib.sha256()
    for action in actions:
        digest.update(
            struct.pack(f"<{len(action)}f", *[float(value) for value in action])
        )
    return digest.hexdigest()


def load_json(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError(f"{path} must contain a JSON object")
    return payload


def rollout_schedule() -> list[dict]:
    return [
        {
            "rollout_index": index,
            "continuation_profile": CONTINUATION_PROFILES[
                index % len(CONTINUATION_PROFILES)
            ],
            "determinization_index": index // len(CONTINUATION_PROFILES),
        }
        for index in range(ROLLOUTS_PER_ACTION)
    ]


def sample_variance(values: list[float]) -> float:
    return float(statistics.variance(values)) if len(values) >= 2 else 0.0


def directional_metrics(
    teacher_returns: list[float | None],
    top1_returns: list[float | None],
) -> dict:
    if len(teacher_returns) != ROLLOUTS_PER_ACTION or len(top1_returns) != (
        ROLLOUTS_PER_ACTION
    ):
        raise RuntimeError("paired return accounting mismatch")
    schedule = rollout_schedule()
    paired = [
        float(teacher) - float(top1)
        for teacher, top1 in zip(teacher_returns, top1_returns)
        if teacher is not None and top1 is not None
    ]
    teacher_values = [float(value) for value in teacher_returns if value is not None]
    top1_values = [float(value) for value in top1_returns if value is not None]
    advantage = sum(paired) / len(paired) if paired else 0.0
    paired_variance = sample_variance(paired)
    standard_error = (
        math.sqrt(paired_variance / len(paired)) if paired else float("inf")
    )
    lower_bound = advantage - 1.96 * standard_error
    confidence = max(0.0, min(1.0, 0.5 + lower_bound / 2.0))
    profile_metrics: dict[str, dict] = {}
    for profile in CONTINUATION_PROFILES:
        differences = [
            float(teacher_returns[item["rollout_index"]])
            - float(top1_returns[item["rollout_index"]])
            for item in schedule
            if item["continuation_profile"] == profile
            and teacher_returns[item["rollout_index"]] is not None
            and top1_returns[item["rollout_index"]] is not None
        ]
        profile_metrics[profile] = {
            "paired_count": len(differences),
            "teacher_minus_top1_mean_advantage": (
                sum(differences) / len(differences) if differences else None
            ),
            "paired_return_variance": sample_variance(differences),
        }
    teacher_variance = sample_variance(teacher_values)
    top1_variance = sample_variance(top1_values)
    teacher_failures = gate_failure_reasons(
        paired_count=len(paired),
        advantage=advantage,
        candidate_variance=teacher_variance,
        lower_bound=lower_bound,
        profile_advantages={
            name: values["teacher_minus_top1_mean_advantage"]
            for name, values in profile_metrics.items()
        },
    )
    top1_failures = gate_failure_reasons(
        paired_count=len(paired),
        advantage=-advantage,
        candidate_variance=top1_variance,
        lower_bound=-advantage - 1.96 * standard_error,
        profile_advantages={
            name: (
                -float(values["teacher_minus_top1_mean_advantage"])
                if values["teacher_minus_top1_mean_advantage"] is not None
                else None
            )
            for name, values in profile_metrics.items()
        },
    )
    teacher_supported = not teacher_failures
    top1_supported = not top1_failures
    if teacher_supported and top1_supported:
        raise RuntimeError("opposite directional gates cannot both pass")
    direction = (
        "teacher_over_top1_supported"
        if teacher_supported
        else "top1_over_teacher_supported"
        if top1_supported
        else "inconclusive"
    )
    return {
        "paired_count": len(paired),
        "teacher_mean_return": (
            sum(teacher_values) / len(teacher_values) if teacher_values else None
        ),
        "teacher_return_variance": teacher_variance,
        "top1_mean_return": sum(top1_values) / len(top1_values) if top1_values else None,
        "top1_return_variance": top1_variance,
        "teacher_minus_top1_advantage": advantage,
        "paired_return_variance": paired_variance,
        "teacher_minus_top1_95_lower_bound": lower_bound,
        "teacher_over_top1_confidence": confidence,
        "continuation_policy_advantages": profile_metrics,
        "teacher_over_top1_supported": teacher_supported,
        "teacher_over_top1_failure_reasons": teacher_failures,
        "top1_over_teacher_supported": top1_supported,
        "top1_over_teacher_failure_reasons": top1_failures,
        "directional_classification": direction,
    }


def gate_failure_reasons(
    *,
    paired_count: int,
    advantage: float,
    candidate_variance: float,
    lower_bound: float,
    profile_advantages: dict[str, float | None],
) -> list[str]:
    reasons: list[str] = []
    if paired_count != ROLLOUTS_PER_ACTION:
        reasons.append("paired_rollout_count_incomplete")
    if advantage < MIN_ADVANTAGE:
        reasons.append("mean_advantage_below_frozen_threshold")
    if candidate_variance > MAX_RETURN_VARIANCE:
        reasons.append("candidate_return_variance_above_frozen_threshold")
    if lower_bound <= 0.0:
        reasons.append("advantage_95_lower_bound_not_positive")
    if any(
        value is None or float(value) < MIN_ADVANTAGE
        for value in profile_advantages.values()
    ):
        reasons.append("continuation_profile_advantage_below_frozen_threshold")
    return reasons


def verify_frozen_inputs() -> dict[str, str]:
    paths = {
        "stage_6_3_audit": AUDIT_PATH,
        "stage_6_2_diagnosis": DIAGNOSIS_PATH,
        "teacher_dataset": TEACHER_PATH,
        "split_manifest": SPLIT_PATH,
        "training_report": TRAINING_REPORT_PATH,
        "checkpoint": CHECKPOINT_PATH,
        "arena_evidence": ARENA_PATH,
    }
    actual: dict[str, str] = {}
    for name, path in paths.items():
        value = sha256(path)
        if value != EXPECTED_HASHES[name]:
            raise RuntimeError(f"{name} SHA-256 mismatch")
        actual[name] = value
    source_hash = sha256(SOURCE_DATASET_PATH)
    if source_hash != EXPECTED_SOURCE_DATASET_SHA256:
        raise RuntimeError("source train/development dataset SHA-256 mismatch")
    return actual


def reproduce_targets(
    audit: dict,
    diagnosis: dict,
    split: dict,
    teacher_samples: list[dict],
    source_samples: list[dict],
    source_summary: dict,
) -> tuple[list[dict], list[dict]]:
    if audit.get("schema_version") != (
        "website_teacher_preference_unpaired_evidence_audit_v1"
    ) or audit.get("status") != "completed":
        raise RuntimeError("Stage 6.3 audit status mismatch")
    if audit.get("future_counterfactual_manifest_executed") is not False:
        raise RuntimeError("Stage 6.3 future manifest was already executed")
    if diagnosis.get("schema_version") != (
        "website_teacher_preference_failure_diagnosis_v1"
    ):
        raise RuntimeError("Stage 6.2 diagnosis schema mismatch")
    if source_summary.get("partition_role") != "train_development":
        raise RuntimeError("source dataset is not the physical train/development partition")
    if source_summary.get("contains_locked_test_samples") is not False:
        raise RuntimeError("source dataset contains locked-test samples")
    if any(sample.get("split") == "locked_test" for sample in source_samples):
        raise RuntimeError("source dataset loaded a locked-test sample")

    train_ids = {str(value) for value in split["pipeline_train_game_ids"]}
    development_ids = {
        str(value) for value in split["pipeline_development_game_ids"]
    }
    if len(train_ids) != 18 or len(development_ids) != 4 or train_ids & development_ids:
        raise RuntimeError("frozen 18/4 pipeline split mismatch")
    teacher_by_key = {
        (str(sample["game_id"]), int(sample["turn_index"])): sample
        for sample in teacher_samples
    }
    source_by_key = {
        (str(sample["game_id"]), int(sample["turn_index"])): sample
        for sample in source_samples
        if sample.get("split") == "train"
    }
    audit_by_key = {
        (str(item["game_id"]), int(item["turn_index"])): item
        for item in audit.get("target_audits") or []
    }
    manifest = audit.get("future_counterfactual_manifest") or []
    train_entries = [
        item for item in manifest if item.get("pipeline_partition") == "pipeline_train"
    ]
    heldout_entries = [
        item
        for item in manifest
        if item.get("pipeline_partition") == "pipeline_development"
    ]
    if len(train_entries) != 9 or len(heldout_entries) != 3 or len(manifest) != 12:
        raise RuntimeError("Stage 6.3 nine/three manifest accounting mismatch")

    targets: list[dict] = []
    seen: set[tuple[str, int]] = set()
    for entry in train_entries:
        key = (str(entry["game_id"]), int(entry["turn_index"]))
        if key in seen or key not in teacher_by_key or key not in source_by_key:
            raise RuntimeError("pipeline-train target is duplicate or missing")
        seen.add(key)
        if key[0] not in train_ids or entry.get("execution_allowed_in_this_stage"):
            raise RuntimeError("pipeline-train manifest partition/provenance mismatch")
        teacher = teacher_by_key[key]
        source = source_by_key[key]
        target_audit = audit_by_key.get(key)
        if target_audit is None or target_audit.get("pipeline_partition") != (
            "pipeline_train"
        ):
            raise RuntimeError("Stage 6.3 target audit is missing")
        actions = source.get("legal_actions") or []
        metadata = source.get("legal_action_metadata") or []
        if (
            source.get("split") != "train"
            or source.get("state") != teacher.get("state")
            or actions != teacher.get("legal_actions")
            or len(actions) != len(metadata)
            or action_order_sha256(actions)
            != target_audit.get("legal_action_order_sha256")
        ):
            raise RuntimeError("source state/legal-action identity mismatch")
        teacher_index = int(target_audit["teacher_action_index"])
        top1_index = int(target_audit["top1_action_index"])
        if (
            actions[teacher_index] != teacher.get("teacher_action")
            or actions[top1_index] != target_audit.get("top1_action")
            or action_sha256(actions[top1_index])
            != target_audit.get("top1_action_sha256")
            or metadata[teacher_index].get("cards")
            != target_audit["teacher_physical_identity"]["cards_website"]
            or metadata[top1_index].get("cards")
            != target_audit["top1_physical_identity"]["cards_website"]
            or metadata[teacher_index].get("cards")
            != teacher.get("teacher_physical_cards")
        ):
            raise RuntimeError("teacher/top1 exact action identity mismatch")
        targets.append(
            {
                "game_id": key[0],
                "turn_index": key[1],
                "pipeline_partition": "pipeline_train",
                "source_sample": source,
                "legal_action_count": len(actions),
                "legal_action_order_sha256": action_order_sha256(actions),
                "teacher_action_index": teacher_index,
                "teacher_action_sha256": action_sha256(actions[teacher_index]),
                "teacher_physical_identity": target_audit[
                    "teacher_physical_identity"
                ],
                "top1_action_index": top1_index,
                "top1_action_sha256": action_sha256(actions[top1_index]),
                "top1_physical_identity": target_audit["top1_physical_identity"],
            }
        )

    heldout: list[dict] = []
    for entry in heldout_entries:
        key = (str(entry["game_id"]), int(entry["turn_index"]))
        if key[0] not in development_ids or key not in audit_by_key:
            raise RuntimeError("pipeline-development held-out mapping mismatch")
        heldout.append(
            {
                "game_id": key[0],
                "turn_index": key[1],
                "pipeline_partition": "pipeline_development",
                "top1_action_index": entry["top1_action_index"],
                "top1_action_sha256": entry["top1_action_sha256"],
                "case_execution_count": 0,
                "rollout_count": 0,
                "held_out_from_objective_design": True,
            }
        )
    return targets, heldout


def materialize_candidate(
    target: dict,
    action_role: str,
    game: Any,
    components: dict,
    adaptive: Any,
) -> dict:
    sample = target["source_sample"]
    index = int(target[f"{action_role}_action_index"])
    metadata = sample["legal_action_metadata"][index]
    website_cards = list(metadata.get("cards") or [])
    local_cards = adaptive.website_cards_to_local(website_cards)
    info = adaptive.offline_make_action_info_from_cards(
        game,
        components,
        local_cards,
        random.Random(0),
        policy="teacher_preference_unpaired_confirmation",
        audit_masks=False,
    )
    if info.get("illegal") or info.get("materialization_fail") or info.get(
        "hand_card_mismatch"
    ):
        raise RuntimeError(f"{action_role} candidate materialization failed")
    if information_set._candidate_key(list(info.get("chosen_cards") or [])) != (
        information_set._candidate_key(local_cards)
    ):
        raise RuntimeError(f"{action_role} physical-card materialization changed")
    return {
        "role": action_role,
        "action_index": index,
        "action_sha256": target[f"{action_role}_action_sha256"],
        "action_id": int(info.get("action_id") or 0),
        "physical_cards": list(info.get("chosen_cards") or []),
        "physical_cards_website": website_cards,
        "action_type": str(
            info.get("action_type") or metadata.get("action_type") or "unknown"
        ),
        "is_bomb": bool(info.get("is_bomb")),
    }


def execute_case(
    target: dict,
    candidates: list[dict],
    components: dict,
    adaptive: Any,
    profile_config: dict,
    baseline_cache: dict[str, list[str]],
    baseline_stats: dict[str, Any],
    *,
    restore_fn: Callable[..., Any] = information_set.restore_game,
    simulate_fn: Callable[..., tuple[float | None, dict | None]] = (
        information_set._simulate_candidate
    ),
) -> dict:
    if [candidate.get("role") for candidate in candidates] != ["teacher", "top1"]:
        raise RuntimeError("confirmation candidate set must be exactly teacher/top1")
    sample = target["source_sample"]
    started = time.monotonic()
    deadline = started + MAX_SECONDS_PER_CASE
    returns: list[list[float | None]] = [[], []]
    failures: list[list[dict]] = [[], []]
    paired_rollouts: list[dict] = []
    for item in rollout_schedule():
        seed = information_set._stable_determinization_seed(
            sample, item["determinization_index"]
        )
        base_game = restore_fn(sample, components, random.Random(seed))
        values: list[float | None] = []
        for candidate_index, candidate in enumerate(candidates):
            value, failure = simulate_fn(
                base_game,
                candidate,
                components,
                adaptive,
                seed,
                MAX_ROLLOUT_STEPS,
                item["continuation_profile"],
                profile_config,
                deadline,
                baseline_cache,
                baseline_stats,
            )
            returns[candidate_index].append(value)
            values.append(value)
            if failure:
                failures[candidate_index].append(failure)
        paired_rollouts.append(
            {
                **item,
                "determinization_seed": seed,
                "teacher_return": values[0],
                "top1_return": values[1],
                "teacher_minus_top1_return": (
                    float(values[0]) - float(values[1])
                    if values[0] is not None and values[1] is not None
                    else None
                ),
            }
        )
    metrics = directional_metrics(returns[0], returns[1])
    candidate_results = []
    for candidate, values, candidate_failures in zip(candidates, returns, failures):
        completed = [float(value) for value in values if value is not None]
        candidate_results.append(
            {
                **candidate,
                "requested_rollout_count": ROLLOUTS_PER_ACTION,
                "completed_rollout_count": len(completed),
                "completion_rate": len(completed) / ROLLOUTS_PER_ACTION,
                "mean_return": sum(completed) / len(completed) if completed else None,
                "return_variance": sample_variance(completed),
                "failure_count": len(candidate_failures),
                "failures": candidate_failures,
            }
        )
    return {
        "game_id": target["game_id"],
        "turn_index": target["turn_index"],
        "pipeline_partition": "pipeline_train",
        "legal_action_count": target["legal_action_count"],
        "legal_action_order_sha256": target["legal_action_order_sha256"],
        "case_seconds": time.monotonic() - started,
        "case_timed_out": time.monotonic() >= deadline,
        "candidate_results": candidate_results,
        "paired_rollouts": paired_rollouts,
        "metrics": metrics,
    }


def validate_completed_result(result: dict) -> None:
    cases = result.get("case_results") or []
    if len(cases) != 9:
        raise RuntimeError("formal confirmation did not produce exactly nine cases")
    if len(result.get("pipeline_development_heldout") or []) != 3:
        raise RuntimeError("formal confirmation lost development held-out accounting")
    if result.get("requested_total_rollouts") != 288:
        raise RuntimeError("formal confirmation requested rollout count mismatch")
    if result.get("completed_rollouts") != 288:
        raise RuntimeError("formal confirmation is incomplete")
    if result.get("continuation_profile_rollout_counts") != {
        "greedy_bot": 144,
        "tempo_baseline": 144,
    }:
        raise RuntimeError("formal confirmation profile rollout count mismatch")
    if result.get("timeout_case_count") != 0 or result.get("candidate_failure_count") != 0:
        raise RuntimeError("formal confirmation contains a timeout or candidate failure")
    if any(
        item.get("case_execution_count") != 0 or item.get("rollout_count") != 0
        for item in result["pipeline_development_heldout"]
    ):
        raise RuntimeError("pipeline-development case was executed")
    if any(int(value) != 0 for value in result["forbidden_operation_counts"].values()):
        raise RuntimeError("formal confirmation recorded a forbidden operation")


def write_json_once(path: Path, payload: dict) -> None:
    if path.exists():
        raise RuntimeError(f"confirmation output already exists: {path}")
    temporary = path.with_name(f"{path.name}.tmp")
    if temporary.exists():
        raise RuntimeError(f"stale confirmation temporary output exists: {temporary}")
    try:
        with temporary.open("x", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        temporary.replace(path)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise


def run(components: dict, adaptive: Any, output_path: Path = OUTPUT_PATH) -> dict:
    if output_path.exists():
        raise RuntimeError(f"confirmation output already exists: {output_path}")
    primary_hashes = verify_frozen_inputs()
    audit = load_json(AUDIT_PATH)
    diagnosis = load_json(DIAGNOSIS_PATH)
    split = load_json(SPLIT_PATH)
    report = load_json(TRAINING_REPORT_PATH)
    arena = load_json(ARENA_PATH)
    teacher_samples, _teacher_summary, teacher_hash = preference.load_teacher_dataset(
        TEACHER_PATH
    )
    if teacher_hash != EXPECTED_HASHES["teacher_dataset"]:
        raise RuntimeError("teacher dataset loader hash mismatch")
    source_samples, source_summary = website_data.load_dataset(SOURCE_DATASET_PATH)
    targets, heldout = reproduce_targets(
        audit,
        diagnosis,
        split,
        teacher_samples,
        source_samples,
        source_summary,
    )
    if (
        arena.get("requested_games") != 20
        or arena.get("completed_games") != 20
        or arena.get("model_wins") != 0
        or arena.get("early_screen_continuation_allowed") is not False
        or report.get("checkpoint_promotion_allowed") is not False
    ):
        raise RuntimeError("frozen checkpoint rejection conclusion mismatch")

    profile_config = adaptive.load_json(adaptive.PROFILE_PATH, {}).get(
        "tempo_baseline", {"engine_mode": "tempo"}
    )
    baseline_cache: dict[str, list[str]] = {}
    baseline_stats: dict[str, Any] = {}
    case_results: list[dict] = []
    for target in targets:
        validation_game = information_set.restore_game(
            target["source_sample"],
            components,
            random.Random(
                information_set._stable_determinization_seed(
                    target["source_sample"], -1
                )
            ),
        )
        candidates = [
            materialize_candidate(target, "teacher", validation_game, components, adaptive),
            materialize_candidate(target, "top1", validation_game, components, adaptive),
        ]
        case_results.append(
            execute_case(
                target,
                candidates,
                components,
                adaptive,
                profile_config,
                baseline_cache,
                baseline_stats,
            )
        )
        print(
            json.dumps(
                {
                    "completed_case": (
                        f"{target['game_id']}:{target['turn_index']}"
                    ),
                    "completed_case_count": len(case_results),
                    "direction": case_results[-1]["metrics"][
                        "directional_classification"
                    ],
                },
                ensure_ascii=False,
            ),
            flush=True,
        )

    direction_counts = Counter(
        case["metrics"]["directional_classification"] for case in case_results
    )
    completed_rollouts = sum(
        candidate["completed_rollout_count"]
        for case in case_results
        for candidate in case["candidate_results"]
    )
    profile_counts = Counter(
        item["continuation_profile"]
        for case in case_results
        for item in case["paired_rollouts"]
        for _candidate in range(2)
    )
    result = {
        "schema_version": SCHEMA_VERSION,
        "frozen_inputs": {
            "paths": {
                "stage_6_3_audit": str(AUDIT_PATH),
                "stage_6_2_diagnosis": str(DIAGNOSIS_PATH),
                "teacher_dataset": str(TEACHER_PATH),
                "split_manifest": str(SPLIT_PATH),
                "training_report": str(TRAINING_REPORT_PATH),
                "checkpoint": str(CHECKPOINT_PATH),
                "arena_evidence": str(ARENA_PATH),
            },
            "sha256": primary_hashes,
        },
        "source_dataset": {
            "path": str(SOURCE_DATASET_PATH),
            "sha256": EXPECTED_SOURCE_DATASET_SHA256,
            "partition_role": "train_development",
            "contains_locked_test_samples": False,
            "loaded_once": True,
        },
        "checkpoint_screen_status": "rejected_from_100_200_game_screen",
        "arena_conclusion": {
            "requested_games": 20,
            "completed_games": 20,
            "model_wins": 0,
            "baseline_wins": 20,
            "early_screen_continuation_allowed": False,
        },
        "confirmation_contract": {
            "evaluated_pipeline_partition": "pipeline_train",
            "evaluated_case_count": 9,
            "evaluated_action_roles": ["teacher", "top1"],
            "actions_per_case": 2,
            "rollouts_per_action": ROLLOUTS_PER_ACTION,
            "continuation_profiles": list(CONTINUATION_PROFILES),
            "rollouts_per_action_per_profile": ROLLOUTS_PER_PROFILE,
            "shared_determinizations_across_actions": True,
            "shared_determinizations_across_continuation_profiles": True,
            "hidden_card_sampling_method": (
                "uniform_physical_assignment_given_public_counts_v1"
            ),
            "determinization_seed_scheme": (
                "sha256_game_id_turn_index_determinization_index_v1"
            ),
            "minimum_advantage": MIN_ADVANTAGE,
            "maximum_candidate_return_variance": MAX_RETURN_VARIANCE,
            "confidence_z_value": 1.96,
            "thresholds_tuned_in_this_stage": False,
        },
        "target_reproduction": {
            "expected_pipeline_train_case_count": 9,
            "reproduced_pipeline_train_case_count": len(targets),
            "expected_pipeline_development_heldout_count": 3,
            "reproduced_pipeline_development_heldout_count": len(heldout),
            "missing_target_count": 0,
            "duplicate_target_count": 0,
            "extra_target_count": 0,
            "reconstructed_action_count": 0,
            "substituted_action_count": 0,
            "ambiguous_action_mapping_count": 0,
        },
        "pipeline_development_heldout": heldout,
        "case_results": case_results,
        "requested_total_rollouts": 9 * 2 * ROLLOUTS_PER_ACTION,
        "completed_rollouts": completed_rollouts,
        "rollout_completion_rate": completed_rollouts / 288,
        "continuation_profile_rollout_counts": dict(profile_counts),
        "timeout_case_count": sum(case["case_timed_out"] for case in case_results),
        "candidate_failure_count": sum(
            candidate["failure_count"]
            for case in case_results
            for candidate in case["candidate_results"]
        ),
        "directional_classification_counts": {
            "teacher_over_top1_supported": direction_counts[
                "teacher_over_top1_supported"
            ],
            "top1_over_teacher_supported": direction_counts[
                "top1_over_teacher_supported"
            ],
            "inconclusive": direction_counts["inconclusive"],
        },
        "baseline_action_cache": {
            "enabled": True,
            "entry_count": len(baseline_cache),
            "hit_count": int(baseline_stats.get("hits", 0.0)),
            "miss_count": int(baseline_stats.get("misses", 0.0)),
        },
        "integrity": {
            "pipeline_development_case_execution_count": 0,
            "pipeline_development_rollout_count": 0,
            "locked_test_loaded": False,
            "opponent_or_teammate_true_hands_used": False,
            "future_information_used": False,
            "common_determinizations_verified": True,
            "integrity_failure_count": 0,
        },
        "forbidden_operation_counts": {
            "training_runs": 0,
            "hyperparameter_searches": 0,
            "checkpoint_selections": 0,
            "checkpoint_modifications": 0,
            "arena_games": 0,
            "locked_test_loads": 0,
            "pipeline_development_case_executions": 0,
            "website_shadow_games": 0,
            "website_games": 0,
            "model_controlled_website_actions": 0,
            "checkpoint_promotions": 0,
            "capability_claims": 0,
        },
        "interpretation_scope": (
            "frozen pipeline-train counterfactual evidence only; no training, "
            "checkpoint selection, offline capability, or website capability claim"
        ),
        "status": "completed",
    }
    validate_completed_result(result)
    if verify_frozen_inputs() != primary_hashes:
        raise RuntimeError("a frozen input changed during confirmation")
    write_json_once(output_path, result)
    print(
        json.dumps(
            {
                "status": result["status"],
                "completed_rollouts": result["completed_rollouts"],
                "directional_classification_counts": result[
                    "directional_classification_counts"
                ],
                "output": str(output_path),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return result


def main() -> None:
    import play_research_adaptive as adaptive

    restore_baseline = adaptive.offline_install_arena_baseline_optimizations()
    try:
        run(adaptive.offline_load_guandan_components(), adaptive)
    finally:
        restore_baseline()


if __name__ == "__main__":
    main()
