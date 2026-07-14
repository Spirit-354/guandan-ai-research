# NEXT_TASK.md

## Single Next Stage

Run Stage 6.7: frozen corrective full-legal-set diagnosis.

Score the frozen Stage 6.6 corrective checkpoint exactly once on every recorded
legal action in the same 22 frozen teacher states. Diagnose whether the six
corrective constraints changed the intended rankings and whether other
unsupported full-set top actions remain. This is static diagnostic evidence
only.

Do not run rollout, train or fine-tune a model, tune thresholds, select or
modify a checkpoint, load locked test or any website dataset, run Arena, access
the website, begin Shadow or model-controlled play, promote a model, or claim
capability. Do not design the next objective from pipeline-development results.

## Frozen Inputs

- Corrective checkpoint:
  `models_website_teacher_preference_corrective_v1/website_teacher_preference_corrective_final.pth`,
  SHA-256
  `8cb368c8c0ae3f8c41c577e055ddd4796cbaae8163720cc630a435aa25bc1a49`.
- Corrective training report:
  `website_teacher_preference_corrective_training_v1.json`, SHA-256
  `baa97ccf71c237895a92f4cb8b36b9559cf3cabe45b4901b7481d9f50f4c0830`.
- Corrective dataset and manifest, unchanged:
  `website_teacher_preference_corrective_dataset_v1.pth`, SHA-256
  `fad7ae18fea8b02cbc88ad4a8a7f8ecee298abe436ef589f5c88d66e42a32707`;
  `website_teacher_preference_corrective_dataset_v1_manifest.json`, SHA-256
  `0a5dc4f60091338b65f86f83ad30ae55dc18c058ee8b07535a314510ad96ef0a`.
- Frozen teacher v6 and 18/4 split, unchanged:
  `website_information_set_teacher_dataset_v6.pth`, SHA-256
  `a74416e6facb28a1bc64563eba90cb33d460dc9e59cc2109518da142465e15f8`;
  `website_teacher_preference_split_v1.json`, SHA-256
  `5a15e514dc9bc51d77d300837151d9f1a49250f42885cc7940725bcbe4d35107`.
- Stage 6.4 confirmation, unchanged:
  `website_teacher_preference_unpaired_train_confirmation_v1.json`, SHA-256
  `8e17377b5a1523d9f0a47af7218d687e062a3ade671c57f387eb4c1a0888cfae`.
- Old full-set diagnosis and rejected checkpoint, unchanged:
  `website_teacher_preference_failure_diagnosis_v1.json`, SHA-256
  `da08516c39986a01349533e160ba0e97a566d7fad6e42b0b7b3ce41df835b0b2`;
  `models_website_teacher_preference_v1/website_teacher_preference_final.pth`,
  SHA-256
  `c54801a9db05100c2fe5a9bf610a64fc7c94dc2cd947dfaab115ff827bd90919`.
- The only new curated output is
  `website_teacher_preference_corrective_failure_diagnosis_v1.json`, which must
  not exist before execution.

## Diagnostic Contract

- Reload and validate the Stage 6.6 report/checkpoint schema, frozen hashes,
  fixed 513/54 recipe, one-run accounting, false promotion/capability flags,
  and exact train/development plus base/corrective metrics and prediction
  digests.
- Use the 22 frozen teacher-v6 samples in their recorded order. Score all 934
  recorded legal-action entries exactly once; preserve duplicate action entries
  and original first-maximum tie semantics.
- Reproduce the frozen 18 train/four development partition with zero overlap or
  unknown games. Do not use development results for objective or threshold
  design.
- Report per-state teacher, behavior, and first-maximum top-1 indices/Q values,
  teacher rank/ties, actions strictly above teacher, and top-1 class. Report
  aggregate teacher/behavior/other top-1 counts, pass top-1 count, teacher-rank
  statistics, and nonfinite values by partition and overall.
- For all six Stage 6.4 corrective pairs, report the preferred/rejected indices,
  ranks, Q margin, whether teacher now outranks the frozen rejected top1, and
  whether teacher is full-set top-1. Compare these outcomes with the old frozen
  diagnosis without claiming causality or capability.
- Independently recompute every ranking, tie, action-order digest, aggregate,
  pair metric, and prediction digest. Do not rerun training.

## Required Work

1. Re-read the canonical handoffs; verify Git state, every frozen hash, Stage
   6.6 independent-audit conclusion, and output nonexistence.
2. Add the smallest static corrective-diagnosis path and focused tests for
   recorded-order scoring, duplicate preservation, tie/rank semantics,
   corrective-pair mapping, partition isolation, and output refusal.
3. Run the static diagnosis once and independently audit the curated output.
4. Keep all frozen inputs and both checkpoints unchanged.
5. Update `PROJECT_STATE.md`, `EXPERIMENTS.md`, `NEXT_TASK.md`, and the durable
   progress document; run narrow regressions, credential and diff checks,
   commit, and push.

## Acceptance Criteria

- All frozen hashes remain unchanged. Stage 6.6 remains one fixed training run
  with zero development training uses, and Stage 6.1 remains rejected at 0-20.
- Exactly 22 states and all 934 recorded legal-action entries are scored once;
  dropped, reconstructed, repeated-score, invalid-dimension, illegal-recorded,
  and nonfinite-Q counts are zero.
- The Stage 6.6 aggregate/base/corrective metrics and prediction digests
  reproduce exactly. All six corrective pair mappings and ranking arithmetic
  independently reproduce.
- Rollout, training, tuning, checkpoint selection/modification, locked-test or
  website-dataset loads, Arena, website Shadow/play, model-controlled website
  actions, promotion, and capability claims are zero.
- Credential occurrences in new tracked/curated files are zero.
- Handoff updates, focused tests, independent audit, conventional commit, and
  push all succeed before the next stage Goal is marked complete.

## Ready-to-Use Goal Prompt

请创建一个阶段 Goal：完成 Stage 6.7 frozen corrective full-legal-set
diagnosis。只在 22 个冻结 teacher-v6 state 上静态评分纠正 checkpoint 的全部
934 个原始合法动作，精确复现 Stage 6.6 指标/digests，并诊断六个纠正约束和
剩余 full-set 排名；不得 rollout、训练、调参、选择或修改 checkpoint、加载
locked test/网站 dataset、运行 Arena、访问网站、Shadow、模型控制、提升或作
能力结论。独立复核、交接更新、验证、凭据零命中、commit 和 push 全部成功后
才能完成 Goal。
