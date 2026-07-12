# Stage 0: Baseline Freeze and Project Audit

## Repository State

Stage 0 started from `agent/dmc-pairwise-ranking` at commit `0f89dd9`.
The working tree was clean and no Python training or arena process was active.

Four draft pull requests were open and all compile checks passed:

- PR 1: paired hybrid override audit, based on `main`
- PR 2: m038 300-game result, based on `main`
- PR 3: DMC Q calibration audit, stacked on PR 1
- PR 4: DMC pairwise ranking pipeline, stacked on PR 3

The branch stack is intentional and preserves the evidence history. Stage 0 is
stacked on PR 4 until the research branches are consolidated.

## Baseline Freeze

`tempo_baseline` is now protected by `research_baseline_manifest.json` and
`tools/verify_baseline_freeze.py`. The verifier checks:

- the complete `play_step_0902.py` SHA-256;
- `recognize`;
- `info_beats`;
- `legal_play_options`;
- `choose_lead_play`;
- `choose_play`;
- the adaptive `choose_profiled_play` wrapper;
- the offline baseline materialization wrapper;
- the canonical `tempo_baseline` profile configuration.

CI compiles the verifier and runs it on every push and pull request. Any change
to the frozen rules, baseline decision functions, or baseline profile fails the
check and requires explicit user approval plus an intentional manifest update.

## Model and Data Inventory

The local workspace contains the historical website logs, imitation datasets,
self-play datasets, DMC datasets, checkpoints, and arena outputs. Important
large assets include:

- balanced DMC self-play dataset: approximately 1.38 GB;
- DMC self-play 10k dataset: approximately 278 MB;
- model/checkpoint directories: approximately 1 GB combined;
- historical website research logs: approximately 20 MB.

All generated JSON, JSONL, model, dataset, log, PDF, and credential files are
ignored by Git. The largest tracked source file is the research driver at less
than 1 MB. No model weight or large dataset is tracked.

## Model Status

`research_model_registry.json` is the machine-readable source of truth.

- Active default: `tempo_baseline`
- Candidates: none
- Offline-only models: none
- Failed: self-play actor, BC, balanced BC, safe PPO, DMC 10k, DMC balanced50k,
  m038 hybrid, and the pairwise DMC smoke
- Archived: all prior heuristic experimental profiles

No learned model is currently authorized for website shadow or direct play.

## Security Audit

The source scan found no hard-coded account, password, token, or private key.
Only documented placeholders such as `GUANDAN_PASSWORD=your_password` were
present. Credentials remain environment-variable only. Local logs and model
artifacts remain ignored.

## Fixed Evaluation Protocol

- local teams are seats 0/2 versus 1/3;
- first player is randomized per game;
- seat swapping is required for arena comparisons;
- website-oracle legal actions are mandatory;
- baseline equivalence is required before formal arena evaluation;
- 20 games are a smoke gate, 100 games a screening gate, 300 games an initial
  success gate, and 1000 games final offline confirmation;
- no proxy score may be written as Elo;
- the first website model-control test requires explicit user confirmation.

## Stage-0 Validation

The final 500-state baseline equivalence run completed in approximately 33
minutes.

- Requested equivalence samples: 500
- Completed equivalence samples: 500
- Baseline equivalence mismatches: 0
- Baseline freeze hash mismatches: 0
- Core script compilation: passed
- Tracked-source secret scan: passed
- Stage-0 threshold: passed

Stage 0 is complete. Stage 1 may add new paper-style state and physical-action
representations, but it must not modify any frozen baseline hash.
