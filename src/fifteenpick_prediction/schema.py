"""Frozen feature definitions for the V12 study."""

CONVENTIONAL_FEATURES = [
    "elo_diff",
    "prior_win_pct_diff",
    "prior_run_diff_per_game_diff",
    "prior_rank_advantage",
    "bullpen_strength_diff",
    "PS_R20_RA_G_diff",
]

STARTER_INDEX_FEATURES = [
    "K10_starter_value_diff",
    "K10_starter_count_diff",
    "K10_starter_reliability_diff",
    "K10_both_starters_covered",
]

BATTER_INDEX_FEATURES = ["mean", "coverage", "count_mean", "coverage_min"]

ALL_FEATURES = (
    CONVENTIONAL_FEATURES[:5]
    + STARTER_INDEX_FEATURES
    + ["PS_R20_RA_G_diff"]
    + BATTER_INDEX_FEATURES
)
