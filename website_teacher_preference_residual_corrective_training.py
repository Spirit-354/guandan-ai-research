from __future__ import annotations

from collections import Counter
import argparse
import copy
import json
import math
from pathlib import Path
import random
from typing import Any

import torch

import danzero_dmc
import website_teacher_preference as preference
import website_teacher_preference_corrective_dataset as dataset_v1_builder
import website_teacher_preference_corrective_dataset_v2 as dataset_v2_builder
import website_teacher_preference_corrective_training as frozen_training


SCHEMA_VERSION = "website_teacher_preference_residual_corrective_training_v1"
CHECKPOINT_SCHEMA_VERSION = (
    "website_teacher_preference_residual_corrective_checkpoint_v1"
)
DATASET_PATH = Path("website_teacher_preference_corrective_dataset_v2.pth")
MANIFEST_PATH = Path("website_teacher_preference_corrective_dataset_v2_manifest.json")
RECIPE_AUTHORITY_PATH = Path("website_teacher_preference_corrective_training_v1.json")
V1_DATASET_PATH = Path("website_teacher_preference_corrective_dataset_v1.pth")
V1_MANIFEST_PATH = Path(
    "website_teacher_preference_corrective_dataset_v1_manifest.json"
)
TEACHER_PATH = Path("website_information_set_teacher_dataset_v6.pth")
SPLIT_PATH = Path("website_teacher_preference_split_v1.json")
CONFIRMATION_PATH = Path(
    "website_teacher_preference_corrective_residual_train_confirmation_v1.json"
)
CHECKPOINT_PATH = Path(
    "models_website_teacher_preference_residual_corrective_v1/"
    "website_teacher_preference_residual_corrective_final.pth"
)
REPORT_PATH = Path("website_teacher_preference_residual_corrective_training_v1.json")
EXPECTED_HASHES = {
    "corrective_dataset_v2": "40024f7c064f0ebb7999c4ac0f7bc85d77b759a23956cbe596756763d4009d4d",
    "corrective_manifest_v2": "ce5141f6254218d9230b15117a88d3c5e6bd374839bcf5fc77b393e2599ec353",
    "stage_6_6_recipe_authority": "baa97ccf71c237895a92f4cb8b36b9559cf3cabe45b4901b7481d9f50f4c0830",
    "corrective_dataset_v1": "fad7ae18fea8b02cbc88ad4a8a7f8ecee298abe436ef589f5c88d66e42a32707",
    "corrective_manifest_v1": "0a5dc4f60091338b65f86f83ad30ae55dc18c058ee8b07535a314510ad96ef0a",
    "teacher_dataset": "a74416e6facb28a1bc64563eba90cb33d460dc9e59cc2109518da142465e15f8",
    "split_manifest": "5a15e514dc9bc51d77d300837151d9f1a49250f42885cc7940725bcbe4d35107",
    "stage_6_9_confirmation": "352cd0dfe0a4c958ba0555b776326a2b58470a980aef461ed49d4c59a7474c7a",
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
SEED = 20260714
EPOCHS = 20
STATES_PER_BATCH = 6
LEARNING_RATE = 0.001


def load_json(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError(f"{path} must contain a JSON object")
    return payload


def frozen_paths() -> dict[str, Path]:
    return {
        "corrective_dataset_v2": DATASET_PATH,
        "corrective_manifest_v2": MANIFEST_PATH,
        "stage_6_6_recipe_authority": RECIPE_AUTHORITY_PATH,
        "corrective_dataset_v1": V1_DATASET_PATH,
        "corrective_manifest_v1": V1_MANIFEST_PATH,
        "teacher_dataset": TEACHER_PATH,
        "split_manifest": SPLIT_PATH,
        "stage_6_9_confirmation": CONFIRMATION_PATH,
    }


def fixed_recipe() -> dict:
    recipe = frozen_training.fixed_recipe()
    expected = {
        "device": "cpu",
        "seed": SEED,
        "epochs": EPOCHS,
        "states_per_batch": STATES_PER_BATCH,
        "learning_rate": LEARNING_RATE,
        "initial_checkpoint": None,
        "model_architecture": "danzero_dmc.build_q_model",
        "state_dim": 513,
        "action_dim": 54,
        "objective": (
            "mean_states(sum_pairs(within_state_pair_weight*"
            "softplus(Q_rejected-Q_preferred)))"
        ),
    }
    if recipe != expected:
        raise RuntimeError("Stage 6.6 fixed recipe changed")
    return recipe


def verify_frozen_hashes() -> dict[str, str]:
    actual = {
        name: dataset_v1_builder.sha256(path) for name, path in frozen_paths().items()
    }
    for name, expected in EXPECTED_HASHES.items():
        if actual.get(name) != expected:
            raise RuntimeError(f"{name} SHA-256 mismatch")
    return actual


def ensure_unused_outputs(
    checkpoint_path: Path = CHECKPOINT_PATH,
    report_path: Path = REPORT_PATH,
) -> None:
    paths = [
        checkpoint_path,
        report_path,
        checkpoint_path.with_name(f"{checkpoint_path.name}.tmp"),
        report_path.with_name(f"{report_path.name}.tmp"),
    ]
    existing = [str(path) for path in paths if path.exists()]
    if existing:
        raise RuntimeError(
            "residual corrective training output already exists: " + ", ".join(existing)
        )


def select_supported_cases(confirmation: dict) -> list[dict]:
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
        or any(
            int(value) != 0
            for value in (confirmation.get("forbidden_operation_counts") or {}).values()
        )
    ):
        raise RuntimeError("Stage 6.9 confirmation contract mismatch")
    for case in supported:
        metrics = case.get("metrics") or {}
        candidates = case.get("candidate_results") or []
        if (
            metrics.get("teacher_over_residual_supported") is not True
            or metrics.get("teacher_over_residual_failure_reasons") != []
            or len(candidates) != 2
            or [item.get("role") for item in candidates] != ["teacher", "residual"]
            or any(item.get("completed_rollout_count") != 16 for item in candidates)
            or any(item.get("failure_count") != 0 for item in candidates)
        ):
            raise RuntimeError("Stage 6.9 supported case qualification mismatch")
    return supported


def reconstruct_expected_pairs(
    v1_dataset: dict,
    samples: list[dict],
    confirmation: dict,
) -> list[dict]:
    pairs = copy.deepcopy(v1_dataset["pairs"])
    samples_by_key = {
        (str(sample["game_id"]), int(sample["turn_index"])): (index, sample)
        for index, sample in enumerate(samples)
    }
    for case in select_supported_cases(confirmation):
        key = (str(case["game_id"]), int(case["turn_index"]))
        if key not in samples_by_key:
            raise RuntimeError(f"Stage 6.9 supported sample missing: {key}")
        index, sample = samples_by_key[key]
        pairs.append(dataset_v2_builder.residual_corrective_pair(sample, index, case))
    dataset_v2_builder.apply_and_validate_weights(pairs)
    return pairs


def validate_inputs() -> tuple[list[dict], dict[str, str], dict]:
    hashes = verify_frozen_hashes()
    dataset = frozen_training.torch_load(DATASET_PATH)
    manifest = load_json(MANIFEST_PATH)
    recipe_authority = load_json(RECIPE_AUTHORITY_PATH)
    v1_dataset = frozen_training.torch_load(V1_DATASET_PATH)
    v1_manifest = load_json(V1_MANIFEST_PATH)
    split = load_json(SPLIT_PATH)
    confirmation = load_json(CONFIRMATION_PATH)
    samples, _summary, teacher_hash = preference.load_teacher_dataset(TEACHER_PATH)
    if teacher_hash != EXPECTED_HASHES["teacher_dataset"]:
        raise RuntimeError("teacher loader hash mismatch")
    dataset_v2_builder.validate_v1_context(v1_dataset, v1_manifest, samples, split)
    expected_pairs = reconstruct_expected_pairs(v1_dataset, samples, confirmation)
    pairs = dataset.get("pairs") if isinstance(dataset, dict) else None
    if (
        recipe_authority.get("schema_version") != frozen_training.SCHEMA_VERSION
        or recipe_authority.get("status") != "completed"
        or recipe_authority.get("recipe") != fixed_recipe()
        or recipe_authority.get("training_accounting", {}).get("training_run_count")
        != 1
        or recipe_authority.get("training_accounting", {}).get("optimizer_step_count")
        != 60
        or recipe_authority.get("checkpoint_promotion_allowed") is not False
        or recipe_authority.get("capability_claim_allowed") is not False
    ):
        raise RuntimeError("Stage 6.6 recipe authority mismatch")
    if (
        dataset.get("format") != dataset_v2_builder.FORMAT_VERSION
        or dataset.get("frozen_base_sample_count") != 22
        or dataset.get("frozen_base_samples") != samples
        or dataset.get("frozen_base_samples_sha256")
        != dataset_v1_builder.canonical_sha256(samples)
        or dataset.get("frozen_base_sample_sha256")
        != [dataset_v1_builder.canonical_sha256(sample) for sample in samples]
        or dataset_v1_builder.canonical_sha256(pairs)
        != dataset_v1_builder.canonical_sha256(expected_pairs)
        or any(
            int(value) != 0
            for value in (dataset.get("forbidden_operation_counts") or {}).values()
        )
    ):
        raise RuntimeError("corrective dataset v2 validation mismatch")
    v1_semantic_hashes = [
        dataset_v2_builder.pair_semantic_sha256(pair) for pair in v1_dataset["pairs"]
    ]
    new_semantic_hashes = [
        dataset_v2_builder.pair_semantic_sha256(pair) for pair in expected_pairs[28:]
    ]
    if (
        dataset.get("frozen_v1_pair_ids")
        != [pair["pair_id"] for pair in v1_dataset["pairs"]]
        or dataset.get("frozen_v1_pair_semantic_sha256") != v1_semantic_hashes
        or [dataset_v2_builder.pair_semantic_sha256(pair) for pair in pairs[:28]]
        != v1_semantic_hashes
        or [dataset_v2_builder.pair_semantic_sha256(pair) for pair in pairs[28:]]
        != new_semantic_hashes
    ):
        raise RuntimeError("corrective dataset v2 pair preservation mismatch")
    if (
        manifest.get("schema_version") != dataset_v2_builder.MANIFEST_SCHEMA_VERSION
        or manifest.get("status") != "completed"
        or manifest.get("dataset_sha256") != hashes["corrective_dataset_v2"]
        or manifest.get("frozen_v1_pair_semantic_sha256") != v1_semantic_hashes
        or manifest.get("new_pair_semantic_sha256") != new_semantic_hashes
        or manifest.get("pair_ids") != [pair["pair_id"] for pair in pairs]
        or manifest.get("objective_manifest") != dataset.get("objective_manifest")
        or any(
            int(value) != 0
            for value in (manifest.get("forbidden_operation_counts") or {}).values()
        )
    ):
        raise RuntimeError("corrective dataset v2 manifest mismatch")
    groups = frozen_training.build_state_groups(pairs)
    train_groups = [
        group for group in groups if group["pipeline_partition"] == "pipeline_train"
    ]
    development_groups = [
        group
        for group in groups
        if group["pipeline_partition"] == "pipeline_development"
    ]
    source_counts = Counter(pair["pair_source"] for pair in pairs)
    partition_counts = Counter(pair["pipeline_partition"] for pair in pairs)
    partition_weight_sums = {
        partition: sum(
            float(pair["partition_normalized_pair_weight"])
            for pair in pairs
            if pair["pipeline_partition"] == partition
        )
        for partition in ("pipeline_train", "pipeline_development")
    }
    if (
        len(pairs) != 32
        or len(train_groups) != 18
        or len(development_groups) != 4
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
        or any(
            not math.isclose(value, 1.0, abs_tol=1e-12)
            for value in partition_weight_sums.values()
        )
        or {group["key"] for group in train_groups}
        & {group["key"] for group in development_groups}
    ):
        raise RuntimeError("corrective dataset v2 accounting/isolation mismatch")
    return pairs, hashes, dataset


def evaluate_model(model: Any, pairs: list[dict]) -> dict:
    train_pairs = [
        pair for pair in pairs if pair["pipeline_partition"] == "pipeline_train"
    ]
    development_pairs = [
        pair for pair in pairs if pair["pipeline_partition"] == "pipeline_development"
    ]
    train_base = [
        pair for pair in train_pairs if pair["pair_source"] == "frozen_teacher_v6"
    ]
    train_stage_6_4 = [
        pair
        for pair in train_pairs
        if pair["pair_source"] == "stage_6_4_train_confirmation"
    ]
    train_stage_6_9 = [
        pair
        for pair in train_pairs
        if pair["pair_source"] == "stage_6_9_residual_train_confirmation"
    ]
    return {
        "pipeline_train": {
            "aggregate": frozen_training.evaluate_partition(model, train_pairs),
            "base_pairs": frozen_training.evaluate_partition(model, train_base),
            "stage_6_4_corrective_pairs": (
                frozen_training.evaluate_partition(model, train_stage_6_4)
            ),
            "stage_6_9_residual_pairs": (
                frozen_training.evaluate_partition(model, train_stage_6_9)
            ),
        },
        "pipeline_development": {
            "aggregate": frozen_training.evaluate_partition(model, development_pairs)
        },
    }


def checkpoint_payload(model: Any, hashes: dict[str, str]) -> dict:
    return {
        "schema_version": CHECKPOINT_SCHEMA_VERSION,
        "model_state_dict": {
            key: value.detach().cpu() for key, value in model.state_dict().items()
        },
        "frozen_input_hashes": dict(hashes),
        "recipe": fixed_recipe(),
        "training_mode": ("state_balanced_residual_corrective_pairwise_softplus"),
        "pipeline_train_state_count": 18,
        "pipeline_train_pair_count": 28,
        "pipeline_development_training_use_count": 0,
        "extra_training_target_count": 0,
        "fine_tuning_run_count": 0,
        "capability_claim_allowed": False,
        "checkpoint_promotion_allowed": False,
    }


def load_checkpoint(path: Path, hashes: dict[str, str]) -> tuple[Any, dict]:
    payload = frozen_training.torch_load(path)
    required = {
        "schema_version": CHECKPOINT_SCHEMA_VERSION,
        "frozen_input_hashes": hashes,
        "recipe": fixed_recipe(),
        "training_mode": ("state_balanced_residual_corrective_pairwise_softplus"),
        "pipeline_train_state_count": 18,
        "pipeline_train_pair_count": 28,
        "pipeline_development_training_use_count": 0,
        "extra_training_target_count": 0,
        "fine_tuning_run_count": 0,
        "capability_claim_allowed": False,
        "checkpoint_promotion_allowed": False,
    }
    for key, expected in required.items():
        if payload.get(key) != expected:
            raise RuntimeError(f"residual corrective checkpoint {key} mismatch")
    model = danzero_dmc.build_q_model(torch.device("cpu"))
    model.load_state_dict(payload["model_state_dict"])
    model.eval()
    return model, payload


def preflight() -> dict:
    ensure_unused_outputs()
    pairs, hashes, _dataset = validate_inputs()
    groups = frozen_training.build_state_groups(pairs)
    result = {
        "status": "ready",
        "frozen_input_hashes": hashes,
        "total_pair_count": len(pairs),
        "pipeline_train_pair_count": sum(
            pair["pipeline_partition"] == "pipeline_train" for pair in pairs
        ),
        "pipeline_development_pair_count": sum(
            pair["pipeline_partition"] == "pipeline_development" for pair in pairs
        ),
        "pipeline_train_state_count": sum(
            group["pipeline_partition"] == "pipeline_train" for group in groups
        ),
        "pipeline_development_state_count": sum(
            group["pipeline_partition"] == "pipeline_development" for group in groups
        ),
        "train_pair_source_counts": dict(
            Counter(
                pair["pair_source"]
                for pair in pairs
                if pair["pipeline_partition"] == "pipeline_train"
            )
        ),
        "recipe": fixed_recipe(),
        "outputs_written": False,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return result


def train_once() -> dict:
    ensure_unused_outputs()
    pairs, hashes, _dataset = validate_inputs()
    groups = frozen_training.build_state_groups(pairs)
    train_groups = [
        group for group in groups if group["pipeline_partition"] == "pipeline_train"
    ]
    development_groups = [
        group
        for group in groups
        if group["pipeline_partition"] == "pipeline_development"
    ]
    if (
        len(train_groups) != 18
        or len(development_groups) != 4
        or sum(len(group["pairs"]) for group in train_groups) != 28
        or sum(len(group["pairs"]) for group in development_groups) != 4
    ):
        raise RuntimeError("fixed residual corrective partition mismatch")
    frozen_training.set_deterministic()
    model = danzero_dmc.build_q_model(torch.device("cpu"))
    optimizer = torch.optim.Adam(model.parameters(), lr=LEARNING_RATE)
    rng = random.Random(SEED)
    history: list[dict] = []
    optimizer_steps = 0
    nonfinite_training_loss_count = 0
    for epoch in range(1, EPOCHS + 1):
        epoch_groups = list(train_groups)
        rng.shuffle(epoch_groups)
        model.train()
        batch_losses: list[float] = []
        for start in range(0, len(epoch_groups), STATES_PER_BATCH):
            batch = epoch_groups[start : start + STATES_PER_BATCH]
            loss = frozen_training.state_balanced_batch_loss(model, batch)
            if not bool(torch.isfinite(loss).item()):
                nonfinite_training_loss_count += 1
                raise RuntimeError("nonfinite residual corrective training loss")
            optimizer.zero_grad()
            loss.backward()
            optimizer.step()
            optimizer_steps += 1
            batch_losses.append(float(loss.item()))
        history.append(
            {
                "epoch": epoch,
                "mean_batch_state_balanced_loss": (
                    sum(batch_losses) / len(batch_losses)
                ),
            }
        )
    final_metrics = evaluate_model(model, pairs)
    if any(
        section["nonfinite_value_count"] != 0
        for partition in final_metrics.values()
        for section in partition.values()
    ):
        raise RuntimeError("nonfinite residual corrective prediction")
    frozen_training.save_checkpoint_once(
        CHECKPOINT_PATH, checkpoint_payload(model, hashes)
    )
    reloaded_model, checkpoint = load_checkpoint(CHECKPOINT_PATH, hashes)
    reloaded_metrics = evaluate_model(reloaded_model, pairs)
    if reloaded_metrics != final_metrics:
        raise RuntimeError("residual corrective checkpoint reload mismatch")
    if verify_frozen_hashes() != hashes:
        raise RuntimeError("a frozen input changed during training")
    forbidden = {
        "rollout_runs": 0,
        "fine_tuning_runs": 0,
        "hyperparameter_searches": 0,
        "threshold_tuning_runs": 0,
        "checkpoint_selections": 0,
        "locked_test_loads": 0,
        "website_dataset_loads": 0,
        "full_legal_set_diagnosis_runs": 0,
        "arena_games": 0,
        "website_shadow_games": 0,
        "website_games": 0,
        "model_controlled_website_actions": 0,
        "checkpoint_promotions": 0,
        "capability_claims": 0,
    }
    report = {
        "schema_version": SCHEMA_VERSION,
        "status": "completed",
        "frozen_inputs": {
            "paths": {name: str(path) for name, path in frozen_paths().items()},
            "sha256": hashes,
        },
        "dataset_validation": {
            "total_pair_count": 32,
            "pipeline_train_state_count": 18,
            "pipeline_train_pair_count": 28,
            "pipeline_development_state_count": 4,
            "pipeline_development_pair_count": 4,
            "exact_base_sample_count": 22,
            "exact_preserved_v1_pair_count": 28,
            "exact_stage_6_4_corrective_pair_count": 6,
            "exact_stage_6_9_residual_pair_count": 4,
            "excluded_pair_leakage_count": 0,
        },
        "recipe": fixed_recipe(),
        "training_accounting": {
            "training_run_count": 1,
            "optimizer_step_count": optimizer_steps,
            "train_state_epoch_use_count": EPOCHS * len(train_groups),
            "train_pair_epoch_use_count": EPOCHS * 28,
            "development_training_use_count": 0,
            "extra_training_target_count": 0,
            "fine_tuning_run_count": 0,
            "nonfinite_training_loss_count": (nonfinite_training_loss_count),
        },
        "history": history,
        "final_metrics": final_metrics,
        "checkpoint": str(CHECKPOINT_PATH),
        "checkpoint_sha256": dataset_v1_builder.sha256(CHECKPOINT_PATH),
        "checkpoint_schema_version": checkpoint["schema_version"],
        "checkpoint_save_count": 1,
        "checkpoint_reload_verified": True,
        "forbidden_operation_counts": forbidden,
        "checkpoint_promotion_allowed": False,
        "capability_claim_allowed": False,
        "metric_eligibility": "pipeline_only_not_capability_evidence",
        "threshold_passed": bool(
            optimizer_steps == 60
            and reloaded_metrics == final_metrics
            and not any(forbidden.values())
        ),
    }
    frozen_training.write_report_once(REPORT_PATH, report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return report


def audit() -> dict:
    pairs, hashes, _dataset = validate_inputs()
    report = load_json(REPORT_PATH)
    if (
        report.get("schema_version") != SCHEMA_VERSION
        or report.get("status") != "completed"
        or report.get("frozen_inputs", {}).get("sha256") != hashes
        or report.get("checkpoint_sha256") != dataset_v1_builder.sha256(CHECKPOINT_PATH)
    ):
        raise RuntimeError("residual corrective report contract mismatch")
    model, payload = load_checkpoint(CHECKPOINT_PATH, hashes)
    metrics = evaluate_model(model, pairs)
    if metrics != report.get("final_metrics"):
        raise RuntimeError("independent residual metric/digest mismatch")
    accounting = report.get("training_accounting") or {}
    if (
        accounting.get("training_run_count") != 1
        or accounting.get("optimizer_step_count") != 60
        or accounting.get("train_state_epoch_use_count") != 360
        or accounting.get("train_pair_epoch_use_count") != 560
        or accounting.get("development_training_use_count") != 0
        or accounting.get("extra_training_target_count") != 0
        or accounting.get("fine_tuning_run_count") != 0
        or accounting.get("nonfinite_training_loss_count") != 0
        or len(report.get("history") or []) != 20
        or report.get("checkpoint_save_count") != 1
        or report.get("checkpoint_reload_verified") is not True
        or any(
            int(value) != 0
            for value in (report.get("forbidden_operation_counts") or {}).values()
        )
        or report.get("checkpoint_promotion_allowed") is not False
        or report.get("capability_claim_allowed") is not False
        or report.get("threshold_passed") is not True
    ):
        raise RuntimeError("residual corrective training accounting mismatch")
    if verify_frozen_hashes() != hashes:
        raise RuntimeError("a frozen input changed before audit completion")
    result = {
        "status": "passed",
        "checkpoint_sha256": report["checkpoint_sha256"],
        "report_sha256": dataset_v1_builder.sha256(REPORT_PATH),
        "checkpoint_schema_version": payload["schema_version"],
        "state_dim": payload["recipe"]["state_dim"],
        "action_dim": payload["recipe"]["action_dim"],
        "optimizer_step_count": accounting["optimizer_step_count"],
        "metrics_and_prediction_digests_exact": True,
        "frozen_input_hashes_exact": True,
        "dataset_invariants_exact": True,
        "development_training_use_count": 0,
        "forbidden_operation_count": sum(report["forbidden_operation_counts"].values()),
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--preflight", action="store_true")
    modes.add_argument("--train-once", action="store_true")
    modes.add_argument("--audit", action="store_true")
    args = parser.parse_args()
    if args.preflight:
        preflight()
    elif args.train_once:
        train_once()
    else:
        audit()


if __name__ == "__main__":
    main()
