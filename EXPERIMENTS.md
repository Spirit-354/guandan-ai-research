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

Status: pipeline smoke trained; Stage 6.1 continuation rejected at 0-20.

Accepted strong labels:

- Frozen v1 contributed 7 unchanged labels from 7 independent games.
- Extension v1 contributed 4 labels from 4 independent games:
  `13958:12`, `13959:7`, `13957:14`, and `13960:15`.
- Extension v2 contributed 2 labels from 2 independent games: `13992:16` and
  `14000:5`.
- Extension v3 contributed 3 labels from 3 independent games: `14022:16`,
  `14025:20`, and `14031:4`.
- Extension v4 contributed 3 labels from 3 independent games: `14038:12`,
  `14044:9`, and `14045:5`.
- Extension v5 contributed 3 labels from 3 independent games: `14058:22`,
  `14074:9`, and `14077:10`.
- Current teacher dataset: `website_information_set_teacher_dataset_v6.pth`.
- Current total: 22 labels from 22 independent games.
- State/action representation: 513/54.
- Teacher v6 SHA-256:
  `a74416e6facb28a1bc64563eba90cb33d460dc9e59cc2109518da142465e15f8`.

Rejected or exhausted evidence:

- Several old candidates had positive mean advantage but failed confidence,
  variance, or continuation-robustness gates.
- The old 50-game candidate pool is mostly exhausted.
- The extension v5 eligible pool is exhausted under the frozen gates.

Decision:

- Freeze teacher v6 and the teacher-preference checkpoint. The checkpoint
  passed engineering integrity but lost 0-20 against `tempo_baseline`; it is
  rejected from larger offline screens and remains unpromoted.
- Diagnose full-legal-set Q rankings on the 22 frozen teacher states before
  changing labels, loss, or training. No capability claim is allowed.

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

## Website Dataset Extension v4

Status: frozen; coverage gate passed.

Evidence:

- The extension v3 manifest content hash was verified as
  `51fe0244407d67e8267ea11b7146ff214f73823c29db92062189a58d033e5af9`
  before construction, and all five v3 artifact hashes remained unchanged.
- Extension v4 contains 94 accepted bot-only games, 55 wins, 39 losses, 2,340
  decisions, and 70,830 legal candidates; rejected files or games: 0.
- All 82 extension v3 games, their split assignments, all 14 old sessions, and
  every old source-file hash are unchanged. The nine-game locked-test set is
  exactly identical.
- New games 14035 through 14046 all entered train. New development and
  locked-test games: 0.
- All 2,061 old samples are unchanged after excluding the expected new split
  manifest hash field. All 279 new samples are train, bot-verified,
  `leaderboard_elo`, and information-set consistent.
- The physical train/development partition contains 1,469 decisions across 85
  games: 1,305 train and 164 development, with 58,733 legal candidates.
- Physical coverage includes 245 lead, 1,224 follow, 944 level-card, 406
  wildcard, 1,100 endgame, and 727 bomb-candidate decisions; all levels and
  first-player seats are represented across three Elo bands.
- Duplicate state count is zero. Coverage, information-set, physical-isolation,
  and threshold gates pass; capability evidence remains ineligible.
- The isolated locked-test partition contains the same nine games and 90
  consistent decisions, with zero training samples.
- Extension v4 manifest content hash:
  `368771a6a647d34d0d6fcd0490d7cdd1e57991a4c4188e3c127780a5323acbec`.
- Extension v4 artifact SHA-256 values:
  - bundle: `c8c05785defe37e589b99b3071b58c43d20ed1f1cf87fdb3c031a196151dcf87`;
  - train/development: `ad4da83e2af29c580a1b1d8fe70a06f88fc645525ab025945a7be48fd349fde1`;
  - locked-test: `cec1aba85cfbc388345d5ac17fd1ec48ec02642fb5743bed76513f872b7a512d`;
  - manifest file: `30d8103a156b84b3f1b26a78512b29757a3a603e925e15522752266f426bda04`;
  - data card: `fdfbe98a17e27e6c6cb20f5d85e6d17c6e775ee758b999aba5294b5a3f3fedee`.

