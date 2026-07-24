# Failure, defect, and root-cause ledger

A strong applied data-science project should document not only its best model, but also how observed failures were investigated, which causes were confirmed, which explanations remained inferential, and how each finding changed the research design.

## Interpretation rules

This ledger separates three levels of causal certainty:

- **Confirmed defect:** a data, implementation, or validation failure that was directly reproduced or isolated.
- **Supported interpretation:** a mechanism consistent with the evidence, but not experimentally isolated as the sole cause.
- **Governance risk:** a model-selection or evaluation issue controlled through process rather than claimed away.

Each entry follows: **problem → evidence → cause status → resolution → verification → scientific consequence**. Metrics from different historical protocols are not treated as one common leaderboard.

## At a glance

| ID | Issue | Cause status | Final action |
|---|---|---|---|
| F01 | Limited-sample overdevelopment | Supported interpretation | Close branch and expand the data foundation |
| F02 | Starting-pitcher identity asymmetry | Confirmed defect | Rebuild identity resolution and invalidate affected claims |
| F03 | Innings parser and validator failures | Confirmed defect | Canonicalize innings as outs and fail closed |
| F04 | Role-contaminated player histories | Confirmed defect | Rebuild strict-prior histories by role |
| F05 | Complex-model degradation | Supported interpretation | Reject complexity without temporal gain |
| F06 | Invalid predictive-ceiling claim | Confirmed premise failure | Withdraw the claim and redesign features |
| F07 | Initial batter system failed integration | Supported interpretation | Rebuild the batter representation from scratch |
| F08 | Player-level relief index was null or harmful | Supported interpretation | Reject it and retain team-level bullpen context |
| F09 | Accuracy improved while probability quality worsened | Confirmed metric conflict | Keep Log loss and Brier as primary criteria |
| F10 | Adaptive retraining did not beat static learning | Supported interpretation | Preserve static frozen candidates |
| F11 | Public reproduction drift | Confirmed defect | Restore exact ordering, solver behavior, and tests |
| F12 | Source and scoring parity defects | Confirmed defects | Correct derived data without overwriting evidence |
| F13 | Reuse of the 2026 development period | Governance risk | Freeze two models and require prospective validation |

## F01 — limited-sample overdevelopment

- **Problem:** sophisticated models did not produce defensible pregame probability forecasts in the 2026-only branch.
- **Evidence:** 424 completed games yielded 416 binary games and only 281 outer predictions; fold choices were unstable, probabilities were compressed, and the research-grade model recorded Log loss `0.693281`.
- **Cause status — supported interpretation:** the effective sample was small relative to the adaptive search space, teams and dates were repeatedly observed, and important point-in-time context was unavailable. These factors are consistent with high selection variance, but no single factor was isolated as the sole cause.
- **Resolution:** close the branch as a valid negative result and expand to official 2024–2026 data rather than continuing to tune the same sample.
- **Verification:** Phase 2 produced 1,824 decision games across three seasons while preserving the Phase 1 result unchanged.
- **Scientific consequence:** disciplined stopping became part of the evidence; the failed branch was not hidden or retrospectively relabeled.
- **Primary artifact:** [Phase 1 experiment card](../experiments/01_phase1_limited_sample/README.md).

## F02 — starting-pitcher identity asymmetry

- **Problem:** home starter history was available for all 416 model-period games, while away starter history was available for none.
- **Evidence:** prior-gap values had an impossible one-sided distribution; the side-specific audit showed home eligibility `416/416` and away eligibility `0/416`.
- **Cause status — confirmed defect:** home source tokens contained numeric KBO IDs, while away tokens often contained names; the original eligibility logic rejected nonnumeric identifiers.
- **Resolution:** combine numeric IDs, unique season-team-name mappings, occurrence-level evidence, official profiles, and explicit unresolved states. Name-only forced merges were prohibited.
- **Verification:** source starters were resolved `848/848`; binary-game starter sides were eligible `832/832`, split evenly as home `416/416` and away `416/416`.
- **Scientific consequence:** all starter-value claims depending on the asymmetric feature were invalidated and not reused.
- **Primary artifacts:** [multi-season foundation](../experiments/02_multiseason_foundation/README.md) and [data lineage](data_lineage_and_quality.md).

## F03 — innings parser and validator failures

