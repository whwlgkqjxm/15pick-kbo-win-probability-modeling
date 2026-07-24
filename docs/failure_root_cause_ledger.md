# Failure analysis and corrective actions

This document records issues that changed the data foundation, feature definitions, validation protocol, model selection, or reported conclusions. Each comparison below uses results produced on the same evaluation protocol; metrics from different stages are not ranked against one another.

`Confirmed` marks a defect, invalid premise, or evaluation conflict established directly from the audits. `Supported explanation` marks a mechanism consistent with the evidence but not isolated as the sole cause. `Evaluation risk` marks a limitation controlled through the study design and future validation.

## Summary

| ID | Problem | Diagnosis | Decision |
|---|---|---|---|
| F01 | Unstable results in the 2026-only branch | Supported explanation | Stop tuning and expand to 2024–2026 data |
| F02 | Home and away starter identities were handled differently | Confirmed defect | Rebuild starter identity resolution and discard affected claims |
| F03 | Valid baseball innings notation failed parsing and validation | Confirmed defect | Represent innings as outs and stop on unresolved schemas |
| F04 | Batter and pitcher histories mixed different game roles | Confirmed defect | Rebuild strict-prior histories by role |
| F05 | Broader feature and model searches performed worse than V2 | Supported explanation | Require temporal probability improvement before adding complexity |
| F06 | The V5 predictive-ceiling claim relied on contaminated features | Confirmed premise failure | Withdraw the claim and redesign the role features |
| F07 | The first batter index failed integrated evaluation | Supported explanation | Rebuild the batter index from official batting events |
| F08 | The player-level relief index added no reliable pregame signal | Supported explanation | Reject the index and keep team-level bullpen context as a challenger |
| F09 | Accuracy improved while probability scores worsened | Confirmed evaluation conflict | Select models primarily by Log loss and Brier score |
| F10 | Adaptive retraining did not beat the best static window | Supported explanation | Preserve the frozen static candidates |
| F11 | Public reproduction code diverged from the frozen V12 execution | Confirmed defect | Restore exact ordering, solver behavior, and replay tests |
| F12 | Source, scoring, identity, and snapshot parity failed | Confirmed defects | Correct derived data while preserving the original evidence |
| F13 | 2026 outcomes were reused during method selection | Evaluation risk | Freeze both models and move to prospective validation |

## F01 — instability in the 2026-only branch

