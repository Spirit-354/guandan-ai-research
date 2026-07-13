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
- Collect new independent website Shadow states first.

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

Name: Website Shadow Supplement v1.

Purpose:

- Increase independent information-set-consistent train/development website
  states.
- Improve level, lead/follow, Elo-band, and endgame coverage.
- Enable more robust teacher candidate screening.

Acceptance:

- 8 completed bot-only baseline games.
- Model-controlled website actions: 0.
- Non-bot table stop before first action.
- Leaderboard Elo recorded before and after.
- New frozen extension passes manifest and coverage checks.

