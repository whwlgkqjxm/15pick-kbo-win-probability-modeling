# Temporal validation and leakage-control contract

This page defines when information may enter a prediction, how chronological evaluation was constructed, and why the 2026 results are development evidence rather than a final untouched test.

## Prediction setting

The intended prediction point is **after the official starting lineups and starting pitchers are known, but before first pitch**.

Information is separated into two categories:

- **Current-game pregame information:** the scheduled matchup, official starting lineups, and starting pitchers may be used because they are known before the game begins.
- **Outcome-derived information:** the target result, box-score events, player performance from the target game, actual relief-pitcher usage, and any other information revealed during or after the game may not be used.

For every historical feature derived from completed games, the latest contributing game date must be strictly earlier than the target game date.

The source-pipeline audits report no current-game, same-date, or future-result use in the historical features. However, official historical records identify who started without providing an independently archived pre-first-pitch capture timestamp for every game. The retrospective study is therefore a **leakage-controlled reconstruction**, not an immutable real-time pregame feed. The prospective protocol provides timestamped evidence for future games.

## Evaluation population

The official foundation contains **1,864 completed games**.

- The canonical records retain **40 ties**, which are excluded from binary home-win modeling under the predefined target rule.
- The final binary modeling dataset contains **1,824 decision games**:
  - **710** from 2024;
  - **698** from 2025;
  - **416** from 2026.
- Cancelled or postponed games are excluded from model evaluation.
- Each eligible game appears once, and the released modeling table is ordered deterministically by `game_date, game_id`.

## Two different evaluation risks

Feature leakage and evaluation-period reuse are related but different problems.

| Risk | Meaning | Status in this project |
|---|---|---|
| Feature leakage | Information from the target outcome, the same date, or the future enters a feature vector | Controlled through strict-prior and same-date exclusion rules |
| Evaluation-period reuse | Observed outcomes are used to choose models, hyperparameters, or training strategies | Present in the V11.1 2025 validation and the V12 2026 training-strategy comparison |

A prediction can be free of target-game leakage while still being evaluated on a period that is no longer an untouched test.

Evaluation-period reuse occurred in two places. In V11.1, a batter candidate developed on 2024 data was examined on 2025, after which the prior-averaging design was reviewed; the final 2025 result is therefore validation evidence rather than an untouched final test. In V12, 2026 outcomes were inspected while regularization, training windows, adaptive strategies, calibration, and ensembles were compared.

## Hard rules

1. Historical outcome-derived features may use only games with dates strictly earlier than the target game date.
2. The target game's outcome, box-score events, and player results are excluded from its feature vector.
3. Results from every other game on the same calendar date are also excluded.
4. The first game of a same-day doubleheader is not used when constructing features for the second game.
5. Current-game lineups and starting pitchers may be used only as pregame inputs; pitchers who actually appear in relief may not be used.
6. All feature rows for a calendar date are frozen before that date's completed games are added to history.
7. For adaptive methods, predictions for every game on a date are generated before any outcome from that date is added to the training history.
8. Imputation, scaling, feature selection, model fitting, calibration, and other learned transformations are fitted only on the corresponding training rows.
9. Missing historical coverage and cold starts are represented through prior-count, coverage, and missing-value fields with train-fitted preprocessing; later outcomes are never used to fill earlier gaps.
10. Primary model conclusions use chronological evaluation. Random shuffled train-test splits and random K-fold validation are not used.
11. Cancelled and postponed games are excluded from modeling and evaluation. Tied games remain in the canonical records but are excluded from the binary target under the predefined rule.

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
- validation outcomes are not used to fit the corresponding fold model.

| Fold | Training period | Validation period | Training games | Validation games |
|---:|---|---|---:|---:|
| 1 | 2024-03-23 to 2024-07-11 | 2024-07-12 to 2024-09-06 | 422 | 210 |
| 2 | 2024-03-23 to 2024-09-06 | 2024-09-07 to 2025-04-22 | 632 | 195 |
| 3 | 2024-03-23 to 2025-04-22 | 2025-04-23 to 2025-06-19 | 827 | 232 |
| 4 | 2024-03-23 to 2025-06-19 | 2025-06-20 to 2025-08-14 | 1,059 | 180 |
| 5 | 2024-03-23 to 2025-08-14 | 2025-08-15 to 2025-10-02 | 1,239 | 167 |

