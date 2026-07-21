# Prospective validation protocol

## Frozen models

- Scientific CV candidate: `L2_C0.03_ALL_EQUAL`
- Best observed development candidate: `L2_C0.1_RECENT_720`

## Pregame ledger fields

- game ID
- scheduled first pitch
- prediction timestamp
- source cutoff timestamp
- official lineup and starter snapshot hashes
- feature schema and feature-row hash
- model ID and model binary hash
- probability from each frozen model
- no outcome field in the initial record

## Postgame settlement

Outcomes are stored separately and appended after completion. The initial prediction record is never overwritten. Cancelled games are void. Tie handling is declared before evaluation.

## Primary and secondary metrics

Primary: Log loss.

Secondary: Brier score, calibration intercept/slope, reliability bins, AUC, accuracy, date-cluster bootstrap, and drift diagnostics.

## Change control

No feature, formula, regularization value, or training window is altered within the frozen model. New ideas begin as separately versioned challengers. Prospective outcomes are not used for silent daily overwrites.
