# EXPERIMENTS.md

## Experiment Ledger

This file summarizes results that affect current decisions. Full raw artifacts
remain in the workspace but are not the primary handoff surface.

## Frozen Baseline and Website Shadow

Status: active baseline, not replaced.

Evidence:

- `tempo_baseline` remains the strongest and safest website submitter.
- Earlier experimental profiles did not consistently outperform it.
- Website Shadow data collection uses `tempo_baseline` only.

Decision:

- Do not make any learned model the default website strategy.
- Do not modify `tempo_baseline` core logic.

## Website Dataset 050

Status: frozen.

Evidence:

- 50 bot-only baseline website games.
- 28 wins, 22 losses.
- 1,294 decisions and 35,231 candidates.
- Split manifest hash:
  `83a58a43ea91f5662e2588494d7bad1b3d9d18de51c30216e5be0e589e0437e4`.
- 423 physically consistent train/development decisions.

Decision:

- Keep the old split frozen.
- Extend with explicitly assigned new sessions only.
- Do not inspect or use locked test for candidate design.

## Website Information-Set Teacher Labels

Status: expanded but below training gate.

Accepted strong labels:

- Frozen v1 contributed 7 unchanged labels from 7 independent games.
- Extension v1 contributed 4 labels from 4 independent games:
  `13958:12`, `13959:7`, `13957:14`, and `13960:15`.
- Extension v2 contributed 2 labels from 2 independent games: `13992:16` and
  `14000:5`.
- Extension v3 contributed 3 labels from 3 independent games: `14022:16`,
  `14025:20`, and `14031:4`.
- Current teacher dataset: `website_information_set_teacher_dataset_v4.pth`.
- Current total: 16 labels from 16 independent games.
- State/action representation: 513/54.
- Teacher v4 SHA-256:
  `fa193705777987d0bad91f9a45f5aa956a02e22ffa077a04bc2c81892aeb5f99`.

Rejected or exhausted evidence:

- Several old candidates had positive mean advantage but failed confidence,
  variance, or continuation-robustness gates.
- The old 50-game candidate pool is mostly exhausted.

Decision:

- Do not train from the 16-label teacher dataset as a capability candidate.
- Collect more independent baseline-only train games before another teacher
  expansion; at least 4 additional strong-label games are still required.

## Website Shadow Supplement v1

Status: completed; baseline-only gate passed.

Evidence:

- Five train-session and three development-session games completed.
- All eight games were verified bot tables and used `tempo_baseline` as the
  only submission policy.
- The sessions contain 179 exhaustive Shadow decisions: 119 train and 60
  development.
- All 179 submit results succeeded.
- Four wins and four losses moved leaderboard Elo from 2070 to 2060, a net
  change of -10.
- Model control, communication failure, state encoding, team mapping, hand
  subset, local legality, oracle disagreement, materialization, website-rule,
  wildcard, information-set, duplicate-submit, and unrecoverable-desync counts
  are all zero.
- Runtime credential values were redacted from the new logs and global research
  results before the extension was rebuilt; the final logs, datasets, curated
  evidence, source changes, and handoff files contain neither value.

Decision:

- Accept all eight games into the explicitly assigned extension sessions.
- Do not infer Elo from `final_state["scores"]`; the supplement metric source is
  `leaderboard_elo` for all eight games.

## Website Dataset Extension v1

Status: frozen; coverage gate passed.

Evidence:

- 58 accepted bot-only games, 1,473 decisions, and 42,919 legal candidates.
- The original 50-game split, every old session assignment, and the nine-game
  locked-test set are unchanged.
- New games 13956-13960 are train; 13961-13963 are development; locked test has
  no new game.
- The information-set-consistent train/development partition contains 602
  decisions across 49 independent games: 438 train and 164 development.
- It contains 88 lead, 514 follow, 471 level-card, 212 wildcard, 351 endgame,
  and 375 bomb-candidate states, with all levels and all first-player seats
  represented.
