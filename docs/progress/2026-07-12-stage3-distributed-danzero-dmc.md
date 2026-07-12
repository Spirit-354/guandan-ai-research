# Stage 3: Distributed DanZero DMC Engineering Gate

## Architecture

Stage 3 introduces a separate `danzero_dmc.py` runtime instead of extending
the failed legacy `3049 + 31` action-value implementation.

- input: 513-dimensional paper state plus 54-dimensional physical action;
- model: four 512-unit `tanh` layers and one scalar Q output;
- actors: four Windows `spawn` processes sharing one Q policy across all seats;
- learner: the main process is the only GPU/optimizer owner;
- reward: terminal team win/loss `+1/-1` for every decision in the trajectory;
- exploration: versioned epsilon-greedy;
- transport: bounded complete-game trajectory queue with backpressure;
- replay: bounded learner replay buffer;
- synchronization: serialized CPU state dict broadcast with monotonic policy
  versions and stale-sample rejection;
- recovery: atomic checkpoints containing model, optimizer, replay, counters,
  encoding/oracle/reward versions, and learner RNG state;
- episodes: a locked global episode counter prevents deal reuse after resume.

## Complete Physical Oracle

The previous fast oracle was not sufficient for DanZero. In an initial 27-card
lead state it returned only 202 of 1,504 legal physical actions, a recall of
13.43%. It emitted no illegal extras, but the omissions would bias every
`argmax Q(s,a)`.

`danzero_oracle.py` now generates actions structurally by website-recognized
type, rank window, physical suit, duplicate count, and heart-level wildcard
allocation. Website recognition remains the final validator.

Two independent audits compared physical-card multisets with the old brute
force website-rule enumerator:

- 10 consecutive lead/follow states: 1,695/1,695 exact matches;
- 13 fresh lead states with levels 2 through A: 8,760/8,760 exact matches;
- missing actions: 0;
- extra actions: 0;
- structural-action mapping failures: 0;
- aggregate structured time for all levels: 0.26 seconds;
- aggregate brute-force time for all levels: 86.07 seconds.

The all-level audit is about 331 times faster while producing the same physical
sets. The production oracle is versioned as
`structured_exhaustive_website_oracle_v1`.

## 1000-Game Engineering Validation

The formal local run used four actors, one CUDA learner, a 20,000-transition
replay buffer, checkpoints every 200 games, and the complete structured oracle.

- completed games: 1,000/1,000;
- failed games: 0;
- decisions: 132,429;
- learner updates/version: 997;
- actor version range: 0 to 980;
- stale samples: 0;
- illegal actions: 0;
- fallbacks: 0;
- materialization failures: 0;
- hand-card mismatches: 0;
- fatal empty candidate sets: 0;
- first-player distribution: `240/266/231/263`;
- team win rates: `51.9%/48.1%`;
- all 13 levels were represented;
- elapsed learner time: about 136 seconds;
- checkpoint size with replay: about 120 MB.

The observed team symmetry gap was 1.9 percentage points and maximum
first-player deviation was below 2 percentage points.

## Resume Validation

The 1,000-game checkpoint was loaded with strict schema, dimension, encoding,
oracle, and reward compatibility checks, then continued to game 1,001.

- learner version: 997 to 998;
- replay restored at 20,000;
- actor loaded version 997;
- next episode index: 1,001;
- compatibility mismatches: 0;
- all action integrity counters remained zero.

An initial resume smoke exposed that CUDA RNG tensors loaded through
`map_location=cuda` must be moved to CPU before `set_rng_state_all`; that bug is
fixed and covered by the successful resume.

## Interpretation

This gate proves the distributed learning system, complete candidate source,
version synchronization, team symmetry, and recovery mechanics. It does not
prove playing strength. The checkpoint is registered as `offline_only`, has not
run against `tempo_baseline`, and is forbidden from website use.

Stage 4 must train at decision-count milestones and apply the 20/100/300/1000
Arena promotion gates. Stage 2 online Shadow state validation also remains
pending because test-account environment variables are not available in the
current process.
