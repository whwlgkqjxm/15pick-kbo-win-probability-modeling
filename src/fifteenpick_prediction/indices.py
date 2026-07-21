"""Role-specific player-performance indices used by the public pipeline."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class BatterIndexConfig:
    """Frozen scaling constants for the batter performance index."""

    plate_appearance_normalizer: float = 4.2
    reference_mean: float = 0.738432383380831
    reference_sd: float = 0.9411772120687678
    center: float = 1000.0
    scale: float = 250.0
    lower_clip: float = -500.0
    upper_clip: float = 3000.0


DEFAULT_BATTER_INDEX_CONFIG = BatterIndexConfig()

def batter_game_performance_index(
    *,
    at_bats: float,
    singles: float,
    doubles: float,
    triples: float,
    home_runs: float,
    walks: float,
    hit_by_pitch: float,
    stolen_bases: float,
    strikeouts: float,
    double_plays: float,
    config: BatterIndexConfig = DEFAULT_BATTER_INDEX_CONFIG,
) -> float:
    """Calculate the selected standardized batter game-performance index.

    Official event counts are converted to a 4.2-plate-appearance rate and
    standardized against the frozen early-2024 reference distribution.
    """

    pa_approx = float(at_bats) + float(walks) + float(hit_by_pitch)
    event_score = (
        0.50 * singles
        + 0.95 * doubles
        + 1.35 * triples
        + 1.85 * home_runs
        + 0.42 * walks
        + 0.42 * hit_by_pitch
        + 0.22 * stolen_bases
        - 0.08 * strikeouts
        - 0.32 * double_plays
    )
    rate = (
        event_score / pa_approx * config.plate_appearance_normalizer
        if pa_approx > 0
        else 0.0
    )
    standardized = config.center + config.scale * (
        (rate - config.reference_mean) / config.reference_sd
    )
    return float(np.clip(standardized, config.lower_clip, config.upper_clip))


def starter_game_performance_index(
    *,
    outs_recorded: float,
    strikeouts: float,
    home_runs_allowed: float,
    walks_allowed: float,
    hit_by_pitch_allowed: float,
) -> float:
    """Calculate the selected start-only pitcher game-performance index."""

    return float(
        1000.0
        * (
            0.216 * outs_recorded
            + 0.132 * strikeouts
            - 1.565 * home_runs_allowed
            - 0.557 * (walks_allowed + hit_by_pitch_allowed)
        )
    )


def strict_prior_shrunk_mean(
    *, prior_sum: float, prior_count: float, center: float, k: float
) -> float:
    """Return a K-shrunk mean computed only from dates before the target date."""

    if prior_count < 0 or k < 0:
        raise ValueError("prior_count and k must be non-negative")
    denominator = float(prior_count) + float(k)
    if denominator == 0:
        return float(center)
    return float((float(prior_sum) + float(k) * float(center)) / denominator)
