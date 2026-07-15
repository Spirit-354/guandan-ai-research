from __future__ import annotations

import argparse
import json
from pathlib import Path
import random
from typing import Any

import website_information_set as information_set
import website_teacher_preference_corrective_residual_confirmation as stage_6_9_impl
import website_teacher_preference_residual_corrective_remaining_confirmation as confirmation
import website_teacher_preference_residual_corrective_remaining_parallel_equivalence as parallel
import website_teacher_preference_unpaired_confirmation as frozen_confirmation


SCHEMA_VERSION = (
    "website_teacher_preference_residual_corrective_remaining_parallel_confirmation_v1"
)
PARALLEL_ARTIFACT_PATH = parallel.OUTPUT_PATH
PARALLEL_IMPLEMENTATION_PATH = Path(
    "website_teacher_preference_residual_corrective_remaining_parallel_equivalence.py"
)
CONFIRMATION_IMPLEMENTATION_PATH = Path(
    "website_teacher_preference_residual_corrective_remaining_confirmation.py"
)
OUTPUT_PATH = confirmation.OUTPUT_PATH
EXPECTED_PARALLEL_ARTIFACT_SHA256 = (
    "8e168656c35519aae9054038f0fd31398ac0e9260c419de0534a09bf1f4c59ca"
)
EXPECTED_PARALLEL_IMPLEMENTATION_SHA256 = (
    "f2093a8c348d9d91435209fd9ee258130b18f7de7b4b7758c0656c1d7a70e2e5"
)
EXPECTED_CONFIRMATION_IMPLEMENTATION_SHA256 = (
    "e509ebc50f9fef9a159435d582561e72ac36083f059a0781539ec797c709bf55"
)


