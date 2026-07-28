"""Computed verification for the machine-readable files linked from the data-lineage page."""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd

from .schema import ALL_FEATURES
from .temporal import stable_temporal_sort
from .validation import validate_modeling_dataset

V11_EXPECTED_MODELS = {
    "V11_1_NEW_BATTER",
    "V9_STYLE_CURRENT_PRIMARY",
    "CLEAN_NO_BATTER",
    "TEAM_BASELINE",
}
V11_EXPECTED_BATTER_WEIGHTS = {
    "singles": 0.50,
    "doubles": 0.95,
    "triples": 1.35,
    "home_runs": 1.85,
    "walks": 0.42,
    "hit_by_pitch": 0.42,
    "stolen_bases": 0.22,
    "strikeouts": -0.08,
    "double_play": -0.32,
}
V11_EXPECTED_FORMULA_WEIGHTS = {
    **V11_EXPECTED_BATTER_WEIGHTS,
    "runs": 0.0,
    "rbi": 0.0,
    "game_winning_hit": 0.0,
}
V11_EXPECTED_LINEUP_FEATURES = [
    "mean",
    "coverage",
    "count_mean",
    "coverage_min",
]


_TOLERANT_AUDIT_FLOAT_PATHS = {
    ("key_results", "cv_model_max_abs_prediction_error"),
    ("key_results", "development_model_max_abs_prediction_error"),
}


def audit_payloads_equal(
    left: Any,
    right: Any,
    *,
    abs_tol: float = 1e-14,
    _path: tuple[str | int, ...] = (),
) -> bool:
    """Compare audit payloads exactly except machine-precision replay diagnostics."""

    if isinstance(left, dict) and isinstance(right, dict):
        if left.keys() != right.keys():
            return False
        return all(
            audit_payloads_equal(
                left[key],
                right[key],
                abs_tol=abs_tol,
                _path=(*_path, key),
            )
            for key in left
        )

    if isinstance(left, list) and isinstance(right, list):
        if len(left) != len(right):
            return False
        return all(
            audit_payloads_equal(
                left_item,
                right_item,
                abs_tol=abs_tol,
                _path=(*_path, index),
            )
            for index, (left_item, right_item) in enumerate(
                zip(left, right, strict=True)
            )
        )

    if _path in _TOLERANT_AUDIT_FLOAT_PATHS:
        if isinstance(left, bool) or isinstance(right, bool):
            return left is right
        if isinstance(left, (int, float)) and isinstance(right, (int, float)):
            return math.isclose(
                float(left),
                float(right),
                rel_tol=0.0,
                abs_tol=abs_tol,
            )

    return left == right


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _numeric_mapping_matches(
    actual: object,
    expected: dict[str, float],
    *,
    abs_tol: float = 1e-12,
) -> bool:
    """Return whether a JSON object contains the expected finite numeric values."""

    if not isinstance(actual, dict) or set(actual) != set(expected):
        return False
    for key, expected_value in expected.items():
        actual_value = actual[key]
        if isinstance(actual_value, bool) or not isinstance(actual_value, (int, float)):
            return False
        if not math.isfinite(float(actual_value)) or not math.isclose(
            float(actual_value), expected_value, rel_tol=0.0, abs_tol=abs_tol
        ):
            return False
    return True


def _finite_number_matches(
    actual: object,
    expected: float,
    *,
    abs_tol: float = 1e-12,
) -> bool:
    """Return whether one JSON value matches the expected finite number."""

    return (
        not isinstance(actual, bool)
        and isinstance(actual, (int, float))
        and math.isfinite(float(actual))
        and math.isclose(float(actual), expected, rel_tol=0.0, abs_tol=abs_tol)
    )


def _probability_columns(frame: pd.DataFrame) -> list[str]:
    return [column for column in frame.columns if column.startswith("p__")]


def _all_probabilities_valid(frame: pd.DataFrame, columns: list[str]) -> bool:
    if not columns:
        return False
    values = frame[columns].to_numpy(dtype=float)
    return bool(np.isfinite(values).all() and ((values >= 0.0) & (values <= 1.0)).all())


