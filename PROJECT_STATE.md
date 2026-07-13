# PROJECT_STATE.md

## Current Project State

Date: 2026-07-13

Branch: `agent/stage5-website-bot-adaptation`

Latest completed stage:

- Website Shadow Supplement v1 collection and frozen dataset extension.

Primary program:

- `play_research_adaptive.py`

Frozen baseline:

- `tempo_baseline` remains the frozen website action submitter and comparison
  baseline.
- Baseline equivalence checks have passed in prior stages.

## Current Research Status

The project is in website-domain data adaptation, not model website control.

Current website dataset:

- The original 50-game baseline-only dataset remains frozen and unchanged.
- Extension v1 contains 58 baseline-only website bot games: 32 wins and 26
  losses.
- The eight-game supplement contributed 179 decisions from four wins and four
  losses; all eight games used `leaderboard_elo` and verified bot tables.
- Extension v1 contains 1,473 decisions and 42,919 legal candidates.
- Frozen base manifest hash:
  `83a58a43ea91f5662e2588494d7bad1b3d9d18de51c30216e5be0e589e0437e4`.
- Extension manifest hash:
  `db209561f6961b289dda668861687fcd7a258a2f283cecaae065501b2006f429`.
- Curated evidence: `website_dataset_split_manifest_extension_v1.json` and
  `website_dataset_card_extension_v1.json`.

Information-set-consistent train/development subset:

- 602 decisions across 49 independent games.
- 438 train decisions and 164 development decisions.
- 30,822 legal candidates.
- 88 lead decisions and 514 follow decisions.
- 471 level-card states, including 212 wildcard states.
- 351 endgame states and 375 bomb-candidate states.
- All 13 level values and all four first-player seats are represented; the
  website account itself remains in seat 0.
- Elo bands: 174 decisions in `1900-1999` and 428 in `2000-2099`.
- Duplicate state count: 0.

Locked test:

- The original nine-game locked-test set is exactly unchanged in extension v1.
- No new session or game was assigned to locked test.
- The locked-test partition remains prohibited for training, candidate design,
  checkpoint selection, and teacher threshold tuning.

Teacher dataset:

- `website_information_set_teacher_dataset_v1.pth`
- 7 accepted high-confidence teacher labels.
- 7 independent teacher games.
- Representation: 513 state dimensions, 54 website action dimensions.
- Training gate is closed until at least 20 independent high-confidence teacher
  games exist.

Current blocker:

- The new train/development states are ready for information-set teacher
  candidate screening.
- Training remains blocked until at least 20 independent high-confidence
  teacher games exist; the current count remains 7.

## Active Stage Plan

### Stage 1: Context and Handoff

Goal: create durable handoff docs and define stage prompts.

Acceptance:

- `AGENTS.md`, `PROJECT_STATE.md`, `EXPERIMENTS.md`, and `NEXT_TASK.md` exist.
- Next task is unambiguous.
- No secrets are written to files.

### Stage 2: Website Shadow Supplement

Goal: collect additional baseline-only website bot games.

Status: completed.

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

- 8 new completed bot-only games: 5 train and 3 development.
- 179 successful submissions and model-controlled actions: 0.
- Communication, legality, materialization, hand-card mismatch,
  duplicate-submit, and unrecoverable-desync counts: 0.
- Leaderboard Elo before/after recorded for every game; net change: -10.

### Stage 3: Frozen Dataset Extension

Goal: rebuild a new extension dataset without changing the old frozen split.

Status: completed.

Acceptance:

- Original locked game set and all old session assignments are unchanged.
- New sessions are explicitly assigned to train/development only.
- Consistent train/development decisions: 602; both the 500 gate and 600
  target passed.
- Extension manifest and data card were written without overwriting frozen 050
  files.

### Stage 4: Teacher Candidate Expansion

Goal: screen only new train/development states for robust information-set
teacher labels.

Status: next stage; not started.

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

All JSON persistence now recursively redacts the active runtime credential
values before writing. The supplement logs, global research results, extension
artifacts, source changes, and handoff files passed a zero-occurrence audit for
both runtime values.

## Repository Hygiene

The root directory currently contains many historical models, logs, datasets,
and JSON outputs. Do not move them without a migration manifest. For now:

- Use these four handoff files as the current entry point.
- Keep durable analysis under `docs/`.
- Keep new large artifacts ignored by Git.
- Use explicit output names for every new stage.
