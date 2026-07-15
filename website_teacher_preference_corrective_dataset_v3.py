from __future__ import annotations

import argparse
import copy
from collections import Counter, defaultdict
import json
import math
from pathlib import Path

import website_teacher_preference as preference
import website_teacher_preference_corrective_dataset as v1_builder
import website_teacher_preference_corrective_dataset_v2 as v2_builder
import website_teacher_preference_residual_corrective_remaining_confirmation as confirmation
import website_teacher_preference_residual_corrective_remaining_parallel_confirmation as formal


FORMAT_VERSION = "website_teacher_preference_corrective_dataset_v3"
MANIFEST_SCHEMA_VERSION = "website_teacher_preference_corrective_dataset_v3_manifest"
CONFIRMATION_PATH = confirmation.OUTPUT_PATH
FORMAL_IMPLEMENTATION_PATH = Path(
    "website_teacher_preference_residual_corrective_remaining_parallel_confirmation.py"
)
V2_DATASET_PATH = v2_builder.DATASET_OUTPUT_PATH
V2_MANIFEST_PATH = v2_builder.MANIFEST_OUTPUT_PATH
TEACHER_PATH = v2_builder.TEACHER_PATH
SPLIT_PATH = v2_builder.SPLIT_PATH
DATASET_OUTPUT_PATH = Path("website_teacher_preference_corrective_dataset_v3.pth")
MANIFEST_OUTPUT_PATH = Path(
    "website_teacher_preference_corrective_dataset_v3_manifest.json"
)
EXPECTED_HASHES = {
    "stage_6_14e_confirmation": (
        "450e89f780a33dd543f49f029e735f7fb32e11cd657163c52e6a4301d21f7eb5"
    ),
    "stage_6_14e_formal_implementation": (
        "972b67ed585e9a96f9e8be55b70d0b6585a7e499f6dc692c2861d5e636b9e55d"
    ),
    "corrective_dataset_v2": (
        "40024f7c064f0ebb7999c4ac0f7bc85d77b759a23956cbe596756763d4009d4d"
    ),
    "corrective_dataset_v2_manifest": (
        "ce5141f6254218d9230b15117a88d3c5e6bd374839bcf5fc77b393e2599ec353"
    ),
}
SUPPORTED = [("13957", 14, 17), ("14038", 12, 3)]
INCONCLUSIVE = [("13872", 4, 19)]
EXCLUDED_TRAIN = [("14077", 10, 0), ("13959", 7, 5), ("14025", 20, 1)]
DEVELOPMENT = [("13992", 16), ("14074", 9), ("13871", 9)]
WEIGHT_FIELDS = v2_builder.WEIGHT_FIELDS


def load_json(path: Path) -> dict:
    return v2_builder.load_json(path)


def frozen_paths() -> dict[str, Path]:
    return {
        **confirmation.FROZEN_PATHS,
        "stage_6_14p_parallel_equivalence": formal.PARALLEL_ARTIFACT_PATH,
        "stage_6_14p_parallel_implementation": formal.PARALLEL_IMPLEMENTATION_PATH,
        "stage_6_14_confirmation_implementation": (
            formal.CONFIRMATION_IMPLEMENTATION_PATH
        ),
        "stage_6_14e_confirmation": CONFIRMATION_PATH,
        "stage_6_14e_formal_implementation": FORMAL_IMPLEMENTATION_PATH,
        "corrective_dataset_v2": V2_DATASET_PATH,
        "corrective_dataset_v2_manifest": V2_MANIFEST_PATH,
    }


def verify_frozen_inputs() -> dict[str, str]:
    recursive = formal.verify_frozen_inputs()
    specific_paths = {
        "stage_6_14e_confirmation": CONFIRMATION_PATH,
        "stage_6_14e_formal_implementation": FORMAL_IMPLEMENTATION_PATH,
        "corrective_dataset_v2": V2_DATASET_PATH,
        "corrective_dataset_v2_manifest": V2_MANIFEST_PATH,
    }
    specific = {
        name: v1_builder.sha256(path) for name, path in specific_paths.items()
    }
    for name, expected in EXPECTED_HASHES.items():
        if specific[name] != expected:
            raise RuntimeError(f"{name} SHA-256 mismatch")
    return {**recursive, **specific}


