from pathlib import Path

import pandas as pd

from fifteenpick_prediction.temporal import stable_temporal_sort
from fifteenpick_prediction.validation import validate_modeling_dataset

ROOT = Path(__file__).resolve().parents[1]


def test_frozen_modeling_dataset_contract():
    frame = stable_temporal_sort(pd.read_csv(ROOT / "data/derived/V12_MODELING_DATASET.csv"))
    audit = validate_modeling_dataset(frame)
    assert audit["status"] == "PASS"
    assert audit["dataset"]["rows"] == 1824
    assert audit["dataset"]["columns"] == 71
    assert audit["dataset"]["rows_by_season"] == {"2024": 710, "2025": 698, "2026": 416}
    assert audit["dataset"]["unique_game_ids"] == 1824
    assert audit["dataset"]["binary_target"] is True
    assert audit["features"]["expected_count"] == 14
    assert audit["features"]["groups"] == {
        "team_strength": 5,
        "post_starter_team": 1,
        "starting_pitcher_index": 4,
        "batter_lineup_index": 4,
    }
    assert audit["features"]["infinite_values"] == 0
    assert audit["lineup_and_starter_controls"]["home_lineup_count_all_9"] is True
    assert audit["lineup_and_starter_controls"]["away_lineup_count_all_9"] is True
