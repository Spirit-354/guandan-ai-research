# PROJECT_STATE.md

## Current Project State

Date: 2026-07-14

Branch: `agent/stage5-website-bot-adaptation`

Latest completed stage:

- Stage 6.4 Frozen Pipeline-Train Unpaired Counterfactual Confirmation.

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
- Extension v3 remains frozen and unchanged at 82 games.
- Extension v4 remains frozen and unchanged at 94 games.
- Current extension v5 contains 106 baseline-only website bot games: 64 wins
  and 42 losses, 2,685 decisions, and 82,417 legal candidates.
- Frozen base manifest hash:
  `83a58a43ea91f5662e2588494d7bad1b3d9d18de51c30216e5be0e589e0437e4`.
- Extension v1 manifest hash:
  `db209561f6961b289dda668861687fcd7a258a2f283cecaae065501b2006f429`.
- Extension v2 manifest hash:
  `31c5bc501286ac41d3a791811c7089200e49097132bfd886aa10d281c5ddb27e`.
- Extension v3 manifest hash:
  `51fe0244407d67e8267ea11b7146ff214f73823c29db92062189a58d033e5af9`.
- Extension v4 manifest hash:
  `368771a6a647d34d0d6fcd0490d7cdd1e57991a4c4188e3c127780a5323acbec`.
- Extension v5 manifest hash:
  `a2931c6078487662d25f115896034311354eade265bec8b72f94ea2d5a7bdaf7`.
- Curated evidence: `website_dataset_split_manifest_extension_v5.json` and
  `website_dataset_card_extension_v5.json`.
- All 12 Supplement v5 games, 345 decisions, and 11,587 candidates entered
  train; rejected new games or decisions: 0.

Information-set-consistent train/development subset:

- 1,814 decisions across 97 independent games.
- 1,650 train decisions and 164 development decisions.
- 70,320 legal candidates.
- 306 lead decisions and 1,508 follow decisions.
- 1,118 level-card states, including 467 wildcard states.
- 1,371 endgame states and 872 bomb-candidate states.
- All 13 level values and all four first-player seats are represented; the
  website account itself remains in seat 0.
- Elo bands: 174 decisions in `1900-1999`, 744 in `2000-2099`, and 896 in
  `2100-2199`.
- Duplicate state count: 0.

Locked test:

- The original nine-game locked-test set is exactly unchanged in extension v5.
- No new session or game was assigned to locked test.
- The isolated physical locked-test partition remains 90 consistent decisions.
- The locked-test partition remains prohibited for training, candidate design,
  checkpoint selection, and teacher threshold tuning.

Teacher dataset:

- Frozen base: `website_information_set_teacher_dataset_v3.pth`, unchanged at
  13 labels from 13 independent games.
- Frozen base: `website_information_set_teacher_dataset_v4.pth`, unchanged at
  16 labels from 16 independent games.
- Frozen base: `website_information_set_teacher_dataset_v5.pth`, unchanged at
  19 labels from 19 independent games.
- Current dataset: `website_information_set_teacher_dataset_v6.pth`.
- 22 accepted high-confidence teacher labels from 22 independent games: 19
  frozen labels plus 3 extension v5 labels.
- New accepted cases: `14058:22`, `14074:9`, and `14077:10`.
- Representation: 513 state dimensions, 54 website action dimensions.
- Teacher v6 SHA-256:
  `a74416e6facb28a1bc64563eba90cb33d460dc9e59cc2109518da142465e15f8`.
- The 20-game teacher gate is satisfied at 22 independent games. No model has
  been promoted from teacher v6, and capability claims remain prohibited.
- The frozen teacher-preference pipeline split contains 18 train games and four
  internal development games with zero overlap. Split manifest SHA-256:
  `5a15e514dc9bc51d77d300837151d9f1a49250f42885cc7940725bcbe4d35107`.
- Curated training report SHA-256:
  `896192b1d0b4de2caabe20ac17d6a20766fc7f89d6e82a981d834b777932ddd3`.
- The deterministic CPU smoke produced the ignored checkpoint
  `models_website_teacher_preference_v1/website_teacher_preference_final.pth`,
  SHA-256
  `c54801a9db05100c2fe5a9bf610a64fc7c94dc2cd947dfaab115ff827bd90919`.
  It is pipeline evidence only and is not promoted.
- The Stage 6.1 paired offline Arena output is
  `website_teacher_preference_arena_smoke20_v1.json`, SHA-256
  `aa45da9de202194102fe8d11e612ad3eb4b51177fd910b9a7948836afd2a1fe6`.
  It completed 20/20 integrity games but the model lost all 20, so offline
  continuation is not allowed.
