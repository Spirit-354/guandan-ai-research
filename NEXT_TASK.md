# NEXT_TASK.md

## Single Next Stage

Build and freeze Website Dataset Extension v4 by adding only the completed,
preassigned Supplement v4 train session to frozen extension v3.

Do not run website games, teacher rollout, model training, offline evaluation,
or model-controlled website play in this stage.

## Locked Conclusion From the Previous Stage

- `logs_website_shadow_supplement_train_004` contains exactly 12 completed
  verified bot-table games: 6 wins and 6 losses.
- Game IDs: 14035, 14036, 14037, 14038, 14039, 14040, 14041, 14042, 14043,
  14044, 14045, and 14046.
- The session contains 279/279 successful, exhaustive,
  information-set-consistent Shadow decisions and 12,959 legal candidates.
- All actions came from frozen `tempo_baseline`; model-controlled actions and
  all integrity counters are zero.
- Leaderboard Elo moved continuously from 2158 to 2121, net -37, with
  `metric_source=leaderboard_elo` for all 12 games.
- The session was assigned to train before collection in
  `website_dataset_extension_session_splits_v4.json`, which preserves all four
  prior assignments exactly and adds no locked-test assignment.

## Authoritative Inputs

- Frozen base manifest:
  `website_dataset_split_manifest_extension_v3.json`.
- Frozen base manifest content hash:
  `51fe0244407d67e8267ea11b7146ff214f73823c29db92062189a58d033e5af9`.
- Frozen extension v3 artifacts:
  - bundle SHA-256:
    `0235f53f7aec87cd3f7c62a529fd2d05af899a7befa72280fe4d5da234b4ac81`;
  - train/development SHA-256:
    `e5edc7090657ac1c4b4a2b2a14f38ad9bb0145ba1c19b6e85fca20bb1b5a687a`;
  - locked-test SHA-256:
    `941c66107e93aaa5d26965aa4b3a26fee0e0fab70f73ed489d6c49eaf3d60e59`;
  - manifest file SHA-256:
    `c91cb7665e9fcca68ee0161582a2794701057611a71485527f7ab8fcf97ecc83`;
  - data-card SHA-256:
    `f8eedcec8fa6679760e5bf4e202bef19bd07ee681b040f68168b22ce8b01c177`.
- Cumulative assignments:
  `website_dataset_extension_session_splits_v4.json`.
- Frozen teacher v4 SHA-256, which must remain unchanged:
  `fa193705777987d0bad91f9a45f5aa956a02e22ffa077a04bc2c81892aeb5f99`.
- Include every source session already recorded by extension v3 plus only
  `logs_website_shadow_supplement_train_004`.
- Write only new v4 outputs:
  - `website_danzero_shadow_extension_v4.pth`;
  - `website_danzero_shadow_extension_v4.train_dev.pth`;
  - `website_danzero_shadow_extension_v4.locked_test.pth`;
  - `website_dataset_split_manifest_extension_v4.json`;
  - `website_dataset_card_extension_v4.json`.

## Required Work

1. Re-read the canonical handoffs and verify Git state, frozen hashes, and that
   none of the v4 outputs exists before construction.
2. Record extension v3 game IDs, source paths/hashes, session assignments,
   split membership, locked-test set, and artifact hashes before rebuilding.
3. Verify the cumulative v4 assignment preserves all four prior assignments
   and adds only `logs_website_shadow_supplement_train_004: train`.
4. Build the v4 dataset from every extension v3 source session plus the new
   Supplement v4 session, using extension v3 as the frozen manifest base.
5. Freeze the v4 split manifest, physical train/development partition, isolated
   locked-test partition, and data card under the explicit v4 names.
6. Verify every old game, source hash, session, and split remains unchanged;
   verify the locked-test set is exactly identical and all 12 new games enter
   train.
7. Audit accepted/rejected games, decisions, candidates, win/loss balance,
   complete coverage fields, duplicate states, information-set consistency,
   bot-table evidence, Elo source, and model-controlled action count.
8. Verify all frozen v3 artifact hashes and teacher v4 remain unchanged. Scan
   new tracked/curated files for runtime credentials.
9. Update `PROJECT_STATE.md`, `EXPERIMENTS.md`, `NEXT_TASK.md`, and
   `docs/progress/2026-07-13-website-bot-route.md`; keep raw and large artifacts
   ignored, run the narrowest relevant tests, commit, and push.

## Acceptance Criteria

- Accepted games: 94 total, with 55 wins and 39 losses.
- Total decisions: 2,340; total legal candidates: 70,830.
- Exactly 12 new games and 279 new decisions accepted into train; new
  development or locked-test games: 0.
- Extension v3 games, source hashes, session assignments, and split changes: 0.
- Locked-test membership changes: 0; locked test remains nine games and 90
  information-set-consistent decisions.
- Physical train/development partition: 1,469 consistent decisions, with 1,305
  train and 164 development decisions, and 58,733 legal candidates.
- Rejected new games or decisions, non-bot games, non-`leaderboard_elo` games,
  model-controlled actions, information-set errors, integrity failures, and
  duplicate states: 0.
- Dataset coverage, information-set, physical-isolation, and threshold gates
  pass; the complete bundle remains ineligible for training.
- All frozen extension v3 artifact hashes and teacher v4 remain unchanged.
- Credential occurrences in new tracked/curated files: 0.
- Website games, teacher rollouts, teacher labels, model training, offline
  evaluation, and model-controlled website play in this stage: 0.
- Handoff updates, validation, conventional commit, and push all succeed before
  the stage Goal is marked complete.

## Ready-to-Use Goal Prompt

请创建一个阶段 Goal：

目标名称：构建并冻结 Website Dataset Extension v4，只把已完成的 Supplement v4 训练会话加入 extension v3。

约束：本阶段只做数据集扩展，不运行网站对局、teacher rollout、teacher label、模型训练、离线评估或模型控制网站。以 `website_dataset_split_manifest_extension_v3.json` 为冻结基线，先核验其 content hash 为 `51fe0244407d67e8267ea11b7146ff214f73823c29db92062189a58d033e5af9`。使用 `website_dataset_extension_session_splits_v4.json`，完整保留四个旧分配，仅新增 `logs_website_shadow_supplement_train_004: train`。不得覆盖任何 extension v3 文件；所有输出必须使用 extension_v4 名称。必须保持旧 82 局、全部旧 source hash 与 split 完全不变，原九局 locked_test 集合完全不变，12 局新游戏只能进入 train。Elo 只能来自 `leaderboard_elo`，严禁把 `final_state["scores"]` 当作 Elo。

验收：总计 94 局、55 胜 39 负、2,340 个决策和 70,830 个候选；12 局新游戏和 279 个新决策全部接受并进入 train；旧游戏、source hash、session assignment 或 split 改动为 0；locked_test 改动为 0，仍为九局和 90 个一致决策；physical train/development partition 为 1,469 个一致决策，其中 train 1,305、development 164，候选 58,733；新游戏或决策拒绝、非机器人桌、非 leaderboard_elo、模型控制、信息集错误、完整性失败和重复状态均为 0；coverage、信息集、物理隔离和 threshold gate 全部通过；extension v3 与 teacher v4 冻结哈希不变；新 tracked/curated 文件凭据命中 0；本阶段网站对局、teacher、训练、离线评估和模型控制网站均为 0；只有全部交接、验证、commit 和 push 成功后才能完成 Goal。
