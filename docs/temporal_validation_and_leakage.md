# Temporal validation and leakage-control contract

This page defines when information is allowed to enter a prediction, how the chronological evaluation was constructed, and why the 2026 results are development evidence rather than a final untouched test.

## Prediction setting

The intended prediction point is **after the official starting lineups and starting pitchers are known, but before first pitch**.

Information is divided into two categories:

- **Current-game pregame information:** the scheduled matchup, official starting lineups, and announced starting pitchers may be used because they are available before the game begins.
- **Outcome-derived information:** game results, BoxScore events, player performance from the target game, and other information revealed during or after the game may not be used.

For every historical feature derived from earlier game results, the latest contributing game date must be strictly earlier than the target game date.

The retrospective study reconstructs starting lineups and starting pitchers from official historical game records. Those records identify who started, but an independent pre-first-pitch capture timestamp is not available for every historical game. The retrospective analysis is therefore outcome-leakage controlled, but it is not equivalent to an immutable real-time pregame feed. Future evaluation addresses this limitation through timestamped prospective predictions.

## Evaluation population

The official foundation contains 1,864 completed games.

- 40 tied games remain in the canonical game records but are excluded from binary home-win modeling under the fixed target rule.
- The final binary modeling dataset contains 1,824 decision games:
  - 710 from 2024;
  - 698 from 2025;
  - 416 from 2026.
- Cancelled or postponed games are excluded from model evaluation.
- Each eligible game appears once and the released modeling table is ordered deterministically by `game_date, game_id`.

## Two different evaluation risks

Feature leakage and evaluation-period reuse are related but different problems.

| Risk | Meaning | Status in this project |
|---|---|---|
| Feature leakage | Information from the target outcome, the same date, or the future enters a feature vector | Controlled through strict-prior and same-date exclusion rules |
| Evaluation-period reuse | Observed outcomes are used to choose models, hyperparameters, or training strategies | Present in the 2026 training-strategy comparison |

A prediction can be free of target-game leakage while still being evaluated on a period that is no longer an untouched test.

## Hard rules

1. Historical outcome-derived features may use only games with dates strictly earlier than the target game date.
2. The target game's outcome, BoxScore events, and player results are excluded from its feature vector.
3. Results from every other game on the same calendar date are also excluded.
4. The first game of a same-day doubleheader is not used when constructing features for the second game.
5. Current-game lineups and starting pitchers may be used only as pregame inputs; the pitchers who actually appear in relief may not be used.
6. All feature rows for a calendar date are frozen before that date's completed games are added to history.
7. For adaptive methods, predictions for every game on a date are generated before any outcome from that date is added to the training history.
8. Imputation, scaling, feature selection, model fitting, calibration, and other learned transformations are fitted only on the corresponding training rows.
9. Primary model conclusions use chronological evaluation. Random shuffled train-test splits and random K-fold validation are not used.
10. Cancelled and postponed games are void. Tied games are retained in the source data but excluded from the binary target under the predefined rule.

## Date-batched feature construction

Feature construction follows a date-level batch process.

For each target date:

1. the historical state contains only games completed on earlier dates;
2. feature rows are created for every eligible game on the target date;
3. all feature rows, and any adaptive predictions, are frozen;
4. only after the entire date has been processed are that date's completed outcomes added to history.

This procedure prevents an earlier-finishing game from affecting another game played on the same date. It also applies to doubleheaders, even when the first game may have finished before the second game began.

The date-level rule is intentionally conservative because consistent historical event and confirmation timestamps are not available for every game.

## Expanding temporal cross-validation

Model-family and hyperparameter comparison across 2024–2025 used five expanding temporal folds.

In every fold:

- the training period occurs entirely before the validation period;
- the training set grows as time advances;
- preprocessing and model fitting are repeated using only that fold's training rows;
- the validation outcomes are not used when fitting the corresponding fold model.

