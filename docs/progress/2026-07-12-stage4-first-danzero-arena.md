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
