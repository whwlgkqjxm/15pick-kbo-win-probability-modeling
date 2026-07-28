import json
import math
from pathlib import Path

import numpy as np
import pytest

from fifteenpick_prediction.indices import (
    DEFAULT_BATTER_INDEX_CONFIG,
    BatterIndexConfig,
    batter_game_performance_index,
    starter_game_performance_index,
    strict_prior_shrunk_mean,
)

ROOT = Path(__file__).resolve().parents[1]
BATTER_CONFIG_PATH = ROOT / "configs/batter_index.json"
STARTER_CONFIG_PATH = ROOT / "configs/starter_index.json"


def _read_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def test_default_batter_scaling_matches_frozen_config() -> None:
    config = _read_json(BATTER_CONFIG_PATH)

    assert DEFAULT_BATTER_INDEX_CONFIG == BatterIndexConfig(
        plate_appearance_normalizer=float(config["plate_appearance_normalizer"]),
        reference_mean=float(config["reference_mean"]),
        reference_sd=float(config["reference_sd"]),
        center=float(config["standardized_center"]),
        scale=float(config["standardized_scale"]),
        lower_clip=float(config["clip"][0]),  # type: ignore[index]
        upper_clip=float(config["clip"][1]),  # type: ignore[index]
    )


def test_batter_implementation_matches_frozen_config() -> None:
    config = _read_json(BATTER_CONFIG_PATH)
    weights = config["weights"]
    assert isinstance(weights, dict)

    stats = {
        "at_bats": 5.0,
        "singles": 2.0,
        "doubles": 1.0,
        "triples": 0.0,
        "home_runs": 1.0,
        "walks": 1.0,
        "hit_by_pitch": 0.0,
        "stolen_bases": 1.0,
        "strikeouts": 2.0,
        "double_plays": 1.0,
    }
    event_score = (
        float(weights["singles"]) * stats["singles"]
        + float(weights["doubles"]) * stats["doubles"]
        + float(weights["triples"]) * stats["triples"]
        + float(weights["home_runs"]) * stats["home_runs"]
        + float(weights["walks"]) * stats["walks"]
        + float(weights["hit_by_pitch"]) * stats["hit_by_pitch"]
        + float(weights["stolen_bases"]) * stats["stolen_bases"]
        + float(weights["strikeouts"]) * stats["strikeouts"]
        + float(weights["double_play"]) * stats["double_plays"]
    )
    pa_approx = stats["at_bats"] + stats["walks"] + stats["hit_by_pitch"]
    rate = event_score / pa_approx * float(config["plate_appearance_normalizer"])
    standardized = float(config["standardized_center"]) + float(
        config["standardized_scale"]
    ) * (
        (rate - float(config["reference_mean"])) / float(config["reference_sd"])
    )
    lower_clip, upper_clip = (float(value) for value in config["clip"])  # type: ignore[union-attr]
    expected = float(np.clip(standardized, lower_clip, upper_clip))

    actual = batter_game_performance_index(**stats)
    assert actual == pytest.approx(expected, abs=1e-12)


def test_batter_zero_pa_uses_zero_rate_then_standardizes() -> None:
    value = batter_game_performance_index(
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


def test_batter_index_applies_both_clip_bounds() -> None:
    upper = batter_game_performance_index(
        at_bats=1,
        singles=0,
        doubles=0,
        triples=0,
        home_runs=20,
        walks=0,
        hit_by_pitch=0,
        stolen_bases=0,
        strikeouts=0,
        double_plays=0,
    )
    lower = batter_game_performance_index(
        at_bats=1,
        singles=0,
        doubles=0,
        triples=0,
        home_runs=0,
        walks=0,
        hit_by_pitch=0,
        stolen_bases=0,
        strikeouts=0,
        double_plays=20,
    )

    assert upper == DEFAULT_BATTER_INDEX_CONFIG.upper_clip
    assert lower == DEFAULT_BATTER_INDEX_CONFIG.lower_clip


def test_batter_config_rejects_invalid_scaling_metadata() -> None:
    with pytest.raises(ValueError, match="reference_sd must be positive"):
        BatterIndexConfig(reference_sd=0)
    with pytest.raises(ValueError, match="scale must be positive"):
        BatterIndexConfig(scale=0)
    with pytest.raises(ValueError, match="lower_clip must be smaller"):
        BatterIndexConfig(lower_clip=1, upper_clip=1)
    with pytest.raises(ValueError, match="must be finite"):
        BatterIndexConfig(reference_mean=float("nan"))


def test_starter_implementation_matches_frozen_config() -> None:
    config = _read_json(STARTER_CONFIG_PATH)
    weights = config["weights"]
    assert isinstance(weights, dict)

    stats = {
        "outs_recorded": 18.0,
        "strikeouts": 7.0,
        "home_runs_allowed": 1.0,
        "walks_allowed": 2.0,
        "hit_by_pitch_allowed": 1.0,
    }
    expected = float(config["multiplier"]) * (
        float(weights["outs_recorded"]) * stats["outs_recorded"]
        + float(weights["strikeouts"]) * stats["strikeouts"]
        + float(weights["home_runs_allowed"]) * stats["home_runs_allowed"]
        + float(weights["walks_plus_hbp_allowed"])
        * (stats["walks_allowed"] + stats["hit_by_pitch_allowed"])
    )

    actual = starter_game_performance_index(**stats)
    assert actual == pytest.approx(expected, abs=1e-12)


def test_starter_more_outs_improves_index() -> None:
    low = starter_game_performance_index(
        outs_recorded=12,
        strikeouts=3,
        home_runs_allowed=1,
        walks_allowed=2,
        hit_by_pitch_allowed=0,
    )
    high = starter_game_performance_index(
        outs_recorded=18,
        strikeouts=3,
        home_runs_allowed=1,
        walks_allowed=2,
        hit_by_pitch_allowed=0,
    )
    assert high > low


@pytest.mark.parametrize(
    ("prior_sum", "prior_count", "center", "k", "expected"),
    [
        (2400, 2, 1000, 5, 7400 / 7),
        (0, 0, 1000, 5, 1000),
        (2400, 2, 1000, 0, 1200),
        (0, 0, 1000, 0, 1000),
    ],
)
def test_strict_prior_shrunk_mean(
    prior_sum: float,
    prior_count: float,
    center: float,
    k: float,
    expected: float,
) -> None:
    actual = strict_prior_shrunk_mean(
        prior_sum=prior_sum,
        prior_count=prior_count,
        center=center,
        k=k,
    )
    assert actual == pytest.approx(expected, abs=1e-12)


@pytest.mark.parametrize(
    ("prior_count", "k"),
    [(-1, 5), (1, -1)],
)
def test_strict_prior_shrunk_mean_rejects_negative_count_or_k(
    prior_count: float, k: float
) -> None:
    with pytest.raises(ValueError, match="must be non-negative"):
        strict_prior_shrunk_mean(
            prior_sum=0,
            prior_count=prior_count,
            center=1000,
            k=k,
        )
