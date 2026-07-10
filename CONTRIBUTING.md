# Contribution Guide

## Commit format

Use Conventional Commits with a concise scope:

```text
<type>(<scope>): <summary>
```

Common types:

- `feat`: new offline research capability
- `fix`: correctness or runtime fix
- `test`: validation or reproducibility work
- `docs`: documentation or curated progress note
- `chore`: repository maintenance

Examples:

```text
feat(dmc): add hybrid override audit
fix(arena): validate physical card materialization
test(dmc): record control-pass threshold evaluation
docs(progress): summarize m038 validation
```

## Progress commits

Commit after a coherent, verified milestone rather than every intermediate
keystroke. Each progress commit should include:

1. The implementation or analysis change.
2. A concise note under `docs/progress/` when results affect the research plan.
3. The exact validation command and outcome.
4. No credentials, raw logs, datasets, or model checkpoints.

Use feature branches named `agent/<short-topic>`. Keep `main` as the stable
history and publish work through a draft pull request when practical.
