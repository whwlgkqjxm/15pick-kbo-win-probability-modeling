# Role-specific player-index design

This document defines the frozen batter and starting-pitcher indices used in the win-probability study. It covers the game-level scores, strict-prior player estimates, and the exact pregame features supplied to the model.

The two roles use separate formulas because the official statistics and game responsibilities are different. Batter history is built from batting appearances, while starting-pitcher history includes starts only. Relief appearances are never mixed into the starting-pitcher index.

## Shared pregame rule

Every player estimate obeys the same time boundary:

```text
source game date < target game date
```

The target game and every other game on the same date are excluded. This also prevents the first game of a doubleheader from updating a feature for the second game. Cancelled games do not contribute player performance records.

Current-game starting lineups and named starting pitchers may be used because the intended prediction point is after those inputs are known but before first pitch. See [temporal validation and leakage control](temporal_validation_and_leakage.md) for the full information contract.

## Batter index: POWER_OBP__RATE100

### Game-level event score

The batter score uses official batting, on-base, power, and baserunning events:

```text
1B = H − 2B − 3B − HR

raw event score =
  0.50 × 1B
+ 0.95 × 2B
+ 1.35 × 3B
+ 1.85 × HR
+ 0.42 × BB
+ 0.42 × HBP
+ 0.22 × SB
− 0.08 × SO
− 0.32 × GIDP
```

Runs, RBI, and game-winning hits are excluded because they depend more heavily on team context and batting opportunities.

### Opportunity adjustment and fixed scaling

Approximate plate appearances are defined as:

```text
approximate PA = AB + BB + HBP
```

The event total is converted to a 4.2-plate-appearance rate. When approximate PA is zero, the rate is set to zero.

```text
rate score = raw event score / approximate PA × 4.2
```

The rate is then standardized using a frozen early-2024 reference distribution:

```text
batter index =
  1000
  + 250 × ((rate score − 0.738432383380831)
           / 0.9411772120687678)
```

The final game index is clipped to `[-500, 3000]`. These constants are fixed in [`configs/batter_index.json`](../configs/batter_index.json), and the maintained implementation is in [`src/fifteenpick_prediction/indices.py`](../src/fifteenpick_prediction/indices.py).

### Batter prior: S_K5

For each target date, the current-season sum and count include only earlier games. The prior center is the same player's previous-season mean when available; otherwise it is `1000`.

```text
pregame batter value =
  (current-season prior score sum + 5 × center)
  / (current-season prior game count + 5)
```

The `K=5` term treats the prior center as five virtual games. This limits extreme values when a player has only a small number of current-season appearances without discarding the player's observed history.

### Starting-lineup aggregation

Exactly nine official starting batters are used for each team. The model receives four batter features:

| Feature | Definition |
|---|---|
| Starting-lineup performance difference | Home nine-player mean minus away nine-player mean |
| Lineup-history coverage difference | Home minus away share of starters with at least one earlier current-season game |
| Average prior-game-count difference | Home minus away mean of the nine players' earlier current-season game counts |
| Minimum lineup coverage | The lower of the home and away coverage values |

Players without an earlier current-season game still receive the shrunk prior value, but the coverage and count features tell the model how much observed history supports each lineup estimate.

## Starting-pitcher index

### Start-only game score

The starting-pitcher score is:

```text
1000 × (
  0.216 × outs recorded
  + 0.132 × strikeouts
  − 1.565 × home runs allowed
  − 0.557 × (walks + hit by pitch allowed)
)
```

Only appearances officially recorded as starts are eligible. Relief appearances by the same pitcher are excluded from the score history, prior count, reliability calculation, and coverage flag. The fixed coefficients are stored in [`configs/starter_index.json`](../configs/starter_index.json).

### K=10 strict-prior estimate

The current-season history uses only earlier starts:

```text
pregame starter value =
  (prior start-only score sum + 10 × center)
  / (prior start count + 10)
```

The center is selected in this order:

1. the same pitcher's previous-season start-only mean;
2. the previous-season league mean for starting pitchers;
3. the current-season expanding league mean from starts before the target date.

Reliability is reported separately rather than being hidden inside the value:

```text
reliability = prior start count / (prior start count + 10)
```

### Starting-pitcher model features

| Feature | Definition |
|---|---|
| Starting-pitcher performance difference | Home starter value minus away starter value |
| Prior-start-count difference | Home minus away number of earlier current-season starts |
| Reliability difference | Home minus away reliability |
| Both starters covered | `1` when both named starters have an eligible earlier current-season start, otherwise `0` |

The four batter features and four starting-pitcher features are listed with the six conventional pregame variables in the [modeling dataset schema](../data/schema/modeling_dataset_schema.csv).

## Interpretation boundaries

These indices are predictive representations, not estimates of causal player value. Their coefficients were selected for this modeling task and should not be interpreted as universal baseball-value weights.

The design does not use target-game outcomes, same-date results, legacy batter metrics, relief appearances in starter history, or the identities of pitchers who later enter the target game in relief. The separate player-level relief experiment is documented in the [relief-pitcher negative-result record](relief_pitcher_index_negative_result.md).

This repository verifies the frozen formulas, model inputs, saved-model compatibility, and aggregate results. Some row-level historical lineup-prior intermediates are recorded in the source research archive but are not included in this repository; this limitation is stated in the [`V11.1` reproducibility audit](../reports/frozen/V11_1_REPRODUCIBILITY_AUDIT.json).
