# Research failures, negative results, and corrective actions

This ledger records the defects, invalidated assumptions, negative results, and evaluation risks that materially changed the dataset, feature definitions, validation protocol, model selection, reproducibility status, or scientific conclusions.

Each entry answers five questions:

1. **What happened?**
2. **What evidence established the problem or result?**
3. **What was the diagnosis, and how certain was it?**
4. **How did it affect the research?**
5. **What changed, and what was verified afterward?**

The diagnosis labels distinguish evidence from interpretation:

- **Confirmed defect:** an audit directly established a data, parsing, implementation, or reproducibility error.
- **Confirmed negative result:** the tested feature, model, or training strategy failed to improve the primary objective under its stated protocol.
- **Invalidated claim:** later evidence showed that an earlier conclusion rested on an unsuitable feature definition or evaluation premise.
- **Evaluation conflict:** different metrics favored different choices, requiring an explicit decision about the research objective.
- **Supported explanation:** the evidence supports a likely mechanism, but does not prove it was the only cause.
- **Evaluation risk:** the analysis may be leakage-safe at the row level while still having limits that weaken a final generalization claim.

Direct model comparisons below are made only within the same evaluation protocol. Metrics from different stages are not combined into one leaderboard.


---

# 1. Why the study changed direction

## F01 — the 2026-only study produced weak and unstable probabilities

**What happened:** The project began with `424` completed 2026 games through July 9 and `416` non-tie decisions. It tested team, lineup, starter, player-index, price, rank, nonlinear, ensemble, and effect-shape branches.

**Evidence:** The strongest development point estimate remained weak:

| Phase 1 model | Log loss | Brier score | ROC AUC | Accuracy |
|---|---:|---:|---:|---:|
| `RANK_ADAPTIVE_V1` | `0.685090` | `0.246008` | `0.573867` | `58.72%` |
| 337-feature research model | `0.693281` | `0.249958` | `0.529567` | `51.60%` |

Most probabilities remained close to `0.5`, and the larger model performed approximately at the constant-probability benchmark.

**Diagnosis — confirmed negative result with a supported explanation:** The tested models did not provide strong out-of-time probability forecasts. The limited temporal sample, repeated observations of the same teams and dates, and extensive candidate search plausibly increased selection variance. The study did not claim that sample size was the only cause.

**Research impact:** Continuing to search the same inspected 2026 period would have increased selection risk without creating independent evidence.

**Change and verification:** Phase 1 was closed as a valid negative result. The project then collected official 2024 and 2025 records and rebuilt the study on `1,864` completed games, `65,554` player-game occurrences, and `1,824` non-tie modeling rows.