Decision:

- Freeze extension v4 and use only its physical train/development partition in
  the next teacher-candidate stage.
- Keep the complete bundle and isolated locked-test partition out of screening,
  threshold selection, and label construction.
- Preserve teacher v4 as the frozen 16-label base; do not train during the next
  teacher expansion.

## Extension v4 Teacher Candidate Expansion

Status: completed; three new labels accepted and training gate remains closed.

Evidence:

- The only loaded dataset was
  `website_danzero_shadow_extension_v4.train_dev.pth`, whose SHA-256 remained
  `ad4da83e2af29c580a1b1d8fe70a06f88fc645525ab025945a7be48fd349fde1`;
  complete-bundle and locked-test loads were zero.
- All 279 decisions from the 12 new train games were enumerated. 252 were
  rollout eligible; 27 were excluded because at least one public hand count was
  nonpositive. Per-game eligibility and rejection counts were recorded.
- Greedy-only screening covered all 252 eligible states, 782 candidate actions,
  and 6,256/6,256 rollouts. It emitted zero strong labels and was used only to
  choose confirmation cases.
- Eight positive-lower-bound, low-variance screen signals covered six games.
  Confirmation evaluated the strongest state from every game: six cases, 24
  candidates, and 384/384 rollouts split evenly between greedy and frozen-tempo
  continuations.
- Every rollout used uniform physical assignment conditioned on public counts,
  stable game/turn/determinization seeds, and shared determinizations. Timeouts,
  incomplete cases, integrity failures, hidden-hand access, future-information
  access, and locked-test access were all zero.
- `14038:12` passed with advantage 1.125, 95% lower bound 0.623, candidate
  variance 0.0, and greedy/frozen-tempo advantages 1.0/1.25.
- `14044:9` passed with advantage 0.75, 95% lower bound 0.143, candidate
  variance 0.467, and greedy/frozen-tempo advantages 1.25/0.25.
- `14045:5` passed with advantage 0.625, 95% lower bound 0.156, candidate
  variance 0.0, and greedy/frozen-tempo advantages 1.0/0.25.
- `14036:4` failed variance, confidence, and frozen-tempo robustness;
  `14042:9` exceeded candidate variance 0.50; `14043:8` failed confidence and
  frozen-tempo robustness. None of these games retained another permitted
  positive-screen alternative.
- Teacher v5 preserves all 16 teacher v4 samples exactly after deserialization
  and appends only the three accepted labels. All source-state,
  behavior-action, legal-action, 513/54 dimension, and physical-card remap
  checks passed. Teacher v4 remained unchanged.

Decision:

- Freeze `website_information_set_teacher_dataset_v5.pth` at 19 labels from 19
  independent games; its SHA-256 is
  `155fc348e939490bc036b2b5e3e0993be732b259250cac3d0244e888910fb9da`.
- Keep the 20-game training gate closed; do not train, evaluate, or promote a
  model from this artifact.
- Treat the extension v4 candidate pool as exhausted and collect another
  explicitly preassigned baseline-only train supplement without weakening any
  teacher threshold.

## Website Shadow Supplement v5

Status: completed; baseline-only collection gate passed.

Evidence:

- The cumulative v5 assignment preserves all five prior assignments and adds
  only `logs_website_shadow_supplement_train_005: train`; no locked-test
  assignment changed.
- Exactly 12 verified bot-table games completed: 9 wins and 3 losses across
  game IDs `14058`, `14059`, `14061`, `14063`, `14064`, `14066`, `14068`,
  `14070`, `14072`, `14074`, `14077`, and `14081`.
- Frozen `tempo_baseline` submitted all 345 actions successfully. All decisions
  retained exhaustive website-oracle candidate sets containing 11,587 total
  candidates and consistent decision-time information sets.
