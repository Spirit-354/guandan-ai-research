# NEXT_TASK.md

## Single Next Stage

Run Stage 6.16: frozen remaining-top1 corrective training smoke.

Stage 6.15 froze corrective dataset v3 after preserving all 32 v2 pair
semantics and adding only the two Stage 6.14E-supported pipeline-train pairs.
Run exactly one fixed, deterministic, from-scratch CPU training smoke on that
dataset. This stage is training and independent checkpoint audit only; do not
run a full-legal-set diagnosis or Arena.

## Frozen Inputs and Recipe

- Corrective dataset v3:
  `website_teacher_preference_corrective_dataset_v3.pth`, SHA-256
  `71e90241170882dd97893e71fbe0694368af96525737b55370cd0a60e098ce6f`.
- Corrective dataset v3 manifest:
  `website_teacher_preference_corrective_dataset_v3_manifest.json`, SHA-256
  `c9b25d75da0fc5966e1f29bcbd50dd471971e16fc9f4a368cda5b5ba2f8d822d`.
- Stage 6.15 builder:
  `website_teacher_preference_corrective_dataset_v3.py`, SHA-256
  `df44cdc1c1e45ddea310324393b2ec0d1693523480b3f78ef4bf70fd369a8d97`.
- Stage 6.11 fixed-recipe authority:
  `website_teacher_preference_residual_corrective_training_v1.json`, SHA-256
  `307b92eca7aef2d7fa927dec71f1e2ccd8b87b71d2336c5630f39c24d0a176dd`.
- Stage 6.11 implementation:
  `website_teacher_preference_residual_corrective_training.py`, SHA-256
  `cc1c6263644635da01822f9ce8f231610b997d7ddbac932ba19efb24a905f00c`.
- Recursively freeze the teacher v6, 18/4 split, v1/v2 corrective datasets and
  manifests, Stage 6.4/6.9/6.14E confirmations, and all hashes recorded by the
  accepted v3 manifest.
- Fixed recipe: CPU, seed `20260714`, 20 epochs, six complete states per batch,
  learning rate `0.001`, no initialization checkpoint, unchanged
  state-balanced pairwise `softplus(Q_rejected-Q_preferred)` objective.
- New report and final-checkpoint paths must be unused before the single run.

## Required Work

1. Re-read all canonical handoffs; verify Git state, every frozen hash, the v3
   34/30/4 pair contract, exact provenance and weights, and unused outputs.
2. Reuse the Stage 6.11 implementation and audit pattern with the smallest
   necessary v3-specific wrapper/change. Do not alter architecture, optimizer,
   batching, seed, epochs, learning rate, initialization, or objective.
3. Train exactly once from scratch using only all 18 pipeline-train states and
   30 train pairs. Keep all four pipeline-development states/pairs strictly
   evaluation-only.
4. Write one curated report and one ignored final checkpoint, then reload the
   checkpoint in a separate process and independently reproduce all metrics
   and prediction digests.
5. Update `PROJECT_STATE.md`, `EXPERIMENTS.md`, `NEXT_TASK.md`, and the durable
   progress document; run focused and full tests plus credential and diff
   checks; commit and push.

## Run Contract

- Exactly one training run, 20 epochs, 60 optimizer steps, 360 train-state
  epoch uses, and 600 train-pair epoch uses.
- Gradient inputs are exactly the 18 train states and 30 train pairs. All four
  development states/pairs have zero gradient uses and are evaluated only
  after training.
- Report aggregate train/development metrics and separate train metrics for 18
  base pairs, six Stage 6.4 pairs, four Stage 6.9 pairs, and two Stage 6.14E
  pairs.
- Nonfinite losses or predictions, missing/duplicate states or pairs, and
  frozen invariant mismatches must fail closed.
- The single final checkpoint is pipeline-only, unpromoted, ineligible for
  capability claims, and must not be selected against alternatives.

## Prohibited Work

- Do not run rollout, add or change labels/pairs, define or tune an objective,
  fine-tune, search any hyperparameter or threshold, initialize from a prior
  checkpoint, run more than one training configuration, or select a checkpoint.
- Do not load locked test or the complete website bundle, run a full-legal-set
  diagnosis, Arena, website Shadow, or website play; do not start model control,
  promote a checkpoint, or claim capability.

## Acceptance Criteria

- Every frozen input hash and every v3 sample, pair, split, provenance,
  exclusion, and weight invariant match before and after training.
- The exact one-run/20-epoch/60-step/360-state-use/600-pair-use contract passes,
  with zero development gradient use and zero prohibited extra work.
- The run completes with finite metrics for aggregate train/development and all
  four train pair-source groups.
- A separate process reloads the exact final checkpoint and reproduces every
  reported metric and prediction digest.
- Credential occurrences in new tracked/curated files are zero.
- Handoffs, focused tests, full tests, conventional commit, and push succeed
  before Stage 6.16 is accepted.
