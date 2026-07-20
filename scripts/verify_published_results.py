#!/usr/bin/env python3
"""Verify the frozen aggregate results published in this repository."""

from __future__ import annotations

import math
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "reports" / "primary_income_ablation.csv"
BOOTSTRAP = ROOT / "reports" / "primary_income_ablation_bootstrap.csv"

EXPECTED = {
    "NO_PLAYER_INCOME": {
        "log_loss": 0.6839421791444644,
        "brier": 0.24531296565005117,
        "roc_auc": 0.575780743211936,
        "accuracy": 0.5432692307692307,
    },
    "ALL_PLAYER_INCOME": {
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
    print("PASS: published primary results match the frozen values")


if __name__ == "__main__":
    main()
