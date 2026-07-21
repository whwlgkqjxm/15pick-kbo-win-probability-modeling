# Data Lineage

## Source-to-model path

```text
Official KBO schedule and GameCenter pages
    ↓
Immutable game-page cache and source hashes
    ↓
Canonical schedule, batter, pitcher, and lineup tables
    ↓
Occurrence-level numeric player identity resolution
    ↓
Role-specific player-game performance indices
    ↓
Strict-prior player and team histories
    ↓
Confirmed-lineup and announced-starter aggregation
    ↓
Leakage-controlled modeling dataset
    ↓
Temporal model comparison and ablation
```

## Source inventory

The official schedule inventory contained 2,047 rows: 1,864 completed games and 183 cancelled or postponed games. Every completed game was matched to a cached official game page before canonical parsing.

## Canonical tables

The canonical foundation contains:

- 47,353 batter appearances
- 18,201 pitcher appearances
- 33,552 official starting-lineup rows
- 65,554 total player-game occurrences

## Identity resolution

Player identity uses official numeric IDs whenever available. Ambiguous same-name cases were resolved using official occurrence evidence and targeted daily records. The final table contains zero unresolved occurrences and zero name-only forced assignments.

## Role scope

Histories are separated by role:

- official starting batters
- substitute batter appearances
- starting pitchers
- relief pitchers

The public prediction model uses confirmed starting batters and announced starting pitchers. Starting-pitcher history excludes relief appearances.

## Temporal construction

For a target game on date `d`, every historical source row must satisfy:

```text
source_game_date < d
```

All games on `d` are excluded from feature history. This rule prevents target leakage and same-date doubleheader contamination.

## Auditability

The public repository contains schemas, aggregate counts, frozen result tables, and verification tests. Full official source pages and local modeling tables are retained outside the public repository because of size and redistribution constraints.
