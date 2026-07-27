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
    with pytest.raises(ValueError, match="strict-prior"):
        assert_strict_prior(frame)


def test_strict_prior_rejects_future_date() -> None:
    frame = pd.DataFrame(
        {"source_max_date": ["2026-04-03"], "game_date": ["2026-04-02"]}
    )
    with pytest.raises(ValueError, match="strict-prior"):
        assert_strict_prior(frame)


@pytest.mark.parametrize("column", ["source_max_date", "game_date"])
def test_strict_prior_rejects_missing_dates(column: str) -> None:
    frame = pd.DataFrame(
        {"source_max_date": ["2026-04-01"], "game_date": ["2026-04-02"]}
    )
    frame.loc[0, column] = None
    with pytest.raises(ValueError, match=f"{column} contains missing"):
        assert_strict_prior(frame)


def test_strict_prior_rejects_invalid_date() -> None:
    frame = pd.DataFrame(
        {"source_max_date": ["not-a-date"], "game_date": ["2026-04-02"]}
    )
    with pytest.raises(ValueError, match="invalid dates"):
        assert_strict_prior(frame)


def test_recent_training_rows_respects_cutoff() -> None:
    frame = pd.DataFrame(
        {
            "game_date": pd.date_range("2026-01-01", periods=5, freq="D"),
            "game_id": [f"G{i}" for i in range(5)],
            "value": range(5),
        }
    )
    selected = most_recent_training_rows(frame, cutoff_date="2026-01-05", n_rows=2)
    assert selected["value"].tolist() == [2, 3]
