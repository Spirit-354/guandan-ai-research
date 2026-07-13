# AGENTS.md

## Long-Term Operating Rules

This repository is for GuanDan website-domain AI research. The final target is a
website bot-only model that passes the frozen statistical gate: at least 500
completed website games, point win rate at least 70%, and 95% Wilson lower bound
at least 70%.

## Non-Negotiable Constraints

- Do not modify `tempo_baseline` core play semantics.
- Do not modify the website server protocol unless fixing a confirmed
  compatibility bug.
- Do not modify leaderboard Elo semantics.
- Never treat `final_state["scores"]` as Elo. It is proxy-only.
- Website Elo must come from `leaderboard_elo`.
- Do not make an experimental model the default website strategy.
- Do not start model-controlled website play without explicit user confirmation
  for that risk stage.
- Do not write account names, passwords, tokens, or secrets into source, logs,
  datasets, Git commits, PRs, or documentation.
- Runtime credentials must be supplied through `GUANDAN_USER` and
  `GUANDAN_PASSWORD`.

## Information-Set Rules

- Models, search, rollout teachers, and labels may use only information visible
  at the real decision point.
- Do not use opponent hands, teammate hands, future actions, future states, or
  post-game-only information as model/search features.
- Hidden-card simulation must use legal information-set sampling or
  determinization.
- Counterfactual teacher labels must record rollout count, hidden-card sampling
  method, mean return, return variance, candidate advantage, and confidence.
- High-variance or low-advantage candidates must not become strong teacher
  labels.

## Data Rules

- Split website data by complete `game_id`, collection session, time block, and
  robot/table signature.
- Maintain `train`, `development`, and `locked_test`.
- `locked_test` must not be used for training, hyperparameter selection,
  checkpoint selection, teacher threshold tuning, or candidate rule design.
- Formal website validation data must not flow back into research before the
  conclusion is locked.
- Data coverage gates must report independent games, decisions, candidate
  actions, win/loss balance, seat coverage, first-player coverage, level-card
  coverage, wildcard coverage, lead/follow coverage, endgame coverage,
  bomb-state coverage, Elo-band coverage, robot/table coverage, and duplicate
  state rate.

## Execution Rules

- Before coding, state assumptions and success criteria.
- Prefer the smallest change that directly satisfies the current task.
- Do not refactor unrelated code.
- Keep existing code style.
- Validate changes with the narrowest relevant command.
- Commit each completed stage with a conventional commit message.
- Push progress to GitHub after a clean validation.

## Directory Hygiene

- Do not move existing historical logs, models, datasets, or JSON artifacts
  unless a migration manifest is created and every script reference is checked.
- New durable conclusions belong under `docs/progress/` or `docs/research/`.
- New one-off generated outputs should use explicit stage-prefixed names and
  should not be committed unless they are small, curated evidence files.
- New large datasets, model checkpoints, logs, and raw JSON outputs should remain
  ignored by `.gitignore`.
- These handoff files are the canonical context entry points:
  - `PROJECT_STATE.md`
  - `EXPERIMENTS.md`
  - `NEXT_TASK.md`

## Goal-Mode Protocol

Use one stage goal at a time. At the end of each stage:

- update `PROJECT_STATE.md`;
- update `EXPERIMENTS.md` if an experiment ran;
- update `NEXT_TASK.md` with the next single-stage prompt;
- run validation;
- commit and push;
- only mark a goal complete when that stage's acceptance criteria are met.

