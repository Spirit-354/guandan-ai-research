from __future__ import annotations

import argparse
from collections import Counter
import concurrent.futures
import hashlib
import inspect
import json
import os
from pathlib import Path
import random
import time
from typing import Any, Callable

import website_information_set as information_set
import website_teacher_preference_residual_corrective_remaining_confirmation as confirmation
import website_teacher_preference_residual_corrective_remaining_timeout_recovery_audit as recovery
import website_teacher_preference_unpaired_confirmation as frozen_confirmation


SCHEMA_VERSION = (
    "website_teacher_preference_residual_corrective_remaining_parallel_equivalence_v1"
)
TASK_SCHEMA_VERSION = "stage_6_14_determinization_task_v1"
RESULT_SCHEMA_VERSION = "stage_6_14_determinization_result_v1"
RECOVERY_PATH = recovery.OUTPUT_PATH
CONFIRMATION_IMPLEMENTATION_PATH = Path(
    "website_teacher_preference_residual_corrective_remaining_confirmation.py"
)
OUTPUT_PATH = Path(
    "website_teacher_preference_residual_corrective_remaining_parallel_equivalence_v1.json"
)
EXPECTED_RECOVERY_SHA256 = (
    "75115cfc5a9dfa3ecb6ac868d04a2e73d20473cfe3a49c8e805a042028872c0d"
)
EXPECTED_CONFIRMATION_IMPLEMENTATION_SHA256 = (
    "e509ebc50f9fef9a159435d582561e72ac36083f059a0781539ec797c709bf55"
)
SYNTHETIC_DEADLINE = 987654.0

_WORKER_COMPONENTS: dict | None = None
_WORKER_ADAPTIVE: Any = None
_WORKER_PROFILE_CONFIG: dict | None = None
_WORKER_BASELINE_CACHE: dict[str, list[str]] | None = None
_WORKER_BASELINE_STATS: dict[str, Any] | None = None
_WORKER_RESTORE_BASELINE: Callable[[], None] | None = None


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_sha256(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
    ).hexdigest()


