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
python -B -m py_compile play_research_adaptive.py play_step_0902.py play_step_09.py
```

Detailed research usage is documented in [README_RESEARCH.md](README_RESEARCH.md).
Project milestones are summarized under `docs/progress/`.
