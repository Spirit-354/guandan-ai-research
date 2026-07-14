# NEXT_TASK.md

## Single Next Stage

Run Stage 6.10: frozen residual corrective dataset extension.

Preserve the frozen corrective dataset v1 and add only the four Stage 6.9
pipeline-train teacher-over-residual comparisons that passed every unchanged
strong gate: `14044:9`, `14038:12`, `14000:5`, and `14022:16`. Exclude the
four inconclusive train comparisons and all three pipeline-development residual
targets. Recompute deterministic state-balanced pair weights after the four
additions.

Do not run rollout, train or fine-tune a model, tune thresholds, select or
modify a checkpoint, load locked test or any website dataset, run Arena, access
the website, begin Shadow or model-controlled play, promote a model, claim
capability, or execute the new objective.

## Frozen Inputs

- Stage 6.9 residual confirmation:
  `website_teacher_preference_corrective_residual_train_confirmation_v1.json`,
  SHA-256
  `352cd0dfe0a4c958ba0555b776326a2b58470a980aef461ed49d4c59a7474c7a`.
- Corrective dataset v1 and manifest:
  `website_teacher_preference_corrective_dataset_v1.pth`, SHA-256
  `fad7ae18fea8b02cbc88ad4a8a7f8ecee298abe436ef589f5c88d66e42a32707`;
  `website_teacher_preference_corrective_dataset_v1_manifest.json`, SHA-256
  `0a5dc4f60091338b65f86f83ad30ae55dc18c058ee8b07535a314510ad96ef0a`.
- Stage 6.8 residual evidence audit:
  `website_teacher_preference_corrective_residual_evidence_audit_v1.json`,
  SHA-256
  `676232033f07051670b4407f15aca9f3939d9754ac2dcf4d078957263a1e2a6b`.
- Frozen teacher v6 and 18/4 split:
  `website_information_set_teacher_dataset_v6.pth`, SHA-256
  `a74416e6facb28a1bc64563eba90cb33d460dc9e59cc2109518da142465e15f8`;
  `website_teacher_preference_split_v1.json`, SHA-256
  `5a15e514dc9bc51d77d300837151d9f1a49250f42885cc7940725bcbe4d35107`.
- Stage 6.4 confirmation remains the provenance authority for the six existing
  corrective pairs:
  `website_teacher_preference_unpaired_train_confirmation_v1.json`, SHA-256
  `8e17377b5a1523d9f0a47af7218d687e062a3ade671c57f387eb4c1a0888cfae`.
- The only new outputs are
  `website_teacher_preference_corrective_dataset_v2.pth` and
  `website_teacher_preference_corrective_dataset_v2_manifest.json`; neither may
  exist before execution.

## Dataset Contract

- Validate every frozen hash and reload the v1 dataset/manifest. Preserve all
  22 embedded teacher v6 samples exactly after deserialization, including every
  per-sample canonical hash and the aggregate sample hash.
- Preserve the identities, preferred/rejected actions, action hashes, physical
  identities, pair types, partitions, and provenance of all 28 v1 pairs.
  Pair-weight fields may change only through the deterministic state-balancing
  rule required after adding the four new pairs.
- Add exactly four `teacher_action_beats_residual_top1` pairs for `14044:9`,
  `14038:12`, `14000:5`, and `14022:16`. Each must match the Stage 6.9 teacher
  and residual indices, 54D hashes, physical identities, and frozen directional
  metrics with an empty teacher-direction failure list.
- Add no pair for inconclusive train cases `13957:14`, `14077:10`, `13959:7`,
  and `14025:20`. Record them as exclusions. Keep development residual targets
  `13992:16`, `14074:9`, and `13871:9` as held-out keys only; do not inspect or
  add their actions.
- The final dataset must contain 32 pairs across the same 22 states: 28
  pipeline-train pairs across 18 states and four pipeline-development pairs
  across four states. Counts are 22 base teacher-versus-behavior pairs, six
  existing Stage 6.4 corrective pairs, and four new Stage 6.9 residual pairs.
- Apply only the frozen state-balanced rule: pair weights sum to exactly one
  for every state. Eight two-pair states use weights 0.5/0.5; `14022:16` has
  three pairs with equal one-third weights; the other 13 states retain weight
  1.0. Partition-normalized weights sum to exactly one for train and one for
  development.
- The manifest may describe the unchanged state-balanced pairwise softplus
  objective, but the objective must not execute. Capability and checkpoint-
  promotion eligibility remain false.
- Independently reload and recompute all sample/pair hashes, v1 preservation,
  four additions, seven exclusions/held-out keys, state and partition counts,
  weight arithmetic, provenance, and forbidden-operation counters.

## Required Work

1. Re-read the canonical handoffs; verify Git state, every frozen hash, and both
   output paths are unused.
2. Add the smallest v2 dataset-extension path and focused tests for exact v1
   preservation, four supported additions, exclusion/held-out isolation,
   32/28/4 accounting, one-third weighting, and output refusal.
3. Build the v2 dataset and manifest once, then independently reload and audit
   both outputs.
4. Keep all frozen inputs and both checkpoints unchanged. Do not run rollout,
   training, Arena, or any website path regardless of the result.
5. Update `PROJECT_STATE.md`, `EXPERIMENTS.md`, `NEXT_TASK.md`, and the durable
   progress document; run narrow regressions, credential and diff checks,
   commit, and push.

## Acceptance Criteria

- All frozen hashes remain unchanged. All 22 teacher samples and 28 v1 pair
  identities/provenance records are preserved with zero dropped, substituted,
  ambiguous, or unsupported old pairs.
- Exactly four supported train residual pairs are added. Final counts are 32
  total, 28 train, four development, 22 base, six existing corrective, and four
  new residual corrective pairs across the unchanged 18/4 state split.
- The four inconclusive train cases add zero pairs. The three development
  residual targets have zero action inspection and zero pair additions.
- Every state weight sum is exactly one; `14022:16` has three equal one-third
  pair weights; train/development normalized weights each sum to one.
- Rollout, training, fine-tuning, tuning, checkpoint selection/modification,
  locked-test or website-dataset loads, Arena, website Shadow/play,
  model-controlled website actions, promotion, and capability claims are zero.
- Credential occurrences in new tracked/curated files are zero.
- Handoff updates, focused tests, independent audit, conventional commit, and
  push all succeed before the next stage Goal is marked complete.

## Ready-to-Use Goal Prompt

请创建一个阶段 Goal：完成 Stage 6.10 frozen residual corrective dataset
extension。完整保留 corrective dataset v1 的 22 个 sample 和 28 个 pair identity/
provenance，仅加入 Stage 6.9 支持的 4 个 pipeline-train teacher-over-residual
pair；4 个 inconclusive train case 和 3 个 development target 必须零新增 pair，
development action 不得检查。最终应为 32 pairs（28 train/4 development），逐 state
权重和为 1，`14022:16` 的 3 个 pair 各为三分之一。不得 rollout、训练、调参、
checkpoint 选择/修改、加载 locked test/网站 dataset、运行 Arena、访问网站、Shadow、
模型控制、提升或能力结论。独立复核、交接更新、验证、凭据零命中、commit 和 push
全部成功后，才能完成 Goal。
