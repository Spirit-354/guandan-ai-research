from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path

import website_teacher_preference as preference
import website_teacher_preference_corrective_dataset as corrective_dataset
import website_teacher_preference_corrective_training as corrective_training
import website_teacher_preference_diagnosis as old_diagnosis


SCHEMA_VERSION = "website_teacher_preference_corrective_failure_diagnosis_v1"
OUTPUT_PATH = Path("website_teacher_preference_corrective_failure_diagnosis_v1.json")
OLD_DIAGNOSIS_PATH = Path("website_teacher_preference_failure_diagnosis_v1.json")
EXPECTED_HASHES = {
    "corrective_checkpoint": "8cb368c8c0ae3f8c41c577e055ddd4796cbaae8163720cc630a435aa25bc1a49",
    "corrective_training_report": "baa97ccf71c237895a92f4cb8b36b9559cf3cabe45b4901b7481d9f50f4c0830",
    "corrective_dataset": "fad7ae18fea8b02cbc88ad4a8a7f8ecee298abe436ef589f5c88d66e42a32707",
    "corrective_manifest": "0a5dc4f60091338b65f86f83ad30ae55dc18c058ee8b07535a314510ad96ef0a",
    "teacher_dataset": "a74416e6facb28a1bc64563eba90cb33d460dc9e59cc2109518da142465e15f8",
    "split_manifest": "5a15e514dc9bc51d77d300837151d9f1a49250f42885cc7940725bcbe4d35107",
    "stage_6_4_confirmation": "8e17377b5a1523d9f0a47af7218d687e062a3ade671c57f387eb4c1a0888cfae",
    "old_diagnosis": "da08516c39986a01349533e160ba0e97a566d7fad6e42b0b7b3ce41df835b0b2",
    "old_rejected_checkpoint": "c54801a9db05100c2fe5a9bf610a64fc7c94dc2cd947dfaab115ff827bd90919",
    "stage_6_1_arena": "aa45da9de202194102fe8d11e612ad3eb4b51177fd910b9a7948836afd2a1fe6",
}


def frozen_paths() -> dict[str, Path]:
    return {
        "corrective_checkpoint": corrective_training.CHECKPOINT_PATH,
        "corrective_training_report": corrective_training.REPORT_PATH,
        "corrective_dataset": corrective_training.DATASET_PATH,
        "corrective_manifest": corrective_training.MANIFEST_PATH,
        "teacher_dataset": corrective_training.TEACHER_PATH,
        "split_manifest": corrective_training.SPLIT_PATH,
        "stage_6_4_confirmation": corrective_training.CONFIRMATION_PATH,
        "old_diagnosis": OLD_DIAGNOSIS_PATH,
        "old_rejected_checkpoint": corrective_training.OLD_CHECKPOINT_PATH,
        "stage_6_1_arena": corrective_training.ARENA_PATH,
    }


def verify_frozen_hashes() -> dict[str, str]:
    actual = {
        name: corrective_training.sha256(path) for name, path in frozen_paths().items()
    }
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
        raise RuntimeError("corrective diagnostic output already exists")


