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

## V5 — ceiling audit, role contamination, and research pivot

An initial ceiling audit suggested that performance flattened after roughly 600 games and that 224 additional features could not predict V2 errors. The tentative interpretation was that the remaining BoxScore information might contain little incremental signal.

A role-scope audit then invalidated that premise. The history key separated season, player, and broad position type, but did not separate starting from substitute batting appearances or starting from relief pitching appearances. As a result:

- 25,870 of 33,121 experienced starting-batter rows included substitute history (`78.11%`);
- 726 of 3,496 experienced starting-pitcher rows included relief history (`20.77%`);
- among 614 pitchers with both roles, the median absolute difference between all-role and start-only averages was `149.14`, and the 90th percentile was `779.51`.

The earlier models had therefore tested contaminated batter and starter histories, not clean role-specific representations. The bullpen feature at that stage was a team-level prior run-prevention measure, not a player-level relief-pitcher index. A ceiling measured on those features could not answer the corrected research question.

**Decision:** withdraw the ceiling claim, rebuild role-specific histories from official records, and evaluate batter, starter, and relief representations separately. This was the main turning point from model tuning to feature redesign.

## V6 — role-specific redesign and starter-index selection

V6 compared six official-record scoring families under role-aware strict-prior construction. The purpose was not only to choose a formula, but to identify which role was responsible for any incremental improvement.

In the 2025 domain ablation against the same team baseline:

| Added role block | Difference in Log loss | Interpretation |
|---|---:|---|
| Clean start-only pitcher index | `−0.009401` | Improved; 95% interval `[−0.014817, −0.003986]` |
| Starting-lineup batter index | `+0.000417` | No improvement |
| Player-level relief-pitcher index | `+0.000967` | No improvement |

The gain came almost entirely from correcting and redesigning the starting-pitcher representation. The selected `KBO_CONSTRAINED` score used only prior starts and combined outs, strikeouts, home runs allowed, walks, and hit batters. It also showed stronger starter stability and next-game association than the role-aware legacy score.

**Decision:** freeze the start-only `KBO_CONSTRAINED` score with a K=10 prior as the leading starter-index candidate. Do not advance the V6 batter or relief-pitcher formulations.

## V7 — integrating the starter index into prediction

V7 compared 16 strict-prior averaging candidates and several application methods. The strongest structure did not force all variables into one joint feature matrix. It trained the stabilized V2 component and the clean starter-index component separately, then combined their temporal out-of-fold logits.

On 2025 temporal OOF evaluation, Log loss improved from `0.678417` for V2 to `0.669483` for the logit stack. The difference was `−0.008934`; the paired date-cluster 95% interval was `[−0.017472, −0.000544]`, with a `98.14%` probability of improvement.

**Decision:** preserve separate role-specific model components when that structure generalizes better than direct feature concatenation.

## V8 — initial batter and player-level relief negative results

After the starter redesign succeeded, V8 asked whether separately designed batter and player-level relief-pitcher indices could add further value to the V7 structure.

The selected batter candidate improved its standalone domain model from the team baseline `0.687435` to `0.682866`, but standalone performance did not translate into incremental value once the stronger V7 starter structure was present. The 2025 temporal integration results were:

| Model | Log loss | Difference from V7 |
|---|---:|---:|
| V7 starter stack | `0.669483` | — |
| V7 + initial batter index | `0.673388` | `+0.003905` |
| V7 + player-level relief-pitcher index | `0.674253` | `+0.004770` |
| V7 + batter + relief | `0.674833` | `+0.005350` |

Positive differences are worse. The relief block was also effectively null by itself: `0.687444` versus `0.687435` for the team baseline, with a `49.95%` improvement probability.

The batter result indicated that the first search over scoring, prior construction, and lineup aggregation was not robust enough for integration. The relief result was consistent with a deeper pregame representation problem: the starting pitcher and starting lineup are known before first pitch, but the relievers who will actually appear are not. A leakage-safe player-level feature must therefore approximate a candidate pool from earlier appearances, workload, rest, and roster information, which can include pitchers who never enter the target game.

**Decision:** reject both V8 additions. Rebuild the batter index from scratch, and treat the relief result as failure of the tested pregame representation—not evidence that relief pitching is unimportant.

## V9–V10 — team-level bullpen context and richer pregame features

