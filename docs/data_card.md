# Data card

## Purpose

The derived data supports a study of pregame KBO home-win probabilities using conventional team strength, clean start-only pitcher priors, team post-starter run prevention, and a newly designed official-event batter-lineup index.

## Observation units

- Canonical foundation: one row per player-game occurrence or event, depending on table.
- Modeling table: one row per completed decision game.
- Prediction target: home win (`1`) versus away win (`0`).
- Ties: preserved in canonical data, excluded from binary fitting.
- Cancelled/postponed games: excluded or voided.

## Coverage

| Season | Completed games | Binary modeling rows |
|---|---:|---:|
| 2024 | 720 | 710 |
| 2025 | 720 | 698 |
| 2026 through July 9 | 424 | 416 |
| **Total** | **1,864** | **1,824** |

## Player-level foundation

- batter occurrences: 47,353
- pitcher occurrences: 18,201
- total occurrences: 65,554
- numeric identity resolution: 65,554/65,554
- name-only forced merges: 0
- official starting-lineup rows: 33,552
- history available: 63,595
- cold starts: 1,959
- temporal violations: 0

## Included table

`data/derived/V12_MODELING_DATASET.csv` contains 71 columns and 1,824 decision-game rows. It includes identifiers and outcomes needed for audit plus the 14 frozen model features. It is deterministically ordered by `game_date, game_id`.

## Quality controls

- duplicate official game ID check;
- exact official nine-player lineup per side;
- side-specific identity coverage;
- no name-only forced identity merge;
- score-component parity and mismatch adjudication;
- current-game and same-date exclusion;
- model probability range checks;
- saved-model binary replay;
- SHA256 artifact manifest.

## Known limitations

Historical lineup confirmation is reconstructed from official game records rather than preserved timestamped screenshots for every game. Exact physical runs after a starter exits and historical daily roster availability require additional play-by-play and point-in-time roster sources. See `docs/limitations.md`.
