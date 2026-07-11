# DMC Pairwise Ranking Smoke

## Scope

This phase converted paired rollout outcomes into action-preference examples
and added a conservative DMC ranking trainer. It remained entirely offline and
did not change `tempo_baseline`, website communication, Elo retrieval, or live
strategy behavior.

## Dataset

The enriched 30-state calibration report contained state observations and
action features for every evaluated candidate.

- Source states: 30
- Raw candidate pairs: 176
- Material preference pairs: 97
- State groups represented: 24
- Pairs rejected as outcome/rank ties: 79
- State dimension: 3049
- Action feature dimension: 31
- Legal mask source: website oracle

The builder preferred terminal win differences first and average team-rank
differences second. Training and validation were split by state group.

## Training Smoke

The balanced50k DMC checkpoint initialized a 15-epoch ranking run with a
learning rate of `1e-5`, pairwise margin `0.10`, and reference anchor weight
`0.25`.

- Train samples: 69 from 19 state groups
- Validation samples: 28 from 5 state groups
- Train pairwise accuracy: 52.17% to 81.16%
- Validation pairwise accuracy: 64.29% to 71.43%
- Validation pairwise loss: 0.6739 to 0.6693
- Best epoch: 15
- Training threshold: passed

## Arena Result

The best pairwise checkpoint then played 20 offline games against
`tempo_baseline`, with seat swapping and random first players. Runtime was
approximately 42 minutes including the 200-state equivalence check.

- Completed games: 20
- Pairwise DMC wins: 0
- Tempo baseline wins: 20
- Pairwise DMC win rate: 0.0
- Illegal actions: 0
- Fallbacks: 0
- Materialization failures: 0
- Hand-card mismatches: 0
- Baseline equivalence mismatches: 0/200
- Website shadow allowed: false
- Website dry-run allowed: false

## Decision

Do not expand or deploy this checkpoint. The pairwise training pipeline works,
but 97 pairs from 24 states are too narrow and improved held-out ranking labels
did not translate into game strength. The result also shows that a modest Q
anchor is insufficient to preserve global policy behavior when supervision is
this concentrated.

Before another pairwise training attempt, collect counterfactual pairs across
many independent games and action contexts, measure Q drift against the source
model, and require an arena regression guard against the unchanged initializer.
