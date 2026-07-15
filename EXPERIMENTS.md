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

Status: Stage 6.1 continuation rejected at 0-20; Stage 6.4 confirmed six
train-only teacher-versus-top1 constraints and Stage 6.6 completed one fixed
corrective pipeline smoke. Stage 6.7 found 11/22 teacher top-1 states, and
Stage 6.8 found no direct frozen support for the eight residual train
orderings. Stage 6.9 confirmed four additional teacher-over-residual train
comparisons, with four inconclusive and no reverse support. Stage 6.10 froze a
32-pair residual corrective dataset, and Stage 6.11 completed one fixed
from-scratch pipeline smoke on its 28 train pairs. Stage 6.12 raised frozen
teacher full-set top-1 coverage to 13/22, leaving six train and three held-out
development residual states. Stage 6.13 found no supported ordering for any
current train top-1 and isolated three actions that still lack a direct paired
comparison. Stage 6.14 then requested the frozen three-case confirmation but
completed only 90/96 rollouts because `13872:4` timed out with six candidate
failures. Stage 6.14R derived the exact failure path without a new rollout and
froze a process-isolation equivalence stage. Stage 6.14P then proved exact
synthetic sequential/process equivalence and authorized one formal parallel
confirmation. Stage 6.14E completed 96/96 and confirmed two teacher-over-
current-top1 comparisons while one remained inconclusive. Stage 6.15 then
preserved all 32 v2 pairs and froze a 34-pair v3 dataset containing only those
two supported additions. Stage 6.16 completed one fixed from-scratch smoke on
its 30 train pairs with exact independent checkpoint reload; no capability
evidence exists.

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

## Stage 6.2 Frozen Teacher-Preference Failure Diagnosis

Status: completed; objective-coverage pattern identified without causal or
capability claims.

Evidence:

- All five frozen checkpoint, teacher, split, training-report, and 0-20 Arena
  hashes matched before and after the run. The checkpoint remained rejected
  from the 100/200-game screen.
- All 22 unique teacher states and all 934 recorded legal-action entries were
  scored exactly once. Pipeline train/development contained 18/4 states and
  889/45 actions, with zero overlap or unknown games.
- Eight source entries duplicate another recorded action vector; they were
  preserved in recorded order and scored separately. Dropped, repeated-score,
  reconstructed, dimension-invalid, illegal-recorded, and nonfinite-Q counts
  were zero.
- Pipeline-train pairwise loss, accuracy, mean margin, and prediction digest
  exactly reproduced at `0.0000722892`, `1.00`, `20.7220`, and
  `951b51bc3000686ecc35260813b8f191246e0df25cd66c2b2b80cbd78b5810cc`.
- Pipeline-development values exactly reproduced at `3.3015`, `0.75`,
  `12.3318`, and
  `2a453f34104e5e052e469127ae473fb4cf89c8d71ee35e6bebe12b08cc377fe7`.
- Overall teacher-over-behavior ordering was 21/22, while teacher was full-set
  top-1 in only 10/22 states. Behavior was top-1 in 0/22 and another recorded
  action was top-1 in 12/22.
- An unpaired action strictly outranked teacher in those same 12 states, with
  161 such action entries overall. Mean teacher rank was 8.36 and median rank
  was 2.0.
- Pass was top-1 in 0/22 teacher states. This diagnostic therefore does not
  directly explain the Stage 6.1 model pass rate of 66.3%.
- Independent audit recomputed every per-state rank, tie, first-maximum source,
  action-order digest, aggregate, pairwise metric, and prediction digest with
  zero errors. All forbidden operation counts were zero.
- Curated diagnostic evidence:
  `website_teacher_preference_failure_diagnosis_v1.json`, SHA-256
  `da08516c39986a01349533e160ba0e97a566d7fad6e42b0b7b3ce41df835b0b2`.

Decision:

- Treat pairwise supervision coverage as a supported failure pattern, not a
  causal proof: the frozen objective constrains teacher versus behavior but
  supplies no automatic ordering for the remaining recorded legal actions.
- Do not assume the teacher is superior to the 12 unpaired top actions. Audit
  their existing frozen counterfactual evidence before defining a corrective
  loss or running any new rollout.
- Keep the checkpoint rejected and unpromoted. Do not run another Arena,
  training job, website Shadow, or website game in the next audit stage.

## Stage 6.3 Frozen Unpaired-Action Evidence Audit

Status: completed; existing frozen evidence does not support a
teacher-versus-all objective.

Evidence:

- The Stage 6.2 diagnosis, teacher v6, frozen 18/4 split, training report,
  rejected checkpoint, and Stage 6.1 0-20 Arena evidence all retained their
  frozen hashes. The audit read only the ten rollout-evidence files referenced
  directly by the 12 target teacher samples and recorded every file hash.
- All 12 first-maximum unpaired targets reproduced in original action order:
  nine pipeline-train and three pipeline-development states. Missing,
  duplicate, extra, reconstructed, and ambiguous state/action mappings were
  zero.
- Pipeline train contained two dual-continuation-confirmed actions and seven
  actions present without a qualifying comparison. Pipeline development
  contained two and one respectively; overall counts were 4/12 and 8/12.
  Greedy-only, absent, and ambiguous classifications were all zero.
- The four dual-continuation cases had complete 16-rollout results for both the
  teacher and model top-1 under the frozen greedy/tempo ensemble, but the
  source labels recorded confidence for teacher versus behavior, not teacher
  versus model top-1. None contained top1-specific lower-bound, confidence, and
  continuation-profile advantage fields.
