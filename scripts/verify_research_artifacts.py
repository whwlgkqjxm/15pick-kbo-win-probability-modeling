#!/usr/bin/env python3
"""Fail-closed verification of data, reproduced metrics, and saved model replay."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import subprocess
import sys
import tempfile
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

from fifteenpick_prediction.schema import ALL_FEATURES
from fifteenpick_prediction.temporal import stable_temporal_sort
from fifteenpick_prediction.validation import validate_modeling_dataset

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "derived" / "V12_MODELING_DATASET.csv"
FROZEN = ROOT / "reports" / "frozen"
MODELS = ROOT / "models" / "frozen"
MANIFEST = ROOT / "artifacts" / "RESEARCH_MANIFEST_SHA256.csv"

EXPECTED = {
    ("CV_SELECTED", "BATTER_PLUS_STARTER_INDICES"): {
        "log_loss": 0.6673896327657686,
        "brier": 0.2370343931469793,
        "roc_auc": 0.6315679733110926,
        "accuracy": 0.59375,
    },
    ("BEST_DEVELOPMENT", "BATTER_PLUS_STARTER_INDICES"): {
        "log_loss": 0.6661347844671042,
        "brier": 0.23649786240497755,
        "roc_auc": 0.635274766008711,
        "accuracy": 0.5961538461538461,
    },
    ("BEST_DEVELOPMENT", "BASELINE_NO_PLAYER_INDICES"): {
        "log_loss": 0.6839421791444644,
        "brier": 0.24531296565005117,
        "roc_auc": 0.575780743211936,
        "accuracy": 0.5432692307692307,
    },
    ("BEST_DEVELOPMENT", "CONSTANT_0_5"): {
        "log_loss": 0.6931471805599453,
        "brier": 0.25,
        "roc_auc": 0.5,
        "accuracy": 0.5240384615384616,
    },
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def verify_manifest() -> None:
    manifest = pd.read_csv(MANIFEST)
    for row in manifest.itertuples(index=False):
        path = ROOT / row.relative_path
        if not path.is_file():
            raise SystemExit(f"FAIL missing manifest file: {row.relative_path}")
        if sha256(path) != row.sha256:
            raise SystemExit(f"FAIL SHA mismatch: {row.relative_path}")


def verify_reproduction() -> None:
    with tempfile.TemporaryDirectory() as directory:
        target = Path(directory)
        subprocess.run(
            [
                sys.executable,
                str(ROOT / "scripts" / "reproduce_core_results.py"),
                "--data",
                str(DATA),
                "--output-dir",
                str(target),
                "--bootstrap-reps",
                "20000",
            ],
            check=True,
        )
        results = pd.read_csv(target / "player_index_ablation.csv").set_index(["protocol", "model"])
        for key, metrics in EXPECTED.items():
            for metric, expected in metrics.items():
                actual = float(results.loc[key, metric])
                if not math.isclose(actual, expected, rel_tol=0, abs_tol=1e-12):
                    raise SystemExit(f"FAIL reproduction {key} {metric}: {actual} != {expected}")
        bootstrap = pd.read_csv(
            target / "player_index_ablation_bootstrap.csv"
        ).set_index("protocol")
        expected_boot = {
            "CV_SELECTED": (-0.0161267523384099, -0.0320656558113629, 0.0004246983726018, 0.97165),
            "BEST_DEVELOPMENT": (
                -0.0178073946773601,
                -0.0331539101136537,
                -0.0021136959864507,
                0.9869,
            ),
        }
        for protocol, expected in expected_boot.items():
            actual = bootstrap.loc[protocol]
            for column, value in zip(
                [
                    "delta_log_loss_indices_minus_baseline",
                    "ci_low",
                    "ci_high",
                    "improvement_probability",
                ],
                expected,
                strict=True,
            ):
                if not math.isclose(float(actual[column]), value, rel_tol=0, abs_tol=1e-12):
                    raise SystemExit(f"FAIL bootstrap {protocol} {column}")


def verify_model_replay(frame: pd.DataFrame) -> dict[str, float]:
    test = frame.loc[frame["season"].eq(2026)]
    frozen_predictions = pd.read_csv(FROZEN / "V12_2026_ALL_PREDICTIONS.csv")
    cv = joblib.load(MODELS / "V12_CV_SELECTED_MODEL_REFIT_2024_2025.joblib")
    dev = joblib.load(MODELS / "V12_2026_BEST_OBSERVED_RECENT720_MODEL.joblib")
    cv_probability = cv.predict_proba(test[ALL_FEATURES])[:, 1]
    dev_probability = dev.predict_proba(test[ALL_FEATURES])[:, 1]
    cv_error = float(
        np.max(np.abs(cv_probability - frozen_predictions["p__L2_C0.03__ALL_EQUAL"].to_numpy()))
    )
    dev_error = float(
        np.max(np.abs(dev_probability - frozen_predictions["p__L2_C0.1__RECENT_720"].to_numpy()))
    )
    if cv_error >= 1e-12 or dev_error >= 1e-12:
        raise SystemExit(f"FAIL model replay: cv={cv_error}, development={dev_error}")
    return {"cv_model_max_abs_error": cv_error, "development_model_max_abs_error": dev_error}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--skip-manifest", action="store_true")
    args = parser.parse_args()
    frame = stable_temporal_sort(pd.read_csv(DATA))
    audit = validate_modeling_dataset(frame)
    if not args.skip_manifest:
        verify_manifest()
    verify_reproduction()
    replay = verify_model_replay(frame)
    print(json.dumps({"status": "PASS", "dataset": audit, "model_replay": replay}, indent=2))


if __name__ == "__main__":
    main()
