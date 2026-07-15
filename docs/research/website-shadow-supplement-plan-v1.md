# Website Shadow Supplement Plan v1

This plan extends the frozen 50-game website dataset without changing any
existing game or session assignment. It does not add to or inspect the contents
of the locked test partition for candidate design.

## Evidence and target

- Frozen manifest: `website_dataset_split_manifest_050.json`
- Frozen manifest hash:
  `83a58a43ea91f5662e2588494d7bad1b3d9d18de51c30216e5be0e589e0437e4`
- Current information-set-consistent train/development decisions: 423
- Current consistent train decisions: 319
- Current consistent development decisions: 104
- Current consistent lead/follow decisions: 53/370
- Current consistent level-6 decisions: 11
- Current Elo bands: 1900-1999 and 2000-2099
- Minimum rollout gate: 500 consistent train/development decisions
- Collection target: at least 600 consistent train/development decisions

The supplement uses the cumulative public-history collector, so every accepted
new decision must be information-set consistent. Collection count is a minimum
coverage milestone, not evidence that a learned policy is stronger.

## Frozen assignments

The two new collection sessions are assigned before collection:

- `logs_website_shadow_supplement_train_001`: train, target 5 completed games
- `logs_website_shadow_supplement_development_001`: development, target 3
  completed games

No new session may be assigned to `locked_test`. The original nine locked games
must remain exactly unchanged. The machine-readable assignments are in
`website_dataset_extension_session_splits_v1.json`.

## Collection commands

Credentials must already exist in `GUANDAN_USER` and `GUANDAN_PASSWORD` in the
launching shell. They must never appear in commands, logs, source, manifests, or
documentation.

```powershell
python -u -B .\play_research_adaptive.py --website-shadow --profile tempo_baseline --loop --games 5 --metric elo --require-elo --require-bot-table --log-dir logs_website_shadow_supplement_train_001 --poll 8 --delay 10 --timeout 45 --retries 5

python -u -B .\play_research_adaptive.py --website-shadow --profile tempo_baseline --loop --games 3 --metric elo --require-elo --require-bot-table --log-dir logs_website_shadow_supplement_development_001 --poll 8 --delay 10 --timeout 45 --retries 5
```

Only the frozen `tempo_baseline` may submit actions. A table that is not verified
as four website bots must stop before the first submitted action. Communication
or legality failures stop collection and are not silently excluded.

## Extension build

After both sessions complete, rebuild from all original source directories plus
the two supplement directories. Use a new output manifest and data card; never
overwrite the original frozen artifacts.

```powershell
$sources = @(
  "logs_website_shadow_candidates_smoke",
  "logs_website_shadow_batch_001",
  "logs_website_shadow_batch_002",
  "logs_website_shadow_batch_003",
  "logs_website_shadow_batch_004",
  "logs_website_shadow_batch_005",
  "logs_website_shadow_batch_006",
  "logs_website_shadow_batch_007",
  "logs_website_shadow_batch_008",
  "logs_website_shadow_batch_009",
  "logs_website_shadow_supplement_train_001",
  "logs_website_shadow_supplement_development_001"
) -join ","

python -u -B .\play_research_adaptive.py --build-website-danzero-dataset $sources --website-dataset-out website_danzero_shadow_extension_v1.pth --freeze-website-splits --website-base-split-manifest website_dataset_split_manifest_050.json --website-extension-session-splits website_dataset_extension_session_splits_v1.json --website-split-manifest-out website_dataset_split_manifest_extension_v1.json --website-data-card-out website_dataset_card_extension_v1.json
```

The extension build must fail if an old session or game changes split, an old
game is missing, a new session lacks an explicit assignment, a new session is
assigned to locked test, or the locked game set changes.

## Acceptance gate

- baseline freeze mismatch count: 0
- bot-only completed games: 8 new games
- model-controlled actions: 0
- all accepted supplement decisions information-set consistent
- consistent train/development decisions: at least 600 target, never below 500
- train and development both non-empty
- locked game set identical to the base manifest
- duplicate state rate reported
- leaderboard Elo only; final-state scores remain proxy-only

If the target is not met, create and freeze a separate v2 supplement plan before
collecting another session. Do not retroactively move sessions or locked games.