- The Stage 6.2 static full-legal-set diagnosis is
  `website_teacher_preference_failure_diagnosis_v1.json`, SHA-256
  `da08516c39986a01349533e160ba0e97a566d7fad6e42b0b7b3ce41df835b0b2`.
  It scored all 934 recorded actions from all 22 frozen teacher states and
  exactly reproduced both frozen pairwise metrics and prediction digests.
- The Stage 6.4 pipeline-train counterfactual confirmation is
  `website_teacher_preference_unpaired_train_confirmation_v1.json`, SHA-256
  `8e17377b5a1523d9f0a47af7218d687e062a3ade671c57f387eb4c1a0888cfae`.
  Six of nine train-only teacher-versus-top1 comparisons passed every frozen
  strong-teacher gate; three were inconclusive and none supported top1 over
  teacher. All three pipeline-development targets remained unexecuted.

Current blocker:

- The Stage 6.1 integrity gate passed, but the early-screen performance gate
  failed at 0 wins and 20 losses. The checkpoint remains rejected from the
  100/200-game screen.
- Stage 6.2 found pairwise teacher-over-behavior accuracy of 21/22 while the
  teacher was full-set top-1 in only 10/22 states. An unpaired recorded action
  strictly outranked teacher in 12/22 states, across 161 action entries. This
  is an objective-coverage pattern, not a causal finding.
- Pass was top-1 in 0/22 teacher states, so the 66.3% Arena pass rate is not
  explained by this frozen diagnostic. Stage 6.4 now supplies six qualifying
  train-only teacher-versus-top1 constraints, but the rejected checkpoint has
  not been retrained and no improved offline performance has been shown.
- The eligible extension v5 pool is exhausted: all 277 rollout-eligible states
  were screened, all permitted positive-screen game signals were confirmed or
  exhausted, and three labels passed.

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

Status: completed.

Constraints:

- Preserve all cumulative session assignments and preassign only the unused v4
  supplement session to train before collection.
- Only frozen `tempo_baseline` may submit website actions; stop non-bot tables
  before the first action.
- Collect exactly 12 completed verified bot-table games with exhaustive oracle
  candidates and decision-time-consistent information sets.
- Record Elo only from `leaderboard_elo`. Do not rebuild a dataset, run teacher
  rollout, train, evaluate, or allow model-controlled website play.

Acceptance:

- `website_dataset_extension_session_splits_v4.json` preserves all four prior
  assignments and adds only `logs_website_shadow_supplement_train_004: train`;
  locked-test assignment changes: 0.
- Exactly 12 verified bot-table games completed: 6 wins and 6 losses, game IDs
  14035 through 14046.
- All 279 submissions succeeded; all 279 decisions recorded exhaustive
  website-oracle candidates and consistent decision-time information sets,
  covering 12,959 legal candidates.
- Frozen `tempo_baseline` submitted every action; model-controlled actions and
  suggestion differences: 0.
- Leaderboard Elo was continuous from 2158 to 2121, net -37, with all 12 games
  sourced from `leaderboard_elo` rather than final-state scores.
- Failed games, non-bot actions, communication, encoding, team mapping,
  hand-subset, legality, oracle, materialization, website-rule, wildcard,
  information-set, duplicate-submit, and unrecoverable-desync errors: 0.
- No dataset rebuild, teacher rollout, teacher label, model training, offline
  evaluation, or model-controlled website play occurred; credential
  occurrences: 0.

### Stage 4.12: Frozen Dataset Extension v4

Goal: add the preassigned Supplement v4 train session without changing any
frozen extension v3 game, split, source hash, or locked-test membership.

Status: completed.

Constraints:

- Use extension v3 as the frozen manifest base and the cumulative v4 assignment
  file; include only the new Supplement v4 session beyond existing sources.
- Preserve all 82 old games, source hashes, splits, assignments, and the exact
  nine-game locked-test set.
- Write only new extension v4 bundle, physical partitions, manifest, and data
  card. Do not run website play, teacher rollout, training, or evaluation.

Acceptance:

- All 94 games were accepted: 55 wins and 39 losses, with 2,340 decisions and
  70,830 legal candidates; rejected files or games: 0.
- All 82 extension v3 games, source hashes, session assignments, splits, and
  the exact nine-game locked-test set are unchanged.
- All 12 Supplement v4 games entered train, contributing 279 consistent
  decisions and 12,959 candidates; new development or locked-test games: 0.
- The physical train/development partition contains 1,469 consistent decisions:
  1,305 train and 164 development, with 58,733 candidates and zero duplicate
  states. Coverage, information-set, physical-isolation, and threshold gates
  pass.
