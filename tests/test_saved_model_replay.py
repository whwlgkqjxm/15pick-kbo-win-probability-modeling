from pathlib import Path

import joblib
import numpy as np
import pandas as pd

from fifteenpick_prediction.schema import ALL_FEATURES
from fifteenpick_prediction.temporal import stable_temporal_sort

ROOT = Path(__file__).resolve().parents[1]


def test_saved_models_replay_frozen_predictions():
    frame = stable_temporal_sort(pd.read_csv(ROOT / "data/derived/V12_MODELING_DATASET.csv"))
    test = frame[frame["season"].eq(2026)]
    pred = pd.read_csv(ROOT / "reports/frozen/V12_2026_ALL_PREDICTIONS.csv")
    cv = joblib.load(ROOT / "models/frozen/V12_CV_SELECTED_MODEL_REFIT_2024_2025.joblib")
    dev = joblib.load(ROOT / "models/frozen/V12_2026_BEST_OBSERVED_RECENT720_MODEL.joblib")
    assert np.max(
        np.abs(cv.predict_proba(test[ALL_FEATURES])[:, 1] - pred["p__L2_C0.03__ALL_EQUAL"])
    ) < 1e-12
    assert np.max(
        np.abs(dev.predict_proba(test[ALL_FEATURES])[:, 1] - pred["p__L2_C0.1__RECENT_720"])
    ) < 1e-12
