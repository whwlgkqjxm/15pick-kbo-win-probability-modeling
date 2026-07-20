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
- Probability ensembles and stacking

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

The best observed strategy is reported as a development result because its selection used 2026 comparisons.
