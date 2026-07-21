# Motivation and Research Question

## Product origin

15Pick was built as a KBO fantasy-sports and point-based prediction platform. Official baseball performance is distributed across many heterogeneous events, and the interpretation of those events differs by role. A single game can contain information about hit type, plate discipline, baserunning, strikeouts, innings recorded, home runs allowed, and many other outcomes.

To make those records easier to compare, the platform summarized them as a single **player performance score**. The product objective was interpretability, not statistical proof: users could understand and compare player form without reading every component statistic separately.

## From interface design to empirical research

Compression creates a trade-off. A compact score may preserve meaningful signal, but it may also discard information, amplify noise, or apply weights that are useful for presentation but not for forecasting.

The research therefore treats the score as a candidate representation rather than assuming it is valid. Conventional team and pregame variables, model family, and training protocol are held constant while batter and starting-pitcher performance-index blocks are removed or restored.

## Primary research question

> Do role-specific, strictly prior composite player performance indices derived from official KBO game records improve pregame KBO win-probability forecasts beyond models based on conventional team strength and pregame records?

## Hypotheses

- **H1:** Adding batter and starting-pitcher indices lowers Log loss and Brier score relative to the identical no-player-index baseline.
- **H2:** Batter and starting-pitcher indices provide partially complementary information.
- **H3:** Role-specific histories outperform histories contaminated by different appearance roles.
- **H4:** A player-level relief-pitcher index will add value only when the likely reliever pool, availability, and workload can be represented without postgame information.
- **H5:** Recent-window training may adapt to changing league conditions better than uniform full-history training, but must be confirmed prospectively.

## Scope of the claim

The study asks whether the engineered representation adds predictive information. It does not claim that the index is a complete measure of player quality, a causal estimate of contribution, or a replacement for established sabermetric metrics.