def validate_context() -> dict:
    frozen_hashes = verify_frozen_hashes()
    pairs, stage_6_6_hashes, dataset = corrective_training.validate_inputs()
    report = load_json(corrective_training.REPORT_PATH)
    old = load_json(OLD_DIAGNOSIS_PATH)
    required_accounting = {
        "training_run_count": 1,
        "optimizer_step_count": 60,
        "development_training_use_count": 0,
        "extra_training_target_count": 0,
        "nonfinite_training_loss_count": 0,
    }
    accounting = report.get("training_accounting") or {}
    if (
        report.get("schema_version") != corrective_training.SCHEMA_VERSION
        or report.get("status") != "completed"
        or report.get("frozen_inputs", {}).get("sha256") != stage_6_6_hashes
        or report.get("checkpoint_sha256") != EXPECTED_HASHES["corrective_checkpoint"]
        or report.get("checkpoint_schema_version")
        != corrective_training.CHECKPOINT_SCHEMA_VERSION
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
        raise RuntimeError("Stage 6.6 report validation mismatch")
    old_scoring = old.get("scoring_accounting") or {}
    old_aggregates = old.get("aggregates") or {}
    if (
        old.get("schema_version") != old_diagnosis.SCHEMA_VERSION
        or old.get("status") != "completed"
        or old.get("checkpoint_screen_status")
        != "rejected_from_100_200_game_screen"
        or old_scoring.get("unique_teacher_state_count") != 22
        or old_scoring.get("recorded_legal_action_count") != 934
        or old_scoring.get("legal_action_score_count") != 934
        or old_scoring.get("source_duplicate_action_vector_count") != 8
        or set(old_aggregates) != {
            "pipeline_train",
            "pipeline_development",
            "overall",
        }
        or any(
            int(value) != 0
            for value in (old.get("forbidden_operation_counts") or {}).values()
        )
    ):
        raise RuntimeError("old full-legal-set diagnosis validation mismatch")
    samples, _summary, teacher_hash = preference.load_teacher_dataset(
        corrective_training.TEACHER_PATH
    )
    if teacher_hash != EXPECTED_HASHES["teacher_dataset"]:
        raise RuntimeError("teacher dataset loader hash mismatch")
    split = load_json(corrective_training.SPLIT_PATH)
    partitions = old_diagnosis.map_partitions(samples, split)
    confirmation = load_json(corrective_training.CONFIRMATION_PATH)
    corrective_mappings = build_corrective_mappings(
        samples, pairs, confirmation, old["state_diagnostics"]
    )
    return {
        "frozen_hashes": frozen_hashes,
        "stage_6_6_hashes": stage_6_6_hashes,
        "pairs": pairs,
        "dataset": dataset,
        "report": report,
        "old": old,
        "samples": samples,
        "partitions": partitions,
        "corrective_mappings": corrective_mappings,
    }


def build_corrective_mappings(
    samples: list[dict],
    pairs: list[dict],
    confirmation: dict,
    old_states: list[dict],
) -> dict[tuple[str, int], dict]:
    sample_by_key = {
        (str(sample["game_id"]), int(sample["turn_index"])): sample
        for sample in samples
    }
    old_by_key = {
        (str(state["game_id"]), int(state["turn_index"])): state
        for state in old_states
    }
    corrective_pairs = [
        pair
        for pair in pairs
        if pair["pair_source"] == "stage_6_4_train_confirmation"
    ]
    pair_by_key = {
        (str(pair["game_id"]), int(pair["turn_index"])): pair
        for pair in corrective_pairs
    }
    supported, _inconclusive = corrective_dataset.select_confirmation_cases(confirmation)
    if len(supported) != 6 or len(pair_by_key) != 6:
        raise RuntimeError("corrective mapping count mismatch")
    mappings: dict[tuple[str, int], dict] = {}
    for case in supported:
        key = (str(case["game_id"]), int(case["turn_index"]))
        sample = sample_by_key.get(key)
        pair = pair_by_key.get(key)
        old_state = old_by_key.get(key)
        candidates = {item["role"]: item for item in case["candidate_results"]}
        teacher_index = int(candidates["teacher"]["action_index"])
        rejected_index = int(candidates["top1"]["action_index"])
        if sample is None or pair is None or old_state is None:
            raise RuntimeError(f"missing corrective mapping source {key}")
        if (
            sample["legal_actions"][teacher_index] != pair["preferred_action"]
            or sample["legal_actions"][rejected_index] != pair["rejected_action"]
            or corrective_dataset.action_sha256(sample["legal_actions"][teacher_index])
            != pair["preferred_action_sha256"]
            or corrective_dataset.action_sha256(sample["legal_actions"][rejected_index])
            != pair["rejected_action_sha256"]
            or candidates["teacher"]["action_sha256"]
            != pair["preferred_action_sha256"]
            or candidates["top1"]["action_sha256"]
            != pair["rejected_action_sha256"]
            or candidates["teacher"]["physical_cards_website"]
            != pair["preferred_physical_cards_website"]
            or candidates["top1"]["physical_cards_website"]
            != pair["rejected_physical_cards_website"]
            or int(old_state["teacher_action_index"]) != teacher_index
            or int(old_state["top1_index"]) != rejected_index
        ):
            raise RuntimeError(f"corrective mapping content mismatch {key}")
        mappings[key] = {
            "pair_id": pair["pair_id"],
            "preferred_index": teacher_index,
            "rejected_index": rejected_index,
            "preferred_action_sha256": pair["preferred_action_sha256"],
            "rejected_action_sha256": pair["rejected_action_sha256"],
        }
        if pair_action_indices(pair, sample, {key: mappings[key]}) != (
            teacher_index,
            rejected_index,
        ):
            raise RuntimeError(f"corrective index validation mismatch {key}")
    if set(mappings) != set(pair_by_key):
        raise RuntimeError("corrective mapping key mismatch")
    return mappings


def pair_action_indices(
    pair: dict, sample: dict, corrective_mappings: dict[tuple[str, int], dict]
) -> tuple[int, int]:
    key = (str(pair["game_id"]), int(pair["turn_index"]))
    preferred_matches = [
        index
        for index, action in enumerate(sample["legal_actions"])
        if action == pair["preferred_action"]
    ]
    if len(preferred_matches) != 1:
        raise RuntimeError(f"preferred action mapping is ambiguous {pair['pair_id']}")
    if pair["pair_source"] == "stage_6_4_train_confirmation":
        mapping = corrective_mappings.get(key)
        if mapping is None or mapping["pair_id"] != pair["pair_id"]:
            raise RuntimeError(f"missing confirmed corrective mapping {pair['pair_id']}")
        indices = preferred_matches[0], int(mapping["rejected_index"])
    else:
        rejected_matches = [
            index
            for index, action in enumerate(sample["legal_actions"])
            if action == pair["rejected_action"]
        ]
        if len(rejected_matches) != 1:
            raise RuntimeError(f"rejected action mapping is ambiguous {pair['pair_id']}")
        indices = preferred_matches[0], rejected_matches[0]
    if (
        sample["legal_actions"][indices[0]] != pair["preferred_action"]
        or sample["legal_actions"][indices[1]] != pair["rejected_action"]
    ):
        raise RuntimeError(f"pair action index content mismatch {pair['pair_id']}")
    return indices


def reproduce_stage_6_6_metrics(
    model: object, pairs: list[dict], report: dict
) -> dict:
    actual = corrective_training.evaluate_model(model, pairs)
    if actual != report.get("final_metrics"):
        raise RuntimeError("Stage 6.6 metrics or prediction digests did not reproduce")
    return {
        "actual": actual,
        "frozen": report["final_metrics"],
        "exact_match": True,
        "evaluation_accounting": {
            "pair_metric_section_count": 4,
            "pair_evaluation_count": 52,
            "action_value_evaluation_count": 104,
            "model_forward_batch_count": 8,
            "included_in_full_legal_set_score_count": False,
            "purpose": "exact_frozen_stage_6_6_batch_shape_reproduction",
        },
    }


def action_order_digest(states: list[dict]) -> str:
    digest = hashlib.sha256()
    for state in states:
        digest.update(f"{state['game_id']}:{state['turn_index']}\n".encode("utf-8"))
        digest.update(bytes.fromhex(state["legal_action_order_sha256"]))
    return digest.hexdigest()


def add_old_comparison(state: dict, old_state: dict) -> dict:
    identity_keys = (
        "game_id",
        "turn_index",
        "pipeline_partition",
        "legal_action_count",
        "legal_action_order_sha256",
        "teacher_action_index",
        "behavior_action_index",
    )
    if any(state[key] != old_state[key] for key in identity_keys):
        raise RuntimeError("new/old state identity mismatch")
    result = dict(state)
    result["old_checkpoint_comparison"] = {
        "old_teacher_rank": int(old_state["teacher_rank"]),
        "new_minus_old_teacher_rank": int(state["teacher_rank"])
        - int(old_state["teacher_rank"]),
        "old_top1_index": int(old_state["top1_index"]),
        "old_top1_source": old_state["top1_source"],
        "old_top1_index_remains_new_top1": int(old_state["top1_index"])
        == int(state["top1_index"]),
        "old_actions_strictly_above_teacher_count": int(
            old_state["actions_strictly_above_teacher_count"]
        ),
        "new_minus_old_actions_strictly_above_teacher_count": int(
            state["actions_strictly_above_teacher_count"]
        )
        - int(old_state["actions_strictly_above_teacher_count"]),
    }
    return result


def corrective_pair_diagnostics(
    states: list[dict], mappings: dict[tuple[str, int], dict]
) -> list[dict]:
    state_by_key = {
        (str(state["game_id"]), int(state["turn_index"])): state for state in states
    }
    results: list[dict] = []
    for key, mapping in mappings.items():
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
                "pair_id": mapping["pair_id"],
                "preferred_index": preferred_index,
                "rejected_index": rejected_index,
                "preferred_rank": 1 + sum(value > preferred_q for value in q_values),
                "rejected_rank": 1 + sum(value > rejected_q for value in q_values),
                "preferred_q": preferred_q,
                "rejected_q": rejected_q,
                "preferred_minus_rejected_margin": preferred_q - rejected_q,
                "teacher_outranks_frozen_rejected_top1": preferred_q > rejected_q,
                "teacher_is_first_max_full_set_top1": int(state["top1_index"])
                == preferred_index,
                "frozen_rejected_top1_remains_new_top1": int(state["top1_index"])
                == rejected_index,
                "new_full_set_top1_index": int(state["top1_index"]),
                "new_full_set_top1_source": state["top1_source"],
            }
        )
    return results


