from __future__ import annotations

from collections import Counter
import argparse
import json
from pathlib import Path

import website_teacher_preference as preference
import website_teacher_preference_corrective_dataset as dataset_v1
import website_teacher_preference_corrective_dataset_v3 as dataset_v3
import website_teacher_preference_corrective_diagnosis as old_corrective_diagnosis
import website_teacher_preference_diagnosis as base_diagnosis
import website_teacher_preference_remaining_corrective_training as training
import website_teacher_preference_residual_corrective_diagnosis as diagnosis_pattern


SCHEMA_VERSION = (
    "website_teacher_preference_remaining_corrective_failure_diagnosis_v1"
)
OUTPUT_PATH = Path(
    "website_teacher_preference_remaining_corrective_failure_diagnosis_v1.json"
)
TRAINING_REPORT_PATH = training.REPORT_PATH
TRAINING_CHECKPOINT_PATH = training.CHECKPOINT_PATH
TRAINING_IMPLEMENTATION_PATH = Path(
    "website_teacher_preference_remaining_corrective_training.py"
)
STAGE_6_12_IMPLEMENTATION_PATH = Path(
    "website_teacher_preference_residual_corrective_diagnosis.py"
)
STAGE_6_12_EVIDENCE_PATH = diagnosis_pattern.OUTPUT_PATH
EXPECTED_HASHES = {
    "stage_6_16_training_report": (
        "cac3ecb0542a7f9aaac2654f73f4e3650422be7eb5990bf4c403f3f082145156"
    ),
    "stage_6_16_checkpoint": (
        "8407f897e36b45affc628fbd2fe68dc4c76a5085fad095511c8045bc73ec5aad"
    ),
    "stage_6_16_implementation": (
        "8f3c74b272228cb0423aa192187d64028c4b7bce2f23dd74d12d811c55f76ded"
    ),
    "stage_6_12_implementation": (
        "75af0c847a49484059c103fe12f8db1f4fb447cb04c2161ed1ffe913dea8e008"
    ),
    "stage_6_12_evidence": (
        "e8e12f4fd259bc0c2689100d08bdfb3b71662e29c8af0f1e1013fbc6e9573e9f"
    ),
}


def frozen_paths() -> dict[str, Path]:
    return {
        **training.frozen_paths(),
        "stage_6_16_training_report": TRAINING_REPORT_PATH,
        "stage_6_16_checkpoint": TRAINING_CHECKPOINT_PATH,
        "stage_6_16_implementation": TRAINING_IMPLEMENTATION_PATH,
        "stage_6_12_implementation": STAGE_6_12_IMPLEMENTATION_PATH,
        "stage_6_12_evidence": STAGE_6_12_EVIDENCE_PATH,
    }


def verify_frozen_hashes() -> dict[str, str]:
    recursive = training.verify_frozen_hashes()
    specific_paths = {
        "stage_6_16_training_report": TRAINING_REPORT_PATH,
        "stage_6_16_checkpoint": TRAINING_CHECKPOINT_PATH,
        "stage_6_16_implementation": TRAINING_IMPLEMENTATION_PATH,
        "stage_6_12_implementation": STAGE_6_12_IMPLEMENTATION_PATH,
        "stage_6_12_evidence": STAGE_6_12_EVIDENCE_PATH,
    }
    specific = {
        name: dataset_v1.sha256(path) for name, path in specific_paths.items()
    }
    for name, expected in EXPECTED_HASHES.items():
        if specific.get(name) != expected:
            raise RuntimeError(f"{name} SHA-256 mismatch")
    return {**recursive, **specific}


