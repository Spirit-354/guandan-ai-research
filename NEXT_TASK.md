# NEXT_TASK.md

## Single Next Stage

Run Stage 6.6: frozen corrective training smoke.

Train exactly one from-scratch 513+54 Q model using only the 24 frozen
pipeline-train pairs from Stage 6.5 and the frozen state-balanced pairwise
softplus objective. Keep the four pipeline-development pairs evaluation-only.

Do not run rollout, tune hyperparameters, select among checkpoints, load locked
test or any website dataset, run Arena, access the website, begin Shadow or
model-controlled play, promote a model, or claim capability. The old checkpoint
remains rejected, and the new checkpoint is pipeline-only regardless of its
pairwise metrics.

## Frozen Inputs

- Corrective dataset:
  `website_teacher_preference_corrective_dataset_v1.pth`, SHA-256
  `fad7ae18fea8b02cbc88ad4a8a7f8ecee298abe436ef589f5c88d66e42a32707`.
- Corrective dataset manifest:
  `website_teacher_preference_corrective_dataset_v1_manifest.json`, SHA-256
  `0a5dc4f60091338b65f86f83ad30ae55dc18c058ee8b07535a314510ad96ef0a`.
- Frozen teacher v6:
  `website_information_set_teacher_dataset_v6.pth`, SHA-256
  `a74416e6facb28a1bc64563eba90cb33d460dc9e59cc2109518da142465e15f8`.
- Frozen 18/4 split:
  `website_teacher_preference_split_v1.json`, SHA-256
  `5a15e514dc9bc51d77d300837151d9f1a49250f42885cc7940725bcbe4d35107`.
- Stage 6.4 confirmation:
  `website_teacher_preference_unpaired_train_confirmation_v1.json`, SHA-256
  `8e17377b5a1523d9f0a47af7218d687e062a3ade671c57f387eb4c1a0888cfae`.
- Old rejected checkpoint, unchanged:
  `models_website_teacher_preference_v1/website_teacher_preference_final.pth`,
  SHA-256
  `c54801a9db05100c2fe5a9bf610a64fc7c94dc2cd947dfaab115ff827bd90919`.
- Stage 6.1 Arena evidence, unchanged:
  `website_teacher_preference_arena_smoke20_v1.json`, SHA-256
  `aa45da9de202194102fe8d11e612ad3eb4b51177fd910b9a7948836afd2a1fe6`.
- Outputs must be unused before execution and named
  `models_website_teacher_preference_corrective_v1/website_teacher_preference_corrective_final.pth`
  and `website_teacher_preference_corrective_training_v1.json`.

## Training Contract

- Reload and validate the corrective dataset and manifest before training:
  28 total pairs, 24 train, four development, 18/4 games, 22 exact base
  samples, six exact corrective pairs, and zero excluded-pair leakage.
- Reuse `danzero_dmc.build_q_model` with unchanged 513-state and 54-action
  dimensions. Do not modify website action semantics or baseline logic.
- Use exactly CPU, seed `20260714`, 20 epochs, six states per batch, learning
  rate `0.001`, no initialization checkpoint, and no alternative recipe.
- Optimize the frozen state-balanced objective exactly: within each state,
  average its pairwise `softplus(Q_rejected-Q_preferred)` losses using frozen
  pair weights; then average equally across states in the batch.
- Train only the 18 pipeline-train states/24 pairs. Use the four development
  states/four pairs only for post-training evaluation.
- Report state-balanced loss, pair ranking accuracy, and mean margin for train
  and development, plus separate train base-pair and corrective-pair metrics.
  Record deterministic prediction digests and zero nonfinite values.
- Save exactly one final checkpoint. It must record all frozen input hashes,
  the fixed recipe, `checkpoint_promotion_allowed=false`, and
  `capability_claim_allowed=false`.
- Independently reload the checkpoint and reproduce every reported metric and
  prediction digest. Do not rerun training or choose a checkpoint.

## Required Work

1. Re-read the canonical handoffs; verify Git state, all seven frozen hashes,
   Stage 6.5 28/24/4 arithmetic, and output nonexistence.
2. Add the smallest state-balanced training path and focused tests for grouped
   weights, train/development isolation, fixed recipe, pair metrics, checkpoint
   metadata, and output refusal/atomicity.
3. Run exactly one fixed training job and write the checkpoint/report.
4. Independently reload and audit model dimensions, metadata, input hashes,
   train/development and base/corrective metrics, prediction digests, and zero
   forbidden operations.
5. Keep every frozen input and the old rejected checkpoint unchanged.
6. Update `PROJECT_STATE.md`, `EXPERIMENTS.md`, `NEXT_TASK.md`, and the durable
   progress document; run narrow regressions, credential and diff checks,
   commit, and push.

## Acceptance Criteria

- All seven frozen hashes remain unchanged; Stage 6.1 remains 0-20 with
  continuation false and the old checkpoint remains rejected.
- Exactly one fixed training run completes using only 18 train states/24 pairs;
  development training uses, extra targets, nonfinite losses or predictions,
  hyperparameter searches, and checkpoint selections are zero.
- The final report, independently reloaded checkpoint metrics, and prediction
  digests match exactly. The checkpoint schema and 513/54 dimensions match.
- Rollout, locked-test or website-dataset loads, Arena, website Shadow/play,
  model-controlled website actions, promotion, and capability claims are zero.
- Credential occurrences in new tracked/curated files are zero.
- Handoff updates, focused tests, independent audit, conventional commit, and
  push all succeed before the stage Goal is marked complete.

## Ready-to-Use Goal Prompt

请创建一个阶段 Goal：完成 Stage 6.6 frozen corrective training smoke。只用
Stage 6.5 的 18 个 pipeline-train state/24 个 pair，按冻结 state-balanced
pairwise softplus objective 从头训练一个 513+54 Q model；固定 CPU、seed
20260714、20 epochs、每 batch 六个 state、learning rate 0.001，不得尝试其他
配方或选择 checkpoint。四个 development state/pair 只能在训练后评估。不得
rollout、调参、加载 locked test/网站 dataset、运行 Arena、访问网站、运行
Shadow/对局、模型控制、提升或能力结论。独立重载复算、交接更新、验证、凭据
零命中、commit 和 push 全部成功后才能完成 Goal。
