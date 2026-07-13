# Website-Domain Research Protocol

This protocol is mandatory for website-domain training and evaluation. It does
not change the frozen `tempo_baseline`, website communication, leaderboard Elo
acquisition, or the proxy-only meaning of `final_state["scores"]`.

## Behavioral Value Boundary

Website logs containing only the submitted action and the terminal team result
supervise `Q(s, a_behavior)` only. Unexecuted legal candidates are unlabeled.
Such data may initialize website-domain representations and a Q network, but it
does not establish reliable candidate ranking, policy improvement, or permission
to replace the baseline. Lower validation loss is not a strategy-strength claim.

## Information Set

States, search, and teacher labels may use only information available to the
acting player at decision time. Opponent or teammate hands, future actions,
future states, and post-hoc information are forbidden inputs. Hidden cards must
be sampled from the legal information set through repeated determinizations.

Every counterfactual teacher label must record rollout count, hidden-card
sampling method, mean return, return variance, candidate advantage, and label
confidence. High-variance or low-advantage comparisons cannot become strong
teacher labels.

## Data Isolation

Website data is grouped by complete game and further separated by collection
session, time block, and bot-table signature. The required partitions are:

- train;
- development validation;
- locked test.

Locked-test games cannot be used for training, hyperparameter or checkpoint
selection, teacher-threshold tuning, or candidate design. Formal website-control
games remain outside all training data until the declared study is concluded.

## Coverage Gate

Game count alone is not sufficient. Every dataset report must include independent
games, decisions, candidate actions, outcome balance, seat and first-player
coverage, level-card and wildcard coverage, lead/follow coverage, endgame and
bomb-state coverage, Elo bands, bot/table coverage, and duplicate-state rate.
Insufficient coverage requires more or targeted data, never more epochs.

## Dual Capability Gate

Candidates must pass both:

1. paired, seat-swapped local Arena against frozen `tempo_baseline`;
2. a website-domain gate using locked website states, bot behavior models,
   information-set rollout, and representative website cases.

Neither gate implies the other. Shadow performance also does not imply positive
return under real control.

## Shadow Gate

Shadow reports legality, physical action materialization, hand-subset integrity,
model/baseline disagreement, Q calibration, teacher advantage, checkpoint
consistency, in-distribution support, low-support action rate, and a casebook of
high-confidence disagreements. Confidence alone never authorizes control.

## Controlled Website Escalation

Model control advances only through 1-2 communication-smoke games, then 5, 10,
20, 50, 100, 200, and 500 games. The first takeover and every increase in risk
require explicit user confirmation. Any illegal action, materialization failure,
hand mismatch, duplicate submit, unrecoverable desynchronization, non-leaderboard
value written as Elo, or active stop-loss breach stops the stage immediately.

## Frozen Final Analysis

Before formal testing, freeze sample size, primary Elo interval, win definition,
completed-game definition, exclusions, stop-loss, Wilson implementation, primary
metric, and stratified secondary metrics. Model-caused failures stay in the win-
rate denominator and also fail safety acceptance.

The final gate requires both observed win rate at least 70% and the 95% Wilson
lower bound at least 70%. At 500 games this needs approximately 371 wins (74.2%),
not 350 wins.

## Current Evidence Status

The first 16-game website dataset and its Q-training smoke are pre-freeze pipeline
evidence only. They demonstrate dimensions, legality, persistence, and checkpoint
compatibility. They are not capability evidence and cannot promote a checkpoint.
