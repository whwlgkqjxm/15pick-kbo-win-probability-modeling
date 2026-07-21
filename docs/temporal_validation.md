# Temporal Validation and Leakage Controls

## Prediction setting

The target is the home-team win probability after official starting lineups and starting pitchers are known but before first pitch.

## Hard temporal rules

1. Every historical source date must be strictly earlier than the target game date.
2. Target-game box-score events are never features.
3. All games on the target date are excluded from historical aggregates.
4. Doubleheader Game 1 is not used for Game 2 on the same date.
5. Imputation, scaling, feature selection, and calibration are fitted on training data only.
6. Primary model comparison uses chronological splits rather than shuffled K-fold validation.
7. Cancelled games are excluded or voided.
8. Actual target-game relief pitchers are never used as pregame predictors.
9. Ties are excluded from the binary target.

## Evaluation roles

- **2024–2025 temporal comparison:** model-family and regularization selection
- **2026 retrospective development evaluation:** leakage-controlled but repeatedly observed during research
- **future prospective ledger:** required for confirmatory generalization

## Metrics

Primary:

- Log loss
- Brier score
- calibration intercept and slope
- reliability bins

Secondary:

- ROC AUC
- threshold accuracy

## Uncertainty

Paired differences are bootstrapped by game date rather than by individual game. This preserves same-day clustering and compares candidate and baseline losses on the same resampled dates.

## Scientific interpretation

Leakage control makes the retrospective result more credible, but it does not turn a repeatedly observed development period into an untouched test set. Model selection history must therefore be considered when interpreting 2026 performance.
