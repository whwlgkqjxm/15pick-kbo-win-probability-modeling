# Reproducibility and artifact provenance

## Reproduction levels

### Level 1 — portable core reproduction

`make reproduce` loads the included 1,824-row derived modeling table and regenerates:

- four role-specific ablation models under two frozen specifications;
- game-level probabilities;
- Log loss, Brier, AUC, and accuracy;
- paired date-cluster bootstrap intervals;
- calibration deciles and intercept/slope;
- standardized logistic coefficients.

### Level 2 — fail-closed verification

`make verify` checks:

- dataset schema and exact season row counts;
- unique game IDs;
- deterministic `game_date, game_id` sorting;
- same-date exclusion flags;
- research artifact SHA256 manifest;
- exact published metrics and bootstrap values;
- saved CV/development model replay against frozen prediction columns.

### Level 3 — historical execution evidence

`research/authoritative/v11_1` and `research/authoritative/v12` preserve the original research execution scripts. These scripts reference the historical private workspace and optional heavy ML dependencies. They are evidence of the full search, while `scripts/` provides the maintained portable entry points.

## Expected replay precision

The stored V12 model binaries replay the frozen 2026 probabilities with maximum absolute errors on the order of `1e-16`, below the repository threshold of `1e-12`.

## Environment

The authoritative V12 run recorded Python 3.13.5, pandas 2.2.3, NumPy 2.3.5, scikit-learn 1.8.0, XGBoost 3.1.3, LightGBM 4.6.0, CatBoost 1.2.8, and seed 20260720. A portable dependency range is provided in `pyproject.toml`; the historical exact versions are in `requirements-research-lock.txt`.

## Artifact manifest

`artifacts/RESEARCH_MANIFEST_SHA256.csv` records relative path, byte size, and SHA256 for derived data, frozen models, frozen results, historical source, and research records.
