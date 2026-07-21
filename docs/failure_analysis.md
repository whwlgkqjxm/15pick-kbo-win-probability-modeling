# Failure Analysis and What Changed

## 1. Limited-sample overreach

**Failure:** The first phase used only part of 2026. Candidate probabilities stayed close to 0.5 and could not support a strong deployment claim.

**Correction:** Expand to complete 2024 and 2025 seasons, retain the initial phase as a negative result, and distinguish retrospective development from future confirmation.

## 2. More features did not mean better probabilities

**Failure:** Hundreds of engineered columns and nonlinear ensembles increased variance and worsened Log loss.

**Correction:** Use lower-dimensional role-aware features, strong regularization, and probability-first temporal evaluation.

## 3. Role contamination

**Failure:** Early player histories combined appearances with different responsibilities, including relief work in starting-pitcher histories.

**Correction:** Define role-specific history scopes and audit every target occurrence against its eligible prior appearances.

## 4. Player-level bullpen income

**Failure:** Relief-pitcher income did not improve the team-only bullpen model and worsened the stronger starter stack.

**Diagnosis:** The actual reliever sequence is unknown pregame and depends on game state, leverage, starter duration, matchups, workload, and managerial choice. Individual reliever samples are also small and volatile. Using actual relievers would leak postgame deployment; using a broad possible pool dilutes the signal.

**Correction:** Retain team-level strictly prior post-starter responsibility-run features. Treat probabilistic reliever-appearance modeling as future work.

## 5. Daily adaptive retraining

**Failure:** Expanding and rolling daily updates followed short-term noise and underperformed a fixed recent-window model.

**Correction:** Freeze the recent-720 static development candidate and require future evidence before changing the update policy.

## 6. Accuracy-only improvements

**Failure:** Some feature combinations increased 0.5-threshold accuracy while worsening Log loss.

**Correction:** Treat win probability as the primary output. Choose models using Log loss, Brier score, calibration, and paired uncertainty.

## 7. External benchmark misuse risk

**Failure avoided:** Published baseball accuracy values can look directly comparable even when leagues, units, features, and splits differ.

**Correction:** Use MLB results as contextual target ranges only. The primary scientific comparison remains the within-dataset, same-protocol ablation.
