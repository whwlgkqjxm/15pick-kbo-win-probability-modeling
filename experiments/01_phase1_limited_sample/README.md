# Phase 1 — 2026-only limited-sample experiment

## Research question

Could official 2026 KBO data support stable pregame win-probability prediction?

## Data

- Completed games: `424`
- Decision games: `416`
- Temporal outer predictions: `281`

All target-game features were constructed from information available before the target game date.

## Result

The strongest development candidate, `RANK_ADAPTIVE_V1`, recorded:

- Log loss: `0.685090`
- Brier score: `0.246008`
- ROC AUC: `0.573867`

Predicted probabilities remained concentrated near `0.5`. A later research-grade model using 337 features and a broader effect search recorded Log loss `0.693281`.

## Decision

The 2026-only branch was closed as a negative result. Further model development was moved to an official 2024–2026 multi-season foundation.

## Evidence

- [`MASTER_EXPERIMENT_LEDGER_v15.csv`](../../research_records/control/MASTER_EXPERIMENT_LEDGER_v15.csv)
- [`research_journey.md`](../../docs/research_journey.md)
- [`failure_root_cause_ledger.md`](../../docs/failure_root_cause_ledger.md)
