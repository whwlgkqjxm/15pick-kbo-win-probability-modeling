# Phase 1 — Limited-sample negative result

## Hypothesis

Could a 2026-only official-data model produce deployable pregame probabilities?

## Data and protocol

424 completed games; 416 binary games; repeatedly observed development folds.

The experiment follows the date-level strict-prior contract applicable at that stage. Protocol differences are not hidden; absolute metrics from different protocols are not ranked as if they were one common leaderboard.

## Result

The strongest point estimate remained weak and compressed; the research-grade model degraded to Log loss 0.693281.

## Decision

Close the branch as a valid negative result and expand to multi-season official data.

## What changed next

The limited sample, repeated teams/dates, adaptive search, and missing contextual data made strong claims indefensible.

## Reproducibility status

See `research_records/control/MASTER_EXPERIMENT_LEDGER_v15.csv` for artifact status and the relevant exact reports, decision JSON files, and result CSVs under `research_records/` and `reports/frozen/`.
