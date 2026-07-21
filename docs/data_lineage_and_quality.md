# Data lineage and quality controls

## Source layers

1. Official KBO schedule pages define game identity and status.
2. Official GameCenter/BoxScore responses provide completed-game records, lineups, batter events, and pitcher lines.
3. Canonical tables separate game, player occurrence, event detail, and role.
4. Numeric identity resolution links occurrences without name-only forced merges.
5. Corrected player-game performance streams are calculated from official canonical fields.
6. Strict-prior histories are produced in date batches.
7. Lineup-confirmed game features join team, starter, post-starter, and batter-lineup blocks.
8. V12 creates the final 1,824-row decision-game modeling table.

## Scale and completeness

- 2,047 schedule rows
- 1,864 completed games
- 183 cancelled/postponed games
- 47,353 batter occurrences
- 18,201 pitcher occurrences
- 33,552 official starting-lineup rows
- 65,554 total player-game occurrences
- 65,554 resolved occurrences
- 0 name-only forced merges
- 0 strict-prior temporal violations

## Identity quality

Displayed names are not sufficient keys because same-name collisions and formatting differences exist. The pipeline uses numeric player IDs and official evidence. Unresolved states are preferable to speculative merging. Targeted daily evidence and occurrence fingerprints were used to resolve the final 127 initially unresolved occurrences.

## Scoring parity

The audit compared canonical replay against the legacy 2026 stream. Differences were investigated rather than overwritten. Root causes included strikeout token coverage, stolen-base suffix interpretation, double-play detail, five incorrect legacy IDs, display-name formatting, and a stale July 8 snapshot.

## Included derived data

`data/derived/V12_MODELING_DATASET.csv` contains one row per decision game and the features required to reproduce the core V12 logistic models. It is deterministically sorted by `game_date, game_id` and has 1,824 rows.

The derived table is included to make the portfolio technically reviewable. It is not a substitute for permission to redistribute complete official raw responses. Review the release policy before making the repository public.
