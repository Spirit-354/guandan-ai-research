# Stage 6.17 Frozen Remaining-Top1 Corrective Full-Legal-Set Diagnosis

Date: 2026-07-15

Status: completed; static pipeline evidence only, no capability claim.

## Scope

Stage 6.17 loaded only the frozen Stage 6.16 checkpoint and scored every
recorded legal action from the same 22 teacher states once in original order.
It separately replayed the six frozen metric sections using their original
batch shapes. No rollout, label or objective change, training, tuning,
checkpoint change, locked test, complete website bundle, Arena, Shadow, or
website play ran.

## Frozen Inputs

- Stage 6.16 report/checkpoint/implementation:
  `cac3ecb0542a7f9aaac2654f73f4e3650422be7eb5990bf4c403f3f082145156`,
  `8407f897e36b45affc628fbd2fe68dc4c76a5085fad095511c8045bc73ec5aad`,
  and
  `8f3c74b272228cb0423aa192187d64028c4b7bce2f23dd74d12d811c55f76ded`.
- Stage 6.12 diagnosis evidence/implementation:
  `e8e12f4fd259bc0c2689100d08bdfb3b71662e29c8af0f1e1013fbc6e9573e9f`
  and
  `75af0c847a49484059c103fe12f8db1f4fb447cb04c2161ed1ffe913dea8e008`.
- All 19 hashes recursively frozen by Stage 6.16 reproduced exactly; 24 total
  frozen hashes were checked.

## Scoring and Replay Accounting

- Exactly 22 states and 934 recorded legal-action entries were scored once:
  18/4 states and 889/45 actions for train/development.
- All eight duplicate-vector source entries remained in original positions.
- Dropped, duplicate-state, reconstructed, repeated-score, invalid-dimension,
  illegal-recorded, nonfinite-Q, and action-order errors were zero.
- The separately accounted Stage 6.16 replay reproduced all six metric
  sections and prediction digests with 64 pair evaluations and 128
  action-value evaluations excluded from the 934 full-set count.

## Ranking Results

- Train teacher/behavior/other first-max top-1 counts are `15/0/3`.
- Development counts remain `1/0/3`; overall counts are `16/0/6`.
- Pass top-1 remains `0/22`.
- Overall mean/median teacher rank is `1.7273/1.0`.
- Six states contain 16 actions strictly above teacher: three train states
  with four actions and three development states with 12 actions.
- Relative to Stage 6.12, teacher top-1 increased by three, residual states
  fell by three, and strictly-above entries fell from 24 to 16.
- All 12 corrective actions are below teacher and none remains new top-1. All
  6 Stage 6.4, 4 Stage 6.9, and 2 Stage 6.14E corrective states now have
  teacher as first-max full-set top-1.

The remaining train residual states are `14077:10` top-1 index 0,
`14031:4` index 2, and `14025:20` index 2. Development states `13992:16`,
`14074:9`, and `13871:9` remain held out.

## Output and Audit

- Curated diagnosis:
  `website_teacher_preference_remaining_corrective_failure_diagnosis_v1.json`,
  SHA-256
  `1757016ae33628cca075a9cdfc881cd49be7b63f1078ca3f7288f95c7fa00a68`.
- Diagnosis implementation SHA-256:
  `9231c25d24ee773c0fc376c4e2bb55c6a746897e8d95be2a351fd0c0b6fa85e1`.
- A separate process reconstructed every input hash, action score/order/hash,
  rank, tie, aggregate, replay metric/digest, 6+4+2 mapping, and forbidden
  counter exactly.

## Decision

Do not run Arena or claim capability. First perform a separate frozen evidence
audit for only the three remaining train current-top1 actions. Keep all three
development targets identity-only and do not score a model or execute rollout
in that audit stage.
