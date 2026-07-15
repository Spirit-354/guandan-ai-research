# NEXT_TASK.md

## Single Next Stage

Run Stage 6.14P: process-isolated determinization parallel equivalence.

Stage 6.14R proved that the unchanged sequential confirmation path has no
unused optimization switch: it already installs all frozen offline engine
optimizations and enables the complete-visible-state baseline action cache.
The common 600-second deadline leaves `13872:4` with 13/16 paired schedule
items and exactly six failed candidate values.

Add only the scheduling/equivalence layer needed to evaluate the eight frozen
determinizations in isolated worker processes. This stage is implementation and
synthetic equivalence only: do not execute any real information-set rollout.
The layer must reconstruct each determinization from the same physical train
sample and stable seed, execute teacher/current-top1 under greedy then frozen
tempo in frozen schedule order, and restore all results to the original 16-item
schedule before Stage 6.9 metric computation.

Do not change the actions, physical materialization, hidden-card sampler,
stable seed scheme, continuation policies, 16-rollout/action count, eight
determinizations, `MAX_ROLLOUT_STEPS=300`, `MAX_SECONDS_PER_CASE=600`, return
definition, confidence arithmetic, thresholds, or directional gates. Do not
execute a real rollout, use either partial supported-looking comparison,
construct a dataset/objective, score a model, train, tune, modify a checkpoint,
load locked test or the complete website bundle, run Arena, access the website,
begin Shadow or model-controlled play, promote a model, or claim capability.

## Frozen Inputs

- Stage 6.14R recovery audit:
  `website_teacher_preference_residual_corrective_remaining_timeout_recovery_audit_v1.json`,
  SHA-256
  `75115cfc5a9dfa3ecb6ac868d04a2e73d20473cfe3a49c8e805a042028872c0d`.
- Stage 6.13 evidence audit:
  `website_teacher_preference_residual_corrective_remaining_evidence_audit_v1.json`,
  SHA-256
  `2dff04b2be010a10c3f3e77a144f98d1aeca89a885e21cc98be9c51868b53345`.
- Stage 6.9 execution/gate authority:
  `website_teacher_preference_corrective_residual_train_confirmation_v1.json`,
  SHA-256
  `352cd0dfe0a4c958ba0555b776326a2b58470a980aef461ed49d4c59a7474c7a`.
- Frozen teacher v6, 18/4 split, physical train/development source partition,
  Stage 6.12 diagnosis, and Stage 6.1 Arena rejection retain the hashes recorded
  by Stage 6.14R.
- Stage 6.14 confirmation implementation:
  `website_teacher_preference_residual_corrective_remaining_confirmation.py`,
  frozen Stage 6.14R SHA-256
  `e509ebc50f9fef9a159435d582561e72ac36083f059a0781539ec797c709bf55`.
- The failed confirmation output
  `website_teacher_preference_residual_corrective_remaining_train_confirmation_v1.json`
  must remain absent throughout this equivalence stage.
- The only new curated output is
  `website_teacher_preference_residual_corrective_remaining_parallel_equivalence_v1.json`;
  it must not exist before execution.

## Frozen Parallel Contract

- Exactly eight worker tasks per case, one for each determinization index 0-7.
- Every task receives only the physical train sample identity, frozen teacher
  and current-top1 identities, determinization index/seed, both continuation
  profile names, the common absolute parent deadline, and frozen limits.
- Each task independently restores the information-set game from the exact
  sample and stable seed. It must not receive or inspect opponent/teammate true
  hands from another source.
- Within each task, execution order is teacher/greedy, current-top1/greedy,
  teacher/tempo, current-top1/tempo, matching the two adjacent frozen schedule
  items for that determinization.
- Workers may install the already-frozen offline engine optimizations and use a
  worker-local complete-visible-state baseline action cache. Cache hit/miss
  behavior may affect runtime only; chosen actions and returns must not change.
- Parent aggregation must sort by frozen `rollout_index` and action role before
  invoking the unchanged Stage 6.9 normalization, metrics, gates, and writer.
- Workers cannot decide labels, thresholds, classifications, retries, or
  deadline extensions. A worker crash, missing result, duplicate result, seed
  mismatch, late result, or out-of-order identity must fail closed.

## Required Work

1. Re-read all canonical handoffs; verify Git state, frozen hashes, recovery
   artifact, and both output-path preconditions.
2. Add the smallest top-level, Windows-spawn-safe task/result representation and
   process-isolated executor. Keep the existing sequential function untouched
   as the frozen reference.
3. Add synthetic/instrumented equivalence tests that execute no real rollout:
   exact 8-task/16-schedule/32-call accounting, identical determinization seeds,
   action/profile order, common deadline propagation, sequential-versus-
   parallel returns/failures, stable parent ordering, and fail-closed handling.
4. Write one small curated equivalence JSON and independently reload/recompute
   it in a separate process. Do not run the three real cases.
5. Update `PROJECT_STATE.md`, `EXPERIMENTS.md`, `NEXT_TASK.md`, and the durable
   progress document; run narrow regressions, credential and diff checks,
   commit, and push.

## Acceptance Criteria

- Every frozen hash remains unchanged and the failed Stage 6.14 confirmation
  output remains absent.
- Synthetic sequential and process-isolated paths match exactly for all 32
  candidate calls, including returns, failures, seeds, actions, profiles,
  schedule indices, and aggregate ordering.
- Exactly eight tasks reconstruct the frozen schedule without missing,
  duplicate, extra, substituted, or ambiguous results.
- The common parent deadline and frozen 300-step limit propagate unchanged;
  worker timeout/failure results fail closed and cannot become a label.
- Real rollout count, partial comparison uses, dataset/objective construction,
  model scoring, training, tuning, limit changes, checkpoint activity,
  locked-test/complete-bundle loads, Arena, website activity, promotion, and
  capability claims are all zero.
- An independent process reproduces every code/input hash, task identity,
  synthetic result, equivalence digest, aggregate, and forbidden counter.
- Credential occurrences in new tracked/curated files are zero.
- Handoff updates, focused tests, conventional commit, and push all succeed
  before this equivalence stage is accepted. The active Stage 6.14 Goal remains
  incomplete until a later formal 96/96 run and independent audit pass.

## Ready-to-Use Goal Prompt

继续当前 Stage 6.14 Goal，完成 Stage 6.14P process-isolated determinization
parallel equivalence。只新增 Windows-spawn-safe 的 8 determinization worker
调度层，并用 synthetic/instrumented 校验证明它与冻结 Stage 6.9 顺序路径在
sample、action、seed、profile、return、failure、deadline、顺序和聚合上完全一致。
不得执行真实 rollout，不得修改 600 秒/300 步/16-rollout/action/8 determinization、
采样、动作、profile、回报或门槛，不得使用 partial comparison、dataset/objective、
模型评分、训练、调参、checkpoint、locked test、Arena、网站、Shadow、模型控制、
提升或能力结论。独立审计、交接、验证、凭据零命中、commit 和 push 全部成功后，
才能接受 Stage 6.14P；Stage 6.14 Goal 仍需后续正式 96/96 才能完成。
