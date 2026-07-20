# Temporal Validation and Leakage Controls

## Prediction setting

The target setting is lineup-confirmed pregame forecasting:

- official starting nine for each team
- official starting pitcher for each team
- information available before the target game

## Hard temporal rules

1. `source_game_date < target_game_date`
2. Target-game box-score events are never features.
3. All games on the target date are excluded from history.
4. Doubleheader Game 1 is not used for Game 2 on the same date.
5. Imputation, scaling, feature selection, and calibration are fit on training data only.
6. Primary evaluation uses temporal splits, never shuffled K-fold validation.
7. Cancelled games are excluded or voided.
8. Actual target-game relief pitchers are never used as pregame predictors.

## Evaluation roles

- **2024–2025 temporal CV:** model-family and regularization comparison.
- **2026 retrospective development evaluation:** leakage-controlled, but repeatedly observed during research.
- **Future prospective evaluation:** required for a final confirmatory claim.

## Metrics

Primary:

- Log loss
- Brier score

Secondary:

- ROC AUC
- Accuracy
- Calibration bins
- Calibration intercept and slope

Uncertainty uses paired date-cluster bootstrap because games on the same day are not treated as independent resampling units.
