# Research journey: from limited-sample failure to a prospective model freeze

This document explains why each research stage was conducted, what evidence changed the project direction, and which conclusions remain scientifically valid. It is a decision history rather than a list of model versions.

For the exact research question and contribution statement, see [research question and contribution](research_question_and_contribution.md). Defects and failed experiments are documented in greater detail in the [failure and root-cause ledger](failure_root_cause_ledger.md).

## Research arc at a glance

| Stage | Main question | Outcome |
|---|---|---|
| Phase 1 | Was the 2026-only sample sufficient? | No; weak temporal performance led to a valid negative result. |
| Phase 2 | Could a reliable multi-season foundation be built? | Yes; 1,864 games and 65,554 player-game records were converted into strict-prior data. |
| V1–V4 | Would stabilized histories or greater model complexity help? | Stabilized priors helped, but complex models and adaptive training did not. |
| V5 audit | Had the model reached its predictive ceiling? | The claim was withdrawn after role-contaminated histories were discovered. |
| V6–V7 | Could a clean starter index improve prediction? | Yes; the start-only index and probability stacking improved Log loss. |
| V8 | Did the initial batter and player-level bullpen indices help? | No; both worsened the integrated model and were rejected. |
| V9–V10 | Could team-level bullpen and richer pregame features help? | The post-starter measure remained a challenger, but the added features did not improve probability quality. |
| V11.1–V12 | Could the batter index be rebuilt and role value compared? | The new batter index added signal; the starter was stronger alone, and both together performed best. |
| Current freeze | What remains? | Frozen models await prospective evaluation on future games. |

## Phase 1 — 2026-only limited-sample study

The project began with 424 completed 2026 games through July 9 and 416 binary decisions after excluding ties. The study explored batter, pitcher, team, starter, lineup, rank, price, and nonlinear modeling branches.

The most favorable development point estimate was still weak. `RANK_ADAPTIVE_V1` produced Log loss `0.685090`, Brier score `0.246008`, and ROC AUC `0.573867`, with most predictions concentrated close to 0.5. A later research-grade model using 337 features and thousands of effect candidates degraded to Log loss `0.693281`.

**Decision:** close Phase 1 as a valid negative result. Repeatedly adding candidates to the same inspected sample would increase selection risk without adding independent information. The project moved to a multi-season official-data foundation.

## Phase 2 foundation — official 2024–2026 data

The next stage collected and canonicalized official KBO schedule and BoxScore records for 1,864 completed games. The resulting foundation contained 47,353 batter occurrences, 18,201 pitcher occurrences, 33,552 official starting-lineup rows, and 65,554 total player-game occurrences.

Player identity was not resolved through a name-only join. Numeric player IDs, official profile evidence, season-team evidence, targeted daily records, and occurrence-level fingerprints were combined. Final identity resolution reached `65,554 / 65,554`, with zero name-only forced merges.

Scoring and source audits identified strikeout-token omissions, stolen-base suffix interpretation differences, double-play detail differences, five incorrect legacy player-ID rows, display-name formatting inconsistencies, and a stale July 8, 2026 snapshot. Corrected analytical data was created without overwriting the historical evidence.

**Decision:** freeze the canonical games, occurrence-level identities, scoring corrections, and strict-prior histories as the research foundation. The full lineage and quality gates are documented in [data lineage and quality](data_lineage_and_quality.md).

## V1 — first lineup-confirmed temporal model

V1 tested whether strict-prior player-performance averages added information to a conventional team baseline. The player-feature models improved the main point estimates, but paired date-cluster bootstrap intervals included zero.

**Decision:** retain V1 as directionally positive but statistically inconclusive evidence. Continue by improving early-season stability and prior construction rather than claiming confirmed incremental value.

## V2 — stabilized player-performance averages

V2 introduced train-fitted median imputation, missing indicators, standardization, previous-season information, K-shrunk cross-season averages, and batting-order aggregates. In the already-observed 2026 period, Log loss improved from V1 Extended `0.680663` to `0.670610`.

This model later became historically important but was not treated as the final clean-role specification because subsequent audits showed that some player histories mixed distinct roles.