def build_v12_audit(
    *,
    data_path: Path,
    predictions_path: Path,
    cv_model_path: Path,
    development_model_path: Path,
    model_schema_path: Path,
    selection_decision_path: Path,
) -> dict[str, Any]:
    """Recompute the public V12 dataset, prediction, and saved-model checks."""

    frame = pd.read_csv(data_path)
    dataset_audit = validate_modeling_dataset(frame)
    frame = stable_temporal_sort(frame)
    test = frame.loc[frame["season"].eq(2026)].copy()

    predictions = pd.read_csv(predictions_path)
    probability_columns = _probability_columns(predictions)
    rows_match = len(predictions) == len(test)
    ids_match = rows_match and predictions["game_id"].tolist() == test["game_id"].tolist()
    probabilities_valid = _all_probabilities_valid(predictions, probability_columns)
    if not rows_match:
        raise ValueError(f"V12 prediction row mismatch: {len(predictions)} != {len(test)}")
    if not ids_match:
        raise ValueError("V12 prediction game_id order does not match the 2026 dataset")
    if not probabilities_valid:
        raise ValueError("V12 prediction probabilities are missing, non-finite, or out of bounds")

    cv_model = joblib.load(cv_model_path)
    development_model = joblib.load(development_model_path)
    cv_probability = cv_model.predict_proba(test[ALL_FEATURES])[:, 1]
    development_probability = development_model.predict_proba(test[ALL_FEATURES])[:, 1]

    cv_reference = predictions["p__L2_C0.03__ALL_EQUAL"].to_numpy(dtype=float)
    development_reference = predictions["p__L2_C0.1__RECENT_720"].to_numpy(dtype=float)
    cv_error = float(np.max(np.abs(cv_probability - cv_reference)))
    development_error = float(np.max(np.abs(development_probability - development_reference)))
    replay_threshold = 1e-12
    replay_pass = cv_error < replay_threshold and development_error < replay_threshold
    if not replay_pass:
        raise ValueError(
            "saved-model replay failed: "
            f"cv={cv_error}, development={development_error}, threshold={replay_threshold}"
        )

    model_schema = _read_json(model_schema_path)
    selection_decision = _read_json(selection_decision_path)
    schema_features_match = model_schema.get("feature_columns") == ALL_FEATURES
    training_seasons = model_schema.get("development_training_seasons")
    evaluation_season = model_schema.get("development_evaluation_season")
    selection_metadata_excludes_2026 = (
        training_seasons == [2024, 2025] and evaluation_season == 2026
    )
    if not schema_features_match:
        raise ValueError("V12 model schema does not match the 14 frozen features")
    if not selection_metadata_excludes_2026:
        raise ValueError(
            "V12 model-selection metadata does not preserve the 2026 evaluation boundary"
        )

    checks = {
        "dataset_validation_passed": dataset_audit["status"] == "PASS",
        "prediction_rows_416": rows_match,
        "prediction_game_ids_match": ids_match,
        "prediction_probabilities_valid": probabilities_valid,
        "model_schema_matches_14_features": schema_features_match,
        "selection_metadata_excludes_2026": selection_metadata_excludes_2026,
        "saved_models_loadable": True,
        "saved_predictions_replay": replay_pass,
        "same_date_team_updates_excluded": dataset_audit["temporal_controls"][
            "same_date_team_updates_excluded"
        ],
        "same_date_player_results_excluded": dataset_audit["temporal_controls"][
            "same_date_player_results_excluded"
        ],
    }
    if not all(checks.values()):
        raise ValueError(f"V12 audit failed: {checks}")

    return {
        "status": "PASS",
        "audit_scope": (
            "repository-recomputed from the released modeling table, frozen predictions, "
            "saved models, and frozen model metadata"
        ),
        "checks": checks,
        "key_results": {
            "rows_total": dataset_audit["dataset"]["rows"],
            "rows_by_season": dataset_audit["dataset"]["rows_by_season"],
            "feature_count": dataset_audit["features"]["present_count"],
            "feature_groups": dataset_audit["features"]["groups"],
            "candidate_probability_columns": len(probability_columns),
            "probability_out_of_bounds": 0,
            "cv_model_max_abs_prediction_error": cv_error,
            "development_model_max_abs_prediction_error": development_error,
            "required_max_abs_prediction_error_below": replay_threshold,
        },
        "scientific_status": selection_decision.get("scientific_status", {}),
        "evidence": {
            "modeling_dataset": data_path.as_posix(),
            "frozen_predictions": predictions_path.as_posix(),
            "cv_model": cv_model_path.as_posix(),
            "development_model": development_model_path.as_posix(),
            "model_schema": model_schema_path.as_posix(),
            "selection_decision": selection_decision_path.as_posix(),
        },
    }


