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

## Frozen Dataset Extension v1

The baseline-only supplement completed five train games and three development
games. All eight were verified bot tables, all 179 submitted actions succeeded,
and all Shadow safety counters remained zero. The four wins and four losses
moved leaderboard Elo from 2070 to 2060; every before/after measurement came
from `leaderboard_elo`.

Dataset construction now supports explicit extension of a frozen manifest. Old
session assignments and game splits must remain unchanged, every new session
must be assigned before collection, new sessions may enter only train or
development, and the locked game set must remain exactly equal to the base
manifest. The base manifest content hash is verified before extension. An
extension cannot be frozen until at least 500 consistent train/development
decisions exist; physically excluded legacy states no longer depress this gate.

Extension v1 preserves every original session assignment and the exact
nine-game locked-test set. New games 13956-13960 are train and 13961-13963 are
development. The physical train/development partition now contains 602
information-set-consistent decisions across 49 independent games: 438 train,
164 development, 88 lead, 514 follow, 212 wildcard, 351 endgame, and 375
bomb-candidate states. It covers all levels and all first-player seats, both
observed Elo bands, and has zero duplicate states. The 500-decision gate and
600-decision target both pass. The extension manifest content hash is
`db209561f6961b289dda668861687fcd7a258a2f283cecaae065501b2006f429`.

## High-Confidence Teacher Dataset Gate

Another exact-tempo profile found that large hands spent most decision time
enumerating bombs for a two-hand finish that was mathematically impossible. In
a two-deck game, one legal play contains at most ten cards; therefore a hand
larger than twenty cannot be cleared by one bomb plus one remaining legal play.
The arena-only optimizer now skips that unreachable search. The slow reference
state fell from about 19.5 seconds to 2.5 seconds, and a fresh 200-state
comparison against the unmodified baseline again produced zero mismatches.

With that optimization, game 13872 turn 4 completed all 64 requested
counterfactual rollouts in about 25.2 minutes. Playing the four-card bomb instead
of the behavior single produced mean team return 0.875 versus -0.25. The paired
advantage was 1.125, its 95% lower bound was 0.623, candidate return variance was
0.25, and greedy/tempo continuation advantages were 1.0/1.25. No hidden or
future information was used. Smoke runs below 16 paired rollouts are now
explicitly forbidden from producing strong teacher labels.

A dedicated 513-state/54-action website teacher builder recovers each selected
physical action from the original frozen train sample instead of treating the
375 compatibility action ID as the paper action. It accepts only complete,
stable-seed, greedy-plus-tempo rollout files and verifies state identity, hand
subset, legal action membership, and train-only provenance.

The final low-variance confirmation sweep produced five more independent strong
labels. Games 13865 turn 8 and 13871 turn 9 replace a pass or a small-joker pair
with a four-card bomb; game 13882 turn 10 replaces a three-with-pair with a
six-card bomb; game 13861 turn 10 replaces a single with a steel; and game 13879
turn 6 chooses a different three-with-pair. Their paired advantages range from
0.5 to 0.875, every greedy and frozen-tempo continuation advantage is positive,
and every 95% advantage lower bound is above zero.

The sweep also supplied useful rejections. Game 13881 turn 7 retained positive
mean advantage but had a negative 95% lower bound. Games 13864 and 13883 were not
robust across continuation profiles, game 13866 had no behavior advantage, and
games 13862, 13877, 13884, and 13885 failed advantage, variance, confidence, or
robustness gates. The six-case final independent batch required about 20.6
minutes; game 13877 alone used about 13.7 minutes and still produced no label.
This supports collecting new independent states instead of repeatedly expanding
rollouts on the exhausted old candidate pool.

The rebuilt teacher dataset contains seven accepted labels from seven independent
games, with no rejection during source remapping, no locked-test access, and the
expected 513-state/54-action representation. Its training gate remains false
until at least 20 independent high-confidence teacher games exist, so no model
training follows.

## Extension v1 Teacher Expansion

