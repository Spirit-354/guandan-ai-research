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

## Information-Set Audit

The website caps public action history near 40 entries. The original 513 encoder
therefore produced impossible unknown-card pools after the cap: only 513/1,294
frozen decisions preserved card-count consistency. The earlier behavior-Q
checkpoints are invalidated and must not be reused.

Formal physical partitions now contain only consistent states: 423 train/dev
and 90 locked-test decisions. A cumulative rolling-window overlap tracker was
added for future online Shadow collection. A separate 30-decision live
engineering smoke accumulated 111 public actions and kept all 30 information
sets consistent with zero Shadow errors; it is not added to the frozen dataset.

Information-set determinization was validated on 50 train states with eight
seeds each: 400/400 restores preserved all 108 physical cards and re-encoded the
original 513-vector exactly. Rollout remains restricted to states where nobody
has finished; ranking and partner-wind states await separate state-machine
coverage.

A first stratified teacher feasibility run evaluated 10 games, 31 candidates,
and 496 paired greedy-continuation rollouts. All reached legal terminal states,
but no comparison met the frozen advantage, variance, and confidence criteria.
No teacher label was produced and no model training followed.

After impossible history-capped states were removed, the corrected behavior-Q
diagnostic used 319 train and 104 development decisions while loading zero
locked-test samples. Scratch initialization reached development MSE about 0.982
and sign accuracy about 58.7%. Old-v5 initialization reached best-loss MSE about
1.800 and sign accuracy about 45.2%. These metrics only compare initialization
for `Q(s,a_behavior)`; neither checkpoint is a policy candidate.

A continuation-policy robustness probe then combined deterministic greedy and
frozen tempo policies on four distinct games. All 72 paired rollouts reached a
legal terminal state with no hidden-hand or future-information access. No
candidate robustly beat the behavior action across both policies, so again no
teacher label was emitted. The probe took about 8.9 minutes (roughly 7.4 seconds
per rollout); broader search requires disagreement-state filtering and caching,
not a blind multiplication of rollouts.

## Stable Information-Set Teacher Screening

The rollout seed originally depended on a case's position in the command. That
made the same state draw different hidden-card assignments when evaluated alone
or in a batch. Seeds now derive from `game_id`, `turn_index`, and the
determinization index. Multiple continuation profiles also receive the same
hidden assignment, separating continuation-policy effects from hidden-card
sampling effects.

Risk-priority screening now covers all 319 consistent train states. The first
93 states completed 4,960 greedy rollouts and the remaining 226 completed 5,872;
all rollouts reached legal terminal states with no integrity failure. Greedy-only
signals were treated as screening results, not teacher labels. Multi-policy
confirmation rejected apparent improvements from game 13880 because the frozen
tempo continuation did not support them.

One independent game currently supplies a stable strong teacher case. At game
13868 turn 10, playing the available five-card bomb instead of passing produced
mean team return 0.90625 versus 0.34375 over 64 paired evaluations. Candidate
return variance was 0.1815, paired advantage was 0.5625 with 95% lower bound
0.3239, and greedy/tempo continuation advantages were 0.625/0.5. Nearby turn 9
was rejected because its greedy advantage was below the frozen threshold. This
is not enough independent evidence to train or promote a model.

A three-case tempo confirmation batch exceeded 30 minutes and was terminated;
no partial result was accepted. Rollout evaluation now supports an optional
per-case time budget so one expensive state cannot invalidate a whole batch.

## Exact-Tempo Rollout Performance Audit

An optional frozen-tempo action cache now keys the complete visible state
returned by `offline_arena_state_for_player`, including public history and
ranking. A 200-state cache materialization check reproduced the uncached cards,
action type, and pass decision with zero mismatches. The cache is not a general
speed solution: a real case-13872 probe produced only 3 hits across 530 baseline
decisions (0.57%). Hidden hands are not included in the key or timing samples.

Profiling isolated two offline-only combinatorial costs. The original exact
remaining-group recursion consumed about 106 of 107 profiled seconds on one
small-hand decision. A bitmask dynamic program returned the same exact group
count and reduced the same unprofiled decision from about 62.4 seconds to 0.90
seconds. Large-hand legal-play enumeration also repeated equivalent combinations
because the two decks contain duplicate physical card codes; the arena-only
enumerator now visits each distinct physical multiset once while preserving the
original recognition and ranking rules.

The first post-DP case-13872 probe improved from 4/64 completed rollouts (6.25%)
to 14/64 (21.88%) within the same 180-second case budget, but it still timed out
and emitted no teacher label. This is engineering progress, not a completed
teacher comparison. Exact frozen-tempo continuation remains reserved for narrow
confirmation until the final equivalence gate and throughput probes pass; broad
screening continues to use the already validated cheaper continuation policy.

The final arena-only optimizer passed a 200-state comparison against the
unmodified baseline with zero card, action-type, or pass mismatches. A smaller
case-13872 throughput probe then completed 7/8 requested rollouts (87.5%) before
the same 180-second deadline. Its complete-visible-state cache hit rate was only
0.78%. Because the case was incomplete, the partial comparison is rejected and
cannot emit a strong teacher label. The optimizer is semantically gated, but
full-tempo counterfactual search remains too slow for broad dataset generation.

## Frozen Dataset Extension Plan

The physically isolated train/development partition currently contains 423
information-set-consistent decisions: 319 train and 104 development. It covers
53 lead and 370 follow decisions, only 11 level-6 decisions, and Elo bands
1900-1999 and 2000-2099. The 500-decision information-set rollout gate therefore
remains closed even though the original broad 50-game coverage gate passed.

Dataset construction now supports explicit extension of a frozen manifest. Old
session assignments and game splits must remain unchanged, every new session
must be assigned before collection, new sessions may enter only train or
development, and the locked game set must remain exactly equal to the base
manifest. The base manifest content hash is verified before extension. An
extension cannot be frozen until at least 500 consistent train/development
decisions exist; physically excluded legacy states no longer depress this gate.

Supplement plan v1 assigns a five-game train session and a three-game
development session, targeting at least 600 consistent train/development
decisions. No website game was started while preparing this plan because the
credential environment variables were not present in the running process.
