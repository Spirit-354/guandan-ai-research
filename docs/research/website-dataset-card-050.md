# Website Shadow Dataset Card: Frozen 050

## Scope

This dataset contains baseline-only website Shadow decisions against verified
website bots. It supervises `Q(s, a_behavior)` only. Unexecuted legal candidates
have no factual return label and cannot be treated as preferred or rejected
actions without information-set counterfactual evaluation.

## Frozen Identity

- manifest: `website_dataset_split_manifest_050.json`
- manifest SHA-256 content hash:
  `83a58a43ea91f5662e2588494d7bad1b3d9d18de51c30216e5be0e589e0437e4`
- format: `website_danzero_action_value_v1`
- state/action dimensions: 513/54
- metric source: `leaderboard_elo`
- split policy: temporal collection sessions targeting 70/15/15

## Population

- independent games: 50
- wins/losses: 28/22
- decisions: 1,294
- legal candidate actions: 35,231
- collection sessions: 10
- verified bot tables: 50/50
- rejected games or decisions: 0
- duplicate state rate: 0

The original online encoder treated the website's rolling 40-action history as
complete history. A post-freeze information-set audit found only 513/1,294
states preserved the physical unknown-card invariant; the remaining 781 are
retained for audit provenance but are forbidden from behavior-Q or rollout
training.

## Physical Isolation

- train/development: 423 information-set-consistent decisions physically stored
  in `website_danzero_shadow_050_frozen.train_dev.pth`
- locked test: 90 consistent decisions physically stored only in
  `website_danzero_shadow_050_frozen.locked_test.pth`
- formal training refuses the complete bundle and never loads the locked-test file
- 672 inconsistent train/dev and 109 inconsistent locked-test decisions are
  excluded from the physical partitions

## Coverage

- all four first-player positions represented
- all 13 possible level ranks represented
- level-card available decisions: 695
- heart-level wildcard available decisions: 261
- lead/follow decisions: 213/1,081
- endgame decisions: 1,007
- bomb-candidate states: 486
- Elo bands: 1900-1999 and 2000-2099
- observed table signature: `玩家1|玩家2|玩家3|玩家4`

Seat coverage is intentionally seat 0 only because the website test client is
fixed to the self seat. Generic website bot names do not expose strength IDs;
Elo band and observed behavior remain the available strength covariates.

## Behavior-Q Diagnostic

The first two behavior-Q diagnostics are invalidated because they predated the
information-set consistency gate and included impossible states. Neither
checkpoint may be reused. A 50-state, eight-determinization sanity check on the
filtered train/dev partition completed 400/400 restores with exact 513-state
re-encoding and 108-card conservation.

Ten stratified train cases then completed 496 paired greedy-continuation
rollouts. No strong teacher label was emitted: apparent advantages had negative
95% lower bounds or excessive paired-return variance. This is a successful
uncertainty gate, not evidence that the behavior action was optimal.