- The other eight top-1 actions were exactly present in the frozen 54D legal
  action list and physical-card metadata but were not evaluated as candidates
  in their source rollout case.
- Teacher-versus-top1 ordering is therefore supported for 0/12 states. A
  12-case future counterfactual manifest records eight missing-candidate and
  four missing-paired-confidence reasons; it was not executed.
- Independent recomputation matched all state/action hashes, ten source-file
  hashes, mappings, classifications, 9/3 partition counts, aggregates, and
  zero forbidden operations.
- Curated output:
  `website_teacher_preference_unpaired_evidence_audit_v1.json`, SHA-256
  `09f52df90d095ab6b3777a046c50901f96fbeb15e6ef5f613343a13be1249383`.

Decision:

- Do not define or train a teacher-versus-all objective from this evidence.
- If counterfactual confirmation proceeds, restrict objective-design evidence
  to the nine pipeline-train cases. Keep the three pipeline-development cases
  held out from candidate-rule, threshold, and objective design.
- Keep the checkpoint rejected and unpromoted. Do not run Arena or access the
  website in the next confirmation stage.

## Stage 6.4 Frozen Pipeline-Train Unpaired Counterfactual Confirmation

Status: completed; six train-only corrective comparisons passed the frozen
strong-teacher gates, without training or capability claims.

Evidence:

- All seven primary frozen hashes and the physical train/development source
  dataset hash remained unchanged. The source partition contained no
  locked-test samples, and every evaluated source sample had `split=train`.
- Exactly the nine Stage 6.3 pipeline-train manifest states reproduced by
  game/turn key, original action order, teacher/top1 index, 54D action hash,
  and physical-card identity. Missing, duplicate, extra, reconstructed,
  substituted, and ambiguous mappings were zero.
- Each case evaluated exactly teacher and model top1 with 16 rollouts per
  action: eight greedy and eight frozen-tempo continuations over eight shared
  information-set determinizations. Total completion was 288/288, with 144
  rollouts per profile.
- Six comparisons passed every unchanged gate:
  `13879:6` (advantage 0.875, lower bound 0.3729),
  `13861:10` (0.50, 0.0617), `13957:14` (0.625, 0.1559),
  `13960:15` (1.00, 0.4939), `13959:7` (1.00, 0.3802), and
  `14022:16` (1.25, 0.76). Both continuation-profile advantages were at
  least 0.15 in every accepted comparison.
- Three comparisons were inconclusive: `14077:10` failed the positive lower
  bound and frozen-tempo advantage gates; `13882:10` failed the positive lower
  bound and frozen-tempo advantage gates; `14025:20` had zero advantage and
  failed advantage, lower-bound, and both-profile robustness. No comparison
  supported top1 over teacher under the symmetric frozen gates.
- Pipeline-development targets `13992:16`, `14074:9`, and `13871:9` had zero
  case executions and zero rollouts. Locked-test loads, timeouts, candidate
  failures, hidden/future information use, and integrity failures were zero.
- Independent audit recomputed every input/action hash, determinization seed,
  paired return, mean, variance, 95% lower bound, confidence, per-profile
  advantage, direction, and aggregate exactly.
- Curated output:
  `website_teacher_preference_unpaired_train_confirmation_v1.json`, SHA-256
  `8e17377b5a1523d9f0a47af7218d687e062a3ade671c57f387eb4c1a0888cfae`.

Decision:

- Permit only the six supported pipeline-train comparisons to become new
  corrective preference pairs. Exclude all three inconclusive train cases and
  all pipeline-development unpaired cases.
- Preserve the original 22 teacher-versus-behavior pairs and frozen 18/4 game
  split. Construct and audit a state-balanced corrective dataset before any
  training.
- Keep the checkpoint rejected and unpromoted. Do not run another rollout,
  train, run Arena, or access the website in the next dataset stage.

## Stage 6.5 Frozen Corrective Preference Dataset Construction

Status: completed; state-balanced 28-pair pipeline dataset frozen without
training.

Evidence:

- All seven frozen input hashes remained unchanged. The formal builder ran
  once and invoked no rollout, training, tuning, checkpoint, Arena, or website
  path.
- The new `.pth` embeds all 22 teacher v6 samples unchanged. Independent reload
  matched the complete sample list, all 22 per-sample canonical hashes, and the
  aggregate canonical hash exactly.
- All 22 original teacher-versus-behavior pairs remain. Exactly six
  `teacher_action_beats_model_top1` pairs were added for `13879:6`,
  `13861:10`, `13957:14`, `13960:15`, `13959:7`, and `14022:16`, with exact
  Stage 6.4 action indices, 54D hashes, physical identities, and metrics.
- Final counts are 28 pairs: 24 pipeline train across 18 games and four
  pipeline development across four games. Split overlap and dropped base
  samples are zero.
- Inconclusive train cases `14077:10`, `13882:10`, and `14025:20` were
  recorded as exclusions and added zero pairs. The three development unpaired
  cases were recorded only as held-out keys; their actions were not inspected
  and they added zero pairs.
- For each state, pair weights sum exactly to one. The six two-negative states
  assign 0.5 to behavior and 0.5 to top1; all other states assign 1.0 to their
  sole behavior pair. Partition-normalized weights sum to 1.0 for train and
  1.0 for development.