- **Problem:** effect-shape experiments failed on ambiguous innings fields and baseball one-third/two-thirds notation.
- **Evidence:** fail-closed preflight checks stopped execution before model fitting rather than silently coercing invalid innings values.
- **Cause status — confirmed defect:** schema resolution was incomplete and fractional-inning parsing did not cover all official representations.
- **Resolution:** use canonical outs as the calculation unit, add fraction-specific tests, require exact schema resolution, and enforce domain-minimum checks before modeling.
- **Verification:** the corrected 2026 pitcher foundation joined 4,110 pitcher rows and resolved 832 binary-game starter sides.
- **Scientific consequence:** successful code execution was explicitly separated from scientifically valid data construction.
- **Primary artifact:** [data lineage and quality controls](data_lineage_and_quality.md).

## F04 — role contamination in player histories

- **Problem:** starting-lineup and starting-pitcher features contained performance from different roles.
- **Evidence:** `25,870/33,121` experienced starting-batter rows included substitute history (`78.11%`); `726/3,496` experienced starting-pitcher rows included relief history (`20.77%`). Among 614 pitchers with both roles, the median absolute difference between all-role and start-only averages was `149.14`, with a 90th percentile of `779.51`.
- **Cause status — confirmed defect:** the historical key separated season, player, and broad position type, but omitted start/substitute and start/relief role state.
- **Resolution:** rebuild date-batched strict-prior histories by role and construct a clean start-only starter score.
- **Verification:** role distributions, contamination rates, and all-role versus role-specific differences were quantified and preserved before downstream redesign.
- **Scientific consequence:** V2 remained a useful historical baseline, but not a clean-role specification; conclusions based on the contaminated representation required revision.
- **Primary artifacts:** [role-scope audit summary](../research_records/key_results/ROLE_SCOPE_AUDIT_SUMMARY.csv) and [V5 audit card](../experiments/06_v5_role_scope_audit/README.md).

## F05 — V3 complexity degradation

- **Problem:** a much larger feature and model search produced worse probability forecasts than the stabilized V2 model.
- **Evidence:** V3 evaluated 763 candidate columns, selected 162 features, compared nine model families and 37 configurations across roughly 610 temporal fits. Its ensemble Log loss was `0.677185`, versus V2 at `0.670610`; the estimated improvement probability was only `15.83%`.
- **Cause status — supported interpretation:** feature redundancy, limited independent signal, selection variance, and excess model capacity are consistent with the result, but their individual causal contributions were not isolated.
- **Resolution:** reject complexity unless it improves out-of-time probability quality; retain regularized logistic regression as the reference family.
- **Verification:** V12 again compared broad linear, tree, boosting, ensemble, calibration, and online families; L2 logistic regression with `C=0.03` remained the temporal-CV champion.
- **Scientific consequence:** model sophistication was not used as a proxy for research quality.
- **Primary artifacts:** [V3 experiment card](../experiments/04_v3_complex_model_search/README.md) and [V12 temporal CV](../reports/frozen/V12_MODEL_FAMILY_TEMPORAL_CV.csv).

## F06 — V5 predictive-ceiling claim invalidation

- **Problem:** the V5 audit initially suggested that little predictable BoxScore signal remained after roughly 600 games and that 224 additional features could not explain V2 errors.
- **Evidence:** error-prediction AUC was near `0.5`, and added features provided little improvement under the existing representation.
- **Cause status — confirmed premise failure:** the audit measured the ceiling of role-contaminated features identified in F04, not the ceiling of clean batter, starter, and relief representations.
- **Resolution:** withdraw the ceiling claim rather than merely qualify it, then move from model tuning to role-specific feature redesign.
- **Verification:** the clean starter system later improved 2025 Log loss by `−0.009401`; the rebuilt batter block also added signal in later development evaluation.
- **Scientific consequence:** conclusions were treated as conditional on data construction and withdrawn when their assumptions failed.
- **Primary artifacts:** [V5 ceiling report](../research_records/reports/RQ1_V5_CEILING_AUDIT_REPORT.md) and [role-aware audit report](../research_records/reports/RQ1_ROLE_AWARE_INCOME_AUDIT_REPORT.md).

## F07 — initial batter system failed integration

