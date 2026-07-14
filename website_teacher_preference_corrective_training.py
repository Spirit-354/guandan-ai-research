from __future__ import annotations

from collections import defaultdict
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import random
import struct
from typing import Any

import numpy as np

import website_teacher_preference as preference
import website_teacher_preference_corrective_dataset as corrective


SCHEMA_VERSION = "website_teacher_preference_corrective_training_v1"
CHECKPOINT_SCHEMA_VERSION = "website_teacher_preference_corrective_checkpoint_v1"
DATASET_PATH = Path("website_teacher_preference_corrective_dataset_v1.pth")
MANIFEST_PATH = Path("website_teacher_preference_corrective_dataset_v1_manifest.json")
TEACHER_PATH = Path("website_information_set_teacher_dataset_v6.pth")
SPLIT_PATH = Path("website_teacher_preference_split_v1.json")
CONFIRMATION_PATH = Path("website_teacher_preference_unpaired_train_confirmation_v1.json")
OLD_CHECKPOINT_PATH = Path(
    "models_website_teacher_preference_v1/website_teacher_preference_final.pth"
)
ARENA_PATH = Path("website_teacher_preference_arena_smoke20_v1.json")
CHECKPOINT_PATH = Path(
    "models_website_teacher_preference_corrective_v1/"
    "website_teacher_preference_corrective_final.pth"
)
REPORT_PATH = Path("website_teacher_preference_corrective_training_v1.json")
EXPECTED_HASHES = {
    "corrective_dataset": "fad7ae18fea8b02cbc88ad4a8a7f8ecee298abe436ef589f5c88d66e42a32707",
    "corrective_manifest": "0a5dc4f60091338b65f86f83ad30ae55dc18c058ee8b07535a314510ad96ef0a",
    "teacher_dataset": "a74416e6facb28a1bc64563eba90cb33d460dc9e59cc2109518da142465e15f8",
    "split_manifest": "5a15e514dc9bc51d77d300837151d9f1a49250f42885cc7940725bcbe4d35107",
    "stage_6_4_confirmation": "8e17377b5a1523d9f0a47af7218d687e062a3ade671c57f387eb4c1a0888cfae",
    "old_rejected_checkpoint": "c54801a9db05100c2fe5a9bf610a64fc7c94dc2cd947dfaab115ff827bd90919",
    "stage_6_1_arena": "aa45da9de202194102fe8d11e612ad3eb4b51177fd910b9a7948836afd2a1fe6",
}
SEED = 20260714
STATE_DIM = 513
ACTION_DIM = 54
EPOCHS = 20
STATES_PER_BATCH = 6
LEARNING_RATE = 0.001


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_json(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError(f"{path} must contain a JSON object")
    return payload


def torch_load(path: Path) -> Any:
    import torch

    try:
        return torch.load(path, map_location="cpu", weights_only=False)
    except TypeError:
        return torch.load(path, map_location="cpu")


def frozen_paths() -> dict[str, Path]:
    return {
        "corrective_dataset": DATASET_PATH,
        "corrective_manifest": MANIFEST_PATH,
        "teacher_dataset": TEACHER_PATH,
        "split_manifest": SPLIT_PATH,
        "stage_6_4_confirmation": CONFIRMATION_PATH,
        "old_rejected_checkpoint": OLD_CHECKPOINT_PATH,
        "stage_6_1_arena": ARENA_PATH,
    }


def fixed_recipe() -> dict:
    return {
        "device": "cpu",
        "seed": SEED,
        "epochs": EPOCHS,
        "states_per_batch": STATES_PER_BATCH,
        "learning_rate": LEARNING_RATE,
        "initial_checkpoint": None,
        "model_architecture": "danzero_dmc.build_q_model",
        "state_dim": STATE_DIM,
        "action_dim": ACTION_DIM,
        "objective": (
            "mean_states(sum_pairs(within_state_pair_weight*"
            "softplus(Q_rejected-Q_preferred)))"
        ),
    }


def verify_frozen_hashes() -> dict[str, str]:
    actual = {name: sha256(path) for name, path in frozen_paths().items()}
    for name, expected in EXPECTED_HASHES.items():
        if actual.get(name) != expected:
            raise RuntimeError(f"{name} SHA-256 mismatch")
    return actual


def ensure_unused_outputs() -> None:
    paths = [
        CHECKPOINT_PATH,
        REPORT_PATH,
        CHECKPOINT_PATH.with_name(f"{CHECKPOINT_PATH.name}.tmp"),
        REPORT_PATH.with_name(f"{REPORT_PATH.name}.tmp"),
    ]
    existing = [str(path) for path in paths if path.exists()]
    if existing:
        raise RuntimeError("corrective training output already exists: " + ", ".join(existing))


def _expected_pairs(
    samples: list[dict], split: dict, confirmation: dict
) -> list[dict]:
    train_ids = {str(value) for value in split["pipeline_train_game_ids"]}
    development_ids = {
        str(value) for value in split["pipeline_development_game_ids"]
    }
    supported, inconclusive = corrective.select_confirmation_cases(confirmation)
    if len(supported) != 6 or len(inconclusive) != 3:
        raise RuntimeError("Stage 6.4 confirmation case accounting mismatch")
    supported_by_key = {
        (str(case["game_id"]), int(case["turn_index"])): case for case in supported
    }
    pairs: list[dict] = []
    for index, sample in enumerate(samples):
        game_id = str(sample["game_id"])
        if game_id in train_ids:
            partition = "pipeline_train"
        elif game_id in development_ids:
            partition = "pipeline_development"
        else:
            raise RuntimeError("base sample has no frozen pipeline partition")
        pairs.append(corrective.base_pair(sample, index, partition))
        key = (game_id, int(sample["turn_index"]))
        if key in supported_by_key:
            if partition != "pipeline_train":
                raise RuntimeError("corrective pair leaked into development")
            pairs.append(corrective.corrective_pair(sample, index, supported_by_key[key]))
    corrective.apply_state_balanced_weights(pairs)
    return pairs


def validate_inputs() -> tuple[list[dict], dict[str, str], dict]:
    actual_hashes = verify_frozen_hashes()
    dataset = torch_load(DATASET_PATH)
    manifest = load_json(MANIFEST_PATH)
    split = load_json(SPLIT_PATH)
    confirmation = load_json(CONFIRMATION_PATH)
    arena = load_json(ARENA_PATH)
    samples, _summary, teacher_hash = preference.load_teacher_dataset(TEACHER_PATH)
    if teacher_hash != EXPECTED_HASHES["teacher_dataset"]:
        raise RuntimeError("teacher loader hash mismatch")
    expected_pairs = _expected_pairs(samples, split, confirmation)
    pairs = dataset.get("pairs") if isinstance(dataset, dict) else None
    expected_summary = {
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
    if (
        dataset.get("format") != corrective.FORMAT_VERSION
        or dataset.get("summary") != expected_summary
        or corrective.canonical_sha256(pairs) != corrective.canonical_sha256(expected_pairs)
        or dataset.get("frozen_base_samples") != samples
        or dataset.get("frozen_base_sample_count") != 22
        or dataset.get("frozen_base_samples_sha256")
        != corrective.canonical_sha256(samples)
        or any(
            int(value) != 0
            for value in (dataset.get("forbidden_operation_counts") or {}).values()
        )
    ):
        raise RuntimeError("corrective dataset validation mismatch")
    if (
        manifest.get("schema_version") != corrective.MANIFEST_SCHEMA_VERSION
        or manifest.get("dataset_sha256") != actual_hashes["corrective_dataset"]
        or manifest.get("summary") != expected_summary
        or manifest.get("pair_ids") != [pair["pair_id"] for pair in pairs]
        or manifest.get("objective_manifest") != dataset.get("objective_manifest")
        or manifest.get("status") != "completed"
        or any(
            int(value) != 0
            for value in (manifest.get("forbidden_operation_counts") or {}).values()
        )
    ):
        raise RuntimeError("corrective dataset manifest validation mismatch")
    if (
        arena.get("requested_games") != 20
        or arena.get("completed_games") != 20
        or arena.get("model_wins") != 0
        or arena.get("baseline_wins") != 20
        or arena.get("early_screen_continuation_allowed") is not False
        or arena.get("checkpoint_promotion_allowed") is not False
    ):
        raise RuntimeError("Stage 6.1 rejected-checkpoint conclusion mismatch")
    groups = build_state_groups(pairs)
    train_groups = [group for group in groups if group["pipeline_partition"] == "pipeline_train"]
    development_groups = [
        group for group in groups if group["pipeline_partition"] == "pipeline_development"
    ]
    if (
        len(pairs) != 28
        or sum(len(group["pairs"]) for group in train_groups) != 24
        or sum(len(group["pairs"]) for group in development_groups) != 4
        or len(train_groups) != 18
        or len(development_groups) != 4
        or {group["key"] for group in train_groups}
        & {group["key"] for group in development_groups}
    ):
        raise RuntimeError("corrective train/development isolation mismatch")
    return pairs, actual_hashes, dataset


def build_state_groups(pairs: list[dict]) -> list[dict]:
    grouped: dict[tuple[str, int], list[dict]] = defaultdict(list)
    order: list[tuple[str, int]] = []
    for pair in pairs:
        key = (str(pair["game_id"]), int(pair["turn_index"]))
        if key not in grouped:
            order.append(key)
        grouped[key].append(pair)
    result: list[dict] = []
    for key in order:
        state_pairs = grouped[key]
        partitions = {pair["pipeline_partition"] for pair in state_pairs}
        states = {corrective.canonical_sha256(pair["state"]) for pair in state_pairs}
        weight_sum = sum(float(pair["within_state_pair_weight"]) for pair in state_pairs)
        if len(partitions) != 1 or len(states) != 1 or not math.isclose(weight_sum, 1.0):
            raise RuntimeError(f"invalid state group {key}")
        result.append(
            {
                "key": key,
                "pipeline_partition": state_pairs[0]["pipeline_partition"],
                "state": state_pairs[0]["state"],
                "pairs": state_pairs,
            }
        )
    return result


def state_balanced_batch_loss(model: Any, groups: list[dict]) -> Any:
    import torch
    import torch.nn.functional as functional

    state_losses = []
    for group in groups:
        pairs = group["pairs"]
        states = torch.tensor(
            np.asarray([group["state"]] * len(pairs), dtype=np.float32)
        )
        preferred = torch.tensor(
            np.asarray([pair["preferred_action"] for pair in pairs], dtype=np.float32)
        )
        rejected = torch.tensor(
            np.asarray([pair["rejected_action"] for pair in pairs], dtype=np.float32)
        )
        weights = torch.tensor(
            [float(pair["within_state_pair_weight"]) for pair in pairs],
            dtype=torch.float32,
        )
        losses = functional.softplus(model(states, rejected) - model(states, preferred))
        state_losses.append((losses * weights).sum())
    return torch.stack(state_losses).mean()


def _pair_metrics(pairs: list[dict], preferred: Any, rejected: Any) -> dict:
    import torch
    import torch.nn.functional as functional

    margins = preferred - rejected
    losses = functional.softplus(-margins)
    finite = torch.isfinite(preferred) & torch.isfinite(rejected)
    finite &= torch.isfinite(margins) & torch.isfinite(losses)
    digest = hashlib.sha256()
    for pair, preferred_value, rejected_value in zip(
        pairs, preferred.tolist(), rejected.tolist()
    ):
        digest.update(f"{pair['pair_id']}\n".encode("utf-8"))
        digest.update(struct.pack("<ff", float(preferred_value), float(rejected_value)))
    return {
        "pair_count": len(pairs),
        "mean_pairwise_loss": float(losses.mean().item()),
        "pair_ranking_accuracy": float((margins > 0.0).float().mean().item()),
        "mean_preferred_minus_rejected_margin": float(margins.mean().item()),
        "prediction_sha256": digest.hexdigest(),
        "nonfinite_value_count": int((~finite).sum().item()),
    }


def evaluate_partition(model: Any, pairs: list[dict]) -> dict:
    import torch
    import torch.nn.functional as functional

    if not pairs:
        raise RuntimeError("cannot evaluate an empty pair partition")
    model.eval()
    states = torch.tensor(np.asarray([pair["state"] for pair in pairs], dtype=np.float32))
    preferred_actions = torch.tensor(
        np.asarray([pair["preferred_action"] for pair in pairs], dtype=np.float32)
    )
    rejected_actions = torch.tensor(
        np.asarray([pair["rejected_action"] for pair in pairs], dtype=np.float32)
    )
    with torch.no_grad():
        preferred = model(states, preferred_actions)
        rejected = model(states, rejected_actions)
        losses = functional.softplus(rejected - preferred)
    aggregate = _pair_metrics(pairs, preferred, rejected)
    by_key: dict[tuple[str, int], float] = defaultdict(float)
    for pair, loss in zip(pairs, losses.tolist()):
        key = (str(pair["game_id"]), int(pair["turn_index"]))
        by_key[key] += float(pair["within_state_pair_weight"]) * float(loss)
    aggregate["state_count"] = len(by_key)
    aggregate["state_balanced_loss"] = sum(by_key.values()) / len(by_key)
    return aggregate


def evaluate_model(model: Any, pairs: list[dict]) -> dict:
    train_pairs = [pair for pair in pairs if pair["pipeline_partition"] == "pipeline_train"]
    development_pairs = [
        pair for pair in pairs if pair["pipeline_partition"] == "pipeline_development"
    ]
    train_base = [pair for pair in train_pairs if pair["pair_source"] == "frozen_teacher_v6"]
    train_corrective = [
        pair for pair in train_pairs if pair["pair_source"] == "stage_6_4_train_confirmation"
    ]
    return {
        "pipeline_train": {
            "aggregate": evaluate_partition(model, train_pairs),
            "base_pairs": evaluate_partition(model, train_base),
            "corrective_pairs": evaluate_partition(model, train_corrective),
        },
        "pipeline_development": {
            "aggregate": evaluate_partition(model, development_pairs),
        },
    }


def set_deterministic() -> None:
    import torch

    random.seed(SEED)
    np.random.seed(SEED)
    torch.manual_seed(SEED)
    torch.set_num_threads(1)
    torch.use_deterministic_algorithms(True)


def checkpoint_payload(model: Any, hashes: dict[str, str]) -> dict:
    return {
        "schema_version": CHECKPOINT_SCHEMA_VERSION,
        "model_state_dict": {
            key: value.detach().cpu() for key, value in model.state_dict().items()
        },
        "frozen_input_hashes": dict(hashes),
        "recipe": fixed_recipe(),
        "training_mode": "state_balanced_corrective_pairwise_softplus",
        "pipeline_train_state_count": 18,
        "pipeline_train_pair_count": 24,
        "pipeline_development_training_use_count": 0,
        "extra_training_target_count": 0,
        "capability_claim_allowed": False,
        "checkpoint_promotion_allowed": False,
    }


def save_checkpoint_once(path: Path, payload: dict) -> None:
    import torch

    temporary = path.with_name(f"{path.name}.tmp")
    if path.exists() or temporary.exists():
        raise RuntimeError("corrective checkpoint output already exists")
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        torch.save(payload, temporary)
        temporary.replace(path)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise


def load_checkpoint(path: Path, hashes: dict[str, str]) -> tuple[Any, dict]:
    import torch
    import danzero_dmc

    payload = torch_load(path)
    required = {
        "schema_version": CHECKPOINT_SCHEMA_VERSION,
        "frozen_input_hashes": hashes,
        "recipe": fixed_recipe(),
        "training_mode": "state_balanced_corrective_pairwise_softplus",
        "pipeline_train_state_count": 18,
        "pipeline_train_pair_count": 24,
        "pipeline_development_training_use_count": 0,
        "extra_training_target_count": 0,
        "capability_claim_allowed": False,
        "checkpoint_promotion_allowed": False,
    }
    for key, expected in required.items():
        if payload.get(key) != expected:
            raise RuntimeError(f"corrective checkpoint {key} mismatch")
    model = danzero_dmc.build_q_model(torch.device("cpu"))
    model.load_state_dict(payload["model_state_dict"])
    model.eval()
    return model, payload


def write_report_once(path: Path, report: dict) -> None:
    temporary = path.with_name(f"{path.name}.tmp")
    if path.exists() or temporary.exists():
        raise RuntimeError("corrective training report already exists")
    try:
        with temporary.open("x", encoding="utf-8") as handle:
            json.dump(report, handle, ensure_ascii=False, indent=2, allow_nan=False)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        temporary.replace(path)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise


def preflight() -> dict:
    ensure_unused_outputs()
    pairs, hashes, _dataset = validate_inputs()
    groups = build_state_groups(pairs)
    result = {
        "status": "ready",
        "frozen_input_hashes": hashes,
        "total_pair_count": len(pairs),
        "pipeline_train_pair_count": sum(
            1 for pair in pairs if pair["pipeline_partition"] == "pipeline_train"
        ),
        "pipeline_development_pair_count": sum(
            1 for pair in pairs if pair["pipeline_partition"] == "pipeline_development"
        ),
        "pipeline_train_state_count": sum(
            1 for group in groups if group["pipeline_partition"] == "pipeline_train"
        ),
        "pipeline_development_state_count": sum(
            1 for group in groups if group["pipeline_partition"] == "pipeline_development"
        ),
        "recipe": fixed_recipe(),
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return result


def train_once() -> dict:
    import torch
    import danzero_dmc

    ensure_unused_outputs()
    pairs, hashes, _dataset = validate_inputs()
    groups = build_state_groups(pairs)
    train_groups = [group for group in groups if group["pipeline_partition"] == "pipeline_train"]
    development_groups = [
        group for group in groups if group["pipeline_partition"] == "pipeline_development"
    ]
    if len(train_groups) != 18 or len(development_groups) != 4:
        raise RuntimeError("fixed training partition mismatch")
    set_deterministic()
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
            loss = state_balanced_batch_loss(model, batch)
            if not bool(torch.isfinite(loss).item()):
                nonfinite_training_loss_count += 1
                raise RuntimeError("nonfinite corrective training loss")
            optimizer.zero_grad()
            loss.backward()
            optimizer.step()
            optimizer_steps += 1
            batch_losses.append(float(loss.item()))
        history.append(
            {
                "epoch": epoch,
                "mean_batch_state_balanced_loss": sum(batch_losses) / len(batch_losses),
            }
        )
    final_metrics = evaluate_model(model, pairs)
    if any(
        section["nonfinite_value_count"] != 0
        for partition in final_metrics.values()
        for section in partition.values()
    ):
        raise RuntimeError("nonfinite corrective prediction")
    save_checkpoint_once(CHECKPOINT_PATH, checkpoint_payload(model, hashes))
    reloaded_model, checkpoint = load_checkpoint(CHECKPOINT_PATH, hashes)
    reloaded_metrics = evaluate_model(reloaded_model, pairs)
    if reloaded_metrics != final_metrics:
        raise RuntimeError("corrective checkpoint reload metrics mismatch")
    if verify_frozen_hashes() != hashes:
        raise RuntimeError("a frozen input changed during corrective training")
    forbidden = {
        "rollout_runs": 0,
        "hyperparameter_searches": 0,
        "checkpoint_selections": 0,
        "locked_test_loads": 0,
        "website_dataset_loads": 0,
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
            "total_pair_count": 28,
            "pipeline_train_state_count": 18,
            "pipeline_train_pair_count": 24,
            "pipeline_development_state_count": 4,
            "pipeline_development_pair_count": 4,
            "exact_base_sample_count": 22,
            "exact_corrective_pair_count": 6,
            "excluded_pair_leakage_count": 0,
        },
        "recipe": fixed_recipe(),
        "training_accounting": {
            "training_run_count": 1,
            "optimizer_step_count": optimizer_steps,
            "train_state_epoch_use_count": EPOCHS * len(train_groups),
            "train_pair_epoch_use_count": EPOCHS * 24,
            "development_training_use_count": 0,
            "extra_training_target_count": 0,
            "nonfinite_training_loss_count": nonfinite_training_loss_count,
        },
        "history": history,
        "final_metrics": final_metrics,
        "checkpoint": str(CHECKPOINT_PATH),
        "checkpoint_sha256": sha256(CHECKPOINT_PATH),
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
    write_report_once(REPORT_PATH, report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return report


def audit() -> dict:
    pairs, hashes, _dataset = validate_inputs()
    report = load_json(REPORT_PATH)
    if report.get("schema_version") != SCHEMA_VERSION or report.get("status") != "completed":
        raise RuntimeError("corrective training report schema/status mismatch")
    if report.get("frozen_inputs", {}).get("sha256") != hashes:
        raise RuntimeError("corrective report frozen hashes mismatch")
    if report.get("checkpoint_sha256") != sha256(CHECKPOINT_PATH):
        raise RuntimeError("corrective checkpoint report hash mismatch")
    model, payload = load_checkpoint(CHECKPOINT_PATH, hashes)
    metrics = evaluate_model(model, pairs)
    if metrics != report.get("final_metrics"):
        raise RuntimeError("independent corrective metric/digest mismatch")
    if (
        report.get("training_accounting", {}).get("training_run_count") != 1
        or report.get("training_accounting", {}).get("development_training_use_count") != 0
        or report.get("training_accounting", {}).get("optimizer_step_count") != 60
        or any(int(value) != 0 for value in report.get("forbidden_operation_counts", {}).values())
        or report.get("threshold_passed") is not True
    ):
        raise RuntimeError("corrective training accounting mismatch")
    result = {
        "status": "passed",
        "checkpoint_sha256": report["checkpoint_sha256"],
        "checkpoint_schema_version": payload["schema_version"],
        "state_dim": payload["recipe"]["state_dim"],
        "action_dim": payload["recipe"]["action_dim"],
        "metrics_and_prediction_digests_exact": True,
        "frozen_input_hashes_exact": True,
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
