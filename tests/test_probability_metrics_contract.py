import pytest

from fifteenpick_prediction.metrics import probability_metrics


def test_probability_metrics_complete():
    out = probability_metrics([0, 0, 1, 1], [0.1, 0.4, 0.6, 0.9])
    assert out["n"] == 4
    assert out["log_loss"] < 0.6
    assert out["roc_auc"] == 1.0
    assert out["accuracy"] == 1.0


def test_probability_metrics_single_class_raises():
    with pytest.raises(ValueError):
        probability_metrics([1, 1], [0.7, 0.8])
