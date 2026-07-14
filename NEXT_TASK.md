# NEXT_TASK.md

## Single Next Stage

Run Stage 6.5: frozen corrective preference dataset construction.

Preserve all 22 frozen teacher-versus-behavior pairs and the frozen 18/4 game
split. Append exactly the six Stage 6.4 `pipeline_train`
teacher-versus-top1 comparisons that passed every unchanged strong-teacher
gate. Exclude the three inconclusive train comparisons and every
pipeline-development unpaired comparison.

Do not run rollout, train, tune, select or modify a checkpoint, run Arena, load
locked test, access the website, begin Shadow or model-controlled play, promote
a model, or claim capability. The existing checkpoint remains rejected from
the 100/200-game screen.

## Frozen Inputs

- Stage 6.4 confirmation:
  `website_teacher_preference_unpaired_train_confirmation_v1.json`, SHA-256
  `8e17377b5a1523d9f0a47af7218d687e062a3ade671c57f387eb4c1a0888cfae`.
- Stage 6.3 audit:
  `website_teacher_preference_unpaired_evidence_audit_v1.json`, SHA-256
  `09f52df90d095ab6b3777a046c50901f96fbeb15e6ef5f613343a13be1249383`.
- Frozen teacher dataset:
  `website_information_set_teacher_dataset_v6.pth`, SHA-256
  `a74416e6facb28a1bc64563eba90cb33d460dc9e59cc2109518da142465e15f8`.
- Frozen 18/4 split:
  `website_teacher_preference_split_v1.json`, SHA-256
  `5a15e514dc9bc51d77d300837151d9f1a49250f42885cc7940725bcbe4d35107`.
- Frozen training report:
  `website_teacher_preference_training_v1.json`, SHA-256
  `896192b1d0b4de2caabe20ac17d6a20766fc7f89d6e82a981d834b777932ddd3`.
- Rejected checkpoint, unchanged:
  `models_website_teacher_preference_v1/website_teacher_preference_final.pth`,
  SHA-256
  `c54801a9db05100c2fe5a9bf610a64fc7c94dc2cd947dfaab115ff827bd90919`.
- Stage 6.1 Arena evidence, unchanged:
  `website_teacher_preference_arena_smoke20_v1.json`, SHA-256
  `aa45da9de202194102fe8d11e612ad3eb4b51177fd910b9a7948836afd2a1fe6`.
- Outputs must be unused before execution and named
  `website_teacher_preference_corrective_dataset_v1.pth` and
  `website_teacher_preference_corrective_dataset_v1_manifest.json`.

## Dataset Contract

- Revalidate all 22 teacher v6 samples by schema, 513/54 dimensions, legal
  action identity, physical-card provenance, source partition, and locked-test
  exclusion. Preserve their serialized sample content exactly inside the new
  dataset.
- Preserve the frozen pipeline split: 18 train games and four development
  games, with zero overlap or dropped games.
- Add exactly six new `teacher_action_beats_model_top1` pairs for
  `13879:6`, `13861:10`, `13957:14`, `13960:15`, `13959:7`, and `14022:16`.
  The teacher action, negative top1 action, indices, 54D hashes, physical-card
  identities, rollout metrics, and Stage 6.4 provenance must match exactly.
- Do not add `14077:10`, `13882:10`, or `14025:20`; record each exclusion and
  its frozen-gate reasons. Do not add or inspect any pipeline-development
  unpaired pair.
- The final dataset must contain 24 pipeline-train pairs across 18 games and
  four unchanged pipeline-development pairs across four games: 28 pairs total.
- Freeze, but do not execute, the next training objective as a state-balanced
  pairwise softplus objective: each state has equal aggregate weight and its
  available negative pairs share that state weight equally. Do not tune weights
  or hyperparameters in this stage.
- The dataset and manifest must state that they are pipeline-only, ineligible
  for capability evidence, and cannot promote a checkpoint.

## Required Work

1. Re-read the canonical handoffs; verify Git state, all seven frozen hashes,
   Stage 6.4 arithmetic, the 6/3/0 directional counts, and output nonexistence.
2. Add the smallest deterministic dataset builder and focused tests for frozen
   sample preservation, exact supported-pair inclusion, inconclusive and
   development exclusion, split accounting, state-balanced weights, and
   output refusal/atomicity.
3. Build the dataset and manifest exactly once. Do not call any rollout or
   training path.
4. Independently reload and audit sample identity, hashes, pair provenance,
   24/4 split counts, 18/4 game counts, weights, exclusions, and all forbidden
   counters.
5. Keep every frozen input unchanged; do not update teacher v6 or checkpoint.
6. Update `PROJECT_STATE.md`, `EXPERIMENTS.md`, `NEXT_TASK.md`, and the durable
   progress document; run narrow regressions, credential and diff checks,
   commit, and push.

## Acceptance Criteria

- All seven frozen hashes remain unchanged; Stage 6.1 remains 0-20 with
  continuation false and the checkpoint remains rejected.
- All 22 original pairs are preserved exactly. Exactly six supported train
  corrective pairs are added; unsupported/inconclusive and development
  unpaired pairs added: zero.
- Dataset counts are exactly 28 pairs: 24 train and four development, across
  18 and four games respectively, with zero overlap or dropped base samples.
- Per-state aggregate training weight is equal within each partition and
  multi-negative state weights sum exactly to one state unit. No weight or
  threshold tuning occurs.
- Rollout, training, tuning, checkpoint selection or modification, locked-test
  loads, Arena, website Shadow/play, model-controlled website actions,
  promotion, and capability claims are all zero.
- Credential occurrences in new tracked/curated files are zero.
- Handoff updates, focused tests, independent audit, conventional commit, and
  push all succeed before the stage Goal is marked complete.

## Ready-to-Use Goal Prompt

请创建一个阶段 Goal：完成 Stage 6.5 frozen corrective preference dataset
construction。完整保留 teacher v6 的 22 个 teacher-versus-behavior pair 和
冻结 18/4 game split，只追加 Stage 6.4 中通过全部冻结门槛的六个
pipeline-train teacher-versus-top1 pair；排除三个 inconclusive train pair
和全部 development unpaired pair。冻结 state-balanced pairwise softplus
objective manifest，但不得执行 rollout、训练、调参、checkpoint 选择或修改、
locked-test 加载、Arena、网站 Shadow/对局、模型控制、提升或能力结论。完成
独立审计、交接更新、验证、凭据零命中、commit 和 push 后才能完成 Goal。
