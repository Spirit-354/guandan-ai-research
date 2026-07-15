# NEXT_TASK.md

## Single Next Stage

Run Stage 6.12: frozen residual corrective full-legal-set diagnosis.

Use only the frozen Stage 6.11 checkpoint and the same 22 teacher-v6 states to
score every recorded legal action exactly once in original order. Diagnose
teacher rank and first-maximum top-1 coverage, including the four Stage 6.9
residual corrections. This is a static diagnosis only.

Do not run rollout, train or fine-tune, tune thresholds or hyperparameters,
select or modify a checkpoint, load locked test or any website dataset, run
Arena, access the website, begin Shadow or model-controlled play, promote a
model, or claim capability.

## Frozen Inputs

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
- Stage 6.9 confirmation remains the authority for the four residual actions:
  `website_teacher_preference_corrective_residual_train_confirmation_v1.json`,
  SHA-256
  `352cd0dfe0a4c958ba0555b776326a2b58470a980aef461ed49d4c59a7474c7a`.
- Stage 6.7 diagnosis is the frozen comparison baseline:
  `website_teacher_preference_corrective_failure_diagnosis_v1.json`, SHA-256
  `2b4359470e74f5eae28d6589477aca5f929ae6b5b88e094fa86209bf4328163d`.
- Stage 6.6 report/checkpoint and Stage 6.1 Arena conclusion remain frozen:
  `website_teacher_preference_corrective_training_v1.json`, SHA-256
  `baa97ccf71c237895a92f4cb8b36b9559cf3cabe45b4901b7481d9f50f4c0830`;
  `models_website_teacher_preference_corrective_v1/website_teacher_preference_corrective_final.pth`,
  SHA-256
  `8cb368c8c0ae3f8c41c577e055ddd4796cbaae8163720cc630a435aa25bc1a49`;
  `website_teacher_preference_arena_smoke20_v1.json`, SHA-256
  `aa45da9de202194102fe8d11e612ad3eb4b51177fd910b9a7948836afd2a1fe6`.
- The only new curated output is
  `website_teacher_preference_residual_corrective_failure_diagnosis_v1.json`;
  it must not exist before execution.

## Diagnostic Contract

- Validate every frozen hash. Reproduce the Stage 6.11 one-run, 60-step,
  28-train/4-development, zero-development-training conclusion and strict
  checkpoint metadata before scoring.
- Reload the same 22 frozen teacher samples and 18/4 split. Preserve all 934
  recorded legal-action entries in source order: 889 train and 45 development.
  Keep all eight duplicate 54D action vectors in their original positions.
- Score each of the 934 full-set entries exactly once with the Stage 6.11
  checkpoint. Do not reconstruct, deduplicate, drop, substitute, or reorder an
  action. Reject invalid dimensions, illegal recorded actions, and nonfinite Q
  values.
- For each state, record teacher and behavior action indices/hashes, all Q
  values in original order, first-maximum top-1 index/source, teacher rank with
  frozen tie semantics, pass top-1 status, and every action strictly above the
  teacher.
- Report overall and partitioned teacher/behavior/other first-max top-1 counts,
  mean/median teacher rank, pass top-1 count, states/actions above teacher, and
  exact comparison with the frozen Stage 6.7 diagnosis.
- Reproduce the six Stage 6.4 corrective actions and four Stage 6.9 residual
  corrective actions by exact state, original action index, 54D hash, and
  physical identity. Report teacher-versus-rejected margin and whether each
  teacher is full-set first-max top-1.
- Separately replay the exact Stage 6.11 metric batch shapes: train aggregate,
  train base, Stage 6.4 corrective, Stage 6.9 residual, and development
  aggregate. Account for 60 pair evaluations/120 action-value evaluations and
  exclude them from the 934 full-set scoring count. Reproduce every Stage 6.11
  metric and prediction digest exactly.
- In a separate process, independently recompute action order, every Q value,
  rank/tie/top-1 result, aggregate, comparison, corrective mapping, metric
  replay, prediction digest, and forbidden-operation counter.

## Required Work

1. Re-read the canonical handoffs; verify Git state, every frozen hash, and the
   output path is unused.
2. Add the smallest residual-corrective diagnosis path and focused tests for
   strict checkpoint/report loading, original action order and duplicates,
   first-max tie semantics, corrective mappings, metric replay, and output
   refusal.
3. Run preflight, execute the static diagnosis once, then independently reload
   and audit the curated output.
4. Keep every frozen input unchanged. Do not run rollout, training, Arena, or
   any website path regardless of diagnostic results.
5. Update `PROJECT_STATE.md`, `EXPERIMENTS.md`, `NEXT_TASK.md`, and the durable
   progress document; run narrow regressions, credential and diff checks,
   commit, and push.

## Acceptance Criteria

- All frozen hashes remain unchanged and the Stage 6.11 checkpoint/report
  contract reproduces exactly.
- Exactly 22 states and all 934 recorded legal-action entries are scored once;
  partition counts remain 889/45 and all eight duplicate vectors remain in
  original positions. Dropped, reconstructed, repeated-score,
  invalid-dimension, illegal-recorded, and nonfinite-Q counts are zero.
- Every teacher rank, tie, first-max source, pass result, action-above-teacher
  record, six Stage 6.4 mappings, and four Stage 6.9 residual mappings is
  reported and independently reproduced.
- The separate 60-pair/120-action metric replay exactly reproduces all Stage
  6.11 aggregate, pair-type, development metrics, and prediction digests, and
  is excluded from the 934 full-set score count.
- Rollout, training, fine-tuning, tuning, checkpoint selection/modification,
  locked-test or website-dataset loads, Arena, website Shadow/play,
  model-controlled website actions, promotion, and capability claims are zero.
- Credential occurrences in new tracked/curated files are zero.
- Handoff updates, focused tests, independent audit, conventional commit, and
  push all succeed before the Stage 6.12 Goal is marked complete.

## Ready-to-Use Goal Prompt

请创建一个阶段 Goal：完成 Stage 6.12 frozen residual corrective
full-legal-set diagnosis。只使用冻结的 Stage 6.11 checkpoint，在相同 22 个
teacher-v6 状态上按原始顺序各评分一次全部 934 个 recorded legal action，保留
8 个重复 action vector，报告 teacher rank/top-1、pass、teacher 以上 action、
6 个 Stage 6.4 和 4 个 Stage 6.9 纠偏动作结果；另行复现 Stage 6.11 的
60-pair/120-action 指标批次并排除在 934 计数之外。不得 rollout、训练、调参、
修改 checkpoint、加载 locked test/网站 dataset、运行 Arena、访问网站、
Shadow、模型控制、提升或能力结论。独立审计、交接更新、验证、凭据零命中、
commit 和 push 全部成功后，才能完成 Goal。
