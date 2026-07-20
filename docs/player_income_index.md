# Role-Specific Player-Income Indices

## Terminology

“Income” is a platform-specific composite performance index, not salary, contract value, or real-money earnings. The research interprets it as a compact representation of official game performance.

## Batter game index

For game `g`, define the approximate plate appearances:

```text
PA_approx = AB + BB + HBP
```

The selected event score is:

```text
0.50·1B + 0.95·2B + 1.35·3B + 1.85·HR
+ 0.42·BB + 0.42·HBP + 0.22·SB
− 0.08·SO − 0.32·GIDP
```

It is converted to a 4.2-PA rate and standardized using an early-2024 reference distribution:

```text
rate = event_score / PA_approx × 4.2
income = clip(1000 + 250 × (rate − 0.7384323834) / 0.9411772121, −500, 3000)
```

### Strict-prior batter mean

For a player before target date `d`:

```text
prior_income = (current-season prior sum + 5 × center) / (prior games + 5)
```

The center is the player’s completed previous-season mean when available, otherwise 1,000. All target-date results are excluded, including same-day doubleheader Game 1 from Game 2.

The official nine-player starting lineup is summarized by:

- mean prior income
- history coverage
- average prior-game count
- minimum side coverage

## Starting-pitcher game index

The selected start-only game value is:

```text
1000 × (
  0.216·outs_recorded
  + 0.132·strikeouts
  − 1.565·home_runs_allowed
  − 0.557·(walks + hit_by_pitch)_allowed
)
```

Only prior **starting appearances** enter the pitcher history. Relief appearances are not mixed into the start-only mean.

A `K=10` shrinkage mean combines the current-season prior sum with a previous-season player or league starter center. Reliability and coverage are retained as separate model features.

## Bullpen representation

The final model does not use a player-level bullpen-income block. It uses team-level strict-prior responsibility-run measures, including the recent-20 post-starter team runs feature. Player-level bullpen income did not demonstrate stable incremental value.
