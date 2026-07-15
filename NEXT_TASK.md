# NEXT_TASK.md

## Single Next Stage

Run Stage 6.17: frozen remaining-top1 corrective full-legal-set diagnosis.

Stage 6.16 completed exactly one fixed from-scratch smoke on corrective dataset
v3 and independently reproduced every checkpoint metric and prediction digest.
Run one static diagnosis of that frozen checkpoint over the complete recorded
legal-action sets of the same 22 teacher states. This stage is model scoring
and independent diagnosis audit only; do not train, tune, or run Arena.

## Frozen Inputs

- Stage 6.16 training report:
  `website_teacher_preference_remaining_corrective_training_v1.json`, SHA-256
  `cac3ecb0542a7f9aaac2654f73f4e3650422be7eb5990bf4c403f3f082145156`.
- Stage 6.16 checkpoint:
  `models_website_teacher_preference_remaining_corrective_v1/website_teacher_preference_remaining_corrective_final.pth`,
  SHA-256
  `8407f897e36b45affc628fbd2fe68dc4c76a5085fad095511c8045bc73ec5aad`.
- Stage 6.16 implementation:
  `website_teacher_preference_remaining_corrective_training.py`, SHA-256
  `8f3c74b272228cb0423aa192187d64028c4b7bce2f23dd74d12d811c55f76ded`.
- Corrective dataset v3 and manifest:
  `71e90241170882dd97893e71fbe0694368af96525737b55370cd0a60e098ce6f`
  and
  `c9b25d75da0fc5966e1f29bcbd50dd471971e16fc9f4a368cda5b5ba2f8d822d`.
- Stage 6.12 diagnosis pattern and evidence:
  `website_teacher_preference_residual_corrective_diagnosis.py`, SHA-256
  `75af0c847a49484059c103fe12f8db1f4fb447cb04c2161ed1ffe913dea8e008`,
  and `website_teacher_preference_residual_corrective_failure_diagnosis_v1.json`,
  SHA-256
  `e8e12f4fd259bc0c2689100d08bdfb3b71662e29c8af0f1e1013fbc6e9573e9f`.
- Recursively freeze every input hash recorded by the accepted Stage 6.16
  report, including teacher v6, the 18/4 split, Stage 6.1 rejection, all
  confirmations, v1/v2/v3 datasets and manifests, and implementation hashes.
- The new curated diagnosis path must be unused before the formal run:
  `website_teacher_preference_remaining_corrective_failure_diagnosis_v1.json`.

## Required Work

1. Re-read all canonical handoffs; verify Git state, every frozen hash, exact
   Stage 6.16 accounting/metrics/digests, and the unused diagnosis output.
2. Reuse the Stage 6.12 diagnosis and audit pattern with the smallest necessary
   v3/checkpoint-specific change. Do not modify the frozen checkpoint, dataset,
   training implementation, scoring semantics, or recorded action order.
3. Score exactly all 934 recorded legal-action entries across the same 22
   teacher states once: 889 train entries and 45 development entries. Preserve
   all eight duplicate-vector source entries in their original positions.
4. Separately reproduce Stage 6.16 train aggregate/base/Stage 6.4/Stage
   6.9/Stage 6.14E and development metrics and prediction digests using their
   frozen batch shapes. Account for 64 pair evaluations/128 action-value
   evaluations outside the 934-entry full-set count.
5. Record every teacher rank, first-maximum source and tie, pass-top1 count,
   action-order digest, strictly-above-teacher entry, and exact 6+4+2
   corrective-pair mapping. Independently reload and reproduce the complete
   artifact in a separate process.
6. Update `PROJECT_STATE.md`, `EXPERIMENTS.md`, `NEXT_TASK.md`, and the durable
   progress document; run focused and full tests plus credential and diff
   checks; commit and push.

## Diagnosis Contract

- Exactly 22 states and 934 full-set action scores: 18/4 states and 889/45
  actions by train/development partition.
- Dropped, extra, reconstructed, repeated-score, invalid-dimension,
  illegal-recorded, nonfinite-Q, missing/duplicate-state, ambiguous-action, and
  action-order mismatch counts must be zero.
- Stage 6.16 training run/step/use accounting, all six metric sections, all
  prediction digests, frozen hashes, false promotion/capability flags, and
  zero forbidden-operation counters must reproduce exactly.
- The 64 replay pair evaluations and 128 replay action-value evaluations must
  be reported separately and excluded from the 934 full-set score count.
- Report the result as static pipeline evidence only. Do not interpret ranking
  movement as causal proof or capability evidence.

## Prohibited Work

- Do not execute rollout, add or change labels/pairs/objectives, train,
  fine-tune, tune or search anything, select or modify a checkpoint, or change
  action/model semantics.
- Do not load locked test or the complete website bundle, run Arena, website
  Shadow, or website play; do not start model control, promote a checkpoint,
  or claim capability.

## Acceptance Criteria

- Every frozen input, Stage 6.16 metric/digest, v3 invariant, full-set action,
  ordering, rank, tie, aggregate, and 6+4+2 mapping independently reproduces.
- Exact 22/934, 18/4, 889/45, 64/128 replay, and zero-error accounting passes.
- The formal artifact is written once and a separate process reconstructs it
  exactly with every prohibited-operation counter at zero.
- Credential occurrences in new tracked/curated files are zero.
- Handoffs, focused tests, full tests, conventional commit, and push succeed
  before Stage 6.17 is accepted.
