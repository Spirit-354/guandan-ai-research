# NEXT_TASK.md

## Next Task

Collect Website Shadow Supplement v2 as one baseline-only train session with
exactly 12 new completed verified bot-table games.

Do not rebuild a dataset, run teacher screening, train a model, or start
model-controlled website play in this task.

## Locked Conclusion From the Previous Stage

- `website_information_set_teacher_dataset_v2.pth` contains 11 accepted labels
  from 11 independent train games: 7 frozen v1 labels plus 4 extension v1
  labels.
- The eligible extension v1 train candidate pool is exhausted.
- At least 9 additional independent high-confidence teacher games are required
  before training may start.
- The current training gate is closed and must remain closed throughout this
  collection stage.

## Authoritative Inputs

- Use the existing frozen `tempo_baseline` as the only website action
  submitter.
- Read runtime credentials only from `GUANDAN_USER` and `GUANDAN_PASSWORD`.
- Use a new explicit session directory:
  `logs_website_shadow_supplement_train_002`.
- Preassign that session to `train`; do not alter any frozen base or extension
  v1 session assignment.
- Require verified bot tables before the first submitted action.

## Constraints

- Do not allow a model to submit any website action. Model output may be logged
  only as Shadow evidence.
- Stop before the first action if the table is not a verified bot table.
- Record leaderboard Elo from `leaderboard_elo` before and after every game;
  never infer Elo from `final_state["scores"]`.
- Preserve exhaustive website-oracle legal candidates and decision-time
  information-set consistency for every submitted action.
- Do not modify `tempo_baseline`, the website protocol, leaderboard Elo
  semantics, teacher thresholds, or frozen manifests.
- Do not load or inspect `locked_test`.
- Do not persist or print credentials, tokens, or secrets.
- Do not continue into dataset extension, teacher rollout, training, or any
  later risk stage after collection acceptance passes.

## Required Work

1. Verify Git state and re-read the canonical handoff files.
2. Verify `GUANDAN_USER` and `GUANDAN_PASSWORD` exist without printing their
   values.
3. Verify the new session directory is unused and explicitly assigned to
   `train` before collection.
4. Run with bot-table enforcement and frozen `tempo_baseline` submissions until
   exactly 12 new games complete successfully.
5. For every game, verify terminal completion, counted result, verified robot
   signature, exhaustive Shadow decisions, leaderboard Elo before/after, and
   zero model-controlled submissions.
6. Audit communication, encoding, team mapping, hand subset, local legality,
   oracle disagreement, materialization, website-rule, wildcard,
   information-set, duplicate-submit, and unrecoverable-desync counters.
7. Audit generated logs and tracked changes for credential values without
   printing them.
8. Update `PROJECT_STATE.md`, `EXPERIMENTS.md`, and `NEXT_TASK.md`; update the
   durable progress document if the collection changes a conclusion.
9. Run the narrowest relevant validation, then commit and push.

## Success Criteria

- New completed verified bot-table games: exactly 12.
- Session assignment: train only; frozen assignments changed: 0.
- Submitted actions controlled by `tempo_baseline`: all.
- Model-controlled website actions: 0.
- Non-bot actions submitted: 0.
- Every game has `leaderboard_elo` before/after and a counted terminal result.
- Shadow decisions are exhaustive and information-set consistent.
- Communication, legality, materialization, hand-subset, duplicate-submit, and
  unrecoverable-desync errors: 0.
- Credential occurrences in generated logs, tracked files, and handoffs: 0.
- Dataset rebuilds, teacher rollouts, model training, and model-controlled
  website play performed in this stage: 0.
- The next single-stage Goal prompt is written only after the collection
  conclusion is locked.

## Stage Goal Prompt

```text
请创建一个阶段 Goal：
目标名称：完成 Website Shadow Supplement v2 的 12 局 baseline-only 训练会话采集。
约束：本阶段只采集网站机器人桌 Shadow 数据。只能由冻结的 tempo_baseline 提交动作；模型只能作为观察者，model-controlled action 必须为 0。凭据只能从 GUANDAN_USER 和 GUANDAN_PASSWORD 读取，不得打印或写入文件。新会话固定使用 logs_website_shadow_supplement_train_002，并在采集前明确分配为 train；不得修改任何冻结会话分配，不得读取 locked_test。必须启用 bot-table 校验，非机器人桌在第一次动作前停止。网站 Elo 只能来自 leaderboard_elo，final_state["scores"] 仅作代理分数，不能当作 Elo。
任务：1. 检查 Git 与交接文件。2. 只验证环境变量存在，不显示其值。3. 验证新会话目录未使用并预分配为 train。4. 使用 tempo_baseline 完成恰好 12 局机器人桌对局，并记录 exhaustive Shadow 候选。5. 逐局核验完成状态、计数结果、机器人签名、leaderboard Elo 前后值和零模型控制动作。6. 审计通信、编码、队伍映射、手牌子集、合法性、oracle、物化、网站规则、逢人配、信息集、重复提交和不可恢复不同步计数。7. 对生成日志和跟踪文件做凭据零出现审计，不打印凭据。8. 更新 PROJECT_STATE.md、EXPERIMENTS.md 和 NEXT_TASK.md，运行最窄相关验证，commit 并 push。
验收：恰好 12 局新完成机器人桌游戏；全部归属新的 train 会话；冻结分配改动 0；全部提交动作来自 tempo_baseline；模型控制动作 0；非机器人桌提交动作 0；每局都有 leaderboard_elo 前后值与计数终局；Shadow 候选完整且信息集一致；所有安全与同步错误计数为 0；凭据落盘出现 0；本阶段不得重建数据集、运行 teacher rollout、训练模型或开始模型控制网站对局；只有全部验收、交接更新、验证、commit 和 push 成功后才能完成 Goal。
```
