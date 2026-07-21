#!/usr/bin/env python3
"""Reproduce the two frozen V12 specifications and role-specific ablations."""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from fifteenpick_prediction.bootstrap import paired_date_bootstrap
from fifteenpick_prediction.calibration import calibration_intercept_slope, calibration_table
from fifteenpick_prediction.metrics import probability_metrics
from fifteenpick_prediction.modeling import build_l2_logistic
from fifteenpick_prediction.schema import (
    ALL_FEATURES,
    BATTER_INDEX_FEATURES,
    CONVENTIONAL_FEATURES,
    STARTER_INDEX_FEATURES,
)
from fifteenpick_prediction.temporal import most_recent_training_rows, stable_temporal_sort
from fifteenpick_prediction.validation import validate_modeling_dataset

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATA = ROOT / "data" / "derived" / "V12_MODELING_DATASET.csv"
DEFAULT_OUTPUT = ROOT / "reports" / "reproduced"
SEED = 20260720

PROTOCOLS = [
    {"protocol": "CV_SELECTED", "C": 0.03, "training_strategy": "ALL_EQUAL"},
    {"protocol": "BEST_DEVELOPMENT", "C": 0.1, "training_strategy": "RECENT_720"},
]
FEATURE_GROUPS = {
    "BASELINE_NO_PLAYER_INDICES": CONVENTIONAL_FEATURES,
    "STARTER_INDEX_ONLY": CONVENTIONAL_FEATURES + STARTER_INDEX_FEATURES,
    "BATTER_INDEX_ONLY": CONVENTIONAL_FEATURES + BATTER_INDEX_FEATURES,
    "BATTER_PLUS_STARTER_INDICES": ALL_FEATURES,
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", type=Path, default=DEFAULT_DATA)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--bootstrap-reps", type=int, default=20_000)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    output = args.output_dir
    output.mkdir(parents=True, exist_ok=True)

    frame = stable_temporal_sort(pd.read_csv(args.data))
    audit = validate_modeling_dataset(frame)
    test = frame.loc[frame["season"].eq(2026)].copy()
    rng = np.random.default_rng(SEED)

    metric_rows: list[dict[str, object]] = []
    bootstrap_rows: list[dict[str, object]] = []
    prediction_frames: list[pd.DataFrame] = []
    calibration_frames: list[pd.DataFrame] = []
    calibration_summary_rows: list[dict[str, object]] = []
    coefficient_rows: list[dict[str, object]] = []

    for specification in PROTOCOLS:
        protocol = specification["protocol"]
        C = float(specification["C"])
        strategy = specification["training_strategy"]
        if strategy == "RECENT_720":
            train = most_recent_training_rows(frame, cutoff_date=20260328, n_rows=720)
        else:
            train = frame.loc[frame["game_date"] < 20260328].copy()

        predictions = test[["game_id", "game_date", "home_win"]].copy()
        fitted = {}
        for model_id, features in FEATURE_GROUPS.items():
            model = build_l2_logistic(C=C)
            model.fit(train[features], train["home_win"].astype(int))
            probability = model.predict_proba(test[features])[:, 1]
            predictions[model_id] = probability
            fitted[model_id] = model
            metric_rows.append(
                {
                    "protocol": protocol,
                    "C": C,
                    "training_strategy": strategy,
                    "model": model_id,
                    "feature_count": len(features),
                    **probability_metrics(test["home_win"], probability),
                }
            )

        predictions.insert(0, "protocol", protocol)
        prediction_frames.append(predictions)
        boot = paired_date_bootstrap(
            predictions,
            new_probability_col="BATTER_PLUS_STARTER_INDICES",
            reference_probability_col="BASELINE_NO_PLAYER_INDICES",
            reps=args.bootstrap_reps,
            rng=rng,
        )
        bootstrap_rows.append(
            {
                "protocol": protocol,
                "delta_log_loss_indices_minus_baseline": boot["delta_log_loss"],
                "ci_low": boot["ci_low"],
                "ci_high": boot["ci_high"],
                "improvement_probability": boot["improvement_probability"],
                "reps": boot["reps"],
            }
        )

        full_probability = predictions["BATTER_PLUS_STARTER_INDICES"].to_numpy(float)
        cal = calibration_table(test["home_win"], full_probability, bins=10)
        cal.insert(0, "protocol", protocol)
        calibration_frames.append(cal)
        calibration_summary_rows.append(
            {
                "protocol": protocol,
                **calibration_intercept_slope(test["home_win"], full_probability),
            }
        )

        full_model = fitted["BATTER_PLUS_STARTER_INDICES"]
        transformed_names = full_model.named_steps["imputer"].get_feature_names_out(ALL_FEATURES)
        coefs = full_model.named_steps["model"].coef_[0]
        for feature, coefficient in zip(transformed_names, coefs, strict=True):
            coefficient_rows.append(
                {"protocol": protocol, "feature": feature, "standardized_coefficient": coefficient}
            )

    pd.DataFrame(metric_rows).to_csv(output / "player_index_ablation.csv", index=False)
    pd.DataFrame(bootstrap_rows).to_csv(output / "player_index_ablation_bootstrap.csv", index=False)
    pd.concat(prediction_frames, ignore_index=True).to_csv(
        output / "player_index_ablation_predictions.csv", index=False
    )
    pd.concat(calibration_frames, ignore_index=True).to_csv(
        output / "calibration_deciles.csv", index=False
    )
    pd.DataFrame(calibration_summary_rows).to_csv(
        output / "calibration_intercept_slope.csv", index=False
    )
    pd.DataFrame(coefficient_rows).to_csv(output / "standardized_coefficients.csv", index=False)
    pd.DataFrame([audit]).to_json(output / "dataset_validation.json", orient="records", indent=2)
    print(f"PASS: reproduced core results in {output}")


if __name__ == "__main__":
    main()
