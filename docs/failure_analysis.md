# Failure Analysis and What Changed

## 1. Limited-sample overreach

**Failure:** The first phase used only part of 2026. Candidate probabilities stayed close to 0.5 and could not support a strong deployment claim.

**Correction:** Expand to complete 2024 and 2025 seasons and preserve 2026 as a later retrospective interval.

## 2. More features did not mean better probability estimates

**Failure:** Hundreds of engineered columns and nonlinear ensembles increased variance and worsened Log loss.

**Correction:** Use lower-dimensional role-aware features and strong regularization. Select models using temporal probability loss rather than complexity or training fit.

## 3. Role contamination

**Failure:** Early player histories combined appearances with different responsibilities, such as relief work in starting-pitcher histories.

**Correction:** Define role-specific history scopes and audit every target occurrence against its eligible prior appearances.

## 4. Player-level bullpen income

**Failure:** A reconstructed relief-pitcher index did not improve the team-only model.

**Correction:** Do not force every domain into the final model. Retain team-level prior post-starter responsibility-run features instead.

## 5. Daily adaptive retraining

**Failure:** Expanding and rolling daily updates followed short-term noise and underperformed a fixed recent-window model.

**Correction:** Freeze the recent-720 static development candidate and require future evidence before changing the update policy.

## 6. Accuracy-only improvements

**Failure:** Some feature combinations increased 0.5-threshold accuracy while worsening Log loss.

**Correction:** Treat win probability as the primary output. Choose models with Log loss, Brier score, and calibration, not accuracy alone.
