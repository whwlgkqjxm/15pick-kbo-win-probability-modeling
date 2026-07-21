# External Baseball Benchmarks and Success Criteria

## Why an external benchmark is needed

A model can improve over an internal baseline and still be weak in practical terms. This project therefore reports two separate standards:

1. **Internal causal comparison:** Does the player-income representation add information when everything else is held constant?
2. **External forecasting context:** Is the resulting discrimination in the range reported by serious pregame baseball studies?

## MLB literature context

Soto Valero (2016) used ten years of past-only accumulated sabermetric data and reported that SVM classification achieved nearly 60% mean accuracy across MLB teams. Li, Huang, and Li (2022) summarized prior next-game MLB prediction accuracy as commonly falling between 55% and 62%; their best feature-selected SVM result reached 65.75% accuracy and 0.6501 AUC.

These numbers are not directly interchangeable with the 15Pick result. Important differences include:

- MLB versus KBO
- team-specific versus league-wide modeling units
- random/stratified cross-validation versus chronological validation
- feature availability and timing
- class balance and season composition
- accuracy/AUC reporting versus calibrated probability scoring

The literature is therefore used as a **contextual target range**, not as proof that one model is superior to another.

## Benchmark table

| Reference level | Accuracy | ROC AUC | Log loss | Brier |
|---|---:|---:|---:|---:|
| Neutral 0.5 probability forecast | 50% | 0.500 | 0.6931 | 0.2500 |
| Common MLB literature range | 55–62% | varies | usually not reported | usually not reported |
| Strong published MLB example | 65.75% | 0.6501 | not reported | not reported |
| 15Pick retrospective development model | 59.62% | 0.6353 | 0.6661 | 0.2365 |

## Preregistered success ladder for future evaluation

### Level 1 — representation value

The full player-income model must improve both Log loss and Brier score against the identical no-income model. The preferred evidentiary standard is a paired date-cluster 95% interval below zero for the difference in Log loss.

### Level 2 — competitive baseball forecasting

On frozen prospective games, the model should maintain approximately:

- Accuracy around or above 60%
- AUC at or above 0.63
- Better Log loss and Brier than the no-income comparator
- Stable calibration across probability bins

### Level 3 — aspirational strong performance

Approach the upper published MLB context:

- AUC near 0.65
- Accuracy in the 62–65% range
- No degradation in Log loss, Brier, or calibration

This is an aspiration, not a universal cutoff. A model with lower accuracy can still be scientifically better if its probabilities are better calibrated and its proper scoring rules improve.

## Why Log loss and Brier are primary

Accuracy discards probability magnitude. A 50.1% and a 90% forecast receive the same classification if both predict the same winner. Log loss penalizes confident mistakes, while Brier score measures squared probability error. Because 15Pick publishes win probabilities rather than only winner labels, proper scoring rules are the primary model-selection criteria.

## Betting boundary

A predictive edge does not automatically imply profitable betting. Profitability additionally depends on market odds, bookmaker margin, line movement, bet timing, limits, and transaction costs. Market evaluation should be a separate benchmark after the probability model is frozen.

## References

- Soto Valero, C. (2016). Predicting Win-Loss outcomes in MLB regular season games—A comparative study using data mining methods. *International Journal of Computer Science in Sport, 15*(2), 91–112. https://doi.org/10.1515/ijcss-2016-0007
- Li, S.-F., Huang, M.-L., & Li, Y.-Z. (2022). Exploring and Selecting Features to Predict the Next Outcomes of MLB Games. *Entropy, 24*(2), 288. https://doi.org/10.3390/e24020288
