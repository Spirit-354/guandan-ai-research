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
import website_teacher_preference_corrective_dataset as dataset_v1_builder
import website_teacher_preference_corrective_dataset_v3 as dataset_v3_builder
import website_teacher_preference_corrective_training as frozen_training
import website_teacher_preference_residual_corrective_training as recipe_authority


SCHEMA_VERSION = "website_teacher_preference_remaining_corrective_training_v1"
CHECKPOINT_SCHEMA_VERSION = (
    "website_teacher_preference_remaining_corrective_checkpoint_v1"
)
DATASET_PATH = Path("website_teacher_preference_corrective_dataset_v3.pth")
MANIFEST_PATH = Path("website_teacher_preference_corrective_dataset_v3_manifest.json")
DATASET_BUILDER_PATH = Path("website_teacher_preference_corrective_dataset_v3.py")
RECIPE_AUTHORITY_PATH = Path(
    "website_teacher_preference_residual_corrective_training_v1.json"
)
RECIPE_IMPLEMENTATION_PATH = Path(
    "website_teacher_preference_residual_corrective_training.py"
)
CHECKPOINT_PATH = Path(
    "models_website_teacher_preference_remaining_corrective_v1/"
    "website_teacher_preference_remaining_corrective_final.pth"
)
REPORT_PATH = Path("website_teacher_preference_remaining_corrective_training_v1.json")
EXPECTED_HASHES = {
    "corrective_dataset_v3": (
        "71e90241170882dd97893e71fbe0694368af96525737b55370cd0a60e098ce6f"
    ),
    "corrective_manifest_v3": (
        "c9b25d75da0fc5966e1f29bcbd50dd471971e16fc9f4a368cda5b5ba2f8d822d"
    ),
    "stage_6_15_dataset_builder": (
        "df44cdc1c1e45ddea310324393b2ec0d1693523480b3f78ef4bf70fd369a8d97"
    ),
    "stage_6_11_recipe_authority": (
        "307b92eca7aef2d7fa927dec71f1e2ccd8b87b71d2336c5630f39c24d0a176dd"
    ),
    "stage_6_11_implementation": (
        "cc1c6263644635da01822f9ce8f231610b997d7ddbac932ba19efb24a905f00c"
    ),
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
        **dataset_v3_builder.frozen_paths(),
        "corrective_dataset_v3": DATASET_PATH,
        "corrective_manifest_v3": MANIFEST_PATH,
        "stage_6_15_dataset_builder": DATASET_BUILDER_PATH,
        "stage_6_11_recipe_authority": RECIPE_AUTHORITY_PATH,
        "stage_6_11_implementation": RECIPE_IMPLEMENTATION_PATH,
    }


def fixed_recipe() -> dict:
    recipe = recipe_authority.fixed_recipe()
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
        raise RuntimeError("Stage 6.11 fixed recipe changed")
    return recipe


def verify_frozen_hashes() -> dict[str, str]:
    recursive = dataset_v3_builder.verify_frozen_inputs()
    specific_paths = {
        "corrective_dataset_v3": DATASET_PATH,
        "corrective_manifest_v3": MANIFEST_PATH,
        "stage_6_15_dataset_builder": DATASET_BUILDER_PATH,
        "stage_6_11_recipe_authority": RECIPE_AUTHORITY_PATH,
        "stage_6_11_implementation": RECIPE_IMPLEMENTATION_PATH,
    }
    specific = {
        name: dataset_v1_builder.sha256(path)
        for name, path in specific_paths.items()
    }
    for name, expected in EXPECTED_HASHES.items():
        if specific.get(name) != expected:
            raise RuntimeError(f"{name} SHA-256 mismatch")
    return {**recursive, **specific}


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
            "remaining corrective training output already exists: "
            + ", ".join(existing)
        )


def forbidden_operation_counts() -> dict[str, int]:
    return {
        "rollout_runs": 0,
        "label_or_pair_additions": 0,
        "objective_definitions": 0,
        "objective_tuning_runs": 0,
        "fine_tuning_runs": 0,
        "hyperparameter_searches": 0,
        "threshold_tuning_runs": 0,
        "initial_checkpoint_loads": 0,
        "extra_training_configurations": 0,
        "checkpoint_selections": 0,
        "locked_test_loads": 0,
        "complete_website_dataset_loads": 0,
        "full_legal_set_diagnosis_runs": 0,
        "arena_games": 0,
        "website_shadow_games": 0,
        "website_games": 0,
        "model_controlled_website_actions": 0,
        "checkpoint_promotions": 0,
        "capability_claims": 0,
    }


