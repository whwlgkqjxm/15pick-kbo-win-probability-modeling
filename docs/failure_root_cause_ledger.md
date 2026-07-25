# Research failures, negative results, and corrective actions

This document is a selective analytical ledger, not a chronological bug log and not a record of website operations. It includes only defects, negative experiments, invalidated assumptions, and evaluation risks that materially changed the analytical dataset, feature definitions, validation protocol, model selection, reproducibility status, or scientific claims.

Each entry separates five questions:

1. **What happened?**
2. **What evidence established the problem or result?**
3. **What was the diagnosis, and how certain was it?**
4. **How did it affect the research?**
5. **What was changed, and what was verified afterward?**

The diagnosis labels are used deliberately:

- **Confirmed defect:** a data, implementation, or reproducibility problem established directly by an audit.
- **Confirmed premise failure:** a scientific conclusion was based on a feature definition later shown to be invalid for that claim.
- **Confirmed evaluation conflict:** evaluation criteria favored different models, requiring an explicit metric-priority decision.
- **Supported explanation:** the evidence supports a mechanism, but the study did not isolate it as the only cause.
- **Evaluation risk:** the pipeline prevents row-level leakage, but the evaluation design still permits optimism or limits the strength of the claim.

Direct model comparisons below are made only within the same evaluation protocol. Metrics from different stages are not treated as a single leaderboard.

## Evidence note

Each linked CSV or JSON was checked against the metric quoted in the corresponding entry. Links to narrative documents provide context and interpretation; where the public repository does not contain the original machine-readable failure artifact, the entry is presented as a documented historical audit rather than as a newly reproduced result.

## Executive summary

| ID | Type | Stage | Failure or negative result | Research impact | Resolution |
|---|---|---|---|---|---|
| F01 | Data defect | 2026 starter foundation | Home and away starter identities followed different eligibility paths | Starter-history features were invalid on one side of every game | Rebuilt occurrence-level identity resolution and discarded affected claims |
| F02 | Parsing defect | Pitcher feature construction | Valid baseball innings notation and ambiguous schema fields failed validation | Pitcher workload and rate features could not be trusted | Standardized innings as integer outs and added fail-closed domain tests |
| F03 | Feature-definition defect | Role audit | Batter and pitcher histories mixed different game roles | “Starter” features did not represent starter-only history | Rebuilt strict-prior histories by role and reinterpreted earlier models |
| F04 | Reproducibility defect | V12 repository release | Maintained reproduction code diverged from the frozen execution | Published code did not exactly replay the frozen probabilities | Restored solver behavior, deterministic ordering, and exact replay tests |
| F05 | Data-integrity defect | Canonical reconciliation | Canonical replay disagreed with preserved 2026 derived data | Some scores and identities were inconsistent across data versions | Corrected derived tables from official evidence while preserving the originals |
| F06 | Invalidated premise | V5 ceiling audit | A predictive-ceiling claim relied on role-contaminated features | The claim overstated the limit of clean player-role information | Withdrew the claim and redesigned the player-role features |
| F07 | Metric conflict | V10 model selection | Accuracy improved while Log loss and Brier score worsened | A classification-oriented choice would conflict with the probability objective | Kept probability scores primary and retained V10 only as a challenger |
| F08 | Evaluation risk | V11.1–V12 selection | Validation and development periods were reused during method comparison | Reported gains may be optimistic despite leakage-safe feature rows | Froze two candidates and moved final comparison to prospective data |
| F09 | Evaluation risk | Historical lineup reconstruction | Historical lineups were not independently timestamped before first pitch | Retrospective inputs cannot be described as an immutable historical pregame feed | Qualified the retrospective setting and designed timestamped prospective capture |
| F10 | Negative research result | 2026-only Phase 1 | Repeated search on a small temporal sample produced unstable weak probabilities | Continued tuning would increase selection risk without stronger evidence | Closed the branch as a negative result and expanded to multi-season data |
| F11 | Negative modeling result | V3 broad search | More features and more complex models performed worse than V2 | Complexity did not earn better out-of-time probability quality | Required temporal improvement before accepting added complexity |
| F12 | Negative modeling result | V8 batter integration | The first batter index helped alone but hurt the stronger integrated model | Standalone domain performance did not translate into incremental value | Rejected it and rebuilt the batter index from official batting events |
| F13 | Negative modeling result | V6–V9 relief modeling | Player-level relief indices added no reliable leakage-safe pregame signal | The tested representation could not identify useful incremental value | Rejected the player-level index and retained team-level context as a challenger |
| F14 | Negative modeling result | V12 training strategies | Daily and online adaptation did not beat the best static window | Automatic retraining would add complexity without demonstrated benefit | Preserved static frozen candidates and versioned adaptive methods separately |