**Supporting material:** [research journey](research_journey.md#phase-1--2026-only-limited-sample-study) · [data card](data_card.md)

---

# 2. Data-foundation defects

## F02 — starter identity was asymmetric between home and away teams

**What happened:** The first 2026 starter-history pipeline processed home and away pitcher tokens through different eligibility paths.

**Evidence:** The audit found an impossible pattern:

- home starter history eligibility: `416/416`;
- away starter history eligibility: `0/416`;
- prior-start difference: positive `331`, zero `85`, negative `0`.

**Diagnosis — confirmed defect.** Home starter tokens usually contained numeric KBO IDs, while away starter tokens often appeared as names. The original history-eligibility path accepted the former and rejected the latter.

**Research impact:** Starter-history variables could reflect source-token format rather than pitcher performance. All affected starter claims were discarded.

**Change and verification:** Identity resolution was rebuilt with official IDs, season-team evidence, profile records, targeted daily records, and occurrence-level fingerprints. Source starters were resolved `848/848`; model-period starters became eligible home `416/416` and away `416/416`; final multi-season identity resolution reached `65,554/65,554`, with zero name-only forced merges.

**Supporting material:** [data lineage and quality](data_lineage_and_quality.md)

## F03 — innings parsing failed on valid baseball notation

**What happened:** An early structured-model run completed even though the intended starter-income and run-prevention domains were empty or constant. Later pitcher-feature preflight then encountered ambiguous innings fields and valid fractions such as `1/3`, `2/3`, `5 1/3`, and `5 2/3`.

**Evidence:** The first validator did not stop the empty critical domain, so that run was invalid for any starter-value claim. The later fail-closed preflight correctly stopped before model fitting because the schema resolver could not consistently distinguish raw innings notation from already-converted outs, and the parser did not cover every one-third and two-thirds representation.

**Diagnosis — confirmed defect.** The pipeline lacked one canonical internal unit. Baseball notation such as `5.1` cannot be interpreted as 5.1 decimal innings.

**Research impact:** Workload, rate, and run-prevention variables from the affected path could not be trusted. These failed runs were treated as implementation diagnostics, not evidence that pitcher data lacked predictive value.

**Change and verification:** All internal innings calculations were standardized as integer outs. Exact source-column resolution, fraction unit tests, actual-data preflight, and fail-closed minimum-coverage gates were added before model training. The earlier structured result remains preserved as an invalid implementation attempt, not a negative result about pitcher information.

**Supporting material:** [data lineage and quality](data_lineage_and_quality.md)

## F04 — canonical replay exposed scoring and identity disagreements

**What happened:** The official multi-season canonical replay did not exactly match the previously preserved 2026 derived dataset.

**Evidence:** Initial reconciliation found:

- batter-input mismatches: `39`;
- pitcher-input mismatches: `21`;
- score mismatches: `40` among `14,891` replay rows;
- initially unresolved player-game occurrences: `127`.

The traced causes included strikeout-token coverage, stolen-base suffix interpretation, double-play details, five incorrect historical player IDs, display-name formatting, and a stale July 8 source snapshot.

**Diagnosis — confirmed defect:** Each discrepancy was tied to a concrete parsing, identity, formatting, or source-snapshot cause.

**Research impact:** Without reconciliation, the same official game could produce different player identities or scores depending on the preserved data version.

**Change and verification:** Official canonical records plus final numeric identity became the analytical source of truth. Corrected derived tables were created without overwriting historical evidence. Final checks recorded `65,554/65,554` resolved occurrences, `0` unresolved occurrences, `0` name-only forced merges, `0` scoring-component mismatches, and `0` strict-prior temporal violations.

**Supporting material:** [data lineage and quality](data_lineage_and_quality.md) · [final dataset validation](../reports/reproduced/dataset_validation.json)

---

# 3. Early model-development results

## F05 — V1 suggested signal, but the result was not conclusive

**What happened:** The first multi-season lineup-confirmed model tested whether strict-prior player averages improved a conventional team baseline.

**Evidence:** On `416` non-tie 2026 games:

| V1 model | Log loss | Brier score | ROC AUC | Accuracy |
|---|---:|---:|---:|---:|
| Team baseline | `0.685329` | `0.246102` | `0.572792` | `56.01%` |
| Income Core | `0.681950` | `0.244315` | `0.594917` | `58.41%` |
| Income Extended | `0.680663` | `0.243667` | `0.594245` | `56.49%` |

The Core-versus-baseline date-cluster bootstrap interval crossed zero.

**Diagnosis — supported explanation:** The favorable point estimates suggested incremental player signal, but low early-season sample counts and cold starts made the prior averages unstable.

**Research impact:** The result was reported as directionally positive but statistically inconclusive. The project did not treat V1 as proof.

**Change and verification:** V2 introduced train-fitted imputation, missing indicators, previous-season information, and K-shrunk cross-season averages. In the already-observed 2026 comparison, V2 improved Log loss from V1 Extended `0.680663` to `0.670610`; the paired interval was `[−0.018242, −0.002074]`. V2 was retained as a stabilized historical baseline, not as the final clean-role model.

**Supporting material:** [V1–V2 decision history](research_journey.md#v1--first-lineup-confirmed-temporal-model)

## F06 — more complexity and different learning schedules did not improve V2

**What happened:** V3 expanded the feature and algorithm search; V4 changed weighting, windows, retraining, ensembling, and the first Poisson implementation.

**Evidence:** V3 evaluated `763` candidate columns, `162` selected features, `9` model families, `37` configurations, and roughly `610` temporal fits:

| Model or strategy | 2026 Log loss |
|---|---:|
| V2 reference | **`0.670610`** |
| V3 ensemble | `0.677185` |
| V4 730-day decay | `0.670973` |
| V4 online expanding | `0.672144` |
| V4 learned stack | `0.672703` |
| V4 recent 1,000 games | `0.674724` |
| V4 Poisson alpha 10 | `0.679821` |

**Diagnosis — confirmed negative result with a supported explanation:** The tested extra complexity and training schedules did not improve out-of-time probability quality. Redundant features, limited independent signal, selection variance, and excess capacity are plausible explanations, but no single cause was isolated.

**Research impact:** The project rejected the idea that a more sophisticated algorithm or more frequent retraining would automatically fix the model.

**Change and verification:** V2 remained the reference. The next investigation shifted from model tuning to auditing what the player-history features actually represented.

**Supporting material:** [V3–V4 experiment history](research_journey.md#v3--broad-complex-model-search)

---

# 4. Role definitions changed the scientific conclusion

## F07 — role contamination invalidated the V5 predictive-ceiling claim

**What happened:** Histories intended for starting batters and starting pitchers included prior appearances from different roles. V5 had already used those histories to argue that the available BoxScore signal might be near a practical ceiling.

**Evidence:** The role audit found:

- `25,870/33,121` experienced starting-batter rows included substitute history (`78.11%`);
- `726/3,496` experienced starting-pitcher rows included relief history (`20.77%`);
- among `614` pitchers with both roles, the median absolute all-role versus start-only difference was `149.14`, and the 90th percentile was `779.51`.

The earlier V5 error-prediction models had ROC AUC around `0.497–0.510`, but they were evaluating the contaminated representation.

**Diagnosis — confirmed defect and invalidated claim:** The history key separated season, player, and broad position type, but not game role. V5 therefore measured the limit of the old representation, not the limit of clean role-specific information.

**Research impact:** The predictive-ceiling claim was withdrawn. Earlier models remained historical baselines, but they could no longer be described as clean role-specific models.

**Change and verification:** Strict-prior histories were rebuilt by role, with start-only history for starting pitchers. Batter, starter, and relief blocks were then evaluated separately. The clean starter result in F08 demonstrated that the earlier ceiling did not apply to the corrected representation.

**Supporting material:** [role-contamination decision history](research_journey.md#v5--ceiling-audit-role-contamination-and-research-pivot) · [role-specific model comparison](../research_records/key_results/V6_1_V2_CHALLENGER_AND_DOMAIN_ABLATION.csv)

## F08 — the corrective redesign showed that starter information carried the strongest role-specific signal

**What happened:** V6 tested six official-record scoring families under the corrected role-aware history design. V7 then tested how to integrate the selected starter index.

**Evidence:** Under one common 2025 temporal-OOF team-baseline protocol:

| Added role block | Log loss | Difference from team baseline |
|---|---:|---:|
| Team baseline | `0.687049` | — |
| Starting-lineup batter block | `0.687465` | `+0.000417` |
| Clean start-only starter block | **`0.677648`** | **`−0.009401`** |
| Player-level relief block | `0.688016` | `+0.000967` |

V7 integration results under its common 2025 protocol were:

| Integration method | Log loss |
|---|---:|
| V2 direct | `0.678417` |
| Starter model direct | `0.670455` |
| Fixed probability blend | `0.670051` |
| Temporal OOF logit stack | **`0.669483`** |

The stack-versus-V2 difference was `−0.008934`, with paired 95% interval `[−0.017472, −0.000544]`.

**Diagnosis — supported explanation:** The corrected starter representation contained strong incremental signal, and its probability output complemented the stabilized V2 component better than direct feature concatenation.

**Research impact:** The project abandoned a universal one-score-fits-all assumption. Role-specific models and modular probability integration became the main architecture.

**Change and verification:** `KBO_CONSTRAINED` start-only scoring with a K=10 prior was frozen as the starter index. V2 and starter components were trained separately, and the meta model used temporal out-of-fold logits only. The initial V7 evaluation had omitted the first 2025 date; corrected V7 v1.1 restored all dates and is the authoritative result reported here.

**Supporting material:** [starter-index design](player_index_design.md#starting-pitcher-index) · [integration results](../research_records/key_results/V7_APPLICATION_METHOD_RESULTS.csv)

---

# 5. Batter and relief-pitcher representation failures

## F09 — the first batter index helped alone but harmed the integrated model

**What happened:** The V8 batter index improved a standalone batter-domain model, but adding it to the stronger V7 starter architecture made the complete probability model worse.

**Evidence:** Under the 2025 V8 protocol:

| Comparison | Log loss |
|---|---:|
| Team baseline | `0.687435` |
| Selected V8 batter index | `0.682866` |
| V7 starter stack | **`0.669483`** |
| V7 + V8 batter | `0.673388` |

The index therefore showed domain signal but negative incremental value after the stronger components were already present.

**Diagnosis — confirmed negative result with a supported explanation:** Standalone performance did not guarantee complementary information. Redundancy with team and starter variables, unstable rate-volume balance, and limitations of the first score design are plausible explanations.

**Research impact:** The V8 batter block was rejected. The project did not generalize this result into the claim that batter information was useless.

**Change and verification:** V11.1 rebuilt the batter index from official batting events without legacy batter scores. It searched `215` score candidates, multiple prior methods, lineup aggregations, and model families. On 698 games in 2025 validation, the new batter block improved Log loss from `0.668954` without the block to `0.665020`; the difference was `−0.003934`, but the interval `[−0.010585, 0.002925]` still crossed zero. In the later V12 2026 development ablation, the best observed model improved from `0.673157` without the batter block to `0.666135` with it; that larger gain is development evidence because 2026 was used during strategy comparison.

**Supporting material:** [initial integration results](../research_records/key_results/V8_2025_PREDICTION_APPLICATION_RESULTS.csv) · [rebuilt batter-index design](player_index_design.md#batter-index-power_obp__rate100)

## F10 — the player-level relief index failed because pregame deployment could not be represented reliably

**What happened:** V8 built a strict-prior player-level relief-pitcher index. Because the actual target-game relievers are known only after the game, the feature had to approximate a candidate pool from earlier appearances.

**Evidence:** The index failed both standalone and integrated comparisons:

| Evaluation | Reference Log loss | With relief index | Difference |
|---|---:|---:|---:|
| 2025 standalone relief domain | `0.687435` | `0.687444` | `+0.000009` |
| 2025 added to V7 | `0.669483` | `0.674253` | `+0.004770` |
| 2026 post-hoc addition | `0.667785` | `0.668898` | `+0.001113` |

Positive differences are worse. The standalone 2025 improvement probability was `49.95%`, effectively a null result.

**Diagnosis — confirmed negative result with a supported explanation:** Relief pitching matters, but the tested pregame player-level representation was structurally noisy:

- the actual relievers and their innings are unknown before first pitch;
- deployment depends on score, inning, leverage, starter exit, handedness, and strategy;
- using actual target-game relievers would leak postgame information;
- a broad prior pool includes pitchers who may never enter;
- workload, recovery, injury, and roster availability change from day to day.

The study supports these mechanisms but did not isolate the individual contribution of each.

**Research impact:** The player-level relief index was removed from the primary architecture. The conclusion was limited to the tested representation, not to the importance of relief pitching itself.

**Change and verification:** V9 moved to a simpler team-level strict-prior measure: runs officially assigned to non-starting pitchers per team game. A recent-20 version changed the V7 architecture from `0.669483` to `0.669004` in 2025, but the difference `−0.000478` had interval `[−0.003102, 0.002145]`. It remained a challenger, not a proven replacement. This responsibility-run measure is not identical to physical runs scored after the starter exits; exact post-exit runs require play-by-play timelines.

**Supporting material:** [relief-index negative-result analysis](relief_pitcher_index_negative_result.md) · [team-level replacement results](../research_records/key_results/V9_2025_V7_REPLACEMENT_RESULTS.csv)

---

# 6. Later feature and model-selection limits

## F11 — richer pregame features improved Accuracy but worsened probability scores

**What happened:** V10 added starter workload, pitch count, handedness matchup, batting-order structure, lineup continuity, and missing-regular proxies.

**Evidence:** Under the common strict 2025 holdout protocol:

| Model | Log loss | Brier score | Accuracy |
|---|---:|---:|---:|
| V9-style model | **`0.667336`** | **`0.237412`** | `58.31%` |
| V10 combined | `0.667817` | `0.237603` | **`59.74%`** |

V10 improved Accuracy by `1.43` percentage points but worsened Log loss by `+0.000481` and Brier score by `+0.000191`. The estimated probability of Log-loss improvement was only `38.48%`.

**Diagnosis — evaluation conflict and confirmed negative result:** Accuracy evaluates a thresholded class decision; Log loss and Brier score evaluate the complete probability forecast, which was the primary objective.

**Research impact:** Selecting V10 by Accuracy alone would have silently changed the research task from probability forecasting to classification.

**Change and verification:** Log loss remained the primary selection metric, with Brier score and calibration as supporting metrics. V10 was preserved only as an accuracy-oriented challenger.

**Supporting material:** [holdout results](../research_records/key_results/V10_2025_UNTOUCHED_HOLDOUT_RESULTS.csv) · [paired bootstrap](../research_records/key_results/V10_PAIRED_DATE_BOOTSTRAP.csv)

## F12 — complex model families and adaptive retraining did not beat static L2 logistic regression

**What happened:** V12 held the corrected batter and starter representations fixed and compared regularized linear models, tree and boosting families, training windows, decay, daily retraining, online updates, ensembles, and calibration.

**Evidence:** In 2024–2025 temporal CV, L2 Logistic achieved the best family result:

| Family | CV Log loss |
|---|---:|
| L2 Logistic | **`0.668643`** |
| Elastic Net | `0.669683` |
| XGBoost | `0.675691` |
| Random Forest | `0.675770` |
| Gradient Boosting | `0.676440` |

In the 2026 development comparison:

| Strategy | Log loss |
|---|---:|
| Static L2 C=`0.1`, recent 720 games | **`0.666135`** |
| Mean ensemble of top six CV models | `0.667718` |
| Platt-calibrated CV champion | `0.668225` |
| Best daily retraining | `0.668838` |
| Isotonic-calibrated CV champion | `0.725047` |

**Diagnosis — confirmed negative result with a supported explanation:** At this sample size and with these fixed features, strongly regularized logistic regression was more stable than the tested nonlinear and continuously adapting methods. Frequent refitting can follow short-term noise, but the experiment did not prove that this was the only cause.

**Research impact:** The project did not adopt complex models, calibration, ensembling, or daily retraining for presentation value alone.

**Change and verification:** Two static L2 candidates were frozen: a 2024–2025 CV-selected reference (`C=0.03`, all history) and the best-observed 2026 development model (`C=0.1`, recent 720). Their 2026 Log-loss difference was only `−0.001255`, with interval `[−0.004790, 0.002336]`, so the recent-720 model was not declared definitively superior.

**Supporting material:** [model-selection summary](model_selection_ablation_and_calibration.md) · [reproduction code](../scripts/reproduce_core_results.py)

---

# 7. Evaluation and reproducibility boundaries

## F13 — leakage-safe feature rows did not make reused periods untouched tests

**What happened:** Current-game, same-date, and future outcomes were excluded from each feature row, but labeled evaluation periods were inspected while the method was still evolving.

**Evidence:** Two forms of reuse occurred:

1. V11.1 examined a 2024-developed batter candidate on 2025 and then reviewed the prior-averaging structure; the final 2025 result is validation evidence.
2. V12 used 2026 outcomes to compare regularization, windows, adaptive strategies, calibration, and ensembles; recent-720 is therefore development-selected.

**Diagnosis — evaluation risk, not row-level leakage:** Each prediction used strict-prior information, but repeated method selection on a labeled period can make observed performance optimistic.

**Research impact:** The project cannot call 2025 in V11.1 or 2026 in V12 a final untouched test. The recent-720 model is a development champion, not a future-validated production model.

**Change and verification:** Both the CV-selected and development-selected models were frozen. Further adjustment of the batter formula, shrinkage rule, regularization, or training window using observed 2026 results was prohibited. Final comparison moved to an immutable prospective ledger.

**Supporting material:** [temporal-validation contract](temporal_validation_and_leakage.md) · [prospective-validation protocol](prospective_validation.md)

## F14 — historical lineups did not have an immutable pregame timestamp for every game

**What happened:** Official historical records identify the starting lineup and starting pitcher, but the archive does not contain an independent pre-first-pitch capture timestamp for every game.

**Evidence:** The canonical foundation contains exact starting-lineup rows for all `1,864` games, but historical confirmation time is not independently archived for every row.

**Diagnosis — evaluation risk:** The retrospective features are outcome-leakage controlled, but the historical input feed cannot be represented as an immutable timestamped pregame capture in the same way as future predictions.

**Research impact:** Historical evaluation must be described as reconstructed lineup-confirmed pregame analysis, not as proof that every input was captured and sealed before first pitch.

**Change and verification.** The prospective protocol requires prediction time, source cutoff time, lineup and starter snapshot hashes, model and feature hashes, and separate postgame settlement. The original prediction record cannot be edited after the result becomes known.

**Supporting material:** [data card](data_card.md) · [prospective-validation protocol](prospective_validation.md)

## F15 — maintained repository code initially diverged from the frozen execution

**What happened:** An early maintained reproduction path ran without an error but did not exactly reproduce the frozen V12 probabilities and metrics.

**Evidence:** The maintained path forced `solver="liblinear"` and selected the recent training window using date-only ordering. The frozen execution used its original solver behavior and deterministic ordering by `game_date, game_id`.

**Diagnosis — confirmed defect:** The repository implementation had drifted from the historical execution contract.

**Research impact:** A reader could successfully run the code and still obtain values different from the frozen reports, weakening the reproducibility claim.

**Change and verification:** The solver override was removed, deterministic two-key ordering was restored, and exact metric and model-replay tests were added. Reproduced metrics match within `1e-12`; maximum absolute probability replay error is `1.67e-16` for the CV model and `2.78e-16` for the development model.

**Supporting material:** [reproducibility guide](reproducibility.md) · [saved-model replay test](../tests/test_saved_model_replay.py)

---

# Methodological lessons for data science

1. **Feature quality matters more than model complexity:**  
   Incorrectly defined or contaminated features cannot be fixed by using a more sophisticated model.

2. **Only information available at prediction time should be used:**  
   Pregame models must exclude variables that depend on future player deployment or game outcomes.

3. **Features should be tested for incremental value:**  
   Strong standalone performance does not guarantee improvement when a feature is added to an existing model.

4. **Validation must match the prediction setting:**  
   Temporal splits, strict-prior features, and same-date exclusion were necessary to prevent leakage and estimate realistic performance.

5. **Evaluation metrics must match the research objective:**  
   Because the goal was probability forecasting, Log loss and Brier score were prioritized over Accuracy.

6. **Negative results and reproducibility strengthen the study:**  
   Failed experiments helped refine feature design, while uncertainty analysis and exact replay limited overconfident conclusions.
