from __future__ import annotations

import hashlib
import json
import struct
from collections import Counter
from pathlib import Path
from typing import Any

import website_teacher_preference as preference


SCHEMA_VERSION = "website_teacher_preference_unpaired_evidence_audit_v1"
DIAGNOSIS_PATH = Path("website_teacher_preference_failure_diagnosis_v1.json")
TEACHER_PATH = Path("website_information_set_teacher_dataset_v6.pth")
SPLIT_PATH = Path("website_teacher_preference_split_v1.json")
TRAINING_REPORT_PATH = Path("website_teacher_preference_training_v1.json")
CHECKPOINT_PATH = Path(
    "models_website_teacher_preference_v1/website_teacher_preference_final.pth"
)
ARENA_PATH = Path("website_teacher_preference_arena_smoke20_v1.json")
OUTPUT_PATH = Path("website_teacher_preference_unpaired_evidence_audit_v1.json")

EXPECTED_HASHES = {
    "stage_6_2_diagnosis": "da08516c39986a01349533e160ba0e97a566d7fad6e42b0b7b3ce41df835b0b2",
    "teacher_dataset": preference.EXPECTED_TEACHER_SHA256,
    "split_manifest": "5a15e514dc9bc51d77d300837151d9f1a49250f42885cc7940725bcbe4d35107",
    "training_report": "896192b1d0b4de2caabe20ac17d6a20766fc7f89d6e82a981d834b777932ddd3",
    "checkpoint": "c54801a9db05100c2fe5a9bf610a64fc7c94dc2cd947dfaab115ff827bd90919",
    "arena_evidence": "aa45da9de202194102fe8d11e612ad3eb4b51177fd910b9a7948836afd2a1fe6",
}
EVIDENCE_CLASSES = (
    "dual_continuation_confirmed",
    "greedy_only_screened",
    "present_without_qualifying_comparison",
    "absent_from_prior_evidence",
    "ambiguous_mapping",
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_json(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError(f"{path} must contain a JSON object")
    return payload


def _verify_hash(path: Path, expected: str) -> str:
    actual = _sha256(path)
    if actual != expected:
        raise RuntimeError(
            f"{path} SHA-256 mismatch: expected {expected}, got {actual}"
        )
    return actual


def _action_sha256(action: list[float]) -> str:
    return hashlib.sha256(
        struct.pack(f"<{len(action)}f", *[float(value) for value in action])
    ).hexdigest()


def _action_order_sha256(actions: list[list[float]]) -> str:
    digest = hashlib.sha256()
    for action in actions:
        digest.update(
            struct.pack(f"<{len(action)}f", *[float(value) for value in action])
        )
    return digest.hexdigest()


def resolve_direct_evidence_path(reference: str, root: Path) -> Path:
    relative = Path(reference)
    if relative.is_absolute() or len(relative.parts) != 1 or relative.name != reference:
        raise RuntimeError("source rollout evidence must be a direct filename")
    resolved_root = root.resolve()
    resolved = (resolved_root / relative).resolve()
    if resolved.parent != resolved_root:
        raise RuntimeError("source rollout evidence escapes the workspace root")
    if not resolved.is_file():
        raise RuntimeError(f"source rollout evidence does not exist: {reference}")
    return resolved


def classify_evidence(
    *,
    mapping_ambiguous: bool,
    dual_continuation_qualified: bool,
    greedy_only_recorded: bool,
    present_in_source_legal_actions: bool,
) -> str:
    if mapping_ambiguous:
        return "ambiguous_mapping"
    if dual_continuation_qualified:
        return "dual_continuation_confirmed"
    if greedy_only_recorded:
        return "greedy_only_screened"
    if present_in_source_legal_actions:
        return "present_without_qualifying_comparison"
    return "absent_from_prior_evidence"


def reproduce_target(state: dict, sample: dict, partition: str) -> dict:
    actions = sample.get("legal_actions") or []
    q_values = state.get("legal_action_q_values") or []
    if len(actions) != len(q_values) or not actions:
        raise RuntimeError("target legal-action/Q accounting mismatch")
    if _action_order_sha256(actions) != state.get("legal_action_order_sha256"):
        raise RuntimeError("target legal-action order hash mismatch")
    teacher_matches = [
        index for index, action in enumerate(actions) if action == sample["teacher_action"]
    ]
    behavior_matches = [
        index for index, action in enumerate(actions) if action == sample["behavior_action"]
    ]
    if len(teacher_matches) != 1 or len(behavior_matches) != 1:
        raise RuntimeError("target preference action identity is ambiguous")
    top1_index = q_values.index(max(q_values))
    if top1_index != state.get("top1_index"):
        raise RuntimeError("target first-maximum index mismatch")
    if teacher_matches[0] != state.get("teacher_action_index"):
        raise RuntimeError("target teacher index mismatch")
    if behavior_matches[0] != state.get("behavior_action_index"):
        raise RuntimeError("target behavior index mismatch")
    if top1_index in {teacher_matches[0], behavior_matches[0]}:
        raise RuntimeError("target top-1 action is not unpaired")
    if not q_values[top1_index] > q_values[teacher_matches[0]]:
        raise RuntimeError("target top-1 action does not strictly outrank teacher")
    if state.get("pipeline_partition") != partition:
        raise RuntimeError("target pipeline partition mismatch")
    return {
        "game_id": str(sample["game_id"]),
        "turn_index": int(sample["turn_index"]),
        "pipeline_partition": partition,
        "legal_action_count": len(actions),
        "legal_action_order_sha256": state["legal_action_order_sha256"],
        "teacher_action_index": teacher_matches[0],
        "behavior_action_index": behavior_matches[0],
        "top1_action_index": top1_index,
        "top1_q": float(q_values[top1_index]),
        "teacher_q": float(q_values[teacher_matches[0]]),
        "top1_minus_teacher_q": float(
            q_values[top1_index] - q_values[teacher_matches[0]]
        ),
        "top1_action": actions[top1_index],
        "top1_action_sha256": _action_sha256(actions[top1_index]),
    }


def reproduce_targets(
    diagnosis: dict, samples: list[dict], split: dict
) -> tuple[list[dict], dict[tuple[str, int], dict]]:
    sample_by_key = {
        (str(sample["game_id"]), int(sample["turn_index"])): sample
        for sample in samples
    }
    if len(sample_by_key) != 22:
        raise RuntimeError("teacher samples must contain 22 unique state keys")
    train_ids = {str(value) for value in split["pipeline_train_game_ids"]}
    development_ids = {
        str(value) for value in split["pipeline_development_game_ids"]
    }
    if len(train_ids) != 18 or len(development_ids) != 4 or train_ids & development_ids:
        raise RuntimeError("frozen pipeline partition mismatch")
    states = [
        state
        for state in diagnosis.get("state_diagnostics") or []
        if state.get("unpaired_action_strictly_outranks_teacher") is True
    ]
    if len(states) != 12:
        raise RuntimeError("Stage 6.2 must contain exactly 12 target states")
    targets: list[dict] = []
    seen: set[tuple[str, int]] = set()
    for state in states:
        key = (str(state["game_id"]), int(state["turn_index"]))
        if key in seen or key not in sample_by_key:
            raise RuntimeError("target state is duplicated or missing from teacher data")
        seen.add(key)
        partition = (
            "pipeline_train"
            if key[0] in train_ids
            else "pipeline_development"
            if key[0] in development_ids
            else None
        )
        if partition is None:
            raise RuntimeError("target state has no frozen pipeline partition")
        targets.append(reproduce_target(state, sample_by_key[key], partition))
    return targets, sample_by_key


def _all_empty(value: Any) -> bool:
    if isinstance(value, list):
        return all(_all_empty(item) for item in value)
    if isinstance(value, dict):
        return all(_all_empty(item) for item in value.values())
    return value in (None, "", False, 0)


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
        "advantage_95_lower_bound": candidate.get("advantage_95_lower_bound"),
        "label_confidence": candidate.get("label_confidence"),
        "continuation_policy_advantages": candidate.get(
            "continuation_policy_advantages"
        ),
    }


def evidence_file_summary(path: Path, payload: dict) -> dict:
    required = {
        "schema_version": "website_information_set_rollout_v1",
        "dataset_partition_role": "train_development",
        "hidden_card_sampling_method": (
            "uniform_physical_assignment_given_public_counts_v1"
        ),
        "continuation_policy": "information_set_profile_ensemble_v1",
        "continuation_profiles": ["greedy_bot", "tempo_baseline"],
        "common_determinizations_across_continuation_profiles": True,
        "requested_rollouts_per_action": 16,
        "minimum_strong_teacher_rollouts": 16,
        "all_cases_completed": True,
        "rollout_completion_rate": 1.0,
        "locked_test_loaded": False,
        "opponent_or_teammate_true_hands_used": False,
        "future_information_used": False,
        "capability_claim_allowed": False,
    }
    for key, expected in required.items():
        if payload.get(key) != expected:
            raise RuntimeError(f"source rollout evidence {path.name} {key} mismatch")
    if payload.get("integrity_failures") != []:
        raise RuntimeError(f"source rollout evidence {path.name} has integrity failures")
    return {
        "path": path.name,
        "sha256": _sha256(path),
        "schema_version": payload["schema_version"],
        "dataset_partition_role": payload["dataset_partition_role"],
        "hidden_card_sampling_method": payload["hidden_card_sampling_method"],
        "continuation_policy": payload["continuation_policy"],
        "continuation_profiles": payload["continuation_profiles"],
        "continuation_profile_rollout_counts": payload.get(
            "continuation_profile_rollout_counts"
        ),
        "common_determinizations_across_continuation_profiles": True,
        "requested_rollouts_per_action": payload["requested_rollouts_per_action"],
        "minimum_strong_teacher_rollouts": payload["minimum_strong_teacher_rollouts"],
        "requested_total_rollouts": payload.get("requested_total_rollouts"),
        "completed_rollouts": payload.get("completed_rollouts"),
        "rollout_completion_rate": payload["rollout_completion_rate"],
        "all_cases_completed": True,
        "integrity_failure_count": 0,
        "hidden_or_future_information_use_count": 0,
        "locked_test_loaded": False,
    }


def audit_target_evidence(
    target: dict,
    sample: dict,
    evidence_path: Path,
    evidence: dict,
    file_summary: dict,
) -> dict:
    key = (target["game_id"], target["turn_index"])
    labels = [
        label
        for label in evidence.get("strong_teacher_labels") or []
        if str(label.get("game_id")) == key[0]
        and int(label.get("turn_index")) == key[1]
    ]
    cases = [
        case
        for case in evidence.get("case_results") or []
        if str(case.get("game_id")) == key[0]
        and int(case.get("turn_index")) == key[1]
    ]
    if len(labels) != 1 or len(cases) != 1:
        raise RuntimeError("source evidence state mapping is not unique")
    label = labels[0]
    case = cases[0]
    if label.get("state") != sample.get("state"):
        raise RuntimeError("source evidence state does not match teacher sample")
    if label.get("legal_actions") != sample.get("legal_actions"):
        raise RuntimeError("source evidence legal actions do not match teacher sample")
    metadata = label.get("legal_action_metadata") or []
    if len(metadata) != len(sample["legal_actions"]):
        raise RuntimeError("source evidence legal-action metadata count mismatch")
    top_metadata = metadata[target["top1_action_index"]]
    teacher_metadata = metadata[target["teacher_action_index"]]
    top_cards = top_metadata.get("cards")
    teacher_cards = teacher_metadata.get("cards")
    if not isinstance(top_cards, list) or not isinstance(teacher_cards, list):
        raise RuntimeError("source evidence physical-card identity is missing")
    candidates = case.get("candidate_results") or []
    top_matches = [
        index
        for index, candidate in enumerate(candidates)
        if candidate.get("physical_cards_website") == top_cards
    ]
    teacher_matches = [
        index
        for index, candidate in enumerate(candidates)
        if candidate.get("physical_cards_website") == teacher_cards
    ]
    mapping_ambiguous = len(top_matches) > 1 or len(teacher_matches) != 1
    top_candidate = candidates[top_matches[0]] if len(top_matches) == 1 else None
    teacher_candidate = (
        candidates[teacher_matches[0]] if len(teacher_matches) == 1 else None
    )
    dual_integrity = bool(
        top_candidate is not None
        and teacher_candidate is not None
        and evidence.get("continuation_profiles")
        == ["greedy_bot", "tempo_baseline"]
        and evidence.get("common_determinizations_across_continuation_profiles")
        is True
        and evidence.get("all_cases_completed") is True
        and evidence.get("integrity_failures") == []
        and evidence.get("opponent_or_teammate_true_hands_used") is False
        and evidence.get("future_information_used") is False
        and case.get("case_timed_out") is False
        and _all_empty(case.get("candidate_failures") or [])
        and top_candidate.get("rollout_count") == 16
        and teacher_candidate.get("rollout_count") == 16
        and top_candidate.get("completion_rate") == 1.0
        and teacher_candidate.get("completion_rate") == 1.0
    )
    classification = classify_evidence(
        mapping_ambiguous=mapping_ambiguous,
        dual_continuation_qualified=dual_integrity,
        greedy_only_recorded=False,
        present_in_source_legal_actions=True,
    )
    top_specific_confidence_recorded = bool(
        top_candidate is not None
        and top_candidate.get("advantage_95_lower_bound") is not None
        and top_candidate.get("label_confidence") is not None
        and top_candidate.get("continuation_policy_advantages") is not None
    )
    teacher_minus_top_mean_return = None
    if top_candidate is not None and teacher_candidate is not None:
        teacher_minus_top_mean_return = float(
            teacher_candidate["mean_return"] - top_candidate["mean_return"]
        )
    source_label_metrics = {
        "comparison_target": "behavior_action_not_model_top1",
        "rollout_count": label.get("rollout_count"),
        "hidden_card_sampling_method": label.get("hidden_card_sampling_method"),
        "mean_return": label.get("mean_return"),
        "return_variance": label.get("return_variance"),
        "candidate_advantage": label.get("candidate_advantage"),
        "candidate_return_variance": label.get("candidate_return_variance"),
        "paired_return_variance": label.get("paired_return_variance"),
        "advantage_95_lower_bound": label.get("advantage_95_lower_bound"),
        "label_confidence": label.get("label_confidence"),
        "continuation_policy_advantages": label.get(
            "continuation_policy_advantages"
        ),
        "robust_across_continuation_profiles": label.get(
            "robust_across_continuation_profiles"
        ),
    }
    return {
        **target,
        "source_rollout_evidence": evidence_path.name,
        "source_rollout_evidence_sha256": file_summary["sha256"],
        "source_rollout_schema_version": file_summary["schema_version"],
        "source_state_match": True,
        "source_legal_actions_match": True,
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
        "top1_candidate_index": top_matches[0] if len(top_matches) == 1 else None,
        "teacher_candidate_match_count": len(teacher_matches),
        "teacher_candidate_index": (
            teacher_matches[0] if len(teacher_matches) == 1 else None
        ),
        "evidence_class": classification,
        "dual_continuation_integrity_qualified": dual_integrity,
        "top1_candidate_evidence": _candidate_summary(top_candidate),
        "teacher_candidate_evidence": _candidate_summary(teacher_candidate),
        "teacher_minus_top1_mean_return": teacher_minus_top_mean_return,
        "top1_specific_paired_confidence_recorded": (
            top_specific_confidence_recorded
        ),
        "source_teacher_label_metrics": source_label_metrics,
        "teacher_vs_top1_ordering_supported": bool(
            dual_integrity
            and top_specific_confidence_recorded
            and teacher_minus_top_mean_return is not None
            and teacher_minus_top_mean_return > 0.0
        ),
    }


def aggregate_audits(audits: list[dict]) -> dict:
    if not audits:
        raise RuntimeError("cannot aggregate an empty evidence audit")
    classes = Counter(audit["evidence_class"] for audit in audits)
    result = {
        "target_state_count": len(audits),
        "referenced_evidence_file_count": len(
            {audit["source_rollout_evidence"] for audit in audits}
        ),
        "teacher_vs_top1_ordering_supported_count": sum(
            audit["teacher_vs_top1_ordering_supported"] for audit in audits
        ),
        "future_counterfactual_manifest_case_count": sum(
            not audit["teacher_vs_top1_ordering_supported"] for audit in audits
        ),
    }
    for name in EVIDENCE_CLASSES:
        result[f"{name}_count"] = classes[name]
        result[f"{name}_rate"] = classes[name] / len(audits)
    return result


def validate_primary_inputs(
    diagnosis: dict, split: dict, report: dict, arena: dict
) -> dict[str, str]:
    paths = {
        "stage_6_2_diagnosis": DIAGNOSIS_PATH,
        "teacher_dataset": TEACHER_PATH,
        "split_manifest": SPLIT_PATH,
        "training_report": TRAINING_REPORT_PATH,
        "checkpoint": CHECKPOINT_PATH,
        "arena_evidence": ARENA_PATH,
    }
    actual = {
        name: _verify_hash(path, EXPECTED_HASHES[name])
        for name, path in paths.items()
    }
    if diagnosis.get("schema_version") != (
        "website_teacher_preference_failure_diagnosis_v1"
    ):
        raise RuntimeError("Stage 6.2 diagnosis schema mismatch")
    if diagnosis.get("checkpoint_screen_status") != (
        "rejected_from_100_200_game_screen"
    ):
        raise RuntimeError("Stage 6.2 checkpoint rejection mismatch")
    if sum((diagnosis.get("forbidden_operation_counts") or {}).values()) != 0:
        raise RuntimeError("Stage 6.2 forbidden operation count mismatch")
    if (
        split.get("pipeline_train_game_count") != 18
        or split.get("pipeline_development_game_count") != 4
        or split.get("overlap_game_ids") != []
    ):
        raise RuntimeError("frozen split counts mismatch")
    if (
        report.get("checkpoint_sha256") != EXPECTED_HASHES["checkpoint"]
        or report.get("checkpoint_promotion_allowed") is not False
        or report.get("capability_claim_allowed") is not False
    ):
        raise RuntimeError("frozen training report flags mismatch")
    required_arena = {
        "requested_games": 20,
        "completed_games": 20,
        "model_wins": 0,
        "baseline_wins": 20,
        "early_screen_continuation_allowed": False,
        "checkpoint_promotion_allowed": False,
        "capability_claim_allowed": False,
    }
    for key, expected in required_arena.items():
        if arena.get(key) != expected:
            raise RuntimeError(f"frozen Arena {key} mismatch")
    for key in (
        "illegal_action_count",
        "fallback_count",
        "materialization_fail_count",
        "hand_card_mismatch_count",
        "fatal_no_candidate_count",
    ):
        if arena.get(key) != 0:
            raise RuntimeError(f"frozen Arena safety count {key} mismatch")
    return actual


def run(output_path: Path = OUTPUT_PATH) -> dict:
    if output_path.exists():
        raise RuntimeError(f"audit output already exists: {output_path}")
    diagnosis = _load_json(DIAGNOSIS_PATH)
    split = _load_json(SPLIT_PATH)
    report = _load_json(TRAINING_REPORT_PATH)
    arena = _load_json(ARENA_PATH)
    primary_hashes = validate_primary_inputs(diagnosis, split, report, arena)
    samples, _summary, teacher_sha256 = preference.load_teacher_dataset(TEACHER_PATH)
    if teacher_sha256 != primary_hashes["teacher_dataset"]:
        raise RuntimeError("loaded teacher SHA-256 mismatch")
    targets, sample_by_key = reproduce_targets(diagnosis, samples, split)

    workspace_root = Path.cwd()
    evidence_cache: dict[str, tuple[Path, dict, dict]] = {}
    for target in targets:
        key = (target["game_id"], target["turn_index"])
        reference = sample_by_key[key].get("source_rollout_eval")
        if not isinstance(reference, str) or not reference:
            raise RuntimeError("teacher sample source rollout evidence is missing")
        if reference not in evidence_cache:
            path = resolve_direct_evidence_path(reference, workspace_root)
            payload = _load_json(path)
            summary = evidence_file_summary(path, payload)
            evidence_cache[reference] = (path, payload, summary)

    audits: list[dict] = []
    for target in targets:
        key = (target["game_id"], target["turn_index"])
        reference = sample_by_key[key]["source_rollout_eval"]
        path, payload, summary = evidence_cache[reference]
        audits.append(
            audit_target_evidence(
                target, sample_by_key[key], path, payload, summary
            )
        )
    if len(audits) != 12 or len(evidence_cache) != 10:
        raise RuntimeError("frozen target/evidence coverage count mismatch")
    ambiguous_count = sum(
        audit["evidence_class"] == "ambiguous_mapping" for audit in audits
    )
    if ambiguous_count:
        raise RuntimeError("ambiguous state/action mappings are not acceptable")

    train_audits = [
        audit for audit in audits if audit["pipeline_partition"] == "pipeline_train"
    ]
    development_audits = [
        audit
        for audit in audits
        if audit["pipeline_partition"] == "pipeline_development"
    ]
    future_manifest = []
    for audit in audits:
        if audit["teacher_vs_top1_ordering_supported"]:
            continue
        reason = (
            "top1_action_not_evaluated_as_candidate"
            if audit["top1_candidate_match_count"] == 0
            else "teacher_vs_top1_paired_confidence_not_recorded"
        )
        future_manifest.append(
            {
                "game_id": audit["game_id"],
                "turn_index": audit["turn_index"],
                "pipeline_partition": audit["pipeline_partition"],
                "top1_action_index": audit["top1_action_index"],
                "top1_action_sha256": audit["top1_action_sha256"],
                "top1_physical_identity": audit["top1_physical_identity"],
                "reason": reason,
                "execution_allowed_in_this_stage": False,
            }
        )
    result = {
        "schema_version": SCHEMA_VERSION,
        "primary_frozen_inputs": {
            "paths": {
                "stage_6_2_diagnosis": str(DIAGNOSIS_PATH),
                "teacher_dataset": str(TEACHER_PATH),
                "split_manifest": str(SPLIT_PATH),
                "training_report": str(TRAINING_REPORT_PATH),
                "checkpoint": str(CHECKPOINT_PATH),
                "arena_evidence": str(ARENA_PATH),
            },
            "sha256": primary_hashes,
        },
        "checkpoint_screen_status": "rejected_from_100_200_game_screen",
        "arena_conclusion": {
            "requested_games": 20,
            "completed_games": 20,
            "model_wins": 0,
            "baseline_wins": 20,
            "early_screen_continuation_allowed": False,
            "safety_error_count": 0,
        },
        "target_reproduction": {
            "expected_target_count": 12,
            "reproduced_target_count": len(targets),
            "missing_target_count": 0,
            "duplicate_target_count": 0,
            "extra_target_count": 0,
            "reconstructed_action_count": 0,
            "ambiguous_state_action_mapping_count": ambiguous_count,
            "pipeline_train_target_count": len(train_audits),
            "pipeline_development_target_count": len(development_audits),
        },
        "referenced_evidence_files": [
            evidence_cache[name][2] for name in sorted(evidence_cache)
        ],
        "referenced_evidence_file_count": len(evidence_cache),
        "unreferenced_evidence_file_read_count": 0,
        "target_audits": audits,
        "aggregates": {
            "pipeline_train": aggregate_audits(train_audits),
            "pipeline_development": aggregate_audits(development_audits),
            "overall": aggregate_audits(audits),
        },
        "teacher_versus_all_objective_supported_by_existing_evidence": False,
        "teacher_versus_all_decision_reason": (
            "eight top1 actions lack candidate evaluation and four evaluated "
            "top1 actions lack teacher-versus-top1 paired confidence"
        ),
        "future_counterfactual_manifest": future_manifest,
        "future_counterfactual_manifest_executed": False,
        "interpretation_scope": {
            "causal_claim_allowed": False,
            "corrective_model_result_claimed": False,
            "capability_claim_allowed": False,
            "checkpoint_promotion_allowed": False,
        },
        "forbidden_operation_counts": {
            "new_rollout_runs": 0,
            "training_runs": 0,
            "hyperparameter_searches": 0,
            "checkpoint_selections": 0,
            "checkpoint_modifications": 0,
            "website_dataset_loads": 0,
            "locked_test_loads": 0,
            "arena_games": 0,
            "website_shadow_games": 0,
            "website_games": 0,
            "model_controlled_website_actions": 0,
            "checkpoint_promotions": 0,
            "capability_claims": 0,
        },
        "status": "completed",
    }
    output_path.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return result


if __name__ == "__main__":
    run()