def validate_inputs() -> tuple[list[dict], dict[str, str], dict]:
    hashes = verify_frozen_hashes()
    dataset = frozen_training.torch_load(DATASET_PATH)
    manifest = load_json(MANIFEST_PATH)
    recipe_report = load_json(RECIPE_AUTHORITY_PATH)
    context = dataset_v3_builder.load_context()
    expected_dataset, expected_manifest = dataset_v3_builder.build_payload(context)
    if not isinstance(dataset, dict):
        raise RuntimeError("corrective dataset v3 must contain a dictionary")
    if dataset_v1_builder.canonical_sha256(dataset) != (
        dataset_v1_builder.canonical_sha256(expected_dataset)
    ):
        raise RuntimeError("corrective dataset v3 reconstruction mismatch")
    manifest_without_dataset_hash = copy.deepcopy(manifest)
    manifest_without_dataset_hash.pop("dataset_sha256", None)
    if dataset_v1_builder.canonical_sha256(manifest_without_dataset_hash) != (
        dataset_v1_builder.canonical_sha256(expected_manifest)
    ):
        raise RuntimeError("corrective manifest v3 reconstruction mismatch")
    if (
        manifest.get("dataset_sha256") != hashes["corrective_dataset_v3"]
        or dataset.get("frozen_input_hashes") != context["frozen_hashes"]
        or manifest.get("frozen_inputs", {}).get("sha256")
        != context["frozen_hashes"]
    ):
        raise RuntimeError("corrective dataset v3 frozen hash mismatch")
    accounting = recipe_report.get("training_accounting") or {}
    if (
        recipe_report.get("schema_version") != recipe_authority.SCHEMA_VERSION
        or recipe_report.get("status") != "completed"
        or recipe_report.get("recipe") != fixed_recipe()
        or accounting.get("training_run_count") != 1
        or accounting.get("optimizer_step_count") != 60
        or accounting.get("train_state_epoch_use_count") != 360
        or accounting.get("train_pair_epoch_use_count") != 560
        or accounting.get("development_training_use_count") != 0
        or recipe_report.get("checkpoint_promotion_allowed") is not False
        or recipe_report.get("capability_claim_allowed") is not False
    ):
        raise RuntimeError("Stage 6.11 recipe authority mismatch")
    pairs = dataset.get("pairs") or []
    groups = frozen_training.build_state_groups(pairs)
    train_groups = [
        group for group in groups if group["pipeline_partition"] == "pipeline_train"
    ]
    development_groups = [
        group
        for group in groups
        if group["pipeline_partition"] == "pipeline_development"
    ]
    source_counts = Counter(pair.get("pair_source") for pair in pairs)
    partition_counts = Counter(pair.get("pipeline_partition") for pair in pairs)
    state_size_counts = Counter(len(group["pairs"]) for group in groups)
    partition_weight_sums = {
        partition: sum(
            float(pair["partition_normalized_pair_weight"])
            for pair in pairs
            if pair["pipeline_partition"] == partition
        )
        for partition in ("pipeline_train", "pipeline_development")
    }
    if (
        dataset.get("format") != dataset_v3_builder.FORMAT_VERSION
        or len(pairs) != 34
        or len(train_groups) != 18
        or len(development_groups) != 4
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
        or state_size_counts != Counter({1: 13, 2: 6, 3: 3})
        or any(
            not math.isclose(
                sum(
                    float(pair["within_state_pair_weight"])
                    for pair in group["pairs"]
                ),
                1.0,
                abs_tol=1e-12,
            )
            for group in groups
        )
        or any(
            not math.isclose(value, 1.0, abs_tol=1e-12)
            for value in partition_weight_sums.values()
        )
        or {group["key"] for group in train_groups}
        & {group["key"] for group in development_groups}
        or any(
            int(value) != 0
            for value in (dataset.get("forbidden_operation_counts") or {}).values()
        )
        or any(
            int(value) != 0
            for value in (manifest.get("forbidden_operation_counts") or {}).values()
        )
    ):
        raise RuntimeError("corrective dataset v3 accounting/isolation mismatch")
    return pairs, hashes, dataset


