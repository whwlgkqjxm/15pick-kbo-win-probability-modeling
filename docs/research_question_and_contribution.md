# Research question and contribution

## Project origin

[15Pick Kbo](https://mypickkbo.com/) is a fantasy-baseball website built to translate official KBO game events into role-specific composite performance indices. This repository evaluates whether strict-prior averages of those product-originated indices carry incremental pregame predictive information beyond conventional team-strength features.

## Question

Do role-specific composite player-performance indices derived from official KBO game records provide incremental information for pregame win-probability forecasting beyond conventional team-strength features, and which roles contribute the greatest predictive value?

## Unit of analysis

The canonical dataset contains one row per completed KBO game. Binary modeling uses the 1,824 decision games among 1,864 completed games, with the target defined as whether the home team wins. The 40 ties remain in the canonical game table but are excluded from binary fitting under a prespecified rule. Cancelled or postponed games are excluded from evaluation.

## Prediction timestamp

The target setting is lineup-confirmed pregame: both official starting lineups and starting pitchers are known, and the prediction is generated before first pitch. In the retrospective study, these inputs are reconstructed from official KBO game records, and all features use only information from dates strictly earlier than the target game date; the historical records are therefore not independently timestamped pregame snapshots. For future games, pregame inputs and predictions will be timestamped and stored before first pitch in the prospective ledger described in [`prospective_validation.md`](prospective_validation.md).

## Contributions

1. **Data engineering:** a multi-season official-data foundation with 1,864 completed games, 65,554 player-game occurrences, and 65,554/65,554 numeric identity resolution.
2. **Leakage control:** all target-game and same-date results are excluded, including same-day doubleheader game 1 when predicting game 2.
3. **Audit-driven feature redesign:** the project detected identity asymmetry and role-contaminated histories, invalidated an earlier ceiling claim, and rebuilt role-specific histories.
4. **Player-index design:** 215 batter-score candidates and 20 prior-average methods were compared before selecting a rate-normalized official-event score with K=5 shrinkage and official-nine-player aggregation.
5. **Temporal model comparison:** 42 model configurations and multiple static, adaptive, online, calibration, and ensemble strategies were evaluated using temporal protocols.
6. **Incremental-value testing:** no-player, batter-only, starter-only, and combined models were compared under identical learning rules.
7. **Reproducibility:** derived data, frozen predictions, model binaries, model replay, environment records, SHA manifests, and portable reproduction code are preserved.
8. **Negative-result reporting:** complex models, player-level relief indices, several feature families, and adaptive retraining strategies are retained when they fail.

## What this project does not claim

- The indices are not economic player value.
- 2026 is not a fully untouched final test because it was inspected during method comparison.
- The best observed recent-720 model is not yet a future-proven production champion.
- Failure of the tested relief-pitcher index does not imply relief pitching is unimportant.
- Accuracy alone is not the model-selection criterion; probability quality and calibration are primary.
