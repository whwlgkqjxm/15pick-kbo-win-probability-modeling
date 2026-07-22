# Prospective validation and future results

## Purpose

The 2026 results are development evidence. The predictions contain no target-game or same-date data leakage, but 2026 outcomes were inspected during model and training-strategy comparison. The next stage therefore evaluates the frozen pipeline on future games whose outcomes were not available during development.

## Questions still requiring validation

1. Do the batter and starting-pitcher indices continue to improve Log loss over conventional pregame variables?
2. Does the starting-pitcher index remain stronger than the batter index when each is tested separately, and does the combined model remain best?
3. Which frozen model candidate performs better in prospective evaluation?
4. Do calibration and predictive performance remain stable as new games and seasons introduce data drift?

## Frozen model candidates

| Specification | Frozen training rule | Role |
|---|---|---|
| `L2_C0.03_ALL_EQUAL` | all 2024–2025 decision games, `C=0.03` | CV-selected reference candidate |
| `L2_C0.1_RECENT_720` | most recent 720 pre-2026 decision games, `C=0.1` | best observed development candidate |

Within these candidates, the feature definitions, player-index formulas, preprocessing rules, regularization values, and training windows are fixed. Any new idea must be introduced as a separately versioned challenger rather than silently replacing a frozen candidate.

## Immutable pregame ledger

For every eligible game, the following fields are written before first pitch:

- game ID and scheduled first pitch;
- prediction timestamp and source cutoff timestamp;
- official lineup and starting-pitcher snapshot hashes;
- feature schema version and feature-row hash;
- model ID and model binary hash;
- predicted home-win probability from each frozen candidate;
- no outcome field in the initial prediction record.

## Postgame settlement

Game outcomes are stored separately and joined only after completion. The original pregame record is never overwritten. Cancelled or postponed games are void. Tie handling and evaluation checkpoints must be declared before the corresponding results are calculated.

## Evaluation plan

The primary metric is **Log loss**. The required paired comparisons are:

- batter and starting-pitcher indices combined versus conventional pregame variables;
- batter index only versus conventional pregame variables;
- starting-pitcher index only versus conventional pregame variables;
- `L2_C0.03_ALL_EQUAL` versus `L2_C0.1_RECENT_720`.

Secondary evaluation includes Brier score, calibration intercept and slope, reliability bins, ROC AUC, accuracy, paired date-cluster bootstrap intervals, and data-drift diagnostics. Prospective outcomes are not used for retrospective tuning of the frozen candidates.

## Prospective validation record

Future checkpoints and results will be appended here without replacing earlier records.

| Checkpoint | Prediction period | Eligible games | Data cutoff | Main result | Status |
|---|---|---:|---|---|---|
| Protocol definition | Before the first prospective prediction | 0 | Frozen pregame pipeline | No prospective result yet | Documented |
| First prospective checkpoint | To be declared before evaluation | — | — | — | Pending |
| Confirmatory checkpoint | To be declared before evaluation | — | — | — | Pending |

Until prospective evidence is recorded, claims remain limited to the development results described in [scientific status and allowed claims](scientific_status_and_claims.md).
