# Why Player-Level Bullpen Income Was Not Selected

## Empirical result

The player-level relief-pitcher index did not provide stable incremental prediction value.

| Evaluation | Reference Log loss | + Bullpen-income Log loss | Difference | Interpretation |
|---|---:|---:|---:|---|
| 2025 bullpen-domain comparison | 0.687434978 | 0.687444156 | +0.000009178 | Null/slightly worse |
| 2025 added to V7 starter stack | 0.669482620 | 0.674253000 | +0.004770380 | Worse |
| 2026 post-hoc added to V7 stack | 0.667785123 | 0.668898000 | +0.001112877 | Worse |

For the standalone 2025 comparison, the estimated probability of improvement was 49.95%, which is indistinguishable from chance.

## Why this negative result is plausible

### 1. Pregame identity uncertainty

A starting pitcher and starting lineup are announced before the game. The actual relief sequence is not. Which reliever enters depends on information generated after first pitch.

### 2. Endogenous deployment

Managers choose relievers conditional on the score, inning, base-out state, leverage, opponent handedness, and future schedule. Observed relief performance is therefore entangled with when and why a pitcher was selected.

### 3. Availability is time-varying

Recent pitch count, consecutive-day use, injury status, recovery, and role changes alter who is realistically available. Research on MLB reliever fatigue finds measurable short-term effects from recent pitch workload, reinforcing the need for point-in-time availability data.

### 4. Small-sample volatility

Relievers accumulate fewer innings and batters faced than starters. A few poor appearances can move an average substantially, increasing estimation variance.

### 5. Leakage-versus-dilution trade-off

- Using the relievers who actually appeared would leak postgame deployment information.
- Using every plausible pregame reliever creates a noisy pool containing pitchers who may never enter.

This creates a difficult identification problem: the most precise bullpen composition is only known after the game, but the legal pregame approximation is inherently uncertain.

## Modeling decision

The negative result does **not** imply that bullpens do not matter. It implies that the tested player-level pregame income aggregation was not stable enough to improve probability forecasts.

The maintained model instead uses team-level, strictly prior measures:

- cumulative bullpen/post-starter responsibility runs
- recent-20 post-starter team responsibility runs

These variables sacrifice individual attribution in exchange for a more stable pregame team representation.

## Future research

A stronger player-level bullpen model would require point-in-time information such as:

- official active-roster snapshots
- recent pitch counts and consecutive-day workload
- injury and availability status
- expected starter workload
- leverage-role hierarchy
- handedness and projected matchup sequence
- a probabilistic model for which relievers are likely to appear

The correct future formulation is likely a two-stage model:

1. Estimate each reliever's probability of appearing and expected workload.
2. Aggregate expected relief performance using those probabilities.

## References

- Greenhouse, M., Reiter, J. P., & Zahran, S. (2019). Out of gas: quantifying fatigue in MLB relievers. *Journal of Quantitative Analysis in Sports*. https://doi.org/10.1515/jqas-2018-0007
- Hirotsu, N., & Wright, M. (2005). Modelling a baseball game to optimise pitcher substitution strategies incorporating handedness of players. *IMA Journal of Management Mathematics, 16*(2), 179–194. https://doi.org/10.1093/imaman/dpi009
