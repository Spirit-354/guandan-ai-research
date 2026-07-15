from __future__ import annotations

from collections import Counter, defaultdict
import copy
import hashlib
import json
import math
import os
from pathlib import Path
import struct
from typing import Any

import website_teacher_preference as preference


FORMAT_VERSION = "website_teacher_preference_corrective_dataset_v1"
MANIFEST_SCHEMA_VERSION = "website_teacher_preference_corrective_dataset_v1_manifest"
CONFIRMATION_PATH = Path(
    "website_teacher_preference_unpaired_train_confirmation_v1.json"
)
AUDIT_PATH = Path("website_teacher_preference_unpaired_evidence_audit_v1.json")
TEACHER_PATH = Path("website_information_set_teacher_dataset_v6.pth")
SPLIT_PATH = Path("website_teacher_preference_split_v1.json")
TRAINING_REPORT_PATH = Path("website_teacher_preference_training_v1.json")
CHECKPOINT_PATH = Path(
    "models_website_teacher_preference_v1/website_teacher_preference_final.pth"
)
ARENA_PATH = Path("website_teacher_preference_arena_smoke20_v1.json")
DATASET_OUTPUT_PATH = Path("website_teacher_preference_corrective_dataset_v1.pth")
MANIFEST_OUTPUT_PATH = Path(
    "website_teacher_preference_corrective_dataset_v1_manifest.json"
)

EXPECTED_HASHES = {
    "stage_6_4_confirmation": "8e17377b5a1523d9f0a47af7218d687e062a3ade671c57f387eb4c1a0888cfae",
    "stage_6_3_audit": "09f52df90d095ab6b3777a046c50901f96fbeb15e6ef5f613343a13be1249383",
    "teacher_dataset": "a74416e6facb28a1bc64563eba90cb33d460dc9e59cc2109518da142465e15f8",
    "split_manifest": "5a15e514dc9bc51d77d300837151d9f1a49250f42885cc7940725bcbe4d35107",
    "training_report": "896192b1d0b4de2caabe20ac17d6a20766fc7f89d6e82a981d834b777932ddd3",
    "checkpoint": "c54801a9db05100c2fe5a9bf610a64fc7c94dc2cd947dfaab115ff827bd90919",
    "arena_evidence": "aa45da9de202194102fe8d11e612ad3eb4b51177fd910b9a7948836afd2a1fe6",
}
SUPPORTED_KEYS = {
    ("13879", 6),
    ("13861", 10),
    ("13957", 14),
    ("13960", 15),
    ("13959", 7),
    ("14022", 16),
}
INCONCLUSIVE_KEYS = {("14077", 10), ("13882", 10), ("14025", 20)}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_sha256(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    ).hexdigest()


def action_sha256(action: list[float]) -> str:
    return hashlib.sha256(
        struct.pack(f"<{len(action)}f", *[float(value) for value in action])
    ).hexdigest()


