# V7 — Income-to-prediction integration

## Hypothesis

Should role signals be directly merged, blended, or stacked?

## Data and protocol

16 prior-average candidates and five application methods.

The experiment follows the date-level strict-prior contract applicable at that stage. Protocol differences are not hidden; absolute metrics from different protocols are not ranked as if they were one common leaderboard.

## Result

Temporal logit stack improved 2025 OOF Log loss from 0.678417 to 0.669483.

## Decision

Use independent role models and out-of-fold integration where supported.

## What changed next

The application method mattered as much as the score itself.

## Reproducibility status

See `research_records/control/MASTER_EXPERIMENT_LEDGER_v15.csv` for artifact status and the relevant exact reports, decision JSON files, and result CSVs under `research_records/` and `reports/frozen/`.
