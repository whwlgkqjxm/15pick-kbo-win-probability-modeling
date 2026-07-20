# Prospective Validation Plan

For every future game after model freeze:

1. Capture official lineup and starter snapshots before first pitch.
2. Store source cutoff timestamps and input hashes.
3. Generate conventional, starter-income, and batter-income features.
4. Save model version, model hash, feature schema, and predicted probability.
5. Never modify the original prediction record.
6. Join the outcome only after game completion.
7. Void cancelled games.

Primary comparison:

- frozen full-income model
- frozen no-income model

Metrics:

- Log loss
- Brier score
- calibration intercept and slope
- reliability bins
- ROC AUC
- accuracy
- date-cluster confidence intervals

No model update should occur until a predeclared sample threshold is reached.
