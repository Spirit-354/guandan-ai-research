# Stage 6.14R Timeout Recovery Audit

## Outcome

The no-rollout recovery audit completed and independently reproduced the exact
Stage 6.14 blocker. The unchanged sequential confirmation path is exhausted:
all existing semantics-preserving engine optimizations and the baseline action
cache were already active when `13872:4` reached the 600-second case deadline.

Stage 6.14 remains incomplete. No partial comparison became eligible evidence.

## Exact Failure Path

The frozen Stage 6.9 executor creates one absolute deadline at case start:

```text
deadline = started + 600 seconds
```

It then traverses all 16 schedule items and both candidates. Each candidate
simulation checks that common deadline before every continuation step. Once the
deadline has passed, the simulation returns `case_time_budget_exhausted`; the
fixed schedule continues and records one failure for each later candidate call.

The two supported-looking cases must each contain all 16 paired results because
the frozen gate rejects an incomplete paired count. They therefore account for
64 completed candidate values. The terminal total of 90 leaves 26 completed
values, or 13 pairs, in `13872:4`. Its final three paired schedule items account
for exactly six missing candidate values, matching the observed failure count.

## Existing Optimization Boundary

The Stage 6.14 entry point already installs the frozen offline patches for:

- all-out decisions;
- non-bomb follow decisions;
- bomb finish setup for lead and follow;
- exact remaining-group calculation;
- legal-play option caching.

It also enables the complete-visible-state `tempo_baseline` action cache. The
repository contains equivalence checkers for these caches and optimizations.
There is no additional existing sequential toggle to enable.

The repository does use `ProcessPoolExecutor` for other offline workloads, but
the confirmation remains sequential. The only frozen recovery direction is a
separate process-isolation equivalence stage. It must prove, without a real
rollout, that one task per determinization recreates the same hidden assignment,
actions, local seeds, greedy/tempo behavior, returns, failures, common deadline,
schedule order, and parent-side Stage 6.9 metrics.

## Curated Evidence

- Artifact:
  `website_teacher_preference_residual_corrective_remaining_timeout_recovery_audit_v1.json`.
- SHA-256:
  `75115cfc5a9dfa3ecb6ac868d04a2e73d20473cfe3a49c8e805a042028872c0d`.
- Independent audit: passed.
- Frozen/input hashes verified: 12.
- Real rollout executions: 0.
- Failed Stage 6.14 confirmation output present: no.

## Safety and Isolation

- Model loads or scores: 0.
- Dataset/objective construction: 0.
- Training, fine-tuning, tuning, or checkpoint changes: 0.
- Deadline, rollout-step, seed, profile, return, or threshold changes: 0.
- Locked-test or complete website-bundle loads: 0.
- Arena, website Shadow, website games, or model-controlled actions: 0.
- Promotion, capability claims, partial labels, or unsupported labels: 0.

## Decision

Do not repeat the sequential run. Stage 6.14P may implement only a Windows-
spawn-safe process-isolated scheduling layer and synthetic equivalence tests.
The formal three-case confirmation remains forbidden until that layer and an
independent static audit prove every frozen semantic invariant. If they cannot,
Stage 6.14 must be frozen as infeasible under the unchanged contract.