def load_v2_dataset() -> dict:
    import torch

    payload = torch.load(V2_DATASET_PATH, map_location="cpu", weights_only=False)
    if not isinstance(payload, dict):
        raise RuntimeError("corrective dataset v2 must contain a dictionary")
    return payload


def pair_semantic_sha256(pair: dict) -> str:
    return v2_builder.pair_semantic_sha256(pair)


def validate_v2_context(
    payload: dict,
    manifest: dict,
    teacher_samples: list[dict],
    split: dict,
) -> None:
    pairs = payload.get("pairs") or []
    samples = payload.get("frozen_base_samples") or []
    pair_ids = [pair.get("pair_id") for pair in pairs]
    semantic_hashes = [pair_semantic_sha256(pair) for pair in pairs]
    manifest_ids = list(manifest.get("frozen_v1_pair_ids") or []) + list(
        manifest.get("new_pair_ids") or []
    )
    manifest_semantics = list(
        manifest.get("frozen_v1_pair_semantic_sha256") or []
    ) + list(manifest.get("new_pair_semantic_sha256") or [])
    train_ids = {str(value) for value in split.get("pipeline_train_game_ids") or []}
    development_ids = {
        str(value) for value in split.get("pipeline_development_game_ids") or []
    }
    if (
        payload.get("format") != v2_builder.FORMAT_VERSION
        or manifest.get("schema_version") != v2_builder.MANIFEST_SCHEMA_VERSION
        or manifest.get("status") != "completed"
        or manifest.get("dataset_sha256") != EXPECTED_HASHES["corrective_dataset_v2"]
        or len(pairs) != 32
        or len(set(pair_ids)) != 32
        or pair_ids != manifest_ids
        or semantic_hashes != manifest_semantics
    ):
        raise RuntimeError("frozen corrective dataset v2 contract mismatch")
    if (
        len(samples) != 22
        or payload.get("frozen_base_sample_count") != 22
        or v1_builder.canonical_sha256(samples)
        != payload.get("frozen_base_samples_sha256")
        or [v1_builder.canonical_sha256(sample) for sample in samples]
        != payload.get("frozen_base_sample_sha256")
        or v1_builder.canonical_sha256(samples)
        != v1_builder.canonical_sha256(teacher_samples)
    ):
        raise RuntimeError("frozen v2 teacher samples changed")
    partition_counts = Counter(pair.get("pipeline_partition") for pair in pairs)
    source_counts = Counter(pair.get("pair_source") for pair in pairs)
    if (
        len(train_ids) != 18
        or len(development_ids) != 4
        or train_ids & development_ids
        or split.get("overlap_game_ids") != []
        or split.get("dropped_game_ids") != []
        or partition_counts
        != Counter({"pipeline_train": 28, "pipeline_development": 4})
        or source_counts
        != Counter(
            {
                "frozen_teacher_v6": 22,
                "stage_6_4_train_confirmation": 6,
                "stage_6_9_residual_train_confirmation": 4,
            }
        )
    ):
        raise RuntimeError("frozen v2 pair/split accounting mismatch")
    if any(
        int(value) != 0
        for value in (payload.get("forbidden_operation_counts") or {}).values()
    ):
        raise RuntimeError("frozen v2 dataset contains a forbidden operation")


