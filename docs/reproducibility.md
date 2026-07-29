# Reproducibility and artifact provenance

## What this page establishes

This repository provides a maintained, portable path for reproducing the core V12
player-index comparisons from the released derived modeling table. It also preserves the
frozen reports, fitted model binaries, historical V11.1/V12 execution scripts, environment
records, and integrity checks needed to trace the reported results back to their released
artifacts.

Reproduction here has a deliberately limited meaning. It confirms that the released code can
regenerate the reported development-period calculations from the included inputs. It does not
reconstruct the private raw KBO archive, make the already observed 2026 period an untouched
test, or replace the need for future pregame prospective validation.

## Quick start

From the repository root on Linux (the CI platform), or on macOS with Python 3.11+ and compatible wheels:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements-reproduce-lock.txt
pip install -e . --no-deps
make reproduce
make verify
```

`make reproduce` writes the portable outputs under
[`reports/reproduced/`](../reports/reproduced/). `make verify` is fail-closed: it exits with an
error when a required audit, output, metric, model replay, or immutable artifact does not match
the recorded research state. For the broader code-quality suite, run `make check`, which adds
Ruff and the repository tests before verification. Install the development extras with
`pip install -e ".[dev]"` before running that broader suite. A successful core run regenerates seven
files, verifies three linked audits, and validates every entry in the current research manifest.

## What is and is not reproduced

The portable analysis starts from
[`data/derived/V12_MODELING_DATASET.csv`](../data/derived/V12_MODELING_DATASET.csv), a frozen
1,824-game decision table with 71 columns. The released table contains 710 games from 2024,
698 from 2025, and 416 from the observed 2026 development period. It includes the target,
pregame team features, the clean starting-pitcher block, and the selected batter-lineup block.

From that table, the maintained pipeline reproduces:

- four predefined feature-set models under each of two frozen specifications, for eight fitted
  model runs in total;
- a constant 0.5 probability reference for each specification;
- game-level 2026 probabilities;
- Log loss, Brier score, ROC AUC, and accuracy;
- paired date-cluster bootstrap comparisons;
- calibration deciles and calibration intercept/slope;
- standardized logistic-regression coefficients, including any imputer-generated missingness indicators; and
- the released dataset-validation audit.

The two specifications are the 2024–2025 temporal-CV-selected L2 model and the best observed
2026 development training strategy. Their scientific roles and selection history are described
in [model selection, role comparison, and calibration](model_selection_ablation_and_calibration.md).

The released repository does **not** reproduce the following from first principles:

- the complete raw KBO HTTP-response and BoxScore archive;
- the private canonical-data construction process that preceded the released modeling table;
- row-level historical lineup-prior intermediates that are not redistributed;
- operational 15Pick service databases, user, betting, pricing, or settlement data; or
- an independent prospective test on games that had not yet occurred when the methods were
  selected.

These boundaries are intentional. See the [data-release policy](data_release_policy.md) and
[data lineage and quality](data_lineage_and_quality.md) for the release scope.

## Portable reproduction outputs

Running `make reproduce` regenerates exactly seven files:

| Output | Purpose |
|---|---|
| [`player_index_ablation.csv`](../reports/reproduced/player_index_ablation.csv) | Metrics for the four feature sets, plus the constant reference, under both frozen specifications |
| [`player_index_ablation_predictions.csv`](../reports/reproduced/player_index_ablation_predictions.csv) | Game-level probabilities for the 416 observed 2026 decision games |
| [`player_index_ablation_bootstrap.csv`](../reports/reproduced/player_index_ablation_bootstrap.csv) | Paired date-cluster comparison of the combined player-index model against the conventional baseline |
| [`calibration_deciles.csv`](../reports/reproduced/calibration_deciles.csv) | Decile-level predicted and observed probabilities for the combined model |
| [`calibration_intercept_slope.csv`](../reports/reproduced/calibration_intercept_slope.csv) | Calibration intercept and slope for each frozen specification |
| [`standardized_coefficients.csv`](../reports/reproduced/standardized_coefficients.csv) | Coefficients for the transformed 14-input logistic pipelines, including imputer-generated missingness indicators |
| [`dataset_validation.json`](../reports/reproduced/dataset_validation.json) | Dataset, feature, temporal, lineup, and starter validation results |

The maintained entry point is
[`scripts/reproduce_core_results.py`](../scripts/reproduce_core_results.py). It uses deterministic
sorting, a fixed random seed of `20260720`, the documented temporal cutoff, and 20,000 bootstrap
replicates in the verification path.

## Fail-closed verification

[`scripts/verify_research_artifacts.py`](../scripts/verify_research_artifacts.py) performs three
linked groups of checks.

### Dataset and temporal controls

The released table must contain exactly 1,824 unique decision-game IDs and the expected season
counts. The target must be binary, ties must be absent, all 14 model features must be present,
and no feature may contain an infinite value. Every home and away lineup must contain nine
starters, named starting-pitcher IDs must be present, and the committed audit must record that
same-date team updates and same-date player results were excluded. Ordering is deterministic by
`game_date, game_id`. Because the row-level historical source tables are not redistributed, the
repository verifier confirms the frozen exclusion flags and linked-audit consistency; it does not
independently reconstruct every contributing source date from the private raw event archive.

### Regenerated results

Verification reruns the entire portable reproduction in a temporary directory rather than
trusting the committed files. It requires the exact seven-file output set, the same CSV column
order and shape, the same row order and text identifiers, and an identical JSON validation
payload. Numeric CSV values are compared with zero relative tolerance and an absolute tolerance
of `1e-12`.

The verifier also checks selected published metrics and both paired-bootstrap summaries directly.
This guards against a pipeline that completes successfully but silently changes a solver,
training window, temporal order, model definition, or result calculation.

### Linked audits and immutable artifacts

Three committed audit payloads are recomputed from the released supporting evidence and frozen
metadata available in this repository and must match:

- [`reports/reproduced/dataset_validation.json`](../reports/reproduced/dataset_validation.json);
- [`reports/frozen/V12_REPRODUCIBILITY_AND_LEAKAGE_AUDIT.json`](../reports/frozen/V12_REPRODUCIBILITY_AND_LEAKAGE_AUDIT.json); and
- [`reports/frozen/V11_1_REPRODUCIBILITY_AUDIT.json`](../reports/frozen/V11_1_REPRODUCIBILITY_AUDIT.json).

The V11.1 repository audit verifies released summaries, frozen metadata, formula consistency, and model
loading. Its row-level lineup-prior construction remains recorded provenance rather than a result
recomputed from released row-level intermediates, because those private intermediates are not
redistributed.

The verifier then checks every entry in
[`artifacts/RESEARCH_MANIFEST_SHA256.csv`](../artifacts/RESEARCH_MANIFEST_SHA256.csv). The manifest
records relative path, byte size, and SHA256 for the included configurations, maintained source
and scripts, execution-contract files, tests and CI workflow, derived data and schemas, frozen
models and reports, historical V11.1/V12 source, and research records. Missing, extra, duplicate, non-portable, size-mismatched, or hash-mismatched
entries cause failure.

Files under `reports/reproduced/` are intentionally excluded from byte-level hashing. Supported
platforms can differ in the final floating-point digits while retaining the same scientific
calculation. Those seven files therefore use strict structural comparison and the `1e-12`
numeric threshold instead of requiring byte-identical CSV serialization.

## Saved-model replay

The repository does not rely only on refitting new models. It also loads the two released V12
model binaries and replays their probabilities on the 416-row 2026 table:

- [`V12_CV_SELECTED_MODEL_REFIT_2024_2025.joblib`](../models/frozen/V12_CV_SELECTED_MODEL_REFIT_2024_2025.joblib);
- [`V12_2026_BEST_OBSERVED_RECENT720_MODEL.joblib`](../models/frozen/V12_2026_BEST_OBSERVED_RECENT720_MODEL.joblib); and
- the corresponding frozen columns in
  [`V12_2026_ALL_PREDICTIONS.csv`](../reports/frozen/V12_2026_ALL_PREDICTIONS.csv).

The recorded maximum absolute replay errors are on the order of `1e-16`, below the required
`1e-12` threshold. The executable check is in
[`tests/test_saved_model_replay.py`](../tests/test_saved_model_replay.py), and the released audit
is [`V12_MODEL_BINARY_REPRODUCTION_AUDIT.json`](../reports/frozen/V12_MODEL_BINARY_REPRODUCTION_AUDIT.json).

This replay check was added after an earlier maintained path drifted from the frozen execution by
forcing a different solver and using date-only ordering for the recent training window. The
solver override was removed, deterministic `game_date, game_id` ordering was restored, and exact
metric and replay tests now prevent the same class of silent divergence. The incident and its
resolution are documented as F15 in the
[failure and root-cause ledger](failure_root_cause_ledger.md#f15--maintained-repository-code-initially-diverged-from-the-frozen-execution).

## Artifact and provenance map

The released evidence can be read as the following chain:

```text
official historical records
    -> private raw and canonical research archive
    -> released 1,824-game derived modeling table
    -> maintained portable reproduction code
    -> reports/reproduced portable outputs
    -> frozen reports, saved models, and linked audits
    -> SHA256 manifest and fail-closed verification