def build_v11_audit(
    *,
    comparison_path: Path,
    bootstrap_path: Path,
    decision_path: Path,
    model_schema_path: Path,
    formula_path: Path,
    batter_config_path: Path,
    model_path: Path,
) -> dict[str, Any]:
    """Verify the V11.1 artifacts that can be checked from the public repository."""

    required_paths = [
        comparison_path,
        bootstrap_path,
        decision_path,
        model_schema_path,
        formula_path,
        batter_config_path,
        model_path,
    ]
    required_files_present = all(path.is_file() for path in required_paths)
    if not required_files_present:
        missing = [path.as_posix() for path in required_paths if not path.is_file()]
        raise ValueError(f"missing V11.1 evidence files: {missing}")

    comparison = pd.read_csv(comparison_path).set_index("model_id")
    bootstrap = pd.read_csv(bootstrap_path)
    decision = _read_json(decision_path)
    model_schema = _read_json(model_schema_path)
    formula = _read_json(formula_path)
    batter_config = _read_json(batter_config_path)
    model = joblib.load(model_path)

    comparison_models_present = set(comparison.index) == V11_EXPECTED_MODELS
    comparison_rows_698 = bool(comparison["n"].eq(698).all())
    metric_bounds_valid = bool(
        comparison["log_loss"].gt(0).all()
        and comparison["brier"].between(0, 1).all()
        and comparison["roc_auc"].between(0, 1).all()
        and comparison["accuracy"].between(0, 1).all()
    )
    if not comparison_models_present or not comparison_rows_698 or not metric_bounds_valid:
        raise ValueError("V11.1 comparison table failed structural validation")

    new_loss = float(comparison.loc["V11_1_NEW_BATTER", "log_loss"])
    clean_loss = float(comparison.loc["CLEAN_NO_BATTER", "log_loss"])
    v9_loss = float(comparison.loc["V9_STYLE_CURRENT_PRIMARY", "log_loss"])
    new_auc = float(comparison.loc["V11_1_NEW_BATTER", "roc_auc"])
    delta_clean = new_loss - clean_loss
    delta_v9 = new_loss - v9_loss

    bootstrap_clean = bootstrap.loc[
        (bootstrap["new_model"] == "p_v11_1_new_batter")
        & (bootstrap["reference_model"] == "p_clean_no_batter")
    ]
    if len(bootstrap_clean) != 1:
        raise ValueError("V11.1 clean-baseline bootstrap row is missing or duplicated")
    bootstrap_clean_row = bootstrap_clean.iloc[0]
    reported_delta_matches = math.isclose(
        float(bootstrap_clean_row["delta_log_loss"]), delta_clean, rel_tol=0, abs_tol=1e-12
    )
    if not reported_delta_matches:
        raise ValueError("V11.1 comparison and bootstrap deltas do not match")

    bootstrap_ci_low = float(bootstrap_clean_row["ci_low"])
    bootstrap_ci_high = float(bootstrap_clean_row["ci_high"])
    bootstrap_interval_includes_zero = bootstrap_ci_low <= 0.0 <= bootstrap_ci_high

    schema_matches = model_schema.get("feature_columns") == ALL_FEATURES
    no_2026_training = (
        model_schema.get("training_seasons") == [2024, 2025]
        and model_schema.get("excluded_from_training") == [2026]
        and decision.get("no_2026_tuning") is True
    )
    formula_weights = formula.get("weights")
    config_clip = batter_config.get("clip")
    config_metadata_matches = (
        batter_config.get("index_id") == "BATTER_POWER_OBP_RATE100"
        and batter_config.get("role") == "batter"
        and _numeric_mapping_matches(
            batter_config.get("weights"), V11_EXPECTED_BATTER_WEIGHTS
        )
        and _finite_number_matches(
            batter_config.get("plate_appearance_normalizer"), 4.2
        )
        and _finite_number_matches(
            batter_config.get("reference_mean"), 0.738432383380831
        )
        and _finite_number_matches(
            batter_config.get("reference_sd"), 0.9411772120687678
        )
        and _finite_number_matches(batter_config.get("standardized_center"), 1000.0)
        and _finite_number_matches(batter_config.get("standardized_scale"), 250.0)
        and isinstance(config_clip, list)
        and len(config_clip) == 2
        and _finite_number_matches(config_clip[0], -500.0)
        and _finite_number_matches(config_clip[1], 3000.0)
        and _finite_number_matches(batter_config.get("strict_prior_shrinkage_k"), 5.0)
        and _finite_number_matches(batter_config.get("cold_start_center"), 1000.0)
    )
    formula_matches = (
        formula.get("score_id") == "POWER_OBP__RATE100"
        and _numeric_mapping_matches(formula_weights, V11_EXPECTED_FORMULA_WEIGHTS)
        and _finite_number_matches(formula.get("rate_share"), 1.0)
        and _finite_number_matches(
            formula.get("early_mean_raw"), 0.738432383380831
        )
        and _finite_number_matches(
            formula.get("early_sd_raw"), 0.9411772120687678
        )
        and formula.get("history_method") == "S_K5"
        and formula.get("lineup_block") == "MEAN"
        and formula.get("lineup_features") == V11_EXPECTED_LINEUP_FEATURES
        and formula.get("legacy_income_used") is False
    )
    if not hasattr(model, "n_features_in_"):
        raise ValueError("saved V11.1 model does not expose n_features_in_")
    model_feature_count = int(model.n_features_in_)
    model_feature_count_matches = model_feature_count == len(ALL_FEATURES)
    scientific_status = str(decision.get("status", ""))
    prospective_confirmation_required = "prospective" in scientific_status.lower()

    checks = {
        "required_files_present": required_files_present,
        "comparison_models_present": comparison_models_present,
        "comparison_rows_698": comparison_rows_698,
        "comparison_metric_bounds_valid": metric_bounds_valid,
        "bootstrap_clean_reference_present": True,
        "reported_delta_matches": reported_delta_matches,
        "model_schema_matches_14_features": schema_matches,
        "model_schema_excludes_2026_from_training": no_2026_training,
        "batter_config_metadata_matches": config_metadata_matches,
        "selected_formula_metadata_matches": formula_matches,
        "saved_model_loadable": True,
        "saved_model_feature_count_14": model_feature_count_matches,
        "observed_log_loss_lower_than_clean_no_batter": new_loss < clean_loss,
        "observed_log_loss_lower_than_v9_style": new_loss < v9_loss,
        "bootstrap_interval_includes_zero": bootstrap_interval_includes_zero,
        "prospective_confirmation_required": prospective_confirmation_required,
    }
    if not all(checks.values()):
        raise ValueError(f"V11.1 audit failed: {checks}")

    return {
        "status": "PASS",
        "audit_scope": {
            "repository_verified_from_released_artifacts": (
                "comparison and bootstrap summary consistency, frozen metadata, "
                "and saved-model loading"
            ),
            "source_pipeline_recorded_only": (
                "row-level selected-prior lineup checks; the selected-prior table is not "
                "redistributed and cannot be recomputed from the public repository"
            ),
        },
        "checks": checks,
        "source_pipeline_lineup_record": {
            "selected_prior_rows": 33552,
            "expected_rows_from_1864_games_x_2_sides_x_9": 33552,
            "rows_per_game": 18,
            "rows_per_side": 9,
            "player_id_missing": 0,
            "public_repository_recomputation": False,
        },
        "key_results": {
            "n_2025_validation": 698,
            "v11_1_new_batter_log_loss": new_loss,
            "clean_no_batter_log_loss": clean_loss,
            "delta_vs_clean_no_batter": delta_clean,
            "v9_style_log_loss": v9_loss,
            "delta_vs_v9_style": delta_v9,
            "v11_1_auc": new_auc,
            "bootstrap_vs_clean": {
                "new_model": str(bootstrap_clean_row["new_model"]),
                "reference_model": str(bootstrap_clean_row["reference_model"]),
                "delta_log_loss": float(bootstrap_clean_row["delta_log_loss"]),
                "ci_low": bootstrap_ci_low,
                "ci_high": bootstrap_ci_high,
                "interval_includes_zero": bootstrap_interval_includes_zero,
                "improvement_probability": float(
                    bootstrap_clean_row["improvement_probability"]
                ),
                "improvement_probability_definition": (
                    "fraction of paired date-cluster bootstrap replicates with lower "
                    "Log loss; not a posterior probability of model superiority"
                ),
                "reps": int(bootstrap_clean_row["reps"]),
            },
        },
        "scientific_status": scientific_status,
        "reproducibility_note": (
            "The public repository can verify the released comparison and bootstrap summary "
            "artifacts, model schema, frozen metadata, and saved-model loading. The observed "
            "log-loss improvement is not treated as conclusive because the bootstrap interval "
            "includes zero. Row-level lineup construction remains a recorded source-pipeline "
            "result because the required intermediate table is outside the public release."
        ),
        "evidence": {
            "comparison": comparison_path.as_posix(),
            "bootstrap": bootstrap_path.as_posix(),
            "candidate_decision": decision_path.as_posix(),
            "model_schema": model_schema_path.as_posix(),
            "selected_formula": formula_path.as_posix(),
            "batter_config": batter_config_path.as_posix(),
            "saved_model": model_path.as_posix(),
        },
    }
