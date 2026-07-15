# NEXT_TASK.md

## Single Next Stage

Run Stage 6.14: frozen three-new-top1 counterfactual confirmation.

Execute only the three pipeline-train current top-1 actions that Stage 6.13
proved still lack any direct teacher-versus-current-top1 comparison:
`13957:14` index 17, `14038:12` index 3, and `13872:4` index 19. Apply the
unchanged Stage 6.9 paired information-set recipe and strong directional gates.

Do not rerun the already inconclusive `14077:10`, `13959:7`, or `14025:20`
comparisons. Keep all three pipeline-development targets unexecuted. Do not
construct a dataset or objective, train or fine-tune, tune any threshold or
hyperparameter, load locked test, score a model checkpoint, run Arena, access
the website, begin Shadow or model-controlled play, promote a model, or claim
capability.

## Frozen Inputs

- Stage 6.13 evidence audit:
  `website_teacher_preference_residual_corrective_remaining_evidence_audit_v1.json`,
  SHA-256
  `2dff04b2be010a10c3f3e77a144f98d1aeca89a885e21cc98be9c51868b53345`.
- Stage 6.12 full-set diagnosis:
  `website_teacher_preference_residual_corrective_failure_diagnosis_v1.json`,
  SHA-256
  `e8e12f4fd259bc0c2689100d08bdfb3b71662e29c8af0f1e1013fbc6e9573e9f`.
- Stage 6.9 confirmation is the unchanged execution/gate authority:
  `website_teacher_preference_corrective_residual_train_confirmation_v1.json`,
  SHA-256
  `352cd0dfe0a4c958ba0555b776326a2b58470a980aef461ed49d4c59a7474c7a`.
- Frozen teacher v6 and 18/4 split:
  `website_information_set_teacher_dataset_v6.pth`, SHA-256
  `a74416e6facb28a1bc64563eba90cb33d460dc9e59cc2109518da142465e15f8`;
  `website_teacher_preference_split_v1.json`, SHA-256
  `5a15e514dc9bc51d77d300837151d9f1a49250f42885cc7940725bcbe4d35107`.
- Physical train/development source partition only:
  `website_danzero_shadow_extension_v5.train_dev.pth`, SHA-256
  `e5e220c3c770116ca9d01478e98e610dd6309a0f3d6c17088a8328f62b47174b`.
  Do not load the complete bundle or locked-test partition.
- Stage 6.1 Arena rejection remains frozen:
  `website_teacher_preference_arena_smoke20_v1.json`, SHA-256
  `aa45da9de202194102fe8d11e612ad3eb4b51177fd910b9a7948836afd2a1fe6`.
- The only new curated output is
  `website_teacher_preference_residual_corrective_remaining_train_confirmation_v1.json`;
  it must not exist before execution.

## Confirmation Contract

- Validate every frozen hash and the Stage 6.13 6-train/3-development evidence
  classification. Freeze the three new-confirmation keys and explicitly exclude
  the three already inconclusive train keys plus all development keys.
- Load only the physical train/development source partition. Map each of the
  three cases to exactly one physical `train` sample by state, source action
  order, teacher/current-top1 indices, 54D action hashes, and physical-card
  identities. Reject missing, duplicate, extra, reconstructed, substituted,
  ambiguous, non-train, or information-set-inconsistent mappings.
- Execute exactly teacher and current top-1 for each case with the unchanged
  Stage 6.9 recipe: 16 rollouts per action, eight `greedy_bot` and eight frozen
  `tempo_baseline`, over eight determinizations shared across both actions and
  both continuation profiles. Use the frozen stable game/turn/determinization
  seed scheme.
- Complete exactly 96/96 rollouts: three cases x two actions x 16. Record every
  return, mean, return variance, paired advantage/variance, both directional
  95% lower bounds/confidence values, both continuation-profile advantages,
  failure reasons, and directional classification.
- Apply the unchanged Stage 6.9 gates: minimum mean advantage `0.15`, maximum
  candidate return variance `0.50`, positive directional 95% lower bound, and
  both profile advantages at least `0.15`. Do not change thresholds or infer a
  label from an inconclusive result.
- The already inconclusive train keys `14077:10`, `13959:7`, and `14025:20`
  must have zero mappings, executions, and rollouts. Development keys
  `13992:16`, `14074:9`, and `13871:9` must likewise remain identity-only with
  zero source mappings, executions, rollouts, or design use.
- In a separate process, independently reproduce every frozen/input/action
  hash, physical mapping, determinization seed, paired return, mean, variance,
  confidence bound, profile advantage, classification, aggregate, exclusion,
  and forbidden-operation counter.

## Required Work

1. Re-read the canonical handoffs; verify Git state, all frozen hashes, and the
   output path is unused.
2. Add the smallest three-case confirmation path by reusing the frozen Stage
   6.9 rollout/gate implementation, plus focused tests for exact target
   selection, exclusions, action identity, schedule, gates, and output refusal.
3. Run preflight, execute the confirmation once, then independently reload and
   audit the curated output in a separate process.
4. Stop after the 96-rollout confirmation regardless of result. Do not build a
   dataset/objective, train, run Arena, or access any website path.
5. Update `PROJECT_STATE.md`, `EXPERIMENTS.md`, `NEXT_TASK.md`, and the durable
   progress document; run narrow regressions, credential and diff checks,
   commit, and push.

## Acceptance Criteria

- All frozen hashes remain unchanged. Exactly the three permitted train cases
  reproduce with zero mapping/information-set errors.
- Exactly 96/96 rollouts complete with 48 per continuation profile; timeouts,
  candidate failures, hidden/future information use, and integrity failures are
  zero.
- Every directional metric, frozen-gate result, and independent recomputation
  matches exactly. Unsupported or inconclusive comparisons add zero labels.
- The three already inconclusive train cases and all three development cases
  have zero mappings, executions, rollouts, and design use.
- Dataset/objective construction, model scoring, training, fine-tuning, tuning,
  checkpoint selection/modification, locked-test or complete-bundle loads,
  Arena, website Shadow/play, model-controlled actions, promotion, and
  capability claims are zero.
- Credential occurrences in new tracked/curated files are zero.
- Handoff updates, focused tests, independent audit, conventional commit, and
  push all succeed before the Stage 6.14 Goal is marked complete.

## Ready-to-Use Goal Prompt

请创建一个阶段 Goal：完成 Stage 6.14 frozen three-new-top1 counterfactual
confirmation。只确认 Stage 6.13 识别出的 `13957:14` index 17、`14038:12`
index 3、`13872:4` index 19 三个 train 动作，严格复用 Stage 6.9 的配对信息集
rollout、种子、16-rollout/action 和强门槛，完成且仅完成 96/96 rollouts。
不得重跑 3 个已有 inconclusive train 案例或任何 development 案例；不得构造
dataset/objective、模型评分、训练、调参、修改 checkpoint、加载 locked test、
运行 Arena、访问网站、Shadow、模型控制、提升或能力结论。独立审计、交接更新、
验证、凭据零命中、commit 和 push 全部成功后，才能完成 Goal。
