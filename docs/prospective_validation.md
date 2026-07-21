# Prospective Validation Plan

For each future game after model freeze:

1. capture official lineup and starting-pitcher snapshots before first pitch
2. store source timestamps, input hashes, and schema version
3. generate conventional team/context, starting-pitcher index, and batter index features
4. store model version, model hash, and predicted home-win probability
5. prevent edits to the original prediction record
6. join the final outcome only after game completion
7. void cancelled games and exclude ties from binary scoring

## Frozen comparison

- candidate: conventional variables plus batter and starting-pitcher indices
- comparator: identical model and training protocol without player indices

## Evaluation metrics

- Log loss
- Brier score
- calibration intercept and slope
- reliability bins
- ROC AUC
- accuracy
- paired date-cluster confidence intervals

## Stopping and update policy

No model update should occur until a predeclared sample threshold is reached. Any revised model must receive a new version and begin a separate prospective ledger rather than rewriting earlier predictions.