---

# A. Data and implementation defects

## F01 — home/away starter identity asymmetry

### What happened

Starter history was available for every home starter and no away starter in the 416-game binary model period.

### Evidence

- Home starter eligibility: `416/416`
- Away starter eligibility: `0/416`

This side-specific pattern was impossible as a baseball result and therefore indicated a data-processing defect rather than ordinary missingness.

### Diagnosis — confirmed defect

Home starter tokens often contained numeric KBO player IDs, while away starter tokens often appeared as names. The original eligibility path accepted the numeric identifiers but rejected many name-based tokens.

### Research impact

Any feature or conclusion that depended on the asymmetric starter history could reflect token format rather than pitcher ability. Those claims were discarded.

### Corrective action

The identity pipeline was rebuilt using, in order of evidentiary strength:

1. numeric KBO player IDs;
2. unique season-team-name mappings;
3. official player profiles;
4. targeted daily official evidence;
5. occurrence-level fingerprints and contiguous pitcher-order evidence.

Name-only forced cross-game merges were prohibited.

### Verification

- Official source starters resolved: `848/848`
- Binary-game starter eligibility: home `416/416`, away `416/416`
- Final multi-season player-game occurrences resolved: `65,554/65,554`
- Name-only forced merges: `0`

### Records

- [Data lineage and identity checks](data_lineage_and_quality.md)
- [Repository overview of the starter-identity correction](../README.ko.md)

## F02 — innings parsing and schema-validation failures

### What happened

Pitcher feature construction stopped when it encountered ambiguous innings fields and valid one-third or two-thirds inning representations.

### Evidence

The preflight checks failed before model fitting rather than silently coercing unresolved values. The failure affected valid baseball notation such as one-third and two-thirds innings and exposed ambiguity between raw innings strings and already-derived outs fields.

### Diagnosis — confirmed defect

The schema resolver did not identify every innings representation consistently, and the parser did not cover all official fractional formats. Baseball notation also cannot be interpreted as ordinary decimal arithmetic: for example, `5.1` conventionally represents five innings and one out, not 5.1 decimal innings.

### Research impact

Incorrect innings conversion would contaminate workload, rate, and starting-pitcher performance features. Continuing with a fallback value would have produced plausible-looking but invalid model inputs.

### Corrective action

- Standardize internal innings representation as integer outs.
- Require exact schema resolution before feature construction.
- Add unit tests for one-third, two-thirds, mixed-number, and decimal-like baseball notation.
- Fail closed when a critical pitcher field cannot be resolved.

### Verification

The corrected 2026 pitcher foundation joined `4,110` pitcher rows and resolved all `832` starter sides in the `416` decision games.

### Records

- [Data lineage and validation checks](data_lineage_and_quality.md)

## F03 — role contamination in player histories

### What happened

Features intended to describe starting batters and starting pitchers included prior appearances from different roles.

### Evidence

