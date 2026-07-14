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

## Extension v2 Teacher Expansion

The extension v2 physical train/development partition was the only dataset
loaded for selection and rollout. Its SHA-256 remained
`03d1a0967429fd75433ea3753a96c4bce43660f636a7cf9801140bd02777cc60`;
the complete bundle and isolated locked-test partition were not read.

All 280 decisions from new train games 13985, 13986, 13987, 13989, 13991,
13992, 13994, 13996, 13997, 13999, 14000, and 14002 were enumerated. Thirty-one
were ineligible because at least one public hand count was nonpositive. The
remaining 249 states all completed greedy-only screening: 720 candidates and
5,760/5,760 rollouts, with zero timeout or integrity failure. Screening emitted
no strong labels.

Twelve positive-95%-lower-bound screen signals covered six independent games.
The strongest signal per game was confirmed first, followed only by the two
remaining positive-screen alternatives for failed games. Across the two
confirmation batches, eight cases and 32 candidates completed 512/512 paired
rollouts, evenly divided between greedy and frozen-tempo continuations. Every
run used uniform physical information-set assignment, stable game/turn/seed
determinizations shared across profiles, and no hidden-hand or future
information. Locked-test loads, incomplete accepted files, timeouts, and
integrity failures remained zero.

Two cases passed every frozen gate. Games 13992 turn 16 and 14000 turn 5 each
had paired advantage 0.875, 95% lower bound 0.373, candidate return variance
0.0, and greedy/frozen-tempo advantages 1.0/0.75. The two game-13986 candidates
were rejected for variance above 0.50. The candidates from games 13987, 13991,
and 14002 failed confidence or continuation robustness, and no other game had a
remaining positive-screen alternative.

`website_information_set_teacher_dataset_v3.pth` preserves all 11 teacher v2
samples exactly after deserialization and appends only `13992:16` and
`14000:5`. Source states, behavior actions, legal teacher actions, physical-card
mapping, and 513-state/54-action dimensions all passed. Its SHA-256 is
`901ebe397d4fea8842e439e80cd0dfa7605985133ab01b5172bac4708a1a75b1`.
The dataset contains 13 labels from 13 independent games, so the 20-game gate
remains closed. This stage ran no website games, model training, offline
evaluation, or model-controlled website play.

## Website Shadow Supplement v3

Before collection, a cumulative v3 assignment file preserved all three prior
session assignments and added only `logs_website_shadow_supplement_train_003`
as train. The new directory was unused, and no session was assigned to locked
test. Frozen extension v2, teacher v3, and `tempo_baseline` hashes passed their
preflight checks.

Frozen `tempo_baseline` then completed exactly 12 verified bot-table games:
games 14018, 14019, 14020, 14021, 14022, 14023, 14025, 14026, 14027, 14029,
14030, and 14031. Results were 9 wins and 3 losses. Leaderboard Elo was
continuous across every boundary, moving from 2102 to 2158 for a net change of
+56. Every before/after value came from `leaderboard_elo`; final-state scores
remained proxy-only.

The session contains 308 submitted decisions and 8,322 legal candidates. All
308 submissions succeeded, all 308 candidate sets were generated through
exhaustive website-oracle validation, and all 308 decision-time information
sets were consistent. Every table had the verified four-bot signature, every
action came from `tempo_baseline`, and model-controlled actions were zero.

The online Shadow gate passed. Failed games, non-bot actions, state encoding,
team mapping, hand subset, local legality, oracle disagreement,
materialization, website-rule, inferred acceptance, wildcard, information-set,
duplicate-turn, extra error-log, and unrecoverable-desync counts were zero. A
targeted scan of the new logs, summary, assignment, global research results,
and tracked files found zero runtime credential occurrences.

This stage did not rebuild a dataset, run teacher rollout, train a model, run
offline evaluation, or allow model-controlled website play. The next stage is
limited to constructing extension v3 artifacts from frozen extension v2 plus
this preassigned train session.

## Frozen Dataset Extension v3

The extension v2 manifest content hash and all five v2 artifact hashes were
verified before construction. Its 70 game IDs, split lists, 13 session
assignments, 70 source paths and hashes, and nine-game locked-test set were
recorded. None of the five v3 outputs existed before the build.