- The frozen objective is state-balanced pairwise
  `softplus(Q_rejected-Q_preferred)`. It was not executed, weights were not
  tuned, capability eligibility is false, and checkpoint promotion is false.
- Dataset SHA-256:
  `fad7ae18fea8b02cbc88ad4a8a7f8ecee298abe436ef589f5c88d66e42a32707`;
  manifest SHA-256:
  `0a5dc4f60091338b65f86f83ad30ae55dc18c058ee8b07535a314510ad96ef0a`.

Decision:

- Freeze the dataset and manifest. Permit one fixed, from-scratch corrective
  training smoke using only the 24 train pairs and state-balanced objective.
- Keep the four development pairs evaluation-only. Do not use them for
  training, hyperparameter selection, checkpoint selection, or objective
  design.
- Keep the old checkpoint rejected. Do not run Arena or access the website in
  the corrective training stage.

## Stage 6.6 Frozen Corrective Training Smoke

Status: completed; deterministic pipeline smoke passed without capability
validation.

Evidence:

- All seven frozen input hashes remained unchanged. Reload validation exactly
  reproduced all 28 pairs, the 24/4 train/development split, 18/4 state split,
  all 22 base samples, all six corrective pairs, and zero excluded-pair
  leakage.
- Exactly one from-scratch CPU run used seed `20260714`, 20 epochs, six states
  per batch, learning rate `0.001`, no initialization checkpoint, and the
  frozen state-balanced pairwise softplus objective. It completed 60 optimizer
  steps using only the 18 train states/24 pairs; development training uses and
  extra targets were zero.
- Final train state-balanced loss was `0.0003623383`. Aggregate, base, and
  corrective train pair accuracies were all `1.0`, with mean margins
  `18.9867`, `19.8011`, and `16.5434` respectively.
- Final development state-balanced loss was `0.0000023221`, pair accuracy was
  `1.0`, and mean margin was `26.5879`. These are pipeline diagnostics only and
  were not used for tuning or checkpoint selection.
- Nonfinite training losses and predictions were zero. The checkpoint records
  all frozen hashes, the fixed 513/54 recipe, and false promotion/capability
  flags. A separate process independently reloaded it and exactly reproduced
  every train/development, base/corrective metric and prediction digest.
- Rollout, hyperparameter search, checkpoint selection, locked-test or website
  dataset load, Arena, website Shadow/play, model control, promotion, and
  capability claims were all zero.
- Curated report:
  `website_teacher_preference_corrective_training_v1.json`, SHA-256
  `baa97ccf71c237895a92f4cb8b36b9559cf3cabe45b4901b7481d9f50f4c0830`.
  Ignored checkpoint SHA-256:
  `8cb368c8c0ae3f8c41c577e055ddd4796cbaae8163720cc630a435aa25bc1a49`.

Decision:

- Keep the corrective checkpoint pipeline-only, unpromoted, and ineligible for
  capability claims despite perfect pair accuracy.
- Before any Arena, run only a frozen static full-legal-set ranking diagnosis
  across the same 22 teacher states. Do not train, tune, change the checkpoint,
  or access the website in that diagnosis stage.

## Stage 6.7 Frozen Corrective Full-Legal-Set Diagnosis

Status: completed; six intended orderings were corrected, but residual full-set
coverage remains insufficient for Arena or capability claims.

Evidence:

- All ten directly validated frozen hashes remained unchanged. The Stage 6.6
  report still records exactly one training run, zero development training
  uses, an exact reload, and false promotion/capability flags.
- The formal full-set path scored exactly 22 frozen states and all 934 recorded
  legal-action entries: 889 train and 45 development. All eight duplicate
  vectors were retained in original positions. Dropped, reconstructed,
  repeated-score, invalid-dimension, illegal-recorded, and nonfinite-Q counts
  were zero.
- Exact Stage 6.6 metric/digest reproduction required the frozen 24/18/6/4 pair
  batch shapes because the six corrective values have last-bit batch-shape
  differences in the 865-action full-set other batch. This replay was separately
  accounted as 52 pair/104 action-value evaluations and was excluded from the
  934-entry full-set scoring count.
- Train teacher/behavior/other first-max top-1 counts were 10/0/8; development
  counts were 1/0/3; overall counts were 11/0/11. Pass top-1 remained 0/22.
- Overall mean/median teacher rank improved from 8.36/2.0 to 2.27/1.5. States
  with an action strictly above teacher fell from 12 to 11, and the number of
  such action entries fell from 161 to 28. These are static ranking changes,
  not causal or capability evidence.
- Teacher outranked all six Stage 6.4 rejected top1 actions with margins from
  9.26 to 22.58, and none of those rejected actions remained new top-1.
  Teacher was first-max full-set top-1 in only three of those six states;
  residual other actions remained above teacher in the other three.
- A separate process independently reproduced every ranking, tie, action-order
  digest, aggregate, Stage 6.6 metric/prediction digest, and corrective mapping.
  All forbidden operation counts were zero.
- Curated output:
  `website_teacher_preference_corrective_failure_diagnosis_v1.json`, SHA-256
  `2b4359470e74f5eae28d6589477aca5f929ae6b5b88e094fa86209bf4328163d`.

Decision:

- Do not run Arena, promote the checkpoint, or claim capability. Perfect pair
  fit did not produce teacher full-set top-1 in half of the frozen states.
- Audit existing frozen evidence only for the eight residual pipeline-train
  top1 actions before proposing any further corrective objective or rollout.
  Keep the three residual development cases held out from design.

