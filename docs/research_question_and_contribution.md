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

1. **Official data engineering:** the project built a multi-season KBO data foundation covering 1,864 completed games and 65,554 player-game occurrences, with numeric player identity resolved for all 65,554 occurrences.
2. **Strict temporal leakage control:** all target-game and same-date results are excluded from feature construction, including the first game of a same-day doubleheader when predicting the second game.
3. **Audit-driven data correction:** the project detected home-away identity asymmetry and role-contaminated player histories, invalidated an earlier ceiling claim, and rebuilt role-specific historical features.
4. **Role-specific index redesign:** official KBO records were used to redesign both a clean start-only starting-pitcher index and a fully new batter index. The batter study compared 215 game-score candidates and 20 prior-averaging methods before selecting a rate-normalized score with K=5 shrinkage and aggregation over the official nine-player starting lineup.
5. **Temporal model and training-strategy comparison:** 42 model configurations were evaluated using static, rolling, expanding, adaptive, and online training strategies, together with calibration and ensemble methods.
6. **Incremental-value testing:** no-player, batter-only, starter-only, and combined batter-plus-starter models were compared under the same V12 learning protocol to measure the additional predictive contribution of each player-index block.
7. **Probability-focused evaluation:** models were evaluated using log loss and Brier score as primary metrics, together with calibration analysis and temporally clustered uncertainty estimates, rather than accuracy alone.
8. **Reproducibility:** derived modeling data, frozen predictions, fitted model binaries, replay checks, environment records, SHA manifests, and portable reproduction code are preserved.
9. **Transparent negative-result reporting:** unsuccessful complex models, player-level relief-pitcher indices, feature families, and adaptive retraining strategies are documented and preserved rather than omitted.

## What this project does not claim

- The player-performance indices do not represent economic, contractual, or market value.
- The 2026 evaluation is not a fully untouched final test because its outcomes were inspected during method and training-strategy comparison.
- Operational deployment of the recent-720 model does not imply that its future generalization has already been demonstrated.
- Failure of the tested player-level relief-pitcher index does not imply that relief pitching is unimportant.
- Historical lineups are reconstructed from official game records rather than independently archived pregame snapshots.
- The results demonstrate predictive association, not a causal effect of the indices on game outcomes.

Unresolved limitations and their planned follow-up are documented in [`prospective_validation.md`](prospective_validation.md).
