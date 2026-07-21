# Model and Training-Strategy Selection

## Candidate model families

- L2 logistic regression
- Elastic Net logistic regression
- Random Forest
- Extra Trees
- Gradient Boosting
- Histogram Gradient Boosting
- XGBoost
- LightGBM
- CatBoost
- probability blending, stacking, and calibration

## Temporal learning strategies

- all eligible history with equal weight
- most recent 720 games
- most recent 1,080 games
- recent-season weighting
- exponential time decay
- daily expanding refit
- daily rolling-window refit
- online updates
- calibrated and stacked probabilities

## Selection principle

Model selection is probability-first. Log loss and Brier score take priority over threshold accuracy because the system produces win probabilities. All preprocessing is fitted inside the training period.

## Selected specifications

### Temporally CV-selected specification

- model: L2 logistic regression
- `C = 0.03`
- training: all eligible 2024–2025 rows
- selection: temporal comparison without using 2026 labels in the model-family search

### Best observed development specification

- model: L2 logistic regression
- `C = 0.1`
- training: most recent 720 eligible decision games before the evaluation cutoff
- features: 6 conventional team/context variables, 4 starting-pitcher index variables, 4 batter index variables

The recent-720 model is the strongest observed development candidate, not a final production champion, because its selection used repeated inspection of 2026 outcomes.

## Why a simpler model won

Regularized logistic regression produced more stable out-of-time probabilities than several higher-capacity tree and ensemble methods. The available sample size, correlated features, seasonal drift, and probability-calibration objective likely favored stronger regularization.

The negative result for complex models is part of the research finding: additional capacity did not compensate for limited independent seasons and changing baseball conditions.
