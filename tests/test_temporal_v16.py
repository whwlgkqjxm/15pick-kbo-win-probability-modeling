import pandas as pd
import pytest

from fifteenpick_prediction.temporal import most_recent_training_rows, stable_temporal_sort


def test_stable_temporal_sort_uses_game_id_tie_breaker() -> None:
    frame = pd.DataFrame(
        {"game_date": [20250101, 20250101, 20241231], "game_id": ["B", "A", "Z"]}
    )
    out = stable_temporal_sort(frame)
    assert out["game_id"].tolist() == ["Z", "A", "B"]


def test_stable_temporal_sort_is_input_order_invariant() -> None:
    frame = pd.DataFrame(
        {
            "game_date": [20250102, 20250101, 20250101, 20250103],
            "game_id": ["C", "B", "A", "D"],
        }
    )
    expected = stable_temporal_sort(frame)["game_id"].tolist()
    shuffled = frame.sample(frac=1.0, random_state=7).reset_index(drop=True)
    assert stable_temporal_sort(shuffled)["game_id"].tolist() == expected


@pytest.mark.parametrize("missing_column", ["game_date", "game_id"])
def test_stable_temporal_sort_requires_both_keys(missing_column: str) -> None:
    frame = pd.DataFrame({"game_date": [20250101], "game_id": ["A"]}).drop(
        columns=[missing_column]
    )
    with pytest.raises(KeyError, match=missing_column):
        stable_temporal_sort(frame)


def test_stable_temporal_sort_rejects_missing_game_id() -> None:
    frame = pd.DataFrame({"game_date": [20250101], "game_id": [None]})
    with pytest.raises(ValueError, match="game_id contains missing"):
        stable_temporal_sort(frame)


def test_stable_temporal_sort_rejects_blank_game_id() -> None:
    frame = pd.DataFrame({"game_date": [20250101], "game_id": ["  "]})
    with pytest.raises(ValueError, match="game_id contains blank"):
        stable_temporal_sort(frame)


def test_stable_temporal_sort_rejects_duplicate_game_id() -> None:
    frame = pd.DataFrame(
        {"game_date": [20250101, 20250102], "game_id": ["A", "A"]}
    )
    with pytest.raises(ValueError, match="duplicate game_id"):
        stable_temporal_sort(frame)


def test_stable_temporal_sort_rejects_missing_game_date() -> None:
    frame = pd.DataFrame({"game_date": [None], "game_id": ["A"]})
    with pytest.raises(ValueError, match="game_date contains missing"):
        stable_temporal_sort(frame)


def test_recent_rows_are_deterministic() -> None:
    frame = pd.DataFrame(
        {
            "game_date": [20250101, 20250101, 20250102, 20250103],
            "game_id": ["B", "A", "C", "D"],
        }
    )
    out = most_recent_training_rows(frame, cutoff_date=20250104, n_rows=2)
    assert out["game_id"].tolist() == ["C", "D"]


@pytest.mark.parametrize("n_rows", [True, 0, -1, 1.5, "2"])
def test_recent_rows_requires_positive_integer(n_rows: object) -> None:
    frame = pd.DataFrame({"game_date": [20250101], "game_id": ["A"]})
    with pytest.raises(ValueError, match="positive integer"):
        most_recent_training_rows(
            frame, cutoff_date=20250102, n_rows=n_rows  # type: ignore[arg-type]
        )


def test_recent_rows_rejects_invalid_cutoff() -> None:
    frame = pd.DataFrame({"game_date": [20250101], "game_id": ["A"]})
    with pytest.raises(ValueError, match="cutoff_date"):
        most_recent_training_rows(frame, cutoff_date="not-a-date", n_rows=1)
