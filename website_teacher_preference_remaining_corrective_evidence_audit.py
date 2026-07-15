from __future__ import annotations

import argparse
from collections import Counter
import json
import os
from pathlib import Path

import website_teacher_preference as preference
import website_teacher_preference_corrective_dataset_v3 as dataset_v3
import website_teacher_preference_evidence_audit as source_audit
import website_teacher_preference_remaining_corrective_diagnosis as diagnosis
import website_teacher_preference_residual_corrective_remaining_evidence_audit as pattern


SCHEMA_VERSION = (
    "website_teacher_preference_remaining_corrective_final_evidence_audit_v1"
)
OUTPUT_PATH = Path(
    "website_teacher_preference_remaining_corrective_final_evidence_audit_v1.json"
)
STAGE_6_13_IMPLEMENTATION_PATH = Path(
    "website_teacher_preference_residual_corrective_remaining_evidence_audit.py"
)
STAGE_6_4_PATH = Path(
    "website_teacher_preference_unpaired_train_confirmation_v1.json"
)
EXPECTED_HASHES = {
    "stage_6_17_diagnosis": (
        "1757016ae33628cca075a9cdfc881cd49be7b63f1078ca3f7288f95c7fa00a68"
    ),
    "stage_6_17_implementation": (
        "9231c25d24ee773c0fc376c4e2bb55c6a746897e8d95be2a351fd0c0b6fa85e1"
    ),
    "stage_6_13_implementation": (
        "f49975ace9a3eefd6fa93fafb838463f0b4c2690438856214809ada9d6b31687"
    ),
    "stage_6_4_confirmation": (
        "8e17377b5a1523d9f0a47af7218d687e062a3ade671c57f387eb4c1a0888cfae"
    ),
}
EXPECTED_TRAIN_TARGETS = [
    ("14077", 10, 0),
    ("14031", 4, 2),
    ("14025", 20, 2),
]
EXPECTED_DEVELOPMENT_TARGETS = [
    ("13992", 16, 7),
    ("14074", 9, 9),
    ("13871", 9, 10),
]


def frozen_paths() -> dict[str, Path]:
    return {
        **diagnosis.frozen_paths(),
        "stage_6_17_diagnosis": diagnosis.OUTPUT_PATH,
        "stage_6_17_implementation": Path(
            "website_teacher_preference_remaining_corrective_diagnosis.py"
        ),
        "stage_6_13_implementation": STAGE_6_13_IMPLEMENTATION_PATH,
        "stage_6_4_confirmation": STAGE_6_4_PATH,
    }


