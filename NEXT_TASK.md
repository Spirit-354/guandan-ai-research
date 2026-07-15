# NEXT_TASK.md

## Single Next Stage

Run Stage 6.13: frozen remaining-top1 evidence audit.

Use the frozen Stage 6.12 diagnosis to reproduce the six current
pipeline-train first-maximum top-1 actions that still outrank teacher, then
inspect only their directly referenced existing frozen counterfactual evidence.
Keep the three pipeline-development targets identity-only. This is a read-only
evidence audit; do not score a model or execute a rollout.

Do not train or fine-tune, tune thresholds or hyperparameters, construct a
dataset or objective, select or modify a checkpoint, load locked test or any
website dataset, run Arena, access the website, begin Shadow or model-controlled
play, promote a model, or claim capability.

## Frozen Inputs

- Stage 6.12 diagnosis:
  `website_teacher_preference_residual_corrective_failure_diagnosis_v1.json`,
  SHA-256
  `e8e12f4fd259bc0c2689100d08bdfb3b71662e29c8af0f1e1013fbc6e9573e9f`.
- Stage 6.11 report and ignored checkpoint:
  `website_teacher_preference_residual_corrective_training_v1.json`, SHA-256
  `307b92eca7aef2d7fa927dec71f1e2ccd8b87b71d2336c5630f39c24d0a176dd`;
  `models_website_teacher_preference_residual_corrective_v1/website_teacher_preference_residual_corrective_final.pth`,
  SHA-256
  `cdb3c18948c9310c88f52789f2fd5a12326859ff653558a6aebe7eb569393105`.
- Corrective dataset v2 and manifest:
  `website_teacher_preference_corrective_dataset_v2.pth`, SHA-256
  `40024f7c064f0ebb7999c4ac0f7bc85d77b759a23956cbe596756763d4009d4d`;
  `website_teacher_preference_corrective_dataset_v2_manifest.json`, SHA-256
  `ce5141f6254218d9230b15117a88d3c5e6bd374839bcf5fc77b393e2599ec353`.
- Frozen teacher v6 and 18/4 split:
  `website_information_set_teacher_dataset_v6.pth`, SHA-256
  `a74416e6facb28a1bc64563eba90cb33d460dc9e59cc2109518da142465e15f8`;
  `website_teacher_preference_split_v1.json`, SHA-256
  `5a15e514dc9bc51d77d300837151d9f1a49250f42885cc7940725bcbe4d35107`.
- Stage 6.9 confirmation and Stage 6.8 evidence audit:
  `website_teacher_preference_corrective_residual_train_confirmation_v1.json`,
  SHA-256
  `352cd0dfe0a4c958ba0555b776326a2b58470a980aef461ed49d4c59a7474c7a`;
  `website_teacher_preference_corrective_residual_evidence_audit_v1.json`,
  SHA-256
  `676232033f07051670b4407f15aca9f3939d9754ac2dcf4d078957263a1e2a6b`.
- Stage 6.7 diagnosis and Stage 6.1 Arena conclusion remain frozen:
  `website_teacher_preference_corrective_failure_diagnosis_v1.json`, SHA-256
  `2b4359470e74f5eae28d6589477aca5f929ae6b5b88e094fa86209bf4328163d`;
  `website_teacher_preference_arena_smoke20_v1.json`, SHA-256
  `aa45da9de202194102fe8d11e612ad3eb4b51177fd910b9a7948836afd2a1fe6`.
- The only new curated output is
  `website_teacher_preference_residual_corrective_remaining_evidence_audit_v1.json`;
  it must not exist before execution.

## Audit Contract

- Validate every frozen hash. Reproduce the Stage 6.12 22-state/934-action,
  13/0/9 teacher/behavior/other top-1, zero-pass-top1, and zero-forbidden-
  operation conclusion without loading or scoring a model.
- Reproduce exactly six pipeline-train targets by state, original action index,
  54D action hash, action-order digest, teacher index/rank, and physical-card
  identity: `13957:14` index 17, `14077:10` index 0, `14038:12` index 3,
  `13959:7` index 5, `14025:20` index 1, and `13872:4` index 19.
- Reproduce exactly three pipeline-development targets by identity only:
  `13992:16` index 7, `14074:9` index 9, and `13871:9` index 9. Do not open
  their source references, inspect candidate evidence, or use them for rule,
  threshold, objective, or confirmation design.
- Open only the source evidence files directly referenced by the six train
  teacher samples. Record every opened path and SHA-256. Do not scan unrelated
  rollout evidence.
- For each train target, map teacher and current top-1 to the frozen source
  legal-action order and physical metadata. Classify whether the top-1 was
  absent, present but unevaluated, evaluated without a direct paired
  teacher-versus-top1 comparison, or supported in either direction under the
  already frozen confidence/variance/two-profile gates.
- Existing Stage 6.9 results may be recorded as provenance, but must not be
  reinterpreted as evidence for a different current top-1 action. Do not weaken
  thresholds, infer missing pairwise confidence, or turn an unsupported action
  into a label.
- In a separate process, independently recompute every input/action hash,
  target mapping, source-file hash, evidence classification, partition count,
  aggregate, development-isolation counter, and forbidden-operation counter.

## Required Work

1. Re-read the canonical handoffs; verify Git state, every frozen hash, and the
   output path is unused.
2. Add the smallest remaining-top1 evidence-audit path and focused tests for
   exact target identity, original action index/duplicates, direct-evidence
   classification, development isolation, and output refusal.
3. Run preflight, execute the read-only audit once, then independently reload
   and reproduce the curated output in a separate process.
4. Keep every frozen input unchanged. Do not score a model, run rollout,
   construct a dataset/objective, train, run Arena, or access any website path
   regardless of audit results.
5. Update `PROJECT_STATE.md`, `EXPERIMENTS.md`, `NEXT_TASK.md`, and the durable
   progress document; run narrow regressions, credential and diff checks,
   commit, and push.

## Acceptance Criteria

- All frozen hashes remain unchanged and the Stage 6.12 conclusion reproduces
  exactly without model scoring.
- Exactly six train and three identity-only development targets reproduce with
  zero missing, duplicate, extra, reconstructed, substituted, or ambiguous
  mappings.
- Only directly referenced train source files are opened and hashed. Every
  train evidence classification is explicit; unsupported or inconclusive
  comparisons add zero labels.
- Development source-reference exposure, candidate inspection, threshold or
  objective-design use, and confirmation execution are all zero.
- Model scoring, rollout, dataset/objective construction, training,
  fine-tuning, tuning, checkpoint selection/modification, locked-test or
  website-dataset loads, Arena, website Shadow/play, model-controlled website
  actions, promotion, and capability claims are zero.
- Credential occurrences in new tracked/curated files are zero.
- Handoff updates, focused tests, independent audit, conventional commit, and
  push all succeed before the Stage 6.13 Goal is marked complete.

## Ready-to-Use Goal Prompt

请创建一个阶段 Goal：完成 Stage 6.13 frozen remaining-top1 evidence audit。
只复现 Stage 6.12 中仍严格高于 teacher 的 6 个 pipeline-train 当前 top-1
动作，并只审计这些 train 样本直接引用的已有冻结反事实证据；3 个
pipeline-development 目标只保留身份，不查看来源证据。不得模型评分、
rollout、构造 dataset/objective、训练、调参、修改 checkpoint、加载 locked
test/网站 dataset、运行 Arena、访问网站、Shadow、模型控制、提升或能力结论。
独立审计、交接更新、验证、凭据零命中、commit 和 push 全部成功后，才能完成
Goal。
