# EXPERIMENTS.md

## Experiment Ledger

This file summarizes results that affect current decisions. Full raw artifacts
remain in the workspace but are not the primary handoff surface.

## Frozen Baseline and Website Shadow

Status: active baseline, not replaced.

Evidence:

- `tempo_baseline` remains the strongest and safest website submitter.
- Earlier experimental profiles did not consistently outperform it.
- Website Shadow data collection uses `tempo_baseline` only.

Decision:

- Do not make any learned model the default website strategy.
- Do not modify `tempo_baseline` core logic.

## Website Dataset 050

Status: frozen.

Evidence:

- 50 bot-only baseline website games.
- 28 wins, 22 losses.
- 1,294 decisions and 35,231 candidates.
- Split manifest hash:
  `83a58a43ea91f5662e2588494d7bad1b3d9d18de51c30216e5be0e589e0437e4`.
- 423 physically consistent train/development decisions.

Decision:

- Keep the old split frozen.
- Extend with explicitly assigned new sessions only.
- Do not inspect or use locked test for candidate design.

## Website Information-Set Teacher Labels

Status: promising but below training gate.

Accepted strong labels:

- 7 independent strong teacher labels.
- Current teacher dataset: `website_information_set_teacher_dataset_v1.pth`.
- State/action representation: 513/54.

Rejected or exhausted evidence:

- Several old candidates had positive mean advantage but failed confidence,
  variance, or continuation-robustness gates.
- The old 50-game candidate pool is mostly exhausted.

Decision:

- Do not train from the 7-label teacher dataset as a capability candidate.
- Screen only the new extension v1 train/development states next.

## Website Shadow Supplement v1

Status: completed; baseline-only gate passed.

Evidence:

- Five train-session and three development-session games completed.
- All eight games were verified bot tables and used `tempo_baseline` as the
  only submission policy.
- The sessions contain 179 exhaustive Shadow decisions: 119 train and 60
  development.
- All 179 submit results succeeded.
- Four wins and four losses moved leaderboard Elo from 2070 to 2060, a net
  change of -10.
- Model control, communication failure, state encoding, team mapping, hand
  subset, local legality, oracle disagreement, materialization, website-rule,
  wildcard, information-set, duplicate-submit, and unrecoverable-desync counts
  are all zero.
- Runtime credential values were redacted from the new logs and global research
  results before the extension was rebuilt; the final logs, datasets, curated
  evidence, source changes, and handoff files contain neither value.

Decision:

- Accept all eight games into the explicitly assigned extension sessions.
- Do not infer Elo from `final_state["scores"]`; the supplement metric source is
  `leaderboard_elo` for all eight games.

## Website Dataset Extension v1

Status: frozen; coverage gate passed.

Evidence:

- 58 accepted bot-only games, 1,473 decisions, and 42,919 legal candidates.
- The original 50-game split, every old session assignment, and the nine-game
  locked-test set are unchanged.
- New games 13956-13960 are train; 13961-13963 are development; locked test has
  no new game.
- The information-set-consistent train/development partition contains 602
  decisions across 49 independent games: 438 train and 164 development.
- It contains 88 lead, 514 follow, 471 level-card, 212 wildcard, 351 endgame,
  and 375 bomb-candidate states, with all levels and all first-player seats
  represented.
- Elo-band coverage is 174 decisions in `1900-1999` and 428 in `2000-2099`;
  duplicate state count is zero.
- Extension manifest hash:
  `db209561f6961b289dda668861687fcd7a258a2f283cecaae065501b2006f429`.

Decision:

- Freeze extension v1 and use only its physical train/development partition
  for the next teacher-candidate stage.
- Keep the complete bundle and locked-test partition out of candidate design,
  rollout selection, and threshold tuning.

## Model A / Shared Self-Play / BC / PPO / DMC

Status: not eligible for website control.

Observed pattern:

- Legality and physical action materialization were stabilized.
- Pure self-play, behavior cloning, balanced BC, PPO, safe PPO, corrective BC,
  rollout distillation, and early DMC/hybrid variants did not reliably exceed
  `tempo_baseline`.

Decision:

- Do not continue scaling these routes mechanically.
- Use findings as infrastructure and negative evidence.
- Focus current work on website-domain data and robust information-set labels.

## DMC Hybrid Override Experiments

Status: paused.

Evidence:

- Some whitelist/control-pass variants showed limited offline signals, but they
  are not website-domain verified.
- Offline override counts were too small or too unstable to justify website
  takeover.

Decision:

- Keep as analysis evidence only.
- Do not promote to website control.

## Current Next Experiment

Name: Extension v1 information-set teacher candidate expansion.

Purpose:

- Screen only newly collected train/development states for robust
  counterfactual teacher labels.
- Use legal information-set determinization and both greedy and frozen-tempo
  continuation checks.
- Determine whether the teacher dataset reaches 20 independent
  high-confidence games.

Acceptance:

- No website play and no locked-test access.
- No hidden or future information is used.
- Every accepted label records rollout count, sampling method, return mean and
  variance, advantage, confidence, and continuation-profile robustness.
- Teacher label remap errors: 0.
- If fewer than 20 independent high-confidence teacher games exist, do not
  train a model.
