"""Temporal ordering, split, and leakage-control helpers."""

from __future__ import annotations

from numbers import Integral
from typing import Any

import pandas as pd


def _require_dataframe(frame: pd.DataFrame) -> None:
    if not isinstance(frame, pd.DataFrame):
        raise TypeError("frame must be a pandas DataFrame")
    if frame.columns.duplicated().any():
        duplicates = frame.columns[frame.columns.duplicated()].tolist()
        raise ValueError(f"duplicate column names: {duplicates}")


def _parse_date_series(frame: pd.DataFrame, column: str) -> pd.Series:
    if column not in frame.columns:
        raise KeyError(f"missing column: {column}")

    values = frame[column]
    if values.isna().any():
        raise ValueError(f"{column} contains missing values")

    text = values.astype(str).str.strip()
    if text.eq("").any():
        raise ValueError(f"{column} contains blank values")

    parsed = pd.to_datetime(text, format="mixed", errors="coerce")
    if parsed.isna().any():
        invalid = text.loc[parsed.isna()].drop_duplicates().head(5).tolist()
        raise ValueError(f"{column} contains invalid dates: {invalid}")
    return parsed


def _parse_date_value(value: Any, *, label: str) -> pd.Timestamp:
    if value is None or (not isinstance(value, (list, tuple, dict, set)) and pd.isna(value)):
        raise ValueError(f"{label} must be a valid date")

    text = str(value).strip()
    if not text:
        raise ValueError(f"{label} must be a valid date")

    parsed = pd.to_datetime(text, format="mixed", errors="coerce")
    if pd.isna(parsed):
        raise ValueError(f"{label} must be a valid date: {value!r}")
    return parsed


def _validated_identifier_text(frame: pd.DataFrame, column: str) -> pd.Series:
    if column not in frame.columns:
        raise KeyError(f"missing column: {column}")

    values = frame[column]
    if values.isna().any():
        raise ValueError(f"{column} contains missing values")

    text = values.astype(str).str.strip()
    if text.eq("").any():
        raise ValueError(f"{column} contains blank values")
    if text.duplicated().any():
        raise ValueError(f"duplicate {column}")
    return text


def stable_temporal_sort(
    frame: pd.DataFrame, *, date_col: str = "game_date", id_col: str = "game_id"
) -> pd.DataFrame:
    """Return a deterministic chronological order using valid dates and unique game IDs."""

    _require_dataframe(frame)
    date_key = _parse_date_series(frame, date_col)
    id_key = _validated_identifier_text(frame, id_col)

    order = pd.DataFrame(
        {"_date_key": date_key, "_id_key": id_key},
        index=frame.index,
    ).sort_values(["_date_key", "_id_key"], kind="mergesort")
    return frame.loc[order.index].reset_index(drop=True)


def assert_strict_prior(
    frame: pd.DataFrame,
    *,
    source_date_col: str = "source_max_date",
    target_date_col: str = "game_date",
) -> None:
    """Fail when any feature source date is missing, invalid, or not strictly prior."""

    _require_dataframe(frame)
    source = _parse_date_series(frame, source_date_col)
    target = _parse_date_series(frame, target_date_col)
    bad = frame.loc[source >= target]
    if not bad.empty:
        raise ValueError(f"strict-prior violation in {len(bad)} rows")


def most_recent_training_rows(
    frame: pd.DataFrame,
    *,
    cutoff_date: int | str,
    n_rows: int,
    date_col: str = "game_date",
    id_col: str = "game_id",
) -> pd.DataFrame:
    """Select the last N unique decision games strictly before a valid cutoff date."""

    if isinstance(n_rows, bool) or not isinstance(n_rows, Integral) or n_rows <= 0:
        raise ValueError("n_rows must be a positive integer")

    ordered = stable_temporal_sort(frame, date_col=date_col, id_col=id_col)
    cutoff = _parse_date_value(cutoff_date, label="cutoff_date")
    dates = _parse_date_series(ordered, date_col)
    eligible = ordered.loc[dates < cutoff]
    if len(eligible) < int(n_rows):
        raise ValueError(f"requested {n_rows} rows but found {len(eligible)}")
    return eligible.tail(int(n_rows)).copy()
