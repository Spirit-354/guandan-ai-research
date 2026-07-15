from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path


SCHEMA_VERSION = "website_teacher_preference_stage6_final_disposition_v1"
OUTPUT_PATH = Path("website_teacher_preference_stage6_final_disposition_v1.json")
STAGE_6_19_PATH = Path(
    "website_teacher_preference_remaining_corrective_final_train_confirmation_v1.json"
)
STAGE_6_19_IMPLEMENTATION_PATH = Path(
    "website_teacher_preference_remaining_corrective_final_parallel_confirmation.py"
)
STAGE_6_18_PATH = Path(
    "website_teacher_preference_remaining_corrective_final_evidence_audit_v1.json"
)
STAGE_6_16_PATH = Path(
    "website_teacher_preference_remaining_corrective_training_v1.json"
)
STAGE_6_17_PATH = Path(
    "website_teacher_preference_remaining_corrective_failure_diagnosis_v1.json"
)
STAGE_6_1_PATH = Path("website_teacher_preference_arena_smoke20_v1.json")
EXPECTED_STAGE_6_19_SHA256 = (
    "a1f32207255867dd2a59c7f9043c57038aff37f506746c970f8892f1d852e189"
)
EXPECTED_STAGE_6_19_IMPLEMENTATION_SHA256 = (
    "63d0f047d11d4b92b9a3fcdcd9dd2ee68b939e68fafc19513fb3a1527ec41bdb"
)
EXPECTED_STAGE_6_18_SHA256 = (
    "b7dc15c779556a972c1b471348cb949bd98d54c1ce1aecb14a3d23cda083681b"
)
EXPECTED_STAGE_6_17_SHA256 = (
    "1757016ae33628cca075a9cdfc881cd49be7b63f1078ca3f7288f95c7fa00a68"
)
EXPECTED_STAGE_6_16_SHA256 = (
    "cac3ecb0542a7f9aaac2654f73f4e3650422be7eb5990bf4c403f3f082145156"
)
EXPECTED_STAGE_6_1_SHA256 = (
    "aa45da9de202194102fe8d11e612ad3eb4b51177fd910b9a7948836afd2a1fe6"
)
EXPECTED_RESIDUALS = [
    (
        "14077",
        10,
        0,
        "a7aaaf7c156c09ab5ad0b8c5d33bb6bb60cd85766562f597d1b89c9be31d053c",
    ),
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
EXPECTED_DEVELOPMENT = [("13992", 16), ("14074", 9), ("13871", 9)]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            block = handle.read(1024 * 1024)
            if not block:
                return digest.hexdigest()
            digest.update(block)


def load_json(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError(f"{path} must contain a JSON object")
    return payload


def ensure_unused_output(path: Path = OUTPUT_PATH) -> None:
    temporary = path.with_name(f"{path.name}.tmp")
    if path.exists() or temporary.exists():
        raise RuntimeError(f"final disposition output already exists: {path}")


def verify_frozen_hashes(stage_6_19: dict, stage_6_18: dict) -> dict[str, str]:
    recursive = stage_6_19.get("frozen_inputs", {}).get("sha256") or {}
    recursive_paths = stage_6_18.get("frozen_inputs", {}).get("paths") or {}
    if len(recursive) != 30 or len(recursive_paths) != 28:
        raise RuntimeError("Stage 6.19 recursive frozen accounting mismatch")
    path_by_name = {
        **{name: Path(path) for name, path in recursive_paths.items()},
        "stage_6_18_audit": STAGE_6_18_PATH,
        "stage_6_18_implementation": Path(
            "website_teacher_preference_remaining_corrective_evidence_audit.py"
        ),
    }
    if set(path_by_name) != set(recursive):
        raise RuntimeError("Stage 6.19 recursive frozen path set mismatch")
    actual = {}
    for name, expected in recursive.items():
        value = sha256(path_by_name[name])
        if value != expected:
            raise RuntimeError(f"{name} SHA-256 mismatch")
        actual[name] = value
    if actual.get("stage_6_18_audit") != EXPECTED_STAGE_6_18_SHA256:
        raise RuntimeError("Stage 6.18 audit SHA-256 mismatch")
    specific = {
        "stage_6_19_confirmation": sha256(STAGE_6_19_PATH),
        "stage_6_19_implementation": sha256(STAGE_6_19_IMPLEMENTATION_PATH),
    }
    if specific["stage_6_19_confirmation"] != EXPECTED_STAGE_6_19_SHA256:
        raise RuntimeError("Stage 6.19 confirmation SHA-256 mismatch")
    if (
        specific["stage_6_19_implementation"]
        != EXPECTED_STAGE_6_19_IMPLEMENTATION_SHA256
    ):
        raise RuntimeError("Stage 6.19 implementation SHA-256 mismatch")
    return {**actual, **specific}


def validate_stage_6_1(payload: dict) -> dict:
    zero_fields = (
        "training_run_count",
        "hyperparameter_search_count",
        "checkpoint_selection_count",
        "website_dataset_load_count",
        "locked_test_load_count",
        "website_shadow_count",
        "website_game_count",
        "model_controlled_website_action_count",
        "illegal_action_count",
        "fallback_count",
        "materialization_fail_count",
        "hand_card_mismatch_count",
        "fatal_no_candidate_count",
    )
    if (
        sha256(STAGE_6_1_PATH) != EXPECTED_STAGE_6_1_SHA256
        or payload.get("schema_version") != "danzero_offline_arena_v1"
        or payload.get("status") != "completed"
        or payload.get("requested_games") != 20
        or payload.get("completed_games") != 20
        or payload.get("model_wins") != 0
        or payload.get("baseline_wins") != 20
        or payload.get("model_team_win_rate") != 0.0
        or payload.get("early_screen_min_win_rate") != 0.30
        or payload.get("early_screen_continuation_allowed") is not False
        or payload.get("checkpoint_promotion_allowed") is not False
        or payload.get("capability_claim_allowed") is not False
        or any(payload.get(name) != 0 for name in zero_fields)
    ):
        raise RuntimeError("Stage 6.1 Arena rejection mismatch")
    return {
        "status": "completed_rejected",
        "requested_games": 20,
        "completed_games": 20,
        "model_wins": 0,
        "baseline_wins": 20,
        "model_win_rate": 0.0,
        "early_screen_min_win_rate": 0.30,
        "continuation_allowed": False,
        "checkpoint_promotion_allowed": False,
        "capability_claim_allowed": False,
        "integrity_counter_sum": 0,
    }


def validate_stage_6_16(payload: dict) -> dict:
    accounting = payload.get("training_accounting") or {}
    if (
        sha256(STAGE_6_16_PATH) != EXPECTED_STAGE_6_16_SHA256
        or payload.get("schema_version")
        != "website_teacher_preference_remaining_corrective_training_v1"
        or payload.get("status") != "completed"
        or payload.get("checkpoint_sha256")
        != "8407f897e36b45affc628fbd2fe68dc4c76a5085fad095511c8045bc73ec5aad"
        or payload.get("checkpoint_reload_verified") is not True
        or payload.get("metric_eligibility")
        != "pipeline_only_not_capability_evidence"
        or payload.get("checkpoint_promotion_allowed") is not False
        or payload.get("capability_claim_allowed") is not False
        or accounting.get("training_run_count") != 1
        or accounting.get("optimizer_step_count") != 60
        or accounting.get("development_training_use_count") != 0
        or sum((payload.get("forbidden_operation_counts") or {}).values()) != 0
    ):
        raise RuntimeError("Stage 6.16 pipeline checkpoint mismatch")
    return {
        "training_run_count": 1,
        "optimizer_step_count": 60,
        "checkpoint_sha256": payload["checkpoint_sha256"],
        "checkpoint_reload_verified": True,
        "metric_eligibility": "pipeline_only_not_capability_evidence",
        "checkpoint_promotion_allowed": False,
        "capability_claim_allowed": False,
    }


def validate_stage_6_17(payload: dict) -> dict:
    aggregates = payload.get("aggregates") or {}
    expected = {
        "pipeline_train": (18, 889, 15, 0, 3, 0),
        "pipeline_development": (4, 45, 1, 0, 3, 0),
        "overall": (22, 934, 16, 0, 6, 0),
    }
    if (
        sha256(STAGE_6_17_PATH) != EXPECTED_STAGE_6_17_SHA256
        or payload.get("schema_version")
        != "website_teacher_preference_remaining_corrective_failure_diagnosis_v1"
        or payload.get("status") != "completed"
        or payload.get("checkpoint_status")
        != "pipeline_only_unpromoted_not_capability_evidence"
        or sum((payload.get("forbidden_operation_counts") or {}).values()) != 0
    ):
        raise RuntimeError("Stage 6.17 diagnosis mismatch")
    for partition, values in expected.items():
        item = aggregates.get(partition) or {}
        actual = (
            item.get("state_count"),
            item.get("legal_action_count"),
            item.get("teacher_top1_count"),
            item.get("behavior_top1_count"),
            item.get("other_action_top1_count"),
            item.get("pass_top1_count"),
        )
        if actual != values:
            raise RuntimeError(f"Stage 6.17 {partition} aggregate mismatch")
    return {
        "state_count": 22,
        "recorded_legal_action_count": 934,
        "pipeline_train_teacher_top1": 15,
        "pipeline_train_state_count": 18,
        "pipeline_development_teacher_top1": 1,
        "pipeline_development_state_count": 4,
        "overall_teacher_top1": 16,
        "overall_other_top1": 6,
        "pass_top1": 0,
        "checkpoint_status": "pipeline_only_unpromoted_not_capability_evidence",
        "arena_authorized": False,
    }


def validate_stage_6_18(payload: dict) -> tuple[dict, list[dict]]:
    audits = payload.get("pipeline_train_target_audits") or []
    development = payload.get("pipeline_development_identity_only") or []
    target_reproduction = payload.get("target_reproduction") or {}
    if (
        sha256(STAGE_6_18_PATH) != EXPECTED_STAGE_6_18_SHA256
        or payload.get("schema_version")
        != "website_teacher_preference_remaining_corrective_final_evidence_audit_v1"
        or payload.get("status") != "completed"
        or len(audits) != 3
        or len(development) != 3
        or target_reproduction.get("transferred_action_count") != 0
        or payload.get("future_counterfactual_manifest_new_confirmation_needed_count")
        != 2
        or payload.get("future_counterfactual_manifest_existing_inconclusive_count")
        != 1
        or payload.get("future_counterfactual_manifest_executed") is not False
        or sum((payload.get("forbidden_operation_counts") or {}).values()) != 0
    ):
        raise RuntimeError("Stage 6.18 evidence audit mismatch")
    by_key = {
        (str(item["game_id"]), int(item["turn_index"])): item for item in audits
    }
    if len(by_key) != 3:
        raise RuntimeError("Stage 6.18 train target identity is duplicated")
    first = by_key.get(("14077", 10))
    if (
        not first
        or first.get("top1_action_index") != 0
        or first.get("top1_action_sha256") != EXPECTED_RESIDUALS[0][3]
        or first.get("evidence_classification")
        != "direct_paired_comparison_inconclusive"
        or first.get("stage_6_9_provenance", {}).get(
            "directional_classification"
        )
        != "inconclusive"
    ):
        raise RuntimeError("Stage 6.18 preserved inconclusive target mismatch")
    development_keys = [
        (str(item["game_id"]), int(item["turn_index"])) for item in development
    ]
    if development_keys != EXPECTED_DEVELOPMENT:
        raise RuntimeError("Stage 6.18 development identities mismatch")
    return (
        {
            "pipeline_train_residual_count": 3,
            "pipeline_development_residual_count": 3,
            "transferred_action_count": 0,
            "preserved_direct_inconclusive_count": 1,
            "new_confirmation_needed_count": 2,
            "development_source_exposure_count": 0,
        },
        audits,
    )


def validate_stage_6_19(payload: dict) -> tuple[dict, list[dict]]:
    cases = payload.get("case_results") or []
    directions = payload.get("directional_classification_counts") or {}
    parallel = payload.get("parallel_execution") or {}
    execution = payload.get("formal_execution_accounting") or {}
    if (
        sha256(STAGE_6_19_PATH) != EXPECTED_STAGE_6_19_SHA256
        or payload.get("schema_version")
        != "website_teacher_preference_remaining_corrective_final_train_confirmation_v1"
        or payload.get("status") != "completed"
        or len(cases) != 2
        or payload.get("requested_total_rollouts") != 64
        or payload.get("completed_rollouts") != 64
        or payload.get("timeout_case_count") != 0
        or payload.get("candidate_failure_count") != 0
        or directions
        != {
            "teacher_over_residual_supported": 0,
            "residual_over_teacher_supported": 0,
            "inconclusive": 2,
        }
        or payload.get("supported_comparison_manifest") != []
        or payload.get("dataset_constructed") is not False
        or payload.get("new_objective_defined") is not False
        or parallel.get("total_worker_task_count") != 16
        or parallel.get("total_schedule_item_count") != 32
        or parallel.get("total_candidate_call_count") != 64
        or parallel.get("sequential_fallback_count") != 0
        or parallel.get("retry_count") != 0
        or execution
        != {
            "authorized_execution_count": 1,
            "extra_execution_attempt_count": 0,
            "retry_count": 0,
            "sequential_fallback_count": 0,
            "partial_curated_output_count": 0,
        }
        or sum((payload.get("forbidden_operation_counts") or {}).values()) != 0
    ):
        raise RuntimeError("Stage 6.19 final confirmation mismatch")
    expected_keys = [("14031", 4), ("14025", 20)]
    if [
        (str(case["game_id"]), int(case["turn_index"])) for case in cases
    ] != expected_keys or any(
        case.get("metrics", {}).get("directional_classification") != "inconclusive"
        for case in cases
    ):
        raise RuntimeError("Stage 6.19 case identity or direction mismatch")
    return (
        {
            "executed_train_case_count": 2,
            "worker_task_count": 16,
            "schedule_item_count": 32,
            "requested_rollout_count": 64,
            "completed_rollout_count": 64,
            "inconclusive_count": 2,
            "supported_comparison_count": 0,
            "timeout_count": 0,
            "candidate_failure_count": 0,
            "retry_count": 0,
            "sequential_fallback_count": 0,
        },
        cases,
    )


def forbidden_operation_counts() -> dict[str, int]:
    return {
        "model_loads": 0,
        "model_scoring_runs": 0,
        "checkpoint_semantic_loads": 0,
        "teacher_dataset_semantic_loads": 0,
        "source_dataset_semantic_loads": 0,
        "locked_test_loads": 0,
        "complete_website_dataset_loads": 0,
        "rollout_runs": 0,
        "simulation_runs": 0,
        "arena_games": 0,
        "website_shadow_games": 0,
        "website_games": 0,
        "model_controlled_website_actions": 0,
        "data_collection_runs": 0,
        "dataset_constructions": 0,
        "objective_definitions": 0,
        "training_runs": 0,
        "fine_tuning_runs": 0,
        "hyperparameter_tuning_runs": 0,
        "threshold_tuning_runs": 0,
        "checkpoint_selections": 0,
        "checkpoint_modifications": 0,
        "checkpoint_promotions": 0,
        "new_ordering_labels": 0,
        "unsupported_inferences": 0,
        "capability_claims": 0,
        "stage_7_executions": 0,
    }


def build_result() -> dict:
    stage_6_19 = load_json(STAGE_6_19_PATH)
    stage_6_18 = load_json(STAGE_6_18_PATH)
    frozen_hashes = verify_frozen_hashes(stage_6_19, stage_6_18)
    stage_6_1 = validate_stage_6_1(load_json(STAGE_6_1_PATH))
    stage_6_16 = validate_stage_6_16(load_json(STAGE_6_16_PATH))
    stage_6_17 = validate_stage_6_17(load_json(STAGE_6_17_PATH))
    stage_6_18_summary, audits = validate_stage_6_18(stage_6_18)
    stage_6_19_summary, cases = validate_stage_6_19(stage_6_19)
    audit_by_key = {
        (str(item["game_id"]), int(item["turn_index"])): item for item in audits
    }
    case_by_key = {
        (str(item["game_id"]), int(item["turn_index"])): item for item in cases
    }
    residuals = []
    for game_id, turn_index, action_index, action_hash in EXPECTED_RESIDUALS:
        key = (game_id, turn_index)
        if key == ("14077", 10):
            source = audit_by_key[key]
            metrics = source["stage_6_9_provenance"]
            provenance = "stage_6_9_preserved_by_stage_6_18"
        else:
            source = audit_by_key[key]
            case = case_by_key[key]
            metrics = case["metrics"]
            provenance = "stage_6_19_final_train_confirmation"
        if (
            source.get("top1_action_index") != action_index
            or source.get("top1_action_sha256") != action_hash
            or metrics.get("directional_classification") != "inconclusive"
        ):
            raise RuntimeError("final residual identity or classification mismatch")
        residuals.append(
            {
                "game_id": game_id,
                "turn_index": turn_index,
                "pipeline_partition": "pipeline_train",
                "current_top1_action_index": action_index,
                "current_top1_action_sha256": action_hash,
                "directional_classification": "inconclusive",
                "provenance": provenance,
                "strong_ordering_label_allowed": False,
                "rerun_allowed": False,
            }
        )
    forbidden = forbidden_operation_counts()
    result = {
        "schema_version": SCHEMA_VERSION,
        "status": "completed",
        "frozen_inputs": {
            "entry_count": len(frozen_hashes),
            "sha256": frozen_hashes,
            "verification_mode": "raw_bytes_sha256_only_no_semantic_model_or_data_load",
        },
        "curated_json_read_accounting": {
            "parsed_json_file_count": 5,
            "parsed_paths": [
                str(STAGE_6_1_PATH),
                str(STAGE_6_16_PATH),
                str(STAGE_6_17_PATH),
                str(STAGE_6_18_PATH),
                str(STAGE_6_19_PATH),
            ],
            "non_json_semantic_load_count": 0,
        },
        "stage_6_route_chronology": [
            {"stage": "6.1", "conclusion": "offline_arena_rejected"},
            {"stage": "6.16", "conclusion": "pipeline_checkpoint_only"},
            {"stage": "6.17", "conclusion": "static_full_set_incomplete"},
            {"stage": "6.18", "conclusion": "three_train_residuals_isolated"},
            {"stage": "6.19", "conclusion": "final_two_comparisons_inconclusive"},
        ],
        "stage_6_1_arena_reproduction": stage_6_1,
        "stage_6_16_checkpoint_reproduction": stage_6_16,
        "stage_6_17_static_reproduction": stage_6_17,
        "stage_6_18_evidence_reproduction": stage_6_18_summary,
        "stage_6_19_confirmation_reproduction": stage_6_19_summary,
        "final_train_residuals": residuals,
        "final_train_residual_count": 3,
        "pipeline_development_heldout": [
            {
                "game_id": game_id,
                "turn_index": turn_index,
                "source_exposure_count": 0,
                "execution_count": 0,
                "design_use_count": 0,
            }
            for game_id, turn_index in EXPECTED_DEVELOPMENT
        ],
        "pipeline_development_heldout_count": 3,
        "evidence_exhaustion": {
            "current_residual_supported_teacher_over_current_count": 0,
            "current_residual_supported_current_over_teacher_count": 0,
            "current_residual_inconclusive_count": 3,
            "new_corrective_pair_authorized_count": 0,
            "new_dataset_extension_authorized": False,
            "new_training_run_authorized": False,
            "new_arena_candidate_authorized": False,
            "unsupported_inference_count": 0,
        },
        "final_disposition": {
            "stage_6_status": "completed_rejected",
            "offline_gate_passed": False,
            "eligible_offline_candidate_count": 0,
            "stage_7_authorized": False,
            "website_control_authorized": False,
            "capability_claim_allowed": False,
            "automatic_next_stage_available": False,
        },
        "interpretation": (
            "Stage 6 work is closed with a negative offline-gate result. "
            "This is not a pass, improvement, promotion, deployment, or capability claim."
        ),
        "evidence_inconsistency_count": 0,
        "missing_evidence_count": 0,
        "duplicate_evidence_count": 0,
        "extra_evidence_count": 0,
        "forbidden_operation_counts": forbidden,
    }
    if any(forbidden.values()):
        raise RuntimeError("final disposition recorded a forbidden operation")
    return result


def write_output_once(path: Path, result: dict) -> None:
    temporary = path.with_name(f"{path.name}.tmp")
    ensure_unused_output(path)
    try:
        with temporary.open("x", encoding="utf-8") as handle:
            json.dump(result, handle, ensure_ascii=False, indent=2, allow_nan=False)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        temporary.replace(path)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise


def preflight() -> dict:
    ensure_unused_output()
    result = build_result()
    summary = {
        "status": "ready",
        "output_exists": False,
        "frozen_hash_count": result["frozen_inputs"]["entry_count"],
        "parsed_curated_json_count": result["curated_json_read_accounting"][
            "parsed_json_file_count"
        ],
        "final_train_residual_count": result["final_train_residual_count"],
        "pipeline_development_heldout_count": result[
            "pipeline_development_heldout_count"
        ],
        **result["final_disposition"],
        "forbidden_operation_count": sum(
            result["forbidden_operation_counts"].values()
        ),
    }
    print(json.dumps(summary, indent=2))
    return summary


def run() -> dict:
    ensure_unused_output()
    result = build_result()
    write_output_once(OUTPUT_PATH, result)
    print(
        json.dumps(
            {
                "status": result["status"],
                "output": str(OUTPUT_PATH),
                **result["final_disposition"],
            },
            indent=2,
        )
    )
    return result


def audit() -> dict:
    saved = load_json(OUTPUT_PATH)
    recomputed = build_result()
    if saved != recomputed:
        raise RuntimeError("independent final disposition reconstruction mismatch")
    result = {
        "status": "passed",
        "all_32_frozen_hashes_exact": True,
        "stage_6_1_rejection_exact": True,
        "stage_6_16_pipeline_status_exact": True,
        "stage_6_17_static_ranking_exact": True,
        "stage_6_18_residual_isolation_exact": True,
        "stage_6_19_inconclusive_results_exact": True,
        "final_disposition_exact": True,
        "semantic_model_checkpoint_or_data_load_count": 0,
        "new_execution_count": 0,
        "stage_7_execution_count": 0,
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
    elif args.run:
        run()
    else:
        audit()


if __name__ == "__main__":
    main()
