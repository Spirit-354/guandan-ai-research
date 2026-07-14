# NEXT_TASK.md

## Single Next Stage

Run Website Shadow Supplement v5 as one baseline-only collection stage. Do not
rebuild the dataset, run teacher rollout, create teacher labels, train or
evaluate a model, or begin model-controlled website play in this stage.

## Frozen Inputs and Preconditions

- Branch: `agent/stage5-website-bot-adaptation`.
- Frozen website strategy: `tempo_baseline`; do not change its core semantics.
- Frozen extension v4 manifest content hash:
  `368771a6a647d34d0d6fcd0490d7cdd1e57991a4c4188e3c127780a5323acbec`.
- Frozen extension v4 artifact SHA-256 values:
  - bundle: `c8c05785defe37e589b99b3071b58c43d20ed1f1cf87fdb3c031a196151dcf87`;
  - train/development: `ad4da83e2af29c580a1b1d8fe70a06f88fc645525ab025945a7be48fd349fde1`;
  - locked-test: `cec1aba85cfbc388345d5ac17fd1ec48ec02642fb5743bed76513f872b7a512d`.
- Frozen teacher v5 SHA-256:
  `155fc348e939490bc036b2b5e3e0993be732b259250cac3d0244e888910fb9da`.
- Teacher gate: 19 of 20 independent high-confidence games; training remains
  prohibited.
- Extend the existing cumulative session assignment into
  `website_dataset_extension_session_splits_v5.json`. Preserve every existing
  assignment exactly and preassign only the unused session
  `logs_website_shadow_supplement_train_005` to `train` before collection.
- The v5 assignment output and session directory are currently unused.
- Runtime credentials must come only from `GUANDAN_USER` and
  `GUANDAN_PASSWORD`. Do not print or persist their values.

## Scope

1. Re-read the canonical handoffs and verify the frozen hashes, current branch,
   clean starting worktree, cumulative v4 session assignments, and that the new
   session directory and cumulative v5 assignment output remain unused.
2. Create the cumulative v5 assignment file before website play. Existing
   train/development assignments and the locked-test set must not change; the
   new session must be assigned only to train.
3. Collect exactly 12 completed verified bot-table games in
   `logs_website_shadow_supplement_train_005`.
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
8. Do not rebuild extension v5, screen teacher candidates, build teacher v6,
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
- Frozen extension v4 and teacher v5 hashes remain unchanged.
- Credential occurrences in new tracked/curated files: 0.
- Handoff updates, validation, conventional commit, and push all succeed before
  the stage Goal is marked complete.

## Ready-to-Use Goal Prompt

请创建一个阶段 Goal：

目标名称：完成 Website Shadow Supplement v5 的 12 局基线专用训练会话采集。

约束：先在 `website_dataset_extension_session_splits_v5.json` 中完整保留既有累计分配，并将唯一的新会话 `logs_website_shadow_supplement_train_005` 预分配到 train；新目录和输出必须未使用。只能由冻结 `tempo_baseline` 提交网站动作，遇到非机器人桌必须在首个动作前停止。凭据只从 `GUANDAN_USER` 和 `GUANDAN_PASSWORD` 读取，不得打印、落盘或提交。每个决策保留 exhaustive website-oracle candidates 和决策时一致的信息集；不得使用隐藏手牌、未来动作或赛后信息。每局 Elo 必须来自 `leaderboard_elo`，严禁把 `final_state["scores"]` 当 Elo。本阶段不得重建数据集、运行 teacher rollout、创建 teacher label、训练模型、运行离线评估或进行模型控制网站对局。

验收：恰好 12 局完成且均为 verified bot table；全部动作由 `tempo_baseline` 提交；提交成功率 100%；candidate exhaustiveness 与 information-set consistency 100%；非机器人动作、失败局、通信、编码、队伍映射、手牌子集、合法性、oracle、materialization、网站规则、wildcard、信息集、重复提交、不可恢复 desync 和模型控制计数均为 0；每局 `leaderboard_elo` 前后连续可核验；旧 session assignment 和 locked-test 变化均为 0；extension v4 与 teacher v5 冻结哈希不变；新 tracked/curated 文件凭据命中 0；更新全部交接文件、运行验证、commit 并 push，全部满足后才能完成 Goal。