def validate_and_select_confirmation(payload: dict) -> tuple[list[dict], list[dict]]:
    formal.validate_parallel_execution_metadata(payload)
    confirmation.validate_completed_result(payload)
    cases = payload.get("case_results") or []
    actual = [
        (
            str(case.get("game_id")),
            int(case.get("turn_index")),
            int((case.get("candidate_results") or [{}, {}])[1].get("action_index", -1)),
            case.get("metrics", {}).get("directional_classification"),
        )
        for case in cases
    ]
    expected = [
        (game_id, turn_index, action_index, "teacher_over_residual_supported")
        for game_id, turn_index, action_index in SUPPORTED
    ] + [
        (game_id, turn_index, action_index, "inconclusive")
        for game_id, turn_index, action_index in INCONCLUSIVE
    ]
    supported = cases[:2]
    inconclusive = cases[2:]
    supported_manifest_keys = [
        (str(item["game_id"]), int(item["turn_index"]))
        for item in payload.get("supported_comparison_manifest") or []
    ]
    if (
        payload.get("schema_version") != confirmation.SCHEMA_VERSION
        or payload.get("status") != "completed"
        or actual != expected
        or supported_manifest_keys != [(item[0], item[1]) for item in SUPPORTED]
        or payload.get("directional_classification_counts")
        != {
            "teacher_over_residual_supported": 2,
            "residual_over_teacher_supported": 0,
            "inconclusive": 1,
        }
    ):
        raise RuntimeError("Stage 6.14E case accounting mismatch")
    for case in supported:
        metrics = case.get("metrics") or {}
        candidates = case.get("candidate_results") or []
        if (
            case.get("pipeline_partition") != "pipeline_train"
            or metrics.get("teacher_over_residual_supported") is not True
            or metrics.get("teacher_over_residual_failure_reasons") != []
            or metrics.get("residual_over_teacher_supported") is not False
            or [item.get("role") for item in candidates] != ["teacher", "residual"]
            or any(item.get("completed_rollout_count") != 16 for item in candidates)
            or any(item.get("failure_count") != 0 for item in candidates)
            or any(item.get("failures") != [] for item in candidates)
        ):
            raise RuntimeError("Stage 6.14E supported case is not fully qualified")
    excluded = payload.get("excluded_inconclusive_train") or []
    heldout = payload.get("pipeline_development_heldout") or []
    if [
        (str(item["game_id"]), int(item["turn_index"]), int(item["top1_action_index"]))
        for item in excluded
    ] != EXCLUDED_TRAIN or [
        (str(item["game_id"]), int(item["turn_index"])) for item in heldout
    ] != DEVELOPMENT:
        raise RuntimeError("Stage 6.14E exclusions changed")
    for item in excluded + heldout:
        if (
            item.get("source_sample_mapping_count") != 0
            or item.get("case_execution_count") != 0
            or item.get("rollout_count") != 0
            or item.get("used_for_confirmation_or_design") is not False
        ):
            raise RuntimeError("an excluded Stage 6.14E case was used")
    if sum((payload.get("forbidden_operation_counts") or {}).values()) != 0:
        raise RuntimeError("Stage 6.14E contains a forbidden operation")
    return supported, inconclusive


