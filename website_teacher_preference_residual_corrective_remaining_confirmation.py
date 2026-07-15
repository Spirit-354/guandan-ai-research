from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import random
from typing import Any

import website_danzero_dataset as website_data
import website_information_set as information_set
import website_teacher_preference as preference
import website_teacher_preference_corrective_residual_confirmation as stage_6_9_impl
import website_teacher_preference_unpaired_confirmation as frozen_confirmation


SCHEMA_VERSION = (
    "website_teacher_preference_residual_corrective_remaining_train_confirmation_v1"
)
AUDIT_PATH = Path(
    "website_teacher_preference_residual_corrective_remaining_evidence_audit_v1.json"
)
DIAGNOSIS_PATH = Path(
    "website_teacher_preference_residual_corrective_failure_diagnosis_v1.json"
)
STAGE_6_9_PATH = Path(
    "website_teacher_preference_corrective_residual_train_confirmation_v1.json"
)
TEACHER_PATH = Path("website_information_set_teacher_dataset_v6.pth")
SPLIT_PATH = Path("website_teacher_preference_split_v1.json")
SOURCE_DATASET_PATH = Path("website_danzero_shadow_extension_v5.train_dev.pth")
ARENA_PATH = Path("website_teacher_preference_arena_smoke20_v1.json")
OUTPUT_PATH = Path(
    "website_teacher_preference_residual_corrective_remaining_train_confirmation_v1.json"
)

EXPECTED_HASHES = {
    "stage_6_13_audit": "2dff04b2be010a10c3f3e77a144f98d1aeca89a885e21cc98be9c51868b53345",
    "stage_6_12_diagnosis": "e8e12f4fd259bc0c2689100d08bdfb3b71662e29c8af0f1e1013fbc6e9573e9f",
    "stage_6_9_confirmation": "352cd0dfe0a4c958ba0555b776326a2b58470a980aef461ed49d4c59a7474c7a",
    "teacher_dataset": "a74416e6facb28a1bc64563eba90cb33d460dc9e59cc2109518da142465e15f8",
    "split_manifest": "5a15e514dc9bc51d77d300837151d9f1a49250f42885cc7940725bcbe4d35107",
    "source_train_development_dataset": "e5e220c3c770116ca9d01478e98e610dd6309a0f3d6c17088a8328f62b47174b",
    "stage_6_1_arena": "aa45da9de202194102fe8d11e612ad3eb4b51177fd910b9a7948836afd2a1fe6",
}
FROZEN_PATHS = {
    "stage_6_13_audit": AUDIT_PATH,
    "stage_6_12_diagnosis": DIAGNOSIS_PATH,
    "stage_6_9_confirmation": STAGE_6_9_PATH,
    "teacher_dataset": TEACHER_PATH,
    "split_manifest": SPLIT_PATH,
    "source_train_development_dataset": SOURCE_DATASET_PATH,
    "stage_6_1_arena": ARENA_PATH,
}
EXPECTED_EXECUTED = [
    ("13957", 14, 17),
    ("14038", 12, 3),
    ("13872", 4, 19),
]
EXPECTED_EXCLUDED = [
    ("14077", 10, 0),
    ("13959", 7, 5),
    ("14025", 20, 1),
]
EXPECTED_DEVELOPMENT = [("13992", 16), ("14074", 9), ("13871", 9)]
EXPECTED_TRAIN_CASES = len(EXPECTED_EXECUTED)
EXPECTED_EXCLUDED_CASES = len(EXPECTED_EXCLUDED)
EXPECTED_DEVELOPMENT_CASES = len(EXPECTED_DEVELOPMENT)
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
    stage_6_9_impl.ensure_unused_output(output_path)


