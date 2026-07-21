"""Fail-closed validations for the derived modeling dataset."""

from __future__ import annotations

import pandas as pd

from .schema import ALL_FEATURES
from .temporal import stable_temporal_sort

EXPECTED_ROWS_BY_SEASON = {2024: 710, 2025: 698, 2026: 416}


def validate_modeling_dataset(frame: pd.DataFrame) -> dict[str, object]:
    required = {
        "season",
        "game_date",
        "game_id",
        "home_win",
        "decision_game",
        "same_date_team_updates_excluded",
        "same_date_income_results_excluded",
        *ALL_FEATURES,
    }
    missing = required - set(frame.columns)
    if missing:
        raise ValueError(f"missing required columns: {sorted(missing)}")
    if frame["game_id"].duplicated().any():
        raise ValueError("duplicate game_id")
    if not frame["decision_game"].eq(1).all():
        raise ValueError("non-decision games are present")
    if not frame["same_date_team_updates_excluded"].eq(1).all():
        raise ValueError("same-date team update exclusion failed")
    if not frame["same_date_income_results_excluded"].eq(1).all():
        raise ValueError("same-date income exclusion failed")
    if frame[ALL_FEATURES].isna().all(axis=0).any():
        bad = frame[ALL_FEATURES].isna().all(axis=0)
        raise ValueError(f"entirely missing features: {bad[bad].index.tolist()}")
    counts = {int(k): int(v) for k, v in frame.groupby("season").size().items()}
    if counts != EXPECTED_ROWS_BY_SEASON:
        raise ValueError(f"season row mismatch: {counts}")
    ordered = stable_temporal_sort(frame)
    if not ordered["game_id"].tolist() == frame["game_id"].tolist():
        raise ValueError("dataset is not deterministically sorted by game_date, game_id")
    return {
        "status": "PASS",
        "rows": int(len(frame)),
        "rows_by_season": counts,
        "unique_game_ids": int(frame["game_id"].nunique()),
        "feature_count": len(ALL_FEATURES),
        "same_date_exclusion": True,
    }