- Starting-batter feature rows with prior history: `33,121`
- Rows whose history included substitute appearances: `25,870` (`78.11%`)
- Starting-pitcher rows with prior history: `3,496`
- Rows whose history included relief appearances: `726` (`20.77%`)
- Pitchers with both starter and relief history: `614`
- Median absolute difference between all-role and start-only pitcher averages: `149.14`
- 90th percentile absolute difference: `779.51`

### Diagnosis — confirmed defect

The historical key separated season, player, and broad position type, but did not distinguish:

- starting-lineup batting appearances from substitute appearances; or
- starting-pitcher appearances from relief appearances.

### Research impact

Earlier models could still be retained as historical baselines, but their player-history variables could not be described as clean role-specific indices. The defect also invalidated later conclusions that assumed the representation already separated player roles.

### Corrective action

- Rebuild date-batched strict-prior histories by role.
- Use start-only appearances for the starting-pitcher index.
- Preserve all-role and role-specific histories as separate analytical objects.
- Reevaluate batter, starter, and relief contributions independently.

### Verification

The corrected role histories became the foundation for the V6–V12 redesign. V2 remained documented as a historical baseline rather than being relabeled as a clean role-specific model.

### Records

- [Role-scope audit table](../research_records/key_results/ROLE_SCOPE_AUDIT_SUMMARY.csv)
- [Role-aware audit report](../research_records/reports/RQ1_ROLE_AWARE_INCOME_AUDIT_REPORT.md)

## F04 — repository reproduction drift

### What happened

An early maintained reproduction script did not regenerate the frozen V12 predictions and metrics exactly.

### Evidence

The reproduction path:

- forced `solver="liblinear"`; and
- selected the recent training window using date-only ordering.

The frozen execution used the original solver behavior and deterministic ordering by `game_date, game_id`. These differences changed the fitted probabilities and evaluation metrics.

### Diagnosis — confirmed defect

The maintained repository code had diverged from the historical execution environment and row-order contract.

### Research impact

A reader could run the repository successfully but obtain results different from the frozen reports. That would weaken the reproducibility claim even though the original result artifacts were preserved.

### Corrective action

- Remove the solver override.
- Restore deterministic two-key ordering.
- Reproduce the original date-cluster bootstrap procedure.
- Add exact published-metric tests.
- Add saved-model probability replay tests.

### Verification

- Reproduced metrics match the frozen values within `1e-12`.
- Maximum absolute probability replay error for the CV model: `1.67e-16`
- Maximum absolute probability replay error for the development model: `2.78e-16`

### Records

- [Reproduction procedure](reproducibility.md)
- [Repository correction history](../CHANGELOG.md)
- [Model replay audit](../reports/frozen/V12_MODEL_BINARY_REPRODUCTION_AUDIT.json)

## F05 — canonical replay and identity reconciliation

### What happened

Canonical replay disagreed with the previously preserved 2026 derived-data stream on a small set of player-game scores and identities.

### Evidence

The initial 2026 reconciliation found:

- batter-input mismatches: `39`;
- pitcher-input mismatches: `21`;
- score mismatches: `40` among `14,891` replay rows; and
- `127` initially unresolved player-game occurrences in the broader identity-recovery stage.

The discrepancies included:

- incomplete strikeout-token coverage;
- stolen-base suffix interpretation;
- double-play and triple-play details;
- five incorrect historical player-ID rows;
- display-name formatting differences; and
- a stale July 8 source snapshot.

### Diagnosis — confirmed data-integrity defects

The discrepancies were traceable to specific parsing, identity, formatting, or source-snapshot problems. They were not treated as random noise and were not resolved by forcing the canonical data to match the older stream.

### Research impact

Without reconciliation, the same official game could produce different player scores or player identities depending on which preserved data version was used.

### Corrective action

- Treat official canonical records plus final numeric identity as the analytical source of truth.
- Correct the derived analytical tables rather than overwrite the historical evidence.
- Preserve reconciliation tables and the original data version.
- Resolve ambiguous identities only with occurrence-level or official evidence.

