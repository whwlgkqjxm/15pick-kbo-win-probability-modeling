# V4 — Training-strategy negative result

## Hypothesis

Can decay, recent windows, online retraining, ensembles, or Poisson modeling improve the existing representation?

## Data and protocol

Time decay, recent 400/700/1000 windows, expanding online, blends, stack, Poisson.

The experiment follows the date-level strict-prior contract applicable at that stage. Protocol differences are not hidden; absolute metrics from different protocols are not ranked as if they were one common leaderboard.

## Result

No strategy beat V2.

## Decision

Do not treat learning strategy as a substitute for feature correctness.

## What changed next

Representation quality remained the bottleneck.

## Reproducibility status

See `research_records/control/MASTER_EXPERIMENT_LEDGER_v15.csv` for artifact status and the relevant exact reports, decision JSON files, and result CSVs under `research_records/` and `reports/frozen/`.