The builder used extension v2 as its frozen manifest base and added only
`logs_website_shadow_supplement_train_003` through the cumulative v3 assignment
file. It accepted all 82 source games and rejected none. The new bundle contains
49 wins, 33 losses, 2,061 decisions, and 57,871 legal candidates. Every game is
bot verified, every metric source is `leaderboard_elo`, and the
model-controlled action count is zero.

Independent manifest comparison found zero removed old games, source-hash
changes, old session changes, old split changes, or locked-test membership
changes. The 12 added game IDs exactly match Supplement v3 and all entered
train; none entered development or locked test. Comparing serialized samples
found all 1,753 old samples unchanged except for the expected v3 split manifest
hash field. All 308 new samples are consistent train samples.

The physical train/development partition contains 1,190 consistent decisions
across 73 games: 1,026 train and 164 development, with 45,774 legal candidates.
It includes 193 lead, 997 follow, 807 level-card, 331 wildcard, 891 endgame, and
606 bomb-candidate decisions. All 13 levels and all four first-player seats are
covered across the 1900-1999, 2000-2099, and 2100-2199 Elo bands, and duplicate
state count remains zero. The isolated locked-test partition remains the same
nine games and 90 consistent decisions.

Coverage, information-set rollout, and threshold gates all pass. Capability
evidence remains ineligible, and this stage ran no website play, teacher
rollout, model training, offline evaluation, or model-controlled website play.
The extension v3 manifest content hash is
`51fe0244407d67e8267ea11b7146ff214f73823c29db92062189a58d033e5af9`.

The frozen v3 artifact SHA-256 audit is:

- bundle: `0235f53f7aec87cd3f7c62a529fd2d05af899a7befa72280fe4d5da234b4ac81`;
- train/development partition:
  `e5edc7090657ac1c4b4a2b2a14f38ad9bb0145ba1c19b6e85fca20bb1b5a687a`;
- locked-test partition:
  `941c66107e93aaa5d26965aa4b3a26fee0e0fab70f73ed489d6c49eaf3d60e59`;
- manifest file:
  `c91cb7665e9fcca68ee0161582a2794701057611a71485527f7ab8fcf97ecc83`;
- data card:
  `f8eedcec8fa6679760e5bf4e202bef19bd07ee681b040f68168b22ce8b01c177`.

The next stage may read only the v3 physical train/development partition and
screen the 308 new train decisions for robust teacher candidates.

## Extension v3 Teacher Expansion

The v3 physical train/development partition was the only dataset loaded for
selection and rollout. Its SHA-256 remained
`e5edc7090657ac1c4b4a2b2a14f38ad9bb0145ba1c19b6e85fca20bb1b5a687a`;
the complete bundle and isolated locked-test partition were not read.

All 308 decisions from new train games 14018, 14019, 14020, 14021, 14022,
14023, 14025, 14026, 14027, 14029, 14030, and 14031 were enumerated. Sixty-one
were ineligible because at least one public hand count was nonpositive. The
remaining 247 states all completed greedy-only screening: 695 candidates and
5,560/5,560 rollouts, with zero timeout or integrity failure. Screening emitted
no strong labels.

The frozen eligibility audit by game, shown as eligible/ineligible, was:
`14018` 18/0, `14019` 10/14, `14020` 19/17, `14021` 23/2, `14022` 18/0,
`14023` 20/0, `14025` 22/0, `14026` 27/7, `14027` 20/2, `14029` 26/9,
`14030` 25/10, and `14031` 19/0. Every one of the 61 exclusions had the same
frozen reason: a nonpositive public hand count.

Ten positive-95%-lower-bound, low-variance screen signals covered five
independent games. The strongest signal per game was confirmed first. For the
two failed games, 14020 had no remaining permitted signal and only `14021:10`
remained for 14021. Across the two confirmation batches, six cases and 23
candidates completed 368/368 rollouts, evenly divided between greedy and
frozen-tempo continuations. Every run used uniform physical information-set
assignment, stable game/turn/seed determinizations shared across profiles, and
no hidden-hand or future information. Locked-test loads, incomplete accepted
files, timeouts, and integrity failures remained zero.

Three cases passed every frozen gate:

