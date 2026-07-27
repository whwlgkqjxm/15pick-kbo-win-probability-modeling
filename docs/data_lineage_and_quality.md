# Data lineage and quality assurance

The modeling results in this repository depend on a data foundation built directly from official KBO records. This page documents that foundation: the source coverage, the analytical records created from it, the identity and role checks applied to player appearances, the corrections made after reconciliation, and the final verified dataset used for modeling.

Model performance, player-index formulas, and temporal evaluation are documented separately. The purpose here is narrower: to show that the data entering those analyses are complete, internally consistent, and auditable.

## Official source coverage

The source index contains **2,047 official schedule records** across three regular seasons:

- **2024:** March 23 through October 1;
- **2025:** March 22 through October 4;
- **2026:** March 28 through July 9.

The schedule records reconcile exactly to **1,864 completed games** and **183 cancelled or postponed games**. Completed games comprise **720 in 2024**, **720 in 2025**, and **424 in 2026**. The schedule also contains **42 doubleheader games**, representing **21 doubleheader pairs**, and no duplicated official game IDs.

Official GameCenter and BoxScore records were captured for all **1,864 of 1,864 completed games**. These records supplied final scores, starting lineups, batting events, pitcher lines, and game details. Raw source responses were preserved separately from parsed outputs so that corrections could be made without rewriting the original evidence.

## Canonical analytical records

The raw records were normalized into separate analytical layers rather than one wide scraped table. Each layer has a fixed observation unit and key:

- one canonical record per completed game;
- one record per batter appearance in a game;
- one record per pitcher appearance in a game;
- event-level batting details linked to the corresponding player appearance;
- one official starting-lineup record per batting-order position;
- one official starting-pitcher record per team and game.

The completed canonical foundation contains:

- **1,864 games**;
- **14,785 game-detail records**;
- **47,353 batter appearances**;
- **146,633 batter-event records**;
- **18,201 pitcher appearances**;
- **33,552 official starting-lineup records**;
- **3,728 official starting-pitcher records**.

The counts reconcile across independently constructed layers:

- `33,552 = 1,864 games × 2 teams × 9 starting batters`;
- `3,728 = 1,864 games × 2 starting pitchers`;
- `65,554 = 47,353 batter appearances + 18,201 pitcher appearances`.

Ties remain in the canonical game data. Binary win-probability modeling excludes the **40 tied games** under a fixed rule, leaving **1,824 decision games**: **710 from 2024**, **698 from 2025**, and **416 from 2026**.

## Player identity and role integrity

Player names were not treated as durable identifiers. The source data contained formatting differences and **26 same-name collision groups**, so a name-only join could merge different players or split one player into multiple histories.

Identity resolution used official numeric player identifiers, profile evidence, season-team evidence, targeted official daily records, and occurrence-level fingerprints. The first pass resolved **65,427 of 65,554 player-game appearances**, leaving **127 unresolved**. Targeted recovery collected **392 evidence records from 12 of 12 required official pages**. That evidence produced **124 exact fingerprint assignments** and **3 within-game pitcher-sequence assignments**.

The final result was:

- **65,554 of 65,554 appearances resolved**;
- **0 unresolved appearances**;
- **0 name-only forced merges**;
- **844 unique numeric player IDs** in the corrected player-game foundation.

Identity and role were validated separately. Starting batters, substitute batters, starting pitchers, and relief pitchers were retained as distinct analytical roles. This prevents a player's historical record in one role from silently changing the meaning of a feature defined for another role.

## Canonical reconciliation and correction

The multi-season canonical replay was compared with the previously preserved 2026 derived records. The initial comparison identified:

- **39 batter-input disagreements**;
- **21 pitcher-input disagreements**;
- **40 derived-record disagreements among 14,891 replayed player-game records**;
- **5 incorrect historical player-ID assignments**.

The disagreements were traced to specific source or parsing issues, including strikeout-token coverage, stolen-base count suffixes, double-play details, player-ID errors, display-name formatting, and one stale July 8 source snapshot. Earlier files were retained as historical evidence; corrected records were written as a new version using official canonical fields and final numeric identity as the analytical source of truth.

After correction:

- **6,881 of 6,881 score-relevant event details** were resolved;
- **10 of 10 manually audited overrides** were verified;
- **0 event-component mismatches** remained;
- **14,857 of 14,891 preserved 2026 records** were unchanged;
- **34 records** received a corrected derived score;
- **5 records** received a corrected player identity.

These corrections were completed before the final historical features and modeling dataset were frozen.

## Strict-prior histories

Every player-game appearance has a corresponding history state calculated at the target-game cutoff. Histories are updated by date: all games on a target date are assigned features using records from earlier dates, and only after those feature rows are frozen are that date's completed records added to history.

The final history foundation contains **65,554 rows**:

- **63,595 rows** have at least one eligible earlier observation;
- **1,959 rows** are genuine cold starts;
- **0 rows** use the current game;
- **0 rows** use another result from the same date;
- **0 temporal-order violations** were detected.

Cold starts were preserved as an observable data condition through prior-count, coverage, and missing-value fields. They were not filled with later-season or future information. The full timing contract is documented in [temporal validation and leakage](temporal_validation_and_leakage.md).

## Frozen modeling dataset

The final [game-level modeling dataset](../data/derived/V12_MODELING_DATASET.csv) contains **1,824 rows and 71 columns**, with one row per non-tie completed game. It includes identifiers and outcomes for retrospective reproduction, data-quality and coverage fields, strict-prior team and player summaries, and the **14 inputs** used by the frozen models.

The 14 modeling inputs consist of:

- **5 conventional team-strength variables**;
- **5 starting-pitcher and post-starter variables**;
- **4 batter-lineup variables**.

The dataset has **1,824 unique game IDs**, is ordered deterministically by `game_date, game_id`, and preserves the exact column names and order required for saved-model replay. The public [modeling schema](../data/schema/modeling_dataset_schema.csv) defines each model input and its analytical role.

## Final quality status

The final data foundation passed the following checks:

- official schedule totals reconciled to completed and cancelled/postponed records;
- all **1,864 completed games** were represented once in the canonical game layer;
- every game-side contained exactly **9 official starting batters**;
- every game-side contained exactly **1 official starting pitcher**;
- player identity was complete for all **65,554 appearances**;
- missing player IDs in the selected lineup data were **0**;
- name-only forced identity merges were **0**;
- event-component mismatches after correction were **0**;
- strict-prior temporal violations were **0**;
- the modeling table contained **1,824 rows**, **1,824 unique game IDs**, and **14 frozen model features**;
- audit status for the final batter-lineup and modeling pipelines was **PASS**.

Machine-readable verification is available in the [portable dataset validation](../reports/reproduced/dataset_validation.json), [final modeling and leakage audit](../reports/frozen/V12_REPRODUCIBILITY_AND_LEAKAGE_AUDIT.json), [lineup-construction audit](../reports/frozen/V11_1_REPRODUCIBILITY_AUDIT.json), [modeling schema](../data/schema/modeling_dataset_schema.csv), and [SHA256 artifact manifest](../artifacts/RESEARCH_MANIFEST_SHA256.csv).

The complete raw-response archive is not redistributed. The repository includes the derived modeling data, schemas, audit results, saved models, and hashes needed to inspect and reproduce the published analysis. Release boundaries are documented in the [data release policy](data_release_policy.md).
