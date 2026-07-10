# Guandan Research Adaptive Client

This client is a research wrapper around `play_step_0902.py`.
It reuses the existing card recognition, legality checks, comparison rules,
and server protocol. It does not treat `final_state["scores"]` as Elo.

## Environment

Set credentials before running:

```powershell
$env:GUANDAN_USER="your_user"
$env:GUANDAN_PASSWORD="your_password"
$env:GUANDAN_BASE_URL="http://183.175.14.145:8003"
```

`GUANDAN_BASE_URL` is optional. `GUANDAN_USER` and `GUANDAN_PASSWORD`
are required.

## Baseline

Run the original tempo baseline through the research wrapper:

```powershell
python -u -B .\play_research_adaptive.py --strategy tempo --loop --games 30 --metric elo --require-elo --log-dir logs_tempo
```

This uses the `tempo_baseline` profile and should be compared against every
adaptive run.

## Fixed Profile

Run one profile repeatedly:

```powershell
python -u -B .\play_research_adaptive.py --profile defense_heavy --loop --games 50 --metric elo --require-elo --log-dir logs_defense
```

Available profiles are defined in `strategy_profiles.json`.

## Research Mode

Run adaptive profile selection:

```powershell
python -u -B .\play_research_adaptive.py --strategy research --loop --games 200 --metric elo --require-elo --exploration-rate 0.15 --min-games-per-scenario-profile 20 --leaderboard-url "http://183.175.14.145:8003/rank/" --log-dir logs_research
```

The client builds scenario tags from current game state and player models,
then chooses a profile from historical research data plus current state.
Each game reads leaderboard Elo before joining, waits 2-5 seconds after
completion, reads leaderboard Elo again, and stores `elo_delta =
elo_after - elo_before`.

Current live default is `tempo_baseline`. If no `--profile` and no
`--alternate-profiles` are provided, the client uses `tempo_baseline` even when
`--strategy research` is present. Paused profiles are not selected by default;
they run only when explicitly named.

## Alternate Profiles

Restrict research to a subset:

```powershell
python -u -B .\play_research_adaptive.py --strategy research --alternate-profiles tempo_baseline,balanced,defense_heavy,self_sprint --loop --games 100
```

## Metric Modes

- `--metric elo`: reads leaderboard Elo before and after each completed game.
  This mode automatically requires leaderboard Elo. If the current user is not
  visible on `/rank/`, the run stops.
- `--metric proxy`: does not require or read leaderboard Elo. It records
  `final_state["scores"]` only as `proxy_scores` and leaves Elo fields null.
- `--require-elo`: explicit guard for any run where missing leaderboard Elo
  must stop the script.

## Rating Field Probe

Probe whether the server exposes true Elo/rating fields:

```powershell
python -u -B .\play_research_adaptive.py --probe-rating-fields --games 3 --log-dir logs_probe
```

If no confirmed Elo/rating/leaderboard field is found, the output will say:

```text
elo_unavailable=true
```

In normal research, prefer the leaderboard probe. Interface fields are not used
as the primary Elo metric unless explicitly confirmed.

## Leaderboard Elo Probe

Probe the public leaderboard page for the current user:

```powershell
python -u -B .\play_research_adaptive.py --probe-leaderboard "http://183.175.14.145:8003/rank/" --log-dir logs_probe
```

This command reads `GUANDAN_USER`, fetches the HTML leaderboard, verifies the
`# / 用户 / Elo` table columns, then records the current user's rank and Elo
only if the user is visible on the leaderboard. If the user is not found, the
client does not treat proxy scores as Elo.

## Data Files

- `strategy_profiles.json`: tunable profile parameters.
- `bot_memory.json`: persistent player models only when stable player IDs exist.
- `research_results.json`: scenario + profile statistics.
- `logs_research/`: per-game logs, if `--log-dir` is set.

## Elo Versus Scores

`final_state["scores"]` is stored only as proxy data:

```text
proxy_metric_source="final_state.scores"
metric_source="proxy_not_elo"
```

It is never written as `elo_delta`. In Elo mode, `elo_delta` is computed only as
leaderboard `elo_after - elo_before`.

## Checking Whether Adaptive Beats Tempo

1. Run `tempo_baseline` for enough games.
2. Run the adaptive research mode for a comparable number of games.
3. Open `research_results.json`.
4. Compare `average_elo_delta_per_game` only when `metric_source` is
   `leaderboard_elo`.
5. Treat proxy metrics as debugging context, not as the main research metric.

Do not call a profile the best Elo strategy unless true Elo fields are
available.

## Profile Parameters

Currently active parameters:

- `engine_mode`
- `remaining_group_weight`
- `ally_reliability_base`
- `teammate_help_weight`
- `self_sprint_weight`
- `opponent_block_weight`
- `opponent_risk_weight`
- `endgame_defense_weight`
- `bad_lead_size_penalty`
- `teammate_override_penalty`
- `useless_bomb_penalty`
- `giving_control_to_strong_opponent_penalty`

Reserved parameters are stored for later experiments but currently do not
change decisions:

- `follow_gain_threshold`
- `bomb_aggression`
- `bomb_save_weight`
- `strong_opponent_penalty`
- `defense_trigger_count`
- `force_block_count`
- `self_sprint_group_limit`
- `ally_support_count_limit`

## Research Summary

Print the current Elo research summary:

```powershell
python -u -B .\play_research_adaptive.py --summary research_results.json --recent-window 10
```

The summary uses `leaderboard_elo` only. It marks scenario/profile pairs with
fewer than 20 games as `insufficient_samples`, and does not treat a global
profile as comparable until it has at least 30 games.

The summary also prints recent-window statistics from `game_records` and
`profile_status` with:

- `active_default`: `tempo_baseline`
- `candidate`: `weak_ally_safe`, `tempo_high_elo_safe`, `bait_high_card`
- `paused`: profiles paused by observed Elo or manual risk status

## Experimental Profiles

`tempo_high_elo_safe` is a candidate wrapper around tempo for high-Elo risk
control. It activates its extra caution when leaderboard Elo is high, recent
tempo results are negative, or opponents are near finishing. It does not modify
the baseline `choose_play` implementation.

`bait_high_card` is a candidate wrapper around tempo. In early or mid game, it
may lead a non-critical J/Q/K/A singleton to test whether aggressive bots spend
control cards early. It stops baiting when any opponent has 6 or fewer cards or
when high-Elo risk is active.

Both profiles are experiments. `tempo_baseline` remains the live default.
