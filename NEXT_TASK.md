# NEXT_TASK.md

## Single Next Stage

Run the Extension v3 information-set teacher candidate expansion. Enumerate all
new train decisions, screen every eligible state, confirm only robust signals,
and rebuild teacher v4 from frozen teacher v3 plus accepted new labels.

Do not run website games, train a model, run offline capability evaluation, or
begin model-controlled website play in this stage, even if the 20-game teacher
gate is reached.

## Frozen Inputs

- Only permitted rollout dataset:
  `website_danzero_shadow_extension_v3.train_dev.pth`.
- Permitted dataset SHA-256:
  `e5edc7090657ac1c4b4a2b2a14f38ad9bb0145ba1c19b6e85fca20bb1b5a687a`.
- Required dataset metadata:
  `partition_role=train_development`, `contains_locked_test_samples=false`,
  `all_samples_information_set_consistent=true`.
- Extension v3 manifest content hash:
  `51fe0244407d67e8267ea11b7146ff214f73823c29db92062189a58d033e5af9`.
- Frozen teacher base:
  `website_information_set_teacher_dataset_v3.pth`.
- Frozen teacher v3 SHA-256:
  `901ebe397d4fea8842e439e80cd0dfa7605985133ab01b5172bac4708a1a75b1`.
- Frozen teacher v3 contains 13 labels from 13 independent games.
- New train game IDs, and no others:
  `14018`, `14019`, `14020`, `14021`, `14022`, `14023`, `14025`, `14026`,
  `14027`, `14029`, `14030`, and `14031`.
- These games contain exactly 308 consistent train decisions and 8,322 legal
  candidates before rollout eligibility filtering.
- Write the rebuilt artifact only as
  `website_information_set_teacher_dataset_v4.pth`; never overwrite teacher v3.

## Information-Set and Label Rules

- Do not load `website_danzero_shadow_extension_v3.pth` or
  `website_danzero_shadow_extension_v3.locked_test.pth` for selection,
  screening, tuning, or label construction.
- Use only decision-time visible state, public counts/history, the actor hand,
  and the recorded exhaustive website-oracle legal mask.
- Do not use teammate/opponent true hands, future actions, future states,
  terminal outcomes as features, or post-game-only information.
- Hidden-card simulation must use the existing legal uniform physical
  assignment conditioned on public counts and the stable
  game/turn/determinization seed scheme.
- Enumerate all 308 new decisions. Report every ineligible state and reason;
  screen every eligible state.
- Greedy-only 8-rollout results are screening evidence only and must emit zero
  strong labels.
- Confirm only positive-95%-lower-bound, low-variance screen signals, with
  independent-game coverage prioritized before alternatives from the same
  game.
- A strong label requires at least 16 complete paired rollouts, shared complete
  determinizations, candidate return variance at most 0.50, candidate advantage
  at least 0.15, positive 95% lower bound, and at least 0.15 mean advantage
  under both greedy and frozen `tempo_baseline` continuations.
- Timeout, incomplete, unstable-seed, high-variance, low-advantage,
  non-robust, hidden-information, or remap-failing results must be rejected.
- Preserve all 13 frozen teacher v3 samples exactly after deserialization.
  Recover every new 54-dimensional teacher action from the source legal action
  and physical-card metadata; behavior action and source state must match.

## Required Work

1. Re-read the canonical handoffs and verify Git state, frozen hashes, dataset
   partition metadata, teacher v3 contents, and that teacher v4 does not exist.
2. Enumerate the 308 decisions in the 12 permitted game IDs and report eligible
   and ineligible counts by game and reason.
3. Run greedy-only 8-rollout screening for every eligible state, with zero
   strong-label acceptance.
4. Select confirmation candidates only from frozen positive-lower-bound,
   low-variance screen evidence, prioritizing one strongest state per game.
