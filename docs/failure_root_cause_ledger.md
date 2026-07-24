# Failure and root-cause ledger

This file records the problems that changed the data, features, validation protocol, model choice, or final claims. Each entry keeps the observed failure, the evidence used to diagnose it, the correction, and the result after correction.

Assessment labels are used only to distinguish what was directly reproduced from what remains an evidence-based explanation. Results are compared directly only when they were produced under the same evaluation protocol.

## Summary

| ID | Problem | Assessment | Action |
|---|---|---|---|
| F01 | 2026-only sample was too weak for continued model search | Supported explanation | Stop the branch and expand to 2024–2026 |
| F02 | Home and away starter identities were resolved differently | Confirmed defect | Rebuild starter identity resolution |
| F03 | Innings parsing and schema checks failed on valid baseball notation | Confirmed defect | Convert innings to outs and fail closed |
| F04 | Batter and starter histories mixed different roles | Confirmed defect | Rebuild strict-prior histories by role |
| F05 | Larger feature and model searches performed worse than V2 | Supported explanation | Reject added complexity without temporal gain |
| F06 | The V5 ceiling claim relied on contaminated features | Confirmed premise failure | Withdraw the claim and redesign role features |
| F07 | The first batter index failed when added to the V7 model | Supported explanation | Rebuild the batter index from official events |
| F08 | The player-level relief index was null or harmful | Supported explanation | Reject it and retain team-level bullpen context |
| F09 | Accuracy improved while probability scores worsened | Confirmed metric conflict | Use Log loss and Brier score for primary selection |
| F10 | Adaptive retraining did not beat the best static window | Supported explanation | Keep the frozen static candidates |
| F11 | The public reproduction code did not exactly match V12 | Confirmed defect | Restore ordering, solver behavior, and replay tests |
| F12 | Source parsing, scoring, identity, and snapshot parity failed | Confirmed defects | Correct derived data while preserving original evidence |
| F13 | 2026 outcomes were reused during method selection | Evaluation risk | Freeze both models and move to prospective validation |

## F01 — 2026-only sample was too weak for continued search

