# DMC Q Calibration Audit

## Motivation

The 300-game `m038` control-pass experiment produced nine overrides. A paired
counterfactual replay found one improved state, one harmed state, and seven
neutral states. The net causal value was zero, so further threshold tuning
would not address the underlying issue: DMC Q values may be poorly calibrated
or may rank actions incorrectly.

## Implementation

The new offline audit:

- scans deterministic local `tempo_baseline` trajectories;
- obtains every legal action from the website-rule oracle;
- scores all legal actions with the selected DMC Q model;
- evaluates baseline, DMC top-K, pass, smallest non-bomb, and smallest bomb
  candidates from identical cloned states;
- uses identical continuation seeds for all actions at a state;
- reports value error, action-ranking agreement, q-margin buckets, context
  summaries, pairwise ordering accuracy, rank regret, and high-confidence
  harmful choices;
- runs the existing 200-state baseline equivalence guard before evaluation.

No live strategy, website communication, Elo retrieval, or `tempo_baseline`
decision behavior was changed.

## Smoke Validation

The CUDA smoke evaluated two states and nine candidate actions using greedy
continuations to terminal.

- Evaluated states: 2
- Evaluated actions: 9
- Baseline equivalence: 200 samples, 0 mismatches
- Scanner illegal actions: 0
- Scanner fallbacks: 0
- Scanner materialization failures: 0
- Scanner hand-card mismatches: 0
- Rollout illegal actions: 0
- Rollout fallbacks: 0
- Rollout materialization failures: 0
- Rollout hand-card mismatches: 0
- Correctness threshold: passed
- Q calibration gate: not passed because the sample is below 30 states

The smoke is a mechanics check only. The next evidence-producing run should
audit at least 30 states before deciding whether to build a pairwise
action-value dataset or reconsider hybrid validation.
