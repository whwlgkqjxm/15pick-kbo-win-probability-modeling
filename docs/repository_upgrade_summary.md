# Repository upgrade summary — v2.0

## Why the upgrade was necessary

The first portfolio repository had a strong high-level README but exposed only a small part of the work performed in the verified research archive. Its simplified reproduction script diverged from the authoritative V12 execution in logistic solver choice, deterministic recent-window ordering, and date-cluster bootstrap behavior.

A reviewer could understand the story but could not independently regenerate the main results or inspect the full failure-driven research process.

## Major upgrades

### Exact core reproduction

- included the 1,824-row frozen V12 modeling table;
- restored authoritative feature order and default logistic solver;
- made recent-window selection deterministic with `game_date, game_id` ordering;
- restored the original date-cluster bootstrap that resamples dates and concatenates their games;
- regenerates metrics, game probabilities, calibration, coefficients, and bootstrap intervals.

### Artifact verification

- 123 SHA256-manifested research artifacts;
- exact season row and schema checks;
- same-date exclusion flag checks;
- published metric and bootstrap comparison to `1e-12`;
- saved-model replay errors of `1.665e-16` and `2.776e-16`.

### Research history

- full Phase 1–V12 journey;
- defect and root-cause ledger;
- 12 experiment cards;
- exact reports and decision JSON files for role audit, V5–V12, and negative results;
- complete v15 master handover retained under research records;
- original V11.1 and V12 execution scripts retained as authoritative historical source.

### Software quality

- maintained package modules for indices, temporal ordering, modeling, bootstrap, calibration, schema, metrics, and validation;
- 21 tests with 91% package coverage;
- lint and CI workflow;
- portable Makefile commands;
- expanded frozen-model registry and release policy.

## Remaining scientific work

The repository is now substantially stronger as a graduate-school and data-science employment portfolio. It still does not convert the retrospective development evidence into a final generalization claim. The remaining highest-priority scientific task is a timestamped immutable prospective ledger comparing the two frozen models on future games.
