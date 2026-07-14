from __future__ import annotations

from collections import Counter, defaultdict
import argparse
import copy
import json
import math
from pathlib import Path
from typing import Any

import website_teacher_preference as preference
import website_teacher_preference_corrective_dataset as v1_builder


FORMAT_VERSION = "website_teacher_preference_corrective_dataset_v2"
MANIFEST_SCHEMA_VERSION = "website_teacher_preference_corrective_dataset_v2_manifest"
CONFIRMATION_PATH = Path(
    "website_teacher_preference_corrective_residual_train_confirmation_v1.json"
)
V1_DATASET_PATH = Path("website_teacher_preference_corrective_dataset_v1.pth")
V1_MANIFEST_PATH = Path(
    "website_teacher_preference_corrective_dataset_v1_manifest.json"
)
RESIDUAL_AUDIT_PATH = Path(
    "website_teacher_preference_corrective_residual_evidence_audit_v1.json"
)
TEACHER_PATH = Path("website_information_set_teacher_dataset_v6.pth")
SPLIT_PATH = Path("website_teacher_preference_split_v1.json")
STAGE_6_4_CONFIRMATION_PATH = Path(
    "website_teacher_preference_unpaired_train_confirmation_v1.json"
)
DATASET_OUTPUT_PATH = Path("website_teacher_preference_corrective_dataset_v2.pth")
MANIFEST_OUTPUT_PATH = Path(
    "website_teacher_preference_corrective_dataset_v2_manifest.json"
)

EXPECTED_HASHES = {
    "stage_6_9_confirmation": "352cd0dfe0a4c958ba0555b776326a2b58470a980aef461ed49d4c59a7474c7a",
    "corrective_dataset_v1": "fad7ae18fea8b02cbc88ad4a8a7f8ecee298abe436ef589f5c88d66e42a32707",
    "corrective_dataset_v1_manifest": "0a5dc4f60091338b65f86f83ad30ae55dc18c058ee8b07535a314510ad96ef0a",
    "stage_6_8_audit": "676232033f07051670b4407f15aca9f3939d9754ac2dcf4d078957263a1e2a6b",
    "teacher_dataset": "a74416e6facb28a1bc64563eba90cb33d460dc9e59cc2109518da142465e15f8",
    "split_manifest": "5a15e514dc9bc51d77d300837151d9f1a49250f42885cc7940725bcbe4d35107",
    "stage_6_4_confirmation": "8e17377b5a1523d9f0a47af7218d687e062a3ade671c57f387eb4c1a0888cfae",
}
SUPPORTED_KEYS = [
    ("14044", 9),
    ("14038", 12),
    ("14000", 5),
    ("14022", 16),
]
INCONCLUSIVE_KEYS = {
    ("13957", 14),
    ("14077", 10),
    ("13959", 7),
    ("14025", 20),
}
DEVELOPMENT_KEYS = {("13992", 16), ("14074", 9), ("13871", 9)}
WEIGHT_FIELDS = {
    "state_objective_weight",
    "within_state_pair_weight",
    "partition_normalized_pair_weight",
}


