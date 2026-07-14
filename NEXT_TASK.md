# NEXT_TASK.md

## Single Next Stage

Build Frozen Dataset Extension v5 from the frozen extension v4 manifest and
the already collected Supplement v5 train session. Do not run website play,
teacher screening or rollout, create teacher labels, train or evaluate a model,
or begin model-controlled website play in this stage.

## Frozen Inputs and Preconditions

- Branch: `agent/stage5-website-bot-adaptation`.
- Sole base manifest: `website_dataset_split_manifest_extension_v4.json`.
- Frozen extension v4 manifest content hash:
  `368771a6a647d34d0d6fcd0490d7cdd1e57991a4c4188e3c127780a5323acbec`.
- Frozen extension v4 artifact SHA-256 values:
  - bundle: `c8c05785defe37e589b99b3071b58c43d20ed1f1cf87fdb3c031a196151dcf87`;
  - train/development: `ad4da83e2af29c580a1b1d8fe70a06f88fc645525ab025945a7be48fd349fde1`;
  - locked-test: `cec1aba85cfbc388345d5ac17fd1ec48ec02642fb5743bed76513f872b7a512d`;
  - manifest file: `30d8103a156b84b3f1b26a78512b29757a3a603e925e15522752266f426bda04`;
  - data card: `fdfbe98a17e27e6c6cb20f5d85e6d17c6e775ee758b999aba5294b5a3f3fedee`.
- Frozen teacher v5: `website_information_set_teacher_dataset_v5.pth`,
  SHA-256
  `155fc348e939490bc036b2b5e3e0993be732b259250cac3d0244e888910fb9da`.
- Teacher gate: 19 of 20 independent high-confidence games; training remains
  prohibited.
- Sole cumulative session assignment authority:
  `website_dataset_extension_session_splits_v5.json`. It preserves all five
  prior assignments and adds only
  `logs_website_shadow_supplement_train_005: train`.
- New source session: `logs_website_shadow_supplement_train_005`, containing
  exactly 12 verified bot-table games, 345 decisions, and 11,587 exhaustive
  legal candidates. Game IDs are `14058`, `14059`, `14061`, `14063`, `14064`,
  `14066`, `14068`, `14070`, `14072`, `14074`, `14077`, and `14081`.
- The new v5 output names below must be unused before the build.

## Required Outputs

- `website_danzero_shadow_extension_v5.pth`
- `website_danzero_shadow_extension_v5.train_dev.pth`
- `website_danzero_shadow_extension_v5.locked_test.pth`
- `website_dataset_split_manifest_extension_v5.json`
- `website_dataset_card_extension_v5.json`

## Scope

1. Re-read the canonical handoffs and verify the current branch, clean starting
   worktree, every frozen hash, cumulative v5 assignment, Supplement v5 source
   inventory, and unused output names.
2. Build extension v5 using only the v4 manifest as the base and the cumulative
   v5 assignment as the session-split authority.
3. Preserve all 94 old games, their source hashes, session assignments, split
   assignments, locked-test membership, and serialized sample content. Add only
   the 12 Supplement v5 games and assign all of them to train.
4. Reject incomplete, non-bot, non-`leaderboard_elo`, model-controlled,
   non-exhaustive, information-set-inconsistent, illegal, failed-submission, or
   otherwise unsafe source games rather than weakening a gate.
5. Build the complete v5 bundle, physical train/development partition, isolated
   physical locked-test partition, manifest, and data card under the required
   output names.
6. Audit independent games, decisions, legal candidates, wins/losses, seats,
   first-player seats, level cards, wildcards, lead/follow, endgame,
   bomb-candidate states, Elo bands, robot/table signatures, duplicate states,
   physical dimensions, information-set consistency, and split isolation.
7. Independently compare v4 and v5 manifests and serialized samples. Expected
   old differences are limited to the new manifest-reference field; report any
   other old-sample difference as a failure.
8. Do not run website play, teacher screening or rollout, create teacher
   labels, train a model, run offline Arena, or begin model-controlled website
   play.
9. Update `PROJECT_STATE.md`, `EXPERIMENTS.md`, `NEXT_TASK.md`, and
   `docs/progress/2026-07-13-website-bot-route.md`; keep raw or large generated
   outputs ignored unless they are small curated evidence files. Run validation,
   scan tracked/curated changes for credentials, commit conventionally, and
   push.

## Acceptance Criteria

- Base manifests used: exactly 1, and it is extension v4; cumulative assignment
  authorities used: exactly 1, and it is v5.
- Old games removed: 0; old source-hash changes: 0; old session-assignment
  changes: 0; old split changes: 0; locked-test membership changes: 0.
- New accepted games: exactly 12; new rejected games: 0; all new game IDs match
  the frozen Supplement v5 list and all enter train.
- New accepted decisions: exactly 345; new legal candidates: exactly 11,587;
  all are physically materializable, exhaustive, information-set consistent,
  and derived from successful frozen-baseline submissions.
- All 94 old games and old serialized samples are preserved except for the
  expected v5 manifest-reference field update.
- Complete bundle, train/development partition, and locked-test partition have
  correct 513-state/54-action dimensions and mutually valid split isolation.
- Coverage and duplicate-state audits are complete; duplicate state count is
  zero and all safety/integrity counters are zero.
- Website games, teacher rollouts, teacher labels, model training, offline
  evaluation, and model-controlled website actions in this stage: 0.
- Frozen extension v4 and teacher v5 hashes remain unchanged.
- Credential occurrences in tracked/curated changes: 0.
- Handoff updates, validation, conventional commit, and push all succeed before
  the stage Goal is marked complete.

## Ready-to-Use Goal Prompt

请创建一个阶段 Goal：完成 Frozen Dataset Extension v5。只使用冻结的
`website_dataset_split_manifest_extension_v4.json` 作为基础 manifest，只使用
`website_dataset_extension_session_splits_v5.json` 作为累计会话分配依据；保留
全部 94 个旧游戏、旧 source hash、旧会话分配、旧 split、locked-test 成员和
序列化样本，仅加入 Supplement v5 的 12 个指定游戏、345 个决策和 11,587 个
候选，且全部进入 train。生成指定的五个 v5 输出并完成覆盖、信息集、物理隔离、
重复状态和新旧 manifest/样本差异审计。本阶段严禁网站对局、teacher screening
或 rollout、teacher label、训练、离线评估和模型控制网站。更新全部交接文件，
运行验证，凭据命中为 0，commit 并 push；只有全部验收条件满足后才能完成 Goal。
