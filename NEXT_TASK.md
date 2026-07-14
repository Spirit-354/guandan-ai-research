# NEXT_TASK.md

## Single Next Stage

Run Stage 6.4: frozen pipeline-train unpaired counterfactual confirmation.

Execute the Stage 6.3 future manifest only for its nine `pipeline_train`
cases. Compare each frozen teacher action directly with the frozen Stage 6.2
model top-1 action. The three `pipeline_development` cases are held out and
must not be executed, interpreted for objective design, or used to tune any
rule or threshold.

Do not train, tune, select or modify a checkpoint, run Arena, load locked test,
access the website, begin Shadow or model-controlled play, promote a model, or
claim capability. The rejected checkpoint remains ineligible for the
100/200-game screen regardless of the confirmation result.

## Frozen Inputs

- Stage 6.3 audit:
  `website_teacher_preference_unpaired_evidence_audit_v1.json`, SHA-256
  `09f52df90d095ab6b3777a046c50901f96fbeb15e6ef5f613343a13be1249383`.
- Stage 6.2 diagnosis:
  `website_teacher_preference_failure_diagnosis_v1.json`, SHA-256
  `da08516c39986a01349533e160ba0e97a566d7fad6e42b0b7b3ce41df835b0b2`.
- Frozen teacher dataset:
  `website_information_set_teacher_dataset_v6.pth`, SHA-256
  `a74416e6facb28a1bc64563eba90cb33d460dc9e59cc2109518da142465e15f8`.
- Frozen 18/4 split:
  `website_teacher_preference_split_v1.json`, SHA-256
  `5a15e514dc9bc51d77d300837151d9f1a49250f42885cc7940725bcbe4d35107`.
- Frozen training report:
  `website_teacher_preference_training_v1.json`, SHA-256
  `896192b1d0b4de2caabe20ac17d6a20766fc7f89d6e82a981d834b777932ddd3`.
- Rejected checkpoint, unchanged:
  `models_website_teacher_preference_v1/website_teacher_preference_final.pth`,
  SHA-256
  `c54801a9db05100c2fe5a9bf610a64fc7c94dc2cd947dfaab115ff827bd90919`.
- Stage 6.1 Arena evidence, unchanged:
  `website_teacher_preference_arena_smoke20_v1.json`, SHA-256
  `aa45da9de202194102fe8d11e612ad3eb4b51177fd910b9a7948836afd2a1fe6`.
- Use only the existing train/development website source data required to
  replay the nine pipeline-train state keys. Do not load or execute any
  pipeline-development case or locked-test data.
- The output must be unused before execution and named
  `website_teacher_preference_unpaired_train_confirmation_v1.json`.

## Confirmation Contract

- Reproduce the nine pipeline-train manifest entries exactly before launching
  any rollout: game/turn key, action-order hash, teacher index, top-1 index,
  54D action hashes, and physical-card identities must match Stage 6.3.
- For each state, evaluate exactly the frozen teacher and frozen model top-1
  actions. Do not reconstruct, canonicalize, add, drop, or substitute an
  action. Behavior may be retained only as immutable provenance, not as a
  third evaluated candidate.
- Use 16 completed rollouts per action: eight `greedy_bot` and eight frozen
  `tempo_baseline` continuations, with the same legal information-set physical
  determinizations shared across both actions and both continuation profiles.
- Record rollout count, hidden-card sampling method, mean return, return and
  paired-return variance, teacher-minus-top1 advantage, 95% lower bound,
  confidence, per-profile paired advantages, completion, timeout, failure, and
  integrity fields for every case.
- Apply the existing strong-teacher gates without tuning them. Report supported
  and unsupported teacher-versus-top1 comparisons by exact reason. Do not
  convert the results into training labels or a corrective loss in this stage.
- The three pipeline-development manifest cases remain read-only and appear
  only in an explicit held-out accounting section. Their rollout count must be
  zero.

## Required Work

1. Re-read the canonical handoffs; verify Git state, all seven frozen hashes,
   the 0-20 rejection, Stage 6.3 arithmetic, and output nonexistence.
2. Add the smallest train-only confirmation implementation and focused tests
   for manifest partition restriction, exact action identity, shared
   determinization, fixed rollout accounting, confidence arithmetic, held-out
   exclusion, and interruption-safe failure handling.
3. Run exactly one confirmation job for the nine pipeline-train cases and
   write the single curated JSON output.
4. Independently audit case coverage, hashes, action identities, rollout and
   profile counts, confidence arithmetic, held-out zero execution, and all
   integrity/forbidden counters.
5. Keep every frozen input unchanged. Do not update teacher data or checkpoint.
6. Update `PROJECT_STATE.md`, `EXPERIMENTS.md`, `NEXT_TASK.md`, and the durable
   progress document; run narrow regressions, credential and diff checks,
   commit, and push.

## Acceptance Criteria

- All seven frozen hashes remain unchanged; Stage 6.1 remains 0-20 with
  continuation false and the checkpoint remains rejected.
- Exactly nine pipeline-train cases run with zero missing, duplicate, extra,
  reconstructed, substituted, or ambiguous action mappings.
- Exactly 288 rollouts complete: 9 cases x 2 actions x 16 rollouts. Each action
  has eight greedy and eight frozen-tempo continuations using common legal
  information-set determinizations.
- Pipeline-development case executions, locked-test loads, hidden/future
  information use, timeouts, candidate failures, and integrity failures are
  zero.
- Training, tuning, checkpoint selection or modification, Arena, website
  Shadow/play, model-controlled website actions, promotion, and capability
  claims are all zero.
- Credential occurrences in new tracked/curated files are zero.
- Handoff updates, focused tests, independent audit, conventional commit, and
  push all succeed before the stage Goal is marked complete.

## Ready-to-Use Goal Prompt

请创建一个阶段 Goal：完成 Stage 6.4 frozen pipeline-train unpaired
counterfactual confirmation。只执行 Stage 6.3 manifest 中九个
`pipeline_train` 状态，按原始 54D 动作与 physical-card identity 直接比较
teacher 和模型 top-1；每动作固定 16 次 rollout，greedy/冻结 tempo 各八次，
所有动作与 continuation profile 共享合法 information-set determinization。
三个 `pipeline_development` 状态必须保持 held-out 且执行数为零。不得训练、
调参、选择或修改 checkpoint、运行 Arena、加载 locked test、访问网站、运行
Shadow/对局、模型控制、提升或能力结论。更新交接、验证、凭据零命中、commit
和 push 全部成功后才能完成 Goal。
