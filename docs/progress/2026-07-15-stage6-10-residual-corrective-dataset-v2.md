# Stage 6.10 Frozen Residual Corrective Dataset Extension

Date: 2026-07-15

Status: completed; dataset-only evidence, no capability claim.

## Scope

Stage 6.10 preserved the frozen corrective dataset v1 and added only the four
Stage 6.9 pipeline-train teacher-over-residual comparisons that passed every
unchanged strong gate. The stage did not execute the objective or run rollout,
training, tuning, checkpoint work, Arena, locked test, website data, or website
activity.

## Frozen Inputs

- Stage 6.9 confirmation:
  `352cd0dfe0a4c958ba0555b776326a2b58470a980aef461ed49d4c59a7474c7a`.
- Corrective dataset v1:
  `fad7ae18fea8b02cbc88ad4a8a7f8ecee298abe436ef589f5c88d66e42a32707`.
- Corrective dataset v1 manifest:
  `0a5dc4f60091338b65f86f83ad30ae55dc18c058ee8b07535a314510ad96ef0a`.
- Stage 6.8 residual evidence audit:
  `676232033f07051670b4407f15aca9f3939d9754ac2dcf4d078957263a1e2a6b`.
- Teacher v6:
  `a74416e6facb28a1bc64563eba90cb33d460dc9e59cc2109518da142465e15f8`.
- Frozen 18/4 split:
  `5a15e514dc9bc51d77d300837151d9f1a49250f42885cc7940725bcbe4d35107`.
- Stage 6.4 confirmation:
  `8e17377b5a1523d9f0a47af7218d687e062a3ade671c57f387eb4c1a0888cfae`.

## Results

- All 22 embedded teacher samples retained exact per-sample and aggregate
  canonical hashes.
- All 28 v1 pair semantics and ordering were preserved. Only the three
  deterministic weight fields were recomputed.
- Four new train pairs were added: `14044:9`, `14038:12`, `14000:5`, and
  `14022:16`.
- Four inconclusive train cases added zero pairs: `13957:14`, `14077:10`,
  `13959:7`, and `14025:20`.
- Development targets `13992:16`, `14074:9`, and `13871:9` remained
  identity-only with zero action inspection and zero pair additions.
- The dataset contains 32 pairs across 22 states: 28 train across 18 states and
  four development across four states. Pair types are 22 base, six Stage 6.4
  corrective, and four Stage 6.9 residual corrective.
- Thirteen states have one pair, eight have two pairs weighted 0.5/0.5, and
  `14022:16` has three pairs weighted one-third each. Every state sum and both
  partition-normalized sums equal one.

## Outputs and Audit

- `website_teacher_preference_corrective_dataset_v2.pth`, SHA-256
  `40024f7c064f0ebb7999c4ac0f7bc85d77b759a23956cbe596756763d4009d4d`.
- `website_teacher_preference_corrective_dataset_v2_manifest.json`, SHA-256
  `ce5141f6254218d9230b15117a88d3c5e6bd374839bcf5fc77b393e2599ec353`.
- The formal outputs were built once. A separate process independently
  reconstructed the payload and manifest and matched every frozen hash,
  sample, preserved v1 semantic pair, new pair, exclusion/held-out key, count,
  weight, provenance record, and forbidden-operation counter.

## Decision

Freeze dataset v2 and its manifest. They are pipeline inputs only and do not
show improved offline capability. The next stage may run exactly one fixed,
from-scratch corrective training smoke; it must not run Arena or access the
website.
