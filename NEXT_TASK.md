# NEXT_TASK.md

## Single Next Stage

Run Stage 6.3: a frozen unpaired-action evidence audit for the 12 teacher
states where Stage 6.2 found an unpaired recorded action strictly above the
teacher.

Do not run a new rollout, train, tune, select or modify a checkpoint, run Arena,
load a website dataset or locked test, access the website, or begin any later
offline or website stage. The rejected checkpoint remains ineligible for the
100/200-game screen regardless of the audit result.

## Frozen Inputs

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
- The only additional readable artifacts are existing frozen rollout-evidence
  files referenced directly by the 12 target teacher samples. Hash every such
  file before interpreting it.
- The audit output must be unused before execution and named
  `website_teacher_preference_unpaired_evidence_audit_v1.json`.

## Audit Contract

- Reproduce the 12 target state keys, teacher/action indices, Q ordering, and
  action-order hashes from Stage 6.2 before reading source rollout evidence.
- For each target state, map the first-maximum unpaired action exactly to its
  recorded 54-dimensional action and physical-card identity. Do not reconstruct,
  canonicalize, add, or drop an action.
- Read only the existing frozen rollout-evidence path recorded by that teacher
  sample. Record its path, SHA-256, schema, completeness, hidden-card sampling
  method, continuation profiles, rollout counts, candidate identity, mean,
  variance, advantage, confidence, and integrity fields when present.
- Classify the model top-1 action as exactly one of: dual-continuation confirmed,
  greedy-only screened, present without qualifying comparison, absent from
  prior evidence, or ambiguous mapping. Do not infer an ordering from missing
  fields or a different candidate.
- Report separately by pipeline train/development and overall. Include exact
  counts for each evidence class and a future counterfactual-manifest section
  for absent or insufficient cases, but do not execute that manifest.
- This stage may decide whether a teacher-versus-all objective is supported by
  existing evidence. It must not claim causality, train a corrective model, or
  claim capability.

## Required Work

1. Re-read the canonical handoffs; verify Git state, all six frozen hashes,
   the 0-20 rejection, the Stage 6.2 arithmetic, and output nonexistence.
2. Add the smallest static evidence-audit implementation and focused tests for
   exact action identity, evidence-path restriction, evidence classification,
   missing-field conservatism, partition mapping, and aggregate arithmetic.
3. Run the audit once for exactly the 12 target states and write the single
   curated JSON output. Do not launch any rollout worker.
4. Independently audit target coverage, action/evidence hashes, classifications,
   partition counts, aggregate arithmetic, and zero forbidden operations.
5. Keep every frozen input and referenced rollout-evidence file unchanged.
6. Update `PROJECT_STATE.md`, `EXPERIMENTS.md`, `NEXT_TASK.md`, and the durable
   progress document; run narrow regression tests, credential and diff checks,
   commit, and push.

## Acceptance Criteria

- All six primary frozen hashes and every referenced source-evidence hash remain
  unchanged; Stage 6.1 remains 0-20 with continuation false.
- Exactly the 12 Stage 6.2 target states are audited with zero missing,
  duplicate, extra, reconstructed, or ambiguous state/action mappings.
- Every evidence classification is traceable to the exact frozen action and
  source fields. Unsupported or incomplete evidence is never promoted to a
  teacher-versus-all ordering.
- Pipeline partition counts, evidence-class counts, and all aggregate values
  recompute exactly in an independent audit.
- New rollouts, training, hyperparameter search, checkpoint selection or
  modification, website dataset or locked-test loads, Arena games, website
  Shadow/play, model-controlled website actions, promotion, and capability
  claims are all zero.
- Credential occurrences in new tracked/curated files are zero.
- Handoff updates, focused tests, independent audit, conventional commit, and
  push all succeed before the stage Goal is marked complete.

## Ready-to-Use Goal Prompt

请创建一个阶段 Goal：完成 Stage 6.3 冻结 unpaired-action evidence audit。只对
Stage 6.2 中 12 个被未配对动作压过 teacher 的状态，读取 teacher 样本直接引用的
既有冻结 rollout 证据，精确映射模型 top-1 动作并保守分类其证据覆盖；不得运行新
rollout、训练、调参、checkpoint 选择或修改、网站 dataset/locked-test 加载、Arena、
网站 Shadow/对局、模型控制、提升或能力结论。缺失或不足证据只能写入未来 manifest，
不能执行。checkpoint 无论结果如何都保持 100/200-game screen rejected。更新交接、
验证、凭据零命中、commit 和 push 全部成功后才能完成 Goal。
