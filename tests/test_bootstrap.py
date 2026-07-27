import numpy as np
import pandas as pd
import pytest

from fifteenpick_prediction.bootstrap import binary_log_loss_rows, paired_date_bootstrap


def sample_frame() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "game_date": [1, 1, 2, 3, 3, 3],
            "home_win": [1, 0, 1, 0, 1, 0],
            "new": [0.7, 0.4, 0.6, 0.3, 0.7, 0.4],
            "ref": [0.5] * 6,
        }
    )


def test_date_cluster_bootstrap_is_seed_reproducible():
    frame = sample_frame()
    first = paired_date_bootstrap(
        frame,
        new_probability_col="new",
        reference_probability_col="ref",
        reps=200,
        random_seed=3,
    )
    second = paired_date_bootstrap(
        frame,
        new_probability_col="new",
        reference_probability_col="ref",
        reps=200,
        random_seed=3,
    )

    assert first == second
    assert first["delta_log_loss"] < 0


def test_identical_predictions_produce_zero_paired_difference():
    frame = sample_frame().assign(new=lambda data: data["ref"])
    result = paired_date_bootstrap(
        frame,
        new_probability_col="new",
        reference_probability_col="ref",
        reps=100,
        random_seed=9,
    )

    assert result["delta_log_loss"] == pytest.approx(0.0)
    assert result["ci_low"] == pytest.approx(0.0)
    assert result["ci_high"] == pytest.approx(0.0)
    assert result["improvement_probability"] == pytest.approx(0.0)


@pytest.mark.parametrize(
    "targets",
    [
        np.array([0, 2]),
        np.array([0.2, 1.0]),
        np.array([0, np.nan]),
    ],
)
def test_binary_log_loss_rejects_nonbinary_targets(targets: np.ndarray):
    with pytest.raises(ValueError, match="binary values"):
        binary_log_loss_rows(targets, np.array([0.4, 0.6]))


@pytest.mark.parametrize(
    "probabilities, message",
    [
        (np.array([-0.1, 0.5]), "closed interval"),
        (np.array([1.1, 0.5]), "closed interval"),
        (np.array([np.nan, 0.5]), "finite"),
        (np.array([np.inf, 0.5]), "finite"),
    ],
)
def test_binary_log_loss_rejects_invalid_probabilities(
    probabilities: np.ndarray,
    message: str,
):
    with pytest.raises(ValueError, match=message):
        binary_log_loss_rows(np.array([0, 1]), probabilities)


def test_binary_log_loss_rejects_shape_mismatch_and_non_vector_inputs():
    with pytest.raises(ValueError, match="same shape"):
        binary_log_loss_rows(np.array([0, 1]), np.array([0.5]))

    with pytest.raises(ValueError, match="one-dimensional"):
        binary_log_loss_rows(np.array([[0, 1]]), np.array([[0.4, 0.6]]))


def test_binary_log_loss_accepts_boundary_probabilities_safely():
    losses = binary_log_loss_rows(np.array([0, 1]), np.array([0.0, 1.0]))

    assert np.isfinite(losses).all()
    assert (losses > 0).all()


def test_bootstrap_rejects_missing_columns_and_invalid_repetitions():
    frame = sample_frame()

    with pytest.raises(KeyError, match="missing columns"):
        paired_date_bootstrap(
            frame.drop(columns="new"),
            new_probability_col="new",
            reference_probability_col="ref",
        )

    for invalid_reps in (0, -1, 1.5, True):
        with pytest.raises(ValueError, match="positive integer"):
            paired_date_bootstrap(
                frame,
                new_probability_col="new",
                reference_probability_col="ref",
                reps=invalid_reps,
            )


def test_bootstrap_rejects_empty_frames_and_missing_dates():
    frame = sample_frame()

    with pytest.raises(ValueError, match="at least one row"):
        paired_date_bootstrap(
            frame.iloc[0:0],
            new_probability_col="new",
            reference_probability_col="ref",
        )

    frame.loc[0, "game_date"] = np.nan
    with pytest.raises(ValueError, match="must not contain missing values"):
        paired_date_bootstrap(
            frame,
            new_probability_col="new",
            reference_probability_col="ref",
        )


def test_bootstrap_result_is_invariant_to_row_order():
    frame = sample_frame()
    shuffled = frame.sample(frac=1.0, random_state=17).reset_index(drop=True)

    original = paired_date_bootstrap(
        frame,
        new_probability_col="new",
        reference_probability_col="ref",
        reps=300,
        random_seed=13,
    )
    reordered = paired_date_bootstrap(
        shuffled,
        new_probability_col="new",
        reference_probability_col="ref",
        reps=300,
        random_seed=13,
    )

    for key in ("delta_log_loss", "ci_low", "ci_high", "improvement_probability"):
        assert original[key] == pytest.approx(reordered[key])


def test_point_estimate_preserves_game_level_weighting_across_dates():
    frame = pd.DataFrame(
        {
            "game_date": [1, 2, 2, 2],
            "home_win": [1, 0, 0, 0],
            "new": [0.9, 0.6, 0.6, 0.6],
            "ref": [0.5, 0.5, 0.5, 0.5],
        }
    )
    result = paired_date_bootstrap(
        frame,
        new_probability_col="new",
        reference_probability_col="ref",
        reps=100,
        random_seed=4,
    )

    row_deltas = binary_log_loss_rows(
        frame["home_win"].to_numpy(), frame["new"].to_numpy()
    ) - binary_log_loss_rows(frame["home_win"].to_numpy(), frame["ref"].to_numpy())
    equal_date_weighted = frame.assign(delta=row_deltas).groupby("game_date")["delta"].mean().mean()

    assert result["delta_log_loss"] == pytest.approx(row_deltas.mean())
    assert result["delta_log_loss"] != pytest.approx(equal_date_weighted)


def test_bootstrap_rejects_non_dataframe_input() -> None:
    with pytest.raises(TypeError, match="pandas DataFrame"):
        paired_date_bootstrap(  # type: ignore[arg-type]
            [],
            new_probability_col="new",
            reference_probability_col="ref",
        )


def test_bootstrap_rejects_duplicate_column_names() -> None:
    frame = sample_frame()
    frame.columns = ["game_date", "home_win", "new", "new"]

    with pytest.raises(ValueError, match="column names must be unique"):
        paired_date_bootstrap(
            frame,
            new_probability_col="new",
            reference_probability_col="ref",
        )


def test_bootstrap_rejects_invalid_rng_type() -> None:
    with pytest.raises(TypeError, match="numpy.random.Generator"):
        paired_date_bootstrap(
            sample_frame(),
            new_probability_col="new",
            reference_probability_col="ref",
            rng=np.random.RandomState(7),  # type: ignore[arg-type]
        )