def evaluate_model(model: Any, pairs: list[dict]) -> dict:
    train_pairs = [
        pair for pair in pairs if pair["pipeline_partition"] == "pipeline_train"
    ]
    development_pairs = [
        pair
        for pair in pairs
        if pair["pipeline_partition"] == "pipeline_development"
    ]
    source_sections = {
        "base_pairs": "frozen_teacher_v6",
        "stage_6_4_corrective_pairs": "stage_6_4_train_confirmation",
        "stage_6_9_residual_pairs": "stage_6_9_residual_train_confirmation",
        "stage_6_14e_remaining_pairs": (
            "stage_6_14e_remaining_train_confirmation"
        ),
    }
    train_metrics = {
        "aggregate": frozen_training.evaluate_partition(model, train_pairs)
    }
    for section, source in source_sections.items():
        train_metrics[section] = frozen_training.evaluate_partition(
            model, [pair for pair in train_pairs if pair["pair_source"] == source]
        )
    return {
        "pipeline_train": train_metrics,
        "pipeline_development": {
            "aggregate": frozen_training.evaluate_partition(
                model, development_pairs
            )
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
        "training_mode": "state_balanced_remaining_corrective_pairwise_softplus",
        "pipeline_train_state_count": 18,
        "pipeline_train_pair_count": 30,
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
        "training_mode": "state_balanced_remaining_corrective_pairwise_softplus",
        "pipeline_train_state_count": 18,
        "pipeline_train_pair_count": 30,
        "pipeline_development_training_use_count": 0,
        "extra_training_target_count": 0,
        "fine_tuning_run_count": 0,
        "capability_claim_allowed": False,
        "checkpoint_promotion_allowed": False,
    }
    for key, expected in required.items():
        if payload.get(key) != expected:
            raise RuntimeError(f"remaining corrective checkpoint {key} mismatch")
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
            group["pipeline_partition"] == "pipeline_development"
            for group in groups
        ),
        "train_pair_source_counts": dict(
            Counter(
                pair["pair_source"]
                for pair in pairs
                if pair["pipeline_partition"] == "pipeline_train"
            )
        ),
        "recipe": fixed_recipe(),
        "expected_optimizer_step_count": 60,
        "expected_train_state_epoch_use_count": 360,
        "expected_train_pair_epoch_use_count": 600,
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
        or sum(len(group["pairs"]) for group in train_groups) != 30
        or sum(len(group["pairs"]) for group in development_groups) != 4
    ):
        raise RuntimeError("fixed remaining corrective partition mismatch")
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
                raise RuntimeError("nonfinite remaining corrective training loss")
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
        raise RuntimeError("nonfinite remaining corrective prediction")
    if optimizer_steps != 60:
        raise RuntimeError("remaining corrective optimizer accounting mismatch")
    frozen_training.save_checkpoint_once(
        CHECKPOINT_PATH, checkpoint_payload(model, hashes)
    )
    reloaded_model, checkpoint = load_checkpoint(CHECKPOINT_PATH, hashes)
    reloaded_metrics = evaluate_model(reloaded_model, pairs)
    if reloaded_metrics != final_metrics:
        raise RuntimeError("remaining corrective checkpoint reload mismatch")
    if verify_frozen_hashes() != hashes:
        raise RuntimeError("a frozen input changed during training")
    forbidden = forbidden_operation_counts()
    report = {
        "schema_version": SCHEMA_VERSION,
        "status": "completed",
        "frozen_inputs": {
            "paths": {name: str(path) for name, path in frozen_paths().items()},
            "sha256": hashes,
        },
        "dataset_validation": {
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
        },
        "recipe": fixed_recipe(),
        "training_accounting": {
            "training_run_count": 1,
            "optimizer_step_count": optimizer_steps,
            "train_state_epoch_use_count": EPOCHS * len(train_groups),
            "train_pair_epoch_use_count": EPOCHS * 30,
            "development_training_use_count": 0,
            "extra_training_target_count": 0,
            "fine_tuning_run_count": 0,
            "nonfinite_training_loss_count": nonfinite_training_loss_count,
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
            and EPOCHS * len(train_groups) == 360
            and EPOCHS * 30 == 600
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
        or report.get("frozen_inputs", {}).get("paths")
        != {name: str(path) for name, path in frozen_paths().items()}
        or report.get("frozen_inputs", {}).get("sha256") != hashes
        or report.get("recipe") != fixed_recipe()
        or report.get("checkpoint_sha256")
        != dataset_v1_builder.sha256(CHECKPOINT_PATH)
    ):
        raise RuntimeError("remaining corrective report contract mismatch")
    model, payload = load_checkpoint(CHECKPOINT_PATH, hashes)
    metrics = evaluate_model(model, pairs)
    if metrics != report.get("final_metrics"):
        raise RuntimeError("independent remaining metric/digest mismatch")
    accounting = report.get("training_accounting") or {}
    validation = report.get("dataset_validation") or {}
    if (
        validation
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
        or len(report.get("history") or []) != 20
        or report.get("checkpoint_save_count") != 1
        or report.get("checkpoint_reload_verified") is not True
        or report.get("checkpoint_schema_version") != payload["schema_version"]
        or report.get("forbidden_operation_counts")
        != forbidden_operation_counts()
        or report.get("checkpoint_promotion_allowed") is not False
        or report.get("capability_claim_allowed") is not False
        or report.get("threshold_passed") is not True
    ):
        raise RuntimeError("remaining corrective training accounting mismatch")
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
        "train_state_epoch_use_count": accounting["train_state_epoch_use_count"],
        "train_pair_epoch_use_count": accounting["train_pair_epoch_use_count"],
        "metrics_and_prediction_digests_exact": True,
        "frozen_input_hashes_exact": True,
        "dataset_invariants_exact": True,
        "development_training_use_count": 0,
        "forbidden_operation_count": sum(
            report["forbidden_operation_counts"].values()
        ),
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
