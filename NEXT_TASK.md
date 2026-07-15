# NEXT_TASK.md

## Current Gate

There is no automatic executable next stage.

Stage 6 is closed as `completed_rejected`. The frozen Stage 6 evidence contains
zero candidates that pass the offline gate:

- `offline_gate_passed = false`;
- `eligible_offline_candidate_count = 0`;
- `stage_7_authorized = false`;
- `website_control_authorized = false`;
- `capability_claim_allowed = false`.

This is a negative gate result. It does not mean the model passed, improved,
was promoted, or is deployable.

## Required User Decision

A future task must explicitly choose and freeze a new pre-Stage-7 research
route. It must define its assumptions, evidence boundary, single-stage scope,
and acceptance criteria before execution. Do not infer that decision from the
exhaustion of the current route.

## Frozen Final Evidence

- Stage 6.20 disposition:
  `website_teacher_preference_stage6_final_disposition_v1.json`, SHA-256
  `e93450fafe18586ae74662c58a1af2eb40497fdb7128e33e8be4e3b077f4fab5`.
- Stage 6.20 implementation:
  `website_teacher_preference_stage6_final_disposition.py`, SHA-256
  `03c2388e5b618a8d0f46faa81537dfccdef963b41a097530f8ba0c354a740491`.
- The artifact freezes 32 exact hashes and independently reproduces all Stage
  6 gate conclusions with zero semantic model/checkpoint/data loads and zero
  forbidden operations.

## Prohibited Automatic Work

- Do not enter or execute Stage 7.
- Do not run website Shadow, website play, or model-controlled website actions.
- Do not promote the current checkpoint or make capability claims.
- Do not rerun the three inconclusive train comparisons or convert them into
  labels.
- Do not start a new dataset, objective, training, tuning, Arena, or candidate
  route without an explicit user-authorized single-stage handoff.