def compute_result(context: dict) -> dict:
    model, checkpoint = corrective_training.load_checkpoint(
        corrective_training.CHECKPOINT_PATH, context["stage_6_6_hashes"]
    )
    old_by_key = {
        (str(state["game_id"]), int(state["turn_index"])): state
        for state in context["old"]["state_diagnostics"]
    }
    states_by_partition: dict[str, list[dict]] = {}
    accounting_by_partition: dict[str, dict] = {}
    for partition, samples in context["partitions"].items():
        q_values, accounting = old_diagnosis.score_partition(model, samples)
        states_by_partition[partition] = [
            add_old_comparison(
                old_diagnosis.diagnose_state(sample, partition, values),
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
    metrics = reproduce_stage_6_6_metrics(
        model, context["pairs"], context["report"]
    )
    corrective_pairs = corrective_pair_diagnostics(
        all_states, context["corrective_mappings"]
    )
    new_aggregates = {
        "pipeline_train": old_diagnosis.aggregate_states(
            states_by_partition["pipeline_train"]
        ),
        "pipeline_development": old_diagnosis.aggregate_states(
            states_by_partition["pipeline_development"]
        ),
        "overall": old_diagnosis.aggregate_states(all_states),
    }
    old_aggregates = context["old"]["aggregates"]
    comparison = {
        partition: {
            "old": old_aggregates[partition],
            "new": new_aggregates[partition],
            "teacher_top1_count_delta": new_aggregates[partition]["teacher_top1_count"]
            - old_aggregates[partition]["teacher_top1_count"],
            "other_action_top1_count_delta": new_aggregates[partition][
                "other_action_top1_count"
            ]
            - old_aggregates[partition]["other_action_top1_count"],
            "strictly_outranking_state_count_delta": new_aggregates[partition][
                "unpaired_action_strictly_outranks_teacher_state_count"
            ]
            - old_aggregates[partition][
                "unpaired_action_strictly_outranks_teacher_state_count"
            ],
        }
        for partition in ("pipeline_train", "pipeline_development", "overall")
    }
    forbidden = {
        "rollout_runs": 0,
        "training_runs": 0,
        "hyperparameter_searches": 0,
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
    result = {
        "schema_version": SCHEMA_VERSION,
        "frozen_inputs": {
            "paths": {name: str(path) for name, path in frozen_paths().items()},
            "sha256": context["frozen_hashes"],
        },
        "checkpoint_schema_version": checkpoint["schema_version"],
        "checkpoint_status": "pipeline_only_unpromoted_not_capability_evidence",
        "stage_6_6_validation": {
            "training_run_count": 1,
            "development_training_use_count": 0,
            "checkpoint_reload_verified": True,
            "metrics_and_prediction_digests_reproduced": True,
        },
        "partition_mapping": {
            "pipeline_train_game_count": len(context["partitions"]["pipeline_train"]),
            "pipeline_development_game_count": len(
                context["partitions"]["pipeline_development"]
            ),
            "overlap_game_count": 0,
            "unknown_game_count": 0,
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
        "stage_6_6_metric_reproduction": metrics,
        "state_diagnostics": all_states,
        "aggregates": new_aggregates,
        "old_checkpoint_comparison": comparison,
        "corrective_pair_diagnostics": corrective_pairs,
        "corrective_pair_summary": {
            "pair_count": len(corrective_pairs),
            "teacher_outranks_frozen_rejected_top1_count": sum(
                item["teacher_outranks_frozen_rejected_top1"]
                for item in corrective_pairs
            ),
            "teacher_is_first_max_full_set_top1_count": sum(
                item["teacher_is_first_max_full_set_top1"]
                for item in corrective_pairs
            ),
            "frozen_rejected_top1_remains_new_top1_count": sum(
                item["frozen_rejected_top1_remains_new_top1"]
                for item in corrective_pairs
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
        or len(corrective_pairs) != 6
        or any(forbidden.values())
    ):
        raise RuntimeError("corrective diagnosis accounting gate failed")
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
        "corrective_pair_count": len(context["corrective_mappings"]),
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
        raise RuntimeError("a frozen input changed during corrective diagnosis")
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
        raise RuntimeError("independent corrective diagnosis reproduction mismatch")
    if verify_frozen_hashes() != context["frozen_hashes"]:
        raise RuntimeError("a frozen input changed during corrective diagnosis audit")
    result = {
        "status": "passed",
        "state_count": len(saved["state_diagnostics"]),
        "legal_action_count": saved["scoring_accounting"]["legal_action_score_count"],
        "action_order_digest_exact": True,
        "rankings_and_aggregates_exact": True,
        "stage_6_6_metrics_and_prediction_digests_exact": True,
        "corrective_pair_mappings_and_arithmetic_exact": True,
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
