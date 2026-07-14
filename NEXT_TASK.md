# NEXT_TASK.md

## Single Next Stage

Run Stage 6.8: frozen corrective residual-top1 evidence audit.

Reproduce the 11 residual `other` first-maximum top1 states from the frozen
Stage 6.7 corrective diagnosis. Audit existing frozen source evidence only for
the eight pipeline-train targets. Keep the three pipeline-development targets
identity-only and out of evidence inspection, candidate rules, objective design,
and threshold design.

Do not run rollout, train or fine-tune a model, tune thresholds, select or
modify a checkpoint, load locked test or any website dataset, run Arena, access
the website, begin Shadow or model-controlled play, promote a model, claim
capability, or execute a future manifest.

## Frozen Inputs

- Stage 6.7 corrective diagnosis:
  `website_teacher_preference_corrective_failure_diagnosis_v1.json`, SHA-256
  `2b4359470e74f5eae28d6589477aca5f929ae6b5b88e094fa86209bf4328163d`.
- Corrective checkpoint and training report, unchanged:
  `models_website_teacher_preference_corrective_v1/website_teacher_preference_corrective_final.pth`,
  SHA-256
  `8cb368c8c0ae3f8c41c577e055ddd4796cbaae8163720cc630a435aa25bc1a49`;
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
- Stage 6.4 confirmation and old diagnosis, unchanged:
  `website_teacher_preference_unpaired_train_confirmation_v1.json`, SHA-256
  `8e17377b5a1523d9f0a47af7218d687e062a3ade671c57f387eb4c1a0888cfae`;
  `website_teacher_preference_failure_diagnosis_v1.json`, SHA-256
  `da08516c39986a01349533e160ba0e97a566d7fad6e42b0b7b3ce41df835b0b2`.
- The only new curated output is
  `website_teacher_preference_corrective_residual_evidence_audit_v1.json`, which
  must not exist before execution.

## Audit Contract

- Validate every frozen hash and the Stage 6.7 independent-audit conclusion.
  Reproduce overall 11 teacher/0 behavior/11 other top1 counts, zero pass top1,
  and exact Stage 6.6 metric/prediction digests without rescoring or training.
- Reproduce exactly the 11 residual `other` top1 targets by game/turn key,
  pipeline partition, original action index/order, 54D action hash, and teacher
  rank. Expected partition counts are eight train and three development.
- For the eight train targets only, inspect only the frozen source rollout files
  directly referenced by their teacher samples. Record every source-file hash.
  Map the exact residual action to recorded legal-action and physical-card
  metadata with zero reconstruction or substitution.
- Classify whether existing evidence contains a direct teacher-versus-residual-
  top1 paired comparison with rollout count, hidden-card sampling method, mean
  returns, return variances, candidate advantage, confidence/lower bound, and
  both continuation-profile advantages under the already frozen strong gates.
- Development targets may be recorded only by identity, partition, action index,
  and action hash from the Stage 6.7 diagnosis. Do not open their source evidence
  for candidate, threshold, or objective design.
- If train evidence is insufficient, write a non-executed future manifest for
  only the insufficient train cases. Do not run it and do not define or train a
  new objective in this stage.
- Independently recompute target identities, source hashes, mappings,
  classifications, partition counts, aggregates, and all forbidden-operation
  counters.

## Required Work

1. Re-read the canonical handoffs; verify Git state, all frozen hashes, Stage
   6.7 conclusion, and output nonexistence.
2. Add the smallest residual-evidence audit path and focused tests for target
   extraction, 8/3 isolation, exact action mapping, evidence classification,
   development non-inspection, and output refusal.
3. Run the audit once and independently verify the curated output.
4. Keep every frozen input and both checkpoints unchanged.
5. Update `PROJECT_STATE.md`, `EXPERIMENTS.md`, `NEXT_TASK.md`, and the durable
   progress document; run narrow regressions, credential and diff checks,
   commit, and push.

## Acceptance Criteria

- All frozen hashes remain unchanged. Stage 6.7 remains 22 states/934 full-set
  action scores with exact independent reproduction and zero integrity errors.
- Exactly 11 residual targets reproduce: eight train and three development,
  with zero missing, duplicate, extra, reconstructed, substituted, or ambiguous
  mappings.
- Only train-target source evidence is inspected. Development source-evidence
  reads, locked-test or website-dataset loads, and future-manifest executions
  are zero.
- Every train classification records the required frozen evidence fields or an
  explicit insufficiency reason. No unsupported ordering becomes a label.
- Rollout, training, tuning, checkpoint selection/modification, Arena, website
  Shadow/play, model-controlled website actions, promotion, and capability
  claims are zero.
- Credential occurrences in new tracked/curated files are zero.
- Handoff updates, focused tests, independent audit, conventional commit, and
  push all succeed before the next stage Goal is marked complete.

## Ready-to-Use Goal Prompt

请创建一个阶段 Goal：完成 Stage 6.8 frozen corrective residual-top1 evidence
audit。精确复现 Stage 6.7 的 11 个 residual other-top1 state，只审计其中 8 个
pipeline-train target 已有的冻结 source evidence；3 个 development target 只能
登记 identity，不得检查其 source evidence 或用于规则/阈值/目标设计。不得
rollout、训练、调参、选择/修改 checkpoint、加载 locked test/网站 dataset、
运行 Arena、访问网站、Shadow、模型控制、提升、能力结论或执行 future
manifest。独立复核、交接更新、验证、凭据零命中、commit 和 push 全部成功后
才能完成 Goal。
