# Stage 6.15 Frozen Remaining-Top1 Corrective Dataset Extension

Date: 2026-07-15

Status: completed; dataset-only evidence, no capability claim.

## Scope

Stage 6.15 preserved all 32 Stage 6.10 v2 pair semantics and added only the
two Stage 6.14E pipeline-train teacher-over-current-top1 comparisons that
passed every frozen directional gate. The stage reconstructed deterministic
state-balanced weights and did not execute the objective or run rollout,
model scoring, training, tuning, checkpoint work, Arena, locked test, complete
website data, Shadow, or website play.

## Frozen Inputs

- Stage 6.14E confirmation:
  `450e89f780a33dd543f49f029e735f7fb32e11cd657163c52e6a4301d21f7eb5`.
- Stage 6.14E formal wrapper:
  `972b67ed585e9a96f9e8be55b70d0b6585a7e499f6dc692c2861d5e636b9e55d`.
- Corrective dataset v2:
  `40024f7c064f0ebb7999c4ac0f7bc85d77b759a23956cbe596756763d4009d4d`.
- Corrective dataset v2 manifest:
  `ce5141f6254218d9230b15117a88d3c5e6bd374839bcf5fc77b393e2599ec353`.
- All recursively frozen teacher, split, source, audit, diagnosis,
  confirmation, Arena-rejection, and parallel-equivalence hashes reproduced.

## Results

- All 22 embedded teacher samples remained exact.
- All 32 v2 pairs retained exact order and semantics. Only
  `within_state_pair_weight`, `partition_state_weight`, and
  `partition_normalized_pair_weight` were recomputed.
- Exactly two train pairs were added:
  `remaining_corrective:13957:14:teacher_vs_current_top1` for action index 17
  and `remaining_corrective:14038:12:teacher_vs_current_top1` for action index
  3.
- `13872:4` index 19, the three previously inconclusive train cases, and all
  three development cases added zero pairs.
- The dataset contains 34 pairs across the unchanged 22 states: 30 train pairs
  across 18 states and four evaluation-only development pairs across four
  states. Provenance counts are 22 base, six Stage 6.4, four Stage 6.9, and two
  Stage 6.14E pairs.
- Thirteen states have one pair, six have two pairs, and three have three
  pairs. Every within-state weight sum and both partition-normalized sums equal
  one.

## Outputs and Audit

- `website_teacher_preference_corrective_dataset_v3.pth`, SHA-256
  `71e90241170882dd97893e71fbe0694368af96525737b55370cd0a60e098ce6f`.
- `website_teacher_preference_corrective_dataset_v3_manifest.json`, SHA-256
  `c9b25d75da0fc5966e1f29bcbd50dd471971e16fc9f4a368cda5b5ba2f8d822d`.
- Builder SHA-256:
  `df44cdc1c1e45ddea310324393b2ec0d1693523480b3f78ef4bf70fd369a8d97`.
- The formal outputs were written once. A separate process reloaded and
  reconstructed every frozen hash, embedded sample, preserved v2 pair, new
  action identity, metric, provenance field, exclusion, weight, output hash,
  and forbidden-operation counter exactly.

## Decision

Freeze dataset v3 and its manifest as pipeline-only inputs. The next stage may
run exactly one fixed, from-scratch CPU training smoke using the 18 train
states and 30 train pairs, with the four development pairs evaluation-only.
It must not tune, diagnose full legal sets, run Arena, or access the website.
