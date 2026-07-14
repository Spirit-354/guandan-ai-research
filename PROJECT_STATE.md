# PROJECT_STATE.md

## Current Project State

Date: 2026-07-14

Branch: `agent/stage5-website-bot-adaptation`

Latest completed stage:

- Extension v3 Information-Set Teacher Candidate Expansion.

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
- Extension v2 remains frozen and unchanged at 70 games.
- Current extension v3 contains 82 baseline-only website bot games: 49 wins and
  33 losses, 2,061 decisions, and 57,871 legal candidates.
- Frozen base manifest hash:
  `83a58a43ea91f5662e2588494d7bad1b3d9d18de51c30216e5be0e589e0437e4`.
- Extension v1 manifest hash:
  `db209561f6961b289dda668861687fcd7a258a2f283cecaae065501b2006f429`.
- Extension v2 manifest hash:
  `31c5bc501286ac41d3a791811c7089200e49097132bfd886aa10d281c5ddb27e`.
- Extension v3 manifest hash:
  `51fe0244407d67e8267ea11b7146ff214f73823c29db92062189a58d033e5af9`.
- Curated evidence: `website_dataset_split_manifest_extension_v3.json` and
  `website_dataset_card_extension_v3.json`.
- All 12 Supplement v3 games, 308 decisions, and 8,322 candidates entered
  train; rejected new games or decisions: 0.

Information-set-consistent train/development subset:

- 1,190 decisions across 73 independent games.
- 1,026 train decisions and 164 development decisions.
- 45,774 legal candidates.
- 193 lead decisions and 997 follow decisions.
- 807 level-card states, including 331 wildcard states.
- 891 endgame states and 606 bomb-candidate states.
- All 13 level values and all four first-player seats are represented; the
  website account itself remains in seat 0.
- Elo bands: 174 decisions in `1900-1999`, 744 in `2000-2099`, and 272 in
  `2100-2199`.
- Duplicate state count: 0.

Locked test:

- The original nine-game locked-test set is exactly unchanged in extension v3.
- No new session or game was assigned to locked test.
- The isolated physical locked-test partition remains 90 consistent decisions.
- The locked-test partition remains prohibited for training, candidate design,
  checkpoint selection, and teacher threshold tuning.

Teacher dataset:

- Frozen base: `website_information_set_teacher_dataset_v3.pth`, unchanged at
  13 labels from 13 independent games.
- Current dataset: `website_information_set_teacher_dataset_v4.pth`.
- 16 accepted high-confidence teacher labels from 16 independent games: 13
  frozen labels plus 3 extension v3 labels.
- New accepted cases: `14022:16`, `14025:20`, and `14031:4`.
- Representation: 513 state dimensions, 54 website action dimensions.
- Teacher v4 SHA-256:
  `fa193705777987d0bad91f9a45f5aa956a02e22ffa077a04bc2c81892aeb5f99`.
- Training gate is closed until at least 20 independent high-confidence teacher
  games exist.

Current blocker:

- Training remains blocked until at least 20 independent high-confidence
  teacher games exist; the current count is 16 and at least 4 more independent
  strong-label games are required.
- The eligible extension v3 train pool is exhausted: all 247 rollout-eligible
  states were screened and every permitted positive-lower-bound alternative
  for a failed game was confirmed or rejected by the frozen strong-label gates.
- The next stage is a new explicitly preassigned baseline-only train supplement;
  it must not rebuild the dataset, run teacher rollout, or train a model.

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

Status: completed.

Acceptance:

- Only `website_danzero_shadow_extension_v2.train_dev.pth` was loaded; complete
  bundle and locked-test loads were zero.
- All 280 new train decisions were enumerated: 249 eligible states completed
  greedy-only screening and 31 were ineligible because a public hand count was
  nonpositive.
- Greedy-only screening completed 5,760/5,760 rollouts and accepted zero strong
  labels. Dual-continuation confirmation completed 512/512 rollouts across
  eight selected cases, with no timeout or integrity failure.
- `13992:16` and `14000:5` passed the frozen completeness, variance, advantage,
  confidence, and greedy-plus-frozen-tempo gates; every other positive-screen
  alternative was rejected.
- All 11 teacher v2 samples were preserved exactly after deserialization;
  state, behavior-action, legality, 54-dimensional physical-action remap, and
  credential errors were zero.
- Teacher v3 contains 13 labels from 13 games. The 20-game gate remains closed,
  and website play, model training, offline evaluation, and model-controlled
  website actions were all zero in this stage.

### Stage 4.8: Website Shadow Supplement v3

