# NEXT_TASK.md

## Single Next Stage

Run Stage 6.9: frozen pipeline-train residual counterfactual confirmation.

Execute only the eight insufficient pipeline-train cases in the frozen Stage
6.8 future manifest. Compare each exact teacher action with its exact residual
top1 action under the already frozen paired information-set rollout schedule
and strong-teacher gates. Keep the three pipeline-development residual targets
unexecuted and out of candidate rules, threshold design, objective design, and
all result-based decisions.

Do not train or fine-tune a model, tune thresholds, select or modify a
checkpoint, load locked test or any complete website dataset, run Arena, access
the website, begin Shadow or model-controlled play, promote a model, claim
capability, construct a corrective dataset, or define a new objective.

## Frozen Inputs

- Stage 6.8 residual evidence audit:
  `website_teacher_preference_corrective_residual_evidence_audit_v1.json`,
  SHA-256
  `676232033f07051670b4407f15aca9f3939d9754ac2dcf4d078957263a1e2a6b`.
- Stage 6.7 corrective diagnosis:
  `website_teacher_preference_corrective_failure_diagnosis_v1.json`, SHA-256
  `2b4359470e74f5eae28d6589477aca5f929ae6b5b88e094fa86209bf4328163d`.
- Frozen teacher v6 and 18/4 split:
  `website_information_set_teacher_dataset_v6.pth`, SHA-256
  `a74416e6facb28a1bc64563eba90cb33d460dc9e59cc2109518da142465e15f8`;
  `website_teacher_preference_split_v1.json`, SHA-256
  `5a15e514dc9bc51d77d300837151d9f1a49250f42885cc7940725bcbe4d35107`.
- The only permitted physical source partition is
  `website_danzero_shadow_extension_v5.train_dev.pth`, SHA-256
  `e5e220c3c770116ca9d01478e98e610dd6309a0f3d6c17088a8328f62b47174b`.
  Every executed target must map to a source sample whose dataset split is
  `train`; do not load the complete bundle or locked-test partition.
- Stage 6.4 confirmation, which freezes the paired rollout schedule, seed
  construction, arithmetic, and strong gates:
  `website_teacher_preference_unpaired_train_confirmation_v1.json`, SHA-256
  `8e17377b5a1523d9f0a47af7218d687e062a3ade671c57f387eb4c1a0888cfae`.
- The only new curated output is
  `website_teacher_preference_corrective_residual_train_confirmation_v1.json`,
  which must not exist before execution.

## Confirmation Contract

- Validate every frozen hash and reproduce exactly the eight Stage 6.8
  insufficient train manifest cases by game/turn key, original action order,
  teacher and residual indices, 54D hashes, and physical-card identities.
- Do not score a checkpoint. Use only the exact teacher and residual actions
  frozen by Stage 6.8 and the matching physical train source sample.
- For each case, execute exactly 16 rollouts for the teacher and 16 for the
  residual action: eight `greedy_bot` and eight frozen `tempo_baseline`
  continuations over eight information-set determinizations shared across both
  actions and both profiles. Total requested completion is 256/256 rollouts,
  split 128/128 by continuation profile.
- Keep the Stage 6.4 gates unchanged: paired rollout count 16, mean directional
  advantage at least 0.15, candidate return variance at most 0.50, positive 95%
  lower bound, and both continuation-profile directional advantages at least
  0.15. Record both directions and classify each case as teacher-over-residual
  supported, residual-over-teacher supported, or inconclusive.
- Record rollout count, hidden-card sampling method, both mean returns and
  return variances, paired advantage and variance, 95% lower bound/confidence,
  both profile advantages, completion, and integrity for every executed case.
- The three development targets `13992:16`, `14074:9`, and `13871:9` must have
  zero source-sample mapping, zero execution, and zero rollout. They may appear
  only as frozen held-out keys copied from Stage 6.8.
- Independently recompute input/action hashes, determinization seeds, paired
  returns, means, variances, confidence bounds, both-profile advantages,
  classifications, partition counts, aggregates, and forbidden-operation
  counters.

## Required Work

1. Re-read the canonical handoffs; verify Git state, all frozen hashes, source
   partition isolation, and output nonexistence.
2. Add the smallest train-only confirmation path and focused tests for exact
   manifest mapping, 8/3 isolation, rollout schedule, frozen gates, paired
   arithmetic, development non-execution, and output refusal.
3. Run exactly one formal 256-rollout confirmation and independently verify the
   curated output.
4. Keep every frozen input and both model checkpoints unchanged. Do not build a
   dataset, train, run Arena, or access the website regardless of the result.
5. Update `PROJECT_STATE.md`, `EXPERIMENTS.md`, `NEXT_TASK.md`, and the durable
   progress document; run narrow regressions, credential and diff checks,
   commit, and push.

## Acceptance Criteria

- All frozen hashes remain unchanged. Exactly eight train manifest cases map
  with zero missing, duplicate, extra, reconstructed, substituted, ambiguous,
  or non-train source mappings.
- Exactly 256/256 requested rollouts complete: eight cases, two exact actions,
  and 16 rollouts per action. Greedy/frozen-tempo counts are 128/128 and all
  paired actions share the same eight determinizations per case.
- Every directional classification is derived only from the unchanged frozen
  gates. Inconclusive comparisons and the losing direction add no label; no
  dataset or objective is constructed in this stage.
- Development case executions, development source mappings, development
  rollouts, hidden/future information use, timeouts, candidate failures,
  integrity failures, and locked-test loads are zero.
- Training, fine-tuning, tuning, checkpoint selection/modification, Arena,
  website Shadow/play, model-controlled website actions, promotion, and
  capability claims are zero.
- Credential occurrences in new tracked/curated files are zero.
- Handoff updates, focused tests, independent audit, conventional commit, and
  push all succeed before the next stage Goal is marked complete.

## Ready-to-Use Goal Prompt

请创建一个阶段 Goal：完成 Stage 6.9 frozen pipeline-train residual
counterfactual confirmation。只执行 Stage 6.8 future manifest 中 8 个证据不足的
pipeline-train case，严格复用冻结的 teacher/residual action、共享信息集
determinization、16-rollout 双 continuation schedule 和强 teacher gates；3 个
development target 必须零映射、零执行、零 rollout。不得训练、调参、选择/修改
checkpoint、加载 locked test/完整网站 dataset、构建 dataset/新目标、运行 Arena、
访问网站、Shadow、模型控制、提升或能力结论。独立复核、交接更新、验证、凭据零命中、
commit 和 push 全部成功后，才能完成 Goal。