- Elo-band coverage is 174 decisions in `1900-1999` and 428 in `2000-2099`;
  duplicate state count is zero.
- Extension manifest hash:
  `db209561f6961b289dda668861687fcd7a258a2f283cecaae065501b2006f429`.

Decision:

- Freeze extension v1 and use only its physical train/development partition
  for the next teacher-candidate stage.
- Keep the complete bundle and locked-test partition out of candidate design,
  rollout selection, and threshold tuning.

## Extension v1 Teacher Candidate Expansion

Status: completed; four new labels accepted and training gate remains closed.

Evidence:

- The physical train/development partition SHA-256 is
  `9fb93a87f625230638ee0beeac32a1edfb2ca3d9718aa514a972c683a189d6b0`.
- Of 119 decisions in new train games 13956-13960, 103 had nonzero public
  hand counts for every player and were eligible for information-set rollout;
  all 103 were screened. The 60 new development decisions were held out from
  teacher-label creation.
- Greedy-only screening evaluated 339 candidates with 2,712/2,712 completed
  rollouts. It was used only to select confirmation cases and could not emit a
  strong label.
- Ensemble confirmation evaluated 12 cases and 47 candidates with 752/752
  completed paired rollouts: 376 greedy and 376 frozen-tempo continuations.
- Every evaluation recorded uniform physical information-set sampling, the
  stable game/turn/determinization seed scheme, mean and variance, paired
  advantage and 95% lower bound, completion, and per-profile advantages.
- Locked-test loads, hidden/future information use, timeouts, integrity
  failures, incomplete accepted files, and remap errors were all zero.
- Accepted new cases and key statistics:
  - `13958:12`: advantage 0.875, lower bound 0.373, candidate variance
    0.467, greedy/tempo advantages 1.0/0.75.
  - `13959:7`: advantage 0.875, lower bound 0.258, candidate variance 0.25,
    greedy/tempo advantages 1.5/0.25.
  - `13957:14`: advantage 0.875, lower bound 0.373, candidate variance
    0.467, greedy/tempo advantages 1.0/0.75.
  - `13960:15`: advantage 0.625, lower bound 0.156, candidate variance
    0.467, greedy/tempo advantages 0.75/0.5.
- Several apparently strong greedy signals were rejected because frozen-tempo
  advantage was zero or negative, confidence was not positive, or candidate
  variance exceeded 0.50. Game 13956 produced no confirmation-worthy strong
  signal.
- Rebuilding from the frozen v1 base preserved all seven old samples exactly
  after deserialization and appended only the four accepted train labels.
  Source state identity, behavior action, legal teacher action, physical remap,
  and 513/54 dimensions all passed.

Decision:

- Freeze `website_information_set_teacher_dataset_v2.pth` as the current
  11-game teacher dataset.
- Keep the training gate closed because 11 is below the required 20
  independent high-confidence teacher games.
- Treat the eligible extension v1 train pool as exhausted and collect a new
  baseline-only train supplement rather than weaken thresholds or repeatedly
  expand low-evidence candidates.

## Website Shadow Supplement v2

Status: completed; baseline-only collection gate passed.

Evidence:

- `logs_website_shadow_supplement_train_002` was assigned to train before
  collection in `website_dataset_extension_session_splits_v2.json`; the two v1
  supplement assignments are unchanged and no session is assigned to locked
  test.
- Exactly 12 verified bot-table games completed: 8 wins and 4 losses.
- Leaderboard Elo moved continuously from 2060 to 2102, a net change of +42;
  all 12 games use `leaderboard_elo` and none infer Elo from final-state scores.
- The session contains 280 Shadow decisions. All 280 submissions succeeded,
  all 280 candidate sets are website-oracle exhaustive, and all 280
  decision-time information sets are consistent.
- Every submitted action came from frozen `tempo_baseline`; model-controlled
  actions and suggestion disagreements are zero.