Goal: collect the next explicitly assigned baseline-only train session for new
independent information-set teacher candidates.

Status: completed.

Acceptance:

- `logs_website_shadow_supplement_train_003` was assigned to train before
  collection while all three prior assignments remained unchanged; locked-test
  assignment changes: 0.
- Exactly 12 verified bot-table games completed: 9 wins and 3 losses.
- All 308 submissions succeeded; all 308 decisions recorded exhaustive
  website-oracle candidates and consistent decision-time information sets,
  covering 8,322 legal candidates.
- Frozen `tempo_baseline` submitted every action; model-controlled actions and
  suggestion differences: 0.
- Leaderboard Elo was continuous from 2102 to 2158, net +56, with every game
  sourced from `leaderboard_elo` rather than final-state scores.
- Failed games, non-bot actions, communication, encoding, team mapping,
  hand-subset, legality, oracle, materialization, website-rule, wildcard,
  information-set, duplicate-submit, and unrecoverable-desync errors: 0.
- No dataset rebuild, teacher rollout, model training, offline evaluation, or
  model-controlled website play occurred; credential occurrences: 0.

### Stage 4.9: Frozen Dataset Extension v3

Goal: add the preassigned Supplement v3 train session without changing any
frozen extension v2 game, split, source hash, or locked-test membership.

Status: completed.

Acceptance:

- New v3 bundle, physical partitions, manifest, and data card were written
  without overwriting v2.
- All 70 extension v2 games, 70 old source hashes, 13 old session assignments,
  old split memberships, and the exact nine-game locked-test set are unchanged.
- All 12 Supplement v3 games entered train, contributing 308 decisions and
  8,322 candidates; new development or locked-test games: 0.
- Extension v3 contains 82 games, 49 wins, 33 losses, 2,061 decisions, and
  57,871 candidates; rejected files or games: 0.
- The physical train/development partition contains 1,190 consistent decisions:
  1,026 train and 164 development, with 45,774 candidates and zero duplicate
  states. Coverage, information-set rollout, and threshold gates pass.
- The isolated locked-test partition remains nine games and 90 consistent
  decisions. Model-controlled actions: 0; no website play, teacher rollout,
  model training, or offline evaluation occurred.

### Stage 4.10: Extension v3 Teacher Candidate Expansion

Goal: screen every eligible new train state from the 12 Supplement v3 games and
append only robust information-set labels to the frozen teacher v3 base.

Status: completed.

Constraints:

- Load only `website_danzero_shadow_extension_v3.train_dev.pth`; do not load
  the complete bundle or locked-test partition.
- Restrict screening to the 12 new game IDs recorded in `NEXT_TASK.md`.
- Greedy-only results may select confirmation candidates but cannot directly
  produce strong labels.
- Accept labels only through the frozen 16-rollout completeness, variance,
  advantage, confidence, and greedy-plus-frozen-tempo robustness gates.
- Preserve all 13 teacher v3 labels and verify 54-dimensional physical-action
  remapping. Do not train, even if the 20-game gate is reached.

Acceptance:

- Only the v3 physical train/development partition was loaded; complete-bundle
  and locked-test loads were zero.
- All 308 new train decisions were enumerated: 247 eligible states completed
  greedy-only screening and 61 were ineligible because a public hand count was
  nonpositive.
- Greedy-only screening completed 5,560/5,560 rollouts and accepted zero strong
  labels. Dual-continuation confirmation completed 368/368 rollouts across six
  selected cases, with no timeout or integrity failure.
- `14022:16`, `14025:20`, and `14031:4` passed every frozen strong-label gate;
  all permitted alternatives for failed games were exhausted.
- All 13 teacher v3 samples were preserved exactly after deserialization;
  state, behavior-action, legality, 513/54 dimensions, and physical-card remap
  errors were zero.
- Teacher v4 contains 16 labels from 16 games. The 20-game gate remains closed,
  and website play, model training, offline evaluation, and model-controlled
  website actions were all zero in this stage.

### Stage 4.11: Website Shadow Supplement v4

Goal: collect the next explicitly assigned baseline-only train session for new
independent information-set teacher candidates.

Status: next stage; not started.

Constraints:

- Preserve all cumulative session assignments and preassign only the unused v4
  supplement session to train before collection.
- Only frozen `tempo_baseline` may submit website actions; stop non-bot tables
  before the first action.
- Collect exactly 12 completed verified bot-table games with exhaustive oracle
  candidates and decision-time-consistent information sets.
- Record Elo only from `leaderboard_elo`. Do not rebuild a dataset, run teacher
  rollout, train, evaluate, or allow model-controlled website play.

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
