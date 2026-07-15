# NEXT_TASK.md

## Single Next Stage

Run Stage 6.14R: frozen confirmation timeout recovery audit.

Stage 6.14 is not accepted. Its unchanged Stage 6.9 schedule requested 96
action rollouts but completed only 90. The third case, `13872:4` index 19,
hit the frozen 600-second case deadline and produced six candidate failures.
The intended curated confirmation output was not written. Do not use the two
supported-looking directions, and do not rerun any counterfactual rollout in
this recovery-audit stage.

Perform only a static/code-path recovery audit. Identify the exact deadline and
failure path, determine whether the repository already contains a semantics-
preserving offline optimization that can be applied without changing the
Stage 6.9 rollout, action, seed, continuation, return, or gate semantics, and
freeze a single subsequent execution plan. If no such path exists, conclude
that the frozen confirmation is infeasible rather than weakening its contract.

Do not change `MAX_SECONDS_PER_CASE`, `MAX_ROLLOUT_STEPS`, the 16-rollout/action
schedule, seeds, hidden-card sampling, continuation profiles, thresholds, or
directional gates. Do not execute a rollout, construct a dataset/objective,
score a model, train, tune, modify a checkpoint, load locked test or the
complete website bundle, run Arena, access the website, begin Shadow or model-
controlled play, promote a model, or claim capability.

## Frozen Inputs

- Stage 6.13 evidence audit:
  `website_teacher_preference_residual_corrective_remaining_evidence_audit_v1.json`,
  SHA-256
  `2dff04b2be010a10c3f3e77a144f98d1aeca89a885e21cc98be9c51868b53345`.
- Stage 6.12 full-set diagnosis:
  `website_teacher_preference_residual_corrective_failure_diagnosis_v1.json`,
  SHA-256
  `e8e12f4fd259bc0c2689100d08bdfb3b71662e29c8af0f1e1013fbc6e9573e9f`.
- Stage 6.9 confirmation authority:
  `website_teacher_preference_corrective_residual_train_confirmation_v1.json`,
  SHA-256
  `352cd0dfe0a4c958ba0555b776326a2b58470a980aef461ed49d4c59a7474c7a`.
- Frozen teacher v6, split, physical source partition, and Arena rejection
  retain the hashes listed in the prior Stage 6.14 handoff.
- The Stage 6.14 implementation is
  `website_teacher_preference_residual_corrective_remaining_confirmation.py`.
- The intended curated output
  `website_teacher_preference_residual_corrective_remaining_train_confirmation_v1.json`
  must remain absent throughout this audit.

## Confirmed Failure Evidence

- Preflight: seven frozen hashes, three permitted train cases, three excluded
  inconclusive train cases, three held-out development cases, requested 96.
- Terminal accounting: `requested=96`, `completed=90`,
  `profiles={'greedy_bot': 48, 'tempo_baseline': 48}`, `timeouts=1`,
  `candidate_failures=6`.
- Case classifications before writer rejection: `13957:14` teacher supported,
  `14038:12` teacher supported, `13872:4` inconclusive.
- Curated output written: no. Dataset/objective/labels/training/Arena/website:
  zero.
- An earlier external command timeout produced no case-completion output or
- A following run printed the same three case directions but was rejected by a
  generic aggregate assertion before exact failure fields or an artifact were
  preserved. The instrumented run above is the only exact blocker accounting;
  the retries are also a one-shot acceptance violation.

## Required Work

1. Re-read all canonical handoffs; verify Git state, frozen hashes, and output
   absence.
2. Trace the unchanged Stage 6.9 `execute_case` deadline propagation and the
   candidate simulation failure accounting. Do not execute the path.
3. Audit existing offline optimization/install/cache paths and tests for exact
   semantic equivalence. Do not add a new optimization unless equivalence can
   be proven without rollout execution in this stage.
4. Write one small curated recovery-audit JSON and focused tests that reproduce
   the 90/96 blocker from frozen handoff facts and freeze exactly one next
   action: a semantics-preserving retry plan or an infeasibility conclusion.
5. Update `PROJECT_STATE.md`, `EXPERIMENTS.md`, `NEXT_TASK.md`, and the durable
   progress document; run narrow regressions, credential and diff checks,
   commit, and push.

## Acceptance Criteria

- All frozen hashes remain unchanged and the intended Stage 6.14 confirmation
  output remains absent.
- The 90/96, one-timeout, six-failure condition is reproduced without new
  rollout, model scoring, training, Arena, or website execution.
- The exact code path from case deadline to six failed candidate values is
  documented and tested.
- Any proposed recovery preserves action materialization, information-set
  sampling, seeds, continuation behavior, returns, rollout counts, limits, and
  directional gates exactly; otherwise the result must be infeasible.
- A single next-stage plan is frozen. No comparison or label from the failed
  Stage 6.14 attempt is used.
- Credential occurrences in new tracked/curated files are zero.
- Handoff updates, focused tests, independent audit, conventional commit, and
  push all succeed before the Stage 6.14R Goal is marked complete.

## Ready-to-Use Goal Prompt

请创建一个阶段 Goal：完成 Stage 6.14R frozen confirmation timeout recovery
audit。Stage 6.14 仅完成 90/96 rollouts，`13872:4` 在冻结 600 秒 case deadline
下产生 1 timeout 和 6 candidate failures，正式 artifact 未写出。只做静态代码路径
与现有等价优化审计，不得执行新 rollout、修改 deadline/步数/种子/profile/门槛，
不得使用两个 supported-looking 方向，不得构造 dataset/objective、模型评分、训练、
调参、checkpoint、locked test、Arena、网站、Shadow、模型控制、提升或能力结论。
冻结一个语义完全等价的后续执行计划，或明确判定该确认不可完成；独立审计、交接、
验证、凭据零命中、commit 和 push 全部成功后，才能完成 Goal。
