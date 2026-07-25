# Role-specific player-index design

## Design principle

The goal is to compress official role-specific game events into a reproducible signal that can be averaged strictly before a target game and tested for incremental prediction value.

## Batter index: POWER_OBP__RATE100

Raw event score:

```text
0.50 × 1B + 0.95 × 2B + 1.35 × 3B + 1.85 × HR
+ 0.42 × BB + 0.42 × HBP + 0.22 × SB
− 0.08 × SO − 0.32 × GIDP
```

Approximate plate appearances are `AB + BB + HBP`. The event score is divided by approximate PA and multiplied by 4.2. The rate is standardized against an early-2024 design reference to a 1,000 center and 250 scale, then clipped to `[-500, 3000]`.

Runs, RBI, and game-winning hits are deliberately excluded from the selected formula to emphasize direct batting, on-base, and power events rather than team-context outcomes.

## Batter prior: S_K5

For a target date, only earlier games in the same season contribute to the current-season sum and count. The center is the player's previous-season mean when available, otherwise 1,000.

```text
(current-season prior score sum + 5 × center) / (current-season prior games + 5)
```

## Lineup aggregation

Exactly nine official starting batters per side are used. Four features enter the model:

- mean difference;
- history-coverage difference;
- prior-game-count mean difference;
- minimum coverage across the two teams.

## Starting-pitcher index

```text
1000 × (
  0.216 × outs
  + 0.132 × strikeouts
  − 1.565 × home runs allowed
  − 0.557 × (walks + hit by pitch allowed)
)
```

Only starts are included. The K=10 prior uses previous-season player or league centers and exposes value, count, reliability, and both-starters-covered features.

## Relief pitching

The selected player-level relief index was not retained. The final model uses team-level strict-prior post-starter responsibility runs, including a recent-20 feature. This is not identical to physical runs after the actual starter exits; play-by-play data is required for that quantity.
