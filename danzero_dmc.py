from __future__ import annotations

import hashlib
import io
import json
import multiprocessing as mp
import queue
import random
import time
from collections import Counter, deque
from pathlib import Path
from typing import Any

import numpy as np

import danzero_features as features
import danzero_oracle


DANZERO_DMC_SCHEMA_VERSION = "danzero_distributed_dmc_v1"
DANZERO_DMC_INPUT_DIM = features.DANZERO_COMPACT_STATE_DIM + features.DANZERO_PHYSICAL_ACTION_DIM
TEACHER_PREFERENCE_CHECKPOINT_SCHEMA_VERSION = "website_teacher_preference_checkpoint_v1"
TEACHER_PREFERENCE_SHA256 = "a74416e6facb28a1bc64563eba90cb33d460dc9e59cc2109518da142465e15f8"
TEACHER_PREFERENCE_TRAINING_MODE = "teacher_over_behavior_pairwise_softplus"


def build_q_model(device: Any) -> Any:
    import torch.nn as nn

    class DanZeroQNet(nn.Module):
        def __init__(self) -> None:
            super().__init__()
            layers: list[nn.Module] = []
            input_dim = DANZERO_DMC_INPUT_DIM
            for _ in range(4):
                layers.extend([nn.Linear(input_dim, 512), nn.Tanh()])
                input_dim = 512
            layers.append(nn.Linear(512, 1))
            self.net = nn.Sequential(*layers)

        def forward(self, states: Any, actions: Any) -> Any:
            import torch

            return self.net(torch.cat([states, actions], dim=-1)).squeeze(-1)

    return DanZeroQNet().to(device)


def serialize_model(model: Any) -> bytes:
    import torch

    buffer = io.BytesIO()
    torch.save({key: value.detach().cpu() for key, value in model.state_dict().items()}, buffer)
    return buffer.getvalue()


def load_serialized_model(model: Any, payload: bytes) -> None:
    import torch

    buffer = io.BytesIO(payload)
    try:
        state_dict = torch.load(buffer, map_location="cpu", weights_only=True)
    except TypeError:
        state_dict = torch.load(buffer, map_location="cpu")
    model.load_state_dict(state_dict)


def epsilon_for_game(game_count: int, start: float, end: float, decay_games: int) -> float:
    if int(decay_games) <= 0:
        return float(end)
    progress = min(1.0, max(0.0, float(game_count) / float(decay_games)))
    return float(start) + (float(end) - float(start)) * progress


def should_drop_stale_sample(sample: dict, learner_version: int, max_version_lag: int) -> bool:
    return bool(
        not sample.get("teacher_action")
        and int(learner_version) - int(sample.get("actor_version") or 0) > int(max_version_lag)
    )


def candidate_metadata(adaptive: Any, components: dict, candidates: list[tuple[int, list[str]]]) -> list[dict]:
    return [
        {
            "cards": list(cards),
            "action_type": adaptive.dmc_sample_action_type(components, int(action_id)),
        }
        for action_id, cards in candidates
    ]


def actor_select_action(
    model: Any,
    state: np.ndarray,
    candidates: list[tuple[int, list[str]]],
    epsilon: float,
    rng: random.Random,
) -> tuple[int, list[str], float | None]:
    if rng.random() < float(epsilon):
        action_id, cards = rng.choice(candidates)
        return int(action_id), list(cards), None
    import torch

    actions = np.asarray(
        [features.encode_physical_action_54(cards) for _action_id, cards in candidates],
        dtype=np.float32,
    )
    states = np.repeat(state.reshape(1, -1), len(candidates), axis=0)
    with torch.no_grad():
        values = model(
            torch.from_numpy(states),
            torch.from_numpy(actions),
        ).cpu().numpy()
    best_value = float(np.max(values))
    best_indices = np.flatnonzero(np.isclose(values, best_value)).tolist()
    selected = int(rng.choice(best_indices))
    action_id, cards = candidates[selected]
    return int(action_id), list(cards), best_value


