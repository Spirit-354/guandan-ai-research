from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

import website_teacher_preference as preference
import website_teacher_preference_evidence_audit as source_audit


SCHEMA_VERSION = "website_teacher_preference_corrective_residual_evidence_audit_v1"
DIAGNOSIS_PATH = Path("website_teacher_preference_corrective_failure_diagnosis_v1.json")
CHECKPOINT_PATH = Path(
    "models_website_teacher_preference_corrective_v1/"
    "website_teacher_preference_corrective_final.pth"
)
TRAINING_REPORT_PATH = Path("website_teacher_preference_corrective_training_v1.json")
CORRECTIVE_DATASET_PATH = Path("website_teacher_preference_corrective_dataset_v1.pth")
CORRECTIVE_MANIFEST_PATH = Path(
    "website_teacher_preference_corrective_dataset_v1_manifest.json"
)
TEACHER_PATH = Path("website_information_set_teacher_dataset_v6.pth")
SPLIT_PATH = Path("website_teacher_preference_split_v1.json")
CONFIRMATION_PATH = Path(
    "website_teacher_preference_unpaired_train_confirmation_v1.json"
)
OLD_DIAGNOSIS_PATH = Path("website_teacher_preference_failure_diagnosis_v1.json")
OUTPUT_PATH = Path(
    "website_teacher_preference_corrective_residual_evidence_audit_v1.json"
)

EXPECTED_HASHES = {
    "stage_6_7_diagnosis": "2b4359470e74f5eae28d6589477aca5f929ae6b5b88e094fa86209bf4328163d",
    "corrective_checkpoint": "8cb368c8c0ae3f8c41c577e055ddd4796cbaae8163720cc630a435aa25bc1a49",
    "corrective_training_report": "baa97ccf71c237895a92f4cb8b36b9559cf3cabe45b4901b7481d9f50f4c0830",
    "corrective_dataset": "fad7ae18fea8b02cbc88ad4a8a7f8ecee298abe436ef589f5c88d66e42a32707",
    "corrective_manifest": "0a5dc4f60091338b65f86f83ad30ae55dc18c058ee8b07535a314510ad96ef0a",
    "teacher_dataset": "a74416e6facb28a1bc64563eba90cb33d460dc9e59cc2109518da142465e15f8",
    "split_manifest": "5a15e514dc9bc51d77d300837151d9f1a49250f42885cc7940725bcbe4d35107",
    "stage_6_4_confirmation": "8e17377b5a1523d9f0a47af7218d687e062a3ade671c57f387eb4c1a0888cfae",
    "old_diagnosis": "da08516c39986a01349533e160ba0e97a566d7fad6e42b0b7b3ce41df835b0b2",
}
FROZEN_PATHS = {
    "stage_6_7_diagnosis": DIAGNOSIS_PATH,
    "corrective_checkpoint": CHECKPOINT_PATH,
    "corrective_training_report": TRAINING_REPORT_PATH,
    "corrective_dataset": CORRECTIVE_DATASET_PATH,
    "corrective_manifest": CORRECTIVE_MANIFEST_PATH,
    "teacher_dataset": TEACHER_PATH,
    "split_manifest": SPLIT_PATH,
    "stage_6_4_confirmation": CONFIRMATION_PATH,
    "old_diagnosis": OLD_DIAGNOSIS_PATH,
}
EXPECTED_PROFILES = ["greedy_bot", "tempo_baseline"]


