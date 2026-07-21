# External Baseball Benchmarks and Success Criteria

## Two different evaluation questions

The project separates:

1. **Controlled incremental-value evidence:** do the player indices improve prediction when the dataset, model family, training strategy, and conventional pregame features are held constant?
2. **External forecasting context:** is the resulting discrimination broadly consistent with published baseball prediction work?

The first is the primary research test. The second provides practical context but is not a direct leaderboard.

## Published MLB context

Li, Huang, and Li (2022) state that previous next-game MLB studies commonly reported accuracy between approximately 55% and 62%. Their study organized separate datasets for the 30 MLB teams, used an 80/20 split and five-fold cross-validation, and reported a best feature-selected SVM result of 65.75% accuracy and 0.6501 AUC.

The same article reports earlier results including 58.92% for Soto Valero (2016), 59.60% for Jia et al., 55.52% for Elfrink, and 61.77% for Cui.

These protocols differ from 15Pick in league, modeling unit, time split, feature construction, and probability evaluation. Therefore, their values are contextual reference points only.

## Benchmark table

| Reference level | Accuracy | ROC AUC | Log loss | Brier |
|---|---:|---:|---:|---:|
| Neutral 0.5 probability forecast | 50.00% | 0.5000 | 0.6931 | 0.2500 |
| Broad published MLB context | approximately 55–62% | varies | usually not reported | usually not reported |
| Strong published MLB example | 65.75% | 0.6501 | not reported | not reported |
| 15Pick retrospective development model | 59.62% | 0.6353 | 0.6661 | 0.2365 |

## Prospective success ladder

### Level 1 — incremental representation value

The batter-plus-starter model must improve both Log loss and Brier score against the identical conventional-feature baseline. The preferred evidence is a paired date-cluster 95% interval below zero for the Log-loss difference.

### Level 2 — competitive probability forecasting

On a frozen future ledger, the candidate should maintain:

- accuracy near 60%
- ROC AUC at or above 0.63
- lower Log loss and Brier score than the frozen comparator
- stable calibration intercept, slope, and reliability bins

### Level 3 — aspirational strong performance

Approach ROC AUC 0.65 and low-to-mid-60% accuracy without degrading proper scoring rules or calibration.

This is an aspiration, not a universal cutoff. A lower-accuracy model may be better if its probabilities are better calibrated and its Log loss and Brier score are lower.

## Why proper scoring rules are primary

Accuracy ignores probability magnitude. A 50.1% forecast and a 90% forecast receive the same correct/incorrect label even though their confidence differs substantially. Log loss penalizes confident errors, and Brier score measures squared probability error. Because the product outputs win probabilities, those metrics govern model selection.

## Betting boundary

Forecast quality does not imply betting profitability. Profit additionally depends on market odds, bookmaker margin, timing, limits, line movement, and transaction costs. Market evaluation should remain separate from model development.

## References

- Li, S.-F., Huang, M.-L., & Li, Y.-Z. (2022). *Exploring and Selecting Features to Predict the Next Outcomes of MLB Games*. Entropy, 24(2), 288. https://doi.org/10.3390/e24020288
- Soto Valero, C. (2016). *Predicting Win-Loss Outcomes in MLB Regular Season Games—A Comparative Study Using Data Mining Methods*. International Journal of Computer Science in Sport, 15(2), 91–112. https://doi.org/10.1515/ijcss-2016-0007
