import pandas as pd
import pytest

from fifteenpick_prediction.temporal import assert_strict_prior, most_recent_training_rows


def test_strict_prior_accepts_earlier_dates() -> None:
    frame = pd.DataFrame(
        {
            "source_max_date": ["2026-04-01", "2026-04-02"],
            "game_date": ["2026-04-02", "2026-04-03"],
        }
    )
    assert_strict_prior(frame)


def test_strict_prior_rejects_same_date() -> None:
    frame = pd.DataFrame(
        {"source_max_date": ["2026-04-02"], "game_date": ["2026-04-02"]}
    )
    with pytest.raises(ValueError):
        assert_strict_prior(frame)


def test_recent_training_rows_respects_cutoff() -> None:
    frame = pd.DataFrame(
        {
            "game_date": pd.date_range("2026-01-01", periods=5, freq="D"),
            "value": range(5),
        }
    )
    selected = most_recent_training_rows(frame, cutoff_date="2026-01-05", n_rows=2)
    assert selected["value"].tolist() == [2, 3]
