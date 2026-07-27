from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from fifteenpick_prediction.validation import validate_modeling_dataset

ROOT = Path(__file__).resolve().parents[1]


def load_frame() -> pd.DataFrame:
    return pd.read_csv(ROOT / "data/derived/V12_MODELING_DATASET.csv")


def test_duplicate_game_id_fails() -> None:
    frame = load_frame()
    frame.loc[1, "game_id"] = frame.loc[0, "game_id"]
    with pytest.raises(ValueError, match="duplicate"):
        validate_modeling_dataset(frame)


def test_missing_game_id_fails() -> None:
    frame = load_frame()
    frame.loc[len(frame) - 1, "game_id"] = None
    with pytest.raises(ValueError, match="game_id contains missing"):
        validate_modeling_dataset(frame)


def test_blank_game_id_fails() -> None:
    frame = load_frame()
    frame.loc[len(frame) - 1, "game_id"] = "  "
    with pytest.raises(ValueError, match="game_id contains blank"):
        validate_modeling_dataset(frame)


def test_missing_game_date_fails() -> None:
    frame = load_frame()
    frame.loc[len(frame) - 1, "game_date"] = np.nan
    with pytest.raises(ValueError, match="game_date contains missing"):
        validate_modeling_dataset(frame)


def test_malformed_game_date_fails() -> None:
    frame = load_frame()
    frame.loc[0, "game_date"] = 20240230
    with pytest.raises(ValueError, match="YYYYMMDD"):
        validate_modeling_dataset(frame)


def test_season_date_mismatch_fails() -> None:
    frame = load_frame()
    frame.loc[0, "season"] = 2025
    with pytest.raises(ValueError, match="season does not match"):
        validate_modeling_dataset(frame)


def test_same_date_team_flag_fails() -> None:
    frame = load_frame()
    frame.loc[0, "same_date_team_updates_excluded"] = 0
    with pytest.raises(ValueError, match="same-date team"):
        validate_modeling_dataset(frame)


def test_same_date_player_flag_fails() -> None:
    frame = load_frame()
    frame.loc[0, "same_date_income_results_excluded"] = 0
    with pytest.raises(ValueError, match="same-date player"):
        validate_modeling_dataset(frame)


@pytest.mark.parametrize(
    "column",
    [
        "mean",
        "tie_flag",
        "lineup_confirmed_flag",
        "home_lineup_count",
        "away_lineup_count",
        "home_starter_player_id",
        "away_starter_player_id",
    ],
)
def test_missing_required_column_fails(column: str) -> None:
    frame = load_frame().drop(columns=[column])
    with pytest.raises(ValueError, match="missing required"):
        validate_modeling_dataset(frame)


def test_nonbinary_target_fails() -> None:
    frame = load_frame()
    frame.loc[0, "home_win"] = 2
    with pytest.raises(ValueError, match="binary target"):
        validate_modeling_dataset(frame)


def test_infinite_feature_fails() -> None:
    frame = load_frame()
    frame.loc[0, "elo_diff"] = np.inf
    with pytest.raises(ValueError, match="infinite feature"):
        validate_modeling_dataset(frame)


def test_lineup_count_other_than_nine_fails() -> None:
    frame = load_frame()
    frame.loc[0, "home_lineup_count"] = 8
    with pytest.raises(ValueError, match="uniformly 9"):
        validate_modeling_dataset(frame)


def test_unconfirmed_lineup_fails() -> None:
    frame = load_frame()
    frame.loc[0, "lineup_confirmed_flag"] = 0
    with pytest.raises(ValueError, match="lineup confirmation"):
        validate_modeling_dataset(frame)


def test_missing_starter_id_fails() -> None:
    frame = load_frame()
    frame.loc[0, "home_starter_player_id"] = np.nan
    with pytest.raises(ValueError, match="missing home_starter_player_id"):
        validate_modeling_dataset(frame)


def test_unsorted_dataset_fails() -> None:
    frame = load_frame().iloc[::-1].reset_index(drop=True)
    with pytest.raises(ValueError, match="deterministically sorted"):
        validate_modeling_dataset(frame)
