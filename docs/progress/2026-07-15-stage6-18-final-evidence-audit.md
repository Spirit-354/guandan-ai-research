# Stage 6.18 Frozen Three-Train Remaining-Top1 Evidence Audit

Date: 2026-07-15

Status: accepted; read-only evidence audit only, no capability claim.

## Scope

This stage reproduced the three remaining pipeline-train top-1 actions and the
three held-out development identities from Stage 6.17 without loading or
scoring a model. It opened only source evidence directly referenced by the
three train samples. No rollout, dataset, objective, training, tuning,
checkpoint operation, Arena, or website activity ran.

## Frozen Reproduction

- All 28 frozen hashes matched.
- Train targets reproduced exactly: `14077:10` index 0, `14031:4` index 2,
  and `14025:20` index 2.
- Development `13992:16`, `14074:9`, and `13871:9` remained identity-only.
- Missing, duplicate, extra, reconstructed, substituted, transferred, and
  ambiguous actions were zero.

## Evidence Result

- Two directly referenced train source files were opened and hashed.
- `14077:10` index 0 retained its frozen direct-paired inconclusive result.
- `14031:4` index 2 and `14025:20` index 2 both appear as source candidates,
  but no direct teacher-versus-current paired statistics exist.
- No current train ordering is supported in either direction.
- Prior Stage 6.4/6.9/6.13 evidence for `14025:20` refers to index 1 and a
  different action hash, so it was not transferred to current index 2.
- The future manifest is unexecuted. Only `14031:4` and `14025:20` are marked
  as needing new confirmation; `14077:10` remains preserved inconclusive.

## Isolation and Audit

- Development source-reference exposure, evidence queries, candidate
  inspection, and design use were all zero.
- Model loading/scoring and every forbidden operation counter were zero.
- A separate process reproduced all frozen/source hashes, action identities,
  classifications, aggregates, future-manifest entries, isolation counters,
  and forbidden counters.

## Evidence

- Curated output:
  `website_teacher_preference_remaining_corrective_final_evidence_audit_v1.json`
- Output SHA-256:
  `b7dc15c779556a972c1b471348cb949bd98d54c1ce1aecb14a3d23cda083681b`
- Implementation SHA-256:
  `6200af71c14081418b1abfd1fd45d99347c3f20d601ec355014dbbc931a3ea26`

## Decision

Preserve `14077:10` as inconclusive and do not rerun it. The next single stage
may execute the unchanged frozen train-only counterfactual schedule once for
only `14031:4` index 2 and `14025:20` index 2. Development remains excluded;
no dataset, objective, training, Arena, promotion, or capability claim is
authorized by this result.
