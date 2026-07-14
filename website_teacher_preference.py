from __future__ import annotations

import hashlib
import json
import math
import random
import struct
from pathlib import Path
from typing import Any

import numpy as np


SCHEMA_VERSION = "website_teacher_preference_training_v1"
SPLIT_SCHEMA_VERSION = "website_teacher_preference_split_v1"
CHECKPOINT_SCHEMA_VERSION = "website_teacher_preference_checkpoint_v1"
TEACHER_SCHEMA_VERSION = "website_information_set_teacher_v1"
EXPECTED_TEACHER_SHA256 = "a74416e6facb28a1bc64563eba90cb33d460dc9e59cc2109518da142465e15f8"
SPLIT_NAMESPACE = "website_teacher_v6_split_v1:"
SEED = 20260714
STATE_DIM = 513
ACTION_DIM = 54
DEVELOPMENT_GAME_COUNT = 4
EPOCHS = 20
BATCH_SIZE = 6
LEARNING_RATE = 0.001


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _torch_load(path: Path, *, map_location: Any = "cpu") -> Any:
    import torch

    try:
        return torch.load(path, map_location=map_location, weights_only=False)
    except TypeError:
        return torch.load(path, map_location=map_location)


def _finite_vector(value: Any, size: int) -> bool:
    return bool(
        isinstance(value, list)
        and len(value) == size
        and all(math.isfinite(float(item)) for item in value)
    )


def load_teacher_dataset(
    path: Path, *, expected_sha256: str = EXPECTED_TEACHER_SHA256
) -> tuple[list[dict], dict, str]:
    actual_sha256 = _sha256(path)
    if actual_sha256 != expected_sha256:
        raise RuntimeError(
            f"teacher dataset SHA-256 mismatch: expected {expected_sha256}, got {actual_sha256}"
        )
    payload = _torch_load(path)
    if not isinstance(payload, dict) or payload.get("format") != TEACHER_SCHEMA_VERSION:
        raise RuntimeError("teacher dataset format mismatch")
    summary = payload.get("summary") or {}
    samples = payload.get("samples") or []
    required_summary = {
        "schema_version": TEACHER_SCHEMA_VERSION,
        "accepted_teacher_label_count": 22,
        "independent_teacher_games": 22,
        "training_gate_passed": True,
        "locked_test_loaded": False,
        "capability_claim_allowed": False,
        "threshold_passed": True,
        "source_base_partition_role": "train_development",
        "state_dim": STATE_DIM,
        "action_dim": ACTION_DIM,
    }
    for key, expected in required_summary.items():
        if summary.get(key) != expected:
            raise RuntimeError(f"teacher summary {key} mismatch")
    if len(samples) != 22:
        raise RuntimeError("teacher dataset must contain exactly 22 labels")
    game_ids: set[str] = set()
    for index, sample in enumerate(samples):
        prefix = f"teacher sample {index}"
        if sample.get("game_id") is None or sample.get("turn_index") is None:
            raise RuntimeError(f"{prefix} is missing its source key")
        game_id = str(sample.get("game_id"))
        if game_id in game_ids:
            raise RuntimeError(f"{prefix} duplicates game_id {game_id}")
        game_ids.add(game_id)
        state = sample.get("state")
        teacher_action = sample.get("teacher_action")
        behavior_action = sample.get("behavior_action")
        legal_actions = sample.get("legal_actions") or []
        if sample.get("state_dim") != STATE_DIM or not _finite_vector(state, STATE_DIM):
            raise RuntimeError(f"{prefix} has invalid state")
        if sample.get("action_dim") != ACTION_DIM:
            raise RuntimeError(f"{prefix} has invalid action dimension")
        if not _finite_vector(teacher_action, ACTION_DIM) or not _finite_vector(
            behavior_action, ACTION_DIM
        ):
            raise RuntimeError(f"{prefix} has invalid preference action")
        if teacher_action == behavior_action:
            raise RuntimeError(f"{prefix} has identical teacher and behavior actions")
        if not legal_actions or any(
            not _finite_vector(action, ACTION_DIM) for action in legal_actions
        ):
            raise RuntimeError(f"{prefix} has invalid legal actions")
        if teacher_action not in legal_actions or behavior_action not in legal_actions:
            raise RuntimeError(f"{prefix} preference action is not legal")
        if sample.get("split") != "train":
            raise RuntimeError(f"{prefix} is not train-only")
        if sample.get("source_dataset_partition") != "train_development":
            raise RuntimeError(f"{prefix} source partition mismatch")
        if sample.get("locked_test_used") is not False:
            raise RuntimeError(f"{prefix} reports locked-test use")
        if sample.get("preference_target") != "teacher_action_beats_behavior_action":
            raise RuntimeError(f"{prefix} preference target mismatch")
    if len(game_ids) != 22:
        raise RuntimeError("teacher dataset must contain 22 independent games")
    return samples, summary, actual_sha256


