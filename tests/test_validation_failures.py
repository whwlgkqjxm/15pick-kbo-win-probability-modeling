from pathlib import Path

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
