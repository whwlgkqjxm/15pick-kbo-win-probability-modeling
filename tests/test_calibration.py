import numpy as np

from fifteenpick_prediction.calibration import calibration_intercept_slope, calibration_table, logit


def test_logit_and_calibration_outputs():
    p = np.array([0.1, 0.2, 0.7, 0.8, 0.9, 0.4, 0.6, 0.3])
    y = np.array([0, 0, 1, 1, 1, 0, 1, 0])
    z = logit(p)
    assert np.isfinite(z).all()
    summary = calibration_intercept_slope(y, p)
    assert set(summary) == {"calibration_intercept", "calibration_slope"}
    table = calibration_table(y, p, bins=4)
    assert table["n"].sum() == len(y)
    assert (table["abs_gap"] >= 0).all()
