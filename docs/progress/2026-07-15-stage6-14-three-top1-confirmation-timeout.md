# Stage 6.14 Three-Top1 Confirmation Timeout

## Outcome

Stage 6.14 was attempted but did not meet acceptance. The frozen three-case
schedule requested 96 action rollouts and completed 90. One case timed out and
six candidate values failed, so the curated writer correctly refused to create
`website_teacher_preference_residual_corrective_remaining_train_confirmation_v1.json`.

Stage 6.14 and Stage 6 remain incomplete. No partial comparison is eligible for
dataset construction, training, Arena, promotion, or capability evidence.

## Frozen Scope

The implementation selected only:

- `13957:14`, current top-1 index 17;
- `14038:12`, current top-1 index 3;
- `13872:4`, current top-1 index 19.

It excluded the already-inconclusive train cases `14077:10`, `13959:7`, and
`14025:20`, and kept development cases `13992:16`, `14074:9`, and `13871:9`
identity-only. Each excluded item retained zero source mappings, executions,
rollouts, and design uses.

The code directly reused the frozen Stage 6.9 materialization, 16-rollout/action
schedule, eight shared determinizations, greedy/frozen-tempo continuations,
stable seeds, paired statistics, and bidirectional gates.

## Execution Evidence

Preflight passed with seven exact frozen hashes, 3/3/3 executed/excluded/held-
out accounting, an unused output path, and 96 requested rollouts.

The instrumented terminal result was:

```text
13957:14  teacher_over_residual_supported
14038:12  teacher_over_residual_supported
13872:4   inconclusive
requested=96
completed=90
profiles={'greedy_bot': 48, 'tempo_baseline': 48}
timeouts=1
candidate_failures=6
```

The two supported-looking directions are not accepted evidence because the
formal confirmation failed its complete-run integrity contract. The incomplete
third case cannot become a label.

An earlier invocation was interrupted by an external 600-second command limit
before any case-completion output or curated artifact. It was not used as
experiment evidence. A following run printed the same three directions but was
rejected by a generic aggregate assertion before preserving exact failure
fields or an artifact. After adding exact accounting to the validation error,
the final instrumented run reproduced the blocker above. The output path
remained absent throughout. These retries also mean the intended one-shot
acceptance cannot be claimed.

## Safety and Isolation

- Dataset or objective constructions: 0.
- Model scoring, training, fine-tuning, tuning, or checkpoint changes: 0.
- Locked-test or complete website-bundle loads: 0.
- Arena, website Shadow, website games, or model-controlled actions: 0.
- Promotion or capability claims: 0.
- Partial or unsupported labels: 0.

## Decision

Do not rerun or weaken the contract in this stage. The next single stage is a
no-rollout recovery audit of the deadline and candidate-failure path. It may
freeze a subsequent retry only if an existing semantics-preserving offline
optimization can preserve every action, information-set, seed, continuation,
return, rollout-limit, and gate invariant. Otherwise it must freeze an
infeasibility conclusion.