def load_json(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError(f"{path} must contain a JSON object")
    return payload


def verify_frozen_inputs() -> dict[str, str]:
    recovery_hash = sha256(RECOVERY_PATH)
    implementation_hash = sha256(CONFIRMATION_IMPLEMENTATION_PATH)
    if recovery_hash != EXPECTED_RECOVERY_SHA256:
        raise RuntimeError("Stage 6.14R recovery audit SHA-256 mismatch")
    if implementation_hash != EXPECTED_CONFIRMATION_IMPLEMENTATION_SHA256:
        raise RuntimeError("Stage 6.14 confirmation implementation SHA-256 mismatch")
    recovery_hashes = recovery.verify_frozen_hashes()
    if confirmation.OUTPUT_PATH.exists():
        raise RuntimeError("failed Stage 6.14 confirmation output unexpectedly exists")
    return {
        **recovery_hashes,
        "stage_6_14r_recovery_audit": recovery_hash,
        "stage_6_14_confirmation_implementation": implementation_hash,
    }


def ensure_unused_output(output_path: Path = OUTPUT_PATH) -> None:
    if confirmation.OUTPUT_PATH.exists():
        raise RuntimeError("failed Stage 6.14 confirmation output unexpectedly exists")
    if output_path.exists():
        raise RuntimeError(f"parallel equivalence output already exists: {output_path}")
    temporary = output_path.with_name(f"{output_path.name}.tmp")
    if temporary.exists():
        raise RuntimeError(f"stale parallel equivalence temporary exists: {temporary}")


def candidate_contract(candidate: dict) -> dict:
    return {
        "role": str(candidate["role"]),
        "action_index": int(candidate["action_index"]),
        "action_sha256": str(candidate["action_sha256"]),
        "action_id": int(candidate.get("action_id") or 0),
        "physical_cards": list(candidate.get("physical_cards") or []),
        "physical_cards_website": list(
            candidate.get("physical_cards_website") or []
        ),
    }


def task_contract_payload(task: dict) -> dict:
    return {
        "schema_version": task["schema_version"],
        "task_id": task["task_id"],
        "game_id": task["game_id"],
        "turn_index": task["turn_index"],
        "pipeline_partition": task["pipeline_partition"],
        "legal_action_order_sha256": task["legal_action_order_sha256"],
        "source_sample_sha256": task["source_sample_sha256"],
        "determinization_index": task["determinization_index"],
        "determinization_seed": task["determinization_seed"],
        "schedule_items": task["schedule_items"],
        "candidate_contracts": task["candidate_contracts"],
        "case_deadline_monotonic": task["case_deadline_monotonic"],
        "max_rollout_steps": task["max_rollout_steps"],
        "synthetic_failure_mode": task.get("synthetic_failure_mode", False),
    }


def validate_task(task: dict) -> None:
    if task.get("schema_version") != TASK_SCHEMA_VERSION:
        raise RuntimeError("parallel task schema mismatch")
    if task.get("pipeline_partition") != "pipeline_train":
        raise RuntimeError("parallel task partition mismatch")
    if int(task.get("determinization_index", -1)) not in range(8):
        raise RuntimeError("parallel task determinization index mismatch")
    if int(task.get("max_rollout_steps", -1)) != frozen_confirmation.MAX_ROLLOUT_STEPS:
        raise RuntimeError("parallel task rollout-step limit mismatch")
    if [item.get("continuation_profile") for item in task.get("schedule_items") or []] != [
        "greedy_bot",
        "tempo_baseline",
    ]:
        raise RuntimeError("parallel task profile order mismatch")
    if [item.get("rollout_index") for item in task["schedule_items"]] != [
        2 * int(task["determinization_index"]),
        2 * int(task["determinization_index"]) + 1,
    ]:
        raise RuntimeError("parallel task rollout-index order mismatch")
    if any(
        int(item.get("determinization_index", -1))
        != int(task["determinization_index"])
        for item in task["schedule_items"]
    ):
        raise RuntimeError("parallel task schedule determinization mismatch")
    if [item.get("role") for item in task.get("candidate_contracts") or []] != [
        "teacher",
        "top1",
    ]:
        raise RuntimeError("parallel task candidate-role order mismatch")
    if task.get("source_sample_sha256") != canonical_sha256(task["source_sample"]):
        raise RuntimeError("parallel task source-sample hash mismatch")
    expected_hash = canonical_sha256(task_contract_payload(task))
    if task.get("task_contract_sha256") != expected_hash:
        raise RuntimeError("parallel task contract hash mismatch")


def build_determinization_tasks(
    target: dict,
    candidates: list[dict],
    case_deadline_monotonic: float,
    *,
    synthetic_failure_mode: bool = False,
) -> list[dict]:
    if [candidate.get("role") for candidate in candidates] != ["teacher", "top1"]:
        raise RuntimeError("parallel candidate set must be teacher/top1")
    schedule = frozen_confirmation.rollout_schedule()
    tasks = []
    for determinization_index in range(8):
        schedule_items = [
            dict(item)
            for item in schedule
            if int(item["determinization_index"]) == determinization_index
        ]
        seed = information_set._stable_determinization_seed(
            target["source_sample"], determinization_index
        )
        task = {
            "schema_version": TASK_SCHEMA_VERSION,
            "task_id": (
                f"{target['game_id']}:{target['turn_index']}:determinization:"
                f"{determinization_index}"
            ),
            "game_id": str(target["game_id"]),
            "turn_index": int(target["turn_index"]),
            "pipeline_partition": "pipeline_train",
            "legal_action_order_sha256": target["legal_action_order_sha256"],
            "source_sample_sha256": canonical_sha256(target["source_sample"]),
            "determinization_index": determinization_index,
            "determinization_seed": seed,
            "schedule_items": schedule_items,
            "candidate_contracts": [
                candidate_contract(candidate) for candidate in candidates
            ],
            "case_deadline_monotonic": float(case_deadline_monotonic),
            "max_rollout_steps": frozen_confirmation.MAX_ROLLOUT_STEPS,
            "synthetic_failure_mode": bool(synthetic_failure_mode),
            "source_sample": target["source_sample"],
            "candidates": candidates,
        }
        task["task_contract_sha256"] = canonical_sha256(task_contract_payload(task))
        validate_task(task)
        tasks.append(task)
    if len(tasks) != 8 or len({task["task_id"] for task in tasks}) != 8:
        raise RuntimeError("parallel task construction did not produce eight identities")
    return tasks


def expected_call_contracts(task: dict) -> list[dict]:
    calls = []
    for schedule_item in task["schedule_items"]:
        for candidate in task["candidate_contracts"]:
            calls.append(
                {
                    "rollout_index": int(schedule_item["rollout_index"]),
                    "continuation_profile": schedule_item["continuation_profile"],
                    "determinization_index": int(task["determinization_index"]),
                    "determinization_seed": int(task["determinization_seed"]),
                    "role": candidate["role"],
                    "action_index": int(candidate["action_index"]),
                    "action_sha256": candidate["action_sha256"],
                    "case_deadline_monotonic": float(
                        task["case_deadline_monotonic"]
                    ),
                    "max_rollout_steps": int(task["max_rollout_steps"]),
                }
            )
    return calls


def synthetic_determinization_worker(task: dict) -> dict:
    validate_task(task)
    items = []
    for call in expected_call_contracts(task):
        role_offset = 0 if call["role"] == "teacher" else 1
        failure = None
        value: float | None = float(
            1
            if (
                call["determinization_index"]
                + call["rollout_index"]
                + role_offset
            )
            % 2
            == 0
            else -1
        )
        if (
            task.get("synthetic_failure_mode")
            and call["determinization_index"] == 7
            and call["rollout_index"] == 15
        ):
            value = None
            failure = {"reason": "case_time_budget_exhausted", "steps": 0}
        items.append({**call, "return": value, "failure": failure})
    items.reverse()
    return {
        "schema_version": RESULT_SCHEMA_VERSION,
        "task_id": task["task_id"],
        "task_contract_sha256": task["task_contract_sha256"],
        "worker_process_id": os.getpid(),
        "items": items,
    }


def initialize_production_worker() -> None:
    global _WORKER_ADAPTIVE
    global _WORKER_BASELINE_CACHE
    global _WORKER_BASELINE_STATS
    global _WORKER_COMPONENTS
    global _WORKER_PROFILE_CONFIG
    global _WORKER_RESTORE_BASELINE

    import play_research_adaptive as worker_adaptive

    _WORKER_ADAPTIVE = worker_adaptive
    _WORKER_COMPONENTS = worker_adaptive.offline_load_guandan_components()
    _WORKER_PROFILE_CONFIG = worker_adaptive.load_json(
        worker_adaptive.PROFILE_PATH, {}
    ).get("tempo_baseline", {"engine_mode": "tempo"})
    _WORKER_BASELINE_CACHE = {}
    _WORKER_BASELINE_STATS = {}
    _WORKER_RESTORE_BASELINE = (
        worker_adaptive.offline_install_arena_baseline_optimizations()
    )


def production_determinization_worker(task: dict) -> dict:
    validate_task(task)
    if (
        _WORKER_COMPONENTS is None
        or _WORKER_ADAPTIVE is None
        or _WORKER_PROFILE_CONFIG is None
        or _WORKER_BASELINE_CACHE is None
        or _WORKER_BASELINE_STATS is None
    ):
        raise RuntimeError("parallel production worker was not initialized")
    items = []
    for schedule_item in task["schedule_items"]:
        base_game = information_set.restore_game(
            task["source_sample"],
            _WORKER_COMPONENTS,
            random.Random(int(task["determinization_seed"])),
        )
        for candidate in task["candidates"]:
            value, failure = information_set._simulate_candidate(
                base_game,
                candidate,
                _WORKER_COMPONENTS,
                _WORKER_ADAPTIVE,
                int(task["determinization_seed"]),
                int(task["max_rollout_steps"]),
                schedule_item["continuation_profile"],
                _WORKER_PROFILE_CONFIG,
                float(task["case_deadline_monotonic"]),
                _WORKER_BASELINE_CACHE,
                _WORKER_BASELINE_STATS,
            )
            contract = next(
                item
                for item in task["candidate_contracts"]
                if item["role"] == candidate["role"]
            )
            items.append(
                {
                    "rollout_index": int(schedule_item["rollout_index"]),
                    "continuation_profile": schedule_item[
                        "continuation_profile"
                    ],
                    "determinization_index": int(task["determinization_index"]),
                    "determinization_seed": int(task["determinization_seed"]),
                    "role": contract["role"],
                    "action_index": int(contract["action_index"]),
                    "action_sha256": contract["action_sha256"],
                    "case_deadline_monotonic": float(
                        task["case_deadline_monotonic"]
                    ),
                    "max_rollout_steps": int(task["max_rollout_steps"]),
                    "return": value,
                    "failure": failure,
                }
            )
    return {
        "schema_version": RESULT_SCHEMA_VERSION,
        "task_id": task["task_id"],
        "task_contract_sha256": task["task_contract_sha256"],
        "worker_process_id": os.getpid(),
        "items": items,
    }


def run_tasks_sequential(
    tasks: list[dict], worker: Callable[[dict], dict]
) -> list[dict]:
    return [worker(task) for task in tasks]


def run_tasks_process_isolated(
    tasks: list[dict],
    worker: Callable[[dict], dict],
    *,
    initializer: Callable[[], None] | None = None,
) -> list[dict]:
    if len(tasks) != 8:
        raise RuntimeError("process-isolated executor requires exactly eight tasks")
    results = []
    with concurrent.futures.ProcessPoolExecutor(
        max_workers=8, initializer=initializer
    ) as executor:
        future_by_id = {
            executor.submit(worker, task): task["task_id"] for task in tasks
        }
        for future in concurrent.futures.as_completed(future_by_id):
            task_id = future_by_id[future]
            try:
                results.append(future.result())
            except Exception as exc:
                raise RuntimeError(f"parallel worker failed closed: {task_id}") from exc
    return results


def validate_and_order_results(tasks: list[dict], results: list[dict]) -> list[dict]:
    task_by_id = {task["task_id"]: task for task in tasks}
    if len(task_by_id) != 8 or len(tasks) != 8:
        raise RuntimeError("parallel parent task manifest mismatch")
    if len(results) != 8:
        raise RuntimeError("parallel result task count mismatch")
    result_ids = [str(result.get("task_id")) for result in results]
    if len(set(result_ids)) != 8 or set(result_ids) != set(task_by_id):
        raise RuntimeError("parallel result task identities are missing or duplicated")

    expected_calls = {}
    actual_calls = {}
    for result in results:
        task = task_by_id[result["task_id"]]
        if (
            result.get("schema_version") != RESULT_SCHEMA_VERSION
            or result.get("task_contract_sha256")
            != task["task_contract_sha256"]
        ):
            raise RuntimeError("parallel worker result contract mismatch")
        for expected in expected_call_contracts(task):
            key = (expected["rollout_index"], expected["role"])
            if key in expected_calls:
                raise RuntimeError("parallel expected call identity is duplicated")
            expected_calls[key] = expected
        for item in result.get("items") or []:
            key = (int(item.get("rollout_index", -1)), str(item.get("role")))
            if key in actual_calls:
                raise RuntimeError("parallel result call identity is duplicated")
            actual_calls[key] = item
    if set(actual_calls) != set(expected_calls):
        raise RuntimeError("parallel result calls are missing or extra")
    for key, expected in expected_calls.items():
        actual = actual_calls[key]
        for field, value in expected.items():
            if actual.get(field) != value:
                raise RuntimeError(f"parallel result call {field} mismatch")
        if actual.get("return") is None and not actual.get("failure"):
            raise RuntimeError("parallel missing return lacks failure evidence")
        if actual.get("return") is not None and actual.get("failure") is not None:
            raise RuntimeError("parallel completed return also records failure")
    role_order = {"teacher": 0, "top1": 1}
    return sorted(
        actual_calls.values(),
        key=lambda item: (int(item["rollout_index"]), role_order[item["role"]]),
    )


def normalized_call_payload(items: list[dict]) -> list[dict]:
    return [
        {
            key: item[key]
            for key in (
                "rollout_index",
                "continuation_profile",
                "determinization_index",
                "determinization_seed",
                "role",
                "action_index",
                "action_sha256",
                "case_deadline_monotonic",
                "max_rollout_steps",
                "return",
                "failure",
            )
        }
        for item in items
    ]


def build_raw_case_result(
    target: dict,
    candidates: list[dict],
    ordered_items: list[dict],
    *,
    case_seconds: float,
    case_timed_out: bool,
) -> dict:
    by_key = {
        (int(item["rollout_index"]), str(item["role"])): item
        for item in ordered_items
    }
    teacher_returns = [
        by_key[(index, "teacher")]["return"] for index in range(16)
    ]
    top1_returns = [by_key[(index, "top1")]["return"] for index in range(16)]
    candidate_results = []
    for candidate, values in zip(candidates, (teacher_returns, top1_returns)):
        failures = [
            by_key[(index, candidate["role"])]["failure"]
            for index in range(16)
            if by_key[(index, candidate["role"])]["failure"] is not None
        ]
        completed = [float(value) for value in values if value is not None]
        candidate_results.append(
            {
                **candidate,
                "requested_rollout_count": 16,
                "completed_rollout_count": len(completed),
                "completion_rate": len(completed) / 16,
                "mean_return": sum(completed) / len(completed) if completed else None,
                "return_variance": frozen_confirmation.sample_variance(completed),
                "failure_count": len(failures),
                "failures": failures,
            }
        )
    paired_rollouts = []
    for schedule_item in frozen_confirmation.rollout_schedule():
        index = int(schedule_item["rollout_index"])
        teacher = teacher_returns[index]
        top1 = top1_returns[index]
        paired_rollouts.append(
            {
                **schedule_item,
                "determinization_seed": by_key[(index, "teacher")][
                    "determinization_seed"
                ],
                "teacher_return": teacher,
                "top1_return": top1,
                "teacher_minus_top1_return": (
                    float(teacher) - float(top1)
                    if teacher is not None and top1 is not None
                    else None
                ),
            }
        )
    return {
        "game_id": target["game_id"],
        "turn_index": target["turn_index"],
        "pipeline_partition": "pipeline_train",
        "legal_action_count": target["legal_action_count"],
        "legal_action_order_sha256": target["legal_action_order_sha256"],
        "case_seconds": float(case_seconds),
        "case_timed_out": bool(case_timed_out),
        "candidate_results": candidate_results,
        "paired_rollouts": paired_rollouts,
        "metrics": frozen_confirmation.directional_metrics(
            teacher_returns, top1_returns
        ),
    }


def execute_parallel_case(target: dict, candidates: list[dict]) -> dict:
    started = time.monotonic()
    deadline = started + frozen_confirmation.MAX_SECONDS_PER_CASE
    tasks = build_determinization_tasks(target, candidates, deadline)
    results = run_tasks_process_isolated(
        tasks,
        production_determinization_worker,
        initializer=initialize_production_worker,
    )
    ordered = validate_and_order_results(tasks, results)
    finished = time.monotonic()
    timed_out = finished >= deadline or any(
        (item.get("failure") or {}).get("reason") == "case_time_budget_exhausted"
        for item in ordered
    )
    return build_raw_case_result(
        target,
        candidates,
        ordered,
        case_seconds=finished - started,
        case_timed_out=timed_out,
    )


def synthetic_target_and_candidates() -> tuple[dict, list[dict]]:
    source_sample = {"game_id": "synthetic", "turn_index": 4}
    target = {
        "game_id": "synthetic",
        "turn_index": 4,
        "pipeline_partition": "pipeline_train",
        "source_sample": source_sample,
        "legal_action_count": 2,
        "legal_action_order_sha256": "synthetic-order-sha256",
    }
    candidates = [
        {
            "role": "teacher",
            "action_index": 1,
            "action_sha256": "teacher-action-sha256",
            "action_id": 11,
            "physical_cards": ["S3"],
            "physical_cards_website": ["S3"],
        },
        {
            "role": "top1",
            "action_index": 7,
            "action_sha256": "top1-action-sha256",
            "action_id": 17,
            "physical_cards": ["H4"],
            "physical_cards_website": ["H4"],
        },
    ]
    return target, candidates


def fail_closed_probes(tasks: list[dict], valid_results: list[dict]) -> dict:
    probes = {}

    def rejected(name: str, changed: list[dict]) -> None:
        try:
            validate_and_order_results(tasks, changed)
        except RuntimeError as exc:
            probes[name] = {"rejected": True, "reason": str(exc)}
            return
        raise RuntimeError(f"parallel fail-closed probe unexpectedly passed: {name}")

    rejected("missing_task", valid_results[:-1])
    rejected("duplicate_task", valid_results[:-1] + [valid_results[0]])
    seed_changed = json.loads(json.dumps(valid_results))
    seed_changed[0]["items"][0]["determinization_seed"] += 1
    rejected("seed_mismatch", seed_changed)
    deadline_changed = json.loads(json.dumps(valid_results))
    deadline_changed[0]["items"][0]["case_deadline_monotonic"] += 1.0
    rejected("deadline_mismatch", deadline_changed)
    duplicate_call = json.loads(json.dumps(valid_results))
    duplicate_call[0]["items"][1] = dict(duplicate_call[0]["items"][0])
    rejected("duplicate_call", duplicate_call)
    return probes


def build_equivalence_result() -> dict:
    frozen_hashes = verify_frozen_inputs()
    target, candidates = synthetic_target_and_candidates()
    scenarios = {}
    parent_pid = os.getpid()
    for name, failure_mode in (("complete", False), ("timeout_failure", True)):
        tasks = build_determinization_tasks(
            target,
            candidates,
            SYNTHETIC_DEADLINE,
            synthetic_failure_mode=failure_mode,
        )
        sequential_results = run_tasks_sequential(
            tasks, synthetic_determinization_worker
        )
        process_results = run_tasks_process_isolated(
            tasks, synthetic_determinization_worker
        )
        sequential_calls = normalized_call_payload(
            validate_and_order_results(tasks, sequential_results)
        )
        process_calls = normalized_call_payload(
            validate_and_order_results(tasks, process_results)
        )
        if sequential_calls != process_calls:
            raise RuntimeError("synthetic sequential/process call mismatch")
        sequential_raw = build_raw_case_result(
            target,
            candidates,
            sequential_calls,
            case_seconds=0.0,
            case_timed_out=failure_mode,
        )
        process_raw = build_raw_case_result(
            target,
            candidates,
            process_calls,
            case_seconds=0.0,
            case_timed_out=failure_mode,
        )
        if sequential_raw != process_raw:
            raise RuntimeError("synthetic sequential/process aggregate mismatch")
        process_pids = {
            int(item["worker_process_id"]) for item in process_results
        }
        if not process_pids or parent_pid in process_pids:
            raise RuntimeError("synthetic executor did not use process isolation")
        scenarios[name] = {
            "task_count": len(tasks),
            "schedule_item_count": sum(
                len(task["schedule_items"]) for task in tasks
            ),
            "candidate_call_count": len(process_calls),
            "task_manifest_sha256": canonical_sha256(
                [task_contract_payload(task) for task in tasks]
            ),
            "ordered_call_sha256": canonical_sha256(process_calls),
            "aggregate_sha256": canonical_sha256(process_raw),
            "sequential_process_calls_exact": True,
            "sequential_process_aggregate_exact": True,
            "process_isolation_verified": True,
            "all_worker_processes_differ_from_parent": True,
            "completed_candidate_call_count": sum(
                item["return"] is not None for item in process_calls
            ),
            "failed_candidate_call_count": sum(
                item["failure"] is not None for item in process_calls
            ),
            "directional_classification": process_raw["metrics"][
                "directional_classification"
            ],
            "calls": process_calls,
            "aggregate": process_raw,
            "fail_closed_probes": (
                fail_closed_probes(tasks, process_results)
                if name == "complete"
                else {}
            ),
        }
    production_source = inspect.getsource(production_determinization_worker)
    executor_source = inspect.getsource(execute_parallel_case)
    required_production_fragments = [
        "information_set.restore_game",
        "random.Random(int(task[\"determinization_seed\"]))",
        "information_set._simulate_candidate",
        "task[\"case_deadline_monotonic\"]",
        "task[\"max_rollout_steps\"]",
    ]
    required_executor_fragments = [
        "started + frozen_confirmation.MAX_SECONDS_PER_CASE",
        "production_determinization_worker",
        "validate_and_order_results",
        "build_raw_case_result",
    ]
    if any(value not in production_source for value in required_production_fragments):
        raise RuntimeError("production worker frozen-contract path changed")
    if any(value not in executor_source for value in required_executor_fragments):
        raise RuntimeError("parallel parent frozen-contract path changed")
    result = {
        "schema_version": SCHEMA_VERSION,
        "status": "completed",
        "frozen_inputs": {
            "paths": {
                **{
                    name: str(path) for name, path in recovery.FROZEN_PATHS.items()
                },
                "stage_6_14r_recovery_audit": str(RECOVERY_PATH),
                "stage_6_14_confirmation_implementation": str(
                    CONFIRMATION_IMPLEMENTATION_PATH
                ),
            },
            "sha256": frozen_hashes,
        },
        "parallel_contract": {
            "worker_task_count_per_case": 8,
            "one_task_per_determinization": True,
            "determinization_indices": list(range(8)),
            "schedule_items_per_case": 16,
            "candidate_calls_per_case": 32,
            "candidate_role_order": ["teacher", "top1"],
            "profile_order_per_determinization": [
                "greedy_bot",
                "tempo_baseline",
            ],
            "common_parent_deadline_seconds": 600.0,
            "max_rollout_steps": 300,
            "worker_label_or_gate_logic": False,
            "parent_metric_function": "frozen_stage_6_9_directional_metrics",
            "result_order": "rollout_index_then_teacher_top1",
            "fail_closed": True,
        },
        "synthetic_equivalence": scenarios,
        "production_static_contract": {
            "worker_recreates_game_from_sample_and_seed": True,
            "worker_uses_frozen_simulate_candidate": True,
            "worker_receives_common_absolute_deadline": True,
            "worker_receives_frozen_max_steps": True,
            "parent_uses_process_pool": True,
            "parent_restores_frozen_schedule_order": True,
            "parent_uses_frozen_metrics": True,
            "formal_rollout_executed_in_this_stage": False,
        },
        "formal_execution_gate": {
            "parallel_equivalence_passed": True,
            "formal_three_case_execution_allowed_in_next_stage": True,
            "required_formal_executor": (
                "execute_parallel_case_with_eight_determinization_tasks_v1"
            ),
            "sequential_retry_allowed": False,
            "partial_stage_6_14_comparison_use_allowed": False,
        },
        "integrity": {
            "failed_confirmation_output_absent": True,
            "parallel_equivalence_output_written_once": True,
            "real_rollout_count": 0,
            "partial_comparison_use_count": 0,
            "integrity_failure_count": 0,
        },
        "forbidden_operation_counts": {
            "real_rollout_runs": 0,
            "partial_comparison_uses": 0,
            "dataset_constructions": 0,
            "objective_constructions": 0,
            "model_scoring_runs": 0,
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
            "synthetic process-isolation equivalence only; no real rollout, "
            "model, dataset, objective, training, Arena, website, or capability evidence"
        ),
    }
    if sum(result["forbidden_operation_counts"].values()) != 0:
        raise RuntimeError("parallel equivalence recorded a forbidden operation")
    return result


def write_json_once(path: Path, result: dict) -> None:
    temporary = path.with_name(f"{path.name}.tmp")
    temporary.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    if path.exists():
        raise RuntimeError(f"parallel equivalence output already exists: {path}")
    temporary.replace(path)


def preflight() -> dict:
    ensure_unused_output()
    hashes = verify_frozen_inputs()
    target, candidates = synthetic_target_and_candidates()
    tasks = build_determinization_tasks(target, candidates, SYNTHETIC_DEADLINE)
    result = {
        "status": "ready",
        "frozen_hash_count": len(hashes),
        "task_count": len(tasks),
        "schedule_item_count": sum(len(task["schedule_items"]) for task in tasks),
        "candidate_call_count": sum(
            len(expected_call_contracts(task)) for task in tasks
        ),
        "failed_confirmation_output_absent": True,
        "equivalence_output_absent": True,
        "real_rollout_count": 0,
    }
    print(json.dumps(result, indent=2))
    return result


def run() -> dict:
    ensure_unused_output()
    result = build_equivalence_result()
    if verify_frozen_inputs() != result["frozen_inputs"]["sha256"]:
        raise RuntimeError("a frozen input changed during parallel equivalence")
    write_json_once(OUTPUT_PATH, result)
    print(
        json.dumps(
            {
                "status": result["status"],
                "output": str(OUTPUT_PATH),
                "complete_synthetic_calls": result["synthetic_equivalence"][
                    "complete"
                ]["candidate_call_count"],
                "timeout_synthetic_failures": result["synthetic_equivalence"][
                    "timeout_failure"
                ]["failed_candidate_call_count"],
                "real_rollout_count": 0,
            },
            indent=2,
        )
    )
    return result


def audit() -> dict:
    saved = load_json(OUTPUT_PATH)
    recomputed = build_equivalence_result()
    if saved != recomputed:
        raise RuntimeError("parallel equivalence independent recomputation mismatch")
    if verify_frozen_inputs() != saved["frozen_inputs"]["sha256"]:
        raise RuntimeError("a frozen input changed during independent audit")
    result = {
        "status": "passed",
        "frozen_hashes_exact": True,
        "eight_task_manifest_exact": True,
        "thirty_two_call_order_exact": True,
        "sequential_process_returns_and_failures_exact": True,
        "common_deadline_and_max_steps_exact": True,
        "fail_closed_probes_passed": True,
        "production_static_contract_exact": True,
        "failed_confirmation_output_absent": not confirmation.OUTPUT_PATH.exists(),
        "real_rollout_count": 0,
        "forbidden_operation_count": sum(
            saved["forbidden_operation_counts"].values()
        ),
    }
    if not result["failed_confirmation_output_absent"]:
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
