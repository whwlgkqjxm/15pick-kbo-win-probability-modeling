"""Fail-closed validation for the released modeling dataset."""

from __future__ import annotations

import numpy as np
import pandas as pd

from .schema import (
    ALL_FEATURES,
    BATTER_INDEX_FEATURES,
    CONVENTIONAL_FEATURES,
    STARTER_INDEX_FEATURES,
)
from .temporal import stable_temporal_sort

EXPECTED_ROWS = 1824
EXPECTED_COLUMNS = 71
EXPECTED_ROWS_BY_SEASON = {2024: 710, 2025: 698, 2026: 416}
POST_STARTER_FEATURES = ["PS_R20_RA_G_diff"]
TEAM_STRENGTH_FEATURES = CONVENTIONAL_FEATURES[:5]
PLAYER_UPDATE_FLAG = "same_date_income_results_excluded"


def feature_group_counts() -> dict[str, int]:
    """Return the public analytical grouping of the 14 frozen inputs."""

    return {
        "team_strength": len(TEAM_STRENGTH_FEATURES),
        "post_starter_team": len(POST_STARTER_FEATURES),
        "starting_pitcher_index": len(STARTER_INDEX_FEATURES),
        "batter_lineup_index": len(BATTER_INDEX_FEATURES),
    }


def validate_modeling_dataset(frame: pd.DataFrame) -> dict[str, object]:
    """Validate the frozen modeling table and return computed evidence."""

    required = {
        "season",
        "game_date",
        "game_id",
        "home_win",
        "decision_game",
        "same_date_team_updates_excluded",
        PLAYER_UPDATE_FLAG,
        *ALL_FEATURES,
    }
    missing = required - set(frame.columns)
    if missing:
        raise ValueError(f"missing required columns: {sorted(missing)}")

    if len(frame) != EXPECTED_ROWS:
        raise ValueError(f"row mismatch: {len(frame)} != {EXPECTED_ROWS}")
    if len(frame.columns) != EXPECTED_COLUMNS:
        raise ValueError(f"column mismatch: {len(frame.columns)} != {EXPECTED_COLUMNS}")
    if frame["game_id"].duplicated().any():
        raise ValueError("duplicate game_id")
    if not frame["decision_game"].eq(1).all():
        raise ValueError("non-decision games are present")
    if "tie_flag" in frame.columns and not frame["tie_flag"].eq(0).all():
        raise ValueError("tied games are present in the binary modeling table")

    if frame["home_win"].isna().any():
        raise ValueError("home_win contains missing values")
    target_values = set(frame["home_win"].astype(int).unique().tolist())
    if target_values != {0, 1} or not frame["home_win"].isin([0, 1]).all():
        raise ValueError(f"home_win is not a complete binary target: {sorted(target_values)}")

    if not frame["same_date_team_updates_excluded"].eq(1).all():
        raise ValueError("same-date team-update exclusion failed")
    if not frame[PLAYER_UPDATE_FLAG].eq(1).all():
        raise ValueError("same-date player-result exclusion failed")

    entirely_missing = frame[ALL_FEATURES].columns[frame[ALL_FEATURES].isna().all()].tolist()
    if entirely_missing:
        raise ValueError(f"entirely missing features: {entirely_missing}")

    feature_values = frame[ALL_FEATURES].to_numpy(dtype=float)
    infinite_values = int(np.isinf(feature_values).sum())
    if infinite_values:
        raise ValueError(f"infinite feature values: {infinite_values}")

    counts = {int(k): int(v) for k, v in frame.groupby("season").size().items()}
    if counts != EXPECTED_ROWS_BY_SEASON:
        raise ValueError(f"season row mismatch: {counts}")

    ordered = stable_temporal_sort(frame)
    if ordered["game_id"].tolist() != frame["game_id"].tolist():
        raise ValueError("dataset is not deterministically sorted by game_date, game_id")

    lineup_checks: dict[str, object] = {}
    for side in ("home", "away"):
        lineup_column = f"{side}_lineup_count"
        if lineup_column in frame.columns:
            all_nine = bool(frame[lineup_column].eq(9).all())
            if not all_nine:
                raise ValueError(f"{lineup_column} is not uniformly 9")
            lineup_checks[f"{side}_lineup_count_all_9"] = all_nine

        starter_column = f"{side}_starter_player_id"
        if starter_column in frame.columns:
            missing_starters = int(frame[starter_column].isna().sum())
            if missing_starters:
                raise ValueError(f"missing {starter_column}: {missing_starters}")
            lineup_checks[f"{side}_starter_id_missing"] = missing_starters

    groups = feature_group_counts()
    if sum(groups.values()) != len(ALL_FEATURES):
        raise ValueError(f"feature-group count mismatch: {groups}")

    dates = frame["game_date"].astype(str)
    return {
        "status": "PASS",
        "dataset": {
            "rows": int(len(frame)),
            "columns": int(len(frame.columns)),
            "rows_by_season": {str(k): v for k, v in counts.items()},
            "unique_game_ids": int(frame["game_id"].nunique()),
            "date_min": dates.min(),
            "date_max": dates.max(),
            "decision_games_only": True,
            "ties_present": False,
            "binary_target": True,
            "deterministically_sorted": True,
        },
        "features": {
            "expected_count": len(ALL_FEATURES),
            "present_count": len(ALL_FEATURES),
            "groups": groups,
            "entirely_missing_columns": [],
            "infinite_values": infinite_values,
        },
        "temporal_controls": {
            "same_date_team_updates_excluded": True,
            "same_date_player_results_excluded": True,
        },
        "lineup_and_starter_controls": lineup_checks,
    }