## Stage 6.8 Frozen Corrective Residual-Top1 Evidence Audit

Status: completed; all eight train residual comparisons lack sufficient direct
frozen evidence, with development isolation preserved.

Evidence:

- All nine frozen input hashes remained unchanged. The audit reproduced the
  Stage 6.7 conclusion without model scoring: 22 states, 934 full-set action
  scores, 11/0/11 teacher/behavior/other first-max top-1 counts, zero pass
  top-1, and exact Stage 6.6 metrics plus all prediction digests.
- Exactly 11 residual targets reproduced by game/turn key, frozen partition,
  original action index/order, 54D action hash, and teacher rank. Counts were
  eight pipeline train and three pipeline development; missing, duplicate,
  extra, reconstructed, substituted, and ambiguous mappings were zero.
- The audit opened only the six rollout files directly referenced by the eight
  train teacher samples and recorded every file hash. All eight actions mapped
  exactly to the frozen legal-action order and physical-card metadata.
- Five residual actions were present in the source legal-action list but were
  not evaluated as candidates. Three actions had complete teacher and residual
  candidate summaries, but no direct teacher-versus-residual paired advantage,
  positive 95% lower bound/confidence, or both continuation-profile advantages.
- Direct supported teacher-over-residual or residual-over-teacher orderings
  were both 0/8. All eight train cases therefore remain insufficient and enter
  only a non-executed future confirmation manifest; unsupported labels are zero.
- Development targets `13992:16`, `14074:9`, and `13871:9` contain identity
  fields only. Their source-reference exposure, target evidence queries,
  candidate inspection, threshold-design use, and objective-design use were
  all zero.
- Independent recomputation matched every target identity, source hash, action
  mapping, classification, partition count, aggregate, and forbidden-operation
  counter. Rollout, training, tuning, checkpoint changes, locked-test or
  website-dataset loads, Arena, website activity, promotion, and capability
  claims were zero.
- Curated artifact:
  `website_teacher_preference_corrective_residual_evidence_audit_v1.json`,
  SHA-256
  `676232033f07051670b4407f15aca9f3939d9754ac2dcf4d078957263a1e2a6b`.

Decision:

- Do not define or train another corrective objective from the existing
  evidence, and do not run Arena or promote the corrective checkpoint.
- If confirmation proceeds, execute only the eight frozen pipeline-train
  manifest cases under the unchanged paired information-set rollout and strong
  gates. Keep all three development targets unexecuted and held out.

## Stage 6.9 Frozen Pipeline-Train Residual Counterfactual Confirmation

Status: completed; four train-only teacher-over-residual comparisons passed the
frozen gates, without dataset construction, training, or capability claims.

Evidence:

- All eight frozen hashes, including the old and corrective checkpoints,
  remained unchanged. Exactly the eight Stage 6.8 train manifest cases mapped
  to unique physical `train` samples by state, action order, teacher/residual
  indices, 54D hashes, and physical-card identities.
- Every case executed exactly the teacher and residual action with 16 rollouts
  per action: eight greedy and eight frozen-tempo continuations over eight
  determinizations shared by both actions and profiles. All 256/256 rollouts
  completed, split 128/128 by continuation profile.
- Four comparisons passed every unchanged teacher-direction gate:
  `14044:9` (advantage 0.625, lower bound 0.1559, greedy/tempo 1.0/0.25),
  `14038:12` (0.75, 0.26, 0.25/1.25), `14000:5` (0.50, 0.0617,
  0.75/0.25), and `14022:16` (0.75, 0.26, 0.75/0.75).
- `13957:14` and `14077:10` failed positive confidence and one profile gate;
  `13959:7` had negative mean teacher advantage; `14025:20` had zero
  advantage. These four were inconclusive. Residual-over-teacher supported
  comparisons were zero.
- Development targets `13992:16`, `14074:9`, and `13871:9` had zero source
  mappings, executions, and rollouts. Timeouts, candidate failures,
  hidden/future information use, integrity failures, and locked-test loads were
  zero.
- A separate process reproduced every input/action hash, determinization seed,
  paired return, mean, variance, both directional confidence bounds, both
  profile advantages, classification, partition count, aggregate, and
  forbidden-operation counter.
- No dataset or objective was constructed. Training, fine-tuning, threshold
  tuning, checkpoint selection/modification, Arena, website activity,
  promotion, capability claims, and unsupported labels were zero.
- Curated artifact:
  `website_teacher_preference_corrective_residual_train_confirmation_v1.json`,
  SHA-256
  `352cd0dfe0a4c958ba0555b776326a2b58470a980aef461ed49d4c59a7474c7a`.

Decision:

- Permit only the four supported train comparisons to enter a separate frozen
  corrective dataset extension. Exclude all four inconclusive cases and all
  three development residual cases.
- Preserve the existing 28 pairs and 22 states, then recompute state-balanced
  weights after adding only those four pairs. Do not train, run another
  rollout, run Arena, or access the website in the dataset stage.

## Stage 6.10 Frozen Residual Corrective Dataset Extension

Status: completed; 32-pair state-balanced dataset frozen without training.

Evidence:

- All seven frozen inputs retained their expected hashes. The formal builder
  wrote the dataset and manifest once and executed no rollout, training,
  tuning, checkpoint, Arena, locked-test, website-dataset, or website path.
