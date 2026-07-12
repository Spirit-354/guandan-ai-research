# Stage 2: Website Shadow Audit Scaffold

## Status

The implementation and offline tests are complete. The 20-50 game website
Shadow gate has not started because `GUANDAN_USER` and `GUANDAN_PASSWORD` are
not present in the current process environment. No website request was made
during this implementation stage.

## Safety Contract

- the only submitting policy is the frozen `tempo_baseline`;
- `model_controlled_action` is always false and its count is always zero;
- credentials are read only from environment variables and never written to
  logs;
- the current suggestion source is `tempo_baseline_mirror`, not a learned
  checkpoint;
- server communication and leaderboard Elo handling are unchanged;
- `final_state["scores"]` remains proxy-only.

This mirror mode intentionally validates the website-state adapter, physical
action encoding, oracle legality, and server acceptance before a new DanZero
model exists. A learned suggestion source will be added only after the DMC
stage produces a gated checkpoint, and it will still remain non-submitting
until the user approves website model control.

## Logged Decision Evidence

Every Shadow decision records:

- 513-dimensional paper state and 487-dimensional website state;
- encoding versions and finite/dimension checks;
- relative seat and team mapping;
- submitted baseline action and Shadow suggestion separately;
- 54-dimensional physical action identity;
- action type, rank, size, level-card and heart-level wildcard presence;
- all locally recognized wildcard interpretations;
- hand multiset membership, local legality, and oracle membership;
- explicit server acceptance or an inferred acceptance after submit timeout.

Each completed game records a `website_shadow_summary` with counts for state,
team, hand, legality, oracle, materialization, website-rule, and wildcard
errors. Ordinary non-Shadow logs do not receive this field.

## Offline Validation

The pure tests cover:

- website state conversion from `seats`, `teams`, `hand_counts`,
  `trick_history`, `ranking`, level, and own hand;
- 513/487 feature dimensions;
- username-to-seat ranking conversion;
- valid follow action and oracle membership;
- action-not-in-hand rejection;
- server result propagation and zero model-controlled actions.

Historical website logs can be replayed without networking using
`--website-shadow-replay`. Their `trick_history` is capped at 40 actions, so a
final log cannot reconstruct an earlier decision's complete 513-dimensional
state. Replay therefore audits only the recorded chosen action, hand, level,
last play, team mapping, and server result. It explicitly reports
`state_encoding_not_evaluated_count` and never treats replay as satisfying the
online Shadow state gate.

The complete available replay covered 134 completed `tempo_baseline` games and
3,573 recorded website actions. Reconstruction, team mapping, hand membership,
chosen-action legality, chosen-action oracle membership, materialization,
server-rule, and wildcard error counts were all zero. All 134 logs had capped
history, so all 3,573 state encodings remained explicitly unevaluated and
`online_shadow_gate_satisfied` remained false.

The frozen baseline verifier remains mandatory. Online Stage 2 passes only
after at least 20 completed test-account games have all of these at zero:

- `action_not_in_hand_count`;
- `local_legality_error_count`;
- `oracle_disagree_count`;
- `materialization_fail_count`;
- `website_rule_disagree_count`;
- `team_mapping_error_count`;
- `level_wildcard_error_count`.

## Pending Run

Once credentials are set in the launching PowerShell process, run:

```powershell
python -u -B .\play_research_adaptive.py --website-shadow --profile tempo_baseline --loop --games 20 --metric elo --require-elo --log-dir logs_website_shadow_stage2 --poll 8 --delay 10 --timeout 45 --retries 5
```

The run is a baseline website session with Shadow auditing. It is not model
control and does not authorize any later learned checkpoint to submit actions.