def split_game_ids(samples: list[dict]) -> tuple[list[str], list[str]]:
    game_ids = {str(sample["game_id"]) for sample in samples}
    if len(game_ids) != 22:
        raise RuntimeError("frozen teacher split requires exactly 22 games")
    ordered = sorted(
        game_ids,
        key=lambda game_id: (
            hashlib.sha256(f"{SPLIT_NAMESPACE}{game_id}".encode("utf-8")).hexdigest(),
            game_id,
        ),
    )
    development_ids = ordered[:DEVELOPMENT_GAME_COUNT]
    train_ids = ordered[DEVELOPMENT_GAME_COUNT:]
    return train_ids, development_ids


def build_split_manifest(
    samples: list[dict], teacher_path: Path, teacher_sha256: str
) -> dict:
    train_ids, development_ids = split_game_ids(samples)
    overlap = sorted(set(train_ids) & set(development_ids))
    return {
        "schema_version": SPLIT_SCHEMA_VERSION,
        "teacher_dataset": str(teacher_path),
        "teacher_sha256": teacher_sha256,
        "split_namespace": SPLIT_NAMESPACE,
        "split_method": "sha256_namespace_game_id_ascending_first_4_development",
        "seed": SEED,
        "source_sample_split": "train",
        "pipeline_train_game_ids": train_ids,
        "pipeline_development_game_ids": development_ids,
        "pipeline_train_game_count": len(train_ids),
        "pipeline_development_game_count": len(development_ids),
        "total_game_count": len(train_ids) + len(development_ids),
        "overlap_game_ids": overlap,
        "dropped_game_ids": [],
        "locked_test_loaded": False,
        "capability_claim_allowed": False,
        "threshold_passed": bool(
            len(train_ids) == 18
            and len(development_ids) == 4
            and not overlap
            and len(set(train_ids) | set(development_ids)) == 22
        ),
    }


def pairwise_ranking_loss(teacher_values: Any, behavior_values: Any) -> Any:
    import torch.nn.functional as functional

    return functional.softplus(behavior_values - teacher_values).mean()


def _ordered_samples(samples: list[dict], game_ids: list[str]) -> list[dict]:
    positions = {game_id: index for index, game_id in enumerate(game_ids)}
    return sorted(
        (sample for sample in samples if str(sample["game_id"]) in positions),
        key=lambda sample: (positions[str(sample["game_id"])], int(sample["turn_index"])),
    )


def evaluate_preferences(model: Any, samples: list[dict]) -> dict:
    import torch

    model.eval()
    states = torch.tensor(np.asarray([sample["state"] for sample in samples], dtype=np.float32))
    teacher_actions = torch.tensor(
        np.asarray([sample["teacher_action"] for sample in samples], dtype=np.float32)
    )
    behavior_actions = torch.tensor(
        np.asarray([sample["behavior_action"] for sample in samples], dtype=np.float32)
    )
    with torch.no_grad():
        teacher_values = model(states, teacher_actions)
        behavior_values = model(states, behavior_actions)
        margins = teacher_values - behavior_values
        loss = pairwise_ranking_loss(teacher_values, behavior_values)
    digest = hashlib.sha256()
    for sample, teacher_value, behavior_value in zip(
        samples, teacher_values.tolist(), behavior_values.tolist()
    ):
        digest.update(f"{sample['game_id']}:{sample['turn_index']}\n".encode("utf-8"))
        digest.update(struct.pack("<ff", float(teacher_value), float(behavior_value)))
    return {
        "sample_count": len(samples),
        "pairwise_loss": float(loss.item()),
        "ranking_accuracy": float((margins > 0.0).float().mean().item()),
        "mean_teacher_minus_behavior_margin": float(margins.mean().item()),
        "prediction_sha256": digest.hexdigest(),
        "metric_eligibility": "pipeline_only_not_capability_evidence",
    }