- All 22 embedded teacher samples preserved their exact per-sample and
  aggregate canonical hashes. All 28 v1 pairs preserved their ID, action,
  action-hash, physical identity, pair type, partition, and provenance fields;
  only deterministic weight fields changed.
- Exactly four `teacher_action_beats_residual_top1` train pairs were added for
  `14044:9`, `14038:12`, `14000:5`, and `14022:16`, with exact Stage 6.9
  indices, 54D hashes, physical identities, metrics, and empty teacher failure
  lists.
- Final counts are 32 pairs across the same 22 states: 28 train and four
  development, comprising 22 base, six Stage 6.4 corrective, and four Stage
  6.9 residual pairs. The four inconclusive train cases and three identity-only
  development targets added zero pairs.
- State pair-count distribution is 13 single, eight double, and one triple.
  Double states use 0.5/0.5; `14022:16` uses three equal one-third weights;
  all state sums and train/development normalized sums equal one.
- A separate process reconstructed the entire payload and manifest and matched
  hashes, v1 semantics, additions, seven exclusions/held-out keys, counts,
  weights, provenance, and all zero forbidden-operation counters.
- Dataset SHA-256:
  `40024f7c064f0ebb7999c4ac0f7bc85d77b759a23956cbe596756763d4009d4d`.
  Manifest SHA-256:
  `ce5141f6254218d9230b15117a88d3c5e6bd374839bcf5fc77b393e2599ec353`.

Decision:

- Freeze corrective dataset v2 and its manifest. The unchanged state-balanced
  pairwise softplus objective remains unexecuted, and promotion/capability
  eligibility remains false.
- Permit one separate fixed, from-scratch CPU training smoke using only the 18
  train states and 28 train pairs. Keep all four development pairs
  evaluation-only and do not tune or select a checkpoint.
- Do not run Arena, full-legal-set diagnosis, website Shadow, or website play in
  that training stage.

## Stage 6.11 Frozen Residual Corrective Training Smoke

Status: completed; deterministic pipeline smoke passed without capability
validation.

Evidence:

- All eight frozen inputs and all Stage 6.10 sample, preserved-pair,
  residual-pair, weight, split, exclusion, and provenance invariants reproduced
  exactly before and after training.
- Exactly one from-scratch CPU run used seed `20260714`, 20 epochs, six states
  per batch, learning rate `0.001`, no initialization checkpoint, and the
  unchanged state-balanced pairwise softplus objective. It completed 60
  optimizer steps using only the 18 train states/28 pairs.
- Development training uses, extra targets, fine-tuning runs, hyperparameter
  or threshold searches, checkpoint selections, and nonfinite training losses
  were zero.
- Final train state-balanced loss was `0.0000278473`. Aggregate, 18 base, six
  Stage 6.4 corrective, and four Stage 6.9 residual pair accuracies were all
  `1.0`; mean margins were `21.6998`, `24.6659`, `19.7933`, and `11.2119`.
- The four evaluation-only development pairs had state-balanced loss
  `0.0004767285`, accuracy `1.0`, and mean margin `23.5365`. They did not affect
  gradients, tuning, or checkpoint selection.
- A separate process reloaded the final checkpoint and exactly reproduced all
  train/development aggregate and pair-type metrics plus prediction digests.
  All forbidden-operation counters remained zero.
- Curated report:
  `website_teacher_preference_residual_corrective_training_v1.json`, SHA-256
  `307b92eca7aef2d7fa927dec71f1e2ccd8b87b71d2336c5630f39c24d0a176dd`.
  Ignored checkpoint SHA-256:
  `cdb3c18948c9310c88f52789f2fd5a12326859ff653558a6aebe7eb569393105`.

Decision:

- Keep the new checkpoint pipeline-only, unpromoted, and ineligible for
  capability claims. Perfect pair fit does not establish full-set behavior.
- Before any Arena, run only a frozen static full-legal-set ranking diagnosis
  across the same 22 teacher states and 934 recorded action entries. Reproduce
  Stage 6.11 metrics separately and do not train or tune in that stage.

## Stage 6.12 Frozen Residual Corrective Full-Legal-Set Diagnosis

Status: completed; all ten corrective orderings hold, but nine residual
full-set states remain and Arena is still disallowed.

Evidence:

- All 11 frozen inputs retained their expected hashes. The Stage 6.11 report
  still records exactly one training run, 60 steps, zero development training
  use, exact reload, and false promotion/capability flags.
- Exactly 22 states and all 934 recorded legal-action entries were scored once:
  889 train and 45 development. All eight duplicate vectors remained in source
  order. Dropped, repeated-score, reconstructed, invalid-dimension,
  illegal-recorded, and nonfinite-Q counts were zero.
- Train teacher/behavior/other first-max top-1 counts were 12/0/6;
  development counts were 1/0/3; overall counts were 13/0/9. Pass top-1
  remained 0/22.
- Overall mean/median teacher rank was 2.09/1.0. Nine states contained 24
  entries strictly above teacher: six train and three development. Relative to
  Stage 6.7, teacher top-1 increased by two, residual states fell by two, and
  strictly-above entries fell from 28 to 24.
- Teacher outranked all six Stage 6.4 rejected actions and all four Stage 6.9
  residual actions. None remained new top-1. Teacher was full-set top-1 in
  four of the six and three of the four respective states.
- The separately accounted frozen-batch replay exactly reproduced Stage 6.11
  train aggregate/base/Stage 6.4/Stage 6.9 and development metrics plus all
  prediction digests. It used 60 pair/120 action-value evaluations excluded
  from the 934-entry full-set count.