The extension v1 physical train/development partition was the only dataset
loaded for candidate selection and rollout. Its SHA-256 is
`9fb93a87f625230638ee0beeac32a1edfb2ca3d9718aa514a972c683a189d6b0`, it
reports `partition_role=train_development`, and it contains no locked-test
samples. The complete bundle and isolated locked-test partition were not read.

New train games 13956-13960 contain 119 decisions. Sixteen decisions were
ineligible because at least one public hand count was zero; all remaining 103
were screened. New development games 13961-13963 remained held out from teacher
label creation. Greedy-only screening covered 339 candidates with 2,712/2,712
completed rollouts. Those results were used only to select confirmation cases
and were never permitted to emit strong labels.

The confirmation sweep evaluated 12 cases and 47 candidates with 752/752
completed paired rollouts, evenly divided between greedy and frozen-tempo
continuations. Every run used uniform physical assignment conditioned on public
counts and the stable game/turn/determinization seed scheme. There were no
timeouts, integrity failures, hidden-hand or future-information accesses, or
accepted incomplete files.

Four new cases passed every frozen gate. Games 13958 turn 12, 13959 turn 7,
13957 turn 14, and 13960 turn 15 had paired advantages of 0.875, 0.875, 0.875,
and 0.625. Their 95% lower bounds were 0.373, 0.258, 0.373, and 0.156; candidate
return variances were 0.467, 0.25, 0.467, and 0.467. Greedy/frozen-tempo
advantages were respectively 1.0/0.75, 1.5/0.25, 1.0/0.75, and 0.75/0.5.
Other high greedy signals were rejected when frozen-tempo advantage was zero or
negative, confidence was not positive, or candidate variance exceeded 0.50.
Game 13956 produced no confirmation-worthy strong signal.

The teacher builder now supports appending to a validated frozen teacher base.
It verifies that every frozen sample still maps to an unchanged train source
state before preserving it, and it applies the existing source, legality,
physical-card, completeness, stable-seed, variance, advantage, confidence, and
continuation robustness checks to every new label. An end-to-end test covers a
frozen old label plus a newly accepted label.

`website_information_set_teacher_dataset_v2.pth` preserves the seven v1 samples
exactly after deserialization and appends only the four accepted extension
labels. The artifact audit found zero state, behavior-action, legal-action, or
physical remap errors. It contains 11 labels from 11 independent train games,
uses the expected 513/54 representation, and has SHA-256
`620b378675ef1964f16043c7c2cdd4d75dc8db3bb7377cab773c3bbe8aec250f`.
The 20-game training gate therefore remains closed, no model was trained, and
the next stage is baseline-only collection of 12 new explicitly assigned train
games rather than threshold relaxation or further search over exhausted
low-evidence states.

## Website Shadow Supplement v2

Before collection, `logs_website_shadow_supplement_train_002` was assigned to
train in a cumulative v2 session-split file. Both v1 supplement assignments were
preserved exactly and no session was assigned to locked test. The target
directory was verified unused, and runtime credentials were loaded only from
the user-level process environment without displaying their values.

Frozen `tempo_baseline` then completed exactly 12 verified bot-table games. The
session produced 8 wins and 4 losses, moving leaderboard Elo continuously from
2060 to 2102 for a net change of +42. Per-game deltas were -17, +14, +14, +14,
-17, +13, -16, +13, -17, +14, +14, and +13. Every measurement came from
`leaderboard_elo`; final-state scores remained proxy-only.

The 12 games contain 280 submitted decisions. Every submission succeeded,
every decision recorded an exhaustive website-oracle candidate set, and every
decision-time information set was consistent. All tables used the verified
four-bot signature. Model-controlled actions, failed games, state encoding,
team mapping, hand-subset, local-legality, oracle-disagreement,
materialization, website-rule, inferred-acceptance, wildcard, information-set,
duplicate-submit, and unrecoverable-desync counts were all zero. Strategy
failure tags such as missed blocks remain research diagnostics and are not
communication or integrity failures; the formal online Shadow gate passed.