def load_json(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError(f"{path} must contain a JSON object")
    return payload


def verify_frozen_hashes() -> dict[str, str]:
    actual = {}
    for name, path in FROZEN_PATHS.items():
        value = source_audit._sha256(path)
        if value != EXPECTED_HASHES[name]:
            raise RuntimeError(f"{name} SHA-256 mismatch")
        actual[name] = value
    return actual


def ensure_unused_output(output_path: Path = OUTPUT_PATH) -> None:
    if output_path.exists():
        raise RuntimeError(f"audit output already exists: {output_path}")


def validate_stage_6_7(diagnosis: dict, training_report: dict) -> dict:
    if diagnosis.get("schema_version") != (
        "website_teacher_preference_corrective_failure_diagnosis_v1"
    ):
        raise RuntimeError("Stage 6.7 diagnosis schema mismatch")
    scoring = diagnosis.get("scoring_accounting") or {}
    required_scoring = {
        "unique_teacher_state_count": 22,
        "recorded_legal_action_count": 934,
        "legal_action_score_count": 934,
        "dropped_state_count": 0,
        "duplicate_state_count": 0,
        "dimension_invalid_action_count": 0,
        "nonfinite_q_count": 0,
        "illegal_recorded_action_count": 0,
        "dropped_action_count": 0,
        "duplicate_action_scoring_count": 0,
        "reconstructed_action_count": 0,
    }
    for key, expected in required_scoring.items():
        if scoring.get(key) != expected:
            raise RuntimeError(f"Stage 6.7 scoring {key} mismatch")
    aggregates = diagnosis.get("aggregates") or {}
    expected_top1 = {
        "pipeline_train": (10, 0, 8, 0),
        "pipeline_development": (1, 0, 3, 0),
        "overall": (11, 0, 11, 0),
    }
    for partition, expected in expected_top1.items():
        item = aggregates.get(partition) or {}
        actual = (
            item.get("teacher_top1_count"),
            item.get("behavior_top1_count"),
            item.get("other_action_top1_count"),
            item.get("pass_top1_count"),
        )
        if actual != expected:
            raise RuntimeError(f"Stage 6.7 {partition} top1 conclusion mismatch")
    reproduction = diagnosis.get("stage_6_6_metric_reproduction") or {}
    if reproduction.get("exact_match") is not True:
        raise RuntimeError("Stage 6.6 metric reproduction is not exact")
    if reproduction.get("actual") != reproduction.get("frozen"):
        raise RuntimeError("Stage 6.6 actual/frozen metrics differ")
    if reproduction.get("frozen") != training_report.get("final_metrics"):
        raise RuntimeError("Stage 6.6 report metrics/digests mismatch")
    validation = diagnosis.get("stage_6_6_validation") or {}
    if validation != {
        "training_run_count": 1,
        "development_training_use_count": 0,
        "checkpoint_reload_verified": True,
        "metrics_and_prediction_digests_reproduced": True,
    }:
        raise RuntimeError("Stage 6.6 validation conclusion mismatch")
    if sum((diagnosis.get("forbidden_operation_counts") or {}).values()) != 0:
        raise RuntimeError("Stage 6.7 forbidden operation count mismatch")
    return {
        "state_count": 22,
        "full_set_action_score_count": 934,
        "teacher_top1_count": 11,
        "behavior_top1_count": 0,
        "other_top1_count": 11,
        "pass_top1_count": 0,
        "stage_6_6_metrics_and_prediction_digests_exact": True,
        "independent_audit_conclusion_retained": True,
    }


def extract_residual_targets(
    diagnosis: dict, samples: list[dict], split: dict
) -> tuple[list[dict], dict[tuple[str, int], dict]]:
    sample_by_key = {
        (str(sample["game_id"]), int(sample["turn_index"])): sample
        for sample in samples
    }
    if len(sample_by_key) != 22:
        raise RuntimeError("teacher samples must contain 22 unique keys")
    train_ids = {str(value) for value in split.get("pipeline_train_game_ids") or []}
    development_ids = {
        str(value) for value in split.get("pipeline_development_game_ids") or []
    }
    if len(train_ids) != 18 or len(development_ids) != 4 or train_ids & development_ids:
        raise RuntimeError("frozen 18/4 split mismatch")
    residual_states = [
        state
        for state in diagnosis.get("state_diagnostics") or []
        if state.get("top1_source") == "other"
    ]
    if len(residual_states) != 11:
        raise RuntimeError("Stage 6.7 must contain exactly 11 residual states")
    targets = []
    seen = set()
    for state in residual_states:
        key = (str(state["game_id"]), int(state["turn_index"]))
        if key in seen or key not in sample_by_key:
            raise RuntimeError("residual target is duplicated or missing")
        seen.add(key)
        sample = sample_by_key[key]
        actions = sample.get("legal_actions") or []
        q_values = state.get("legal_action_q_values") or []
        if len(actions) != len(q_values) or not actions:
            raise RuntimeError("residual legal-action/Q accounting mismatch")
        if source_audit._action_order_sha256(actions) != state.get(
            "legal_action_order_sha256"
        ):
            raise RuntimeError("residual legal-action order mismatch")
        top1_index = q_values.index(max(q_values))
        teacher_matches = [
            index
            for index, action in enumerate(actions)
            if action == sample.get("teacher_action")
        ]
        behavior_matches = [
            index
            for index, action in enumerate(actions)
            if action == sample.get("behavior_action")
        ]
        if len(teacher_matches) != 1 or len(behavior_matches) != 1:
            raise RuntimeError("residual preference action identity is ambiguous")
        if (
            top1_index != state.get("top1_index")
            or teacher_matches[0] != state.get("teacher_action_index")
            or behavior_matches[0] != state.get("behavior_action_index")
        ):
            raise RuntimeError("residual action index mismatch")
        if top1_index in {teacher_matches[0], behavior_matches[0]}:
            raise RuntimeError("residual top1 source is not other")
        if state.get("teacher_rank") != 1 + sum(
            value > q_values[teacher_matches[0]] for value in q_values
        ):
            raise RuntimeError("residual teacher rank mismatch")
        partition = (
            "pipeline_train"
            if key[0] in train_ids
            else "pipeline_development" if key[0] in development_ids else None
        )
        if partition is None or state.get("pipeline_partition") != partition:
            raise RuntimeError("residual pipeline partition mismatch")
        targets.append(
            {
                "game_id": key[0],
                "turn_index": key[1],
                "pipeline_partition": partition,
                "legal_action_count": len(actions),
                "legal_action_order_sha256": state["legal_action_order_sha256"],
                "teacher_rank": int(state["teacher_rank"]),
                "top1_action_index": top1_index,
                "top1_action_sha256": source_audit._action_sha256(actions[top1_index]),
            }
        )
    return targets, sample_by_key


def classify_direct_evidence(
    *,
    top1_candidate_count: int,
    teacher_candidate_count: int,
    required_field_status: dict[str, bool],
    direct_pair: dict | None,
) -> tuple[str, list[str]]:
    if top1_candidate_count > 1 or teacher_candidate_count != 1:
        return "ambiguous_mapping", ["ambiguous_candidate_mapping"]
    if top1_candidate_count == 0:
        return (
            "residual_action_not_evaluated_as_candidate",
            ["residual_top1_candidate_result_missing"],
        )
    missing = [name for name, present in required_field_status.items() if not present]
    if missing:
        return (
            "candidate_present_without_direct_paired_statistics",
            [f"missing_direct_field:{name}" for name in missing],
        )
    profiles = direct_pair["continuation_profile_advantages"]
    if not isinstance(profiles, dict) or set(profiles) != set(EXPECTED_PROFILES):
        return (
            "candidate_present_without_direct_paired_statistics",
            ["missing_direct_field:both_continuation_profile_advantages"],
        )
    direction = direct_pair["directional_classification"]
    if direction == "teacher_over_residual_top1_supported":
        return direction, []
    if direction == "residual_top1_over_teacher_supported":
        return direction, []
    return "direct_paired_comparison_inconclusive", []


def _candidate_summary(candidate: dict | None) -> dict | None:
    if candidate is None:
        return None
    return {
        "action_id": candidate.get("action_id"),
        "action_type": candidate.get("action_type"),
        "physical_cards": candidate.get("physical_cards"),
        "physical_cards_website": candidate.get("physical_cards_website"),
        "rollout_count": candidate.get("rollout_count"),
        "mean_return": candidate.get("mean_return"),
        "return_variance": candidate.get("return_variance"),
        "completion_rate": candidate.get("completion_rate"),
    }


def audit_train_target(
    target: dict, sample: dict, evidence_path: Path, evidence: dict
) -> dict:
    key = (target["game_id"], target["turn_index"])
    labels = [
        item
        for item in evidence.get("strong_teacher_labels") or []
        if str(item.get("game_id")) == key[0] and int(item.get("turn_index")) == key[1]
    ]
    cases = [
        item
        for item in evidence.get("case_results") or []
        if str(item.get("game_id")) == key[0] and int(item.get("turn_index")) == key[1]
    ]
    if len(labels) != 1 or len(cases) != 1:
        raise RuntimeError("train source state mapping is not unique")
    label, case = labels[0], cases[0]
    if label.get("state") != sample.get("state"):
        raise RuntimeError("train source state mismatch")
    if label.get("legal_actions") != sample.get("legal_actions"):
        raise RuntimeError("train source legal actions mismatch")
    metadata = label.get("legal_action_metadata") or []
    if len(metadata) != len(sample["legal_actions"]):
        raise RuntimeError("train source legal-action metadata count mismatch")
    top_metadata = metadata[target["top1_action_index"]]
    teacher_index = sample["legal_actions"].index(sample["teacher_action"])
    teacher_metadata = metadata[teacher_index]
    top_cards = top_metadata.get("cards")
    teacher_cards = teacher_metadata.get("cards")
    if not isinstance(top_cards, list) or not isinstance(teacher_cards, list):
        raise RuntimeError("train source physical-card metadata missing")
    candidates = case.get("candidate_results") or []
    top_matches = [
        item for item in candidates if item.get("physical_cards_website") == top_cards
    ]
    teacher_matches = [
        item
        for item in candidates
        if item.get("physical_cards_website") == teacher_cards
    ]
    direct_pair = case.get("direct_teacher_vs_residual_top1_comparison")
    top_candidate = top_matches[0] if len(top_matches) == 1 else None
    teacher_candidate = teacher_matches[0] if len(teacher_matches) == 1 else None
    direct_pair = direct_pair if isinstance(direct_pair, dict) else None
    required_field_status = {
        "rollout_count": bool(
            top_candidate is not None
            and teacher_candidate is not None
            and top_candidate.get("rollout_count") == 16
            and teacher_candidate.get("rollout_count") == 16
        ),
        "hidden_card_sampling_method": evidence.get("hidden_card_sampling_method")
        == "uniform_physical_assignment_given_public_counts_v1",
        "mean_returns": bool(
            top_candidate is not None
            and teacher_candidate is not None
            and top_candidate.get("mean_return") is not None
            and teacher_candidate.get("mean_return") is not None
        ),
        "return_variances": bool(
            top_candidate is not None
            and teacher_candidate is not None
            and top_candidate.get("return_variance") is not None
            and teacher_candidate.get("return_variance") is not None
        ),
        "candidate_advantage": bool(
            direct_pair is not None
            and direct_pair.get("teacher_minus_residual_top1_advantage") is not None
        ),
        "confidence_and_lower_bound": bool(
            direct_pair is not None
            and direct_pair.get("teacher_over_residual_top1_confidence") is not None
            and direct_pair.get("teacher_minus_residual_top1_95_lower_bound")
            is not None
        ),
        "both_continuation_profile_advantages": bool(
            direct_pair is not None
            and isinstance(direct_pair.get("continuation_profile_advantages"), dict)
            and set(direct_pair["continuation_profile_advantages"])
            == set(EXPECTED_PROFILES)
        ),
        "directional_classification": bool(
            direct_pair is not None
            and direct_pair.get("directional_classification") is not None
        ),
    }
    evidence_class, reasons = classify_direct_evidence(
        top1_candidate_count=len(top_matches),
        teacher_candidate_count=len(teacher_matches),
        required_field_status=required_field_status,
        direct_pair=direct_pair,
    )
    if evidence_class == "ambiguous_mapping":
        raise RuntimeError("ambiguous train candidate mapping")
    source_summary = source_audit.evidence_file_summary(evidence_path, evidence)
    return {
        **target,
        "source_rollout_evidence": evidence_path.name,
        "source_rollout_evidence_sha256": source_summary["sha256"],
        "source_state_match": True,
        "source_legal_actions_match": True,
        "action_mapping_reconstructed": False,
        "action_mapping_substituted": False,
        "top1_physical_identity": {
            "cards_website": top_cards,
            "action_type": top_metadata.get("action_type"),
            "rank": top_metadata.get("rank"),
            "size": top_metadata.get("size"),
        },
        "teacher_physical_identity": {
            "cards_website": teacher_cards,
            "action_type": teacher_metadata.get("action_type"),
            "rank": teacher_metadata.get("rank"),
            "size": teacher_metadata.get("size"),
        },
        "top1_candidate_match_count": len(top_matches),
        "teacher_candidate_match_count": len(teacher_matches),
        "top1_candidate_evidence": _candidate_summary(top_candidate),
        "teacher_candidate_evidence": _candidate_summary(teacher_candidate),
        "source_hidden_card_sampling_method": evidence.get(
            "hidden_card_sampling_method"
        ),
        "source_continuation_profiles": evidence.get("continuation_profiles"),
        "direct_teacher_vs_residual_top1_comparison": direct_pair,
        "required_direct_field_status": required_field_status,
        "evidence_classification": evidence_class,
        "insufficiency_reasons": reasons,
        "teacher_over_residual_top1_supported": (
            evidence_class == "teacher_over_residual_top1_supported"
        ),
        "residual_top1_over_teacher_supported": (
            evidence_class == "residual_top1_over_teacher_supported"
        ),
    }


def aggregate_train_audits(audits: list[dict]) -> dict:
    classes = Counter(item["evidence_classification"] for item in audits)
    return {
        "target_count": len(audits),
        "source_file_count": len({item["source_rollout_evidence"] for item in audits}),
        "residual_action_not_evaluated_as_candidate_count": classes[
            "residual_action_not_evaluated_as_candidate"
        ],
        "candidate_present_without_direct_paired_statistics_count": classes[
            "candidate_present_without_direct_paired_statistics"
        ],
        "direct_paired_comparison_inconclusive_count": classes[
            "direct_paired_comparison_inconclusive"
        ],
        "teacher_over_residual_top1_supported_count": classes[
            "teacher_over_residual_top1_supported"
        ],
        "residual_top1_over_teacher_supported_count": classes[
            "residual_top1_over_teacher_supported"
        ],
        "insufficient_evidence_count": sum(
            bool(item["insufficiency_reasons"]) for item in audits
        ),
        "ambiguous_mapping_count": classes["ambiguous_mapping"],
    }


def validate_context() -> dict:
    frozen_hashes = verify_frozen_hashes()
    diagnosis = load_json(DIAGNOSIS_PATH)
    report = load_json(TRAINING_REPORT_PATH)
    split = load_json(SPLIT_PATH)
    conclusion = validate_stage_6_7(diagnosis, report)
    samples, _summary, teacher_hash = preference.load_teacher_dataset(TEACHER_PATH)
    if teacher_hash != frozen_hashes["teacher_dataset"]:
        raise RuntimeError("loaded teacher dataset hash mismatch")
    targets, sample_by_key = extract_residual_targets(diagnosis, samples, split)
    train_targets = [
        item for item in targets if item["pipeline_partition"] == "pipeline_train"
    ]
    development_targets = [
        item for item in targets if item["pipeline_partition"] == "pipeline_development"
    ]
    if len(train_targets) != 8 or len(development_targets) != 3:
        raise RuntimeError("residual target partition count mismatch")
    return {
        "frozen_hashes": frozen_hashes,
        "stage_6_7_conclusion": conclusion,
        "targets": targets,
        "train_targets": train_targets,
        "development_targets": development_targets,
        "sample_by_key": sample_by_key,
    }


def compute_result(context: dict) -> dict:
    workspace_root = Path.cwd()
    evidence_cache = {}
    train_audits = []
    for target in context["train_targets"]:
        key = (target["game_id"], target["turn_index"])
        sample = context["sample_by_key"][key]
        reference = sample.get("source_rollout_eval")
        if not isinstance(reference, str) or not reference:
            raise RuntimeError("train teacher sample source evidence missing")
        if reference not in evidence_cache:
            path = source_audit.resolve_direct_evidence_path(reference, workspace_root)
            payload = load_json(path)
            evidence_cache[reference] = (path, payload)
        path, payload = evidence_cache[reference]
        train_audits.append(audit_train_target(target, sample, path, payload))
    aggregates = aggregate_train_audits(train_audits)
    if aggregates != {
        "target_count": 8,
        "source_file_count": 6,
        "residual_action_not_evaluated_as_candidate_count": 5,
        "candidate_present_without_direct_paired_statistics_count": 3,
        "direct_paired_comparison_inconclusive_count": 0,
        "teacher_over_residual_top1_supported_count": 0,
        "residual_top1_over_teacher_supported_count": 0,
        "insufficient_evidence_count": 8,
        "ambiguous_mapping_count": 0,
    }:
        raise RuntimeError("frozen train evidence aggregate mismatch")
    future_manifest = [
        {
            "game_id": item["game_id"],
            "turn_index": item["turn_index"],
            "pipeline_partition": "pipeline_train",
            "top1_action_index": item["top1_action_index"],
            "top1_action_sha256": item["top1_action_sha256"],
            "reason": item["insufficiency_reasons"],
            "execution_allowed_in_this_stage": False,
        }
        for item in train_audits
        if item["insufficiency_reasons"]
    ]
    result = {
        "schema_version": SCHEMA_VERSION,
        "status": "completed",
        "frozen_inputs": {
            "paths": {name: str(path) for name, path in FROZEN_PATHS.items()},
            "sha256": context["frozen_hashes"],
        },
        "stage_6_7_conclusion_reproduction": context["stage_6_7_conclusion"],
        "target_reproduction": {
            "expected_target_count": 11,
            "reproduced_target_count": 11,
            "pipeline_train_target_count": 8,
            "pipeline_development_target_count": 3,
            "missing_target_count": 0,
            "duplicate_target_count": 0,
            "extra_target_count": 0,
            "reconstructed_action_count": 0,
            "substituted_action_count": 0,
            "ambiguous_mapping_count": 0,
        },
        "pipeline_train_target_audits": train_audits,
        "pipeline_development_identity_only": context["development_targets"],
        "source_evidence_files": [
            {
                "path": name,
                "sha256": source_audit._sha256(evidence_cache[name][0]),
            }
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
        },
        "future_counterfactual_manifest": future_manifest,
        "future_counterfactual_manifest_case_count": len(future_manifest),
        "future_counterfactual_manifest_executed": False,
        "new_objective_defined": False,
        "unsupported_ordering_label_count": 0,
        "interpretation_scope": {
            "causal_claim_allowed": False,
            "capability_claim_allowed": False,
            "checkpoint_promotion_allowed": False,
        },
        "forbidden_operation_counts": {
            "new_rollout_runs": 0,
            "training_runs": 0,
            "fine_tuning_runs": 0,
            "threshold_tuning_runs": 0,
            "checkpoint_selections": 0,
            "checkpoint_modifications": 0,
            "website_dataset_loads": 0,
            "locked_test_loads": 0,
            "arena_games": 0,
            "website_shadow_games": 0,
            "website_games": 0,
            "model_controlled_website_actions": 0,
            "future_manifest_executions": 0,
            "checkpoint_promotions": 0,
            "capability_claims": 0,
        },
    }
    return result


def preflight() -> dict:
    ensure_unused_output()
    context = validate_context()
    result = {
        "status": "ready",
        "output_exists": False,
        "frozen_hash_count": len(context["frozen_hashes"]),
        "residual_target_count": len(context["targets"]),
        "pipeline_train_target_count": len(context["train_targets"]),
        "pipeline_development_target_count": len(context["development_targets"]),
        "development_source_evidence_read_count": 0,
    }
    print(json.dumps(result, indent=2))
    return result


def run() -> dict:
    ensure_unused_output()
    context = validate_context()
    result = compute_result(context)
    if verify_frozen_hashes() != context["frozen_hashes"]:
        raise RuntimeError("a frozen input changed during the audit")
    OUTPUT_PATH.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "status": result["status"],
                "output": str(OUTPUT_PATH),
                "target_reproduction": result["target_reproduction"],
                "train_evidence_aggregates": result["train_evidence_aggregates"],
                "development_isolation": result["development_isolation"],
            },
            indent=2,
        )
    )
    return result


def audit() -> dict:
    saved = load_json(OUTPUT_PATH)
    context = validate_context()
    recomputed = compute_result(context)
    if saved != recomputed:
        raise RuntimeError("independent residual evidence reproduction mismatch")
    if verify_frozen_hashes() != context["frozen_hashes"]:
        raise RuntimeError("a frozen input changed during independent audit")
    result = {
        "status": "passed",
        "target_identities_exact": True,
        "source_hashes_exact": True,
        "action_mappings_exact": True,
        "classifications_exact": True,
        "partition_counts_exact": True,
        "aggregates_exact": True,
        "development_source_evidence_read_count": 0,
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
    elif args.run:
        run()
    else:
        audit()


if __name__ == "__main__":
    main()