def remaining_corrective_pair(sample: dict, base_index: int, case: dict) -> dict:
    teacher, current_top1 = case["candidate_results"]
    teacher_index = int(teacher["action_index"])
    top1_index = int(current_top1["action_index"])
    legal_actions = sample["legal_actions"]
    if (
        teacher_index < 0
        or top1_index < 0
        or teacher_index >= len(legal_actions)
        or top1_index >= len(legal_actions)
        or legal_actions[teacher_index] != sample["teacher_action"]
        or teacher["action_sha256"]
        != v1_builder.action_sha256(sample["teacher_action"])
        or current_top1["action_sha256"]
        != v1_builder.action_sha256(legal_actions[top1_index])
        or teacher["physical_cards_website"] != sample["teacher_physical_cards"]
        or legal_actions[top1_index] == sample["teacher_action"]
        or legal_actions[top1_index] == sample["behavior_action"]
    ):
        raise RuntimeError("Stage 6.14E remaining-top1 action identity mismatch")
    return {
        "pair_id": (
            f"remaining_corrective:{sample['game_id']}:{sample['turn_index']}:"
            "teacher_vs_current_top1"
        ),
        "pair_source": "stage_6_14e_remaining_train_confirmation",
        "preference_target": "teacher_action_beats_current_top1",
        "game_id": str(sample["game_id"]),
        "turn_index": int(sample["turn_index"]),
        "pipeline_partition": "pipeline_train",
        "base_sample_index": base_index,
        "state": copy.deepcopy(sample["state"]),
        "state_dim": int(sample["state_dim"]),
        "preferred_action": copy.deepcopy(sample["teacher_action"]),
        "rejected_action": copy.deepcopy(legal_actions[top1_index]),
        "action_dim": int(sample["action_dim"]),
        "preferred_action_index": teacher_index,
        "rejected_action_index": top1_index,
        "preferred_action_sha256": teacher["action_sha256"],
        "rejected_action_sha256": current_top1["action_sha256"],
        "preferred_physical_cards_website": copy.deepcopy(
            teacher["physical_cards_website"]
        ),
        "rejected_physical_cards_website": copy.deepcopy(
            current_top1["physical_cards_website"]
        ),
        "source_evidence": str(CONFIRMATION_PATH),
        "source_evidence_sha256": EXPECTED_HASHES["stage_6_14e_confirmation"],
        "source_execution_implementation": str(FORMAL_IMPLEMENTATION_PATH),
        "source_execution_implementation_sha256": EXPECTED_HASHES[
            "stage_6_14e_formal_implementation"
        ],
        "source_metrics": copy.deepcopy(case["metrics"]),
        "hidden_card_sampling_method": (
            "uniform_physical_assignment_given_public_counts_v1"
        ),
        "rollout_count_per_action": 16,
        "continuation_profiles": ["greedy_bot", "tempo_baseline"],
        "locked_test_used": False,
    }


def apply_and_validate_weights(pairs: list[dict]) -> dict:
    for pair in pairs:
        for field in WEIGHT_FIELDS:
            pair.pop(field, None)
    objective = v1_builder.apply_state_balanced_weights(pairs)
    grouped: dict[tuple[str, str, int], list[dict]] = defaultdict(list)
    for pair in pairs:
        grouped[
            (pair["pipeline_partition"], str(pair["game_id"]), int(pair["turn_index"]))
        ].append(pair)
    size_counts = Counter(len(state_pairs) for state_pairs in grouped.values())
    triple_keys = sorted(
        f"{partition}:{game_id}:{turn_index}"
        for (partition, game_id, turn_index), state_pairs in grouped.items()
        if len(state_pairs) == 3
    )
    expected_triples = [
        "pipeline_train:13957:14",
        "pipeline_train:14022:16",
        "pipeline_train:14038:12",
    ]
    if size_counts != Counter({1: 13, 2: 6, 3: 3}) or triple_keys != expected_triples:
        raise RuntimeError("v3 state pair-count distribution mismatch")
    for key, state_pairs in grouped.items():
        expected = 1.0 / len(state_pairs)
        if any(
            not math.isclose(
                pair["within_state_pair_weight"], expected, abs_tol=1e-12
            )
            for pair in state_pairs
        ):
            raise RuntimeError(f"v3 state weight mismatch for {key}")
        if not math.isclose(
            sum(float(pair["within_state_pair_weight"]) for pair in state_pairs),
            1.0,
            abs_tol=1e-12,
        ):
            raise RuntimeError(f"v3 state weights do not sum to one for {key}")
    partition_sums = {
        partition: sum(
            float(pair["partition_normalized_pair_weight"])
            for pair in pairs
            if pair["pipeline_partition"] == partition
        )
        for partition in ("pipeline_train", "pipeline_development")
    }
    if any(
        not math.isclose(value, 1.0, abs_tol=1e-12)
        for value in partition_sums.values()
    ):
        raise RuntimeError("v3 partition weights do not sum to one")
    objective["state_pair_count_distribution"] = {
        "one_pair_state_count": 13,
        "two_pair_state_count": 6,
        "three_pair_state_count": 3,
    }
    objective["three_pair_state_keys"] = triple_keys
    objective["partition_normalized_weight_sums"] = partition_sums
    objective["objective_executed"] = False
    return objective