- `14022:16`: advantage 0.875, 95% lower bound 0.373, candidate variance 0.0,
  and greedy/frozen-tempo advantages 1.25/0.50;
- `14025:20`: advantage 1.0, 95% lower bound 0.494, candidate variance 0.0,
  and greedy/frozen-tempo advantages 1.0/1.0;
- `14031:4`: advantage 0.625, 95% lower bound 0.156, candidate variance 0.25,
  and greedy/frozen-tempo advantages 0.75/0.50.

`14020:7` and `14021:2` were rejected for candidate variance above 0.50.
`14021:10` was rejected because its 95% lower bound was negative. No failed
game retained another permitted positive-screen alternative.

`website_information_set_teacher_dataset_v4.pth` preserves all 13 teacher v3
samples exactly after deserialization and appends only the three accepted
labels. Source states, behavior actions, legal teacher actions, physical-card
mapping, and 513-state/54-action dimensions all passed. Its SHA-256 is
`fa193705777987d0bad91f9a45f5aa956a02e22ffa077a04bc2c81892aeb5f99`;
teacher v3 remained unchanged at
`901ebe397d4fea8842e439e80cd0dfa7605985133ab01b5172bac4708a1a75b1`.

Teacher v4 contains 16 labels from 16 independent games, so the 20-game gate
remains closed. This stage ran no website games, model training, offline
evaluation, or model-controlled website play. The next stage is limited to a
new explicitly preassigned baseline-only 12-game train supplement.

## Website Shadow Supplement v4

Before collection, a cumulative v4 assignment file preserved all four prior
session assignments and added only `logs_website_shadow_supplement_train_004`
as train. The new directory and assignment output were unused before this
preassignment, and no session was assigned to locked test. Frozen extension v3,
teacher v4, and `tempo_baseline` passed their preflight hash or freeze checks.

Frozen `tempo_baseline` then completed exactly 12 verified bot-table games:
games 14035 through 14046. Results were 6 wins and 6 losses. Leaderboard Elo
was continuous across every boundary, moving from 2158 to 2121 for a net change
of -37. Per-game deltas were -19, +12, +12, -18, +12, +11, -18, -18, +12,
-18, -18, and +13. Every before/after value came from `leaderboard_elo`;
final-state scores remained proxy-only.

The session contains 279 submitted decisions and 12,959 legal candidates. All
279 submissions succeeded, all 279 candidate sets were generated through
exhaustive website-oracle validation, and all 279 decision-time information
sets and public histories were consistent. Every table had the verified
four-bot signature, every action came from `tempo_baseline`, and
model-controlled actions and suggestion differences were zero.

The online Shadow gate passed. Failed games, non-bot actions, state encoding,
team mapping, hand subset, local legality, oracle disagreement,
materialization, website-rule, inferred acceptance, wildcard, information-set,
duplicate-submit, extra error-log, and unrecoverable-desync counts were zero. A
targeted scan of the new logs, summary, assignment, global research results,
and tracked files found zero runtime credential occurrences.

This stage did not rebuild a dataset, run teacher rollout, create teacher
labels, train a model, run offline evaluation, or allow model-controlled
website play. The next stage is limited to constructing extension v4 artifacts
from frozen extension v3 plus this preassigned train session.

## Frozen Dataset Extension v4

The extension v3 manifest content hash and all five v3 artifact hashes were
verified before construction. Its 82 game IDs, split lists, 14 session
assignments, 82 source paths and hashes, and nine-game locked-test set were
recorded. None of the five v4 outputs existed before the build. Frozen teacher
v4 also retained its expected SHA-256.

The builder used extension v3 as its frozen manifest base and added only
`logs_website_shadow_supplement_train_004` through the cumulative v4 assignment
file. It accepted all 94 source games and rejected none. The new bundle contains
55 wins, 39 losses, 2,340 decisions, and 70,830 legal candidates. Every game is
bot verified, every metric source is `leaderboard_elo`, and the
model-controlled action count is zero.

Independent manifest comparison found zero removed old games, source-hash
changes, old session changes, old split changes, or locked-test membership
changes. The 12 added game IDs are exactly 14035 through 14046 and all entered
train; none entered development or locked test. Comparing serialized samples
found all 2,061 old samples unchanged except for the expected v4 split manifest
hash field. All 279 new samples are consistent train samples.

