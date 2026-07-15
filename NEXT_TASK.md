# NEXT_TASK.md

## Single Next Stage

Run Stage 6.20: frozen Stage 6 final offline-gate disposition audit.

Stage 6.19 completed the last permitted train-only comparison and found both
new actions inconclusive. All three current train residual actions now have
direct inconclusive evidence, the three development residuals remain held out,
and the supported-comparison manifest is empty. Perform one no-execution audit
that freezes the complete Stage 6 evidence chain and closes Stage 6 as
completed-rejected. Do not run another Arena or begin Stage 7.

## Frozen Inputs

- Stage 6.19 confirmation:
  `website_teacher_preference_remaining_corrective_final_train_confirmation_v1.json`,
  SHA-256
  `a1f32207255867dd2a59c7f9043c57038aff37f506746c970f8892f1d852e189`.
- Stage 6.19 implementation:
  `website_teacher_preference_remaining_corrective_final_parallel_confirmation.py`,
  SHA-256
  `63d0f047d11d4b92b9a3fcdcd9dd2ee68b939e68fafc19513fb3a1527ec41bdb`.
- Recursively freeze all 30 hashes recorded by Stage 6.19, including Stage
  6.18/6.17 evidence and implementations, Stage 6.16 report/checkpoint, Stage
  6.14P/E executor authority/evidence, Stage 6.13/6.12/6.9/6.4 evidence,
  teacher v6, split, source train/development data, and Stage 6.1 Arena.
- The new curated output path must be unused:
  `website_teacher_preference_stage6_final_disposition_v1.json`.

## Required Reproduction

1. Stage 6.1 remains the only completed paired Arena screen for its frozen
   candidate: 20/20 games, model/baseline wins 0/20, continuation false,
   promotion false, and capability false.
2. The current remaining-corrective checkpoint remains pipeline-only and
   unpromoted. Stage 6.17 scored 22 states/934 actions with teacher first-max
   top-1 in 16/22: train 15/18 and development 1/4; pass top-1 was 0/22.
3. Stage 6.18 isolated exactly three current train residual actions and three
   identity-only development residuals with zero evidence transfer.
4. Direct current-action conclusions are all inconclusive:
   - `14077:10` index 0, preserved from Stage 6.9;
   - `14031:4` index 2, Stage 6.19;
   - `14025:20` index 2, Stage 6.19.
5. Stage 6.19 completed 16 isolated tasks, 32 schedule items, and 64/64
   rollouts with zero failure/retry/fallback, and its supported manifest is
   empty.
6. No further strong corrective pair, dataset extension, training run, or
   Arena candidate is authorized by frozen evidence.

## Required Work

1. Re-read all canonical handoffs; verify Git state, every frozen hash, exact
   conclusions above, and the unused output path.
2. Implement the smallest read-only disposition auditor. It may load only the
   named curated JSON evidence and inspect recorded hashes/metrics; it must not
   load a model/checkpoint, teacher/source dataset, locked test, or complete
   website bundle.
3. Reproduce the Stage 6 route chronology, candidate identities, executed and
   prohibited counts, residual classifications, supported-pair count, and all
   pass/reject booleans without scoring, simulation, or new statistical design.
4. Record the final disposition exactly as:
   - `stage_6_status = completed_rejected`;
   - `offline_gate_passed = false`;
   - `eligible_offline_candidate_count = 0`;
   - `stage_7_authorized = false`;
   - `website_control_authorized = false`;
   - `capability_claim_allowed = false`.
5. Independently reconstruct the complete small artifact in a separate
   process, update handoffs/progress, run focused and full tests plus
   credential/diff checks, commit, and push.

## Interpretation Contract

- “Completed-rejected” means Stage 6 work is closed with a negative gate
  result; it does not mean the model passed, improved, or is deployable.
- Inconclusive train comparisons must not be converted into teacher or current
  action labels. Held-out development cases remain unused.
- The current checkpoint must not receive an Arena run merely because the
  corrective evidence route is exhausted. No frozen decision authorized it.
- Stage 7 and website control remain blocked until a future user-authorized
  route produces a candidate that actually passes the required offline gate.

## Prohibited Work

- Do not load/score a model or checkpoint; do not load teacher/source data,
  locked test, or the complete website bundle.
- Do not run rollout, simulation, Arena, Shadow, website play, model control,
  data collection, dataset/objective construction, training, fine-tuning,
  tuning, search, checkpoint selection/modification, promotion, or new labels.
- Do not change `tempo_baseline`, protocol, Elo semantics, thresholds,
  information-set rules, prior artifacts, or any earlier conclusion.
- Do not enter or execute Stage 7 in this stage.

## Acceptance Criteria

- All 32 unique frozen hashes (30 recursive plus Stage 6.19 output and
  implementation) and every required recorded conclusion reproduce exactly.
- The disposition artifact is written once and independently reconstructed;
  missing/duplicate/extra/inconsistent evidence and unsupported inference
  counts are zero.
- Model/checkpoint/data loads, rollout/simulation, Arena, dataset/objective,
  training/tuning, website, promotion, new-label, capability-claim, and Stage
  7 execution counters are all zero.
- Handoffs explicitly state that Stage 6 is completed-rejected, Stage 7 is not
  authorized, and there is no automatic executable next stage.
- Credential occurrences in new tracked/curated files are zero.
- Focused tests, full tests, conventional commit, and push succeed before Stage
  6.20 or Stage 6 is marked complete.