def validate_frozen_authorities(
    audit: dict, diagnosis: dict, stage_6_9: dict, arena: dict
) -> dict:
    if (
        audit.get("schema_version")
        != "website_teacher_preference_residual_corrective_remaining_evidence_audit_v1"
        or audit.get("status") != "completed"
        or audit.get("future_counterfactual_manifest_case_count") != 6
        or audit.get("future_counterfactual_manifest_new_confirmation_needed_count")
        != 3
        or audit.get("future_counterfactual_manifest_existing_inconclusive_count")
        != 3
        or audit.get("future_counterfactual_manifest_executed") is not False
        or sum((audit.get("forbidden_operation_counts") or {}).values()) != 0
    ):
        raise RuntimeError("Stage 6.13 frozen conclusion mismatch")
    if (
        diagnosis.get("schema_version")
        != "website_teacher_preference_residual_corrective_failure_diagnosis_v1"
        or diagnosis.get("status") != "completed"
        or sum((diagnosis.get("forbidden_operation_counts") or {}).values()) != 0
    ):
        raise RuntimeError("Stage 6.12 frozen conclusion mismatch")
    if (
        stage_6_9.get("schema_version")
        != stage_6_9_impl.SCHEMA_VERSION
        or stage_6_9.get("status") != "completed"
        or stage_6_9.get("requested_total_rollouts") != 256
        or stage_6_9.get("completed_rollouts") != 256
        or sum((stage_6_9.get("forbidden_operation_counts") or {}).values()) != 0
    ):
        raise RuntimeError("Stage 6.9 execution authority mismatch")
    contract = stage_6_9.get("confirmation_contract") or {}
    expected_contract = {
        "evaluated_pipeline_partition": "pipeline_train",
        "evaluated_action_roles": ["teacher", "residual"],
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
    for key, value in expected_contract.items():
        if contract.get(key) != value:
            raise RuntimeError(f"Stage 6.9 frozen contract {key} mismatch")
    if (
        arena.get("status") != "completed"
        or arena.get("completed_games") != 20
        or arena.get("model_wins") != 0
        or arena.get("baseline_wins") != 20
        or arena.get("early_screen_continuation_allowed") is not False
        or arena.get("checkpoint_promotion_allowed") is not False
        or arena.get("capability_claim_allowed") is not False
    ):
        raise RuntimeError("Stage 6.1 Arena rejection mismatch")
    return expected_contract


def reproduce_targets(
    audit: dict,
    split: dict,
    teacher_samples: list[dict],
    source_samples: list[dict],
    source_summary: dict,
) -> tuple[list[dict], list[dict], list[dict]]:
    if source_summary.get("partition_role") != "train_development":
        raise RuntimeError("source dataset is not train/development physical data")
    if source_summary.get("contains_locked_test_samples") is not False or any(
        sample.get("split") == "locked_test" for sample in source_samples
    ):
        raise RuntimeError("source dataset contains locked-test samples")

    train_ids = {str(value) for value in split.get("pipeline_train_game_ids") or []}
    development_ids = {
        str(value) for value in split.get("pipeline_development_game_ids") or []
    }
    if len(train_ids) != 18 or len(development_ids) != 4 or train_ids & development_ids:
        raise RuntimeError("frozen 18/4 pipeline split mismatch")

    expected_executed_keys = {(game_id, turn) for game_id, turn, _ in EXPECTED_EXECUTED}
    teacher_by_key = {
        (str(sample["game_id"]), int(sample["turn_index"])): sample
        for sample in teacher_samples
    }
    if len(teacher_by_key) != len(teacher_samples):
        raise RuntimeError("teacher source state key is duplicated")
    source_counts = Counter(
        (str(sample["game_id"]), int(sample["turn_index"]))
        for sample in source_samples
        if sample.get("split") == "train"
        and (str(sample["game_id"]), int(sample["turn_index"]))
        in expected_executed_keys
    )
    source_by_key = {
        (str(sample["game_id"]), int(sample["turn_index"])): sample
        for sample in source_samples
        if sample.get("split") == "train"
        and (str(sample["game_id"]), int(sample["turn_index"]))
        in expected_executed_keys
    }
    audits = audit.get("pipeline_train_target_audits") or []
    manifests = audit.get("future_counterfactual_manifest") or []
    if len(audits) != 6 or len(manifests) != 6:
        raise RuntimeError("Stage 6.13 six-case train accounting mismatch")
    audit_by_key = {
        (str(item["game_id"]), int(item["turn_index"])): item for item in audits
    }
    manifest_by_key = {
        (str(item["game_id"]), int(item["turn_index"])): item for item in manifests
    }
    if len(audit_by_key) != 6 or len(manifest_by_key) != 6:
        raise RuntimeError("Stage 6.13 train target is duplicated")

    targets = []
    for game_id, turn_index, top1_index in EXPECTED_EXECUTED:
        key = (game_id, turn_index)
        target_audit = audit_by_key.get(key)
        manifest = manifest_by_key.get(key)
        teacher = teacher_by_key.get(key)
        source = source_by_key.get(key)
        if not all((target_audit, manifest, teacher, source)) or source_counts[key] != 1:
            raise RuntimeError("permitted train target is missing or duplicated")
        if (
            game_id not in train_ids
            or target_audit.get("pipeline_partition") != "pipeline_train"
            or manifest.get("pipeline_partition") != "pipeline_train"
            or manifest.get("new_confirmation_needed") is not True
            or manifest.get("execution_allowed_in_this_stage") is not False
            or int(target_audit.get("top1_action_index")) != top1_index
            or int(manifest.get("top1_action_index")) != top1_index
        ):
            raise RuntimeError("permitted train target provenance mismatch")
        actions = source.get("legal_actions") or []
        metadata = source.get("legal_action_metadata") or []
        teacher_matches = [
            index
            for index, action in enumerate(actions)
            if action == teacher.get("teacher_action")
        ]
        if len(teacher_matches) != 1 or top1_index < 0 or top1_index >= len(actions):
            raise RuntimeError("permitted train action mapping is ambiguous")
        teacher_index = teacher_matches[0]
        order_hash = frozen_confirmation.action_order_sha256(actions)
        top1_hash = frozen_confirmation.action_sha256(actions[top1_index])
        teacher_hash = frozen_confirmation.action_sha256(actions[teacher_index])
        if (
            source.get("split") != "train"
            or source.get("information_set_consistent") is not True
            or source.get("public_history_consistent") is not True
            or source.get("state") != teacher.get("state")
            or actions != teacher.get("legal_actions")
            or len(actions) != len(metadata)
            or len(actions) != target_audit.get("legal_action_count")
            or order_hash != target_audit.get("legal_action_order_sha256")
            or top1_hash != target_audit.get("top1_action_sha256")
            or top1_hash != manifest.get("top1_action_sha256")
            or teacher_hash != target_audit.get("teacher_action_sha256")
        ):
            raise RuntimeError("permitted train state/action identity mismatch")
        teacher_cards = metadata[teacher_index].get("cards")
        top1_cards = metadata[top1_index].get("cards")
        if (
            Counter(teacher_cards)
            != Counter(target_audit.get("teacher_physical_cards_website") or [])
            or Counter(top1_cards)
            != Counter(target_audit.get("top1_physical_cards_website") or [])
            or teacher_cards != teacher.get("teacher_physical_cards")
        ):
            raise RuntimeError("permitted train physical-card identity mismatch")
        targets.append(
            {
                "game_id": game_id,
                "turn_index": turn_index,
                "pipeline_partition": "pipeline_train",
                "source_sample": source,
                "legal_action_count": len(actions),
                "legal_action_order_sha256": order_hash,
                "teacher_action_index": teacher_index,
                "teacher_action_sha256": teacher_hash,
                "teacher_physical_identity": {"cards_website": teacher_cards},
                "top1_action_index": top1_index,
                "top1_action_sha256": top1_hash,
                "top1_physical_identity": {"cards_website": top1_cards},
            }
        )

    exclusions = []
    for game_id, turn_index, top1_index in EXPECTED_EXCLUDED:
        key = (game_id, turn_index)
        target_audit = audit_by_key.get(key)
        manifest = manifest_by_key.get(key)
        if not target_audit or not manifest:
            raise RuntimeError("excluded train target is missing")
        if (
            game_id not in train_ids
            or int(target_audit.get("top1_action_index")) != top1_index
            or int(manifest.get("top1_action_index")) != top1_index
            or target_audit.get("evidence_classification")
            != "direct_paired_comparison_inconclusive"
            or manifest.get("new_confirmation_needed") is not False
            or manifest.get("execution_allowed_in_this_stage") is not False
            or target_audit.get("top1_action_sha256")
            != manifest.get("top1_action_sha256")
        ):
            raise RuntimeError("excluded train target identity mismatch")
        exclusions.append(
            {
                "game_id": game_id,
                "turn_index": turn_index,
                "pipeline_partition": "pipeline_train",
                "top1_action_index": top1_index,
                "top1_action_sha256": manifest["top1_action_sha256"],
                "evidence_classification": "direct_paired_comparison_inconclusive",
                "source_sample_mapping_count": 0,
                "case_execution_count": 0,
                "rollout_count": 0,
                "used_for_confirmation_or_design": False,
            }
        )

    development_items = audit.get("pipeline_development_identity_only") or []
    development_by_key = {
        (str(item["game_id"]), int(item["turn_index"])): item
        for item in development_items
    }
    if len(development_by_key) != EXPECTED_DEVELOPMENT_CASES:
        raise RuntimeError("Stage 6.13 development accounting mismatch")
    heldout = []
    for key in EXPECTED_DEVELOPMENT:
        item = development_by_key.get(key)
        if not item or key[0] not in development_ids:
            raise RuntimeError("development identity mismatch")
        heldout.append(
            {
                **item,
                "source_sample_mapping_count": 0,
                "case_execution_count": 0,
                "rollout_count": 0,
                "used_for_confirmation_or_design": False,
            }
        )
    return targets, exclusions, heldout


def load_context() -> dict:
    frozen_hashes = verify_frozen_hashes()
    audit = load_json(AUDIT_PATH)
    diagnosis = load_json(DIAGNOSIS_PATH)
    stage_6_9 = load_json(STAGE_6_9_PATH)
    split = load_json(SPLIT_PATH)
    arena = load_json(ARENA_PATH)
    contract = validate_frozen_authorities(audit, diagnosis, stage_6_9, arena)
    teacher_samples, _teacher_summary, teacher_hash = preference.load_teacher_dataset(
        TEACHER_PATH
    )
    if teacher_hash != frozen_hashes["teacher_dataset"]:
        raise RuntimeError("teacher dataset loader hash mismatch")
    source_samples, source_summary = website_data.load_dataset(SOURCE_DATASET_PATH)
    targets, exclusions, heldout = reproduce_targets(
        audit, split, teacher_samples, source_samples, source_summary
    )
    if (
        len(targets) != EXPECTED_TRAIN_CASES
        or len(exclusions) != EXPECTED_EXCLUDED_CASES
        or len(heldout) != EXPECTED_DEVELOPMENT_CASES
    ):
        raise RuntimeError("Stage 6.14 target accounting mismatch")
    return {
        "frozen_hashes": frozen_hashes,
        "frozen_contract": contract,
        "targets": targets,
        "excluded": exclusions,
        "heldout": heldout,
    }


def validate_completed_result(result: dict) -> None:
    if len(result.get("case_results") or []) != EXPECTED_TRAIN_CASES:
        raise RuntimeError("formal confirmation did not produce exactly three cases")
    if len(result.get("excluded_inconclusive_train") or []) != 3:
        raise RuntimeError("formal confirmation lost train exclusions")
    if len(result.get("pipeline_development_heldout") or []) != 3:
        raise RuntimeError("formal confirmation lost development isolation")
    if (
        result.get("requested_total_rollouts") != EXPECTED_TOTAL_ROLLOUTS
        or result.get("completed_rollouts") != EXPECTED_TOTAL_ROLLOUTS
        or result.get("continuation_profile_rollout_counts")
        != {"greedy_bot": 48, "tempo_baseline": 48}
        or result.get("timeout_case_count") != 0
        or result.get("candidate_failure_count") != 0
    ):
        raise RuntimeError(
            "formal confirmation rollout/integrity accounting mismatch: "
            f"requested={result.get('requested_total_rollouts')}, "
            f"completed={result.get('completed_rollouts')}, "
            f"profiles={result.get('continuation_profile_rollout_counts')}, "
            f"timeouts={result.get('timeout_case_count')}, "
            f"candidate_failures={result.get('candidate_failure_count')}"
        )
    isolated = list(result["excluded_inconclusive_train"]) + list(
        result["pipeline_development_heldout"]
    )
    if any(
        item.get("source_sample_mapping_count") != 0
        or item.get("case_execution_count") != 0
        or item.get("rollout_count") != 0
        or item.get("used_for_confirmation_or_design") is not False
        for item in isolated
    ):
        raise RuntimeError("excluded train or development case was used")
    if sum((result.get("forbidden_operation_counts") or {}).values()) != 0:
        raise RuntimeError("formal confirmation recorded a forbidden operation")


def build_result(context: dict, case_results: list[dict]) -> dict:
    directions = Counter(
        case["metrics"]["directional_classification"] for case in case_results
    )
    completed = sum(
        candidate["completed_rollout_count"]
        for case in case_results
        for candidate in case["candidate_results"]
    )
    profiles = Counter(
        rollout["continuation_profile"]
        for case in case_results
        for rollout in case["paired_rollouts"]
        for _candidate in range(2)
    )
    supported = [
        {
            "game_id": case["game_id"],
            "turn_index": case["turn_index"],
            "directional_classification": case["metrics"][
                "directional_classification"
            ],
            "teacher_action_sha256": case["candidate_results"][0]["action_sha256"],
            "top1_action_sha256": case["candidate_results"][1]["action_sha256"],
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
            **context["frozen_contract"],
            "evaluated_case_count": EXPECTED_TRAIN_CASES,
            "evaluated_action_roles": ["teacher", "current_top1"],
        },
        "target_reproduction": {
            "expected_pipeline_train_case_count": 3,
            "reproduced_pipeline_train_case_count": len(context["targets"]),
            "excluded_inconclusive_train_case_count": len(context["excluded"]),
            "pipeline_development_heldout_count": len(context["heldout"]),
            "missing_target_count": 0,
            "duplicate_target_count": 0,
            "extra_target_count": 0,
            "reconstructed_action_count": 0,
            "substituted_action_count": 0,
            "ambiguous_action_mapping_count": 0,
            "non_train_source_mapping_count": 0,
            "information_set_inconsistent_mapping_count": 0,
        },
        "excluded_inconclusive_train": context["excluded"],
        "pipeline_development_heldout": context["heldout"],
        "case_results": case_results,
        "requested_total_rollouts": EXPECTED_TOTAL_ROLLOUTS,
        "completed_rollouts": completed,
        "rollout_completion_rate": completed / EXPECTED_TOTAL_ROLLOUTS,
        "continuation_profile_rollout_counts": dict(profiles),
        "timeout_case_count": sum(case["case_timed_out"] for case in case_results),
        "candidate_failure_count": sum(
            candidate["failure_count"]
            for case in case_results
            for candidate in case["candidate_results"]
        ),
        "directional_classification_counts": {
            "teacher_over_residual_supported": directions[
                "teacher_over_residual_supported"
            ],
            "residual_over_teacher_supported": directions[
                "residual_over_teacher_supported"
            ],
            "inconclusive": directions["inconclusive"],
        },
        "supported_comparison_manifest": supported,
        "supported_comparison_manifest_executed_as_training": False,
        "unsupported_ordering_label_count": 0,
        "dataset_constructed": False,
        "new_objective_defined": False,
        "integrity": {
            "excluded_train_source_mapping_count": 0,
            "excluded_train_case_execution_count": 0,
            "excluded_train_rollout_count": 0,
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
            "model_scoring_runs": 0,
            "training_runs": 0,
            "fine_tuning_runs": 0,
            "hyperparameter_tuning_runs": 0,
            "threshold_tuning_runs": 0,
            "checkpoint_selections": 0,
            "checkpoint_modifications": 0,
            "dataset_constructions": 0,
            "new_objective_definitions": 0,
            "complete_website_dataset_loads": 0,
            "locked_test_loads": 0,
            "arena_games": 0,
            "excluded_train_source_mappings": 0,
            "excluded_train_case_executions": 0,
            "pipeline_development_source_mappings": 0,
            "pipeline_development_case_executions": 0,
            "website_shadow_games": 0,
            "website_games": 0,
            "model_controlled_website_actions": 0,
            "checkpoint_promotions": 0,
            "capability_claims": 0,
        },
        "interpretation_scope": (
            "three frozen pipeline-train current-top1 counterfactual comparisons "
            "only; no dataset, objective, model scoring, training, Arena, website, "
            "promotion, or capability claim"
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
        "excluded_inconclusive_train_case_count": len(context["excluded"]),
        "pipeline_development_heldout_count": len(context["heldout"]),
        "requested_total_rollouts": EXPECTED_TOTAL_ROLLOUTS,
        "excluded_train_source_mapping_count": 0,
        "pipeline_development_source_mapping_count": 0,
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
            stage_6_9_impl.execute_residual_case(
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
    if saved.get("excluded_inconclusive_train") != context["excluded"]:
        raise RuntimeError("excluded train identities changed")
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
        if (target["game_id"], target["turn_index"]) != (
            str(case.get("game_id")),
            int(case.get("turn_index")),
        ):
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
                target["top1_action_index"],
                target["top1_action_sha256"],
                target["top1_physical_identity"]["cards_website"],
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
        top1_returns = []
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
                != float(rollout["teacher_return"])
                - float(rollout["residual_return"])
            ):
                raise RuntimeError("saved confirmation schedule/return mismatch")
            teacher_returns.append(float(rollout["teacher_return"]))
            top1_returns.append(float(rollout["residual_return"]))
            profiles[rollout["continuation_profile"]] += 2
        metrics = stage_6_9_impl.normalize_metrics(
            frozen_confirmation.directional_metrics(teacher_returns, top1_returns)
        )
        if case.get("metrics") != metrics:
            raise RuntimeError("saved confirmation metrics mismatch")
        for candidate, values in zip(candidates, (teacher_returns, top1_returns)):
            if candidate.get("mean_return") != sum(values) / len(
                values
            ) or candidate.get("return_variance") != frozen_confirmation.sample_variance(
                values
            ):
                raise RuntimeError("saved confirmation candidate arithmetic mismatch")
            completed += candidate["completed_rollout_count"]
        direction = metrics["directional_classification"]
        directions[direction] += 1
        if direction != "inconclusive":
            expected_supported.append(
                {
                    "game_id": target["game_id"],
                    "turn_index": target["turn_index"],
                    "directional_classification": direction,
                    "teacher_action_sha256": candidates[0]["action_sha256"],
                    "top1_action_sha256": candidates[1]["action_sha256"],
                    "metrics": metrics,
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
        or saved.get("directional_classification_counts")
        != expected_direction_counts
        or saved.get("supported_comparison_manifest") != expected_supported
    ):
        raise RuntimeError("saved confirmation aggregate mismatch")
    validate_completed_result(saved)
    if verify_frozen_hashes() != context["frozen_hashes"]:
        raise RuntimeError("a frozen input changed during independent audit")
    result = {
        "status": "passed",
        "input_and_action_hashes_exact": True,
        "physical_mappings_exact": True,
        "determinization_seeds_exact": True,
        "paired_returns_and_arithmetic_exact": True,
        "means_variances_confidence_and_profiles_exact": True,
        "directional_classifications_exact": True,
        "partition_counts_aggregates_and_exclusions_exact": True,
        "excluded_train_source_mapping_count": 0,
        "excluded_train_case_execution_count": 0,
        "excluded_train_rollout_count": 0,
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
