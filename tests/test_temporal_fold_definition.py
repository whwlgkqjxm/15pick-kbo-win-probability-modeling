from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data/derived/V12_MODELING_DATASET.csv"
FOLDS = ROOT / "data/derived/V12_TEMPORAL_FOLD_DEFINITION.csv"

EXPECTED_FOLDS = [
    {
        "fold_id": 1,
        "train_start": 20240323,
        "train_end": 20240711,
        "valid_start": 20240712,
        "valid_end": 20240906,
        "n_train": 422,
        "n_valid": 210,
    },
    {
        "fold_id": 2,
        "train_start": 20240323,
        "train_end": 20240906,
        "valid_start": 20240907,
        "valid_end": 20250422,
        "n_train": 632,
        "n_valid": 195,
    },
    {
        "fold_id": 3,
        "train_start": 20240323,
        "train_end": 20250422,
        "valid_start": 20250423,
        "valid_end": 20250619,
        "n_train": 827,
        "n_valid": 232,
    },
    {
        "fold_id": 4,
        "train_start": 20240323,
        "train_end": 20250619,
        "valid_start": 20250620,
        "valid_end": 20250814,
        "n_train": 1059,
        "n_valid": 180,
    },
    {
        "fold_id": 5,
        "train_start": 20240323,
        "train_end": 20250814,
        "valid_start": 20250815,
        "valid_end": 20251002,
        "n_train": 1239,
        "n_valid": 167,
    },
]


def test_frozen_temporal_fold_definition_matches_released_dataset() -> None:
    frame = pd.read_csv(DATA)
    development = frame.loc[frame["season"].isin([2024, 2025])].copy()
    folds = pd.read_csv(FOLDS)

    assert folds.to_dict("records") == EXPECTED_FOLDS
    assert len(development) == 1408

    validation_ids: set[str] = set()
    for fold in folds.itertuples(index=False):
        train = development.loc[
            development["game_date"].between(fold.train_start, fold.train_end)
        ]
        valid = development.loc[
            development["game_date"].between(fold.valid_start, fold.valid_end)
        ]

        assert fold.train_end < fold.valid_start
        assert len(train) == fold.n_train
        assert len(valid) == fold.n_valid
        assert validation_ids.isdisjoint(valid["game_id"])
        validation_ids.update(valid["game_id"])

    assert len(validation_ids) == 984

    first_fold = folds.iloc[0]
    initial_training = development.loc[
        development["game_date"].between(first_fold["train_start"], first_fold["train_end"])
    ]
    assert len(initial_training) == 422

    final_fold = folds.iloc[-1]
    trailing = development.loc[development["game_date"] > final_fold["valid_end"]]
    assert len(trailing) == 2
    assert trailing["game_date"].unique().tolist() == [20251004]

    partitioned_ids = (
        set(initial_training["game_id"]) | validation_ids | set(trailing["game_id"])
    )
    assert partitioned_ids == set(development["game_id"])
