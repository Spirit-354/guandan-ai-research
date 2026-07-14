# NEXT_TASK.md

## Single Next Stage

Run Website Shadow Supplement v4 as one baseline-only collection stage. Do not
rebuild the dataset, run teacher rollout, train or evaluate a model, or begin
model-controlled website play in this stage.

## Frozen Inputs and Preconditions

- Branch: `agent/stage5-website-bot-adaptation`.
- Frozen website strategy: `tempo_baseline`; do not change its core semantics.
- Frozen extension v3 manifest content hash:
  `51fe0244407d67e8267ea11b7146ff214f73823c29db92062189a58d033e5af9`.
- Frozen extension v3 artifact SHA-256 values:
  - bundle: `0235f53f7aec87cd3f7c62a529fd2d05af899a7befa72280fe4d5da234b4ac81`;
  - train/development: `e5edc7090657ac1c4b4a2b2a14f38ad9bb0145ba1c19b6e85fca20bb1b5a687a`;
  - locked-test: `941c66107e93aaa5d26965aa4b3a26fee0e0fab70f73ed489d6c49eaf3d60e59`.
- Frozen teacher v4 SHA-256:
  `fa193705777987d0bad91f9a45f5aa956a02e22ffa077a04bc2c81892aeb5f99`.
- Teacher gate: 16 of 20 independent high-confidence games; training remains
  prohibited.
- Extend the existing cumulative session assignment into
  `website_dataset_extension_session_splits_v4.json`. Preserve every existing
  session assignment exactly and preassign only the unused session
  `logs_website_shadow_supplement_train_004` to `train` before collection.
- Runtime credentials must come only from `GUANDAN_USER` and
  `GUANDAN_PASSWORD`. Do not print or persist their values.

## Scope

1. Re-read the canonical handoffs and verify the frozen hashes, current branch,
   clean starting worktree, cumulative v3 session assignments, and that the new
   session directory and cumulative v4 assignment output are unused.
2. Create the cumulative v4 assignment file before website play. Existing
   train/development assignments and the locked-test set must not change; the
   new session must be assigned only to train.
3. Collect exactly 12 completed verified bot-table games in
   `logs_website_shadow_supplement_train_004`.
4. Stop any non-bot table before the first submitted action. Only frozen
   `tempo_baseline` may submit actions; model suggestions may be observed but
   must never control or be submitted.
5. For every decision, retain exhaustive website-oracle candidates and a
   decision-time-consistent information set. Do not use hidden hands, future
   actions, future states, or post-game information as features.
6. Read and record actual `leaderboard_elo` before and after every completed
   game. Never treat `final_state["scores"]` as Elo.
7. Audit game count, wins/losses, Elo continuity, decisions, successful
   submissions, bot/table signature, candidate exhaustiveness, information-set
   consistency, model-control count, and all safety/error counters.
8. Do not rebuild extension v4, screen teacher candidates, build teacher v5,
   train a model, run offline Arena, or start model-controlled website play.
9. Update `PROJECT_STATE.md`, `EXPERIMENTS.md`, `NEXT_TASK.md`, and
   `docs/progress/2026-07-13-website-bot-route.md`; keep raw logs and large JSON
   ignored. Run validation, scan tracked/curated changes for credentials,
   commit with a conventional message, and push.

## Acceptance Criteria

- New preassigned train sessions: exactly 1; changed prior assignments: 0;
  locked-test membership changes: 0.
- Completed verified bot-only website games: exactly 12.
- Every website action is submitted by frozen `tempo_baseline`; model-controlled
  or model-suggestion-submitted actions: 0.
- Every submission succeeds and every retained decision has exhaustive
  website-oracle candidates plus a consistent decision-time information set.
- Non-bot actions, failed games, communication, encoding, team mapping,
  hand-subset, legality, oracle, materialization, website-rule, wildcard,
  information-set, duplicate-submit, and unrecoverable-desync errors: 0.
- Each game has continuous `leaderboard_elo` before/after evidence; inferred
  Elo from final-state scores: 0.
- Dataset builds, teacher rollouts, teacher labels, model training, offline
  evaluation, and model-controlled website play in this stage: 0.
- Frozen extension v3 and teacher v4 hashes remain unchanged.
- Credential occurrences in new tracked/curated files: 0.
- Handoff updates, validation, conventional commit, and push all succeed before
  the stage Goal is marked complete.

## Ready-to-Use Goal Prompt

请创建一个阶段 Goal：

目标名称：完成 Website Shadow Supplement v4 的 12 局基线专用训练会话采集。

约束：先在 `website_dataset_extension_session_splits_v4.json` 中完整保留既有累计分配，并将唯一的新会话 `logs_website_shadow_supplement_train_004` 预分配到 train；新目录和输出必须未使用。只能由冻结 `tempo_baseline` 提交网站动作，遇到非机器人桌必须在首个动作前停止。凭据只从 `GUANDAN_USER` 和 `GUANDAN_PASSWORD` 读取，不得打印、落盘或提交。每个决策保留 exhaustive website-oracle candidates 和决策时一致的信息集；不得使用隐藏手牌、未来动作或赛后信息。每局 Elo 必须来自 `leaderboard_elo`，严禁把 `final_state["scores"]` 当 Elo。本阶段不得重建数据集、运行 teacher rollout、构建 teacher v5、训练模型、运行离线评估或进行模型控制网站对局。

验收：恰好 12 局完成且均为 verified bot table；全部动作由 `tempo_baseline` 提交；提交成功率 100%；candidate exhaustiveness 与 information-set consistency 100%；非机器人动作、失败局、通信、编码、队伍映射、手牌子集、合法性、oracle、materialization、网站规则、wildcard、信息集、重复提交、不可恢复 desync 和模型控制计数均为 0；每局 `leaderboard_elo` 前后连续可核验；旧 session assignment 和 locked-test 变化均为 0；extension v3 与 teacher v4 冻结哈希不变；新 tracked/curated 文件凭据命中 0；更新全部交接文件、运行验证、commit 并 push，全部满足后才能完成 Goal。
