# NEXT_TASK.md

## Single Next Stage

Run Stage 6.11: frozen residual corrective training smoke.

Use only the frozen Stage 6.10 corrective dataset v2 and execute exactly one
fixed, from-scratch CPU training run with the unchanged Stage 6.6
state-balanced pairwise softplus recipe. Train on the 18 pipeline-train states
and 28 train pairs only. Keep the four pipeline-development states and four
development pairs evaluation-only.

Do not run rollout, fine-tune from any checkpoint, tune thresholds or
hyperparameters, select among checkpoints, load locked test or any website
dataset, run a full-legal-set diagnosis or Arena, access the website, begin
Shadow or model-controlled play, promote a model, or claim capability.

## Frozen Inputs

- Corrective dataset v2 and manifest:
  `website_teacher_preference_corrective_dataset_v2.pth`, SHA-256
  `40024f7c064f0ebb7999c4ac0f7bc85d77b759a23956cbe596756763d4009d4d`;
  `website_teacher_preference_corrective_dataset_v2_manifest.json`, SHA-256
  `ce5141f6254218d9230b15117a88d3c5e6bd374839bcf5fc77b393e2599ec353`.
- Stage 6.6 fixed-recipe authority:
  `website_teacher_preference_corrective_training_v1.json`, SHA-256
  `baa97ccf71c237895a92f4cb8b36b9559cf3cabe45b4901b7481d9f50f4c0830`.
- Corrective dataset v1 and manifest remain frozen provenance inputs:
  `website_teacher_preference_corrective_dataset_v1.pth`, SHA-256
  `fad7ae18fea8b02cbc88ad4a8a7f8ecee298abe436ef589f5c88d66e42a32707`;
  `website_teacher_preference_corrective_dataset_v1_manifest.json`, SHA-256
  `0a5dc4f60091338b65f86f83ad30ae55dc18c058ee8b07535a314510ad96ef0a`.
- Teacher v6 and frozen 18/4 split:
  `website_information_set_teacher_dataset_v6.pth`, SHA-256
  `a74416e6facb28a1bc64563eba90cb33d460dc9e59cc2109518da142465e15f8`;
  `website_teacher_preference_split_v1.json`, SHA-256
  `5a15e514dc9bc51d77d300837151d9f1a49250f42885cc7940725bcbe4d35107`.
- Stage 6.9 residual confirmation:
  `website_teacher_preference_corrective_residual_train_confirmation_v1.json`,
  SHA-256
  `352cd0dfe0a4c958ba0555b776326a2b58470a980aef461ed49d4c59a7474c7a`.
- The new curated report must be
  `website_teacher_preference_residual_corrective_training_v1.json`. The new
  ignored checkpoint must be
  `models_website_teacher_preference_residual_corrective_v1/website_teacher_preference_residual_corrective_final.pth`.
  Neither output may exist before execution.

## Training Contract

- Independently reload dataset v2 and reproduce all 22 teacher sample hashes,
  all 28 preserved v1 pair semantic hashes, all four Stage 6.9 residual pair
  hashes, the 32/28/4 pair accounting, the unchanged 18/4 state split, every
  state-balanced weight, both partition-normalized sums, all provenance, and
  every zero forbidden-operation counter.
- Freeze the Stage 6.6 recipe exactly: CPU, seed `20260714`, 20 epochs, six
  states per batch, learning rate `0.001`, no initialization checkpoint, and
  the existing `danzero_dmc.build_q_model` 513+54 architecture.
- Run exactly one training job from scratch. Each optimizer batch must group
  complete states and evaluate the frozen objective
  `softplus(Q_rejected-Q_preferred)` with the recorded within-state pair
  weights. With 18 train states, the run must complete exactly 60 optimizer
  steps.
- Use only the 18 pipeline-train states and 28 train pairs for gradients. The
  four pipeline-development states/pairs may be evaluated only after training;
  development training uses must remain zero.
- Record deterministic train and development state-balanced loss, pair
  accuracy, mean margin, and prediction digest. Report train metrics separately
  for the 18 base pairs, six Stage 6.4 corrective pairs, and four Stage 6.9
  residual corrective pairs.
- Save only the final checkpoint from the one frozen run. Record every frozen
  input hash, the exact recipe, architecture dimensions, false promotion and
  capability flags, and zero tuning/selection counts.
- In a separate process, reload the checkpoint and independently reproduce all
  train/development aggregate and pair-type metrics plus prediction digests.
  Do not use those metrics to tune, select, or modify the checkpoint.

## Required Work

1. Re-read the canonical handoffs; verify Git state, every frozen hash, and both
   output paths are unused.
2. Add the smallest v2 training path and focused tests for loader invariants,
   state-grouped weighting, 28-train/4-development isolation, fixed recipe,
   output refusal, and checkpoint metadata.
3. Run preflight before training. Execute the formal training job exactly once,
   then independently reload and audit the final checkpoint/report.
4. Keep all frozen inputs unchanged. Do not run rollout, diagnosis, Arena, or
   any website path regardless of metrics.
5. Update `PROJECT_STATE.md`, `EXPERIMENTS.md`, `NEXT_TASK.md`, and the durable
   progress document; run narrow regressions, credential and diff checks,
   commit, and push.

## Acceptance Criteria

- All frozen hashes and all Stage 6.10 dataset invariants reproduce exactly.
- Exactly one from-scratch training run uses only 18 train states and 28 train
  pairs with seed `20260714`, 20 epochs, six states per batch, learning rate
  `0.001`, and exactly 60 optimizer steps.
- Development training uses, extra targets, fine-tuning, hyperparameter or
  threshold searches, and checkpoint selections are zero.
- The final report records aggregate and base/Stage-6.4/Stage-6.9 residual
  train metrics plus development metrics. All values are finite and an
  independent process exactly reproduces every metric and prediction digest.
- Rollout, locked-test or website-dataset loads, full-set diagnosis, Arena,
  website Shadow/play, model-controlled website actions, promotion, and
  capability claims are zero.
- Credential occurrences in new tracked/curated files are zero.
- Handoff updates, focused tests, independent audit, conventional commit, and
  push all succeed before the Stage 6.11 Goal is marked complete.

## Ready-to-Use Goal Prompt

请创建一个阶段 Goal：完成 Stage 6.11 frozen residual corrective training
smoke。只使用冻结的 corrective dataset v2，在 CPU 上按固定 seed 20260714、
20 epochs、每批 6 个完整状态、学习率 0.001，从头执行恰好一次
state-balanced pairwise softplus 训练；只允许 18 个 train 状态和 28 个 train
pair 进入梯度，4 个 development pair 仅评估，完成 60 个 optimizer steps。
不得 rollout、fine-tune、调参、选择 checkpoint、加载 locked test 或网站
dataset、运行诊断/Arena、访问网站、Shadow、模型控制、提升或能力结论。独立
进程精确复现全部指标和 digest，交接更新、验证、凭据零命中、commit 和 push
全部成功后，才能完成 Goal。
