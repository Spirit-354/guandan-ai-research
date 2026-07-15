from __future__ import annotations

import argparse
from collections import Counter
import json
import math
import os
from pathlib import Path

import danzero_features as features
import website_teacher_preference as preference
import website_teacher_preference_evidence_audit as source_audit


SCHEMA_VERSION = (
    "website_teacher_preference_residual_corrective_remaining_evidence_audit_v1"
)
DIAGNOSIS_PATH = Path(
    "website_teacher_preference_residual_corrective_failure_diagnosis_v1.json"
)
TRAINING_REPORT_PATH = Path(
    "website_teacher_preference_residual_corrective_training_v1.json"
)
CHECKPOINT_PATH = Path(
    "models_website_teacher_preference_residual_corrective_v1/"
    "website_teacher_preference_residual_corrective_final.pth"
)
DATASET_PATH = Path("website_teacher_preference_corrective_dataset_v2.pth")
MANIFEST_PATH = Path("website_teacher_preference_corrective_dataset_v2_manifest.json")
TEACHER_PATH = Path("website_information_set_teacher_dataset_v6.pth")
SPLIT_PATH = Path("website_teacher_preference_split_v1.json")
STAGE_6_9_PATH = Path(
    "website_teacher_preference_corrective_residual_train_confirmation_v1.json"
)
STAGE_6_8_PATH = Path(
    "website_teacher_preference_corrective_residual_evidence_audit_v1.json"
)
STAGE_6_7_PATH = Path("website_teacher_preference_corrective_failure_diagnosis_v1.json")
ARENA_PATH = Path("website_teacher_preference_arena_smoke20_v1.json")
OUTPUT_PATH = Path(
    "website_teacher_preference_residual_corrective_remaining_evidence_audit_v1.json"
)
EXPECTED_HASHES = {
    "stage_6_12_diagnosis": (
        "e8e12f4fd259bc0c2689100d08bdfb3b71662e29c8af0f1e1013fbc6e9573e9f"
    ),
    "stage_6_11_training_report": (
        "307b92eca7aef2d7fa927dec71f1e2ccd8b87b71d2336c5630f39c24d0a176dd"
    ),
    "stage_6_11_checkpoint": (
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
    "stage_6_8_evidence_audit": (
        "676232033f07051670b4407f15aca9f3939d9754ac2dcf4d078957263a1e2a6b"
    ),
    "stage_6_7_diagnosis": (
        "2b4359470e74f5eae28d6589477aca5f929ae6b5b88e094fa86209bf4328163d"
    ),
    "stage_6_1_arena": (
        "aa45da9de202194102fe8d11e612ad3eb4b51177fd910b9a7948836afd2a1fe6"
    ),
}
FROZEN_PATHS = {
    "stage_6_12_diagnosis": DIAGNOSIS_PATH,
    "stage_6_11_training_report": TRAINING_REPORT_PATH,
    "stage_6_11_checkpoint": CHECKPOINT_PATH,
    "corrective_dataset_v2": DATASET_PATH,
    "corrective_manifest_v2": MANIFEST_PATH,
    "teacher_dataset": TEACHER_PATH,
    "split_manifest": SPLIT_PATH,
    "stage_6_9_confirmation": STAGE_6_9_PATH,
    "stage_6_8_evidence_audit": STAGE_6_8_PATH,
    "stage_6_7_diagnosis": STAGE_6_7_PATH,
    "stage_6_1_arena": ARENA_PATH,
}
EXPECTED_TRAIN_TARGETS = [
    ("13957", 14, 17),
    ("14077", 10, 0),
    ("14038", 12, 3),
    ("13959", 7, 5),
    ("14025", 20, 1),
    ("13872", 4, 19),
]
EXPECTED_DEVELOPMENT_TARGETS = [
    ("13992", 16, 7),
    ("14074", 9, 9),
    ("13871", 9, 9),
]


def load_json(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError(f"{path} must contain a JSON object")
    return payload


def verify_frozen_hashes() -> dict[str, str]:
    actual = {name: source_audit._sha256(path) for name, path in FROZEN_PATHS.items()}
    for name, expected in EXPECTED_HASHES.items():
        if actual.get(name) != expected:
            raise RuntimeError(f"{name} SHA-256 mismatch")
    return actual


def ensure_unused_output(path: Path = OUTPUT_PATH) -> None:
    temporary = path.with_name(f"{path.name}.tmp")
    if path.exists() or temporary.exists():
        raise RuntimeError(f"remaining evidence audit output already exists: {path}")


def _website_card_to_local(card: str) -> str:
    if card == "B":
        return "小王"
    if card == "R":
        return "大王"
    suit_map = {"S": "黑桃", "H": "红桃", "D": "方块", "C": "梅花"}
    if len(card) < 2 or card[0] not in suit_map:
        raise RuntimeError(f"invalid website card {card!r}")
    rank = "10" if card[1:] == "T" else card[1:]
    return suit_map[card[0]] + rank


def _local_card_to_website(card: str) -> str:
    if card == "小王":
        return "B"
    if card == "大王":
        return "R"
    suit_map = {"黑桃": "S", "红桃": "H", "方块": "D", "梅花": "C"}
    for suit, code in suit_map.items():
        if card.startswith(suit):
            rank = card[len(suit) :]
            return code + ("T" if rank == "10" else rank)
    raise RuntimeError(f"invalid local card {card!r}")


def physical_cards_website(action: list[float]) -> list[str]:
    if len(action) != 54:
        raise RuntimeError("physical action dimension mismatch")
    cards = []
    for card, value in zip(features.CARD_KEYS_54, action):
        count = int(round(float(value)))
        if count < 0 or not math.isclose(float(value), count, abs_tol=1e-7):
            raise RuntimeError("physical action contains a non-count value")
        cards.extend([_local_card_to_website(card)] * count)
    return cards


def candidate_action_vector(candidate: dict) -> list[float]:
    cards = candidate.get("physical_cards_website")
    if not isinstance(cards, list):
        raise RuntimeError("candidate physical-card identity missing")
    local_cards = [_website_card_to_local(str(card)) for card in cards]
    return [float(value) for value in features.encode_physical_action_54(local_cards)]


def validate_stage_6_12(diagnosis: dict, report: dict, arena: dict) -> dict:
    if diagnosis.get("schema_version") != (
        "website_teacher_preference_residual_corrective_failure_diagnosis_v1"
    ) or diagnosis.get("status") != "completed":
        raise RuntimeError("Stage 6.12 diagnosis schema/status mismatch")
    scoring = diagnosis.get("scoring_accounting") or {}
    required_scoring = {
        "diagnostic_run_count": 1,
        "unique_teacher_state_count": 22,
        "recorded_legal_action_count": 934,
        "legal_action_score_count": 934,
        "source_duplicate_action_vector_count": 8,
        "dropped_state_count": 0,
        "duplicate_state_count": 0,
        "dimension_invalid_action_count": 0,
        "nonfinite_q_count": 0,
        "illegal_recorded_action_count": 0,
        "dropped_action_count": 0,
        "duplicate_action_scoring_count": 0,
        "reconstructed_action_count": 0,
    }
    if any(scoring.get(key) != value for key, value in required_scoring.items()):
        raise RuntimeError("Stage 6.12 scoring conclusion mismatch")
    expected_aggregates = {
        "pipeline_train": (18, 889, 12, 0, 6, 0, 6, 13),
        "pipeline_development": (4, 45, 1, 0, 3, 0, 3, 11),
        "overall": (22, 934, 13, 0, 9, 0, 9, 24),
    }
    aggregates = diagnosis.get("aggregates") or {}
    for partition, expected in expected_aggregates.items():
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
        if actual != expected:
            raise RuntimeError(f"Stage 6.12 {partition} aggregate mismatch")
    reproduction = diagnosis.get("stage_6_11_metric_reproduction") or {}
    if (
        reproduction.get("exact_match") is not True
        or reproduction.get("actual") != reproduction.get("frozen")
        or reproduction.get("frozen") != report.get("final_metrics")
        or reproduction.get("evaluation_accounting", {}).get("pair_evaluation_count")
        != 60
        or reproduction.get("evaluation_accounting", {}).get(
            "action_value_evaluation_count"
        )
        != 120
    ):
        raise RuntimeError("Stage 6.11 frozen metric reproduction mismatch")
    validation = diagnosis.get("stage_6_11_validation") or {}
    if validation != {
        "training_run_count": 1,
        "development_training_use_count": 0,
        "checkpoint_reload_verified": True,
        "metrics_and_prediction_digests_reproduced": True,
    }:
        raise RuntimeError("Stage 6.11 validation conclusion mismatch")
    if (
        sum((diagnosis.get("forbidden_operation_counts") or {}).values()) != 0
        or arena.get("completed_games") != 20
        or arena.get("model_wins") != 0
        or arena.get("baseline_wins") != 20
        or arena.get("early_screen_continuation_allowed") is not False
        or arena.get("checkpoint_promotion_allowed") is not False
        or arena.get("capability_claim_allowed") is not False
    ):
        raise RuntimeError("frozen rejection/forbidden conclusion mismatch")
    return {
        "state_count": 22,
        "full_set_action_score_count": 934,
        "teacher_top1_count": 13,
        "behavior_top1_count": 0,
        "other_top1_count": 9,
        "pass_top1_count": 0,
        "stage_6_11_metrics_and_prediction_digests_exact": True,
        "model_loaded_or_scored": False,
        "stage_6_1_early_screen_continuation_allowed": False,
    }


def extract_remaining_targets(
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
    if len(residual_states) != 9:
        raise RuntimeError("Stage 6.12 must contain exactly nine residual states")
    targets = []
    seen = set()
    for state in residual_states:
        key = (str(state["game_id"]), int(state["turn_index"]))
        sample = sample_by_key.get(key)
        if sample is None or key in seen:
            raise RuntimeError("remaining target missing or duplicated")
        seen.add(key)
        actions = sample.get("legal_actions") or []
        q_values = state.get("legal_action_q_values") or []
        if len(actions) != len(q_values) or not actions:
            raise RuntimeError("remaining legal-action/Q accounting mismatch")
        if source_audit._action_order_sha256(actions) != state.get(
            "legal_action_order_sha256"
        ):
            raise RuntimeError("remaining legal-action order mismatch")
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
            raise RuntimeError("remaining preference action identity is ambiguous")
        teacher_index = teacher_matches[0]
        if (
            top1_index != state.get("top1_index")
            or teacher_index != state.get("teacher_action_index")
            or behavior_matches[0] != state.get("behavior_action_index")
            or top1_index in {teacher_index, behavior_matches[0]}
            or q_values[top1_index] <= q_values[teacher_index]
        ):
            raise RuntimeError("remaining top1 identity/ranking mismatch")
        if state.get("teacher_rank") != 1 + sum(
            value > q_values[teacher_index] for value in q_values
        ):
            raise RuntimeError("remaining teacher rank mismatch")
        partition = (
            "pipeline_train"
            if key[0] in train_ids
            else "pipeline_development" if key[0] in development_ids else None
        )
        if partition is None or partition != state.get("pipeline_partition"):
            raise RuntimeError("remaining target partition mismatch")
        same_vector_indices = [
            index for index, action in enumerate(actions) if action == actions[top1_index]
        ]
        target = {
            "game_id": key[0],
            "turn_index": key[1],
            "pipeline_partition": partition,
            "legal_action_count": len(actions),
            "legal_action_order_sha256": state["legal_action_order_sha256"],
            "teacher_action_index": teacher_index,
            "teacher_action_sha256": source_audit._action_sha256(
                actions[teacher_index]
            ),
            "teacher_rank": int(state["teacher_rank"]),
            "top1_action_index": top1_index,
            "top1_action_sha256": source_audit._action_sha256(actions[top1_index]),
            "top1_same_vector_recorded_indices": same_vector_indices,
            "top1_physical_cards_website": physical_cards_website(
                actions[top1_index]
            ),
            "teacher_physical_cards_website": physical_cards_website(
                actions[teacher_index]
            ),
            "physical_identity_derivation": "decoded_from_frozen_physical_action_54",
        }
        if same_vector_indices != [top1_index]:
            raise RuntimeError("remaining top1 vector mapping is ambiguous")
        targets.append(target)
    train_actual = [
        (item["game_id"], item["turn_index"], item["top1_action_index"])
        for item in targets
        if item["pipeline_partition"] == "pipeline_train"
    ]
    development_actual = [
        (item["game_id"], item["turn_index"], item["top1_action_index"])
        for item in targets
        if item["pipeline_partition"] == "pipeline_development"
    ]
    if train_actual != EXPECTED_TRAIN_TARGETS:
        raise RuntimeError("pipeline-train remaining target identity mismatch")
    if development_actual != EXPECTED_DEVELOPMENT_TARGETS:
        raise RuntimeError("pipeline-development remaining target identity mismatch")
    return targets, sample_by_key


def validate_stage_6_9(confirmation: dict) -> dict[tuple[str, int], dict]:
    cases = confirmation.get("case_results") or []
    if (
        confirmation.get("schema_version")
        != "website_teacher_preference_corrective_residual_train_confirmation_v1"
        or confirmation.get("status") != "completed"
        or confirmation.get("completed_rollouts") != 256
        or confirmation.get("directional_classification_counts")
        != {
            "teacher_over_residual_supported": 4,
            "residual_over_teacher_supported": 0,
            "inconclusive": 4,
        }
        or len(cases) != 8
        or any(
            int(value) != 0
            for value in (confirmation.get("forbidden_operation_counts") or {}).values()
        )
    ):
        raise RuntimeError("Stage 6.9 confirmation contract mismatch")
    result = {
        (str(case["game_id"]), int(case["turn_index"])): case for case in cases
    }
    if len(result) != 8:
        raise RuntimeError("Stage 6.9 case identity is not unique")
    return result


def validate_stage_6_8(audit: dict) -> dict[tuple[str, int], dict]:
    entries = audit.get("pipeline_train_target_audits") or []
    if (
        audit.get("schema_version")
        != "website_teacher_preference_corrective_residual_evidence_audit_v1"
        or audit.get("status") != "completed"
        or len(entries) != 8
        or audit.get("source_evidence_file_count") != 6
        or audit.get("development_isolation", {}).get("identity_only_target_count")
        != 3
        or any(
            int(value) != 0
            for value in (audit.get("forbidden_operation_counts") or {}).values()
        )
    ):
        raise RuntimeError("Stage 6.8 evidence audit contract mismatch")
    result = {
        (str(item["game_id"]), int(item["turn_index"])): item for item in entries
    }
    if len(result) != 8:
        raise RuntimeError("Stage 6.8 audit identity is not unique")
    return result


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


def _stage_6_9_provenance(
    target: dict, sample: dict, case: dict | None
) -> dict:
    if case is None:
        return {
            "case_present": False,
            "residual_action_identity_matches_current_top1": False,
            "applicable_to_current_top1": False,
            "used_as_current_direct_evidence": False,
        }
    candidates = case.get("candidate_results") or []
    if [item.get("role") for item in candidates] != ["teacher", "residual"]:
        raise RuntimeError("Stage 6.9 candidate roles mismatch")
    teacher, residual = candidates
    teacher_index = int(teacher["action_index"])
    residual_index = int(residual["action_index"])
    actions = sample["legal_actions"]
    if (
        actions[teacher_index] != sample["teacher_action"]
        or source_audit._action_sha256(actions[teacher_index])
        != teacher["action_sha256"]
        or source_audit._action_sha256(actions[residual_index])
        != residual["action_sha256"]
        or Counter(physical_cards_website(actions[teacher_index]))
        != Counter(teacher["physical_cards_website"])
        or Counter(physical_cards_website(actions[residual_index]))
        != Counter(residual["physical_cards_website"])
    ):
        raise RuntimeError("Stage 6.9 frozen action identity mismatch")
    identity_matches = (
        residual_index == target["top1_action_index"]
        and residual["action_sha256"] == target["top1_action_sha256"]
    )
    metrics = case.get("metrics") or {}
    direction = metrics.get("directional_classification")
    if direction not in {
        "teacher_over_residual_supported",
        "residual_over_teacher_supported",
        "inconclusive",
    }:
        raise RuntimeError("Stage 6.9 directional classification mismatch")
    return {
        "case_present": True,
        "residual_action_index": residual_index,
        "residual_action_sha256": residual["action_sha256"],
        "residual_physical_cards_website": residual["physical_cards_website"],
        "directional_classification": direction,
        "teacher_over_residual_failure_reasons": metrics.get(
            "teacher_over_residual_failure_reasons"
        ),
        "residual_over_teacher_failure_reasons": metrics.get(
            "residual_over_teacher_failure_reasons"
        ),
        "residual_action_identity_matches_current_top1": identity_matches,
        "applicable_to_current_top1": identity_matches,
        "used_as_current_direct_evidence": identity_matches,
    }


def audit_train_target(
    target: dict,
    sample: dict,
    evidence_path: Path,
    evidence: dict,
    stage_6_9_case: dict | None,
    stage_6_8_entry: dict | None,
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
    metadata_status = "absent_in_legacy_source"
    if metadata:
        if len(metadata) != len(sample["legal_actions"]):
            raise RuntimeError("train source legal-action metadata count mismatch")
        top_cards = metadata[target["top1_action_index"]].get("cards")
        teacher_cards = metadata[target["teacher_action_index"]].get("cards")
        if (
            Counter(top_cards or []) != Counter(target["top1_physical_cards_website"])
            or Counter(teacher_cards or [])
            != Counter(target["teacher_physical_cards_website"])
        ):
            raise RuntimeError("train source physical metadata mismatch")
        metadata_status = "exact_source_legal_action_metadata"
    candidates = case.get("candidate_results") or []
    top_action = sample["legal_actions"][target["top1_action_index"]]
    teacher_action = sample["legal_actions"][target["teacher_action_index"]]
    top_matches = [
        item for item in candidates if candidate_action_vector(item) == top_action
    ]
    teacher_matches = [
        item for item in candidates if candidate_action_vector(item) == teacher_action
    ]
    if len(top_matches) > 1 or len(teacher_matches) != 1:
        raise RuntimeError("train source candidate mapping is ambiguous")
    top_candidate = top_matches[0] if top_matches else None
    teacher_candidate = teacher_matches[0]
    provenance = _stage_6_9_provenance(target, sample, stage_6_9_case)
    if provenance["applicable_to_current_top1"]:
        direction = provenance["directional_classification"]
        classification = {
            "teacher_over_residual_supported": "teacher_over_current_top1_supported",
            "residual_over_teacher_supported": "current_top1_over_teacher_supported",
            "inconclusive": "direct_paired_comparison_inconclusive",
        }[direction]
        insufficiency = (
            []
            if direction != "inconclusive"
            else [
                "stage_6_9_direct_comparison_inconclusive",
                *[
                    f"teacher_direction:{reason}"
                    for reason in provenance["teacher_over_residual_failure_reasons"]
                ],
                *[
                    f"residual_direction:{reason}"
                    for reason in provenance["residual_over_teacher_failure_reasons"]
                ],
            ]
        )
        evidence_source = "stage_6_9_exact_action_confirmation"
    elif top_candidate is None:
        classification = "current_top1_not_evaluated_as_source_candidate"
        insufficiency = ["current_top1_candidate_result_missing"]
        evidence_source = "direct_source_rollout_evidence"
    else:
        classification = "source_candidates_present_without_direct_paired_comparison"
        insufficiency = [
            "current_top1_and_teacher_candidates_present",
            "direct_teacher_vs_current_top1_statistics_missing",
        ]
        evidence_source = "direct_source_rollout_evidence"
    old_identity_matches = bool(
        stage_6_8_entry is not None
        and int(stage_6_8_entry["top1_action_index"]) == target["top1_action_index"]
        and stage_6_8_entry["top1_action_sha256"] == target["top1_action_sha256"]
    )
    source_summary = source_audit.evidence_file_summary(evidence_path, evidence)
    return {
        **target,
        "source_rollout_evidence": evidence_path.name,
        "source_rollout_evidence_sha256": source_summary["sha256"],
        "source_state_match": True,
        "source_legal_actions_match": True,
        "action_mapping_reconstructed": False,
        "action_mapping_substituted": False,
        "source_physical_metadata_status": metadata_status,
        "top1_candidate_match_count": len(top_matches),
        "teacher_candidate_match_count": len(teacher_matches),
        "top1_candidate_evidence": _candidate_summary(top_candidate),
        "teacher_candidate_evidence": _candidate_summary(teacher_candidate),
        "source_hidden_card_sampling_method": evidence.get(
            "hidden_card_sampling_method"
        ),
        "source_continuation_profiles": evidence.get("continuation_profiles"),
        "stage_6_8_provenance": {
            "target_present": stage_6_8_entry is not None,
            "action_identity_matches_current_top1": old_identity_matches,
            "old_action_index": (
                stage_6_8_entry.get("top1_action_index")
                if stage_6_8_entry is not None
                else None
            ),
            "old_action_sha256": (
                stage_6_8_entry.get("top1_action_sha256")
                if stage_6_8_entry is not None
                else None
            ),
            "old_evidence_classification": (
                stage_6_8_entry.get("evidence_classification")
                if stage_6_8_entry is not None
                else None
            ),
            "used_as_current_direct_evidence": False,
        },
        "stage_6_9_provenance": provenance,
        "current_top1_evidence_source": evidence_source,
        "evidence_classification": classification,
        "insufficiency_reasons": insufficiency,
        "teacher_over_current_top1_supported": (
            classification == "teacher_over_current_top1_supported"
        ),
        "current_top1_over_teacher_supported": (
            classification == "current_top1_over_teacher_supported"
        ),
    }


def aggregate_train_audits(audits: list[dict]) -> dict:
    classes = Counter(item["evidence_classification"] for item in audits)
    return {
        "target_count": len(audits),
        "source_file_count": len({item["source_rollout_evidence"] for item in audits}),
        "current_top1_absent_from_source_legal_actions_count": 0,
        "current_top1_not_evaluated_as_source_candidate_count": classes[
            "current_top1_not_evaluated_as_source_candidate"
        ],
        "source_candidates_present_without_direct_paired_comparison_count": classes[
            "source_candidates_present_without_direct_paired_comparison"
        ],
        "direct_paired_comparison_inconclusive_count": classes[
            "direct_paired_comparison_inconclusive"
        ],
        "teacher_over_current_top1_supported_count": classes[
            "teacher_over_current_top1_supported"
        ],
        "current_top1_over_teacher_supported_count": classes[
            "current_top1_over_teacher_supported"
        ],
        "stage_6_9_exact_action_evidence_count": sum(
            item["stage_6_9_provenance"]["applicable_to_current_top1"]
            for item in audits
        ),
        "stage_6_9_different_action_nontransfer_count": sum(
            item["stage_6_9_provenance"]["case_present"]
            and not item["stage_6_9_provenance"]["applicable_to_current_top1"]
            for item in audits
        ),
        "insufficient_evidence_count": sum(
            bool(item["insufficiency_reasons"]) for item in audits
        ),
        "ambiguous_mapping_count": 0,
    }


def validate_context() -> dict:
    frozen_hashes = verify_frozen_hashes()
    diagnosis = load_json(DIAGNOSIS_PATH)
    report = load_json(TRAINING_REPORT_PATH)
    split = load_json(SPLIT_PATH)
    stage_6_9 = load_json(STAGE_6_9_PATH)
    stage_6_8 = load_json(STAGE_6_8_PATH)
    arena = load_json(ARENA_PATH)
    conclusion = validate_stage_6_12(diagnosis, report, arena)
    samples, _summary, teacher_hash = preference.load_teacher_dataset(TEACHER_PATH)
    if teacher_hash != frozen_hashes["teacher_dataset"]:
        raise RuntimeError("loaded teacher dataset hash mismatch")
    targets, sample_by_key = extract_remaining_targets(diagnosis, samples, split)
    train_targets = [
        item for item in targets if item["pipeline_partition"] == "pipeline_train"
    ]
    development_targets = [
        item
        for item in targets
        if item["pipeline_partition"] == "pipeline_development"
    ]
    return {
        "frozen_hashes": frozen_hashes,
        "stage_6_12_conclusion": conclusion,
        "targets": targets,
        "train_targets": train_targets,
        "development_targets": development_targets,
        "sample_by_key": sample_by_key,
        "stage_6_9_by_key": validate_stage_6_9(stage_6_9),
        "stage_6_8_by_key": validate_stage_6_8(stage_6_8),
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
        train_audits.append(
            audit_train_target(
                target,
                sample,
                path,
                evidence,
                context["stage_6_9_by_key"].get(key),
                context["stage_6_8_by_key"].get(key),
            )
        )
    aggregates = aggregate_train_audits(train_audits)
    expected_aggregates = {
        "target_count": 6,
        "source_file_count": 6,
        "current_top1_absent_from_source_legal_actions_count": 0,
        "current_top1_not_evaluated_as_source_candidate_count": 2,
        "source_candidates_present_without_direct_paired_comparison_count": 1,
        "direct_paired_comparison_inconclusive_count": 3,
        "teacher_over_current_top1_supported_count": 0,
        "current_top1_over_teacher_supported_count": 0,
        "stage_6_9_exact_action_evidence_count": 3,
        "stage_6_9_different_action_nontransfer_count": 2,
        "insufficient_evidence_count": 6,
        "ambiguous_mapping_count": 0,
    }
    if aggregates != expected_aggregates:
        raise RuntimeError("frozen remaining train evidence aggregate mismatch")
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
    ]
    forbidden = {
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
        "website_dataset_loads": 0,
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
    return {
        "schema_version": SCHEMA_VERSION,
        "status": "completed",
        "frozen_inputs": {
            "paths": {name: str(path) for name, path in FROZEN_PATHS.items()},
            "sha256": context["frozen_hashes"],
        },
        "stage_6_12_conclusion_reproduction": context["stage_6_12_conclusion"],
        "target_reproduction": {
            "expected_target_count": 9,
            "reproduced_target_count": 9,
            "pipeline_train_target_count": 6,
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
        "future_counterfactual_manifest_case_count": 6,
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
        raise RuntimeError("a frozen input changed during remaining evidence audit")
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
        raise RuntimeError("independent remaining evidence reproduction mismatch")
    if verify_frozen_hashes() != context["frozen_hashes"]:
        raise RuntimeError("a frozen input changed during independent audit")
    _verify_source_hashes(saved)
    result = {
        "status": "passed",
        "stage_6_12_conclusion_exact_without_model_scoring": True,
        "target_identities_and_physical_cards_exact": True,
        "source_hashes_exact": True,
        "stage_6_9_action_nontransfer_exact": True,
        "classifications_exact": True,
        "partition_counts_and_aggregates_exact": True,
        "development_source_evidence_read_count": 0,
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
