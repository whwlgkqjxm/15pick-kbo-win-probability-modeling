import math

from mypick_rq1.indices import batter_game_income, shrunk_prior_mean, starter_game_income


def test_batter_index_is_finite() -> None:
    value = batter_game_income(
        at_bats=4,
        singles=1,
        doubles=1,
        triples=0,
        home_runs=0,
        walks=1,
        hit_by_pitch=0,
        stolen_bases=1,
        strikeouts=1,
        double_plays=0,
    )
    assert math.isfinite(value)


def test_batter_zero_pa_uses_zero_rate_then_standardizes() -> None:
    value = batter_game_income(
        at_bats=0,
        singles=0,
        doubles=0,
        triples=0,
        home_runs=0,
        walks=0,
        hit_by_pitch=0,
        stolen_bases=0,
        strikeouts=0,
        double_plays=0,
    )
    expected = 1000.0 + 250.0 * ((0.0 - 0.738432383380831) / 0.9411772120687678)
    assert math.isclose(value, expected, rel_tol=0, abs_tol=1e-12)


def test_starter_more_outs_improves_index() -> None:
    low = starter_game_income(
        outs_recorded=12,
        strikeouts=3,
        home_runs_allowed=1,
        walks_allowed=2,
        hit_by_pitch_allowed=0,
    )
    high = starter_game_income(
        outs_recorded=18,
        strikeouts=3,
        home_runs_allowed=1,
        walks_allowed=2,
        hit_by_pitch_allowed=0,
    )
    assert high > low


def test_shrunk_prior_mean() -> None:
    assert shrunk_prior_mean(prior_sum=2400, prior_count=2, center=1000, k=5) == 7400 / 7
