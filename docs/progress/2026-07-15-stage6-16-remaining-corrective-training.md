# Stage 6.16 Frozen Remaining-Top1 Corrective Training Smoke

Date: 2026-07-15

Status: completed; pipeline-only training evidence, no capability claim.

## Scope

Stage 6.16 executed exactly one deterministic from-scratch CPU training smoke
on frozen corrective dataset v3. Only the 18 pipeline-train states and 30
train pairs entered gradients. Four pipeline-development states and pairs were
evaluation-only. No rollout, label or objective change, fine-tuning, tuning,
checkpoint selection, full-legal-set diagnosis, Arena, locked test, complete
website bundle, Shadow, or website play ran.

## Frozen Inputs and Recipe

- Corrective dataset v3:
  `71e90241170882dd97893e71fbe0694368af96525737b55370cd0a60e098ce6f`.
- Corrective manifest v3:
  `c9b25d75da0fc5966e1f29bcbd50dd471971e16fc9f4a368cda5b5ba2f8d822d`.
- Stage 6.15 builder:
  `df44cdc1c1e45ddea310324393b2ec0d1693523480b3f78ef4bf70fd369a8d97`.
- Stage 6.11 recipe authority and implementation:
  `307b92eca7aef2d7fa927dec71f1e2ccd8b87b71d2336c5630f39c24d0a176dd`
  and
  `cc1c6263644635da01822f9ce8f231610b997d7ddbac932ba19efb24a905f00c`.
- All 14 hashes recursively frozen by dataset v3 also reproduced exactly.
- Fixed recipe: CPU, seed `20260714`, 20 epochs, six complete states per
  batch, learning rate `0.001`, no initialization checkpoint, and unchanged
  state-balanced pairwise softplus.

## Training Accounting

- Training runs: 1.
- Optimizer steps: 60.
- Train state epoch uses: 360.
- Train pair epoch uses: 600.
- Development gradient uses, extra targets, fine-tuning runs, searches,
  tuning, initialization loads, and checkpoint selections: 0.
- Nonfinite training losses and prediction values: 0.

## Final Pipeline Metrics

- Train aggregate: state-balanced loss `0.0063847274`, pair accuracy `1.0`,
  mean margin `11.2822`.
- Train base pairs: accuracy `1.0`, mean margin `13.8454`.
- Stage 6.4 pairs: accuracy `1.0`, mean margin `8.2260`.
- Stage 6.9 pairs: accuracy `1.0`, mean margin `4.5802`.
- Stage 6.14E pairs: accuracy `1.0`, mean margin `10.7853`.
- Development aggregate: state-balanced loss `0.0100213728`, pair accuracy
  `1.0`, mean margin `12.8601`.

These are frozen-pair pipeline diagnostics only. They do not establish
full-legal-set ranking quality or offline capability.

## Outputs and Audit

- Curated report:
  `website_teacher_preference_remaining_corrective_training_v1.json`, SHA-256
  `cac3ecb0542a7f9aaac2654f73f4e3650422be7eb5990bf4c403f3f082145156`.
- Ignored checkpoint:
  `models_website_teacher_preference_remaining_corrective_v1/website_teacher_preference_remaining_corrective_final.pth`,
  SHA-256
  `8407f897e36b45affc628fbd2fe68dc4c76a5085fad095511c8045bc73ec5aad`.
- Training implementation SHA-256:
  `8f3c74b272228cb0423aa192187d64028c4b7bce2f23dd74d12d811c55f76ded`.
- A separate process reloaded the exact checkpoint and reproduced every
  aggregate and pair-source metric and prediction digest. Frozen hashes,
  dataset invariants, training accounting, and all forbidden-operation
  counters remained exact.

## Decision

Keep the checkpoint pipeline-only, unpromoted, and ineligible for capability
claims. Before any Arena, run a separate frozen static full-legal-set ranking
diagnosis across the same 22 teacher states and 934 recorded action entries.
Do not train or tune in that diagnosis stage.
