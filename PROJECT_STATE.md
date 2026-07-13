# PROJECT_STATE.md

## Current Project State

Date: 2026-07-13

Branch: `agent/stage5-website-bot-adaptation`

Latest completed stage:

- Frozen Website Dataset Extension v2.

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
- Extension v1 remains frozen and unchanged at 58 games.
- Current extension v2 contains 70 baseline-only website bot games: 40 wins and
  30 losses, 1,753 decisions, and 49,549 legal candidates.
- Frozen base manifest hash:
  `83a58a43ea91f5662e2588494d7bad1b3d9d18de51c30216e5be0e589e0437e4`.
- Extension v1 manifest hash:
  `db209561f6961b289dda668861687fcd7a258a2f283cecaae065501b2006f429`.
- Extension v2 manifest hash:
  `31c5bc501286ac41d3a791811c7089200e49097132bfd886aa10d281c5ddb27e`.
- Curated evidence: `website_dataset_split_manifest_extension_v2.json` and
  `website_dataset_card_extension_v2.json`.
- All 12 Supplement v2 games and 280 decisions entered train; rejected new
  games or decisions: 0.

Information-set-consistent train/development subset:

- 882 decisions across 61 independent games.
- 718 train decisions and 164 development decisions.
- 37,452 legal candidates.
- 141 lead decisions and 741 follow decisions.
- 659 level-card states, including 278 wildcard states.
- 619 endgame states and 500 bomb-candidate states.
- All 13 level values and all four first-player seats are represented; the
  website account itself remains in seat 0.
- Elo bands: 174 decisions in `1900-1999` and 708 in `2000-2099`.
- Duplicate state count: 0.

Locked test:

- The original nine-game locked-test set is exactly unchanged in extension v2.
- No new session or game was assigned to locked test.
- The isolated physical locked-test partition remains 90 consistent decisions.
- The locked-test partition remains prohibited for training, candidate design,
  checkpoint selection, and teacher threshold tuning.

Teacher dataset:

- Frozen base: `website_information_set_teacher_dataset_v1.pth`, unchanged at
  7 labels from 7 independent games.
- Current dataset: `website_information_set_teacher_dataset_v2.pth`.
- 11 accepted high-confidence teacher labels from 11 independent games: 7
  frozen labels plus 4 extension v1 labels.
- New accepted cases: `13958:12`, `13959:7`, `13957:14`, and `13960:15`.
- Representation: 513 state dimensions, 54 website action dimensions.
- Teacher v2 SHA-256:
  `620b378675ef1964f16043c7c2cdd4d75dc8db3bb7377cab773c3bbe8aec250f`.
- Training gate is closed until at least 20 independent high-confidence teacher
  games exist.

Current blocker:

- Training remains blocked until at least 20 independent high-confidence
  teacher games exist; the current count is 11 and at least 9 more independent
  strong-label games are required.
- The eligible extension v1 train pool is exhausted. Extension v2 now exposes
  280 new consistent train decisions from 12 independent games for the next
  teacher-candidate stage.

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

Status: completed.

Acceptance:

- All 103 eligible decisions from new train games 13956-13960 were screened;
  the 60 development decisions remained held out from teacher-label creation.
- Locked-test states read: 0; hidden/future information use: 0.
- All 3,464 screening and confirmation rollouts completed; incomplete files
  accepted: 0.
- Four new labels passed the existing completeness, variance, advantage,
  confidence, and greedy-plus-frozen-tempo robustness gates.
- Frozen v1 samples are byte-content equivalent after deserialization, source
  state and physical-action remap checks pass, and remap errors are zero.
- Teacher gate remains closed at 11 of 20 independent games.

### Stage 4.5: Website Shadow Supplement v2

Goal: collect the next explicitly assigned baseline-only train session for new
independent information-set teacher candidates.

Status: completed.

Acceptance:

- Exactly 12 new completed verified bot-table games were collected in
  `logs_website_shadow_supplement_train_002`, preassigned to train.
- Results: 8 wins, 4 losses; leaderboard Elo 2060 to 2102, net +42.
- All 280 submissions succeeded and all 280 decisions recorded exhaustive
  website-oracle candidates with consistent decision-time information sets.
- `tempo_baseline` submitted every action; model-controlled website actions: 0.
- Communication, encoding, team mapping, hand-subset, legality, oracle,
  materialization, website-rule, wildcard, information-set, duplicate-submit,
  and unrecoverable-desync counters are all zero.
- Credential occurrences are zero; no dataset rebuild, teacher rollout, model
  training, or model-controlled website play occurred.

### Stage 4.6: Frozen Dataset Extension v2

Goal: add the preassigned supplement v2 train session without changing any
frozen extension v1 game or split.

Status: completed.

Acceptance:

- New extension v2 bundle, physical partitions, manifest, and data card were
  written without overwriting v1.
- All 58 extension v1 games, 12 old session assignments, old source hashes, and
  old split memberships are unchanged; locked-test set changes: 0.
- All 12 supplement v2 games entered train, contributing 280 accepted decisions;
  new development or locked-test games: 0.
- The final dataset contains 70 games, 40 wins, 30 losses, 1,753 decisions, and
  49,549 candidates; rejected files/games: 0.
- The physical train/development partition contains 882 consistent decisions;
  duplicate states: 0; coverage and threshold gates pass.
- Model-controlled actions: 0; no website play, teacher rollout, or training
  occurred.

### Stage 4.7: Extension v2 Teacher Candidate Expansion

Goal: screen every eligible new train state from the 12 Supplement v2 games and
append only robust information-set labels to the frozen teacher v2 base.

Status: next stage; not started.

Acceptance:

- Use only `website_danzero_shadow_extension_v2.train_dev.pth`; do not load the
  complete bundle or locked-test partition.
- Restrict screening to new game IDs 13985-14002 listed in `NEXT_TASK.md`.
- Accept labels only through the existing completeness, variance, advantage,
  confidence, and greedy-plus-frozen-tempo robustness gates.
- Preserve all 11 teacher v2 labels and verify physical-action remapping.
- Do not train a model in this teacher-expansion stage, even if the 20-game gate
  is reached.

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
