from __future__ import annotations

from collections import Counter
import argparse
import hashlib
import json
import os
from pathlib import Path

import website_teacher_preference as preference
import website_teacher_preference_corrective_dataset as dataset_v1
import website_teacher_preference_corrective_dataset_v2 as dataset_v2
import website_teacher_preference_corrective_diagnosis as old_corrective_diagnosis
import website_teacher_preference_diagnosis as base_diagnosis
import website_teacher_preference_residual_corrective_training as residual_training


SCHEMA_VERSION = (
    "website_teacher_preference_residual_corrective_failure_diagnosis_v1"
)
OUTPUT_PATH = Path(
    "website_teacher_preference_residual_corrective_failure_diagnosis_v1.json"
)
OLD_DIAGNOSIS_PATH = Path(
    "website_teacher_preference_corrective_failure_diagnosis_v1.json"
)
STAGE_6_6_REPORT_PATH = Path("website_teacher_preference_corrective_training_v1.json")
STAGE_6_6_CHECKPOINT_PATH = Path(
    "models_website_teacher_preference_corrective_v1/"
    "website_teacher_preference_corrective_final.pth"
)
ARENA_PATH = Path("website_teacher_preference_arena_smoke20_v1.json")
EXPECTED_HASHES = {
    "residual_corrective_training_report": (
        "307b92eca7aef2d7fa927dec71f1e2ccd8b87b71d2336c5630f39c24d0a176dd"
    ),
    "residual_corrective_checkpoint": (
        "cdb3c18948c9310c88f52789f2fd5a12326859ff653558a6aebe7eb569393105"
    ),
    "corrective_dataset_v2": (
        "40024f7c064f0ebb7999c4ac0f7bc85d77b759a23956cbe596756763d4009d4d"
    ),
    "corrective_manifest_v2": (
        "ce5141f6254218d9230b15117a88d3c5e6bd374839bcf5fc77b393e2599ec353"
    ),
    "teacher_dataset": (
        "a74416e6facb28a1bc64563eba90cb33d460dc9e59cc2109518da142465e15f8"
    ),
    "split_manifest": (
        "5a15e514dc9bc51d77d300837151d9f1a49250f42885cc7940725bcbe4d35107"
    ),
    "stage_6_9_confirmation": (
        "352cd0dfe0a4c958ba0555b776326a2b58470a980aef461ed49d4c59a7474c7a"
    ),
    "stage_6_7_diagnosis": (
        "2b4359470e74f5eae28d6589477aca5f929ae6b5b88e094fa86209bf4328163d"
    ),
    "stage_6_6_training_report": (
        "baa97ccf71c237895a92f4cb8b36b9559cf3cabe45b4901b7481d9f50f4c0830"
    ),
    "stage_6_6_checkpoint": (
        "8cb368c8c0ae3f8c41c577e055ddd4796cbaae8163720cc630a435aa25bc1a49"
    ),
    "stage_6_1_arena": (
        "aa45da9de202194102fe8d11e612ad3eb4b51177fd910b9a7948836afd2a1fe6"
    ),
}


def frozen_paths() -> dict[str, Path]:
    return {
        "residual_corrective_training_report": residual_training.REPORT_PATH,
        "residual_corrective_checkpoint": residual_training.CHECKPOINT_PATH,
        "corrective_dataset_v2": residual_training.DATASET_PATH,
        "corrective_manifest_v2": residual_training.MANIFEST_PATH,
        "teacher_dataset": residual_training.TEACHER_PATH,
        "split_manifest": residual_training.SPLIT_PATH,
        "stage_6_9_confirmation": residual_training.CONFIRMATION_PATH,
        "stage_6_7_diagnosis": OLD_DIAGNOSIS_PATH,
        "stage_6_6_training_report": STAGE_6_6_REPORT_PATH,
        "stage_6_6_checkpoint": STAGE_6_6_CHECKPOINT_PATH,
        "stage_6_1_arena": ARENA_PATH,
    }


def verify_frozen_hashes() -> dict[str, str]:
    actual = {name: dataset_v1.sha256(path) for name, path in frozen_paths().items()}
    for name, expected in EXPECTED_HASHES.items():
        if actual.get(name) != expected:
            raise RuntimeError(f"{name} SHA-256 mismatch")
    return actual


