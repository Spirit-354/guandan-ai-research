# Website Bot Domain-Adaptation Route

The mandatory research constraints are defined in
`docs/research/website-domain-protocol.md`. That protocol takes precedence over
milestone counts or favorable intermediate metrics.

The user authorized staged automated play on a dedicated test account against
website bots only. Leaderboard Elo is no longer a stop-loss objective, but it
remains a required environment variable because score economics and matched bot
strength can change by Elo segment.

## Final Contract

- at least 500 completed website-bot games with `elo_before >= 2200`;
- 95% Wilson lower confidence bound for team win rate at least 70%;
- separate reporting by 100-Elo observation band and opponent signature;
- zero legality, fallback, materialization, and hand-subset errors;
- `final_state["scores"]` remains proxy-only and is never treated as Elo;
- no human-opponent automation.

## Stages

1. Run the frozen `tempo_baseline` on the test account to calibrate website bot
   identities, strength distribution, Elo economics, and rule/runtime behavior.
2. Collect website Shadow states and outcomes while baseline remains the
   submission policy.
3. Build website-domain 513-state/54-action teacher and action-value data.
4. Pretrain action ranking, then apply conservative DanZero DMC fine-tuning.
5. Run champion/challenger Shadow and randomized website A/B in 50, 200, and
   500-game stages.
6. Promote only when the high-Elo Wilson target and all integrity gates pass.

Credentials must be supplied through `GUANDAN_USER` and `GUANDAN_PASSWORD` in
the process environment. They must not be committed or printed.

Historical bot-table audit scanned 500 log files and found 497 valid completed
states. Every one used seats `\u73a9\u5bb61/\u73a9\u5bb62/\u73a9\u5bb63/\u73a9\u5bb64` with the test
client at seat 0. Website runs under this route must use `--require-bot-table`;
any other signature stops before the first submitted action. The generic names
do not expose individual bot strength, so strength is inferred from Elo bands
and observed outcomes rather than nickname.

## Initial Calibration

The frozen baseline completed 20 verified bot games across the 2000-2099 and
2100-2199 Elo bands:

- 10 wins and 10 losses, team win rate 50%;
- 95% Wilson interval approximately 29.9% to 70.1%;
- total leaderboard Elo delta -36, average -1.8 per game;
- average win gain 13.3 and average loss cost 16.9;
- estimated break-even win rate 56.0%;
- zero illegal, fallback, materialization, hand-subset, or submit-desync errors.

This makes `tempo_baseline` a data-collection control, not a candidate for the
70% final target.

## Website-Domain Dataset

Online Shadow now records every website-oracle legal candidate as a 54-value
physical action vector alongside the 513-value DanZero paper state. The offline
builder accepts only completed, counted, leaderboard-Elo, verified-bot games
whose Shadow integrity gate passed:

```powershell
python -u -B .\play_research_adaptive.py `
  --build-website-danzero-dataset logs_website_shadow_candidates_smoke `
  --website-dataset-out website_danzero_candidates_smoke.pth
```

The first real smoke dataset contains 45 decisions and 607 legal candidate
actions from one completed game, with zero rejected decisions. Its terminal
team reward applies only to the action actually submitted; unchosen candidates
remain unlabeled rather than being treated as wins or losses.

The first five-game collection batch then completed with 3 wins, 2 losses, and
a total leaderboard Elo delta of +13. All 124 decisions used exhaustive oracle
candidates and all integrity counters remained zero. Combining this batch with
the candidate smoke produced the first website-domain dataset snapshot:

- 6 completed verified-bot games;
- 169 submitted decision samples;
- 2,472 legal physical candidate actions;
- mean 14.63 and maximum 373 candidates per decision;
- zero rejected games or decisions.

A second ten-game collection batch completed with 3 wins and 7 losses. Its 261
decisions all passed exhaustive Shadow validation. The cumulative website data
snapshot now contains:

- 16 verified-bot games, 7 wins and 9 losses;
- 430 submitted decision samples;
- 10,082 legal candidate actions;
- zero rejected games, decisions, or integrity errors.

The first website-domain Q-training smoke initialized the existing compatible
DanZero 513+54 network and split validation by whole game rather than by
decision. With only 16 games it overfit quickly: epoch 1 was the best validation
checkpoint, while later training accuracy rose without validation improvement.
A two-game paired Arena compatibility smoke completed with all integrity
counters zero but 0 model wins. This is a pipeline validation only; the model
is not eligible for Shadow recommendations or website control. More independent
website games are required before the next training comparison.

After adopting the mandatory website-domain protocol, the 16-game snapshot was
rebuilt with provisional session-level isolation. The three collection sessions
currently map to 1 train game, 5 development games, and 10 locked-test games.
This is intentionally unsuitable for capability training and its coverage gate
is false. The audit nevertheless confirms all four first-player seats, nine
observed level ranks, 62 wildcard-available decisions, 153 bomb-available
states, two Elo bands, and a zero duplicate-state rate. Future collection must
improve independent train-session and level/Elo coverage before a split is
frozen; increasing epochs is explicitly disallowed as a substitute.

## Frozen 50-Game Dataset

Additional independent collection sessions brought the snapshot to 50 verified-
bot games. The coverage gate passed with 28 wins, 22 losses, 1,294 decisions,
35,231 candidate actions, all four first-player positions, all 13 level ranks,
two Elo bands, and zero duplicate states or integrity errors.

The temporal session split is frozen at 31 train, 10 development, and 9 locked-
test games. Locked-test samples are physically isolated from the train/dev file;
formal training refuses a bundle that contains them. The immutable manifest
content hash is recorded in `docs/research/website-dataset-card-050.md`.

Five-epoch behavior-Q diagnostics from an old DanZero initialization and from
scratch both completed without loading locked test. Their development metrics
are not policy evidence. No model was promoted, no candidate ranking claim was
made, and additional epochs were rejected in favor of information-set rollout
teacher work.