- A separate process reproduced every rank, first-max tie, action hash,
  action-order digest, aggregate, metric digest, and corrective mapping. All
  forbidden-operation counters were zero.
- Curated output:
  `website_teacher_preference_residual_corrective_failure_diagnosis_v1.json`,
  SHA-256
  `e8e12f4fd259bc0c2689100d08bdfb3b71662e29c8af0f1e1013fbc6e9573e9f`.

Decision:

- Do not run Arena, promote the checkpoint, or claim capability. Static
  teacher top-1 coverage remains only 13/22.
- Audit existing frozen evidence only for the six current pipeline-train top-1
  actions: `13957:14`, `14077:10`, `14038:12`, `13959:7`, `14025:20`, and
  `13872:4`. Keep development states `13992:16`, `14074:9`, and `13871:9`
  identity-only. Do not train or run a new rollout in the audit stage.

## Stage 6.13 Frozen Remaining-Top1 Evidence Audit

Status: completed; all six train targets remain evidence-insufficient, with
only three new actions lacking a direct paired comparison.

Evidence:

- All 11 frozen input hashes remained unchanged. The Stage 6.12 conclusion
  reproduced exactly without model loading or scoring: 22 states, 934 recorded
  actions, 13/0/9 teacher/behavior/other top-1, zero pass top-1, exact Stage
  6.11 metric digests, and zero forbidden operations.
- Exactly six train and three development targets reproduced by state, original
  action index/order, 54D hash, teacher index/rank, and physical identity.
  Missing, duplicate, extra, reconstructed, substituted, and ambiguous
  mappings were zero.
- Only the six rollout files directly referenced by train teacher samples were
  opened and hashed. `13957:14` index 17 and `13872:4` index 19 were not
  evaluated as source candidates. `14038:12` index 3 had both candidates but
  no direct paired comparison.
- `14077:10` index 0, `13959:7` index 5, and `14025:20` index 1 exactly match
  their Stage 6.9 residual actions; all three frozen direct comparisons remain
  inconclusive. The Stage 6.9 actions for `13957:14` and `14038:12` differ
  from the current top-1 and were explicitly not transferred.
- Supported teacher-over-current and current-over-teacher comparisons were both
  0/6. Unsupported labels, new datasets/objectives, and executed future cases
  were zero.
- Development targets `13992:16`, `14074:9`, and `13871:9` remained
  identity-only. Their source exposure, candidate inspection,
  threshold/objective/confirmation-design use, and execution counts were zero.
- A separate process reproduced every target/source/action hash, physical
  identity, Stage 6.9 identity boundary, classification, partition aggregate,
  isolation counter, and forbidden-operation counter.
- Curated output:
  `website_teacher_preference_residual_corrective_remaining_evidence_audit_v1.json`,
  SHA-256
  `2dff04b2be010a10c3f3e77a144f98d1aeca89a885e21cc98be9c51868b53345`.

Decision:

- Do not run Arena, train, promote, or claim capability. Existing evidence
  supports no current residual ordering.
- Permit only a separate frozen confirmation for `13957:14` index 17,
  `14038:12` index 3, and `13872:4` index 19. Exclude the three already
  inconclusive train cases and all three development targets from execution.

## Stage 6.14 Frozen Three-New-Top1 Counterfactual Confirmation

Status: attempted; acceptance failed and no curated result was written.

Evidence:

- All seven frozen input hashes matched. Preflight selected only `13957:14`
  index 17, `14038:12` index 3, and `13872:4` index 19, while preserving zero
  mappings and executions for the three already-inconclusive train cases and
  all three development cases.
- The unchanged Stage 6.9 schedule requested 96 action rollouts, with 48
  scheduled for `greedy_bot` and 48 for frozen `tempo_baseline`.
- `13957:14` and `14038:12` produced teacher-over-current-top1 supported
  classifications. `13872:4` remained inconclusive, but the run was not
  complete enough for any comparison to become usable evidence.
- Exact terminal accounting was requested 96, completed 90, profile schedule
  48/48, timeout cases 1, and candidate failures 6. The failure occurred under
  the unchanged 600-second per-case limit. The zero-timeout, zero-failure, and
  96/96 gates therefore failed.
- The one-shot writer rejected the incomplete result before creating
  `website_teacher_preference_residual_corrective_remaining_train_confirmation_v1.json`.
  Partial or unsupported labels, datasets, objectives, training runs, model
  scores, Arena games, website activity, promotion, and capability claims were
  all zero.
- A prior outer-command timeout also ended before any case-completion output or
  curated artifact and was not used as evidence. A following run printed the
  same three directions but a generic aggregate assertion discarded the exact
  failure fields before write. The final instrumented run above is the exact
  diagnosed blocker. The retries themselves also violate the intended one-shot
  acceptance, so Stage 6.14 cannot be accepted even apart from 90/96.

Decision:

- Do not use either supported-looking direction, because the formal three-case
  confirmation did not pass its completeness and integrity contract.
- Do not rerun rollouts, change the 600-second limit, weaken a gate, construct a
  dataset, train, or enter Arena in the same stage. First perform a no-rollout
  recovery audit that identifies a semantics-preserving execution path or
  concludes that the frozen confirmation cannot be completed.
- Stage 6.14 and Stage 6 remain incomplete; the active Goal must not be marked
  complete.

## Stage 6.14R Frozen Confirmation Timeout Recovery Audit

