# NEXT_TASK.md

## Next Task

Build and freeze Website Dataset Extension v2 by adding the completed
Supplement v2 train session to extension v1 without changing any existing game
or split.

Do not run website games, teacher rollout, model training, or model-controlled
website play in this task.

## Locked Conclusion From the Previous Stage

- `logs_website_shadow_supplement_train_002` contains exactly 12 completed
  verified bot-table games: 8 wins and 4 losses.
- The session contains 280/280 successful, exhaustive,
  information-set-consistent Shadow decisions.
- All submitted actions came from frozen `tempo_baseline`; model-controlled
  actions and all integrity counters are zero.
- Leaderboard Elo moved from 2060 to 2102, net +42, with
  `metric_source=leaderboard_elo` for all 12 games.
- The session was assigned to train before collection in
  `website_dataset_extension_session_splits_v2.json`.

## Authoritative Inputs

- Frozen base for this extension:
  `website_dataset_split_manifest_extension_v1.json`.
- Frozen base manifest content hash:
  `db209561f6961b289dda668861687fcd7a258a2f283cecaae065501b2006f429`.
- Cumulative extension assignments:
  `website_dataset_extension_session_splits_v2.json`.
- Include all source sessions used by extension v1 plus
  `logs_website_shadow_supplement_train_002`.
- Write only new v2 outputs:
  - `website_danzero_shadow_extension_v2.pth`;
  - `website_danzero_shadow_extension_v2.train_dev.pth`;
  - `website_danzero_shadow_extension_v2.locked_test.pth`;
  - `website_dataset_split_manifest_extension_v2.json`;
  - `website_dataset_card_extension_v2.json`.

## Constraints

- Do not overwrite or modify any extension v1 dataset, partition, manifest, or
  data card.
- Preserve all 58 extension v1 games and their existing splits exactly.
- Preserve the exact nine-game locked-test set; no supplement v2 game may enter
  development or locked test.
- All 12 new games must enter train through their preassigned session.
- Use only `leaderboard_elo`; never treat `final_state["scores"]` as Elo.
- Reject any game that is incomplete, uncounted, non-bot, non-exhaustive,
  information-set inconsistent, model-controlled, or fails an integrity gate.
- Keep raw and large dataset artifacts ignored; commit only small curated
  manifests, data cards, code changes if required, and handoff documents.
- Do not continue into teacher screening, training, offline evaluation, or
  website play after the extension passes.

## Required Work

1. Verify Git state and re-read the canonical handoff files.
2. Verify the extension v1 manifest content hash and record its complete game,
   session, split, and locked-test membership before rebuilding.
3. Verify the cumulative v2 assignment file preserves the two v1 supplement
   assignments and adds only `logs_website_shadow_supplement_train_002: train`.
4. Build `website_danzero_shadow_extension_v2.pth` from all extension v1 source
   sessions plus the new supplement session, using extension v1 as the frozen
   base manifest.
5. Freeze the v2 split manifest, physical train/development partition, isolated
   locked-test partition, and data card under the explicit v2 names.
6. Verify every old game and session retains its extension v1 split, the locked
   game set is exactly unchanged, and all 12 new game IDs enter train.
7. Audit accepted/rejected games, decisions, candidates, win/loss balance,
   complete coverage fields, duplicate states, information-set consistency,
   bot-table evidence, Elo source, and model-controlled action count.
8. Verify old extension v1 artifact hashes are unchanged and runtime credential
   occurrences in new curated/tracked files are zero.
9. Update `PROJECT_STATE.md`, `EXPERIMENTS.md`, and `NEXT_TASK.md`; update the
   durable progress document with the locked extension conclusion.
10. Run the narrowest relevant tests, then commit and push.

## Success Criteria

- Accepted complete bot-only games: 70 total, including all 12 new train games.
- Win/loss balance: 40 wins and 30 losses.
- Total decisions: 1,753; new session decisions accepted: 280.
- Extension v1 game or session split changes: 0.
- Locked-test membership changes: 0; locked-test game count remains 9.
- New game split counts: train 12, development 0, locked test 0.
- Model-controlled actions, non-bot games, integrity failures, and rejected new
  games or decisions: 0.
- Information-set-consistent train/development decisions: 882, with 718 train
  and 164 development decisions.
- Duplicate-state rate is reported and the existing coverage gate passes.
- Extension v1 artifact hashes remain unchanged; credential occurrences in new
  tracked/curated files: 0.
- Website games, teacher rollouts, model training, and model-controlled website
  play performed in this stage: 0.
- The next single-stage Goal prompt is written only after the v2 conclusion is
  locked.

## Stage Goal Prompt

```text
请创建一个阶段 Goal：
目标名称：构建并冻结 Website Dataset Extension v2，只把已完成的 Supplement v2 训练会话加入 extension v1。
约束：本阶段只做数据集扩展，不运行网站对局、teacher rollout、模型训练或模型控制网站。以 website_dataset_split_manifest_extension_v1.json 为冻结基线，先核验其 content hash 为 db209561f6961b289dda668861687fcd7a258a2f283cecaae065501b2006f429。使用 website_dataset_extension_session_splits_v2.json，保留两个 v1 supplement 分配，仅新增 logs_website_shadow_supplement_train_002: train。不得覆盖任何 extension v1 文件；所有输出必须使用 extension_v2 名称。必须保持旧 58 局及其 split 完全不变，原九局 locked_test 集合完全不变，12 局新游戏只能进入 train。Elo 只能来自 leaderboard_elo，final_state["scores"] 不能当作 Elo。
任务：1. 检查 Git 与全部交接文件。2. 记录并核验 extension v1 的完整游戏、会话、split、locked_test 集合和 artifact hash。3. 核验 v2 session assignment。4. 从 extension v1 的全部源会话加 logs_website_shadow_supplement_train_002 构建 website_danzero_shadow_extension_v2.pth。5. 冻结新的 train_dev、locked_test、split manifest 和 data card。6. 验证旧游戏与分配零变化、locked_test 零变化、12 个新 game_id 全部为 train。7. 审计游戏、决策、候选、胜负、完整 coverage、重复状态、信息集一致性、机器人桌、Elo source 和模型控制计数。8. 核验旧 v1 artifact hash 未变及凭据零出现。9. 更新交接与进展文档，运行最窄相关验证，commit 并 push。
验收：总计 70 局、40 胜 30 负、1,753 个决策；12 局新游戏和 280 个新决策全部接受且全部进入 train；旧游戏或会话 split 改动 0；locked_test 改动 0 且仍为 9 局；模型控制动作、非机器人桌、完整性失败、新游戏或决策拒绝均为 0；信息集一致的 train/development 决策为 882，其中 train 718、development 164；重复状态率已报告且 coverage gate 通过；extension v1 hash 不变；新 tracked/curated 文件凭据出现 0；本阶段网站对局、teacher rollout、训练和模型控制网站均为 0；只有全部验收、交接、验证、commit 和 push 成功后才能完成 Goal。
```
