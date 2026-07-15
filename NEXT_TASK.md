# NEXT_TASK.md

## Single Next Stage

Run Stage 6.18: frozen three-train remaining-top1 evidence audit.

Stage 6.17 raised teacher full-set first-max top-1 to 16/22 and left only
three pipeline-train residual states plus the same three held-out development
states. Audit existing frozen evidence for the exact three train current-top1
actions before any new rollout, dataset, objective, or Arena decision. This is
an evidence-read and independent audit stage only; do not load or score a
model.

## Frozen Inputs

- Stage 6.17 diagnosis:
  `website_teacher_preference_remaining_corrective_failure_diagnosis_v1.json`,
  SHA-256
  `1757016ae33628cca075a9cdfc881cd49be7b63f1078ca3f7288f95c7fa00a68`.
- Stage 6.17 implementation:
  `website_teacher_preference_remaining_corrective_diagnosis.py`, SHA-256
  `9231c25d24ee773c0fc376c4e2bb55c6a746897e8d95be2a351fd0c0b6fa85e1`.
- Stage 6.13 evidence-audit pattern and evidence:
  `website_teacher_preference_residual_corrective_remaining_evidence_audit.py`,
  SHA-256
  `f49975ace9a3eefd6fa93fafb838463f0b4c2690438856214809ada9d6b31687`,
  and
  `website_teacher_preference_residual_corrective_remaining_evidence_audit_v1.json`,
  SHA-256
  `2dff04b2be010a10c3f3e77a144f98d1aeca89a885e21cc98be9c51868b53345`.
- Recursively freeze all 24 hashes recorded by Stage 6.17, including Stage
  6.16 report/checkpoint/implementation, corrective dataset v3/manifest,
  teacher v6, split, source train/development data, Stage 6.1 rejection, and
  all prior confirmation/equivalence evidence.
- The new curated output must be unused before construction:
  `website_teacher_preference_remaining_corrective_final_evidence_audit_v1.json`.

## Exact Targets

- Pipeline train, evidence may be inspected:
  - `14077:10`, current top-1 action index 0;
  - `14031:4`, current top-1 action index 2;
  - `14025:20`, current top-1 action index 2.
- Pipeline development, identity-only with zero source exposure or use:
  - `13992:16`;
  - `14074:9`;
  - `13871:9`.

## Required Work

1. Re-read all canonical handoffs; verify Git state, every frozen hash, the
   exact 3/3 target set, and the unused output path.
2. Reuse the Stage 6.13 evidence-audit pattern with the smallest necessary
   target-specific change. Reproduce each target by state, original action
   order/index, 54D action hash, teacher index/rank, top1 rank, and physical
   identity without loading the Stage 6.16 checkpoint or rescoring actions.
3. For train only, open and hash only source evidence files directly referenced
   by the three frozen teacher samples. Determine whether the exact teacher and
   current-top1 actions were source candidates and whether a direct complete
   paired comparison records mean/variance, advantage, confidence/lower bound,
   and both continuation-profile advantages.
4. Explicitly compare each current action identity with Stage 6.4, Stage 6.9,
   and Stage 6.14E actions. Do not transfer evidence between different action
   hashes. Preserve every frozen inconclusive classification.
5. Keep all three development targets identity-only: zero source-reference
   exposure, candidate inspection, evidence query, threshold/objective design
   use, or execution.
6. Write one small audit artifact and independently reconstruct it in a
   separate process. Update handoffs and progress documentation, run focused
   and full tests plus credential/diff checks, commit, and push.

## Classification Contract

- Classify each train target as exactly one of: direct supported
  teacher-over-current, direct supported current-over-teacher, direct
  inconclusive, candidate present without direct paired statistics, or source
  candidate absent.
- Existing evidence must pass the unchanged completeness, action identity,
  16-rollout, variance, advantage, positive-confidence, and dual-continuation
  requirements before it can be called supported.
- Missing, duplicate, extra, reconstructed, substituted, transferred, and
  ambiguous targets/actions must be zero. Unsupported labels must be zero.
- Any future manifest is non-executed and may contain only train cases still
  lacking sufficient direct evidence.

## Prohibited Work

- Do not load or score a model, run rollout, build a dataset or objective,
  train, fine-tune, tune, search, select or modify a checkpoint, or inspect
  development source evidence.
- Do not load locked test or the complete website bundle, run Arena, Shadow,
  or website play; do not start model control, promote, or claim capability.

## Acceptance Criteria

- All frozen hashes and exact 3/3 target identities reproduce, with development
  isolation and every classification/action-identity boundary independently
  audited.
- Only directly referenced train evidence is opened; supported/inconclusive/
  insufficient counts and any future manifest reproduce exactly.
- Model loading/scoring, rollout, dataset/objective/training/tuning/checkpoint,
  Arena, website, promotion, unsupported-label, and capability counters are
  all zero.
- Credential occurrences in new tracked/curated files are zero.
- Handoffs, focused tests, full tests, conventional commit, and push succeed
  before Stage 6.18 is accepted.