def _save_checkpoint(path: Path, model: Any, teacher_sha256: str) -> None:
    import torch

    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    torch.save(
        {
            "schema_version": CHECKPOINT_SCHEMA_VERSION,
            "model_state_dict": {
                key: value.detach().cpu() for key, value in model.state_dict().items()
            },
            "state_dim": STATE_DIM,
            "action_dim": ACTION_DIM,
            "teacher_sha256": teacher_sha256,
            "seed": SEED,
            "training_mode": "teacher_over_behavior_pairwise_softplus",
            "capability_claim_allowed": False,
            "checkpoint_promotion_allowed": False,
        },
        temporary,
    )
    temporary.replace(path)


def load_checkpoint(
    path: Path, *, expected_teacher_sha256: str = EXPECTED_TEACHER_SHA256
) -> tuple[Any, dict]:
    import torch
    import danzero_dmc

    payload = _torch_load(path)
    if payload.get("schema_version") != CHECKPOINT_SCHEMA_VERSION:
        raise RuntimeError("teacher-preference checkpoint schema mismatch")
    if payload.get("state_dim") != STATE_DIM or payload.get("action_dim") != ACTION_DIM:
        raise RuntimeError("teacher-preference checkpoint dimensions mismatch")
    required_metadata = {
        "teacher_sha256": expected_teacher_sha256,
        "training_mode": "teacher_over_behavior_pairwise_softplus",
        "capability_claim_allowed": False,
        "checkpoint_promotion_allowed": False,
    }
    for key, expected in required_metadata.items():
        if payload.get(key) != expected:
            raise RuntimeError(f"teacher-preference checkpoint {key} mismatch")
    model = danzero_dmc.build_q_model(torch.device("cpu"))
    model.load_state_dict(payload["model_state_dict"])
    model.eval()
    return model, payload


def _set_deterministic() -> None:
    import torch

    random.seed(SEED)
    np.random.seed(SEED)
    torch.manual_seed(SEED)
    torch.set_num_threads(1)
    torch.use_deterministic_algorithms(True)


