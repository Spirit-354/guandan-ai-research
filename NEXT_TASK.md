# NEXT_TASK.md

## Single Next Stage

Run Stage 6.1: a 20-game paired, seat-swapped offline Arena integrity smoke for
the frozen teacher-preference checkpoint against frozen `tempo_baseline`.

This is offline screening evidence only. Do not run the 100/200-game screen,
1000-game confirmation, locked test, website Shadow, website games, checkpoint
promotion, or model-controlled website play in this stage, regardless of the
20-game result.

## Frozen Inputs

- Candidate checkpoint:
  `models_website_teacher_preference_v1/website_teacher_preference_final.pth`.
- Candidate checkpoint SHA-256:
  `c54801a9db05100c2fe5a9bf610a64fc7c94dc2cd947dfaab115ff827bd90919`.
- Required checkpoint schema:
  `website_teacher_preference_checkpoint_v1`, state dimension 513, action
  dimension 54, teacher SHA-256
  `a74416e6facb28a1bc64563eba90cb33d460dc9e59cc2109518da142465e15f8`,
  `capability_claim_allowed=false`, and
  `checkpoint_promotion_allowed=false`.
- Frozen teacher v6 SHA-256, for provenance audit only:
  `a74416e6facb28a1bc64563eba90cb33d460dc9e59cc2109518da142465e15f8`.
- Frozen split manifest:
  `website_teacher_preference_split_v1.json`, SHA-256
  `5a15e514dc9bc51d77d300837151d9f1a49250f42885cc7940725bcbe4d35107`.
- Frozen training report:
  `website_teacher_preference_training_v1.json`, SHA-256
  `896192b1d0b4de2caabe20ac17d6a20766fc7f89d6e82a981d834b777932ddd3`.
- Frozen baseline manifest:
  `research_baseline_manifest.json`, SHA-256
  `a1b2853fea1331f9d423cef2f09931b0ffbf8f794520ab4de69d6cac8b8f6812`.
- Required baseline evidence: `tempo_baseline`, 500 equivalence samples, zero
  mismatches, and all frozen function/profile hashes unchanged.
- Arena output must be unused before execution and named
  `website_teacher_preference_arena_smoke20_v1.json`.

## Arena Contract

- Add only the compatibility required for `danzero_dmc.load_q_checkpoint` to
  load the teacher-preference checkpoint schema into the existing
  `danzero_dmc.build_q_model`. Preserve the existing distributed-DMC checkpoint
  path unchanged.
- Reject a teacher-preference checkpoint if its schema, dimensions, teacher
  hash, training mode, capability flag, or promotion flag differs from the
  frozen contract.
- Use only the existing exhaustive website-oracle 513+54 Arena action path.
  Do not change Q ranking, action materialization, `tempo_baseline`, Guandan
  rules, website protocol, or Elo semantics.
- Run exactly 20 completed games as ten adjacent pairs. Within each pair, use
  the same deal seed and first-player seed; assign the model to team 0 once and
  team 1 once. Reset the per-game Arena RNG from the same frozen pair seed so
  pairing is explicit rather than inferred from a process-global RNG stream.
- Use Arena seed `20260714`, `--danzero-arena-swap-seats`, CPU, and frozen
  `tempo_baseline`. Do not retry a failed integrity game into a replacement
  result; report the failure and stop under the existing integrity gate.
- Report pair index, seed, first player, model team, winner, game length, and
  safety counters per game or in an auditable compact trace.
- The integrity gate requires 20/20 completed games and zero illegal-action,
  fallback, materialization, hand-card-mismatch, and fatal-no-candidate counts.
- The frozen early-screen continuation rule is integrity pass plus model team
  win rate at least 0.30. This flag only decides whether a later 100/200-game
  stage may be proposed; it is not a capability or promotion claim.

## Required Work

1. Re-read the canonical handoffs and verify Git state, every frozen hash and
   flag above, baseline equivalence evidence, and output nonexistence.
2. Add the narrowest checkpoint-loader compatibility and paired-seed audit
   trace. Add focused tests for valid loading, rejection of mismatched metadata,
   unchanged legacy checkpoint loading, 513+54 forward compatibility, and the
   ten-pair seed/team layout.
3. Run baseline freeze verification and the focused tests before Arena.
4. Run exactly one formal 20-game CPU Arena smoke with the frozen checkpoint,
   seed, seat swap, baseline, and output path.
5. Independently audit 20/20 completion, ten paired seeds, team 0/1 balance,
   within-pair deal/first-player identity, result arithmetic, safety counters,
   baseline evidence, candidate/baseline hashes, and continuation flag.
6. Keep the raw Arena JSON ignored unless deliberately force-added as small
   curated evidence. Do not load website datasets or locked test, train, tune,
   select a checkpoint, or execute any later gate.
7. Update `PROJECT_STATE.md`, `EXPERIMENTS.md`, `NEXT_TASK.md`, and the durable
   progress document; run narrow regression tests, credential and diff checks,
   commit, and push.

## Acceptance Criteria

- Frozen checkpoint, teacher, split, training report, and baseline manifest
  hashes remain unchanged; checkpoint metadata and baseline equivalence pass.
- Existing distributed-DMC checkpoint loading remains supported and its tests
  pass. Teacher-preference loader accepts only the frozen compatible schema.
- Exactly 20 games complete as ten adjacent paired seeds. Each pair has the
  same deal seed and first player, model teams `{0,1}`, and auditable results.
- Illegal-action, fallback, materialization, hand-card-mismatch, and
  fatal-no-candidate counts are all zero; baseline equivalence mismatches are
  zero.
- Model/baseline wins sum to 20 and rates match counts. The early-screen
  continuation flag exactly follows integrity pass and model win rate >= 0.30.
- Training runs, hyperparameter searches, checkpoint selections, locked-test
  or website-dataset loads, 100/200/1000-game Arena runs, website Shadow,
  website games, model-controlled website actions, checkpoint promotion, and
  capability claims are all zero.
- Credential occurrences in new tracked/curated files are zero.
- Handoff updates, focused tests, independent audit, conventional commit, and
  push all succeed before the stage Goal is marked complete.

## Ready-to-Use Goal Prompt

请创建一个阶段 Goal：完成 Stage 6.1 冻结 teacher-preference checkpoint 对
`tempo_baseline` 的 20-game paired seat-swapped 离线 Arena 完整性 smoke。
只允许使用 SHA-256 为
`c54801a9db05100c2fe5a9bf610a64fc7c94dc2cd947dfaab115ff827bd90919`
的 checkpoint；只增加现有 513+54 Arena 加载该冻结 schema 所需的最小兼容，
并保持旧 DMC checkpoint 加载不变。用 CPU、seed 20260714，严格运行 10 个
相邻 pair；每个 pair 的 deal/first-player/per-game RNG seed 相同，模型分别在
team 0 和 team 1。必须完成 20/20，对局及 baseline equivalence、illegal、
fallback、materialization、hand-card mismatch、fatal candidate 错误全部为 0。
胜率至少 0.30 只能设置“允许提议后续 screen”的早期标志，不能构成能力或提升
结论。严禁训练、调参、checkpoint 选择、locked-test 或网站数据加载、
100/200/1000-game Arena、网站 Shadow、网站对局、checkpoint 提升或模型控制
网站。只完成本阶段；交接、验证、凭据零命中、commit 和 push 全部成功后才能
完成 Goal。