The physical train/development partition contains 1,469 consistent decisions
across 85 games: 1,305 train and 164 development, with 58,733 legal candidates.
It includes 245 lead, 1,224 follow, 944 level-card, 406 wildcard, 1,100 endgame,
and 727 bomb-candidate decisions. All 13 levels and all four first-player seats
are covered across the 1900-1999, 2000-2099, and 2100-2199 Elo bands, and
duplicate state count remains zero. The isolated locked-test partition remains
the same nine games and 90 consistent decisions.

Coverage, information-set, physical-isolation, and threshold gates all pass.
Capability evidence remains ineligible. This stage ran no website play, teacher
rollout, teacher-label creation, model training, offline evaluation, or
model-controlled website play. The extension v4 manifest content hash is
`368771a6a647d34d0d6fcd0490d7cdd1e57991a4c4188e3c127780a5323acbec`.

The frozen v4 artifact SHA-256 audit is:

- bundle: `c8c05785defe37e589b99b3071b58c43d20ed1f1cf87fdb3c031a196151dcf87`;
- train/development partition:
  `ad4da83e2af29c580a1b1d8fe70a06f88fc645525ab025945a7be48fd349fde1`;
- locked-test partition:
  `cec1aba85cfbc388345d5ac17fd1ec48ec02642fb5743bed76513f872b7a512d`;
- manifest file:
  `30d8103a156b84b3f1b26a78512b29757a3a603e925e15522752266f426bda04`;
- data card:
  `fdfbe98a17e27e6c6cb20f5d85e6d17c6e775ee758b999aba5294b5a3f3fedee`.

The next stage may read only the v4 physical train/development partition and
screen the 279 new train decisions for robust teacher candidates. Teacher v4
remains the frozen 16-label base, and training remains prohibited even if the
next stage reaches the 20-game gate.

## Extension v4 Teacher Expansion

The v4 physical train/development partition was the only dataset loaded for
selection and rollout. Its SHA-256 remained
`ad4da83e2af29c580a1b1d8fe70a06f88fc645525ab025945a7be48fd349fde1`;
the complete bundle and isolated locked-test partition were not loaded.

All 279 decisions from games 14035 through 14046 were enumerated. Twenty-seven
were ineligible because at least one public hand count was nonpositive. The
remaining 252 states all completed greedy-only screening: 782 candidates and
6,256/6,256 rollouts, with zero timeout or integrity failure. Screening emitted
no strong labels.

The frozen eligibility audit by game, shown as eligible/ineligible, was:
`14035` 19/3, `14036` 15/0, `14037` 20/5, `14038` 18/2, `14039` 12/0,
`14040` 28/0, `14041` 29/4, `14042` 18/7, `14043` 20/0, `14044` 34/5,
`14045` 18/1, and `14046` 21/0. Every one of the 27 exclusions had the same
frozen reason: a nonpositive public hand count.

Eight positive-95%-lower-bound, low-variance screen signals covered six
independent games. The strongest signal per game was confirmed: six cases and
24 candidates completed 384/384 rollouts, evenly divided between greedy and
frozen-tempo continuations. Every run used uniform physical information-set
assignment, stable game/turn/seed determinizations shared across profiles, and
no hidden-hand or future information. Locked-test loads, incomplete accepted
files, timeouts, and integrity failures remained zero.

Three cases passed every frozen gate:

- `14038:12`: advantage 1.125, 95% lower bound 0.623, candidate variance 0.0,
  and greedy/frozen-tempo advantages 1.0/1.25;
- `14044:9`: advantage 0.75, 95% lower bound 0.143, candidate variance 0.467,
  and greedy/frozen-tempo advantages 1.25/0.25;
- `14045:5`: advantage 0.625, 95% lower bound 0.156, candidate variance 0.0,
  and greedy/frozen-tempo advantages 1.0/0.25.

`14036:4` was rejected for candidate variance 0.65, negative confidence lower
bound, and zero frozen-tempo advantage. `14042:9` was rejected for candidate
variance 0.80. `14043:8` was rejected for a negative confidence lower bound and
frozen-tempo advantage -0.25. None of these three games retained another
permitted positive-screen alternative. Game 14044 had additional screen
signals, but its strongest case passed, so no same-game alternative was run.