- The isolated locked-test partition remains nine games and 90 consistent
  decisions. Frozen extension v3 and teacher v4 hashes remain unchanged.
- Model-controlled actions: 0; no website play, teacher rollout, teacher label,
  model training, or offline evaluation occurred.

### Stage 4.13: Extension v4 Teacher Candidate Expansion

Goal: screen every eligible new train state from the 12 Supplement v4 games and
append only robust information-set labels to frozen teacher v4.

Status: completed.

Constraints:

- Load only `website_danzero_shadow_extension_v4.train_dev.pth`; do not load
  the complete bundle or locked-test partition.
- Restrict screening to games 14035 through 14046 and preserve the frozen
  strong-label gates.
- Greedy-only results may select confirmation candidates but cannot directly
  produce strong labels.
- Preserve all 16 teacher v4 labels and verify 54-dimensional physical-action
  remapping. Do not train, even if the 20-game gate is reached.

Acceptance:

- Only the v4 physical train/development partition was loaded; complete-bundle
  and locked-test loads were zero.
- All 279 new train decisions were enumerated: 252 eligible states completed
  greedy-only screening and 27 were ineligible because a public hand count was
  nonpositive.
- Greedy-only screening completed 6,256/6,256 rollouts across 782 candidates
  and accepted zero strong labels. Dual-continuation confirmation completed
  384/384 rollouts across six cases and 24 candidates.
- `14038:12`, `14044:9`, and `14045:5` passed every frozen strong-label gate;
  no failed game retained a permitted positive-screen alternative.
- All 16 teacher v4 samples were preserved exactly after deserialization;
  state, behavior-action, legality, 513/54 dimensions, and physical-card remap
  errors were zero.
- Teacher v5 contains 19 labels from 19 games. The 20-game gate remains closed,
  and website play, model training, offline evaluation, and model-controlled
  website actions were all zero in this stage.

### Stage 4.14: Website Shadow Supplement v5

Goal: collect the next explicitly assigned baseline-only train session for new
independent information-set teacher candidates.

Status: completed.

Constraints:

- Preserve all cumulative session assignments and preassign only the unused v5
  supplement session to train before collection.
- Only frozen `tempo_baseline` may submit website actions; stop non-bot tables
  before the first action.
- Collect exactly 12 completed verified bot-table games with exhaustive oracle
  candidates and decision-time-consistent information sets.
- Record Elo only from `leaderboard_elo`. Do not rebuild a dataset, run teacher
  rollout, train, evaluate, or allow model-controlled website play.

Acceptance:

- `website_dataset_extension_session_splits_v5.json` preserves all five prior
  assignments exactly and adds only
  `logs_website_shadow_supplement_train_005: train`; locked-test membership did
  not change.
- Exactly 12 verified bot-table games were completed: 9 wins and 3 losses,
  game IDs `14058`, `14059`, `14061`, `14063`, `14064`, `14066`, `14068`,
  `14070`, `14072`, `14074`, `14077`, and `14081`.
- Frozen `tempo_baseline` submitted all 345 decisions successfully. The logs
  retain 11,587 exhaustive website-oracle candidates and consistent
  decision-time information sets; model-controlled actions were zero.
- Elo came only from `leaderboard_elo`, remained continuous between games, and
  moved from 2121 to 2168 for a net change of +47.
- All reported communication, encoding, team-mapping, hand-subset, legality,
  oracle, materialization, website-rule, wildcard, information-set,
  duplicate-submit, and unrecoverable-desync errors were zero.
- No dataset build, teacher rollout or label creation, training, offline
  evaluation, or model-controlled website play occurred.

### Stage 4.15: Frozen Dataset Extension v5

Goal: extend the frozen v4 dataset with only the preassigned Supplement v5
train session.

Status: completed.

Constraints:

- Use `website_dataset_split_manifest_extension_v4.json` as the sole frozen
  manifest base and `website_dataset_extension_session_splits_v5.json` as the
  cumulative assignment authority.
- Add only the 12 Supplement v5 games; preserve all old source hashes, session
  assignments, splits, samples, and locked-test membership.
- Rebuild new v5 outputs and run coverage/integrity audits without teacher
  rollout, label creation, training, offline evaluation, or website play.

Acceptance:

- Extension v5 contains 106 accepted games, 64 wins and 42 losses, 2,685
  decisions, and 82,417 legal candidates; rejected files or games: 0.
- All 94 v4 games, source hashes, session assignments, splits, and all 2,340
  old samples are unchanged except for the expected v5 manifest-reference
  field. Locked-test membership changes: 0.