- **Problem:** the 2026-only branch did not produce stable enough pregame probabilities to justify continued search on the same sample.
- **Evidence:** 424 completed games yielded 416 decision games and 281 temporal outer predictions. The strongest development candidate recorded Log loss `0.685090`, Brier score `0.246008`, and ROC AUC `0.573867`, with predictions concentrated near `0.5`. A later 337-feature search recorded Log loss `0.693281`.
- **Diagnosis — supported explanation:** the effective sample was small relative to the number of inspected features, models, and fold choices. Repeated observations of the same teams and dates also limited the amount of independent information. These factors explain the instability collectively; no single cause was isolated.
- **Change:** stop tuning the observed 2026 sample and rebuild the study on official 2024–2026 data.
- **Verified outcome:** the expanded foundation contained 1,824 decision games across three seasons. The Phase 1 result remained documented as a negative result rather than being reinterpreted after the expansion.
- **Records:** [Phase 1 and Phase 2 research history](research_journey.md#phase-1--2026-only-limited-sample-study).

## F02 — home/away starter identity asymmetry

- **Problem:** starter history was available for every home team and no away team in the 416-game model period.
- **Evidence:** starter eligibility was home `416/416` and away `0/416`, an impossible side-specific pattern.
- **Diagnosis — confirmed defect:** home starter tokens often contained numeric KBO IDs, while away tokens often contained names. The original eligibility rule accepted numeric identifiers and rejected the name-based tokens.
- **Change:** combine numeric IDs, unique season-team-name mappings, official profiles, targeted daily evidence, and occurrence-level fingerprints. Name-only forced merges were prohibited.
- **Verified outcome:** all source starters were resolved (`848/848`), and binary-game starter eligibility became home `416/416` and away `416/416`. Claims produced from the asymmetric feature were discarded.
- **Records:** [data lineage and identity checks](data_lineage_and_quality.md).

## F03 — innings parsing and schema-validation failures

- **Problem:** pitcher feature construction stopped on ambiguous innings fields and valid one-third/two-thirds inning notation.
- **Evidence:** preflight validation failed before model fitting instead of silently coercing unresolved values.
- **Diagnosis — confirmed defect:** schema resolution was incomplete, and the parser did not cover every official representation of fractional innings.
- **Change:** represent innings internally as outs, require exact schema matches, test baseball-specific fractions, and stop the pipeline when domain checks fail.
- **Verified outcome:** the corrected 2026 pitcher foundation joined 4,110 pitcher rows and resolved all 832 starter sides in the 416 decision games.
- **Records:** [data lineage and validation checks](data_lineage_and_quality.md).

## F04 — role contamination in player histories

- **Problem:** starting-lineup and starting-pitcher features included prior performance from different roles.
- **Evidence:** `25,870/33,121` starting-batter feature rows with prior history included substitute appearances (`78.11%`), and `726/3,496` starting-pitcher rows with prior history included relief appearances (`20.77%`). Among 614 pitchers with both roles, the median absolute difference between all-role and start-only averages was `149.14`; the 90th percentile was `779.51`.
- **Diagnosis — confirmed defect:** the historical key separated season, player, and broad position type, but did not distinguish starter from substitute batting appearances or starter from relief pitching appearances.
- **Change:** rebuild date-batched strict-prior histories by role and design a start-only pitcher score.
- **Verified outcome:** V2 was retained only as a historical baseline, not as a clean role-specific specification. The corrected histories became the foundation for the V6–V12 role redesign.
- **Records:** [role-scope audit table](../research_records/key_results/ROLE_SCOPE_AUDIT_SUMMARY.csv) and [role-aware audit report](../research_records/reports/RQ1_ROLE_AWARE_INCOME_AUDIT_REPORT.md).

## F05 — complexity without temporal improvement

- **Problem:** a broader feature and model search performed worse than the stabilized V2 model.
- **Evidence:** V3 evaluated 763 candidate columns, selected 162 features, compared nine model families and 37 configurations across roughly 610 temporal fits. Its ensemble Log loss was `0.677185`, compared with V2 at `0.670610`; the estimated probability of improvement was `15.83%`.
- **Diagnosis — supported explanation:** redundant features, limited independent signal, model-selection variance, and excess capacity are consistent with the result, but their separate contributions were not isolated.
- **Change:** require out-of-time probability improvement before accepting additional model or feature complexity.
- **Verified outcome:** V12 again compared linear, tree, boosting, ensemble, calibration, adaptive, and online methods. L2-regularized logistic regression remained the temporal-CV winner.
- **Records:** [V3 research history](research_journey.md#v3--broad-complex-model-search) and [V12 model-family temporal CV](../reports/frozen/V12_MODEL_FAMILY_TEMPORAL_CV.csv).

## F06 — predictive-ceiling claim invalidated

- **Problem:** V5 initially suggested that performance had flattened after roughly 600 games and that 224 additional features could not explain V2 errors.
- **Evidence:** the error-prediction AUC was near `0.5`, and the added features provided little improvement under the existing representation.
- **Diagnosis — confirmed premise failure:** the ceiling audit used the role-contaminated histories identified in F04. It measured the limit of that representation, not the limit of clean batter, starter, and relief features.
- **Change:** withdraw the predictive-ceiling claim and move from model tuning to role-specific feature redesign.
- **Verified outcome:** the clean starter block later improved 2025 Log loss by `−0.009401`, and the rebuilt batter block added signal in subsequent evaluation.
- **Records:** [V5 ceiling audit](../research_records/reports/RQ1_V5_CEILING_AUDIT_REPORT.md), [role-aware audit](../research_records/reports/RQ1_ROLE_AWARE_INCOME_AUDIT_REPORT.md), and [rebuild decision](../research_records/decisions/ROLE_AWARE_REBUILD_DECISION.json).

## F07 — initial batter index failed integrated evaluation

- **Problem:** the initial batter index improved a standalone domain model but worsened the stronger V7 integrated model.
- **Evidence:** the standalone batter model improved from `0.687435` to `0.682866`, but adding it to V7 worsened 2025 Log loss from `0.669483` to `0.673388` (`+0.003905`).
- **Diagnosis — supported explanation:** the first search over score design, prior averaging, and lineup aggregation did not produce a sufficiently robust incremental feature. Overlap with the existing team and starter components is plausible, but was not isolated as the sole cause.
- **Change:** reject the V8 batter addition and rebuild the batter index from official batting events without the legacy batter score.
- **Verified outcome:** V11.1 compared 215 game-index candidates, 20 prior methods, and six lineup blocks. The selected system improved 2025 validation from `0.668954` to `0.665020` (difference `−0.003934`; 95% interval `[−0.010585, 0.002925]`). Under the best-observed 2026 development protocol, the batter block improved Log loss by `−0.007022` with a 95% interval of `[−0.013416, −0.000548]`. The 2026 result remains development evidence because those outcomes were used during method comparison.
- **Records:** [V8 integration results](../research_records/key_results/V8_2025_PREDICTION_APPLICATION_RESULTS.csv), [V11.1 candidate comparison](../reports/frozen/V11_1_ROBUST_CANDIDATE_COMPARISON.csv), and [V12 batter ablation](../reports/frozen/V12_2026_BATTER_ABLATION_RESULTS.csv).

## F08 — player-level relief index failed pregame evaluation

- **Problem:** the tested player-level relief features did not add reliable pregame value.
- **Evidence:** the preliminary V6 relief screen worsened Log loss by `+0.000967`. In V8, the selected relief index was effectively null against the team baseline (`0.687444` versus `0.687435`) and worsened V7 from `0.669483` to `0.674253` (`+0.004770`). A 2026 post-hoc addition also worsened Log loss by `+0.001113`.
- **Diagnosis — supported explanation:** the actual relievers who will appear are unknown before first pitch. A leakage-safe feature must approximate a candidate pool from prior appearances, workload, rest, and roster evidence, which can include pitchers who never enter the game. This is a plausible representation limit, not a uniquely proven cause.
- **Change:** reject the tested player-level relief index. Retain the team-level post-starter measure only as a challenger until stronger point-in-time availability or play-by-play data are available.
- **Verified outcome:** the V9 recent-20 team measure improved V7 by `−0.000478`, but its 95% interval `[−0.003102, 0.002145]` included zero; it was not promoted to a confirmed replacement. The negative player-level result was not interpreted as evidence that relief pitching is unimportant.
- **Records:** [V6 role ablation](../research_records/key_results/V6_1_V2_CHALLENGER_AND_DOMAIN_ABLATION.csv), [V8 domain comparison](../research_records/key_results/V8_DOMAIN_BASELINE_AND_LEGACY_COMPARISON.csv), and [relief-index analysis](relief_pitcher_index_negative_result.md).

## F09 — accuracy and probability scores moved in opposite directions

- **Problem:** the V10 feature set improved classification accuracy while worsening the primary probability metrics.
- **Evidence:** on the strict 2025 holdout, accuracy increased from `58.31%` to `59.74%`, while Log loss worsened from `0.667336` to `0.667817` and Brier score from `0.237412` to `0.237603`. The paired-date 95% interval for the Log-loss difference was `[−0.002909, 0.003879]`; the probability of improvement was `38.475%`.
- **Diagnosis — confirmed evaluation conflict:** accuracy evaluates thresholded class decisions and ignores probability confidence. Log loss and Brier score evaluate the full probability assignment, which was the target of this study. The result alone does not establish miscalibration or overconfidence as a unique mechanism.
- **Change:** keep Log loss and Brier score as the primary model-selection criteria and retain V10 only as an accuracy-oriented challenger.
- **Verified outcome:** the simpler V9-style probability model remained primary under the common 2024-selection/2025-holdout protocol.
- **Records:** [V10 holdout results](../research_records/key_results/V10_2025_UNTOUCHED_HOLDOUT_RESULTS.csv) and [paired-date bootstrap](../research_records/key_results/V10_PAIRED_DATE_BOOTSTRAP.csv).

## F10 — adaptive retraining did not beat the best static window

- **Problem:** expanding, rolling, decay-weighted daily retraining, and online updates did not improve on the strongest static recent-window model.
- **Evidence:** the best adaptive method recorded 2026 development Log loss `0.668838`; the best static recent-720 model recorded `0.666135`. Online SGD variants were substantially worse.
- **Diagnosis — supported explanation:** frequent updates can follow short-term noise when the effective sample is modest and existing features already summarize recent form. The experiments support this explanation but do not isolate it as the sole cause.
- **Change:** do not allow adaptive methods to replace the frozen models automatically; evaluate them as separately versioned challengers.
- **Verified outcome:** the static CV-selected and recent-720 specifications were preserved for prospective comparison.
- **Records:** [V12 adaptive-strategy results](../reports/frozen/V12_2026_ADAPTIVE_STRATEGY_RESULTS.csv).

## F11 — public reproduction drift

- **Problem:** an early public reproduction script did not regenerate the frozen V12 predictions and metrics exactly.
- **Evidence:** the script forced `solver="liblinear"` and ordered the recent training window only by date, producing different probabilities and metrics.
- **Diagnosis — confirmed defect:** the maintained reproduction path had diverged from the historical solver behavior and deterministic `game_date, game_id` ordering used for the frozen results.
- **Change:** remove the solver override, restore two-key ordering, reproduce the original date-cluster bootstrap, and add exact metric and saved-model replay tests.
- **Verified outcome:** reproduced metrics match the frozen values within `1e-12`. The saved models replay the 416 frozen probabilities with maximum absolute errors of `1.67e-16` for the CV model and `2.78e-16` for the development model.
- **Records:** [reproduction procedure](reproducibility.md) and [model replay audit](../reports/frozen/V12_MODEL_BINARY_REPRODUCTION_AUDIT.json).

## F12 — source and scoring parity defects

- **Problem:** canonical replay and the historical 2026 stream disagreed on several player-game scores and identities.
- **Evidence:** the audits found incomplete strikeout-token coverage, stolen-base suffix differences, double-play detail differences, five incorrect legacy player-ID rows, display-name formatting differences, a stale July 8 snapshot, and 127 initially unresolved occurrences.
- **Diagnosis — confirmed defects:** each discrepancy was traced to a specific parsing, identity, formatting, or snapshot problem rather than treated as random noise.
- **Change:** correct analytical tables from official evidence while preserving the original historical stream and audit trail.
- **Verified outcome:** all `65,554/65,554` player-game occurrences were resolved, with zero name-only forced merges and zero detected strict-prior temporal violations.
- **Records:** [data lineage and quality checks](data_lineage_and_quality.md).

## F13 — reuse of the 2026 development period

- **Problem:** target-game and same-date leakage were excluded, but 2026 outcomes were inspected while comparing model families, training windows, adaptive strategies, calibration, and ensembles.
- **Evidence:** 42 configurations and multiple learning strategies were compared. The 2026-independent CV candidate recorded Log loss `0.667390`; the best-observed recent-720 candidate recorded `0.666135`. Their paired difference was `−0.001255`, with a 95% interval of `[−0.004790, 0.002336]` and a `74.61%` probability favoring the recent-720 method.
- **Diagnosis — evaluation risk:** this is model-selection risk from reusing a development period, not row-level feature leakage.
- **Change:** freeze both specifications, stop tuning on observed 2026 outcomes, and require new ideas to enter as separately versioned challengers.
- **Verified outcome:** the recent-720 model is reported as the best observed development model, not as a future-validated champion. The next comparison will use predictions written before first pitch to an immutable prospective ledger.
- **Records:** [model-selection decision](../reports/frozen/V12_MODEL_SELECTION_DECISION.json), [scientific status](scientific_status_and_claims.md), and [prospective validation protocol](prospective_validation.md).