### Verification

- Final player-game occurrences resolved: `65,554/65,554`
- Unresolved occurrences: `0`
- Name-only forced merges: `0`
- Score-component mismatches in the corrected foundation: `0`
- Detected strict-prior temporal violations: `0`

### Records

- [Data lineage and quality checks](data_lineage_and_quality.md)

---

# B. Invalidated assumptions and evaluation risks

## F06 — predictive-ceiling claim invalidated

### What happened

The V5 audit initially suggested that model performance had flattened after roughly 600 games and that 224 additional features could not explain the remaining V2 errors.

### Evidence

The error-prediction models produced ROC AUC values near `0.5`, and additional features provided little improvement under the existing representation.

### Diagnosis — confirmed premise failure

The audit relied on the role-contaminated histories later identified in F03. It measured the limit of that feature representation, not the limit of clean batter, starter, and relief information.

### Research impact

The original conclusion could have incorrectly discouraged further player-role feature engineering. It was therefore withdrawn rather than preserved as a final ceiling claim.

### Corrective action

Shift the next stage from broader model tuning to role-specific feature redesign.

### Verification

Under the common V6 2025 temporal-OOF protocol:

- Team baseline Log loss: `0.687049`
- Team baseline plus clean start-only starter block: `0.677648`
- Difference: `−0.009401`

The later official-event batter redesign also added predictive signal. These results show that V5 described the limit of the contaminated representation, not a general predictive ceiling.

### Records

- [V5 ceiling audit](../research_records/reports/RQ1_V5_CEILING_AUDIT_REPORT.md)
- [Role-aware audit](../research_records/reports/RQ1_ROLE_AWARE_INCOME_AUDIT_REPORT.md)
- [Rebuild decision](../research_records/decisions/ROLE_AWARE_REBUILD_DECISION.json)

## F07 — accuracy and probability scores moved in opposite directions

### What happened

The V10 combined feature set increased thresholded classification accuracy but worsened the primary probability metrics.

### Evidence

Under the common strict 2025 holdout protocol:

| Model | Log loss | Brier score | Accuracy |
|---|---:|---:|---:|
| V9-style probability model | `0.667336` | `0.237412` | `58.31%` |
| V10 combined model | `0.667817` | `0.237603` | `59.74%` |

The paired-date 95% interval for the V10-minus-V9 Log-loss difference was `[−0.002909, 0.003879]`, and the estimated probability that V10 improved Log loss was `38.475%`.

### Diagnosis — confirmed evaluation conflict

Accuracy scores only the class decision after applying a threshold. Log loss and Brier score evaluate the full probability assignment, which was the primary target of this study. The result does not, by itself, prove one unique calibration failure mechanism.

### Research impact

Selecting V10 by accuracy alone would have changed the objective from probability forecasting to thresholded classification without stating that change.

### Corrective action

- Keep Log loss as the primary model-selection metric.
- Use Brier score and calibration as supporting probability metrics.
- Report accuracy as secondary evidence.
- Retain V10 only as an accuracy-oriented challenger.

### Verification

The simpler V9-style model remained the probability primary under the common 2024-selection/2025-holdout protocol.

### Records

- [V10 holdout results](../research_records/key_results/V10_2025_UNTOUCHED_HOLDOUT_RESULTS.csv)
- [Paired-date bootstrap](../research_records/key_results/V10_PAIRED_DATE_BOOTSTRAP.csv)

## F08 — reuse of validation and development periods

### What happened

The feature rows excluded target-game and same-date results, but some evaluation periods were inspected while the research design was still evolving.

Two forms of reuse must be distinguished:

1. **V11.1 batter design:** an initial candidate was developed with 2024 data, examined on 2025, and the prior-averaging structure was subsequently reviewed. The final 2025 result is therefore validation evidence, not an untouched final test.
2. **V12 learning-strategy comparison:** 2026 outcomes were used while comparing model families, regularization values, static windows, adaptive strategies, calibration, and ensembles.