def load_json(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError(f"{path} must contain a JSON object")
    return payload


def verify_parallel_authority(payload: dict) -> None:
    contract = payload.get("parallel_contract") or {}
    gate = payload.get("formal_execution_gate") or {}
    integrity = payload.get("integrity") or {}
    if (
        payload.get("schema_version") != parallel.SCHEMA_VERSION
        or payload.get("status") != "completed"
        or contract.get("worker_task_count_per_case") != 8
        or contract.get("one_task_per_determinization") is not True
        or contract.get("determinization_indices") != list(range(8))
        or contract.get("schedule_items_per_case") != 16
        or contract.get("candidate_calls_per_case") != 32
        or contract.get("candidate_role_order") != ["teacher", "top1"]
        or contract.get("profile_order_per_determinization")
        != ["greedy_bot", "tempo_baseline"]
        or contract.get("common_parent_deadline_seconds")
        != frozen_confirmation.MAX_SECONDS_PER_CASE
        or contract.get("max_rollout_steps")
        != frozen_confirmation.MAX_ROLLOUT_STEPS
        or contract.get("worker_label_or_gate_logic") is not False
        or contract.get("parent_metric_function")
        != "frozen_stage_6_9_directional_metrics"
        or contract.get("result_order") != "rollout_index_then_teacher_top1"
        or contract.get("fail_closed") is not True
        or gate.get("parallel_equivalence_passed") is not True
        or gate.get("formal_three_case_execution_allowed_in_next_stage") is not True
        or gate.get("required_formal_executor")
        != "execute_parallel_case_with_eight_determinization_tasks_v1"
        or gate.get("sequential_retry_allowed") is not False
        or gate.get("partial_stage_6_14_comparison_use_allowed") is not False
        or integrity.get("real_rollout_count") != 0
        or integrity.get("partial_comparison_use_count") != 0
        or integrity.get("integrity_failure_count") != 0
        or sum((payload.get("forbidden_operation_counts") or {}).values()) != 0
    ):
        raise RuntimeError("Stage 6.14P parallel authority mismatch")


def verify_frozen_inputs() -> dict[str, str]:
    hashes = confirmation.verify_frozen_hashes()
    parallel_artifact_hash = frozen_confirmation.sha256(PARALLEL_ARTIFACT_PATH)
    parallel_implementation_hash = frozen_confirmation.sha256(
        PARALLEL_IMPLEMENTATION_PATH
    )
    confirmation_implementation_hash = frozen_confirmation.sha256(
        CONFIRMATION_IMPLEMENTATION_PATH
    )
    if parallel_artifact_hash != EXPECTED_PARALLEL_ARTIFACT_SHA256:
        raise RuntimeError("Stage 6.14P artifact SHA-256 mismatch")
    if parallel_implementation_hash != EXPECTED_PARALLEL_IMPLEMENTATION_SHA256:
        raise RuntimeError("Stage 6.14P implementation SHA-256 mismatch")
    if confirmation_implementation_hash != EXPECTED_CONFIRMATION_IMPLEMENTATION_SHA256:
        raise RuntimeError("Stage 6.14 confirmation implementation SHA-256 mismatch")
    verify_parallel_authority(load_json(PARALLEL_ARTIFACT_PATH))
    return {
        **hashes,
        "stage_6_14p_parallel_equivalence": parallel_artifact_hash,
        "stage_6_14p_parallel_implementation": parallel_implementation_hash,
        "stage_6_14_confirmation_implementation": confirmation_implementation_hash,
    }


def expected_parallel_execution_metadata() -> dict:
    return {
        "schema_version": SCHEMA_VERSION,
        "executor": "execute_parallel_case_with_eight_determinization_tasks_v1",
        "process_isolated": True,
        "worker_task_count_per_case": 8,
        "total_worker_task_count": 24,
        "schedule_item_count_per_case": 16,
        "total_schedule_item_count": 48,
        "candidate_call_count_per_case": 32,
        "total_candidate_call_count": 96,
        "common_parent_deadline_seconds": frozen_confirmation.MAX_SECONDS_PER_CASE,
        "max_rollout_steps": frozen_confirmation.MAX_ROLLOUT_STEPS,
        "sequential_fallback_count": 0,
        "retry_count": 0,
        "worker_label_or_gate_logic": False,
        "parent_metric_and_gate_owner": "frozen_stage_6_9",
        "parallel_artifact_sha256": EXPECTED_PARALLEL_ARTIFACT_SHA256,
        "parallel_implementation_sha256": EXPECTED_PARALLEL_IMPLEMENTATION_SHA256,
        "confirmation_implementation_sha256": (
            EXPECTED_CONFIRMATION_IMPLEMENTATION_SHA256
        ),
    }


def validate_parallel_execution_metadata(result: dict) -> None:
    if result.get("parallel_execution") != expected_parallel_execution_metadata():
        raise RuntimeError("formal parallel execution metadata mismatch")


def preflight() -> dict:
    confirmation.ensure_unused_output()
    hashes = verify_frozen_inputs()
    context = confirmation.load_context()
    result = {
        "status": "ready",
        "output_exists": False,
        "frozen_hash_count": len(hashes),
        "pipeline_train_case_count": len(context["targets"]),
        "excluded_inconclusive_train_case_count": len(context["excluded"]),
        "pipeline_development_heldout_count": len(context["heldout"]),
        "worker_task_count": 24,
        "schedule_item_count": 48,
        "requested_total_rollouts": confirmation.EXPECTED_TOTAL_ROLLOUTS,
        "sequential_fallback_count": 0,
        "retry_count": 0,
        "excluded_train_source_mapping_count": 0,
        "pipeline_development_source_mapping_count": 0,
    }
    print(json.dumps(result, indent=2))
    return result


def materialize_candidates(
    target: dict, components: dict, adaptive: Any
) -> list[dict]:
    validation_game = information_set.restore_game(
        target["source_sample"],
        components,
        random.Random(
            information_set._stable_determinization_seed(target["source_sample"], -1)
        ),
    )
    return [
        frozen_confirmation.materialize_candidate(
            target, "teacher", validation_game, components, adaptive
        ),
        frozen_confirmation.materialize_candidate(
            target, "top1", validation_game, components, adaptive
        ),
    ]


def run(components: dict, adaptive: Any) -> dict:
    confirmation.ensure_unused_output()
    frozen_hashes = verify_frozen_inputs()
    context = confirmation.load_context()
    case_results = []
    for target in context["targets"]:
        candidates = materialize_candidates(target, components, adaptive)
        raw = parallel.execute_parallel_case(target, candidates)
        case_results.append(stage_6_9_impl.normalize_case_result(raw))
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
    result = confirmation.build_result(context, case_results)
    result["parallel_execution"] = expected_parallel_execution_metadata()
    validate_parallel_execution_metadata(result)
    if verify_frozen_inputs() != frozen_hashes:
        raise RuntimeError("a frozen input changed during formal parallel confirmation")
    frozen_confirmation.write_json_once(OUTPUT_PATH, result)
    print(
        json.dumps(
            {
                "status": result["status"],
                "completed_rollouts": result["completed_rollouts"],
                "directional_classification_counts": result[
                    "directional_classification_counts"
                ],
                "worker_task_count": result["parallel_execution"][
                    "total_worker_task_count"
                ],
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
    saved = confirmation.load_json(OUTPUT_PATH)
    verify_frozen_inputs()
    validate_parallel_execution_metadata(saved)
    base = confirmation.audit()
    if base.get("status") != "passed" or base.get("forbidden_operation_count") != 0:
        raise RuntimeError("frozen Stage 6.14 audit did not pass")
    result = {
        **base,
        "parallel_executor_hashes_exact": True,
        "parallel_authority_exact": True,
        "worker_task_count": 24,
        "schedule_item_count": 48,
        "candidate_call_count": 96,
        "sequential_fallback_count": 0,
        "retry_count": 0,
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
