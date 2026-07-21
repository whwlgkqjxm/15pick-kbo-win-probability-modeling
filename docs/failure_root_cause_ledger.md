# Failure, defect, and root-cause ledger

A high-quality applied data-science project should document not only successful models but also how invalid assumptions, implementation defects, and negative results were distinguished.

## Ledger format

Every entry follows: **symptom → evidence → root cause → corrective action → verification → scientific consequence**.

## F01 — limited-sample overdevelopment

- **Symptom:** many sophisticated models failed to improve over simple rank or team baselines.
- **Evidence:** 416 binary games, 281 outer predictions, narrow probability range, unstable fold choices, research-grade model Log loss `0.693281`.
- **Root cause:** small effective sample size, repeated teams and dates, large adaptive candidate space, and missing external pregame information.
- **Correction:** closed the branch, froze the negative result, and expanded to 2024–2026 official data.
- **Verification:** Phase 2 contained 1,824 decision games and supported cleaner multi-season temporal evaluation.
- **Consequence:** Phase 1 is evidence of disciplined stopping, not a hidden failed attempt.

## F02 — starting-pitcher identity asymmetry

- **Symptom:** home starter history was available for 416 model-period games, away starter history for zero.
- **Evidence:** impossible prior-gap distribution with no negative values; side-specific eligibility audit.
- **Root cause:** home raw tokens contained numeric KBO IDs while away raw tokens often contained names; the initial eligibility logic rejected nonnumeric tokens.
- **Correction:** unique team-name-to-ID mappings, occurrence-specific evidence, official profile checks, and explicit unresolved states.
- **Verification:** source starters 848/848 resolved; model-period starters 832/832 eligible; home 416/416 and away 416/416.
- **Consequence:** all results depending on the defective starter feature were invalid for starter-value claims and were not reused.

## F03 — innings parser and validator failures

- **Symptom:** effect-shape runs failed on innings schema ambiguity and one-third/two-thirds inning notation.
- **Evidence:** fail-closed preflight stopped before model fitting.
- **Root cause:** incomplete schema resolution and fractional-inning parser coverage.
- **Correction:** canonical outs as the calculation unit, fraction unit tests, exact schema resolution, and domain-minimum validation.
- **Verification:** corrected starter foundation joined 4,110 pitcher occurrences and produced 832 game-side starters.
- **Consequence:** execution success was explicitly separated from scientific validity.

## F04 — role contamination

- **Symptom:** starter means and starting-lineup means differed substantially when restricted to role-specific history.
- **Evidence:** 78.11% of experienced starting-batter rows included substitute history; 20.77% of experienced starter rows included relief history.
- **Root cause:** history key omitted start/substitute and start/relief role.
- **Correction:** role-aware histories, clean start-only starter score, and explicit role audits.
- **Verification:** role distributions and all-role versus role-specific deltas were quantified and preserved.
- **Consequence:** the earlier ceiling conclusion was suspended and V2 remained a historical, not clean-role, baseline.

## F05 — V3 complexity degradation

- **Symptom:** a larger feature space and nine model families produced worse probability quality.
- **Evidence:** V3 ensemble Log loss `0.677185` versus V2 `0.670610`; improvement probability only `15.83%`.
- **Root cause:** limited independent signal, redundant features, selection variance, and model complexity.
- **Correction:** retained regulated logistic models and required temporal evidence for added complexity.
- **Verification:** later V12 comparisons again found strongly regularized logistic regression most stable.
- **Consequence:** model sophistication was not used as a proxy for scientific quality.

## F06 — V5 ceiling claim invalidation

- **Symptom:** an audit suggested little predictable error structure remained.
- **Evidence:** error-prediction AUC near 0.5 and weak benefit from additional features.
- **Root cause:** the audit evaluated a contaminated feature construction.
- **Correction:** suspended the ceiling claim after role contamination was discovered.
- **Verification:** clean starter and later new batter systems produced incremental signal.
- **Consequence:** conclusions are conditional on data construction and must be withdrawn when assumptions fail.

## F07 — initial batter system failed integration

- **Symptom:** the selected V8 batter candidate improved a standalone domain model but worsened the V7 stack.
- **Evidence:** 2025 V7 `0.669483`; V7 plus batter `0.673388`.
- **Root cause:** limited score-family, prior-average, and aggregation search; instability as a universal player-ranking score.
- **Correction:** V11.1 rebuilt the batter system from official events without legacy batter income, comparing 215 scores and broad application strategies.
- **Verification:** V12 recent-720 batter ablation improved Log loss by `−0.007022`, with interval excluding zero.
- **Consequence:** “the tested batter representation failed” was not generalized into “batting has no predictive value.”

## F08 — player-level relief index null/negative result

- **Symptom:** selected relief score failed to improve a team baseline and worsened stacked prediction.
- **Evidence:** 2025 domain delta `+0.000009`; V7 plus relief `0.674253` versus V7 `0.669483`.
- **Root cause:** pregame deployment is unknown, actual relievers would leak postgame information, full-pool averages dilute likely participants, and availability is time-varying.
- **Correction:** retained team-level strict-prior post-starter responsibility-run features; documented the need for roster/workload and play-by-play data.
- **Verification:** target starters were excluded from relief pools, weighted means were manually checked, and the negative result remained.
- **Consequence:** scope was narrowed rather than forcing a weak feature into the final model.

## F09 — V10 accuracy/probability conflict

- **Symptom:** added workload, matchup, and lineup features increased accuracy but worsened Log loss and Brier.
- **Evidence:** V10 combined Log loss `0.667817` versus V9-style `0.667336`, while accuracy increased.
- **Root cause:** threshold classification can improve even when predicted probabilities become less well calibrated or overconfident.
- **Correction:** retained V9-style as probability primary and V10 only as an accuracy-oriented challenger.
- **Verification:** paired-date interval included zero and probability of Log-loss improvement was 38.475%.
- **Consequence:** the project explicitly prioritizes probabilistic scoring rules over accuracy alone.

## F10 — adaptive retraining did not outperform static learning

- **Symptom:** expanding, rolling, decay-weighted daily retraining, and online updates did not beat static recent-window learning.
- **Evidence:** best adaptive L2 expanding daily Log loss `0.668838` versus recent-720 static `0.666135`.
- **Root cause:** frequent adaptation can follow short-term noise when the sample is modest and features already summarize recent form.
- **Correction:** preserve static and adaptive results; do not assume continual retraining is inherently superior.
- **Verification:** all prediction columns remained bounded and same-date outcomes were added only after all games on a date were predicted.
- **Consequence:** future updates must be separate challenger versions, not silent daily overwrites.

## F11 — public reproduction implementation drift

- **Symptom:** an early public script did not exactly reproduce frozen V12 metrics.
- **Evidence:** the public script used `solver="liblinear"` and sorted recent rows only by date; reproduced Log loss differed from the authoritative value.
- **Root cause:** simplified public code diverged from the historical execution environment and deterministic ordering rule.
- **Correction:** removed the solver override, sorted by `game_date, game_id`, restored the authoritative date-cluster bootstrap, and added exact metric and model-replay tests.
- **Verification:** current reproduction matches frozen metrics to `1e-12`; saved model replay errors are approximately `1e-16`.
- **Consequence:** a polished README is not accepted as reproducibility evidence unless executable code regenerates the numbers.
