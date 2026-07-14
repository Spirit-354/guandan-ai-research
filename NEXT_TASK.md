# NEXT_TASK.md

## Single Next Stage

Run the Extension v4 information-set teacher candidate expansion. Enumerate all
new train decisions, screen every eligible state, confirm only robust signals,
and rebuild teacher v5 from frozen teacher v4 plus accepted new labels.

Do not run website games, train a model, run offline capability evaluation, or
begin model-controlled website play in this stage, even if the 20-game teacher
gate is reached.

## Frozen Inputs

- Only permitted rollout dataset:
  `website_danzero_shadow_extension_v4.train_dev.pth`.
- Permitted dataset SHA-256:
  `ad4da83e2af29c580a1b1d8fe70a06f88fc645525ab025945a7be48fd349fde1`.
- Required dataset metadata:
  `partition_role=train_development`, `contains_locked_test_samples=false`,
  `all_samples_information_set_consistent=true`.
- Extension v4 manifest content hash:
  `368771a6a647d34d0d6fcd0490d7cdd1e57991a4c4188e3c127780a5323acbec`.
- Frozen teacher base:
  `website_information_set_teacher_dataset_v4.pth`.
- Frozen teacher v4 SHA-256:
  `fa193705777987d0bad91f9a45f5aa956a02e22ffa077a04bc2c81892aeb5f99`.
- Frozen teacher v4 contains 16 labels from 16 independent games.
- New train game IDs, and no others:
  `14035`, `14036`, `14037`, `14038`, `14039`, `14040`, `14041`, `14042`,
  `14043`, `14044`, `14045`, and `14046`.
- These games contain exactly 279 consistent train decisions and 12,959 legal
  candidates before rollout eligibility filtering.
- Write the rebuilt artifact only as
  `website_information_set_teacher_dataset_v5.pth`; never overwrite teacher v4.

## Information-Set and Label Rules

- Do not load `website_danzero_shadow_extension_v4.pth` or
  `website_danzero_shadow_extension_v4.locked_test.pth` for selection,
  screening, tuning, or label construction.
- Use only decision-time visible state, public counts/history, the actor hand,
  and the recorded exhaustive website-oracle legal mask.
- Do not use teammate/opponent true hands, future actions, future states,
  terminal outcomes as features, or post-game-only information.
- Hidden-card simulation must use the existing legal uniform physical
  assignment conditioned on public counts and the stable
  game/turn/determinization seed scheme.
- Enumerate all 279 new decisions. Report every ineligible state and reason;
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
- Preserve all 16 frozen teacher v4 samples exactly after deserialization.
  Recover every new 54-dimensional teacher action from the source legal action
  and physical-card metadata; behavior action and source state must match.

## Required Work

1. Re-read the canonical handoffs and verify Git state, frozen hashes, dataset
   partition metadata, teacher v4 contents, and that teacher v5 does not exist.
2. Enumerate the 279 decisions in the 12 permitted game IDs and report eligible
   and ineligible counts by game and reason.
3. Run greedy-only 8-rollout screening for every eligible state, with zero
   strong-label acceptance.
4. Select confirmation candidates only from frozen positive-lower-bound,
   low-variance screen evidence, prioritizing one strongest state per game.
5. Run 16-rollout greedy-plus-frozen-tempo confirmation. If a game fails, test
   only its remaining positive-screen alternatives; do not broaden to negative
   or zero-lower-bound candidates.
6. Build teacher v5 from frozen teacher v4 plus all and only accepted new labels.
7. Audit frozen-prefix identity, source state, behavior action, legal teacher
   action, physical-card remap, dimensions, thresholds, independent-game count,
   and the 20-game gate.
8. Keep raw rollout JSON and teacher PTH ignored. Update `PROJECT_STATE.md`,
   `EXPERIMENTS.md`, `NEXT_TASK.md`, and the durable progress document; run
   tests, credential/diff checks, commit, and push.

## Acceptance Criteria

- New decisions enumerated: 279; all eligible states screened; every ineligible
  state has a reported frozen reason.
- Complete bundle and locked-test partition loads: 0; locked-test states used: 0.
- Hidden teammate/opponent hands, future information, and post-game feature
  use: 0.
- Greedy-only accepted strong labels: 0; incomplete rollout files accepted: 0.
- Every new label passes the frozen 16-rollout completeness, variance,
  advantage, positive-confidence, and greedy/frozen-tempo dual-robustness gates.
- Frozen teacher v4 labels changed or removed: 0; source-state, behavior-action,
  legal-action, 513/54 dimension, and physical-card remap errors: 0.
- Teacher v5 accurately reports new labels, total labels, independent games,
  and whether the 20-game teacher gate is reached.
- Website games, model training, offline capability evaluation, and
  model-controlled website play in this stage: 0 regardless of gate status.
- Frozen extension v4 and teacher v4 hashes remain unchanged; credential
  occurrences in new tracked/curated files: 0.
- Handoff updates, narrow tests, conventional commit, and push all succeed
  before the stage Goal is marked complete.

## Ready-to-Use Goal Prompt

请创建一个阶段 Goal：

目标名称：完成 extension v4 新增 12 个 train 游戏的全量信息集 teacher candidate 筛选、稳健双 continuation 确认和 teacher v5 重建。

约束：本阶段不得运行网站对局、训练模型、离线能力评估或模型控制网站。只能加载 `website_danzero_shadow_extension_v4.train_dev.pth`，其 SHA-256 必须为 `ad4da83e2af29c580a1b1d8fe70a06f88fc645525ab025945a7be48fd349fde1`；严禁加载 complete bundle 或 locked-test partition。只处理 game_id 14035 至 14046 的 279 个 train 决策。只能使用决策点可见信息和 exhaustive website-oracle legal mask；隐藏牌模拟必须采用现有合法信息集 determinization。greedy-only 8-rollout 只能初筛，不能产强标签。强标签必须至少 16 个完整配对 rollout，candidate variance 不超过 0.50，candidate advantage 至少 0.15，95% 下界为正，并且 greedy 与冻结 tempo continuation 的平均优势都至少为 0.15。冻结保留 teacher v4 的 16 条标签，核验 54 维 physical-action remap，并只输出新的 teacher v5。即使独立 teacher 游戏达到 20，本阶段也不得训练。

验收：279 个新增 train 决策全部枚举，所有 eligible 状态完成筛选且所有 ineligible 原因有报告；locked-test 和 complete bundle 访问 0；隐藏或未来信息使用 0；greedy-only 接受标签 0；不完整 rollout 接受 0；每个新增标签通过 16-rollout、方差、优势、正 95% 下界及 greedy/frozen-tempo 双稳健门槛；teacher v4 旧标签改动或删除 0；source state、behavior action、legal action、513/54 维度和 physical-action remap error 均为 0；teacher v5 准确报告新增、总标签、独立游戏和 20-game gate；本阶段网站对局、训练、离线评估和模型控制网站均为 0；冻结哈希不变且凭据命中 0；只有全部交接、验证、commit 和 push 成功后才能完成 Goal。
