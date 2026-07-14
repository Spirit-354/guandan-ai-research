# NEXT_TASK.md

## Single Next Stage

Run a frozen teacher-preference training-pipeline smoke using only teacher v6.
Add the smallest deterministic path that trains the existing compatible
513-state/54-action Q architecture to rank each frozen teacher action above its
recorded behavior action.

This is pipeline validation, not offline capability evaluation. Do not run
Arena, website Shadow, website games, checkpoint promotion, or
model-controlled website play in this stage. Do not begin any later evaluation
or website-risk stage.

## Frozen Inputs

- Only permitted teacher input:
  `website_information_set_teacher_dataset_v6.pth`.
- Required teacher v6 SHA-256:
  `a74416e6facb28a1bc64563eba90cb33d460dc9e59cc2109518da142465e15f8`.
- Required teacher metadata: 22 accepted labels from 22 independent games,
  `training_gate_passed=true`, `locked_test_loaded=false`, state dimension 513,
  action dimension 54, and `capability_claim_allowed=false`.
- Frozen provenance dataset, for hash/metadata audit only if needed:
  `website_danzero_shadow_extension_v5.train_dev.pth`, SHA-256
  `e5e220c3c770116ca9d01478e98e610dd6309a0f3d6c17088a8328f62b47174b`.
  It must not supply extra training targets.
- Frozen teacher v5 provenance SHA-256:
  `155fc348e939490bc036b2b5e3e0993be732b259250cac3d0244e888910fb9da`.
- Never load `website_danzero_shadow_extension_v5.pth` or
  `website_danzero_shadow_extension_v5.locked_test.pth`.
- Use the existing `danzero_dmc.build_q_model` 513+54 architecture. Do not
  introduce a second model family or change website action semantics.

## Training Contract

- Treat each teacher sample as one pairwise preference:
  `Q(state, teacher_action) > Q(state, behavior_action)`.
- Use only a pairwise logistic/softplus ranking loss. Do not invent scalar
  return targets, synthesize labels, add self-play data, or use terminal game
  outcomes as model features.
- Validate before training that every state has length 513, every teacher and
  behavior action has length 54, both actions are in the recorded legal-action
  set, the teacher and behavior actions differ, all samples are train-only,
  and no sample reports locked-test use.
- Split by complete `game_id`, never by individual sample. Sort games by
  `sha256("website_teacher_v6_split_v1:" + game_id)`; assign the first four to
  an internal pipeline-development partition and the remaining 18 to the
  internal pipeline-train partition. This internal split does not alter the
  frozen website dataset split and is not capability evidence.
- Use CPU, seed `20260714`, deterministic PyTorch settings, no initialization
  checkpoint, and a single fixed smoke recipe. Keep the recipe small; do not
  add a hyperparameter search or checkpoint selection loop.
- Report train and internal-development pairwise ranking accuracy and mean
  teacher-minus-behavior margin before and after training, but label every
  metric as pipeline-only and ineligible for capability or promotion claims.

## Required Work

1. Re-read the canonical handoffs and verify Git state, frozen hashes, teacher
   v6 schema/counts/games, and that planned smoke outputs do not already exist.
2. Add the narrowest CLI/training implementation and focused tests for teacher
   validation, deterministic game-grouped splitting, pairwise loss direction,
   513+54 model compatibility, and checkpoint reload.
3. Write a small curated frozen split manifest as
   `website_teacher_preference_split_v1.json`. It must record the exact method,
   seed, teacher hash, 18/4 game membership, zero overlap, and zero locked-test
   use.
4. Run one deterministic CPU smoke and write its ignored checkpoint under
   `models_website_teacher_preference_v1/` plus a small curated report named
   `website_teacher_preference_training_v1.json`.
5. Reload the final checkpoint and independently recompute the reported
   pairwise metrics. Re-run the smoke to temporary outputs and verify the split
   and predictions/metrics are reproducible under the frozen recipe.
6. Audit that teacher v6 and all frozen provenance artifacts remain unchanged;
   locked-test loads, website access, Arena runs, checkpoint promotion,
   capability claims, and model-controlled website actions must all be zero.
7. Update `PROJECT_STATE.md`, `EXPERIMENTS.md`, `NEXT_TASK.md`, and the durable
   progress document; run narrow tests, credential and diff checks, commit, and
   push.

## Acceptance Criteria

- Teacher v6 hash, 22 labels, 22 independent games, dimensions, legal actions,
  differing preference pairs, train-only provenance, and gate metadata all
  pass before training.
- The frozen internal split contains 18 train games and four development games,
  with 22 unique games total and zero overlap or dropped games.
- The existing 513+54 Q model consumes both actions for every preference pair;
  ranking-loss direction and checkpoint reload tests pass.
- The CPU smoke completes with finite losses and metrics. Independent checkpoint
  reload reproduces the report, and a temporary rerun reproduces the frozen
  split and predictions/metrics under the same environment and recipe.
- All reported train/development metrics are marked pipeline-only;
  `capability_claim_allowed=false` and `checkpoint_promotion_allowed=false`.
- Locked-test and complete-bundle loads: 0. Extra training targets, hidden or
  future information, website games, Arena evaluation, website Shadow,
  checkpoint promotion, and model-controlled website actions: 0.
- Teacher v6, teacher v5, extension v5 train/development, and frozen semantics
  remain unchanged. Credential occurrences in new tracked/curated files: 0.
- Handoff updates, focused tests, deterministic audits, conventional commit,
  and push all succeed before the stage Goal is marked complete.

## Ready-to-Use Goal Prompt

请创建一个阶段 Goal：只使用 SHA-256 为
`a74416e6facb28a1bc64563eba90cb33d460dc9e59cc2109518da142465e15f8` 的
`website_information_set_teacher_dataset_v6.pth`，完成冻结的
teacher-preference 训练管线 smoke。严格校验 22 条标签、22 个独立游戏、
513/54 维度、合法且不同的 teacher/behavior action、train-only 来源及
locked-test 零使用；按 `sha256("website_teacher_v6_split_v1:" + game_id)`
排序，将前 4 个完整游戏分到内部 pipeline-development、其余 18 个分到
pipeline-train。复用现有 513+54 Q 模型，仅用 pairwise logistic/softplus
损失令 teacher action 排在 behavior action 之前；CPU、seed 20260714、无
初始化 checkpoint、无调参或 checkpoint 选择。产出冻结 split manifest、
一次 smoke 报告和忽略的 checkpoint，独立 reload 并用临时输出复跑验证可
复现性。所有指标只能标记为 pipeline-only，严禁加载 complete bundle 或
locked-test，严禁 Arena、网站 Shadow、网站对局、checkpoint 提升、能力
结论或模型控制网站。只完成本阶段；更新交接、验证、凭据零命中、commit
并 push 全部成功后才能完成 Goal。
