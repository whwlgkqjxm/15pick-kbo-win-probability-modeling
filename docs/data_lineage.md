# Data Lineage

```mermaid
flowchart TD
    S[Official KBO schedule pages] --> G[1,864 completed games]
    G --> R[Immutable raw GameCenter responses]
    R --> C[Canonical game, batter, pitcher, and lineup tables]
    C --> I[Numeric player identity resolution]
    I --> P[65,554 player-game occurrences]
    P --> B[Batter and starter game indices]
    B --> H[Strict-prior same-season and cross-season histories]
    H --> F[Game-level lineup, starter, bullpen, and team features]
    F --> M[Temporal probabilistic models]
    M --> E[Ablation, calibration, bootstrap, and model selection]
```

## Fixed data interval

- 2024-03-23 through 2024-10-01
- 2025-03-22 through 2025-10-04
- 2026-03-28 through 2026-07-09

## Core counts

- Schedule rows: 2,047
- Official completed games: 1,864
- Cancelled or postponed rows: 183
- Batter occurrences: 47,353
- Pitcher occurrences: 18,201
- Starting-lineup rows: 33,552
- Player-game occurrences: 65,554
- Final unresolved occurrences: 0

## Public-data policy

The repository publishes code, schemas, aggregate results, formulas, and synthetic examples. Complete official raw responses and large derived player-level tables are not redistributed in the main branch.
