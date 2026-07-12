# Website Bot Domain-Adaptation Route

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
