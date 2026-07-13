# GuanDan AI Research

Research code for GuanDan rule validation, offline arena evaluation, imitation
learning, self-play, PPO, rollout teachers, and DMC action-value experiments.

The repository tracks source code and curated experiment notes. Credentials,
raw game logs, datasets, model checkpoints, and generated evaluation output are
kept outside Git because they may contain private data or exceed GitHub limits.

## Safety

Never commit real account credentials. Configure local runs with environment
variables based on `.env.example`:

```powershell
$env:GUANDAN_USER="your_user"
$env:GUANDAN_PASSWORD="your_password"
```

Offline research commands do not require website credentials. The stable
`tempo_baseline` strategy remains unchanged unless a change explicitly targets
that implementation and is separately validated.

## Validation

Compile the core scripts before committing:

```powershell
python -B -m py_compile play_research_adaptive.py play_step_0902.py play_step_09.py danzero_features.py
python -B tools/test_danzero_features.py
python -u -B tools/danzero_feature_sanity.py --games 100 --out danzero_feature_sanity_100.json
```

Detailed research usage is documented in [README_RESEARCH.md](README_RESEARCH.md).
Project milestones are summarized under `docs/progress/`.

## DanZero Feature Contract

`danzero_features.py` provides the frozen paper-style representation used by
the new DanZero route:

- 54 physical-card count slots in rank-major `H,C,S,D` order, followed by the
  black and red jokers;
- the original 513-dimensional paper state;
- a 487-dimensional website small-round state that omits cross-round team
  levels;
- a separate 155-dimensional diagnostic action representation. The learning
  baseline remains the paper's 54-dimensional physical action.

The 375 structural action IDs remain an oracle/materialization compatibility
layer and are not the primary DanZero action semantics.

## Website Shadow Audit

Stage 2 can audit real test-account states while the frozen `tempo_baseline`
remains the only policy allowed to submit actions:

```powershell
$env:GUANDAN_USER="your_test_user"
$env:GUANDAN_PASSWORD="your_test_password"
python -u -B .\play_research_adaptive.py --website-shadow --profile tempo_baseline --loop --games 20 --metric elo --require-elo --log-dir logs_website_shadow_stage2 --poll 8 --delay 10 --timeout 45 --retries 5
```

The current Shadow suggestion source is explicitly logged as
`tempo_baseline_mirror`; no learned model controls website actions. Shadow logs
include 513/487 state encodings, physical action features, team/seat checks,
local oracle legality, server acceptance, and a per-game error summary.

Historical action-only replay is available without credentials:

```powershell
python -u -B .\play_research_adaptive.py --website-shadow-replay tempo_baseline --shadow-replay-out website_shadow_replay_tempo_baseline.json
```

Because old website logs cap `trick_history` at 40 actions, replay explicitly
does not claim to validate historical 513-dimensional states.

After an online Shadow batch, evaluate the hard gate with:

```powershell
python -u -B .\play_research_adaptive.py --website-shadow-summary logs_website_shadow_stage2 --shadow-summary-out website_shadow_summary_stage2.json --shadow-minimum-games 20
```

Frozen datasets can be extended without reassigning old sessions by supplying
both `--website-base-split-manifest` and
`--website-extension-session-splits`. Every new session must be assigned to
train or development before collection; adding or changing locked-test games is
rejected. The current supplement protocol is documented in
[`docs/research/website-shadow-supplement-plan-v1.md`](docs/research/website-shadow-supplement-plan-v1.md).

## Distributed DanZero DMC

The Stage 3 runtime uses four shared-policy actors, one GPU learner, a bounded
trajectory queue, Monte Carlo team returns, replay, versioned weight sync,
stale-sample filtering, and resumable atomic checkpoints. Its network consumes
the paper-style `513 + 54 = 567` state-action input.

```powershell
python -u -B .\play_research_adaptive.py --danzero-dmc-train --danzero-games 1000 --danzero-actors 4 --danzero-out-dir models_danzero_dmc_stage3_1000 --danzero-log-out danzero_dmc_stage3_1000.json --danzero-save-every 200 --danzero-batch-size 512 --danzero-replay-capacity 20000 --device cuda --report-every 100
```

The structured physical oracle is exhaustively checked against the slower
website-rule enumerator. Checkpoints and generated logs remain ignored by Git.

Evaluate a compatible checkpoint with paired deal/first-player seat swaps:

```powershell
python -u -B .\play_research_adaptive.py --offline-danzero-arena-eval --danzero-checkpoint models_danzero_dmc_stage3_1000\danzero_dmc_latest.pth --baseline-profile tempo_baseline --danzero-arena-games 20 --danzero-arena-out danzero_arena_stage4_smoke20.json --danzero-arena-swap-seats --device cuda --report-every 2
```

The first 1000-game engineering checkpoint scored 0/20 and is archived as a
failed strength candidate. Its zero legality-error result remains useful as
runtime evidence, but it must not be expanded or used on the website.
