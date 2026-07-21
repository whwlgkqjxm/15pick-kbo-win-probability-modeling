# Player-level relief-pitcher index: negative result

## Question

Can a strict-prior player-level relief-pitcher performance index improve pregame win-probability forecasts?

## Tested representation

The selected historical candidate used an official-record run-prevention score, hierarchical prior averaging, and a target-game relief pool built only from prior appearances. The target starting pitcher was excluded, and actual target-game relievers were never used.

## Result

| Evaluation | Reference Log loss | + Relief index | Difference |
|---|---:|---:|---:|
| 2025 standalone relief domain | 0.687434978 | 0.687444156 | +0.000009 |
| 2025 added to V7 starter stack | 0.669482620 | 0.674253000 | +0.004770 |
| 2026 post-hoc addition | 0.667785123 | 0.668898000 | +0.001113 |

Positive differences are worse. The standalone 2025 comparison had a 49.95% improvement probability, effectively a null result.

## Root-cause interpretation

- actual reliever deployment is unknown before first pitch;
- deployment depends on score, inning, leverage, starter exit, handedness, and strategy;
- using actual relievers would leak postgame information;
- averaging a broad prior pool includes pitchers who may not appear;
- availability changes with recent workload, recovery, injury, and roster status;
- relief samples are small and role/leverage dependent.

## Decision

Do not include the tested player-level relief index in the primary model. Retain team-level strict-prior post-starter responsibility-run features. This is a representation failure, not evidence that relief pitching is unimportant.