def build_payload(context: dict) -> tuple[dict, dict]:
    v2_payload = context["v2_payload"]
    samples = v2_payload["frozen_base_samples"]
    supported, inconclusive = validate_and_select_confirmation(
        context["confirmation"]
    )
    sample_by_key = {
        (str(sample["game_id"]), int(sample["turn_index"])): (index, sample)
        for index, sample in enumerate(samples)
    }
    pairs = copy.deepcopy(v2_payload["pairs"])
    v2_semantic_hashes = [pair_semantic_sha256(pair) for pair in pairs]
    existing_rejected_hashes = {
        (str(pair["game_id"]), int(pair["turn_index"]), pair["rejected_action_sha256"])
        for pair in pairs
    }
    new_pairs = []
    for case in supported:
        key = (str(case["game_id"]), int(case["turn_index"]))
        if key not in sample_by_key:
            raise RuntimeError(f"Stage 6.14E state missing from teacher v6: {key}")
        base_index, sample = sample_by_key[key]
        new_pair = remaining_corrective_pair(sample, base_index, case)
        identity = (key[0], key[1], new_pair["rejected_action_sha256"])
        if identity in existing_rejected_hashes:
            raise RuntimeError("Stage 6.14E pair duplicates a frozen rejected action")
        existing_rejected_hashes.add(identity)
        pairs.append(new_pair)
        new_pairs.append(new_pair)
    objective = apply_and_validate_weights(pairs)
    if [pair_semantic_sha256(pair) for pair in pairs[:32]] != v2_semantic_hashes:
        raise RuntimeError("a frozen v2 pair changed outside weight fields")
    pair_ids = [pair["pair_id"] for pair in pairs]
    partition_counts = Counter(pair["pipeline_partition"] for pair in pairs)
    source_counts = Counter(pair["pair_source"] for pair in pairs)
    if (
        len(pairs) != 34
        or len(set(pair_ids)) != 34
        or partition_counts
        != Counter({"pipeline_train": 30, "pipeline_development": 4})
        or source_counts
        != Counter(
            {
                "frozen_teacher_v6": 22,
                "stage_6_4_train_confirmation": 6,
                "stage_6_9_residual_train_confirmation": 4,
                "stage_6_14e_remaining_train_confirmation": 2,
            }
        )
    ):
        raise RuntimeError("corrective dataset v3 pair accounting mismatch")
    excluded_train = context["confirmation"]["excluded_inconclusive_train"]
    heldout = context["confirmation"]["pipeline_development_heldout"]
    exclusions = {
        "frozen_v2_exclusions": copy.deepcopy(v2_payload["exclusions"]),
        "stage_6_14e_inconclusive_pipeline_train": [
            {
                "game_id": str(case["game_id"]),
                "turn_index": int(case["turn_index"]),
                "current_top1_action_index": int(
                    case["candidate_results"][1]["action_index"]
                ),
                "directional_classification": "inconclusive",
                "teacher_over_current_top1_failure_reasons": copy.deepcopy(
                    case["metrics"]["teacher_over_residual_failure_reasons"]
                ),
                "pair_added": False,
            }
            for case in inconclusive
        ],
        "stage_6_14e_existing_inconclusive_pipeline_train": [
            {
                "game_id": str(item["game_id"]),
                "turn_index": int(item["turn_index"]),
                "current_top1_action_index": int(item["top1_action_index"]),
                "current_top1_action_sha256": item["top1_action_sha256"],
                "pair_added": False,
                "source_sample_mapping_count": 0,
            }
            for item in excluded_train
        ],
        "stage_6_14e_pipeline_development_identity_only": [
            {
                "game_id": str(item["game_id"]),
                "turn_index": int(item["turn_index"]),
                "reason": "pipeline_development_held_out",
                "pair_added": False,
                "action_inspected_in_this_stage": False,
                "source_sample_mapping_count": 0,
            }
            for item in heldout
        ],
    }
    summary = {
        "total_pair_count": 34,
        "pipeline_train_pair_count": 30,
        "pipeline_development_pair_count": 4,
        "base_pair_count": 22,
        "stage_6_4_corrective_pair_count": 6,
        "stage_6_9_residual_corrective_pair_count": 4,
        "stage_6_14e_remaining_corrective_pair_count": 2,
        "preserved_v2_pair_count": 32,
        "pipeline_train_game_count": 18,
        "pipeline_development_game_count": 4,
        "stage_6_14e_inconclusive_pair_added_count": 0,
        "existing_inconclusive_train_pair_added_count": 0,
        "pipeline_development_pair_added_count": 0,
        "stage_6_14e_excluded_or_heldout_count": 7,
        "dropped_base_sample_count": 0,
        "locked_test_loaded": False,
        "complete_website_dataset_loaded": False,
        "pipeline_only": True,
        "capability_evidence_eligible": False,
        "checkpoint_promotion_allowed": False,
        "threshold_passed": True,
    }
    forbidden = {
        "rollout_runs": 0,
        "objective_executions": 0,
        "new_objective_definitions": 0,
        "model_scoring_runs": 0,
        "training_runs": 0,
        "fine_tuning_runs": 0,
        "threshold_tuning_runs": 0,
        "hyperparameter_searches": 0,
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
        "unsupported_pair_additions": 0,
    }
    sample_hashes = [v1_builder.canonical_sha256(sample) for sample in samples]
    payload = {
        "format": FORMAT_VERSION,
        "summary": summary,
        "frozen_input_hashes": copy.deepcopy(context["frozen_hashes"]),
        "frozen_base_teacher_format": v2_payload["frozen_base_teacher_format"],
        "frozen_base_sample_count": 22,
        "frozen_base_samples_sha256": v1_builder.canonical_sha256(samples),
        "frozen_base_sample_sha256": sample_hashes,
        "frozen_base_samples": copy.deepcopy(samples),
        "frozen_v2_pair_ids": [pair["pair_id"] for pair in v2_payload["pairs"]],
        "frozen_v2_pair_semantic_sha256": v2_semantic_hashes,
        "pairs": pairs,
        "objective_manifest": objective,
        "exclusions": exclusions,
        "forbidden_operation_counts": forbidden,
    }
    manifest = {
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "dataset_path": str(DATASET_OUTPUT_PATH),
        "frozen_inputs": {
            "paths": {name: str(path) for name, path in frozen_paths().items()},
            "sha256": copy.deepcopy(context["frozen_hashes"]),
        },
        "summary": copy.deepcopy(summary),
        "frozen_base_samples_sha256": payload["frozen_base_samples_sha256"],
        "frozen_base_sample_sha256": sample_hashes,
        "frozen_v2_pair_ids": payload["frozen_v2_pair_ids"],
        "frozen_v2_pair_semantic_sha256": v2_semantic_hashes,
        "new_pair_ids": [pair["pair_id"] for pair in new_pairs],
        "new_pair_semantic_sha256": [pair_semantic_sha256(pair) for pair in new_pairs],
        "pair_ids": pair_ids,
        "pair_source_counts": dict(source_counts),
        "pipeline_partition_pair_counts": dict(partition_counts),
        "objective_manifest": copy.deepcopy(objective),
        "exclusions": copy.deepcopy(exclusions),
        "forbidden_operation_counts": copy.deepcopy(forbidden),
        "status": "completed",
    }
    return payload, manifest


