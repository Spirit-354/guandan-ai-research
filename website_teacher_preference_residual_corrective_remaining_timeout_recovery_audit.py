from __future__ import annotations

import argparse
import hashlib
import inspect
import json
from pathlib import Path

import play_research_adaptive as adaptive
import website_information_set as information_set
import website_teacher_preference_residual_corrective_remaining_confirmation as confirmation
import website_teacher_preference_unpaired_confirmation as frozen_confirmation


SCHEMA_VERSION = (
    "website_teacher_preference_residual_corrective_remaining_timeout_recovery_audit_v1"
)
OUTPUT_PATH = Path(
    "website_teacher_preference_residual_corrective_remaining_timeout_recovery_audit_v1.json"
)
CONFIRMATION_OUTPUT_PATH = confirmation.OUTPUT_PATH
PROGRESS_PATH = Path(
    "docs/progress/2026-07-15-stage6-14-three-top1-confirmation-timeout.md"
)

FROZEN_PATHS = {
    **confirmation.FROZEN_PATHS,
    "stage_6_14_confirmation_implementation": Path(
        "website_teacher_preference_residual_corrective_remaining_confirmation.py"
    ),
    "stage_6_9_execution_implementation": Path(
        "website_teacher_preference_unpaired_confirmation.py"
    ),
    "information_set_implementation": Path("website_information_set.py"),
    "offline_optimization_implementation": Path("play_research_adaptive.py"),
    "stage_6_14_timeout_progress": PROGRESS_PATH,
}
EXPECTED_HASHES = {
    **confirmation.EXPECTED_HASHES,
    "stage_6_14_confirmation_implementation": (
        "e509ebc50f9fef9a159435d582561e72ac36083f059a0781539ec797c709bf55"
    ),
    "stage_6_9_execution_implementation": (
        "d3933e16afdc45bb60d6badff8db35aadf8214910ad752abf3f46274ebb23915"
    ),
    "information_set_implementation": (
        "35334c14d96faf9c4d7fdc93890afcba9ec6bc26f78fcca66e7af53ddae36e66"
    ),
    "offline_optimization_implementation": (
        "fdeb8993bb28a73616de012f5a6422f0c774923e868464ccb62c96abd04fdd1e"
    ),
    "stage_6_14_timeout_progress": (
        "67382f92cdb3559d8eb6dd50a36fff695e007bde829276207eed76a5aeb04f6b"
    ),
}
CONFIRMED_TERMINAL_ACCOUNTING = {
    "requested_rollouts": 96,
    "completed_rollouts": 90,
    "continuation_profile_rollout_counts": {
        "greedy_bot": 48,
        "tempo_baseline": 48,
    },
    "timeout_case_count": 1,
    "candidate_failure_count": 6,
}
CONFIRMED_CASE_DIRECTIONS = [
    {
        "game_id": "13957",
        "turn_index": 14,
        "directional_classification": "teacher_over_residual_supported",
    },
    {
        "game_id": "14038",
        "turn_index": 12,
        "directional_classification": "teacher_over_residual_supported",
    },
    {
        "game_id": "13872",
        "turn_index": 4,
        "directional_classification": "inconclusive",
    },
]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_json(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError(f"{path} must contain a JSON object")
    return payload


def verify_frozen_hashes() -> dict[str, str]:
    actual = {}
    for name, path in FROZEN_PATHS.items():
        value = sha256(path)
        if value != EXPECTED_HASHES[name]:
            raise RuntimeError(f"{name} SHA-256 mismatch")
        actual[name] = value
    return actual


def ensure_output_state(output_path: Path = OUTPUT_PATH) -> None:
    if CONFIRMATION_OUTPUT_PATH.exists():
        raise RuntimeError("failed Stage 6.14 confirmation output unexpectedly exists")
    if output_path.exists():
        raise RuntimeError(f"recovery audit output already exists: {output_path}")
    temporary = output_path.with_name(f"{output_path.name}.tmp")
    if temporary.exists():
        raise RuntimeError(f"stale recovery audit temporary output exists: {temporary}")


def validate_failure_handoff() -> dict:
    text = PROGRESS_PATH.read_text(encoding="utf-8")
    required = [
        "requested=96",
        "completed=90",
        "profiles={'greedy_bot': 48, 'tempo_baseline': 48}",
        "timeouts=1",
        "candidate_failures=6",
        "13957:14  teacher_over_residual_supported",
        "14038:12  teacher_over_residual_supported",
        "13872:4   inconclusive",
        "The output path",
        "remained absent throughout.",
    ]
    missing = [value for value in required if value not in text]
    if missing:
        raise RuntimeError(f"Stage 6.14 failure handoff is incomplete: {missing}")
    return {
        "source_path": str(PROGRESS_PATH),
        "source_sha256": EXPECTED_HASHES["stage_6_14_timeout_progress"],
        "terminal_accounting": CONFIRMED_TERMINAL_ACCOUNTING,
        "case_directions": CONFIRMED_CASE_DIRECTIONS,
        "curated_confirmation_output_exists": False,
    }


def trace_deadline_path() -> dict:
    schedule = frozen_confirmation.rollout_schedule()
    if (
        frozen_confirmation.MAX_SECONDS_PER_CASE != 600.0
        or frozen_confirmation.MAX_ROLLOUT_STEPS != 300
        or len(schedule) != 16
        or sum(
            item["continuation_profile"] == "greedy_bot" for item in schedule
        )
        != 8
        or sum(
            item["continuation_profile"] == "tempo_baseline" for item in schedule
        )
        != 8
    ):
        raise RuntimeError("frozen Stage 6.9 schedule or limits changed")

    execute_source = inspect.getsource(frozen_confirmation.execute_case)
    simulate_source = inspect.getsource(information_set._simulate_candidate)
    gate_source = inspect.getsource(frozen_confirmation.gate_failure_reasons)
    required_execute_fragments = [
        "deadline = started + MAX_SECONDS_PER_CASE",
        "for item in rollout_schedule():",
        "for candidate_index, candidate in enumerate(candidates):",
        "deadline,",
        '"case_timed_out": time.monotonic() >= deadline',
    ]
    required_simulate_fragments = [
        "while not game.is_game_over and steps < int(max_steps):",
        "time.monotonic() >= deadline_monotonic",
        '"reason": "case_time_budget_exhausted"',
        '"reason": "rollout_depth_exhausted"',
    ]
    if any(value not in execute_source for value in required_execute_fragments):
        raise RuntimeError("Stage 6.9 execute_case deadline path changed")
    if any(value not in simulate_source for value in required_simulate_fragments):
        raise RuntimeError("information-set candidate deadline path changed")
    if "paired_count != ROLLOUTS_PER_ACTION" not in gate_source:
        raise RuntimeError("frozen completeness gate changed")

    first_two_completed = 2 * 2 * frozen_confirmation.ROLLOUTS_PER_ACTION
    third_completed = (
        CONFIRMED_TERMINAL_ACCOUNTING["completed_rollouts"] - first_two_completed
    )
    if third_completed != 26 or third_completed % 2 != 0:
        raise RuntimeError("Stage 6.14 incomplete-case arithmetic mismatch")
    third_completed_pairs = third_completed // 2
    missing_pairs = len(schedule) - third_completed_pairs
    missing_candidate_values = missing_pairs * 2
    if missing_pairs != 3 or missing_candidate_values != 6:
        raise RuntimeError("Stage 6.14 timeout-failure derivation mismatch")
    return {
        "case_deadline_seconds": 600.0,
        "rollout_max_steps": 300,
        "schedule_items_per_case": len(schedule),
        "candidate_actions_per_schedule_item": 2,
        "deadline_scope": "single_absolute_deadline_shared_by_entire_case",
        "deadline_checked_before_each_continuation_step": True,
        "deadline_failure_reason": "case_time_budget_exhausted",
        "schedule_continues_after_deadline": True,
        "supported_direction_requires_complete_16_pairs": True,
        "first_two_supported_cases_completed_candidate_values": first_two_completed,
        "third_case_completed_candidate_values": third_completed,
        "third_case_completed_pairs": third_completed_pairs,
        "third_case_missing_schedule_items": missing_pairs,
        "third_case_missing_candidate_values": missing_candidate_values,
        "derived_candidate_failure_count_matches_terminal": (
            missing_candidate_values
            == CONFIRMED_TERMINAL_ACCOUNTING["candidate_failure_count"]
        ),
    }


def audit_optimization_boundary() -> dict:
    confirmation_main = inspect.getsource(confirmation.main)
    confirmation_run = inspect.getsource(confirmation.run)
    installer = inspect.getsource(adaptive.offline_install_arena_baseline_optimizations)
    baseline_cache = inspect.getsource(information_set._cached_baseline_action_info)
    cache_equivalence = inspect.getsource(information_set.run_baseline_cache_equivalence)
    adaptive_source = Path("play_research_adaptive.py").read_text(encoding="utf-8")
    installed_patches = [
        "choose_all_out_if_possible",
        "choose_non_bomb_follow",
        "choose_bomb_to_set_up_finish",
        "choose_lead_bomb_to_set_up_finish",
        "exact_remaining_groups",
        "_legal_play_options_cached",
    ]
    if "offline_install_arena_baseline_optimizations()" not in confirmation_main:
        raise RuntimeError("Stage 6.14 does not install the frozen offline optimizations")
    if "baseline_cache: dict[str, list[str]] = {}" not in confirmation_run:
        raise RuntimeError("Stage 6.14 baseline action cache is not enabled")
    if any(f"engine.{name}" not in installer for name in installed_patches):
        raise RuntimeError("offline optimization patch set changed")
    if "if key is not None and key in cache" not in baseline_cache:
        raise RuntimeError("baseline action cache hit path changed")
    if (
        "baseline_equivalence_mismatch_count" not in cache_equivalence
        or "ProcessPoolExecutor" not in adaptive_source
    ):
        raise RuntimeError("recovery prerequisites are missing")
    return {
        "offline_optimization_installer_already_active": True,
        "installed_engine_patch_names": installed_patches,
        "baseline_visible_state_action_cache_already_active": True,
        "baseline_cache_equivalence_checker_exists": True,
        "additional_existing_sequential_optimization_toggle_found": False,
        "existing_process_isolation_infrastructure_found": True,
        "process_isolation_used_by_confirmation": False,
        "unchanged_sequential_path_can_meet_600_second_gate": False,
        "sequential_path_infeasibility_reason": (
            "all existing semantics-preserving caches are already active and the "
            "same frozen case still reaches the absolute 600-second deadline"
        ),
    }


def build_result() -> dict:
    frozen_hashes = verify_frozen_hashes()
    failure = validate_failure_handoff()
    deadline = trace_deadline_path()
    optimization = audit_optimization_boundary()
    result = {
        "schema_version": SCHEMA_VERSION,
        "status": "completed",
        "frozen_inputs": {
            "paths": {name: str(path) for name, path in FROZEN_PATHS.items()},
            "sha256": frozen_hashes,
        },
        "failed_confirmation": failure,
        "deadline_failure_path": deadline,
        "optimization_boundary": optimization,
        "recovery_decision": {
            "unchanged_sequential_retry_allowed": False,
            "deadline_or_rollout_limit_change_allowed": False,
            "partial_comparison_use_allowed": False,
            "frozen_next_stage": (
                "stage_6_14p_process_isolated_determinization_parallel_equivalence"
            ),
            "next_stage_rollout_execution_allowed": False,
            "next_stage_required_proof": [
                "one task per determinization recreates the same hidden-card assignment from the frozen seed",
                "teacher and current-top1 simulations receive independent deep copies and identical per-action seeds",
                "greedy and frozen-tempo continuation actions and returns are unchanged",
                "result order is restored to the frozen 16-item schedule before metric computation",
                "the common absolute 600-second case deadline and all gates remain unchanged",
            ],
            "formal_confirmation_retry_condition": (
                "all process-isolation equivalence tests and an independent static audit pass in a separate stage"
            ),
            "fallback_if_equivalence_unproven": (
                "freeze Stage 6.14 as infeasible under the unchanged contract"
            ),
        },
        "integrity": {
            "confirmation_output_absent": True,
            "new_rollout_executed": False,
            "model_loaded_or_scored": False,
            "locked_test_or_complete_bundle_loaded": False,
            "partial_comparison_used": False,
            "integrity_failure_count": 0,
        },
        "forbidden_operation_counts": {
            "new_rollout_runs": 0,
            "model_scoring_runs": 0,
            "dataset_constructions": 0,
            "objective_constructions": 0,
            "training_runs": 0,
            "fine_tuning_runs": 0,
            "hyperparameter_tuning_runs": 0,
            "threshold_tuning_runs": 0,
            "deadline_or_rollout_limit_changes": 0,
            "checkpoint_selections": 0,
            "checkpoint_modifications": 0,
            "complete_website_dataset_loads": 0,
            "locked_test_loads": 0,
            "arena_games": 0,
            "website_shadow_games": 0,
            "website_games": 0,
            "model_controlled_website_actions": 0,
            "checkpoint_promotions": 0,
            "capability_claims": 0,
            "partial_or_unsupported_labels": 0,
        },
        "interpretation_scope": (
            "static Stage 6.14 timeout recovery audit only; no rollout, model, "
            "dataset, objective, training, Arena, website, or capability evidence"
        ),
    }
    if (
        not result["deadline_failure_path"][
            "derived_candidate_failure_count_matches_terminal"
        ]
        or sum(result["forbidden_operation_counts"].values()) != 0
        or CONFIRMATION_OUTPUT_PATH.exists()
    ):
        raise RuntimeError("recovery audit integrity gate failed")
    return result


def write_json_once(path: Path, result: dict) -> None:
    temporary = path.with_name(f"{path.name}.tmp")
    temporary.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    if path.exists():
        raise RuntimeError(f"recovery audit output already exists: {path}")
    temporary.replace(path)


def preflight() -> dict:
    ensure_output_state()
    result = build_result()
    summary = {
        "status": "ready",
        "frozen_hash_count": len(result["frozen_inputs"]["sha256"]),
        "confirmation_output_absent": True,
        "terminal_completed_rollouts": result["failed_confirmation"][
            "terminal_accounting"
        ]["completed_rollouts"],
        "derived_missing_candidate_values": result["deadline_failure_path"][
            "third_case_missing_candidate_values"
        ],
        "new_rollout_runs": 0,
    }
    print(json.dumps(summary, indent=2))
    return summary


def run() -> dict:
    ensure_output_state()
    result = build_result()
    if verify_frozen_hashes() != result["frozen_inputs"]["sha256"]:
        raise RuntimeError("a frozen input changed during recovery audit")
    write_json_once(OUTPUT_PATH, result)
    print(
        json.dumps(
            {
                "status": result["status"],
                "output": str(OUTPUT_PATH),
                "frozen_next_stage": result["recovery_decision"][
                    "frozen_next_stage"
                ],
                "new_rollout_runs": 0,
            },
            indent=2,
        )
    )
    return result


def audit() -> dict:
    saved = load_json(OUTPUT_PATH)
    recomputed = build_result()
    if saved != recomputed:
        raise RuntimeError("saved recovery audit differs from independent recomputation")
    if verify_frozen_hashes() != saved["frozen_inputs"]["sha256"]:
        raise RuntimeError("a frozen input changed during independent audit")
    result = {
        "status": "passed",
        "frozen_hashes_exact": True,
        "terminal_failure_handoff_exact": True,
        "deadline_failure_path_exact": True,
        "six_candidate_failures_derived_exactly": True,
        "optimization_boundary_exact": True,
        "single_next_stage_frozen": True,
        "confirmation_output_absent": not CONFIRMATION_OUTPUT_PATH.exists(),
        "forbidden_operation_count": sum(
            saved["forbidden_operation_counts"].values()
        ),
    }
    if not result["confirmation_output_absent"]:
        raise RuntimeError("failed confirmation output appeared during audit")
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
