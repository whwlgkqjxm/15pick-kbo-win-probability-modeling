# Data Card

## Purpose

The dataset supports retrospective research on pregame KBO win-probability forecasting and the incremental value of role-specific player-income indices.

## Source

Official KBO schedule, GameCenter, box-score, and player-profile pages.

## Unit of analysis

- Player-event and player-game occurrence tables for feature construction
- One row per completed game for probability modeling

## Time interval

2024-03-23 through 2026-07-09, with season-specific cutoffs documented in the research protocol.

## Target

Binary home-win outcome for decision games. Ties remain in source data but are excluded from binary model fitting and evaluation.

## Sensitive information

No private user account, betting, asset, or transaction data is used in this research dataset.

## Known limitations

Historical lineup confirmation timestamps are not available for every game; official final game pages are used for retrospective lineup reconstruction. Full raw data is not redistributed in the public repository.