A targeted scan found zero runtime credential occurrences in the new session
logs, Shadow summary, global research results, preassignment, or tracked stage
files. This stage did not rebuild a dataset, run teacher rollout, train a model,
or allow model-controlled website play. The next stage is limited to rebuilding
new extension v2 artifacts while preserving every extension v1 assignment and
the exact nine-game locked-test set.

## Frozen Dataset Extension v2

The extension v1 manifest content hash was verified as
`db209561f6961b289dda668861687fcd7a258a2f283cecaae065501b2006f429`
before construction. Its 58 game IDs, split lists, 12 session assignments, 58
source paths and source hashes, and five artifact SHA-256 values were recorded.
No extension v2 output existed before the build.

The builder used extension v1 as its frozen manifest base and added only
`logs_website_shadow_supplement_train_002` through the cumulative v2 assignment
file. It accepted all 70 source games and rejected none. The new bundle contains
40 wins, 30 losses, 1,753 decisions, and 49,549 legal candidates. Every game is
bot verified, every metric source is `leaderboard_elo`, and the
model-controlled action count is zero.

Independent manifest comparison found zero removed old games, old split
changes, old session changes, old source-hash changes, or locked-test set
changes. The 12 added game IDs exactly match the new session logs and all 12
entered train; none entered development or locked test. Comparing serialized
samples found all 1,473 old samples unchanged except for the expected v2 split
manifest hash field. All 280 new samples are consistent train samples from the
new session.

The physical train/development partition now contains 882 consistent decisions
across 61 games: 718 train and 164 development, with 37,452 legal candidates.
It includes 141 lead, 741 follow, 659 level-card, 278 wildcard, 619 endgame, and
500 bomb-candidate decisions. All 13 level values and all four first-player
seats remain covered across the 1900-1999 and 2000-2099 Elo bands, and duplicate
state count remains zero. The isolated locked-test partition remains the same
nine games with 90 consistent decisions.

The dataset coverage, information-set rollout, and threshold gates all pass.
Capability evidence remains ineligible, and no website play, teacher rollout,
model training, or locked-test candidate use occurred. The extension v2
manifest content hash is
`31c5bc501286ac41d3a791811c7089200e49097132bfd886aa10d281c5ddb27e`.
The next stage may read only the v2 physical train/development partition and
screen the 280 new train decisions for robust teacher candidates.

The frozen artifact SHA-256 audit is:

- extension v1 bundle:
  `2b442112a494cd68dc919d372784aeaf9d9c3692747bc6750d11f622c7d6f7d1`;
- extension v1 train/development partition:
  `9fb93a87f625230638ee0beeac32a1edfb2ca3d9718aa514a972c683a189d6b0`;
- extension v1 locked-test partition:
  `e1a769328fbf8ec86600c833126f0342468a537be908863df0edbbf2d00145f0`;
- extension v1 manifest file:
  `1794483391ad9c8e223bc9f44e27e601d65d434e18f01902b017ba34e6f0b90f`;
- extension v1 data card:
  `436436f4c6d9ab27eab86c6a8b3ad899ff28b1942d3f2b81154fa13916fe14d3`;
- extension v2 bundle:
  `15751388b891cbc9985f21418130fad626bfaefcc7f1fd3cf0b210af2342aaeb`;
- extension v2 train/development partition:
  `03d1a0967429fd75433ea3753a96c4bce43660f636a7cf9801140bd02777cc60`;
- extension v2 locked-test partition:
  `b53605e702b09c8ef8b750740ddedf9c64fc150daa9a1477d9fdadbe1a61da47`;
- extension v2 manifest file:
  `72841302506d427fdbb1c18a4fefd82b4b0615661e9a843022d11c4fd61214e3`;
- extension v2 data card:
  `8c866a690ed4012124caacece00b8c493e563ef31ac363eaecc73a74da11e601`.
