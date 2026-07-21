# Model and Training-Strategy Selection

## Candidate families

- L2 logistic regression
- Elastic Net logistic regression
- Random Forest
- Extra Trees
- Gradient Boosting
- Histogram Gradient Boosting
- XGBoost
- LightGBM
- CatBoost
- Probability ensembles, stacking, and calibration

## Temporal learning strategies

- all history with equal weight
- most recent 720 games
- most recent 1,080 games
- recent-season weighting
- exponential time decay
- daily expanding refit
- daily rolling-window refit
- online update
- calibrated and stacked probabilities

## Selection principle

Model selection is probability-first. Log loss and Brier score take priority over threshold accuracy because the output is a win probability. All preprocessing is fitted inside the training period, and shuffled cross-validation is not used as the primary evidence.

## Selected specifications

### CV-selected model

- L2 logistic regression
- `C = 0.03`
- all available 2024–2025 training games
- selected without using 2026 labels in the V12 model-family search

### Best observed development model

- L2 logistic regression
- `C = 0.1`
- most recent 720 decision games before 2026-03-28
- 14 features: 6 conventional/team variables, 4 starter-income variables, 4 batter-income variables

The recent-720 strategy is a retrospective development champion because its selection used 2026 comparisons.

## External target

The current AUC of 0.635 and accuracy of 59.62% fall within the broad range reported by MLB pregame prediction studies and approach stronger published AUC values near 0.65. This is context, not direct confirmation. The final target is to sustain the result on a frozen prospective ledger.