- **Observed:** the 2026-only branch did not produce stable pregame probabilities.
- **Evidence:** 424 completed games produced 416 decision games and 281 temporal outer predictions. The best development candidate recorded Log loss `0.685090`, Brier score `0.246008`, and ROC AUC `0.573867`, with probabilities concentrated near `0.5`. A later 337-feature search recorded Log loss `0.693281`.
- **Assessment:** the effective sample was small relative to the number of inspected features, models, and fold choices. Repeated teams and dates also limited the amount of independent information. These factors support the diagnosis, but no single cause was isolated.
- **Action:** stop tuning the inspected 2026 sample and rebuild the study on official 2024–2026 data.
- **Result:** the next foundation contained 1,824 decision games across three seasons. The Phase 1 result was retained as a negative result rather than reinterpreted after the expansion.
- **Evidence:** [Phase 1 research record](research_journey.md#phase-1--2026-only-limited-sample-study).

## F02 — home/away starter identity asymmetry

- **Observed:** starter history was available for every home team and no away team in the 416-game model period.
- **Evidence:** eligibility was home `416/416` and away `0/416`, an impossible side-specific pattern.
- **Root cause:** home starter tokens often contained numeric KBO IDs, while away tokens often contained names. The original eligibility rule accepted the former and rejected the latter.
- **Action:** combine numeric IDs, unique season-team-name mappings, official profiles, targeted daily evidence, and occurrence-level fingerprints. Name-only forced merges were prohibited.
- **Result:** source starters were resolved `848/848`; binary-game starter eligibility became home `416/416` and away `416/416`. Claims based on the asymmetric feature were discarded.
- **Evidence:** [data lineage and identity checks](data_lineage_and_quality.md).

## F03 — innings parser and validation failures

- **Observed:** pitcher feature construction stopped on ambiguous innings fields and one-third/two-thirds inning notation.
- **Evidence:** preflight validation failed before model fitting instead of coercing unresolved values.
- **Root cause:** schema resolution was incomplete, and the parser did not cover every official representation of fractional innings.
- **Action:** represent innings internally as outs, require exact schema matches, test baseball-specific fractions, and stop the pipeline when domain checks fail.
- **Result:** the corrected 2026 pitcher foundation joined 4,110 pitcher rows and resolved all 832 starter sides in the 416 decision games.
- **Evidence:** [data lineage and validation checks](data_lineage_and_quality.md).

## F04 — role-contaminated player histories

- **Observed:** starting-lineup and starting-pitcher features included performance from different roles.
- **Evidence:** `25,870/33,121` experienced starting-batter rows included substitute history (`78.11%`); `726/3,496` experienced starting-pitcher rows included relief history (`20.77%`). Among 614 pitchers with both roles, the median absolute difference between all-role and start-only averages was `149.14`; the 90th percentile was `779.51`.
- **Root cause:** the history key separated season, player, and broad position type, but not starter/substitute batting or starter/relief pitching.
- **Action:** rebuild date-batched strict-prior histories by role and design a start-only pitcher score.
- **Result:** V2 remained a historical baseline, but it was no longer treated as a clean role-specific specification. The role audit became the basis for V6–V12 redesign.
- **Evidence:** [role-scope audit table](../research_records/key_results/ROLE_SCOPE_AUDIT_SUMMARY.csv) and [role-aware audit report](../research_records/reports/RQ1_ROLE_AWARE_INCOME_AUDIT_REPORT.md).

## F05 — complex-model degradation

- **Observed:** a broader feature and model search performed worse than the stabilized V2 model.
- **Evidence:** V3 evaluated 763 candidate columns, selected 162 features, compared nine model families and 37 configurations across roughly 610 temporal fits. Its ensemble Log loss was `0.677185`, compared with V2 at `0.670610`; the estimated probability of improvement was `15.83%`.
- **Assessment:** redundant features, limited independent signal, selection variance, and excess model capacity are consistent with the result, but their separate effects were not isolated.
- **Action:** require out-of-time probability improvement before accepting added complexity.
- **Result:** V12 again compared linear, tree, boosting, ensemble, calibration, adaptive, and online methods. L2-regularized logistic regression remained the temporal-CV winner.
- **Evidence:** [V3 research record](research_journey.md#v3--broad-complex-model-search) and [V12 model-family CV](../reports/frozen/V12_MODEL_FAMILY_TEMPORAL_CV.csv).

## F06 — invalid predictive-ceiling claim

- **Observed:** V5 initially suggested that performance had flattened after roughly 600 games and that 224 additional features could not explain V2 errors.
- **Evidence:** the error-prediction AUC was near `0.5`, and the extra features added little under the existing representation.
- **Root cause:** the ceiling audit used the role-contaminated histories identified in F04. It measured the limit of the flawed representation, not the limit of clean batter, starter, and relief features.
- **Action:** withdraw the ceiling claim and move from model tuning to role-specific feature redesign.
- **Result:** the clean starter block later improved 2025 Log loss by `−0.009401`, and the rebuilt batter block added signal in later development evaluation.
- **Evidence:** [V5 ceiling audit](../research_records/reports/RQ1_V5_CEILING_AUDIT_REPORT.md), [role-aware audit](../research_records/reports/RQ1_ROLE_AWARE_INCOME_AUDIT_REPORT.md), and [rebuild decision](../research_records/decisions/ROLE_AWARE_REBUILD_DECISION.json).

## F07 — first batter index failed integration

- **Observed:** the initial batter index improved a standalone domain model but worsened the stronger V7 integrated model.
- **Evidence:** the standalone batter model improved from `0.687435` to `0.682866`, but adding it to V7 worsened 2025 Log loss from `0.669483` to `0.673388` (`+0.003905`).
- **Assessment:** the first score, prior, and lineup-aggregation search did not produce a sufficiently robust incremental feature. Signal overlap with the team and starter components is also plausible, but was not isolated as the sole cause.
- **Action:** reject the V8 batter addition and rebuild the batter index from official events without the legacy batter score.
- **Result:** V11.1 compared 215 game-index candidates, 20 prior methods, and six lineup blocks. The selected system improved 2025 validation from `0.668954` to `0.665020`. Under the best-observed 2026 development protocol, removing the batter block worsened Log loss by `0.007022`; that result remains development evidence because 2026 was used during method comparison.
- **Evidence:** [V8 integration results](../research_records/key_results/V8_2025_PREDICTION_APPLICATION_RESULTS.csv), [V11.1 comparison](../reports/frozen/V11_1_ROBUST_CANDIDATE_COMPARISON.csv), and [V12 batter ablation](../reports/frozen/V12_2026_BATTER_ABLATION_RESULTS.csv).

## F08 — player-level relief index was null or harmful

- **Observed:** the tested player-level relief features did not add reliable pregame value.
- **Evidence:** the preliminary V6 relief screen worsened Log loss by `+0.000967`. In V8, the selected relief index was effectively null against the team baseline (`0.687444` versus `0.687435`) and worsened V7 from `0.669483` to `0.674253`. A 2026 post-hoc addition also worsened Log loss by `+0.001113`.
- **Assessment:** the actual relievers who will appear are unknown before first pitch. A leakage-safe feature must approximate a candidate pool using prior appearances, workload, rest, and roster evidence, so it can include pitchers who do not enter the game. This is a supported explanation, not a uniquely proven cause.
- **Action:** reject the player-level relief index and retain team-level strict-prior bullpen and post-starter context.
- **Result:** the V9 recent-20 team measure improved V7 by only `−0.000478`, with a 95% interval of `[−0.003102, 0.002145]`; it remained a challenger rather than a confirmed replacement. The negative player-level result does not imply that relief pitching is unimportant.
- **Evidence:** [V6 role ablation](../research_records/key_results/V6_1_V2_CHALLENGER_AND_DOMAIN_ABLATION.csv), [V8 domain comparison](../research_records/key_results/V8_DOMAIN_BASELINE_AND_LEGACY_COMPARISON.csv), and [relief-index analysis](relief_pitcher_index_negative_result.md).

## F09 — accuracy and probability-quality conflict

- **Observed:** the V10 feature set improved classification accuracy while worsening the primary probability metrics.
- **Evidence:** on the strict 2025 holdout, accuracy increased from `58.31%` to `59.74%`, but Log loss worsened from `0.667336` to `0.667817` and Brier score from `0.237412` to `0.237603`. The paired-date 95% interval for the Log-loss difference was `[−0.002909, 0.003879]`; the probability of improvement was `38.475%`.
- **Root cause:** accuracy evaluates threshold decisions and ignores probability confidence. Log loss and Brier score evaluate the full probability assignment, which was the target of this study.
- **Action:** keep Log loss and Brier score as the primary model-selection criteria and retain V10 only as an accuracy-oriented challenger.
- **Result:** the simpler V9-style probability model remained primary under the common 2024-selection/2025-holdout protocol.
- **Evidence:** [V10 holdout results](../research_records/key_results/V10_2025_UNTOUCHED_HOLDOUT_RESULTS.csv) and [paired-date bootstrap](../research_records/key_results/V10_PAIRED_DATE_BOOTSTRAP.csv).

## F10 — adaptive retraining did not beat the best static window

- **Observed:** expanding, rolling, decay-weighted daily retraining, and online updates did not improve on the best static recent-window model.
- **Evidence:** the best adaptive method recorded 2026 development Log loss `0.668838`; the best static recent-720 model recorded `0.666135`. Online SGD variants were substantially worse.
- **Assessment:** frequent updates can follow short-term noise when the sample is modest and the existing features already summarize recent form. The experiments support this explanation but do not isolate it as the only cause.
- **Action:** reject automatic continual replacement of the frozen models and require adaptive methods to enter as separately versioned challengers.
- **Result:** the static CV-selected and recent-720 specifications were preserved for prospective comparison.
- **Evidence:** [V12 adaptive-strategy results](../reports/frozen/V12_2026_ADAPTIVE_STRATEGY_RESULTS.csv).

## F11 — public reproduction drift

- **Observed:** an early public reproduction script did not regenerate the frozen V12 results exactly.
- **Evidence:** the script forced `solver="liblinear"` and ordered the recent window only by date, producing different probabilities and metrics.
- **Root cause:** the maintained reproduction path had diverged from the historical solver behavior and deterministic `game_date, game_id` ordering.
- **Action:** remove the solver override, restore two-key ordering, reproduce the original date-cluster bootstrap, and add exact metric and saved-model replay tests.
- **Result:** published metrics now match within `1e-12`; saved model binaries replay frozen probabilities with maximum absolute errors on the order of `1e-16`.
- **Evidence:** [reproduction procedure](reproducibility.md) and [model replay audit](../reports/frozen/V12_MODEL_BINARY_REPRODUCTION_AUDIT.json).

## F12 — source and scoring parity defects

- **Observed:** canonical replay and the historical 2026 stream disagreed on several player-game scores and identities.
- **Evidence:** the audit found incomplete strikeout-token coverage, stolen-base suffix differences, double-play detail differences, five incorrect legacy player-ID rows, display-name formatting differences, a stale July 8 snapshot, and 127 initially unresolved occurrences.
- **Root cause:** each discrepancy was traced to a specific parser, identity, formatting, or snapshot issue.
- **Action:** correct analytical tables from official evidence while preserving the original historical stream and audit trail.
- **Result:** all `65,554/65,554` player-game occurrences were resolved, with zero name-only forced merges and zero detected strict-prior temporal violations.
- **Evidence:** [data lineage and quality checks](data_lineage_and_quality.md).

## F13 — reuse of the 2026 development period

- **Observed:** target-game and same-date leakage were excluded, but 2026 outcomes were inspected while comparing model families, windows, adaptive strategies, calibration, and ensembles.
- **Evidence:** 42 configurations and multiple learning strategies were compared. The 2026-independent CV candidate recorded Log loss `0.667390`; the best-observed recent-720 candidate recorded `0.666135`. Their paired difference was `−0.001255`, with a 95% interval of `[−0.004790, 0.002336]`.
- **Assessment:** this is model-selection risk from reusing a development period, not row-level feature leakage.
- **Action:** freeze both specifications, stop tuning on observed 2026 outcomes, and require new ideas to enter as versioned challengers.
- **Result:** the recent-720 model is reported as the best observed development model, not as a future-validated champion. The next comparison will use predictions written before first pitch to an immutable prospective ledger.
- **Evidence:** [model-selection decision](../reports/frozen/V12_MODEL_SELECTION_DECISION.json), [scientific status](scientific_status_and_claims.md), and [prospective protocol](prospective_validation.md).