Status: completed; exact timeout path derived without executing a rollout.

Evidence:

- Twelve frozen data, code, and failure-handoff hashes matched, and the intended
  Stage 6.14 confirmation output remained absent.
- The frozen confirmation establishes one absolute 600-second deadline for the
  entire case. Every `_simulate_candidate` continuation step checks it, and
  every later call returns `case_time_budget_exhausted` while the fixed schedule
  continues.
- The two supported-looking cases necessarily contain 64 complete candidate
  values because the frozen gate requires all 16 pairs. The 90 total therefore
  leave 26 values, or 13 pairs, in `13872:4`; its final three paired schedule
  items account for exactly six missing candidate values.
- Stage 6.14 already installs the frozen Arena offline optimizations and enables
  the complete-visible-state baseline action cache. No additional existing
  sequential optimization toggle was found.
- The repository already uses process isolation elsewhere, but the confirmation
  path does not. The audit froze one next stage to prove that one task per
  determinization can recreate identical hidden assignments, per-action seeds,
  continuation behavior, returns, schedule order, common deadline, and gates.
- A separate process reconstructed the complete artifact exactly. New rollout,
  model scoring, dataset/objective construction, training, tuning, limit or
  checkpoint changes, locked-test or website data, Arena, website activity,
  promotion, partial labels, and capability claims were all zero.
- Curated audit:
  `website_teacher_preference_residual_corrective_remaining_timeout_recovery_audit_v1.json`,
  SHA-256
  `75115cfc5a9dfa3ecb6ac868d04a2e73d20473cfe3a49c8e805a042028872c0d`.

Decision:

- Do not run another unchanged sequential confirmation and do not use the two
  partial supported-looking directions.
- Permit only a separate no-rollout process-isolation equivalence stage. A
  formal retry remains forbidden until every frozen semantic invariant is
  proven and independently audited.
- If process isolation cannot preserve the contract exactly, freeze Stage 6.14
  as infeasible rather than increasing limits or weakening gates.

## Stage 6.14P Process-Isolated Determinization Parallel Equivalence

Status: completed; synthetic equivalence passed without a real rollout.

Evidence:

- All 13 frozen hashes matched, the failed Stage 6.14 confirmation output
  remained absent, and the real rollout count was zero.
- Exactly eight Windows-spawn-safe tasks reconstructed one determinization
  each, producing the frozen 16 schedule items and 32 teacher/top1 candidate
  calls in greedy/tempo order under one common 600-second deadline.
- Synthetic sequential and real process-pool paths matched every sample hash,
  determinization seed, action identity, profile, return, failure, 300-step
  limit, ordered-call digest, raw aggregate, and frozen Stage 6.9 metric.
- Complete and timeout/failure scenarios both matched. Missing or duplicate
  tasks/calls, seed mismatches, and deadline mismatches failed closed before
  metric construction.
- A separate process recreated both process-pool scenarios and the curated
  artifact exactly. Partial comparison use, dataset/objective construction,
  model scoring, training, tuning, limit or checkpoint changes, locked-test or
  complete-bundle loads, Arena, website activity, promotion, partial labels,
  and capability claims were all zero.
- Curated equivalence:
  `website_teacher_preference_residual_corrective_remaining_parallel_equivalence_v1.json`,
  SHA-256
  `8e168656c35519aae9054038f0fd31398ac0e9260c419de0534a09bf1f4c59ca`.
  Frozen parallel implementation SHA-256:
  `f2093a8c348d9d91435209fd9ee258130b18f7de7b4b7758c0656c1d7a70e2e5`.

Decision:

- Permit exactly one separate formal process-isolated confirmation for the
  three Stage 6.14 train cases. Do not use a sequential fallback or retry.
- Stage 6.14 remains incomplete until that run finishes 96/96 with zero
  timeout/failure and passes an independent audit.

## Stage 6.14E Formal Process-Isolated Three-New-Top1 Confirmation

Status: completed; the single authorized formal execution and independent
audit passed.

Evidence:

- All ten frozen input and implementation hashes matched before and after the
  run. Exactly the three permitted train targets mapped by frozen state,
  action order/index, 54D hash, and physical identity.
- Twenty-four isolated determinization tasks reconstructed 48 schedule items
  and completed exactly 96/96 candidate rollouts: 32 per case and 48/48 by
  greedy/tempo profile. Timeout, candidate failure, retry, and sequential
  fallback counts were zero.
- `13957:14` supported teacher over current top-1 with advantage `1.0`, 95%
  lower bound `0.4939301761`, and greedy/tempo advantages `1.25/0.75`.
- `14038:12` supported teacher over current top-1 with advantage `0.75`, 95%
  lower bound `0.26`, and greedy/tempo advantages `0.25/1.25`.
- `13872:4` remained inconclusive with advantage `0.25`, lower bound `-0.24`,
  and greedy/tempo advantages `0.25/0.25`; it produced no supported label.
- The three excluded train cases and all three development cases retained zero
  source mappings, executions, and rollouts. All forbidden-operation counts
  were zero.
- A separate process reproduced all hashes, mappings, seeds, returns, metrics,
  directions, aggregates, executor metadata, isolation, and forbidden counts.
- Curated confirmation:
  `website_teacher_preference_residual_corrective_remaining_train_confirmation_v1.json`,
  SHA-256
  `450e89f780a33dd543f49f029e735f7fb32e11cd657163c52e6a4301d21f7eb5`.
  Formal wrapper SHA-256:
  `972b67ed585e9a96f9e8be55b70d0b6585a7e499f6dc692c2861d5e636b9e55d`.

