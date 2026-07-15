# NEXT_TASK.md

## Single Next Stage

Run Stage 6.14E: formal process-isolated three-new-top1 confirmation.

Stage 6.14P proved that one task per determinization preserves the frozen Stage
6.9 sequential semantics exactly. Execute exactly one formal process-isolated
run for only these train cases:

- `13957:14`, current top-1 action index 17;
- `14038:12`, current top-1 action index 3;
- `13872:4`, current top-1 action index 19.

Each case must compare only the frozen teacher action and current top-1 action,
using 16 rollouts per action: greedy/tempo eight each over eight shared
determinizations. The formal total is exactly 96 candidate rollouts, split
48/48 by profile. Use eight isolated tasks per case and restore results to the
original order before the unchanged Stage 6.9 metrics and gates run.

Do not use a sequential fallback or retry. Do not change the actions, physical
materialization, hidden-card sampler, seed scheme, continuation policies,
`MAX_ROLLOUT_STEPS=300`, `MAX_SECONDS_PER_CASE=600`, return definition,
confidence arithmetic, thresholds, or directional gates. If any worker,
deadline, identity, completeness, or audit gate fails, write no curated result
and stop Stage 6.14.

## Frozen Inputs

- Stage 6.14P equivalence artifact:
  `website_teacher_preference_residual_corrective_remaining_parallel_equivalence_v1.json`,
  SHA-256
  `8e168656c35519aae9054038f0fd31398ac0e9260c419de0534a09bf1f4c59ca`.
- Stage 6.14P implementation:
  `website_teacher_preference_residual_corrective_remaining_parallel_equivalence.py`,
  SHA-256
  `f2093a8c348d9d91435209fd9ee258130b18f7de7b4b7758c0656c1d7a70e2e5`.
- Stage 6.14R recovery audit:
  `website_teacher_preference_residual_corrective_remaining_timeout_recovery_audit_v1.json`,
  SHA-256
  `75115cfc5a9dfa3ecb6ac868d04a2e73d20473cfe3a49c8e805a042028872c0d`.
- Stage 6.13 evidence audit:
  `website_teacher_preference_residual_corrective_remaining_evidence_audit_v1.json`,
  SHA-256
  `2dff04b2be010a10c3f3e77a144f98d1aeca89a885e21cc98be9c51868b53345`.
- Stage 6.9 execution/gate authority:
  `website_teacher_preference_corrective_residual_train_confirmation_v1.json`,
  SHA-256
  `352cd0dfe0a4c958ba0555b776326a2b58470a980aef461ed49d4c59a7474c7a`.
- The teacher v6, 18/4 split, physical source partition, Stage 6.12 diagnosis,
  Stage 6.1 Arena rejection, and unchanged Stage 6.14 confirmation hashes must
  match the values recursively verified by Stage 6.14P.
- The intended output
  `website_teacher_preference_residual_corrective_remaining_train_confirmation_v1.json`
  must be absent before execution and written only after full acceptance.

## Required Work

1. Re-read the canonical handoffs and verify Git state, every frozen hash, the
   accepted parallel artifact, and the output-path precondition.
2. Add only a small formal wrapper around the accepted process-isolated
   executor and frozen Stage 6.14 context, materialization, metrics, gates, and
   one-shot writer. Do not modify either frozen implementation.
3. Run one formal execution. Require exactly 24 determinization tasks, 48
   schedule items, and 96/96 completed candidate calls with zero timeout or
   failure. Do not rerun if it fails.
4. Independently audit the curated output in a separate process, including all
   mappings, physical identities, raw action order/index, 54D hashes, seeds,
   returns, arithmetic, directions, exclusions, task accounting, and forbidden
   counters.
5. Update `PROJECT_STATE.md`, `EXPERIMENTS.md`, `NEXT_TASK.md`, and the durable
   progress document; run focused and full regressions plus credential and diff
   checks; commit and push.

## Isolation and Prohibited Work

- Train cases `14077:10` index 0, `13959:7` index 5, and `14025:20` index 1,
  plus development cases `13992:16`, `14074:9`, and `13871:9`, must have zero
  mappings, executions, and rollouts.
- Do not use partial Stage 6.14 directions or any failed result.
- Dataset/objective construction, model scoring, training, tuning, checkpoint
  changes, locked-test or complete-bundle loads, Arena, website access, Shadow
  or model-controlled play, promotion, partial labels, and capability claims
  must all remain zero.

## Acceptance Criteria

- All frozen hashes and exact target identities match; excluded identities are
  absent from formal mapping and execution.
- Exactly 96/96 candidate rollouts complete, with 32 per target and 48/48
  greedy/tempo accounting; timeout, failure, missing, duplicate, extra,
  substituted, retry, and sequential-fallback counts are zero.
- The unchanged Stage 6.9 metrics and gates alone determine each direction.
- An independent process reproduces the curated evidence and all isolation and
  forbidden counters.
- Credential occurrences in new tracked/curated files are zero.
- Handoffs, focused tests, full tests, conventional commit, and push succeed.
- Only after all conditions pass may the active Stage 6.14 Goal be completed.