| Fold | Training period | Validation period | Training games | Validation games |
|---:|---|---|---:|---:|
| 1 | 2024-03-23 to 2024-07-11 | 2024-07-12 to 2024-09-06 | 422 | 210 |
| 2 | 2024-03-23 to 2024-09-06 | 2024-09-07 to 2025-04-22 | 632 | 195 |
| 3 | 2024-03-23 to 2025-04-22 | 2025-04-23 to 2025-06-19 | 827 | 232 |
| 4 | 2024-03-23 to 2025-06-19 | 2025-06-20 to 2025-08-14 | 1,059 | 180 |
| 5 | 2024-03-23 to 2025-08-14 | 2025-08-15 to 2025-10-02 | 1,239 | 167 |

The machine-readable fold definition is published in
[`data/derived/V12_TEMPORAL_FOLD_DEFINITION.csv`](../data/derived/V12_TEMPORAL_FOLD_DEFINITION.csv).

## How the 2026 results must be interpreted

Every 2026 feature row follows the strict-prior and same-date exclusion rules. No target-game result enters its own prediction, and no result from another game on the same date is used.

However, 2026 outcomes were inspected while comparing:

- regularization settings;
- training-window lengths;
- static and adaptive training strategies;
- weighting and time-decay approaches;
- calibration methods;
- ensembles.

The correct interpretation is therefore:

- **The 2026 predictions are controlled for target-game and same-date outcome leakage.**
- **The 2026 period is not a final untouched test.**
- **The recent-720 specification is the best observed development model, not a future-validated champion.**
- **A final generalization claim requires predictions recorded before first pitch on games whose outcomes were unavailable during development.**

The CV-selected reference model was selected using the 2024–2025 temporal folds without using 2026 outcomes for model selection. Its later 2026 evaluation is scientifically cleaner than a model selected through 2026 comparison, but 2026 is still an already observed period for the project as a whole.

Detailed model comparisons are documented in
[model selection, ablation, and calibration](model_selection_ablation_and_calibration.md).
The rules governing future evidence are documented in
[prospective validation](prospective_validation.md).

## Paired date-cluster uncertainty

Multiple games played on the same date may share scheduling conditions, league-wide context, weather patterns, and operational timing. Treating every game row as fully independent would ignore this within-date dependence.

Model differences are therefore evaluated with a paired date-cluster bootstrap:

1. unique game dates are sampled with replacement;
2. every game belonging to each sampled date is included;
3. both models are evaluated on the same sampled games;
4. the paired Log-loss difference is calculated;
5. the procedure is repeated to form a percentile interval and an improvement probability.

All games from a sampled date are concatenated rather than first reducing each date to a single average. This preserves the game-level weighting of dates containing different numbers of games.

The implementation is available in
[`src/fifteenpick_prediction/bootstrap.py`](../src/fifteenpick_prediction/bootstrap.py).

Date-cluster intervals represent uncertainty in the observed paired performance difference under this resampling design. They do not remove uncertainty caused by model selection, repeated inspection of an evaluation period, future season shifts, or changes in team composition.

## What this contract establishes

The published checks support the following statements:

- target-game outcomes are excluded from feature construction;
- outcomes from the same date are excluded;
- historical features use only earlier dates;
- same-day doubleheader results do not cross into the second game's features;
- chronological ordering is deterministic;
- learned preprocessing is restricted to training data;
- saved predictions and model outputs can be replayed from the released artifacts.

The contract does not establish that:

- every historical lineup was independently captured and timestamped before first pitch;
- 2026 was an untouched final test;
- the observed development performance will necessarily persist in future seasons.

## Verification resources

The temporal rules can be inspected in the following repository files:

- [temporal fold definition](../data/derived/V12_TEMPORAL_FOLD_DEFINITION.csv);
- [temporal ordering and strict-prior helpers](../src/fifteenpick_prediction/temporal.py);
- [fail-closed dataset validation](../src/fifteenpick_prediction/validation.py);
- [paired date-cluster bootstrap](../src/fifteenpick_prediction/bootstrap.py);
- [final modeling and leakage audit](../reports/frozen/V12_REPRODUCIBILITY_AND_LEAKAGE_AUDIT.json);
- [temporal tests](../tests/test_temporal.py);
- [dataset-validation tests](../tests/test_dataset_validation.py);
- [bootstrap tests](../tests/test_bootstrap.py).
