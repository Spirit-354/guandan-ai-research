# Stage 6.11 Frozen Residual Corrective Training Smoke

Date: 2026-07-15

Status: completed; pipeline-only evidence, no capability claim.

## Scope

Stage 6.11 executed exactly one fixed, from-scratch CPU training smoke on the
frozen Stage 6.10 corrective dataset v2. Only 18 pipeline-train states and 28
train pairs entered gradients. Four pipeline-development states and pairs were
evaluation-only. No rollout, fine-tuning, tuning, checkpoint selection,
full-legal-set diagnosis, Arena, locked test, website dataset, or website path
ran.

## Frozen Inputs

- Corrective dataset v2:
  `40024f7c064f0ebb7999c4ac0f7bc85d77b759a23956cbe596756763d4009d4d`.
- Corrective dataset v2 manifest:
  `ce5141f6254218d9230b15117a88d3c5e6bd374839bcf5fc77b393e2599ec353`.
- Stage 6.6 fixed-recipe authority:
  `baa97ccf71c237895a92f4cb8b36b9559cf3cabe45b4901b7481d9f50f4c0830`.
- Corrective dataset v1 and manifest:
  `fad7ae18fea8b02cbc88ad4a8a7f8ecee298abe436ef589f5c88d66e42a32707` and
  `0a5dc4f60091338b65f86f83ad30ae55dc18c058ee8b07535a314510ad96ef0a`.
- Teacher v6 and frozen split:
  `a74416e6facb28a1bc64563eba90cb33d460dc9e59cc2109518da142465e15f8` and
  `5a15e514dc9bc51d77d300837151d9f1a49250f42885cc7940725bcbe4d35107`.
- Stage 6.9 residual confirmation:
  `352cd0dfe0a4c958ba0555b776326a2b58470a980aef461ed49d4c59a7474c7a`.

## Fixed Run

- Device: CPU.
- Seed: `20260714`.
- Epochs: 20.
- Complete states per batch: 6.
- Learning rate: `0.001`.
- Initialization checkpoint: none.
- Objective: unchanged state-balanced pairwise softplus.
- Training runs: 1.
- Optimizer steps: 60.
- Train state/pair epoch uses: 360/560.
- Development training uses, extra targets, fine-tuning, searches, and
  checkpoint selections: 0.

## Metrics

- Train aggregate: state-balanced loss `0.0000278473`, pair accuracy `1.0`,
  mean margin `21.6998`.
- Train base pairs: accuracy `1.0`, mean margin `24.6659`.
- Stage 6.4 corrective pairs: accuracy `1.0`, mean margin `19.7933`.
- Stage 6.9 residual pairs: accuracy `1.0`, mean margin `11.2119`.
- Development aggregate: state-balanced loss `0.0004767285`, pair accuracy
  `1.0`, mean margin `23.5365`.
- Nonfinite training losses and prediction values: 0.

These are pairwise pipeline diagnostics only. They do not establish full-set
ranking quality or offline capability.

## Outputs and Audit

- `website_teacher_preference_residual_corrective_training_v1.json`, SHA-256
  `307b92eca7aef2d7fa927dec71f1e2ccd8b87b71d2336c5630f39c24d0a176dd`.
- Ignored checkpoint
  `models_website_teacher_preference_residual_corrective_v1/website_teacher_preference_residual_corrective_final.pth`,
  SHA-256
  `cdb3c18948c9310c88f52789f2fd5a12326859ff653558a6aebe7eb569393105`.
- A separate process reloaded the checkpoint and exactly reproduced all
  aggregate and pair-type metrics and prediction digests. Frozen hashes and
  dataset invariants remained exact, and all forbidden-operation counters were
  zero.

## Decision

Keep the checkpoint pipeline-only and unpromoted. Before any Arena, run a
separate frozen full-legal-set diagnosis across the same 22 states and 934
recorded actions. Do not train or tune in that diagnosis stage.
