# PROJECT_STATE.md

## Current Project State

Date: 2026-07-13

Branch: `agent/stage5-website-bot-adaptation`

Latest pushed commit:

- `3cf42fa docs(research): record teacher confirmation sweep`

Primary program:

- `play_research_adaptive.py`

Frozen baseline:

- `tempo_baseline` remains the frozen website action submitter and comparison
  baseline.
- Baseline equivalence checks have passed in prior stages.

## Current Research Status

The project is in website-domain data adaptation, not model website control.

Current website dataset:

- 50 baseline-only website bot games.
- 28 wins, 22 losses.
- 1,294 decisions.
- 35,231 legal candidates.
- Frozen split manifest hash:
  `83a58a43ea91f5662e2588494d7bad1b3d9d18de51c30216e5be0e589e0437e4`.

Information-set-consistent train/development subset:

- 423 decisions total.
- 319 train decisions.
- 104 development decisions.
- 53 lead decisions.
- 370 follow decisions.
- 11 level-6 decisions.
- Elo bands currently observed: `1900-1999`, `2000-2099`.

Locked test:

- The locked test split exists and must remain untouched for training,
  candidate design, checkpoint selection, and teacher threshold tuning.

Teacher dataset:

- `website_information_set_teacher_dataset_v1.pth`
- 7 accepted high-confidence teacher labels.
- 7 independent teacher games.
- Representation: 513 state dimensions, 54 website action dimensions.
- Training gate is closed until at least 20 independent high-confidence teacher
  games exist.

Current blocker:

- More independent website bot Shadow data is needed before further teacher
  expansion or training.

## Active Stage Plan

### Stage 1: Context and Handoff

Goal: create durable handoff docs and define stage prompts.

Acceptance:

- `AGENTS.md`, `PROJECT_STATE.md`, `EXPERIMENTS.md`, and `NEXT_TASK.md` exist.
- Next task is unambiguous.
- No secrets are written to files.

### Stage 2: Website Shadow Supplement

Goal: collect additional baseline-only website bot games.

Constraints:

- Only `tempo_baseline` may submit website actions.
- Model suggestions may be logged only as Shadow evidence.
- Non-bot tables must stop before the first action.
- Credentials must come from `GUANDAN_USER` and `GUANDAN_PASSWORD`.

Planned sessions:

- `logs_website_shadow_supplement_train_001`: 5 completed games, train.
- `logs_website_shadow_supplement_development_001`: 3 completed games,
  development.

Acceptance:

- 8 new completed bot-only games.
- Model-controlled actions: 0.
- Communication and legality errors: 0.
- Leaderboard Elo before/after recorded.

### Stage 3: Frozen Dataset Extension

Goal: rebuild a new extension dataset without changing the old frozen split.

Acceptance:

- Original locked game set unchanged.
- Old session assignments unchanged.
- New sessions explicitly assigned to train/development only.
- Consistent train/development decisions at least 500, target at least 600.
- New manifest and data card are written without overwriting frozen 050 files.

### Stage 4: Teacher Candidate Expansion

Goal: screen only new train/development states for robust information-set
teacher labels.

Acceptance:

- No locked-test state is read.
- No hidden information or future information is used.
- Strong labels require robust greedy-plus-frozen-tempo advantages.
- Teacher gate remains closed until 20 independent teacher games exist.

### Stage 5: Training Gate

Goal: train only after enough teacher labels and coverage exist.

Acceptance:

- At least 20 independent high-confidence teacher games.
- Coverage audit passes.
- Train/development split is frozen.
- Capability claims remain limited until offline and website-domain gates pass.

### Stage 6: Offline Gate

Goal: compare candidates against frozen `tempo_baseline`.

Acceptance:

- Paired, seat-swapped offline Arena.
- 20-game smoke, 100/200-game screen, and only strongest candidates proceed to
  1000-game confirmation.
- Legality, materialization, hand subset, and duplicate-submit counters all zero.

### Stage 7: Website Shadow Candidate

Goal: run model as observer only on website states.

Acceptance:

- No model-controlled website play.
- Report disagreement, Q calibration, low-support actions, and high-confidence
  disagreement casebook.

### Stage 8: Controlled Website Takeover

Goal: model-controlled website play only after explicit user confirmation.

Required sequence:

- 1-2 game communication smoke.
- 5 games.
- 10 games.
- 20 games.
- 50 games.
- 100 games.
- 200 games.
- 500 games.

Each expansion requires user confirmation.

### Stage 9: Final Validation

Goal: prove final website bot-only performance.

Acceptance:

- At least 500 completed games.
- Point estimate win rate at least 70%.
- 95% Wilson lower bound at least 70%.
- All safety counters zero.
- Results stratified by Elo band, bot/table type, and scenario.

## Credential Handling

The user has authorized use of a test account for website robot experiments, but
the values must not be persisted. Commands must read credentials from:

- `GUANDAN_USER`
- `GUANDAN_PASSWORD`

Do not print or commit credential values.

## Repository Hygiene

The root directory currently contains many historical models, logs, datasets,
and JSON outputs. Do not move them without a migration manifest. For now:

- Use these four handoff files as the current entry point.
- Keep durable analysis under `docs/`.
- Keep new large artifacts ignored by Git.
- Use explicit output names for every new stage.

