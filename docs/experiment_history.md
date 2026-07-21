# Experiment History

| Stage | Question | Result | Decision |
|---|---|---|---|
| Limited-sample phase | Can partial-2026 data support a strong model? | Probabilities were weak and compressed around 0.5. | Expand to multiple seasons. |
| Multi-season foundation | Can official KBO records be resolved and replayed consistently? | 1,864 games and 65,554 player occurrences passed identity and temporal audits. | Use as canonical foundation. |
| Stabilized averages | Do strict-prior and cross-season means help? | Regularized probability models improved over early specifications. | Retain shrinkage histories. |
| Broad complex-model search | Do many features and nonlinear models outperform simple logistic regression? | High-dimensional ensembles underperformed the regularized logistic benchmark. | Reject complexity without temporal gains. |
| Role audit | Were histories role-pure? | Substitute/starter and starter/reliever histories had been mixed. | Rebuild role-specific indices. |
| Starter redesign | Does start-only pitcher performance add value? | Start-only K10 signal produced the strongest role-specific improvement. | Retain starter block. |
| Batter and bullpen audit | Do redesigned batter and bullpen scores add value? | Early batter candidate was weak; player-level bullpen signal was null or negative; deployment uncertainty and small-sample volatility limited pregame identification. | Rebuild batter index; omit player bullpen income. |
| Post-starter team runs | Does recent team relief responsibility improve the model? | Recent-20 measure was the best observed team bullpen representation. | Retain as development feature. |
| Additional official features | Do workload, hand matchup, and lineup interaction features improve probability loss? | Accuracy sometimes rose, but Log loss did not improve reliably. | Reject from probability-primary model. |
| Batter rebuild | Which official-event batter representation is strongest? | Selected POWER_OBP RATE100 / K5 after 215 score candidates and multiple aggregation methods. | Retain new batter block. |
| Learning strategy search | Which algorithms and temporal training rules generalize best? | Regularized logistic regression was most stable; recent 720 games was the best observed development window. | Freeze as development champion. |
| Full income ablation | Does all player income add information beyond conventional features? | Log loss improved from 0.683942 to 0.666135. | Research hypothesis supported retrospectively. |


## External benchmark stage

The final reporting layer added MLB literature context and preregistered prospective success criteria. External numbers are not treated as directly comparable leaderboard scores; the primary claim remains the within-protocol ablation.
