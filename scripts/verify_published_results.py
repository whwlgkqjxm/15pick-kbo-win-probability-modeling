#!/usr/bin/env python3
"""Verify the frozen aggregate results published in this repository."""

from __future__ import annotations

import math
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "reports" / "player_index_ablation.csv"
BOOTSTRAP = ROOT / "reports" / "player_index_ablation_bootstrap.csv"
RELIEF = ROOT / "reports" / "relief_pitcher_index_ablation.csv"

EXPECTED = {
    "BASELINE_NO_PLAYER_INDICES": {
        "log_loss": 0.6839421791444644,
        "brier": 0.24531296565005117,
        "roc_auc": 0.575780743211936,
        "accuracy": 0.5432692307692307,
    },
    "BATTER_PLUS_STARTER_INDICES": {
        "log_loss": 0.6661347844671042,
        "brier": 0.23649786240497755,
        "roc_auc": 0.635274766008711,
        "accuracy": 0.5961538461538461,
    },
}


def main() -> None:
    results = pd.read_csv(RESULTS)
    dev = results.loc[results["protocol"] == "BEST_DEVELOPMENT"].set_index("model")
    for model, metrics in EXPECTED.items():
        for metric, expected in metrics.items():
            actual = float(dev.loc[model, metric])
            if not math.isclose(actual, expected, rel_tol=0, abs_tol=1e-12):
                raise SystemExit(f"FAIL {model} {metric}: {actual} != {expected}")

    boot = pd.read_csv(BOOTSTRAP)
    row = boot.loc[boot["protocol"] == "BEST_DEVELOPMENT"].iloc[0]
    if not math.isclose(float(row["improvement_probability"]), 0.9869, abs_tol=1e-12):
        raise SystemExit("FAIL bootstrap improvement probability")

    relief = pd.read_csv(RELIEF).set_index("evaluation")
    expected_relief = {
        "2025_bullpen_domain": (0.687434978, 0.687444156),
        "2025_incremental": (0.669482620, 0.674253000),
        "2026_posthoc_incremental": (0.667785123, 0.668898000),
    }
    for evaluation, (reference, with_index) in expected_relief.items():
        actual_reference = float(relief.loc[evaluation, "reference_log_loss"])
        actual_index = float(relief.loc[evaluation, "relief_pitcher_index_log_loss"])
        if not math.isclose(actual_reference, reference, abs_tol=1e-12):
            raise SystemExit(f"FAIL relief reference: {evaluation}")
        if not math.isclose(actual_index, with_index, abs_tol=1e-12):
            raise SystemExit(f"FAIL relief-index model: {evaluation}")
        if with_index <= reference:
            raise SystemExit(f"FAIL expected negative relief-index result: {evaluation}")

    print("PASS: published player-index and relief-pitcher results match frozen values")


if __name__ == "__main__":
    main()
