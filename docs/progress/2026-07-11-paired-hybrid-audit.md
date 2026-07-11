# Paired Hybrid Override Audit

## Motivation

The `m038` 300-game arena result contained only nine hybrid overrides. Its
44.33% aggregate win rate could not isolate the effect of those actions from
ordinary deal variance. A paired counterfactual audit was added to compare the
baseline action and DMC override from the exact same game state.

## Implementation

- Replays fixed-seed local games with the website oracle legal mask.
- Uses source override `(game_index, step)` records to avoid rescanning all 300
  games.
- Clones each matching game state before applying either action.
- Continues both branches with the same seed and selected offline policy.
- Separates correctness validation from the policy promotion gate.
- Saves partial results after every matched state.
- Records website-rule fallback when a legal wildcard physical combo is absent
  from the oracle option enumeration.

No live strategy, website communication, Elo retrieval, or `tempo_baseline`
decision logic was changed.

## M038 Source Audit

The coarse audit replayed all seven source games containing the nine recorded
control-pass overrides. Continuations used `greedy_bot` and ran to terminal.

- Source states matched: 9/9
- Baseline branch wins: 5/9
- Pass override branch wins: 5/9
- Causal win-rate delta: 0.0
- Improved pairs: 1
- Harmed pairs: 1
- Neutral pairs: 7
- 95% delta interval: -0.327 to +0.327
- Exact terminal pairs: 9/9
- Illegal actions: 0
- Fallbacks: 0
- Materialization failures: 0
- Hand-card mismatches: 0
- Oracle candidate validation failures: 0
- Website-rule option fallbacks: 2
- Policy gate: failed

The two option fallbacks were legal four-card bombs involving wildcard
interpretation. Both passed website rule recognition, physical hand-subset
validation, and action mapping before execution.

## Decision

Do not promote the control-pass override. The existing nine source states show
no net paired win benefit and are below the 30-state minimum for a policy gate.
Further work should collect new offline override states or improve Q-value
calibration before another candidate is tested.