`website_information_set_teacher_dataset_v5.pth` preserves all 16 teacher v4
samples exactly after deserialization and appends only the three accepted
labels. Source states, behavior actions, legal teacher actions, physical-card
mapping, and 513-state/54-action dimensions all passed. Its SHA-256 is
`155fc348e939490bc036b2b5e3e0993be732b259250cac3d0244e888910fb9da`;
teacher v4 remained unchanged at
`fa193705777987d0bad91f9a45f5aa956a02e22ffa077a04bc2c81892aeb5f99`.

Teacher v5 contains 19 labels from 19 independent games, so the 20-game gate
remains closed. This stage ran no website games, model training, offline
evaluation, or model-controlled website play. The next stage is limited to a
new explicitly preassigned baseline-only 12-game train supplement.

## Website Shadow Supplement v5

Before website play, the cumulative assignment was extended without modifying
any prior entry: `logs_website_shadow_supplement_train_005` was the only new
session and was assigned to train. No session was added to locked test.

Frozen `tempo_baseline` then completed exactly 12 verified bot-table games:
`14058`, `14059`, `14061`, `14063`, `14064`, `14066`, `14068`, `14070`,
`14072`, `14074`, `14077`, and `14081`. The result was 9 wins and 3 losses.
All 345 submissions succeeded, all 345 decisions retained exhaustive
website-oracle candidate sets with 11,587 candidates in total, and every
decision-time information set was consistent.

Model-controlled actions, suggestion differences, non-bot actions, failed
games, and all reported encoding, team-mapping, hand-subset, legality, oracle,
materialization, website-rule, wildcard, information-set, communication,
duplicate-submit, and unrecoverable-desync errors were zero. Elo came only from
the continuous `leaderboard_elo` sequence, moving from 2121 to 2168 for +47;
final-state scores were not treated as Elo.

Extension v4 and teacher v5 remained frozen. No dataset build, teacher rollout
or label creation, training, offline evaluation, or model-controlled website
play occurred. The next stage is limited to building extension v5 from the
frozen v4 manifest and cumulative v5 assignment.

## Website Dataset Extension v5

Extension v5 was built using only the frozen v4 manifest and cumulative v5
session assignment. It accepted all 106 source games and rejected none. The
bundle contains 64 wins, 42 losses, 2,685 decisions, and 82,417 legal
candidates.

Independent manifest and sample comparison found zero removed old games, old
source-hash changes, old session changes, old split changes, or locked-test
membership changes. All 2,340 old samples are unchanged after excluding only
the expected v5 split-manifest reference. The 12 new game IDs are exactly
`14058`, `14059`, `14061`, `14063`, `14064`, `14066`, `14068`, `14070`,
`14072`, `14074`, `14077`, and `14081`; all entered train and contributed 345
consistent samples and 11,587 candidates.

The physical train/development partition contains 1,814 consistent decisions
across 97 games: 1,650 train and 164 development, with 70,320 candidates. It
contains 306 lead, 1,508 follow, 1,118 level-card, 467 wildcard, 1,371 endgame,
and 872 bomb-candidate decisions. All levels and first-player seats remain
covered across the 1900-1999, 2000-2099, and 2100-2199 Elo bands; duplicate
state count is zero. The isolated locked-test partition remains the same nine
games and 90 samples.

Coverage, information-set rollout, physical-isolation, and threshold gates all
pass. This stage ran no website play, teacher rollout or label creation,
training, offline evaluation, or model-controlled website play. The extension
v5 manifest content hash is
`a2931c6078487662d25f115896034311354eade265bec8b72f94ea2d5a7bdaf7`.

The frozen v5 artifact SHA-256 audit is:

- bundle: `c013fe4cc89ef872c246a81ee37f8f6711da85bcf724238c570e703b942f9ee2`;
- train/development:
  `e5e220c3c770116ca9d01478e98e610dd6309a0f3d6c17088a8328f62b47174b`;
- locked-test:
  `3b2e7f1386fc73449178a01631c866a5045f19f9fa3de267794b53a9b9a8fe6c`;