def load_json(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError(f"{path} must contain a JSON object")
    return payload


def verify_frozen_hashes() -> dict[str, str]:
    recursive = diagnosis.verify_frozen_hashes()
    specific_paths = {
        "stage_6_17_diagnosis": diagnosis.OUTPUT_PATH,
        "stage_6_17_implementation": Path(
            "website_teacher_preference_remaining_corrective_diagnosis.py"
        ),
        "stage_6_13_implementation": STAGE_6_13_IMPLEMENTATION_PATH,
        "stage_6_4_confirmation": STAGE_6_4_PATH,
    }
    specific = {
        name: source_audit._sha256(path) for name, path in specific_paths.items()
    }
    for name, expected in EXPECTED_HASHES.items():
        if specific.get(name) != expected:
            raise RuntimeError(f"{name} SHA-256 mismatch")
    return {**recursive, **specific}


def ensure_unused_output(path: Path = OUTPUT_PATH) -> None:
    temporary = path.with_name(f"{path.name}.tmp")
    if path.exists() or temporary.exists():
        raise RuntimeError(f"final evidence audit output already exists: {path}")


def validate_stage_6_17(payload: dict) -> dict:
    scoring = payload.get("scoring_accounting") or {}
    replay = (payload.get("stage_6_16_metric_reproduction") or {}).get(
        "evaluation_accounting"
    ) or {}
    aggregates = payload.get("aggregates") or {}
    expected = {
        "pipeline_train": (18, 889, 15, 0, 3, 0, 3, 4),
        "pipeline_development": (4, 45, 1, 0, 3, 0, 3, 12),
        "overall": (22, 934, 16, 0, 6, 0, 6, 16),
    }
    if (
        payload.get("schema_version") != diagnosis.SCHEMA_VERSION
        or payload.get("status") != "completed"
        or scoring.get("unique_teacher_state_count") != 22
        or scoring.get("recorded_legal_action_count") != 934
        or scoring.get("legal_action_score_count") != 934
        or scoring.get("source_duplicate_action_vector_count") != 8
        or replay.get("pair_evaluation_count") != 64
        or replay.get("action_value_evaluation_count") != 128
        or any(
            int(value) != 0
            for value in (payload.get("forbidden_operation_counts") or {}).values()
        )
    ):
        raise RuntimeError("Stage 6.17 diagnosis contract mismatch")
    for partition, values in expected.items():
        item = aggregates.get(partition) or {}
        actual = (
            item.get("state_count"),
            item.get("legal_action_count"),
            item.get("teacher_top1_count"),
            item.get("behavior_top1_count"),
            item.get("other_action_top1_count"),
            item.get("pass_top1_count"),
            item.get("unpaired_action_strictly_outranks_teacher_state_count"),
            item.get("unpaired_actions_strictly_above_teacher_count"),
        )
        if actual != values:
            raise RuntimeError(f"Stage 6.17 {partition} aggregate mismatch")
    return {
        "state_count": 22,
        "full_set_action_score_count": 934,
        "teacher_top1_count": 16,
        "behavior_top1_count": 0,
        "other_top1_count": 6,
        "pass_top1_count": 0,
        "model_loaded_or_scored": False,
    }


def extract_targets(
    diagnosis_payload: dict, samples: list[dict], split: dict
) -> tuple[list[dict], dict[tuple[str, int], dict]]:
    sample_by_key = {
        (str(sample["game_id"]), int(sample["turn_index"])): sample
        for sample in samples
    }
    train_ids = {str(value) for value in split["pipeline_train_game_ids"]}
    development_ids = {
        str(value) for value in split["pipeline_development_game_ids"]
    }
    residual_states = [
        state
        for state in diagnosis_payload["state_diagnostics"]
        if state.get("top1_source") == "other"
    ]
    targets = []
    for state in residual_states:
        key = (str(state["game_id"]), int(state["turn_index"]))
        sample = sample_by_key.get(key)
        if sample is None:
            raise RuntimeError("remaining target sample missing")
        actions = sample["legal_actions"]
        q_values = state["legal_action_q_values"]
        if (
            len(actions) != len(q_values)
            or source_audit._action_order_sha256(actions)
            != state["legal_action_order_sha256"]
        ):
            raise RuntimeError("remaining target action order mismatch")
        top1_index = q_values.index(max(q_values))
        teacher_indices = [
            index for index, action in enumerate(actions)
            if action == sample["teacher_action"]
        ]
        if len(teacher_indices) != 1 or top1_index != int(state["top1_index"]):
            raise RuntimeError("remaining target action identity mismatch")
        teacher_index = teacher_indices[0]
        partition = (
            "pipeline_train" if key[0] in train_ids else
            "pipeline_development" if key[0] in development_ids else None
        )
        if partition != state["pipeline_partition"]:
            raise RuntimeError("remaining target partition mismatch")
        same = [index for index, action in enumerate(actions) if action == actions[top1_index]]
        if same != [top1_index]:
            raise RuntimeError("remaining current top1 mapping is ambiguous")
        targets.append(
            {
                "game_id": key[0],
                "turn_index": key[1],
                "pipeline_partition": partition,
                "legal_action_count": len(actions),
                "legal_action_order_sha256": state["legal_action_order_sha256"],
                "teacher_action_index": teacher_index,
                "teacher_action_sha256": source_audit._action_sha256(actions[teacher_index]),
                "teacher_rank": int(state["teacher_rank"]),
                "top1_action_index": top1_index,
                "top1_action_sha256": source_audit._action_sha256(actions[top1_index]),
                "top1_same_vector_recorded_indices": same,
                "top1_physical_cards_website": pattern.physical_cards_website(actions[top1_index]),
                "teacher_physical_cards_website": pattern.physical_cards_website(actions[teacher_index]),
                "physical_identity_derivation": "decoded_from_frozen_physical_action_54",
            }
        )
    train_actual = [
        (item["game_id"], item["turn_index"], item["top1_action_index"])
        for item in targets if item["pipeline_partition"] == "pipeline_train"
    ]
    development_actual = [
        (item["game_id"], item["turn_index"], item["top1_action_index"])
        for item in targets if item["pipeline_partition"] == "pipeline_development"
    ]
    if train_actual != EXPECTED_TRAIN_TARGETS or development_actual != EXPECTED_DEVELOPMENT_TARGETS:
        raise RuntimeError("remaining 3/3 target identity mismatch")
    return targets, sample_by_key


def case_by_key(payload: dict, expected_schema: str) -> dict[tuple[str, int], dict]:
    cases = payload.get("case_results") or []
    if (
        payload.get("schema_version") != expected_schema
        or payload.get("status") != "completed"
        or any(
            int(value) != 0
            for value in (payload.get("forbidden_operation_counts") or {}).values()
        )
    ):
        raise RuntimeError("frozen confirmation contract mismatch")
    result = {
        (str(case["game_id"]), int(case["turn_index"])): case for case in cases
    }
    if len(result) != len(cases):
        raise RuntimeError("frozen confirmation case identity is not unique")
    return result


def action_provenance(
    target: dict,
    sample: dict,
    case: dict | None,
    rejected_role: str,
) -> dict:
    if case is None:
        return {
            "case_present": False,
            "rejected_action_identity_matches_current_top1": False,
            "applicable_to_current_top1": False,
            "used_as_current_direct_evidence": False,
        }
    candidates = case.get("candidate_results") or []
    if [item.get("role") for item in candidates] != ["teacher", rejected_role]:
        raise RuntimeError("frozen confirmation candidate roles mismatch")
    teacher, rejected = candidates
    teacher_index = int(teacher["action_index"])
    rejected_index = int(rejected["action_index"])
    actions = sample["legal_actions"]
    if (
        source_audit._action_sha256(actions[teacher_index])
        != teacher["action_sha256"]
        or source_audit._action_sha256(actions[rejected_index])
        != rejected["action_sha256"]
    ):
        raise RuntimeError("frozen confirmation action identity mismatch")
    identity_matches = (
        rejected_index == target["top1_action_index"]
        and rejected["action_sha256"] == target["top1_action_sha256"]
    )
    metrics = case.get("metrics") or {}
    return {
        "case_present": True,
        "rejected_action_role": rejected_role,
        "rejected_action_index": rejected_index,
        "rejected_action_sha256": rejected["action_sha256"],
        "directional_classification": metrics.get("directional_classification"),
        "rejected_action_identity_matches_current_top1": identity_matches,
        "applicable_to_current_top1": identity_matches,
        "used_as_current_direct_evidence": False,
    }


def validate_context() -> dict:
    frozen_hashes = verify_frozen_hashes()
    diagnosis_payload = load_json(diagnosis.OUTPUT_PATH)
    conclusion = validate_stage_6_17(diagnosis_payload)
    samples, _summary, teacher_hash = preference.load_teacher_dataset(
        dataset_v3.TEACHER_PATH
    )
    if teacher_hash != frozen_hashes["teacher_dataset"]:
        raise RuntimeError("loaded teacher dataset hash mismatch")
    split = load_json(dataset_v3.SPLIT_PATH)
    targets, sample_by_key = extract_targets(diagnosis_payload, samples, split)
    stage_6_9 = pattern.validate_stage_6_9(load_json(pattern.STAGE_6_9_PATH))
    stage_6_13_payload = load_json(pattern.OUTPUT_PATH)
    prior_entries = stage_6_13_payload.get("pipeline_train_target_audits") or []
    if (
        stage_6_13_payload.get("schema_version") != pattern.SCHEMA_VERSION
        or stage_6_13_payload.get("status") != "completed"
        or len(prior_entries) != 6
        or any(
            int(value) != 0
            for value in (
                stage_6_13_payload.get("forbidden_operation_counts") or {}
            ).values()
        )
    ):
        raise RuntimeError("Stage 6.13 evidence audit contract mismatch")
    stage_6_13_by_key = {
        (str(item["game_id"]), int(item["turn_index"])): item
        for item in prior_entries
    }
    stage_6_13_source_hashes: dict[str, str] = {}
    for item in prior_entries:
        name = item.get("source_rollout_evidence")
        source_hash = item.get("source_rollout_evidence_sha256")
        if not isinstance(name, str) or not isinstance(source_hash, str):
            raise RuntimeError("Stage 6.13 source evidence hash missing")
        previous = stage_6_13_source_hashes.setdefault(name, source_hash)
        if previous != source_hash:
            raise RuntimeError("Stage 6.13 source evidence hash is inconsistent")
    stage_6_4 = case_by_key(
        load_json(STAGE_6_4_PATH),
        "website_teacher_preference_unpaired_train_confirmation_v1",
    )
    remaining_payload = load_json(dataset_v3.CONFIRMATION_PATH)
    dataset_v3.validate_and_select_confirmation(remaining_payload)
    stage_6_14e = {
        (str(case["game_id"]), int(case["turn_index"])): case
        for case in remaining_payload["case_results"]
    }
    return {
        "frozen_hashes": frozen_hashes,
        "stage_6_17_payload": diagnosis_payload,
        "stage_6_17_conclusion": conclusion,
        "targets": targets,
        "train_targets": [
            item for item in targets
            if item["pipeline_partition"] == "pipeline_train"
        ],
        "development_targets": [
            item for item in targets
            if item["pipeline_partition"] == "pipeline_development"
        ],
        "sample_by_key": sample_by_key,
        "stage_6_4_by_key": stage_6_4,
        "stage_6_9_by_key": stage_6_9,
        "stage_6_13_by_key": stage_6_13_by_key,
        "stage_6_13_source_hashes": stage_6_13_source_hashes,
        "stage_6_14e_by_key": stage_6_14e,
    }


def forbidden_operation_counts() -> dict[str, int]:
    return {
        "model_loads": 0,
        "model_scoring_runs": 0,
        "new_rollout_runs": 0,
        "dataset_constructions": 0,
        "objective_constructions": 0,
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
        "future_manifest_executions": 0,
        "checkpoint_promotions": 0,
        "capability_claims": 0,
        "unsupported_ordering_labels": 0,
    }


def compute_result(context: dict) -> dict:
    workspace_root = Path.cwd()
    evidence_cache: dict[str, tuple[Path, dict]] = {}
    train_audits = []
    for target in context["train_targets"]:
        key = (target["game_id"], target["turn_index"])
        sample = context["sample_by_key"][key]
        reference = sample.get("source_rollout_eval")
        if not isinstance(reference, str) or not reference:
            raise RuntimeError("train teacher sample source evidence missing")
        if reference not in evidence_cache:
            path = source_audit.resolve_direct_evidence_path(reference, workspace_root)
            evidence_cache[reference] = (path, load_json(path))
        path, evidence = evidence_cache[reference]
        item = pattern.audit_train_target(
            target,
            sample,
            path,
            evidence,
            context["stage_6_9_by_key"].get(key),
            context["stage_6_13_by_key"].get(key),
        )
        expected_source_hash = context["stage_6_13_source_hashes"].get(
            item["source_rollout_evidence"]
        )
        if item["source_rollout_evidence_sha256"] != expected_source_hash:
            raise RuntimeError("direct source evidence hash is not frozen")
        item["stage_6_13_provenance"] = item.pop("stage_6_8_provenance")
        item["stage_6_4_provenance"] = action_provenance(
            target, sample, context["stage_6_4_by_key"].get(key), "top1"
        )
        item["stage_6_14e_provenance"] = action_provenance(
            target, sample, context["stage_6_14e_by_key"].get(key), "residual"
        )
        if (
            item["stage_6_4_provenance"]["applicable_to_current_top1"]
            and item["evidence_classification"]
            != "direct_paired_comparison_inconclusive"
        ):
            raise RuntimeError("Stage 6.4 direct evidence classification mismatch")
        train_audits.append(item)
    aggregates = pattern.aggregate_train_audits(train_audits)
    expected_aggregates = {
        "target_count": 3,
        "source_file_count": 2,
        "current_top1_absent_from_source_legal_actions_count": 0,
        "current_top1_not_evaluated_as_source_candidate_count": 0,
        "source_candidates_present_without_direct_paired_comparison_count": 2,
        "direct_paired_comparison_inconclusive_count": 1,
        "teacher_over_current_top1_supported_count": 0,
        "current_top1_over_teacher_supported_count": 0,
        "stage_6_9_exact_action_evidence_count": 1,
        "stage_6_9_different_action_nontransfer_count": 1,
        "insufficient_evidence_count": 3,
        "ambiguous_mapping_count": 0,
    }
    if aggregates != expected_aggregates or len(evidence_cache) != 2:
        raise RuntimeError("final train evidence aggregate mismatch")
    future_manifest = [
        {
            "game_id": item["game_id"],
            "turn_index": item["turn_index"],
            "pipeline_partition": "pipeline_train",
            "top1_action_index": item["top1_action_index"],
            "top1_action_sha256": item["top1_action_sha256"],
            "evidence_classification": item["evidence_classification"],
            "reason": item["insufficiency_reasons"],
            "new_confirmation_needed": item["evidence_classification"]
            in {
                "current_top1_not_evaluated_as_source_candidate",
                "source_candidates_present_without_direct_paired_comparison",
            },
            "execution_allowed_in_this_stage": False,
        }
        for item in train_audits
        if not item["teacher_over_current_top1_supported"]
        and not item["current_top1_over_teacher_supported"]
    ]
    forbidden = forbidden_operation_counts()
    result = {
        "schema_version": SCHEMA_VERSION,
        "status": "completed",
        "frozen_inputs": {
            "paths": {name: str(path) for name, path in frozen_paths().items()},
            "sha256": context["frozen_hashes"],
        },
        "stage_6_17_conclusion_reproduction": context["stage_6_17_conclusion"],
        "target_reproduction": {
            "expected_target_count": 6,
            "reproduced_target_count": 6,
            "pipeline_train_target_count": 3,
            "pipeline_development_target_count": 3,
            "missing_target_count": 0,
            "duplicate_target_count": 0,
            "extra_target_count": 0,
            "reconstructed_action_count": 0,
            "substituted_action_count": 0,
            "transferred_action_count": 0,
            "ambiguous_mapping_count": 0,
        },
        "pipeline_train_target_audits": train_audits,
        "pipeline_development_identity_only": context["development_targets"],
        "source_evidence_files": [
            {"path": name, "sha256": source_audit._sha256(evidence_cache[name][0])}
            for name in sorted(evidence_cache)
        ],
        "source_evidence_file_count": len(evidence_cache),
        "train_evidence_aggregates": aggregates,
        "development_isolation": {
            "identity_only_target_count": 3,
            "source_reference_record_count": 0,
            "source_evidence_target_query_count": 0,
            "candidate_inspection_count": 0,
            "threshold_design_use_count": 0,
            "objective_design_use_count": 0,
            "confirmation_design_use_count": 0,
        },
        "future_counterfactual_manifest": future_manifest,
        "future_counterfactual_manifest_case_count": len(future_manifest),
        "future_counterfactual_manifest_new_confirmation_needed_count": sum(
            item["new_confirmation_needed"] for item in future_manifest
        ),
        "future_counterfactual_manifest_existing_inconclusive_count": sum(
            not item["new_confirmation_needed"] for item in future_manifest
        ),
        "future_counterfactual_manifest_executed": False,
        "new_dataset_or_objective_defined": False,
        "unsupported_ordering_label_count": 0,
        "interpretation_scope": {
            "read_only_existing_evidence_audit": True,
            "causal_claim_allowed": False,
            "capability_claim_allowed": False,
            "checkpoint_promotion_allowed": False,
        },
        "forbidden_operation_counts": forbidden,
    }
    if any(forbidden.values()):
        raise RuntimeError("forbidden final evidence operation recorded")
    return result


def _verify_source_hashes(result: dict) -> None:
    workspace_root = Path.cwd()
    for item in result["source_evidence_files"]:
        path = source_audit.resolve_direct_evidence_path(item["path"], workspace_root)
        if source_audit._sha256(path) != item["sha256"]:
            raise RuntimeError("a direct source evidence file changed during audit")


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
    context = validate_context()
    result = {
        "status": "ready",
        "output_exists": False,
        "frozen_hash_count": len(context["frozen_hashes"]),
        "remaining_target_count": len(context["targets"]),
        "pipeline_train_target_count": len(context["train_targets"]),
        "pipeline_development_target_count": len(context["development_targets"]),
        "model_loaded_or_scored": False,
        "development_source_evidence_read_count": 0,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return result


def run() -> dict:
    ensure_unused_output()
    context = validate_context()
    result = compute_result(context)
    if verify_frozen_hashes() != context["frozen_hashes"]:
        raise RuntimeError("a frozen input changed during final evidence audit")
    _verify_source_hashes(result)
    write_output_once(OUTPUT_PATH, result)
    print(
        json.dumps(
            {
                "status": result["status"],
                "output": str(OUTPUT_PATH),
                "target_reproduction": result["target_reproduction"],
                "train_evidence_aggregates": result["train_evidence_aggregates"],
                "development_isolation": result["development_isolation"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return result


def audit() -> dict:
    saved = load_json(OUTPUT_PATH)
    context = validate_context()
    recomputed = compute_result(context)
    if saved != recomputed:
        raise RuntimeError("independent final evidence reproduction mismatch")
    if verify_frozen_hashes() != context["frozen_hashes"]:
        raise RuntimeError("a frozen input changed during independent audit")
    _verify_source_hashes(saved)
    result = {
        "status": "passed",
        "stage_6_17_conclusion_exact_without_model_scoring": True,
        "target_identities_and_physical_cards_exact": True,
        "source_hashes_exact": True,
        "prior_action_identity_boundaries_exact": True,
        "classifications_exact": True,
        "partition_counts_and_aggregates_exact": True,
        "development_source_evidence_read_count": 0,
        "forbidden_operation_count": sum(
            saved["forbidden_operation_counts"].values()
        ),
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
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
