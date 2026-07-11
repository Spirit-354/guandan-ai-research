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

## Balanced50k 30-State Audit

The first evidence-producing run evaluated 30 differing DMC/baseline states
from a deterministic baseline trajectory. Each candidate used one greedy-bot
continuation rollout to terminal.

- Evaluated states: 30
- Evaluated candidate actions: 115
- Q top-1 versus rollout-best agreement: 20/30 (66.67%)
- Pairwise comparable action pairs: 97
- Pairwise Q-order agreement: 54/97 (55.67%)
- Q value MSE: 0.8713
- Q value MAE: 0.7445
- Q probability Brier score: 0.1979
- DMC action better than baseline: 3 states
- Baseline action better than DMC: 1 state
- Equal terminal outcome: 26 states
- Average DMC-minus-baseline win value: +0.0667
- Average DMC team-rank improvement: +0.05
- High-margin harmful choices: 1
- Scanner and rollout legality failures: 0
- Website-rule option fallbacks: 2
- Correctness threshold: passed
- Q calibration gate: failed

The high-margin harmful case occurred on the opening lead. DMC preferred a
triple over the baseline gangban with a Q margin of 0.3001. Both branches won,
but the DMC branch had a worse average team rank (2.0 versus 1.5), so the model
was confidently wrong about the action ordering.

This sample is sufficient to reject immediate hybrid promotion, but not to
claim a stable +0.0667 policy gain: all states came from one trajectory and
each action received one rollout. The next training step should use these
counterfactual action pairs to build a pairwise action-value dataset and train
with an ordering loss before another arena candidate is created.
