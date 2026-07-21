# Why the Player-Level Relief-Pitcher Index Was Not Selected

## Empirical result

| Evaluation | Reference Log loss | + Relief-pitcher index | Difference | Interpretation |
|---|---:|---:|---:|---|
| 2025 relief-unit domain model | 0.687435 | 0.687444 | +0.000009 | null / slightly worse |
| 2025 added to starter stack | 0.669483 | 0.674253 | +0.004770 | worse |
| 2026 post-hoc addition | 0.667785 | 0.668898 | +0.001113 | worse |

Lower Log loss is better. The standalone 2025 comparison produced a 49.95% bootstrap probability of improvement, which is indistinguishable from chance.

## Interpretation

The result does not show that relief pitching is unimportant. It shows that the tested **player-level pregame representation** did not align reliably with the information set available before first pitch.

### 1. Deployment is unknown before the game

A starting pitcher is normally announced. Relief assignments are conditional on events that have not yet occurred: the starter's exit, inning, score, leverage, baserunner state, upcoming handedness, and managerial priorities.

### 2. Actual-reliever features would leak outcome-dependent information

Using the pitchers who eventually appeared would reveal decisions made after observing the target game's state. Those identities are post-treatment information and cannot be used in a valid pregame model.

### 3. Pregame pool aggregation dilutes the signal

Averaging every available reliever avoids direct leakage but includes many pitchers who may not enter. The average can obscure the few high-leverage arms most relevant to a close game.

### 4. Availability is time-varying

Recent pitch count, consecutive-day usage, rest, recovery, injury, roster moves, and role changes affect whether a reliever is realistically available. Burris and Coleman (2018) found evidence that recent workload can produce short-term velocity effects, reinforcing the need for current workload information.

### 5. Relief samples are noisy and selected

Relievers accumulate fewer innings than starters, and their appearances are selected by game state and role. Raw averages therefore combine small-sample variance with leverage and managerial selection effects.

### 6. Matchups and managerial policy matter

Pitcher substitution decisions can depend on handedness and strategic game state. Hirotsu and Wright (2005) explicitly model substitution strategy with handedness, illustrating why a static average of the bullpen is an incomplete pregame representation.

## Modeling decision

The final model excludes player-level relief-pitcher indices and retains team-level strict-prior run-prevention measures after the starter. This is a conservative proxy for the relief unit as a whole.

## Future research

A stronger relief model would require a historically timestamped pregame availability layer, such as:

- active roster and injury status
- recent pitch counts and days of rest
- consecutive-day usage
- expected leverage hierarchy
- handedness matchups against the confirmed lineup
- manager-specific deployment tendencies
- probabilistic reliever-appearance weights

Until those inputs are available without leakage, the negative result should be treated as a representation failure, not as evidence that bullpens do not affect game outcomes.

## References

- Burris, K., & Coleman, J. (2018). *Out of Gas: Quantifying Fatigue in MLB Relievers*. Journal of Quantitative Analysis in Sports, 14(2), 57–64. https://doi.org/10.1515/jqas-2018-0007
- Hirotsu, N., & Wright, M. (2005). *Modelling a Baseball Game to Optimise Pitcher Substitution Strategies Incorporating Handedness of Players*. IMA Journal of Management Mathematics, 16(2), 179–194. https://doi.org/10.1093/imaman/dpi009
