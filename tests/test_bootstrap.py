import pandas as pd

from fifteenpick_prediction.bootstrap import paired_date_bootstrap


def test_date_cluster_bootstrap_is_seed_reproducible():
    frame = pd.DataFrame(
        {
            "game_date": [1, 1, 2, 3, 3, 3],
            "home_win": [1, 0, 1, 0, 1, 0],
            "new": [0.7, 0.4, 0.6, 0.3, 0.7, 0.4],
            "ref": [0.5] * 6,
        }
    )
    a = paired_date_bootstrap(
        frame,
        new_probability_col="new",
        reference_probability_col="ref",
        reps=200,
        random_seed=3,
    )
    b = paired_date_bootstrap(
        frame,
        new_probability_col="new",
        reference_probability_col="ref",
        reps=200,
        random_seed=3,
    )
    assert a == b
    assert a["delta_log_loss"] < 0