- Failed games, state encoding, team mapping, hand subset, local legality,
  oracle disagreement, materialization, website-rule, inferred acceptance,
  wildcard, information-set, duplicate-submit, and unrecoverable-desync counts
  are all zero.
- Runtime credential occurrences in the session logs, Shadow summary, global
  research results, preassignment, and tracked stage files are zero.
- No dataset rebuild, teacher rollout, model training, or model-controlled
  website play occurred in this stage.

Decision:

- Accept all 12 games as the new preassigned train-session supplement.
- Keep extension v1 and teacher v2 frozen until a separate dataset-extension
  stage rebuilds new v2 artifacts.
- Do not screen these states or train from them before the extension v2
  partitions and manifests pass their existing gates.

## Website Dataset Extension v2

Status: frozen; coverage gate passed.

Evidence:

- The extension v1 manifest content hash was verified as
  `db209561f6961b289dda668861687fcd7a258a2f283cecaae065501b2006f429`
  before rebuilding.
- Extension v2 contains 70 accepted bot-only games, 40 wins, 30 losses, 1,753
  decisions, and 49,549 legal candidates; rejected files or games: 0.
- All 58 extension v1 games, their split assignments, all 12 old sessions, and
  every old source-file hash are unchanged. The nine-game locked-test set is
  exactly identical.
- New game IDs 13985, 13986, 13987, 13989, 13991, 13992, 13994, 13996, 13997,
  13999, 14000, and 14002 all entered train. New development and locked-test
  games: 0.
- The 1,473 old samples are unchanged after excluding the expected new split
  manifest hash field. All 280 new samples are train, bot-verified,
  `leaderboard_elo`, information-set consistent, and sourced from the new
  supplement session.
- The physical train/development partition contains 882 decisions across 61
  games: 718 train and 164 development, with 37,452 legal candidates.
- Physical coverage includes 141 lead, 741 follow, 659 level-card, 278 wildcard,
  619 endgame, and 500 bomb-candidate decisions; all levels and first-player
  seats are represented across both Elo bands.
- Duplicate state count is zero. Coverage, information-set rollout, and dataset
  threshold gates pass; capability evidence remains ineligible.
- The isolated locked-test partition contains the same nine games and 90
  consistent decisions. It was audited only for isolation and membership, not
  used for candidate design or tuning.
- Extension v2 manifest content hash:
  `31c5bc501286ac41d3a791811c7089200e49097132bfd886aa10d281c5ddb27e`.

Decision:

- Freeze extension v2 and use only its physical train/development partition in
  the next teacher-candidate stage.
- Keep the complete bundle and isolated locked-test partition out of screening,
  threshold selection, and label construction.
- Preserve teacher v2 as the frozen 11-label base; do not train during the next
  teacher expansion.

## Extension v2 Teacher Candidate Expansion

Status: completed; two new labels accepted and training gate remains closed.

Evidence:

- The only loaded dataset was the physical train/development partition with
  SHA-256
  `03d1a0967429fd75433ea3753a96c4bce43660f636a7cf9801140bd02777cc60`;
  complete-bundle and locked-test loads were zero.
- All 280 decisions from the 12 new train games were enumerated. 249 were
  rollout eligible; 31 were excluded because at least one public hand count was
  nonpositive.
- Greedy-only screening covered all 249 eligible states, 720 candidate actions,
  and 5,760/5,760 rollouts. It emitted zero strong labels and was used only to
  choose confirmation cases.
- Twelve positive-lower-bound, low-variance screen signals covered six games.
  Confirmation evaluated the strongest state per game and the remaining
  positive-screen alternatives for failed games: eight cases, 32 candidates,
  and 512/512 paired rollouts, split evenly between greedy and frozen-tempo
  continuations.
- Every rollout used uniform physical assignment conditioned on public counts,
  the stable game/turn/determinization seed scheme, and shared
  determinizations. Timeouts, incomplete cases, integrity failures, hidden-hand
  access, future-information access, and locked-test access were all zero.
