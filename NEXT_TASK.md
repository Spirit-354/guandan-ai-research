# NEXT_TASK.md

## Next Task

Run the Website Shadow Supplement v1 baseline-only collection, then rebuild the
dataset extension.

Do not train a model in this task. Do not run model-controlled website play.

## Success Criteria

- Collect 5 train-session games in
  `logs_website_shadow_supplement_train_001`.
- Collect 3 development-session games in
  `logs_website_shadow_supplement_development_001`.
- Only `tempo_baseline` submits website actions.
- Bot-only requirement is enforced.
- Leaderboard Elo is used; `final_state["scores"]` remains proxy-only.
- Rebuild extension artifacts without changing frozen 050 splits.
- Update `PROJECT_STATE.md`, `EXPERIMENTS.md`, and this file after completion.
- Run relevant validation and commit/push.

## Required Preflight

1. Verify Git worktree state.
2. Verify credential environment variables exist without printing values.
3. Verify no model-control flags are enabled.
4. Verify `--require-bot-table` is present.

Credential values must not be written to files or printed. Use only:

- `GUANDAN_USER`
- `GUANDAN_PASSWORD`

## Commands

If credentials exist only in user-scope environment variables, import them into
the current PowerShell process before running collection. Do not echo their
values.

```powershell
$env:GUANDAN_USER = [Environment]::GetEnvironmentVariable("GUANDAN_USER", "User")
$env:GUANDAN_PASSWORD = [Environment]::GetEnvironmentVariable("GUANDAN_PASSWORD", "User")
```

Train supplement:

```powershell
python -u -B .\play_research_adaptive.py --website-shadow --profile tempo_baseline --loop --games 5 --metric elo --require-elo --require-bot-table --log-dir logs_website_shadow_supplement_train_001 --poll 8 --delay 10 --timeout 45 --retries 5
```

Development supplement:

```powershell
python -u -B .\play_research_adaptive.py --website-shadow --profile tempo_baseline --loop --games 3 --metric elo --require-elo --require-bot-table --log-dir logs_website_shadow_supplement_development_001 --poll 8 --delay 10 --timeout 45 --retries 5
```

Dataset extension build:

```powershell
$sources = @(
  "logs_website_shadow_candidates_smoke",
  "logs_website_shadow_batch_001",
  "logs_website_shadow_batch_002",
  "logs_website_shadow_batch_003",
  "logs_website_shadow_batch_004",
  "logs_website_shadow_batch_005",
  "logs_website_shadow_batch_006",
  "logs_website_shadow_batch_007",
  "logs_website_shadow_batch_008",
  "logs_website_shadow_batch_009",
  "logs_website_shadow_supplement_train_001",
  "logs_website_shadow_supplement_development_001"
) -join ","

python -u -B .\play_research_adaptive.py --build-website-danzero-dataset $sources --website-dataset-out website_danzero_shadow_extension_v1.pth --freeze-website-splits --website-base-split-manifest website_dataset_split_manifest_050.json --website-extension-session-splits website_dataset_extension_session_splits_v1.json --website-split-manifest-out website_dataset_split_manifest_extension_v1.json --website-data-card-out website_dataset_card_extension_v1.json
```

## Stage Goal Prompt For Next Run

```text
请创建一个阶段 goal：

目标名称：
完成 Website Shadow Supplement v1 baseline-only 数据补充和冻结扩展构建。

约束：
不训练模型。
不真实接管网站出牌。
只允许 tempo_baseline 提交网站动作。
必须使用 GUANDAN_USER 和 GUANDAN_PASSWORD 环境变量。
不得输出、写入或提交账号密码。
必须启用 --require-bot-table。
不得修改 tempo_baseline 核心逻辑。
不得修改服务器通信协议。
不得修改 leaderboard Elo 语义。
不得把 final_state["scores"] 当 Elo。
不得读取或使用 locked_test 进行候选设计。

任务：
1. 检查 Git 状态和当前交接文档。
2. 验证 GUANDAN_USER/GUANDAN_PASSWORD 是否存在，只输出 true/false。
3. 运行 5 局 train supplement baseline-only Shadow。
4. 运行 3 局 development supplement baseline-only Shadow。
5. 使用 base manifest 和 extension session splits 构建 extension v1 数据集。
6. 验证旧 frozen 050 split 未变化，locked_test game set 未变化。
7. 汇总 coverage、Elo bucket、lead/follow、level/wildcard/endgame/bomb 覆盖。
8. 更新 PROJECT_STATE.md、EXPERIMENTS.md、NEXT_TASK.md。
9. 运行必要测试，commit 并 push。

验收：
8 个新 completed bot-only games。
model_controlled_actions=0。
illegal_action_count=0。
materialization_fail_count=0。
hand_card_mismatch_count=0。
duplicate_submit_count=0。
unrecoverable_desync_count=0。
Elo 只来自 leaderboard_elo。
consistent train/development decisions >= 500，目标 >= 600。
输出下一阶段 goal 提示词。
```

## Following Stage Prompt Template

After the supplement dataset passes its gate, replace this file with the next
single-stage prompt:

```text
请创建一个阶段 goal：

目标名称：
完成新增 train/development 状态的信息集 teacher candidate 筛选。

约束：
不真实网站对局。
不模型接管网站。
不修改 tempo_baseline。
不修改服务器通信。
不修改 Elo 获取。
不读取 locked_test。
只使用 train/development 状态和 website_oracle legal mask。

任务：
1. 从 extension v1 train/development 中筛选高风险、高价值、覆盖不足的候选状态。
2. 使用合法信息集 determinization 做 rollout/search。
3. 记录 rollout_count、hidden_card_sampling_method、mean_return、variance、advantage、confidence。
4. 只接受低方差、优势显著、greedy 与 frozen-tempo continuation 都为正的标签。
5. 重建 teacher dataset。
6. 检查 independent high-confidence teacher games 是否达到 20。
7. 更新交接文档、验证、commit、push。

验收：
无 locked_test 访问。
无隐藏信息泄漏。
teacher label remap error=0。
如果 teacher game count < 20，不训练模型。
输出下一阶段 goal 提示词。
```

