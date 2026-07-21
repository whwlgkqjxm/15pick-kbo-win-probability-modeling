# Research journey: from failed limited-sample modeling to prospective freeze

This document records why each phase existed, what evidence changed the direction, and which conclusions remain valid.

## Phase 1 — 2026-only limited sample

The project began with 424 completed 2026 games through July 9 and 416 binary decisions after ties. Batter, pitcher, fantasy-score, team, starter, lineup, rank, price, and nonlinear model branches were attempted.

The most favorable development point estimate remained weak: `RANK_ADAPTIVE_V1` produced Log loss `0.685090`, Brier `0.246008`, AUC `0.573867`, and predictions concentrated near 0.5. A later research-grade model with 337 features and thousands of effect candidates degraded to Log loss `0.693281`.

**Decision:** close Phase 1 as a valid negative result. Do not continue adding candidates to the same repeatedly inspected sample. Build a multi-season official foundation.

## Phase 2 foundation — official 2024–2026 data

The next stage collected and canonicalized official schedule and BoxScore records for 1,864 completed games. It created 47,353 batter occurrences, 18,201 pitcher occurrences, 33,552 official starting-lineup rows, and 65,554 player-game occurrences.

Identity resolution was not treated as a name join. Numeric player IDs, official profile evidence, season-team evidence, daily identity evidence, and occurrence-level fingerprints were used. Final resolution was 65,554/65,554 with zero name-only forced merges.

Scoring parity audits found strikeout token omissions, stolen-base suffix interpretation differences, double-play detail differences, five legacy wrong-player-ID rows, display-name formatting differences, and a stale 2026-07-08 snapshot. Corrected data was created without overwriting legacy evidence.

## V1 — first lineup-confirmed temporal model

V1 tested whether prior-average income features added signal to a team baseline. The income models improved point estimates, but date-cluster bootstrap intervals included zero. The result was promising but inconclusive.

## V2 — stabilized average-income model

V2 added train-fitted median imputation, missing indicators, scaling, previous-season information, K-shrunk cross-season averages, and lineup-position aggregates. It improved 2026 post-hoc Log loss from V1 Extended `0.680663` to `0.670610`.

**Decision:** preserve V2 as the historical stabilized baseline.

## V3 — broad complex-model search

V3 evaluated 763 candidate columns, 162 selected features, 9 model families, 37 configurations, and roughly 610 temporal fits. The resulting ensemble produced Log loss `0.677185`, worse than V2 `0.670610`.

**Decision:** reject complexity without improved probability quality. Preserve the negative result.

## V4 — training-strategy lab

Time decay, recent windows, online expanding retraining, season-adaptive blending, median/mean ensembles, learned stacking, and an initial Poisson branch were compared using the then-current feature set. None improved over V2.

**Decision:** weighting and retraining cannot repair a deficient representation by themselves.

## V5 — ceiling audit and suspended conclusion

An initial ceiling audit suggested performance flattened after roughly 600 games and that 224 additional features could not predict V2 errors. The tentative interpretation was that remaining BoxScore information might have little incremental value.

That conclusion was later suspended. A role-scope audit showed the feature construction itself was contaminated. A ceiling measured on contaminated histories could not be treated as a ceiling of the corrected research question.

**Decision:** explicitly retract the final ceiling claim rather than defend it after its assumptions failed.

## Role-scope audit — the pivotal correction

The history key separated season, player, and position type but not role. Consequently:

- 25,870 of 33,121 experienced starting-batter rows included substitute history (`78.11%`);
- 726 of 3,496 experienced starting-pitcher rows included relief history (`20.77%`);
- among 614 pitchers with both roles, the median absolute all-role versus start-only mean difference was `149.14` and the 90th percentile was `779.51`.

**Decision:** build parallel all-role and role-specific histories; redesign the starting-pitcher and relief representations.

## V6 — official performance-index design

Six official-record scoring families were compared. The selected `KBO_CONSTRAINED` starter score was start-only and based on outs, strikeouts, home runs allowed, walks, and hit by pitch. The baseline-plus-new-starter model improved 2025 Log loss by `−0.009401`, with a bootstrap interval excluding zero.

**Decision:** freeze the clean starter score as the best starter-index candidate.

## V7 — applying the index to prediction

Sixteen prior-average candidates and several application methods were compared. The best historical integration separated the V2 model and the clean starter-income model, then combined their out-of-fold logits. The 2025 temporal OOF Log loss improved from `0.678417` to `0.669483`.

**Decision:** maintain independent role signals rather than forcing every feature into one unregulated model.

## V8 — first batter and relief systems

A selected batter candidate improved its standalone team baseline slightly, but adding it to the V7 stack worsened 2025 Log loss. A player-level relief index was effectively null in the standalone domain and worsened the stack.

**Decision:** reject both additions to the primary model. Do not interpret this as proof that batting or relief pitching lacks value; interpret it as failure of the tested representations.

## V9 — team-level post-starter run prevention

The user proposed replacing uncertain player-level relief scores with team performance after the starter. Audit showed the cumulative responsibility-run version was mathematically identical to an existing bullpen-strength feature. Recent-window alternatives were evaluated, and a recent-20 responsibility-runs-per-game feature became the strongest observed challenger.

**Limitation:** official responsibility runs are not identical to all physical runs scored after the actual starter exits. Exact physical post-exit runs require play-by-play substitution and scoring timelines.

## V10 — official game-page feature lab

Starter workload, pitch count, bat/throw handedness, lineup sections, order, continuity, missing-regular proxies, and stacking were tested under a stricter 2025 holdout protocol. The combined model gained accuracy but worsened Log loss and Brier versus V9-style.

**Decision:** keep V9-style probability architecture; retain V10 only as an accuracy-oriented challenger. Probability models are not selected by accuracy alone.

## V11.1 — complete batter-index rebuild

The earlier batter branch was replaced. No legacy batter income was used. Official batting events produced 215 score candidates, 30 full temporal score searches, 18 top scores × 20 average methods, 6 lineup blocks, linear and nonlinear model families, direct integration, blending, stacking, and ensemble methods.

The selected system was:

- score: `POWER_OBP__RATE100`;
- prior average: `S_K5`;
- lineup aggregation: official-nine-player `MEAN` block.

Against a clean no-batter model on 2025 validation, the new batter model improved Log loss by `−0.003934`, with an 87.84% improvement probability. The interval included zero, so the result was not overstated.

## V12 — machine learning and learning-strategy comparison

The V11.1 batter structure was held fixed while model families and learning strategies were compared. The 2024–2025 temporal-CV champion was L2 Logistic Regression `C=0.03`. On 2026 development evaluation, the best observed strategy was L2 `C=0.1` trained on the most recent 720 decision games.

The best observed combined model achieved Log loss `0.666135`. Removing only the new batter block worsened Log loss to `0.673157`; the paired-date bootstrap interval for the difference excluded zero.

Complex tree/boosting families and frequent adaptive retraining did not improve probability quality in this data regime.

## Current freeze

Two specifications are preserved:

1. `L2_C0.03_ALL_EQUAL`: selected without 2026 using 2024–2025 temporal CV.
2. `L2_C0.1_RECENT_720`: strongest observed 2026 development method, selected after inspecting 2026.

The next scientific stage is not another 2026 tuning loop. It is an immutable prospective prediction ledger with separate postgame settlement and predefined metrics.