Decision:

- Permit only the two supported train comparisons to enter a separate frozen
  corrective dataset extension. Exclude `13872:4`, the three previously
  inconclusive train cases, and all three development targets.
- Do not run another rollout, train, diagnose, run Arena, access the website,
  promote a checkpoint, or claim capability in the dataset stage.

## Stage 6.15 Frozen Remaining-Top1 Corrective Dataset Extension

Status: completed; dataset and independent audit passed without executing the
objective or producing capability evidence.

Evidence:

- All 14 frozen hashes matched. All 22 embedded teacher samples and all 32 v2
  pair semantics and ordering remained exact; only the three deterministic
  weight fields were recomputed.
- Exactly two Stage 6.14E-supported pipeline-train pairs were added:
  `13957:14` teacher over current top-1 index 17 and `14038:12` teacher over
  current top-1 index 3.
- The one new inconclusive case, three previously inconclusive train cases,
  and three held-out development cases added zero pairs.
- The dataset contains 34 pairs across the unchanged 22 states: 30 train pairs
  across 18 states and four development pairs across four states. Provenance
  counts are 22 base, six Stage 6.4, four Stage 6.9, and two Stage 6.14E.
- The state pair-count distribution is 13 single, six double, and three triple
  states. All within-state sums and both partition-normalized sums equal one.
- A separate process reconstructed every hash, sample, preserved/new pair,
  action and physical identity, metric, provenance field, exclusion, weight,
  and forbidden-operation counter exactly.
- Dataset v3 SHA-256:
  `71e90241170882dd97893e71fbe0694368af96525737b55370cd0a60e098ce6f`;
  manifest SHA-256:
  `c9b25d75da0fc5966e1f29bcbd50dd471971e16fc9f4a368cda5b5ba2f8d822d`.

Decision:

- Freeze v3 and its manifest as pipeline-only inputs. Permit one separate
  fixed, from-scratch CPU training smoke on only the 18 train states/30 train
  pairs, with four development pairs evaluation-only.
- Do not tune, select among checkpoints, diagnose full legal sets, run Arena,
  access the website, promote, or claim capability in that training stage.

## Stage 6.16 Frozen Remaining-Top1 Corrective Training Smoke

Status: completed; deterministic pipeline smoke and independent checkpoint
audit passed without capability validation.

Evidence:

- All 19 frozen inputs and every v3 sample, pair, split, provenance,
  exclusion, and weight invariant reproduced exactly before and after training.
- Exactly one from-scratch CPU run used seed `20260714`, 20 epochs, six states
  per batch, learning rate `0.001`, no initialization checkpoint, and the
  unchanged state-balanced pairwise softplus objective.
- Only the 18 train states/30 pairs entered gradients. The run completed 60
  optimizer steps, 360 train-state epoch uses, and 600 train-pair epoch uses.
  All four development states/pairs were evaluation-only.
- Development gradient uses, extra targets, fine-tuning, objective or threshold
  tuning, hyperparameter searches, initialization loads, extra configurations,
  checkpoint selections, and nonfinite values were zero.
- Final train state-balanced loss was `0.0063847274`. Aggregate, base, Stage
  6.4, Stage 6.9, and Stage 6.14E pair accuracies were all `1.0`; mean margins
  were `11.2822`, `13.8454`, `8.2260`, `4.5802`, and `10.7853`.
- Development state-balanced loss was `0.0100213728`, pair accuracy was `1.0`,
  and mean margin was `12.8601`. These metrics were not used for tuning or
  checkpoint selection.
- A separate process reloaded the final checkpoint and reproduced every
  aggregate/pair-source metric and prediction digest exactly. All forbidden
  operation counters remained zero.
- Curated report:
  `website_teacher_preference_remaining_corrective_training_v1.json`, SHA-256
  `cac3ecb0542a7f9aaac2654f73f4e3650422be7eb5990bf4c403f3f082145156`.
  Ignored checkpoint SHA-256:
  `8407f897e36b45affc628fbd2fe68dc4c76a5085fad095511c8045bc73ec5aad`.

Decision:

- Keep the checkpoint pipeline-only, unpromoted, and ineligible for capability
  claims. Perfect frozen-pair fit does not establish full-set behavior.
- Before any Arena, run only a separate frozen static full-legal-set ranking
  diagnosis across the same 22 states and 934 recorded action entries. Do not
  train or tune in that stage.

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

Name: Stage 6.17 Frozen Remaining-Top1 Corrective Full-Legal-Set Diagnosis.

Purpose:

- Load only the frozen Stage 6.16 checkpoint and score all 934 recorded legal
  action entries across the same 22 teacher states once in original order.
- Separately replay the frozen 30/18/6/4/2 train and four development pair
  batches to reproduce every Stage 6.16 metric and prediction digest without
  mixing replay accounting into full-set scoring.

Acceptance:

- Exact 22-state, 934-action, 889/45 train/development accounting passes with
  all duplicate action entries preserved and no dropped, reconstructed,
  repeated, invalid, illegal, or nonfinite scores.
- A separate process reproduces every rank, tie, action-order digest,
  aggregate, Stage 6.16 metric/digest, and all 6+4+2 corrective mappings.
- Rollout, training, tuning, checkpoint changes, locked-test or complete-bundle
  loads, Arena, website access, promotion, and capability claims remain zero.
