# NEXT_TASK.md

## Single Next Stage

Build and freeze Website Dataset Extension v3 by adding only the completed,
preassigned Supplement v3 train session to frozen extension v2.

Do not run website games, teacher rollout, model training, offline evaluation,
or model-controlled website play in this stage.

## Locked Conclusion From the Previous Stage

- `logs_website_shadow_supplement_train_003` contains exactly 12 completed
  verified bot-table games: 9 wins and 3 losses.
- Game IDs: 14018, 14019, 14020, 14021, 14022, 14023, 14025, 14026, 14027,
  14029, 14030, and 14031.
- The session contains 308/308 successful, exhaustive,
  information-set-consistent Shadow decisions and 8,322 legal candidates.
- All actions came from frozen `tempo_baseline`; model-controlled actions and
  all integrity counters are zero.
- Leaderboard Elo moved continuously from 2102 to 2158, net +56, with
  `metric_source=leaderboard_elo` for all 12 games.
- The session was assigned to train before collection in
  `website_dataset_extension_session_splits_v3.json`, which preserves all
  three prior assignments exactly and adds no locked-test assignment.

## Authoritative Inputs

- Frozen base manifest:
  `website_dataset_split_manifest_extension_v2.json`.
- Frozen base manifest content hash:
  `31c5bc501286ac41d3a791811c7089200e49097132bfd886aa10d281c5ddb27e`.
- Frozen extension v2 artifacts:
  - bundle SHA-256:
    `15751388b891cbc9985f21418130fad626bfaefcc7f1fd3cf0b210af2342aaeb`;
  - train/development SHA-256:
    `03d1a0967429fd75433ea3753a96c4bce43660f636a7cf9801140bd02777cc60`;
  - locked-test SHA-256:
    `b53605e702b09c8ef8b750740ddedf9c64fc150daa9a1477d9fdadbe1a61da47`;
  - manifest file SHA-256:
    `72841302506d427fdbb1c18a4fefd82b4b0615661e9a843022d11c4fd61214e3`;
  - data-card SHA-256:
    `8c866a690ed4012124caacece00b8c493e563ef31ac363eaecc73a74da11e601`.
- Cumulative assignments:
  `website_dataset_extension_session_splits_v3.json`.
- Frozen teacher v3 SHA-256, which must remain unchanged:
  `901ebe397d4fea8842e439e80cd0dfa7605985133ab01b5172bac4708a1a75b1`.
- Include every source session already recorded by extension v2 plus only
  `logs_website_shadow_supplement_train_003`.
- Write only new v3 outputs:
  - `website_danzero_shadow_extension_v3.pth`;
  - `website_danzero_shadow_extension_v3.train_dev.pth`;
  - `website_danzero_shadow_extension_v3.locked_test.pth`;
  - `website_dataset_split_manifest_extension_v3.json`;
  - `website_dataset_card_extension_v3.json`.

## Required Work

1. Re-read the canonical handoffs and verify Git state, frozen hashes, and that
   none of the v3 outputs exists before construction.
2. Record extension v2 game IDs, source paths/hashes, session assignments,
   split membership, locked-test set, and artifact hashes before rebuilding.
3. Verify the cumulative v3 assignment preserves all three prior assignments
   and adds only `logs_website_shadow_supplement_train_003: train`.
4. Build the v3 dataset from every extension v2 source session plus the new
   Supplement v3 session, using extension v2 as the frozen manifest base.
5. Freeze the v3 split manifest, physical train/development partition, isolated
   locked-test partition, and data card under the explicit v3 names.
6. Verify every old game, source hash, session, and split remains unchanged;
   verify the locked-test set is exactly identical and all 12 new games enter
   train.
7. Audit accepted/rejected games, decisions, candidates, win/loss balance,
   complete coverage fields, duplicate states, information-set consistency,
   bot-table evidence, Elo source, and model-controlled action count.
8. Verify all frozen v2 artifact hashes and teacher v3 remain unchanged. Scan
   new tracked/curated files for runtime credentials.
9. Update `PROJECT_STATE.md`, `EXPERIMENTS.md`, `NEXT_TASK.md`, and
   `docs/progress/2026-07-13-website-bot-route.md`; keep raw and large artifacts
   ignored, run the narrowest relevant tests, commit, and push.

## Acceptance Criteria

- Accepted games: 82 total, with 49 wins and 33 losses.
- Total decisions: 2,061; total legal candidates: 57,871.
- Exactly 12 new games and 308 new decisions accepted into train; new
  development or locked-test games: 0.
- Extension v2 games, source hashes, session assignments, and split changes: 0.
- Locked-test membership changes: 0; locked-test remains nine games and 90
  information-set-consistent decisions.
- Physical train/development partition: 1,190 consistent decisions, with 1,026
  train and 164 development decisions, and 45,774 legal candidates.
- Rejected new games or decisions, non-bot games, non-`leaderboard_elo` games,
  model-controlled actions, information-set errors, integrity failures, and
  duplicate states: 0.
- Dataset coverage, information-set, physical-isolation, and threshold gates
  pass; the complete bundle remains ineligible for training.
- All frozen extension v2 artifact hashes and teacher v3 remain unchanged.
- Credential occurrences in new tracked/curated files: 0.
- Website games, teacher rollouts, teacher labels, model training, offline
  evaluation, and model-controlled website play in this stage: 0.
- Handoff updates, validation, conventional commit, and push all succeed before
  the stage Goal is marked complete.

## Ready-to-Use Goal Prompt

请创建一个阶段 Goal：

目标名称：构建并冻结 Website Dataset Extension v3，只把已完成的 Supplement v3 训练会话加入 extension v2。

约束：本阶段只做数据集扩展，不运行网站对局、teacher rollout、teacher label、模型训练、离线评估或模型控制网站。以 `website_dataset_split_manifest_extension_v2.json` 为冻结基线，先核验其 content hash 为 `31c5bc501286ac41d3a791811c7089200e49097132bfd886aa10d281c5ddb27e`。使用 `website_dataset_extension_session_splits_v3.json`，完整保留三个旧分配，仅新增 `logs_website_shadow_supplement_train_003: train`。不得覆盖任何 extension v2 文件；所有输出必须使用 extension_v3 名称。必须保持旧 70 局、全部旧 source hash 与 split 完全不变，原九局 locked_test 集合完全不变，12 局新游戏只能进入 train。Elo 只能来自 `leaderboard_elo`，严禁把 `final_state["scores"]` 当作 Elo。

验收：总计 82 局、49 胜 33 负、2,061 个决策和 57,871 个候选；12 局新游戏和 308 个新决策全部接受并进入 train；旧游戏、source hash、session assignment 或 split 改动为 0；locked_test 改动为 0，仍为九局和 90 个一致决策；physical train/development partition 为 1,190 个一致决策，其中 train 1,026、development 164，候选 45,774；新游戏或决策拒绝、非机器人桌、非 leaderboard_elo、模型控制、信息集错误、完整性失败和重复状态均为 0；coverage、信息集、物理隔离和 threshold gate 全部通过；extension v2 与 teacher v3 冻结哈希不变；新 tracked/curated 文件凭据命中 0；本阶段网站对局、teacher、训练、离线评估和模型控制网站均为 0；只有全部交接、验证、commit 和 push 成功后才能完成 Goal。
