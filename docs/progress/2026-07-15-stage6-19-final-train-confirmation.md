# Stage 6.19 Frozen Two-New-Action Train-Only Counterfactual Confirmation

Date: 2026-07-15

Status: accepted; both comparisons inconclusive, no capability claim.

## Scope

This stage executed the accepted frozen process-isolated schedule exactly once
for only `14031:4` index 2 and `14025:20` index 2. It did not rerun
`14077:10`, expose development evidence, change sampling/seeds/profiles/limits/
returns/gates, build a dataset or objective, train, run Arena, or access the
website.

## Execution Integrity

- All 30 unique frozen hashes matched before and after execution.
- Exactly 16 isolated determinization tasks reconstructed 32 schedule items.
- Exactly 64/64 candidate rollouts completed: 32 per case and 32/32 by
  greedy/tempo profile.
- Timeout, candidate failure, retry, sequential fallback, missing, duplicate,
  extra, and partial-output counts were zero.
- `14077:10`, three development targets, and 16 other teacher states had zero
  source mappings, executions, rollouts, and design use.

## Results

- `14031:4`: inconclusive. Teacher/current means `0.875/0.75`, variances
  `0.25/0.4666666667`, teacher-minus-current advantage `0.125`, 95% lower
  bound `-0.12`, and greedy/tempo advantages `0.25/0.0`.
- `14025:20`: inconclusive. Means `1.0/1.0`, variances `0.0/0.0`, advantage
  and lower bound `0.0/0.0`, and greedy/tempo advantages `0.0/0.0`.
- Both directions failed the unchanged mean-advantage, positive-confidence,
  and dual-continuation requirements. The supported manifest is empty.

## Independent Audit

A separate process reproduced all frozen/action hashes, physical mappings,
task and schedule identities, determinization seeds, paired returns, means,
variances, confidence bounds, profile advantages, classifications, exclusion
counts, aggregates, executor metadata, and forbidden counters. All prohibited
operation counters were zero.

## Evidence

- Curated output:
  `website_teacher_preference_remaining_corrective_final_train_confirmation_v1.json`
- Output SHA-256:
  `a1f32207255867dd2a59c7f9043c57038aff37f506746c970f8892f1d852e189`
- Implementation SHA-256:
  `63d0f047d11d4b92b9a3fcdcd9dd2ee68b939e68fafc19513fb3a1527ec41bdb`

## Decision

Add no new corrective pair and do not rerun any of the three directly
inconclusive train cases. No further dataset extension or training is
authorized on this route. The next single stage is a no-execution final Stage
6 disposition audit; Arena and Stage 7 remain unauthorized until that audit
locks the result.
