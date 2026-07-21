#!/usr/bin/env python3
"""Refit the player-index ablation on a local modeling dataset."""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from fifteenpick_prediction.metrics import probability_metrics
from fifteenpick_prediction.modeling import build_l2_logistic

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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", required=True, type=Path)
    parser.add_argument(
        "--protocol",
        choices=["cv-selected", "best-development"],
        default="best-development",
    )
    parser.add_argument("--output", required=True, type=Path)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    frame = pd.read_csv(args.data)
    frame["game_date"] = pd.to_datetime(frame["game_date"].astype(str))
    target = "home_win"

    if args.protocol == "best-development":
        c_value = 0.1
        cutoff = pd.Timestamp("2026-03-28")
        train = frame.loc[frame["game_date"] < cutoff].sort_values("game_date").tail(720)
    else:
        c_value = 0.03
        train = frame.loc[frame["game_date"] < pd.Timestamp("2026-03-28")].copy()

    test = frame.loc[
        (frame["game_date"] >= pd.Timestamp("2026-03-28"))
        & (frame["game_date"] <= pd.Timestamp("2026-07-09"))
    ].copy()

    groups = {
        "BASELINE_NO_PLAYER_INDICES": CONVENTIONAL_FEATURES,
        "STARTER_INDEX_ONLY": CONVENTIONAL_FEATURES + STARTER_INDEX_FEATURES,
        "BATTER_INDEX_ONLY": CONVENTIONAL_FEATURES + BATTER_INDEX_FEATURES,
        "BATTER_PLUS_STARTER_INDICES": (
            CONVENTIONAL_FEATURES + STARTER_INDEX_FEATURES + BATTER_INDEX_FEATURES
        ),
    }

    rows = []
    for model_id, features in groups.items():
        model = build_l2_logistic(C=c_value)
        model.fit(train[features], train[target])
        probability = model.predict_proba(test[features])[:, 1]
        rows.append(
            {
                "protocol": args.protocol,
                "model": model_id,
                "feature_count": len(features),
                **probability_metrics(test[target], probability),
            }
        )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(args.output, index=False)
    print(f"wrote {args.output}")


if __name__ == "__main__":
    main()
