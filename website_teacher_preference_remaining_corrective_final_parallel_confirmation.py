from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
from typing import Any

import website_danzero_dataset as website_data
import website_information_set as information_set
import website_teacher_preference as preference
import website_teacher_preference_corrective_residual_confirmation as stage_6_9
import website_teacher_preference_remaining_corrective_evidence_audit as evidence
import website_teacher_preference_residual_corrective_remaining_confirmation as confirmation
import website_teacher_preference_residual_corrective_remaining_parallel_confirmation as formal
import website_teacher_preference_residual_corrective_remaining_parallel_equivalence as parallel
import website_teacher_preference_unpaired_confirmation as frozen_confirmation


SCHEMA_VERSION = (
    "website_teacher_preference_remaining_corrective_final_train_confirmation_v1"
)
OUTPUT_PATH = Path(
    "website_teacher_preference_remaining_corrective_final_train_confirmation_v1.json"
)
AUDIT_IMPLEMENTATION_PATH = Path(
    "website_teacher_preference_remaining_corrective_evidence_audit.py"
)
FORMAL_PATTERN_PATH = Path(
    "website_teacher_preference_residual_corrective_remaining_parallel_confirmation.py"
)
EXPECTED_HASHES = {
    "stage_6_18_audit": (
        "b7dc15c779556a972c1b471348cb949bd98d54c1ce1aecb14a3d23cda083681b"
    ),
    "stage_6_18_implementation": (
        "6200af71c14081418b1abfd1fd45d99347c3f20d601ec355014dbbc931a3ea26"
    ),
    "stage_6_14p_parallel_equivalence": (
        "8e168656c35519aae9054038f0fd31398ac0e9260c419de0534a09bf1f4c59ca"
    ),
    "stage_6_14p_parallel_implementation": (
        "f2093a8c348d9d91435209fd9ee258130b18f7de7b4b7758c0656c1d7a70e2e5"
    ),
    "stage_6_14e_formal_implementation": (
        "972b67ed585e9a96f9e8be55b70d0b6585a7e499f6dc692c2861d5e636b9e55d"
    ),
}
EXPECTED_EXECUTED = [
    (
        "14031",
        4,
        2,
        "44eb6c47c92f2c639293a75a2e4825abf2478d706ca7b45f31e8e9a4afc6bb42",
    ),
    (
        "14025",
        20,
        2,
        "8b631095d2fc255edfa14d27e864858829b4f70d910d347d1bff89e38eb903a9",
    ),
]
EXPECTED_EXCLUDED = [
    (
        "14077",
        10,
        0,
        "a7aaaf7c156c09ab5ad0b8c5d33bb6bb60cd85766562f597d1b89c9be31d053c",
    )
]
EXPECTED_DEVELOPMENT = [
    ("13992", 16, 7),
    ("14074", 9, 9),
    ("13871", 9, 10),
]
EXPECTED_TOTAL_ROLLOUTS = 64


