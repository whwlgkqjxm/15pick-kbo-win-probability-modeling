# Data Card

## Intended use

The modeling dataset supports retrospective and prospective research on KBO pregame win-probability forecasting and the incremental value of role-aware player performance indices.

## Coverage

- Official KBO seasons: 2024, 2025, and 2026 through July 9
- Scheduled-game rows: 2,047
- Completed games: 1,864
- Cancelled or postponed games: 183
- Binary modeling rows after excluding ties: 710 in 2024, 698 in 2025, 416 in 2026
- Player-game occurrences: 65,554
- Batter occurrences: 47,353
- Pitcher occurrences: 18,201
- Official starting-lineup rows: 33,552

## Unit of analysis

One modeling row represents one completed decision game with a binary target:

- `home_win = 1` when the home team won
- `home_win = 0` when the away team won

Ties are excluded from binary fitting and scoring.

## Feature timing

All historical aggregates are computed strictly before the target game date. Same-date games are excluded, so doubleheader Game 1 does not enter Game 2 features.

## Identity

Official numeric player IDs are preferred. The final occurrence-level identity table resolves all 65,554 player-game occurrences. Name-only forced merges are not used.

## Public distribution

The repository does not redistribute the complete official KBO raw archive. It publishes:

- modeling schema
- synthetic example rows
- frozen aggregate result tables
- maintained transformation and evaluation code
- data-lineage documentation

## Known limitations

- Historical lineup confirmation timestamps were not archived contemporaneously for every game.
- Complete historical injury and active-roster availability snapshots are not part of the primary dataset.
- Exact relief-pitcher intent and deployment are not observable before first pitch.
- Findings are KBO-specific and may not transfer directly to other leagues.
