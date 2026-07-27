# Data lineage and quality assurance

This page explains how official KBO records were converted into the verified data used in the analysis. It focuses on source coverage, normalized records, player identity, role separation, corrections, and the final modeling dataset. Model performance, index formulas, and temporal evaluation are documented elsewhere.

## Official source coverage

The source index contains **2,047 official schedule records** across three regular-season periods:

- **2024:** March 23–October 1;
- **2025:** March 22–October 4;
- **2026:** March 28–July 9.

The schedule reconciles to **1,864 completed games** and **183 cancelled or postponed games**. The completed games consist of **720 in 2024**, **720 in 2025**, and **424 in 2026**. The schedule also includes **42 doubleheader games**, or **21 pairs**, with **0 duplicated official game IDs**.

Official GameCenter and BoxScore records were captured for all **1,864 completed games**. Raw responses were preserved separately from parsed data so that later corrections did not replace the original evidence.

## Canonical analytical records

Here, canonical records are source-aligned, normalized tables treated as the analytical source of truth. Separate tables were created for games, batter appearances, pitcher appearances, batting events, starting lineups, and starting pitchers.

The completed foundation contains:

- **1,864 games** and **14,785 game-detail records**;
- **47,353 batter appearances** and **146,633 batter-event records**;
- **18,201 pitcher appearances**;
- **33,552 official starting-lineup records**;
- **3,728 official starting-pitcher records**.

The layers reconcile exactly. The lineup count equals `1,864 games × 2 teams × 9 starters`, and the starting-pitcher count equals `1,864 games × 2 teams`. Batter and pitcher appearances sum to **65,554 player-game appearances**, meaning one player appearing in one game in a defined batting or pitching role.

Pitching innings were converted from baseball notation such as `1/3`, `2/3`, and `5 2/3` into integer outs before workload or rate calculations. Unsupported or ambiguous values failed validation instead of being silently converted.

The canonical data retain **40 ties**. Excluding them under the fixed binary-target rule leaves **1,824 decision games**: **710 in 2024**, **698 in 2025**, and **416 in 2026**.

## Player identity and role integrity

Player names were not used as durable identifiers because the source data contained formatting variation and **26 same-name collision groups**. Identity resolution used official numeric IDs, profile and season-team evidence, targeted official daily records, and exact matching on game, team, role, and stat fields.

The initial pass resolved **65,427 of 65,554 appearances**, leaving **127 unresolved**. Targeted recovery obtained **392 evidence records from 12 of 12 required official pages**, producing **124 exact matches** and **3 within-game pitcher-sequence assignments**.

The final identity foundation contains:

- **65,554 of 65,554 appearances resolved**;
- **0 unresolved appearances**;
- **0 name-only forced merges**;
- **844 unique numeric player IDs**.

Role was validated separately from identity. The final records contain **33,552 starting-batter appearances**, **13,801 substitute-batter appearances**, **3,728 starting-pitcher appearances**, and **14,473 relief-pitcher appearances**. These counts reconcile to the full batter and pitcher totals and prevent one role from silently entering another role's history.

Starter-specific checks also passed. All **848 of 848 source starters** were resolved, and all **832 of 832 model-period starters** were eligible for history construction: **416 of 416 home starters** and **416 of 416 away starters**.

## Canonical reconciliation and correction

The multi-season canonical replay was compared with the previously preserved 2026 derived data. The initial audit found **39 batter-input disagreements**, **21 pitcher-input disagreements**, **40 derived-score disagreements among 14,891 player-game records**, and **5 incorrect historical player-ID assignments**.

Each difference was traced to a specific source, parsing, formatting, or identity cause. Official canonical fields and final numeric identity became the analytical source of truth, while earlier files were retained as historical evidence.

After correction:

- **6,881 of 6,881 score-relevant event details** were resolved;
- **10 of 10 manually audited overrides** were verified;
- **0 event-component mismatches** remained;
- scores remained unchanged for **14,857 of 14,891** preserved 2026 player-game records;
- **34 score rows** and **5 player-identity assignments** were corrected.

The full player-game foundation contains **25,131 records from 2024**, **25,532 from 2025**, and **14,891 from 2026**, totaling **65,554**.

## Strict-prior histories

Historical features were created by date. All games on a target date were assigned features using only records from earlier dates; that date's completed records were added to history only after every feature row for the date had been frozen.

The final history data contain **65,554 rows**. Earlier eligible history exists for **63,595 rows**, while **1,959 rows** are genuine cold starts. The audit found **0 uses of the current game**, **0 uses of another result from the same date**, and **0 temporal-order violations**.

Cold starts were retained through prior-count, coverage, and missing-value fields rather than filled with future information. The full timing and evaluation rules are documented in [temporal validation and leakage](temporal_validation_and_leakage.md).

## Frozen modeling dataset and verification

The final [game-level modeling dataset](../data/derived/V12_MODELING_DATASET.csv) contains **1,824 rows and 71 columns**, with **1,824 unique game IDs** and one row per non-tie completed game. It is ordered deterministically by `game_date, game_id`.

The frozen models use **14 pregame inputs**:

- **5 conventional team-strength variables**;
- **1 team-level post-starter run-prevention variable**;
- **4 start-only pitcher-index variables**;
- **4 batter-lineup-index variables**.

The [modeling schema](../data/schema/modeling_dataset_schema.csv) defines each input. Machine-readable checks for the released modeling table, lineup construction, temporal flags, saved-model replay, and artifact hashes are available in the [portable dataset validation](../reports/reproduced/dataset_validation.json), [final modeling and leakage audit](../reports/frozen/V12_REPRODUCIBILITY_AND_LEAKAGE_AUDIT.json), [lineup-construction audit](../reports/frozen/V11_1_REPRODUCIBILITY_AUDIT.json), and [SHA256 artifact manifest](../artifacts/RESEARCH_MANIFEST_SHA256.csv).

The complete raw-response archive is not redistributed. The repository provides the derived modeling data, schemas, audit results, saved models, and hashes needed to inspect the reported analysis. Release boundaries are documented in the [data release policy](data_release_policy.md).
