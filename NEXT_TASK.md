# NEXT_TASK.md

## Single Next Stage

Run Stage 6.2: a static full-legal-set Q-ranking diagnosis for the rejected
teacher-preference checkpoint on all 22 frozen teacher states.

Do not retrain, tune, select or modify a checkpoint, run Arena, load a website
dataset or locked test, access the website, or begin any later offline or
website stage. The checkpoint remains rejected from the 100/200-game screen
regardless of the diagnostic result.

## Frozen Inputs

- Rejected candidate checkpoint:
  `models_website_teacher_preference_v1/website_teacher_preference_final.pth`,
  SHA-256
  `c54801a9db05100c2fe5a9bf610a64fc7c94dc2cd947dfaab115ff827bd90919`.
- Frozen teacher dataset:
  `website_information_set_teacher_dataset_v6.pth`, SHA-256
  `a74416e6facb28a1bc64563eba90cb33d460dc9e59cc2109518da142465e15f8`.
- Frozen 18/4 pipeline split:
  `website_teacher_preference_split_v1.json`, SHA-256
  `5a15e514dc9bc51d77d300837151d9f1a49250f42885cc7940725bcbe4d35107`.
- Frozen training report:
  `website_teacher_preference_training_v1.json`, SHA-256
  `896192b1d0b4de2caabe20ac17d6a20766fc7f89d6e82a981d834b777932ddd3`.
- Frozen Stage 6.1 Arena evidence:
  `website_teacher_preference_arena_smoke20_v1.json`, SHA-256
  `aa45da9de202194102fe8d11e612ad3eb4b51177fd910b9a7948836afd2a1fe6`.
- Required Arena conclusion: 20/20 complete, model/baseline wins 0/20,
  integrity gate true, early-screen continuation false, and every safety count
  zero.
- Diagnostic output must be unused before execution and named
  `website_teacher_preference_failure_diagnosis_v1.json`.

## Diagnostic Contract

- Load only the frozen teacher dataset, split manifest, training report,
  checkpoint, and Stage 6.1 Arena JSON listed above. Do not load any website
  bundle, train/development dataset, locked-test partition, logs, or outcomes.
- Use each teacher sample's recorded 513-dimensional state and exhaustive
  recorded 54-dimensional `legal_actions`. Do not reconstruct or add actions.
- Score every recorded legal action exactly once with the existing frozen
  `danzero_dmc.build_q_model`; all Q values must be finite.
- Preserve recorded legal-action order. Top-1 uses the first maximum exactly as
  `torch.argmax`; teacher and behavior ranks use
  `1 + count(Q_action > Q_target)`. Report tie counts separately.
- For every state, report game/turn, frozen pipeline partition, legal-action
  count, teacher rank/Q, behavior rank/Q, teacher-minus-behavior margin,
  top-1 index/Q, whether top-1 is teacher, behavior, or another legal action,
  whether top-1 is pass, number of actions strictly above teacher, and number
  tied with teacher.
- Aggregate separately for the 18 pipeline-train and four
  pipeline-development games, then overall. Report teacher-over-behavior rate,
  teacher top-1 rate, behavior top-1 rate, other-action top-1 rate,
  pass-top1 rate, mean/median teacher rank, and the count of states where an
  unpaired legal action strictly outranks teacher.
- Recompute the frozen teacher-versus-behavior metrics and prediction digests;
  they must exactly match the training report before full-set conclusions are
  accepted.
- This stage may identify an objective-coverage failure pattern but must not
  claim causality, capability, or a corrective model result.

## Required Work

1. Re-read the canonical handoffs; verify Git state, all frozen hashes and
   flags, the rejected Arena conclusion, and output nonexistence.
2. Add the smallest static diagnostic implementation and focused tests for
   stable first-max tie handling, rank calculation, partition mapping, finite
   Q enforcement, exhaustive action accounting, and aggregate arithmetic.
3. Run the diagnostic once on all 22 teacher states and write the single
   curated JSON output.
4. Independently audit exact state/action coverage, partition counts, per-state
   and aggregate arithmetic, frozen pairwise metric/digest reproduction, and
   zero forbidden operations.
5. Keep the checkpoint and teacher dataset unchanged. Do not train, run Arena,
   load website datasets, or execute any later gate.
6. Update `PROJECT_STATE.md`, `EXPERIMENTS.md`, `NEXT_TASK.md`, and the durable
   progress document; run narrow regression tests, credential and diff checks,
   commit, and push.

## Acceptance Criteria

- All five frozen hashes remain unchanged and Stage 6.1 remains a 0-20 rejected
  candidate with continuation false.
- Exactly 22 unique teacher states and every recorded legal action are scored;
  dropped, duplicated, reconstructed, nonfinite, dimension-invalid, or illegal
  actions are zero.
- Partition mapping is exactly 18 pipeline train and four pipeline development,
  with zero overlap or unknown games.
- Teacher-versus-behavior metrics and prediction digests exactly reproduce the
  frozen training report for both partitions.
- Per-state ranks/top-1 classifications and aggregate rates/counts recompute
  exactly in an independent audit.
- Training, hyperparameter search, checkpoint selection/modification, website
  dataset or locked-test loads, Arena games, website Shadow/play,
  model-controlled website actions, checkpoint promotion, and capability
  claims are all zero.
- Credential occurrences in new tracked/curated files are zero.
- Handoff updates, focused tests, independent audit, conventional commit, and
  push all succeed before the stage Goal is marked complete.

## Ready-to-Use Goal Prompt

请创建一个阶段 Goal：完成 Stage 6.2 冻结 teacher-preference checkpoint 的
full-legal-set Q-ranking 静态失败诊断。只加载冻结 checkpoint、teacher v6、
18/4 split、training report 和 0-20 Arena 证据；对 22 个 teacher 状态的全部
已记录 legal actions 各评分一次，按冻结顺序和 first-maximum 规则报告 teacher/
behavior rank、top-1 来源、pass-top1、未配对动作超过 teacher 的情况，并分别按
pipeline train/development 和 overall 汇总。必须精确复现冻结的 teacher-vs-
behavior metrics 与 prediction digests。严禁训练、调参、checkpoint 选择或修改、
网站 dataset/locked-test 加载、Arena、网站 Shadow/对局、checkpoint 提升或能力
结论；该 checkpoint 无论诊断结果如何都保持 100/200-game screen rejected。
更新交接、验证、凭据零命中、commit 和 push 全部成功后才能完成 Goal。
