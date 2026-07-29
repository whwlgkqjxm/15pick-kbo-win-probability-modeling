# Scientific status and allowed claims

## Current status

This project currently provides **retrospective development evidence**, not prospective confirmation. Two L2-regularized logistic regression specifications are frozen for future pregame evaluation, and this repository contains no completed prospective checkpoint.

The research foundation covers 1,864 completed KBO games from March 23, 2024, through July 9, 2026. After excluding 40 ties from the binary target, the modeling table contains 1,824 decision games. The primary role-ablation comparison uses the 416 decision games from 2026. During historical feature construction, the source-pipeline audit recorded zero uses of target-game outcomes, zero uses of other same-date results, and zero temporal-order violations. Current-game lineups and starting pitchers were allowed as pregame inputs; target-game outcomes and events were not. However, 2026 outcomes were inspected during model and training-strategy comparison.

## Results supported by the current evidence

The two frozen specifications produced the following 2026 development Log losses. Lower values indicate better probability estimates.

| Feature set | CV-selected reference | Best observed development model |
|---|---:|---:|
| Conventional pregame variables | 0.683516 | 0.683942 |
| Conventional + batter block | 0.679916 | 0.678611 |
| Conventional + starting-pitcher block | 0.672733 | 0.673157 |
| Conventional + both player blocks | **0.667390** | **0.666135** |

Under both frozen specifications, the batter and starting-pitcher blocks each reduced observed Log loss relative to the tested conventional pregame baseline, the starting-pitcher block produced the larger standalone reduction, and the combined model produced the lowest Log loss.

For the best observed development model, the combined-model difference from the conventional baseline was `-0.017807`. Its 95% paired date-cluster bootstrap interval was `[-0.033154, -0.002114]`, with lower Log loss in `98.69%` of 20,000 bootstrap replicates. For the CV-selected reference, the difference was `-0.016127`, with an interval of `[-0.032066, 0.000425]`; that interval includes zero.

Additional findings that are supported within their evaluated scope are:

- **Model-family comparison.** L2 logistic regression with `C=0.03` had the lowest pooled Log loss and the best stability-adjusted score among 42 configurations from nine model families evaluated through five expanding 2024–2025 temporal folds and 984 out-of-fold predictions.
- **Frozen candidates.** `L2_C0.03_ALL_EQUAL` was selected without consulting 2026 outcomes and recorded a 2026 Log loss of `0.667390`. `L2_C0.1_RECENT_720` was selected after 2026 training-strategy comparison and recorded the lowest observed 2026 Log loss, `0.666135`. Their 10,000-replicate paired date-cluster interval, `[-0.004790, 0.002336]`, does not establish clear superiority between them.
- **Identity and role audit.** Numeric identity was resolved for all `65,554` player-game occurrences, with zero name-only forced merges. Among starting-batter rows with prior history, `25,870` of `33,121` (`78.11%`) included prior substitute appearances; among starting-pitcher rows with prior history, `726` of `3,496` (`20.77%`) included prior relief appearances. These findings invalidated the earlier predictive-ceiling interpretation and led to role-specific reconstruction.
- **Relief-pitcher result.** Under the separate V8 protocol, the tested leakage-safe player-level relief-pitcher representation did not improve probability quality: `0.687435` to `0.687444` in the 2025 standalone comparison, `0.669483` to `0.674253` in the 2025 integrated comparison, and `0.667785` to `0.668898` in the 2026 post-hoc comparison. The representation was therefore not retained. This does not imply that relief pitching itself is unimportant.

## Claims requiring qualification

- The reconstructed 2026 features passed the recorded target-game and same-date leakage checks, but 2026 was used for method comparison and is not an untouched final test.
- The final V11.1 2025 result is validation evidence rather than an untouched test because the prior-averaging design was reviewed after that period was inspected.
- Historical lineups and starting pitchers were reconstructed from official completed-game records; they are not independently timestamped pregame snapshots.
- The recent-720 model is the best observed development model, not a prospectively validated champion.
- The `C=0.03` reference was selected without consulting 2026 outcomes, but its 2026 performance is still evidence from an already observed development period.
- Bootstrap intervals quantify uncertainty under the stated paired date-cluster resampling design. They do not account for model-selection uncertainty, repeated-evaluation uncertainty, serial dependence across adjacent dates, or future-season distribution shift.
- The `98.69%` bootstrap replicate proportion is not a Bayesian posterior probability that the combined model is truly superior.

## Claims not supported by the current evidence

- “The model has been proven to generalize to future KBO seasons.”
- “2025 or 2026 was a completely untouched final test.”
- “The recent-720 model is the definitive production champion.”
- “The player indices causally increase a team’s probability of winning.”
- “Relief pitching is unimportant.”
- “The composite score measures economic player value.”
- “Complex models are universally worse than logistic regression.”
- “No data leakage exists” without distinguishing feature leakage, historical source timing, and evaluation-period reuse.

## Required next evidence

Any claim of prospective performance requires predictions written before first pitch to an immutable ledger, including model and feature hashes, source cutoff timestamps, lineup and starting-pitcher snapshot hashes, and separate postgame outcome settlement. Broader claims about generalization across seasons require repeated, prespecified prospective checkpoints rather than a single future evaluation.
