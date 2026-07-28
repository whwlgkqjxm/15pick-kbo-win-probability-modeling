# Player-level relief-pitcher index: negative result

## Research question

This experiment tested whether a leakage-safe player-level relief-pitcher representation could add pregame probability information beyond the existing team and starting-pitcher components.

The result was negative: the best tested relief representation did not improve the team baseline and made the stronger integrated model worse. The conclusion applies to the tested representation, not to the general importance of relief pitching.

## What was tested

The best observed historical candidate used the following three-stage construction.

### 1. Relief-appearance game score

Only official relief appearances were included:

```text
180 × outs
+ 90 × strikeouts
− 260 × hits allowed
− 420 × home runs allowed
− 230 × (walks + hit by pitch allowed)
− 350 × earned runs
```

### 2. Strict-prior player estimate

Each reliever's earlier relief scores were averaged with `K=3` hierarchical shrinkage. The first center was the same pitcher's earlier mean across all pitching appearances; a league-level fallback was used when player history was unavailable. Current-game and same-date results were excluded.

### 3. Pregame candidate pool

A pitcher was eligible when the team had used that pitcher in relief during the previous 30 days. The target game's named starter was removed. Eligible pitchers were combined with a 14-day recency half-life, and no additional fatigue multiplier was selected.

The target game's actual relievers and their actual innings were never used. The resulting team block included the recency-weighted pool mean together with top-three, depth, reliability, and recent-workload summaries.

The historical identifiers for this specification were `P_RUN_PREVENT`, `HIER_ALL_K3`, and `W30_H14_NONE`. They are retained here for traceability rather than used as the primary explanation.

## Evaluation results

Log loss is lower when probability estimates are better. The 2025 comparisons used 698 non-tie games; the 2026 post-hoc comparison used 416.

| Evaluation | Reference Log loss | With relief index | Difference | Games |
|---|---:|---:|---:|---:|
| 2025 standalone relief-domain comparison | 0.687435 | 0.687444 | +0.000009 | 698 |
| 2025 added to the frozen starter-stack reference | 0.669483 | 0.674253 | +0.004770 | 698 |
| 2026 post-hoc addition | 0.667785 | 0.668898 | +0.001113 | 416 |

Positive differences are worse. In the standalone 2025 comparison, the relief model had lower Log loss in `49.95%` of paired date-cluster bootstrap replicates, which is effectively indistinguishable from chance. This percentage is not a posterior probability that the relief model is truly superior.

![Relief-pitcher feature result](../reports/figures/relief_index_negative_result.png)

The 2025 domain result is available in the [domain comparison table](../research_records/key_results/V8_DOMAIN_BASELINE_AND_LEGACY_COMPARISON.csv). The integration results are recorded separately for [2025](../research_records/key_results/V8_2025_PREDICTION_APPLICATION_RESULTS.csv) and the [2026 post-hoc period](../research_records/key_results/V8_2026_POSTHOC_APPLICATION_RESULTS.csv).

## Why the representation was difficult

The experiment did not isolate one single cause, but the following structural limitations are consistent with the result:

- The relievers who will enter a game are unknown before first pitch.
- Deployment depends on score, inning, leverage, starter exit, handedness, and managerial strategy.
- Using the actual relievers or their actual innings would introduce postgame leakage.
- A broad prior pool includes pitchers who may never appear, which dilutes the signal.
- Availability changes with workload, recovery, injury, and roster status.
- Individual relief samples are small and strongly affected by role and leverage.

The pool construction itself passed the recorded leakage checks: same-date history was excluded, the target starter was not present in the pool, all values were finite, and the manually recomputed weighted mean matched the feature. See the [average-comparison audit](../research_records/key_results/V8_SELECTED_AVERAGE_COMPARISON_AUDIT.csv).

## Modeling decision

The retained primary architecture excludes the tested player-level relief block. It continues to use team-level strict-prior measures of bullpen and post-starter run prevention.

A follow-up experiment tested a recent-20-game team responsibility-run measure in place of the cumulative version:

| Team-level replacement test | 2025 Log loss |
|---|---:|
| Frozen starter-stack reference | 0.669483 |
| With recent-20 team measure | 0.669004 |

The difference was `−0.000478`, with a paired date-cluster interval of `[-0.003102, 0.002145]`. The recent-20 version was therefore treated as a challenger rather than a confirmed replacement. Full results are in the [replacement table](../research_records/key_results/V9_2025_V7_REPLACEMENT_RESULTS.csv) and [bootstrap record](../research_records/key_results/V9_V7_REPLACEMENT_BOOTSTRAP.csv).

The later 14-feature architecture retains the cumulative bullpen-strength measure and the recent-20 post-starter measure as separate conventional pregame variables. Neither is a player-level relief index.

These team measures use runs officially assigned to non-starting pitchers. They are not identical to every physical run scored after the starter leaves the game; exact post-exit runs would require play-by-play substitution and scoring timelines.

## Interpretation

The experiment supports a narrow conclusion: this leakage-safe player-pool representation did not add reliable predictive value in the evaluated periods. It does not show that relief pitching is unimportant.

A stronger future design would require pregame roster availability, injuries, recent pitch counts, rest and consecutive-use indicators, leverage hierarchy, handedness matchups, and a probabilistic estimate of which pitchers are likely to appear.
