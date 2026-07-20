import pandas as pd
import pytest

from mypick_rq1.temporal import assert_strict_prior, most_recent_training_rows


def test_strict_prior_passes() -> None:
    frame = pd.DataFrame(
        {"source_max_date": ["2026-04-01"], "game_date": ["2026-04-02"]}
    )
    assert_strict_prior(frame)


def test_same_date_is_rejected() -> None:
    frame = pd.DataFrame(
        {"source_max_date": ["2026-04-02"], "game_date": ["2026-04-02"]}
    )
    with pytest.raises(ValueError):
        assert_strict_prior(frame)


def test_recent_window_is_strictly_before_cutoff() -> None:
    frame = pd.DataFrame(
        {"game_date": pd.date_range("2026-01-01", periods=5), "x": range(5)}
    )
    result = most_recent_training_rows(
        frame, cutoff_date="2026-01-05", n_rows=2, date_col="game_date"
    )
    assert result["x"].tolist() == [2, 3]