def train_teacher_preference(
    teacher_path: Path, split_path: Path, report_path: Path, out_dir: Path
) -> dict:
    import torch
    import danzero_dmc

    samples, teacher_summary, teacher_sha256 = load_teacher_dataset(teacher_path)
    split_manifest = build_split_manifest(samples, teacher_path, teacher_sha256)
    if not split_manifest["threshold_passed"]:
        raise RuntimeError("teacher-preference split gate failed")
    train_samples = _ordered_samples(samples, split_manifest["pipeline_train_game_ids"])
    development_samples = _ordered_samples(
        samples, split_manifest["pipeline_development_game_ids"]
    )
    _set_deterministic()
    model = danzero_dmc.build_q_model(torch.device("cpu"))
    initial_metrics = {
        "pipeline_train": evaluate_preferences(model, train_samples),
        "pipeline_development": evaluate_preferences(model, development_samples),
    }
    optimizer = torch.optim.Adam(model.parameters(), lr=LEARNING_RATE)
    rng = random.Random(SEED)
    history: list[dict] = []
    for epoch in range(1, EPOCHS + 1):
        epoch_samples = list(train_samples)
        rng.shuffle(epoch_samples)
        model.train()
        batch_losses: list[float] = []
        for start in range(0, len(epoch_samples), BATCH_SIZE):
            batch = epoch_samples[start : start + BATCH_SIZE]
            states = torch.tensor(
                np.asarray([sample["state"] for sample in batch], dtype=np.float32)
            )
            teacher_actions = torch.tensor(
                np.asarray([sample["teacher_action"] for sample in batch], dtype=np.float32)
            )
            behavior_actions = torch.tensor(
                np.asarray([sample["behavior_action"] for sample in batch], dtype=np.float32)
            )
            loss = pairwise_ranking_loss(
                model(states, teacher_actions), model(states, behavior_actions)
            )
            optimizer.zero_grad()
            loss.backward()
            optimizer.step()
            batch_losses.append(float(loss.item()))
        history.append(
            {"epoch": epoch, "mean_batch_loss": sum(batch_losses) / len(batch_losses)}
        )
    final_metrics = {
        "pipeline_train": evaluate_preferences(model, train_samples),
        "pipeline_development": evaluate_preferences(model, development_samples),
    }
    checkpoint_path = out_dir / "website_teacher_preference_final.pth"
    _save_checkpoint(checkpoint_path, model, teacher_sha256)
    reloaded_model, checkpoint = load_checkpoint(checkpoint_path)
    reloaded_metrics = {
        "pipeline_train": evaluate_preferences(reloaded_model, train_samples),
        "pipeline_development": evaluate_preferences(reloaded_model, development_samples),
    }
    reload_verified = reloaded_metrics == final_metrics
    if not reload_verified:
        raise RuntimeError("teacher-preference checkpoint reload metrics mismatch")
    result = {
        "schema_version": SCHEMA_VERSION,
        "teacher_dataset": str(teacher_path),
        "teacher_sha256": teacher_sha256,
        "teacher_label_count": len(samples),
        "preference_pair_count": len(samples),
        "independent_teacher_games": teacher_summary["independent_teacher_games"],
        "training_gate_passed": teacher_summary["training_gate_passed"],
        "teacher_validation_error_count": 0,
        "train_only_sample_count": len(samples),
        "state_action_dimension_error_count": 0,
        "illegal_preference_action_count": 0,
        "identical_preference_action_count": 0,
        "split_manifest": str(split_path),
        "pipeline_train_game_count": len(split_manifest["pipeline_train_game_ids"]),
        "pipeline_development_game_count": len(
            split_manifest["pipeline_development_game_ids"]
        ),
        "split_overlap_game_count": len(split_manifest["overlap_game_ids"]),
        "device": "cpu",
        "seed": SEED,
        "epochs": EPOCHS,
        "batch_size": BATCH_SIZE,
        "learning_rate": LEARNING_RATE,
        "initial_checkpoint": None,
        "model_architecture": "danzero_dmc.build_q_model",
        "state_dim": STATE_DIM,
        "action_dim": ACTION_DIM,
        "loss": "softplus(Q_behavior-Q_teacher)",
        "training_target": "teacher_action_beats_behavior_action",
        "hyperparameter_search_count": 0,
        "checkpoint_selection_count": 0,
        "history": history,
        "initial_metrics": initial_metrics,
        "final_metrics": final_metrics,
        "checkpoint": str(checkpoint_path),
        "checkpoint_sha256": _sha256(checkpoint_path),
        "checkpoint_schema_version": checkpoint["schema_version"],
        "checkpoint_reload_verified": reload_verified,
        "locked_test_loaded": False,
        "complete_bundle_loaded": False,
        "extra_training_target_count": 0,
        "arena_evaluation_count": 0,
        "website_shadow_count": 0,
        "website_game_count": 0,
        "model_controlled_website_action_count": 0,
        "capability_claim_allowed": False,
        "checkpoint_promotion_allowed": False,
        "metric_eligibility": "pipeline_only_not_capability_evidence",
        "threshold_passed": bool(reload_verified and split_manifest["threshold_passed"]),
    }
    split_path.parent.mkdir(parents=True, exist_ok=True)
    split_path.write_text(
        json.dumps(split_manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return result


def run(args: Any) -> dict:
    return train_teacher_preference(
        Path(args.train_website_teacher_preference),
        Path(args.website_teacher_preference_split_out),
        Path(args.website_teacher_preference_log_out),
        Path(args.website_teacher_preference_out_dir),
    )