def load_context() -> dict:
    frozen_hashes = verify_frozen_inputs()
    v2_payload = load_v2_dataset()
    v2_manifest = load_json(V2_MANIFEST_PATH)
    teacher_samples, _summary, teacher_hash = preference.load_teacher_dataset(
        TEACHER_PATH
    )
    if teacher_hash != confirmation.EXPECTED_HASHES["teacher_dataset"]:
        raise RuntimeError("teacher loader hash mismatch")
    split = load_json(SPLIT_PATH)
    confirmation_payload = load_json(CONFIRMATION_PATH)
    validate_v2_context(v2_payload, v2_manifest, teacher_samples, split)
    validate_and_select_confirmation(confirmation_payload)
    return {
        "frozen_hashes": frozen_hashes,
        "v2_payload": v2_payload,
        "v2_manifest": v2_manifest,
        "teacher_samples": teacher_samples,
        "split": split,
        "confirmation": confirmation_payload,
    }


def ensure_outputs_unused(
    dataset_path: Path = DATASET_OUTPUT_PATH,
    manifest_path: Path = MANIFEST_OUTPUT_PATH,
) -> None:
    if dataset_path.exists() or manifest_path.exists():
        raise RuntimeError("corrective dataset v3 output already exists")


def preflight() -> dict:
    ensure_outputs_unused()
    context = load_context()
    payload, manifest = build_payload(context)
    result = {
        "status": "preflight_passed",
        "frozen_hash_count": len(context["frozen_hashes"]),
        "summary": payload["summary"],
        "new_pair_ids": manifest["new_pair_ids"],
        "objective_manifest": payload["objective_manifest"],
        "outputs_written": False,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return result


def run() -> dict:
    ensure_outputs_unused()
    context = load_context()
    payload, manifest_core = build_payload(context)
    manifest, dataset_hash = v1_builder.write_outputs_once(
        DATASET_OUTPUT_PATH, MANIFEST_OUTPUT_PATH, payload, manifest_core
    )
    if verify_frozen_inputs() != context["frozen_hashes"]:
        raise RuntimeError("a frozen input changed during v3 dataset construction")
    result = {
        "status": manifest["status"],
        "dataset": str(DATASET_OUTPUT_PATH),
        "dataset_sha256": dataset_hash,
        "manifest": str(MANIFEST_OUTPUT_PATH),
        "summary": manifest["summary"],
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return result


def audit() -> dict:
    import torch

    if not DATASET_OUTPUT_PATH.exists() or not MANIFEST_OUTPUT_PATH.exists():
        raise RuntimeError("corrective dataset v3 outputs are missing")
    context = load_context()
    expected_payload, expected_manifest = build_payload(context)
    saved_payload = torch.load(
        DATASET_OUTPUT_PATH, map_location="cpu", weights_only=False
    )
    saved_manifest = load_json(MANIFEST_OUTPUT_PATH)
    if v1_builder.canonical_sha256(saved_payload) != v1_builder.canonical_sha256(
        expected_payload
    ):
        raise RuntimeError("saved v3 dataset does not match independent reconstruction")
    dataset_hash = v1_builder.sha256(DATASET_OUTPUT_PATH)
    if saved_manifest.get("dataset_sha256") != dataset_hash:
        raise RuntimeError("saved v3 manifest dataset hash mismatch")
    manifest_without_dataset_hash = copy.deepcopy(saved_manifest)
    manifest_without_dataset_hash.pop("dataset_sha256", None)
    if v1_builder.canonical_sha256(
        manifest_without_dataset_hash
    ) != v1_builder.canonical_sha256(expected_manifest):
        raise RuntimeError("saved v3 manifest does not match independent reconstruction")
    result = {
        "status": "audit_passed",
        "dataset_sha256": dataset_hash,
        "manifest_sha256": v1_builder.sha256(MANIFEST_OUTPUT_PATH),
        "frozen_input_hashes_exact": True,
        "teacher_samples_exact": True,
        "frozen_v2_pairs_semantically_exact": True,
        "two_new_supported_pairs_exact": True,
        "seven_exclusions_and_heldout_exact": True,
        "pair_counts_34_30_4_exact": True,
        "state_distribution_13_6_3_exact": True,
        "state_weights_exact": True,
        "partition_normalized_weights_exact": True,
        "provenance_exact": True,
        "forbidden_operation_counts_zero": True,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--preflight", action="store_true")
    mode.add_argument("--run", action="store_true")
    mode.add_argument("--audit", action="store_true")
    args = parser.parse_args()
    if args.preflight:
        preflight()
    elif args.run:
        run()
    else:
        audit()


if __name__ == "__main__":
    main()