def load_json(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError(f"{path} must contain a JSON object")
    return payload


def ensure_unused_output(path: Path = OUTPUT_PATH) -> None:
    temporary = path.with_name(f"{path.name}.tmp")
    if path.exists() or temporary.exists():
        raise RuntimeError("residual corrective diagnostic output already exists")


def validate_context() -> dict:
    frozen_hashes = verify_frozen_hashes()
    report = load_json(residual_training.REPORT_PATH)
    old = load_json(OLD_DIAGNOSIS_PATH)
    manifest = load_json(residual_training.MANIFEST_PATH)
    confirmation = load_json(residual_training.CONFIRMATION_PATH)
    dataset = residual_training.frozen_training.torch_load(residual_training.DATASET_PATH)
    samples, _summary, teacher_hash = preference.load_teacher_dataset(
        residual_training.TEACHER_PATH
    )
    pairs = dataset.get("pairs") if isinstance(dataset, dict) else None
    if teacher_hash != EXPECTED_HASHES["teacher_dataset"]:
        raise RuntimeError("teacher dataset loader hash mismatch")
    required_accounting = {
        "training_run_count": 1,
        "optimizer_step_count": 60,
        "development_training_use_count": 0,
        "extra_training_target_count": 0,
        "fine_tuning_run_count": 0,
        "nonfinite_training_loss_count": 0,
    }
    accounting = report.get("training_accounting") or {}
    if (
        report.get("schema_version") != residual_training.SCHEMA_VERSION
        or report.get("status") != "completed"
        or report.get("frozen_inputs", {}).get("sha256")
        != residual_training.EXPECTED_HASHES
        or report.get("checkpoint_sha256")
        != EXPECTED_HASHES["residual_corrective_checkpoint"]
        or report.get("checkpoint_schema_version")
        != residual_training.CHECKPOINT_SCHEMA_VERSION
        or report.get("checkpoint_reload_verified") is not True
        or report.get("checkpoint_save_count") != 1
        or report.get("checkpoint_promotion_allowed") is not False
        or report.get("capability_claim_allowed") is not False
        or report.get("threshold_passed") is not True
        or any(accounting.get(key) != value for key, value in required_accounting.items())
        or any(
            int(value) != 0
            for value in (report.get("forbidden_operation_counts") or {}).values()
        )
    ):
        raise RuntimeError("Stage 6.11 report validation mismatch")
    old_scoring = old.get("scoring_accounting") or {}
    if (
        old.get("schema_version") != old_corrective_diagnosis.SCHEMA_VERSION
        or old.get("status") != "completed"
        or old_scoring.get("unique_teacher_state_count") != 22
        or old_scoring.get("recorded_legal_action_count") != 934
        or old_scoring.get("legal_action_score_count") != 934
        or old_scoring.get("source_duplicate_action_vector_count") != 8
        or set(old.get("aggregates") or {})
        != {"pipeline_train", "pipeline_development", "overall"}
        or any(
            int(value) != 0
            for value in (old.get("forbidden_operation_counts") or {}).values()
        )
    ):
        raise RuntimeError("Stage 6.7 diagnosis validation mismatch")
    if (
        dataset.get("format") != dataset_v2.FORMAT_VERSION
        or dataset.get("frozen_base_sample_count") != 22
        or dataset.get("frozen_base_samples") != samples
        or not isinstance(pairs, list)
        or len(pairs) != 32
        or manifest.get("schema_version") != dataset_v2.MANIFEST_SCHEMA_VERSION
        or manifest.get("status") != "completed"
        or manifest.get("dataset_sha256") != EXPECTED_HASHES["corrective_dataset_v2"]
        or manifest.get("pair_ids") != [pair["pair_id"] for pair in pairs]
        or manifest.get("objective_manifest") != dataset.get("objective_manifest")
        or any(
            int(value) != 0
            for value in (dataset.get("forbidden_operation_counts") or {}).values()
        )
        or any(
            int(value) != 0
            for value in (manifest.get("forbidden_operation_counts") or {}).values()
        )
    ):
        raise RuntimeError("corrective dataset v2 or manifest validation mismatch")
    source_counts = Counter(pair["pair_source"] for pair in pairs)
    partition_counts = Counter(pair["pipeline_partition"] for pair in pairs)
    if source_counts != Counter(
        {
            "frozen_teacher_v6": 22,
            "stage_6_4_train_confirmation": 6,
            "stage_6_9_residual_train_confirmation": 4,
        }
    ) or partition_counts != Counter(
        {"pipeline_train": 28, "pipeline_development": 4}
    ):
        raise RuntimeError("corrective dataset v2 pair accounting mismatch")
    split = load_json(residual_training.SPLIT_PATH)
    partitions = base_diagnosis.map_partitions(samples, split)
    mappings = build_corrective_mappings(samples, pairs, confirmation, old)
    return {
        "frozen_hashes": frozen_hashes,
        "report": report,
        "old": old,
        "samples": samples,
        "pairs": pairs,
        "partitions": partitions,
        "corrective_mappings": mappings,
    }


def build_corrective_mappings(
    samples: list[dict], pairs: list[dict], confirmation: dict, old: dict
) -> dict[str, dict]:
    sample_by_key = {
        (str(sample["game_id"]), int(sample["turn_index"])): sample
        for sample in samples
    }
    old_stage_6_4 = {
        (str(item["game_id"]), int(item["turn_index"])): item
        for item in old["corrective_pair_diagnostics"]
    }
    supported_stage_6_9 = {
        (str(case["game_id"]), int(case["turn_index"])): case
        for case in residual_training.select_supported_cases(confirmation)
    }
    mappings: dict[str, dict] = {}
    corrective_pairs = [
        pair for pair in pairs if pair["pair_source"] != "frozen_teacher_v6"
    ]
    for pair in corrective_pairs:
        key = (str(pair["game_id"]), int(pair["turn_index"]))
        sample = sample_by_key.get(key)
        preferred_index = int(pair["preferred_action_index"])
        rejected_index = int(pair["rejected_action_index"])
        if sample is None or pair["pair_id"] in mappings:
            raise RuntimeError(f"missing or duplicate corrective mapping {pair['pair_id']}")
        if (
            sample["legal_actions"][preferred_index] != pair["preferred_action"]
            or sample["legal_actions"][rejected_index] != pair["rejected_action"]
            or dataset_v1.action_sha256(sample["legal_actions"][preferred_index])
            != pair["preferred_action_sha256"]
            or dataset_v1.action_sha256(sample["legal_actions"][rejected_index])
            != pair["rejected_action_sha256"]
        ):
            raise RuntimeError(f"corrective action identity mismatch {key}")
        if pair["pair_source"] == "stage_6_4_train_confirmation":
            previous = old_stage_6_4.get(key)
            if (
                previous is None
                or previous["pair_id"] != pair["pair_id"]
                or int(previous["preferred_index"]) != preferred_index
                or int(previous["rejected_index"]) != rejected_index
            ):
                raise RuntimeError(f"Stage 6.4 corrective mapping mismatch {key}")
        elif pair["pair_source"] == "stage_6_9_residual_train_confirmation":
            case = supported_stage_6_9.get(key)
            candidates = case.get("candidate_results") if case else None
            if (
                not candidates
                or [item.get("role") for item in candidates] != ["teacher", "residual"]
                or int(candidates[0]["action_index"]) != preferred_index
                or int(candidates[1]["action_index"]) != rejected_index
                or candidates[0]["action_sha256"] != pair["preferred_action_sha256"]
                or candidates[1]["action_sha256"] != pair["rejected_action_sha256"]
                or candidates[0]["physical_cards_website"]
                != pair["preferred_physical_cards_website"]
                or candidates[1]["physical_cards_website"]
                != pair["rejected_physical_cards_website"]
            ):
                raise RuntimeError(f"Stage 6.9 corrective mapping mismatch {key}")
        else:
            raise RuntimeError("unexpected corrective pair source")
        mappings[pair["pair_id"]] = {
            field: pair[field]
            for field in (
                "pair_id",
                "pair_source",
                "preference_target",
                "preferred_action_sha256",
                "rejected_action_sha256",
                "preferred_physical_cards_website",
                "rejected_physical_cards_website",
            )
        }
        mappings[pair["pair_id"]].update(
            {
                "game_id": key[0],
                "turn_index": key[1],
                "preferred_index": preferred_index,
                "rejected_index": rejected_index,
            }
        )
    mapped_stage_6_9_keys = {
        (item["game_id"], item["turn_index"])
        for item in mappings.values()
        if item["pair_source"] == "stage_6_9_residual_train_confirmation"
    }
    if len(mappings) != 10 or set(supported_stage_6_9) != mapped_stage_6_9_keys:
        raise RuntimeError("corrective mapping count mismatch")
    return mappings


def enrich_state(sample: dict, state: dict) -> dict:
    result = dict(state)
    teacher_index = int(result["teacher_action_index"])
    behavior_index = int(result["behavior_action_index"])
    teacher_q = float(result["teacher_q"])
    result["teacher_action_sha256"] = dataset_v1.action_sha256(
        sample["legal_actions"][teacher_index]
    )
    result["behavior_action_sha256"] = dataset_v1.action_sha256(
        sample["legal_actions"][behavior_index]
    )
    result["actions_strictly_above_teacher"] = [
        {
            "action_index": index,
            "action_sha256": dataset_v1.action_sha256(sample["legal_actions"][index]),
            "q_value": float(value),
            "source": (
                "behavior"
                if index == behavior_index
                else "other"
            ),
            "is_pass": all(float(item) == 0.0 for item in sample["legal_actions"][index]),
        }
        for index, value in enumerate(result["legal_action_q_values"])
        if float(value) > teacher_q
    ]
    if len(result["actions_strictly_above_teacher"]) != int(
        result["actions_strictly_above_teacher_count"]
    ):
        raise RuntimeError("strictly-above-teacher detail count mismatch")
    return result


def reproduce_stage_6_11_metrics(model: object, pairs: list[dict], report: dict) -> dict:
    actual = residual_training.evaluate_model(model, pairs)
    if actual != report.get("final_metrics"):
        raise RuntimeError("Stage 6.11 metrics or prediction digests did not reproduce")
    return {
        "actual": actual,
        "frozen": report["final_metrics"],
        "exact_match": True,
        "evaluation_accounting": {
            "pair_metric_section_count": 5,
            "pair_evaluation_count": 60,
            "action_value_evaluation_count": 120,
            "model_forward_batch_count": 10,
            "included_in_full_legal_set_score_count": False,
            "purpose": "exact_frozen_stage_6_11_batch_shape_reproduction",
        },
    }


def corrective_pair_diagnostics(
    states: list[dict], mappings: dict[str, dict]
) -> list[dict]:
    state_by_key = {
        (str(state["game_id"]), int(state["turn_index"])): state for state in states
    }
    results: list[dict] = []
    for mapping in mappings.values():
        key = (str(mapping["game_id"]), int(mapping["turn_index"]))
        state = state_by_key[key]
        q_values = state["legal_action_q_values"]
        preferred_index = int(mapping["preferred_index"])
        rejected_index = int(mapping["rejected_index"])
        preferred_q = float(q_values[preferred_index])
        rejected_q = float(q_values[rejected_index])
        results.append(
            {
                "game_id": key[0],
                "turn_index": key[1],
                "pipeline_partition": state["pipeline_partition"],
                **mapping,
                "preferred_rank": 1 + sum(value > preferred_q for value in q_values),
                "rejected_rank": 1 + sum(value > rejected_q for value in q_values),
                "preferred_q": preferred_q,
                "rejected_q": rejected_q,
                "teacher_minus_rejected_margin": preferred_q - rejected_q,
                "teacher_outranks_frozen_rejected_action": preferred_q > rejected_q,
                "teacher_is_first_max_full_set_top1": (
                    int(state["top1_index"]) == preferred_index
                ),
                "frozen_rejected_action_remains_new_top1": (
                    int(state["top1_index"]) == rejected_index
                ),
                "new_full_set_top1_index": int(state["top1_index"]),
                "new_full_set_top1_source": state["top1_source"],
            }
        )
    return results


def action_order_digest(states: list[dict]) -> str:
    digest = hashlib.sha256()
    for state in states:
        digest.update(f"{state['game_id']}:{state['turn_index']}\n".encode("utf-8"))
        digest.update(bytes.fromhex(state["legal_action_order_sha256"]))
    return digest.hexdigest()


def compute_result(context: dict) -> dict:
    model, checkpoint = residual_training.load_checkpoint(
        residual_training.CHECKPOINT_PATH, residual_training.EXPECTED_HASHES
    )
    old_by_key = {
        (str(state["game_id"]), int(state["turn_index"])): state
        for state in context["old"]["state_diagnostics"]
    }
    states_by_partition: dict[str, list[dict]] = {}
    accounting_by_partition: dict[str, dict] = {}
    for partition, samples in context["partitions"].items():
        q_values, accounting = base_diagnosis.score_partition(model, samples)
        states_by_partition[partition] = [
            old_corrective_diagnosis.add_old_comparison(
                enrich_state(
                    sample,
                    base_diagnosis.diagnose_state(sample, partition, values),
                ),
                old_by_key[(str(sample["game_id"]), int(sample["turn_index"]))],
            )
            for sample, values in zip(samples, q_values)
        ]
        accounting_by_partition[partition] = accounting
    all_states = (
        states_by_partition["pipeline_train"]
        + states_by_partition["pipeline_development"]
    )
    total_actions = sum(state["legal_action_count"] for state in all_states)
    duplicate_vectors = sum(
        item["source_duplicate_action_vector_count"]
        for item in accounting_by_partition.values()
    )
    metrics = reproduce_stage_6_11_metrics(
        model, context["pairs"], context["report"]
    )
    corrective = corrective_pair_diagnostics(
        all_states, context["corrective_mappings"]
    )
    aggregates = {
        "pipeline_train": base_diagnosis.aggregate_states(
            states_by_partition["pipeline_train"]
        ),
        "pipeline_development": base_diagnosis.aggregate_states(
            states_by_partition["pipeline_development"]
        ),
        "overall": base_diagnosis.aggregate_states(all_states),
    }
    old_aggregates = context["old"]["aggregates"]
    comparison = {
        partition: {
            "stage_6_7": old_aggregates[partition],
            "stage_6_12": aggregates[partition],
            "teacher_top1_count_delta": aggregates[partition]["teacher_top1_count"]
            - old_aggregates[partition]["teacher_top1_count"],
            "other_action_top1_count_delta": aggregates[partition][
                "other_action_top1_count"
            ]
            - old_aggregates[partition]["other_action_top1_count"],
            "strictly_outranking_state_count_delta": aggregates[partition][
                "unpaired_action_strictly_outranks_teacher_state_count"
            ]
            - old_aggregates[partition][
                "unpaired_action_strictly_outranks_teacher_state_count"
            ],
            "strictly_outranking_action_count_delta": aggregates[partition][
                "unpaired_actions_strictly_above_teacher_count"
            ]
            - old_aggregates[partition][
                "unpaired_actions_strictly_above_teacher_count"
            ],
        }
        for partition in ("pipeline_train", "pipeline_development", "overall")
    }
    forbidden = {
        "rollout_runs": 0,
        "training_runs": 0,
        "fine_tuning_runs": 0,
        "hyperparameter_searches": 0,
        "threshold_searches": 0,
        "checkpoint_selections": 0,
        "checkpoint_modifications": 0,
        "locked_test_loads": 0,
        "website_dataset_loads": 0,
        "arena_games": 0,
        "website_shadow_games": 0,
        "website_games": 0,
        "model_controlled_website_actions": 0,
        "checkpoint_promotions": 0,
        "capability_claims": 0,
    }
    source_summaries = {
        source: {
            "pair_count": sum(item["pair_source"] == source for item in corrective),
            "teacher_outranks_rejected_count": sum(
                item["pair_source"] == source
                and item["teacher_outranks_frozen_rejected_action"]
                for item in corrective
            ),
            "teacher_is_first_max_full_set_top1_count": sum(
                item["pair_source"] == source
                and item["teacher_is_first_max_full_set_top1"]
                for item in corrective
            ),
            "rejected_action_remains_new_top1_count": sum(
                item["pair_source"] == source
                and item["frozen_rejected_action_remains_new_top1"]
                for item in corrective
            ),
        }
        for source in (
            "stage_6_4_train_confirmation",
            "stage_6_9_residual_train_confirmation",
        )
    }
    result = {
        "schema_version": SCHEMA_VERSION,
        "frozen_inputs": {
            "paths": {name: str(path) for name, path in frozen_paths().items()},
            "sha256": context["frozen_hashes"],
        },
        "checkpoint_schema_version": checkpoint["schema_version"],
        "checkpoint_status": "pipeline_only_unpromoted_not_capability_evidence",
        "stage_6_11_validation": {
            "training_run_count": 1,
            "development_training_use_count": 0,
            "checkpoint_reload_verified": True,
            "metrics_and_prediction_digests_reproduced": True,
        },
        "partition_mapping": {
            "pipeline_train_state_count": len(
                context["partitions"]["pipeline_train"]
            ),
            "pipeline_development_state_count": len(
                context["partitions"]["pipeline_development"]
            ),
            "overlap_state_count": 0,
            "unknown_state_count": 0,
            "development_used_for_objective_design": False,
        },
        "scoring_accounting": {
            "diagnostic_run_count": 1,
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
            "source_duplicate_action_vector_count": duplicate_vectors,
            "state_action_order_sha256": action_order_digest(all_states),
            "by_partition": accounting_by_partition,
        },
        "stage_6_11_metric_reproduction": metrics,
        "state_diagnostics": all_states,
        "aggregates": aggregates,
        "stage_6_7_comparison": comparison,
        "corrective_pair_diagnostics": corrective,
        "corrective_pair_summary": {
            "pair_count": len(corrective),
            "by_source": source_summaries,
            "teacher_outranks_rejected_count": sum(
                item["teacher_outranks_frozen_rejected_action"]
                for item in corrective
            ),
            "teacher_is_first_max_full_set_top1_count": sum(
                item["teacher_is_first_max_full_set_top1"] for item in corrective
            ),
            "rejected_action_remains_new_top1_count": sum(
                item["frozen_rejected_action_remains_new_top1"]
                for item in corrective
            ),
        },
        "interpretation_scope": {
            "static_ranking_diagnostic_only": True,
            "development_used_for_objective_design": False,
            "causal_claim_allowed": False,
            "capability_claim_allowed": False,
            "checkpoint_promotion_allowed": False,
        },
        "forbidden_operation_counts": forbidden,
        "status": "completed",
    }
    if (
        len(all_states) != 22
        or total_actions != 934
        or duplicate_vectors != 8
        or len(corrective) != 10
        or source_summaries["stage_6_4_train_confirmation"]["pair_count"] != 6
        or source_summaries["stage_6_9_residual_train_confirmation"]["pair_count"]
        != 4
        or metrics["evaluation_accounting"]["pair_evaluation_count"] != 60
        or metrics["evaluation_accounting"]["action_value_evaluation_count"] != 120
        or any(forbidden.values())
    ):
        raise RuntimeError("residual corrective diagnosis accounting gate failed")
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
    context = validate_context()
    result = {
        "status": "ready",
        "frozen_input_hashes": context["frozen_hashes"],
        "teacher_state_count": len(context["samples"]),
        "recorded_legal_action_count": sum(
            len(sample["legal_actions"]) for sample in context["samples"]
        ),
        "stage_6_4_corrective_pair_count": sum(
            item["pair_source"] == "stage_6_4_train_confirmation"
            for item in context["corrective_mappings"].values()
        ),
        "stage_6_9_residual_pair_count": sum(
            item["pair_source"] == "stage_6_9_residual_train_confirmation"
            for item in context["corrective_mappings"].values()
        ),
        "pipeline_train_state_count": len(context["partitions"]["pipeline_train"]),
        "pipeline_development_state_count": len(
            context["partitions"]["pipeline_development"]
        ),
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return result


def run() -> dict:
    ensure_unused_output()
    context = validate_context()
    result = compute_result(context)
    if verify_frozen_hashes() != context["frozen_hashes"]:
        raise RuntimeError("a frozen input changed during residual corrective diagnosis")
    write_output_once(OUTPUT_PATH, result)
    print(
        json.dumps(
            {
                "status": result["status"],
                "output": str(OUTPUT_PATH),
                "scoring_accounting": result["scoring_accounting"],
                "aggregates": result["aggregates"],
                "corrective_pair_summary": result["corrective_pair_summary"],
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
        raise RuntimeError("independent residual corrective diagnosis mismatch")
    if verify_frozen_hashes() != context["frozen_hashes"]:
        raise RuntimeError("a frozen input changed during diagnosis audit")
    result = {
        "status": "passed",
        "state_count": len(saved["state_diagnostics"]),
        "legal_action_count": saved["scoring_accounting"]["legal_action_score_count"],
        "action_order_digest_exact": True,
        "rankings_action_hashes_and_aggregates_exact": True,
        "stage_6_11_metrics_and_prediction_digests_exact": True,
        "stage_6_4_and_stage_6_9_mappings_exact": True,
        "forbidden_operation_count": sum(saved["forbidden_operation_counts"].values()),
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