- **Problem:** the V8 batter candidate improved a standalone domain model but degraded the stronger V7 integrated model.
- **Evidence:** the standalone batter model improved over the team baseline from `0.687435` to `0.682866`, yet adding it to V7 worsened 2025 Log loss from `0.669483` to `0.673388` (`+0.003905`).
- **Cause status — supported interpretation:** the first search over score design, prior averaging, and lineup aggregation was not robust enough for integration, and part of its signal may have overlapped with existing team and starter components. These mechanisms were not isolated as unique causes.
- **Resolution:** reject the V8 addition and rebuild the batter representation from official batting events without the legacy batter score. V11.1 compared 215 game-index candidates, 20 prior methods, six lineup blocks, and multiple integration strategies.
- **Verification:** in 2025 validation, the rebuilt model improved from `0.668954` without the batter block to `0.665020` with it (`−0.003934`), although the 95% interval `[−0.010585, 0.002925]` included zero. Under the best-observed `RECENT_720` 2026 development protocol, the batter block improved Log loss by `−0.007022`, with interval `[−0.013416, −0.000548]`; this remains development evidence because 2026 was used during method comparison.
- **Scientific consequence:** failure of one batter representation was not generalized into a claim that batting lacks predictive value.
- **Primary artifacts:** [V8 application results](../research_records/key_results/V8_2025_PREDICTION_APPLICATION_RESULTS.csv), [V11.1 comparison](../reports/frozen/V11_1_ROBUST_CANDIDATE_COMPARISON.csv), and [V12 batter ablation](../reports/frozen/V12_2026_BATTER_ABLATION_RESULTS.csv).

## F08 — player-level relief index null or negative result

- **Problem:** player-level relief-pitcher features failed to add reliable pregame value and worsened the integrated model.
- **Evidence:** the preliminary V6 relief screen worsened Log loss by `+0.000967`. In the dedicated V8 experiment, the selected relief index was effectively null against the team baseline (`0.687444` versus `0.687435`, delta `+0.000009`, improvement probability `49.95%`) and worsened V7 from `0.669483` to `0.674253` (`+0.004770`). A 2026 post-hoc addition also worsened Log loss by `+0.001113`.
- **Cause status — supported interpretation:** actual reliever deployment is unknown before first pitch; leakage-safe features must approximate a candidate pool that may contain nonparticipants; availability changes with workload, recovery, injury, roster status, leverage, and strategy. These are plausible structural limitations, not a uniquely proven causal decomposition.
- **Resolution:** reject the tested player-level relief index, keep the negative result, and retain team-level strict-prior post-starter context. Exact physical post-exit runs and stronger player-level availability modeling were deferred until play-by-play and point-in-time roster/workload data are available.
- **Verification:** target starters were excluded from relief pools, candidate weights were manually audited, and the V9 recent-20 team measure improved V7 only modestly (`−0.000478`, 95% interval `[−0.003102, 0.002145]`), so it remained a challenger rather than a confirmed replacement.
- **Scientific consequence:** the scope was narrowed to a defensible pregame representation; the result does not imply that relief pitching is unimportant.
- **Primary artifacts:** [V6 domain ablation](../research_records/key_results/V6_1_V2_CHALLENGER_AND_DOMAIN_ABLATION.csv), [V8 domain comparison](../research_records/key_results/V8_DOMAIN_BASELINE_AND_LEGACY_COMPARISON.csv), and [relief negative-result note](relief_pitcher_index_negative_result.md).

## F09 — V10 accuracy and probability-quality conflict

- **Problem:** richer workload, matchup, and lineup features increased classification accuracy but worsened proper probability scores.
- **Evidence:** on the strict 2025 holdout, accuracy increased from `58.31%` to `59.74%`, while Log loss worsened from `0.667336` to `0.667817` (`+0.000481`) and Brier score from `0.237412` to `0.237603`. The paired-date 95% interval for the Log-loss difference was `[−0.002909, 0.003879]`, with only a `38.475%` probability of improvement.
- **Cause status — confirmed objective conflict; mechanism not overclaimed:** accuracy evaluates threshold decisions and ignores confidence, whereas Log loss and Brier score evaluate full probability assignments. The evidence does not by itself prove that miscalibration or overconfidence was the unique mechanism.
- **Resolution:** retain the V9-style model as the probability-primary specification and preserve V10 only as an accuracy-oriented challenger.
- **Verification:** all models were compared under the same 2024-selection/2025-holdout protocol and paired by game date.
- **Scientific consequence:** model selection was aligned with the research target—probability quality—rather than whichever metric produced the most favorable headline.
- **Primary artifacts:** [V10 holdout results](../research_records/key_results/V10_2025_UNTOUCHED_HOLDOUT_RESULTS.csv) and [paired bootstrap](../research_records/key_results/V10_PAIRED_DATE_BOOTSTRAP.csv).

## F10 — adaptive retraining did not outperform static learning