- Model-controlled and suggestion-different actions were zero. State encoding,
  team mapping, hand subset, local legality, oracle agreement,
  materialization, website-rule, wildcard, information-set, communication,
  duplicate-submit, and unrecoverable-desync errors were zero.
- All 12 games used `leaderboard_elo`; the continuous series moved from 2121
  to 2168, a net change of +47. Final-state scores were not used as Elo.
- Frozen extension v4 and teacher v5 remained unchanged. No dataset build,
  teacher rollout or label creation, model training, offline evaluation, or
  model-controlled website play occurred.

Decision:

- Freeze Supplement v5 as the sole new source session for extension v5.
- Build the next dataset from the frozen extension v4 manifest and cumulative
  v5 assignment before screening any of the new decisions.

## Website Dataset Extension v5

Status: frozen; coverage gate passed.

Evidence:

- The extension v4 manifest content hash and all five v4 artifact hashes were
  verified before construction. Teacher v5 also remained unchanged.
- Extension v5 contains 106 accepted bot-only games, 64 wins, 42 losses, 2,685
  decisions, and 82,417 legal candidates; rejected files or games: 0.
- All 94 extension v4 games, all prior source hashes, 15 old session
  assignments, old split memberships, and the exact nine-game locked-test set
  are unchanged.
- Games `14058`, `14059`, `14061`, `14063`, `14064`, `14066`, `14068`,
  `14070`, `14072`, `14074`, `14077`, and `14081` all entered train. New
  development and locked-test games: 0.
- All 2,340 old samples are unchanged after excluding the expected new split
  manifest hash field. All 345 new samples are train, bot-verified,
  `leaderboard_elo`, physically valid, and information-set consistent, with
  11,587 legal candidates.
- The physical train/development partition contains 1,814 decisions across 97
  games: 1,650 train and 164 development, with 70,320 candidates.
- Physical coverage includes 306 lead, 1,508 follow, 1,118 level-card, 467
  wildcard, 1,371 endgame, and 872 bomb-candidate decisions. All 13 levels and
  all four first-player seats remain represented across three Elo bands.
- Duplicate state count is zero. Coverage, information-set rollout,
  physical-isolation, and threshold gates pass; capability evidence remains
  ineligible.
- The physical locked-test partition remains exactly nine games and 90
  consistent samples, with zero training samples.
- Extension v5 manifest content hash:
  `a2931c6078487662d25f115896034311354eade265bec8b72f94ea2d5a7bdaf7`.
- Extension v5 artifact SHA-256 values:
  - bundle: `c013fe4cc89ef872c246a81ee37f8f6711da85bcf724238c570e703b942f9ee2`;
  - train/development: `e5e220c3c770116ca9d01478e98e610dd6309a0f3d6c17088a8328f62b47174b`;
  - locked-test: `3b2e7f1386fc73449178a01631c866a5045f19f9fa3de267794b53a9b9a8fe6c`;
  - manifest file: `aa417661b7363b13e4a11c34970559339f6a717cb3eb9404c56b1163cc83dc0b`;
  - data card: `9160f0b1889d8a85899fb3f706da6df78f0ab28c4644c5e2049ad5720346d739`.

Decision:

- Freeze extension v5 and permit the next stage to load only its physical
  train/development partition for new-game teacher screening.
- Keep the complete bundle and locked-test partition out of screening,
  threshold selection, and label construction.
- Preserve teacher v5 as the frozen 19-label base and do not train during the
  next teacher expansion even if the 20-game gate is reached.

## Extension v5 Teacher Candidate Expansion

Status: completed; three new labels accepted and the 20-game gate passed.

Evidence:

- The only loaded dataset was
  `website_danzero_shadow_extension_v5.train_dev.pth`, whose SHA-256 remained
  `e5e220c3c770116ca9d01478e98e610dd6309a0f3d6c17088a8328f62b47174b`;
  complete-bundle and locked-test loads were zero.
