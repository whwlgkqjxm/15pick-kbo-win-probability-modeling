# Do Player-Income Indices Improve KBO Win-Probability Forecasts?

[![Python](https://img.shields.io/badge/Python-3.11%2B-blue)](#reproduction)
[![Task](https://img.shields.io/badge/Task-Probabilistic%20Forecasting-informational)](#research-question)
[![Validation](https://img.shields.io/badge/Validation-Temporal%20%2B%20Leakage--Controlled-success)](#methodology)
[![Status](https://img.shields.io/badge/Status-Retrospective%20Development-orange)](#scientific-status)

**MyPick KBO Player-Income Research** studies whether a compact, role-specific summary of player performance contains real predictive information for pregame baseball forecasts.

I originally built **MyPick**, a fantasy-sports and point-based prediction platform, to translate complex KBO records into a single intuitive **player-income score**. The product goal was simple: help fans compare how strongly different players contributed without requiring them to interpret dozens of batting and pitching statistics.

That product decision led to a research question:

> **Does this simplified player-income representation preserve meaningful information about future game outcomes, or is it only an easier way to display past performance?**

This repository answers that question through official KBO data engineering, role-specific index design, strict point-in-time feature construction, temporal machine learning, ablation studies, and probability-focused evaluation.

## Research Question

> **Do role-specific, strictly prior composite player-performance indices derived from official KBO game records improve pregame KBO win-probability forecasts beyond models based on conventional team strength and pregame records?**

### Korean

> **공식 KBO 경기 기록으로 구축한 역할별 strict-prior 복합 선수 활약도 지표는 기존 팀 전력과 일반적인 경기 전 기록만 사용하는 모델보다 KBO 경기의 승리확률 예측을 개선하는가?**

## Main Finding

**Retrospective evidence supports the hypothesis.** Under the same model family, training window, and team-strength features, adding the prior-average batter and starting-pitcher income indices improved every primary evaluation metric.

### Best observed development comparison — 416 games in 2026

| Model | Log loss ↓ | Brier ↓ | ROC AUC ↑ | Accuracy ↑ |
|---|---:|---:|---:|---:|
| Conventional pregame features, **no player income** | 0.683942 | 0.245313 | 0.575781 | 54.33% |
| Conventional features + **batter and starter income** | **0.666135** | **0.236498** | **0.635275** | **59.62%** |
| Change | **−0.017807** | **−0.008815** | **+0.059494** | **+5.29 pp** |

Date-cluster bootstrap, 20,000 repetitions:

- Probability that the full-income model improves Log loss: **98.69%**
- 95% interval for `full − no income`: **[−0.033154, −0.002114]**

![Primary ablation](reports/figures/primary_ablation_logloss.png)

### Role ablation

| Player-income block | Log loss ↓ | Brier ↓ | ROC AUC ↑ | Accuracy ↑ |
|---|---:|---:|---:|---:|
| No player income | 0.683942 | 0.245313 | 0.575781 | 54.33% |
| Batter income only | 0.678611 | 0.242599 | 0.603188 | 57.45% |
| Starting-pitcher income only | 0.673157 | 0.239875 | 0.617343 | 57.93% |
| **Batter + starting-pitcher income** | **0.666135** | **0.236498** | **0.635275** | **59.62%** |

The result suggests that the two role-specific indices are complementary: starting-pitcher income contributed the larger individual gain, while batter income added further information beyond the starter block.

## Scientific Status

The repository distinguishes two claims:

1. **CV-selected specification:** model family and regularization were selected using temporal cross-validation on 2024–2025. On 2026, adding all player-income features reduced Log loss from `0.683516` to `0.667390`.
2. **Best observed development specification:** the recent-720-game strategy produced the strongest 2026 result, reducing Log loss from `0.683942` to `0.666135`.

The second result is the current development champion, but 2026 has been repeatedly observed during research. It is therefore **not presented as an untouched final test**. A frozen prospective prediction ledger is required for the final generalization claim.

## Why This Project Is More Than a Sports Prediction Model

This is a study of **representation value**:

```mermaid
flowchart LR
    A[Official KBO game records] --> B[Canonical player-game events]
    B --> C[Role-specific game indices]
    C --> D[Strict-prior player averages]
    D --> E[Confirmed lineup and starter aggregation]
    E --> F[Pregame probability model]
    F --> G[Ablation: with vs without player income]
```

The central contribution is not simply a classifier. It is the design and evaluation of a compact player-performance representation under realistic temporal constraints.

## Data Foundation

| Component | Scale |
|---|---:|
| Official completed games | 1,864 |
| Seasons | 2024, 2025, 2026 through July 9 |
| Player-game occurrences | 65,554 |
| Batter occurrences | 47,353 |
| Pitcher occurrences | 18,201 |
| Official starting-lineup rows | 33,552 |
| Resolved player occurrences | 65,554 / 65,554 |
| Same-date temporal violations | 0 |

The public repository does not redistribute the full official raw dataset. It provides schemas, synthetic examples, maintained research code, aggregate results, and reproducibility instructions.

## Player-Income Indices

### Batter index

The selected batter system scores official plate-appearance events, converts the score to a 4.2-PA rate, standardizes it around 1,000, and forms a strict-prior player mean with `K=5` shrinkage toward the previous-season mean.

Event weights:

| Event | Weight |
|---|---:|
| Single | 0.50 |
| Double | 0.95 |
| Triple | 1.35 |
| Home run | 1.85 |
| Walk / HBP | 0.42 |
| Stolen base | 0.22 |
| Strikeout | −0.08 |
| Grounded into double play | −0.32 |

The game feature aggregates the official nine-player starting lineup using the mean prior index plus coverage and reliability variables.

### Starting-pitcher index

Starting pitchers are evaluated from **prior starts only**, without mixing relief appearances. The game index combines recorded outs and strikeouts with penalties for home runs, walks, and hit batters. A `K=10` cross-season shrinkage mean stabilizes early-season estimates.

Detailed definitions are in [`docs/player_income_index.md`](docs/player_income_index.md).

## Methodology

- Official KBO schedule and GameCenter records
- Numeric player identity resolution rather than name-only joins
- Current-game and same-date results excluded
- Doubleheader Game 1 excluded from Game 2 features on the same date
- Train-only imputation and scaling
- Temporal cross-validation rather than shuffled splits
- Probability-first model selection using Log loss and Brier score
- Date-cluster bootstrap for paired uncertainty
- Explicit feature-group ablation

See [`docs/temporal_validation.md`](docs/temporal_validation.md).

## Model and Training-Strategy Search

The study compared:

- L2 logistic regression
- Elastic Net
- Random Forest and Extra Trees
- Gradient boosting and histogram boosting
- XGBoost, LightGBM, and CatBoost
- Probability blending, stacking, and calibration
- Full-history, recent-window, time-decay, rolling, expanding, and daily-update training strategies

The strongest and most stable family was a regularized logistic model. The best observed development configuration was:

```yaml
model: L2 logistic regression
C: 0.1
training_strategy: most recent 720 decision games
features: team strength + post-starter team runs + starter income + batter income
```

Complexity did not automatically improve generalization; several tree and ensemble models were rejected after worse temporal probability performance.

## Research Progress and Failure Analysis

The project deliberately preserves negative results and design corrections:

1. A 2026-only limited-sample model produced weak, compressed probabilities.
2. Multi-season data improved estimation stability.
3. A broad high-dimensional model search underperformed a regularized logistic model.
4. A role audit found that early income histories mixed substitute/starter and starter/reliever appearances.
5. The starting-pitcher index was rebuilt from start-only records.
6. Player-level bullpen income did not add stable predictive value.
7. Additional workload, handedness, and lineup-interaction features did not improve probability loss.
8. A new batter index was selected from 215 official-event candidates.
9. Forty-two model and learning-strategy configurations were compared.
10. The final ablation directly tested all player-income features against a no-income model.

See [`docs/experiment_history.md`](docs/experiment_history.md) and [`docs/failure_analysis.md`](docs/failure_analysis.md).

## Repository Structure

```text
.
├── src/mypick_rq1/           # maintained index, temporal, modeling, and evaluation code
├── scripts/                  # reproducible command-line entry points
├── configs/                  # frozen formulas and model specifications
├── experiments/              # key experiment cards and retained research scripts
├── reports/                  # published aggregate results and figures
├── docs/                     # research design, lineage, failures, and limitations
├── data/schema/              # public schemas
├── data/sample/              # synthetic examples only
├── tests/                    # temporal, formula, and result-verification tests
└── models/                   # model registry; binaries are not required for review
```

## Reproduction

### Install

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

### Verify published results

```bash
python scripts/verify_published_results.py
pytest
```

### Re-run the primary ablation with a local modeling dataset

```bash
python scripts/reproduce_primary_ablation.py \
  --data /path/to/V12_MODELING_DATASET.csv \
  --protocol best-development \
  --output reports/reproduced_primary_ablation.csv
```

The full official dataset is intentionally not committed. Required columns and file contracts are documented in [`data/schema/modeling_dataset_schema.csv`](data/schema/modeling_dataset_schema.csv).

## Limitations

- The strongest recent-720 result is a retrospective development result, not a pristine final test.
- Historical official lineup records were reconstructed from completed game pages; a future production study should capture immutable pregame timestamps.
- Exact physical runs after starter exit require play-by-play substitution and scoring timelines.
- Market odds, weather, injuries, and verified historical roster availability are outside the primary feature set.
- Final external validity requires frozen prospective predictions.

## Next Step

Freeze the current model, store each future prediction before first pitch with input and model hashes, and evaluate the immutable ledger using Log loss, Brier score, calibration, AUC, and date-cluster uncertainty.

## License and Data Use

Code and original documentation are released under the MIT License. Official KBO source data remains subject to its original rights and terms; this repository does not redistribute the complete raw archive.