- **Problem:** expanding, rolling, decay-weighted daily retraining, and online updates did not beat the strongest static recent-window model.
- **Evidence:** the best adaptive method, L2 `C=0.03` with expanding daily retraining, recorded 2026 development Log loss `0.668838`; the best static method, L2 `C=0.1` on the recent 720 games, recorded `0.666135`. Online SGD variants were substantially worse.
- **Cause status — supported interpretation:** frequent updates can follow short-term noise when the effective sample is modest and existing features already summarize recent form. This explanation is consistent with the results but was not isolated as the only cause.
- **Resolution:** preserve both static and adaptive results, reject the assumption that continual retraining is automatically superior, and prevent silent daily replacement of frozen models.
- **Verification:** adaptive predictions remained bounded, and same-date outcomes were added only after every game on that date had been predicted.
- **Scientific consequence:** future adaptive methods must enter as separately versioned challengers with prospective evaluation.
- **Primary artifact:** [V12 adaptive-strategy results](../reports/frozen/V12_2026_ADAPTIVE_STRATEGY_RESULTS.csv).

## F11 — public reproduction implementation drift

- **Problem:** an early public reproduction script did not regenerate the authoritative frozen V12 metrics exactly.
- **Evidence:** the script forced `solver="liblinear"` and ordered recent rows only by date; reproduced Log loss differed from the frozen result.
- **Cause status — confirmed defect:** the maintained public implementation had diverged from the historical execution environment and deterministic `game_date, game_id` ordering rule.
- **Resolution:** remove the solver override, restore deterministic two-key ordering, reproduce the authoritative date-cluster bootstrap, and add exact metric and saved-model replay tests.
- **Verification:** current metrics match the frozen values within `1e-12`; saved model binaries replay frozen probabilities with maximum absolute errors on the order of `1e-16`.
- **Scientific consequence:** documentation alone was not accepted as reproducibility evidence; executable replay became a release gate.
- **Primary artifacts:** [reproducibility guide](reproducibility.md) and [model-binary audit](../reports/frozen/V12_MODEL_BINARY_REPRODUCTION_AUDIT.json).

## F12 — source and scoring parity defects

- **Problem:** canonical replay and the historical 2026 stream disagreed on player-game scoring and identity details.
- **Evidence:** audits found incomplete strikeout-token coverage, stolen-base suffix interpretation differences, double-play detail differences, five incorrect legacy player-ID rows, display-name formatting inconsistencies, and a stale July 8, 2026 snapshot. Identity review also initially left 127 occurrences unresolved.
- **Cause status — confirmed defects:** each discrepancy was traced to a concrete source-parsing, identity, formatting, or snapshot problem rather than treated as random noise.
- **Resolution:** correct analytical tables using official evidence, numeric IDs, targeted daily records, and occurrence fingerprints; preserve the historical stream instead of overwriting it.
- **Verification:** all `65,554/65,554` player-game occurrences were resolved, with zero name-only forced merges and zero detected strict-prior temporal violations.
- **Scientific consequence:** source parity, identity integrity, and provenance were established as prerequisites for modeling rather than post-hoc cleanup.
- **Primary artifacts:** [data lineage and quality controls](data_lineage_and_quality.md) and [multi-season foundation card](../experiments/02_multiseason_foundation/README.md).

## F13 — reuse of the 2026 development period

- **Problem:** 2026 features were leakage-safe at the row level, but 2026 outcomes were inspected while comparing model families, training windows, adaptive strategies, calibration, and ensembles.
- **Evidence:** 42 configurations and multiple learning strategies were compared. The 2026-independent CV candidate `L2_C0.03_ALL_EQUAL` recorded development Log loss `0.667390`; the best-observed `L2_C0.1_RECENT_720` recorded `0.666135`. Their paired difference was `−0.001255`, with a 95% interval `[−0.004790, 0.002336]` and a `74.61%` probability favoring the recent-720 method.
- **Cause status — governance risk:** this is test-set reuse and model-selection uncertainty, not target-game or same-date feature leakage.
- **Resolution:** freeze both specifications, stop further tuning on observed 2026 outcomes, and require new ideas to be separately versioned challengers.
- **Verification:** model schemas, binaries, input hashes, prediction files, and replay audits are preserved; the next evaluation is defined as an immutable pregame ledger with postgame settlement stored separately.
- **Scientific consequence:** the recent-720 result is labeled the best observed development model, not a future-proven production champion; final generalization claims are deferred to prospective data.
- **Primary artifacts:** [scientific status](scientific_status_and_claims.md), [prospective validation](prospective_validation.md), and [V12 paired bootstrap](../reports/frozen/V12_2026_PAIRED_DATE_BOOTSTRAP.csv).

## What this ledger demonstrates

The project did not treat every disappointing metric as the same kind of failure. It distinguished data defects from modeling limitations, metric conflicts, uncertain mechanisms, and evaluation-governance risks. Each finding led to a concrete action: invalidate affected claims, repair the pipeline, redesign the representation, reject an unsupported feature, or freeze the model and wait for new evidence.
