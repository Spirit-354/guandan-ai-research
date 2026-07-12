# Stage 1: DanZero State and Physical-Action Encoding

## Scope

Stage 1 adds a paper-style representation without changing the frozen
`tempo_baseline`, website rules, server communication, or leaderboard Elo
semantics. All legal physical actions still come from the website-rule oracle.

## Physical Action

The primary action representation is a 54-dimensional physical-card count
vector. Slots are rank-major in the paper order:

```text
H2,C2,S2,D2, H3,C3,S3,D3, ..., HA,CA,SA,DA, BlackJoker,RedJoker
```

Each value is 0, 1, or 2 for the two physical decks. A pass is all zero. A
heart-level wildcard remains in its physical heart-level slot even when the
rule engine interprets it as another card. This prevents logical wildcard
substitution from corrupting hand materialization.

The optional 155-dimensional diagnostic action encoding appends action type,
logic rank, size, control flags, and an explicit substitution vector. It is
versioned separately and is not a replacement for the paper's 54-dimensional
learning action.

## Compact State

The 513-dimensional paper state uses these half-open slices:

| Slice | Size | Meaning |
|---|---:|---|
| `[0,54)` | 54 | own hand |
| `[54,108)` | 54 | unknown remaining physical cards |
| `[108,162)` | 54 | last non-pass play |
| `[162,216)` | 54 | teammate last play; all `-1` after teammate finishes |
| `[216,300)` | 84 | relative opponents/teammate hand counts, `3 x 28` |
| `[300,462)` | 162 | cumulative cards played by the other three seats |
| `[462,501)` | 39 | own-team, opponent-team, and current levels |
| `[501,513)` | 12 | named wildcard capability flags |

Other seats are always ordered relative to the observing player as `+1, +2,
+3`, avoiding the absolute-seat overwrite bug in the legacy 3049-dimensional
observation. The website 487-dimensional state retains the first 462 features,
the current-level 13-vector, and the 12 wildcard flags while omitting the two
cross-round team-level vectors.

The papers do not define the exact semantics or bit order of their 12 wildcard
flags. The implementation therefore uses an explicit local contract: wildcard
count, presence, appearance in the last play, and wildcard-enabled candidate
types. This ambiguity is documented rather than presented as an exact paper
reproduction.

## Validation

Unit tests freeze card order, ASCII/local conversion, duplicate counts, pass
encoding, wildcard physical identity, state slices, relative seat order, and
the finished-teammate sentinel.

The 100-game offline sanity run completed with:

- completed games: 100/100;
- decision points: 13,880;
- oracle physical candidates checked: 80,256;
- illegal actions: 0;
- fallbacks: 0;
- materialization failures: 0;
- hand-card mismatches: 0;
- feature dimension/count/non-finite errors: 0;
- fatal lead states: 0.

All four first-player seats were exercised (`26/22/22/30`). The run took about
31 seconds on the local machine.

## Known Boundary

The current website-oracle candidate enumerator is bounded and heuristic in
some lead/follow paths. Stage 1 validates every candidate it emits, but does not
prove that the candidate set is a mathematically exhaustive enumeration of all
website-legal physical plays. Stage 2 Shadow validation must measure this domain
gap before any model controls a website action.

## Result

Stage 1 passes its offline feature and materialization gate. The next stage is
website Shadow rule validation: read real test-account states, compare model
suggestions with `tempo_baseline`, and continue to submit only baseline actions.
The first website access requires a user-facing report before it starts.