### Evidence

For the V12 frozen candidates:

| Candidate | Selection status | 2026 development Log loss |
|---|---|---:|
| `L2_C0.03_ALL_EQUAL` | Selected by 2024–2025 temporal CV without using 2026 | `0.667390` |
| `L2_C0.1_RECENT_720` | Best observed after comparing methods on 2026 | `0.666135` |

The paired difference was `−0.001255`, with a 95% interval of `[−0.004790, 0.002336]` and a `74.61%` estimated probability favoring the recent-720 model.

### Diagnosis — evaluation risk

This is selection risk from reusing validation and development periods. It is not row-level target leakage: current-game, same-date, and future outcomes were excluded from each feature row.

### Research impact

The observed performance can support model development decisions, but it cannot establish a future-validated production champion or a final generalization claim.

### Corrective action

- Freeze both model specifications.
- Stop tuning the batter formula, shrinkage rule, regularization value, and training window on the observed periods.
- Introduce future ideas only as separately versioned challengers.
- Compare frozen candidates on predictions recorded before first pitch.

### Current status

- `L2_C0.03_ALL_EQUAL` is reported as the cleaner CV-selected reference candidate.
- `L2_C0.1_RECENT_720` is reported as the best observed development candidate.
- Prospective evaluation is required before either is described as future validated.

### Records

- [Model-selection decision](../reports/frozen/V12_MODEL_SELECTION_DECISION.json)
- [Paired date-cluster comparison](../reports/frozen/V12_2026_PAIRED_DATE_BOOTSTRAP.csv)
- [Scientific status and allowed claims](scientific_status_and_claims.md)
- [Prospective validation protocol](prospective_validation.md)

## F09 — historical lineups were not independently timestamped pregame snapshots

### What happened

Historical starting lineups and starting pitchers were reconstructed from official completed-game records. The records identify who started, but the frozen historical dataset does not independently prove when every lineup snapshot was captured before first pitch.

### Evidence

The canonical data contain complete official starting-lineup structure:

- starting-lineup rows: `33,552`;
- exact starters per game: `18`;
- exact starters per team: `9`.

However, independent historical pregame capture timestamps are not available for every reconstructed game.

### Diagnosis — evaluation risk

The retrospective pipeline enforces strict date cutoffs and does not use target-game outcomes in player histories. Nevertheless, lineup availability is reconstructed from completed-game official records rather than demonstrated by an immutable historical pregame feed.

### Research impact

The historical study can evaluate a **reconstructed lineup-confirmed setting**, but it should not claim that every historical input was independently archived before first pitch.

### Corrective action

- Describe the historical experiment explicitly as retrospective reconstruction.
- Do not use reconstructed lineup records as proof of historical capture timing.
- In prospective operation, store prediction time, source cutoff time, official lineup and starter snapshots, source hashes, feature hashes, and model hashes before first pitch.

### Current status

The limitation is documented. Genuine timestamped pregame validation begins only with the immutable prospective ledger.

### Records

- [Data card](data_card.md)
- [Limitations](limitations.md)
- [Prospective validation protocol](prospective_validation.md)

---

# C. Negative modeling results and research decisions

These entries describe experiments that ran as intended but did not support adoption. They are not software failures. They are retained because rejecting unsupported complexity is part of the model-selection evidence.

## F10 — instability in the 2026-only branch

### What happened

The initial 2026-only branch did not produce stable or strong enough pregame probabilities to justify continued search on the same sample.

### Evidence

- Completed games: `424`
- Binary decision games after excluding ties: `416`
- Temporal outer predictions: `281`
- Strongest development candidate:
  - Log loss: `0.685090`
  - Brier score: `0.246008`
  - ROC AUC: `0.573867`
- Later 337-feature search Log loss: `0.693281`

