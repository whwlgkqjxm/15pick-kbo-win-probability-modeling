# V9–V10 — Post-starter and official game-page features

## Hypothesis

Can recent team post-starter prevention, workload, matchup, and lineup context improve probability quality?

## Data and protocol

Recent-window post-starter candidates and a stricter 2025 holdout feature lab.

The experiment follows the date-level strict-prior contract applicable at that stage. Protocol differences are not hidden; absolute metrics from different protocols are not ranked as if they were one common leaderboard.

## Result

Recent-20 was a modest challenger; V10 accuracy increased but Log loss/Brier worsened.

## Decision

Retain probability-first V9-style; reject V10 as primary.

## What changed next

Accuracy and probability quality can disagree.

## Reproducibility status

See `research_records/control/MASTER_EXPERIMENT_LEDGER_v15.csv` for artifact status and the relevant exact reports, decision JSON files, and result CSVs under `research_records/` and `reports/frozen/`.