```

The released table is therefore a derived input, not a substitute for the private raw
archive. The frozen reports and model binaries preserve the reviewed research state, while the
portable code demonstrates that the central V12 role-ablation, calibration, and coefficient
results can be regenerated from that released input.

## Historical execution evidence and environment

The [authoritative historical-source guide](../research/authoritative/README.md) catalogs the exact
V11.1 and V12 execution scripts represented in the verified archive. They document the candidate search,
model-family comparison, adaptive-training evaluation, calibration, packaging, and artifact
generation for those stages. They retain historical private-workspace paths and optional heavy
ML dependencies, so they are evidence and traceability material rather than the recommended
portable entry points.

Repository release labels such as `v2.0.0` are distinct from historical research-stage labels such
as `V11.1` and `V12`.

The maintained portable environment is defined by [`pyproject.toml`](../pyproject.toml) and
requires Python 3.11 or later. Exact versions for the core reproduction path are pinned in
[`requirements-reproduce-lock.txt`](../requirements-reproduce-lock.txt). The authoritative V12 run recorded Python 3.13.5, pandas 2.2.3,
NumPy 2.3.5, scikit-learn 1.8.0, XGBoost 3.1.3, LightGBM 4.6.0, CatBoost 1.2.8, and seed
`20260720`; see [`V12_ENVIRONMENT.txt`](../reports/frozen/V12_ENVIRONMENT.txt). Recorded core and optional model-family package versions from the broader historical search are
also listed in [`requirements-research-lock.txt`](../requirements-research-lock.txt). That historical
file is an environment record for the principal packages, whereas
`requirements-reproduce-lock.txt` is the exact version set used by the maintained portable core
path. The [validation workflow](../.github/workflows/validate.yml) keeps Python 3.11 compatibility
checks separate from a Python 3.13 locked-reproduction job that installs this exact version set.
Neither file pins the operating system, CPU libraries, or Python interpreter binary itself.

## Interpretation and remaining limitation

A successful reproduction establishes computational consistency between the released data, code,
portable outputs, frozen metrics, saved models, and audits. It does not establish that the model
will generalize to future seasons, eliminate uncertainty from method selection, or convert 2026
into an independent prospective test. The allowed scientific claims are stated in
[scientific status and claims](scientific_status_and_claims.md), and the remaining generalization
test is defined in [prospective validation](prospective_validation.md).
