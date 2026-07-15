# Stage 6.14E Formal Process-Isolated Three-New-Top1 Confirmation

Date: 2026-07-15

Status: accepted.

## Scope

This stage used the accepted Stage 6.14P executor exactly once for only
`13957:14` index 17, `14038:12` index 3, and `13872:4` index 19. It did not
change the frozen actions, information-set sampler, seeds, continuations,
limits, return definition, metrics, thresholds, or directional gates.

## Result

- 24 isolated determinization tasks and 48 schedule items completed 96/96
  candidate rollouts, split 48/48 between greedy and frozen tempo.
- Timeout, candidate failure, retry, sequential fallback, missing result, and
  duplicate result counts were zero.
- `13957:14`: teacher-over-current-top1 supported; advantage `1.0`, 95% lower
  bound `0.4939301761`, greedy/tempo `1.25/0.75`.
- `14038:12`: teacher-over-current-top1 supported; advantage `0.75`, lower
  bound `0.26`, greedy/tempo `0.25/1.25`.
- `13872:4`: inconclusive; advantage `0.25`, lower bound `-0.24`, greedy/tempo
  `0.25/0.25`.
- The three excluded train cases and three development cases had zero source
  mappings, executions, and rollouts. Every forbidden-operation count was
  zero.

## Independent Audit

A separate process reproduced all frozen and executor hashes, target/action
identities, physical mappings, determinization seeds, returns, means,
variances, confidence bounds, per-profile advantages, directions, aggregates,
isolation counters, and forbidden counters.

## Evidence

- Curated output:
  `website_teacher_preference_residual_corrective_remaining_train_confirmation_v1.json`
- Output SHA-256:
  `450e89f780a33dd543f49f029e735f7fb32e11cd657163c52e6a4301d21f7eb5`
- Formal wrapper SHA-256:
  `972b67ed585e9a96f9e8be55b70d0b6585a7e499f6dc692c2861d5e636b9e55d`

## Decision

Only the two supported train comparisons may enter a separate frozen dataset
extension. The inconclusive case and all prior train/development exclusions
add no pair. No training, Arena, website activity, promotion, or capability
claim is authorized by this result.
