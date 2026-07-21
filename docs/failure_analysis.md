# Failure Analysis and Corrective Decisions

## 1. Limited one-season development

**Observed problem:** A 2026-only model produced weak discrimination and compressed probabilities.

**Correction:** Expand the foundation to official multi-season data and use temporal validation.

## 2. High-dimensional model search

**Observed problem:** Broad feature expansion and complex machine-learning families worsened out-of-time Log loss relative to regularized logistic regression.

**Correction:** Prefer probability-first selection, strong regularization, and explicit feature-group ablation.

## 3. Role-contaminated histories

**Observed problem:** Early histories mixed official starting batters with substitutes and starting-pitcher appearances with relief appearances.

**Why it matters:** Workload, expected opportunity, and performance context differ by role, so pooled histories change the meaning of the index.

**Correction:** Build official-lineup batter histories and start-only pitcher histories.

## 4. Player-level relief-pitcher index

**Observed problem:** The feature produced null or worse Log loss in every reported comparison.

**Diagnosis:** Reliever identity is not known before the game, actual usage is outcome-dependent, roster-wide aggregation dilutes the relevant arms, and availability varies with recent workload and recovery.

**Correction:** Exclude the player-level relief feature and retain team-level strict-prior post-starter run-prevention measures.

## 5. Daily retraining

**Observed problem:** Daily expanding and rolling refits did not outperform the fixed recent-720 strategy.

**Correction:** Keep the simpler frozen-window candidate and reserve adaptive retraining for prospective testing.

## 6. Apparent predictability ceiling

**Observed problem:** An early audit suggested the feature set was near a ceiling.

**Correction:** Suspend the conclusion after discovering role contamination. The later role-aware rebuild improved performance, showing that representation quality—not only model capacity—was limiting the earlier system.

## 7. External benchmark overinterpretation

**Risk:** Published MLB accuracy values can appear directly comparable even when league, unit of analysis, features, and validation differ.

**Correction:** Use MLB results as contextual targets only. The primary evidence remains the same-dataset, same-protocol candidate-versus-baseline ablation.
