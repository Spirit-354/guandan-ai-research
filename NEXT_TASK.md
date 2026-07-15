# NEXT_TASK.md

## Single Next Stage

Run Stage 6.15: frozen remaining-top1 corrective dataset extension.

Stage 6.14E completed the single formal confirmation at 96/96. Only
`13957:14` current top-1 index 17 and `14038:12` current top-1 index 3 passed
the frozen teacher-direction gates. `13872:4` index 19 remained inconclusive.

Build one new v3 corrective preference dataset and manifest by preserving all
32 Stage 6.10 v2 pair semantics and adding only the two supported Stage 6.14E
train comparisons. Recompute deterministic state-balanced weights after those
two additions. This stage is dataset construction and independent audit only;
do not execute the objective or train.

## Frozen Inputs

- Stage 6.14E confirmation:
  `website_teacher_preference_residual_corrective_remaining_train_confirmation_v1.json`,
  SHA-256
  `450e89f780a33dd543f49f029e735f7fb32e11cd657163c52e6a4301d21f7eb5`.
- Stage 6.14E formal wrapper:
  `website_teacher_preference_residual_corrective_remaining_parallel_confirmation.py`,
  SHA-256
  `972b67ed585e9a96f9e8be55b70d0b6585a7e499f6dc692c2861d5e636b9e55d`.
- Frozen v2 corrective dataset:
  `website_teacher_preference_corrective_dataset_v2.pth`, SHA-256
  `40024f7c064f0ebb7999c4ac0f7bc85d77b759a23956cbe596756763d4009d4d`.
- Frozen v2 manifest:
  `website_teacher_preference_corrective_dataset_v2_manifest.json`, SHA-256
  `ce5141f6254218d9230b15117a88d3c5e6bd374839bcf5fc77b393e2599ec353`.
- Teacher v6, frozen 18/4 split, Stage 6.13 evidence audit, Stage 6.12
  diagnosis, Stage 6.9 confirmation, Stage 6.1 rejection, Stage 6.14P
  equivalence, and physical train/development source retain the hashes recorded
  by the accepted Stage 6.14E evidence.
- New outputs must be unused before construction:
  `website_teacher_preference_corrective_dataset_v3.pth` and
  `website_teacher_preference_corrective_dataset_v3_manifest.json`.

## Required Work

1. Re-read all canonical handoffs; verify Git state, frozen hashes, exact
   Stage 6.14E supported manifest, and both unused output paths.
2. Reuse the Stage 6.10 dataset semantics and builder pattern. Preserve every
   v2 sample and pair field exactly except the three deterministic weight
   fields that must be recomputed for all pairs.
3. Add exactly two pipeline-train pairs: teacher preferred over the current
   top-1 action for `13957:14` index 17 and `14038:12` index 3, with exact
   action hashes, physical identities, source metrics, and Stage 6.14E
   provenance.
4. Write one v3 dataset and one small manifest, then independently reload and
   reconstruct both in a separate process.
5. Update `PROJECT_STATE.md`, `EXPERIMENTS.md`, `NEXT_TASK.md`, and the durable
   progress document; run focused and full tests plus credential and diff
   checks; commit and push.

## Dataset Contract

- Exactly 34 pairs across the unchanged 22 states: 30 pipeline train across 18
  states and four pipeline development across four states.
- Pair provenance counts: 22 frozen base, six Stage 6.4 corrective, four Stage
  6.9 residual corrective, and two Stage 6.14E remaining-top1 corrective.
- State pair-count distribution: 13 states with one pair, six with two pairs,
  and three with three pairs.
- Within each state, all pair weights are equal and sum to exactly one.
  Partition-normalized weights sum to exactly one for train and one for
  development.
- The frozen objective remains state-balanced pairwise
  `softplus(Q_rejected-Q_preferred)` and is recorded but not executed.

## Exclusions and Prohibited Work

- `13872:4` index 19, train cases `14077:10` index 0, `13959:7` index 5, and
  `14025:20` index 1, plus development cases `13992:16`, `14074:9`, and
  `13871:9`, must add zero pairs.
- Do not run another rollout, score a model, execute an objective, train,
  fine-tune, tune a threshold or hyperparameter, select or modify a checkpoint,
  load locked test or the complete website bundle, run Arena, access the
  website, start Shadow or model-controlled play, promote, or claim capability.

## Acceptance Criteria

- All frozen hashes match and all 32 v2 pair semantics are preserved exactly.
- Exactly two supported train pairs are added; unsupported, inconclusive,
  development, duplicate, extra, substituted, and ambiguous additions are
  zero.
- The 34/30/4 pair/split counts, 13/6/3 state pair-count distribution, and all
  state/partition weight sums reproduce exactly.
- An independent process reproduces every sample hash, pair ID, action hash,
  physical identity, metric, provenance field, exclusion, weight, output hash,
  and forbidden-operation counter.
- Credential occurrences in new tracked/curated files are zero.
- Handoffs, focused tests, full tests, conventional commit, and push succeed
  before Stage 6.15 is accepted.
