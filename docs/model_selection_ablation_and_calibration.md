# Model selection, ablation, and calibration

## Model-family selection

V12 held the V11.1 batter representation fixed and compared regularized logistic regression, elastic net, random forest, extra trees, gradient boosting, histogram gradient boosting, XGBoost, LightGBM, CatBoost, online SGD, ensembles, and calibration methods.

The 2024–2025 temporal-CV champion was L2 Logistic Regression with `C=0.03`. Complex tree and boosting families did not produce better temporal probability quality in this sample.

![Temporal CV](../reports/figures/model_family_temporal_cv.png)

## Learning strategies

The study compared all-history equal weighting, 2025-only, recent 720/1080 games, season weighting, half-life decay, expanding daily retraining, rolling daily retraining, decay-weighted daily retraining, online updates, mean/median ensembles, logit stacking, and Platt/isotonic calibration.

The best observed 2026 method was static L2 `C=0.1` on the most recent 720 pre-2026 decision games. This choice used 2026 comparison information and is therefore a development result.

![Learning strategies](../reports/figures/training_strategy_comparison.png)

## Role-specific ablation

The portable reproduction compares four nested feature sets under the identical model and training rule:

1. conventional team and post-starter features;
2. conventional + batter index;
3. conventional + starter index;
4. conventional + batter + starter indices.

The combined model performed best, while batter-only and starter-only each improved over the no-player baseline. This supports complementary role-specific information rather than a single-role artifact.

## Calibration

Probability quality is evaluated with Log loss and Brier score, supplemented by reliability bins and calibration intercept/slope. AUC measures ranking, and accuracy is secondary.

![Calibration](../reports/figures/calibration_reliability.png)

## Feature importance

Permutation importance is reported for the CV-selected model evaluated on 2026. Importance is descriptive, not a causal effect. Correlated features can share or mask importance.

![Permutation importance](../reports/figures/permutation_importance.png)
