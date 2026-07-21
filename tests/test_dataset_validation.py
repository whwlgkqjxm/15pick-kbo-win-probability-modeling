from pathlib import Path

import pandas as pd

from fifteenpick_prediction.temporal import stable_temporal_sort
from fifteenpick_prediction.validation import validate_modeling_dataset

ROOT = Path(__file__).resolve().parents[1]


def test_frozen_modeling_dataset_contract():
    frame = stable_temporal_sort(pd.read_csv(ROOT / "data/derived/V12_MODELING_DATASET.csv"))
    audit = validate_modeling_dataset(frame)
    assert audit["status"] == "PASS"
    assert audit["rows"] == 1824
    assert audit["rows_by_season"] == {2024: 710, 2025: 698, 2026: 416}
