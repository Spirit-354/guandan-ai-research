from __future__ import annotations

import argparse
from collections import Counter
import json
import math
from pathlib import Path
import random
from typing import Any

import website_danzero_dataset as website_data
import website_information_set as information_set
import website_teacher_preference as preference
import website_teacher_preference_unpaired_confirmation as frozen_confirmation


SCHEMA_VERSION = "website_teacher_preference_corrective_residual_train_confirmation_v1"
AUDIT_PATH = Path(
    "website_teacher_preference_corrective_residual_evidence_audit_v1.json"
)
DIAGNOSIS_PATH = Path("website_teacher_preference_corrective_failure_diagnosis_v1.json")
TEACHER_PATH = Path("website_information_set_teacher_dataset_v6.pth")
SPLIT_PATH = Path("website_teacher_preference_split_v1.json")
SOURCE_DATASET_PATH = Path("website_danzero_shadow_extension_v5.train_dev.pth")
STAGE_6_4_CONFIRMATION_PATH = Path(
    "website_teacher_preference_unpaired_train_confirmation_v1.json"
)
OLD_CHECKPOINT_PATH = Path(
    "models_website_teacher_preference_v1/website_teacher_preference_final.pth"
)
CORRECTIVE_CHECKPOINT_PATH = Path(
    "models_website_teacher_preference_corrective_v1/"
    "website_teacher_preference_corrective_final.pth"
)
OUTPUT_PATH = Path(
    "website_teacher_preference_corrective_residual_train_confirmation_v1.json"
)

EXPECTED_HASHES = {
    "stage_6_8_audit": "676232033f07051670b4407f15aca9f3939d9754ac2dcf4d078957263a1e2a6b",
    "stage_6_7_diagnosis": "2b4359470e74f5eae28d6589477aca5f929ae6b5b88e094fa86209bf4328163d",
    "teacher_dataset": "a74416e6facb28a1bc64563eba90cb33d460dc9e59cc2109518da142465e15f8",
    "split_manifest": "5a15e514dc9bc51d77d300837151d9f1a49250f42885cc7940725bcbe4d35107",
    "source_train_development_dataset": "e5e220c3c770116ca9d01478e98e610dd6309a0f3d6c17088a8328f62b47174b",
    "stage_6_4_confirmation": "8e17377b5a1523d9f0a47af7218d687e062a3ade671c57f387eb4c1a0888cfae",
    "old_checkpoint": "c54801a9db05100c2fe5a9bf610a64fc7c94dc2cd947dfaab115ff827bd90919",
    "corrective_checkpoint": "8cb368c8c0ae3f8c41c577e055ddd4796cbaae8163720cc630a435aa25bc1a49",
}
FROZEN_PATHS = {
    "stage_6_8_audit": AUDIT_PATH,
    "stage_6_7_diagnosis": DIAGNOSIS_PATH,
    "teacher_dataset": TEACHER_PATH,
    "split_manifest": SPLIT_PATH,
    "source_train_development_dataset": SOURCE_DATASET_PATH,
    "stage_6_4_confirmation": STAGE_6_4_CONFIRMATION_PATH,
    "old_checkpoint": OLD_CHECKPOINT_PATH,
    "corrective_checkpoint": CORRECTIVE_CHECKPOINT_PATH,
}
EXPECTED_TRAIN_CASES = 8
EXPECTED_DEVELOPMENT_CASES = 3
EXPECTED_TOTAL_ROLLOUTS = (
    EXPECTED_TRAIN_CASES * 2 * frozen_confirmation.ROLLOUTS_PER_ACTION
)