The `281` outer predictions came from the defined temporal evaluation folds; they were not presented as an independent 281-game random sample. The strongest candidate also produced probabilities concentrated near `0.5`.

### Diagnosis — supported explanation

The effective sample was small relative to the number of inspected features, transformations, models, and fold choices. Repeated observations of the same teams and game dates further reduced the amount of independent information. The evidence supports these factors collectively, but the study did not isolate one sole cause.

### Research impact

Continuing to add candidates after repeatedly observing the same period would increase model-selection risk without creating stronger evidence.

### Corrective action

Close the branch as a valid negative result and rebuild the study on official 2024–2026 multi-season data.

### Verification

The expanded foundation contained `1,824` decision games across three seasons. The Phase 1 result remained documented as a negative result and was not reinterpreted after the expansion.

### Records

- [Phase 1 and Phase 2 research history](research_journey.md#phase-1--2026-only-limited-sample-study)

## F11 — broader complexity did not improve temporal performance

### What happened

The V3 search added substantially more features, model families, and configurations but performed worse than the stabilized V2 model.

### Evidence

V3 evaluated:

- candidate columns: `763`;
- selected features: `162`;
- model families: `9`;
- configurations: `37`;
- approximate temporal fits: `610`.

| Model | Log loss |
|---|---:|
| V2 stabilized logistic model | `0.670610` |
| V3 ensemble | `0.677185` |


### Diagnosis — supported explanation

Redundant predictors, limited independent signal, model-selection variance, and excess model capacity are all consistent with the result. Their individual causal contributions were not isolated.

### Research impact

The experiment rejected the assumption that a larger feature space or a more complex learner was automatically preferable.

### Corrective action

Require out-of-time improvement in probability quality before accepting additional complexity.

### Verification

V12 again compared regularized linear models, tree and boosting families, ensembles, calibration, adaptive retraining, and online updating. Strongly regularized L2 logistic regression remained the temporal-CV winner.

### Records

- [V3 research history](research_journey.md#v3--broad-complex-model-search)
- [V12 model-family temporal CV](../reports/frozen/V12_MODEL_FAMILY_TEMPORAL_CV.csv)

## F12 — the first batter index failed integrated evaluation

### What happened

The initial batter index improved a standalone batter-domain model but worsened the stronger V7 integrated model.

### Evidence

Under the V8 2025 protocol:

- Standalone team baseline Log loss: `0.687435`
- Standalone selected batter model: `0.682866`
- V7 integrated model: `0.669483`
- V7 plus the selected batter index: `0.673388`
- Integrated difference: `+0.003905` (worse)

### Diagnosis — supported explanation

The first score design, prior averaging method, and lineup aggregation did not provide robust incremental information beyond the existing team and starting-pitcher components. Signal overlap is plausible, but it was not established as the only cause.

### Research impact

A favorable standalone result was not treated as sufficient evidence for inclusion in the final combined model.

### Corrective action

Reject the V8 batter addition and rebuild the batter index from official batting events without using the legacy batter score.

The redesign compared:

- official-event game-score candidates: `215`;
- player prior-averaging methods: `20`;
- lineup aggregation blocks: `6`.

### Verification

The selected V11.1 batter system produced:

- 2025 validation Log loss with batter block: `0.665020`
- 2025 validation Log loss without batter block: `0.668954`
- Difference: `−0.003934`
- 95% interval: `[−0.010585, 0.002925]`

Under the best-observed 2026 development protocol, removing the batter block worsened Log loss by `0.007022`, with a 95% interval of `[0.000548, 0.013416]` in favor of retaining it. That result remains development evidence because 2026 was used during method comparison.

### Records

- [V8 integration results](../research_records/key_results/V8_2025_PREDICTION_APPLICATION_RESULTS.csv)
- [V11.1 candidate comparison](../reports/frozen/V11_1_ROBUST_CANDIDATE_COMPARISON.csv)
- [V12 batter ablation](../reports/frozen/V12_2026_BATTER_ABLATION_RESULTS.csv)

## F13 — the player-level relief index added no reliable pregame signal

### What happened

The tested player-level relief-pitcher indices did not improve leakage-safe pregame probability forecasts.

### Evidence

- Preliminary V6 relief screen: Log-loss difference `+0.000967` (worse)
- V8 selected relief index versus team baseline: `0.687444` versus `0.687435` (effectively null)
- V7 model versus V7 plus relief index: `0.669483` versus `0.674253`
- Integrated difference: `+0.004770` (worse)
- 2026 post-hoc addition: Log-loss difference `+0.001113` (worse)

### Diagnosis — supported explanation

The actual relievers who will enter a game are unknown before first pitch. A leakage-safe player-level feature must approximate an available pool from prior appearances, workload, rest, and roster evidence. That pool can include pitchers who never appear and omit unobserved availability constraints. This is a plausible representation limit, not a uniquely proven cause.

### Research impact

The negative result applies to the tested pregame representation. It is not evidence that relief pitching is unimportant to baseball outcomes.

### Corrective action

- Reject the tested player-level relief index.
- Retain team-level post-starter run-prevention context only as a challenger.
- Defer stronger player-level claims until point-in-time roster and availability data are available.

### Verification

The V9 recent-20 team measure improved V7 Log loss by `−0.000478`, but its 95% interval `[−0.003102, 0.002145]` included zero. It was therefore not promoted as a confirmed replacement.

### Records

- [V6 role ablation](../research_records/key_results/V6_1_V2_CHALLENGER_AND_DOMAIN_ABLATION.csv)
- [V8 domain comparison](../research_records/key_results/V8_DOMAIN_BASELINE_AND_LEGACY_COMPARISON.csv)
- [Detailed relief-index analysis](relief_pitcher_index_negative_result.md)

## F14 — adaptive retraining did not beat the best static window

### What happened

Expanding, rolling, decay-weighted daily retraining, and online updates did not improve on the strongest static recent-window model.

### Evidence

Under the V12 2026 development protocol:

- Best adaptive daily method, `L2_C0.03 / EXPANDING_DAILY`: Log loss `0.668838`
- Best static method, `L2_C0.1 / RECENT_720`: Log loss `0.666135`
- Tested online SGD variants were substantially worse, with Log loss above `1.25`.

### Diagnosis — supported explanation

Frequent refitting can follow short-term noise when the effective sample is modest and the feature set already summarizes recent performance. The results support that explanation but do not isolate it as the only mechanism.

### Research impact

Automatically replacing the frozen model with a frequently updated version would add operational and statistical complexity without demonstrated probability improvement.

### Corrective action

Treat adaptive and online methods as separately versioned challengers rather than automatic replacements.

### Verification

The static CV-selected and recent-720 specifications were preserved for prospective comparison.

### Records

- [V12 adaptive-strategy results](../reports/frozen/V12_2026_ADAPTIVE_STRATEGY_RESULTS.csv)

---

# Cross-cutting lessons

The failures and negative results changed the project in five durable ways:

1. **Aggregate coverage is not enough.** Quality checks must be separated by side, role, season, and data source so impossible asymmetries are visible.
2. **Feature meaning must be audited before model complexity.** A precisely trained model cannot repair a history variable that mixes different player roles.
3. **Standalone signal is not incremental signal.** A domain feature is accepted only if it improves the stronger combined model under temporal evaluation.
4. **Probability forecasting requires probability metrics.** Accuracy remains useful, but it does not replace Log loss, Brier score, or calibration.
5. **Reproducibility and scientific validity are separate requirements.** Exact metric replay, leakage-safe rows, honest development-period labels, and future prospective validation are all necessary.

The ledger therefore supports the final research narrative: the project advanced not by hiding failed experiments, but by using audits and negative results to improve the data foundation, narrow the claims, redesign the player indices, and define a prospective test that the development data can no longer influence.
