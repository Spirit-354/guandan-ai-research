# NEXT_TASK.md

## Single Next Stage

Run the Extension v5 information-set teacher candidate expansion. Enumerate all
new train decisions, screen every eligible state, confirm only robust signals,
and rebuild teacher v6 from frozen teacher v5 plus accepted new labels.

Do not run website games, train a model, run offline capability evaluation, or
begin model-controlled website play in this stage, even if the 20-game teacher
gate is reached.

## Frozen Inputs

- Only permitted rollout dataset:
  `website_danzero_shadow_extension_v5.train_dev.pth`.
- Permitted dataset SHA-256:
  `e5e220c3c770116ca9d01478e98e610dd6309a0f3d6c17088a8328f62b47174b`.
- Required dataset metadata:
  `partition_role=train_development`, `contains_locked_test_samples=false`,
  `all_samples_information_set_consistent=true`.
- Extension v5 manifest content hash:
  `a2931c6078487662d25f115896034311354eade265bec8b72f94ea2d5a7bdaf7`.
- Frozen teacher base:
  `website_information_set_teacher_dataset_v5.pth`.
- Frozen teacher v5 SHA-256:
  `155fc348e939490bc036b2b5e3e0993be732b259250cac3d0244e888910fb9da`.
- Frozen teacher v5 contains 19 labels from 19 independent games.
- New train game IDs, and no others: `14058`, `14059`, `14061`, `14063`,
  `14064`, `14066`, `14068`, `14070`, `14072`, `14074`, `14077`, and
  `14081`.
- These games contain exactly 345 consistent train decisions and 11,587 legal
  candidates before rollout eligibility filtering.
- Write the rebuilt artifact only as
  `website_information_set_teacher_dataset_v6.pth`; never overwrite teacher v5.
- The teacher v6 output and all stage-prefixed rollout outputs must be unused
  before execution.

## Information-Set and Label Rules

- Do not load `website_danzero_shadow_extension_v5.pth` or
  `website_danzero_shadow_extension_v5.locked_test.pth` for selection,
  screening, tuning, or label construction.
- Use only decision-time visible state, public counts/history, the actor hand,
  and the recorded exhaustive website-oracle legal mask.
- Do not use teammate/opponent true hands, future actions, future states,
  terminal outcomes as features, or post-game-only information.
- Hidden-card simulation must use the existing legal uniform physical
  assignment conditioned on public counts and the stable
  game/turn/determinization seed scheme.
- Enumerate all 345 new decisions. Report every ineligible state and reason;
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
- Timeout, incomplete, unstable-seed, high-variance, low-advantage, non-robust,
  hidden-information, or remap-failing results must be rejected.
- Preserve all 19 frozen teacher v5 samples exactly after deserialization.
  Recover every new 54-dimensional teacher action from the source legal action
  and physical-card metadata; behavior action and source state must match.

## Required Work

1. Re-read the canonical handoffs and verify Git state, frozen hashes, dataset
   partition metadata, teacher v5 contents, and that teacher v6 and all planned
   stage-prefixed rollout outputs do not exist.
2. Enumerate the 345 decisions in the 12 permitted game IDs and report eligible
   and ineligible counts by game and reason.
3. Run greedy-only 8-rollout screening for every eligible state, with zero
   strong-label acceptance.
4. Select confirmation candidates only from frozen positive-lower-bound,
   low-variance screen evidence, prioritizing one strongest state per game.
5. Run 16-rollout greedy-plus-frozen-tempo confirmation. If a game fails, test
   only its remaining positive-screen alternatives; do not broaden to negative
   or zero-lower-bound candidates.
6. Build teacher v6 from frozen teacher v5 plus all and only accepted new labels.
7. Audit frozen-prefix identity, source state, behavior action, legal teacher
   action, physical-card remap, dimensions, thresholds, independent-game count,
   and the 20-game gate.
8. Keep raw rollout JSON and teacher PTH ignored. Update `PROJECT_STATE.md`,
   `EXPERIMENTS.md`, `NEXT_TASK.md`, and the durable progress document; run
   tests, credential/diff checks, commit, and push.

## Acceptance Criteria

- New decisions enumerated: 345; all eligible states screened; every ineligible
  state has a reported frozen reason.
- Complete bundle and locked-test partition loads: 0; locked-test states used: 0.
- Hidden teammate/opponent hands, future information, and post-game feature
  use: 0.
- Greedy-only accepted strong labels: 0; incomplete rollout files accepted: 0.
- Every new label passes the frozen 16-rollout completeness, variance,
  advantage, positive-confidence, and greedy/frozen-tempo dual-robustness gates.
- Frozen teacher v5 labels changed or removed: 0; source-state,
  behavior-action, legal-action, 513/54 dimension, and physical-card remap
  errors: 0.
- Teacher v6 accurately reports new labels, total labels, independent games,
  and whether the 20-game teacher gate is reached.
- Website games, model training, offline capability evaluation, and
  model-controlled website play in this stage: 0 regardless of gate status.
- Frozen extension v5 and teacher v5 hashes remain unchanged; credential
  occurrences in new tracked/curated files: 0.
- Handoff updates, narrow tests, conventional commit, and push all succeed
  before the stage Goal is marked complete.

## Ready-to-Use Goal Prompt

请创建一个阶段 Goal：完成 extension v5 新增 12 个 train 游戏的全量信息集
teacher candidate 筛选、稳健双 continuation 确认和 teacher v6 重建。只能加载
`website_danzero_shadow_extension_v5.train_dev.pth`，严禁加载 complete bundle
或 locked-test partition；只处理 game_id `14058`、`14059`、`14061`、`14063`、
`14064`、`14066`、`14068`、`14070`、`14072`、`14074`、`14077`、`14081`
的 345 个 train 决策。greedy-only 8-rollout 只能初筛，不能产强标签；强标签
必须至少 16 个完整配对 rollout，variance 不超过 0.50，advantage 至少 0.15，
95% 下界为正，并且 greedy 与冻结 tempo continuation 的平均优势都至少 0.15。
冻结保留 teacher v5 的 19 条标签，核验 54 维 physical-action remap，只输出
teacher v6。即使达到 20-game gate，本阶段也不得运行网站对局、训练、离线能力
评估或模型控制网站。更新交接、验证、凭据零命中、commit 和 push 全部成功后
才能完成 Goal。