**Decision:** preserve V2 as the stabilized historical baseline and as evidence that better prior construction mattered.

## V3 — broad complex-model search

V3 evaluated 763 candidate columns, 162 selected features, nine model families, 37 configurations, and roughly 610 temporal fits. The resulting ensemble produced Log loss `0.677185`, worse than V2 at `0.670610`.

**Decision:** reject complexity when it does not improve probability quality. Preserve the negative result rather than choosing a more sophisticated model for presentation value.

## V4 — learning-strategy lab

The project compared time decay, recent windows, expanding online retraining, season-adaptive weighting, mean and median ensembles, learned stacking, and an initial Poisson branch using the then-current representation. None improved over V2.

**Decision:** conclude that weighting, window changes, and frequent retraining could not repair limitations in the underlying player representation by themselves.

## V5 — ceiling audit and withdrawal of the conclusion

An initial ceiling audit suggested that performance flattened after roughly 600 games and that 224 additional features could not predict V2 errors. The tentative interpretation was that the remaining BoxScore information might contain little incremental signal.

A later role-scope audit invalidated the premise of that conclusion. Because the historical features themselves mixed distinct player roles, a ceiling measured on those features could not be treated as a ceiling of the corrected research question.

**Decision:** withdraw the final ceiling claim after its assumptions failed. The withdrawal was preserved as part of the scientific record rather than hidden.

## Role-scope audit — the pivotal correction

The history key separated season, player, and position type, but did not distinguish starting from substitute batting appearances or starting from relief pitching appearances. As a result:

- 25,870 of 33,121 experienced starting-batter rows included substitute history (`78.11%`);
- 726 of 3,496 experienced starting-pitcher rows included relief history (`20.77%`);
- among 614 pitchers with both roles, the median absolute difference between all-role and start-only averages was `149.14`, and the 90th percentile was `779.51`.

**Decision:** rebuild role-specific histories and redesign the starting-pitcher and relief representations. This audit changed the interpretation of earlier models and became the main turning point of the project.

## V6 — clean starting-pitcher index design

Six scoring families derived from official KBO records were compared. The selected `KBO_CONSTRAINED` starter index used only prior starts and combined outs, strikeouts, home runs allowed, walks, and hit batters.

Adding the clean starter representation to the team baseline improved 2025 Log loss by `−0.009401`, with a paired bootstrap interval excluding zero.

**Decision:** freeze the clean start-only score as the leading starting-pitcher index candidate.

## V7 — integrating the starter index into prediction

Sixteen strict-prior averaging candidates and several application methods were compared. The strongest historical integration kept the stabilized V2 component and clean starter-index model separate, then combined their out-of-fold logits. The 2025 temporal OOF Log loss improved from `0.678417` to `0.669483`.

**Decision:** preserve separate role-specific model components rather than forcing every feature into a single joint-feature model.

## V8 — first batter and relief-pitcher index systems

The first rebuilt batter candidate slightly improved its standalone team baseline, but adding it to the V7 stack worsened 2025 Log loss. The player-level relief-pitcher index was effectively null as a standalone block and also worsened the stack.

**Decision:** do not retain either tested implementation in the primary model. This was interpreted as failure of those specific representations, not evidence that batting or relief pitching is unimportant.

## V9 — team-level post-starter run prevention

The study evaluated a domain-motivated alternative to uncertain player-level relief scores: team performance after the starter. An audit showed that the cumulative responsibility-run version was mathematically identical to an existing bullpen-strength feature. Recent-window alternatives were then compared, and a recent-20 responsibility-runs-per-game feature became the strongest observed challenger.

**Limitation:** official responsibility runs are not equivalent to all physical runs scored after the starter leaves the game. Exact physical post-exit runs require play-by-play substitution and scoring timelines.

## V10 — official game-page feature lab

Starter workload, pitch count, batter and pitcher handedness, lineup sections, batting order, lineup continuity, missing-regular proxies, and stacking were evaluated under a stricter 2025 holdout protocol.

The combined model improved accuracy but worsened Log loss and Brier score relative to the V9-style probability model.