V9 replaced the uncertain player-level relief approach with a team-level post-starter run-prevention representation. An audit first established that its cumulative responsibility-run definition was mathematically identical to the existing `bullpen_strength` feature. Recent windows were then tested, and the recent-20 version modestly improved the V7 architecture from `0.669483` to `0.669004` in 2025 temporal OOF evaluation.

The improvement was small: `−0.000478`, with a 95% interval of `[−0.003102, 0.002145]` and a `64.66%` improvement probability. It therefore remained a challenger rather than a confirmed replacement. The measure is based on runs assigned to non-starters; exact physical runs after the starter exits would require play-by-play substitution and scoring timelines.

V10 then tested starter workload, pitch count, handedness matchups, lineup sections, batting order, continuity, and missing-regular proxies under a stricter protocol that selected settings on 2024 temporal folds and held out the full 2025 season. Within that common protocol, the V9-style model recorded Log loss `0.667336` and Brier score `0.237412`, while the combined V10 model recorded `0.667817` and `0.237603`. Accuracy rose from `58.31%` to `59.74%`, but probability quality worsened.

**Decision:** retain the probability-first V9-style architecture, preserve the recent-20 measure as a modest challenger, and reject the expanded V10 feature set as the primary probability model.

## V11.1–V12 — full batter rebuild, model comparison, and role ablation

V11.1 replaced the failed V8 batter representation rather than patching it. No legacy batter score was used. Official batting events generated 215 game-index candidates; leading scores were crossed with 20 strict-prior averaging methods, six lineup blocks, and linear, nonlinear, stacking, blending, and ensemble approaches.

The selected system used `POWER_OBP__RATE100`, K=5 previous-season shrinkage (`S_K5`), and the mean of the official nine-player starting lineup. On 698 games in the 2025 validation period, Log loss improved from `0.668954` without the batter block to `0.665020` with it. The difference was `−0.003934`, with an `87.84%` improvement probability; the 95% interval `[−0.010585, 0.002925]` still included zero.

V12 then held the rebuilt batter and clean starter definitions fixed while comparing 42 model and training configurations. Strongly regularized logistic regression remained more stable than the tested tree, boosting, ensemble, calibration, and frequent adaptive-retraining alternatives.

Under the best-observed `RECENT_720` development protocol on 416 games in 2026, the role ablation was:

| Feature set | Log loss | Brier score | ROC AUC | Accuracy |
|---|---:|---:|---:|---:|
| Conventional pregame variables | `0.683942` | `0.245313` | `0.575781` | `54.33%` |
| + Batter index only | `0.678611` | `0.242599` | `0.603188` | `57.45%` |
| + Starting-pitcher index only | `0.673157` | `0.239875` | `0.617343` | `57.93%` |
| + Batter and starting-pitcher indices | **`0.666135`** | **`0.236498`** | **`0.635275`** | **`59.62%`** |

The starter block produced the larger standalone gain, while the combined model performed best. Relative to conventional pregame variables, the combined Log-loss difference was `−0.017807`; the paired date-cluster 95% interval was `[−0.033154, −0.002114]`, with a `98.69%` probability of lower Log loss.

The V8 player-level relief-pitcher index was evaluated under an earlier, separate protocol and is therefore not ranked in this V12 role-ablation table.

**Decision:** freeze both the 2026-independent temporal-CV reference model and the best-observed 2026 development model. Stop further tuning on observed 2026 outcomes.

## Current scientific freeze

Two model specifications are preserved:

1. **`L2_C0.03_ALL_EQUAL`** — selected using 2024–2025 temporal cross-validation without 2026 outcomes in model selection; 2026 development Log loss `0.667390`.
2. **`L2_C0.1_RECENT_720`** — the strongest observed 2026 development method after strategy comparison; Log loss `0.666135`.

The first is the cleaner scientific reference candidate. The second is the best observed development candidate. Neither is described as a future-validated production champion.

The next stage is an immutable pregame prediction ledger with separate postgame settlement, predefined metrics, separately versioned future-data challengers, and versioned product-deployment records. These activities are documented in [prospective validation](prospective_validation.md).

## What the research sequence establishes

The final value of the project is not only its best model. It is the auditable sequence of decisions:

- limited-sample failure led to multi-season official-data engineering;
- weak gains led to root-cause auditing rather than unchecked model expansion;
- role contamination led to withdrawal of an earlier scientific claim;
- role-specific redesign isolated a strong starter signal;
- failed batter and relief implementations were preserved and diagnosed rather than hidden;
- the batter representation was rebuilt from official events and retested under a common protocol;
- development evidence was separated from future generalization through a prospective freeze.
