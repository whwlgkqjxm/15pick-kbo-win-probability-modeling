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


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


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
    model_path: Path,
) -> dict[str, Any]:
    """Verify the V11.1 artifacts that can be checked from the public repository."""

    required_paths = [
        comparison_path,
        bootstrap_path,
        decision_path,
        model_schema_path,
        formula_path,
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
    formula_matches = (
        formula.get("score_id") == "POWER_OBP__RATE100"
        and formula.get("history_method") == "S_K5"
        and formula.get("lineup_block") == "MEAN"
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
            "saved_model": model_path.as_posix(),
        },
    }
