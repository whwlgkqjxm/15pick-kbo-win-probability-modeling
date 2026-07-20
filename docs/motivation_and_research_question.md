# Motivation and Research Question

## Product origin

MyPick was built as a KBO fantasy-sports and point-based prediction platform. Baseball performance is recorded through many heterogeneous events: hits of different values, walks, strikeouts, double plays, innings, home runs allowed, and many others. Most fans cannot compare these quantities directly across players and roles.

The platform therefore compressed official performance records into an intuitive player-income score. The score was originally a product interface: one number that made player contribution easier to understand, rank, and compare.

## Research transition

A convenient interface is not necessarily a valid predictive representation. The research asks whether information is preserved when complex player records are compressed into role-specific average-income indices.

The key comparison is not between unrelated models. It holds conventional team-strength information, model family, and training protocol constant, then removes or restores the player-income blocks.

## Primary research question

> Do role-specific, strictly prior composite player-performance indices derived from official KBO game records improve pregame KBO win-probability forecasts beyond models based on conventional team strength and pregame records?

## Hypotheses

- **H1:** Adding all player-income blocks lowers Log loss and Brier score relative to the no-income model.
- **H2:** Batter and starting-pitcher indices contain partially complementary information.
- **H3:** Role-specific histories outperform histories contaminated by different appearance roles.
- **H4:** Recent-window training may adapt better to seasonal drift than uniform full-history training, but must be validated prospectively.
