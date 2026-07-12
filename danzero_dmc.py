from __future__ import annotations

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


def checkpoint_payload(
    model: Any,
    optimizer: Any,
    replay: deque,
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
    stats: dict,
    learner_version: int,
    rng: random.Random,
) -> None:
    import torch

    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    torch.save(checkpoint_payload(model, optimizer, replay, stats, learner_version, rng), temporary)
    temporary.replace(path)


def train_batch(model: Any, optimizer: Any, replay: deque, batch_size: int, device: Any, rng: random.Random) -> float:
    import torch
    import torch.nn.functional as F

    batch = rng.sample(list(replay), min(int(batch_size), len(replay)))
    states = torch.tensor(np.asarray([sample["state"] for sample in batch], dtype=np.float32), device=device)
    actions = torch.tensor(np.asarray([sample["action"] for sample in batch], dtype=np.float32), device=device)
    targets = torch.tensor([float(sample["target"]) for sample in batch], dtype=torch.float32, device=device)
    predictions = model(states, actions)
    loss = F.mse_loss(predictions, targets)
    optimizer.zero_grad()
    loss.backward()
    torch.nn.utils.clip_grad_norm_(model.parameters(), 10.0)
    optimizer.step()
    return float(loss.item())


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
        "saved_checkpoints": [],
        "resumed_from": None,
        "threshold_passed": False,
        "engineering_smoke_passed": False,
        "stage3_gate_passed": False,
        "resume_compatibility_checked": False,
        "resume_compatibility_mismatches": [],
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
        replay.extend(payload.get("replay_buffer") or [])
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
    output_queue = ctx.Queue(maxsize=max(4, int(args.danzero_actors) * 2))
    episode_counter = ctx.Value("q", int(stats.get("next_episode_index") or stats["completed_games"]))
    episode_lock = ctx.Lock()
    config = {
        "seed": int(args.danzero_seed),
        "max_steps": int(args.danzero_max_steps),
        "epsilon_start": float(args.danzero_epsilon_start),
        "epsilon_end": float(args.danzero_epsilon_end),
        "epsilon_decay_games": int(args.danzero_epsilon_decay_games),
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
                if dead:
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
            ):
                stats[name] += int(counters.get(name, 0))
            if message.get("kind") != "game":
                stats["failed_games"] += 1
                continue
            stats["completed_games"] += 1
            shared["completed_games"] = int(stats["completed_games"])
            winner = int(message["winner_team"])
            stats[f"team{winner}_wins"] += 1
            stats["first_player_distribution"][str(message["first_player"])] += 1
            levels[str(message["active_level"])] += 1
            action_types.update(message.get("action_types") or {})
            total_steps += int(message["steps"])
            actor_version = int(message.get("actor_version") or 0)
            actor_versions.append(actor_version)
            for sample in message.get("samples") or []:
                if learner_version - int(sample.get("actor_version") or 0) > int(args.danzero_max_version_lag):
                    stats["stale_sample_count"] += 1
                    continue
                replay.append(sample)
                stats["accepted_sample_count"] += 1
            stats["total_decisions"] += len(message.get("samples") or [])
            if len(replay) >= int(args.danzero_batch_size):
                model.train()
                for _ in range(int(args.danzero_updates_per_game)):
                    loss = train_batch(model, optimizer, replay, int(args.danzero_batch_size), device, rng)
                    stats["loss_recent"].append(loss)
                    stats["loss_recent"] = stats["loss_recent"][-100:]
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
                save_training_checkpoint(checkpoint, model, optimizer, replay, stats, learner_version, rng)
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
    save_training_checkpoint(final_checkpoint, model, optimizer, replay, stats, learner_version, rng)
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
