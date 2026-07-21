#!/usr/bin/env python3
"""Verify the frozen aggregate results published in this repository."""

from __future__ import annotations

import math
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "reports" / "primary_income_ablation.csv"
BOOTSTRAP = ROOT / "reports" / "primary_income_ablation_bootstrap.csv"
BULLPEN = ROOT / "reports" / "bullpen_income_ablation.csv"

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
    bullpen = pd.read_csv(BULLPEN).set_index("evaluation")
    expected_bullpen = {
        "2025_bullpen_domain": (0.687434978, 0.687444156),
        "2025_incremental": (0.669482620, 0.674253000),
        "2026_posthoc_incremental": (0.667785123, 0.668898000),
    }
    for evaluation, (reference, with_bullpen) in expected_bullpen.items():
        if not math.isclose(float(bullpen.loc[evaluation, "reference_log_loss"]), reference, abs_tol=1e-12):
            raise SystemExit(f"FAIL bullpen reference: {evaluation}")
        if not math.isclose(float(bullpen.loc[evaluation, "bullpen_income_log_loss"]), with_bullpen, abs_tol=1e-12):
            raise SystemExit(f"FAIL bullpen model: {evaluation}")
        if with_bullpen <= reference:
            raise SystemExit(f"FAIL expected negative bullpen result: {evaluation}")

    print("PASS: published primary and bullpen results match the frozen values")


if __name__ == "__main__":
    main()
