# Motivation and Research Question

## Product origin

15Pick was built as a KBO fantasy-sports and point-based prediction platform. Baseball performance is distributed across heterogeneous events—hits of different values, walks, strikeouts, double plays, innings, home runs allowed, and many others. These records are difficult for many fans to compare directly, especially across batting and pitching roles.

The platform therefore compressed official performance records into an intuitive player-income score. The original goal was explanatory and experiential: provide one number that made player contribution easier to understand, rank, and compare.

## Research transition

A useful interface is not necessarily a valid statistical representation. Compressing many records into one number can preserve meaningful signal, but it can also discard information or embed unstable weighting choices.

The research therefore evaluates the representation rather than assuming it is valuable. The key comparison holds conventional pregame information, model family, and training protocol constant, then removes or restores the player-income blocks.

## Primary research question

> Do role-specific, strictly prior composite player-performance indices derived from official KBO game records improve pregame KBO win-probability forecasts beyond models based on conventional team strength and pregame records?

## Hypotheses

- **H1:** Adding batter and starting-pitcher income blocks lowers Log loss and Brier score relative to the no-income model.
- **H2:** Batter and starting-pitcher indices contain partially complementary information.
- **H3:** Role-specific histories outperform histories contaminated by different appearance roles.
- **H4:** Player-level bullpen income will add value only if the likely reliever pool and availability can be represented without postgame leakage.
- **H5:** Recent-window training may adapt to seasonal drift better than uniform full-history training, but must be validated prospectively.

## External performance target

The project uses MLB literature as contextual evidence that pregame baseball prediction commonly operates around 55–62% accuracy, with stronger published results approaching approximately 0.65 AUC and mid-60% accuracy. The final 15Pick claim requires a frozen prospective evaluation, not merely similarity to retrospective literature values.
