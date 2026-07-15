# Stage 6.14P Process-Isolated Determinization Parallel Equivalence

Date: 2026-07-15

Status: accepted. No real rollout executed.

## Scope

This stage added only a Windows-spawn-safe process-isolated executor and
synthetic equivalence evidence. The frozen Stage 6.14 sequential confirmation,
actions, sampler, seeds, continuation policies, limits, metrics, and gates were
not modified.

## Result

- All 13 frozen hashes matched and the failed formal confirmation output stayed
  absent.
- Exactly eight tasks reconstructed 16 schedule items and 32 candidate calls
  per case in frozen teacher/top1 and greedy/tempo order.
- Synthetic sequential and real process-pool executions matched all sample
  hashes, seeds, action identities, profiles, returns, failures, ordering,
  aggregates, and Stage 6.9 metrics.
- Both complete and timeout/failure scenarios matched. Missing/duplicate
  tasks/calls and seed/deadline mismatches failed closed.
- The common 600-second deadline and 300-step limit propagated unchanged.
- Real rollout and every prohibited operation count were zero.

## Evidence

- Curated artifact:
  `website_teacher_preference_residual_corrective_remaining_parallel_equivalence_v1.json`
- Artifact SHA-256:
  `8e168656c35519aae9054038f0fd31398ac0e9260c419de0534a09bf1f4c59ca`
- Parallel implementation SHA-256:
  `f2093a8c348d9d91435209fd9ee258130b18f7de7b4b7758c0656c1d7a70e2e5`

An independent process recreated both process-pool scenarios and the complete
artifact exactly.

## Decision

Permit exactly one separate formal process-isolated Stage 6.14 execution for
the three frozen train cases. Sequential fallback and retry remain forbidden.
Stage 6.14 remains incomplete until that execution reaches 96/96 and passes an
independent audit.
