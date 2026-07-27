import json
from pathlib import Path

import pandas as pd

from fifteenpick_prediction.audit import (
    audit_payloads_equal,
    build_v11_audit,
    build_v12_audit,
)
from fifteenpick_prediction.temporal import stable_temporal_sort
from fifteenpick_prediction.validation import validate_modeling_dataset

ROOT = Path(__file__).resolve().parents[1]
FROZEN = ROOT / "reports/frozen"
MODELS = ROOT / "models/frozen"
DATA = ROOT / "data/derived/V12_MODELING_DATASET.csv"


def relative_evidence(payload):
    payload["evidence"] = {
        key: Path(value).resolve().relative_to(ROOT).as_posix()
        for key, value in payload["evidence"].items()
    }
    return payload


def test_dataset_validation_link_matches_recomputed_data():
    frame = stable_temporal_sort(pd.read_csv(DATA))
    actual = validate_modeling_dataset(frame)
    committed = json.loads(
        (ROOT / "reports/reproduced/dataset_validation.json").read_text(encoding="utf-8")
    )
    assert audit_payloads_equal(actual, committed)


def test_v12_link_matches_recomputed_artifacts():
    actual = build_v12_audit(
        data_path=DATA,
        predictions_path=FROZEN / "V12_2026_ALL_PREDICTIONS.csv",
        cv_model_path=MODELS / "V12_CV_SELECTED_MODEL_REFIT_2024_2025.joblib",
        development_model_path=MODELS / "V12_2026_BEST_OBSERVED_RECENT720_MODEL.joblib",
        model_schema_path=FROZEN / "V12_MODEL_SCHEMA.json",
        selection_decision_path=FROZEN / "V12_MODEL_SELECTION_DECISION.json",
    )
    actual = relative_evidence(actual)
    committed = json.loads(
        (FROZEN / "V12_REPRODUCIBILITY_AND_LEAKAGE_AUDIT.json").read_text(
            encoding="utf-8"
        )
    )
    assert audit_payloads_equal(actual, committed)


def test_v11_link_matches_publicly_verifiable_artifacts():
    actual = build_v11_audit(
        comparison_path=FROZEN / "V11_1_ROBUST_CANDIDATE_COMPARISON.csv",
        bootstrap_path=FROZEN / "V11_1_ROBUST_CANDIDATE_BOOTSTRAP.csv",
        decision_path=FROZEN / "V11_1_PROSPECTIVE_CANDIDATE_DECISION.json",
        model_schema_path=FROZEN / "V11_1_PROSPECTIVE_MODEL_SCHEMA.json",
        formula_path=FROZEN / "V11_1_SELECTED_BATTER_INCOME_FORMULA.json",
        model_path=MODELS / "V11_1_PROSPECTIVE_REFIT_MODEL_2024_2025.joblib",
    )
    actual = relative_evidence(actual)
    committed = json.loads(
        (FROZEN / "V11_1_REPRODUCIBILITY_AUDIT.json").read_text(encoding="utf-8")
    )
    assert audit_payloads_equal(actual, committed)
    assert actual["source_pipeline_lineup_record"]["public_repository_recomputation"] is False


def test_audit_payload_comparison_tolerates_machine_precision_replay_drift():
    committed = {
        "key_results": {
            "cv_model_max_abs_prediction_error": 1.1102230246251565e-16,
            "required_max_abs_prediction_error_below": 1e-12,
        }
    }
    recomputed = {
        "key_results": {
            "cv_model_max_abs_prediction_error": 1.6653345369377348e-16,
            "required_max_abs_prediction_error_below": 1e-12,
        }
    }

    assert audit_payloads_equal(committed, recomputed)


def test_audit_payload_comparison_rejects_material_replay_drift():
    committed = {
        "key_results": {
            "cv_model_max_abs_prediction_error": 0.0,
        }
    }
    recomputed = {
        "key_results": {
            "cv_model_max_abs_prediction_error": 2e-14,
        }
    }

    assert not audit_payloads_equal(committed, recomputed)


def test_audit_payload_comparison_keeps_threshold_exact():
    committed = {
        "key_results": {
            "required_max_abs_prediction_error_below": 1e-12,
        }
    }
    recomputed = {
        "key_results": {
            "required_max_abs_prediction_error_below": 1.000000000001e-12,
        }
    }

    assert not audit_payloads_equal(committed, recomputed)
