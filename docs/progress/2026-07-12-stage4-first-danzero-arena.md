# Stage 4: First DanZero Strength Gate

## Arena Contract

The dedicated 513+54 Arena loader rejects checkpoints whose state, action,
input, encoding, oracle, or reward metadata do not match the current runtime.
It uses:

- the complete `structured_exhaustive_website_oracle_v1` for model actions;
- the frozen `tempo_baseline` for the other team;
- Stage 0's 500-state baseline equivalence evidence plus the live freeze hash;
- paired games with identical deal, level, and first player;
- model team 0 in one game and model team 1 in the paired game;
- random first player across pairs;
- physical-card materialization and hand-subset checks on every action.

## Smoke Result

Checkpoint:
`models_danzero_dmc_stage3_1000/danzero_dmc_latest.pth`

Training evidence:

- 1,000 self-play games;
- 132,429 decisions;
- 997 learner updates;
- 20,000-transition replay;
- complete structured oracle;
- all engineering integrity counters zero.

Paired 20-game Arena:

- completed games: 20/20;
- model wins: 0;
- baseline wins: 20;
- model win rate: 0.0%;
- model teams: 10 games as team 0, 10 as team 1;
- first-player distribution: `4/4/6/6`;
- model decisions: 944;
- baseline decisions: 826;
- model pass rate: 66.10%;
- model bomb usage rate: 2.97%;
- illegal actions: 0;
- fallbacks: 0;
- materialization failures: 0;
- hand-card mismatches: 0;
- fatal empty candidate sets: 0;
- elapsed time: about 12.2 minutes.

## Decision

The checkpoint fails the explicit Stage 4 gate: a 20-game win rate below 30%
is eliminated. It is moved from `offline_only` to `failed` and must not be
continued, promoted to 100 games, used for Shadow, or connected to the website.

This is a strategy-quality failure, not a rule/runtime failure. Visible
symptoms include a 66.1% Arena pass rate and only 997 learner updates for more
than 132k generated decisions. The next candidate must change the training
recipe and repeat the 100k-decision smoke; simply extending this checkpoint
would violate the gate.

## Next Analysis

Before another long run, compare failed model actions with baseline actions on
the same Arena states and measure:

- pass when a legal beat exists;
- action-type coverage and Q margins;
- Q values for visited versus rarely visited actions;
- endgame block and teammate-support errors;
- learner update-to-sample ratio;
- replay age and policy-version distribution.

The evaluation threshold remains unchanged. No website test is authorized.

## Higher-Update Follow-up

A fresh v2 candidate kept the same architecture, oracle, reward, and 1000-game
budget, but increased learner updates from 1 to 8 per game and used epsilon
`0.50 -> 0.10` over the smoke run.

- decisions: 132,569;
- learner updates: 7,976;
- final recent MSE: approximately 0.077;
- training pass rate: 58.73%;
- integrity errors: all zero;
- paired Arena wins: 1/20;
- Arena win rate: 5%;
- Arena pass rate: 61.95%.

The much lower regression loss did not produce useful policy strength. v2 also
fails the below-30% gate and is archived. This rules out “only add more gradient
updates” as the next experiment. The next candidate must add action-ranking
information, such as a small frozen-baseline teacher curriculum with negative
candidate margin loss, before returning to shared-Q self-play.

## Teacher-Margin Follow-ups

v3 added ten frozen-baseline teacher games and eight random negative actions per
teacher decision. The teacher samples shared the ordinary 20,000-transition
replay, so the last 100 updates contained no teacher margin signal. Its paired
Arena result was 0/20 with all integrity counters zero. This run is archived.

v4 introduced a separate persistent teacher replay and a fixed 25% teacher
share in every learner batch. The 1,000-game run completed with:

- 10/10 teacher games and 1,017 teacher decisions;
- 7,960 learner updates;
- 128 teacher samples in each of the last 100 batches;
- nonzero teacher margin loss through the end of training;
- 58.10% training pass rate;
- all integrity counters zero.

The paired Arena improved to 4/20 (20%), with a 60.58% model pass rate and all
integrity counters zero. This is evidence that persistent teacher ranking helps,
but v4 remains below the unchanged 30% continuation gate and is archived.

Checkpoint diagnosis showed 100% top-1 accuracy against the stored random
negative actions, with mean teacher Q margin 0.648. The next experiment should
therefore improve negative-action coverage (complete candidates or current-model
hard negatives), not continue v4 or merely increase its game count. Teacher
samples must also bypass policy-version staleness because they do not depend on
the actor policy that generated self-play actions.