- The 12 Supplement v5 games all entered train and contributed exactly 345
  information-set-consistent decisions and 11,587 candidates; new development
  or locked-test games: 0.
- The physical train/development partition contains 1,814 consistent samples:
  1,650 train and 164 development, with 70,320 candidates and zero duplicate
  states. Coverage, information-set, physical-isolation, and threshold gates
  pass.
- The physical locked-test partition remains the same nine games and 90
  samples. Frozen extension v4 and teacher v5 hashes remain unchanged.
- Website play, teacher rollout or label creation, training, offline
  evaluation, and model-controlled website play were all zero.

### Stage 4.16: Extension v5 Teacher Candidate Expansion

Goal: screen every eligible new train state from the 12 Supplement v5 games and
append only robust information-set labels to frozen teacher v5.

Status: completed.

Constraints:

- Load only `website_danzero_shadow_extension_v5.train_dev.pth`; do not load
  the complete bundle or locked-test partition.
- Restrict enumeration and screening to the 12 Supplement v5 game IDs and keep
  all frozen completeness, variance, advantage, confidence, and dual-
  continuation robustness gates unchanged.
- Preserve all 19 teacher v5 labels exactly and write only teacher v6. Do not
  train or evaluate even if the 20-game teacher gate is reached.

Acceptance:

- Only the v5 physical train/development partition was loaded; complete-bundle
  and locked-test loads were zero.
- All 345 new train decisions were enumerated: 277 eligible states completed
  greedy-only screening and 68 were ineligible only because a public hand
  count was nonpositive.
- Greedy-only screening completed 6,744/6,744 rollouts across 843 candidates
  and accepted zero strong labels. Dual-continuation confirmation completed
  320/320 rollouts across five cases and 20 candidates.
- `14058:22`, `14074:9`, and `14077:10` passed every frozen strong-label gate.
  Failed games retained no permitted positive-screen alternatives; the unused
  same-game `14074:10` alternative was not run because `14074:9` passed.
- All 19 teacher v5 samples were preserved exactly after deserialization;
  source state, behavior action, legal teacher action, 513/54 dimensions, and
  physical-card remap errors were zero.
- Teacher v6 contains 22 labels from 22 games and passes the 20-game teacher
  gate. Website play, model training, offline capability evaluation, and
  model-controlled website play were all zero.

### Stage 5: Training Gate

Goal: train only after enough teacher labels and coverage exist.

Status: completed; pipeline-only smoke passed.

Constraints:

- Freeze teacher v6 and extension v5 train/development as the only permitted
  training/readiness inputs; never load locked test.
- Add the smallest 513+54 teacher-preference training path needed for a
  deterministic pipeline smoke, with complete-game grouping and a frozen split
  manifest. Do not run Arena or website Shadow in the same stage.
- Treat all training metrics as pipeline evidence only; do not promote a
  checkpoint or make a capability claim.

Acceptance:

- At least 20 independent high-confidence teacher games.
- Coverage audit passes.
- Train/development split is frozen.
- Capability claims remain limited until offline and website-domain gates pass.
- Teacher v6 validation found zero schema, dimension, legality, identity,
  provenance, split, or locked-test errors across 22 preference pairs.
- SHA-256 grouping assigned 18 complete games to pipeline train and four to
  internal pipeline development with zero overlap or dropped games.
- The existing `danzero_dmc.build_q_model` completed a fixed CPU recipe using
  only `softplus(Q_behavior-Q_teacher)`. Hyperparameter searches and checkpoint
  selections were zero.
- Final train/development ranking accuracies were 1.00/0.75, but all metrics
  are explicitly pipeline-only and ineligible for capability evidence.
- Independent checkpoint reload exactly reproduced the report. A temporary
  full rerun exactly reproduced the split, recipe, history, metrics, and
  prediction digests.
- Complete-bundle and locked-test loads, extra targets, Arena games, website
  Shadow, website games, model-controlled website actions, checkpoint
  promotion, and capability claims were all zero.

### Stage 6: Offline Gate

Goal: compare candidates against frozen `tempo_baseline`.

Status: Stage 6.4 completed; continuation rejected, six train-only corrective
constraints confirmed but not yet converted into a frozen dataset or model.

Constraints:

- Use only the frozen teacher-preference checkpoint with SHA-256
  `c54801a9db05100c2fe5a9bf610a64fc7c94dc2cd947dfaab115ff827bd90919`.
- Add only the compatibility needed for the existing 513+54 Arena path to load
  the teacher-preference checkpoint. Do not retrain or change action semantics.
- Run exactly 20 paired, seat-swapped games against frozen `tempo_baseline`.
  Treat the result as offline integrity/screening evidence only.
