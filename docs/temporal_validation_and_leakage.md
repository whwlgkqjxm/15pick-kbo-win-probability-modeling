# Temporal validation and leakage contract

## Hard rules

1. Feature source dates must be strictly earlier than the target game date.
2. Target-game outcomes are excluded.
3. All outcomes on the same calendar date are excluded.
4. A same-day doubleheader's first game is not used to predict the second game.
5. Preprocessing is fitted only within training rows.
6. Random shuffled splits are prohibited for primary conclusions.
7. Target-game actual relievers are prohibited.
8. Cancelled games are void/excluded.
9. Adaptive predictions for all games on a date are frozen before that date's outcomes are added.

## Temporal CV

The 2024–2025 model-family comparison uses expanding temporal folds. The fold definition is published in `data/derived/V12_TEMPORAL_FOLD_DEFINITION.csv`.

## 2026 interpretation

No 2026 target outcome enters its own feature vector, and no same-date result is used. However, 2026 results were observed when comparing windows and learning strategies. Therefore:

- “within-game and same-date leakage controlled” is correct;
- “2026 is a final untouched test” is incorrect;
- the recent-720 specification is a development champion;
- future prospective predictions are required for a final generalization claim.

## Uncertainty

Game rows on the same date may share weather, scheduling, league-wide context, and operational timing. Paired uncertainty is therefore estimated by resampling dates and concatenating all games belonging to each sampled date. The implementation is in `src/fifteenpick_prediction/bootstrap.py`.
