# V1–V2 — Prior-average signal and stabilization

## Hypothesis

Do prior-average player-performance features improve a team baseline?

## Data and protocol

2024 train, 2025 validation, 2026 observed evaluation.

The experiment follows the date-level strict-prior contract applicable at that stage. Protocol differences are not hidden; absolute metrics from different protocols are not ranked as if they were one common leaderboard.

## Result

V1 direction was positive but inconclusive; V2 improved 2026 Log loss to 0.670610.

## Decision

Preserve V2 as the historical stabilized baseline.

## What changed next

Shrinkage, previous-season centers, missing indicators, and structured lineup summaries improved stability.

## Reproducibility status

See `research_records/control/MASTER_EXPERIMENT_LEDGER_v15.csv` for artifact status and the relevant exact reports, decision JSON files, and result CSVs under `research_records/` and `reports/frozen/`.