- Do not proceed to the 100/200-game screen, locked test, website Shadow, or
  website control in the same stage.

Stage 6.1 acceptance:

- The frozen teacher-preference and legacy distributed-DMC checkpoint loaders
  both passed focused tests; incompatible preference metadata is rejected.
- Exactly 20 games completed as ten adjacent paired seeds. Each pair used the
  same deal, first-player, and Arena RNG seeds with model teams `{0,1}`.
- Model/baseline results were 0/20 and 20/20. The integrity gate passed, but
  the frozen 0.30 early-screen continuation gate failed and remains false.
- Model/baseline decisions were 964/873; average game length was 91.85. The
  model pass rate was 0.6629 and bomb rate was 0.0239.
- Illegal, fallback, materialization, hand-card mismatch,
  fatal-no-candidate, and baseline-equivalence mismatch counts were zero.
- Training, tuning, checkpoint selection, website-dataset or locked-test loads,
  later Arena screens, website Shadow/play, checkpoint promotion, and
  capability claims were zero.

Stage 6.2 acceptance:

- All five frozen input hashes remained unchanged and the Stage 6.1 conclusion
  remained 0-20 with continuation false.
- Exactly 22 unique states and all 934 recorded legal-action entries were
  scored once. Dropped, repeated-scoring, reconstructed, dimension-invalid,
  illegal-recorded, and nonfinite-Q counts were zero.
- Pipeline partitions remained exactly 18 train and four development games
  with zero overlap or unknown games. Frozen pairwise metrics and both
  prediction digests reproduced exactly.
- Overall teacher-over-behavior rate was 21/22, but teacher/behavior/other
  top-1 counts were 10/0/12. Pass top-1 was 0/22; mean/median teacher rank was
  8.36/2.0. Twelve states contained 161 unpaired action entries strictly above
  teacher.
- Training, tuning, checkpoint selection or modification, website-dataset or
  locked-test loads, Arena, website Shadow/play, model control, promotion, and
  capability claims were zero.

Stage 6.3 acceptance:

- All six primary frozen inputs and ten directly referenced rollout-evidence
  files retained their expected SHA-256 hashes. Stage 6.1 remained 0-20 with
  continuation false and the checkpoint remained rejected.
- Exactly the 12 Stage 6.2 unpaired top-1 targets reproduced: nine pipeline
  train and three pipeline development, with zero missing, duplicate, extra,
  reconstructed, or ambiguous state/action mappings.
- Four top-1 actions had complete dual-continuation candidate results, but none
  recorded teacher-versus-top1-specific paired confidence. The other eight
  were present in the frozen legal-action set without a qualifying candidate
  comparison. Greedy-only, absent, and ambiguous classifications were zero.
- Existing evidence therefore supports zero teacher-versus-top1 orderings and
  does not support a teacher-versus-all objective. All 12 insufficient cases
  were written to a future manifest that was not executed.
- New rollout, training, tuning, checkpoint selection or modification,
  website-dataset or locked-test loads, Arena, website Shadow/play, model
  control, promotion, and capability claims were zero.
- Curated audit evidence:
  `website_teacher_preference_unpaired_evidence_audit_v1.json`, SHA-256
  `09f52df90d095ab6b3777a046c50901f96fbeb15e6ef5f613343a13be1249383`.

Stage 6.4 acceptance:

- All seven frozen primary hashes and the physical train/development source
  hash remained unchanged. Only nine pipeline-train manifest cases ran; the
  three pipeline-development cases remained held out with zero executions and
  rollouts.
- Exactly 288/288 rollouts completed: nine cases, two exact actions per case,
  and 16 rollouts per action. Greedy and frozen-tempo continuation counts were
  144 each, using eight shared determinizations per case across both actions
  and both profiles.
- Six teacher-over-top1 comparisons passed the unchanged advantage, variance,
  positive-95%-lower-bound, and dual-continuation gates. Three were
  inconclusive; top1-over-teacher supported comparisons were zero.
- Exact target, action-order, 54D action, physical-card, return, variance,
  confidence, profile, and aggregate arithmetic independently reproduced.
  Timeouts, candidate failures, hidden/future information use, integrity
  failures, and locked-test loads were zero.
- Training, tuning, checkpoint selection or modification, Arena, website
  Shadow/play, model control, promotion, and capability claims were zero. The
  existing checkpoint remains rejected from the 100/200-game screen.
- Curated confirmation evidence:
  `website_teacher_preference_unpaired_train_confirmation_v1.json`, SHA-256
  `8e17377b5a1523d9f0a47af7218d687e062a3ade671c57f387eb4c1a0888cfae`.

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