def load_json(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError(f"{path} must contain a JSON object")
    return payload


def verify_frozen_inputs() -> dict[str, str]:
    paths = {
        "stage_6_9_confirmation": CONFIRMATION_PATH,
        "corrective_dataset_v1": V1_DATASET_PATH,
        "corrective_dataset_v1_manifest": V1_MANIFEST_PATH,
        "stage_6_8_audit": RESIDUAL_AUDIT_PATH,
        "teacher_dataset": TEACHER_PATH,
        "split_manifest": SPLIT_PATH,
        "stage_6_4_confirmation": STAGE_6_4_CONFIRMATION_PATH,
    }
    actual = {name: v1_builder.sha256(path) for name, path in paths.items()}
    for name, expected in EXPECTED_HASHES.items():
        if actual[name] != expected:
            raise RuntimeError(f"{name} SHA-256 mismatch")
    return actual


def load_v1_dataset() -> dict:
    import torch

    payload = torch.load(V1_DATASET_PATH, map_location="cpu", weights_only=False)
    if not isinstance(payload, dict):
        raise RuntimeError("corrective dataset v1 must contain a dictionary")
    return payload


def without_weight_fields(pair: dict) -> dict:
    return {
        key: copy.deepcopy(value)
        for key, value in pair.items()
        if key not in WEIGHT_FIELDS
    }


def pair_semantic_sha256(pair: dict) -> str:
    return v1_builder.canonical_sha256(without_weight_fields(pair))


def validate_v1_context(
    v1_payload: dict,
    v1_manifest: dict,
    teacher_samples: list[dict],
    split: dict,
) -> None:
    pairs = v1_payload.get("pairs") or []
    embedded_samples = v1_payload.get("frozen_base_samples") or []
    train_ids = {str(value) for value in split.get("pipeline_train_game_ids") or []}
    development_ids = {
        str(value) for value in split.get("pipeline_development_game_ids") or []
    }
    if (
        v1_payload.get("format") != v1_builder.FORMAT_VERSION
        or v1_manifest.get("schema_version") != v1_builder.MANIFEST_SCHEMA_VERSION
        or v1_manifest.get("status") != "completed"
        or v1_manifest.get("dataset_sha256") != EXPECTED_HASHES["corrective_dataset_v1"]
        or len(pairs) != 28
        or len({pair.get("pair_id") for pair in pairs}) != 28
    ):
        raise RuntimeError("frozen corrective dataset v1 contract mismatch")
    if (
        len(embedded_samples) != 22
        or v1_payload.get("frozen_base_sample_count") != 22
        or v1_builder.canonical_sha256(embedded_samples)
        != v1_payload.get("frozen_base_samples_sha256")
        or [v1_builder.canonical_sha256(sample) for sample in embedded_samples]
        != v1_payload.get("frozen_base_sample_sha256")
        or v1_builder.canonical_sha256(embedded_samples)
        != v1_builder.canonical_sha256(teacher_samples)
    ):
        raise RuntimeError("frozen teacher sample preservation mismatch")
    if (
        len(train_ids) != 18
        or len(development_ids) != 4
        or train_ids & development_ids
        or split.get("overlap_game_ids") != []
        or split.get("dropped_game_ids") != []
    ):
        raise RuntimeError("frozen split mismatch")
    pair_counts = Counter(pair.get("pipeline_partition") for pair in pairs)
    source_counts = Counter(pair.get("pair_source") for pair in pairs)
    if pair_counts != Counter(
        {"pipeline_train": 24, "pipeline_development": 4}
    ) or source_counts != Counter(
        {"frozen_teacher_v6": 22, "stage_6_4_train_confirmation": 6}
    ):
        raise RuntimeError("frozen corrective dataset v1 pair accounting mismatch")
    if any(
        int(value) != 0
        for value in (v1_payload.get("forbidden_operation_counts") or {}).values()
    ):
        raise RuntimeError(
            "frozen corrective dataset v1 contains a forbidden operation"
        )


def identity_only_keys(items: list[dict]) -> set[tuple[str, int]]:
    return {(str(item["game_id"]), int(item["turn_index"])) for item in items}


def select_confirmation_cases(
    confirmation: dict, residual_audit: dict
) -> tuple[list[dict], list[dict], list[dict]]:
    cases = confirmation.get("case_results") or []
    supported = [
        case
        for case in cases
        if case.get("metrics", {}).get("directional_classification")
        == "teacher_over_residual_supported"
    ]
    inconclusive = [
        case
        for case in cases
        if case.get("metrics", {}).get("directional_classification") == "inconclusive"
    ]
    heldout = confirmation.get("pipeline_development_heldout") or []
    supported_keys = [
        (str(case["game_id"]), int(case["turn_index"])) for case in supported
    ]
    inconclusive_keys = {
        (str(case["game_id"]), int(case["turn_index"])) for case in inconclusive
    }
    if (
        confirmation.get("schema_version")
        != "website_teacher_preference_corrective_residual_train_confirmation_v1"
        or confirmation.get("status") != "completed"
        or confirmation.get("requested_total_rollouts") != 256
        or confirmation.get("completed_rollouts") != 256
        or confirmation.get("directional_classification_counts")
        != {
            "teacher_over_residual_supported": 4,
            "residual_over_teacher_supported": 0,
            "inconclusive": 4,
        }
        or len(cases) != 8
        or supported_keys != SUPPORTED_KEYS
        or inconclusive_keys != INCONCLUSIVE_KEYS
        or any(case.get("pipeline_partition") != "pipeline_train" for case in cases)
    ):
        raise RuntimeError("Stage 6.9 confirmation case accounting mismatch")
    if any(
        int(value) != 0
        for value in (confirmation.get("forbidden_operation_counts") or {}).values()
    ):
        raise RuntimeError("Stage 6.9 contains a forbidden operation")
    for case in supported:
        metrics = case.get("metrics") or {}
        candidates = case.get("candidate_results") or []
        if (
            metrics.get("teacher_over_residual_supported") is not True
            or metrics.get("teacher_over_residual_failure_reasons") != []
            or metrics.get("residual_over_teacher_supported") is not False
            or len(candidates) != 2
            or [item.get("role") for item in candidates] != ["teacher", "residual"]
            or any(item.get("completed_rollout_count") != 16 for item in candidates)
            or any(item.get("failure_count") != 0 for item in candidates)
            or any(item.get("failures") != [] for item in candidates)
        ):
            raise RuntimeError("supported Stage 6.9 case is not fully qualified")
    if identity_only_keys(heldout) != DEVELOPMENT_KEYS or any(
        item.get("pipeline_partition") != "pipeline_development"
        or item.get("source_sample_mapping_count") != 0
        or item.get("case_execution_count") != 0
        or item.get("rollout_count") != 0
        or item.get("held_out_from_candidate_threshold_objective_design") is not True
        for item in heldout
    ):
        raise RuntimeError("Stage 6.9 development isolation mismatch")
    audit_heldout = residual_audit.get("pipeline_development_identity_only") or []
    if (
        residual_audit.get("schema_version")
        != "website_teacher_preference_corrective_residual_evidence_audit_v1"
        or residual_audit.get("status") != "completed"
        or identity_only_keys(audit_heldout) != DEVELOPMENT_KEYS
        or residual_audit.get("future_counterfactual_manifest_case_count") != 8
        or residual_audit.get("future_counterfactual_manifest_executed") is not False
        or any(
            int(value) != 0
            for value in (
                residual_audit.get("forbidden_operation_counts") or {}
            ).values()
        )
    ):
        raise RuntimeError("Stage 6.8 residual audit contract mismatch")
    return supported, inconclusive, heldout


def residual_corrective_pair(sample: dict, base_index: int, case: dict) -> dict:
    teacher, residual = case["candidate_results"]
    teacher_index = int(teacher["action_index"])
    residual_index = int(residual["action_index"])
    legal_actions = sample["legal_actions"]
    if (
        teacher_index < 0
        or residual_index < 0
        or teacher_index >= len(legal_actions)
        or residual_index >= len(legal_actions)
        or legal_actions[teacher_index] != sample["teacher_action"]
        or teacher["action_sha256"]
        != v1_builder.action_sha256(sample["teacher_action"])
        or residual["action_sha256"]
        != v1_builder.action_sha256(legal_actions[residual_index])
        or teacher["physical_cards_website"] != sample["teacher_physical_cards"]
        or legal_actions[residual_index] == sample["teacher_action"]
        or legal_actions[residual_index] == sample["behavior_action"]
    ):
        raise RuntimeError("Stage 6.9 residual pair action identity mismatch")
    return {
        "pair_id": (
            f"residual_corrective:{sample['game_id']}:{sample['turn_index']}:"
            "teacher_vs_residual_top1"
        ),
        "pair_source": "stage_6_9_residual_train_confirmation",
        "preference_target": "teacher_action_beats_residual_top1",
        "game_id": str(sample["game_id"]),
        "turn_index": int(sample["turn_index"]),
        "pipeline_partition": "pipeline_train",
        "base_sample_index": base_index,
        "state": copy.deepcopy(sample["state"]),
        "state_dim": int(sample["state_dim"]),
        "preferred_action": copy.deepcopy(sample["teacher_action"]),
        "rejected_action": copy.deepcopy(legal_actions[residual_index]),
        "action_dim": int(sample["action_dim"]),
        "preferred_action_index": teacher_index,
        "rejected_action_index": residual_index,
        "preferred_action_sha256": teacher["action_sha256"],
        "rejected_action_sha256": residual["action_sha256"],
        "preferred_physical_cards_website": copy.deepcopy(
            teacher["physical_cards_website"]
        ),
        "rejected_physical_cards_website": copy.deepcopy(
            residual["physical_cards_website"]
        ),
        "source_evidence": str(CONFIRMATION_PATH),
        "source_evidence_sha256": EXPECTED_HASHES["stage_6_9_confirmation"],
        "source_audit": str(RESIDUAL_AUDIT_PATH),
        "source_audit_sha256": EXPECTED_HASHES["stage_6_8_audit"],
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
    triple_key = ("pipeline_train", "14022", 16)
    two_pair_keys = sorted(
        f"{partition}:{game_id}:{turn_index}"
        for (partition, game_id, turn_index), state_pairs in grouped.items()
        if len(state_pairs) == 2
    )
    if size_counts != Counter({1: 13, 2: 8, 3: 1}) or len(grouped[triple_key]) != 3:
        raise RuntimeError("state pair-count distribution mismatch")
    for key, state_pairs in grouped.items():
        expected = 1.0 / len(state_pairs)
        if any(
            not math.isclose(pair["within_state_pair_weight"], expected, abs_tol=1e-12)
            for pair in state_pairs
        ):
            raise RuntimeError(f"state weight mismatch for {key}")
    partition_sums = {
        partition: sum(
            float(pair["partition_normalized_pair_weight"])
            for pair in pairs
            if pair["pipeline_partition"] == partition
        )
        for partition in ("pipeline_train", "pipeline_development")
    }
    if any(
        not math.isclose(value, 1.0, abs_tol=1e-12) for value in partition_sums.values()
    ):
        raise RuntimeError("partition-normalized weights do not sum to one")
    objective["state_pair_count_distribution"] = {
        "one_pair_state_count": 13,
        "two_pair_state_count": 8,
        "three_pair_state_count": 1,
    }
    objective["two_pair_state_keys"] = two_pair_keys
    objective["three_pair_state_key"] = "pipeline_train:14022:16"
    objective["partition_normalized_weight_sums"] = partition_sums
    return objective


def build_payload(context: dict) -> tuple[dict, dict]:
    v1_payload = context["v1_payload"]
    samples = v1_payload["frozen_base_samples"]
    supported, inconclusive, heldout = select_confirmation_cases(
        context["confirmation"], context["residual_audit"]
    )
    sample_by_key = {
        (str(sample["game_id"]), int(sample["turn_index"])): (index, sample)
        for index, sample in enumerate(samples)
    }
    pairs = copy.deepcopy(v1_payload["pairs"])
    v1_semantic_hashes = [pair_semantic_sha256(pair) for pair in pairs]
    new_pairs = []
    for case in supported:
        key = (str(case["game_id"]), int(case["turn_index"]))
        if key not in sample_by_key:
            raise RuntimeError(
                f"Stage 6.9 supported state missing from teacher v6: {key}"
            )
        base_index, sample = sample_by_key[key]
        new_pair = residual_corrective_pair(sample, base_index, case)
        pairs.append(new_pair)
        new_pairs.append(new_pair)
    objective = apply_and_validate_weights(pairs)
    if [pair_semantic_sha256(pair) for pair in pairs[:28]] != v1_semantic_hashes:
        raise RuntimeError("a frozen v1 pair changed outside weight fields")
    pair_ids = [pair["pair_id"] for pair in pairs]
    partition_counts = Counter(pair["pipeline_partition"] for pair in pairs)
    source_counts = Counter(pair["pair_source"] for pair in pairs)
    if (
        len(pairs) != 32
        or len(set(pair_ids)) != 32
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
        raise RuntimeError("corrective dataset v2 pair accounting mismatch")
    exclusions = {
        "frozen_v1_exclusions": copy.deepcopy(v1_payload["exclusions"]),
        "stage_6_9_inconclusive_pipeline_train": [
            {
                "game_id": str(case["game_id"]),
                "turn_index": int(case["turn_index"]),
                "directional_classification": "inconclusive",
                "teacher_over_residual_failure_reasons": copy.deepcopy(
                    case["metrics"]["teacher_over_residual_failure_reasons"]
                ),
                "pair_added": False,
            }
            for case in inconclusive
        ],
        "stage_6_9_pipeline_development_identity_only": [
            {
                "game_id": str(item["game_id"]),
                "turn_index": int(item["turn_index"]),
                "reason": "pipeline_development_held_out",
                "pair_added": False,
                "action_inspected_in_this_stage": False,
            }
            for item in heldout
        ],
    }
    summary = {
        "total_pair_count": 32,
        "pipeline_train_pair_count": 28,
        "pipeline_development_pair_count": 4,
        "base_pair_count": 22,
        "stage_6_4_corrective_pair_count": 6,
        "stage_6_9_residual_corrective_pair_count": 4,
        "preserved_v1_pair_count": 28,
        "pipeline_train_game_count": 18,
        "pipeline_development_game_count": 4,
        "stage_6_9_inconclusive_pair_added_count": 0,
        "pipeline_development_residual_pair_added_count": 0,
        "stage_6_9_excluded_or_heldout_count": 7,
        "dropped_base_sample_count": 0,
        "locked_test_loaded": False,
        "website_dataset_loaded": False,
        "pipeline_only": True,
        "capability_evidence_eligible": False,
        "checkpoint_promotion_allowed": False,
        "threshold_passed": True,
    }
    forbidden = {
        "rollout_runs": 0,
        "training_runs": 0,
        "fine_tuning_runs": 0,
        "threshold_tuning_runs": 0,
        "objective_executions": 0,
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
    sample_hashes = [v1_builder.canonical_sha256(sample) for sample in samples]
    payload = {
        "format": FORMAT_VERSION,
        "summary": summary,
        "frozen_input_hashes": copy.deepcopy(context["frozen_hashes"]),
        "frozen_base_teacher_format": v1_payload["frozen_base_teacher_format"],
        "frozen_base_sample_count": 22,
        "frozen_base_samples_sha256": v1_builder.canonical_sha256(samples),
        "frozen_base_sample_sha256": sample_hashes,
        "frozen_base_samples": copy.deepcopy(samples),
        "frozen_v1_pair_ids": [pair["pair_id"] for pair in v1_payload["pairs"]],
        "frozen_v1_pair_semantic_sha256": v1_semantic_hashes,
        "pairs": pairs,
        "objective_manifest": objective,
        "exclusions": exclusions,
        "forbidden_operation_counts": forbidden,
    }
    manifest = {
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "dataset_path": str(DATASET_OUTPUT_PATH),
        "frozen_inputs": {
            "paths": {
                "stage_6_9_confirmation": str(CONFIRMATION_PATH),
                "corrective_dataset_v1": str(V1_DATASET_PATH),
                "corrective_dataset_v1_manifest": str(V1_MANIFEST_PATH),
                "stage_6_8_audit": str(RESIDUAL_AUDIT_PATH),
                "teacher_dataset": str(TEACHER_PATH),
                "split_manifest": str(SPLIT_PATH),
                "stage_6_4_confirmation": str(STAGE_6_4_CONFIRMATION_PATH),
            },
            "sha256": copy.deepcopy(context["frozen_hashes"]),
        },
        "summary": copy.deepcopy(summary),
        "frozen_base_samples_sha256": payload["frozen_base_samples_sha256"],
        "frozen_base_sample_sha256": sample_hashes,
        "frozen_v1_pair_ids": payload["frozen_v1_pair_ids"],
        "frozen_v1_pair_semantic_sha256": v1_semantic_hashes,
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
    v1_payload = load_v1_dataset()
    v1_manifest = load_json(V1_MANIFEST_PATH)
    teacher_samples, _summary, teacher_hash = preference.load_teacher_dataset(
        TEACHER_PATH
    )
    if teacher_hash != EXPECTED_HASHES["teacher_dataset"]:
        raise RuntimeError("teacher loader hash mismatch")
    split = load_json(SPLIT_PATH)
    confirmation = load_json(CONFIRMATION_PATH)
    residual_audit = load_json(RESIDUAL_AUDIT_PATH)
    validate_v1_context(v1_payload, v1_manifest, teacher_samples, split)
    select_confirmation_cases(confirmation, residual_audit)
    return {
        "frozen_hashes": frozen_hashes,
        "v1_payload": v1_payload,
        "v1_manifest": v1_manifest,
        "teacher_samples": teacher_samples,
        "split": split,
        "confirmation": confirmation,
        "residual_audit": residual_audit,
    }


def ensure_outputs_unused(
    dataset_path: Path = DATASET_OUTPUT_PATH,
    manifest_path: Path = MANIFEST_OUTPUT_PATH,
) -> None:
    if dataset_path.exists() or manifest_path.exists():
        raise RuntimeError("corrective dataset v2 output already exists")


def preflight() -> dict:
    ensure_outputs_unused()
    context = load_context()
    payload, manifest = build_payload(context)
    result = {
        "status": "preflight_passed",
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
        raise RuntimeError("a frozen input changed during v2 dataset construction")
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
        raise RuntimeError("corrective dataset v2 outputs are missing")
    context = load_context()
    expected_payload, expected_manifest = build_payload(context)
    saved_payload = torch.load(
        DATASET_OUTPUT_PATH, map_location="cpu", weights_only=False
    )
    saved_manifest = load_json(MANIFEST_OUTPUT_PATH)
    if v1_builder.canonical_sha256(saved_payload) != v1_builder.canonical_sha256(
        expected_payload
    ):
        raise RuntimeError("saved v2 dataset does not match independent reconstruction")
    dataset_hash = v1_builder.sha256(DATASET_OUTPUT_PATH)
    if saved_manifest.get("dataset_sha256") != dataset_hash:
        raise RuntimeError("saved v2 manifest dataset hash mismatch")
    manifest_without_dataset_hash = copy.deepcopy(saved_manifest)
    manifest_without_dataset_hash.pop("dataset_sha256", None)
    if v1_builder.canonical_sha256(
        manifest_without_dataset_hash
    ) != v1_builder.canonical_sha256(expected_manifest):
        raise RuntimeError(
            "saved v2 manifest does not match independent reconstruction"
        )
    result = {
        "status": "audit_passed",
        "dataset_sha256": dataset_hash,
        "manifest_sha256": v1_builder.sha256(MANIFEST_OUTPUT_PATH),
        "frozen_input_hashes_exact": True,
        "teacher_samples_exact": True,
        "frozen_v1_pairs_semantically_exact": True,
        "new_supported_pairs_exact": True,
        "seven_exclusions_and_heldout_exact": True,
        "pair_counts_exact": True,
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