- All 345 decisions from the 12 new train games were enumerated. Per-game
  total/eligible/ineligible counts were: `14058` 38/38/0, `14059` 19/19/0,
  `14061` 28/28/0, `14063` 16/16/0, `14064` 29/21/8, `14066` 49/21/28,
  `14068` 26/17/9, `14070` 27/22/5, `14072` 31/22/9, `14074` 18/17/1,
  `14077` 31/29/2, and `14081` 33/27/6. All 68 exclusions were caused only
  by a nonpositive public hand count.
- Greedy-only screening covered all 277 eligible states, 843 candidate
  actions, and 6,744/6,744 rollouts. It emitted zero strong labels and was
  used only to choose confirmation cases.
- Six positive-lower-bound, low-variance screen signals covered five games.
  Confirmation evaluated one strongest state per game: five cases, 20
  candidates, and 320/320 rollouts split evenly between greedy and
  frozen-tempo continuations.
- Every rollout used uniform physical assignment conditioned on public counts,
  stable game/turn/determinization seeds, and shared complete
  determinizations. Timeouts, incomplete cases, integrity failures,
  hidden-hand access, future-information access, and locked-test access were
  all zero.
- `14058:22` passed with advantage 0.50, 95% lower bound 0.0617, candidate
  variance 0.0, and greedy/frozen-tempo advantages 0.75/0.25.
- `14074:9` passed with advantage 1.00, 95% lower bound 0.4939, candidate
  variance 0.0, and greedy/frozen-tempo advantages 1.00/1.00.
- `14077:10` passed with advantage 0.50, 95% lower bound 0.0617, candidate
  variance 0.0, and greedy/frozen-tempo advantages 0.75/0.25.
- `14064:1` failed confidence, variance, and frozen-tempo robustness;
  `14070:1` failed variance and frozen-tempo robustness. Neither game retained
  another permitted positive-screen alternative. The same-game alternative
  `14074:10` was not run because the stronger `14074:9` passed.
- Teacher v6 preserves all 19 teacher v5 samples exactly after deserialization
  and appends only the three accepted labels. Source-state, behavior-action,
  legal-action, 513/54 dimension, and physical-card remap errors were zero.

Decision:

- Freeze `website_information_set_teacher_dataset_v6.pth` at 22 labels from 22
  independent games; its SHA-256 is
  `a74416e6facb28a1bc64563eba90cb33d460dc9e59cc2109518da142465e15f8`.
- The 20-game label-count gate passes. No model was trained, no offline
  capability evaluation ran, and no capability or checkpoint-promotion claim
  is allowed from this stage.
- Treat the extension v5 candidate pool as exhausted. The next stage is only a
  frozen, deterministic teacher-preference training-pipeline smoke with
  complete-game grouping; Arena and website play remain out of scope.

## Frozen Teacher-Preference Training Smoke

Status: completed; deterministic pipeline gate passed without capability
validation.

Evidence:

- The only training-label input was frozen
  `website_information_set_teacher_dataset_v6.pth`, SHA-256
  `a74416e6facb28a1bc64563eba90cb33d460dc9e59cc2109518da142465e15f8`.
  All 22 labels from 22 independent games passed train-only, 513-state,
  54-action, finite-vector, legal-action, differing-pair, preference-target,
  source-partition, and locked-test checks.
- Games were sorted by
  `sha256("website_teacher_v6_split_v1:" + game_id)`. The first four games
  (`13992`, `14074`, `13868`, and `13871`) form the internal pipeline
  development split; the remaining 18 form pipeline train. Overlap and dropped
  games are zero.
- The split manifest is `website_teacher_preference_split_v1.json`, SHA-256
  `5a15e514dc9bc51d77d300837151d9f1a49250f42885cc7940725bcbe4d35107`.
- The curated training report SHA-256 is
  `896192b1d0b4de2caabe20ac17d6a20766fc7f89d6e82a981d834b777932ddd3`.
- The existing `danzero_dmc.build_q_model` ran on CPU with seed `20260714`, 20
  epochs, batch size 6, learning rate 0.001, no initialization checkpoint, and
  only `softplus(Q_behavior-Q_teacher)`. Hyperparameter searches and checkpoint
  selections were zero.
