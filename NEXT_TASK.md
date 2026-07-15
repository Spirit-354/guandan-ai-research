# NEXT_TASK.md

## Single Next Stage

Run Stage 6.19: frozen two-new-action train-only counterfactual confirmation.

Stage 6.18 found that `14031:4` index 2 and `14025:20` index 2 are present in
their frozen source candidates but lack direct teacher-versus-current-top1
paired statistics. Execute the unchanged frozen process-isolated confirmation
schedule exactly once for only those two train cases. Do not rerun the already
inconclusive `14077:10` case and do not expose development evidence.

## Frozen Inputs

- Stage 6.18 audit:
  `website_teacher_preference_remaining_corrective_final_evidence_audit_v1.json`,
  SHA-256
  `b7dc15c779556a972c1b471348cb949bd98d54c1ce1aecb14a3d23cda083681b`.
- Stage 6.18 implementation:
  `website_teacher_preference_remaining_corrective_evidence_audit.py`, SHA-256
  `6200af71c14081418b1abfd1fd45d99347c3f20d601ec355014dbbc931a3ea26`.
- Recursively freeze all 28 hashes recorded by Stage 6.18, including Stage
  6.17 diagnosis/implementation, Stage 6.16 report/checkpoint, teacher v6,
  split, source train/development data, and all prior evidence.
- Accepted Stage 6.14P process-isolation authority:
  `website_teacher_preference_residual_corrective_remaining_parallel_equivalence_v1.json`,
  SHA-256
  `8e168656c35519aae9054038f0fd31398ac0e9260c419de0534a09bf1f4c59ca`,
  and implementation SHA-256
  `f2093a8c348d9d91435209fd9ee258130b18f7de7b4b7758c0656c1d7a70e2e5`.
- Stage 6.14E formal wrapper pattern:
  `website_teacher_preference_residual_corrective_remaining_parallel_confirmation.py`,
  SHA-256
  `972b67ed585e9a96f9e8be55b70d0b6585a7e499f6dc692c2861d5e636b9e55d`.
- The new curated output path must be unused before construction:
  `website_teacher_preference_remaining_corrective_final_train_confirmation_v1.json`.

## Exact Executed Targets

- `14031:4`, teacher index 1 versus current top-1 index 2, current action
  SHA-256
  `44eb6c47c92f2c639293a75a2e4825abf2478d706ca7b45f31e8e9a4afc6bb42`.
- `14025:20`, teacher index 0 versus current top-1 index 2, current action
  SHA-256
  `8b631095d2fc255edfa14d27e864858829b4f70d910d347d1bff89e38eb903a9`.

## Exact Exclusions

- Previously direct-inconclusive train target: `14077:10` index 0.
- Development identity-only targets: `13992:16`, `14074:9`, and `13871:9`.
- All other teacher states and actions.

Excluded cases must have zero source mapping, execution, rollout, threshold
use, objective use, and confirmation-design use.

## Required Work

1. Re-read all canonical handoffs; verify Git state, every frozen hash, exact
   two-case executed manifest, exact exclusions, and unused output path.
2. Reuse the accepted Stage 6.14P process-isolated executor and Stage 6.14E
   formal wrapper pattern with only the smallest target/count adaptation. Do
   not change action identity, information-set sampling, seeds, continuation
   policies, rollout limits, return definition, statistics, thresholds, or
   directional gates.
3. For each permitted case, run exactly eight frozen determinizations, two
   candidates, two continuation profiles, and two rollouts per profile:
   32 candidate rollouts per case and 64 total. Workers execute simulation
   only; the parent validates identities and computes all metrics and labels.
4. Fail closed on timeout, candidate failure, retry, sequential fallback,
   missing/duplicate/extra task or result, identity mismatch, nonfinite value,
   or frozen-input drift. A failed or partial run is not accepted and must not
   become a curated output.
5. Record per-candidate rollout count, mean return, return variance, exact
   teacher-minus-current advantage, 95% lower bound, both continuation-profile
   advantages, failure reasons, and directional classification under the
   unchanged gates.
6. Write the curated output once only after 64/64 success, then independently
   reconstruct hashes, schedules, returns, statistics, classifications,
   isolation, and forbidden counters in a separate process.
7. Update handoffs/progress, run focused and full tests plus credential/diff
   checks, commit, and push.

## Interpretation Contract

- A direction is supported only when the unchanged frozen rollout-count,
  variance, mean-advantage, positive-confidence, and both continuation-profile
  gates all pass.
- Inconclusive cases remain excluded from future strong labels.
- Only a supported teacher-over-current comparison may be proposed for a
  separate later dataset stage. This stage does not build or train on it.
- A supported current-over-teacher comparison is evidence against adding the
  teacher ordering and must not be reversed or relabeled.

## Prohibited Work

- Do not execute or inspect source evidence for `14077:10` or any development
  target. Do not transfer evidence between different action hashes.
- Do not define/build a dataset or objective, train, fine-tune, tune, search,
  select or modify a checkpoint, load locked test or the complete website
  bundle, run Arena/Shadow/website play, start model control, promote, or claim
  capability.
- Do not change `tempo_baseline`, website protocol, Elo semantics, frozen
  thresholds, information-set sampling, schedules, seeds, or return semantics.

## Acceptance Criteria

- All frozen hashes and exact target/action identities reproduce; exactly two
  permitted train cases and no excluded case execute.
- Exactly 16 isolated determinization tasks, 32 schedule items, and 64/64
  candidate rollouts complete: 32 per case, balanced by candidate and profile.
- Timeout, failure, retry, sequential fallback, missing, duplicate, extra,
  mapping, identity, nonfinite, and partial-output counts are zero.
- Every statistic, failure reason, and directional classification reproduces
  independently under the unchanged gates. Exclusion and forbidden-operation
  counters are all zero.
- Credential occurrences in new tracked/curated files are zero.
- Handoffs, focused tests, full tests, conventional commit, and push succeed
  before Stage 6.19 is accepted.