def load_json(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError(f"{path} must contain a JSON object")
    return payload


def verify_frozen_inputs() -> dict[str, str]:
    paths = {
        "stage_6_4_confirmation": CONFIRMATION_PATH,
        "stage_6_3_audit": AUDIT_PATH,
        "teacher_dataset": TEACHER_PATH,
        "split_manifest": SPLIT_PATH,
        "training_report": TRAINING_REPORT_PATH,
        "checkpoint": CHECKPOINT_PATH,
        "arena_evidence": ARENA_PATH,
    }
    actual: dict[str, str] = {}
    for name, path in paths.items():
        value = sha256(path)
        if value != EXPECTED_HASHES[name]:
            raise RuntimeError(f"{name} SHA-256 mismatch")
        actual[name] = value
    return actual


def validate_frozen_context(
    confirmation: dict,
    split: dict,
    report: dict,
    arena: dict,
    samples: list[dict],
) -> tuple[set[str], set[str]]:
    if confirmation.get("schema_version") != (
        "website_teacher_preference_unpaired_train_confirmation_v1"
    ) or confirmation.get("status") != "completed":
        raise RuntimeError("Stage 6.4 confirmation status mismatch")
    if confirmation.get("completed_rollouts") != 288 or confirmation.get(
        "requested_total_rollouts"
    ) != 288:
        raise RuntimeError("Stage 6.4 rollout accounting mismatch")
    if confirmation.get("directional_classification_counts") != {
        "teacher_over_top1_supported": 6,
        "top1_over_teacher_supported": 0,
        "inconclusive": 3,
    }:
        raise RuntimeError("Stage 6.4 directional accounting mismatch")
    if any(
        int(value) != 0
        for value in (confirmation.get("forbidden_operation_counts") or {}).values()
    ):
        raise RuntimeError("Stage 6.4 contains a forbidden operation")
    train_ids = {str(value) for value in split.get("pipeline_train_game_ids") or []}
    development_ids = {
        str(value) for value in split.get("pipeline_development_game_ids") or []
    }
    expected_train, expected_development = preference.split_game_ids(samples)
    if (
        len(train_ids) != 18
        or len(development_ids) != 4
        or train_ids & development_ids
        or train_ids != set(expected_train)
        or development_ids != set(expected_development)
        or split.get("overlap_game_ids") != []
        or split.get("dropped_game_ids") != []
    ):
        raise RuntimeError("frozen pipeline split mismatch")
    if (
        report.get("checkpoint_sha256") != EXPECTED_HASHES["checkpoint"]
        or report.get("checkpoint_promotion_allowed") is not False
        or arena.get("requested_games") != 20
        or arena.get("completed_games") != 20
        or arena.get("model_wins") != 0
        or arena.get("early_screen_continuation_allowed") is not False
    ):
        raise RuntimeError("rejected checkpoint conclusion mismatch")
    return train_ids, development_ids


def select_confirmation_cases(confirmation: dict) -> tuple[list[dict], list[dict]]:
    cases = confirmation.get("case_results") or []
    supported = [
        case
        for case in cases
        if case.get("metrics", {}).get("directional_classification")
        == "teacher_over_top1_supported"
    ]
    inconclusive = [
        case
        for case in cases
        if case.get("metrics", {}).get("directional_classification") == "inconclusive"
    ]
    supported_keys = {
        (str(case["game_id"]), int(case["turn_index"])) for case in supported
    }
    inconclusive_keys = {
        (str(case["game_id"]), int(case["turn_index"])) for case in inconclusive
    }
    if (
        len(cases) != 9
        or supported_keys != SUPPORTED_KEYS
        or inconclusive_keys != INCONCLUSIVE_KEYS
        or any(case.get("pipeline_partition") != "pipeline_train" for case in cases)
    ):
        raise RuntimeError("Stage 6.4 supported/inconclusive case set mismatch")
    for case in supported:
        metrics = case.get("metrics") or {}
        candidates = case.get("candidate_results") or []
        if (
            metrics.get("teacher_over_top1_supported") is not True
            or metrics.get("teacher_over_top1_failure_reasons") != []
            or len(candidates) != 2
            or [item.get("role") for item in candidates] != ["teacher", "top1"]
            or any(item.get("completed_rollout_count") != 16 for item in candidates)
            or any(item.get("failure_count") != 0 for item in candidates)
        ):
            raise RuntimeError("supported confirmation case is not fully qualified")
    return supported, inconclusive


def base_pair(sample: dict, base_index: int, partition: str) -> dict:
    return {
        "pair_id": (
            f"base:{sample['game_id']}:{sample['turn_index']}:teacher_vs_behavior"
        ),
        "pair_source": "frozen_teacher_v6",
        "preference_target": "teacher_action_beats_behavior_action",
        "game_id": str(sample["game_id"]),
        "turn_index": int(sample["turn_index"]),
        "pipeline_partition": partition,
        "base_sample_index": base_index,
        "state": copy.deepcopy(sample["state"]),
        "state_dim": int(sample["state_dim"]),
        "preferred_action": copy.deepcopy(sample["teacher_action"]),
        "rejected_action": copy.deepcopy(sample["behavior_action"]),
        "action_dim": int(sample["action_dim"]),
        "preferred_action_sha256": action_sha256(sample["teacher_action"]),
        "rejected_action_sha256": action_sha256(sample["behavior_action"]),
        "preferred_physical_cards_website": copy.deepcopy(
            sample["teacher_physical_cards"]
        ),
        "rejected_physical_cards_website": copy.deepcopy(
            sample["behavior_physical_cards"]
        ),
        "source_evidence": sample["source_rollout_eval"],
        "source_metrics": {
            "rollout_count": sample["rollout_count"],
            "hidden_card_sampling_method": sample["hidden_card_sampling_method"],
            "candidate_advantage": sample["candidate_advantage"],
            "candidate_return_variance": sample["candidate_return_variance"],
            "paired_return_variance": sample["paired_return_variance"],
            "advantage_95_lower_bound": sample["advantage_95_lower_bound"],
            "label_confidence": sample["label_confidence"],
            "continuation_policy_advantages": copy.deepcopy(
                sample["continuation_policy_advantages"]
            ),
        },
        "locked_test_used": False,
    }


def corrective_pair(sample: dict, base_index: int, case: dict) -> dict:
    candidates = case["candidate_results"]
    teacher, top1 = candidates
    teacher_index = int(teacher["action_index"])
    top1_index = int(top1["action_index"])
    legal_actions = sample["legal_actions"]
    if (
        legal_actions[teacher_index] != sample["teacher_action"]
        or teacher["action_sha256"] != action_sha256(sample["teacher_action"])
        or top1["action_sha256"] != action_sha256(legal_actions[top1_index])
        or teacher["physical_cards_website"] != sample["teacher_physical_cards"]
        or legal_actions[top1_index] == sample["teacher_action"]
        or legal_actions[top1_index] == sample["behavior_action"]
    ):
        raise RuntimeError("corrective pair action identity mismatch")
    metrics = case["metrics"]
    return {
        "pair_id": f"corrective:{sample['game_id']}:{sample['turn_index']}:teacher_vs_top1",
        "pair_source": "stage_6_4_train_confirmation",
        "preference_target": "teacher_action_beats_model_top1",
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
        "rejected_action_sha256": top1["action_sha256"],
        "preferred_physical_cards_website": copy.deepcopy(
            teacher["physical_cards_website"]
        ),
        "rejected_physical_cards_website": copy.deepcopy(
            top1["physical_cards_website"]
        ),
        "source_evidence": str(CONFIRMATION_PATH),
        "source_evidence_sha256": EXPECTED_HASHES["stage_6_4_confirmation"],
        "source_metrics": copy.deepcopy(metrics),
        "hidden_card_sampling_method": (
            "uniform_physical_assignment_given_public_counts_v1"
        ),
        "rollout_count_per_action": 16,
        "continuation_profiles": ["greedy_bot", "tempo_baseline"],
        "locked_test_used": False,
    }


def apply_state_balanced_weights(pairs: list[dict]) -> dict:
    grouped: dict[tuple[str, str, int], list[dict]] = defaultdict(list)
    for pair in pairs:
        grouped[
            (
                pair["pipeline_partition"],
                str(pair["game_id"]),
                int(pair["turn_index"]),
            )
        ].append(pair)
    partition_state_counts = Counter(key[0] for key in grouped)
    for key, state_pairs in grouped.items():
        pair_weight = 1.0 / len(state_pairs)
        normalized_weight = pair_weight / partition_state_counts[key[0]]
        for pair in state_pairs:
            pair["state_objective_weight"] = 1.0
            pair["within_state_pair_weight"] = pair_weight
            pair["partition_normalized_pair_weight"] = normalized_weight
    state_totals = {
        f"{partition}:{game_id}:{turn_index}": sum(
            float(pair["within_state_pair_weight"]) for pair in state_pairs
        )
        for (partition, game_id, turn_index), state_pairs in grouped.items()
    }
    if any(not math.isclose(value, 1.0, abs_tol=1e-12) for value in state_totals.values()):
        raise RuntimeError("state-balanced pair weights do not sum to one")
    return {
        "objective_name": "state_balanced_pairwise_softplus_v1",
        "formula": (
            "mean_over_states(sum_over_pairs(within_state_pair_weight * "
            "softplus(Q_rejected-Q_preferred)))"
        ),
        "state_aggregate_weight": 1.0,
        "pair_weight_rule": "one_divided_by_pair_count_for_state",
        "pipeline_train_state_count": partition_state_counts["pipeline_train"],
        "pipeline_development_state_count": partition_state_counts[
            "pipeline_development"
        ],
        "state_weight_sums": state_totals,
        "weights_tuned": False,
        "executed": False,
    }


def build_payload(
    samples: list[dict],
    split: dict,
    confirmation: dict,
    frozen_hashes: dict[str, str],
) -> tuple[dict, dict]:
    train_ids = {str(value) for value in split["pipeline_train_game_ids"]}
    development_ids = {
        str(value) for value in split["pipeline_development_game_ids"]
    }
    supported, inconclusive = select_confirmation_cases(confirmation)
    supported_by_key = {
        (str(case["game_id"]), int(case["turn_index"])): case
        for case in supported
    }
    pairs: list[dict] = []
    for index, sample in enumerate(samples):
        game_id = str(sample["game_id"])
        partition = (
            "pipeline_train"
            if game_id in train_ids
            else "pipeline_development"
            if game_id in development_ids
            else None
        )
        if partition is None:
            raise RuntimeError("base sample has no frozen pipeline partition")
        pairs.append(base_pair(sample, index, partition))
        key = (game_id, int(sample["turn_index"]))
        if key in supported_by_key:
            if partition != "pipeline_train":
                raise RuntimeError("corrective pair is not pipeline train")
            pairs.append(corrective_pair(sample, index, supported_by_key[key]))
    objective = apply_state_balanced_weights(pairs)
    partition_counts = Counter(pair["pipeline_partition"] for pair in pairs)
    pair_source_counts = Counter(pair["pair_source"] for pair in pairs)
    pair_ids = [pair["pair_id"] for pair in pairs]
    if (
        len(pairs) != 28
        or len(set(pair_ids)) != 28
        or partition_counts
        != Counter({"pipeline_train": 24, "pipeline_development": 4})
        or pair_source_counts
        != Counter({"frozen_teacher_v6": 22, "stage_6_4_train_confirmation": 6})
    ):
        raise RuntimeError("corrective dataset pair accounting mismatch")
    exclusions = {
        "inconclusive_pipeline_train": [
            {
                "game_id": str(case["game_id"]),
                "turn_index": int(case["turn_index"]),
                "directional_classification": "inconclusive",
                "teacher_over_top1_failure_reasons": copy.deepcopy(
                    case["metrics"]["teacher_over_top1_failure_reasons"]
                ),
            }
            for case in inconclusive
        ],
        "pipeline_development_unpaired": [
            {
                "game_id": str(item["game_id"]),
                "turn_index": int(item["turn_index"]),
                "reason": "pipeline_development_held_out",
                "pair_added": False,
                "action_inspected_in_this_stage": False,
            }
            for item in confirmation["pipeline_development_heldout"]
        ],
    }
    base_sample_hashes = [canonical_sha256(sample) for sample in samples]
    summary = {
        "total_pair_count": 28,
        "pipeline_train_pair_count": 24,
        "pipeline_development_pair_count": 4,
        "base_pair_count": 22,
        "corrective_pair_count": 6,
        "pipeline_train_game_count": 18,
        "pipeline_development_game_count": 4,
        "inconclusive_pair_added_count": 0,
        "pipeline_development_unpaired_pair_added_count": 0,
        "dropped_base_sample_count": 0,
        "locked_test_loaded": False,
        "pipeline_only": True,
        "capability_evidence_eligible": False,
        "checkpoint_promotion_allowed": False,
        "threshold_passed": True,
    }
    forbidden = {
        "rollout_runs": 0,
        "training_runs": 0,
        "hyperparameter_searches": 0,
        "checkpoint_selections": 0,
        "checkpoint_modifications": 0,
        "locked_test_loads": 0,
        "arena_games": 0,
        "website_shadow_games": 0,
        "website_games": 0,
        "model_controlled_website_actions": 0,
        "checkpoint_promotions": 0,
        "capability_claims": 0,
    }
    payload = {
        "format": FORMAT_VERSION,
        "summary": summary,
        "frozen_input_hashes": frozen_hashes,
        "frozen_base_teacher_format": preference.TEACHER_SCHEMA_VERSION,
        "frozen_base_sample_count": len(samples),
        "frozen_base_samples_sha256": canonical_sha256(samples),
        "frozen_base_sample_sha256": base_sample_hashes,
        "frozen_base_samples": copy.deepcopy(samples),
        "pairs": pairs,
        "objective_manifest": objective,
        "exclusions": exclusions,
        "forbidden_operation_counts": forbidden,
    }
    manifest_core = {
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "dataset_path": str(DATASET_OUTPUT_PATH),
        "frozen_inputs": {
            "paths": {
                "stage_6_4_confirmation": str(CONFIRMATION_PATH),
                "stage_6_3_audit": str(AUDIT_PATH),
                "teacher_dataset": str(TEACHER_PATH),
                "split_manifest": str(SPLIT_PATH),
                "training_report": str(TRAINING_REPORT_PATH),
                "checkpoint": str(CHECKPOINT_PATH),
                "arena_evidence": str(ARENA_PATH),
            },
            "sha256": frozen_hashes,
        },
        "summary": copy.deepcopy(summary),
        "frozen_base_samples_sha256": payload["frozen_base_samples_sha256"],
        "frozen_base_sample_sha256": base_sample_hashes,
        "pair_ids": pair_ids,
        "pair_source_counts": dict(pair_source_counts),
        "pipeline_partition_pair_counts": dict(partition_counts),
        "objective_manifest": copy.deepcopy(objective),
        "exclusions": copy.deepcopy(exclusions),
        "forbidden_operation_counts": copy.deepcopy(forbidden),
        "status": "completed",
    }
    return payload, manifest_core


def write_outputs_once(
    dataset_path: Path,
    manifest_path: Path,
    payload: dict,
    manifest_core: dict,
) -> tuple[dict, str]:
    import torch

    if dataset_path.exists() or manifest_path.exists():
        raise RuntimeError("corrective dataset output already exists")
    dataset_temporary = dataset_path.with_name(f"{dataset_path.name}.tmp")
    manifest_temporary = manifest_path.with_name(f"{manifest_path.name}.tmp")
    if dataset_temporary.exists() or manifest_temporary.exists():
        raise RuntimeError("stale corrective dataset temporary output exists")
    dataset_committed = False
    manifest_committed = False
    try:
        torch.save(payload, dataset_temporary)
        dataset_hash = sha256(dataset_temporary)
        manifest = {**manifest_core, "dataset_sha256": dataset_hash}
        with manifest_temporary.open("x", encoding="utf-8") as handle:
            json.dump(manifest, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        dataset_temporary.replace(dataset_path)
        dataset_committed = True
        manifest_temporary.replace(manifest_path)
        manifest_committed = True
        return manifest, dataset_hash
    except BaseException:
        dataset_temporary.unlink(missing_ok=True)
        manifest_temporary.unlink(missing_ok=True)
        if dataset_committed and not manifest_committed:
            dataset_path.unlink(missing_ok=True)
        if manifest_committed and not dataset_committed:
            manifest_path.unlink(missing_ok=True)
        raise


def run(
    dataset_path: Path = DATASET_OUTPUT_PATH,
    manifest_path: Path = MANIFEST_OUTPUT_PATH,
) -> dict:
    if dataset_path.exists() or manifest_path.exists():
        raise RuntimeError("corrective dataset output already exists")
    frozen_hashes = verify_frozen_inputs()
    confirmation = load_json(CONFIRMATION_PATH)
    split = load_json(SPLIT_PATH)
    report = load_json(TRAINING_REPORT_PATH)
    arena = load_json(ARENA_PATH)
    samples, _summary, teacher_hash = preference.load_teacher_dataset(TEACHER_PATH)
    if teacher_hash != EXPECTED_HASHES["teacher_dataset"]:
        raise RuntimeError("teacher loader hash mismatch")
    validate_frozen_context(confirmation, split, report, arena, samples)
    payload, manifest_core = build_payload(
        samples, split, confirmation, frozen_hashes
    )
    manifest, dataset_hash = write_outputs_once(
        dataset_path, manifest_path, payload, manifest_core
    )
    if verify_frozen_inputs() != frozen_hashes:
        raise RuntimeError("a frozen input changed during dataset construction")
    print(
        json.dumps(
            {
                "status": manifest["status"],
                "dataset": str(dataset_path),
                "dataset_sha256": dataset_hash,
                "manifest": str(manifest_path),
                "summary": manifest["summary"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return manifest


if __name__ == "__main__":
    run()