- manifest file:
  `aa417661b7363b13e4a11c34970559339f6a717cb3eb9404c56b1163cc83dc0b`;
- data card:
  `9160f0b1889d8a85899fb3f706da6df78f0ab28c4644c5e2049ad5720346d739`.

The next stage may read only the v5 physical train/development partition and
screen the 345 new train decisions for robust teacher candidates. Teacher v5
remains the frozen 19-label base; training stays prohibited even if the next
stage reaches the 20-game gate.

## Extension v5 Teacher Expansion

The v5 physical train/development partition was the only dataset loaded for
selection and rollout. Its SHA-256 remained
`e5e220c3c770116ca9d01478e98e610dd6309a0f3d6c17088a8328f62b47174b`;
the complete bundle and isolated locked-test partition were not loaded.

All 345 decisions from the 12 new train games were enumerated. Sixty-eight
were ineligible only because at least one public hand count was nonpositive.
The remaining 277 states all completed greedy-only screening: 843 candidates
and 6,744/6,744 rollouts, with zero timeout or integrity failure. Screening
emitted no strong labels.

The frozen audit by game, shown as total/eligible/ineligible, was: `14058`
38/38/0, `14059` 19/19/0, `14061` 28/28/0, `14063` 16/16/0, `14064`
29/21/8, `14066` 49/21/28, `14068` 26/17/9, `14070` 27/22/5, `14072`
31/22/9, `14074` 18/17/1, `14077` 31/29/2, and `14081` 33/27/6.

Six positive-95%-lower-bound, low-variance screen signals covered five
independent games. The strongest signal per game was confirmed: five cases and
20 candidates completed 320/320 rollouts, evenly divided between greedy and
frozen-tempo continuations. Every run used uniform physical information-set
assignment, stable game/turn/seed determinizations shared across profiles, and
no hidden-hand or future information. Locked-test loads, incomplete accepted
files, timeouts, and integrity failures remained zero.

Three cases passed every frozen gate:

- `14058:22`: advantage 0.50, 95% lower bound 0.0617, candidate variance 0.0,
  and greedy/frozen-tempo advantages 0.75/0.25;
- `14074:9`: advantage 1.00, 95% lower bound 0.4939, candidate variance 0.0,
  and greedy/frozen-tempo advantages 1.00/1.00;
- `14077:10`: advantage 0.50, 95% lower bound 0.0617, candidate variance 0.0,
  and greedy/frozen-tempo advantages 0.75/0.25.

`14064:1` was rejected for candidate variance 0.80, a negative confidence lower
bound, and zero frozen-tempo advantage. `14070:1` was rejected for candidate
variance 1.067 and frozen-tempo advantage -0.25. Neither game retained another
permitted positive-screen alternative. The same-game `14074:10` alternative
was not run because the stronger `14074:9` passed.

`website_information_set_teacher_dataset_v6.pth` preserves all 19 teacher v5
samples exactly after deserialization and appends only the three accepted
labels. Source states, behavior actions, legal teacher actions, physical-card
mapping, and 513-state/54-action dimensions all passed. Its SHA-256 is
`a74416e6facb28a1bc64563eba90cb33d460dc9e59cc2109518da142465e15f8`;
teacher v5 remained unchanged at
`155fc348e939490bc036b2b5e3e0993be732b259250cac3d0244e888910fb9da`.

Teacher v6 contains 22 labels from 22 independent games, so the 20-game
label-count gate passes. This stage ran no website games, model training,
offline capability evaluation, or model-controlled website play. The next
stage is limited to a deterministic, complete-game-grouped teacher-preference
training-pipeline smoke; it cannot run Arena or website play, promote a
checkpoint, or make a capability claim.

## Frozen Teacher-Preference Training Smoke

The training-label input was limited to
`website_information_set_teacher_dataset_v6.pth`, whose SHA-256 remained
`a74416e6facb28a1bc64563eba90cb33d460dc9e59cc2109518da142465e15f8`.
All 22 labels from 22 independent games passed the frozen schema, train-only,
513-state, 54-action, legal-action, differing-pair, preference-target,
source-partition, and locked-test checks.