- `13992:16` and `14000:5` each had advantage 0.875, 95% lower bound 0.373,
  candidate variance 0.0, and greedy/frozen-tempo advantages 1.0/0.75.
- Rejections remained frozen-gate decisions: `13986:8` and `13986:10` exceeded
  candidate variance 0.50; `13987:3`, `13987:6`, `13991:2`, and `14002:8`
  failed the confidence or dual-continuation robustness gates. No other game
  retained a positive-screen alternative.
- Teacher v3 preserves all 11 teacher v2 samples exactly after deserialization
  and appends only the two accepted labels. All source-state, behavior-action,
  legal-action, 513/54 dimension, and physical-card remap checks passed.

Decision:

- Freeze `website_information_set_teacher_dataset_v3.pth` at 13 labels from 13
  independent games.
- Keep the 20-game training gate closed; do not train, evaluate, or promote a
  model from this artifact.
- Treat the extension v2 candidate pool as exhausted and collect another
  explicitly preassigned baseline-only train supplement without weakening any
  teacher threshold.

## Website Shadow Supplement v3

Status: completed; baseline-only collection gate passed.

Evidence:

- `website_dataset_extension_session_splits_v3.json` preserves all three prior
  assignments and adds only `logs_website_shadow_supplement_train_003` as
  train; no session is assigned to locked test.
- Exactly 12 verified bot-table games completed: 9 wins and 3 losses. Game IDs
  are 14018, 14019, 14020, 14021, 14022, 14023, 14025, 14026, 14027, 14029,
  14030, and 14031.
- Leaderboard Elo moved continuously from 2102 to 2158, a net change of +56;
  all 12 games use `leaderboard_elo` and none infer Elo from final-state scores.
- The session contains 308 Shadow decisions and 8,322 legal candidates. All
  308 submissions succeeded, all candidate sets are website-oracle exhaustive,
  and all decision-time information sets are consistent.
- Every submitted action came from frozen `tempo_baseline`; model-controlled
  actions and suggestion differences are zero.
- Failed games, non-bot actions, state encoding, team mapping, hand subset,
  local legality, oracle disagreement, materialization, website-rule, inferred
  acceptance, wildcard, information-set, duplicate-turn, extra error-log, and
  unrecoverable-desync counts are all zero.
- Runtime credential occurrences in the new logs, Shadow summary, cumulative
  assignment, global research results, and tracked files are zero.
- Frozen extension v2 and teacher v3 hashes are unchanged. No dataset rebuild,
  teacher rollout, model training, offline evaluation, or model-controlled
  website play occurred in this stage.

Decision:

- Accept all 12 games as the next explicitly preassigned train supplement.
- Keep extension v2 and teacher v3 frozen until a separate dataset-extension
  stage builds and validates new v3 artifacts.
- Do not screen these states or train from them before the v3 physical
  partitions, manifest, and coverage gates pass.

## Website Dataset Extension v3

Status: frozen; coverage gate passed.

Evidence:

- The extension v2 manifest content hash was verified as
  `31c5bc501286ac41d3a791811c7089200e49097132bfd886aa10d281c5ddb27e`
  before construction, and all five v2 artifact hashes remained unchanged.
- Extension v3 contains 82 accepted bot-only games, 49 wins, 33 losses, 2,061
  decisions, and 57,871 legal candidates; rejected files or games: 0.
- All 70 extension v2 games, their split assignments, all 13 old sessions, and
  every old source-file hash are unchanged. The nine-game locked-test set is
  exactly identical.
- New games 14018, 14019, 14020, 14021, 14022, 14023, 14025, 14026, 14027,
  14029, 14030, and 14031 all entered train. New development and locked-test
  games: 0.
- All 1,753 old samples are unchanged after excluding the expected new split
  manifest hash field. All 308 new samples are train, bot-verified,
  `leaderboard_elo`, information-set consistent, and sourced from Supplement
  v3.
- The physical train/development partition contains 1,190 decisions across 73
  games: 1,026 train and 164 development, with 45,774 legal candidates.
