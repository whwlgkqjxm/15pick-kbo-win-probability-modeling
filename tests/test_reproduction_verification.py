from __future__ import annotations

import shutil
from pathlib import Path

import pandas as pd
import pytest

from fifteenpick_prediction.reproduction import compare_reproduced_outputs

ROOT = Path(__file__).resolve().parents[1]
COMMITTED = ROOT / "reports" / "reproduced"


def copied_outputs(tmp_path: Path) -> Path:
    target = tmp_path / "generated"
    shutil.copytree(COMMITTED, target)
    return target


def test_reproduced_outputs_match_the_committed_portable_results(tmp_path: Path):
    generated = copied_outputs(tmp_path)

    result = compare_reproduced_outputs(generated, COMMITTED)

    assert result == {
        "files_verified": 7,
        "csv_files_verified": 6,
        "json_files_verified": 1,
        "numeric_absolute_tolerance": 1e-12,
    }


def test_reproduced_outputs_accept_last_digit_numeric_drift(tmp_path: Path):
    generated = copied_outputs(tmp_path)
    path = generated / "calibration_deciles.csv"
    frame = pd.read_csv(path)
    frame.loc[0, "predicted_mean"] += 5e-13
    frame.to_csv(path, index=False)

    compare_reproduced_outputs(generated, COMMITTED, absolute_tolerance=1e-12)


def test_reproduced_outputs_reject_numeric_drift_above_tolerance(tmp_path: Path):
    generated = copied_outputs(tmp_path)
    path = generated / "calibration_deciles.csv"
    frame = pd.read_csv(path)
    frame.loc[0, "predicted_mean"] += 2e-12
    frame.to_csv(path, index=False)

    with pytest.raises(ValueError, match="numeric mismatch"):
        compare_reproduced_outputs(generated, COMMITTED, absolute_tolerance=1e-12)


def test_reproduced_outputs_reject_identifier_or_row_order_changes(tmp_path: Path):
    generated = copied_outputs(tmp_path)
    path = generated / "player_index_ablation_predictions.csv"
    frame = pd.read_csv(path)
    frame.loc[0, "game_id"] = "CHANGED_GAME_ID"
    frame.to_csv(path, index=False)

    with pytest.raises(ValueError, match="text mismatch"):
        compare_reproduced_outputs(generated, COMMITTED)


def test_reproduced_outputs_reject_missing_or_unexpected_files(tmp_path: Path):
    generated = copied_outputs(tmp_path)
    (generated / "calibration_deciles.csv").unlink()
    (generated / "unexpected.csv").write_text("value\n1\n", encoding="utf-8")

    with pytest.raises(ValueError, match="file set mismatch"):
        compare_reproduced_outputs(generated, COMMITTED)


def test_reproduced_outputs_reject_missing_directory(tmp_path: Path):
    with pytest.raises(ValueError, match="directory does not exist"):
        compare_reproduced_outputs(tmp_path / "missing", COMMITTED)


def test_reproduced_outputs_reject_column_changes(tmp_path: Path):
    generated = copied_outputs(tmp_path)
    path = generated / "calibration_intercept_slope.csv"
    frame = pd.read_csv(path).rename(
        columns={"calibration_slope": "changed_column"}
    )
    frame.to_csv(path, index=False)

    with pytest.raises(ValueError, match="column mismatch"):
        compare_reproduced_outputs(generated, COMMITTED)


def test_reproduced_outputs_reject_shape_changes(tmp_path: Path):
    generated = copied_outputs(tmp_path)
    path = generated / "calibration_intercept_slope.csv"
    frame = pd.read_csv(path).iloc[:-1]
    frame.to_csv(path, index=False)

    with pytest.raises(ValueError, match="shape mismatch"):
        compare_reproduced_outputs(generated, COMMITTED)


def test_reproduced_outputs_reject_dtype_class_changes(tmp_path: Path):
    generated = copied_outputs(tmp_path)
    path = generated / "calibration_intercept_slope.csv"
    frame = pd.read_csv(path)
    frame["calibration_slope"] = frame["calibration_slope"].astype(object)
    frame.loc[0, "calibration_slope"] = "not_numeric"
    frame.to_csv(path, index=False)

    with pytest.raises(ValueError, match="dtype-class mismatch"):
        compare_reproduced_outputs(generated, COMMITTED)


def test_reproduced_outputs_reject_json_changes(tmp_path: Path):
    generated = copied_outputs(tmp_path)
    path = generated / "dataset_validation.json"
    path.write_text('{"status": "CHANGED"}\n', encoding="utf-8")

    with pytest.raises(ValueError, match="JSON payload mismatch"):
        compare_reproduced_outputs(generated, COMMITTED)


@pytest.mark.parametrize("value", [True, "1e-12"])
def test_reproduced_csv_rejects_non_numeric_tolerance(tmp_path: Path, value):
    generated = copied_outputs(tmp_path)

    with pytest.raises(TypeError, match="real number"):
        compare_reproduced_outputs(
            generated,
            COMMITTED,
            absolute_tolerance=value,
        )


@pytest.mark.parametrize("value", [-1.0, float("inf"), float("nan")])
def test_reproduced_csv_rejects_invalid_numeric_tolerance(tmp_path: Path, value):
    generated = copied_outputs(tmp_path)

    with pytest.raises(ValueError, match="finite and non-negative"):
        compare_reproduced_outputs(
            generated,
            COMMITTED,
            absolute_tolerance=value,
        )