def load_json(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError(f"{path} must contain a JSON object")
    return payload


def verify_frozen_inputs() -> dict[str, str]:
    recursive = evidence.verify_frozen_hashes()
    specific = {
        "stage_6_18_audit": frozen_confirmation.sha256(evidence.OUTPUT_PATH),
        "stage_6_18_implementation": frozen_confirmation.sha256(
            AUDIT_IMPLEMENTATION_PATH
        ),
    }
    for name, value in specific.items():
        if value != EXPECTED_HASHES[name]:
            raise RuntimeError(f"{name} SHA-256 mismatch")
    for name in (
        "stage_6_14p_parallel_equivalence",
        "stage_6_14p_parallel_implementation",
        "stage_6_14e_formal_implementation",
    ):
        if recursive.get(name) != EXPECTED_HASHES[name]:
            raise RuntimeError(f"{name} recursive SHA-256 mismatch")
    if frozen_confirmation.sha256(FORMAL_PATTERN_PATH) != EXPECTED_HASHES[
        "stage_6_14e_formal_implementation"
    ]:
        raise RuntimeError("Stage 6.14E formal pattern SHA-256 mismatch")
    formal.verify_parallel_authority(load_json(parallel.OUTPUT_PATH))
    audit = load_json(evidence.OUTPUT_PATH)
    if audit.get("frozen_inputs", {}).get("sha256") != recursive:
        raise RuntimeError("Stage 6.18 recursive frozen hashes mismatch")
    return {**recursive, **specific}


def ensure_unused_output(path: Path = OUTPUT_PATH) -> None:
    confirmation.ensure_unused_output(path)


def write_output_once(path: Path, result: dict) -> None:
    frozen_confirmation.write_json_once(path, result)


def validate_stage_6_18(audit: dict) -> None:
    aggregates = audit.get("train_evidence_aggregates") or {}
    isolation = audit.get("development_isolation") or {}
    if (
        audit.get("schema_version") != evidence.SCHEMA_VERSION
        or audit.get("status") != "completed"
        or audit.get("future_counterfactual_manifest_case_count") != 3
        or audit.get("future_counterfactual_manifest_new_confirmation_needed_count")
        != 2
        or audit.get("future_counterfactual_manifest_existing_inconclusive_count")
        != 1
        or audit.get("future_counterfactual_manifest_executed") is not False
        or aggregates.get(
            "source_candidates_present_without_direct_paired_comparison_count"
        )
        != 2
        or aggregates.get("direct_paired_comparison_inconclusive_count") != 1
        or isolation.get("identity_only_target_count") != 3
        or any(
            value != 0
            for key, value in isolation.items()
            if key != "identity_only_target_count"
        )
        or sum((audit.get("forbidden_operation_counts") or {}).values()) != 0
    ):
        raise RuntimeError("Stage 6.18 frozen conclusion mismatch")


def frozen_contract() -> dict:
    return confirmation.validate_frozen_authorities(
        load_json(confirmation.AUDIT_PATH),
        load_json(confirmation.DIAGNOSIS_PATH),
        load_json(confirmation.STAGE_6_9_PATH),
        load_json(confirmation.ARENA_PATH),
    )


def reproduce_targets(
    audit: dict,
    split: dict,
    teacher_samples: list[dict],
    source_samples: list[dict],
    source_summary: dict,
) -> tuple[list[dict], list[dict], list[dict], list[dict]]:
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
    teacher_by_key = {
        (str(sample["game_id"]), int(sample["turn_index"])): sample
        for sample in teacher_samples
    }
    if len(teacher_by_key) != 22:
        raise RuntimeError("teacher source state key is duplicated or incomplete")
    audits = audit.get("pipeline_train_target_audits") or []
    manifests = audit.get("future_counterfactual_manifest") or []
    audit_by_key = {
        (str(item["game_id"]), int(item["turn_index"])): item for item in audits
    }
    manifest_by_key = {
        (str(item["game_id"]), int(item["turn_index"])): item for item in manifests
    }
    if len(audits) != 3 or len(audit_by_key) != 3 or len(manifest_by_key) != 3:
        raise RuntimeError("Stage 6.18 train target accounting mismatch")
    executed_keys = {(game_id, turn) for game_id, turn, _index, _hash in EXPECTED_EXECUTED}
    source_counts = Counter(
        (str(sample["game_id"]), int(sample["turn_index"]))
        for sample in source_samples
        if sample.get("split") == "train"
        and (str(sample["game_id"]), int(sample["turn_index"])) in executed_keys
    )
    source_by_key = {
        (str(sample["game_id"]), int(sample["turn_index"])): sample
        for sample in source_samples
        if sample.get("split") == "train"
        and (str(sample["game_id"]), int(sample["turn_index"])) in executed_keys
    }
    targets = []
    for game_id, turn_index, top1_index, expected_top1_hash in EXPECTED_EXECUTED:
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
            or target_audit.get("evidence_classification")
            != "source_candidates_present_without_direct_paired_comparison"
            or manifest.get("new_confirmation_needed") is not True
            or manifest.get("execution_allowed_in_this_stage") is not False
            or int(target_audit.get("top1_action_index")) != top1_index
            or int(manifest.get("top1_action_index")) != top1_index
            or target_audit.get("top1_action_sha256") != expected_top1_hash
            or manifest.get("top1_action_sha256") != expected_top1_hash
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
            or teacher_index != int(target_audit.get("teacher_action_index"))
            or top1_hash != expected_top1_hash
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
    excluded = []
    for game_id, turn_index, top1_index, top1_hash in EXPECTED_EXCLUDED:
        key = (game_id, turn_index)
        target_audit = audit_by_key.get(key)
        manifest = manifest_by_key.get(key)
        if (
            not target_audit
            or not manifest
            or game_id not in train_ids
            or int(target_audit.get("top1_action_index")) != top1_index
            or target_audit.get("top1_action_sha256") != top1_hash
            or manifest.get("top1_action_sha256") != top1_hash
            or target_audit.get("evidence_classification")
            != "direct_paired_comparison_inconclusive"
            or manifest.get("new_confirmation_needed") is not False
            or manifest.get("execution_allowed_in_this_stage") is not False
        ):
            raise RuntimeError("excluded train target identity mismatch")
        excluded.append(
            {
                "game_id": game_id,
                "turn_index": turn_index,
                "pipeline_partition": "pipeline_train",
                "top1_action_index": top1_index,
                "top1_action_sha256": top1_hash,
                "evidence_classification": "direct_paired_comparison_inconclusive",
                "source_sample_mapping_count": 0,
                "case_execution_count": 0,
                "rollout_count": 0,
                "threshold_objective_or_confirmation_design_use_count": 0,
            }
        )
    development_by_key = {
        (str(item["game_id"]), int(item["turn_index"])): item
        for item in audit.get("pipeline_development_identity_only") or []
    }
    if len(development_by_key) != 3:
        raise RuntimeError("Stage 6.18 development accounting mismatch")
    heldout = []
    for game_id, turn_index, top1_index in EXPECTED_DEVELOPMENT:
        item = development_by_key.get((game_id, turn_index))
        if (
            not item
            or game_id not in development_ids
            or int(item.get("top1_action_index")) != top1_index
        ):
            raise RuntimeError("development identity mismatch")
        heldout.append(
            {
                **item,
                "source_sample_mapping_count": 0,
                "case_execution_count": 0,
                "rollout_count": 0,
                "threshold_objective_or_confirmation_design_use_count": 0,
            }
        )
    excluded_keys = executed_keys | {
        (game_id, turn) for game_id, turn, _index, _hash in EXPECTED_EXCLUDED
    } | {(game_id, turn) for game_id, turn, _index in EXPECTED_DEVELOPMENT}
    other = [
        {
            "game_id": key[0],
            "turn_index": key[1],
            "source_sample_mapping_count": 0,
            "case_execution_count": 0,
            "rollout_count": 0,
            "threshold_objective_or_confirmation_design_use_count": 0,
        }
        for key in teacher_by_key
        if key not in excluded_keys
    ]
    if len(other) != 16:
        raise RuntimeError("other teacher-state exclusion count mismatch")
    return targets, excluded, heldout, other


def load_context() -> dict:
    frozen_hashes = verify_frozen_inputs()
    audit = load_json(evidence.OUTPUT_PATH)
    validate_stage_6_18(audit)
    split = load_json(confirmation.SPLIT_PATH)
    contract = frozen_contract()
    teacher_samples, _summary, teacher_hash = preference.load_teacher_dataset(
        confirmation.TEACHER_PATH
    )
    if teacher_hash != frozen_hashes["teacher_dataset"]:
        raise RuntimeError("teacher dataset loader hash mismatch")
    source_samples, source_summary = website_data.load_dataset(
        confirmation.SOURCE_DATASET_PATH
    )
    targets, excluded, heldout, other = reproduce_targets(
        audit, split, teacher_samples, source_samples, source_summary
    )
    if (
        len(targets) != 2
        or len(excluded) != 1
        or len(heldout) != 3
        or len(other) != 16
    ):
        raise RuntimeError("Stage 6.19 target accounting mismatch")
    return {
        "frozen_hashes": frozen_hashes,
        "frozen_contract": contract,
        "targets": targets,
        "excluded": excluded,
        "heldout": heldout,
        "other": other,
    }


def expected_parallel_execution_metadata() -> dict:
    return {
        "schema_version": SCHEMA_VERSION,
        "executor": "execute_parallel_case_with_eight_determinization_tasks_v1",
        "process_isolated": True,
        "worker_task_count_per_case": 8,
        "total_worker_task_count": 16,
        "schedule_item_count_per_case": 16,
        "total_schedule_item_count": 32,
        "candidate_call_count_per_case": 32,
        "total_candidate_call_count": 64,
        "common_parent_deadline_seconds": frozen_confirmation.MAX_SECONDS_PER_CASE,
        "max_rollout_steps": frozen_confirmation.MAX_ROLLOUT_STEPS,
        "sequential_fallback_count": 0,
        "retry_count": 0,
        "worker_label_or_gate_logic": False,
        "parent_metric_and_gate_owner": "frozen_stage_6_9",
        "parallel_artifact_sha256": EXPECTED_HASHES[
            "stage_6_14p_parallel_equivalence"
        ],
        "parallel_implementation_sha256": EXPECTED_HASHES[
            "stage_6_14p_parallel_implementation"
        ],
        "formal_pattern_sha256": EXPECTED_HASHES[
            "stage_6_14e_formal_implementation"
        ],
    }


def forbidden_operation_counts() -> dict[str, int]:
    return {
        "model_scoring_runs": 0,
        "dataset_constructions": 0,
        "new_objective_definitions": 0,
        "training_runs": 0,
        "fine_tuning_runs": 0,
        "hyperparameter_tuning_runs": 0,
        "threshold_tuning_runs": 0,
        "checkpoint_selections": 0,
        "checkpoint_modifications": 0,
        "complete_website_dataset_loads": 0,
        "locked_test_loads": 0,
        "arena_games": 0,
        "website_shadow_games": 0,
        "website_games": 0,
        "model_controlled_website_actions": 0,
        "excluded_train_source_mappings": 0,
        "excluded_train_case_executions": 0,
        "pipeline_development_source_mappings": 0,
        "pipeline_development_case_executions": 0,
        "other_teacher_state_source_mappings": 0,
        "other_teacher_state_case_executions": 0,
        "extra_formal_execution_attempts": 0,
        "sequential_fallbacks": 0,
        "retries": 0,
        "partial_curated_outputs": 0,
        "unsupported_ordering_labels": 0,
        "checkpoint_promotions": 0,
        "capability_claims": 0,
    }


def validate_completed_result(result: dict) -> None:
    cases = result.get("case_results") or []
    if [
        (str(case.get("game_id")), int(case.get("turn_index"))) for case in cases
    ] != [(game_id, turn) for game_id, turn, _index, _hash in EXPECTED_EXECUTED]:
        raise RuntimeError("formal confirmation case identity mismatch")
    if (
        len(result.get("excluded_direct_inconclusive_train") or []) != 1
        or len(result.get("pipeline_development_heldout") or []) != 3
        or len(result.get("other_teacher_states_excluded") or []) != 16
        or result.get("requested_total_rollouts") != EXPECTED_TOTAL_ROLLOUTS
        or result.get("completed_rollouts") != EXPECTED_TOTAL_ROLLOUTS
        or result.get("continuation_profile_rollout_counts")
        != {"greedy_bot": 32, "tempo_baseline": 32}
        or result.get("timeout_case_count") != 0
        or result.get("candidate_failure_count") != 0
        or result.get("parallel_execution") != expected_parallel_execution_metadata()
    ):
        raise RuntimeError("formal confirmation aggregate mismatch")
    if any(
        case.get("case_timed_out") is not False
        or any(
            candidate.get("requested_rollout_count") != 16
            or candidate.get("completed_rollout_count") != 16
            or candidate.get("failure_count") != 0
            for candidate in case.get("candidate_results") or []
        )
        for case in cases
    ):
        raise RuntimeError("formal confirmation is partial or failed")
    isolated = (
        list(result["excluded_direct_inconclusive_train"])
        + list(result["pipeline_development_heldout"])
        + list(result["other_teacher_states_excluded"])
    )
    if any(
        item.get("source_sample_mapping_count") != 0
        or item.get("case_execution_count") != 0
        or item.get("rollout_count") != 0
        or item.get("threshold_objective_or_confirmation_design_use_count") != 0
        for item in isolated
    ):
        raise RuntimeError("an excluded case was used")
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
            "sha256": context["frozen_hashes"],
        },
        "source_dataset": {
            "path": str(confirmation.SOURCE_DATASET_PATH),
            "sha256": context["frozen_hashes"][
                "source_train_development_dataset"
            ],
            "partition_role": "train_development",
            "contains_locked_test_samples": False,
            "loaded_once": True,
        },
        "confirmation_contract": {
            **context["frozen_contract"],
            "evaluated_case_count": 2,
            "evaluated_action_roles": ["teacher", "current_top1"],
        },
        "target_reproduction": {
            "expected_pipeline_train_case_count": 2,
            "reproduced_pipeline_train_case_count": len(context["targets"]),
            "excluded_direct_inconclusive_train_case_count": len(
                context["excluded"]
            ),
            "pipeline_development_heldout_count": len(context["heldout"]),
            "other_teacher_state_exclusion_count": len(context["other"]),
            "missing_target_count": 0,
            "duplicate_target_count": 0,
            "extra_target_count": 0,
            "reconstructed_action_count": 0,
            "substituted_action_count": 0,
            "transferred_action_count": 0,
            "ambiguous_action_mapping_count": 0,
            "non_train_source_mapping_count": 0,
            "information_set_inconsistent_mapping_count": 0,
        },
        "excluded_direct_inconclusive_train": context["excluded"],
        "pipeline_development_heldout": context["heldout"],
        "other_teacher_states_excluded": context["other"],
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
        "dataset_constructed": False,
        "new_objective_defined": False,
        "formal_execution_accounting": {
            "authorized_execution_count": 1,
            "extra_execution_attempt_count": 0,
            "retry_count": 0,
            "sequential_fallback_count": 0,
            "partial_curated_output_count": 0,
        },
        "integrity": {
            "executed_source_mapping_count": 2,
            "excluded_train_source_mapping_count": 0,
            "excluded_train_case_execution_count": 0,
            "excluded_train_rollout_count": 0,
            "pipeline_development_source_mapping_count": 0,
            "pipeline_development_case_execution_count": 0,
            "pipeline_development_rollout_count": 0,
            "other_teacher_state_source_mapping_count": 0,
            "other_teacher_state_case_execution_count": 0,
            "other_teacher_state_rollout_count": 0,
            "locked_test_loaded": False,
            "complete_website_dataset_loaded": False,
            "opponent_or_teammate_true_hands_used": False,
            "future_information_used": False,
            "common_determinizations_verified": True,
            "integrity_failure_count": 0,
        },
        "parallel_execution": expected_parallel_execution_metadata(),
        "forbidden_operation_counts": forbidden_operation_counts(),
        "interpretation_scope": (
            "two frozen pipeline-train current-top1 counterfactual comparisons "
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
        "excluded_direct_inconclusive_train_case_count": len(context["excluded"]),
        "pipeline_development_heldout_count": len(context["heldout"]),
        "other_teacher_state_exclusion_count": len(context["other"]),
        "worker_task_count": 16,
        "schedule_item_count": 32,
        "requested_total_rollouts": EXPECTED_TOTAL_ROLLOUTS,
        "sequential_fallback_count": 0,
        "retry_count": 0,
        "excluded_source_mapping_count": 0,
    }
    print(json.dumps(result, indent=2))
    return result