def actor_worker(
    worker_id: int,
    config: dict,
    shared: Any,
    output_queue: Any,
    episode_counter: Any,
    episode_lock: Any,
) -> None:
    import torch
    import play_research_adaptive as adaptive

    torch.set_num_threads(1)
    components = adaptive.offline_load_guandan_components()
    GuandanGame = components["GuandanGame"]
    profiles = adaptive.load_json(adaptive.PROFILE_PATH, {})
    profile_config = profiles.get("tempo_baseline", {"engine_mode": "tempo"})
    if int(config.get("teacher_games", 0)) > 0:
        adaptive.offline_install_arena_baseline_optimizations()
    rng = random.Random(int(config["seed"]) + int(worker_id) * 1_000_003)
    model = build_q_model("cpu")
    local_version = -1
    while not bool(shared.get("stop", False)):
        shared_version = int(shared.get("model_version", 0))
        if shared_version != local_version:
            load_serialized_model(model, bytes(shared["model_bytes"]))
            model.eval()
            local_version = shared_version
        with episode_lock:
            episode_index = int(episode_counter.value)
            episode_counter.value += 1
        if episode_index >= int(config.get("teacher_games", 0)):
            while (
                not bool(shared.get("stop", False))
                and int(shared.get("teacher_games_completed", 0))
                < int(config.get("teacher_games", 0))
            ):
                time.sleep(0.05)
            if bool(shared.get("stop", False)):
                break
        seed = int(config["seed"]) + episode_index * 1009
        random.seed(seed)
        game = GuandanGame(verbose=False, print_history=False)
        first_player = adaptive.offline_set_random_first_player(game, rng)
        samples: list[dict] = []
        counters = Counter()
        action_types = Counter()
        steps = 0
        fatal = None
        while not game.is_game_over and steps < int(config["max_steps"]):
            adaptive.offline_prepare_turn(game)
            if game.current_player in game.ranking:
                steps += 1
                continue
            player_id = int(game.current_player)
            hand = list(game.players[player_id].hand)
            last_play = list(game.last_play or [])
            was_lead = bool(game.is_free_turn or not last_play)
            candidates = danzero_oracle.candidates(
                adaptive, game, components, hand, last_play, was_lead
            )
            if not candidates:
                fatal = "no_oracle_candidate"
                counters["fatal_no_candidate_count"] += 1
                break
            state = features.encode_compact_state_513(
                game,
                player_id,
                legal_candidates=candidate_metadata(adaptive, components, candidates),
            )
            epsilon = epsilon_for_game(
                int(shared.get("completed_games", 0)),
                float(config["epsilon_start"]),
                float(config["epsilon_end"]),
                int(config["epsilon_decay_games"]),
            )
            teacher_mode = episode_index < int(config.get("teacher_games", 0))
            negative_actions: list[list[float]] = []
            if teacher_mode:
                teacher_info = adaptive.offline_baseline_action_info(
                    game, components, "tempo_baseline", profile_config, rng
                )
                teacher_cards = list(teacher_info.get("chosen_cards") or [])
                teacher_key = danzero_oracle.physical_key(teacher_cards)
                matching = [
                    (candidate_action_id, candidate_cards)
                    for candidate_action_id, candidate_cards in candidates
                    if danzero_oracle.physical_key(candidate_cards) == teacher_key
                ]
                if not matching:
                    fatal = "teacher_action_not_in_complete_oracle"
                    counters["teacher_mapping_fail_count"] += 1
                    break
                action_id, cards = matching[0]
                q_value = None
                negative_candidates = [
                    candidate_cards
                    for _candidate_action_id, candidate_cards in candidates
                    if danzero_oracle.physical_key(candidate_cards) != teacher_key
                ]
                if config.get("teacher_hard_negatives"):
                    selected_negatives = negative_candidates
                else:
                    negative_count = min(
                        int(config.get("teacher_negative_count", 0)), len(negative_candidates)
                    )
                    selected_negatives = (
                        rng.sample(negative_candidates, negative_count) if negative_count else []
                    )
                if selected_negatives:
                    negative_actions = [
                        features.encode_physical_action_54(candidate_cards).tolist()
                        for candidate_cards in selected_negatives
                    ]
                counters["teacher_decision_count"] += 1
                counters["teacher_negative_candidate_count"] += len(negative_actions)
            else:
                action_id, cards, q_value = actor_select_action(model, state, candidates, epsilon, rng)
            physical = features.encode_physical_action_54(cards)
            action_info = adaptive.offline_make_action_info_from_cards(
                game,
                components,
                cards,
                rng,
                policy="danzero_dmc",
                sampled_action_id=action_id,
                audit_masks=False,
            )
            record = adaptive.offline_apply_action(game, action_info)
            counters["illegal_action_count"] += int(bool(record.get("illegal")))
            counters["fallback_count"] += int(bool(record.get("fallback")))
            counters["materialization_fail_count"] += int(bool(record.get("materialization_fail")))
            counters["hand_card_mismatch_count"] += int(bool(record.get("hand_card_mismatch")))
            if any(counters[name] for name in (
                "illegal_action_count",
                "fallback_count",
                "materialization_fail_count",
                "hand_card_mismatch_count",
            )):
                fatal = "action_integrity_failure"
                break
            action_type = adaptive.dmc_sample_action_type(components, action_id)
            action_types[action_type] += 1
            counters["pass_count"] += int(not cards)
            counters["bomb_count"] += int(adaptive.offline_action_is_bomb(components["action_by_id"].get(action_id)))
            samples.append(
                {
                    "state": state.tolist(),
                    "action": physical.tolist(),
                    "action_id": action_id,
                    "physical_cards": cards,
                    "action_type": action_type,
                    "player_id": player_id,
                    "team_id": player_id % 2,
                    "was_lead": was_lead,
                    "was_follow": not was_lead,
                    "active_level": int(game.active_level),
                    "actor_version": local_version,
                    "worker_id": worker_id,
                    "trajectory_id": f"episode:{episode_index}",
                    "episode_index": episode_index,
                    "step_index": len(samples),
                    "epsilon": epsilon,
                    "q_value": q_value,
                    "target": 0.0,
                    "teacher_action": teacher_mode,
                    "negative_actions": negative_actions,
                    "reward_version": "terminal_team_win_loss_v1",
                    "state_encoding_version": features.DANZERO_COMPACT_STATE_ENCODING_VERSION,
                    "action_encoding_version": features.DANZERO_PHYSICAL_ACTION_ENCODING_VERSION,
                    "oracle_version": danzero_oracle.ORACLE_VERSION,
                }
            )
            steps += 1
        if game.is_game_over and game.ranking:
            winner_team = int(game.ranking[0]) % 2
            for sample in samples:
                sample["target"] = 1.0 if int(sample["team_id"]) == winner_team else -1.0
            message = {
                "kind": "game",
                "worker_id": worker_id,
                "episode_index": episode_index,
                "actor_version": local_version,
                "first_player": first_player,
                "winner_team": winner_team,
                "active_level": int(game.active_level),
                "steps": steps,
                "samples": samples,
                "counters": dict(counters),
                "action_types": dict(action_types),
                "fatal": None,
                "teacher_episode": episode_index < int(config.get("teacher_games", 0)),
            }
        else:
            message = {
                "kind": "failed_game",
                "worker_id": worker_id,
                "episode_index": episode_index,
                "actor_version": local_version,
                "first_player": first_player,
                "steps": steps,
                "samples": [],
                "counters": dict(counters),
                "action_types": dict(action_types),
                "fatal": fatal or "max_steps_exceeded",
                "teacher_episode": episode_index < int(config.get("teacher_games", 0)),
            }
        while not bool(shared.get("stop", False)):
            try:
                output_queue.put(message, timeout=1.0)
                break
            except queue.Full:
                continue


def validate_resume_payload(payload: dict) -> list[str]:
    expected = {
        "schema_version": DANZERO_DMC_SCHEMA_VERSION,
        "state_dim": features.DANZERO_COMPACT_STATE_DIM,
        "action_dim": features.DANZERO_PHYSICAL_ACTION_DIM,
        "input_dim": DANZERO_DMC_INPUT_DIM,
        "state_encoding_version": features.DANZERO_COMPACT_STATE_ENCODING_VERSION,
        "action_encoding_version": features.DANZERO_PHYSICAL_ACTION_ENCODING_VERSION,
        "oracle_version": danzero_oracle.ORACLE_VERSION,
        "oracle_exhaustive": danzero_oracle.ORACLE_EXHAUSTIVE,
        "reward_version": "terminal_team_win_loss_v1",
    }
    return [
        f"{key}: expected={value!r} actual={payload.get(key)!r}"
        for key, value in expected.items()
        if payload.get(key) != value
    ]


