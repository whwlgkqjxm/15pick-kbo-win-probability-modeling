# V12 — Model, learning strategy, and role ablation

## Hypothesis

Which temporal learning method is most stable when the new batter system is fixed?

## Data and protocol

42 model configurations; static, adaptive, online, calibration, and ensemble methods.

The experiment follows the date-level strict-prior contract applicable at that stage. Protocol differences are not hidden; absolute metrics from different protocols are not ranked as if they were one common leaderboard.

## Result

CV champion L2 C=0.03; best observed development L2 C=0.1 recent-720; combined Log loss 0.666135.

## Decision

Freeze both specifications and stop tuning on 2026.

## What changed next

The next scientific evidence must be prospective.

## Reproducibility status

See `research_records/control/MASTER_EXPERIMENT_LEDGER_v15.csv` for artifact status and the relevant exact reports, decision JSON files, and result CSVs under `research_records/` and `reports/frozen/`.
