# Stage 6.13 Frozen Remaining-Top1 Evidence Audit

Date: 2026-07-15

Status: completed; read-only existing-evidence audit, no capability claim.

## Scope

Stage 6.13 reproduced the six current pipeline-train top-1 actions and three
identity-only pipeline-development targets from the frozen Stage 6.12
diagnosis. It opened only the six rollout files directly referenced by train
teacher samples and classified existing evidence without loading or scoring a
model. No rollout, dataset/objective construction, training, tuning, Arena,
locked test, website dataset, website access, promotion, or capability path ran.

## Frozen Inputs

All 11 hashes in `NEXT_TASK.md` matched before and after the run, including:

- Stage 6.12 diagnosis:
  `e8e12f4fd259bc0c2689100d08bdfb3b71662e29c8af0f1e1013fbc6e9573e9f`.
- Stage 6.11 report/checkpoint:
  `307b92eca7aef2d7fa927dec71f1e2ccd8b87b71d2336c5630f39c24d0a176dd` and
  `cdb3c18948c9310c88f52789f2fd5a12326859ff653558a6aebe7eb569393105`.
- Corrective dataset v2/manifest:
  `40024f7c064f0ebb7999c4ac0f7bc85d77b759a23956cbe596756763d4009d4d` and
  `ce5141f6254218d9230b15117a88d3c5e6bd374839bcf5fc77b393e2599ec353`.
- Teacher v6/split:
  `a74416e6facb28a1bc64563eba90cb33d460dc9e59cc2109518da142465e15f8` and
  `5a15e514dc9bc51d77d300837151d9f1a49250f42885cc7940725bcbe4d35107`.
- Stage 6.9 confirmation and Stage 6.8 audit:
  `352cd0dfe0a4c958ba0555b776326a2b58470a980aef461ed49d4c59a7474c7a` and
  `676232033f07051670b4407f15aca9f3939d9754ac2dcf4d078957263a1e2a6b`.

## Target Reproduction and Isolation

- Exactly six train and three development targets reproduced.
- Every target matched state, original action index/order, 54D hash, teacher
  index/rank, and physical-card identity.
- Missing, duplicate, extra, reconstructed, substituted, and ambiguous target
  mappings were zero.
- The legacy `13872:4` source omitted legal-action metadata, so its physical
  identity was deterministically decoded from the exact frozen 54D physical
  action vector. No action was reconstructed or substituted.
- Development targets `13992:16`, `14074:9`, and `13871:9` remained
  identity-only. Source references and candidate evidence were not accessed.

## Existing Evidence Result

- `13957:14` index 17 and `13872:4` index 19 were not evaluated as source
  candidates.
- `14038:12` index 3 had both teacher and current top-1 source candidates but
  no direct paired comparison.
- `14077:10` index 0, `13959:7` index 5, and `14025:20` index 1 exactly match
  their Stage 6.9 residual actions. All three frozen direct comparisons remain
  inconclusive.
- The Stage 6.9 actions for `13957:14` and `14038:12` differ from the current
  top-1 actions and were explicitly not transferred.
- Supported teacher-over-current and current-over-teacher comparisons: 0/6 in
  both directions. All six cases remain evidence-insufficient.
- Only three cases lack an existing direct comparison and need a future
  confirmation: `13957:14`, `14038:12`, and `13872:4`. The three already
  inconclusive comparisons must not be rerun under the unchanged recipe.

## Output and Audit

- Curated output:
  `website_teacher_preference_residual_corrective_remaining_evidence_audit_v1.json`.
- SHA-256:
  `2dff04b2be010a10c3f3e77a144f98d1aeca89a885e21cc98be9c51868b53345`.
- Six directly referenced source files were opened and hashed; unrelated
  rollout evidence was not scanned.
- A separate process reproduced every target/source/action hash, physical
  identity, Stage 6.9 action-transfer boundary, classification, partition
  count, aggregate, isolation counter, and forbidden-operation counter.
- All forbidden-operation counters were zero.

## Decision

Do not run Arena, train, promote, or claim capability. Permit only a separate
frozen counterfactual confirmation for the three train actions that still lack
any direct comparison. Exclude the three already inconclusive train cases and
keep all development targets unexecuted.