def validate_teacher_preference_checkpoint(payload: dict) -> list[str]:
    expected = {
        "schema_version": TEACHER_PREFERENCE_CHECKPOINT_SCHEMA_VERSION,
        "state_dim": features.DANZERO_COMPACT_STATE_DIM,
        "action_dim": features.DANZERO_PHYSICAL_ACTION_DIM,
        "teacher_sha256": TEACHER_PREFERENCE_SHA256,
        "training_mode": TEACHER_PREFERENCE_TRAINING_MODE,
        "capability_claim_allowed": False,
        "checkpoint_promotion_allowed": False,
    }
    return [
        f"{key}: expected={value!r} actual={payload.get(key)!r}"
        for key, value in expected.items()
        if payload.get(key) != value
    ]


def checkpoint_payload(
    model: Any,
    optimizer: Any,
    replay: deque,
    teacher_replay: deque,
    stats: dict,
    learner_version: int,
    rng: random.Random,
) -> dict:
    import torch

    return {
        "schema_version": DANZERO_DMC_SCHEMA_VERSION,
        "model_state_dict": model.state_dict(),
        "optimizer_state_dict": optimizer.state_dict(),
        "replay_buffer": list(replay),
        "teacher_replay_buffer": list(teacher_replay),
        "stats": stats,
        "learner_version": int(learner_version),
        "state_dim": features.DANZERO_COMPACT_STATE_DIM,
        "action_dim": features.DANZERO_PHYSICAL_ACTION_DIM,
        "input_dim": DANZERO_DMC_INPUT_DIM,
        "state_encoding_version": features.DANZERO_COMPACT_STATE_ENCODING_VERSION,
        "action_encoding_version": features.DANZERO_PHYSICAL_ACTION_ENCODING_VERSION,
        "oracle_version": danzero_oracle.ORACLE_VERSION,
        "oracle_exhaustive": danzero_oracle.ORACLE_EXHAUSTIVE,
        "reward_version": "terminal_team_win_loss_v1",
        "learner_rng_state": rng.getstate(),
        "torch_rng_state": torch.get_rng_state(),
        "cuda_rng_state_all": torch.cuda.get_rng_state_all() if torch.cuda.is_available() else None,
    }


def save_training_checkpoint(
    path: Path,
    model: Any,
    optimizer: Any,
    replay: deque,
    teacher_replay: deque,
    stats: dict,
    learner_version: int,
    rng: random.Random,
) -> None:
    import torch

    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    torch.save(
        checkpoint_payload(model, optimizer, replay, teacher_replay, stats, learner_version, rng),
        temporary,
    )
    temporary.replace(path)


def train_batch(
    model: Any,
    optimizer: Any,
    replay: deque,
    teacher_replay: deque,
    batch_size: int,
    device: Any,
    rng: random.Random,
    teacher_margin: float,
    teacher_weight: float,
    teacher_batch_ratio: float,
    teacher_hard_negatives: bool,
) -> dict[str, float]:
    import torch
    import torch.nn.functional as F

    requested_teacher = min(
        len(teacher_replay),
        int(round(int(batch_size) * max(0.0, min(1.0, float(teacher_batch_ratio))))),
    )
    requested_regular = min(len(replay), int(batch_size) - requested_teacher)
    batch = rng.sample(list(replay), requested_regular)
    if requested_teacher:
        batch.extend(rng.sample(list(teacher_replay), requested_teacher))
        rng.shuffle(batch)
    states = torch.tensor(np.asarray([sample["state"] for sample in batch], dtype=np.float32), device=device)
    actions = torch.tensor(np.asarray([sample["action"] for sample in batch], dtype=np.float32), device=device)
    targets = torch.tensor([float(sample["target"]) for sample in batch], dtype=torch.float32, device=device)
    predictions = model(states, actions)
    value_loss = F.mse_loss(predictions, targets)
    negative_states: list[list[float]] = []
    negative_actions: list[list[float]] = []
    positive_indices: list[int] = []
    for batch_index, sample in enumerate(batch):
        for negative_action in sample.get("negative_actions") or []:
            negative_states.append(sample["state"])
            negative_actions.append(negative_action)
            positive_indices.append(batch_index)
    if negative_actions:
        negative_q = model(
            torch.tensor(np.asarray(negative_states, dtype=np.float32), device=device),
            torch.tensor(np.asarray(negative_actions, dtype=np.float32), device=device),
        )
        if teacher_hard_negatives:
            owners = sorted(set(positive_indices))
            owner_tensor = torch.tensor(positive_indices, dtype=torch.long, device=device)
            hard_negative_q = torch.stack(
                [negative_q[owner_tensor == owner].max() for owner in owners]
            )
            positive_q = predictions[torch.tensor(owners, dtype=torch.long, device=device)]
            negative_q = hard_negative_q
        else:
            positive_q = predictions[
                torch.tensor(positive_indices, dtype=torch.long, device=device)
            ]
        margin_loss = F.relu(float(teacher_margin) - positive_q + negative_q).mean()
    else:
        margin_loss = torch.zeros((), dtype=torch.float32, device=device)
    loss = value_loss + float(teacher_weight) * margin_loss
    optimizer.zero_grad()
    loss.backward()
    torch.nn.utils.clip_grad_norm_(model.parameters(), 10.0)
    optimizer.step()
    return {
        "total_loss": float(loss.item()),
        "value_loss": float(value_loss.item()),
        "teacher_margin_loss": float(margin_loss.item()),
        "teacher_negative_count": len(negative_actions),
        "teacher_ranked_negative_count": len(set(positive_indices))
        if teacher_hard_negatives
        else len(negative_actions),
        "teacher_sample_count": sum(bool(sample.get("teacher_action")) for sample in batch),
    }


