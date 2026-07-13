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

## Physical Isolation

- train: 31 games, included in `website_danzero_shadow_050_frozen.train_dev.pth`
- development: 10 games, included in the same train/dev file
- locked test: 9 games, stored only in
  `website_danzero_shadow_050_frozen.locked_test.pth`
- formal training refuses the complete bundle and never loads the locked-test file

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

Two five-epoch train/dev diagnostics were run without opening the locked-test
partition. Random initialization reached development MSE about 0.946 and sign
accuracy about 53.7%. Initializing from the prior v5 DanZero checkpoint reached
MSE about 1.325 and sign accuracy about 60.3%. These are representation and
calibration observations only. Neither checkpoint is a policy candidate, and
no ranking or capability claim is permitted.