def load_json(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError(f"{path} must contain a JSON object")
    return payload


def verify_frozen_hashes() -> dict[str, str]:
    actual = {}
    for name, path in FROZEN_PATHS.items():
        value = frozen_confirmation.sha256(path)
        if value != EXPECTED_HASHES[name]:
            raise RuntimeError(f"{name} SHA-256 mismatch")
        actual[name] = value
    return actual


def ensure_unused_output(output_path: Path = OUTPUT_PATH) -> None:
    if output_path.exists():
        raise RuntimeError(f"confirmation output already exists: {output_path}")
    temporary = output_path.with_name(f"{output_path.name}.tmp")
    if temporary.exists():
        raise RuntimeError(f"stale confirmation temporary output exists: {temporary}")


def validate_frozen_confirmation_contract(stage_6_4: dict) -> dict:
    if (
        stage_6_4.get("schema_version") != frozen_confirmation.SCHEMA_VERSION
        or stage_6_4.get("status") != "completed"
        or stage_6_4.get("requested_total_rollouts") != 288
        or stage_6_4.get("completed_rollouts") != 288
    ):
        raise RuntimeError("Stage 6.4 completion conclusion mismatch")
    contract = stage_6_4.get("confirmation_contract") or {}
    expected = {
        "evaluated_pipeline_partition": "pipeline_train",
        "evaluated_action_roles": ["teacher", "top1"],
        "actions_per_case": 2,
        "rollouts_per_action": 16,
        "continuation_profiles": ["greedy_bot", "tempo_baseline"],
        "rollouts_per_action_per_profile": 8,
        "shared_determinizations_across_actions": True,
        "shared_determinizations_across_continuation_profiles": True,
        "hidden_card_sampling_method": (
            "uniform_physical_assignment_given_public_counts_v1"
        ),
        "determinization_seed_scheme": (
            "sha256_game_id_turn_index_determinization_index_v1"
        ),
        "minimum_advantage": 0.15,
        "maximum_candidate_return_variance": 0.50,
        "confidence_z_value": 1.96,
        "thresholds_tuned_in_this_stage": False,
    }
    for key, value in expected.items():
        if contract.get(key) != value:
            raise RuntimeError(f"Stage 6.4 frozen contract {key} mismatch")
    if (
        stage_6_4.get("timeout_case_count") != 0
        or stage_6_4.get("candidate_failure_count") != 0
        or sum((stage_6_4.get("forbidden_operation_counts") or {}).values()) != 0
    ):
        raise RuntimeError("Stage 6.4 integrity conclusion mismatch")
    return expected


def reproduce_targets(
    audit: dict,
    diagnosis: dict,
    split: dict,
    teacher_samples: list[dict],
    source_samples: list[dict],
    source_summary: dict,
) -> tuple[list[dict], list[dict]]:
    if (
        audit.get("schema_version")
        != "website_teacher_preference_corrective_residual_evidence_audit_v1"
        or audit.get("status") != "completed"
        or audit.get("future_counterfactual_manifest_executed") is not False
        or audit.get("future_counterfactual_manifest_case_count") != 8
    ):
        raise RuntimeError("Stage 6.8 audit conclusion mismatch")
    if (
        diagnosis.get("schema_version")
        != "website_teacher_preference_corrective_failure_diagnosis_v1"
        or diagnosis.get("status") != "completed"
    ):
        raise RuntimeError("Stage 6.7 diagnosis conclusion mismatch")
    if source_summary.get("partition_role") != "train_development":
        raise RuntimeError("source dataset is not train/development physical data")
    if source_summary.get("contains_locked_test_samples") is not False:
        raise RuntimeError("source dataset contains locked-test samples")
    if any(sample.get("split") == "locked_test" for sample in source_samples):
        raise RuntimeError("source dataset loaded a locked-test sample")

    train_ids = {str(value) for value in split.get("pipeline_train_game_ids") or []}
    development_ids = {
        str(value) for value in split.get("pipeline_development_game_ids") or []
    }
    if len(train_ids) != 18 or len(development_ids) != 4 or train_ids & development_ids:
        raise RuntimeError("frozen 18/4 pipeline split mismatch")
    teacher_by_key = {
        (str(sample["game_id"]), int(sample["turn_index"])): sample
        for sample in teacher_samples
    }
    if len(teacher_by_key) != len(teacher_samples):
        raise RuntimeError("teacher source state key is duplicated")
    source_train_key_counts = Counter(
        (str(sample["game_id"]), int(sample["turn_index"]))
        for sample in source_samples
        if sample.get("split") == "train"
    )
    source_train_by_key = {
        (str(sample["game_id"]), int(sample["turn_index"])): sample
        for sample in source_samples
        if sample.get("split") == "train"
    }
    train_audit_by_key = {
        (str(item["game_id"]), int(item["turn_index"])): item
        for item in audit.get("pipeline_train_target_audits") or []
    }
    manifest = audit.get("future_counterfactual_manifest") or []
    development_items = audit.get("pipeline_development_identity_only") or []
    if (
        len(manifest) != EXPECTED_TRAIN_CASES
        or len(train_audit_by_key) != EXPECTED_TRAIN_CASES
        or len(development_items) != EXPECTED_DEVELOPMENT_CASES
    ):
        raise RuntimeError("Stage 6.8 eight/three accounting mismatch")

    targets = []
    seen = set()
    for entry in manifest:
        key = (str(entry["game_id"]), int(entry["turn_index"]))
        if (
            key in seen
            or key not in teacher_by_key
            or key not in source_train_by_key
            or key not in train_audit_by_key
            or source_train_key_counts[key] != 1
        ):
            raise RuntimeError("train residual target is duplicate or missing")
        seen.add(key)
        if (
            key[0] not in train_ids
            or entry.get("pipeline_partition") != "pipeline_train"
            or entry.get("execution_allowed_in_this_stage") is not False
        ):
            raise RuntimeError("train residual manifest provenance mismatch")
        teacher = teacher_by_key[key]
        source = source_train_by_key[key]
        target_audit = train_audit_by_key[key]
        actions = source.get("legal_actions") or []
        metadata = source.get("legal_action_metadata") or []
        teacher_matches = [
            index
            for index, action in enumerate(actions)
            if action == teacher.get("teacher_action")
        ]
        if len(teacher_matches) != 1:
            raise RuntimeError("teacher action mapping is ambiguous")
        teacher_index = teacher_matches[0]
        residual_index = int(entry["top1_action_index"])
        if (
            source.get("split") != "train"
            or source.get("state") != teacher.get("state")
            or actions != teacher.get("legal_actions")
            or len(actions) != len(metadata)
            or frozen_confirmation.action_order_sha256(actions)
            != target_audit.get("legal_action_order_sha256")
            or target_audit.get("pipeline_partition") != "pipeline_train"
            or residual_index != target_audit.get("top1_action_index")
            or entry.get("top1_action_sha256") != target_audit.get("top1_action_sha256")
            or frozen_confirmation.action_sha256(actions[residual_index])
            != entry.get("top1_action_sha256")
        ):
            raise RuntimeError("train residual state/action identity mismatch")
        teacher_cards = metadata[teacher_index].get("cards")
        residual_cards = metadata[residual_index].get("cards")
        if (
            teacher_cards != target_audit["teacher_physical_identity"]["cards_website"]
            or residual_cards != target_audit["top1_physical_identity"]["cards_website"]
            or teacher_cards != teacher.get("teacher_physical_cards")
        ):
            raise RuntimeError("train residual physical-card identity mismatch")
        targets.append(
            {
                "game_id": key[0],
                "turn_index": key[1],
                "pipeline_partition": "pipeline_train",
                "source_sample": source,
                "legal_action_count": len(actions),
                "legal_action_order_sha256": frozen_confirmation.action_order_sha256(
                    actions
                ),
                "teacher_action_index": teacher_index,
                "teacher_action_sha256": frozen_confirmation.action_sha256(
                    actions[teacher_index]
                ),
                "teacher_physical_identity": target_audit["teacher_physical_identity"],
                "top1_action_index": residual_index,
                "top1_action_sha256": entry["top1_action_sha256"],
                "top1_physical_identity": target_audit["top1_physical_identity"],
                "residual_action_index": residual_index,
                "residual_action_sha256": entry["top1_action_sha256"],
                "residual_physical_identity": target_audit["top1_physical_identity"],
            }
        )

    heldout = []
    heldout_seen = set()
    for item in development_items:
        key = (str(item["game_id"]), int(item["turn_index"]))
        if key in heldout_seen or key[0] not in development_ids:
            raise RuntimeError("development residual identity mismatch")
        heldout_seen.add(key)
        heldout.append(
            {
                **item,
                "source_sample_mapping_count": 0,
                "case_execution_count": 0,
                "rollout_count": 0,
                "held_out_from_candidate_threshold_objective_design": True,
            }
        )
    return targets, heldout


def normalize_metrics(metrics: dict) -> dict:
    profiles = {
        name: {
            "paired_count": item["paired_count"],
            "teacher_minus_residual_mean_advantage": item[
                "teacher_minus_top1_mean_advantage"
            ],
            "residual_minus_teacher_mean_advantage": -float(
                item["teacher_minus_top1_mean_advantage"]
            ),
            "paired_return_variance": item["paired_return_variance"],
        }
        for name, item in metrics["continuation_policy_advantages"].items()
    }
    standard_error = math.sqrt(
        metrics["paired_return_variance"] / metrics["paired_count"]
    )
    residual_advantage = -float(metrics["teacher_minus_top1_advantage"])
    residual_lower_bound = residual_advantage - 1.96 * standard_error
    residual_confidence = max(0.0, min(1.0, 0.5 + residual_lower_bound / 2.0))
    direction = {
        "teacher_over_top1_supported": "teacher_over_residual_supported",
        "top1_over_teacher_supported": "residual_over_teacher_supported",
        "inconclusive": "inconclusive",
    }[metrics["directional_classification"]]
    return {
        "paired_count": metrics["paired_count"],
        "teacher_mean_return": metrics["teacher_mean_return"],
        "teacher_return_variance": metrics["teacher_return_variance"],
        "residual_mean_return": metrics["top1_mean_return"],
        "residual_return_variance": metrics["top1_return_variance"],
        "teacher_minus_residual_advantage": metrics["teacher_minus_top1_advantage"],
        "residual_minus_teacher_advantage": residual_advantage,
        "paired_return_variance": metrics["paired_return_variance"],
        "teacher_minus_residual_95_lower_bound": metrics[
            "teacher_minus_top1_95_lower_bound"
        ],
        "teacher_over_residual_confidence": metrics["teacher_over_top1_confidence"],
        "residual_minus_teacher_95_lower_bound": residual_lower_bound,
        "residual_over_teacher_confidence": residual_confidence,
        "continuation_policy_advantages": profiles,
        "teacher_over_residual_supported": metrics["teacher_over_top1_supported"],
        "teacher_over_residual_failure_reasons": metrics[
            "teacher_over_top1_failure_reasons"
        ],
        "residual_over_teacher_supported": metrics["top1_over_teacher_supported"],
        "residual_over_teacher_failure_reasons": metrics[
            "top1_over_teacher_failure_reasons"
        ],
        "directional_classification": direction,
    }


def normalize_case_result(raw: dict) -> dict:
    candidate_results = []
    for candidate in raw["candidate_results"]:
        item = dict(candidate)
        if item["role"] == "top1":
            item["role"] = "residual"
        candidate_results.append(item)
    paired_rollouts = []
    for rollout in raw["paired_rollouts"]:
        paired_rollouts.append(
            {
                "rollout_index": rollout["rollout_index"],
                "continuation_profile": rollout["continuation_profile"],
                "determinization_index": rollout["determinization_index"],
                "determinization_seed": rollout["determinization_seed"],
                "teacher_return": rollout["teacher_return"],
                "residual_return": rollout["top1_return"],
                "teacher_minus_residual_return": rollout["teacher_minus_top1_return"],
            }
        )
    return {
        "game_id": raw["game_id"],
        "turn_index": raw["turn_index"],
        "pipeline_partition": raw["pipeline_partition"],
        "legal_action_count": raw["legal_action_count"],
        "legal_action_order_sha256": raw["legal_action_order_sha256"],
        "case_seconds": raw["case_seconds"],
        "case_timed_out": raw["case_timed_out"],
        "candidate_results": candidate_results,
        "paired_rollouts": paired_rollouts,
        "metrics": normalize_metrics(raw["metrics"]),
    }


def execute_residual_case(
    target: dict,
    candidates: list[dict],
    components: dict,
    adaptive: Any,
    profile_config: dict,
    baseline_cache: dict[str, list[str]],
    baseline_stats: dict[str, Any],
) -> dict:
    raw = frozen_confirmation.execute_case(
        target,
        candidates,
        components,
        adaptive,
        profile_config,
        baseline_cache,
        baseline_stats,
    )
    return normalize_case_result(raw)


def load_context() -> dict:
    frozen_hashes = verify_frozen_hashes()
    audit = load_json(AUDIT_PATH)
    diagnosis = load_json(DIAGNOSIS_PATH)
    split = load_json(SPLIT_PATH)
    stage_6_4 = load_json(STAGE_6_4_CONFIRMATION_PATH)
    contract = validate_frozen_confirmation_contract(stage_6_4)
    teacher_samples, _teacher_summary, teacher_hash = preference.load_teacher_dataset(
        TEACHER_PATH
    )
    if teacher_hash != frozen_hashes["teacher_dataset"]:
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
    if len(targets) != EXPECTED_TRAIN_CASES or len(heldout) != (
        EXPECTED_DEVELOPMENT_CASES
    ):
        raise RuntimeError("Stage 6.9 target accounting mismatch")
    return {
        "frozen_hashes": frozen_hashes,
        "frozen_contract": contract,
        "targets": targets,
        "heldout": heldout,
        "source_summary": source_summary,
    }


def validate_completed_result(result: dict) -> None:
    cases = result.get("case_results") or []
    if len(cases) != EXPECTED_TRAIN_CASES:
        raise RuntimeError("formal confirmation did not produce exactly eight cases")
    if len(result.get("pipeline_development_heldout") or []) != (
        EXPECTED_DEVELOPMENT_CASES
    ):
        raise RuntimeError("formal confirmation lost development isolation")
    if (
        result.get("requested_total_rollouts") != EXPECTED_TOTAL_ROLLOUTS
        or result.get("completed_rollouts") != EXPECTED_TOTAL_ROLLOUTS
    ):
        raise RuntimeError("formal confirmation rollout accounting mismatch")
    if result.get("continuation_profile_rollout_counts") != {
        "greedy_bot": 128,
        "tempo_baseline": 128,
    }:
        raise RuntimeError("formal confirmation profile accounting mismatch")
    if (
        result.get("timeout_case_count") != 0
        or result.get("candidate_failure_count") != 0
    ):
        raise RuntimeError("formal confirmation contains timeout/candidate failure")
    if any(
        item.get("source_sample_mapping_count") != 0
        or item.get("case_execution_count") != 0
        or item.get("rollout_count") != 0
        for item in result["pipeline_development_heldout"]
    ):
        raise RuntimeError("pipeline-development residual case was mapped or executed")
    if sum((result.get("forbidden_operation_counts") or {}).values()) != 0:
        raise RuntimeError("formal confirmation recorded a forbidden operation")


def build_result(context: dict, case_results: list[dict]) -> dict:
    direction_counts = Counter(
        case["metrics"]["directional_classification"] for case in case_results
    )
    completed_rollouts = sum(
        candidate["completed_rollout_count"]
        for case in case_results
        for candidate in case["candidate_results"]
    )
    profile_counts = Counter(
        rollout["continuation_profile"]
        for case in case_results
        for rollout in case["paired_rollouts"]
        for _candidate in range(2)
    )
    supported = [
        {
            "game_id": case["game_id"],
            "turn_index": case["turn_index"],
            "directional_classification": case["metrics"]["directional_classification"],
            "teacher_action_sha256": case["candidate_results"][0]["action_sha256"],
            "residual_action_sha256": case["candidate_results"][1]["action_sha256"],
            "metrics": case["metrics"],
        }
        for case in case_results
        if case["metrics"]["directional_classification"] != "inconclusive"
    ]
    result = {
        "schema_version": SCHEMA_VERSION,
        "status": "completed",
        "frozen_inputs": {
            "paths": {name: str(path) for name, path in FROZEN_PATHS.items()},
            "sha256": context["frozen_hashes"],
        },
        "source_dataset": {
            "path": str(SOURCE_DATASET_PATH),
            "sha256": EXPECTED_HASHES["source_train_development_dataset"],
            "partition_role": "train_development",
            "contains_locked_test_samples": False,
            "loaded_once": True,
        },
        "confirmation_contract": {
            "evaluated_pipeline_partition": "pipeline_train",
            "evaluated_case_count": EXPECTED_TRAIN_CASES,
            "evaluated_action_roles": ["teacher", "residual"],
            "actions_per_case": 2,
            "rollouts_per_action": frozen_confirmation.ROLLOUTS_PER_ACTION,
            "continuation_profiles": list(frozen_confirmation.CONTINUATION_PROFILES),
            "rollouts_per_action_per_profile": (
                frozen_confirmation.ROLLOUTS_PER_PROFILE
            ),
            "shared_determinizations_across_actions": True,
            "shared_determinizations_across_continuation_profiles": True,
            "hidden_card_sampling_method": context["frozen_contract"][
                "hidden_card_sampling_method"
            ],
            "determinization_seed_scheme": context["frozen_contract"][
                "determinization_seed_scheme"
            ],
            "minimum_advantage": frozen_confirmation.MIN_ADVANTAGE,
            "maximum_candidate_return_variance": (
                frozen_confirmation.MAX_RETURN_VARIANCE
            ),
            "confidence_z_value": 1.96,
            "thresholds_tuned_in_this_stage": False,
        },
        "target_reproduction": {
            "expected_pipeline_train_case_count": EXPECTED_TRAIN_CASES,
            "reproduced_pipeline_train_case_count": len(context["targets"]),
            "expected_pipeline_development_heldout_count": (EXPECTED_DEVELOPMENT_CASES),
            "reproduced_pipeline_development_heldout_count": len(context["heldout"]),
            "missing_target_count": 0,
            "duplicate_target_count": 0,
            "extra_target_count": 0,
            "reconstructed_action_count": 0,
            "substituted_action_count": 0,
            "ambiguous_action_mapping_count": 0,
            "non_train_source_mapping_count": 0,
        },
        "pipeline_development_heldout": context["heldout"],
        "case_results": case_results,
        "requested_total_rollouts": EXPECTED_TOTAL_ROLLOUTS,
        "completed_rollouts": completed_rollouts,
        "rollout_completion_rate": completed_rollouts / EXPECTED_TOTAL_ROLLOUTS,
        "continuation_profile_rollout_counts": dict(profile_counts),
        "timeout_case_count": sum(case["case_timed_out"] for case in case_results),
        "candidate_failure_count": sum(
            candidate["failure_count"]
            for case in case_results
            for candidate in case["candidate_results"]
        ),
        "directional_classification_counts": {
            "teacher_over_residual_supported": direction_counts[
                "teacher_over_residual_supported"
            ],
            "residual_over_teacher_supported": direction_counts[
                "residual_over_teacher_supported"
            ],
            "inconclusive": direction_counts["inconclusive"],
        },
        "supported_comparison_manifest": supported,
        "supported_comparison_manifest_executed_as_training": False,
        "unsupported_ordering_label_count": 0,
        "dataset_constructed": False,
        "new_objective_defined": False,
        "integrity": {
            "pipeline_development_source_mapping_count": 0,
            "pipeline_development_case_execution_count": 0,
            "pipeline_development_rollout_count": 0,
            "locked_test_loaded": False,
            "complete_website_dataset_loaded": False,
            "opponent_or_teammate_true_hands_used": False,
            "future_information_used": False,
            "common_determinizations_verified": True,
            "integrity_failure_count": 0,
        },
        "forbidden_operation_counts": {
            "training_runs": 0,
            "fine_tuning_runs": 0,
            "threshold_tuning_runs": 0,
            "checkpoint_selections": 0,
            "checkpoint_modifications": 0,
            "dataset_constructions": 0,
            "new_objective_definitions": 0,
            "complete_website_dataset_loads": 0,
            "locked_test_loads": 0,
            "arena_games": 0,
            "pipeline_development_source_mappings": 0,
            "pipeline_development_case_executions": 0,
            "website_shadow_games": 0,
            "website_games": 0,
            "model_controlled_website_actions": 0,
            "checkpoint_promotions": 0,
            "capability_claims": 0,
        },
        "interpretation_scope": (
            "frozen pipeline-train residual counterfactual evidence only; no "
            "dataset, objective, training, checkpoint, Arena, or capability claim"
        ),
    }
    validate_completed_result(result)
    return result


def preflight() -> dict:
    ensure_unused_output()
    context = load_context()
    result = {
        "status": "ready",
        "output_exists": False,
        "frozen_hash_count": len(context["frozen_hashes"]),
        "pipeline_train_case_count": len(context["targets"]),
        "pipeline_development_heldout_count": len(context["heldout"]),
        "requested_total_rollouts": EXPECTED_TOTAL_ROLLOUTS,
        "pipeline_development_source_mapping_count": 0,
        "pipeline_development_case_execution_count": 0,
        "pipeline_development_rollout_count": 0,
    }
    print(json.dumps(result, indent=2))
    return result


def run(components: dict, adaptive: Any) -> dict:
    ensure_unused_output()
    context = load_context()
    profile_config = adaptive.load_json(adaptive.PROFILE_PATH, {}).get(
        "tempo_baseline", {"engine_mode": "tempo"}
    )
    baseline_cache: dict[str, list[str]] = {}
    baseline_stats: dict[str, Any] = {}
    case_results = []
    for target in context["targets"]:
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
            frozen_confirmation.materialize_candidate(
                target, "teacher", validation_game, components, adaptive
            ),
            frozen_confirmation.materialize_candidate(
                target, "top1", validation_game, components, adaptive
            ),
        ]
        case_results.append(
            execute_residual_case(
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
                    "completed_case": f"{target['game_id']}:{target['turn_index']}",
                    "completed_case_count": len(case_results),
                    "direction": case_results[-1]["metrics"][
                        "directional_classification"
                    ],
                },
                ensure_ascii=False,
            ),
            flush=True,
        )
    result = build_result(context, case_results)
    result["baseline_action_cache"] = {
        "enabled": True,
        "entry_count": len(baseline_cache),
        "hit_count": int(baseline_stats.get("hits", 0.0)),
        "miss_count": int(baseline_stats.get("misses", 0.0)),
    }
    if verify_frozen_hashes() != context["frozen_hashes"]:
        raise RuntimeError("a frozen input changed during confirmation")
    frozen_confirmation.write_json_once(OUTPUT_PATH, result)
    print(
        json.dumps(
            {
                "status": result["status"],
                "completed_rollouts": result["completed_rollouts"],
                "directional_classification_counts": result[
                    "directional_classification_counts"
                ],
                "output": str(OUTPUT_PATH),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return result


def audit() -> dict:
    saved = load_json(OUTPUT_PATH)
    context = load_context()
    if saved.get("schema_version") != SCHEMA_VERSION or saved.get("status") != (
        "completed"
    ):
        raise RuntimeError("saved confirmation schema/status mismatch")
    if saved.get("frozen_inputs", {}).get("sha256") != context["frozen_hashes"]:
        raise RuntimeError("saved confirmation frozen hashes mismatch")
    if saved.get("pipeline_development_heldout") != context["heldout"]:
        raise RuntimeError("development held-out identities changed")
    cases = saved.get("case_results") or []
    if len(cases) != len(context["targets"]):
        raise RuntimeError("saved confirmation case count mismatch")

    directions = Counter()
    completed = 0
    profiles = Counter()
    expected_supported = []
    for target, case in zip(context["targets"], cases):
        key = (target["game_id"], target["turn_index"])
        if key != (str(case.get("game_id")), int(case.get("turn_index"))):
            raise RuntimeError("saved confirmation case order/key mismatch")
        if (
            case.get("legal_action_count") != target["legal_action_count"]
            or case.get("legal_action_order_sha256")
            != target["legal_action_order_sha256"]
        ):
            raise RuntimeError("saved confirmation state identity mismatch")
        candidates = case.get("candidate_results") or []
        if [item.get("role") for item in candidates] != ["teacher", "residual"]:
            raise RuntimeError("saved confirmation candidate roles mismatch")
        expected_candidates = [
            (
                target["teacher_action_index"],
                target["teacher_action_sha256"],
                target["teacher_physical_identity"]["cards_website"],
            ),
            (
                target["residual_action_index"],
                target["residual_action_sha256"],
                target["residual_physical_identity"]["cards_website"],
            ),
        ]
        for candidate, expected in zip(candidates, expected_candidates):
            if (
                candidate.get("action_index") != expected[0]
                or candidate.get("action_sha256") != expected[1]
                or candidate.get("physical_cards_website") != expected[2]
                or candidate.get("requested_rollout_count") != 16
                or candidate.get("completed_rollout_count") != 16
                or candidate.get("completion_rate") != 1.0
                or candidate.get("failure_count") != 0
                or candidate.get("failures") != []
            ):
                raise RuntimeError("saved confirmation candidate identity mismatch")
        paired = case.get("paired_rollouts") or []
        schedule = frozen_confirmation.rollout_schedule()
        if len(paired) != len(schedule):
            raise RuntimeError("saved confirmation paired rollout count mismatch")
        teacher_returns = []
        residual_returns = []
        for expected, rollout in zip(schedule, paired):
            seed = information_set._stable_determinization_seed(
                target["source_sample"], expected["determinization_index"]
            )
            if (
                rollout.get("rollout_index") != expected["rollout_index"]
                or rollout.get("continuation_profile")
                != expected["continuation_profile"]
                or rollout.get("determinization_index")
                != expected["determinization_index"]
                or rollout.get("determinization_seed") != seed
                or rollout.get("teacher_return") is None
                or rollout.get("residual_return") is None
                or rollout.get("teacher_minus_residual_return")
                != float(rollout["teacher_return"]) - float(rollout["residual_return"])
            ):
                raise RuntimeError("saved confirmation schedule/return mismatch")
            teacher_returns.append(float(rollout["teacher_return"]))
            residual_returns.append(float(rollout["residual_return"]))
            profiles[rollout["continuation_profile"]] += 2
        recomputed_metrics = normalize_metrics(
            frozen_confirmation.directional_metrics(teacher_returns, residual_returns)
        )
        if case.get("metrics") != recomputed_metrics:
            raise RuntimeError("saved confirmation metrics mismatch")
        for candidate, values in zip(candidates, (teacher_returns, residual_returns)):
            if candidate.get("mean_return") != sum(values) / len(
                values
            ) or candidate.get(
                "return_variance"
            ) != frozen_confirmation.sample_variance(
                values
            ):
                raise RuntimeError("saved confirmation candidate arithmetic mismatch")
            completed += candidate["completed_rollout_count"]
        directions[recomputed_metrics["directional_classification"]] += 1
        if recomputed_metrics["directional_classification"] != "inconclusive":
            expected_supported.append(
                {
                    "game_id": target["game_id"],
                    "turn_index": target["turn_index"],
                    "directional_classification": recomputed_metrics[
                        "directional_classification"
                    ],
                    "teacher_action_sha256": candidates[0]["action_sha256"],
                    "residual_action_sha256": candidates[1]["action_sha256"],
                    "metrics": recomputed_metrics,
                }
            )

    expected_direction_counts = {
        "teacher_over_residual_supported": directions[
            "teacher_over_residual_supported"
        ],
        "residual_over_teacher_supported": directions[
            "residual_over_teacher_supported"
        ],
        "inconclusive": directions["inconclusive"],
    }
    if (
        saved.get("completed_rollouts") != completed
        or saved.get("continuation_profile_rollout_counts") != dict(profiles)
        or saved.get("directional_classification_counts") != expected_direction_counts
        or saved.get("supported_comparison_manifest") != expected_supported
    ):
        raise RuntimeError("saved confirmation aggregate mismatch")
    validate_completed_result(saved)
    if verify_frozen_hashes() != context["frozen_hashes"]:
        raise RuntimeError("a frozen input changed during independent audit")
    result = {
        "status": "passed",
        "input_and_action_hashes_exact": True,
        "determinization_seeds_exact": True,
        "paired_returns_and_arithmetic_exact": True,
        "means_variances_confidence_and_profiles_exact": True,
        "directional_classifications_exact": True,
        "partition_counts_and_aggregates_exact": True,
        "pipeline_development_source_mapping_count": 0,
        "pipeline_development_case_execution_count": 0,
        "pipeline_development_rollout_count": 0,
        "forbidden_operation_count": sum(saved["forbidden_operation_counts"].values()),
    }
    print(json.dumps(result, indent=2))
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--preflight", action="store_true")
    modes.add_argument("--run", action="store_true")
    modes.add_argument("--audit", action="store_true")
    args = parser.parse_args()
    if args.preflight:
        preflight()
        return
    if args.audit:
        audit()
        return
    import play_research_adaptive as adaptive

    restore_baseline = adaptive.offline_install_arena_baseline_optimizations()
    try:
        run(adaptive.offline_load_guandan_components(), adaptive)
    finally:
        restore_baseline()


if __name__ == "__main__":
    main()
