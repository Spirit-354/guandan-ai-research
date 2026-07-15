# Website Shadow Supplement Plan v2

This stage collects one new baseline-only train session. It does not rebuild a
dataset, inspect locked test, run teacher rollout, train a model, or permit
model-controlled website play.

## Frozen assignment

- Frozen extension v1 manifest:
  `website_dataset_split_manifest_extension_v1.json`
- Frozen extension v1 manifest hash:
  `db209561f6961b289dda668861687fcd7a258a2f283cecaae065501b2006f429`
- New session: `logs_website_shadow_supplement_train_002`
- Split assigned before collection: `train`
- Target: exactly 12 completed verified bot-table games
- Machine-readable cumulative extension assignments:
  `website_dataset_extension_session_splits_v2.json`

The v2 assignment file preserves both v1 supplement assignments and adds only
the new train session. It assigns no session to `locked_test`.

## Collection command

Credentials must come from `GUANDAN_USER` and `GUANDAN_PASSWORD` in the process
environment and must not be printed or persisted.

```powershell
python -u -B .\play_research_adaptive.py --website-shadow --profile tempo_baseline --loop --games 12 --metric elo --require-elo --require-bot-table --log-dir logs_website_shadow_supplement_train_002 --poll 8 --delay 10 --timeout 45 --retries 5
```

Only frozen `tempo_baseline` actions may be submitted. A non-bot table must stop
before the first action. Every completed game must record exhaustive Shadow
candidates, decision-time information-set consistency, a counted terminal
result, and `leaderboard_elo` before and after the game.

## Acceptance

- exactly 12 new completed verified bot-table games;
- model-controlled actions and non-bot-table submissions: 0;
- all communication, encoding, team mapping, hand-subset, legality, oracle,
  materialization, website-rule, wildcard, information-set, duplicate-submit,
  and unrecoverable-desync counters: 0;
- credential occurrences in generated logs and tracked files: 0;
- no dataset rebuild, teacher rollout, model training, or later-stage execution.