def run(components: dict, adaptive: Any) -> dict:
    ensure_unused_output()
    frozen_hashes = verify_frozen_inputs()
    context = load_context()
    case_results = []
    for target in context["targets"]:
        candidates = formal.materialize_candidates(target, components, adaptive)
        raw = parallel.execute_parallel_case(target, candidates)
        case_results.append(stage_6_9.normalize_case_result(raw))
        print(
            json.dumps(
                {
                    "completed_case": f"{target['game_id']}:{target['turn_index']}",
                    "completed_case_count": len(case_results),
                    "completed_case_rollouts": sum(
                        item["completed_rollout_count"]
                        for item in case_results[-1]["candidate_results"]
                    ),
                    "direction": case_results[-1]["metrics"][
                        "directional_classification"
                    ],
                },
                ensure_ascii=False,
            ),
            flush=True,
        )
    result = build_result(context, case_results)
    if verify_frozen_inputs() != frozen_hashes:
        raise RuntimeError("a frozen input changed during formal confirmation")
    write_output_once(OUTPUT_PATH, result)
    print(
        json.dumps(
            {
                "status": result["status"],
                "completed_rollouts": result["completed_rollouts"],
                "directional_classification_counts": result[
                    "directional_classification_counts"
                ],
                "worker_task_count": 16,
                "sequential_fallback_count": 0,
                "retry_count": 0,
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
    if (
        saved.get("schema_version") != SCHEMA_VERSION
        or saved.get("status") != "completed"
        or saved.get("frozen_inputs", {}).get("sha256")
        != context["frozen_hashes"]
    ):
        raise RuntimeError("saved confirmation schema or frozen hashes mismatch")
    if (
        saved.get("excluded_direct_inconclusive_train") != context["excluded"]
        or saved.get("pipeline_development_heldout") != context["heldout"]
        or saved.get("other_teacher_states_excluded") != context["other"]
    ):
        raise RuntimeError("saved confirmation exclusions changed")
    cases = saved.get("case_results") or []
    if len(cases) != 2:
        raise RuntimeError("saved confirmation case count mismatch")
    for target, case in zip(context["targets"], cases):
        if (
            (target["game_id"], target["turn_index"])
            != (str(case.get("game_id")), int(case.get("turn_index")))
            or case.get("legal_action_count") != target["legal_action_count"]
            or case.get("legal_action_order_sha256")
            != target["legal_action_order_sha256"]
            or case.get("case_timed_out") is not False
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
        metrics = stage_6_9.normalize_metrics(
            frozen_confirmation.directional_metrics(teacher_returns, top1_returns)
        )
        if case.get("metrics") != metrics:
            raise RuntimeError("saved confirmation metrics mismatch")
        for candidate, values in zip(candidates, (teacher_returns, top1_returns)):
            if (
                candidate.get("mean_return") != sum(values) / len(values)
                or candidate.get("return_variance")
                != frozen_confirmation.sample_variance(values)
            ):
                raise RuntimeError("saved confirmation candidate arithmetic mismatch")
    recomputed = build_result(context, cases)
    if saved != recomputed:
        raise RuntimeError("independent final confirmation reconstruction mismatch")
    if verify_frozen_inputs() != context["frozen_hashes"]:
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
        "parallel_executor_hashes_and_authority_exact": True,
        "worker_task_count": 16,
        "schedule_item_count": 32,
        "candidate_call_count": 64,
        "excluded_source_mapping_count": 0,
        "sequential_fallback_count": 0,
        "retry_count": 0,
        "forbidden_operation_count": sum(
            saved["forbidden_operation_counts"].values()
        ),
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

    run(adaptive.offline_load_guandan_components(), adaptive)


if __name__ == "__main__":
    main()