The internal pipeline split sorts complete games by
`sha256("website_teacher_v6_split_v1:" + game_id)`. Games `13992`, `14074`,
`13868`, and `13871` are the four internal pipeline-development games; the
remaining 18 games are pipeline train. Overlap, dropped games, and locked-test
games are zero. The curated split manifest SHA-256 is
`5a15e514dc9bc51d77d300837151d9f1a49250f42885cc7940725bcbe4d35107`.
The curated training report SHA-256 is
`896192b1d0b4de2caabe20ac17d6a20766fc7f89d6e82a981d834b777932ddd3`.

The smoke reused `danzero_dmc.build_q_model` without changing the 513+54 model
or website action semantics. Its fixed recipe was CPU, seed `20260714`, 20
epochs, batch size 6, learning rate 0.001, no initialization checkpoint, and
the sole loss `softplus(Q_behavior-Q_teacher)`. Hyperparameter searches and
checkpoint selections were zero.

Final pipeline-train ranking accuracy was 1.00 with mean
teacher-minus-behavior margin 20.7220. Internal pipeline-development ranking
accuracy was 0.75 with mean margin 12.3318 and pairwise loss 3.3015. These are
pipeline diagnostics from only four internal development pairs and are not
capability evidence.

The final ignored checkpoint SHA-256 is
`c54801a9db05100c2fe5a9bf610a64fc7c94dc2cd947dfaab115ff827bd90919`.
An independent process reloaded it and reproduced both partition metrics and
prediction digests exactly. A temporary full rerun reproduced the split,
recipe, history, metrics, and prediction digests exactly.

Complete-bundle and locked-test loads, extra training targets, Arena games,
website Shadow, website games, model-controlled website actions, checkpoint
promotion, and capability claims were all zero. The next stage is limited to a
20-game paired, seat-swapped offline Arena integrity smoke against frozen
`tempo_baseline`; it cannot continue to the 100/200-game screen or any website
stage in the same Goal.

## Stage 6.1 Teacher-Preference Offline Arena Smoke

All frozen checkpoint, teacher, split, training-report, and baseline-manifest
hashes passed before execution. Baseline freeze verification reported 500
equivalence samples and zero mismatches. The DanZero checkpoint loader was
extended only to accept the frozen teacher-preference schema when its 513/54
dimensions, teacher hash, training mode, capability flag, and promotion flag
match; the legacy distributed-DMC loader remains supported.

The only formal run used CPU, Arena seed `20260714`, frozen
`tempo_baseline`, and 20 games arranged as ten adjacent pairs. Within every
pair, deal, first-player, and Arena RNG seeds matched, while the model played
team 0 once and team 1 once. The compact trace records every seed, first
player, model team, winner, game length, and per-game safety count.

All 20 games completed with zero illegal action, fallback, materialization,
hand-card mismatch, fatal candidate, or baseline-equivalence mismatch. The
engineering integrity gate therefore passed. The model nevertheless lost all
20 games. Model/baseline decisions were 964/873, average game length was 91.85,
model pass rate was 0.6629, and model bomb rate was 0.0239.

The frozen early-screen rule requires integrity plus model win rate at least
0.30. With win rate 0.0, continuation is false. The checkpoint is rejected
from the 100/200-game screen and remains unpromoted; no capability claim is
allowed. Training, tuning, checkpoint selection, website-dataset or locked-test
loads, larger Arena runs, website Shadow/play, and model-controlled website
actions were all zero.

The curated Arena output SHA-256 is
`aa45da9de202194102fe8d11e612ad3eb4b51177fd910b9a7948836afd2a1fe6`.
The next stage is limited to static full-legal-set Q-ranking diagnosis on the
22 frozen teacher states. It cannot retrain or run additional games.

## Stage 6.2 Frozen Teacher-Preference Failure Diagnosis

The static diagnosis loaded only the five frozen checkpoint, teacher v6,
18/4 split, training report, and Stage 6.1 Arena artifacts. Their hashes all
matched before and after execution. No website dataset, locked test, Arena,
training, tuning, website access, promotion, or capability path ran.