**Decision:** retain the V9-style probability architecture and preserve V10 only as an accuracy-oriented challenger. Accuracy alone was not used to select a probability model.

## V11.1 — complete batter-index rebuild

The earlier batter branch was replaced rather than incrementally patched. No legacy batter score was used. Official batting events were used to construct 215 game-score candidates, followed by 30 full temporal score searches, 18 leading scores crossed with 20 prior-averaging methods, six lineup blocks, linear and nonlinear model families, direct integration, blending, stacking, and ensemble methods.

The selected batter system used:

- game index: `POWER_OBP__RATE100`;
- strict-prior average: `S_K5`;
- lineup aggregation: the mean of the official nine-player starting lineup.

Against a clean no-batter model on 2025 validation, the new batter system improved Log loss by `−0.003934`, with an improvement probability of `87.84%`. The interval included zero, so the result was not described as confirmed superiority.

**Decision:** freeze the rebuilt batter representation as a development candidate and evaluate it within a common final modeling protocol.

## V12 — model, learning-strategy, and role-ablation comparison

The V11.1 batter definition and the clean starter definition were held fixed while model families and training strategies were compared. The 2024–2025 temporal-CV champion was L2-regularized logistic regression with `C=0.03`. After comparing learning strategies on the 2026 development period, the best observed method was L2 logistic regression with `C=0.1`, trained on the most recent 720 pre-2026 decision games.

Under this same `RECENT_720` protocol, the role-ablation results were:

| Feature set | Log loss | Brier score | ROC AUC | Accuracy |
|---|---:|---:|---:|---:|
| Conventional pregame variables | `0.683942` | `0.245313` | `0.575781` | `54.33%` |
| + Batter index only | `0.678611` | `0.242599` | `0.603188` | `57.45%` |
| + Starting-pitcher index only | `0.673157` | `0.239875` | `0.617343` | `57.93%` |
| + Batter and starting-pitcher indices | **`0.666135`** | **`0.236498`** | **`0.635275`** | **`59.62%`** |

The starting-pitcher block produced the larger standalone improvement, while the combined model performed best. Compared with conventional pregame variables, the combined Log-loss difference was `−0.017807`; the paired date-cluster 95% interval was `[−0.033154, −0.002114]`, with a `98.69%` probability of lower Log loss.

The player-level relief-pitcher index was tested under the separate earlier V8 protocol and is therefore not directly ranked in the V12 role-ablation table.

Complex tree and boosting models, as well as frequent adaptive retraining, did not improve probability quality in this data regime.

**Decision:** freeze both the temporal-CV-selected specification and the best-observed development specification. Stop further tuning on 2026 outcomes.

## Current scientific freeze

Two model specifications are preserved:

1. **`L2_C0.03_ALL_EQUAL`** — selected using 2024–2025 temporal cross-validation without using 2026 outcomes for model selection.
2. **`L2_C0.1_RECENT_720`** — the strongest observed 2026 development method, selected after comparing strategies on 2026 results.

The first is the cleaner scientific reference candidate. The second is the best observed development candidate. Neither is described as a future-validated production champion.

The next stage is not another retrospective tuning loop. Future games will be handled through an immutable pregame prediction ledger, separate postgame settlement, predefined evaluation metrics, separately versioned future-data challengers, and versioned product-deployment records. These activities are documented in [prospective validation](prospective_validation.md).

## What the research sequence establishes

The project did not progress through a single uninterrupted sequence of improving scores. Its strongest evidence came from distinguishing different kinds of failure and responding appropriately:

- a small-sample modeling limitation led to multi-season data collection;
- an impossible home-away coverage pattern led to identity repair;
- role-contaminated histories led to withdrawal of an earlier scientific claim;
- failed complex models led to retention of regularized logistic regression;
- failed batter and relief representations led to redesign rather than overgeneralized rejection;
- repeated observation of 2026 results led to an explicit development label and prospective freeze.

The resulting contribution is therefore not only the final model. It is the complete, reproducible path from official-data engineering and defect discovery to role-specific feature design, temporal evaluation, uncertainty reporting, negative-result preservation, and a prospective validation protocol.
