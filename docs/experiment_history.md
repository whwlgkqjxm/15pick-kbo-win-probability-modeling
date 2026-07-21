# Curated Experiment History

The public history records research questions, evidence, and decisions rather than every intermediate implementation file.

| Phase | Question | Main evidence | Decision |
|---|---|---|---|
| Limited-sample baseline | Can one partial season support stable pregame prediction? | Weak discrimination and compressed probabilities | Expand to multiple official seasons |
| Multi-season foundation | Does additional history stabilize features and evaluation? | 1,864 completed games and complete identity resolution | Adopt multi-season strict-prior dataset |
| Complex-model search | Do larger nonlinear models outperform regularized logistic regression? | Worse temporal probability metrics for several complex families | Retain regularized logistic regression |
| Role-scope audit | Are histories semantically consistent by appearance role? | Starting/substitute and start/relief contamination found | Rebuild role-specific histories |
| Starting-pitcher index | Does a start-only index add value? | Stronger 2025 validation and improved 2026 ablation | Retain start-only `K=10` index |
| Batter index | Does a confirmed-lineup batter representation add value? | Batter-only model improved Log loss, AUC, and accuracy | Retain official-lineup `K=5` index |
| Relief-pitcher index | Can player-level relief quality be identified pregame? | Null or worse Log loss; improvement probability 49.95% | Reject player-level relief feature |
| Training-strategy search | Do recent windows, decay, online, or daily refits improve generalization? | Recent-720 L2 logistic was strongest observed candidate | Freeze as development candidate |
| Final player-index ablation | Do player indices add information beyond conventional variables? | Log loss 0.683942 → 0.666135; AUC 0.575781 → 0.635275 | Research hypothesis supported retrospectively |
| Prospective stage | Does the result survive future unseen games? | Not yet available | Highest-priority next stage |

Supporting aggregate outputs are stored in `reports/`, and the maintained implementation is stored in `src/fifteenpick_prediction/`.
