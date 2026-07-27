"""Cross-platform verification helpers for regenerated research outputs."""

from __future__ import annotations

import json
from numbers import Real
from pathlib import Path

import numpy as np
import pandas as pd
from pandas.api.types import is_numeric_dtype

REPRODUCED_CSV_FILES = (
    "calibration_deciles.csv",
    "calibration_intercept_slope.csv",
    "player_index_ablation.csv",
    "player_index_ablation_bootstrap.csv",
    "player_index_ablation_predictions.csv",
    "standardized_coefficients.csv",
)
REPRODUCED_JSON_FILES = ("dataset_validation.json",)
REPRODUCED_FILES = frozenset(REPRODUCED_CSV_FILES + REPRODUCED_JSON_FILES)


def _directory_entry_names(directory: Path) -> set[str]:
    return {path.name for path in directory.iterdir()}


def _require_expected_files(directory: Path, *, label: str) -> None:
    if not directory.is_dir():
        raise ValueError(f"{label} directory does not exist: {directory}")

    actual = _directory_entry_names(directory)
    missing = sorted(REPRODUCED_FILES - actual)
    unexpected = sorted(actual - REPRODUCED_FILES)
    if missing or unexpected:
        raise ValueError(
            f"{label} file set mismatch: missing={missing}, unexpected={unexpected}"
        )


def _compare_text_columns(
    generated: pd.Series,
    committed: pd.Series,
    *,
    file_name: str,
    column: str,
) -> None:
    generated_text = generated.astype("string")
    committed_text = committed.astype("string")
    equal = generated_text.eq(committed_text) | (
        generated_text.isna() & committed_text.isna()
    )
    if not bool(equal.all()):
        first = int(np.flatnonzero(~equal.to_numpy())[0])
        raise ValueError(
            f"{file_name} text mismatch at row {first}, column {column}: "
            f"generated={generated.iloc[first]!r}, committed={committed.iloc[first]!r}"
        )


def _compare_numeric_columns(
    generated: pd.Series,
    committed: pd.Series,
    *,
    file_name: str,
    column: str,
    absolute_tolerance: float,
) -> None:
    generated_values = generated.to_numpy(dtype=float)
    committed_values = committed.to_numpy(dtype=float)
    equal = np.isclose(
        generated_values,
        committed_values,
        rtol=0.0,
        atol=absolute_tolerance,
        equal_nan=True,
    )
    if not bool(equal.all()):
        first = int(np.flatnonzero(~equal)[0])
        difference = abs(generated_values[first] - committed_values[first])
        raise ValueError(
            f"{file_name} numeric mismatch at row {first}, column {column}: "
            f"generated={generated_values[first]!r}, "
            f"committed={committed_values[first]!r}, "
            f"absolute_difference={difference!r}, "
            f"tolerance={absolute_tolerance!r}"
        )


def compare_reproduced_csv(
    generated_path: Path,
    committed_path: Path,
    *,
    absolute_tolerance: float = 1e-12,
) -> None:
    """Compare one regenerated CSV by structure, row order, text, and numeric tolerance."""
    if isinstance(absolute_tolerance, bool) or not isinstance(absolute_tolerance, Real):
        raise TypeError("absolute_tolerance must be a real number")
    absolute_tolerance = float(absolute_tolerance)
    if absolute_tolerance < 0 or not np.isfinite(absolute_tolerance):
        raise ValueError("absolute_tolerance must be finite and non-negative")

    generated = pd.read_csv(generated_path)
    committed = pd.read_csv(committed_path)

    if list(generated.columns) != list(committed.columns):
        raise ValueError(
            f"{generated_path.name} column mismatch: "
            f"generated={list(generated.columns)}, committed={list(committed.columns)}"
        )
    if generated.shape != committed.shape:
        raise ValueError(
            f"{generated_path.name} shape mismatch: "
            f"generated={generated.shape}, committed={committed.shape}"
        )

    for column in generated.columns:
        generated_numeric = is_numeric_dtype(generated[column])
        committed_numeric = is_numeric_dtype(committed[column])
        if generated_numeric != committed_numeric:
            raise ValueError(
                f"{generated_path.name} dtype-class mismatch in {column}: "
                f"generated={generated[column].dtype}, committed={committed[column].dtype}"
            )
        if generated_numeric:
            _compare_numeric_columns(
                generated[column],
                committed[column],
                file_name=generated_path.name,
                column=column,
                absolute_tolerance=absolute_tolerance,
            )
        else:
            _compare_text_columns(
                generated[column],
                committed[column],
                file_name=generated_path.name,
                column=column,
            )


def compare_reproduced_outputs(
    generated_directory: Path,
    committed_directory: Path,
    *,
    absolute_tolerance: float = 1e-12,
) -> dict[str, int | float]:
    """Verify all portable regenerated outputs without requiring byte-identical floats."""
    generated_directory = Path(generated_directory)
    committed_directory = Path(committed_directory)
    _require_expected_files(generated_directory, label="generated")
    _require_expected_files(committed_directory, label="committed")

    for file_name in REPRODUCED_CSV_FILES:
        compare_reproduced_csv(
            generated_directory / file_name,
            committed_directory / file_name,
            absolute_tolerance=absolute_tolerance,
        )

    for file_name in REPRODUCED_JSON_FILES:
        generated = json.loads(
            (generated_directory / file_name).read_text(encoding="utf-8")
        )
        committed = json.loads(
            (committed_directory / file_name).read_text(encoding="utf-8")
        )
        if generated != committed:
            raise ValueError(f"{file_name} JSON payload mismatch")

    return {
        "files_verified": len(REPRODUCED_FILES),
        "csv_files_verified": len(REPRODUCED_CSV_FILES),
        "json_files_verified": len(REPRODUCED_JSON_FILES),
        "numeric_absolute_tolerance": absolute_tolerance,
    }