- Physical coverage includes 193 lead, 997 follow, 807 level-card, 331 wildcard,
  891 endgame, and 606 bomb-candidate decisions; all levels and first-player
  seats are represented across three Elo bands.
- Duplicate state count is zero. Coverage, information-set rollout, and dataset
  threshold gates pass; capability evidence remains ineligible.
- The isolated locked-test partition contains the same nine games and 90
  consistent decisions, with zero training samples.
- Extension v3 manifest content hash:
  `51fe0244407d67e8267ea11b7146ff214f73823c29db92062189a58d033e5af9`.
- Extension v3 artifact SHA-256 values:
  - bundle: `0235f53f7aec87cd3f7c62a529fd2d05af899a7befa72280fe4d5da234b4ac81`;
  - train/development: `e5edc7090657ac1c4b4a2b2a14f38ad9bb0145ba1c19b6e85fca20bb1b5a687a`;
  - locked-test: `941c66107e93aaa5d26965aa4b3a26fee0e0fab70f73ed489d6c49eaf3d60e59`;
  - manifest file: `c91cb7665e9fcca68ee0161582a2794701057611a71485527f7ab8fcf97ecc83`;
  - data card: `f8eedcec8fa6679760e5bf4e202bef19bd07ee681b040f68168b22ce8b01c177`.

Decision:

- Freeze extension v3 and use only its physical train/development partition in
  the next teacher-candidate stage.
- Keep the complete bundle and isolated locked-test partition out of screening,
  threshold selection, and label construction.
- Preserve teacher v3 as the frozen 13-label base; do not train during the next
  teacher expansion.

## Extension v3 Teacher Candidate Expansion

Status: completed; three new labels accepted and training gate remains closed.

Evidence:

- The only loaded dataset was
  `website_danzero_shadow_extension_v3.train_dev.pth`, whose SHA-256 remained
  `e5edc7090657ac1c4b4a2b2a14f38ad9bb0145ba1c19b6e85fca20bb1b5a687a`;
  complete-bundle and locked-test loads were zero.
- All 308 decisions from the 12 new train games were enumerated. 247 were
  rollout eligible; 61 were excluded because at least one public hand count was
  nonpositive. Per-game eligibility and rejection counts were recorded.
- Greedy-only screening covered all 247 eligible states, 695 candidate actions,
  and 5,560/5,560 rollouts. It emitted zero strong labels and was used only to
  choose confirmation cases.
- Ten positive-lower-bound, low-variance screen signals covered five games.
  Confirmation evaluated the strongest state per game first and then the only
  remaining permitted alternative for a failed game: six cases, 23 candidates,
  and 368/368 rollouts split evenly between greedy and frozen-tempo
  continuations.
- Every rollout used uniform physical assignment conditioned on public counts,
  stable game/turn/determinization seeds, and shared determinizations. Timeouts,
  incomplete cases, integrity failures, hidden-hand access, future-information
  access, and locked-test access were all zero.
- `14022:16` passed with advantage 0.875, 95% lower bound 0.373, candidate
  variance 0.0, and greedy/frozen-tempo advantages 1.25/0.50.
- `14025:20` passed with advantage 1.0, 95% lower bound 0.494, candidate
  variance 0.0, and greedy/frozen-tempo advantages 1.0/1.0.
- `14031:4` passed with advantage 0.625, 95% lower bound 0.156, candidate
  variance 0.25, and greedy/frozen-tempo advantages 0.75/0.50.
- `14020:7` and `14021:2` exceeded candidate variance 0.50. The only remaining
  failed-game alternative, `14021:10`, had a negative 95% lower bound. No other
  failed game retained a permitted positive-screen alternative.
- Teacher v4 preserves all 13 teacher v3 samples exactly after deserialization
  and appends only the three accepted labels. All source-state,
  behavior-action, legal-action, 513/54 dimension, and physical-card remap
  checks passed. Teacher v3 remained unchanged.

Decision:

- Freeze `website_information_set_teacher_dataset_v4.pth` at 16 labels from 16
  independent games; its SHA-256 is
  `fa193705777987d0bad91f9a45f5aa956a02e22ffa077a04bc2c81892aeb5f99`.
- Keep the 20-game training gate closed; do not train, evaluate, or promote a
  model from this artifact.
- Treat the extension v3 candidate pool as exhausted and collect another
  explicitly preassigned baseline-only train supplement without weakening any
  teacher threshold.

## Website Shadow Supplement v4

Status: completed; baseline-only collection gate passed.

Evidence:

- `website_dataset_extension_session_splits_v4.json` preserves all four prior
  assignments and adds only `logs_website_shadow_supplement_train_004` as
  train; no session is assigned to locked test.
- Exactly 12 verified bot-table games completed: 6 wins and 6 losses. Game IDs
  are 14035, 14036, 14037, 14038, 14039, 14040, 14041, 14042, 14043, 14044,
  14045, and 14046.
- Leaderboard Elo moved continuously from 2158 to 2121, a net change of -37.
  Per-game deltas were -19, +12, +12, -18, +12, +11, -18, -18, +12, -18,
  -18, and +13; all 12 games use `leaderboard_elo` and none infer Elo from
  final-state scores.
- The session contains 279 Shadow decisions and 12,959 legal candidates. All
  279 submissions succeeded, all candidate sets are website-oracle exhaustive,
  and all decision-time information sets are consistent.
- Every submitted action came from frozen `tempo_baseline`; model-controlled
  actions and suggestion differences are zero.
- Failed games, non-bot actions, state encoding, team mapping, hand subset,
  local legality, oracle disagreement, materialization, website-rule, inferred
  acceptance, wildcard, information-set, duplicate-submit, extra error-log,
  and unrecoverable-desync counts are all zero.
- Runtime credential occurrences in the new logs, Shadow summary, cumulative
  assignment, global research results, and tracked files are zero.
- Frozen extension v3 and teacher v4 hashes are unchanged. No dataset rebuild,
  teacher rollout, teacher label, model training, offline evaluation, or
  model-controlled website play occurred in this stage.

Decision:

- Accept all 12 games as the next explicitly preassigned train supplement.
- Keep extension v3 and teacher v4 frozen until a separate dataset-extension
  stage builds and validates new v4 artifacts.
- Do not screen these states or train from them before the v4 physical
  partitions, manifest, and coverage gates pass.

## Model A / Shared Self-Play / BC / PPO / DMC

Status: not eligible for website control.

Observed pattern:

- Legality and physical action materialization were stabilized.
- Pure self-play, behavior cloning, balanced BC, PPO, safe PPO, corrective BC,
  rollout distillation, and early DMC/hybrid variants did not reliably exceed
  `tempo_baseline`.

Decision:

- Do not continue scaling these routes mechanically.
- Use findings as infrastructure and negative evidence.
- Focus current work on website-domain data and robust information-set labels.

## DMC Hybrid Override Experiments

Status: paused.

Evidence:

- Some whitelist/control-pass variants showed limited offline signals, but they
  are not website-domain verified.
- Offline override counts were too small or too unstable to justify website
  takeover.

Decision:

- Keep as analysis evidence only.
- Do not promote to website control.

## Current Next Experiment

Name: Frozen Website Dataset Extension v4.

Purpose:

- Add only the completed, preassigned Supplement v4 train session to frozen
  extension v3 and write separate v4 artifacts.
- Preserve every old game, source hash, assignment, split, and locked-test
  membership exactly.

Acceptance:

- All 12 new games and 279 decisions enter train; new development and
  locked-test games remain zero.
- All 82 extension v3 games, source hashes, assignments, splits, and the
  nine-game locked-test set remain unchanged.
- Coverage, physical isolation, information-set, duplicate-state, bot-table,
  Elo-source, and threshold gates pass.
- Teacher v4 remains frozen; website play, teacher rollout, training, offline
  evaluation, and model-controlled website play remain zero.
