from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from fifteenpick_prediction.temporal import stable_temporal_sort
from fifteenpick_prediction.validation import validate_modeling_dataset

ROOT = Path(__file__).resolve().parents[1]


def load_frame():
    return stable_temporal_sort(pd.read_csv(ROOT / "data/derived/V12_MODELING_DATASET.csv"))


def test_duplicate_game_id_fails():
    frame = load_frame()
    frame.loc[1, "game_id"] = frame.loc[0, "game_id"]
    with pytest.raises(ValueError, match="duplicate"):
        validate_modeling_dataset(frame)


def test_same_date_flag_fails():
    frame = load_frame()
    frame.loc[0, "same_date_team_updates_excluded"] = 0
    with pytest.raises(ValueError, match="same-date"):
        validate_modeling_dataset(frame)


def test_missing_required_column_fails():
    frame = load_frame().drop(columns=["mean"])
    with pytest.raises(ValueError, match="missing required"):
        validate_modeling_dataset(frame)


def test_nonbinary_target_fails():
    frame = load_frame()
    frame.loc[0, "home_win"] = 2
    with pytest.raises(ValueError, match="binary target"):
        validate_modeling_dataset(frame)


def test_infinite_feature_fails():
    frame = load_frame()
    frame.loc[0, "elo_diff"] = np.inf
    with pytest.raises(ValueError, match="infinite feature"):
        validate_modeling_dataset(frame)


def test_lineup_count_other_than_nine_fails():
    frame = load_frame()
    frame.loc[0, "home_lineup_count"] = 8
    with pytest.raises(ValueError, match="uniformly 9"):
        validate_modeling_dataset(frame)
