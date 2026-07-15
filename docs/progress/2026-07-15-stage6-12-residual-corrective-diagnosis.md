# Stage 6.12 Frozen Residual Corrective Full-Legal-Set Diagnosis

Date: 2026-07-15

Status: completed; static pipeline diagnosis only, no capability claim.

## Scope

Stage 6.12 loaded the frozen Stage 6.11 checkpoint and scored every recorded
legal action from the same 22 teacher-v6 states. It preserved source order and
duplicate vectors, separately replayed the exact Stage 6.11 metric batch
shapes, and independently audited the result. No training, tuning, rollout,
Arena, locked-test or website data, website access, checkpoint change,
promotion, or capability path ran.

## Frozen Inputs

All 11 hashes in `NEXT_TASK.md` matched before and after the run, including:

- Stage 6.11 report/checkpoint:
  `307b92eca7aef2d7fa927dec71f1e2ccd8b87b71d2336c5630f39c24d0a176dd` and
  `cdb3c18948c9310c88f52789f2fd5a12326859ff653558a6aebe7eb569393105`.
- Corrective dataset v2/manifest:
  `40024f7c064f0ebb7999c4ac0f7bc85d77b759a23956cbe596756763d4009d4d` and
  `ce5141f6254218d9230b15117a88d3c5e6bd374839bcf5fc77b393e2599ec353`.
- Teacher v6/split:
  `a74416e6facb28a1bc64563eba90cb33d460dc9e59cc2109518da142465e15f8` and
  `5a15e514dc9bc51d77d300837151d9f1a49250f42885cc7940725bcbe4d35107`.
- Stage 6.9 confirmation and Stage 6.7 diagnosis:
  `352cd0dfe0a4c958ba0555b776326a2b58470a980aef461ed49d4c59a7474c7a` and
  `2b4359470e74f5eae28d6589477aca5f929ae6b5b88e094fa86209bf4328163d`.

## Full-Set Result

- Exactly 22 states and 934 action entries were scored once: 889 train and 45
  development. All eight duplicate vectors stayed in their original positions.
- Train teacher/behavior/other first-max top-1 counts: 12/0/6.
- Development teacher/behavior/other first-max top-1 counts: 1/0/3.
- Overall teacher/behavior/other first-max top-1 counts: 13/0/9.
- Pass top-1: 0/22.
- Overall mean/median teacher rank: 2.09/1.0.
- Nine states contain 24 action entries strictly above teacher: six train
  states and three held-out development states.
- Compared with Stage 6.7, teacher top-1 increased by two, residual states fell
  by two, and strictly-above entries fell from 28 to 24.

The six current train residual states are `13957:14`, `14077:10`,
`14038:12`, `13959:7`, `14025:20`, and `13872:4`. Development states
`13992:16`, `14074:9`, and `13871:9` remain held out from design.

## Corrective and Metric Reproduction

- Teacher outranked all six Stage 6.4 rejected actions and all four Stage 6.9
  residual actions; none remained full-set top-1.
- Teacher was full-set top-1 in four of the six Stage 6.4 states and three of
  the four Stage 6.9 states.
- The separate frozen-batch replay exactly reproduced train aggregate, train
  base, Stage 6.4, Stage 6.9, and development metrics and prediction digests.
- Replay accounting was 60 pair evaluations and 120 action-value evaluations,
  excluded from the 934 full-set action count.

## Output and Audit

- Curated diagnosis:
  `website_teacher_preference_residual_corrective_failure_diagnosis_v1.json`.
- SHA-256:
  `e8e12f4fd259bc0c2689100d08bdfb3b71662e29c8af0f1e1013fbc6e9573e9f`.
- A separate process reproduced every state rank, first-max tie, action hash,
  action-order digest, aggregate, metric digest, and 6+4 corrective mapping.
- All forbidden-operation counters were zero.

## Decision

Do not run Arena, train, promote, or claim capability. Audit only the existing
frozen source evidence for the six current pipeline-train top-1 actions. Keep
the three development residual states identity-only and do not execute a new
rollout in that audit stage.