def run_distributed_dmc(args: Any) -> dict:
    import torch

    import play_research_adaptive as adaptive

    device_info = adaptive.offline_resolve_device(args.device)
    if device_info["torch"] is None:
        raise RuntimeError("DanZero DMC requires PyTorch")
    device = device_info["device"]
    rng = random.Random(int(args.danzero_seed))
    model = build_q_model(device)
    optimizer = torch.optim.Adam(model.parameters(), lr=float(args.danzero_learning_rate))
    replay: deque = deque(maxlen=int(args.danzero_replay_capacity))
    teacher_replay: deque = deque(maxlen=int(args.danzero_teacher_replay_capacity))
    learner_version = 0
    stats = {
        "schema_version": DANZERO_DMC_SCHEMA_VERSION,
        "backend": device_info["backend"],
        "requested_device": device_info["requested_device"],
        "actual_device": device_info["actual_device"],
        "device_fallback": device_info["device_fallback"],
        "state_dim": features.DANZERO_COMPACT_STATE_DIM,
        "action_dim": features.DANZERO_PHYSICAL_ACTION_DIM,
        "input_dim": DANZERO_DMC_INPUT_DIM,
        "state_encoding_version": features.DANZERO_COMPACT_STATE_ENCODING_VERSION,
        "action_encoding_version": features.DANZERO_PHYSICAL_ACTION_ENCODING_VERSION,
        "legal_action_source": danzero_oracle.ORACLE_VERSION,
        "oracle_exhaustive": danzero_oracle.ORACLE_EXHAUSTIVE,
        "reward_version": "terminal_team_win_loss_v1",
        "learner_process": "main_process_only",
        "actor_process_count": int(args.danzero_actors),
        "trajectory_queue_maxsize": max(4, int(args.danzero_actors) * 2),
        "requested_games": int(args.danzero_games),
        "completed_games": 0,
        "failed_games": 0,
        "teacher_games_requested": int(args.danzero_teacher_games),
        "teacher_games_completed": 0,
        "teacher_decision_count": 0,
        "teacher_mapping_fail_count": 0,
        "teacher_negative_count": int(args.danzero_teacher_negatives),
        "teacher_hard_negatives": bool(args.danzero_teacher_hard_negatives),
        "teacher_negative_candidate_count": 0,
        "teacher_margin": float(args.danzero_teacher_margin),
        "teacher_weight": float(args.danzero_teacher_weight),
        "teacher_batch_ratio": float(args.danzero_teacher_batch_ratio),
        "teacher_replay_capacity": int(args.danzero_teacher_replay_capacity),
        "teacher_replay_size": 0,
        "teacher_samples_trained": 0,
        "teacher_sample_count_recent": [],
        "team0_wins": 0,
        "team1_wins": 0,
        "team0_win_rate": 0.0,
        "team1_win_rate": 0.0,
        "total_decisions": 0,
        "average_game_length": 0.0,
        "illegal_action_count": 0,
        "fallback_count": 0,
        "materialization_fail_count": 0,
        "hand_card_mismatch_count": 0,
        "fatal_no_candidate_count": 0,
        "pass_count": 0,
        "bomb_count": 0,
        "pass_rate": 0.0,
        "bomb_usage_rate": 0.0,
        "first_player_distribution": {"0": 0, "1": 0, "2": 0, "3": 0},
        "level_distribution": {},
        "action_type_distribution": {},
        "learner_updates": 0,
        "learner_version": 0,
        "actor_version_min": None,
        "actor_version_max": None,
        "stale_sample_count": 0,
        "accepted_sample_count": 0,
        "replay_buffer_size": 0,
        "loss_recent": [],
        "value_loss_recent": [],
        "teacher_margin_loss_recent": [],
        "saved_checkpoints": [],
        "resumed_from": None,
        "threshold_passed": False,
        "engineering_smoke_passed": False,
        "stage3_gate_passed": False,
        "resume_compatibility_checked": False,
        "resume_compatibility_mismatches": [],
        "resume_recipe_changes": [],
        "next_episode_index": 0,
    }
    if args.danzero_resume:
        resume_path = Path(args.danzero_resume)
        try:
            payload = torch.load(resume_path, map_location=device, weights_only=False)
        except TypeError:
            payload = torch.load(resume_path, map_location=device)
        compatibility_mismatches = validate_resume_payload(payload)
        if compatibility_mismatches:
            raise RuntimeError(
                "incompatible DanZero checkpoint: " + "; ".join(compatibility_mismatches)
            )
        model.load_state_dict(payload["model_state_dict"])
        optimizer.load_state_dict(payload["optimizer_state_dict"])
        payload_replay = payload.get("replay_buffer") or []
        payload_teacher_replay = payload.get("teacher_replay_buffer") or []
        replay.extend(sample for sample in payload_replay if not sample.get("teacher_action"))
        teacher_replay.extend(
            payload_teacher_replay
            or [sample for sample in payload_replay if sample.get("teacher_action")]
        )
        learner_version = int(payload.get("learner_version") or 0)
        if payload.get("learner_rng_state") is not None:
            rng.setstate(payload["learner_rng_state"])
        if payload.get("torch_rng_state") is not None:
            torch.set_rng_state(payload["torch_rng_state"].cpu())
        if torch.cuda.is_available() and payload.get("cuda_rng_state_all") is not None:
            torch.cuda.set_rng_state_all([state.cpu() for state in payload["cuda_rng_state_all"]])
        prior = payload.get("stats") or {}
        immutable_runtime_fields = {
            "schema_version",
            "backend",
            "requested_device",
            "actual_device",
            "device_fallback",
            "state_dim",
            "action_dim",
            "input_dim",
            "state_encoding_version",
            "action_encoding_version",
            "legal_action_source",
            "oracle_exhaustive",
            "reward_version",
            "learner_process",
            "actor_process_count",
            "trajectory_queue_maxsize",
            "requested_games",
            "threshold_passed",
            "engineering_smoke_passed",
            "stage3_gate_passed",
            "resume_compatibility_checked",
            "resume_compatibility_mismatches",
        }
        for key in stats:
            if key in prior and key not in immutable_runtime_fields:
                stats[key] = prior[key]
        current_recipe = {
            "teacher_games_requested": int(args.danzero_teacher_games),
            "teacher_negative_count": int(args.danzero_teacher_negatives),
            "teacher_hard_negatives": bool(args.danzero_teacher_hard_negatives),
            "teacher_margin": float(args.danzero_teacher_margin),
            "teacher_weight": float(args.danzero_teacher_weight),
            "teacher_batch_ratio": float(args.danzero_teacher_batch_ratio),
            "teacher_replay_capacity": int(args.danzero_teacher_replay_capacity),
        }
        stats["resume_recipe_changes"] = [
            {"field": key, "from": prior.get(key), "to": value}
            for key, value in current_recipe.items()
            if prior.get(key) != value
        ]
        stats.update(current_recipe)
        stats["resumed_from"] = str(resume_path)
        stats["resume_compatibility_checked"] = True
        stats["resume_compatibility_mismatches"] = []

    ctx = mp.get_context("spawn")
    manager = ctx.Manager()
    shared = manager.dict()
    shared["stop"] = False
    shared["model_version"] = learner_version
    shared["model_bytes"] = serialize_model(model)
    shared["completed_games"] = int(stats["completed_games"])
    shared["teacher_games_completed"] = int(stats["teacher_games_completed"])
    output_queue = ctx.Queue(maxsize=max(4, int(args.danzero_actors) * 2))
    episode_counter = ctx.Value("q", int(stats.get("next_episode_index") or stats["completed_games"]))
    episode_lock = ctx.Lock()
    config = {
        "seed": int(args.danzero_seed),
        "max_steps": int(args.danzero_max_steps),
        "epsilon_start": float(args.danzero_epsilon_start),
        "epsilon_end": float(args.danzero_epsilon_end),
        "epsilon_decay_games": int(args.danzero_epsilon_decay_games),
        "teacher_games": int(args.danzero_teacher_games),
        "teacher_negative_count": int(args.danzero_teacher_negatives),
        "teacher_hard_negatives": bool(args.danzero_teacher_hard_negatives),
    }
    actors = [
        ctx.Process(
            target=actor_worker,
            args=(worker_id, config, shared, output_queue, episode_counter, episode_lock),
            daemon=True,
        )
        for worker_id in range(int(args.danzero_actors))
    ]
    for process in actors:
        process.start()
    out_dir = Path(args.danzero_out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    next_save = (
        ((int(stats["completed_games"]) // int(args.danzero_save_every)) + 1) * int(args.danzero_save_every)
        if int(args.danzero_save_every) > 0
        else 0
    )
    total_steps = float(stats["average_game_length"]) * int(stats["completed_games"])
    action_types = Counter(stats.get("action_type_distribution") or {})
    levels = Counter(stats.get("level_distribution") or {})
    actor_versions: list[int] = []
    started = time.monotonic()
    try:
        while int(stats["completed_games"]) < int(args.danzero_games):
            try:
                message = output_queue.get(timeout=30.0)
            except queue.Empty:
                dead = [process.exitcode for process in actors if not process.is_alive()]
                if len(dead) == len(actors):
                    raise RuntimeError(f"DanZero actor exited unexpectedly: {dead}")
                continue
            counters = Counter(message.get("counters") or {})
            stats["next_episode_index"] = max(
                int(stats.get("next_episode_index") or 0),
                int(message.get("episode_index") or 0) + 1,
            )
            for name in (
                "illegal_action_count",
                "fallback_count",
                "materialization_fail_count",
                "hand_card_mismatch_count",
                "fatal_no_candidate_count",
                "pass_count",
                "bomb_count",
                "teacher_decision_count",
                "teacher_mapping_fail_count",
                "teacher_negative_candidate_count",
            ):
                stats[name] += int(counters.get(name, 0))
            if message.get("kind") != "game":
                stats["failed_games"] += 1
                continue
            stats["completed_games"] += 1
            stats["teacher_games_completed"] += int(bool(message.get("teacher_episode")))
            shared["completed_games"] = int(stats["completed_games"])
            shared["teacher_games_completed"] = int(stats["teacher_games_completed"])
            winner = int(message["winner_team"])
            stats[f"team{winner}_wins"] += 1
            stats["first_player_distribution"][str(message["first_player"])] += 1
            levels[str(message["active_level"])] += 1
            action_types.update(message.get("action_types") or {})
            total_steps += int(message["steps"])
            actor_version = int(message.get("actor_version") or 0)
            actor_versions.append(actor_version)
            for sample in message.get("samples") or []:
                if should_drop_stale_sample(
                    sample, learner_version, int(args.danzero_max_version_lag)
                ):
                    stats["stale_sample_count"] += 1
                    continue
                if sample.get("teacher_action"):
                    teacher_replay.append(sample)
                else:
                    replay.append(sample)
                stats["accepted_sample_count"] += 1
            stats["total_decisions"] += len(message.get("samples") or [])
            if len(replay) >= int(args.danzero_batch_size):
                model.train()
                for _ in range(int(args.danzero_updates_per_game)):
                    losses = train_batch(
                        model,
                        optimizer,
                        replay,
                        teacher_replay,
                        int(args.danzero_batch_size),
                        device,
                        rng,
                        float(args.danzero_teacher_margin),
                        float(args.danzero_teacher_weight),
                        float(args.danzero_teacher_batch_ratio),
                        bool(args.danzero_teacher_hard_negatives),
                    )
                    stats["loss_recent"].append(losses["total_loss"])
                    stats["value_loss_recent"].append(losses["value_loss"])
                    stats["teacher_margin_loss_recent"].append(losses["teacher_margin_loss"])
                    stats["teacher_sample_count_recent"].append(losses["teacher_sample_count"])
                    stats["teacher_samples_trained"] += int(losses["teacher_sample_count"])
                    stats["loss_recent"] = stats["loss_recent"][-100:]
                    stats["value_loss_recent"] = stats["value_loss_recent"][-100:]
                    stats["teacher_margin_loss_recent"] = stats["teacher_margin_loss_recent"][-100:]
                    stats["teacher_sample_count_recent"] = stats["teacher_sample_count_recent"][-100:]
                    stats["learner_updates"] += 1
                    learner_version += 1
                model.eval()
                if int(args.danzero_sync_every_updates) > 0 and (
                    stats["learner_updates"] % int(args.danzero_sync_every_updates) == 0
                ):
                    shared["model_bytes"] = serialize_model(model)
                    shared["model_version"] = learner_version
            stats["learner_version"] = learner_version
            stats["replay_buffer_size"] = len(replay)
            stats["teacher_replay_size"] = len(teacher_replay)
            stats["team0_win_rate"] = stats["team0_wins"] / max(1, stats["completed_games"])
            stats["team1_win_rate"] = stats["team1_wins"] / max(1, stats["completed_games"])
            stats["average_game_length"] = total_steps / max(1, stats["completed_games"])
            stats["pass_rate"] = stats["pass_count"] / max(1, stats["total_decisions"])
            stats["bomb_usage_rate"] = stats["bomb_count"] / max(1, stats["total_decisions"])
            stats["action_type_distribution"] = dict(action_types)
            stats["level_distribution"] = dict(levels)
            stats["actor_version_min"] = min(actor_versions) if actor_versions else None
            stats["actor_version_max"] = max(actor_versions) if actor_versions else None
            stats["elapsed_seconds"] = time.monotonic() - started
            if next_save and int(stats["completed_games"]) >= next_save:
                checkpoint = out_dir / f"danzero_dmc_games{next_save}.pth"
                save_training_checkpoint(
                    checkpoint, model, optimizer, replay, teacher_replay, stats, learner_version, rng
                )
                stats["saved_checkpoints"].append(str(checkpoint))
                next_save += int(args.danzero_save_every)
            if int(args.report_every) > 0 and stats["completed_games"] % int(args.report_every) == 0:
                print(
                    f"danzero_dmc_progress games={stats['completed_games']}/{args.danzero_games} "
                    f"replay={len(replay)} version={learner_version} loss="
                    f"{(stats['loss_recent'][-1] if stats['loss_recent'] else None)}",
                    flush=True,
                )
            Path(args.danzero_log_out).write_text(
                json.dumps(stats, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
            )
    finally:
        shared["stop"] = True
        for process in actors:
            process.join(timeout=10.0)
            if process.is_alive():
                process.terminate()
                process.join(timeout=5.0)
        manager.shutdown()
    final_checkpoint = out_dir / "danzero_dmc_latest.pth"
    stats["saved_checkpoints"].append(str(final_checkpoint))
    integrity_fields = (
        "illegal_action_count",
        "fallback_count",
        "materialization_fail_count",
        "hand_card_mismatch_count",
        "fatal_no_candidate_count",
        "teacher_mapping_fail_count",
    )
    stats["engineering_smoke_passed"] = bool(
        stats["completed_games"] >= int(args.danzero_games)
        and all(int(stats[name]) == 0 for name in integrity_fields)
        and stats["replay_buffer_size"] > 0
    )
    stats["stage3_gate_passed"] = bool(
        stats["engineering_smoke_passed"]
        and stats["completed_games"] >= 1000
        and bool(stats["oracle_exhaustive"])
        and (stats["actor_version_max"] or 0) > 0
    )
    stats["team_symmetry_gap"] = abs(float(stats["team0_win_rate"]) - 0.5)
    expected_first_player = stats["completed_games"] / 4.0
    stats["first_player_max_deviation"] = max(
        (
            abs(int(count) - expected_first_player) / max(1.0, float(stats["completed_games"]))
            for count in stats["first_player_distribution"].values()
        ),
        default=1.0,
    )
    stats["stage3_gate_passed"] = bool(
        stats["stage3_gate_passed"]
        and stats["team_symmetry_gap"] <= 0.08
        and stats["first_player_max_deviation"] <= 0.08
    )
    stats["threshold_passed"] = stats["engineering_smoke_passed"]
    save_training_checkpoint(
        final_checkpoint, model, optimizer, replay, teacher_replay, stats, learner_version, rng
    )
    if not final_checkpoint.exists():
        stats["engineering_smoke_passed"] = False
        stats["stage3_gate_passed"] = False
        stats["threshold_passed"] = False
    Path(args.danzero_log_out).write_text(
        json.dumps(stats, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(stats, ensure_ascii=False, indent=2))
    if not stats["engineering_smoke_passed"]:
        raise RuntimeError("DanZero distributed DMC engineering gate failed")
    return stats


def load_q_checkpoint(path: Path, device: Any) -> tuple[Any, dict]:
    import torch

    try:
        payload = torch.load(path, map_location=device, weights_only=False)
    except TypeError:
        payload = torch.load(path, map_location=device)
    if payload.get("schema_version") == TEACHER_PREFERENCE_CHECKPOINT_SCHEMA_VERSION:
        mismatches = validate_teacher_preference_checkpoint(payload)
    else:
        mismatches = validate_resume_payload(payload)
    if mismatches:
        raise RuntimeError("incompatible DanZero checkpoint: " + "; ".join(mismatches))
    model = build_q_model(device)
    model.load_state_dict(payload["model_state_dict"])
    model.eval()
    return model, payload


def arena_game_plan(game_index: int, arena_seed: int, swap_seats: bool) -> dict:
    pair_index = int(game_index) // 2 if swap_seats else int(game_index)
    game_seed = int(arena_seed) + pair_index
    return {
        "game_index": int(game_index),
        "pair_index": pair_index,
        "game_seed": game_seed,
        "first_player_seed": game_seed + 50_000_003,
        "arena_rng_seed": game_seed + 100_000_007,
        "model_team": int(game_index) % 2 if swap_seats else 0,
    }


def arena_model_action_info(
    adaptive: Any,
    game: Any,
    components: dict,
    model: Any,
    device: Any,
    rng: random.Random,
) -> dict:
    import torch

    player_id = int(game.current_player)
    hand = list(game.players[player_id].hand)
    last_play = list(game.last_play or [])
    was_lead = bool(game.is_free_turn or not last_play)
    physical_candidates = danzero_oracle.candidates(
        adaptive, game, components, hand, last_play, was_lead
    )
    if not physical_candidates:
        raise RuntimeError("complete DanZero oracle returned no candidate")
    state = features.encode_compact_state_513(
        game,
        player_id,
        legal_candidates=candidate_metadata(adaptive, components, physical_candidates),
    )
    actions = np.asarray(
        [features.encode_physical_action_54(cards) for _action_id, cards in physical_candidates],
        dtype=np.float32,
    )
    states = np.repeat(state.reshape(1, -1), len(physical_candidates), axis=0)
    with torch.no_grad():
        values = model(
            torch.tensor(states, dtype=torch.float32, device=device),
            torch.tensor(actions, dtype=torch.float32, device=device),
        ).detach().cpu().numpy()
    best_value = float(np.max(values))
    best_indices = np.flatnonzero(np.isclose(values, best_value)).tolist()
    selected = int(rng.choice(best_indices))
    action_id, cards = physical_candidates[selected]
    info = adaptive.offline_make_action_info_from_cards(
        game,
        components,
        list(cards),
        rng,
        policy="danzero_dmc_arena",
        sampled_action_id=int(action_id),
        audit_masks=False,
    )
    info["danzero_q_value"] = best_value
    info["danzero_candidate_count"] = len(physical_candidates)
    return info


def frozen_baseline_evidence() -> dict:
    from tools.verify_baseline_freeze import MANIFEST_PATH, verify_manifest

    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    validation = manifest.get("validation") or {}
    freeze = verify_manifest()
    return {
        **freeze,
        "baseline_manifest": str(MANIFEST_PATH),
        "baseline_manifest_sha256": hashlib.sha256(MANIFEST_PATH.read_bytes()).hexdigest(),
        "baseline_equivalence_checked": True,
        "baseline_equivalence_samples": int(validation.get("baseline_equivalence_samples") or 0),
        "baseline_equivalence_mismatch_count": int(
            validation.get("baseline_equivalence_mismatch_count") or 0
        ),
        "baseline_equivalence_evidence": validation.get("evidence"),
    }


def run_offline_arena(args: Any) -> dict:
    import play_research_adaptive as adaptive

    if args.baseline_profile != "tempo_baseline":
        raise RuntimeError("DanZero arena requires --baseline-profile tempo_baseline")
    checkpoint = Path(args.danzero_checkpoint)
    if not checkpoint.exists():
        raise RuntimeError(f"DanZero checkpoint not found: {checkpoint}")
    device_info = adaptive.offline_resolve_device(args.device)
    if device_info["torch"] is None:
        raise RuntimeError("DanZero arena requires PyTorch")
    device = device_info["device"]
    model, checkpoint_payload_data = load_q_checkpoint(checkpoint, device)
    components = adaptive.offline_load_guandan_components()
    GuandanGame = components["GuandanGame"]
    profiles = adaptive.load_json(adaptive.PROFILE_PATH, {})
    profile_config = profiles["tempo_baseline"]
    baseline_evidence = frozen_baseline_evidence()
    if (
        not baseline_evidence["threshold_passed"]
        or baseline_evidence["baseline_equivalence_samples"] < 500
        or baseline_evidence["baseline_equivalence_mismatch_count"] != 0
    ):
        raise RuntimeError("frozen baseline evidence gate failed")
    restore_baseline = adaptive.offline_install_arena_baseline_optimizations()
    checkpoint_sha256 = hashlib.sha256(checkpoint.read_bytes()).hexdigest()
    result = {
        "schema_version": "danzero_offline_arena_v1",
        "checkpoint": str(checkpoint),
        "checkpoint_sha256": checkpoint_sha256,
        "checkpoint_schema_version": checkpoint_payload_data.get("schema_version"),
        "checkpoint_learner_version": int(checkpoint_payload_data.get("learner_version") or 0),
        "baseline_profile": "tempo_baseline",
        "requested_games": int(args.danzero_arena_games),
        "completed_games": 0,
        "model_wins": 0,
        "baseline_wins": 0,
        "model_team_win_rate": 0.0,
        "baseline_team_win_rate": 0.0,
        "seat_swap_enabled": bool(args.danzero_arena_swap_seats),
        "paired_seed_enabled": bool(args.danzero_arena_swap_seats),
        "model_team_distribution": {"0": 0, "1": 0},
        "first_player_policy": "paired_seed_same_within_pair",
        "first_player_distribution": {"0": 0, "1": 0, "2": 0, "3": 0},
        "level_distribution": {},
        "average_game_length": 0.0,
        "model_decision_count": 0,
        "baseline_decision_count": 0,
        "illegal_action_count": 0,
        "fallback_count": 0,
        "materialization_fail_count": 0,
        "hand_card_mismatch_count": 0,
        "fatal_no_candidate_count": 0,
        "model_pass_count": 0,
        "model_bomb_count": 0,
        "model_action_type_distribution": {},
        "legal_action_source": danzero_oracle.ORACLE_VERSION,
        "oracle_exhaustive": danzero_oracle.ORACLE_EXHAUSTIVE,
        "baseline_evidence": baseline_evidence,
        "allowed_for_stage4_continuation": False,
        "threshold_passed": False,
        "failure_samples": [],
        "game_trace": [],
        "screening_evidence_only": True,
        "early_screen_min_win_rate": 0.30,
        "early_screen_continuation_allowed": False,
        "training_run_count": 0,
        "hyperparameter_search_count": 0,
        "checkpoint_selection_count": 0,
        "locked_test_load_count": 0,
        "website_dataset_load_count": 0,
        "website_shadow_count": 0,
        "website_game_count": 0,
        "model_controlled_website_action_count": 0,
        "checkpoint_promotion_allowed": False,
        "capability_claim_allowed": False,
    }
    action_types = Counter()
    levels = Counter()
    total_steps = 0
    started = time.monotonic()
    arena_out = Path(args.danzero_arena_out)

    def write_arena_snapshot(status: str, game_index: int | None = None, error: str | None = None) -> None:
        snapshot = dict(result)
        snapshot["status"] = status
        snapshot["last_game_index"] = game_index
        if error is not None:
            snapshot["error"] = error
        snapshot["elapsed_seconds"] = time.monotonic() - started
        temporary = arena_out.with_suffix(arena_out.suffix + ".tmp")
        temporary.write_text(
            json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        temporary.replace(arena_out)

    write_arena_snapshot("running")
    current_game_index: int | None = None
    try:
        for game_index in range(int(args.danzero_arena_games)):
            current_game_index = game_index
            plan = arena_game_plan(
                game_index,
                int(args.danzero_arena_seed),
                bool(args.danzero_arena_swap_seats),
            )
            random.seed(plan["game_seed"])
            game = GuandanGame(verbose=False, print_history=False)
            first_player_rng = random.Random(plan["first_player_seed"])
            first_player = adaptive.offline_set_random_first_player(game, first_player_rng)
            result["first_player_distribution"][str(first_player)] += 1
            levels[str(game.active_level)] += 1
            model_team = int(plan["model_team"])
            result["model_team_distribution"][str(model_team)] += 1
            rng = random.Random(plan["arena_rng_seed"])
            game_counter_start = {
                field: int(result[field])
                for field in (
                    "illegal_action_count",
                    "fallback_count",
                    "materialization_fail_count",
                    "hand_card_mismatch_count",
                    "fatal_no_candidate_count",
                )
            }
            steps = 0
            while not game.is_game_over and steps < adaptive.OFFLINE_MAX_GAME_STEPS:
                adaptive.offline_prepare_turn(game)
                if game.current_player in game.ranking:
                    steps += 1
                    continue
                is_model_turn = int(game.current_player) % 2 == model_team
                if is_model_turn:
                    action_info = arena_model_action_info(
                        adaptive, game, components, model, device, rng
                    )
                    result["model_decision_count"] += 1
                else:
                    action_info = adaptive.offline_baseline_action_info(
                        game, components, "tempo_baseline", profile_config, rng
                    )
                    result["baseline_decision_count"] += 1
                record = adaptive.offline_apply_action(game, action_info)
                record_fields = {
                    "illegal_action_count": "illegal",
                    "fallback_count": "fallback",
                    "materialization_fail_count": "materialization_fail",
                    "hand_card_mismatch_count": "hand_card_mismatch",
                }
                for field, record_field in record_fields.items():
                    result[field] += int(bool(record.get(record_field)))
                if is_model_turn:
                    cards = list(action_info.get("chosen_cards") or [])
                    action_type = adaptive.dmc_sample_action_type(
                        components, int(action_info.get("action_id") or 0)
                    )
                    action_types[action_type] += 1
                    result["model_pass_count"] += int(not cards)
                    result["model_bomb_count"] += int(
                        adaptive.offline_action_is_bomb(
                            components["action_by_id"].get(int(action_info.get("action_id") or 0))
                        )
                    )
                if any(result[field] for field in (
                    "illegal_action_count",
                    "fallback_count",
                    "materialization_fail_count",
                    "hand_card_mismatch_count",
                )):
                    if len(result["failure_samples"]) < 20:
                        result["failure_samples"].append(
                            {
                                "game_index": game_index,
                                "step": steps,
                                "player": int(game.current_player),
                                "record": record,
                            }
                        )
                    break
                steps += 1
            if not game.is_game_over or not game.ranking:
                result["fatal_no_candidate_count"] += 1
                result["game_trace"].append(
                    {
                        **plan,
                        "first_player": first_player,
                        "completed": False,
                        "winner_team": None,
                        "model_won": None,
                        "game_length": steps,
                        "safety_counts": {
                            field: int(result[field]) - game_counter_start[field]
                            for field in game_counter_start
                        },
                    }
                )
                write_arena_snapshot("running", game_index)
                continue
            winner_team = int(game.ranking[0]) % 2
            result["model_wins"] += int(winner_team == model_team)
            result["baseline_wins"] += int(winner_team != model_team)
            result["completed_games"] += 1
            total_steps += steps
            result["game_trace"].append(
                {
                    **plan,
                    "first_player": first_player,
                    "completed": True,
                    "winner_team": winner_team,
                    "model_won": winner_team == model_team,
                    "game_length": steps,
                    "safety_counts": {
                        field: int(result[field]) - game_counter_start[field]
                        for field in game_counter_start
                    },
                }
            )
            write_arena_snapshot("running", game_index)
            if int(args.report_every) > 0 and result["completed_games"] % int(args.report_every) == 0:
                print(
                    f"danzero_arena_progress games={result['completed_games']}/{args.danzero_arena_games} "
                    f"model_wins={result['model_wins']}",
                    flush=True,
                )
    except Exception as exc:
        write_arena_snapshot("error", current_game_index, f"{type(exc).__name__}: {exc}")
        raise
    finally:
        restore_baseline()
    result["model_team_win_rate"] = result["model_wins"] / max(1, result["completed_games"])
    result["baseline_team_win_rate"] = result["baseline_wins"] / max(1, result["completed_games"])
    result["average_game_length"] = total_steps / max(1, result["completed_games"])
    result["model_action_type_distribution"] = dict(action_types)
    result["level_distribution"] = dict(levels)
    result["model_pass_rate"] = result["model_pass_count"] / max(1, result["model_decision_count"])
    result["model_bomb_usage_rate"] = result["model_bomb_count"] / max(1, result["model_decision_count"])
    result["elapsed_seconds"] = time.monotonic() - started
    result["status"] = "completed"
    result["last_game_index"] = int(args.danzero_arena_games) - 1
    integrity_fields = (
        "illegal_action_count",
        "fallback_count",
        "materialization_fail_count",
        "hand_card_mismatch_count",
        "fatal_no_candidate_count",
    )
    result["threshold_passed"] = bool(
        result["completed_games"] == int(args.danzero_arena_games)
        and all(int(result[field]) == 0 for field in integrity_fields)
    )
    result["early_screen_continuation_allowed"] = bool(
        result["threshold_passed"]
        and result["completed_games"] >= 20
        and result["model_team_win_rate"] >= 0.30
    )
    result["allowed_for_stage4_continuation"] = result["early_screen_continuation_allowed"]
    arena_out.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if not result["threshold_passed"]:
        raise RuntimeError("DanZero offline arena integrity gate failed")
    return result
