#!/usr/bin/env python3
"""Rebuild the three machine-readable audits linked from the data-lineage page."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from fifteenpick_prediction.audit import build_v11_audit, build_v12_audit
from fifteenpick_prediction.temporal import stable_temporal_sort
from fifteenpick_prediction.validation import validate_modeling_dataset

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "derived" / "V12_MODELING_DATASET.csv"
FROZEN = ROOT / "reports" / "frozen"
REPRODUCED = ROOT / "reports" / "reproduced"
MODELS = ROOT / "models" / "frozen"


def _relative_paths(value: object) -> object:
    if isinstance(value, dict):
        result = {key: _relative_paths(item) for key, item in value.items()}
        if "evidence" in result and isinstance(result["evidence"], dict):
            result["evidence"] = {
                key: Path(str(path)).resolve().relative_to(ROOT).as_posix()
                for key, path in result["evidence"].items()
            }
        return result
    if isinstance(value, list):
        return [_relative_paths(item) for item in value]
    return value


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def build_all() -> dict[Path, dict[str, object]]:
    frame = stable_temporal_sort(pd.read_csv(DATA))
    dataset_validation = validate_modeling_dataset(frame)

    v12 = build_v12_audit(
        data_path=DATA,
        predictions_path=FROZEN / "V12_2026_ALL_PREDICTIONS.csv",
        cv_model_path=MODELS / "V12_CV_SELECTED_MODEL_REFIT_2024_2025.joblib",
        development_model_path=MODELS / "V12_2026_BEST_OBSERVED_RECENT720_MODEL.joblib",
        model_schema_path=FROZEN / "V12_MODEL_SCHEMA.json",
        selection_decision_path=FROZEN / "V12_MODEL_SELECTION_DECISION.json",
    )
    v11 = build_v11_audit(
        comparison_path=FROZEN / "V11_1_ROBUST_CANDIDATE_COMPARISON.csv",
        bootstrap_path=FROZEN / "V11_1_ROBUST_CANDIDATE_BOOTSTRAP.csv",
        decision_path=FROZEN / "V11_1_PROSPECTIVE_CANDIDATE_DECISION.json",
        model_schema_path=FROZEN / "V11_1_PROSPECTIVE_MODEL_SCHEMA.json",
        formula_path=FROZEN / "V11_1_SELECTED_BATTER_INCOME_FORMULA.json",
        model_path=MODELS / "V11_1_PROSPECTIVE_REFIT_MODEL_2024_2025.joblib",
    )

    return {
        REPRODUCED / "dataset_validation.json": dataset_validation,
        FROZEN / "V12_REPRODUCIBILITY_AND_LEAKAGE_AUDIT.json": _relative_paths(v12),
        FROZEN / "V11_1_REPRODUCIBILITY_AUDIT.json": _relative_paths(v11),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--check",
        action="store_true",
        help="fail if committed linked audits differ from recomputed values",
    )
    args = parser.parse_args()

    outputs = build_all()
    if args.check:
        stale = []
        for path, payload in outputs.items():
            committed = json.loads(path.read_text(encoding="utf-8"))
            if committed != payload:
                stale.append(path.relative_to(ROOT).as_posix())
        if stale:
            raise SystemExit(f"FAIL stale linked audits: {stale}")
        print(f"PASS: {len(outputs)} linked audits match recomputed values")
        return

    for path, payload in outputs.items():
        _write_json(path, payload)
        print(f"wrote {path.relative_to(ROOT)}")
    print(f"PASS: rebuilt {len(outputs)} linked audits")


if __name__ == "__main__":
    main()