All 22 unique teacher states and every one of their 934 recorded legal-action
entries were scored exactly once with the frozen 513+54 Q model. Pipeline
train contained 18 states and 889 actions; pipeline development contained four
states and 45 actions. Eight source entries duplicate another recorded action
vector, so they were preserved and scored separately. Dropped, duplicate-score,
reconstructed, invalid-dimension, illegal-recorded, and nonfinite-Q counts were
zero.

The diagnostic reused the original pairwise batching order for teacher and
behavior, then scored only the remaining legal-action entries. Pipeline-train
pairwise loss, accuracy, mean margin, and prediction digest reproduced exactly
at `0.0000722892`, `1.00`, `20.7220`, and
`951b51bc3000686ecc35260813b8f191246e0df25cd66c2b2b80cbd78b5810cc`.
Pipeline-development values reproduced exactly at `3.3015`, `0.75`, `12.3318`,
and `2a453f34104e5e052e469127ae473fb4cf89c8d71ee35e6bebe12b08cc377fe7`.

Full-set ranking reveals the gap hidden by pairwise metrics. Teacher beat
behavior in 21/22 states but was top-1 in only 10/22. Behavior was never top-1;
another recorded legal action was top-1 in 12/22 states. Those 12 states contain
161 unpaired action entries strictly above teacher. Overall mean teacher rank
was 8.36 and median rank was 2.0. Pass was top-1 in 0/22 states, so this frozen
teacher-state analysis does not directly explain the Arena pass rate of 66.3%.

An independent audit recomputed all per-state ranks, ties, first-maximum
sources, action-order hashes, partition and overall aggregates, pairwise
metrics, and prediction digests with zero errors. The curated output is
`website_teacher_preference_failure_diagnosis_v1.json`, SHA-256
`da08516c39986a01349533e160ba0e97a566d7fad6e42b0b7b3ce41df835b0b2`.

This supports an objective-coverage pattern, not causality: pairwise training
constrains teacher only against behavior and does not establish that teacher is
better than unpaired legal actions. The checkpoint remains rejected from the
100/200-game screen. The next stage may only audit already-frozen source
counterfactual evidence for the 12 unpaired top actions; it cannot run new
rollouts, train, or play games.

## Stage 6.3 Frozen Unpaired-Action Evidence Audit

The static audit retained the six frozen primary hashes and read only the ten
rollout-evidence files referenced directly by the 12 Stage 6.2 target teacher
samples. Every source file was hashed before interpretation. Stage 6.1 remained
0-20 with continuation false, and the checkpoint remained rejected from the
100/200-game screen.

All 12 target state keys, original legal-action orders, teacher/behavior
indices, first-maximum top-1 indices, 54D vectors, and physical-card identities
reproduced exactly. There were nine pipeline-train and three
pipeline-development targets, with zero missing, duplicate, extra,
reconstructed, or ambiguous mappings.

Four model top-1 actions were candidates in complete dual-continuation source
cases: two in pipeline train and two in pipeline development. The remaining
eight actions were present in the exact source legal-action set but had no
qualifying candidate comparison. No case was greedy-only, absent, or
ambiguously mapped.

The four dual-continuation cases do not establish teacher-versus-top1 ordering.
Their source teacher labels compare teacher with behavior; the top-1 candidate
records contain no top1-specific 95% lower bound, confidence, or per-profile
paired advantages. Thus existing evidence supports zero of 12 direct
teacher-versus-top1 orderings and cannot support a teacher-versus-all training
objective.

The output contains a non-executed 12-case future manifest: eight cases require
the top-1 action to be evaluated as a candidate, and four require direct paired
teacher-versus-top1 confidence. Independent recomputation matched all target
and evidence hashes, classifications, 9/3 partition counts, aggregate
arithmetic, and forbidden-operation counters. New rollouts, training, tuning,
checkpoint changes, website-dataset or locked-test loads, Arena, website
access, promotion, and capability claims were all zero.

The curated artifact is
`website_teacher_preference_unpaired_evidence_audit_v1.json`, SHA-256
`09f52df90d095ab6b3777a046c50901f96fbeb15e6ef5f613343a13be1249383`.
Any next counterfactual stage must use only the nine pipeline-train manifest
cases for objective-design evidence. The three pipeline-development cases must
remain held out, and no training, Arena, or website activity may occur in that
same stage.