- Final pipeline-train ranking accuracy was 1.00 with mean margin 20.7220.
  Internal pipeline-development ranking accuracy was 0.75 with mean margin
  12.3318 and pairwise loss 3.3015. These values are pipeline diagnostics only,
  not capability evidence.
- The ignored final checkpoint SHA-256 is
  `c54801a9db05100c2fe5a9bf610a64fc7c94dc2cd947dfaab115ff827bd90919`.
  A new-process reload exactly reproduced both partition metrics and prediction
  digests. A temporary full rerun exactly reproduced the split, recipe,
  history, metrics, and prediction digests.
- Complete-bundle and locked-test loads, extra targets, Arena evaluations,
  website Shadow, website games, model-controlled website actions, checkpoint
  promotion, and capability claims were all zero.

Decision:

- Freeze the split, report, and checkpoint hashes. Keep
  `capability_claim_allowed=false` and `checkpoint_promotion_allowed=false`.
- Permit only a 20-game paired, seat-swapped offline Arena integrity smoke
  against frozen `tempo_baseline`. Do not run the 100/200-game screen in the
  same stage regardless of result.

## Stage 6.1 Teacher-Preference Offline Arena Smoke

Status: integrity passed; early-screen continuation rejected.

Evidence:

- The candidate checkpoint, teacher v6, split, training report, and baseline
  manifest hashes all matched their frozen values before execution. Frozen
  baseline verification passed with 500 equivalence samples and zero
  mismatches.
- `danzero_dmc.load_q_checkpoint` now accepts the frozen
  `website_teacher_preference_checkpoint_v1` only when schema, 513/54
  dimensions, teacher hash, training mode, capability flag, and promotion flag
  match. Legacy distributed-DMC checkpoint loading remains unchanged.
- The only formal Arena run completed exactly 20 games as ten adjacent paired
  seeds. Each pair shared deal, first-player, and per-game Arena RNG seeds and
  assigned the model once to team 0 and once to team 1.
- All 20 games completed. The model lost every game: model/baseline wins 0/20,
  model win rate 0.0, so the frozen 0.30 continuation rule evaluates false.
- The model made 964 decisions with pass rate 0.6629 and bomb rate 0.0239;
  `tempo_baseline` made 873 decisions. Average game length was 91.85.
- Illegal-action, fallback, materialization, hand-card-mismatch,
  fatal-no-candidate, per-game safety, and baseline-equivalence mismatch counts
  were all zero. The engineering integrity gate passed.
- Training, hyperparameter search, checkpoint selection, locked-test or
  website-dataset loading, larger Arena runs, website Shadow/play,
  model-controlled website actions, checkpoint promotion, and capability
  claims were all zero.
- Curated Arena evidence:
  `website_teacher_preference_arena_smoke20_v1.json`, SHA-256
  `aa45da9de202194102fe8d11e612ad3eb4b51177fd910b9a7948836afd2a1fe6`.

Decision:

- Reject this checkpoint from the 100/200-game offline screen. Do not promote,
  deploy, or use it as evidence of website capability.
- Run only a static full-legal-set Q-ranking diagnosis on the 22 frozen teacher
  states before proposing a corrective objective. Do not retrain in that
  diagnosis stage.

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

Name: Stage 6.2 Frozen Teacher-Preference Failure Diagnosis.

Purpose:

- Evaluate the frozen checkpoint on every recorded legal action of all 22
  teacher states without training or gameplay.
- Quantify teacher/behavior rank, top-1 source, unpaired-action domination, and
  pass-top1 behavior by frozen pipeline partition.

Acceptance:

- All 22 states and all recorded legal actions are scored exactly once with
  finite Q values and stable tie handling.
- Teacher/behavior pairwise ordering reproduces the frozen training report,
  while full-set ranks and top-1 categories are reported separately.
- No dataset, locked test, Arena, training, tuning, website access, promotion,
  or capability claim occurs.
