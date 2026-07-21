# Role-Aware Player Performance Indices

## Purpose

The indices compress multiple official game events into one role-specific scale. They are designed for interpretable comparison and for testing incremental predictive value in a pregame win-probability model.

They are not salary, contract value, market value, or a causal estimate of wins produced.

## Batter game index

Approximate plate appearances are defined as:

```text
PA_approx = AB + BB + HBP
```

The selected event score is:

```text
0.50·1B + 0.95·2B + 1.35·3B + 1.85·HR
+ 0.42·BB + 0.42·HBP + 0.22·SB
− 0.08·SO − 0.32·GIDP
```

The score is converted to a 4.2-plate-appearance rate and standardized using a frozen early-2024 reference distribution:

```text
rate = event_score / PA_approx × 4.2
batter_index = clip(
    1000 + 250 × (rate − 0.7384323834) / 0.9411772121,
    −500,
    3000
)
```

### Strict-prior batter history

For a player before target date `d`:

```text
prior_index = (current-season prior sum + 5 × center) / (prior games + 5)
```

The center is the completed previous-season player mean when available and 1,000 otherwise. All games on the target date are excluded, including doubleheader Game 1 from Game 2.

The confirmed nine-player starting lineup is represented by:

- mean prior batter index
- history coverage difference
- average prior-game count difference
- minimum lineup coverage

## Starting-pitcher game index

The selected start-only value is:

```text
1000 × (
  0.216·outs_recorded
  + 0.132·strikeouts
  − 1.565·home_runs_allowed
  − 0.557·(walks + hit_by_pitch)_allowed
)
```

Only prior **starting appearances** enter the history. Relief appearances are excluded because role mixing changes workload, expected innings, and performance context.

A `K=10` strict-prior shrinkage mean stabilizes early-season and low-sample estimates. Count, reliability, and two-starter coverage are retained as separate model features.

## Relief-pitcher representation

A player-level relief-pitcher index was tested but not selected. The actual reliever set is unknown before the game and depends on game state, workload, handedness, and managerial decisions. The final model uses team-level strict-prior post-starter run-prevention measures instead.

See [`relief_pitcher_index_negative_result.md`](relief_pitcher_index_negative_result.md).