Across the five folds, **984 games** receive out-of-fold validation predictions. The earliest **422 games** form the initial training block, and the two decision games on 2025-10-04 fall outside the published validation blocks. After model selection, the CV-selected reference model is refitted on all **1,408 decision games** from 2024–2025.

The machine-readable fold definition is published in [`data/derived/V12_TEMPORAL_FOLD_DEFINITION.csv`](../data/derived/V12_TEMPORAL_FOLD_DEFINITION.csv).

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
- **The `L2_C0.1_RECENT_720` specification is the best observed development model, not a future-validated champion.**
- **A final generalization claim requires predictions recorded before first pitch on games whose outcomes were unavailable during development.**

The `L2_C0.03_ALL_EQUAL` reference model was chosen using the 2024–2025 temporal folds without using 2026 outcomes for model selection. Its later 2026 evaluation is scientifically cleaner than a specification selected through 2026 comparison, but 2026 is still an already observed period for the project as a whole.

Detailed model comparisons are documented in [model selection, ablation, and calibration](model_selection_ablation_and_calibration.md). Claim boundaries are summarized in [scientific status and allowed claims](scientific_status_and_claims.md), and the rules for future evidence are documented in [prospective validation](prospective_validation.md).

## Paired date-cluster uncertainty

Games played on the same date may share calendar-level scheduling and league-wide conditions, so game rows are not treated as fully independent.

Model differences are evaluated with a paired date-cluster bootstrap:

1. unique game dates are sampled with replacement;
2. every game belonging to each sampled date is included;
3. both models are evaluated on the same sampled games;
4. the paired Log loss difference is calculated;
5. the procedure is repeated to form a percentile interval and the proportion of bootstrap replicates with lower Log loss (`Δ Log loss < 0`).

All games from a sampled date are concatenated rather than first reducing each date to a single average. This preserves game-level weighting when dates contain different numbers of games. The returned `improvement_probability` field is this bootstrap replicate proportion; it is not a Bayesian posterior probability that the new model is truly superior.

The implementation is available in [`src/fifteenpick_prediction/bootstrap.py`](../src/fifteenpick_prediction/bootstrap.py).

These intervals quantify uncertainty in the observed paired performance difference under the stated resampling design. The date-cluster design accounts for dependence among games played on the same date, but it does not model serial dependence across adjacent dates. The intervals also do not remove uncertainty caused by model selection, repeated inspection of an evaluation period, future season shifts, or changes in team composition.

## Evidence and verification scope

The public release directly verifies:

- deterministic ordering by `game_date, game_id`;
- one row per binary decision game;
- same-date team-update and player-result exclusion flags;
- the published temporal-fold definition;
- the paired date-cluster bootstrap implementation.

The source pipeline additionally recorded **0 current-game uses**, **0 same-date result uses**, and **0 temporal-order violations** during historical feature construction. The intermediate row-level history tables needed to reconstruct every contributing source date are not fully redistributed in the public repository.

This contract does not establish that:

- every historical lineup was independently captured and timestamped before first pitch;
- 2026 was an untouched final test;
- observed development performance will necessarily persist in future seasons.

## Verification resources

The timing rules and published checks can be inspected in the following repository files:

- [temporal fold definition](../data/derived/V12_TEMPORAL_FOLD_DEFINITION.csv);
- [temporal ordering and strict-prior helpers](../src/fifteenpick_prediction/temporal.py);
- [fail-closed dataset validation](../src/fifteenpick_prediction/validation.py);
- [paired date-cluster bootstrap](../src/fifteenpick_prediction/bootstrap.py);
- [portable dataset-validation result](../reports/reproduced/dataset_validation.json);
- [final modeling and leakage audit](../reports/frozen/V12_REPRODUCIBILITY_AND_LEAKAGE_AUDIT.json);
- [strict-prior and recent-window tests](../tests/test_temporal.py);
- [deterministic temporal-order tests](../tests/test_temporal_v16.py);
- [dataset-contract tests](../tests/test_dataset_validation.py);
- [fail-closed validation tests](../tests/test_validation_failures.py);
- [bootstrap tests](../tests/test_bootstrap.py).