def load_json(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError(f"{path} must contain a JSON object")
    return payload


def ensure_unused_output(path: Path = OUTPUT_PATH) -> None:
    temporary = path.with_name(f"{path.name}.tmp")
    if path.exists() or temporary.exists():
        raise RuntimeError("remaining corrective diagnostic output already exists")


def validate_training_report(report: dict, training_hashes: dict[str, str]) -> None:
    accounting = report.get("training_accounting") or {}
    validation = report.get("dataset_validation") or {}
    metrics = report.get("final_metrics") or {}
    train_metrics = metrics.get("pipeline_train") or {}
    development_metrics = metrics.get("pipeline_development") or {}
    expected_pair_counts = {
        "aggregate": 30,
        "base_pairs": 18,
        "stage_6_4_corrective_pairs": 6,
        "stage_6_9_residual_pairs": 4,
        "stage_6_14e_remaining_pairs": 2,
    }
    if (
        report.get("schema_version") != training.SCHEMA_VERSION
        or report.get("status") != "completed"
        or report.get("frozen_inputs", {}).get("sha256") != training_hashes
        or report.get("recipe") != training.fixed_recipe()
        or report.get("checkpoint_sha256")
        != EXPECTED_HASHES["stage_6_16_checkpoint"]
        or report.get("checkpoint_schema_version")
        != training.CHECKPOINT_SCHEMA_VERSION
        or report.get("checkpoint_save_count") != 1
        or report.get("checkpoint_reload_verified") is not True
        or report.get("checkpoint_promotion_allowed") is not False
        or report.get("capability_claim_allowed") is not False
        or report.get("threshold_passed") is not True
        or validation
        != {
            "total_pair_count": 34,
            "pipeline_train_state_count": 18,
            "pipeline_train_pair_count": 30,
            "pipeline_development_state_count": 4,
            "pipeline_development_pair_count": 4,
            "exact_base_sample_count": 22,
            "exact_preserved_v2_pair_count": 32,
            "exact_stage_6_4_corrective_pair_count": 6,
            "exact_stage_6_9_residual_pair_count": 4,
            "exact_stage_6_14e_remaining_pair_count": 2,
            "excluded_pair_leakage_count": 0,
        }
        or accounting.get("training_run_count") != 1
        or accounting.get("optimizer_step_count") != 60
        or accounting.get("train_state_epoch_use_count") != 360
        or accounting.get("train_pair_epoch_use_count") != 600
        or accounting.get("development_training_use_count") != 0
        or accounting.get("extra_training_target_count") != 0
        or accounting.get("fine_tuning_run_count") != 0
        or accounting.get("nonfinite_training_loss_count") != 0
        or report.get("forbidden_operation_counts")
        != training.forbidden_operation_counts()
        or set(train_metrics) != set(expected_pair_counts)
        or any(
            train_metrics[name].get("pair_count") != count
            for name, count in expected_pair_counts.items()
        )
        or set(development_metrics) != {"aggregate"}
        or development_metrics["aggregate"].get("pair_count") != 4
    ):
        raise RuntimeError("Stage 6.16 report validation mismatch")


def build_corrective_mappings(
    samples: list[dict],
    pairs: list[dict],
    old: dict,
    remaining_confirmation: dict,
) -> dict[str, dict]:
    sample_by_key = {
        (str(sample["game_id"]), int(sample["turn_index"])): sample
        for sample in samples
    }
    old_by_pair_id = {
        item["pair_id"]: item for item in old["corrective_pair_diagnostics"]
    }
    supported, _inconclusive = dataset_v3.validate_and_select_confirmation(
        remaining_confirmation
    )
    remaining_by_key = {
        (str(case["game_id"]), int(case["turn_index"])): case
        for case in supported
    }
    mappings: dict[str, dict] = {}
    for pair in pairs:
        if pair["pair_source"] == "frozen_teacher_v6":
            continue
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
        if pair["pair_source"] in {
            "stage_6_4_train_confirmation",
            "stage_6_9_residual_train_confirmation",
        }:
            previous = old_by_pair_id.get(pair["pair_id"])
            if (
                previous is None
                or int(previous["preferred_index"]) != preferred_index
                or int(previous["rejected_index"]) != rejected_index
                or previous["preferred_action_sha256"]
                != pair["preferred_action_sha256"]
                or previous["rejected_action_sha256"]
                != pair["rejected_action_sha256"]
            ):
                raise RuntimeError(f"frozen corrective mapping mismatch {key}")
        elif pair["pair_source"] == "stage_6_14e_remaining_train_confirmation":
            case = remaining_by_key.get(key)
            candidates = case.get("candidate_results") if case else None
            if (
                not candidates
                or [item.get("role") for item in candidates]
                != ["teacher", "residual"]
                or int(candidates[0]["action_index"]) != preferred_index
                or int(candidates[1]["action_index"]) != rejected_index
                or candidates[0]["action_sha256"]
                != pair["preferred_action_sha256"]
                or candidates[1]["action_sha256"]
                != pair["rejected_action_sha256"]
                or candidates[0]["physical_cards_website"]
                != pair["preferred_physical_cards_website"]
                or candidates[1]["physical_cards_website"]
                != pair["rejected_physical_cards_website"]
            ):
                raise RuntimeError(f"Stage 6.14E corrective mapping mismatch {key}")
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
    source_counts = Counter(item["pair_source"] for item in mappings.values())
    if len(mappings) != 12 or source_counts != Counter(
        {
            "stage_6_4_train_confirmation": 6,
            "stage_6_9_residual_train_confirmation": 4,
            "stage_6_14e_remaining_train_confirmation": 2,
        }
    ):
        raise RuntimeError("corrective mapping count mismatch")
    return mappings


def validate_context() -> dict:
    frozen_hashes = verify_frozen_hashes()
    training_hashes = training.verify_frozen_hashes()
    pairs, validated_hashes, dataset = training.validate_inputs()
    if validated_hashes != training_hashes:
        raise RuntimeError("Stage 6.16 recursive frozen hashes changed")
    report = load_json(TRAINING_REPORT_PATH)
    validate_training_report(report, training_hashes)
    old = load_json(STAGE_6_12_EVIDENCE_PATH)
    old_scoring = old.get("scoring_accounting") or {}
    old_replay = (old.get("stage_6_11_metric_reproduction") or {}).get(
        "evaluation_accounting"
    ) or {}
    if (
        old.get("schema_version") != diagnosis_pattern.SCHEMA_VERSION
        or old.get("status") != "completed"
        or old_scoring.get("unique_teacher_state_count") != 22
        or old_scoring.get("recorded_legal_action_count") != 934
        or old_scoring.get("legal_action_score_count") != 934
        or old_scoring.get("source_duplicate_action_vector_count") != 8
        or old_replay.get("pair_evaluation_count") != 60
        or old_replay.get("action_value_evaluation_count") != 120
        or set(old.get("aggregates") or {})
        != {"pipeline_train", "pipeline_development", "overall"}
        or any(
            int(value) != 0
            for value in (old.get("forbidden_operation_counts") or {}).values()
        )
    ):
        raise RuntimeError("Stage 6.12 diagnosis validation mismatch")
    samples, _summary, teacher_hash = preference.load_teacher_dataset(
        dataset_v3.TEACHER_PATH
    )
    if (
        teacher_hash != training_hashes["teacher_dataset"]
        or dataset.get("frozen_base_samples") != samples
        or len(pairs) != 34
    ):
        raise RuntimeError("teacher samples or v3 pairs changed")
    split = load_json(dataset_v3.SPLIT_PATH)
    partitions = base_diagnosis.map_partitions(samples, split)
    remaining_confirmation = load_json(dataset_v3.CONFIRMATION_PATH)
    mappings = build_corrective_mappings(
        samples, pairs, old, remaining_confirmation
    )
    return {
        "frozen_hashes": frozen_hashes,
        "training_hashes": training_hashes,
        "report": report,
        "old": old,
        "samples": samples,
        "pairs": pairs,
        "partitions": partitions,
        "corrective_mappings": mappings,
    }


def reproduce_stage_6_16_metrics(
    model: object, pairs: list[dict], report: dict
) -> dict:
    actual = training.evaluate_model(model, pairs)
    if actual != report.get("final_metrics"):
        raise RuntimeError("Stage 6.16 metrics or prediction digests did not reproduce")
    return {
        "actual": actual,
        "frozen": report["final_metrics"],
        "exact_match": True,
        "evaluation_accounting": {
            "pair_metric_section_count": 6,
            "pair_evaluation_count": 64,
            "action_value_evaluation_count": 128,
            "model_forward_batch_count": 12,
            "included_in_full_legal_set_score_count": False,
            "purpose": "exact_frozen_stage_6_16_batch_shape_reproduction",
        },
    }


def forbidden_operation_counts() -> dict[str, int]:
    return {
        "rollout_runs": 0,
        "label_or_pair_additions": 0,
        "objective_definitions_or_changes": 0,
        "training_runs": 0,
        "fine_tuning_runs": 0,
        "hyperparameter_searches": 0,
        "threshold_searches": 0,
        "checkpoint_selections": 0,
        "checkpoint_modifications": 0,
        "locked_test_loads": 0,
        "complete_website_dataset_loads": 0,
        "arena_games": 0,
        "website_shadow_games": 0,
        "website_games": 0,
        "model_controlled_website_actions": 0,
        "checkpoint_promotions": 0,
        "capability_claims": 0,
    }


def compute_result(context: dict) -> dict:
    model, checkpoint = training.load_checkpoint(
        TRAINING_CHECKPOINT_PATH, context["training_hashes"]
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
                diagnosis_pattern.enrich_state(
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
    metrics = reproduce_stage_6_16_metrics(
        model, context["pairs"], context["report"]
    )
    corrective = diagnosis_pattern.corrective_pair_diagnostics(
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
            "stage_6_12": old_aggregates[partition],
            "stage_6_17": aggregates[partition],
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
    sources = (
        "stage_6_4_train_confirmation",
        "stage_6_9_residual_train_confirmation",
        "stage_6_14e_remaining_train_confirmation",
    )
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
        for source in sources
    }
    forbidden = forbidden_operation_counts()
    result = {
        "schema_version": SCHEMA_VERSION,
        "frozen_inputs": {
            "paths": {name: str(path) for name, path in frozen_paths().items()},
            "sha256": context["frozen_hashes"],
        },
        "checkpoint_schema_version": checkpoint["schema_version"],
        "checkpoint_status": "pipeline_only_unpromoted_not_capability_evidence",
        "stage_6_16_validation": {
            "training_run_count": 1,
            "optimizer_step_count": 60,
            "train_state_epoch_use_count": 360,
            "train_pair_epoch_use_count": 600,
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
            "state_action_order_sha256": diagnosis_pattern.action_order_digest(
                all_states
            ),
            "by_partition": accounting_by_partition,
        },
        "stage_6_16_metric_reproduction": metrics,
        "state_diagnostics": all_states,
        "aggregates": aggregates,
        "stage_6_12_comparison": comparison,
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
    train_actions = accounting_by_partition["pipeline_train"][
        "legal_action_score_count"
    ]
    development_actions = accounting_by_partition["pipeline_development"][
        "legal_action_score_count"
    ]
    if (
        len(all_states) != 22
        or len(states_by_partition["pipeline_train"]) != 18
        or len(states_by_partition["pipeline_development"]) != 4
        or total_actions != 934
        or train_actions != 889
        or development_actions != 45
        or duplicate_vectors != 8
        or len(corrective) != 12
        or source_summaries["stage_6_4_train_confirmation"]["pair_count"] != 6
        or source_summaries["stage_6_9_residual_train_confirmation"][
            "pair_count"
        ]
        != 4
        or source_summaries["stage_6_14e_remaining_train_confirmation"][
            "pair_count"
        ]
        != 2
        or metrics["evaluation_accounting"]["pair_evaluation_count"] != 64
        or metrics["evaluation_accounting"]["action_value_evaluation_count"]
        != 128
        or any(forbidden.values())
    ):
        raise RuntimeError("remaining corrective diagnosis accounting gate failed")
    return result


def preflight() -> dict:
    ensure_unused_output()
    context = validate_context()
    result = {
        "status": "ready",
        "frozen_input_hash_count": len(context["frozen_hashes"]),
        "teacher_state_count": len(context["samples"]),
        "recorded_legal_action_count": sum(
            len(sample["legal_actions"]) for sample in context["samples"]
        ),
        "pipeline_train_state_count": len(context["partitions"]["pipeline_train"]),
        "pipeline_development_state_count": len(
            context["partitions"]["pipeline_development"]
        ),
        "corrective_pair_source_counts": dict(
            Counter(
                item["pair_source"]
                for item in context["corrective_mappings"].values()
            )
        ),
        "replay_pair_evaluation_count": 64,
        "replay_action_value_evaluation_count": 128,
        "outputs_written": False,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return result


def run() -> dict:
    ensure_unused_output()
    context = validate_context()
    result = compute_result(context)
    if verify_frozen_hashes() != context["frozen_hashes"]:
        raise RuntimeError("a frozen input changed during remaining diagnosis")
    diagnosis_pattern.write_output_once(OUTPUT_PATH, result)
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
        raise RuntimeError("independent remaining corrective diagnosis mismatch")
    if verify_frozen_hashes() != context["frozen_hashes"]:
        raise RuntimeError("a frozen input changed during diagnosis audit")
    result = {
        "status": "passed",
        "state_count": len(saved["state_diagnostics"]),
        "legal_action_count": saved["scoring_accounting"][
            "legal_action_score_count"
        ],
        "train_action_count": saved["scoring_accounting"]["by_partition"][
            "pipeline_train"
        ]["legal_action_score_count"],
        "development_action_count": saved["scoring_accounting"]["by_partition"][
            "pipeline_development"
        ]["legal_action_score_count"],
        "replay_pair_evaluation_count": saved["stage_6_16_metric_reproduction"][
            "evaluation_accounting"
        ]["pair_evaluation_count"],
        "replay_action_value_evaluation_count": saved[
            "stage_6_16_metric_reproduction"
        ]["evaluation_accounting"]["action_value_evaluation_count"],
        "action_order_digest_exact": True,
        "rankings_action_hashes_and_aggregates_exact": True,
        "stage_6_16_metrics_and_prediction_digests_exact": True,
        "stage_6_4_6_9_6_14e_mappings_exact": True,
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