5. Run 16-rollout greedy-plus-frozen-tempo confirmation. If a game fails, test
   only its remaining positive-screen alternatives; do not broaden to negative
   or zero-lower-bound candidates.
6. Build teacher v4 from frozen teacher v3 plus all and only accepted new labels.
7. Audit frozen-prefix identity, source state, behavior action, legal teacher
   action, physical-card remap, dimensions, thresholds, independent-game count,
   and the 20-game gate.
8. Keep raw rollout JSON and teacher PTH ignored. Update `PROJECT_STATE.md`,
   `EXPERIMENTS.md`, `NEXT_TASK.md`, and the durable progress document; run
   tests, credential/diff checks, commit, and push.

## Acceptance Criteria

- New decisions enumerated: 308; all eligible states screened; every ineligible
  state has a reported frozen reason.
- Complete bundle and locked-test partition loads: 0; locked-test states used: 0.
- Hidden teammate/opponent hands, future information, and post-game feature
  use: 0.
- Greedy-only accepted strong labels: 0; incomplete rollout files accepted: 0.
- Every new label passes the frozen 16-rollout completeness, variance,
  advantage, positive-confidence, and greedy/frozen-tempo dual-robustness gates.
- Frozen teacher v3 labels changed or removed: 0; source-state, behavior-action,
  legal-action, 513/54 dimension, and physical-card remap errors: 0.
- Teacher v4 accurately reports new labels, total labels, independent games,
  and whether the 20-game teacher gate is reached.
- Website games, model training, offline capability evaluation, and
  model-controlled website play in this stage: 0 regardless of gate status.
- Frozen extension v3 and teacher v3 hashes remain unchanged; credential
  occurrences in new tracked/curated files: 0.
- Handoff updates, narrow tests, conventional commit, and push all succeed
  before the stage Goal is marked complete.

## Ready-to-Use Goal Prompt

请创建一个阶段 Goal：

目标名称：完成 extension v3 新增 12 个 train 游戏的全量信息集 teacher candidate 筛选、稳健双 continuation 确认和 teacher v4 重建。

约束：本阶段不得运行网站对局、训练模型、离线能力评估或模型控制网站。只能加载 `website_danzero_shadow_extension_v3.train_dev.pth`，其 SHA-256 必须为 `e5edc7090657ac1c4b4a2b2a14f38ad9bb0145ba1c19b6e85fca20bb1b5a687a`；严禁加载 complete bundle 或 locked-test partition。只处理 game_id 14018、14019、14020、14021、14022、14023、14025、14026、14027、14029、14030、14031 的 308 个 train 决策。只能使用决策点可见信息和 exhaustive website-oracle legal mask；隐藏牌模拟必须采用现有合法信息集 determinization。greedy-only 8-rollout 只能初筛，不能产强标签。强标签必须至少 16 个完整配对 rollout，candidate variance 不超过 0.50，candidate advantage 至少 0.15，95% 下界为正，并且 greedy 与冻结 tempo continuation 的平均优势都至少为 0.15。冻结保留 teacher v3 的 13 条标签，核验 54 维 physical-action remap，并只输出新的 teacher v4。即使独立 teacher 游戏达到 20，本阶段也不得训练。

验收：308 个新增 train 决策全部枚举，所有 eligible 状态完成筛选且所有 ineligible 原因有报告；locked-test 和 complete bundle 访问 0；隐藏或未来信息使用 0；greedy-only 接受标签 0；不完整 rollout 接受 0；每个新增标签通过 16-rollout、方差、优势、正 95% 下界及 greedy/frozen-tempo 双稳健门槛；teacher v3 旧标签改动或删除 0；source state、behavior action、legal action、513/54 维度和 physical-action remap error 均为 0；teacher v4 准确报告新增、总标签、独立游戏和 20-game gate；本阶段网站对局、训练、离线评估和模型控制网站均为 0；冻结哈希不变且凭据命中 0；只有全部交接、验证、commit 和 push 成功后才能完成 Goal。
