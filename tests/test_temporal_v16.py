import pandas as pd

from fifteenpick_prediction.temporal import most_recent_training_rows, stable_temporal_sort


def test_stable_temporal_sort_uses_game_id_tie_breaker():
    frame = pd.DataFrame(
        {"game_date": [20250101, 20250101, 20241231], "game_id": ["B", "A", "Z"]}
    )
    out = stable_temporal_sort(frame)
    assert out["game_id"].tolist() == ["Z", "A", "B"]


def test_recent_rows_are_deterministic():
    frame = pd.DataFrame(
        {
            "game_date": [20250101, 20250101, 20250102, 20250103],
            "game_id": ["B", "A", "C", "D"],
        }
    )
    out = most_recent_training_rows(frame, cutoff_date=20250104, n_rows=2)
    assert out["game_id"].tolist() == ["C", "D"]
