# Initial Public Repository State

## Scope

The public repository starts from the current offline GuanDan research client.
Generated datasets, checkpoints, raw website logs, and credentials remain local.

## Current result

The latest control-pass hybrid evaluation used a conservative Q-margin of
`0.38` over 100 offline arena games:

- Model team wins: 47
- Baseline team wins: 53
- Model team win rate: 0.47
- Hybrid overrides: 5
- Override outcomes: 4 wins, 1 loss
- Illegal actions, fallbacks, materialization failures, and hand mismatches: 0

This result is promising but below the internal 0.48 shadow-evaluation gate.
The next planned offline validation is a 300-game run at the same threshold.

## Repository policy

- `tempo_baseline` remains the stable reference.
- Website credentials are read only from environment variables.
- `final_state["scores"]` is never treated as Elo.
- Raw artifacts are summarized here instead of committed directly.
